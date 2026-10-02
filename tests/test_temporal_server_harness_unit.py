# SPDX-License-Identifier: Apache-2.0
"""Static/fake harness tests only. These never start or import the real SDK."""
from __future__ import annotations
import ast
from datetime import timedelta
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading
import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("temporal_harness_unit", ROOT / "ci/run_temporal_server_gate.py")
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def test_import_does_not_load_sdk_or_start_service():
    tree = ast.parse((ROOT / "ci/run_temporal_server_gate.py").read_text())
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = node.module if isinstance(node, ast.ImportFrom) else " ".join(n.name for n in node.names)
            assert "temporalio" not in module


def test_server_filename_is_not_default_discovery():
    path = ROOT / "tests/acceptance/temporal_server_gate.py"
    assert path.is_file() and not path.name.startswith("test_") and not path.name.endswith("_test.py")
    nodes = (ROOT / "ci/temporal-server-nodes.txt").read_text().splitlines()
    tree = ast.parse(path.read_text())
    actual = ["tests/acceptance/temporal_server_gate.py::" + n.name for n in tree.body
              if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]
    assert len(actual) == 7 and nodes == actual
    assert all("importorskip" not in path.read_text() and "skipif" not in path.read_text() for _ in [0])


def test_fixed_loopback_command_and_no_shell(tmp_path):
    cmd = m.fixed_command(Path("/fixed/temporal"), tmp_path)
    assert cmd == ["/fixed/temporal", "server", "start-dev", "--ip", "127.0.0.1", "--port", "7233",
                   "--http-port", "7243", "--metrics-port", "9090", "--headless", "--db-filename",
                   str(tmp_path / "server/temporal.sqlite"), "--log-level", "error"]


