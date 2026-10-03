# SPDX-License-Identifier: Apache-2.0
"""Explicit, disposable real-server qualification; never imported by production.

No service starts on import. Real execution requires the separate CI scope gate.
Raw logs/history/SQLite/CAS remain in runner temporary storage. This is graceful,
quiescent test orchestration, not crash recovery or an exactly-once effect claim.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from functools import wraps
from dataclasses import asdict, replace
from datetime import timedelta
import hashlib
from importlib.metadata import version
import json
import logging
import os
from pathlib import Path
import platform
import re
import signal
import socket
import subprocess
import threading
import time
from typing import Any

QUEUE = "opendot-temporal-gate"
SCENARIOS = ("durability_replay", "null", "blocked", "failed_validation", "missing_input")
WORKFLOW_TYPE = "ReferenceGateWorkflow"
ACTIVITY_TYPE = "opendot.synthetic.reference.v1"
ACTIVITY_ID = "opendot-synthetic-reference-v1"
ARCHIVE_SHA = "09a0326a51db84d02735e53542b9ebd8c4758daf47482a9ab0abce15844e60d5"
CHECKSUM_SHA = "cc22cb0df0a9bab358500dce212616e8622b0649df68317d9858867d7dc69bd2"
SDK_SHA = "540761f738bdfe5cb5bd7240b659e116a0b5094b94282aef09b8d8c2d66e9c52"
VERSIONS = {"temporalio": "1.34.0", "nexus-rpc": "1.4.0", "protobuf": "7.36.2",
            "types-protobuf": "7.35.1.20260906", "typing_extensions": "4.16.0",
            "pytest": "9.1.1", "iniconfig": "2.3.0", "packaging": "26.3",
            "pluggy": "1.6.0", "Pygments": "2.21.0"}
OWNERS = {
    "src/opendot_engineering/tool_runtime.py": "7c5011e02b2cf07e5f15ad7854905ce0738271e167b873bad9256a8ed169199c",
    "src/opendot_engineering/core/artifacts.py": "4606b7b11a81044267b30fee332d9b6fd6540d862726a9579655ee27c7d9a883",
    "src/opendot_engineering/core/contracts.py": "9462415baf84668825ad2c8cfc3f4f3df68332f65d1f1f4b301fbf01cf8537ca",
}


class GateRunError(RuntimeError):
    """Only fixed codes escape to the pytest boundary."""


def failure_category(error: BaseException) -> tuple[str, str]:
    """Classify without asking an exception instance (or its metaclass) anything.

    Builtin subclass checks use the actual type, not instance ``__class__``.
    The own fixed-code exception's args and foreign class metadata are read
    through trusted builtin descriptors, bypassing user-defined attributes.
    Failure of even this bounded inspection is a fixed unknown observation.
    """
    try:
        error_type = type(error)
        if error_type is GateRunError:
            from verify_temporal_server_gate import DIAGNOSTIC_GATE_REASONS
            args = BaseException.args.__get__(error, GateRunError)
            if len(args) == 1 and type(args[0]) is str and args[0] in DIAGNOSTIC_GATE_REASONS:
                return "gate_refusal", args[0]
        for base, category, code in (
            (TimeoutError, "timeout_error", "TIMEOUT_ERROR"),
            (ImportError, "dependency_error", "DEPENDENCY_ERROR"),
            (KeyError, "key_error", "KEY_ERROR"),
            (AttributeError, "attribute_error", "ATTRIBUTE_ERROR"),
            (TypeError, "type_error", "TYPE_ERROR"),
            (ValueError, "value_error", "VALUE_ERROR"),
            (OSError, "os_error", "OS_ERROR"),
        ):
            if issubclass(error_type, base):
                return category, code
        namespace = type.__dict__["__dict__"].__get__(error_type)
        module = namespace.get("__module__")
        name = type.__dict__["__name__"].__get__(error_type)
        if (type(module) is str and module.startswith("temporalio.") and type(name) is str
                and name in {"RPCError", "WorkflowFailureError", "ApplicationError", "ActivityError",
                             "NondeterminismError", "WorkflowAlreadyStartedError",
                             "WorkflowContinuedAsNewError"}):
            return "sdk_error", "SDK_ERROR"
    except BaseException:
        pass
    return "unknown_error", "UNKNOWN_ERROR"


def is_interruption(error: BaseException) -> bool:
    # Both operands are real classes and Exception has the trusted builtin
    # metaclass. Never use isinstance(error, Exception): __class__ may be hostile.
    return not issubclass(type(error), Exception)


class DiagnosticState:
    """Bounded enum-only failure observations; never exception messages or repr."""
    def __init__(self, requested_revision: str | None):
        self.requested_revision = requested_revision
        self.phase = "preflight"
        self.primary_failure = None
        self.cleanup_failure = None
        self.audit_failure = None

    def capture(self, error: BaseException, *, slot: str = "primary_failure", phase: str | None = None) -> None:
        category, code = failure_category(error)
        if slot not in {"primary_failure", "cleanup_failure", "audit_failure"}:
            raise GateRunError("UNKNOWN_ERROR")
        if getattr(self, slot) is None:
            setattr(self, slot, {"phase": self.phase if phase is None else phase, "reason_code": code,
                                 "exception_category": category})

    def record(self) -> dict:
        from verify_temporal_server_gate import build_diagnostic
        failed = any((self.primary_failure, self.cleanup_failure, self.audit_failure))
        return build_diagnostic(self.requested_revision, status="FAILED" if failed else "COMPLETE",
                                primary_failure=self.primary_failure, cleanup_failure=self.cleanup_failure,
                                audit_failure=self.audit_failure)

    def write(self, audit: Path) -> None:
        from verify_temporal_server_gate import DIAGNOSTIC_MAX_BYTES
        record = self.record()
        encoded = json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        require(len(encoded) + 1 <= DIAGNOSTIC_MAX_BYTES, "JSON_SIZE")
        write_json(audit / "diagnostic.json", record)


def capture_diagnostic(diagnostic: DiagnosticState, error: BaseException, *, slot: str,
                       phase: str) -> tuple[bool, BaseException | None]:
    """Best-effort observation, separate from saved execution failure state.

    A failed/no-op capture gets at most one fixed UNKNOWN fallback in the same
    slot. If even that slot is unavailable, return an explicit diagnostic gap;
    the caller must not publish a misleading COMPLETE or partial diagnostic.
    This never retries diagnostic publication or inspects the original error.
    """
    capture_error = None
    try:
        diagnostic.capture(error, slot=slot, phase=phase)
    except BaseException as failure:
        capture_error = failure
    try:
        if getattr(diagnostic, slot) is None:
            setattr(diagnostic, slot, {"phase": phase, "reason_code": "UNKNOWN_ERROR",
                                      "exception_category": "unknown_error"})
        return getattr(diagnostic, slot) is not None, capture_error
    except BaseException as failure:
        if capture_error is not None and is_interruption(capture_error):
            return False, capture_error
        if is_interruption(failure):
            return False, failure
        return False, capture_error if capture_error is not None else failure


def require(condition: bool, code: str) -> None:
    if not condition:
        raise GateRunError(code)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def strict_load(path: Path, limit: int = 65536) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    data = path.read_bytes()
    require(0 < len(data) <= limit, "JSON_SIZE")
    return json.loads(data, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(GateRunError("NONFINITE_JSON")))


def write_json(path: Path, value: Any) -> None:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    require(len(data) <= 65536, "JSON_SIZE")
    with path.open("xb") as output:
        output.write(data + b"\n")
    path.chmod(0o600)


def seconds(value: Any) -> int | None:
    if type(value) is timedelta and value.microseconds == 0:
        return value.days * 86400 + value.seconds
    return None


def proto_seconds(value: Any) -> int:
    require(value.nanos == 0, "FRACTIONAL_TIMEOUT")
    return value.seconds


def fixed_command(cli: Path, root: Path) -> list[str]:
    return [str(cli), "server", "start-dev", "--ip", "127.0.0.1", "--port", "7233",
            "--http-port", "7243", "--metrics-port", "9090", "--headless",
            "--db-filename", str(root / "server" / "temporal.sqlite"), "--log-level", "error"]


def child_environment(root: Path) -> dict[str, str]:
    return {"PATH": "/usr/bin:/bin", "HOME": str(root / "home"),
            "XDG_CONFIG_HOME": str(root / "home" / "config"),
            "XDG_CACHE_HOME": str(root / "home" / "cache"),
            "TMPDIR": str(root / "private"), "LANG": "C.UTF-8", "TERM": "dumb"}


def verify_cli(cli: Path) -> dict:
    require(cli.is_absolute() and cli.name == "temporal" and cli.is_file()
            and not cli.is_symlink(), "CLI_FILE")
    receipt = strict_load(cli.parent / "acquisition-receipt.json")
    require(receipt["schema_version"] == "opendot.temporal.cli-acquisition.v1"
            and receipt["cli_version"] == "1.9.1" and receipt["platform"] == "linux-x86_64",
            "CLI_RECEIPT")
    require(receipt["archive"]["sha256"] == ARCHIVE_SHA
            and receipt["archive"]["size_bytes"] == 45298806
            and receipt["checksums"]["sha256"] == CHECKSUM_SHA
            and receipt["checksums"]["size_bytes"] == 836, "CLI_PIN")
    for name in ("temporal", "LICENSE"):
        path = cli.parent / name
        require(path.is_file() and not path.is_symlink(), "CLI_FILE")
        data = path.read_bytes()
        require(sha(data) == receipt["files"][name]["sha256"]
                and len(data) == receipt["files"][name]["size_bytes"], "CLI_FILE_HASH")
    return receipt


def verified_sdk_wheel(report: Path) -> str:
    # pip --require-hashes verifies acquired bytes. Retain its fresh install report;
    # no installed-version label is misrepresented as an acquired wheel hash.
    row = strict_load(report, 2 * 1024 * 1024)
    matches = [item for item in row["install"]
               if item["metadata"]["name"].lower() == "temporalio"]
    require(len(matches) == 1, "SDK_WHEEL_REPORT")
    item = matches[0]
    url = item["download_info"]["url"]
    require(item["metadata"]["version"] == "1.34.0" and type(url) is str
            and url.startswith("https://files.pythonhosted.org/")
            and url.endswith("temporalio-1.34.0-cp310-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"),
            "SDK_WHEEL_REPORT")
    digest = item["download_info"]["archive_info"]["hashes"]["sha256"]
    require(digest == SDK_SHA, "SDK_WHEEL_HASH")
    return digest


def preflight(root: Path, cli: Path, source: Path) -> dict:
    require(os.environ.get("OPENDOT_TEMPORAL_EXECUTE") == "1", "EXECUTION_NOT_ENABLED")
    require(os.environ.get("GITHUB_ACTIONS") == "true", "CI_REQUIRED")
    require(platform.system() == "Linux" and platform.machine() == "x86_64"
            and platform.python_version_tuple()[:2] == ("3", "12"), "PLATFORM")
    expected = os.environ["OPENDOT_TEMPORAL_EXPECTED_REVISION"]
    require(re.fullmatch(r"[0-9a-f]{40}", expected) is not None, "REVISION")
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
    require(actual == expected == os.environ["GITHUB_SHA"], "REVISION")
    require(not subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=all"], cwd=source),
            "DIRTY_SOURCE")
    repo = os.environ["GITHUB_REPOSITORY"]
    run = os.environ["GITHUB_RUN_ID"]
    require(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo) is not None
            and re.fullmatch(r"[1-9][0-9]*", run) is not None
            and os.environ["GITHUB_SERVER_URL"] == "https://github.com", "RUN_IDENTITY")
    require({key: version(key) for key in VERSIONS} == VERSIONS, "DEPENDENCY_VERSION")
    require({key: sha((source / key).read_bytes()) for key in OWNERS} == OWNERS, "OWNER_HASH")
    verify_cli(cli)
    sdk_hash = verified_sdk_wheel(Path(os.environ["OPENDOT_TEMPORAL_PIP_REPORT"]))
    from verify_temporal_server_gate import current_source_digests
    return {"schema_version": "opendot.temporal.server-gate.environment.v1",
            "candidate_revision": actual, "requested_revision": expected,
            "workflow_run_url": f"https://github.com/{repo}/actions/runs/{run}",
            "source_kind": "public_source_checkout", "python_version": platform.python_version(),
            "platform": "linux-x86_64", "versions": VERSIONS,
            "cli_version": "1.9.1", "server_version": None,
            "cli_archive_sha256": ARCHIVE_SHA, "cli_checksums_sha256": CHECKSUM_SHA,
            "sdk_wheel_sha256": sdk_hash, **current_source_digests(source),
            "owner_sha256": OWNERS,
            "server_profile": {"frontend_ip": "127.0.0.1", "grpc_port": 7233,
                               "http_port": 7243, "metrics_port": 9090, "ui_enabled": False,
                               "sqlite_id": "server-db-1", "cas_id": "cas-1",
                               "credentials_supplied": False},
            "preflight_status": "PASS", "preflight_code": "OK"}


class Observations:
    def __init__(self):
        self.counters: list[dict] = []
        self.metadata: list[dict] = []
        self.in_flight = 0
        self.execution_uncertain = False
        self.lock = threading.Lock()

    def count(self, scenario: str, event: str, generation: int) -> None:
        with self.lock:
            self.counters.append({"schema_version": "opendot.temporal.server-gate.counter.v1",
                                  "scenario": scenario, "sequence": len(self.counters) + 1,
                                  "event": event, "runtime_generation": generation,
                                  "handler_binding": "bounded_sum_with_test_counter"})

    def execute_once(self, scenario: str, generation: int, original, *args, **options):
        self.count(scenario, "execute_enter", generation)
        try:
            result = original(*args, **options)
            _, receipt = result
            if receipt.execution_liveness.get("reconciliation_required") is True:
                with self.lock:
                    self.execution_uncertain = True
            return result
        except BaseException:
            # Preserve the exact raised control/other error, while recording that
            # a zero handler count cannot prove an unobserved callable never starts.
            with self.lock:
                self.execution_uncertain = True
            raise

    def total(self, scenario: str, event: str) -> int:
        with self.lock:
            return sum(row["scenario"] == scenario and row["event"] == event for row in self.counters)


class ReferenceGateWorkflow:
    """Trusted finite test consumer; top-level for SDK workflow.run validation.

    Decorators and qualified helper bindings are installed only during checked
    bootstrap. The SDK sandbox is deliberately off for this audited test class;
    no sandbox/hostile-workflow security property is asserted by the gate.
    """
    def __init__(self):
        self.response = None
        self.finished = False

    async def run(self, request: dict[str, Any]) -> dict[str, Any]:
        self.response = await execute_reference(request, task_queue=QUEUE)
        await sdk_workflow.wait_condition(lambda: self.finished)
        return self.response

    def recorded_result(self) -> dict[str, Any] | None:
        return self.response

    def finish(self) -> None:
        self.finished = True


def sdk_types(observed: Observations):
    # Imports only after explicit checked setup. Never ActivityEnvironment/fake Info.
    global sdk_workflow, execute_reference
    from temporalio import activity, workflow as sdk_workflow
    from temporalio.worker import ActivityInboundInterceptor, Interceptor
    from opendot_engineering.adapters.temporal_workflow import execute_reference
    ReferenceGateWorkflow.run = sdk_workflow.run(ReferenceGateWorkflow.run)
    ReferenceGateWorkflow.recorded_result = sdk_workflow.query(name="recorded_result")(
        ReferenceGateWorkflow.recorded_result)
    ReferenceGateWorkflow.finish = sdk_workflow.signal(name="finish")(ReferenceGateWorkflow.finish)
    sdk_workflow.defn(name=WORKFLOW_TYPE, sandboxed=False)(ReferenceGateWorkflow)

    class Capture(Interceptor):
        def __init__(self, scenario: str, generation: int):
            self.scenario, self.generation = scenario, generation

        def intercept_activity(self, next):
            scenario, generation = self.scenario, self.generation

            class Entry(ActivityInboundInterceptor):
                async def execute_activity(self, input):
                    info = activity.info()
                    policy = info.retry_policy
                    observed.count(scenario, "activity_enter", generation)
                    with observed.lock:
                        observed.in_flight += 1
                        observed.metadata.append({
                            "schema_version": "opendot.temporal.server-gate.metadata.v1",
                            "scenario": scenario, "entry_sequence": len(observed.metadata) + 1,
                            "activity_id": info.activity_id, "activity_type": info.activity_type,
                            "namespace": info.namespace, "task_queue": info.task_queue,
                            "workflow_id": info.workflow_id, "workflow_run_id": info.workflow_run_id,
                            "attempt": info.attempt, "is_local": info.is_local,
                            "retry_policy_present": policy is not None,
                            "maximum_attempts": policy.maximum_attempts if policy is not None else None,
                            "start_to_close_seconds": seconds(info.start_to_close_timeout),
                            "schedule_to_close_seconds": seconds(info.schedule_to_close_timeout),
                            "metadata_source": "real_sdk_activity_info"})
                    try:
                        return await self.next.execute_activity(input)
                    finally:
                        with observed.lock:
                            observed.in_flight -= 1
            return Entry(next)

    return ReferenceGateWorkflow, Capture


class Runner:
    dag2_profile = False
    def __init__(self, root: Path, cli: Path, environment: dict, diagnostic: DiagnosticState):
        self.root, self.cli, self.environment = root, cli, environment
        self.diagnostic = diagnostic
        self.diagnostic.phase = "sdk_binding"
        self.observed = Observations()
        self.workflow_class, self.capture_class = sdk_types(self.observed)
        self._initialize_lifecycle(root, cli, environment, diagnostic)
        self.requests = {}
        # Seed all fixture bytes before any worker. The missing-input fixture is
        # seeded in a separate canonical store; its object never exists in cas-1.
        from opendot_engineering.core.artifacts import ArtifactStore
        missing_seed = ArtifactStore(root / "private" / "missing-input-seed")
        for scenario in SCENARIOS:
            target = missing_seed if scenario == "missing_input" else self.store
            ref = target.put_json({"left": 99 if scenario == "missing_input" else 2,
                                   "right": 3, "return_null": scenario == "null"},
                                  producer="synthetic", task_id="input")
            self.requests[scenario] = {"schema_version": "opendot.temporal.request.v1",
                                      "input_ref": {**asdict(ref), "source_refs": []}}

    def _initialize_lifecycle(self, root: Path, cli: Path, environment: dict, diagnostic: DiagnosticState):
        self.root, self.cli, self.environment = root, cli, environment
        self.diagnostic = diagnostic
        self.started = time.monotonic()
        self.deadline = self.started + 180
        self.server = None
        self.server_log = None
        self.client = None
        self.server_rows: list[dict] = []
        self.worker_rows: list[dict] = []
        self.workers: list[dict] = []
        self.histories: list[dict] = []
        self.outcomes: list[dict] = []
        self.pending: dict[str, Any] = {}
        self.responses: dict[str, dict] = {}
        self.replay: dict | None = None
        self.stop_uncertain = False
        self.activity_ever_started = False
        self.diagnostic.phase = "input_seeding"
        from opendot_engineering.core.artifacts import ArtifactStore
        self.store = ArtifactStore(root / "cas")

    async def bounded(self, awaitable, seconds_limit: float, code: str, *, cleanup=False):
        # asyncio.wait does not cancel the owned operation on a deadline. A late
        # shutdown remains unconfirmed; no replacement or force termination follows.
        budget = seconds_limit if cleanup else min(seconds_limit, self.deadline - time.monotonic())
        if self.dag2_profile:
            applicable = self.deadline
            if cleanup and self.cleanup_started is not None:
                applicable = (self.final_stop_deadline if self.final_stop_started is not None
                              else self.cleanup_deadline)
            budget = min(budget, applicable - time.monotonic())
        require(budget > 0, "GATE_DEADLINE")
        task = asyncio.ensure_future(awaitable)
        done, _ = await asyncio.wait({task}, timeout=budget)
        require(task in done, code)
        return task.result()

    def quiescent(self) -> bool:
        return (not self.observed.execution_uncertain and self.observed.in_flight == 0 and not self.pending
                and all(self.observed.total(s, "handler_enter") == self.observed.total(s, "handler_return")
                        for s in SCENARIOS))

    async def start_server(self):
        self.diagnostic.phase = "server_launch"
        require(time.monotonic() < self.deadline, "GATE_DEADLINE")
        require(self.server is None and not self.stop_uncertain, "PREVIOUS_STOP_UNCONFIRMED")
        for port in (7233, 7243, 9090):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.bind(("127.0.0.1", port))
        generation = len(self.server_rows) + 1
        start = time.monotonic()
        self.server_log = (self.root / "private" / f"server-{generation}.log").open("xb")
        self.server = subprocess.Popen(fixed_command(self.cli, self.root),
                                       stdin=subprocess.DEVNULL, stdout=self.server_log,
                                       stderr=subprocess.STDOUT, env=child_environment(self.root))
        row = {"generation": generation, "shutdown_requested_signal": None,
               "graceful_exit_observed": False, "exit_code": None,
               "readiness_seconds": None, "shutdown_seconds": None}
        self.server_rows.append(row)
        if self.dag2_profile:
            self.observed.record("server_start")
        self.diagnostic.phase = "client_connect"
        from temporalio.client import Client
        from temporalio.api.workflowservice.v1 import GetSystemInfoRequest
        self.client = await self.bounded(Client.connect("127.0.0.1:7233", namespace="default",
                                                       identity="opendot-gate-client", lazy=True),
                                         2, "CLIENT_CONNECT")
        self.diagnostic.phase = "server_readiness"
        ready_deadline = min(self.deadline, start + 10)
        while time.monotonic() < ready_deadline:
            require(self.server.poll() is None, "SERVER_EXITED")
            try:
                rpc_budget = min(2, ready_deadline - time.monotonic()) if self.dag2_profile else 2
                require(rpc_budget > 0, "GATE_DEADLINE")
                info = await self.client.workflow_service.get_system_info(
                    GetSystemInfoRequest(), retry=False, timeout=timedelta(seconds=rpc_budget))
            except Exception:
                await asyncio.sleep(.1)
                continue
            require(info.server_version == "1.32.0", "SERVER_VERSION")
            self.environment["server_version"] = info.server_version
            row["readiness_seconds"] = round(time.monotonic() - start, 6)
            # Readiness connects the lazy probe, but Worker requires a client
            # created with lazy=False. Use a fresh public, bounded connection.
            self.diagnostic.phase = "client_connect"
            self.client = await self.bounded(Client.connect("127.0.0.1:7233", namespace="default",
                                                           identity="opendot-gate-client", lazy=False),
                                             2, "CLIENT_CONNECT")
            return
        raise GateRunError("SERVER_READINESS")

    async def stop_server(self):
        if self.server is None:
            return
        self.diagnostic.phase = "server_shutdown"
        require(self.quiescent() and all(w["row"]["public_shutdown_completed"] for w in self.workers),
                "NOT_QUIESCENT")
        row = self.server_rows[-1]
        require(self.server.poll() is None, "SERVER_EXITED")
        start = time.monotonic()
        row["shutdown_requested_signal"] = "SIGINT"
        stop_deadline = start + 8
        if self.dag2_profile:
            require(time.monotonic() < self.final_stop_deadline, "DEADLINE_EXHAUSTED")
            stop_deadline = min(stop_deadline, self.final_stop_deadline)
            self.observed.record("server_stop_requested")
        self.server.send_signal(signal.SIGINT)
        while self.server.poll() is None and time.monotonic() < stop_deadline:
            await asyncio.sleep(.05)
        row["shutdown_seconds"] = round(time.monotonic() - start, 6)
        row["exit_code"] = self.server.poll()
        row["graceful_exit_observed"] = row["exit_code"] == 0
        if not row["graceful_exit_observed"]:
            self.stop_uncertain = True
            raise GateRunError("SERVER_STOP_UNCONFIRMED")
        if self.dag2_profile:
            self.observed.record("server_stop_completed")
        self.server = None
        self.server_log.close()
        self.server_log = None

    async def start_worker(self, kind: str, scenario: str | None = None):
        self.diagnostic.phase = "workflow_worker_start" if kind == "workflow" else "activity_worker_start"
        require(time.monotonic() < self.deadline, "GATE_DEADLINE")
        from temporalio.worker import Worker
        require(not self.stop_uncertain, "PREVIOUS_STOP_UNCONFIRMED")
        generation = len(self.worker_rows) + 1
        kwargs = {"task_queue": QUEUE, "identity": f"opendot-gate-{kind}-worker",
                  "graceful_shutdown_timeout": timedelta(seconds=5),
                  "disable_eager_activity_execution": True}
        executor = None
        if kind == "workflow":
            kwargs.update(workflows=[self.workflow_class], no_remote_activities=True,
                          max_cached_workflows=0, max_concurrent_workflow_tasks=1,
                          max_concurrent_workflow_task_polls=1)
        else:
            require(scenario in SCENARIOS, "SCENARIO")
            self.activity_ever_started = True
            from opendot_engineering.adapters import temporal_activity as production
            from opendot_engineering.tool_runtime import ToolRuntime
            runtime = ToolRuntime()
            def handler(payload):
                self.observed.count(scenario, "handler_enter", generation)
                result = production.bounded_sum(payload)
                self.observed.count(scenario, "handler_return", generation)
                return result
            # Negative fixture only: no changed production declaration or owner.
            spec = (replace(production.SYNTHETIC_SPEC, semantic_validator=lambda _: False)
                    if scenario == "failed_validation" else production.SYNTHETIC_SPEC)
            runtime.register(spec, handler)
            original_execute = runtime.execute
            def execute(*args, **options):
                return self.observed.execute_once(scenario, generation, original_execute, *args, **options)
            runtime.execute = execute
            adapter = production.ReferenceActivity(
                runtime=runtime, store=self.store, tool_id=production.TOOL_ID,
                expected_registration_sha256=production.REGISTRATION_SHA256,
                granted_permissions=frozenset() if scenario == "blocked" else frozenset({"synthetic:read"}),
                expected_namespace="default", expected_task_queue=QUEUE)
            executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="opendot-gate")
            kwargs.update(activities=[adapter.run], activity_executor=executor,
                          max_concurrent_activities=1, max_concurrent_activity_task_polls=1,
                          interceptors=[self.capture_class(scenario, generation)])
        worker = Worker(self.client, **kwargs)
        row = {"generation": generation, "type": kind,
               "public_shutdown_called": False, "public_shutdown_completed": False}
        task = asyncio.create_task(worker.run())
        record = {"worker": worker, "task": task, "row": row, "executor": executor}
        self.worker_rows.append(row)
        self.workers.append(record)
        return record

    async def stop_workers(self):
        self.diagnostic.phase = "worker_shutdown"
        require(self.quiescent(), "NOT_QUIESCENT")
        for entry in reversed(self.workers):
            row = entry["row"]
            if row["public_shutdown_completed"]:
                continue
            # Never invoke shutdown again when a previous call has an unknown result.
            require(not row["public_shutdown_called"], "WORKER_STOP_UNCONFIRMED")
            row["public_shutdown_called"] = True
            dag2 = self.dag2_profile
            stop = self.worker_stop_begin(entry) if dag2 else None
            shutdown_start = time.monotonic()
            try:
                await self.bounded(entry["worker"].shutdown(), 5, "WORKER_STOP_UNCONFIRMED", cleanup=True)
                shutdown_end = time.monotonic()
                await self.bounded(entry["task"], 1, "WORKER_STOP_UNCONFIRMED", cleanup=True)
                run_end = time.monotonic()
            except BaseException:
                self.stop_uncertain = True
                raise
            row["public_shutdown_completed"] = True
            if dag2:
                self.worker_stop_observed(entry, stop, shutdown_start, shutdown_end, run_end)
            if entry["executor"] is not None:
                entry["executor"].shutdown(wait=True)
                if dag2:
                    self.executor_stop_observed(entry, stop)

    async def start_case(self, scenario):
        self.diagnostic.phase = "workflow_submit"
        require(time.monotonic() < self.deadline, "GATE_DEADLINE")
        from temporalio.common import RetryPolicy, WorkflowIDReusePolicy
        handle = await self.bounded(self.client.start_workflow(
            self.workflow_class.run, self.requests[scenario], id="opendot-gate-" + scenario,
            task_queue=QUEUE, execution_timeout=timedelta(seconds=120),
            run_timeout=timedelta(seconds=120), task_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=1),
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
            request_eager_start=False, rpc_timeout=timedelta(seconds=2)), 3, "WORKFLOW_START")
        return self.client.get_workflow_handle(handle.id, run_id=handle.first_execution_run_id)

    async def history(self, handle):
        self.diagnostic.phase = "history_read"
        return await self.bounded(handle.fetch_history(rpc_timeout=timedelta(seconds=2)), 3, "HISTORY_READ")

    async def poll_history(self, handle, predicate, budget):
        limit = min(self.deadline, time.monotonic() + budget)
        while time.monotonic() < limit:
            history = await self.history(handle)
            if predicate(history):
                return history
            await asyncio.sleep(.05)
        raise GateRunError("HISTORY_DEADLINE")

    @staticmethod
    def event_name(event):
        from temporalio.api.enums.v1 import EventType
        return "".join(word.title() for word in EventType.Name(event.event_type).removeprefix("EVENT_TYPE_").split("_"))

    def event_count(self, history, name):
        return sum(self.event_name(event) == name for event in history.events)

    async def response_fields(self, payloads):
        values = await self.client.data_converter.decode(payloads.payloads)
        require(len(values) == 1, "RESPONSE_PAYLOAD")
        value = values[0]
        require(type(value) is dict and set(value) == {"schema_version", "result_ref"}
                and value["schema_version"] == "opendot.temporal.response.v1", "RESPONSE_SCHEMA")
        ref = value["result_ref"]
        return {"response_schema": value["schema_version"], "result_artifact_id": ref["artifact_id"],
                "result_sha256": ref["sha256"], "result_size_bytes": ref["size_bytes"]}

    async def snapshot(self, scenario, phase, handle, history):
        self.diagnostic.phase = "history_project"
        events = []
        for event in history.events:
            name = self.event_name(event)
            attr_name = event.WhichOneof("attributes")
            attr = getattr(event, attr_name)
            if name == "WorkflowExecutionStarted":
                attrs = {"workflow_type": attr.workflow_type.name, "task_queue": attr.task_queue.name,
                         "execution_timeout_seconds": proto_seconds(attr.workflow_execution_timeout),
                         "run_timeout_seconds": proto_seconds(attr.workflow_run_timeout),
                         "task_timeout_seconds": proto_seconds(attr.workflow_task_timeout),
                         "maximum_attempts": attr.retry_policy.maximum_attempts}
            elif name == "ActivityTaskScheduled":
                attrs = {"activity_type": attr.activity_type.name, "activity_id": attr.activity_id,
                         "task_queue": attr.task_queue.name, "maximum_attempts": attr.retry_policy.maximum_attempts,
                         "start_to_close_seconds": proto_seconds(attr.start_to_close_timeout),
                         "schedule_to_close_seconds": proto_seconds(attr.schedule_to_close_timeout)}
            elif name == "ActivityTaskStarted":
                attrs = {"scheduled_event_id": attr.scheduled_event_id, "attempt": attr.attempt,
                         "identity": attr.identity}
            elif name == "ActivityTaskCompleted":
                attrs = {"scheduled_event_id": attr.scheduled_event_id,
                         "started_event_id": attr.started_event_id, **await self.response_fields(attr.result)}
            elif name == "ActivityTaskFailed":
                from temporalio.api.enums.v1 import RetryState
                failure = attr.failure.application_failure_info
                attrs = {"scheduled_event_id": attr.scheduled_event_id,
                         "started_event_id": attr.started_event_id, "failure_type": failure.type,
                         "non_retryable": failure.non_retryable,
                         "retry_state": RetryState.Name(attr.retry_state)}
            elif name == "WorkflowExecutionSignaled":
                attrs = {"signal_name": attr.signal_name}
            elif name == "WorkflowExecutionCompleted":
                require(not attr.new_execution_run_id, "UNEXPECTED_NEW_RUN")
                attrs = await self.response_fields(attr.result)
            elif name == "WorkflowExecutionFailed":
                require(not attr.new_execution_run_id, "UNEXPECTED_NEW_RUN")
                failure = attr.failure
                # Bounded public failure chain projection; messages/details omitted.
                for _ in range(4):
                    if failure.HasField("application_failure_info"):
                        break
                    require(failure.HasField("cause"), "FAILURE_CATEGORY")
                    failure = failure.cause
                attrs = {"failure_type": failure.application_failure_info.type}
            elif name == "WorkflowTaskScheduled":
                attrs = {}
            elif name == "WorkflowTaskStarted":
                attrs = {"scheduled_event_id": attr.scheduled_event_id, "identity": attr.identity}
            elif name == "WorkflowTaskCompleted":
                attrs = {"scheduled_event_id": attr.scheduled_event_id,
                         "started_event_id": attr.started_event_id, "identity": attr.identity}
            else:
                raise GateRunError("UNEXPECTED_HISTORY_EVENT")
            events.append({"event_id": event.event_id, "event_type": name, "attributes": attrs})
        raw = history.to_json().encode()
        require(len(raw) <= 2 * 1024 * 1024, "HISTORY_SIZE")
        private_path = self.root / "private" / f"history-{scenario}-{phase}.json"
        private_path.write_bytes(raw)
        private_path.chmod(0o600)
        row = {"scenario": scenario, "phase": phase, "workflow_id": handle.id,
               "workflow_run_id": handle.run_id, "server_generation": len(self.server_rows),
               "raw_history_sha256": sha(raw), "events": events,
               "counter_sequence": len(self.observed.counters),
               "activity_workers_started": sum(row["type"] == "activity" for row in self.worker_rows),
               "active_activity_calls": self.observed.in_flight}
        self.histories.append(row)
        return row

    def verify_result(self, scenario, response):
        self.diagnostic.phase = "result_verify"
        from opendot_engineering.adapters import temporal_activity as production
        row = response["result_ref"]
        from opendot_engineering.core.contracts import ArtifactRef
        require(type(row) is dict and set(row) == {"artifact_id", "uri", "mime_type", "size_bytes",
            "sha256", "schema_version", "producer", "task_id", "source_refs", "integrity_verified"}, "RESULT_REFERENCE")
        require(row["producer"] == production.RESULT_PRODUCER and row["source_refs"] ==
                [self.requests[scenario]["input_ref"]["artifact_id"]] and row["mime_type"] == "application/json"
                and row["schema_version"] == "1.0.0" and type(row["size_bytes"]) is int
                and 1 <= row["size_bytes"] <= 16384, "RESULT_REFERENCE")
        ref = ArtifactRef(**{**row, "source_refs": tuple(row["source_refs"]), "integrity_verified": False})
        ref.validate()
        data = self.store.get_bytes(ref)
        require(sha(data) == ref.sha256 and len(data) == ref.size_bytes, "CAS_INTEGRITY")
        from opendot_engineering.adapters.source_audit import _decode
        document = _decode(data)
        require(set(document) == {"schema_version", "profile", "input_ref", "output", "receipt_report",
                                  "observation_provenance", "scientific_validity", "device_control_authority",
                                  "independent_review", "owner_integration"}, "RESULT_SCHEMA")
        require(document["schema_version"] == "opendot.temporal.result.v1"
                and document["profile"] == production.PROFILE
                and document["observation_provenance"] == "serialized_runtime_report_not_live_proof",
                "RESULT_SCHEMA")
        require(document["input_ref"] == {**self.requests[scenario]["input_ref"], "integrity_verified": True},
                "RESULT_INPUT_REFERENCE")
        report = document["receipt_report"]
        require(type(report) is dict and set(report) == {"call_id", "tool_id", "tool_version", "status", "attempts",
            "latency_s", "input_hash", "output_hash", "semantic_valid", "error_type", "breaker_state",
            "execution_observation", "execution_liveness"}, "RESULT_RECEIPT_SCHEMA")
        require(report["call_id"] == row["task_id"] and re.fullmatch(r"[0-9a-f]{24}", report["call_id"]) is not None
                and report["tool_id"] == production.TOOL_ID and report["tool_version"] == "1",
                "RESULT_RECEIPT_IDENTITY")
        output = document["output"]
        require(output is None or type(output) is int and -2_000_000 <= output <= 2_000_000,
                "RESULT_OUTPUT_PROFILE")
        return {"scenario": scenario, "workflow_transport_status": "COMPLETED",
                "activity_transport_status": "COMPLETED", "result_ref_present": True,
                "result_artifact_id": ref.artifact_id, "cas_digest_verified": True,
                "cas_size_verified": True, "result_schema_verified": True,
                "tool_status": report["status"], "semantic_valid": report["semantic_valid"],
                "output_kind": "null" if output is None else "integer", "output_integer": output,
                "runtime_receipt_attempts": report["attempts"],
                "execute_count": self.observed.total(scenario, "execute_enter"),
                "handler_count": self.observed.total(scenario, "handler_enter"),
                "scientific_validity": document["scientific_validity"],
                "device_control_authority": document["device_control_authority"],
                "independent_review": document["independent_review"],
                "owner_integration": document["owner_integration"],
                "test_only_validator_fault": scenario == "failed_validation"}

    async def queried_result(self, handle, budget=10):
        self.diagnostic.phase = "result_query"
        limit = min(self.deadline, time.monotonic() + budget)
        while time.monotonic() < limit:
            result = await self.bounded(handle.query("recorded_result", rpc_timeout=timedelta(seconds=2)),
                                        3, "QUERY_DEADLINE")
            if result is not None:
                return result
            await asyncio.sleep(.05)
        raise GateRunError("QUERY_NOT_READY")

    async def observe_activity_terminal(self, scenario, handle, budget=15):
        history = await self.poll_history(handle, lambda h: self.event_count(h, "ActivityTaskCompleted")
                                         + self.event_count(h, "ActivityTaskFailed") == 1, budget)
        require(self.observed.in_flight == 0, "ACTIVITY_NOT_QUIESCENT")
        self.pending.pop(scenario, None)
        return history

    async def finish_case(self, handle):
        self.diagnostic.phase = "workflow_signal"
        await self.bounded(handle.signal("finish", rpc_timeout=timedelta(seconds=2)), 3, "SIGNAL_DEADLINE")
        self.diagnostic.phase = "workflow_result"
        return await self.bounded(handle.result(follow_runs=False, rpc_timeout=timedelta(seconds=2)),
                                  10, "WORKFLOW_RESULT")

    async def run_cases(self):
        await self.start_server()
        await self.start_worker("workflow")
        scenario = "durability_replay"
        handle = await self.start_case(scenario)
        queued = await self.poll_history(handle, lambda h: self.event_count(h, "ActivityTaskScheduled") == 1, 10)
        queued_deadline = time.monotonic() + 45
        self.deadline = min(self.deadline, queued_deadline)
        require(not self.activity_ever_started and not self.observed.counters, "QUEUED_COUNTERS")
        require(not any(self.event_name(e).startswith("ActivityTask") and self.event_name(e) != "ActivityTaskScheduled"
                        for e in queued.events), "QUEUED_ACTIVITY_STARTED")
        before = await self.snapshot(scenario, "queued_before_restart", handle, queued)
        await self.stop_workers()
        await self.stop_server()
        await self.start_server()
        handle = self.client.get_workflow_handle(handle.id, run_id=handle.run_id)
        queued_again = await self.history(handle)
        after = await self.snapshot(scenario, "queued_after_restart", handle, queued_again)
        require(before["events"] == after["events"] and not self.observed.counters
                and not self.activity_ever_started, "QUEUED_DURABILITY")
        await self.start_worker("workflow")
        self.pending[scenario] = handle
        await self.start_worker("activity", scenario)
        complete = await self.observe_activity_terminal(scenario, handle)
        response = await self.queried_result(handle)
        recorded = await self.snapshot(scenario, "activity_result_recorded", handle, complete)
        require(self.event_count(complete, "ActivityTaskCompleted") == 1, "ACTIVITY_COMPLETION")
        self.verify_result(scenario, response)
        before_handler_count = self.observed.total(scenario, "handler_enter")
        before_counter_sequence = len(self.observed.counters)
        require(time.monotonic() <= queued_deadline, "QUEUED_PHASE_DEADLINE")
        self.deadline = self.started + 180
        await self.stop_workers()
        await self.stop_server()
        await self.start_server()
        replay_worker = await self.start_worker("workflow")
        activity_online_at_live_replay = any(w["row"]["type"] == "activity"
            and not w["row"]["public_shutdown_completed"] for w in self.workers)
        handle = self.client.get_workflow_handle(handle.id, run_id=handle.run_id)
        replay_query = await self.queried_result(handle)
        require(replay_query == response, "REPLAY_REFERENCE")
        after_live_count = self.observed.total(scenario, "handler_enter")
        after_live_sequence = len(self.observed.counters)
        workflow_response = await self.finish_case(handle)
        require(workflow_response == response, "WORKFLOW_REFERENCE")
        terminal = await self.history(handle)
        terminal_row = await self.snapshot(scenario, "workflow_completed_after_replay", handle, terminal)
        self.diagnostic.phase = "sdk_replay"
        from temporalio.worker import Replayer
        replay_result = await self.bounded(Replayer(workflows=[self.workflow_class]).replay_workflow(
            terminal, raise_on_replay_failure=True), 10, "SDK_REPLAY")
        require(replay_result.replay_failure is None, "SDK_REPLAY")
        # The same actual history object above is persisted, hashed and passed to Replayer.
        require(sha(terminal.to_json().encode()) == terminal_row["raw_history_sha256"], "REPLAY_HISTORY_HASH")
        self.outcomes.append(self.verify_result(scenario, workflow_response))
        completion = next(e for e in recorded["events"] if e["event_type"] == "ActivityTaskCompleted")
        later = next(e for e in terminal_row["events"] if e["event_type"] == "ActivityTaskCompleted")
        self.replay = {"schema_version": "opendot.temporal.server-gate.replay.v1", "scenario": scenario,
                       "workflow_run_id": handle.run_id, "recorded_completion_event_id": completion["event_id"],
                       "same_completion_event_after_restart": completion == later,
                       "before_result_artifact_id": response["result_ref"]["artifact_id"],
                       "after_query_result_artifact_id": replay_query["result_ref"]["artifact_id"],
                       "workflow_result_artifact_id": workflow_response["result_ref"]["artifact_id"],
                       "fresh_workflow_worker": replay_worker["row"]["generation"] == 4
                           and all(w["row"]["public_shutdown_completed"] for w in self.workers[:-1]),
                       "activity_worker_present_during_replay": activity_online_at_live_replay
                           or any(w["row"]["type"] == "activity" and not w["row"]["public_shutdown_completed"]
                                  for w in self.workers),
                       "activity_schedule_count_before": self.event_count(complete, "ActivityTaskScheduled"),
                       "activity_schedule_count_after": self.event_count(terminal, "ActivityTaskScheduled"),
                       "handler_count_before": before_handler_count,
                       "counter_sequence_before": before_counter_sequence,
                       "counter_sequence_after_live_replay": after_live_sequence,
                       "counter_sequence_after_sdk_replay": len(self.observed.counters),
                       "handler_count_after_live_replay": after_live_count,
                       "handler_count_after_sdk_replay": self.observed.total(scenario, "handler_enter"),
                       "raw_history_sha256": terminal_row["raw_history_sha256"],
                       "sdk_replay_failure": None, "cas_reverified": True}
        await self.stop_workers()
        for scenario in SCENARIOS[1:]:
            await self.start_worker("workflow")
            # Mark potentially dispatched work before starting its sole worker.
            handle = await self.start_case(scenario)
            self.pending[scenario] = handle
            await self.start_worker("activity", scenario)
            await self.observe_activity_terminal(scenario, handle)
            if scenario == "missing_input":
                from temporalio.client import WorkflowFailureError
                failed = False
                try:
                    self.diagnostic.phase = "workflow_result"
                    await self.bounded(handle.result(follow_runs=False, rpc_timeout=timedelta(seconds=2)),
                                       10, "WORKFLOW_RESULT")
                except WorkflowFailureError:
                    failed = True
                require(failed, "TRANSPORT_FAILURE_EXPECTED")
                self.outcomes.append({"scenario": scenario, "workflow_transport_status": "FAILED",
                    "activity_transport_status": "FAILED", "result_ref_present": False,
                    "result_artifact_id": None, "cas_digest_verified": None, "cas_size_verified": None,
                    "result_schema_verified": None, "tool_status": None, "semantic_valid": None,
                    "output_kind": None, "output_integer": None, "runtime_receipt_attempts": None,
                    "execute_count": self.observed.total(scenario, "execute_enter"),
                    "handler_count": self.observed.total(scenario, "handler_enter"),
                    "scientific_validity": None, "device_control_authority": None,
                    "independent_review": None, "owner_integration": None, "test_only_validator_fault": False})
            else:
                response = await self.queried_result(handle)
                result = await self.finish_case(handle)
                require(result == response, "WORKFLOW_REFERENCE")
                self.outcomes.append(self.verify_result(scenario, result))
            await self.snapshot(scenario, "terminal", handle, await self.history(handle))
            await self.stop_workers()

    async def cleanup(self):
        # On failure, only observe already submitted work. Never redispatch,
        # cancel a Workflow/Activity, stop an in-flight call, or force a process.
        cleanup_deadline = time.monotonic() + 40
        while (not self.quiescent() and time.monotonic() < cleanup_deadline
               and not self.stop_uncertain and not self.observed.execution_uncertain):
            for scenario, handle in tuple(self.pending.items()):
                try:
                    history = await self.bounded(handle.fetch_history(rpc_timeout=timedelta(seconds=2)),
                                                 3, "CLEANUP_HISTORY", cleanup=True)
                    terminal = sum(self.event_count(history, name) for name in
                                   ("ActivityTaskCompleted", "ActivityTaskFailed", "ActivityTaskTimedOut"))
                    if terminal == 1 and self.observed.in_flight == 0:
                        self.pending.pop(scenario)
                except Exception:
                    pass
            if not self.quiescent():
                await asyncio.sleep(.1)
        if self.quiescent() and not self.stop_uncertain:
            try:
                await self.stop_workers()
                await self.stop_server()
            except Exception:
                self.stop_uncertain = True
        status = self.quiescent() and not self.stop_uncertain and self.server is None
        return {"schema_version": "opendot.temporal.server-gate.cleanup.v1",
                "server_generations": self.server_rows, "worker_generations": self.worker_rows,
                "all_activity_calls_observed_terminal": self.quiescent(),
                "same_sqlite_across_restarts": True, "same_cas_across_restarts": True,
                "in_flight_shutdown_attempted": False, "forced_termination_used": False,
                "cleanup_status": "PASS" if status else "UNCONFIRMED",
                "cleanup_code": "OK" if status else "CLEANUP_UNCONFIRMED",
                "elapsed_seconds": round(time.monotonic() - self.started, 6)}

    def write_audit(self, cleanup):
        """Existing bounded evidence writers; called once, never used as a retry."""
        audit = self.root / "audit"
        write_json(audit / "environment.json", self.environment)
        write_json(audit / "history-projection.json", {
            "schema_version": "opendot.temporal.server-gate.history.v1", "snapshots": self.histories})
        write_json(audit / "outcomes.json", {
            "schema_version": "opendot.temporal.server-gate.outcomes.v1", "scenarios": self.outcomes})
        if cleanup is not None:
            write_json(audit / "cleanup.json", cleanup)
        if self.replay is not None:
            write_json(audit / "replay.json", self.replay)
        for name, rows in (("activity-metadata.jsonl", self.observed.metadata),
                           ("invocation-counters.jsonl", self.observed.counters)):
            require(len(rows) <= 256, "JSONL_SIZE")
            encoded = b"".join(json.dumps(r, separators=(",", ":"), allow_nan=False).encode() + b"\n" for r in rows)
            require(len(encoded) <= 256 * 1024, "JSONL_SIZE")
            (audit / name).write_bytes(encoded)
            (audit / name).chmod(0o600)

    async def execute(self):
        cleanup = None
        primary_error = cleanup_error = audit_error = None
        primary_phase = cleanup_phase = None
        # Preserve actual failures and their phases independently of diagnostic
        # storage. In particular, no diagnostic capture can bypass cleanup.
        try:
            try:
                await self.run_cases()
            except BaseException as error:
                primary_error = error
                primary_phase = self.diagnostic.phase
        finally:
            try:
                self.diagnostic.phase = "cleanup"
                cleanup = await self.cleanup()
                if cleanup["cleanup_status"] != "PASS":
                    cleanup_error = GateRunError("CLEANUP_UNCONFIRMED")
                    cleanup_phase = "cleanup"
            except BaseException as error:
                cleanup_error = error
                cleanup_phase = self.diagnostic.phase
            finally:
                try:
                    self.diagnostic.phase = "audit_write"
                    self.write_audit(cleanup)
                except BaseException as error:
                    audit_error = error

        failures = ((primary_error, "primary_failure", primary_phase),
                    (cleanup_error, "cleanup_failure", cleanup_phase),
                    (audit_error, "audit_failure", "audit_write"))
        # Real execution interruptions precede faults in later observation.
        interrupted = next((error for error, _, _ in failures
                            if error is not None and is_interruption(error)), None)
        diagnostic_gap = False
        for error, slot, phase in failures:
            if error is not None:
                recorded, capture_error = capture_diagnostic(self.diagnostic, error, slot=slot, phase=phase)
                diagnostic_gap = diagnostic_gap or not recorded
                if (interrupted is None and capture_error is not None
                        and is_interruption(capture_error)):
                    interrupted = capture_error

        # One separate small record survives independent audit refusal when the
        # safe job-local directory is writable. A known recording gap leaves no
        # diagnostic rather than claiming completion or inventing a lost cause.
        # No write is retried, including after an uncertain partial publication.
        write_error = None
        if not diagnostic_gap:
            try:
                self.diagnostic.write(self.root / "audit")
            except BaseException as error:
                write_error = error
        if interrupted is not None:
            raise interrupted
        if write_error is not None:
            raise write_error
        require(not diagnostic_gap and all(error is None for error, _, _ in failures),
                "SERVER_GATE_FAILED")
        return {"environment": self.environment, "histories": self.histories,
                "metadata": self.observed.metadata, "counters": self.observed.counters,
                "outcomes": self.outcomes, "replay": self.replay, "cleanup": cleanup}


def run_gate(root: Path, cli: Path, collected_nodes: list[str]) -> dict:
    source = Path(__file__).resolve().parents[1]
    require(root.is_absolute() and not root.exists(), "FRESH_GATE_ROOT_REQUIRED")
    temp = Path(os.environ["RUNNER_TEMP"]).resolve()
    require(root.parent.resolve() == temp, "RUNNER_TEMP_REQUIRED")
    root.mkdir(mode=0o700)
    for name in ("server", "cas", "private", "audit", "home"):
        (root / name).mkdir(mode=0o700)
    write_json(root / "audit" / "collection-receipt.json", {
        "schema_version": "opendot.temporal.server-gate.collection.v1", "nodes": collected_nodes})
    # Revision is a bounded requested identity, never an assertion that preflight
    # succeeded. Invalid/missing configuration stays null in a failed diagnostic.
    requested = os.environ.get("OPENDOT_TEMPORAL_EXPECTED_REVISION")
    requested = requested if type(requested) is str and re.fullmatch(r"[0-9a-f]{40}", requested) else None
    diagnostic = DiagnosticState(requested)
    loop = None
    runner = None
    try:
        if requested is None:
            # Missing/unusable identity is a real bootstrap refusal, never a
            # guessed candidate revision in the diagnostic record.
            raise KeyError("OPENDOT_TEMPORAL_EXPECTED_REVISION")
        logging.basicConfig(filename=root / "private" / "sdk.log", level=logging.ERROR, force=True)
        environment = preflight(root, cli, source)
        loop = asyncio.new_event_loop()
        runner = Runner(root, cli, environment, diagnostic)
        return loop.run_until_complete(runner.execute())
    except Exception as error:
        # Only bootstrap failures belong here. Runner.execute owns its saved
        # primary failure and single diagnostic attempt, even when capture fails.
        if runner is None:
            recorded, capture_error = capture_diagnostic(diagnostic, error, slot="primary_failure",
                                                         phase=diagnostic.phase)
            if recorded and not (root / "audit" / "diagnostic.json").exists():
                diagnostic.write(root / "audit")
            if capture_error is not None and is_interruption(capture_error):
                raise capture_error
        raise GateRunError("SERVER_GATE_FAILED") from None
    finally:
        # Do not cancel unresolved Worker operations on an unconfirmed shutdown.
        if loop is not None and not asyncio.all_tasks(loop):
            loop.close()


# Shared test-only finite admission. Fixture and explicitly selected live consumers
# use this one reservation/acknowledgment/terminal owner. No production imports it.
def admission_locked(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return call


class BatchAdmission:
    """Single-producer finite fixture bookkeeping, not a scheduler or runtime.

    Only validated original results release capacity. This harness never invokes
    an escaped submit callback again. Callback-internal transport retries are
    outside this fixture. Uncertainty is sticky even after late observations.
    """
    def __init__(self, plan: dict, profile: dict):
        import verify_temporal_server_gate as verifier
        self._verifier = verifier
        self._plan = verifier.validate_batch_plan(plan)
        self._profile = verifier.validate_batch_profile(profile)
        # Whole-fixture admission occurs before any individual callback/factory.
        self._budget = {"reserved_job_allowance": 200, "reserved_attempt_allowance": 200,
                        "reserved_output_allowance_bytes": 200 * 16384}
        self._states = {job["job_id"]: {"reserved": False, "run_id": None,
                       "validated_terminal": False, "uncertain": False}
                        for job in self._plan["jobs"]}
        self._next = 0
        self._attempts = 0
        self._outstanding = 0
        self._peak_outstanding = 0
        self._uncertain = False
        self._reasons: set[str] = set()
        self._outcomes: dict[str, dict] = {}
        self._run_ids: set[str] = set()
        self._receipt_ids: set[str] = set()
        self._result_ids: set[str] = set()
        self._inside_submit = False
        self._owner_thread = threading.get_ident()
        self._submission_mode = None
        self._async_loop = None
        self._async_producer = None
        self._pending_start = None
        self._lock = threading.RLock()
        self._live_observer = None
        self._recording_failed = False

    def bind_live_observer(self, observer):
        self._check_owner()
        with self._lock:
            require(self._next == 0 and self._live_observer is None, "BATCH_ADMISSION_STOPPED")
            self._live_observer = observer

    def _emit(self, event, job_id, run_id=None):
        if self._live_observer is not None:
            try:
                self._live_observer._record_locked(event, job_id, run_id=run_id)
            except BaseException:
                self._recording_failed = self._uncertain = True
                self._reasons.add("OBSERVER_FAILURE")
                raise

    def _call_submission(self, submit, job):
        with self._lock:
            require(not self._uncertain, "BATCH_ADMISSION_STOPPED")
        # Callbacks run outside the lock. The live callback separately guards its
        # actual public-client entry, immediately before constructing its awaitable.
        return submit(job)

    @admission_locked
    def snapshot(self) -> dict:
        self._check_owner(mutation=False)
        return {**self._budget, "attempts_consumed": self._attempts,
                "outstanding": self._outstanding, "peak_outstanding": self._peak_outstanding,
                "unsubmitted": 200 - self._next,
                "validated_terminal": sum(s["validated_terminal"] for s in self._states.values()),
                "uncertainty_latched": self._uncertain, "reasons": sorted(self._reasons),
                "submission_mode": self._submission_mode,
                "start_observation_pending": self._pending_start is not None,
                "jobs": {key: dict(value) for key, value in self._states.items()}}

    @admission_locked
    def mark_uncertain(self, job_id: str | None, reason: str) -> None:
        if self._live_observer is None:
            self._check_owner()
        was_uncertain = self._uncertain
        # Latch before validating observer arguments: observer failures themselves
        # must not leave admission open. Unknown identities affect all outstanding.
        self._uncertain = True
        if type(reason) is not str or reason not in self._verifier.BATCH_UNCERTAINTY_REASONS:
            reason = "OBSERVER_FAILURE"
        self._reasons.add(reason)
        if type(job_id) is str and job_id in self._states and self._states[job_id]["reserved"]:
            self._states[job_id]["uncertain"] = True
        else:
            for state in self._states.values():
                if state["reserved"] and not state["validated_terminal"]:
                    state["uncertain"] = True
        if self._live_observer is not None and not was_uncertain:
            try:
                self._live_observer._record_locked("uncertainty", job_id, reason_code=reason)
            except BaseException:
                self._recording_failed = True
                self._reasons.add("OBSERVER_FAILURE")

    def _job(self, job_id: str) -> dict:
        require(type(job_id) is str and job_id in self._states, "BATCH_JOB_ID")
        return self._plan["jobs"][int(job_id[-3:])]

    def _check_owner(self, *, mutation: bool = True) -> None:
        require(threading.get_ident() == self._owner_thread, "BATCH_OWNER_THREAD")
        if mutation and self._async_loop is not None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                raise GateRunError("BATCH_OWNER_LOOP") from None
            require(loop is self._async_loop, "BATCH_OWNER_LOOP")

    def _claim_submission(self, mode: str):
        self._check_owner()
        require(self._submission_mode in (None, mode), "BATCH_SUBMISSION_MODE")
        if mode == "async":
            loop = asyncio.get_running_loop()
            producer = asyncio.current_task()
            require(producer is not None, "BATCH_PRODUCER_TASK")
            require(self._async_loop in (None, loop)
                    and self._async_producer in (None, producer), "BATCH_PRODUCER_TASK")
            self._async_loop, self._async_producer = loop, producer
        self._submission_mode = mode

    @admission_locked
    def _reserve_submission(self, mode: str) -> dict | None:
        """The only attempt/window reservation implementation, before callback entry."""
        self._claim_submission(mode)
        require(not self._uncertain and not self._inside_submit
                and self._pending_start is None, "BATCH_ADMISSION_STOPPED")
        if self._next == 200 or self._outstanding == 16:
            return None
        job = self._plan["jobs"][self._next]
        self._states[job["job_id"]]["reserved"] = True
        self._next += 1
        self._attempts += 1
        self._outstanding += 1
        self._peak_outstanding = max(self._peak_outstanding, self._outstanding)
        self._inside_submit = True
        self._emit("reservation", job["job_id"])
        return {**job, "payload": dict(job["payload"])}

    def _settle_submission_ack(self, job_id: str, acknowledgment: dict) -> None:
        """The only start-ack binding path for synchronous, async and late results."""
        require(type(acknowledgment) is dict
                and acknowledgment.get("job_id") == job_id, "BATCH_ACK_BINDING")
        self.acknowledge(acknowledgment)

    def _submission_uncertain(self, job_id: str | None, error: BaseException) -> None:
        reason = ("UNKNOWN_ACK" if issubclass(type(error), asyncio.CancelledError) else
                  "TIMEOUT" if issubclass(type(error), TimeoutError) else "RPC_EXCEPTION")
        self.mark_uncertain(job_id, reason)

    def submit_next(self, submit) -> str | None:
        """Retained synchronous fixture wrapper over the shared reservation core."""
        job = self._reserve_submission("sync")
        if job is None:
            return None
        job_id = job["job_id"]
        try:
            self._settle_submission_ack(job_id, self._call_submission(submit, job))
        except BaseException as error:
            self._submission_uncertain(job_id, error)
            if is_interruption(error):
                raise
            raise GateRunError("BATCH_RPC_UNCERTAIN") from None
        finally:
            self._inside_submit = False
        return job_id

    async def _await_start_result(self, awaitable):
        return await awaitable

    def _observe_async_start(self, record: dict) -> None:
        """One-time observation of the single retained operation, including late ack.

        No callback reinvocation, replacement task or capacity release occurs here. Reading
        result() also observes a late failure instead of leaking an unhandled task
        exception. The awaiting producer still receives control cancellation.
        """
        self._check_owner()
        if record["settled"] or not record["task"].done():
            return
        record["settled"] = True
        task, job_id = record["task"], record["job_id"]
        try:
            acknowledgment = task.result()
            if task.cancelling():
                record["cancelled"] = True
                self.mark_uncertain(job_id, "UNKNOWN_ACK")
            self._settle_submission_ack(job_id, acknowledgment)
        except BaseException as error:
            record["failed"] = True
            record["cancelled"] = issubclass(type(error), asyncio.CancelledError)
            self._submission_uncertain(job_id, error)
        finally:
            if self._pending_start is record:
                self._pending_start = None

    async def submit_next_async(self, submit, *, start_timeout: float | None = None) -> str | None:
        """Bounded cooperative bootstrap: one loop, producer and shielded start.

        Invocation of this async function only creates a coroutine; reservation
        occurs when its body starts. An unstarted cancelled task issues no RPC.
        The v1 fabricated trace ordering is not a live causality contract.
        Cooperative callbacks must start work only when invoked; this cannot
        retroactively reserve an operation the caller already launched.
        """
        self._claim_submission("async")
        producer = self._async_producer
        if producer.cancelling():
            self.mark_uncertain(None, "UNKNOWN_ACK")
            raise asyncio.CancelledError
        job = self._reserve_submission("async")
        if job is None:
            return None
        job_id, record = job["job_id"], None
        try:
            # Reserve before calling the callback, not merely before its await.
            awaitable = self._call_submission(submit, job)
            require(asyncio.isfuture(awaitable) or asyncio.iscoroutine(awaitable),
                    "BATCH_START_AWAITABLE")
            if asyncio.isfuture(awaitable):
                # A completed foreign-loop Future otherwise may await successfully.
                require(awaitable.get_loop() is self._async_loop
                        and awaitable is not producer, "BATCH_OWNER_LOOP")
            task = (awaitable if isinstance(awaitable, asyncio.Task) else
                    self._async_loop.create_task(self._await_start_result(awaitable)))
            record = {"job_id": job_id, "task": task, "settled": False,
                      "failed": False, "cancelled": False}
            self._pending_start = record
            task.add_done_callback(lambda _done: self._observe_async_start(record))
            if producer.cancelling():
                self.mark_uncertain(job_id, "UNKNOWN_ACK")
                raise asyncio.CancelledError
            if start_timeout is not None:
                require(0 < start_timeout <= 3, "WORKFLOW_START")
                done, _ = await asyncio.wait({task}, timeout=start_timeout)
                if task not in done:
                    raise TimeoutError
            await asyncio.shield(task)
            self._observe_async_start(record)
            # Awaiting a done Future or swallowed cancellation need not raise.
            if producer.cancelling() or record["cancelled"]:
                self.mark_uncertain(job_id, "UNKNOWN_ACK")
                raise asyncio.CancelledError
            require(not record["failed"], "BATCH_RPC_UNCERTAIN")
            return job_id
        except BaseException as error:
            self._submission_uncertain(job_id, error)
            if record is not None:
                self._observe_async_start(record)
            if is_interruption(error):
                raise
            raise GateRunError("BATCH_RPC_UNCERTAIN") from None
        finally:
            self._inside_submit = False

    @admission_locked
    def acknowledge(self, row: dict) -> None:
        self._check_owner()
        job_id = row.get("job_id") if type(row) is dict else None
        try:
            self._verifier._batch_encoded(row, 512)
            self._verifier.shape(row, "job_id workflow_id run_id")
            job = self._job(job_id)
            state = self._states[job_id]
            require(state["reserved"], "BATCH_UNRESERVED_ACK")
            require(state["run_id"] is None, "BATCH_DUPLICATE_ACK")
            self._verifier.exact(row["workflow_id"], job["workflow_id"])
            self._verifier.match(row["run_id"],
                r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
            require(row["run_id"] not in self._run_ids, "BATCH_DUPLICATE_RUN")
            state["run_id"] = row["run_id"]
            self._run_ids.add(row["run_id"])
            self._emit("acknowledgment", job_id, row["run_id"])
        except BaseException as error:
            self.mark_uncertain(job_id, "UNKNOWN_ACK")
            if is_interruption(error):
                raise
            raise GateRunError("BATCH_ACK_UNCERTAIN") from None

    @admission_locked
    def record_outcome(self, row: dict) -> None:
        """Record the independently checked original projection; release nothing.

        The later terminal must match these exact bindings. This is fixture-only;
        real CAS/receipt extraction and received-metadata wiring remain unapproved.
        """
        self._check_owner()
        job_id = row.get("job_id") if type(row) is dict else None
        try:
            job = self._job(job_id)
            state = self._states[job_id]
            require(state["reserved"] and state["run_id"] is not None, "BATCH_UNRESERVED_RESULT")
            checked = self._verifier.validate_batch_terminal(row, job, state["run_id"])
            require(job_id not in self._outcomes and checked["receipt_id"] not in self._receipt_ids
                    and checked["result_artifact_id"] not in self._result_ids, "BATCH_DUPLICATE_RESULT")
            self._outcomes[job_id] = checked
            self._receipt_ids.add(checked["receipt_id"])
            self._result_ids.add(checked["result_artifact_id"])
            if not self._verifier.batch_terminal_accepted(checked):
                self.mark_uncertain(job_id, "RECONCILIATION_REQUIRED"
                                    if checked["reconciliation_required"] else "INVALID_TERMINAL")
        except BaseException as error:
            self.mark_uncertain(job_id, "INVALID_TERMINAL")
            if is_interruption(error):
                raise
            raise GateRunError("BATCH_RESULT_UNCERTAIN") from None

    @admission_locked
    def observe_terminal(self, row: dict) -> bool:
        self._check_owner()
        job_id = row.get("job_id") if type(row) is dict else None
        try:
            job = self._job(job_id)
            state = self._states[job_id]
            require(state["reserved"] and state["run_id"] is not None
                    and not state["validated_terminal"], "BATCH_DUPLICATE_TERMINAL")
            checked = self._verifier.validate_batch_terminal(row, job, state["run_id"])
            require(job_id in self._outcomes, "BATCH_ORIGINAL_RESULT_MISSING")
            self._verifier.exact(checked, self._outcomes[job_id], "OUTCOME_MISMATCH")
            if not self._verifier.batch_terminal_accepted(checked):
                self.mark_uncertain(job_id, "INVALID_TERMINAL")
                return False
            state["validated_terminal"] = True
            self._outstanding -= 1
            self._emit("validated_terminal", job_id, state["run_id"])
            # The global and per-job uncertainty latches are never cleared.
            return True
        except BaseException as error:
            self.mark_uncertain(job_id, "INVALID_TERMINAL")
            if is_interruption(error):
                raise
            raise GateRunError("BATCH_TERMINAL_UNCERTAIN") from None


def batch_worker_arguments(plan: dict, profile: dict) -> dict:
    """Pure external Worker/executor kwargs; the existing serial Runner is untouched."""
    import verify_temporal_server_gate as verifier
    verifier.validate_batch_plan(plan)
    verifier.validate_batch_profile(profile)
    return {
        "executor": {"max_workers": 8, "thread_name_prefix": "opendot-batch-fixture"},
        "activity": {"task_queue": QUEUE, "max_concurrent_activities": 8,
                     "max_concurrent_activity_task_polls": 1,
                     "disable_eager_activity_execution": True},
        "workflow": {"task_queue": QUEUE, "no_remote_activities": True,
                     "max_cached_workflows": 0, "max_concurrent_workflow_tasks": 1,
                     "max_concurrent_workflow_task_polls": 1,
                     "disable_eager_activity_execution": True},
    }


def build_batch_factory_fixture(plan: dict, profile: dict, *, executor_factory, worker_factory) -> dict:
    """Exercise only explicitly supplied test factories; never run/start workers.

    No default factories or SDK imports exist. Entire preflight precedes the first
    callback. Hosted bootstrap/lifecycle must be separately reviewed and wired.
    """
    arguments = batch_worker_arguments(plan, profile)
    executor = executor_factory(**arguments["executor"])
    return {"executor": executor,
            "activity": worker_factory(kind="activity", activity_executor=executor, **arguments["activity"]),
            "workflow": worker_factory(kind="workflow", **arguments["workflow"])}


# Real-service evidence is deliberately separate from fabricated preparation.
_BATCH_INVOCATION = ContextVar("opendot_batch_invocation", default=None)
BATCH_WORKFLOW_TYPE = "ReferenceBatchWorkflow"


class BatchObservations:
    """One monotonic stream, sharing the admission owner's stop/reserve lock.

    Thread-side faults latch the owner immediately. Clock samples and sequence
    allocation happen under this same brief lock; no desired-order sorting occurs.
    """
    def __init__(self, admission, requests, *, clock=time.monotonic_ns):
        self.admission, self.requests, self.clock = admission, requests, clock
        self.lock = admission._lock
        self.origin = clock()
        self.counters, self.metadata = [], []
        self.identities, self.originals, self.responses = {}, {}, {}
        self.in_flight = 0
        self.execution_uncertain = False
        self.observation_uncertain = False
        self._phases = {}
        admission.bind_live_observer(self)

    def _record_locked(self, event, job_id, *, run_id=None, invocation=None, reason_code="OK"):
        import verify_temporal_server_gate as verifier
        try:
            require(len(self.counters) < 4096, "JSONL_SIZE")
            elapsed = (self.clock() - self.origin) // 1000
            require(elapsed >= 0 and (not self.counters or elapsed >= self.counters[-1]["elapsed_us"]),
                    "BATCH_CLOCK")
            if event == "acknowledgment" and job_id in self.identities:
                require(run_id == self.identities[job_id][1], "BATCH_ACK_BINDING")
            row = {"sequence": len(self.counters) + 1, "elapsed_us": elapsed,
                   "event": event, "job_id": job_id, "run_id": run_id,
                   "activity_id": None, "attempt": None, "reason_code": reason_code}
            if invocation is not None:
                row.update(run_id=invocation[1], activity_id=invocation[2], attempt=invocation[3])
            verifier._batch_encoded(row, 1024)
            self.counters.append(row)
            return row
        except BaseException:
            self.observation_uncertain = True
            self.admission._uncertain = self.admission._recording_failed = True
            self.admission._reasons.add("OBSERVER_FAILURE")
            raise

    def uncertain(self, job_id, reason, *, execution=False):
        with self.lock:
            if execution:
                self.execution_uncertain = True
            else:
                self.observation_uncertain = True
            self.admission.mark_uncertain(job_id, reason)

    def _identity(self):
        identity = _BATCH_INVOCATION.get()
        require(type(identity) is tuple and len(identity) == 4, "BATCH_CONTEXT")
        job_id = next((job for job, value in self.identities.items() if value == identity), None)
        require(job_id is not None, "BATCH_CONTEXT")
        return job_id, identity

    def enter_activity(self, info, request):
        import verify_temporal_server_gate as verifier
        job_id = None
        try:
            with self.lock:
                jobs = self.admission._plan["jobs"]
                job = next((j for j in jobs if j["workflow_id"] == info.workflow_id), None)
                require(job is not None, "BATCH_JOB_ID")
                job_id = job["job_id"]
                state = self.admission._states[job_id]
                require(state["reserved"] and any(r["job_id"] == job_id and r["event"] == "rpc_enter"
                                                    for r in self.counters), "BATCH_UNRESERVED_RESULT")
                require(job_id not in self.identities and self.in_flight < 8, "BATCH_DUPLICATE_RUN")
                require(request == self.requests[job_id], "RESULT_INPUT_REFERENCE")
                policy = info.retry_policy
                row = {"job_id": job_id, "entry_sequence": len(self.counters) + 1,
                       "workflow_id": info.workflow_id, "run_id": info.workflow_run_id,
                       "activity_id": info.activity_id, "activity_type": info.activity_type,
                       "namespace": info.namespace, "task_queue": info.task_queue,
                       "attempt": info.attempt, "is_local": info.is_local,
                       "retry_policy_present": policy is not None,
                       "maximum_attempts": policy.maximum_attempts if policy is not None else None,
                       "start_to_close_seconds": seconds(info.start_to_close_timeout),
                       "schedule_to_close_seconds": seconds(info.schedule_to_close_timeout),
                       "input_artifact_id": request["input_ref"]["artifact_id"],
                       "metadata_source": "real_sdk_activity_info"}
                verifier.validate_real_batch_metadata(row, job, state["run_id"])
                identity = (info.workflow_id, info.workflow_run_id, info.activity_id, info.attempt)
                require(identity not in self.identities.values(), "BATCH_DUPLICATE_RUN")
                self.identities[job_id] = identity
                self._phases[job_id] = "activity_enter"
                self._record_locked("activity_enter", job_id, invocation=identity)
                self.metadata.append(row)
                self.in_flight += 1
                return identity
        except BaseException:
            self.uncertain(job_id, "OBSERVER_FAILURE")
            raise

    def phase(self, event, expected, *, payload=None):
        job_id = None
        try:
            with self.lock:
                job_id, identity = self._identity()
                require(self._phases[job_id] == expected, "BATCH_CONTEXT")
                if payload is not None:
                    require(payload == self.admission._job(job_id)["payload"], "RESULT_INPUT_REFERENCE")
                self._record_locked(event, job_id, invocation=identity)
                self._phases[job_id] = event
                return job_id, identity
        except BaseException:
            self.uncertain(job_id, "OBSERVER_FAILURE")
            raise

    def error_phase(self, job_id, event):
        # Preserve the original exception even if observing it fails. Missing
        # error edges leave an explicit observation gap and cannot make a pass.
        with self.lock:
            expected = {"handler_error": {"handler_enter"},
                        "execute_error": {"execute_enter", "handler_return", "handler_error"},
                        "activity_error": {"activity_enter", "execute_return", "execute_error"}}
            try:
                require(job_id in self.identities and self._phases[job_id] in expected[event], "BATCH_CONTEXT")
                self._record_locked(event, job_id, invocation=self.identities[job_id], reason_code="RUNTIME_EXCEPTION")
                self._phases[job_id] = event
            except BaseException:
                self.observation_uncertain = True
                self.admission._recording_failed = self.admission._uncertain = True
                self.admission._reasons.add("OBSERVER_FAILURE")

    def handler(self, original, payload):
        job_id, _ = self.phase("handler_enter", "execute_enter", payload=payload)
        try:
            output = original(payload)
            require(type(output) is int and output == 199, "RESULT_OUTPUT_PROFILE")
            self.phase("handler_return", "handler_enter")
            return output
        except BaseException:
            self.error_phase(job_id, "handler_error")
            self.uncertain(job_id, "RUNTIME_EXCEPTION", execution=True)
            raise

    def execute_once(self, original, *args, **options):
        job_id, _ = self.phase("execute_enter", "activity_enter", payload=args[1] if len(args) > 1 else None)
        try:
            output, receipt = original(*args, **options)
            from opendot_engineering.tool_runtime import ToolCallReceipt
            require(type(receipt) is ToolCallReceipt, "RESULT_RECEIPT_IDENTITY")
            require(receipt.execution_liveness.get("reconciliation_required") is not True,
                    "BATCH_LIVENESS")
            # Retain the actual original object and immutable-value snapshot. No
            # live-proof reconstruction, private dispatch call or native probe.
            snapshot = asdict(receipt)
            snapshot["breaker_state"] = receipt.breaker_state.value
            with self.lock:
                require(job_id not in self.originals, "BATCH_DUPLICATE_RESULT")
                self.originals[job_id] = (output, receipt, snapshot)
            self.phase("execute_return", "handler_return")
            return output, receipt
        except BaseException:
            self.error_phase(job_id, "execute_error")
            self.uncertain(job_id, "RUNTIME_EXCEPTION", execution=True)
            raise

    def exit_activity(self, identity, response, success):
        job_id = next((job for job, value in self.identities.items() if value == identity), None)
        try:
            with self.lock:
                require(job_id is not None and self.in_flight > 0, "BATCH_CONTEXT")
                if success:
                    require(self._phases[job_id] == "execute_return", "BATCH_CONTEXT")
                    self.responses[job_id] = response
                    self._record_locked("activity_exit", job_id, invocation=identity)
                    self._phases[job_id] = "activity_exit"
                else:
                    self.error_phase(job_id, "activity_error")
                    self.uncertain(job_id, "RUNTIME_EXCEPTION", execution=True)
                self.in_flight -= 1
        except BaseException:
            self.uncertain(job_id, "OBSERVER_FAILURE")
            raise

    def workflow_result(self, job_id, run_id):
        with self.lock:
            self._record_locked("workflow_result", job_id, run_id=run_id)

    def total(self, event):
        with self.lock:
            return sum(row["event"] == event for row in self.counters)


class ReferenceBatchWorkflow:
    async def run(self, request: dict[str, Any]) -> dict[str, Any]:
        return await execute_reference(request, task_queue=QUEUE)


def batch_sdk_types(observed):
    global execute_reference
    from temporalio import activity, workflow
    from temporalio.worker import ActivityInboundInterceptor, Interceptor
    from opendot_engineering.adapters.temporal_workflow import execute_reference
    if not getattr(ReferenceBatchWorkflow, "_opendot_decorated", False):
        ReferenceBatchWorkflow.run = workflow.run(ReferenceBatchWorkflow.run)
        workflow.defn(name=BATCH_WORKFLOW_TYPE, sandboxed=False)(ReferenceBatchWorkflow)
        ReferenceBatchWorkflow._opendot_decorated = True

    class Capture(Interceptor):
        def intercept_activity(self, next):
            class Entry(ActivityInboundInterceptor):
                async def execute_activity(self, input):
                    try:
                        info = activity.info()
                        require(type(info) is activity.Info and len(input.args) == 1, "BATCH_CONTEXT")
                        identity = observed.enter_activity(info, input.args[0])
                    except BaseException:
                        observed.uncertain(None, "OBSERVER_FAILURE")
                        raise
                    token = _BATCH_INVOCATION.set(identity)
                    try:
                        try:
                            response = await self.next.execute_activity(input)
                        except BaseException:
                            try:
                                observed.exit_activity(identity, None, False)
                            except BaseException:
                                observed.uncertain(None, "OBSERVER_FAILURE")
                            raise
                        observed.exit_activity(identity, response, True)
                        return response
                    finally:
                        _BATCH_INVOCATION.reset(token)
            return Entry(next)
    return ReferenceBatchWorkflow, Capture


def write_batch_json(path, value, limit):
    from verify_temporal_server_gate import _real_encoded
    # Canonical strict plain-value/size checking precedes the one write attempt.
    data = _real_encoded(value, limit - 1)
    with path.open("xb") as output:
        output.write(data + b"\n")
    path.chmod(0o600)


class BatchRunner(Runner):
    """Finite, explicitly selected real-service consumer of the shared owner."""
    def __init__(self, root, cli, environment, diagnostic):
        import verify_temporal_server_gate as verifier
        self._initialize_lifecycle(root, cli, environment, diagnostic)
        self.plan = verifier.frozen_batch_plan()
        self.profile = verifier.validate_batch_profile(dict(verifier.BATCH_PROFILE))
        self.admission = BatchAdmission(self.plan, self.profile)
        self.requests = {}
        for job in self.plan["jobs"]:
            ref = self.store.put_json(job["payload"], producer="synthetic", task_id="input")
            require(ref.artifact_id == job["input_artifact_id"] and ref.size_bytes == job["input_size_bytes"],
                    "RESULT_INPUT_REFERENCE")
            self.requests[job["job_id"]] = {"schema_version": "opendot.temporal.request.v1",
                                          "input_ref": {**asdict(ref), "source_refs": []}}
        self.observed = BatchObservations(self.admission, self.requests)
        self.diagnostic.phase = "sdk_binding"
        self.workflow_class, self.capture_class = batch_sdk_types(self.observed)
        self.handles, self.result_operations = {}, {}
        self._observer_started = set()
        self.source_sha256 = verifier.real_batch_source_digests(Path(__file__).resolve().parents[1])

    async def start_worker(self, kind, scenario=None):
        self.diagnostic.phase = "workflow_worker_start" if kind == "workflow" else "activity_worker_start"
        require(time.monotonic() < self.deadline and not self.stop_uncertain, "GATE_DEADLINE")
        require(kind in ("workflow", "activity") and not any(row["type"] == kind for row in self.worker_rows),
                "BATCH_WORKER")
        from temporalio.worker import Worker
        arguments = batch_worker_arguments(self.plan, self.profile)
        kwargs = {**arguments[kind], "identity": f"opendot-gate-{kind}-worker",
                  "graceful_shutdown_timeout": timedelta(seconds=5)}
        executor = None
        if kind == "workflow":
            kwargs["workflows"] = [self.workflow_class]
        else:
            from opendot_engineering.adapters import temporal_activity as production
            from opendot_engineering.tool_runtime import ToolRuntime
            self.activity_ever_started = True
            runtime = ToolRuntime()
            runtime.register(production.SYNTHETIC_SPEC,
                             lambda payload: self.observed.handler(production.bounded_sum, payload))
            original = runtime.execute
            runtime.execute = lambda *args, **options: self.observed.execute_once(original, *args, **options)
            adapter = production.ReferenceActivity(runtime=runtime, store=self.store, tool_id=production.TOOL_ID,
                expected_registration_sha256=production.REGISTRATION_SHA256,
                granted_permissions=frozenset({"synthetic:read"}), expected_namespace="default",
                expected_task_queue=QUEUE)
            executor = ThreadPoolExecutor(**arguments["executor"])
            kwargs.update(activities=[adapter.run], activity_executor=executor,
                          interceptors=[self.capture_class()])
        worker = Worker(self.client, **kwargs)
        row = {"generation": len(self.worker_rows) + 1, "type": kind,
               "public_shutdown_called": False, "public_shutdown_completed": False}
        task = asyncio.create_task(worker.run())
        record = {"worker": worker, "task": task, "row": row, "executor": executor}
        self.worker_rows.append(row)
        self.workers.append(record)
        return record

    async def _submit(self, job):
        from temporalio.common import RetryPolicy, WorkflowIDReusePolicy
        # This is the sole high-level application start. Public SDK defaults may
        # retry transport internally. No physical RPC/packet count is claimed.
        with self.admission._lock:
            require(not self.admission._uncertain, "BATCH_ADMISSION_STOPPED")
            self.admission._emit("rpc_enter", job["job_id"])
            operation = self.client.start_workflow(self.workflow_class.run, self.requests[job["job_id"]],
                id=job["workflow_id"], task_queue=QUEUE, execution_timeout=timedelta(seconds=120),
                run_timeout=timedelta(seconds=120), task_timeout=timedelta(seconds=10),
                retry_policy=RetryPolicy(maximum_attempts=1), id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
                request_eager_start=False, rpc_timeout=timedelta(seconds=2))
        handle = await operation
        pinned = self.client.get_workflow_handle(handle.id, run_id=handle.first_execution_run_id)
        require(pinned.id == job["workflow_id"] and pinned.run_id is not None, "BATCH_ACK_BINDING")
        self.handles[job["job_id"]] = pinned
        return {"job_id": job["job_id"], "workflow_id": pinned.id, "run_id": pinned.run_id}

    async def _read_operation(self, job_id, awaitable):
        # Retain the actual read task past any timeout. Do not cancel it or replace
        # it with a new read to manufacture a clean event loop or favorable result.
        task = asyncio.create_task(awaitable)
        require(job_id not in self.result_operations, "BATCH_RESULT_OPERATION")
        self.result_operations[job_id] = task
        try:
            return await asyncio.shield(task)
        finally:
            if task.done():
                self.result_operations.pop(job_id, None)

    def original_result(self, job, run_id, response):
        from opendot_engineering.adapters import temporal_activity as production
        from opendot_engineering.core.contracts import ArtifactRef
        from opendot_engineering.adapters.source_audit import _decode
        def same_json(left, right):
            return json.dumps(left, sort_keys=True, separators=(",", ":"), allow_nan=False) == json.dumps(
                right, sort_keys=True, separators=(",", ":"), allow_nan=False)
        require(type(response) is dict and set(response) == {"schema_version", "result_ref"}
                and response["schema_version"] == "opendot.temporal.response.v1", "RESPONSE_SCHEMA")
        row = response["result_ref"]
        require(type(row) is dict and set(row) == {"artifact_id", "uri", "mime_type", "size_bytes",
            "sha256", "schema_version", "producer", "task_id", "source_refs", "integrity_verified"},
            "RESULT_REFERENCE")
        require(row["producer"] == production.RESULT_PRODUCER and row["source_refs"] == [job["input_artifact_id"]]
                and row["mime_type"] == "application/json" and row["schema_version"] == "1.0.0"
                and type(row["size_bytes"]) is int and 1 <= row["size_bytes"] <= 16384
                and type(row["integrity_verified"]) is bool, "RESULT_REFERENCE")
        ref = ArtifactRef(**{**row, "source_refs": tuple(row["source_refs"]), "integrity_verified": False})
        ref.validate()
        require(ref.artifact_id == "sha256:" + ref.sha256 and ref.uri == "artifact://sha256/" + ref.sha256,
                "RESULT_REFERENCE")
        data = self.store.get_bytes(ref, max_bytes=16384)
        require(sha(data) == ref.sha256 and len(data) == ref.size_bytes, "CAS_INTEGRITY")
        document = _decode(data)
        require(type(document) is dict and set(document) == {"schema_version", "profile", "input_ref", "output",
            "receipt_report", "observation_provenance", "scientific_validity", "device_control_authority",
            "independent_review", "owner_integration"}, "RESULT_SCHEMA")
        require(document["schema_version"] == "opendot.temporal.result.v1" and document["profile"] == production.PROFILE
                and document["observation_provenance"] == "serialized_runtime_report_not_live_proof"
                and same_json(document["input_ref"], {**self.requests[job["job_id"]]["input_ref"], "integrity_verified": True}),
                "RESULT_INPUT_REFERENCE")
        with self.observed.lock:
            identity = self.observed.identities[job["job_id"]]
            require(identity == (job["workflow_id"], run_id, ACTIVITY_ID, 1)
                    and self.observed._phases[job["job_id"]] == "activity_exit"
                    and same_json(response, self.observed.responses[job["job_id"]]), "BATCH_CONTEXT")
            output, receipt, snapshot = self.observed.originals[job["job_id"]]
            current = asdict(receipt)
            current["breaker_state"] = receipt.breaker_state.value
            require(same_json(current, snapshot) and same_json(document["receipt_report"], snapshot), "RESULT_RECEIPT_IDENTITY")
        report = document["receipt_report"]
        require(report["call_id"] == row["task_id"] and re.fullmatch(r"[0-9a-f]{24}", report["call_id"]) is not None
                and report["tool_id"] == production.TOOL_ID and report["tool_version"] == "1"
                and report["input_hash"] == job["input_artifact_id"].removeprefix("sha256:")
                and report["output_hash"] == sha(b"199") and report["status"] == "COMPLETED"
                and type(report["attempts"]) is int and report["attempts"] == 1
                and report["semantic_valid"] is True and report["error_type"] is None
                and report["execution_liveness"].get("reconciliation_required") is not True
                and type(output) is int and type(document["output"]) is int and output == document["output"] == 199, "RESULT_RECEIPT_IDENTITY")
        require(document["scientific_validity"] is False and document["device_control_authority"] is False
                and document["independent_review"] == document["owner_integration"] == "NOT_EVALUATED", "RESULT_SCHEMA")
        terminal = {"job_id": job["job_id"], "workflow_id": job["workflow_id"], "run_id": run_id,
            "activity_id": ACTIVITY_ID, "invocation_id": "inv-" + job["job_id"][-3:], "attempt": 1,
            "receipt_id": report["call_id"], "input_artifact_id": job["input_artifact_id"],
            "result_artifact_id": ref.artifact_id, "result_input_artifact_id": document["input_ref"]["artifact_id"],
            "result_size_bytes": ref.size_bytes, "tool_status": report["status"], "semantic_valid": True,
            "output": output, "reconciliation_required": False, "transport_status": "COMPLETED"}
        return {"terminal": terminal, "original_validation": "CAS_RECEIPT_INPUT_BOUND",
            "receipt_report_kind": "serialized_runtime_report_not_live_proof",
            "scientific_validity": False, "device_control_authority": False,
            "independent_review": "NOT_EVALUATED", "owner_integration": "NOT_EVALUATED"}

    async def real_history(self, job, handle, history, terminal):
        import verify_temporal_server_gate as verifier
        require(history.workflow_id == job["workflow_id"], "BATCH_HISTORY_IDENTITY")
        require(len(history.events) <= 64, "HISTORY_SIZE")
        raw = history.to_json().encode()
        require(0 < len(raw) <= 65536, "HISTORY_SIZE")
        events = []
        for event in history.events:
            name = self.event_name(event)
            attr = getattr(event, event.WhichOneof("attributes"))
            if name == "WorkflowExecutionStarted":
                values = await self.client.data_converter.decode(attr.input.payloads)
                require(values == [self.requests[job["job_id"]]], "RESULT_INPUT_REFERENCE")
                require(not attr.continued_execution_run_id and attr.original_execution_run_id == handle.run_id
                        and attr.first_execution_run_id == handle.run_id and attr.attempt == 1
                        and attr.workflow_id == job["workflow_id"],
                        "UNEXPECTED_NEW_RUN")
                attrs = {"workflow_type": attr.workflow_type.name, "task_queue": attr.task_queue.name,
                    "execution_timeout_seconds": proto_seconds(attr.workflow_execution_timeout),
                    "run_timeout_seconds": proto_seconds(attr.workflow_run_timeout),
                    "task_timeout_seconds": proto_seconds(attr.workflow_task_timeout),
                    "maximum_attempts": attr.retry_policy.maximum_attempts,
                    "workflow_id": attr.workflow_id, "original_execution_run_id": attr.original_execution_run_id,
                    "first_execution_run_id": attr.first_execution_run_id, "attempt": attr.attempt,
                    "continued_execution_run_id": attr.continued_execution_run_id}
            elif name == "ActivityTaskScheduled":
                values = await self.client.data_converter.decode(attr.input.payloads)
                require(values == [self.requests[job["job_id"]]], "RESULT_INPUT_REFERENCE")
                attrs = {"activity_type": attr.activity_type.name, "activity_id": attr.activity_id,
                    "task_queue": attr.task_queue.name, "maximum_attempts": attr.retry_policy.maximum_attempts,
                    "start_to_close_seconds": proto_seconds(attr.start_to_close_timeout),
                    "schedule_to_close_seconds": proto_seconds(attr.schedule_to_close_timeout)}
            elif name == "ActivityTaskStarted":
                attrs = {"scheduled_event_id": attr.scheduled_event_id, "attempt": attr.attempt,
                         "identity": attr.identity}
            elif name in {"ActivityTaskCompleted", "WorkflowExecutionCompleted"}:
                values = await self.client.data_converter.decode(attr.result.payloads)
                require(values == [self.responses[job["job_id"]]], "WORKFLOW_REFERENCE")
                if name == "WorkflowExecutionCompleted":
                    require(not attr.new_execution_run_id, "UNEXPECTED_NEW_RUN")
                    attrs = await self.response_fields(attr.result)
                else:
                    attrs = {"scheduled_event_id": attr.scheduled_event_id, "started_event_id": attr.started_event_id,
                             **await self.response_fields(attr.result)}
            elif name == "WorkflowTaskScheduled":
                attrs = {}
            elif name == "WorkflowTaskStarted":
                attrs = {"scheduled_event_id": attr.scheduled_event_id, "identity": attr.identity}
            elif name == "WorkflowTaskCompleted":
                attrs = {"scheduled_event_id": attr.scheduled_event_id, "started_event_id": attr.started_event_id,
                         "identity": attr.identity}
            else:
                raise GateRunError("UNEXPECTED_HISTORY_EVENT")
            events.append({"event_id": event.event_id, "event_type": name, "attributes": attrs})
        row = {"job_id": job["job_id"], "workflow_id": handle.id, "run_id": handle.run_id,
               "raw_history_sha256": sha(raw), "raw_history_bytes": len(raw), "events": events}
        verifier.validate_real_batch_history(row, job, handle.run_id, terminal)
        require(sum(r["raw_history_bytes"] for r in self.histories) + len(raw) <= 16 * 1024 * 1024, "HISTORY_SIZE")
        path = self.root / "private" / ("history-" + job["job_id"] + ".json")
        with path.open("xb") as target:
            target.write(raw)
        path.chmod(0o600)
        return row

    async def _observe_result(self, job_id):
        job, handle = self.admission._job(job_id), self.handles[job_id]
        try:
            response = await self._read_operation(job_id, handle.result(follow_runs=False,
                                                                       rpc_timeout=timedelta(seconds=2)))
            self.observed.workflow_result(job_id, handle.run_id)
            self.responses[job_id] = response
            outcome = self.original_result(job, handle.run_id, response)
            history = await self._read_operation(job_id, handle.fetch_history(rpc_timeout=timedelta(seconds=2)))
            projected = await self.real_history(job, handle, history, outcome["terminal"])
            self.histories.append(projected)
            self.outcomes.append(outcome)
            self.admission.record_outcome(outcome["terminal"])
            self.admission.observe_terminal(outcome["terminal"])
        except BaseException:
            self.admission.mark_uncertain(job_id, "INVALID_TERMINAL")
            raise

    def _ensure_observers(self):
        for job_id in self.handles:
            state = self.admission._states[job_id]
            if state["run_id"] is not None and not state["validated_terminal"] and job_id not in self._observer_started:
                require(len(self.pending) < 16, "BATCH_RESULT_OPERATION")
                self._observer_started.add(job_id)
                self.pending[job_id] = asyncio.create_task(self._observe_result(job_id))

    def _consume_done(self):
        for job_id, task in tuple(self.pending.items()):
            if task.done():
                self.pending.pop(job_id)
                task.result()

    async def run_cases(self):
        await self.start_server()
        await self.start_worker("workflow")
        await self.start_worker("activity")
        while self.admission.snapshot()["validated_terminal"] < 200:
            self._ensure_observers()
            self._consume_done()
            state = self.admission.snapshot()
            require(not state["uncertainty_latched"], "BATCH_ADMISSION_STOPPED")
            require(time.monotonic() < self.deadline, "GATE_DEADLINE")
            if state["unsubmitted"] and state["outstanding"] < 16:
                self.diagnostic.phase = "workflow_submit"
                await self.admission.submit_next_async(self._submit, start_timeout=min(3, self.deadline - time.monotonic()))
                continue
            require(bool(self.pending), "BATCH_RESULT_OPERATION")
            done, _ = await asyncio.wait(tuple(self.pending.values()),
                timeout=max(0, self.deadline - time.monotonic()), return_when=asyncio.FIRST_COMPLETED)
            require(bool(done), "GATE_DEADLINE")
        self._consume_done()

    def quiescent(self):
        state = self.admission.snapshot()
        return (not state["start_observation_pending"] and not self.pending and not self.result_operations
            and all(not s["reserved"] or s["validated_terminal"] for s in state["jobs"].values())
            and not self.observed.execution_uncertain and not self.observed.observation_uncertain
            and not self.admission._recording_failed and self.observed.in_flight == 0
            and self.observed.total("handler_enter") == self.observed.total("handler_return"))

    async def cleanup(self):
        if not self.quiescent():
            self.admission.mark_uncertain(None, "TRANSPORT_LOSS")
        deadline = time.monotonic() + 40
        while not self.quiescent() and time.monotonic() < deadline and not self.stop_uncertain:
            self._ensure_observers()
            for job_id, task in tuple(self.pending.items()):
                if task.done():
                    self.pending.pop(job_id)
                    try:
                        task.result()
                    except BaseException as error:
                        if is_interruption(error):
                            raise
                        # Observe ordinary invalid outcomes without repeating reads.
                        pass
            # Invalid outcomes cannot be validated by rereading/retrying. Unknown
            # executable liveness likewise cannot become clean through timeout.
            if self.observed.execution_uncertain or self.observed.observation_uncertain:
                break
            tasks = list(self.pending.values())
            start = self.admission._pending_start
            if start is not None:
                tasks.append(start["task"])
            if not tasks:
                break
            await asyncio.wait(tasks, timeout=max(0, deadline - time.monotonic()),
                               return_when=asyncio.FIRST_COMPLETED)
        if self.quiescent() and not self.stop_uncertain:
            try:
                await self.stop_workers()
                await self.stop_server()
            except Exception:
                self.stop_uncertain = True
        state = self.admission.snapshot()
        status = self.quiescent() and not self.stop_uncertain and self.server is None
        return {"schema_version": "opendot.temporal.real-batch.cleanup.v1",
            "server_generations": self.server_rows, "worker_generations": self.worker_rows,
            "all_reservations_accounted": all(not s["reserved"] or s["validated_terminal"] for s in state["jobs"].values()),
            "unresolved_start_operations": int(state["start_observation_pending"]),
            "unresolved_result_operations": sum(not task.done() for task in self.result_operations.values()),
            "active_activity_calls": self.observed.in_flight,
            "handler_entries": self.observed.total("handler_enter"), "handler_returns": self.observed.total("handler_return"),
            "execution_uncertainty": self.observed.execution_uncertain,
            "observation_uncertainty": self.observed.observation_uncertain or self.admission._recording_failed,
            "in_flight_shutdown_attempted": False, "forced_termination_used": False,
            "cleanup_status": "PASS" if status else "UNCONFIRMED", "cleanup_code": "OK" if status else "CLEANUP_UNCONFIRMED",
            "elapsed_seconds": round(time.monotonic() - self.started, 6)}

    def trace(self):
        import verify_temporal_server_gate as verifier
        return {"schema_version": "opendot.temporal.real-batch.trace.v1", "evidence_kind": "HOSTED_REAL_SERVICE",
            "revision": self.environment["candidate_revision"], "source_sha256": self.source_sha256,
            "clock_scope": "HOST_MONOTONIC_OBSERVATIONS", "plan": self.plan, "profile": self.profile,
            "sdk_transport_retries": {"policy": "SDK_DEFAULT", "retry_config_supplied": False,
                                      "high_level_start_retry": True, "physical_rpc_count_claimed": False},
            "events": self.observed.counters}

    def write_audit(self, cleanup):
        audit = self.root / "audit"
        write_json(audit / "environment.json", self.environment)
        write_batch_json(audit / "batch-trace.json", self.trace(), 5 * 1024 * 1024)
        for name, schema, rows, cap in (("metadata", "metadata", self.observed.metadata, 256 * 1024),
                ("histories", "history", self.histories, 4 * 1024 * 1024),
                ("outcomes", "outcomes", self.outcomes, 256 * 1024)):
            write_batch_json(audit / f"batch-{name}.json",
                {"schema_version": f"opendot.temporal.real-batch.{schema}.v1", "rows": rows}, cap)
        if cleanup is not None:
            # Existing cleanup elapsed durations are finite floats, whereas batch
            # trace encoding intentionally permits integer timestamps only.
            write_json(audit / "batch-cleanup.json", cleanup)


def run_real_batch_gate(root: Path, cli: Path, collected_nodes: list[str]):
    import verify_temporal_server_gate as verifier
    require(collected_nodes == list(verifier.REAL_BATCH_REQUIRED_NODES), "BATCH_NODE_SELECTION")
    require(os.environ.get("OPENDOT_TEMPORAL_QUALIFICATION") == "batch200"
            and os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch", "EXECUTION_NOT_ENABLED")
    source = Path(__file__).resolve().parents[1]
    require(root.is_absolute() and not root.exists(), "FRESH_GATE_ROOT_REQUIRED")
    require(root.parent.resolve() == Path(os.environ["RUNNER_TEMP"]).resolve(), "RUNNER_TEMP_REQUIRED")
    root.mkdir(mode=0o700)
    for name in ("server", "cas", "private", "audit", "home"):
        (root / name).mkdir(mode=0o700)
    write_json(root / "audit" / "collection-receipt.json", {
        "schema_version": "opendot.temporal.real-batch.collection.v1", "nodes": collected_nodes})
    requested = os.environ.get("OPENDOT_TEMPORAL_EXPECTED_REVISION")
    requested = requested if type(requested) is str and re.fullmatch(r"[0-9a-f]{40}", requested) else None
    diagnostic, loop, runner = DiagnosticState(requested), None, None
    try:
        if requested is None:
            raise KeyError("OPENDOT_TEMPORAL_EXPECTED_REVISION")
        logging.basicConfig(filename=root / "private" / "sdk.log", level=logging.ERROR, force=True)
        environment = preflight(root, cli, source)
        loop = asyncio.new_event_loop()
        runner = BatchRunner(root, cli, environment, diagnostic)
        result = loop.run_until_complete(runner.execute())
        summary = verifier.validate_real_batch_trace(runner.trace(), runner.plan, runner.profile,
            runner.observed.metadata, runner.histories, runner.outcomes, expected_revision=requested, source=source)
        verifier.validate_real_batch_cleanup(result["cleanup"])
        return {**result, "summary": summary}
    except Exception as error:
        if runner is None:
            recorded, capture_error = capture_diagnostic(diagnostic, error, slot="primary_failure", phase=diagnostic.phase)
            if recorded and not (root / "audit" / "diagnostic.json").exists():
                diagnostic.write(root / "audit")
            if capture_error is not None and is_interruption(capture_error):
                raise capture_error
        raise GateRunError("SERVER_GATE_FAILED") from None
    finally:
        if loop is not None and not asyncio.all_tasks(loop):
            loop.close()


# Fixed, explicitly selected DAG2 hosted profile. No SDK import on collection.
DAG2_CAPS = {'diagnostic_bytes': 4096,
 'evidence_pytest_overhead_seconds': 30,
 'final_stop_seconds': 20,
 'history_bytes_each': 2097152,
 'history_poll_interval_ms': 100,
 'job_seconds': 600,
 'mission_records': 3,
 'nodes': 7,
 'observation_cleanup_seconds': 40,
 'observer_events': 512,
 'pack_admitted_commands': 18,
 'private_evidence_total_bytes': 27262976,
 'production_commands_per_mission': 6,
 'projection_total_bytes': 262144,
 'query_poll_interval_ms': 100,
 'raw_history_total_bytes': 14680064,
 'result_bytes': 16384,
 'retained_history_snapshots': 7,
 'rpc_observer_wait_seconds': 3,
 'rpc_operation_records': 64,
 'rpc_timeout_seconds': 2,
 'seed_bytes': 256,
 'service_step_seconds': 240,
 'state_bytes': 16384,
 'summary_bytes': 8192,
 'trace_bytes': 262144,
 'whole_scenario_seconds': 150,
 'wire_envelope_bytes': 4096}
DAG2_REQUIRED_NODES = ['tests/acceptance/temporal_dag_recovery_gate.py::test_dag2_real_a_to_b_and_original_receipts',
 'tests/acceptance/temporal_dag_recovery_gate.py::test_dag2_quiescent_worker_replacement_preserves_state',
 'tests/acceptance/temporal_dag_recovery_gate.py::test_dag2_recorded_history_replay_has_no_activity_execution',
 'tests/acceptance/temporal_dag_recovery_gate.py::test_dag2_original_put_reconciliation_never_reexecutes_a',
 'tests/acceptance/temporal_dag_recovery_gate.py::test_dag2_unknown_without_reference_blocks_b',
 'tests/acceptance/temporal_dag_recovery_gate.py::test_dag2_cancellation_keeps_unadmitted_b_closed',
 'tests/acceptance/temporal_dag_recovery_gate.py::test_dag2_duplicate_and_stale_updates_consume_no_allowance']
DAG2_SOURCE_CLOSURE = ['.github/workflows/temporal-server.yml',
 'AGENTS.md',
 'ci/acquire_temporal_cli.py',
 'ci/requirements.txt',
 'ci/run_temporal_server_gate.py',
 'ci/temporal-batch-nodes.txt',
 'ci/temporal-dag-recovery-nodes.txt',
 'ci/temporal-real-batch-nodes.txt',
 'ci/temporal-sdk-requirements.txt',
 'ci/temporal-server-nodes.txt',
 'ci/verify_temporal_server_gate.py',
 'docs/decisions/004-temporal-reference-transport.md',
 'docs/decisions/008-fixed-dependent-temporal-recovery.md',
 'docs/temporal-batch-qualification.md',
 'docs/temporal-reference-transport.md',
 'pyproject.toml',
 'src/opendot_engineering/__init__.py',
 'src/opendot_engineering/adapters/__init__.py',
 'src/opendot_engineering/adapters/source_audit.py',
 'src/opendot_engineering/adapters/temporal_activity.py',
 'src/opendot_engineering/adapters/temporal_workflow.py',
 'src/opendot_engineering/core/__init__.py',
 'src/opendot_engineering/core/artifacts.py',
 'src/opendot_engineering/core/contracts.py',
 'src/opendot_engineering/tool_runtime.py',
 'tests/acceptance/temporal_dag_recovery_gate.py',
 'tests/acceptance/temporal_real_batch_gate.py',
 'tests/acceptance/temporal_server_gate.py',
 'tests/test_a2a_worker_turn.py',
 'tests/test_temporal_activity_contract.py',
 'tests/test_temporal_cli_acquisition.py',
 'tests/test_temporal_dag_recovery.py',
 'tests/test_temporal_server_gate_verifier.py',
 'tests/test_temporal_server_harness_unit.py',
 'tests/test_temporal_transport_owner_boundaries.py',
 'tests/test_temporal_workflow_contract.py']
DAG2_EVENT_KINDS = ('seed_put_return',
 'workflow_start_issued',
 'workflow_start_acknowledged',
 'bootstrap_constructed',
 'worker_start',
 'activity_enter',
 'runtime_enter',
 'handler_enter',
 'handler_return',
 'runtime_return',
 'result_put_return',
 'original_capture',
 'adapter_return',
 'controlled_response_failure',
 'activity_terminal_observed',
 'snapshot_retained',
 'query_observed',
 'update_submit',
 'update_handle_returned',
 'update_refusal_observed',
 'update_accepted_observed',
 'update_result_observed',
 'cancel_submit',
 'cancel_acknowledged',
 'cancel_recorded_observed',
 'workflow_terminal_observed',
 'verification_read',
 'replay_begin',
 'replay_end',
 'worker_stop_requested',
 'worker_stop_completed',
 'activity_executor_completed',
 'server_start',
 'server_stop_requested',
 'server_stop_completed',
 'rpc_issued',
 'rpc_settled',
 'observer_failure')
DAG2_COUNT_KEYS = ('workflow_starts',
 'activity_schedules',
 'activity_entries',
 'activity_returns',
 'runtime_entries',
 'runtime_returns',
 'handler_entries',
 'handler_returns',
 'seed_puts',
 'result_puts',
 'endpoint_cas_reads',
 'observer_cas_reads',
 'verification_cas_reads',
 'in_flight_calls',
 'pending_rpc_tasks')
DAG2_CLAIMS = {'actual_crash_process_fencing': 'NOT_EVALUATED',
 'device_control_authority': False,
 'external_effect_authenticity': 'NOT_PROVED',
 'independent_review': 'NOT_EVALUATED',
 'issue_7_closed': False,
 'lost_network_ack': 'NOT_EVALUATED',
 'natural_300_second_deadline': 'NOT_EVALUATED',
 'owner_integration': 'NOT_EVALUATED',
 'scientific_validity': False,
 'termination_status': 'NOT_ESTABLISHED'}
DAG2_MISSIONS = ("hosted-normal", "hosted-reconcile", "hosted-no-ref-cancel")
DAG2_STOP_ORDER = (2, 1, 4, 3, 6, 5, 8, 7)
DAG2_FAILURE_TYPE = "DAG2_TEST_RESPONSE_UNAVAILABLE"
DAG2_CLASS = "OBSERVED_HOSTED_CANDIDATE"
_DAG2_CALL = ContextVar("dag2_observed_activity", default=None)


def dag2_encoded(value, limit):
    data = json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")
    require(0 < len(data) <= limit, "SIZE_LIMIT")
    return data


def write_dag2_bytes(path, data, limit):
    require(type(data) is bytes and 0 < len(data) <= limit, "SIZE_LIMIT")
    with path.open("xb") as output:
        output.write(data)
    path.chmod(0o600)
    return {"file_id": path.name, "sha256": sha(data), "size_bytes": len(data)}


def write_dag2_json(path, value, limit):
    return write_dag2_bytes(path, dag2_encoded(value, limit - 1) + b"\n", limit)


def dag2_selection(event, profile, retain, nodes):
    require(event == "workflow_dispatch" and profile == "dag2" and retain is False,
            "PROFILE_MISMATCH")
    require(type(nodes) is list and nodes == DAG2_REQUIRED_NODES, "REQUIRED_NODES")


def dag2_bind_handle(client, handle, identifier):
    first, result = handle.first_execution_run_id, handle.result_run_id
    require(handle.id == identifier and type(first) is str and type(result) is str
            and re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", first) is not None
            and result == first, "RUN_BINDING")
    return client.get_workflow_handle(identifier, run_id=result, first_execution_run_id=first)


def dag2_worker_options(kind):
    require(kind in {"workflow", "activity"}, "INVALID_VALUE")
    options = {"disable_eager_activity_execution": True,
               "graceful_shutdown_timeout": timedelta(seconds=5)}
    if kind == "workflow":
        options.update(max_concurrent_workflow_tasks=1, max_concurrent_workflow_task_polls=1,
                       max_cached_workflows=0, no_remote_activities=True)
    else:
        options.update(max_concurrent_activities=1, max_concurrent_activity_task_polls=1)
    return options


def dag2_should_fail_response(mission, node, operation):
    return mission in {"hosted-reconcile", "hosted-no-ref-cancel"} and node == "A" and operation == "execute"


class Dag2Observations:
    """Detached causal observations, never an execution scheduler or CAS reader."""
    dag2 = True

    def __init__(self, *, clock=time.monotonic_ns):
        self.clock = clock
        self.lock = threading.RLock()
        self.events = []
        self.counts = dict.fromkeys(DAG2_COUNT_KEYS, 0)
        # Reserve the closed top-level keys, aggregate counts and separators.
        self.trace_bytes = 1024
        self.execution_uncertain = False
        self.originals = {}
        self.returned = set()
        self.calls = {}
        self.metadata, self.counters = [], []  # inherited result envelope only

    def record(self, kind, *, mission=None, node=None, worker_generation=None,
               operation_id=None, history_event_id=None, changes=None):
        with self.lock:
            try:
                require(kind in DAG2_EVENT_KINDS and mission in (*DAG2_MISSIONS, None)
                        and node in ("A", "B", None), "INVALID_VALUE")
                require(len(self.events) < DAG2_CAPS["observer_events"], "SIZE_LIMIT")
                tick = self.clock()
                require(type(tick) is int and 0 <= tick <= 10**18
                        and (not self.events or tick >= self.events[-1]["monotonic_ns"]), "CAUSAL_ORDER")
                require(len(self.events) < DAG2_CAPS["observer_events"], "SIZE_LIMIT")
                counts = dict(self.counts)
                for name, delta in (changes or {}).items():
                    require(name in counts and type(delta) is int, "INVALID_VALUE")
                    counts[name] += delta
                    require(counts[name] >= 0, "COUNTER_MISMATCH")
                row = {"seq": len(self.events) + 1, "monotonic_ns": tick, "mission": mission,
                       "kind": kind, "node": node, "worker_generation": worker_generation,
                       "operation_id": operation_id, "history_event_id": history_event_id,
                       "counts": dict(counts)}
                size = len(dag2_encoded(row, DAG2_CAPS["trace_bytes"])) + 1
                require(self.trace_bytes + size <= DAG2_CAPS["trace_bytes"], "SIZE_LIMIT")
                self.events.append(row)
                self.counts = counts
                self.trace_bytes += size
                return row["seq"]
            except BaseException:
                self.execution_uncertain = True
                raise

    def reserve_trace(self, size):
        # Conservative closed-record allowances are charged before admission.
        with self.lock:
            if type(size) is not int or size < 0 or self.trace_bytes + size > 262144:
                self.execution_uncertain = True
                raise GateRunError("SIZE_LIMIT")
            self.trace_bytes += size

    def count_snapshot(self):
        with self.lock:
            return dict(self.counts)

    def capture_original(self, mission, node, body, reference):
        # The no-ref branch deliberately touches neither argument, even to hash it.
        identity = _DAG2_CALL.get()
        generation = None if identity is None else identity["worker_generation"]
        put_seq = self.record("result_put_return", mission=mission, node=node,
                              worker_generation=generation, changes={"result_puts": 1})
        if mission == "hosted-no-ref-cancel":
            return
        require((mission, node) not in self.originals and len(self.originals) < 4, "ORIGINAL_MUTATED")
        data = dag2_encoded(body, DAG2_CAPS["result_bytes"])
        detached = json.loads(data)
        ref = json.loads(dag2_encoded(reference, DAG2_CAPS["wire_envelope_bytes"]))
        require(sha(data) == ref["sha256"] and len(data) == ref["size_bytes"], "ORIGINAL_MUTATED")
        origin = {"schema_version": "opendot.temporal.dag-origin.v1",
                  "origin_kind": "trusted-single-operator-synthetic-put-observer",
                  "capture_phase": "original_put_return_before_response",
                  "mission_id": mission, "plan_sha256": detached["plan_sha256"], "node_id": node,
                  "effect_id": detached["effect_id"], "namespace": detached["namespace"],
                  "workflow_id": detached["workflow_id"], "workflow_run_id": detached["workflow_run_id"],
                  "execution_activity_id": detached["activity_id"], "original_result_ref": ref}
        seq = self.record("original_capture", mission=mission, node=node, worker_generation=generation)
        self.originals[(mission, node)] = {"body_bytes": data, "body_sha256": sha(data),
            "body_value": detached, "reference": ref, "origin": origin,
            "origin_sha256": sha(dag2_encoded(origin, 4096)), "capture_seq": seq,
            "put_return_seq": put_seq, "put_operation_id": self.counts["seed_puts"] + self.counts["result_puts"]}

    def require_fault_boundary(self, mission, node):
        with self.lock:
            require(not self.execution_uncertain and (mission, node, "execute") in self.returned
                    and self.counts["handler_entries"] == self.counts["handler_returns"]
                    and self.counts["runtime_entries"] == self.counts["runtime_returns"]
                    and self.counts["activity_entries"] == self.counts["activity_returns"]
                    and self.counts["in_flight_calls"] == 0, "CAUSAL_ORDER")

    def phase(self, kind, counter):
        identity = _DAG2_CALL.get()
        require(type(identity) is dict, "CAUSAL_ORDER")
        return self.record(kind, mission=identity["mission"], node=identity["node"],
                           worker_generation=identity["worker_generation"], changes={counter: 1})

    def enter(self, info, request, mission, generation):
        operation = "execute" if info.activity_type == "opendot.synthetic.dependent-step.v1" else request["mode"] + "_inspect"
        require(request["mission_id"] == mission and request["node_id"] in {"A", "B"}
                and info.attempt == 1 and info.is_local is False
                and info.retry_policy.maximum_attempts == 1
                and info.start_to_close_timeout == timedelta(seconds=10)
                and info.schedule_to_close_timeout == timedelta(seconds=60), "HISTORY_MISMATCH")
        key = (mission, info.activity_id)
        with self.lock:
            require(key not in self.calls and self.counts["in_flight_calls"] == 0, "COUNTER_MISMATCH")
            self.reserve_trace(1024)
            seq = self.record("activity_enter", mission=mission, node=request["node_id"],
                worker_generation=generation, changes={"activity_entries": 1, "in_flight_calls": 1})
            call = {"mission": mission, "node": request["node_id"], "kind": operation,
                    "workflow_id": info.workflow_id, "run_id": info.workflow_run_id,
                    "activity_id": info.activity_id, "activity_type": info.activity_type,
                    "attempt": info.attempt, "maximum_attempts": info.retry_policy.maximum_attempts,
                    "start_to_close_seconds": 10, "schedule_to_close_seconds": 60,
                    "entry_seq": seq, "worker_generation": generation,
                    "request_sha256": sha(dag2_encoded(request, 4096)), "response_sha256": None,
                    "fault": "NONE"}
            self.calls[key] = call
            return call

    def adapter_return(self, call, response):
        # A no-ref response is never hashed or retained by the observer.
        fault = dag2_should_fail_response(call["mission"], call["node"], call["kind"])
        with self.lock:
            call["return_seq"] = self.record("adapter_return", mission=call["mission"], node=call["node"],
                worker_generation=call["worker_generation"], changes={"activity_returns": 1, "in_flight_calls": -1})
            self.returned.add((call["mission"], call["node"], call["kind"]))
            if not fault:
                call["response_sha256"] = sha(dag2_encoded(response, 4096))
            if call["kind"] == "execute" and call["mission"] != "hosted-no-ref-cancel":
                self.originals[(call["mission"], call["node"])]["adapter_return_seq"] = call["return_seq"]
            if fault:
                self.require_fault_boundary(call["mission"], call["node"])
                call["fault"] = "CONTROLLED_POST_RETURN_RESPONSE_FAILURE"
                self.record("controlled_response_failure", mission=call["mission"], node=call["node"],
                            worker_generation=call["worker_generation"])
        return fault


def dag2_interceptor(observed, mission, generation):
    from temporalio import activity
    from temporalio.exceptions import ApplicationError
    from temporalio.worker import ActivityInboundInterceptor, Interceptor
    class Capture(Interceptor):
        def intercept_activity(self, next):
            class Entry(ActivityInboundInterceptor):
                async def execute_activity(self, input):
                    try:
                        require(len(input.args) == 1 and type(activity.info()) is activity.Info, "INVALID_VALUE")
                        call = observed.enter(activity.info(), input.args[0], mission, generation)
                        token = _DAG2_CALL.set(call)
                        try:
                            response = await self.next.execute_activity(input)
                        finally:
                            _DAG2_CALL.reset(token)
                        fault = observed.adapter_return(call, response)
                    except BaseException:
                        observed.execution_uncertain = True
                        raise
                    if fault:
                        raise ApplicationError(DAG2_FAILURE_TYPE, type=DAG2_FAILURE_TYPE, non_retryable=True)
                    return response
            return Entry(next)
    return Capture()


class Dag2Runner(Runner):
    """One three-mission test profile, using the existing lifecycle owner."""
    dag2_profile = True
    def __init__(self, root, cli, environment, diagnostic):
        self.observed = Dag2Observations()
        self._initialize_lifecycle(root, cli, environment, diagnostic)
        self.deadline = self.started + 150
        self.service_deadline = self.started + 210
        self.cleanup_deadline = self.final_stop_deadline = None
        self.cleanup_started = self.final_stop_started = None
        self.rpc_pending, self.rpc_rows, self.rpc_ids = {}, [], set()
        self.handles, self.requests, self.queues, self.states = {}, {}, {}, {}
        self.unfinished_updates = set()
        self.admission_closed = False
        self.worker_stops, self.bootstraps, self.updates, self.replays = [], [], [], []
        self.adapters, self.schedule_observations, self.terminal_observations = {}, {}, {}
        self.raw_files, self.snapshot_histories = {}, {}
        self.cancel_calls = 0
        self.last_quiescent_seq = None
        self.source_manifest = environment.pop("dag2_source_manifest")
        self.source_manifest_bytes = environment.pop("dag2_source_manifest_bytes")
        self.identity = environment.pop("dag2_identity")
        self.evidence_complete = False
        from opendot_engineering.adapters.temporal_workflow import DependentSumWorkflow
        self.workflow_class = DependentSumWorkflow
        # Observe the canonical instance; no substitute store class or implementation.
        original_put, original_read = self.store.put_json, self.store.get_bytes
        observed = self.observed
        def put(value, **kwargs):
            ref = original_put(value, **kwargs)
            identity = _DAG2_CALL.get()
            require(type(identity) is dict and identity["kind"] == "execute", "CAUSAL_ORDER")
            if identity["mission"] == "hosted-no-ref-cancel":
                observed.capture_original(identity["mission"], identity["node"], None, None)
            else:
                row = asdict(ref); row["source_refs"] = list(row["source_refs"])
                observed.capture_original(identity["mission"], identity["node"], value, row)
            return ref
        def read(ref, *, max_bytes=None):
            require(type(_DAG2_CALL.get()) is dict and max_bytes in {256, 16384}, "CAUSAL_ORDER")
            value = original_read(ref, max_bytes=max_bytes)
            with observed.lock:
                observed.counts["endpoint_cas_reads"] += 1
            return value
        self.seed_put = original_put
        self.verification_read = original_read
        self.store.put_json, self.store.get_bytes = put, read

    def quiescent(self):
        counts = self.observed.count_snapshot()
        return (not self.observed.execution_uncertain and counts["in_flight_calls"] == 0
                and counts["handler_entries"] == counts["handler_returns"]
                and counts["runtime_entries"] == counts["runtime_returns"]
                and counts["activity_entries"] == counts["activity_returns"]
                and counts["pending_rpc_tasks"] == 0
                and not self.pending and not self.rpc_pending and not self.unfinished_updates)

    def begin_cleanup(self):
        if self.cleanup_started is None:
            self.cleanup_started = time.monotonic()
            self.cleanup_deadline = min(self.cleanup_started + 40, self.service_deadline)
            self.final_stop_deadline = min(self.cleanup_deadline + 20, self.service_deadline)

    async def rpc(self, mission, kind, operation_id, factory, *, update_id=None,
                  expected_refusal=False, history_target=None, cleanup=False):
        require(operation_id not in self.rpc_ids, "RPC_RESUBMITTED")
        require(len(self.rpc_rows) < 64, "SIZE_LIMIT")
        deadline = self.cleanup_deadline if cleanup else self.deadline
        require(deadline is not None and time.monotonic() < deadline, "DEADLINE_EXHAUSTED")
        require(cleanup or not self.admission_closed, "RPC_UNCONFIRMED")
        require(kind in {"start", "query", "history", "result", "start_update", "update_result", "cancel"}, "INVALID_VALUE")
        handle = self.handles.get(mission)
        if handle is None:
            from opendot_engineering.adapters.temporal_workflow import dag_workflow_id
            workflow_id, run_id = dag_workflow_id(mission), None
        else:
            workflow_id, run_id = handle.id, handle.run_id
        self.observed.reserve_trace(768)
        self.rpc_ids.add(operation_id)
        seq = self.observed.record("rpc_issued", mission=mission, operation_id=operation_id,
                                   changes={"pending_rpc_tasks": 1})
        row = {"operation_id": operation_id, "mission": mission, "kind": kind, "issued_seq": seq,
               "settled_seq": None, "workflow_id": workflow_id, "run_id": run_id, "update_id": update_id,
               "outcome": "UNCONFIRMED", "rpc_timeout_seconds": 2, "observation_timeout_seconds": 3,
               "application_submissions": 1, "follow_runs": False}
        self.rpc_rows.append(row)
        try:
            task = asyncio.ensure_future(factory())
            self.rpc_pending[operation_id] = task
            try:
                value = await self.bounded(task, 3, "RPC_UNCONFIRMED", cleanup=cleanup)
            except BaseException as error:
                if expected_refusal and task.done() and dag2_validator_refusal(error):
                    row["outcome"] = "EXPECTED_VALIDATOR_REFUSAL"
                    self.settle_rpc(row)
                    return None
                raise
            target = history_target(value) if history_target is not None else None
            row["outcome"] = "SUCCESS"
            self.settle_rpc(row, history_target=target)
            return value
        except BaseException:
            self.admission_closed = True
            raise

    def settle_rpc(self, row, *, history_target=None):
        task = self.rpc_pending[row["operation_id"]]
        require(task.done(), "RPC_UNCONFIRMED")
        changes = {"pending_rpc_tasks": -1}
        event_id = None
        if history_target is not None:
            event_id, scheduled = history_target
            if scheduled:
                changes["activity_schedules"] = 1
        seq = self.observed.record("rpc_settled", mission=row["mission"], operation_id=row["operation_id"],
                                   history_event_id=event_id, changes=changes)
        row["settled_seq"] = seq
        self.rpc_pending.pop(row["operation_id"])

    async def observe_pending_rpc(self):
        # Observe original tasks only. Late completion never clears admission failure.
        for row in self.rpc_rows:
            task = self.rpc_pending.get(row["operation_id"])
            if task is None:
                continue
            if not task.done():
                try:
                    await self.bounded(task, 3, "RPC_UNCONFIRMED", cleanup=True)
                except BaseException as error:
                    if is_interruption(error):
                        raise
                    if not task.done():
                        continue
            try:
                task.result()
            except BaseException as error:
                if is_interruption(error):
                    raise
            self.settle_rpc(row)

    def worker_stop_begin(self, entry):
        require(not self.stop_uncertain, "WORKER_STOP_UNCONFIRMED")
        deadline = self.deadline if self.final_stop_started is None else self.final_stop_deadline
        require(time.monotonic() < deadline, "DEADLINE_EXHAUSTED")
        seq = self.observed.record("worker_stop_requested", mission=entry["mission"],
                                   worker_generation=entry["row"]["generation"])
        snapshots = [r["seq"] for r in self.observed.events if r["kind"] == "snapshot_retained"]
        stop = {"generation": entry["row"]["generation"], "mission": entry["mission"],
                "kind": entry["row"]["type"], "start_seq": entry["start_seq"],
                "stop_requested_seq": seq, "quiescent_snapshot_seq": snapshots[-1] if snapshots else seq,
                "public_shutdown_calls": 1, "public_shutdown_completed": False,
                "worker_run_task_completed": False, "executor_shutdown_calls": 0,
                "activity_executor_completion_observed": False,
                "cumulative_stop_deadline_remaining_ms": max(0, int((deadline - time.monotonic()) * 1000))}
        self.worker_stops.append(stop)
        return stop

    def worker_stop_observed(self, entry, stop, start, shutdown_end, run_end):
        stop.update(public_shutdown_completed=True, worker_run_task_completed=entry["task"].done(),
                    shutdown_elapsed_ms=int((shutdown_end-start)*1000),
                    run_task_wait_elapsed_ms=int((run_end-shutdown_end)*1000),
                    stop_completed_seq=self.observed.record("worker_stop_completed", mission=entry["mission"],
                        worker_generation=entry["row"]["generation"]))

    def executor_stop_observed(self, entry, stop):
        stop["executor_shutdown_calls"] = 1
        stop["activity_executor_completion_observed"] = True
        self.observed.record("activity_executor_completed", mission=entry["mission"],
                             worker_generation=entry["row"]["generation"])

    def construct_bootstrap(self, mission, *, original_A):
        self.diagnostic.phase = "bootstrap"
        from opendot_engineering.adapters import temporal_activity as production
        from opendot_engineering.adapters.temporal_workflow import (DAG_HANDLER_SOURCE_SHA256,
            DAG_PLAN_SHA256, DAG_SEED_SHA256, DAG_REGISTRATION_SHA256)
        from opendot_engineering.tool_runtime import ToolRuntime
        runtime = ToolRuntime()
        observed = self.observed
        def handler(payload):
            observed.phase("handler_enter", "handler_entries")
            value = production.bounded_sum(payload)
            observed.phase("handler_return", "handler_returns")
            return value
        runtime.register(production.SYNTHETIC_SPEC, handler)
        execute_original = runtime.execute
        def execute(*args, **kwargs):
            observed.phase("runtime_enter", "runtime_entries")
            try:
                value = execute_original(*args, **kwargs)
            except BaseException:
                observed.execution_uncertain = True
                raise
            if value[1].execution_liveness:
                observed.execution_uncertain = True
            observed.phase("runtime_return", "runtime_returns")
            return value
        runtime.execute = execute
        handle = self.handles[mission]
        adapter = production.DependentSumActivity(runtime=runtime, store=self.store,
            expected_registration_sha256=DAG_REGISTRATION_SHA256,
            expected_handler_source_sha256=DAG_HANDLER_SOURCE_SHA256,
            expected_plan_sha256=DAG_PLAN_SHA256, expected_seed_sha256=DAG_SEED_SHA256,
            granted_permissions=frozenset({"synthetic:read"}), expected_namespace="default",
            expected_task_queue=self.queues[mission], expected_workflow_id=handle.id,
            expected_workflow_run_id=handle.run_id, original_A=original_A, original_B=None)
        generation = len(self.worker_rows) + 2
        seq = self.observed.record("bootstrap_constructed", mission=mission, worker_generation=generation)
        captured = self.observed.originals.get((mission, "A")) if original_A is not None else None
        row = {"mission": mission, "workflow_id": handle.id, "run_id": handle.run_id,
               "first_execution_run_id": handle.run_id, "namespace": "default", "task_queue": self.queues[mission],
               "generation": generation, "constructed_seq": seq, "started_seq": None,
               "handler_source_sha256": DAG_HANDLER_SOURCE_SHA256, "registration_sha256": DAG_REGISTRATION_SHA256,
               "original_A_sha256": None if captured is None else captured["origin_sha256"], "original_B_sha256": None,
               "origin_capture_seq": None if captured is None else captured["capture_seq"],
               "source_verified": True, "immutable_config": True, "activity_slots": 1,
               "activity_executor_threads": 1, "workflow_task_slots": 1,
               "eager_activity_execution": False, "request_eager_start": False}
        self.bootstraps.append(row)
        self.adapters[mission] = adapter
        return row

    async def start_worker(self, kind, scenario=None):
        require(scenario in DAG2_MISSIONS and not self.admission_closed and not self.stop_uncertain
                and time.monotonic() < self.deadline, "DEADLINE_EXHAUSTED")
        from temporalio.worker import Worker
        generation = len(self.worker_rows) + 1
        options = dag2_worker_options(kind)
        options.update(task_queue=self.queues[scenario], identity="opendot-dag2-" + str(generation))
        executor = None
        if kind == "workflow":
            options["workflows"] = [self.workflow_class]
        else:
            require(self.bootstraps[-1]["generation"] == generation, "BOOTSTRAP_MISMATCH")
            adapter = self.adapters[scenario]
            executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="opendot-dag2")
            options.update(activities=[adapter.execute_step, adapter.inspect_result], activity_executor=executor,
                           interceptors=[dag2_interceptor(self.observed, scenario, generation)])
        worker = Worker(self.client, **options)
        seq = self.observed.record("worker_start", mission=scenario, worker_generation=generation)
        row = {"generation": generation, "type": kind, "public_shutdown_called": False,
               "public_shutdown_completed": False}
        entry = {"worker": worker, "task": asyncio.create_task(worker.run()), "row": row,
                 "executor": executor, "mission": scenario, "start_seq": seq}
        self.worker_rows.append(row)
        self.workers.append(entry)
        if kind == "activity":
            self.activity_ever_started = True
            self.bootstraps[-1]["started_seq"] = seq
        return entry

    async def start_mission(self, mission):
        self.diagnostic.phase = "start"
        require(mission in DAG2_MISSIONS and mission not in self.handles and self.quiescent()
                and all(row["public_shutdown_completed"] for row in self.worker_rows), "BOOTSTRAP_MISMATCH")
        from temporalio.common import RetryPolicy, WorkflowIDReusePolicy, WorkflowIDConflictPolicy
        from opendot_engineering.adapters.temporal_workflow import dag_workflow_id, DAG_PLAN_SHA256
        ref = self.seed_put({"left": 2, "right": 3, "return_null": False},
                            producer="opendot.temporal.dag-seed.v1", task_id="seed")
        seed = asdict(ref); seed["source_refs"] = list(seed["source_refs"])
        self.observed.record("seed_put_return", mission=mission, changes={"seed_puts": 1})
        self.requests[mission] = {"schema_version": "opendot.temporal.dag-start.v1", "mission_id": mission,
                                  "plan_sha256": DAG_PLAN_SHA256, "seed_ref": seed}
        self.queues[mission] = "opendot-dag2-" + str(self.identity["run_id"]) + "-" + str(self.identity["run_attempt"]) + "-" + mission
        require(re.fullmatch(r"[A-Za-z0-9._-]{1,128}", self.queues[mission]) is not None, "RUN_BINDING")
        self.observed.record("workflow_start_issued", mission=mission)
        handle = await self.rpc(mission, "start", "start-" + mission, lambda: self.client.start_workflow(
            self.workflow_class.run, self.requests[mission], id=dag_workflow_id(mission), task_queue=self.queues[mission],
            execution_timeout=timedelta(seconds=300), run_timeout=timedelta(seconds=300),
            task_timeout=timedelta(seconds=10), retry_policy=RetryPolicy(maximum_attempts=1),
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE, id_conflict_policy=WorkflowIDConflictPolicy.FAIL,
            request_eager_start=False, rpc_timeout=timedelta(seconds=2)))
        self.handles[mission] = dag2_bind_handle(self.client, handle, dag_workflow_id(mission))
        self.rpc_rows[-1]["run_id"] = self.handles[mission].run_id
        self.observed.record("workflow_start_acknowledged", mission=mission, changes={"workflow_starts": 1})
        self.pending[mission] = self.handles[mission]
        self.construct_bootstrap(mission, original_A=None)
        await self.start_worker("workflow", mission)
        await self.start_worker("activity", mission)

    async def read_history(self, mission, *, target=None, cleanup=False):
        self.diagnostic.phase = "observation_cleanup" if cleanup else "history"
        from verify_temporal_server_gate import dag2_extract_history
        handle = self.handles[mission]
        captured = {}
        def inspect(history):
            require(history.workflow_id == handle.id and history.run_id == handle.run_id, "RUN_BINDING")
            raw = history.to_json().encode("utf-8")
            require(len(raw) <= DAG2_CAPS["history_bytes_each"], "SIZE_LIMIT")
            projection = dag2_extract_history(raw)
            captured.update(raw=raw, projection=projection)
            selected = target(projection) if callable(target) else target
            if selected is None:
                return projection[-1]["event_id"], False
            event_id, scheduled = selected
            matching = [event for event in projection if event["event_id"] == event_id]
            require(len(matching) == 1, "HISTORY_LINKAGE")
            if scheduled:
                require(matching[0]["event_type"] == "ActivityTaskScheduled", "HISTORY_LINKAGE")
            return event_id, scheduled
        operation_id = "history-" + str(len(self.rpc_rows) + 1)
        history = await self.rpc(mission, "history", operation_id,
            lambda: handle.fetch_history(rpc_timeout=timedelta(seconds=2)),
            history_target=inspect, cleanup=cleanup)
        return {"history": history, **captured, "rpc": self.rpc_rows[-1]}

    async def await_history(self, mission, predicate, *, target=None):
        while time.monotonic() < self.deadline:
            fetched = await self.read_history(mission, target=target)
            if predicate(fetched["projection"]):
                return fetched
            await asyncio.sleep(.1)
        raise GateRunError("DEADLINE_EXHAUSTED")

    async def query_state(self, mission):
        self.diagnostic.phase = "query"
        handle = self.handles[mission]
        state = await self.rpc(mission, "query", "query-" + str(len(self.rpc_rows) + 1),
                               lambda: handle.query("dag_state", rpc_timeout=timedelta(seconds=2)))
        from verify_temporal_server_gate import validate_dag2_component
        validate_dag2_component("state", state, context={"bootstraps": self.bootstraps,
            "originals": {str(index): {"mission": key[0], "node": key[1], **value}
                          for index, (key, value) in enumerate(self.observed.originals.items())}},
            validation_intent="HOSTED_CANDIDATE_ADMISSION")
        require(state["workflow_id"] == handle.id and state["run_id"] == handle.run_id, "RUN_BINDING")
        dag2_encoded(state, 16384)
        self.observed.record("query_observed", mission=mission, operation_id=self.rpc_rows[-1]["operation_id"])
        self.states[mission] = state
        return state

    async def workflow_result(self, mission):
        handle = self.handles[mission]
        value = await self.rpc(mission, "result", "result-" + mission,
                              lambda: handle.result(follow_runs=False, rpc_timeout=timedelta(seconds=2)))
        dag2_encoded(value, 16384)
        return value

    async def observe_commands(self, mission, fetched, *, queued=False, cleanup=False):
        schedules = [event for event in fetched["projection"] if event["event_type"] == "ActivityTaskScheduled"]
        require(len(schedules) <= 6, "RESOURCE_MISMATCH")
        for schedule in schedules:
            event_id = schedule["event_id"]
            key = (mission, event_id)
            if key not in self.schedule_observations:
                actual = await self.read_history(mission, target=(event_id, True), cleanup=cleanup)
                self.schedule_observations[key] = actual["rpc"]["settled_seq"]
            terminals = [event for event in fetched["projection"]
                         if event["event_type"] in {"ActivityTaskCompleted", "ActivityTaskFailed"}
                         and event["extracted"]["scheduled_event_id"] == event_id]
            if not terminals:
                require(queued and schedule is schedules[-1], "HISTORY_LINKAGE")
                continue
            require(len(terminals) == 1, "HISTORY_LINKAGE")
            if key in self.terminal_observations:
                continue
            terminal = terminals[0]
            actual = await self.read_history(mission, target=(terminal["event_id"], False), cleanup=cleanup)
            activity_id = schedule["extracted"]["activity_id"]
            call = self.observed.calls[(mission, activity_id)]
            require("return_seq" in call, "CAUSAL_ORDER")
            started = [event for event in actual["projection"] if event["event_type"] == "ActivityTaskStarted"
                       and event["extracted"]["scheduled_event_id"] == event_id]
            require(len(started) == 1 and started[0]["event_id"] == terminal["extracted"]["started_event_id"],
                    "HISTORY_LINKAGE")
            seq = self.observed.record("activity_terminal_observed", mission=mission, node=call["node"],
                worker_generation=call["worker_generation"], operation_id=actual["rpc"]["operation_id"],
                history_event_id=terminal["event_id"])
            require(call["request_sha256"] == schedule["extracted"]["payload_sha256"], "HISTORY_PAYLOAD")
            if terminal["event_type"] == "ActivityTaskCompleted":
                require(call["response_sha256"] == terminal["extracted"]["payload_sha256"], "HISTORY_PAYLOAD")
            else:
                require(call["fault"] == "CONTROLLED_POST_RETURN_RESPONSE_FAILURE", "HISTORY_MISMATCH")
            call.update(scheduled_event_id=event_id, started_event_id=started[0]["event_id"],
                        terminal_event_id=terminal["event_id"], terminal_type=terminal["event_type"],
                        schedule_observed_seq=self.schedule_observations[key], terminal_observed_seq=seq)
            self.terminal_observations[key] = seq
        if not queued:
            state = self.states.get(mission)
            require(state is not None and state["mission_status"] in
                    {"PAUSED_UNKNOWN", "COMPLETED", "STOPPED_WITH_UNKNOWN"}, "NOT_QUIESCENT")
            self.pending.pop(mission, None)

    async def retain_snapshot(self, mission, snapshot_id, state):
        require(snapshot_id not in self.snapshot_histories and len(self.histories) < 7, "HISTORY_MISMATCH")
        fetched = await self.read_history(mission)
        completed = [event for event in fetched["projection"] if event["event_type"] == "WorkflowExecutionCompleted"]
        completion = completed[0]["extracted"]["payload_sha256"] if completed else None
        state_raw = dag2_encoded(state, 16384)
        if completion is not None:
            require(len(completed) == 1 and completion == sha(state_raw), "HISTORY_PAYLOAD")
            # Decode the actual SDK payload separately from the query/result path.
            originals = [event for event in fetched["history"].events
                         if self.event_name(event) == "WorkflowExecutionCompleted"]
            values = await self.client.data_converter.decode(
                originals[0].workflow_execution_completed_event_attributes.result.payloads)
            require(len(values) == 1 and dag2_encoded(values[0], 16384) == state_raw, "HISTORY_PAYLOAD")
            self.observed.record("workflow_terminal_observed", mission=mission,
                operation_id=fetched["rpc"]["operation_id"], history_event_id=completed[0]["event_id"])
        audit = self.root / "audit"
        history_file = write_dag2_bytes(audit / (snapshot_id + ".history.json"), fetched["raw"], 2097152)
        state_file = write_dag2_bytes(audit / (snapshot_id + ".state.json"), state_raw, 16384)
        self.raw_files[history_file["file_id"]] = fetched["raw"]
        self.raw_files[state_file["file_id"]] = state_raw
        require(sum(len(value) for name, value in self.raw_files.items() if name.endswith(".history.json"))
                <= 14680064, "SIZE_LIMIT")
        seq = self.observed.record("snapshot_retained", mission=mission,
                                  operation_id=fetched["rpc"]["operation_id"],
                                  history_event_id=fetched["projection"][-1]["event_id"])
        row = {"snapshot_id": snapshot_id, "mission": mission, "observation_seq": seq,
               "history": history_file, "history_event_count": len(fetched["projection"]),
               "last_event_id": fetched["projection"][-1]["event_id"], "state": state_file,
               "state_revision": state["revision"], "state_status": state["mission_status"],
               "completion_payload_sha256": completion, "events": fetched["projection"]}
        self.observed.reserve_trace(len(dag2_encoded(row, 262144)) + 1)
        self.histories.append(row)
        self.snapshot_histories[snapshot_id] = fetched["history"]
        return row

    async def replay_snapshot(self, mission, snapshot_id):
        self.diagnostic.phase = "replay"
        from temporalio.worker import Replayer
        from temporalio.client import WorkflowHistory
        require(self.quiescent() and all(row["public_shutdown_completed"] for row in self.worker_rows), "NOT_QUIESCENT")
        snapshot = next(row for row in self.histories if row["snapshot_id"] == snapshot_id)
        raw = self.raw_files[snapshot["history"]["file_id"]]
        counts_before = self.observed.count_snapshot()
        activity_worker_count = sum(entry["row"]["type"] == "activity" and
                                    not entry["row"]["public_shutdown_completed"] for entry in self.workers)
        require(activity_worker_count == 0 and sha(raw) == snapshot["history"]["sha256"], "REPLAY_MISMATCH")
        begin = self.observed.record("replay_begin", mission=mission)
        history = WorkflowHistory.from_json(self.handles[mission].id, raw.decode("utf-8"))
        replayed = await self.bounded(Replayer(workflows=[self.workflow_class]).replay_workflow(history,
                                       raise_on_replay_failure=False), 10, "REPLAY_MISMATCH")
        require(replayed.replay_failure is None and replayed.history == history, "REPLAY_MISMATCH")
        end = self.observed.record("replay_end", mission=mission)
        counts_after = self.observed.count_snapshot()
        require(counts_before == counts_after, "REPLAY_MISMATCH")
        self.replays.append({"mission": mission, "history_file_id": snapshot["history"]["file_id"],
            "retained_history_sha256": sha(raw), "replayer_input_sha256": sha(raw),
            "completion_payload_sha256": snapshot["completion_payload_sha256"],
            "result_api": "WorkflowReplayResult.history_and_replay_failure", "replay_failure": None,
            "default_pinned_sdk_runner": True, "activity_worker_count": activity_worker_count,
            "counts_before": counts_before, "counts_after": counts_after, "begin_seq": begin, "end_seq": end})

    async def final_state(self, mission):
        result = await self.workflow_result(mission)
        state = await self.query_state(mission)
        fetched = await self.read_history(mission)
        require(any(event["event_type"] == "WorkflowExecutionCompleted" for event in fetched["projection"]),
                "HISTORY_MISMATCH")
        require(result == state, "HISTORY_PAYLOAD")
        await self.observe_commands(mission, fetched)
        return state

    async def unknown_state(self, mission):
        fetched = await self.await_history(mission, dag2_failed_activity_consumed)
        state = await self.query_state(mission)
        require(state["revision"] == 4 and state["mission_status"] == "PAUSED_UNKNOWN"
                and state["nodes"]["A"]["status"] == "UNKNOWN"
                and state["nodes"]["B"]["status"] == "WAITING", "HISTORY_MISMATCH")
        await self.observe_commands(mission, fetched)
        require(self.quiescent(), "NOT_QUIESCENT")
        return state

    async def run_normal(self):
        mission = "hosted-normal"
        await self.start_mission(mission)
        state = await self.final_state(mission)
        require(state["revision"] == 9 and state["mission_status"] == "COMPLETED", "HISTORY_MISMATCH")
        await self.retain_snapshot(mission, "normal-final", state)
        await self.stop_workers()
        await self.replay_snapshot(mission, "normal-final")

    def update_request(self, expected_revision):
        original = self.observed.originals[("hosted-reconcile", "A")]
        return {"schema_version": "opendot.temporal.dag-reconcile.v1", "node_id": "A",
                "effect_id": original["origin"]["effect_id"], "expected_revision": expected_revision,
                "candidate_result_ref": original["reference"], "original_evidence_sha256": original["origin_sha256"],
                "original_result_sha256": original["body_sha256"]}

    async def submit_update(self, operation_id, update_id, expected_revision, refusal=None):
        self.diagnostic.phase = "update"
        from temporalio.client import WorkflowUpdateStage
        mission = "hosted-reconcile"
        handle = self.handles[mission]
        request = self.update_request(expected_revision)
        # No Activity poller exists during these four controls; the preceding
        # owned query is the exact pre-state. Each control gets a fresh post-query.
        before = self.states[mission]
        counts = self.observed.count_snapshot()
        seq = self.observed.record("update_submit", mission=mission, node="A", operation_id=operation_id)
        update_handle = await self.rpc(mission, "start_update", operation_id,
            lambda: handle.start_update("reconcile_result", request, id=update_id,
                wait_for_stage=WorkflowUpdateStage.ACCEPTED, rpc_timeout=timedelta(seconds=2)), update_id=update_id)
        require(update_handle.id == update_id and update_handle.workflow_id == handle.id
                and update_handle.workflow_run_id == handle.run_id, "RUN_BINDING")
        self.observed.record("update_handle_returned", mission=mission, node="A", operation_id=operation_id)
        row = {"mission": mission, "operation_id": operation_id, "update_id": update_id,
               "expected_revision": expected_revision, "pre_revision": before["revision"], "post_revision": None,
               "request_sha256": sha(dag2_encoded(request, 4096)),
               "origin_capture_seq": self.observed.originals[(mission, "A")]["capture_seq"],
               "bootstrap_constructed_seq": self.bootstraps[-1]["constructed_seq"], "submit_seq": seq,
               "accepted_event_id": None, "completed_event_id": None, "result_sha256": None,
               "actual_error_type": None, "actual_error_details": None,
               "reservation_delta": 0, "endpoint_read_delta": 0, "execute_delta": 0}
        if refusal is not None:
            result = await self.rpc(mission, "update_result", operation_id + "-result",
                lambda: update_handle.result(rpc_timeout=timedelta(seconds=2)), update_id=update_id, expected_refusal=True)
            require(result is None and self.rpc_rows[-1]["outcome"] == "EXPECTED_VALIDATOR_REFUSAL", "UPDATE_MISMATCH")
            self.observed.record("update_refusal_observed", mission=mission, node="A", operation_id=operation_id)
            row.update(outcome="VALIDATOR_REFUSED", precondition_oracle=refusal,
                       actual_error_type="TemporalDagUpdateRejected", actual_error_details="UPDATE_REFUSED")
            after = await self.query_state(mission)
            require(before == after, "UPDATE_MISMATCH")
        else:
            fetched = await self.await_history(mission, lambda events: any(
                event["event_type"] == "WorkflowExecutionUpdateAccepted"
                and event["extracted"]["update_id"] == update_id for event in events)
                and sum(event["event_type"] == "ActivityTaskScheduled" for event in events) == 2,
                target=dag2_update_acceptance_target)
            accepted = next(event for event in fetched["projection"]
                            if event["event_type"] == "WorkflowExecutionUpdateAccepted"
                            and event["extracted"]["update_id"] == update_id)
            self.observed.record("update_accepted_observed", mission=mission, node="A",
                                operation_id=fetched["rpc"]["operation_id"], history_event_id=accepted["event_id"])
            row["accepted_event_id"] = accepted["event_id"]
            self.unfinished_updates.add(update_id)
            after = await self.query_state(mission)
            require(after["revision"] == 5 and after["nodes"]["A"]["status"] == "VERIFYING", "UPDATE_MISMATCH")
            if operation_id == "update-original":
                row.update(outcome="ACCEPTED_QUEUED", precondition_oracle="VALID_RECONCILIATION")
                self.pending[mission] = handle
                await self.observe_commands(mission, fetched, queued=True)
            else:
                row.update(outcome="SAME_UPDATE_QUEUED", precondition_oracle="RECORDED_SAME_ID")
                require(before == after, "UPDATE_MISMATCH")
        row["post_revision"] = after["revision"]
        row["reservation_delta"] = after["resources"]["activity_commands_used"] - before["resources"]["activity_commands_used"]
        final_counts = self.observed.count_snapshot()
        row["endpoint_read_delta"] = final_counts["endpoint_cas_reads"] - counts["endpoint_cas_reads"]
        row["execute_delta"] = final_counts["runtime_entries"] - counts["runtime_entries"]
        self.observed.reserve_trace(1024)
        dag2_encoded(row, 1024)
        self.updates.append(row)
        return update_handle

    async def run_reconcile(self):
        mission = "hosted-reconcile"
        await self.start_mission(mission)
        unknown = await self.unknown_state(mission)
        await self.retain_snapshot(mission, "reconcile-unknown-before-stop", unknown)
        await self.stop_workers()
        original = self.observed.originals[(mission, "A")]
        self.construct_bootstrap(mission, original_A=original["origin"])
        await self.start_worker("workflow", mission)
        same = await self.query_state(mission)
        require(same == unknown, "BOOTSTRAP_MISMATCH")
        await self.retain_snapshot(mission, "reconcile-unknown-after-replacement", same)
        await self.submit_update("update-stale", "dag2-reconcile-stale", 3, "STALE_REVISION")
        update_handle = await self.submit_update("update-original", "dag2-reconcile-original", 4)
        await self.retain_snapshot(mission, "reconcile-update-queued", self.states[mission])
        await self.submit_update("update-repeat-same-id", "dag2-reconcile-original", 4)
        await self.submit_update("update-distinct-busy", "dag2-reconcile-busy", 4, "INSPECTION_BUSY")
        await self.start_worker("activity", mission)
        result = await self.rpc(mission, "update_result", "update-original-result",
            lambda: update_handle.result(rpc_timeout=timedelta(seconds=2)), update_id="dag2-reconcile-original")
        require(result["status"] == "ACCEPTED" and result["accepted_result_ref"] == original["reference"], "UPDATE_MISMATCH")
        self.observed.record("update_result_observed", mission=mission, node="A", operation_id="update-original-result")
        self.unfinished_updates.remove("dag2-reconcile-original")
        state = await self.final_state(mission)
        require(state["revision"] == 10 and state["mission_status"] == "COMPLETED", "HISTORY_MISMATCH")
        handle = self.handles[mission].get_update_handle("dag2-reconcile-original")
        repeated = await self.rpc(mission, "update_result", "update-get-completed",
            lambda: handle.result(rpc_timeout=timedelta(seconds=2)), update_id="dag2-reconcile-original")
        require(dag2_encoded(repeated, 4096) == dag2_encoded(result, 4096), "UPDATE_MISMATCH")
        self.observed.record("update_result_observed", mission=mission, node="A", operation_id="update-get-completed")
        completed_rpc = self.rpc_rows[-1]
        final = await self.retain_snapshot(mission, "reconcile-final", state)
        accepted = next(event for event in final["events"] if event["event_type"] == "WorkflowExecutionUpdateAccepted")
        completed = next(event for event in final["events"] if event["event_type"] == "WorkflowExecutionUpdateCompleted")
        require(completed["extracted"]["accepted_event_id"] == accepted["event_id"]
                and completed["extracted"]["update_id"] == "dag2-reconcile-original", "UPDATE_MISMATCH")
        for retained in self.updates:
            if retained["operation_id"] in {"update-original", "update-repeat-same-id"}:
                require(retained["accepted_event_id"] == accepted["event_id"], "UPDATE_MISMATCH")
                retained["completed_event_id"] = completed["event_id"]
        self.observed.reserve_trace(1024)
        self.updates.append({"operation_id": "update-get-completed", "update_id": "dag2-reconcile-original",
            "mission": mission, "expected_revision": 4, "pre_revision": state["revision"], "post_revision": state["revision"],
            "request_sha256": sha(dag2_encoded(self.update_request(4), 4096)),
            "origin_capture_seq": original["capture_seq"], "bootstrap_constructed_seq": self.bootstraps[-1]["constructed_seq"],
            "submit_seq": completed_rpc["issued_seq"], "accepted_event_id": accepted["event_id"],
            "completed_event_id": completed["event_id"], "result_sha256": sha(dag2_encoded(result, 4096)),
            "outcome": "SAME_COMPLETED_RESULT", "precondition_oracle": "RECORDED_SAME_ID",
            "actual_error_type": None, "actual_error_details": None, "reservation_delta": 0,
            "endpoint_read_delta": 0, "execute_delta": 0})
        await self.stop_workers()
        await self.replay_snapshot(mission, "reconcile-final")

    def require_cancel_quiescent(self, handle):
        require(self.cleanup_started is None and self.diagnostic.phase == "cancel"
                and self.diagnostic.primary_failure is None and not self.admission_closed
                and not self.stop_uncertain and not self.observed.execution_uncertain
                and handle is self.handles["hosted-no-ref-cancel"] and self.quiescent(), "CANCEL_SCOPE")
        state = self.states["hosted-no-ref-cancel"]
        require(state["revision"] == 4 and state["nodes"]["A"]["status"] == "UNKNOWN"
                and state["nodes"]["B"]["status"] == "WAITING"
                and state["nodes"]["A"]["candidate_result_ref"] is None
                and state["nodes"]["B"]["effect_id"] is None, "CANCEL_SCOPE")
        require(len([key for key in self.terminal_observations if key[0] == "hosted-no-ref-cancel"]) == 1,
                "CANCEL_SCOPE")

    async def cancel_no_ref(self):
        handle = self.handles["hosted-no-ref-cancel"]
        self.require_cancel_quiescent(handle)
        await self.rpc("hosted-no-ref-cancel", "cancel", "no-ref-cancel", lambda: handle.cancel(rpc_timeout=timedelta(seconds=2)))

    async def run_no_ref(self):
        mission = "hosted-no-ref-cancel"
        await self.start_mission(mission)
        unknown = await self.unknown_state(mission)
        await self.retain_snapshot(mission, "no-ref-unknown", unknown)
        self.diagnostic.phase = "cancel"
        self.observed.record("cancel_submit", mission=mission, operation_id="no-ref-cancel")
        self.cancel_calls += 1
        await self.cancel_no_ref()
        self.observed.record("cancel_acknowledged", mission=mission, operation_id="no-ref-cancel")
        state = await self.final_state(mission)
        fetched = await self.read_history(mission, target=dag2_cancel_target)
        event = next(event for event in fetched["projection"] if event["event_type"] == "WorkflowExecutionCancelRequested")
        self.observed.record("cancel_recorded_observed", mission=mission,
            operation_id=fetched["rpc"]["operation_id"], history_event_id=event["event_id"])
        require(state["revision"] == 5 and state["mission_status"] == "STOPPED_WITH_UNKNOWN"
                and state["cancel_requested"] is True and state["nodes"]["B"]["status"] == "CANCELLED_BEFORE_ADMISSION",
                "CANCEL_MISMATCH")
        await self.retain_snapshot(mission, "no-ref-cancel-final", state)

    async def run_cases(self):
        await self.start_server()
        await self.run_normal()
        await self.run_reconcile()
        await self.run_no_ref()
        require(self.quiescent(), "NOT_QUIESCENT")
        self.verify_originals()
        self.scenario_elapsed_ms = int((time.monotonic() - self.started) * 1000)
        require(time.monotonic() <= self.deadline, "DEADLINE_EXHAUSTED")
        self.evidence_complete = True

    def verify_originals(self):
        from opendot_engineering.core.contracts import ArtifactRef
        require(set(self.observed.originals) == {(mission, node)
                for mission in DAG2_MISSIONS[:2] for node in ("A", "B")}, "RESULT_INVALID")
        for (mission, node), original in self.observed.originals.items():
            ref = ArtifactRef(**{**original["reference"], "source_refs": tuple(original["reference"]["source_refs"])})
            data = self.verification_read(ref, max_bytes=16384)
            require(data == original["body_bytes"] and sha(data) == original["body_sha256"], "ORIGINAL_MUTATED")
            self.observed.record("verification_read", mission=mission, node=node,
                                 changes={"verification_cas_reads": 1})
            name = ("normal" if mission == "hosted-normal" else "reconcile") + "-" + node.lower() + ".result.json"
            original["body"] = write_dag2_bytes(self.root / "audit" / name, data, 16384)
            self.raw_files[name] = data

    async def cleanup(self):
        self.begin_cleanup()
        self.diagnostic.phase = "observation_cleanup"
        while time.monotonic() < self.cleanup_deadline:
            await self.observe_pending_rpc()
            if self.quiescent() or self.observed.execution_uncertain or self.stop_uncertain:
                break
            for mission in tuple(self.pending):
                fetched = await self.read_history(mission, cleanup=True)
                state = self.states.get(mission)
                if state is not None and state["mission_status"] in {"PAUSED_UNKNOWN", "COMPLETED", "STOPPED_WITH_UNKNOWN"}:
                    await self.observe_commands(mission, fetched, cleanup=True)
            if not self.quiescent():
                await asyncio.sleep(.1)
        observation_end = time.monotonic()
        self.final_stop_started = observation_end
        self.final_stop_deadline = min(self.final_stop_deadline, observation_end + 20)
        if self.quiescent() and not self.stop_uncertain:
            try:
                await self.stop_workers()
                await self.stop_server()
            except BaseException:
                self.stop_uncertain = True
                raise
        finished = time.monotonic()
        counts = self.observed.count_snapshot()
        self.evidence_started_ns = time.monotonic_ns()
        stopped = self.quiescent() and not self.stop_uncertain and self.server is None
        server = self.server_rows[-1] if self.server_rows else None
        self.diagnostic.cleanup_observation = "PASS" if stopped else "UNCONFIRMED"
        return {"schema_version": "opendot.temporal.dag2-gate.cleanup.v1", "evidence_class": DAG2_CLASS,
            "worker_stops": self.worker_stops,
            "public_worker_shutdown_calls": sum(row["public_shutdown_called"] for row in self.worker_rows),
            "activity_executor_shutdown_calls": sum(row["executor_shutdown_calls"] for row in self.worker_stops),
            "server_generations": len(self.server_rows),
            "server_shutdown_signal": None if server is None else server["shutdown_requested_signal"],
            "server_shutdown_calls": sum(row["shutdown_requested_signal"] == "SIGINT" for row in self.server_rows),
            "server_exit_code": None if server is None else server["exit_code"],
            "server_stop_observed": server is not None and server["graceful_exit_observed"],
            "server_shutdown_elapsed_ms": 0 if server is None or server["shutdown_seconds"] is None else int(server["shutdown_seconds"]*1000),
            "scenario_elapsed_ms": int((self.cleanup_started-self.started)*1000),
            "observation_cleanup_elapsed_ms": int((observation_end-self.cleanup_started)*1000),
            "final_stop_elapsed_ms": int((finished-self.final_stop_started)*1000),
            "evidence_and_pytest_elapsed_ms": 0,
            "all_scheduled_invocations_terminal": not self.pending,
            "in_flight_calls": counts["in_flight_calls"], "pending_rpc_tasks": len(self.rpc_pending),
            "accepted_updates_unfinished": len(self.unfinished_updates),
            "handler_entries": counts["handler_entries"], "handler_returns": counts["handler_returns"],
            "stop_uncertain": self.stop_uncertain, "cleanup_status": "PASS" if stopped else "UNCONFIRMED",
            "force_or_task_cancellation_calls": 0, "workflow_handle_cancel_calls": self.cancel_calls,
            "same_cas": True, "same_sqlite": True}

    def trace(self):
        return {"schema_version": "opendot.temporal.dag2-gate.trace.v1", "evidence_class": DAG2_CLASS,
                "events": self.observed.events,
                "commands": list(self.observed.calls.values()), "rpc_operations": self.rpc_rows,
                "snapshots": self.histories, "updates": self.updates,
                "aggregate_counts": self.observed.count_snapshot()}

    def original_records(self):
        originals = []
        for (mission, node), original in self.observed.originals.items():
            body = original["body_value"]
            receipt = body["receipt_report"]
            originals.append({"mission": mission, "node": node,
                **{name: original[name] for name in ("put_operation_id", "capture_seq", "put_return_seq",
                    "adapter_return_seq", "reference", "body", "origin", "origin_sha256")},
                "receipt_sha256": sha(dag2_encoded(receipt, 16384)), "receipt_call_id": receipt["call_id"],
                "observation_execution_id": receipt["execution_observation"]["execution_id"],
                "input_sha256": receipt["input_hash"], "output_sha256": receipt["output_hash"], "output": body["output"]})
        no_ref_calls = [call for (mission, _), call in self.observed.calls.items() if mission == "hosted-no-ref-cancel"]
        no_ref_events = [event for event in self.observed.events if event["mission"] == "hosted-no-ref-cancel"]
        return {"schema_version": "opendot.temporal.dag2-gate.originals.v1", "evidence_class": DAG2_CLASS,
                "originals": originals, "no_ref": {"mission": "hosted-no-ref-cancel",
                "result_puts": sum(event["kind"] == "result_put_return" for event in no_ref_events),
                "handler_returns": sum(event["kind"] == "handler_return" for event in no_ref_events),
                "adapter_returns": sum("return_seq" in call for call in no_ref_calls),
                "original_reference": "NOT_RETAINED", "original_body": "NOT_RETAINED",
                "original_digest": "NOT_RETAINED", "origin_record": "NOT_RETAINED",
                "cas_discovery_attempts": 0, "recovery_reference_reads": 0}}

    def write_audit(self, cleanup):
        # Incomplete packs never get padded into the successful schema.
        if not self.evidence_complete or cleanup is None or cleanup["cleanup_status"] != "PASS":
            return
        write_dag2_json(self.root / "private" / "dag2-timing.json", {
            "schema_version": "opendot.temporal.dag2-private-timing.v1",
            "service_started_ns": int(self.started * 1000000000),
            "evidence_started_ns": self.evidence_started_ns}, 4096)
        cleanup["evidence_and_pytest_elapsed_ms"] = (time.monotonic_ns() - self.evidence_started_ns) // 1000000
        source = Path(__file__).resolve().parents[1]
        dag2_check_source(source, self.source_manifest, self.identity)
        require(tuple(row["generation"] for row in self.worker_stops) == DAG2_STOP_ORDER, "CLEANUP_UNCONFIRMED")
        source_digest = sha(self.source_manifest_bytes)
        records = {row["path"]: row for row in self.source_manifest["files"]}
        self.dag2_environment = {"schema_version": "opendot.temporal.dag2-gate.environment.v1",
            "evidence_class": DAG2_CLASS, "identity": self.identity,
            "base_tree": "3dc536c4487422d6706831ac954c91264d771d4b",
            "adr008_sha256": "c7d18394d4a88b74e9b0b30ba5ba960bbc5177e19b2f6c115db91b23819b6737",
            "plan_sha256": "19843079a5da00754ec1b5399962c33874b907eb4d0d6fcf55cd3be2f4dffb63",
            "source_closure": [records[name] for name in DAG2_SOURCE_CLOSURE],
            "complete_tracked_manifest_sha256": source_digest,
            "source_before_sha256": source_digest, "source_after_sha256": source_digest,
            "acquisition_receipt_sha256": sha((self.cli.parent / "acquisition-receipt.json").read_bytes()),
            "pip_report_sha256": sha(Path(os.environ["OPENDOT_TEMPORAL_PIP_REPORT"]).read_bytes()),
            "sdk_version": "1.34.0", "cli_version": "1.9.1", "server_version": self.environment["server_version"],
            "python_version": "3.12", "runner_os": "ubuntu-24.04", "fresh_private_root": True,
            "effective_proxy_refused": True, "bootstrap": self.bootstraps,
            "sdk_transport_retry_policy": "SDK_DEFAULT_NO_PHYSICAL_RPC_COUNT_CLAIM", "claims": DAG2_CLAIMS}
        self.documents = {"dag2-environment.json": self.dag2_environment, "dag2-trace.json": self.trace(),
            "dag2-originals.json": self.original_records(),
            "dag2-replays.json": {"schema_version": "opendot.temporal.dag2-gate.replays.v1",
                                  "evidence_class": DAG2_CLASS, "replays": self.replays},
            "dag2-cleanup.json": cleanup}
        require(sum(len(dag2_encoded(row["events"], 262144)) for row in self.histories) <= 262144, "SIZE_LIMIT")
        for command in self.documents["dag2-trace.json"]["commands"]:
            dag2_encoded(command, 1024)
        for operation in self.rpc_rows:
            dag2_encoded(operation, 768)
        for update in self.updates:
            dag2_encoded(update, 1024)
        audit_documents = dict(self.documents)
        for filename, data in self.raw_files.items():
            if filename.endswith((".state.json", ".result.json")):
                self.documents[filename] = json.loads(data)
        self.documents["dag2-diagnostic.json"] = self.diagnostic.record()
        from verify_temporal_server_gate import validate_dag2_records
        self.validated = validate_dag2_records(self.documents, self.raw_files, self.identity,
            validation_intent="HOSTED_CANDIDATE_ADMISSION", require_phase_receipts=False)
        require(sum(len(value) for value in self.raw_files.values())
                + sum(len(dag2_encoded(value, 262144))+1 for value in audit_documents.values()) <= 27262976, "SIZE_LIMIT")
        for filename, value in audit_documents.items():
            write_dag2_json(self.root / "audit" / filename, value, 262144)


def dag2_update_acceptance_target(events):
    matches = [event for event in events if event["event_type"] == "WorkflowExecutionUpdateAccepted"]
    return (matches[0]["event_id"], False) if matches else None


def dag2_cancel_target(events):
    matches = [event for event in events if event["event_type"] == "WorkflowExecutionCancelRequested"]
    require(len(matches) == 1, "CANCEL_MISMATCH")
    return matches[0]["event_id"], False


def dag2_failed_activity_consumed(events):
    failed = [event["event_id"] for event in events if event["event_type"] == "ActivityTaskFailed"]
    return bool(failed and any(event["event_type"] == "WorkflowTaskCompleted" and event["event_id"] > failed[-1]
                               for event in events))


def dag2_validator_refusal(error):
    from temporalio.client import WorkflowUpdateFailedError
    from temporalio.exceptions import ApplicationError
    return (type(error) is WorkflowUpdateFailedError and type(error.cause) is ApplicationError
            and error.cause.type == "TemporalDagUpdateRejected"
            and tuple(error.cause.details) == ("UPDATE_REFUSED",))


class Dag2DiagnosticState(DiagnosticState):
    def __init__(self, requested_revision):
        super().__init__(requested_revision)
        self.cleanup_observation = "NOT_STARTED"

    def capture(self, error, *, slot="primary_failure", phase=None):
        from verify_temporal_server_gate import DAG2_SCHEMAS, GateError
        allowed = DAG2_SCHEMAS["failure"]["properties"]
        require(slot in {"primary_failure", "cleanup_failure", "audit_failure"}, "INTERNAL_ERROR")
        if getattr(self, slot) is not None:
            return
        code = "INTERNAL_ERROR"
        if type(error) in {GateRunError, GateError}:
            args = BaseException.args.__get__(error, type(error))
            if len(args) == 1 and type(args[0]) is str and args[0] in allowed["code"]["enum"]:
                code = args[0]
        chosen_phase = self.phase if phase is None else phase
        if chosen_phase not in allowed["phase"]["enum"]:
            chosen_phase = {"cleanup": "observation_cleanup", "audit_write": "evidence_write",
                            "server_launch": "start", "server_readiness": "start", "client_connect": "start",
                            "input_seeding": "bootstrap", "sdk_binding": "bootstrap"}.get(chosen_phase, "execution")
        setattr(self, slot, {"phase": chosen_phase, "code": code})

    def record(self):
        failed = any((self.primary_failure, self.cleanup_failure, self.audit_failure))
        return {"schema_version": "opendot.temporal.dag2-gate.diagnostic.v1", "evidence_class": DAG2_CLASS,
            "primary_failure": self.primary_failure, "cleanup_failure": self.cleanup_failure,
            "audit_failure": self.audit_failure,
            "cleanup_status": "UNCONFIRMED" if self.cleanup_failure else self.cleanup_observation,
            "evidence_status": "INCOMPLETE" if failed else "COMPLETE", "result": "FAIL" if failed else "PASS"}

    def write(self, audit):
        write_dag2_json(audit / "dag2-diagnostic.json", self.record(), 4096)


def dag2_check_source(source, manifest, identity):
    require(type(manifest) is dict and set(manifest) == {"schema_version", "commit", "tree", "files"}
            and manifest["schema_version"] == "opendot.temporal.dag2-gate.source-manifest.v1"
            and manifest["commit"] == identity["commit"] and manifest["tree"] == identity["tree"], "SOURCE_MISMATCH")
    rows = manifest["files"]
    require(type(rows) is list and 1 <= len(rows) <= 512, "SOURCE_MISMATCH")
    names = [row["path"] for row in rows]
    require(names == sorted(set(names)) and set(DAG2_SOURCE_CLOSURE) <= set(names), "SOURCE_MISMATCH")
    # The operator supplies exact reviewed paths; no filesystem or CAS discovery.
    for row in rows:
        require(set(row) == {"path", "mode", "sha256", "size_bytes"} and row["mode"] in {"100644", "100755"}
                and re.fullmatch(r"[A-Za-z0-9._/-]{1,256}", row["path"]) is not None
                and not Path(row["path"]).is_absolute() and all(part not in {".", "..", ""} for part in row["path"].split("/")),
                "SOURCE_MISMATCH")
        path = source / row["path"]
        require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(source.resolve()), "SOURCE_MISMATCH")
        data = path.read_bytes()
        require(0 < len(data) <= 4194304 and len(data) == row["size_bytes"] and sha(data) == row["sha256"]
                and ("100755" if path.stat().st_mode & 0o111 else "100644") == row["mode"], "SOURCE_MISMATCH")
    workflow = next(row for row in rows if row["path"] == ".github/workflows/temporal-server.yml")
    require(workflow["sha256"] == identity["workflow_sha256"], "WORKFLOW_MISMATCH")


def dag2_preflight(root, cli, source):
    environment = preflight(root, cli, source)
    from acquire_temporal_cli import _require_unconfigured_proxy_routing
    _require_unconfigured_proxy_routing()
    manifest_path = Path(os.environ["OPENDOT_TEMPORAL_DAG2_SOURCE_MANIFEST"])
    manifest_bytes = manifest_path.read_bytes()
    require(0 < len(manifest_bytes) <= 131072, "SIZE_LIMIT")
    require(sha(manifest_bytes) == os.environ["OPENDOT_TEMPORAL_DAG2_SOURCE_MANIFEST_SHA256"], "SOURCE_MISMATCH")
    manifest = strict_load(manifest_path, 131072)
    repo = os.environ["GITHUB_REPOSITORY"]
    run, attempt = os.environ["GITHUB_RUN_ID"], os.environ["GITHUB_RUN_ATTEMPT"]
    workflow_id = os.environ["OPENDOT_TEMPORAL_DAG2_WORKFLOW_ID"]
    require(all(re.fullmatch(r"[1-9][0-9]{0,14}", value) is not None for value in (run, attempt, workflow_id))
            and int(attempt) <= 999, "CI_IDENTITY")
    tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=source, text=True).strip()
    identity = {"repository": repo, "workflow_path": ".github/workflows/temporal-server.yml",
        "workflow_id": int(workflow_id), "workflow_sha256": os.environ["OPENDOT_TEMPORAL_DAG2_WORKFLOW_SHA256"],
        "commit": os.environ["OPENDOT_TEMPORAL_EXPECTED_REVISION"], "tree": tree,
        "ref": os.environ["GITHUB_REF"], "event": os.environ["GITHUB_EVENT_NAME"],
        "run_id": int(run), "run_attempt": int(attempt),
        "run_url": f"https://github.com/{repo}/actions/runs/{run}/attempts/{attempt}",
        "qualification": "dag2", "retain_public_evidence": False}
    require(tree == os.environ["OPENDOT_TEMPORAL_DAG2_EXPECTED_TREE"], "SOURCE_MISMATCH")
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=source).decode("utf-8").split("\0")[:-1]
    require(sorted(tracked) == [row["path"] for row in manifest["files"]], "SOURCE_MISMATCH")
    dag2_check_source(source, manifest, identity)
    from verify_temporal_server_gate import dag2_validate_schema
    dag2_validate_schema(identity, "identity")
    environment.update(dag2_source_manifest=manifest, dag2_source_manifest_bytes=manifest_bytes, dag2_identity=identity)
    return environment


def run_dag2_gate(root: Path, cli: Path, collected_nodes: list[str]):
    retain = os.environ.get("OPENDOT_TEMPORAL_RETAIN_PUBLIC_EVIDENCE", "false")
    dag2_selection(os.environ.get("GITHUB_EVENT_NAME"), os.environ.get("OPENDOT_TEMPORAL_QUALIFICATION"),
                   False if retain == "false" else retain, collected_nodes)
    require(root.is_absolute() and not root.exists(), "FRESH_GATE_ROOT_REQUIRED")
    require(root.parent.resolve() == Path(os.environ["RUNNER_TEMP"]).resolve(), "RUNNER_TEMP_REQUIRED")
    source = Path(__file__).resolve().parents[1]
    root.mkdir(mode=0o700)
    for name in ("server", "cas", "private", "audit", "home"):
        (root / name).mkdir(mode=0o700)
    requested = os.environ.get("OPENDOT_TEMPORAL_EXPECTED_REVISION")
    diagnostic, loop, runner = Dag2DiagnosticState(requested), None, None
    try:
        environment = dag2_preflight(root, cli, source)
        logging.basicConfig(filename=root / "private" / "sdk.log", level=logging.ERROR, force=True)
        loop = asyncio.new_event_loop()
        runner = Dag2Runner(root, cli, environment, diagnostic)
        result = loop.run_until_complete(runner.execute())
        return {**result, "dag2": runner.documents, "validated": runner.validated}
    except Exception as error:
        if runner is None:
            capture_diagnostic(diagnostic, error, slot="primary_failure", phase="preflight")
            diagnostic.write(root / "audit")
        raise GateRunError("SERVER_GATE_FAILED") from None
    finally:
        if loop is not None and not asyncio.all_tasks(loop):
            loop.close()


DAG2_EVIDENCE_FILES = ('acquisition-receipt.json',
 'collected-nodes.txt',
 'dag-sdk-summary.json',
 'dag2-cleanup.json',
 'dag2-diagnostic.json',
 'dag2-environment.json',
 'dag2-originals.json',
 'dag2-replays.json',
 'dag2-trace.json',
 'no-ref-cancel-final.history.json',
 'no-ref-cancel-final.state.json',
 'no-ref-unknown.history.json',
 'no-ref-unknown.state.json',
 'normal-a.result.json',
 'normal-b.result.json',
 'normal-final.history.json',
 'normal-final.state.json',
 'pip-report.json',
 'reconcile-a.result.json',
 'reconcile-b.result.json',
 'reconcile-final.history.json',
 'reconcile-final.state.json',
 'reconcile-unknown-after-replacement.history.json',
 'reconcile-unknown-after-replacement.state.json',
 'reconcile-unknown-before-stop.history.json',
 'reconcile-unknown-before-stop.state.json',
 'reconcile-update-queued.history.json',
 'reconcile-update-queued.state.json',
 'required-nodes.txt',
 'results.xml',
 'shared-unit-summary.json',
 'source-manifest.json')


def finalize_dag2_evidence(root, *, pytest_exit_code, receipt_sources):
    """Pure exact-path post-pytest finalization, inside the original service budget."""
    from verify_temporal_server_gate import parse_junit, dag2_validate_schema
    require(type(pytest_exit_code) is int and pytest_exit_code == 0, "TEST_FAILED")
    require(root.is_absolute() and root.parent.resolve() == Path(os.environ["RUNNER_TEMP"]).resolve()
            and root.is_dir() and not root.is_symlink(), "READ_FAILED")
    expected_receipts = {"acquisition-receipt.json", "pip-report.json", "source-manifest.json",
                         "shared-unit-summary.json", "dag-sdk-summary.json", "required-nodes.txt",
                         "collected-nodes.txt", "results.xml"}
    require(type(receipt_sources) is dict and set(receipt_sources) == expected_receipts, "MISSING_EVIDENCE")
    timing = strict_load(root / "private" / "dag2-timing.json", 4096)
    require(set(timing) == {"schema_version", "service_started_ns", "evidence_started_ns"}
            and timing["schema_version"] == "opendot.temporal.dag2-private-timing.v1"
            and all(type(timing[key]) is int and 0 < timing[key] <= 10**18
                    for key in ("service_started_ns", "evidence_started_ns")), "INVALID_SCHEMA")
    deadline = min(timing["service_started_ns"] + 240000000000,
                   timing["evidence_started_ns"] + 30000000000)
    require(timing["service_started_ns"] <= timing["evidence_started_ns"] <= time.monotonic_ns() < deadline,
            "DEADLINE_EXHAUSTED")
    audit = root / "audit"
    diagnostic = strict_load(audit / "dag2-diagnostic.json", 4096)
    dag2_validate_schema(diagnostic, "diagnostic")
    require(diagnostic["result"] == "PASS" and diagnostic["evidence_status"] == "COMPLETE", "TEST_FAILED")
    files = {}
    for name in sorted(expected_receipts):
        path = receipt_sources[name]
        require(type(path) is Path or isinstance(path, Path), "INVALID_TYPE")
        require(path.is_file() and not path.is_symlink(), "READ_FAILED")
        data = path.read_bytes()
        require(0 < len(data) <= 2097152, "SIZE_LIMIT")
        files[name] = data
    expected_nodes = ("\n".join(DAG2_REQUIRED_NODES) + "\n").encode("utf-8")
    require(files["required-nodes.txt"] == files["collected-nodes.txt"] == expected_nodes, "COLLECTION_MISMATCH")
    xml = parse_junit(receipt_sources["results.xml"])
    cases = list(xml.iter("testcase"))
    require(len(cases) == 7, "JUNIT_IDENTITY")
    actual = []
    for case in cases:
        require(case.get("classname") == "tests.acceptance.temporal_dag_recovery_gate"
                and not any(child.tag in {"error", "failure", "skipped", "properties"} for child in case), "TEST_FAILED")
        actual.append("tests/acceptance/temporal_dag_recovery_gate.py::" + case.get("name", ""))
    require(actual == DAG2_REQUIRED_NODES, "JUNIT_IDENTITY")
    for name, data in files.items():
        write_dag2_bytes(audit / name, data, 2097152)
    cleanup = strict_load(audit / "dag2-cleanup.json", 262144)
    cleanup["evidence_and_pytest_elapsed_ms"] = (time.monotonic_ns() - timing["evidence_started_ns"]) // 1000000
    dag2_validate_schema(cleanup, "cleanup")
    # Replace the preliminary elapsed observation once. No absent record is invented.
    replacement = root / "private" / "dag2-cleanup-final.json"
    write_dag2_json(replacement, cleanup, 262144)
    replacement.replace(audit / "dag2-cleanup.json")
    manifest_files = []
    for name in DAG2_EVIDENCE_FILES:
        path = audit / name
        require(path.is_file() and not path.is_symlink() and path.resolve().parent == audit.resolve(), "READ_FAILED")
        data = path.read_bytes()
        require(0 < len(data) <= 2097152, "SIZE_LIMIT")
        manifest_files.append({"file_id": name, "sha256": sha(data), "size_bytes": len(data)})
    manifest = {"schema_version": "opendot.temporal.dag2-gate.manifest.v1", "evidence_class": DAG2_CLASS,
                "files": manifest_files, "aggregate_bytes": sum(row["size_bytes"] for row in manifest_files)}
    dag2_validate_schema(manifest, "manifest")
    raw = dag2_encoded(manifest, 262144) + b"\n"
    require(manifest["aggregate_bytes"] + len(raw) + 8192 <= 27262976, "SIZE_LIMIT")
    require(time.monotonic_ns() < deadline, "DEADLINE_EXHAUSTED")
    write_dag2_bytes(audit / "dag2-manifest.json", raw, 262144)
    require(time.monotonic_ns() < deadline, "DEADLINE_EXHAUSTED")


def dag2_main():
    import argparse
    parser = argparse.ArgumentParser(description="Fixed DAG2 post-pytest evidence finalizer")
    parser.add_argument("command", choices=["finalize-dag2-evidence"])
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--pytest-exit-code", type=int, required=True)
    for name in ("acquisition-receipt", "pip-report", "source-manifest", "shared-unit-summary",
                 "dag-sdk-summary", "required-nodes", "collected-nodes", "junit"):
        parser.add_argument("--" + name, type=Path, required=True)
    options = parser.parse_args()
    sources = {"acquisition-receipt.json": options.acquisition_receipt, "pip-report.json": options.pip_report,
        "source-manifest.json": options.source_manifest, "shared-unit-summary.json": options.shared_unit_summary,
        "dag-sdk-summary.json": options.dag_sdk_summary, "required-nodes.txt": options.required_nodes,
        "collected-nodes.txt": options.collected_nodes, "results.xml": options.junit}
    try:
        finalize_dag2_evidence(options.root, pytest_exit_code=options.pytest_exit_code, receipt_sources=sources)
    except Exception:
        print("DAG2_EVIDENCE_FINALIZATION_FAILED")
        return 1
    print("DAG2_EVIDENCE_FINALIZED_REQUIRES_VERIFICATION")
    return 0


if __name__ == "__main__":
    raise SystemExit(dag2_main())
