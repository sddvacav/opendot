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
                info = await self.client.workflow_service.get_system_info(
                    GetSystemInfoRequest(), retry=False, timeout=timedelta(seconds=2))
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
        self.server.send_signal(signal.SIGINT)
        while self.server.poll() is None and time.monotonic() - start < 8:
            await asyncio.sleep(.05)
        row["shutdown_seconds"] = round(time.monotonic() - start, 6)
        row["exit_code"] = self.server.poll()
        row["graceful_exit_observed"] = row["exit_code"] == 0
        if not row["graceful_exit_observed"]:
            self.stop_uncertain = True
            raise GateRunError("SERVER_STOP_UNCONFIRMED")
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
            try:
                await self.bounded(entry["worker"].shutdown(), 5, "WORKER_STOP_UNCONFIRMED", cleanup=True)
                await self.bounded(entry["task"], 1, "WORKER_STOP_UNCONFIRMED", cleanup=True)
            except Exception:
                self.stop_uncertain = True
                raise
            row["public_shutdown_completed"] = True
            if entry["executor"] is not None:
                entry["executor"].shutdown(wait=True)

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