def test_child_environment_ignores_credentials_and_proxy(monkeypatch, tmp_path):
    for key in ("TEMPORAL_ADDRESS", "TEMPORAL_API_KEY", "AWS_SECRET_ACCESS_KEY", "HTTPS_PROXY", "HOME"):
        monkeypatch.setenv(key, "sensitive-untrusted-value")
    env = m.child_environment(tmp_path)
    assert set(env) == {"PATH", "HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "TMPDIR", "LANG", "TERM"}
    assert not any("sensitive" in value for value in env.values())


def test_explicit_gate_refuses_before_external_action(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENDOT_TEMPORAL_EXECUTE", raising=False)
    def forbidden(*args, **kwargs):
        raise AssertionError("external operation must not happen")
    monkeypatch.setattr(m.subprocess, "check_output", forbidden)
    monkeypatch.setattr(m.subprocess, "Popen", forbidden)
    with pytest.raises(m.GateRunError, match="EXECUTION_NOT_ENABLED"):
        m.preflight(tmp_path, tmp_path / "temporal", ROOT)


@pytest.mark.parametrize("value,expected", [(timedelta(seconds=10),10),(timedelta(seconds=60),60),
                                            (None,None),(10,None),(timedelta(microseconds=1),None)])
def test_received_timeout_is_not_defaulted(value, expected):
    assert m.seconds(value) == expected


@pytest.mark.parametrize("body", [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}'])
def test_json_duplicate_and_nonfinite_refused(tmp_path, body):
    path = tmp_path / "bad.json"; path.write_bytes(body)
    with pytest.raises(m.GateRunError):
        m.strict_load(path)


def test_counter_independent_order_and_thread_safety():
    observed = m.Observations()
    threads = [threading.Thread(target=observed.count, args=("null","handler_enter",6)) for _ in range(10)]
    for thread in threads: thread.start()
    for thread in threads: thread.join()
    assert [r["sequence"] for r in observed.counters] == list(range(1,11))
    assert observed.total("null","handler_enter") == 10
    assert observed.total("null","execute_enter") == 0


def wheel_report():
    return {"install":[{"metadata":{"name":"temporalio","version":"1.34.0"},"download_info":{
        "url":"https://files.pythonhosted.org/packages/temporalio-1.34.0-cp310-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
        "archive_info":{"hashes":{"sha256":m.SDK_SHA}}}}]}


def test_sdk_hash_comes_from_report(tmp_path):
    path = tmp_path / "pip.json"; path.write_text(json.dumps(wheel_report()))
    assert m.verified_sdk_wheel(path) == m.SDK_SHA


@pytest.mark.parametrize("mutation", ["missing","duplicate","wrong_hash","wrong_version","wrong_host","sdist"])
def test_sdk_report_faults(tmp_path, mutation):
    report = wheel_report(); item = report["install"][0]
    if mutation == "missing": report["install"] = []
    if mutation == "duplicate": report["install"].append(item)
    if mutation == "wrong_hash": item["download_info"]["archive_info"]["hashes"]["sha256"] = "0"*64
    if mutation == "wrong_version": item["metadata"]["version"] = "1.33.0"
    if mutation == "wrong_host": item["download_info"]["url"] = item["download_info"]["url"].replace("files.pythonhosted.org","example.org")
    if mutation == "sdist": item["download_info"]["url"] = "https://files.pythonhosted.org/a.tar.gz"
    path=tmp_path/"pip.json"; path.write_text(json.dumps(report))
    with pytest.raises(m.GateRunError): m.verified_sdk_wheel(path)


def test_no_kill_cancellation_proc_or_dependency_fallback():
    tree = ast.parse((ROOT / "ci/run_temporal_server_gate.py").read_text())
    calls = [n for n in ast.walk(tree) if isinstance(n,ast.Call)]
    forbidden = {"kill","terminate","killpg","cancel","reset_workflow_execution","start_time_skipping","start_local","importorskip"}
    assert not any(isinstance(n.func,ast.Attribute) and n.func.attr in forbidden for n in calls)
    assert not any(isinstance(n.func,ast.Name) and n.func.id in forbidden for n in calls)
    assert not any(isinstance(n,ast.Constant) and isinstance(n.value,str) and "/proc" in n.value for n in ast.walk(tree))


def test_public_workflow_has_readonly_permissions_and_private_logs():
    source = (ROOT / ".github/workflows/temporal-server.yml").read_text()
    assert "contents: read" in source and "timeout-minutes: 10" in source
    assert "cancel-in-progress: false" in source
    assert "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683" in source
    assert "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065" in source
    assert 'opendot-temporal-pytest-private.log" 2>&1' in source
    assert "--force-reinstall --report" in source and "--require-hashes" in source
    assert "uses: actions/upload-artifact" not in source and "secrets." not in source


def test_quiescence_requires_independent_handler_return():
    runner = m.Runner.__new__(m.Runner)
    runner.diagnostic = m.DiagnosticState("0" * 40)
    runner.observed = m.Observations()
    runner.pending = {}
    assert runner.quiescent()
    runner.observed.count("durability_replay", "handler_enter", 3)
    assert not runner.quiescent()
    runner.observed.count("durability_replay", "handler_return", 3)
    assert runner.quiescent()
    runner.observed.in_flight = 1
    assert not runner.quiescent()
    runner.observed.in_flight = 0
    runner.pending["durability_replay"] = object()
    assert not runner.quiescent()


def test_expired_deadline_never_schedules_operation(monkeypatch):
    import asyncio
    runner = m.Runner.__new__(m.Runner)
    runner.diagnostic = m.DiagnosticState("0" * 40)
    runner.deadline = -1
    def forbidden(*args, **kwargs):
        raise AssertionError("must not schedule")
    monkeypatch.setattr(m.asyncio, "ensure_future", forbidden)
    with pytest.raises(m.GateRunError, match="GATE_DEADLINE"):
        asyncio.run(runner.bounded(object(), 1, "TEST"))


def test_no_shutdown_while_handler_has_not_returned():
    import asyncio
    runner = m.Runner.__new__(m.Runner)
    runner.diagnostic = m.DiagnosticState("0" * 40)
    runner.observed = m.Observations()
    runner.pending = {}
    runner.workers = []
    runner.server = object()
    runner.observed.count("durability_replay", "handler_enter", 3)
    with pytest.raises(m.GateRunError, match="NOT_QUIESCENT"):
        asyncio.run(runner.stop_workers())
    with pytest.raises(m.GateRunError, match="NOT_QUIESCENT"):
        asyncio.run(runner.stop_server())


def test_bounded_timeout_does_not_cancel_owned_operation():
    import asyncio
    import time
    async def exercise():
        runner = m.Runner.__new__(m.Runner)
        runner.diagnostic = m.DiagnosticState("0" * 40)
        runner.deadline = time.monotonic() + 1
        completed = []
        async def operation():
            await asyncio.sleep(.01)
            completed.append(True)
        task = asyncio.create_task(operation())
        with pytest.raises(m.GateRunError, match="TEST_TIMEOUT"):
            await runner.bounded(task, .0001, "TEST_TIMEOUT")
        assert not task.cancelled()
        await task
        assert completed == [True]
    asyncio.run(exercise())


def test_expired_runner_cannot_start_server_worker_or_workflow():
    import asyncio
    runner = m.Runner.__new__(m.Runner)
    runner.diagnostic = m.DiagnosticState("0" * 40)
    runner.deadline = -1
    for awaitable in (runner.start_server(), runner.start_worker("workflow"), runner.start_case("null")):
        with pytest.raises(m.GateRunError, match="GATE_DEADLINE"):
            asyncio.run(awaitable)


@pytest.fixture
def fake_ready_server(monkeypatch, tmp_path):
    """Drive only fake coroutines: no SDK import, event loop, socket, or process."""
    from types import ModuleType, SimpleNamespace
    state = SimpleNamespace(now=1000.0, events=[], clients=[], ready_clients=[], workers=[],
                            servers=[], waits=[], pending_tasks=[], info_results=[],
                            eager_error=None, hold_eager=False)

    def drive(coroutine):
        try:
            coroutine.send(None)
        except StopIteration as result:
            return result.value
        finally:
            coroutine.close()
        raise AssertionError("unexpected real coroutine suspension")

    class Task:
        def __init__(self, coroutine):
            self.coroutine, self.done, self.value, self.error = coroutine, False, None, None
        def step(self):
            if self.done:
                return
            try:
                self.coroutine.send(None)
            except StopIteration as result:
                self.done, self.value = True, result.value
            except BaseException as error:
                self.done, self.error = True, error
        def result(self):
            assert self.done
            if self.error is not None:
                raise self.error
            return self.value

    class Hold:
        def __await__(self):
            yield self

    def ensure_future(awaitable):
        return awaitable if isinstance(awaitable, Task) else Task(awaitable)

    async def wait(tasks, timeout):
        assert len(tasks) == 1
        state.waits.append(timeout)
        task = next(iter(tasks))
        task.step()
        if task.done:
            return {task}, set()
        state.pending_tasks.append(task)
        state.now += timeout
        return set(), {task}

    async def sleep(seconds):
        state.events.append(("sleep", seconds))
        state.now += seconds

    def create_task(coroutine):
        task = Task(coroutine)
        task.step()
        return task

    class Socket:
        def __init__(self, family, kind):
            assert (family, kind) == (m.socket.AF_INET, m.socket.SOCK_STREAM)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def bind(self, address):
            state.events.append(("bind", address))

    class Server:
        def __init__(self, command, **kwargs):
            assert command == m.fixed_command(runner.cli, runner.root)
            assert kwargs == {"stdin": m.subprocess.DEVNULL, "stdout": runner.server_log,
                              "stderr": m.subprocess.STDOUT, "env": m.child_environment(runner.root)}
            self.exit_code = None
            state.servers.append(self)
            state.events.append(("launch", len(state.servers)))
        def poll(self):
            return self.exit_code
        def send_signal(self, value):
            assert value == m.signal.SIGINT
            state.events.append(("shutdown", len(state.servers)))
            self.exit_code = 0

    class GetSystemInfoRequest:
        pass

    class Client:
        def __init__(self, lazy):
            self.lazy, self.connected = lazy, not lazy
            self.workflow_service = SimpleNamespace(get_system_info=self.get_system_info)
        @classmethod
        async def connect(cls, address, **kwargs):
            state.events.append(("connect", address, dict(kwargs), runner.diagnostic.phase))
            assert address == "127.0.0.1:7233"
            assert kwargs == {"namespace": "default", "identity": "opendot-gate-client",
                              "lazy": kwargs["lazy"]}
            if kwargs["lazy"] is False:
                if state.eager_error is not None:
                    raise state.eager_error
                if state.hold_eager:
                    await Hold()
            client = cls(kwargs["lazy"])
            state.clients.append(client)
            if not client.lazy:
                state.ready_clients.append(client)
            state.now += .02 if client.lazy else .04
            state.events.append(("connected", client))
            return client
        async def get_system_info(self, request, **kwargs):
            assert self.lazy is True
            assert type(request) is GetSystemInfoRequest
            assert kwargs == {"retry": False, "timeout": timedelta(seconds=2)}
            assert runner.diagnostic.phase == "server_readiness"
            state.events.append(("probe", self))
            state.now += .03
            result = state.info_results.pop(0) if state.info_results else "1.32.0"
            if isinstance(result, Exception):
                raise result
            self.connected = True
            return SimpleNamespace(server_version=result)
        async def start_workflow(self, *args, **kwargs):
            state.events.append(("dispatch", self))
            assert self in state.ready_clients and self.lazy is False
            return SimpleNamespace(id=kwargs["id"], first_execution_run_id="fake-run")
        def get_workflow_handle(self, workflow_id, *, run_id):
            state.events.append(("handle", self))
            return SimpleNamespace(id=workflow_id, run_id=run_id)

    class Worker:
        def __init__(self, client, **kwargs):
            state.events.append(("worker", client, kwargs))
            # Model the SDK guard, including its rejection of a connected probe.
            if client.lazy:
                raise RuntimeError("fake Worker rejects a lazy client")
            assert client.connected and client in state.ready_clients
            self.client = client
            state.workers.append(self)
        async def run(self):
            state.events.append(("worker_run", self.client))
        async def shutdown(self):
            state.events.append(("worker_shutdown", self.client))

    class RetryPolicy:
        def __init__(self, **kwargs):
            assert kwargs == {"maximum_attempts": 1}

    for name in ("temporalio", "temporalio.client", "temporalio.worker", "temporalio.common",
                 "temporalio.api", "temporalio.api.workflowservice", "temporalio.api.workflowservice.v1"):
        monkeypatch.setitem(sys.modules, name, ModuleType(name))
    sys.modules["temporalio.client"].Client = Client
    sys.modules["temporalio.worker"].Worker = Worker
    sys.modules["temporalio.common"].RetryPolicy = RetryPolicy
    sys.modules["temporalio.common"].WorkflowIDReusePolicy = SimpleNamespace(REJECT_DUPLICATE="reject")
    sys.modules["temporalio.api.workflowservice.v1"].GetSystemInfoRequest = GetSystemInfoRequest
    monkeypatch.setattr(m, "socket", SimpleNamespace(socket=Socket, AF_INET=m.socket.AF_INET,
                                                     SOCK_STREAM=m.socket.SOCK_STREAM))
    monkeypatch.setattr(m, "subprocess", SimpleNamespace(Popen=Server, DEVNULL=m.subprocess.DEVNULL,
                                                         STDOUT=m.subprocess.STDOUT))
    monkeypatch.setattr(m, "time", SimpleNamespace(monotonic=lambda: state.now))
    monkeypatch.setattr(m, "asyncio", SimpleNamespace(ensure_future=ensure_future, wait=wait,
                                                     sleep=sleep, create_task=create_task))
    for name in ("private", "audit"):
        (tmp_path / name).mkdir()
    runner = m.Runner.__new__(m.Runner)
    runner.root, runner.cli, runner.environment = tmp_path, tmp_path / "temporal", {}
    runner.diagnostic = m.DiagnosticState("0" * 40)
    runner.started, runner.deadline = state.now, state.now + 180
    runner.server = runner.server_log = runner.client = runner.replay = None
    runner.stop_uncertain = runner.activity_ever_started = False
    runner.observed = m.Observations()
    runner.server_rows, runner.worker_rows, runner.workers = [], [], []
    runner.histories, runner.outcomes = [], []
    runner.pending, runner.responses = {}, {}
    runner.requests = {scenario: {"scenario": scenario} for scenario in m.SCENARIOS}
    runner.workflow_class = SimpleNamespace(run=object())
    yield SimpleNamespace(runner=runner, state=state, drive=drive)
    for task in state.pending_tasks:
        if not task.done:
            task.coroutine.close()
    if runner.server_log is not None:
        runner.server_log.close()


def test_readiness_publicly_reconnects_before_worker_and_dispatch(fake_ready_server):
    runner, state, drive = (fake_ready_server.runner, fake_ready_server.state, fake_ready_server.drive)
    drive(runner.start_server())
    probe, ready = state.clients
    assert probe.connected and probe.lazy and ready.connected and not ready.lazy
    assert runner.client is ready
    assert runner.environment["server_version"] == "1.32.0"
    assert runner.server_rows[0]["readiness_seconds"] == .05
    assert state.waits == [2, 2]
    drive(runner.start_worker("workflow"))
    drive(runner.start_case("null"))
    assert [event[0] for event in state.events] == [
        "bind", "bind", "bind", "launch", "connect", "connected", "probe", "connect", "connected",
        "worker", "worker_run", "dispatch", "handle"]
    assert [event[1] for event in state.events if event[0] == "bind"] == [
        ("127.0.0.1", 7233), ("127.0.0.1", 7243), ("127.0.0.1", 9090)]
    assert [event[1:] for event in state.events if event[0] == "connect"] == [
        ("127.0.0.1:7233", {"namespace": "default", "identity": "opendot-gate-client", "lazy": lazy},
         "client_connect") for lazy in (True, False)]
    worker_event = next(event for event in state.events if event[0] == "worker")
    assert worker_event[1] is ready
    assert worker_event[2] == {
        "task_queue": m.QUEUE, "identity": "opendot-gate-workflow-worker",
        "graceful_shutdown_timeout": timedelta(seconds=5), "disable_eager_activity_execution": True,
        "workflows": [runner.workflow_class], "no_remote_activities": True, "max_cached_workflows": 0,
        "max_concurrent_workflow_tasks": 1, "max_concurrent_workflow_task_polls": 1}
    assert all(event[1] is ready for event in state.events if event[0] in {"dispatch", "handle"})


def test_readiness_probe_rpc_error_still_recovers_before_eager_connect(fake_ready_server):
    runner, state, drive = (fake_ready_server.runner, fake_ready_server.state, fake_ready_server.drive)
    state.info_results = [RuntimeError("fake transient probe RPC failure"), "1.32.0"]
    drive(runner.start_server())
    assert [event[0] for event in state.events][4:] == [
        "connect", "connected", "probe", "sleep", "probe", "connect", "connected"]
    assert [event[1] for event in state.events if event[0] == "sleep"] == [.1]
    assert len(state.clients) == 2 and runner.client is state.ready_clients[0]
    assert runner.server_rows[0]["readiness_seconds"] == .18
    assert state.waits == [2, 2]


def test_server_version_mismatch_prevents_eager_connect_and_worker(fake_ready_server):
    runner, state, drive = (fake_ready_server.runner, fake_ready_server.state, fake_ready_server.drive)
    state.info_results = ["wrong-version"]
    with pytest.raises(m.GateRunError, match="^SERVER_VERSION$"):
        drive(runner.start_server())
    assert len(state.clients) == 1 and state.clients[0].lazy
    assert not state.ready_clients and not state.workers and "server_version" not in runner.environment
    assert state.waits == [2] and runner.server_rows[0]["readiness_seconds"] is None
    assert runner.diagnostic.phase == "server_readiness"


@pytest.mark.parametrize("remaining,expected_bound", [(180, 2), (.3, .25)])
def test_eager_connect_uses_existing_cap_and_global_deadline(fake_ready_server, remaining, expected_bound):
    runner, state, drive = (fake_ready_server.runner, fake_ready_server.state, fake_ready_server.drive)
    runner.deadline = state.now + remaining
    original_deadline = runner.deadline
    drive(runner.start_server())
    assert state.waits[-1] == pytest.approx(expected_bound)
    assert state.waits[0] == pytest.approx(min(2, remaining))
    assert runner.deadline == original_deadline


@pytest.mark.parametrize("failure", ["exception", "timeout"])
def test_eager_connect_failure_prevents_dispatch_and_execute_cleans_up(
        fake_ready_server, diagnostic_verifier, failure):
    runner, state, drive = (fake_ready_server.runner, fake_ready_server.state, fake_ready_server.drive)
    if failure == "exception":
        state.eager_error = OSError("PRIVATE_EAGER_CONNECT_ERROR")
    else:
        state.hold_eager = True
    with pytest.raises(m.GateRunError, match="^SERVER_GATE_FAILED$"):
        drive(runner.execute())
    assert state.waits == [2, 2]
    assert len([event for event in state.events if event[0] == "connect"]) == 2
    assert not state.workers and not state.ready_clients
    assert not any(event[0] in {"worker", "worker_run", "dispatch", "handle"} for event in state.events)
    assert runner.quiescent() and runner.server is None and runner.server_log is None
    assert runner.stop_uncertain is False and runner.activity_ever_started is False
    cleanup = json.loads((runner.root / "audit/cleanup.json").read_text())
    assert cleanup["cleanup_status"] == "PASS" and cleanup["worker_generations"] == []
    assert cleanup["forced_termination_used"] is False
    assert cleanup["server_generations"][0]["shutdown_requested_signal"] == "SIGINT"
    assert cleanup["server_generations"][0]["graceful_exit_observed"] is True
    value = diagnostic_verifier.read_safe_diagnostic(runner.root / "audit", "0" * 40)["diagnostic"]
    assert value["primary_failure"] == {
        "phase": "client_connect", "reason_code": "CLIENT_CONNECT" if failure == "timeout" else "OS_ERROR",
        "exception_category": "gate_refusal" if failure == "timeout" else "os_error"}
    assert value["cleanup_failure"] is None and value["audit_failure"] is None
    assert "PRIVATE" not in json.dumps(value)
    if failure == "timeout":
        # The existing bounded helper never cancels its owned operation. Let the
        # fake finish late: no assignment, retry, worker, or dispatch follows.
        assert len(state.pending_tasks) == 1 and not state.pending_tasks[0].done
        state.pending_tasks[0].step()
        assert state.pending_tasks[0].done and len(state.ready_clients) == 1
        assert runner.client is state.clients[0] and runner.client.lazy
        assert not state.workers


def test_every_server_restart_replaces_probe_with_fresh_ready_client(fake_ready_server):
    runner, state, drive = (fake_ready_server.runner, fake_ready_server.state, fake_ready_server.drive)
    prior = None
    for generation in range(1, 4):
        drive(runner.start_server())
        probe, ready = state.clients[-2:]
        assert runner.client is ready and ready is not prior and probe is not ready
        assert probe.lazy and probe.connected and not ready.lazy and ready.connected
        assert runner.server_rows[-1]["generation"] == generation
        assert runner.server_rows[-1]["readiness_seconds"] == .05
        drive(runner.start_worker("workflow"))
        assert state.workers[-1].client is ready
        drive(runner.stop_workers())
        drive(runner.stop_server())
        prior = ready
    assert len({id(client) for client in state.clients}) == 6
    assert len(state.ready_clients) == len(state.workers) == 3
    assert [event[2]["lazy"] for event in state.events if event[0] == "connect"] == [True, False] * 3
    assert all(row["graceful_exit_observed"] for row in runner.server_rows)
    assert all(row["public_shutdown_completed"] for row in runner.worker_rows)


@pytest.mark.parametrize("uncertain", [True, False])
def test_runtime_uncertainty_is_latched_without_reconciliation(uncertain):
    from types import SimpleNamespace
    observed = m.Observations()
    result = (None, SimpleNamespace(execution_liveness={"reconciliation_required": uncertain}))
    observed_result = observed.execute_once("null", 6, lambda: result)
    assert observed_result is result
    assert observed.execution_uncertain is uncertain
    assert observed.total("null", "handler_enter") == observed.total("null", "handler_return") == 0
    runner = m.Runner.__new__(m.Runner)
    runner.diagnostic = m.DiagnosticState("0" * 40)
    runner.observed, runner.pending = observed, {}
    assert runner.quiescent() is (not uncertain)


def test_escaping_execute_exception_latches_uncertainty_and_propagates_identity():
    observed = m.Observations()
    error = RuntimeError("synthetic-control-error")
    def original():
        raise error
    with pytest.raises(RuntimeError) as caught:
        observed.execute_once("null", 6, original)
    assert caught.value is error and observed.execution_uncertain is True
    assert observed.total("null", "execute_enter") == 1


@pytest.fixture
def diagnostic_verifier(monkeypatch):
    # The helper is stdlib-only; loading it cannot import the optional SDK.
    monkeypatch.syspath_prepend(str(ROOT / "ci"))
    import verify_temporal_server_gate
    return verify_temporal_server_gate


@pytest.mark.parametrize("error,category,code", [
    (m.GateRunError("SERVER_READINESS"), "gate_refusal", "SERVER_READINESS"),
    (m.GateRunError("PRIVATE_SECRET_UNKNOWN_CODE"), "unknown_error", "UNKNOWN_ERROR"),
    (TimeoutError("PRIVATE_TIMEOUT"), "timeout_error", "TIMEOUT_ERROR"),
    (ModuleNotFoundError("PRIVATE_DEPENDENCY"), "dependency_error", "DEPENDENCY_ERROR"),
    (KeyError("PRIVATE_KEY"), "key_error", "KEY_ERROR"),
    (AttributeError("PRIVATE_ATTRIBUTE"), "attribute_error", "ATTRIBUTE_ERROR"),
    (TypeError("PRIVATE_TYPE"), "type_error", "TYPE_ERROR"),
    (ValueError("PRIVATE_VALUE"), "value_error", "VALUE_ERROR"),
    (OSError("PRIVATE_PATH"), "os_error", "OS_ERROR"),
    (RuntimeError("PRIVATE_UNKNOWN"), "unknown_error", "UNKNOWN_ERROR"),
    (type("PRIVATE_EXCEPTION_CLASS", (Exception,), {"__module__": None})("PRIVATE"),
        "unknown_error", "UNKNOWN_ERROR"),
    (type("RPCError", (Exception,), {"__module__": "temporalio.service"})("PRIVATE_RPC"),
        "sdk_error", "SDK_ERROR"),
])
def test_diagnostic_category_never_serializes_exception_text(diagnostic_verifier, error, category, code):
    state = m.DiagnosticState("0" * 40)
    state.phase = "client_connect"
    state.capture(error)
    value = state.record()
    assert value["status"] == "FAILED"
    assert value["primary_failure"] == {"phase": "client_connect", "reason_code": code,
                                          "exception_category": category}
    assert "PRIVATE" not in json.dumps(value)


def test_primary_diagnostic_is_not_replaced_by_later_failures(diagnostic_verifier):
    state = m.DiagnosticState("0" * 40)
    state.phase = "workflow_worker_start"
    state.capture(TypeError("PRIVATE_PRIMARY"))
    state.capture(ValueError("PRIVATE_LATER_PRIMARY"))
    state.capture(OSError("PRIVATE_CLEANUP"), slot="cleanup_failure", phase="worker_shutdown")
    state.capture(ValueError("PRIVATE_AUDIT"), slot="audit_failure", phase="audit_write")
    value = state.record()
    assert value["primary_failure"]["reason_code"] == "TYPE_ERROR"
    assert value["cleanup_failure"]["reason_code"] == "OS_ERROR"
    assert value["audit_failure"]["reason_code"] == "VALUE_ERROR"
    assert "PRIVATE" not in json.dumps(value)


def fake_diagnostic_runner(tmp_path):
    from types import MethodType
    runner = m.Runner.__new__(m.Runner)
    runner.diagnostic = m.DiagnosticState("0" * 40)
    runner.root = tmp_path
    (tmp_path / "audit").mkdir()
    runner.environment = {"synthetic_unit_fixture": True}
    runner.histories, runner.outcomes, runner.replay = [], [], None
    runner.observed = m.Observations()
    runner.diagnostic = m.DiagnosticState("0" * 40)
    async def cases(self):
        self.diagnostic.phase = "client_connect"
        raise TypeError("PRIVATE_PRIMARY_DETAIL")
    async def cleanup(self):
        return {"cleanup_status": "PASS", "synthetic_unit_fixture": True}
    runner.run_cases = MethodType(cases, runner)
    runner.cleanup = MethodType(cleanup, runner)
    return runner


def test_early_failure_preserves_diagnostic_despite_empty_jsonl(tmp_path, diagnostic_verifier):
    import asyncio
    runner = fake_diagnostic_runner(tmp_path)
    with pytest.raises(m.GateRunError, match="SERVER_GATE_FAILED"):
        asyncio.run(runner.execute())
    audit = tmp_path / "audit"
    assert (audit / "activity-metadata.jsonl").read_bytes() == b""
    with pytest.raises(diagnostic_verifier.GateError, match="SIZE_LIMIT"):
        diagnostic_verifier.read_jsonl(audit / "activity-metadata.jsonl")
    report = diagnostic_verifier.read_safe_diagnostic(audit, "0" * 40)
    assert report["validation"] == "VALID"
    value = report["diagnostic"]
    assert value["primary_failure"] == {"phase": "client_connect", "reason_code": "TYPE_ERROR",
                                          "exception_category": "type_error"}
    assert value["cleanup_failure"] is None and value["audit_failure"] is None
    assert "PRIVATE" not in (audit / "diagnostic.json").read_text()


@pytest.mark.parametrize("failure_slot", ["cleanup_failure", "audit_failure"])
def test_secondary_cleanup_or_audit_failure_does_not_mask_primary(tmp_path, diagnostic_verifier, failure_slot):
    import asyncio
    from types import MethodType
    runner = fake_diagnostic_runner(tmp_path)
    if failure_slot == "cleanup_failure":
        async def cleanup(self):
            self.diagnostic.phase = "worker_shutdown"
            raise OSError("PRIVATE_CLEANUP_PATH")
        runner.cleanup = MethodType(cleanup, runner)
    else:
        def write_audit(self, cleanup):
            raise OSError("PRIVATE_AUDIT_PATH")
        runner.write_audit = MethodType(write_audit, runner)
    with pytest.raises(m.GateRunError, match="SERVER_GATE_FAILED"):
        asyncio.run(runner.execute())
    report = diagnostic_verifier.read_safe_diagnostic(tmp_path / "audit", "0" * 40)
    assert report["validation"] == "VALID"
    value = report["diagnostic"]
    assert value["primary_failure"]["reason_code"] == "TYPE_ERROR"
    assert value[failure_slot]["reason_code"] == "OS_ERROR"
    assert "PRIVATE" not in json.dumps(value)


def test_unconfirmed_cleanup_stays_failed_with_safe_reason(tmp_path, diagnostic_verifier):
    import asyncio
    from types import MethodType
    runner = fake_diagnostic_runner(tmp_path)
    async def cleanup(self):
        return {"cleanup_status": "UNCONFIRMED"}
    runner.cleanup = MethodType(cleanup, runner)
    with pytest.raises(m.GateRunError):
        asyncio.run(runner.execute())
    report = diagnostic_verifier.read_safe_diagnostic(tmp_path / "audit", "0" * 40)
    assert report["validation"] == "VALID"
    value = report["diagnostic"]
    assert value["cleanup_failure"] == {"phase": "cleanup", "reason_code": "CLEANUP_UNCONFIRMED",
                                          "exception_category": "gate_refusal"}


def test_diagnostic_write_is_not_retried_after_failure(tmp_path, diagnostic_verifier):
    import asyncio
    runner = fake_diagnostic_runner(tmp_path)
    calls = []
    error = OSError("PRIVATE_WRITE_FAILURE")
    def write(audit):
        calls.append(audit)
        raise error
    runner.diagnostic.write = write
    with pytest.raises(OSError) as caught:
        asyncio.run(runner.execute())
    assert caught.value is error and calls == [tmp_path / "audit"]
    assert runner.diagnostic.primary_failure["reason_code"] == "TYPE_ERROR"
    assert not (tmp_path / "audit/diagnostic.json").exists()


def test_bootstrap_missing_revision_records_only_safe_missing_config(tmp_path, monkeypatch, diagnostic_verifier):
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
    monkeypatch.delenv("OPENDOT_TEMPORAL_EXPECTED_REVISION", raising=False)
    def forbidden(*args, **kwargs):
        raise AssertionError("bootstrap must not launch external work")
    monkeypatch.setattr(m.subprocess, "Popen", forbidden)
    root = tmp_path / "gate"
    with pytest.raises(m.GateRunError, match="SERVER_GATE_FAILED"):
        m.run_gate(root, tmp_path / "absent-cli", list(diagnostic_verifier.REQUIRED_NODES))
    report = diagnostic_verifier.read_safe_diagnostic(root / "audit", None)
    assert report["validation"] == "VALID"
    value = report["diagnostic"]
    assert value["requested_revision"] is None
    assert value["primary_failure"] == {"phase": "preflight", "reason_code": "KEY_ERROR",
                                          "exception_category": "key_error"}


def test_bootstrap_disabled_execution_records_denial_without_service(tmp_path, monkeypatch, diagnostic_verifier):
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
    monkeypatch.setenv("OPENDOT_TEMPORAL_EXPECTED_REVISION", "0" * 40)
    monkeypatch.setenv("OPENDOT_TEMPORAL_EXECUTE", "0")
    root = tmp_path / "gate"
    with pytest.raises(m.GateRunError, match="SERVER_GATE_FAILED"):
        m.run_gate(root, tmp_path / "absent-cli", list(diagnostic_verifier.REQUIRED_NODES))
    report = diagnostic_verifier.read_safe_diagnostic(root / "audit", "0" * 40)
    assert report["validation"] == "VALID"
    value = report["diagnostic"]
    assert value["primary_failure"] == {"phase": "preflight", "reason_code": "EXECUTION_NOT_ENABLED",
                                          "exception_category": "gate_refusal"}



def test_unknown_exception_metadata_cannot_replace_primary_failure(diagnostic_verifier):
    class UnreadableClass(type):
        def __getattribute__(cls, name):
            if name == "__module__":
                raise RuntimeError("PRIVATE_METADATA_ACCESS")
            return super().__getattribute__(name)
    class UnknownError(Exception, metaclass=UnreadableClass):
        pass
    state = m.DiagnosticState("0" * 40)
    state.phase = "client_connect"
    state.capture(UnknownError("PRIVATE_ORIGINAL"))
    value = state.record()
    assert value["primary_failure"] == {"phase": "client_connect", "reason_code": "UNKNOWN_ERROR",
                                          "exception_category": "unknown_error"}
    assert "PRIVATE" not in json.dumps(value)


@pytest.mark.parametrize("base,code", [
    (Exception, "UNKNOWN_ERROR"), (BaseException, "UNKNOWN_ERROR"),
    (TimeoutError, "TIMEOUT_ERROR"), (ImportError, "DEPENDENCY_ERROR"),
    (KeyError, "KEY_ERROR"), (AttributeError, "ATTRIBUTE_ERROR"),
    (TypeError, "TYPE_ERROR"), (ValueError, "VALUE_ERROR"), (OSError, "OS_ERROR"),
])
def test_diagnostic_uses_real_type_without_any_instance_metadata(diagnostic_verifier, base, code):
    accessed = []
    class Hostile(base):
        def __getattribute__(self, name):
            accessed.append(name)
            raise AssertionError("PRIVATE_INSTANCE_METADATA")
        def __str__(self):
            raise AssertionError("PRIVATE_STRING")
        def __repr__(self):
            raise AssertionError("PRIVATE_REPR")
    error = Hostile("PRIVATE_ARGS")
    state = m.DiagnosticState("0" * 40)
    state.capture(error)
    assert state.record()["primary_failure"]["reason_code"] == code
    assert m.is_interruption(error) is (base is BaseException)
    assert accessed == []


def test_spoofed_instance_class_cannot_claim_builtin_category(diagnostic_verifier):
    accessed = []
    class Spoof(Exception):
        @property
        def __class__(self):
            accessed.append(True)
            return TypeError
    state = m.DiagnosticState("0" * 40)
    state.capture(Spoof("PRIVATE_SPOOF"))
    assert state.record()["primary_failure"]["reason_code"] == "UNKNOWN_ERROR"
    assert accessed == []


@pytest.mark.parametrize("base,module,name,code", [
    (Exception, "private.module", "PrivateError", "UNKNOWN_ERROR"),
    (ValueError, "private.module", "PrivateError", "VALUE_ERROR"),
    (Exception, "temporalio.service", "RPCError", "SDK_ERROR"),
    (Exception, None, "RPCError", "UNKNOWN_ERROR"),
])
def test_diagnostic_bypasses_hostile_class_metadata(diagnostic_verifier, base, module, name, code):
    accessed = []
    class HostileClass(type):
        def __getattribute__(cls, key):
            accessed.append(key)
            raise AssertionError("PRIVATE_CLASS_METADATA")
        def __subclasscheck__(cls, other):
            raise AssertionError("PRIVATE_SUBCLASS_CHECK")
        def __eq__(cls, other):
            raise AssertionError("PRIVATE_CLASS_EQUALITY")
        def __hash__(cls):
            raise AssertionError("PRIVATE_CLASS_HASH")
    kind = HostileClass(name, (base,), {"__module__": module})
    error = kind("PRIVATE_ARGS")
    state = m.DiagnosticState("0" * 40)
    state.capture(error)
    assert state.record()["primary_failure"]["reason_code"] == code
    assert m.is_interruption(error) is False
    assert accessed == []


def test_own_gate_error_reads_only_builtin_args_descriptor(monkeypatch, diagnostic_verifier):
    accessed = []
    def forbidden(self, *args):
        accessed.append(True)
        raise AssertionError("PRIVATE_ARGS_DESCRIPTOR")
    error = m.GateRunError("SERVER_READINESS")
    monkeypatch.setattr(m.GateRunError, "__getattribute__", forbidden)
    monkeypatch.setattr(m.GateRunError, "args", property(forbidden))
    state = m.DiagnosticState("0" * 40)
    state.capture(error)
    assert state.record()["primary_failure"]["reason_code"] == "SERVER_READINESS"
    assert accessed == []


def test_foreign_gate_subclass_args_and_untrusted_code_stay_unknown(diagnostic_verifier):
    class Foreign(m.GateRunError):
        @property
        def args(self):
            raise AssertionError("PRIVATE_FOREIGN_ARGS")
    class SpoofCode(str):
        def __eq__(self, other):
            raise AssertionError("PRIVATE_CODE_EQUALITY")
        def __hash__(self):
            raise AssertionError("PRIVATE_CODE_HASH")
    for error in (Foreign("SERVER_READINESS"), m.GateRunError(SpoofCode("SERVER_READINESS")),
                  m.GateRunError(), m.GateRunError("SERVER_READINESS", "PRIVATE_EXTRA")):
        state = m.DiagnosticState("0" * 40)
        state.capture(error)
        assert state.record()["primary_failure"]["reason_code"] == "UNKNOWN_ERROR"


def test_every_emitted_phase_reason_category_combination_uses_shared_schema(diagnostic_verifier):
    examples = [(m.GateRunError(code), "gate_refusal", code)
                for code in sorted(diagnostic_verifier.DIAGNOSTIC_GATE_REASONS)]
    for kind, category in ((ImportError, "dependency_error"), (TypeError, "type_error"),
                          (ValueError, "value_error"), (AttributeError, "attribute_error"),
                          (KeyError, "key_error"), (OSError, "os_error"), (TimeoutError, "timeout_error"),
                          (RuntimeError, "unknown_error")):
        examples.append((kind("PRIVATE_CANARY"), category,
                         diagnostic_verifier.DIAGNOSTIC_GENERIC_REASONS[category]))
    examples.append((type("RPCError", (Exception,), {"__module__": "temporalio.service"})("PRIVATE"),
                     "sdk_error", "SDK_ERROR"))
    for slot, phases in (("primary_failure", diagnostic_verifier.DIAGNOSTIC_PHASES - {"complete"}),
                         ("cleanup_failure", {"cleanup", "worker_shutdown", "server_shutdown"}),
                         ("audit_failure", {"audit_write"})):
        for phase in sorted(phases):
            for error, category, code in examples:
                state = m.DiagnosticState("0" * 40)
                state.capture(error, slot=slot, phase=phase)
                record = diagnostic_verifier.validate_diagnostic(state.record(), "0" * 40)
                assert record[slot] == {"phase": phase, "reason_code": code,
                                        "exception_category": category}
                assert "PRIVATE" not in json.dumps(record)


def failing_stage_runner(tmp_path, primary=None, cleanup_error=None, audit_error=None):
    runner = fake_diagnostic_runner(tmp_path)
    calls = []
    async def cases():
        calls.append("cases")
        runner.diagnostic.phase = "client_connect"
        if primary is not None:
            raise primary
    async def cleanup():
        calls.append("cleanup")
        runner.diagnostic.phase = "worker_shutdown"
        if cleanup_error is not None:
            raise cleanup_error
        return {"cleanup_status": "PASS"}
    def audit(cleanup):
        calls.append("audit")
        if audit_error is not None:
            raise audit_error
    runner.run_cases, runner.cleanup, runner.write_audit = cases, cleanup, audit
    return runner, calls


def test_primary_cleanup_and_audit_failures_preserve_order_and_phases(tmp_path, diagnostic_verifier):
    import asyncio
    runner, calls = failing_stage_runner(tmp_path, TypeError("PRIVATE_PRIMARY"),
                                         OSError("PRIVATE_CLEANUP"), ValueError("PRIVATE_AUDIT"))
    with pytest.raises(m.GateRunError, match="SERVER_GATE_FAILED"):
        asyncio.run(runner.execute())
    assert calls == ["cases", "cleanup", "audit"]
    value = diagnostic_verifier.read_safe_diagnostic(tmp_path / "audit", "0" * 40)["diagnostic"]
    for slot, phase, code in (("primary_failure", "client_connect", "TYPE_ERROR"),
                             ("cleanup_failure", "worker_shutdown", "OS_ERROR"),
                             ("audit_failure", "audit_write", "VALUE_ERROR")):
        assert value[slot]["phase"] == phase and value[slot]["reason_code"] == code
    assert "PRIVATE" not in json.dumps(value)


@pytest.mark.parametrize("capture_mode", ["throws", "no_op"])
@pytest.mark.parametrize("failed_slot", ["primary_failure", "cleanup_failure", "audit_failure"])
def test_capture_fault_cannot_skip_cleanup_or_turn_failure_into_success(
        tmp_path, diagnostic_verifier, capture_mode, failed_slot):
    import asyncio
    error = TypeError("PRIVATE_ORIGINAL")
    runner, calls = failing_stage_runner(tmp_path,
        error if failed_slot == "primary_failure" else None,
        error if failed_slot == "cleanup_failure" else None,
        error if failed_slot == "audit_failure" else None)
    captures = []
    def capture(error, *, slot, phase):
        captures.append((error, slot, phase))
        if capture_mode == "throws":
            raise RuntimeError("PRIVATE_CAPTURE_FAILURE")
    runner.diagnostic.capture = capture
    with pytest.raises(m.GateRunError, match="SERVER_GATE_FAILED"):
        asyncio.run(runner.execute())
    assert calls == ["cases", "cleanup", "audit"]
    assert len(captures) == 1 and captures[0][0] is error and captures[0][1] == failed_slot
    report = diagnostic_verifier.read_safe_diagnostic(tmp_path / "audit", "0" * 40)
    assert report["validation"] == "VALID" and report["diagnostic"]["status"] == "FAILED"
    assert report["diagnostic"][failed_slot]["reason_code"] == "UNKNOWN_ERROR"
    assert report["diagnostic"][failed_slot]["phase"] == captures[0][2]
    assert "PRIVATE" not in json.dumps(report)


def test_capture_and_storage_unavailable_leave_explicit_diagnostic_gap(tmp_path, diagnostic_verifier):
    import asyncio
    class Unavailable(m.DiagnosticState):
        def capture(self, error, **kwargs):
            raise RuntimeError("PRIVATE_CAPTURE_FAILURE")
        def __setattr__(self, name, value):
            if name == "primary_failure" and value is not None:
                raise OSError("PRIVATE_STORAGE_FAILURE")
            super().__setattr__(name, value)
    runner, calls = failing_stage_runner(tmp_path, TypeError("PRIVATE_PRIMARY"), OSError("PRIVATE_CLEANUP"))
    runner.diagnostic = Unavailable("0" * 40)
    writes = []
    runner.diagnostic.write = lambda audit: writes.append(audit)
    with pytest.raises(m.GateRunError, match="SERVER_GATE_FAILED"):
        asyncio.run(runner.execute())
    assert calls == ["cases", "cleanup", "audit"]
    assert writes == [] and runner.diagnostic.primary_failure is None
    report = diagnostic_verifier.read_safe_diagnostic(tmp_path / "audit", "0" * 40)
    assert report["validation"] == "UNAVAILABLE" and report["reason_code"] == "DIAGNOSTIC_UNAVAILABLE"
    assert report["diagnostic"] is None and "PRIVATE" not in json.dumps(report)


@pytest.mark.parametrize("interrupted_stage", ["primary", "cleanup", "audit"])
@pytest.mark.parametrize("write_fails", [True, False])
def test_true_interruption_rethrows_original_identity_after_cleanup_and_one_write(
        tmp_path, diagnostic_verifier, interrupted_stage, write_fails):
    class Interrupted(BaseException):
        def __getattribute__(self, name):
            if name in {"__class__", "args"}:
                raise AssertionError("PRIVATE_INTERRUPTION_METADATA")
            return super().__getattribute__(name)
    original = Interrupted("PRIVATE_INTERRUPT")
    runner, calls = failing_stage_runner(tmp_path,
        original if interrupted_stage == "primary" else TypeError("PRIVATE_PRIMARY"),
        original if interrupted_stage == "cleanup" else OSError("PRIVATE_CLEANUP"),
        original if interrupted_stage == "audit" else ValueError("PRIVATE_AUDIT"))
    writes = []
    write = runner.diagnostic.write
    def tracked_write(audit):
        writes.append(audit)
        if write_fails:
            raise OSError("PRIVATE_WRITE")
        write(audit)
    runner.diagnostic.write = tracked_write
    # The fake stages never suspend. Drive only this coroutine so the test
    # does not ask asyncio's own task machinery to inspect a hostile exception.
    with pytest.raises(Interrupted) as caught:
        runner.execute().send(None)
    assert caught.value is original
    assert calls == ["cases", "cleanup", "audit"] and writes == [tmp_path / "audit"]
    if not write_fails:
        assert diagnostic_verifier.read_safe_diagnostic(tmp_path / "audit", "0" * 40)["validation"] == "VALID"


def test_interruption_survives_capture_failure(tmp_path, diagnostic_verifier):
    import asyncio
    class Interrupted(BaseException):
        pass
    error = Interrupted("PRIVATE_INTERRUPT")
    runner, calls = failing_stage_runner(tmp_path, error)
    def fail_capture(*args, **kwargs):
        raise RuntimeError("PRIVATE_CAPTURE")
    runner.diagnostic.capture = fail_capture
    with pytest.raises(Interrupted) as caught:
        asyncio.run(runner.execute())
    assert caught.value is error and calls == ["cases", "cleanup", "audit"]
    value = diagnostic_verifier.read_safe_diagnostic(tmp_path / "audit", "0" * 40)["diagnostic"]
    assert value["primary_failure"]["reason_code"] == "UNKNOWN_ERROR"


def test_diagnostic_publication_failure_never_returns_success(tmp_path, diagnostic_verifier):
    import asyncio
    runner, calls = failing_stage_runner(tmp_path)
    writes = []
    error = OSError("PRIVATE_WRITE_FAILURE")
    def write(audit):
        writes.append(audit)
        raise error
    runner.diagnostic.write = write
    with pytest.raises(OSError) as caught:
        asyncio.run(runner.execute())
    assert caught.value is error and calls == ["cases", "cleanup", "audit"]
    assert writes == [tmp_path / "audit"] and not (tmp_path / "audit/diagnostic.json").exists()


@pytest.mark.parametrize("storage_gap", [True, False])
def test_first_real_interruption_precedes_capture_faults(tmp_path, diagnostic_verifier, storage_gap):
    class Interrupted(BaseException):
        pass
    original = Interrupted("PRIVATE_CLEANUP_INTERRUPTION")
    later = Interrupted("PRIVATE_CAPTURE_INTERRUPTION")
    runner, calls = failing_stage_runner(tmp_path, TypeError("PRIVATE_PRIMARY"), original)
    class FailedCapture(m.DiagnosticState):
        def capture(self, error, **kwargs):
            raise later
        def __setattr__(self, name, value):
            if storage_gap and name == "primary_failure" and value is not None:
                raise OSError("PRIVATE_STORAGE")
            super().__setattr__(name, value)
    runner.diagnostic = FailedCapture("0" * 40)
    with pytest.raises(Interrupted) as caught:
        runner.execute().send(None)
    assert caught.value is original and calls == ["cases", "cleanup", "audit"]
    report = diagnostic_verifier.read_safe_diagnostic(tmp_path / "audit", "0" * 40)
    assert report["validation"] == ("UNAVAILABLE" if storage_gap else "VALID")


def test_capture_interruption_is_rethrown_after_cleanup(tmp_path, diagnostic_verifier):
    class Interrupted(BaseException):
        pass
    original = Interrupted("PRIVATE_CAPTURE_INTERRUPTION")
    runner, calls = failing_stage_runner(tmp_path, TypeError("PRIVATE_PRIMARY"))
    def capture(*args, **kwargs):
        raise original
    runner.diagnostic.capture = capture
    with pytest.raises(Interrupted) as caught:
        runner.execute().send(None)
    assert caught.value is original and calls == ["cases", "cleanup", "audit"]
    value = diagnostic_verifier.read_safe_diagnostic(tmp_path / "audit", "0" * 40)["diagnostic"]
    assert value["primary_failure"]["reason_code"] == "UNKNOWN_ERROR"


def test_uncertain_diagnostic_publication_is_never_overwritten(tmp_path, monkeypatch, diagnostic_verifier):
    import asyncio
    runner, calls = failing_stage_runner(tmp_path, TypeError("PRIVATE_PRIMARY"))
    write_json = m.write_json
    writes = []
    error = OSError("PRIVATE_AFTER_PUBLICATION")
    def uncertain_write(path, value):
        writes.append(path)
        write_json(path, value)
        raise error
    monkeypatch.setattr(m, "write_json", uncertain_write)
    with pytest.raises(OSError) as caught:
        asyncio.run(runner.execute())
    assert caught.value is error and calls == ["cases", "cleanup", "audit"]
    assert writes == [tmp_path / "audit/diagnostic.json"]
    value = diagnostic_verifier.read_safe_diagnostic(tmp_path / "audit", "0" * 40)["diagnostic"]
    assert value["primary_failure"]["reason_code"] == "TYPE_ERROR"


def test_bootstrap_wrapper_does_not_recapture_or_rewrite_runner_failure(tmp_path, monkeypatch, diagnostic_verifier):
    calls = []
    runner_type = m.Runner
    def runner_factory(root, cli, environment, diagnostic):
        runner = runner_type.__new__(runner_type)
        runner.root, runner.diagnostic = root, diagnostic
        async def cases():
            calls.append("cases")
            diagnostic.phase = "client_connect"
            raise TypeError("PRIVATE_PRIMARY")
        async def cleanup():
            calls.append("cleanup")
            return {"cleanup_status": "PASS"}
        runner.run_cases, runner.cleanup = cases, cleanup
        runner.write_audit = lambda cleanup: calls.append("audit")
        return runner
    def capture(*args, **kwargs):
        calls.append("capture")
        raise RuntimeError("PRIVATE_CAPTURE")
    def write(*args, **kwargs):
        calls.append("write")
        raise OSError("PRIVATE_WRITE")
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
    monkeypatch.setenv("OPENDOT_TEMPORAL_EXPECTED_REVISION", "0" * 40)
    monkeypatch.setattr(m, "preflight", lambda *args: {})
    monkeypatch.setattr(m, "Runner", runner_factory)
    monkeypatch.setattr(m.DiagnosticState, "capture", capture)
    monkeypatch.setattr(m.DiagnosticState, "write", write)
    with pytest.raises(m.GateRunError, match="SERVER_GATE_FAILED"):
        m.run_gate(tmp_path / "gate", tmp_path / "unused-cli", list(diagnostic_verifier.REQUIRED_NODES))
    assert calls == ["cases", "cleanup", "audit", "capture", "write"]
    report = diagnostic_verifier.read_safe_diagnostic(tmp_path / "gate/audit", "0" * 40)
    assert report["validation"] == "UNAVAILABLE"


def test_storage_interruption_survives_ordinary_capture_failure(tmp_path, diagnostic_verifier):
    class Interrupted(BaseException):
        pass
    original = Interrupted("PRIVATE_STORAGE_INTERRUPTION")
    class Unavailable(m.DiagnosticState):
        def capture(self, error, **kwargs):
            raise RuntimeError("PRIVATE_CAPTURE")
        def __setattr__(self, name, value):
            if name == "primary_failure" and value is not None:
                raise original
            super().__setattr__(name, value)
    runner, calls = failing_stage_runner(tmp_path, TypeError("PRIVATE_PRIMARY"))
    runner.diagnostic = Unavailable("0" * 40)
    with pytest.raises(Interrupted) as caught:
        runner.execute().send(None)
    assert caught.value is original and calls == ["cases", "cleanup", "audit"]
    report = diagnostic_verifier.read_safe_diagnostic(tmp_path / "audit", "0" * 40)
    assert report["validation"] == "UNAVAILABLE" and report["diagnostic"] is None


# BATCH_PREPARATION_TESTS: self-contained stdlib section, also collectable by pytest.
import unittest as _batch_unittest
import sys as _batch_sys
import importlib as _batch_importlib
from copy import deepcopy as _batch_copy
from pathlib import Path as _BatchPath
import hashlib as _batch_hashlib

_batch_root = _BatchPath(__file__).resolve().parents[1]
if str(_batch_root / "ci") not in _batch_sys.path:
    _batch_sys.path.insert(0, str(_batch_root / "ci"))
_batch_gate = _batch_importlib.import_module("verify_temporal_server_gate")
_batch_harness = _batch_importlib.import_module("run_temporal_server_gate")


def _batch_ack(job):
    index = int(job["job_id"][-3:])
    return {"job_id": job["job_id"], "workflow_id": job["workflow_id"],
            "run_id": f"00000000-0000-0000-0000-{index + 1:012x}"}


def _batch_harness_result(job):
    index = int(job["job_id"][-3:])
    return {**_batch_ack(job), "activity_id": _batch_gate.ACTIVITY_ID,
            "invocation_id": f"inv-{index:03d}", "attempt": 1, "receipt_id": f"{index + 1:024x}",
            "input_artifact_id": job["input_artifact_id"],
            "result_artifact_id": "sha256:" + _batch_hashlib.sha256(("result-" + job["job_id"]).encode()).hexdigest(),
            "result_input_artifact_id": job["input_artifact_id"], "result_size_bytes": 1024,
            "tool_status": "COMPLETED", "semantic_valid": True, "output": 199,
            "reconciliation_required": False, "transport_status": "COMPLETED"}


class BatchHarnessPreparationTests(_batch_unittest.TestCase):
    def fresh(self):
        return _batch_harness.BatchAdmission(_batch_gate.frozen_batch_plan(), dict(_batch_gate.BATCH_PROFILE))

    def finish(self, controller, index):
        result = _batch_harness_result(_batch_gate.frozen_batch_plan()["jobs"][index])
        controller.record_outcome(result)
        self.assertTrue(controller.observe_terminal(result))
        return result

    def test_batch_rejects_invalid_or_over_budget_plan_before_submission(self):
        for mutation in ("empty", "199", "201", "duplicate", "unknown", "payload", "order", "overflow", "boolean"):
            with self.subTest(mutation=mutation):
                plan = _batch_gate.frozen_batch_plan()
                if mutation == "empty": plan["jobs"] = []
                if mutation == "199": plan["jobs"].pop()
                if mutation == "201": plan["jobs"].append(_batch_copy(plan["jobs"][0]))
                if mutation == "duplicate": plan["jobs"][1] = _batch_copy(plan["jobs"][0])
                if mutation == "unknown": plan["jobs"][0]["job_id"] = "private-canary"
                if mutation == "payload": plan["jobs"][0]["payload"]["right"] = 200
                if mutation == "order": plan["jobs"].reverse()
                if mutation == "overflow": plan["output_allowance_bytes"] += 1
                if mutation == "boolean": plan["jobs"][0]["payload"]["left"] = False
                with self.assertRaises(_batch_gate.GateError):
                    _batch_harness.BatchAdmission(plan, dict(_batch_gate.BATCH_PROFILE))
                calls = []
                with self.assertRaises(_batch_gate.GateError):
                    _batch_harness.build_batch_factory_fixture(plan, dict(_batch_gate.BATCH_PROFILE),
                        executor_factory=lambda **kw: calls.append(kw), worker_factory=lambda **kw: calls.append(kw))
                self.assertEqual(calls, [])

    def test_batch_reserves_attempt_before_rpc_and_never_refunds_unknown_ack(self):
        for unknown in ("raise", "none", "wrong_job", "malformed"):
            with self.subTest(unknown=unknown):
                controller = self.fresh()
                calls = []
                def rpc(job):
                    state = controller.snapshot()
                    self.assertEqual(state["reserved_attempt_allowance"], 200)
                    self.assertEqual(state["reserved_output_allowance_bytes"], 3276800)
                    self.assertEqual((state["attempts_consumed"], state["outstanding"]), (1, 1))
                    self.assertTrue(state["jobs"][job["job_id"]]["reserved"])
                    calls.append(job["job_id"])
                    if unknown == "raise": raise RuntimeError("PRIVATE_EXCEPTION_MUST_NOT_ESCAPE")
                    if unknown == "none": return None
                    if unknown == "wrong_job": return _batch_ack(_batch_gate.frozen_batch_plan()["jobs"][1])
                    return {**_batch_ack(job), "private_path": "/private/canary"}
                with self.assertRaisesRegex(_batch_harness.GateRunError, "^BATCH_RPC_UNCERTAIN$"):
                    controller.submit_next(rpc)
                self.assertEqual(calls, ["batch-000"])
                self.assertEqual(controller.snapshot()["outstanding"], 1)
                self.assertEqual(controller.snapshot()["attempts_consumed"], 1)
                with self.assertRaises(_batch_harness.GateRunError): controller.submit_next(rpc)
                self.assertEqual(calls, ["batch-000"])

    def test_batch_window_stops_at_sixteen_and_refills_only_validated_terminal(self):
        controller, calls = self.fresh(), []
        def rpc(job):
            calls.append(job["job_id"])
            return _batch_ack(job)
        for _ in range(16): self.assertIsNotNone(controller.submit_next(rpc))
        for _ in range(1000): self.assertIsNone(controller.submit_next(rpc))
        self.assertEqual(len(calls), 16)
        result = _batch_harness_result(_batch_gate.frozen_batch_plan()["jobs"][0])
        controller.record_outcome(result)
        self.assertIsNone(controller.submit_next(rpc))
        self.assertTrue(controller.observe_terminal(result))
        self.assertEqual(controller.submit_next(rpc), "batch-016")
        self.assertIsNone(controller.submit_next(rpc))
        self.assertEqual(controller.snapshot()["peak_outstanding"], 16)

    def test_batch_duplicate_completion_does_not_release_capacity_twice(self):
        controller = self.fresh()
        for _ in range(16): controller.submit_next(_batch_ack)
        result = self.finish(controller, 0)
        with self.assertRaises(_batch_harness.GateRunError): controller.observe_terminal(result)
        self.assertEqual(controller.snapshot()["outstanding"], 15)
        self.assertTrue(controller.snapshot()["uncertainty_latched"])
        with self.assertRaises(_batch_harness.GateRunError): controller.submit_next(_batch_ack)

    def test_batch_liveness_uncertainty_latches_and_prohibits_further_submission(self):
        for reason in sorted(_batch_gate.BATCH_UNCERTAINTY_REASONS):
            with self.subTest(reason=reason):
                controller = self.fresh()
                controller.submit_next(_batch_ack)
                controller.mark_uncertain("batch-000", reason)
                self.finish(controller, 0)
                self.assertTrue(controller.snapshot()["uncertainty_latched"])
                self.assertEqual(controller.snapshot()["attempts_consumed"], 1)
                with self.assertRaises(_batch_harness.GateRunError): controller.submit_next(_batch_ack)
        controller = self.fresh()
        with self.assertRaises(_batch_harness.GateRunError): controller.submit_next(lambda _: None)
        controller.acknowledge(_batch_ack(_batch_gate.frozen_batch_plan()["jobs"][0]))
        self.finish(controller, 0)
        self.assertTrue(controller.snapshot()["uncertainty_latched"])
        with self.assertRaises(_batch_harness.GateRunError): controller.submit_next(_batch_ack)

    def test_batch_worker_caps_match_external_executor_without_owner_mutation(self):
        calls = []
        def factory(**kwargs):
            calls.append(kwargs)
            return object()
        created = _batch_harness.build_batch_factory_fixture(_batch_gate.frozen_batch_plan(),
            dict(_batch_gate.BATCH_PROFILE), executor_factory=factory, worker_factory=factory)
        self.assertEqual(calls[0]["max_workers"], 8)
        self.assertEqual(calls[1]["max_concurrent_activities"], 8)
        self.assertIs(calls[1]["activity_executor"], created["executor"])
        self.assertEqual(calls[1]["max_concurrent_activity_task_polls"], 1)
        self.assertEqual(calls[2]["max_concurrent_workflow_tasks"], 1)
        self.assertEqual(calls[2]["max_concurrent_workflow_task_polls"], 1)
        self.assertEqual(calls[2]["max_cached_workflows"], 0)
        self.assertTrue(calls[1]["disable_eager_activity_execution"])
        self.assertTrue(calls[2]["disable_eager_activity_execution"])
        for key in _batch_gate.BATCH_PROFILE:
            with self.subTest(key=key):
                profile = dict(_batch_gate.BATCH_PROFILE)
                del profile[key]
                before = len(calls)
                with self.assertRaises(_batch_gate.GateError):
                    _batch_harness.build_batch_factory_fixture(_batch_gate.frozen_batch_plan(), profile,
                        executor_factory=factory, worker_factory=factory)
                self.assertEqual(len(calls), before)
        for path, expected in _batch_gate.BATCH_OWNER_SHA256.items():
            self.assertEqual(_batch_hashlib.sha256((_batch_root / path).read_bytes()).hexdigest(), expected)

    def test_batch_finishes_exactly_two_hundred_with_no_extra_submission(self):
        controller, calls = self.fresh(), []
        def rpc(job):
            calls.append(job["job_id"])
            return _batch_ack(job)
        for index in range(200):
            self.assertEqual(controller.submit_next(rpc), f"batch-{index:03d}")
            self.finish(controller, index)
        self.assertIsNone(controller.submit_next(rpc))
        state = controller.snapshot()
        self.assertEqual((state["attempts_consumed"], state["validated_terminal"], state["outstanding"]), (200, 200, 0))
        self.assertEqual(len(set(calls)), 200)
        self.assertFalse(state["uncertainty_latched"])

    def test_batch_unknown_duplicate_or_swapped_results_do_not_release_capacity(self):
        for mutation in ("no_original", "unknown", "run", "attempt", "swapped", "failed", "reconciliation", "duplicate_ack"):
            with self.subTest(mutation=mutation):
                controller = self.fresh()
                controller.submit_next(_batch_ack)
                result = _batch_harness_result(_batch_gate.frozen_batch_plan()["jobs"][0])
                if mutation == "duplicate_ack":
                    with self.assertRaises(_batch_harness.GateRunError): controller.acknowledge(_batch_ack(_batch_gate.frozen_batch_plan()["jobs"][0]))
                else:
                    if mutation != "no_original": controller.record_outcome(result)
                    if mutation == "unknown": result["job_id"] = "batch-199"
                    if mutation == "run": result["run_id"] = "00000000-0000-0000-0000-000000000002"
                    if mutation == "attempt": result["attempt"] = 2
                    if mutation == "swapped": result["result_artifact_id"] = "sha256:" + "0" * 64
                    if mutation == "failed": result["tool_status"] = "FAILED"
                    if mutation == "reconciliation": result["reconciliation_required"] = True
                    with self.assertRaises(_batch_harness.GateRunError): controller.observe_terminal(result)
                self.assertEqual(controller.snapshot()["outstanding"], 1)
                self.assertTrue(controller.snapshot()["uncertainty_latched"])

    def test_batch_input_and_snapshot_mutation_cannot_change_reserved_original(self):
        plan = _batch_gate.frozen_batch_plan()
        controller = _batch_harness.BatchAdmission(plan, dict(_batch_gate.BATCH_PROFILE))
        plan["jobs"][0]["payload"]["left"] = 999
        def rpc(job):
            self.assertEqual(job["payload"]["left"], 0)
            ack = _batch_ack(job)
            job["payload"]["left"] = 777
            state = controller.snapshot()
            state["jobs"]["batch-000"]["reserved"] = False
            return ack
        controller.submit_next(rpc)
        self.finish(controller, 0)
        self.assertEqual(controller.snapshot()["validated_terminal"], 1)


# V2: Future-controlled asyncio preparation. No sleeps or real service.
import asyncio as _batch_asyncio


async def _batch_async_turn():
    ready = _batch_asyncio.get_running_loop().create_future()
    _batch_asyncio.get_running_loop().call_soon(ready.set_result, None)
    await ready


class BatchAsyncPreparationTests(_batch_unittest.TestCase):
    def fresh(self):
        return _batch_harness.BatchAdmission(_batch_gate.frozen_batch_plan(), dict(_batch_gate.BATCH_PROFILE))

    def settle(self, controller, index):
        result = _batch_harness_result(_batch_gate.frozen_batch_plan()["jobs"][index])
        controller.record_outcome(result)
        self.assertTrue(controller.observe_terminal(result))

    def test_async_reserves_before_callback_invocation_and_await(self):
        async def exercise():
            for asynchronous in (False, True):
                controller = self.fresh()
                def check(job):
                    state = controller.snapshot()
                    self.assertEqual((state["attempts_consumed"], state["outstanding"]), (1, 1))
                    self.assertEqual(state["reserved_attempt_allowance"], 200)
                    self.assertEqual(state["reserved_output_allowance_bytes"], 3276800)
                    self.assertTrue(state["jobs"][job["job_id"]]["reserved"])
                    self.assertIsNone(state["jobs"][job["job_id"]]["run_id"])
                    return _batch_ack(job)
                def sync_callback(job):
                    result = _batch_asyncio.get_running_loop().create_future()
                    result.set_result(check(job))
                    return result
                async def async_callback(job):
                    return check(job)
                self.assertEqual(await controller.submit_next_async(
                    async_callback if asynchronous else sync_callback), "batch-000")
                self.assertFalse(controller.snapshot()["start_observation_pending"])
                self.settle(controller, 0)
        _batch_asyncio.run(exercise())

    def test_async_single_producer_blocks_overlap_mixed_modes_and_foreign_owners(self):
        async def exercise():
            controller = self.fresh()
            entered = _batch_asyncio.Event()
            release = _batch_asyncio.get_running_loop().create_future()
            calls = []
            def callback(job):
                calls.append(job["job_id"])
                entered.set()
                return release
            task = _batch_asyncio.create_task(controller.submit_next_async(callback))
            await entered.wait()
            with self.assertRaises(_batch_harness.GateRunError):
                await controller.submit_next_async(callback)
            with self.assertRaises(_batch_harness.GateRunError):
                controller.submit_next(_batch_ack)
            thread = controller._owner_thread
            controller._owner_thread = thread + 1
            with self.assertRaises(_batch_harness.GateRunError):
                controller.mark_uncertain("batch-000", "UNKNOWN_ACK")
            controller._owner_thread = thread
            self.assertFalse(controller.snapshot()["uncertainty_latched"])
            release.set_result(_batch_ack(_batch_gate.frozen_batch_plan()["jobs"][0]))
            self.assertEqual(await task, "batch-000")
            with self.assertRaises(_batch_harness.GateRunError):
                await controller.submit_next_async(callback)
            self.assertEqual(calls, ["batch-000"])
            return controller
        controller = _batch_asyncio.run(exercise())
        async def other_loop():
            with self.assertRaises(_batch_harness.GateRunError):
                await controller.submit_next_async(lambda _: self.fail("foreign loop callback"))
        _batch_asyncio.run(other_loop())
        self.assertEqual(controller.snapshot()["attempts_consumed"], 1)
        synchronous = self.fresh()
        synchronous.submit_next(_batch_ack)
        async def cannot_mix():
            with self.assertRaises(_batch_harness.GateRunError):
                await synchronous.submit_next_async(lambda _: self.fail("mixed callback"))
        _batch_asyncio.run(cannot_mix())

    def test_async_cancellation_before_entry_or_already_pending_issues_no_rpc(self):
        async def exercise():
            controller = self.fresh()
            task = _batch_asyncio.create_task(controller.submit_next_async(
                lambda _: self.fail("unstarted cancelled callback")))
            task.cancel()
            with self.assertRaises(_batch_asyncio.CancelledError): await task
            self.assertEqual(controller.snapshot()["attempts_consumed"], 0)
            self.assertFalse(controller.snapshot()["uncertainty_latched"])
            self.assertIsNone(controller.snapshot()["submission_mode"])
            pending = self.fresh()
            async def cancelled_producer():
                _batch_asyncio.current_task().cancel()
                await pending.submit_next_async(lambda _: self.fail("already cancelling callback"))
            task = _batch_asyncio.create_task(cancelled_producer())
            with self.assertRaises(_batch_asyncio.CancelledError): await task
            self.assertEqual(pending.snapshot()["attempts_consumed"], 0)
            self.assertTrue(pending.snapshot()["uncertainty_latched"])
        _batch_asyncio.run(exercise())

    def test_async_cancelled_start_retains_and_observes_late_ack_without_reopening(self):
        async def exercise():
            controller = self.fresh()
            entered = _batch_asyncio.Event()
            reply = _batch_asyncio.get_running_loop().create_future()
            def start(job):
                entered.set()
                return reply
            producer = _batch_asyncio.create_task(controller.submit_next_async(start))
            await entered.wait()
            owned = controller._pending_start["task"]
            # A server-side event may already have occurred here; it is not an
            # invented ack or input to the ack-first fabricated trace schema.
            self.assertIsNone(controller.snapshot()["jobs"]["batch-000"]["run_id"])
            producer.cancel()
            with self.assertRaises(_batch_asyncio.CancelledError): await producer
            state = controller.snapshot()
            self.assertTrue(state["uncertainty_latched"])
            self.assertTrue(state["start_observation_pending"])
            self.assertEqual((state["attempts_consumed"], state["outstanding"]), (1, 1))
            self.assertFalse(owned.cancelled())
            reply.set_result(_batch_ack(_batch_gate.frozen_batch_plan()["jobs"][0]))
            await owned
            await _batch_async_turn()
            self.assertFalse(controller.snapshot()["start_observation_pending"])
            self.assertIsNotNone(controller.snapshot()["jobs"]["batch-000"]["run_id"])
            self.settle(controller, 0)
            self.assertEqual(controller.snapshot()["outstanding"], 0)
            self.assertTrue(controller.snapshot()["uncertainty_latched"])
            with self.assertRaises(_batch_harness.GateRunError):
                await controller.submit_next_async(lambda _: self.fail("uncertain refill"))
            with self.assertRaises(_batch_harness.GateRunError):
                controller.acknowledge(_batch_ack(_batch_gate.frozen_batch_plan()["jobs"][0]))
        _batch_asyncio.run(exercise())

    def test_async_done_future_and_swallowed_cancellation_never_pass_cleanly(self):
        async def exercise():
            for swallowed in (False, True):
                controller = self.fresh()
                def immediate(job):
                    _batch_asyncio.current_task().cancel()
                    ready = _batch_asyncio.get_running_loop().create_future()
                    ready.set_result(_batch_ack(job))
                    return ready
                async def swallowing(job):
                    _batch_asyncio.current_task().cancel()
                    try:
                        await _batch_asyncio.get_running_loop().create_future()
                    except _batch_asyncio.CancelledError:
                        return _batch_ack(job)
                producer = _batch_asyncio.create_task(controller.submit_next_async(
                    swallowing if swallowed else immediate))
                with self.assertRaises(_batch_asyncio.CancelledError): await producer
                pending = controller._pending_start
                if pending is not None:
                    await pending["task"]
                await _batch_async_turn()
                state = controller.snapshot()
                self.assertTrue(state["uncertainty_latched"])
                self.assertEqual((state["attempts_consumed"], state["outstanding"]), (1, 1))
                self.assertFalse(state["start_observation_pending"])
        _batch_asyncio.run(exercise())

    def test_async_exceptions_timeouts_invalid_awaitables_and_foreign_futures_latch(self):
        foreign = _batch_asyncio.new_event_loop()
        foreign_ready = foreign.create_future()
        foreign_ready.set_result(_batch_ack(_batch_gate.frozen_batch_plan()["jobs"][0]))
        async def exercise():
            for mode in ("before_await", "during_await", "timeout", "malformed", "nonawaitable", "foreign", "hostile_exception"):
                with self.subTest(mode=mode):
                    controller = self.fresh()
                    def callback(job):
                        if mode == "before_await": raise ValueError("PRIVATE_CALLBACK_EXCEPTION")
                        if mode == "hostile_exception":
                            class HostileError(RuntimeError):
                                @property
                                def __class__(self):
                                    raise AssertionError("must not inspect foreign exception attributes")
                            raise HostileError("PRIVATE_HOSTILE_EXCEPTION")
                        if mode == "nonawaitable": return _batch_ack(job)
                        if mode == "foreign": return foreign_ready
                        if mode == "during_await":
                            async def failing(): raise RuntimeError("PRIVATE_ASYNC_EXCEPTION")
                            return failing()
                        ready = _batch_asyncio.get_running_loop().create_future()
                        if mode == "timeout": ready.set_exception(TimeoutError("PRIVATE_TIMEOUT"))
                        else: ready.set_result({})
                        return ready
                    with self.assertRaisesRegex(_batch_harness.GateRunError, "^BATCH_RPC_UNCERTAIN$"):
                        await controller.submit_next_async(callback)
                    state = controller.snapshot()
                    self.assertTrue(state["uncertainty_latched"])
                    self.assertEqual((state["attempts_consumed"], state["outstanding"]), (1, 1))
                    self.assertFalse(state["start_observation_pending"])
                    with self.assertRaises(_batch_harness.GateRunError):
                        await controller.submit_next_async(lambda _: self.fail("uncertain replacement"))
        try:
            _batch_asyncio.run(exercise())
        finally:
            foreign.close()

    def test_async_sixteen_window_and_two_hundred_terminal_cardinality_share_core(self):
        async def exercise():
            controller, calls = self.fresh(), []
            def callback(job):
                calls.append(job["job_id"])
                ready = _batch_asyncio.get_running_loop().create_future()
                ready.set_result(_batch_ack(job))
                return ready
            for _ in range(16): self.assertIsNotNone(await controller.submit_next_async(callback))
            for _ in range(100): self.assertIsNone(await controller.submit_next_async(callback))
            self.assertEqual(len(calls), 16)
            for index in range(200):
                self.settle(controller, index)
                if index + 16 < 200:
                    self.assertEqual(await controller.submit_next_async(callback), f"batch-{index + 16:03d}")
            self.assertIsNone(await controller.submit_next_async(callback))
            state = controller.snapshot()
            self.assertEqual((state["attempts_consumed"], state["validated_terminal"], state["outstanding"]), (200, 200, 0))
            self.assertEqual(state["peak_outstanding"], 16)
            self.assertEqual(len(set(calls)), 200)
            self.assertFalse(state["uncertainty_latched"])
        _batch_asyncio.run(exercise())

    def test_async_reentry_and_callback_mutation_cannot_change_reserved_original(self):
        async def exercise():
            controller = self.fresh()
            async def callback(job):
                acknowledgment = _batch_ack(job)
                with self.assertRaises(_batch_harness.GateRunError):
                    await controller.submit_next_async(lambda _: self.fail("reentrant async callback"))
                with self.assertRaises(_batch_harness.GateRunError):
                    controller.submit_next(lambda _: self.fail("reentrant sync callback"))
                job["job_id"], job["payload"]["left"] = "batch-199", 999
                snapshot = controller.snapshot()
                snapshot["jobs"]["batch-000"]["reserved"] = False
                return acknowledgment
            self.assertEqual(await controller.submit_next_async(callback), "batch-000")
            self.settle(controller, 0)
            self.assertEqual(controller.snapshot()["attempts_consumed"], 1)
            self.assertFalse(controller.snapshot()["uncertainty_latched"])
        _batch_asyncio.run(exercise())
