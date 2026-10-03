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
    forbidden = {"kill","terminate","killpg","reset_workflow_execution","start_time_skipping","start_local","importorskip"}
    _assert_dag2_cancellation_boundary(tree)
    assert not any(isinstance(n.func,ast.Attribute) and n.func.attr in forbidden for n in calls)
    assert not any(isinstance(n.func,ast.Name) and n.func.id in (forbidden | {"cancel"}) for n in calls)
    assert not any(isinstance(n,ast.Constant) and isinstance(n.value,str) and "/proc" in n.value for n in ast.walk(tree))


def test_public_workflow_has_readonly_permissions_and_private_logs():
    source = (ROOT / ".github/workflows/temporal-server.yml").read_text()
    assert "contents: read" in source and "timeout-minutes: 10" in source
    assert "cancel-in-progress: false" in source
    assert "actions/checkout@08c6903cd8c0fde910a37f88322edcfb5dd907a8" in source
    assert "actions/setup-python@e797f83bcb11b83ae66e0230d6156d7c80228e7c" in source
    assert 'opendot-temporal-pytest-private.log" 2>&1' in source
    assert "--force-reinstall --report" in source and "--require-hashes" in source
    # The whole reviewed workflow has a closed byte contract: alternate YAML
    # spelling, extra actions or broader conditions cannot evade this guard.
    from verify_temporal_server_gate import validate_public_batch_workflow
    validate_public_batch_workflow(source.encode("utf-8"))
    # Narrow retention exception: one explicit manual batch-only public export.
    assert source.count("uses: actions/upload-artifact") == 1 and "secrets." not in source
    upload = source.split("      - name: Retain only validated batch public projection\n", 1)[1]
    assert "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" in upload
    assert "github.event_name == 'workflow_dispatch'" in upload
    assert "inputs.qualification == 'batch200'" in upload and "inputs.retain_public_evidence" in upload
    assert "success() && !cancelled()" in upload and "steps.batch_evidence.outcome == 'success'" in upload
    assert "path: ${{ runner.temp }}/opendot-temporal-batch200-public\n" in upload
    assert "retention-days: 30" in upload and "if-no-files-found: error" in upload
    assert "overwrite: false" in upload and "include-hidden-files: false" in upload
    assert 'opendot-temporal-batch200-gate/audit' not in upload and 'private.log' not in upload
    assert "uses: actions/upload-artifact" not in source.split("      - name: Assert separate manually selected 200-job batch", 1)[0]


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


# Live-shaped pure tests. No service/CLI/acquisition or native lifetime probes.
# Test ActivityEnvironment Info is never serialized as hosted acceptance.
import asyncio as _real_asyncio
from contextvars import copy_context as _real_copy_context
from types import SimpleNamespace as _RealNamespace


def _real_observer(clock=None):
    gate = _batch_gate
    owner = m.BatchAdmission(gate.frozen_batch_plan(), dict(gate.BATCH_PROFILE))
    requests = {}
    for job in gate.frozen_batch_plan()["jobs"]:
        requests[job["job_id"]] = {"schema_version": "opendot.temporal.request.v1",
            "input_ref": {"artifact_id": job["input_artifact_id"]}}
    observed = m.BatchObservations(owner, requests, **({"clock": clock} if clock else {}))
    return owner, observed


def _real_info(job, **changes):
    row = dict(workflow_id=job["workflow_id"], workflow_run_id=_batch_ack(job)["run_id"],
        activity_id=m.ACTIVITY_ID, activity_type=m.ACTIVITY_TYPE, namespace="default", task_queue=m.QUEUE,
        attempt=1, is_local=False, retry_policy=_RealNamespace(maximum_attempts=1),
        start_to_close_timeout=timedelta(seconds=10), schedule_to_close_timeout=timedelta(seconds=60))
    row.update(changes)
    return _RealNamespace(**row)


def _real_reserve(owner, observed, *, acknowledge=True):
    job = owner._reserve_submission("sync")
    with owner._lock:
        owner._emit("rpc_enter", job["job_id"])
    if acknowledge:
        owner.acknowledge(_batch_ack(job))
    owner._inside_submit = False
    return job


def test_real_observer_preserves_activity_before_acknowledgment_and_equal_clocks():
    owner, observed = _real_observer(clock=lambda: 1000)
    job = _real_reserve(owner, observed, acknowledge=False)
    identity = observed.enter_activity(_real_info(job), observed.requests[job["job_id"]])
    token = m._BATCH_INVOCATION.set(identity)
    try:
        observed.phase("execute_enter", "activity_enter", payload=job["payload"])
        assert observed.handler(lambda p: p["left"] + p["right"], job["payload"]) == 199
        observed.phase("execute_return", "handler_return")
        observed.exit_activity(identity, {}, True)
    finally:
        m._BATCH_INVOCATION.reset(token)
    owner.acknowledge(_batch_ack(job))
    assert [r["event"] for r in observed.counters] == ["reservation", "rpc_enter", "activity_enter",
        "execute_enter", "handler_enter", "handler_return", "execute_return", "activity_exit", "acknowledgment"]
    assert all(r["elapsed_us"] == 0 for r in observed.counters)
    assert owner.snapshot()["outstanding"] == 1


@pytest.mark.parametrize("change", [
    {"workflow_id": "unreserved"}, {"workflow_run_id": "invalid"}, {"activity_id": "wrong"},
    {"activity_type": "wrong"}, {"namespace": "wrong"}, {"task_queue": "wrong"}, {"attempt": 2},
    {"is_local": True}, {"retry_policy": None}, {"retry_policy": _RealNamespace(maximum_attempts=2)},
    {"start_to_close_timeout": timedelta(seconds=11)}, {"schedule_to_close_timeout": timedelta(seconds=61)},
    {"workflow_run_id": "00000000-0000-0000-0000-111111111111"},
])
def test_real_observer_rejects_wrong_received_metadata(change):
    owner, observed = _real_observer()
    job = _real_reserve(owner, observed)
    with pytest.raises(Exception):
        observed.enter_activity(_real_info(job, **change), observed.requests[job["job_id"]])
    assert owner.snapshot()["uncertainty_latched"]
    assert owner.snapshot()["outstanding"] == 1


@pytest.mark.parametrize("fault", ["duplicate", "wrong_request", "unreserved", "ninth"])
def test_real_observer_rejects_entry_identity_and_capacity_faults(fault):
    owner, observed = _real_observer()
    jobs = [_real_reserve(owner, observed) for _ in range(9 if fault == "ninth" else 1)]
    if fault == "unreserved":
        jobs = [_batch_gate.frozen_batch_plan()["jobs"][1]]
    elif fault in {"duplicate", "ninth"}:
        for job in jobs[:-1] if fault == "ninth" else jobs:
            observed.enter_activity(_real_info(job), observed.requests[job["job_id"]])
    job = jobs[-1]
    with pytest.raises(Exception):
        observed.enter_activity(_real_info(job), {} if fault == "wrong_request" else observed.requests[job["job_id"]])
    assert owner.snapshot()["uncertainty_latched"]


@pytest.mark.parametrize("fault", ["missing_context", "wrong_context", "wrong_payload", "duplicate_handler", "orphan_return"])
def test_real_observer_rejects_context_and_order_gaps(fault):
    owner, observed = _real_observer()
    job = _real_reserve(owner, observed)
    identity = observed.enter_activity(_real_info(job), observed.requests[job["job_id"]])
    token = m._BATCH_INVOCATION.set(None if fault == "missing_context" else
                                  ("wrong", *identity[1:]) if fault == "wrong_context" else identity)
    try:
        with pytest.raises(Exception):
            if fault in {"missing_context", "wrong_context", "wrong_payload"}:
                observed.phase("execute_enter", "activity_enter", payload={} if fault == "wrong_payload" else job["payload"])
            elif fault == "orphan_return":
                observed.phase("handler_return", "handler_enter")
            else:
                observed.phase("execute_enter", "activity_enter")
                observed.phase("handler_enter", "execute_enter")
                observed.phase("handler_enter", "execute_enter")
    finally:
        m._BATCH_INVOCATION.reset(token)
    assert owner.snapshot()["uncertainty_latched"]


def test_real_thread_stop_prevents_reservation_and_client_entry():
    owner, observed = _real_observer()
    thread = threading.Thread(target=lambda: observed.uncertain(None, "OBSERVER_FAILURE"))
    thread.start(); thread.join()
    with pytest.raises(m.GateRunError):
        owner.submit_next(lambda _: pytest.fail("post-stop callback"))
    assert observed.counters[0]["event"] == "uncertainty"
    assert owner.snapshot()["attempts_consumed"] == 0


def test_real_thread_stop_after_reservation_prevents_actual_client_call():
    async def exercise():
        owner, observed = _real_observer()
        runner = m.BatchRunner.__new__(m.BatchRunner)
        runner.admission, runner.requests = owner, observed.requests
        runner.workflow_class = m.ReferenceBatchWorkflow
        runner.client = _RealNamespace(start_workflow=lambda *a, **k: pytest.fail("post-stop public SDK call"))
        async def callback(job):
            thread = threading.Thread(target=lambda: observed.uncertain(job["job_id"], "OBSERVER_FAILURE"))
            thread.start(); thread.join()
            return await runner._submit(job)
        with pytest.raises(m.GateRunError):
            await owner.submit_next_async(callback)
        assert owner.snapshot()["attempts_consumed"] == owner.snapshot()["outstanding"] == 1
        assert [r["event"] for r in observed.counters] == ["reservation", "uncertainty"]
    _real_asyncio.run(exercise())


def test_real_recorder_failure_closes_independently_without_missing_event_success():
    clock = iter([10000, 11000, 9000])
    owner, observed = _real_observer(clock=lambda: next(clock))
    job = owner._reserve_submission("sync")
    with pytest.raises(m.GateRunError):
        with owner._lock:
            owner._emit("rpc_enter", job["job_id"])
    assert owner.snapshot()["uncertainty_latched"] and owner._recording_failed
    assert observed.observation_uncertain
    with pytest.raises(m.GateRunError):
        owner._reserve_submission("sync")


def _real_activity_response(runner, job):
    from dataclasses import replace
    from temporalio.testing import ActivityEnvironment
    from temporalio.common import RetryPolicy
    from opendot_engineering.adapters import temporal_activity as production
    from opendot_engineering.tool_runtime import ToolRuntime
    env = ActivityEnvironment()
    env.info = replace(env.info, workflow_id=job["workflow_id"], workflow_run_id=_batch_ack(job)["run_id"],
        activity_id=m.ACTIVITY_ID, activity_type=m.ACTIVITY_TYPE, namespace="default", task_queue=m.QUEUE,
        attempt=1, is_local=False, retry_policy=RetryPolicy(maximum_attempts=1),
        start_to_close_timeout=timedelta(seconds=10), schedule_to_close_timeout=timedelta(seconds=60))
    runtime = ToolRuntime()
    runtime.register(production.SYNTHETIC_SPEC, lambda payload: runner.observed.handler(production.bounded_sum, payload))
    original = runtime.execute
    runtime.execute = lambda *args, **kwargs: runner.observed.execute_once(original, *args, **kwargs)
    adapter = production.ReferenceActivity(runtime=runtime, store=runner.store, tool_id=production.TOOL_ID,
        expected_registration_sha256=production.REGISTRATION_SHA256, granted_permissions=frozenset({"synthetic:read"}),
        expected_namespace="default", expected_task_queue=m.QUEUE)
    request = runner.requests[job["job_id"]]
    identity = runner.observed.enter_activity(env.info, request)
    token = m._BATCH_INVOCATION.set(identity)
    try:
        # Public test SDK context plus a real bounded outer executor exercises
        # ContextVar propagation to the untouched runtime's nested callable.
        with m.ThreadPoolExecutor(max_workers=1) as executor:
            response = executor.submit(_real_copy_context().run, env.run, adapter.run, request).result()
        runner.observed.exit_activity(identity, response, True)
    finally:
        m._BATCH_INVOCATION.reset(token)
    return response


def _real_original_fixture(tmp_path):
    root = tmp_path / "runner"
    for name in ("cas", "private", "audit"):
        (root / name).mkdir(parents=True)
    runner = m.BatchRunner(root, root / "temporal", {"candidate_revision": "a" * 40}, m.DiagnosticState("a" * 40))
    job = _real_reserve(runner.admission, runner.observed)
    return runner, job, _real_activity_response(runner, job)


def test_real_original_canonical_receipt_and_bounded_cas_binding(tmp_path):
    runner, job, response = _real_original_fixture(tmp_path)
    original = runner.store.get_bytes
    limits = []
    def read(ref, **kwargs):
        limits.append(kwargs)
        return original(ref, **kwargs)
    runner.store.get_bytes = read
    row = runner.original_result(job, _batch_ack(job)["run_id"], response)
    assert row["terminal"]["output"] == 199
    assert row["original_validation"] == "CAS_RECEIPT_INPUT_BOUND"
    assert limits == [{"max_bytes": 16384}]
    assert "worker_pid" not in json.dumps(row)
    assert runner.observed.total("handler_enter") == runner.observed.total("handler_return") == 1
    assert m._BATCH_INVOCATION.get() is None


@pytest.mark.parametrize("fault", ["wrong_run", "wrong_input", "wrong_result", "source_refs", "producer",
    "uri", "size", "receipt_mutation", "document_output", "document_input", "document_semantic", "document_authority",
    "document_output_float", "document_input_float", "document_liveness_integer"])
def test_real_original_refuses_swapped_or_modified_evidence(tmp_path, fault):
    runner, job, response = _real_original_fixture(tmp_path)
    response = json.loads(json.dumps(response))
    run_id = _batch_ack(job)["run_id"]
    if fault == "wrong_run": run_id = "00000000-0000-0000-0000-111111111111"
    elif fault == "wrong_input": job = _batch_gate.frozen_batch_plan()["jobs"][1]
    elif fault == "wrong_result": response["result_ref"]["artifact_id"] = "sha256:" + "b" * 64
    elif fault == "source_refs": response["result_ref"]["source_refs"] = []
    elif fault == "producer": response["result_ref"]["producer"] = "wrong"
    elif fault == "uri": response["result_ref"]["uri"] = "artifact://sha256/" + "b" * 64
    elif fault == "size": response["result_ref"]["size_bytes"] = 16385
    elif fault == "receipt_mutation": runner.observed.originals[job["job_id"]][1].execution_liveness["reconciliation_required"] = True
    else:
        ref = response["result_ref"]
        from opendot_engineering.core.contracts import ArtifactRef
        data = runner.store.get_bytes(ArtifactRef(**{**ref, "source_refs": tuple(ref["source_refs"])}), max_bytes=16384)
        doc = json.loads(data)
        if fault == "document_output_float": doc["output"] = 199.0
        elif fault == "document_input_float": doc["input_ref"]["size_bytes"] = float(doc["input_ref"]["size_bytes"])
        elif fault == "document_liveness_integer": doc["receipt_report"]["execution_liveness"]["reconciliation_required"] = 0
        elif fault == "document_output": doc["output"] = 198
        elif fault == "document_input": doc["input_ref"]["task_id"] = "wrong"
        elif fault == "document_semantic": doc["receipt_report"]["semantic_valid"] = False
        else: doc["scientific_validity"] = True
        new = runner.store.put_json(doc, producer=ref["producer"], task_id=ref["task_id"], source_refs=tuple(ref["source_refs"]))
        response["result_ref"] = {**m.asdict(new), "source_refs": list(new.source_refs)}
        # Preserve only transport equality, deliberately challenge original bytes.
        runner.observed.responses[job["job_id"]] = response
    with pytest.raises(Exception):
        runner.original_result(job, run_id, response)
    assert runner.admission.snapshot()["outstanding"] == 1


def test_real_profile_requires_exact_four_nodes_and_manual_dispatch_before_files(tmp_path, monkeypatch):
    for nodes, profile, event in (([], "batch200", "workflow_dispatch"),
        (list(_batch_gate.REAL_BATCH_REQUIRED_NODES), "reference", "workflow_dispatch"),
        (list(_batch_gate.REAL_BATCH_REQUIRED_NODES), "batch200", "pull_request")):
        monkeypatch.setenv("OPENDOT_TEMPORAL_QUALIFICATION", profile)
        monkeypatch.setenv("GITHUB_EVENT_NAME", event)
        with pytest.raises(m.GateRunError):
            m.run_real_batch_gate(tmp_path / "untouched", tmp_path / "cli", nodes)
        assert not (tmp_path / "untouched").exists()


def test_real_acceptance_manifest_exact_four_nodes_outside_default_discovery():
    path = ROOT / "tests/acceptance/temporal_real_batch_gate.py"
    tree = ast.parse(path.read_text())
    nodes = ["tests/acceptance/temporal_real_batch_gate.py::" + n.name for n in tree.body
             if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]
    assert nodes == list(_batch_gate.REAL_BATCH_REQUIRED_NODES)
    assert nodes == (ROOT / "ci/temporal-real-batch-nodes.txt").read_text().splitlines()
    assert not path.name.startswith("test_") and not path.name.endswith("_test.py")


def test_real_live_runner_uses_no_execution_delays_or_recovery_calls():
    tree = ast.parse((ROOT / "ci/run_temporal_server_gate.py").read_text())
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name in {"BatchRunner", "BatchObservations", "ReferenceBatchWorkflow"}:
            for call in ast.walk(node):
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute):
                    assert call.func.attr not in {"sleep", "cancel", "kill", "terminate", "reset_workflow_execution", "signal"}


async def _real_history_fixture(runner, job, response, *, bind=True):
    from temporalio.api.history.v1 import HistoryEvent
    from temporalio.api.enums.v1 import EventType
    from temporalio.client import WorkflowHistory
    from temporalio.converter import DataConverter
    converter = DataConverter.default
    if bind:
        runner.client = _RealNamespace(data_converter=converter)
        runner.responses[job["job_id"]] = response
    inputs = await converter.encode([runner.requests[job["job_id"]]])
    outputs = await converter.encode([response])
    run_id = _batch_ack(job)["run_id"]
    events = []
    def add(name, attrs):
        enum = "EVENT_TYPE_" + name.upper()
        events.append(HistoryEvent(event_id=len(events) + 1, event_type=getattr(EventType, enum),
                                  **{name.lower() + "_event_attributes": attrs}))
    add("WORKFLOW_EXECUTION_STARTED", {"workflow_type": {"name": m.BATCH_WORKFLOW_TYPE},
        "task_queue": {"name": m.QUEUE}, "workflow_execution_timeout": {"seconds": 120},
        "workflow_run_timeout": {"seconds": 120}, "workflow_task_timeout": {"seconds": 10},
        "retry_policy": {"maximum_attempts": 1}, "workflow_id": job["workflow_id"],
        "original_execution_run_id": run_id, "first_execution_run_id": run_id, "attempt": 1,
        "input": {"payloads": inputs}})
    add("WORKFLOW_TASK_SCHEDULED", {})
    add("WORKFLOW_TASK_STARTED", {"scheduled_event_id": 2, "identity": "opendot-gate-workflow-worker"})
    add("WORKFLOW_TASK_COMPLETED", {"scheduled_event_id": 2, "started_event_id": 3,
                                     "identity": "opendot-gate-workflow-worker"})
    add("ACTIVITY_TASK_SCHEDULED", {"activity_type": {"name": m.ACTIVITY_TYPE}, "activity_id": m.ACTIVITY_ID,
        "task_queue": {"name": m.QUEUE}, "retry_policy": {"maximum_attempts": 1},
        "start_to_close_timeout": {"seconds": 10}, "schedule_to_close_timeout": {"seconds": 60},
        "input": {"payloads": inputs}})
    add("ACTIVITY_TASK_STARTED", {"scheduled_event_id": 5, "attempt": 1, "identity": "opendot-gate-activity-worker"})
    add("ACTIVITY_TASK_COMPLETED", {"scheduled_event_id": 5, "started_event_id": 6, "result": {"payloads": outputs}})
    add("WORKFLOW_TASK_SCHEDULED", {})
    add("WORKFLOW_TASK_STARTED", {"scheduled_event_id": 8, "identity": "opendot-gate-workflow-worker"})
    add("WORKFLOW_TASK_COMPLETED", {"scheduled_event_id": 8, "started_event_id": 9,
                                     "identity": "opendot-gate-workflow-worker"})
    add("WORKFLOW_EXECUTION_COMPLETED", {"result": {"payloads": outputs}})
    return WorkflowHistory(job["workflow_id"], events), _RealNamespace(id=job["workflow_id"], run_id=run_id)


def test_real_history_binds_public_proto_run_input_result_and_projects_only_allowlist(tmp_path):
    runner, job, response = _real_original_fixture(tmp_path)
    async def exercise():
        history, handle = await _real_history_fixture(runner, job, response)
        outcome = runner.original_result(job, handle.run_id, response)
        row = await runner.real_history(job, handle, history, outcome["terminal"])
        assert len(row["events"]) == 11 and row["raw_history_bytes"] <= 65536
        assert row["events"][0]["attributes"]["original_execution_run_id"] == handle.run_id
        assert "payloads" not in json.dumps(row)
    _real_asyncio.run(exercise())


@pytest.mark.parametrize("fault", ["history_workflow", "started_workflow", "original_run", "first_run", "attempt",
    "continued", "workflow_input", "activity_input", "activity_result", "workflow_result", "extra_event", "raw_size"])
def test_real_history_refuses_wrong_run_reset_retries_inputs_and_unbounded_data(tmp_path, fault):
    runner, job, response = _real_original_fixture(tmp_path)
    async def exercise():
        history, handle = await _real_history_fixture(runner, job, response)
        started = history.events[0].workflow_execution_started_event_attributes
        if fault == "history_workflow":
            from temporalio.client import WorkflowHistory
            history = WorkflowHistory("wrong", history.events)
        elif fault == "started_workflow": started.workflow_id = "wrong"
        elif fault == "original_run": started.original_execution_run_id = "00000000-0000-0000-0000-111111111111"
        elif fault == "first_run": started.first_execution_run_id = "00000000-0000-0000-0000-111111111111"
        elif fault == "attempt": started.attempt = 2
        elif fault == "continued": started.continued_execution_run_id = handle.run_id
        elif fault == "workflow_input": started.input.Clear()
        elif fault == "activity_input": history.events[4].activity_task_scheduled_event_attributes.input.Clear()
        elif fault == "activity_result": history.events[6].activity_task_completed_event_attributes.result.Clear()
        elif fault == "workflow_result": history.events[-1].workflow_execution_completed_event_attributes.result.Clear()
        elif fault == "extra_event": history.events.append(history.events[4])
        elif fault == "raw_size": started.identity = "PRIVATE" * 12000
        terminal = runner.original_result(job, handle.run_id, response)["terminal"]
        with pytest.raises(Exception):
            await runner.real_history(job, handle, history, terminal)
        assert not list((runner.root / "private").iterdir())
    _real_asyncio.run(exercise())


def test_real_late_observer_interruption_is_not_swallowed_during_cleanup(tmp_path):
    runner, job, response = _real_original_fixture(tmp_path)
    class Control(BaseException):
        pass
    async def exercise():
        async def failed(): raise Control("PRIVATE_CONTROL")
        task = _real_asyncio.create_task(failed())
        await _real_asyncio.wait({task})
        runner.pending[job["job_id"]] = task
        runner._observer_started.add(job["job_id"])
        with pytest.raises(Control):
            await runner.cleanup()
        assert runner.admission.snapshot()["uncertainty_latched"]
    _real_asyncio.run(exercise())


def test_real_failed_observer_is_never_replaced_by_cleanup(tmp_path):
    runner, job, response = _real_original_fixture(tmp_path)
    async def exercise():
        async def failed(): raise ValueError("PRIVATE_FAILURE")
        task = _real_asyncio.create_task(failed())
        await _real_asyncio.wait({task})
        runner.pending[job["job_id"]] = task
        runner._observer_started.add(job["job_id"])
        runner.handles[job["job_id"]] = _RealNamespace()
        row = await runner.cleanup()
        assert row["cleanup_status"] == "UNCONFIRMED"
        assert runner._observer_started == {job["job_id"]} and not runner.pending
        assert runner.admission.snapshot()["outstanding"] == 1
    _real_asyncio.run(exercise())


def test_real_factory_uses_exact_shared_runtime_and_external_worker_bounds(tmp_path, monkeypatch):
    import temporalio.worker
    root = tmp_path / "runner"
    (root / "cas").mkdir(parents=True)
    runner = m.BatchRunner(root, root / "cli", {"candidate_revision": "a" * 40}, m.DiagnosticState("a" * 40))
    captured = []
    class Worker:
        def __init__(self, client, **kwargs):
            self.kwargs = kwargs
            captured.append(kwargs)
        async def run(self): return None
    monkeypatch.setattr(temporalio.worker, "Worker", Worker)
    async def exercise():
        workflow = await runner.start_worker("workflow")
        activity = await runner.start_worker("activity")
        await workflow["task"]; await activity["task"]
        assert captured[0]["max_concurrent_workflow_tasks"] == 1 and captured[0]["max_cached_workflows"] == 0
        assert captured[0]["max_concurrent_workflow_task_polls"] == 1 and captured[0]["no_remote_activities"]
        assert captured[1]["max_concurrent_activities"] == 8 and captured[1]["max_concurrent_activity_task_polls"] == 1
        assert captured[1]["disable_eager_activity_execution"] and captured[0]["disable_eager_activity_execution"]
        assert activity["executor"]._max_workers == 8
        adapter = captured[1]["activities"][0].__self__
        from opendot_engineering.tool_runtime import ToolRuntime
        from opendot_engineering.core.artifacts import ArtifactStore
        assert type(adapter.runtime) is ToolRuntime and type(adapter.store) is ArtifactStore
        assert adapter.store is runner.store
        with pytest.raises(m.GateRunError): await runner.start_worker("activity")
        activity["executor"].shutdown(wait=True)
    _real_asyncio.run(exercise())


def test_real_async_start_observation_timeout_retains_one_late_operation():
    async def exercise():
        owner = m.BatchAdmission(_batch_gate.frozen_batch_plan(), dict(_batch_gate.BATCH_PROFILE))
        result = _real_asyncio.get_running_loop().create_future()
        calls = []
        def callback(job):
            calls.append(job)
            return result
        with pytest.raises(m.GateRunError):
            await owner.submit_next_async(callback, start_timeout=1e-9)
        assert owner.snapshot()["start_observation_pending"] and not result.cancelled()
        assert owner.snapshot()["outstanding"] == 1
        result.set_result(_batch_ack(calls[0]))
        await _batch_async_turn(); await _batch_async_turn()
        assert not owner.snapshot()["start_observation_pending"]
        assert owner.snapshot()["uncertainty_latched"] and owner.snapshot()["outstanding"] == 1
        with pytest.raises(m.GateRunError):
            await owner.submit_next_async(callback)
        assert len(calls) == 1
    _real_asyncio.run(exercise())


def test_real_finite_loop_never_constructs_two_hundred_observers_at_once(tmp_path):
    root = tmp_path / "runner"
    (root / "cas").mkdir(parents=True)
    runner = m.BatchRunner(root, root / "cli", {"candidate_revision": "a" * 40}, m.DiagnosticState("a" * 40))
    calls, releases, peaks = [], {}, []
    async def nothing(*args): pass
    runner.start_server = runner.start_worker = nothing
    class Client:
        def get_workflow_handle(self, workflow_id, *, run_id):
            return _RealNamespace(id=workflow_id, run_id=run_id)
        async def start_workflow(self, method, request, **kwargs):
            workflow_id = kwargs["id"]
            job = next(j for j in runner.plan["jobs"] if j["workflow_id"] == workflow_id)
            calls.append(job["job_id"])
            releases[job["job_id"]] = _real_asyncio.get_running_loop().create_future()
            peaks.append(runner.admission.snapshot()["outstanding"])
            assert len(runner.pending) <= 16 and len(releases) <= 16
            assert kwargs["request_eager_start"] is False and kwargs["retry_policy"].maximum_attempts == 1
            if len(calls) % 16 == 0 or len(calls) == 200:
                for future in releases.values():
                    if not future.done(): future.set_result(None)
            return _RealNamespace(id=workflow_id, first_execution_run_id=_batch_ack(job)["run_id"])
    runner.client = Client()
    async def observer(job_id):
        await releases[job_id]
        releases.pop(job_id)
        terminal = _batch_harness_result(runner.admission._job(job_id))
        runner.admission.record_outcome(terminal)
        runner.admission.observe_terminal(terminal)
    runner._observe_result = observer
    _real_asyncio.run(runner.run_cases())
    assert calls == [j["job_id"] for j in runner.plan["jobs"]]
    assert len(calls) == 200 and max(peaks) == 16 and not releases and not runner.pending
    assert runner.admission.snapshot()["validated_terminal"] == 200


def test_real_error_edges_preserve_original_control_and_leave_sticky_failure():
    owner, observed = _real_observer()
    job = _real_reserve(owner, observed)
    identity = observed.enter_activity(_real_info(job), observed.requests[job["job_id"]])
    token = m._BATCH_INVOCATION.set(identity)
    class Control(BaseException): pass
    error = Control("PRIVATE")
    def execute(*args, **kwargs):
        def handler(payload): raise error
        return observed.handler(handler, job["payload"])
    try:
        with pytest.raises(Control) as caught:
            observed.execute_once(execute, "synthetic.bounded_sum", job["payload"])
        assert caught.value is error
        observed.exit_activity(identity, None, False)
    finally:
        m._BATCH_INVOCATION.reset(token)
    events = [row["event"] for row in observed.counters]
    assert events[-4:] == ["handler_error", "uncertainty", "execute_error", "activity_error"]
    assert observed.execution_uncertain and owner.snapshot()["uncertainty_latched"]
    assert observed.in_flight == 0 and owner.snapshot()["outstanding"] == 1


def test_real_json_writer_counts_trailing_newline_in_complete_container_cap(tmp_path):
    row = {"bounded": True}
    size = len(_batch_gate._real_encoded(row, 1024))
    with pytest.raises(_batch_gate.GateError):
        m.write_batch_json(tmp_path / "refused.json", row, size)
    assert not (tmp_path / "refused.json").exists()
    m.write_batch_json(tmp_path / "exact.json", row, size + 1)
    assert len((tmp_path / "exact.json").read_bytes()) == size + 1


@pytest.mark.parametrize("fault", ["info", "exit_after_control"])
def test_real_public_interceptor_closes_info_gap_and_preserves_original_control(monkeypatch, fault):
    from temporalio import activity
    from temporalio.testing import ActivityEnvironment
    from temporalio.common import RetryPolicy
    from temporalio.worker import ExecuteActivityInput
    from dataclasses import replace
    owner, observed = _real_observer()
    job = _real_reserve(owner, observed)
    class Control(BaseException): pass
    original = Control("PRIVATE_CONTROL")
    env = ActivityEnvironment()
    env.info = replace(env.info, workflow_id=job["workflow_id"], workflow_run_id=_batch_ack(job)["run_id"],
        activity_id=m.ACTIVITY_ID, activity_type=m.ACTIVITY_TYPE, namespace="default", task_queue=m.QUEUE,
        attempt=1, is_local=False, retry_policy=RetryPolicy(maximum_attempts=1),
        start_to_close_timeout=timedelta(seconds=10), schedule_to_close_timeout=timedelta(seconds=60))
    if fault == "info":
        def failed_info(): raise original
        monkeypatch.setattr(activity, "info", failed_info)
    else:
        def failed_exit(*args): raise ValueError("PRIVATE_EXIT")
        monkeypatch.setattr(observed, "exit_activity", failed_exit)
    _, capture = m.batch_sdk_types(observed)
    class Next:
        async def execute_activity(self, input):
            assert fault != "info"
            raise original
    interceptor = capture().intercept_activity(Next())
    async def exercise():
        with pytest.raises(Control) as caught:
            await env.run(interceptor.execute_activity,
                          ExecuteActivityInput(fn=lambda: None, args=[observed.requests[job["job_id"]]],
                                               executor=None, headers={}))
        assert caught.value is original
        assert owner.snapshot()["uncertainty_latched"] and observed.observation_uncertain
        assert m._BATCH_INVOCATION.get() is None
    _real_asyncio.run(exercise())


# Composed local consumer controls, not hosted/agent-scale acceptance. Keep the
# real loop, observer, original CAS/receipt validation and history validator.
class _RealControlledResultHandle:
    def __init__(self, job, response, history):
        self.id, self.run_id = job["workflow_id"], _batch_ack(job)["run_id"]
        self.response, self.history = response, history
        loop = _real_asyncio.get_running_loop()
        self.result_ready, self.history_ready = loop.create_future(), loop.create_future()
        self.result_entered, self.history_entered = loop.create_future(), loop.create_future()
        self.result_calls, self.history_calls = [], []

    async def result(self, **kwargs):
        self.result_calls.append(kwargs)
        assert len(self.result_calls) == 1
        self.result_entered.set_result(None)
        return await self.result_ready

    async def fetch_history(self, **kwargs):
        self.history_calls.append(kwargs)
        assert len(self.history_calls) == 1
        self.history_entered.set_result(None)
        return await self.history_ready

    def release_remaining(self):
        if not self.result_ready.done():
            self.result_ready.set_result(self.response)
        if not self.history_ready.done():
            self.history_ready.set_result(self.history)


class _RealSaturatedConsumer:
    def __init__(self, tmp_path):
        from temporalio.converter import DataConverter
        root = tmp_path / "runner"
        for name in ("cas", "private", "audit"):
            (root / name).mkdir(parents=True)
        self.runner = m.BatchRunner(root, root / "unused-cli", {"candidate_revision": "a" * 40},
                                    m.DiagnosticState("a" * 40))
        self.handles, self.starts, self.peaks, self.stops, self.reads = {}, [], [], [], []
        self.started = {n: _real_asyncio.get_running_loop().create_future() for n in (16, 17)}
        self.data_converter = DataConverter.default
        self.runner.client = self
        async def no_start(*args): pass
        async def stop_workers(): self.stops.append("workers")
        async def stop_server(): self.stops.append("server")
        self.runner.start_server = self.runner.start_worker = no_start
        self.runner.stop_workers, self.runner.stop_server = stop_workers, stop_server
        original_read = self.runner.store.get_bytes
        def read(ref, **kwargs):
            self.reads.append((ref.artifact_id, kwargs))
            return original_read(ref, **kwargs)
        self.runner.store.get_bytes = read
        self.run = _real_asyncio.create_task(self.runner.run_cases())

    async def start_workflow(self, method, request, **kwargs):
        runner = self.runner
        job = next(j for j in runner.plan["jobs"] if j["workflow_id"] == kwargs["id"])
        assert request == runner.requests[job["job_id"]]
        assert kwargs["request_eager_start"] is False and kwargs["retry_policy"].maximum_attempts == 1
        assert len(self.starts) < 17
        self.starts.append(job["job_id"])
        self.peaks.append(runner.admission.snapshot()["outstanding"])
        assert len(runner.pending) <= 16
        response = _real_activity_response(runner, job)
        history, _ = await _real_history_fixture(runner, job, response, bind=False)
        self.handles[job["job_id"]] = _RealControlledResultHandle(job, response, history)
        if len(self.starts) in self.started:
            self.started[len(self.starts)].set_result(None)
        return _RealNamespace(id=job["workflow_id"], first_execution_run_id=_batch_ack(job)["run_id"])

    def get_workflow_handle(self, workflow_id, *, run_id):
        handle = next(h for h in self.handles.values() if h.id == workflow_id)
        assert handle.run_id == run_id
        return handle

    async def wait(self, *tasks):
        if not tasks:
            return
        done, pending = await _real_asyncio.wait(tasks, timeout=3)
        assert not pending, "controlled observer transition did not complete"
        for task in done:
            task.result()

    async def saturated(self):
        await self.wait(self.started[16])
        await self.wait(*(h.result_entered for h in self.handles.values()))
        state = self.runner.admission.snapshot()
        assert (len(self.starts), state["outstanding"], state["validated_terminal"]) == (16, 16, 0)
        assert len(self.runner.pending) == len(self.runner.result_operations) == 16
        assert not self.runner.outcomes and not self.runner.histories
        assert all(not h.history_calls for h in self.handles.values())

    async def result_before_history(self, job_id):
        handle = self.handles[job_id]
        handle.result_ready.set_result(handle.response)
        await self.wait(handle.history_entered)
        assert not handle.history_ready.done()
        return handle

    def check_single_reads(self, history_count):
        assert len(self.starts) == len(set(self.starts))
        assert max(self.peaks) == self.runner.admission.snapshot()["peak_outstanding"] == 16
        assert sum(len(h.history_calls) for h in self.handles.values()) == history_count
        for handle in self.handles.values():
            assert handle.result_calls == [{"follow_runs": False, "rpc_timeout": timedelta(seconds=2)}]
            assert handle.history_calls in ([], [{"rpc_timeout": timedelta(seconds=2)}])
        result_ids = {h.response["result_ref"]["artifact_id"] for h in self.handles.values()}
        assert all(kwargs == {"max_bytes": 16384} for ref, kwargs in self.reads if ref in result_ids)
        assert len({ref for ref, _ in self.reads if ref in result_ids}) == history_count

    async def finish_owned_tasks(self):
        # End only this fixture's finite prefix through the existing deadline.
        # Resolve retained local reads, including after a failed assertion; never
        # cancel or replace a result observer to manufacture quiescence.
        self.runner.deadline = 0
        for handle in self.handles.values():
            handle.release_remaining()
        tasks = {self.run, *self.runner.pending.values(), *self.runner.result_operations.values()}
        done, pending = await _real_asyncio.wait(tasks, timeout=3)
        assert not pending, "controlled fixture left an owned Task unresolved"
        for task in done:
            task.exception()


def test_real_saturated_consumer_waits_for_bound_history_before_one_slot_refill(tmp_path):
    async def exercise():
        control = _RealSaturatedConsumer(tmp_path)
        runner = control.runner
        try:
            await control.saturated()
            last = await control.result_before_history("batch-015")
            first = await control.result_before_history("batch-000")
            state = runner.admission.snapshot()
            assert (len(control.starts), state["outstanding"], state["validated_terminal"]) == (16, 16, 0)
            assert runner.observed.total("workflow_result") == 2
            assert not runner.outcomes and not runner.histories
            assert not runner.admission._outcomes
            result_reads = [(ref, kwargs) for ref, kwargs in control.reads if kwargs == {"max_bytes": 16384}]
            assert {ref for ref, _ in result_reads} == {
                last.response["result_ref"]["artifact_id"], first.response["result_ref"]["artifact_id"]}
            assert len(result_reads) == 2
            last.history_ready.set_result(last.history)
            await control.wait(control.started[17])
            await control.wait(control.handles["batch-016"].result_entered)
            state = runner.admission.snapshot()
            assert (len(control.starts), state["outstanding"], state["validated_terminal"]) == (17, 16, 1)
            assert state["jobs"]["batch-015"]["validated_terminal"]
            assert not state["jobs"]["batch-000"]["validated_terminal"]
            assert not first.history_ready.done() and len(runner.pending) == 16
            assert [row["terminal"]["job_id"] for row in runner.outcomes] == ["batch-015"]
            assert [row["job_id"] for row in runner.histories] == ["batch-015"]
            runner.deadline = 0
            for handle in control.handles.values():
                handle.release_remaining()
            with pytest.raises(m.GateRunError, match="GATE_DEADLINE"):
                await control.wait(control.run)
            # Expiry can precede the next loop sweep of already-finished reads.
            await control.wait(*runner.pending.values())
            runner._consume_done()
            state = runner.admission.snapshot()
            assert (state["attempts_consumed"], state["validated_terminal"], state["outstanding"]) == (17, 17, 0)
            assert not state["uncertainty_latched"] and state["unsubmitted"] == 183
            assert not runner.pending and not runner.result_operations
            terminals = [row["job_id"] for row in runner.observed.counters if row["event"] == "validated_terminal"]
            assert terminals[0] == "batch-015" and len(set(terminals)) == len(terminals) == 17
            assert control.starts == [f"batch-{i:03d}" for i in range(17)]
            control.check_single_reads(17)
            cleanup = await runner.cleanup()
            assert cleanup["cleanup_status"] == "PASS" and cleanup["all_reservations_accounted"]
            assert control.stops == ["workers", "server"]
        finally:
            await control.finish_owned_tasks()
    _real_asyncio.run(exercise())


@pytest.mark.parametrize("fault", ["swapped_result", "invalid_history", "result_exception"])
def test_real_saturated_consumer_fault_stays_closed_after_late_valid_results(tmp_path, fault):
    async def exercise():
        control = _RealSaturatedConsumer(tmp_path)
        runner = control.runner
        try:
            await control.saturated()
            late = await control.result_before_history("batch-015")
            failed = control.handles["batch-000"]
            expected, message = m.GateRunError, "RESULT_REFERENCE"
            if fault == "swapped_result":
                failed.result_ready.set_result(control.handles["batch-001"].response)
            elif fault == "invalid_history":
                await control.result_before_history("batch-000")
                failed.history.events[0].workflow_execution_started_event_attributes.original_execution_run_id = (
                    "00000000-0000-0000-0000-111111111111")
                failed.history_ready.set_result(failed.history)
                message = "UNEXPECTED_NEW_RUN"
            else:
                expected, message = RuntimeError, "controlled result observation failure"
                failed.result_ready.set_exception(RuntimeError(message))
            with pytest.raises(expected, match=message):
                await control.wait(control.run)
            state = runner.admission.snapshot()
            assert (len(control.starts), state["attempts_consumed"], state["outstanding"],
                    state["validated_terminal"]) == (16, 16, 16, 0)
            assert state["uncertainty_latched"] and state["jobs"]["batch-000"]["uncertain"]
            assert state["reasons"] == ["INVALID_TERMINAL"]
            assert not runner.outcomes and not runner.histories and not runner.admission._outcomes
            assert not list((runner.root / "private").iterdir())
            late.history_ready.set_result(late.history)
            await control.wait(runner.pending["batch-015"])
            state = runner.admission.snapshot()
            assert (state["outstanding"], state["validated_terminal"]) == (15, 1)
            assert state["uncertainty_latched"] and len(control.starts) == 16
            for handle in control.handles.values():
                handle.release_remaining()
            await control.wait(*runner.pending.values())
            runner._consume_done()
            runner._ensure_observers()
            state = runner.admission.snapshot()
            assert (state["attempts_consumed"], state["validated_terminal"], state["outstanding"]) == (16, 15, 1)
            assert state["uncertainty_latched"] and state["unsubmitted"] == 184
            assert not state["jobs"]["batch-000"]["validated_terminal"]
            assert len(runner.outcomes) == len(runner.histories) == len(runner.admission._outcomes) == 15
            assert {row["terminal"]["job_id"] for row in runner.outcomes} == set(control.starts) - {"batch-000"}
            assert runner.observed.total("validated_terminal") == 15
            # Invoke the real refusal core without changing the one-producer
            # identity enforced by submit_next_async; no callback can enter.
            with pytest.raises(m.GateRunError, match="BATCH_ADMISSION_STOPPED"):
                runner.admission._call_submission(lambda _: pytest.fail("post-closure client entry"),
                                                 runner.plan["jobs"][16])
            cleanup = await runner.cleanup()
            assert cleanup["cleanup_status"] == "UNCONFIRMED" and not cleanup["all_reservations_accounted"]
            assert cleanup["unresolved_result_operations"] == 0
            assert not control.stops and not runner.quiescent()
            assert not runner.pending and not runner.result_operations
            assert runner._observer_started == set(control.starts)
            assert len(control.starts) == 16 and runner.admission.snapshot()["uncertainty_latched"]
            control.check_single_reads(16 if fault == "invalid_history" else 15)
        finally:
            await control.finish_owned_tasks()
    _real_asyncio.run(exercise())


# DAG2 stage-one independent controls. FABRICATED_UNIT_DATA only: these literal
# expectations were frozen before the harness increment. They are never live
# histories, service-origin evidence, or a way to authenticate a hosted run.
DAG2_LITERAL_CAPS = {'diagnostic_bytes': 4096,
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

DAG2_LITERAL_AGGREGATE = {'accepted_updates': 1,
 'active_workflows_max': 1,
 'activity_entries': 9,
 'activity_executor_shutdowns': 4,
 'activity_executor_threads_max': 1,
 'activity_returns': 9,
 'activity_schedules': 9,
 'activity_slots_max': 1,
 'completed_update_fetches': 1,
 'distinct_refused_updates': 2,
 'endpoint_cas_reads': 11,
 'handler_entries': 5,
 'handler_returns': 5,
 'observer_cas_reads': 0,
 'result_bytes_reserved': 98304,
 'result_puts': 5,
 'retained_originals': 4,
 'runtime_entries': 5,
 'runtime_returns': 5,
 'same_id_repeats': 1,
 'seed_puts': 3,
 'server_starts': 1,
 'server_stops': 1,
 'verification_cas_reads': 4,
 'worker_shutdowns': 8,
 'workflow_handle_cancel_calls': 1,
 'workflow_starts': 3}

DAG2_LITERAL_NODES = ['tests/acceptance/temporal_dag_recovery_gate.py::test_dag2_real_a_to_b_and_original_receipts',
 'tests/acceptance/temporal_dag_recovery_gate.py::test_dag2_quiescent_worker_replacement_preserves_state',
 'tests/acceptance/temporal_dag_recovery_gate.py::test_dag2_recorded_history_replay_has_no_activity_execution',
 'tests/acceptance/temporal_dag_recovery_gate.py::test_dag2_original_put_reconciliation_never_reexecutes_a',
 'tests/acceptance/temporal_dag_recovery_gate.py::test_dag2_unknown_without_reference_blocks_b',
 'tests/acceptance/temporal_dag_recovery_gate.py::test_dag2_cancellation_keeps_unadmitted_b_closed',
 'tests/acceptance/temporal_dag_recovery_gate.py::test_dag2_duplicate_and_stale_updates_consume_no_allowance']

DAG2_LITERAL_ORIGINAL = {'body': {'activity_id': 'dag2-execute-10ad6c5fa6fa15e6f20bdfcc44b9cb3ba32273acf91c9e12dace74e6aeedcd30',
          'device_control_authority': False,
          'effect_id': 'sha256:10ad6c5fa6fa15e6f20bdfcc44b9cb3ba32273acf91c9e12dace74e6aeedcd30',
          'independent_review': 'NOT_EVALUATED',
          'input_payload_sha256': '897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02',
          'mission_id': 'hosted-normal',
          'namespace': 'default',
          'node_id': 'A',
          'observation_provenance': 'serialized_runtime_report_not_live_proof',
          'output': 5,
          'owner_integration': 'NOT_EVALUATED',
          'parent_result_ref': None,
          'plan_sha256': '19843079a5da00754ec1b5399962c33874b907eb4d0d6fcf55cd3be2f4dffb63',
          'profile': 'synthetic.dependent_sum.v1',
          'receipt_report': {'attempts': 1,
                             'breaker_state': 'closed',
                             'call_id': '000000000000000000000003',
                             'error_type': None,
                             'execution_liveness': {},
                             'execution_observation': {'dispatcher_pid': 101,
                                                       'execution_id': '00000000000000000000000000000003',
                                                       'execution_kind': 'in_process',
                                                       'input_sha256': '897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02',
                                                       'read_only_declared': True,
                                                       'registration_sha256': '5f2b1e81954530f31c7d2c83b9c582883b8391190ebe13b69b8bf91f044cb0c3',
                                                       'review_target_sha256': None,
                                                       'worker_pid': 101},
                             'input_hash': '897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02',
                             'latency_s': 0.0,
                             'output_hash': 'ef2d127de37b942baad06145e54b0c619a1f22327b2ebbcfbec78f5564afe39d',
                             'semantic_valid': True,
                             'status': 'COMPLETED',
                             'tool_id': 'synthetic.bounded_sum',
                             'tool_version': '1'},
          'registration_sha256': '5f2b1e81954530f31c7d2c83b9c582883b8391190ebe13b69b8bf91f044cb0c3',
          'schema_version': 'opendot.temporal.dag-result.v1',
          'scientific_validity': False,
          'seed_ref': {'artifact_id': 'sha256:897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02',
                       'integrity_verified': False,
                       'mime_type': 'application/json',
                       'producer': 'opendot.temporal.dag-seed.v1',
                       'schema_version': '1.0.0',
                       'sha256': '897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02',
                       'size_bytes': 40,
                       'source_refs': [],
                       'task_id': 'seed',
                       'uri': 'artifact://sha256/897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02'},
          'workflow_id': 'opendot-dag2-hosted-normal-19843079a5da00754ec1b5399962c33874b907eb4d0d6fcf55cd3be2f4dffb63',
          'workflow_run_id': '11111111-1111-4111-8111-111111111111'},
 'body_sha256': 'b2e34b932ad0cce76ff4d6a28dc0a62b36107540669db47abb7ed81f24ecfd5f',
 'canonical_body_utf8': '{"activity_id":"dag2-execute-10ad6c5fa6fa15e6f20bdfcc44b9cb3ba32273acf91c9e12dace74e6aeedcd30","device_control_authority":false,"effect_id":"sha256:10ad6c5fa6fa15e6f20bdfcc44b9cb3ba32273acf91c9e12dace74e6aeedcd30","independent_review":"NOT_EVALUATED","input_payload_sha256":"897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02","mission_id":"hosted-normal","namespace":"default","node_id":"A","observation_provenance":"serialized_runtime_report_not_live_proof","output":5,"owner_integration":"NOT_EVALUATED","parent_result_ref":null,"plan_sha256":"19843079a5da00754ec1b5399962c33874b907eb4d0d6fcf55cd3be2f4dffb63","profile":"synthetic.dependent_sum.v1","receipt_report":{"attempts":1,"breaker_state":"closed","call_id":"000000000000000000000003","error_type":null,"execution_liveness":{},"execution_observation":{"dispatcher_pid":101,"execution_id":"00000000000000000000000000000003","execution_kind":"in_process","input_sha256":"897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02","read_only_declared":true,"registration_sha256":"5f2b1e81954530f31c7d2c83b9c582883b8391190ebe13b69b8bf91f044cb0c3","review_target_sha256":null,"worker_pid":101},"input_hash":"897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02","latency_s":0.0,"output_hash":"ef2d127de37b942baad06145e54b0c619a1f22327b2ebbcfbec78f5564afe39d","semantic_valid":true,"status":"COMPLETED","tool_id":"synthetic.bounded_sum","tool_version":"1"},"registration_sha256":"5f2b1e81954530f31c7d2c83b9c582883b8391190ebe13b69b8bf91f044cb0c3","schema_version":"opendot.temporal.dag-result.v1","scientific_validity":false,"seed_ref":{"artifact_id":"sha256:897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02","integrity_verified":false,"mime_type":"application/json","producer":"opendot.temporal.dag-seed.v1","schema_version":"1.0.0","sha256":"897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02","size_bytes":40,"source_refs":[],"task_id":"seed","uri":"artifact://sha256/897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02"},"workflow_id":"opendot-dag2-hosted-normal-19843079a5da00754ec1b5399962c33874b907eb4d0d6fcf55cd3be2f4dffb63","workflow_run_id":"11111111-1111-4111-8111-111111111111"}',
 'origin': {'capture_phase': 'original_put_return_before_response',
            'effect_id': 'sha256:10ad6c5fa6fa15e6f20bdfcc44b9cb3ba32273acf91c9e12dace74e6aeedcd30',
            'execution_activity_id': 'dag2-execute-10ad6c5fa6fa15e6f20bdfcc44b9cb3ba32273acf91c9e12dace74e6aeedcd30',
            'mission_id': 'hosted-normal',
            'namespace': 'default',
            'node_id': 'A',
            'origin_kind': 'trusted-single-operator-synthetic-put-observer',
            'original_result_ref': {'artifact_id': 'sha256:b2e34b932ad0cce76ff4d6a28dc0a62b36107540669db47abb7ed81f24ecfd5f',
                                    'integrity_verified': False,
                                    'mime_type': 'application/json',
                                    'producer': 'opendot.temporal.dag-result.v1',
                                    'schema_version': '1.0.0',
                                    'sha256': 'b2e34b932ad0cce76ff4d6a28dc0a62b36107540669db47abb7ed81f24ecfd5f',
                                    'size_bytes': 2219,
                                    'source_refs': ['sha256:897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02'],
                                    'task_id': '10ad6c5fa6fa15e6f20bdfcc44b9cb3ba32273acf91c9e12dace74e6aeedcd30',
                                    'uri': 'artifact://sha256/b2e34b932ad0cce76ff4d6a28dc0a62b36107540669db47abb7ed81f24ecfd5f'},
            'plan_sha256': '19843079a5da00754ec1b5399962c33874b907eb4d0d6fcf55cd3be2f4dffb63',
            'schema_version': 'opendot.temporal.dag-origin.v1',
            'workflow_id': 'opendot-dag2-hosted-normal-19843079a5da00754ec1b5399962c33874b907eb4d0d6fcf55cd3be2f4dffb63',
            'workflow_run_id': '11111111-1111-4111-8111-111111111111'},
 'origin_sha256': 'd92e6d4d7b3bf6936dd0d1e6e0c9b3f20b9fb9fb643b5c44e5c3ddb0c3a23d8c',
 'receipt_sha256': '4872fee41110f2dba3493bb20e791f08ffdb400639fcefb04cbfe6a9093369ad',
 'reference': {'artifact_id': 'sha256:b2e34b932ad0cce76ff4d6a28dc0a62b36107540669db47abb7ed81f24ecfd5f',
               'integrity_verified': False,
               'mime_type': 'application/json',
               'producer': 'opendot.temporal.dag-result.v1',
               'schema_version': '1.0.0',
               'sha256': 'b2e34b932ad0cce76ff4d6a28dc0a62b36107540669db47abb7ed81f24ecfd5f',
               'size_bytes': 2219,
               'source_refs': ['sha256:897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02'],
               'task_id': '10ad6c5fa6fa15e6f20bdfcc44b9cb3ba32273acf91c9e12dace74e6aeedcd30',
               'uri': 'artifact://sha256/b2e34b932ad0cce76ff4d6a28dc0a62b36107540669db47abb7ed81f24ecfd5f'}}

DAG2_CANCEL_SOURCE = """async def cancel_no_ref(self):
    handle = self.handles["hosted-no-ref-cancel"]
    self.require_cancel_quiescent(handle)
    await self.rpc("hosted-no-ref-cancel", "cancel", "no-ref-cancel", lambda: handle.cancel(rpc_timeout=timedelta(seconds=2)))
"""


def _assert_dag2_cancellation_boundary(tree, *, require_call=False, require_live_caller=False):
    """A conservative reviewed-source syntax boundary, not Python alias analysis."""
    wanted = ast.parse(DAG2_CANCEL_SOURCE).body[0]
    cancel_attrs = [node for node in ast.walk(tree)
                    if isinstance(node, ast.Attribute) and node.attr == "cancel"]
    dynamic = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
               and isinstance(node.func, ast.Name) and node.func.id in {"getattr", "setattr"}
               and any(isinstance(arg, ast.Constant) and arg.value in {"cancel", "cancel_no_ref"} for arg in node.args)]
    assert not dynamic
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                   and node.func.id in {"cancel", "cancel_no_ref"} for node in ast.walk(tree))
    methods = [node for node in ast.walk(tree)
               if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
               and node.name == "cancel_no_ref"]
    # The scenario wrapper has one closed direct caller. An alias or dynamic
    # reference anywhere else, including a finally/exception handler, is denied.
    wrapper_refs = [node for node in ast.walk(tree)
                    if isinstance(node, ast.Attribute) and node.attr == "cancel_no_ref"]
    callers = [node for node in ast.walk(tree)
               if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
               and node.name == "run_no_ref"]
    if wrapper_refs or require_live_caller:
        assert len(wrapper_refs) == len(callers) == 1
        caller = callers[0]
        direct = ast.parse("await self.cancel_no_ref()").body[0]
        statements = [node for node in caller.body
                      if ast.dump(node, include_attributes=False) == ast.dump(direct, include_attributes=False)]
        assert len(statements) == 1 and wrapper_refs[0] in list(ast.walk(statements[0]))
        assert not any(isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del))
                       and node.id == "self" for node in ast.walk(caller))
    if cancel_attrs or require_call:
        assert len(cancel_attrs) == len(methods) == 1
        assert ast.dump(methods[0], include_attributes=False) == ast.dump(wanted, include_attributes=False)
        assert cancel_attrs[0] in list(ast.walk(methods[0]))
        parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
        owner = parents.get(methods[0])
        assert isinstance(owner, (ast.Module, ast.ClassDef))
        owners = [owner]
        if isinstance(owner, ast.ClassDef):
            # The inherited Runner lifecycle is part of the admitted owner.
            # Unrelated classes (for example diagnostic data holders) are not.
            classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
            for current in owners:
                for base in current.bases:
                    assert isinstance(base, ast.Name)
                    if base.id == "object":
                        continue
                    matches = [node for node in classes if node.name == base.id]
                    assert len(matches) == 1
                    if matches[0] not in owners:
                        owners.append(matches[0])
        owner_methods = [node for scope in owners for node in scope.body
                         if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        for method in owner_methods:
            pending_nodes = [method]
            while pending_nodes:
                node = pending_nodes.pop()
                # A nested function can close over self; a separate class has
                # a different receiver and is not silently treated as this one.
                if isinstance(node, ast.ClassDef):
                    continue
                pending_nodes.extend(ast.iter_child_nodes(node))
                if isinstance(node, ast.Name) and node.id == "self":
                    parent = parents.get(node)
                    assert isinstance(node.ctx, ast.Load)
                    assert isinstance(parent, ast.Attribute) and parent.value is node
                if isinstance(node, ast.Attribute):
                    assert not (node.attr.startswith("__") and node.attr.endswith("__"))
                    assert node.attr not in {"getattr", "setattr", "delattr", "vars", "locals", "globals", "eval", "exec"}
                if isinstance(node, ast.Name):
                    assert node.id not in {"vars", "locals", "globals", "eval", "exec", "__import__"}
                    if node.id in {"getattr", "setattr", "delattr"}:
                        parent = parents.get(node)
                        assert isinstance(parent, ast.Call) and parent.func is node
        # Saving the scenario method or obtaining it through another receiver
        # is outside the admitted syntax, even if a later call hides its name.
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in {"run_no_ref", "cancel_no_ref"}:
                call = parents.get(node)
                awaitable = parents.get(call)
                assert isinstance(node.value, ast.Name) and node.value.id == "self"
                assert isinstance(call, ast.Call) and call.func is node and not call.args and not call.keywords
                assert isinstance(awaitable, ast.Await) and awaitable.value is call
        # Finite, conservative self-method reachability also covers a helper
        # or saved method reference invoked indirectly from failure cleanup.
        graph = {}
        function_names = {node.name for node in ast.walk(tree)
                          if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        for method in ast.walk(tree):
            if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                graph.setdefault(method.name, set()).update(
                    node.attr for node in ast.walk(method) if isinstance(node, ast.Attribute))
                graph[method.name].update(node.id for node in ast.walk(method)
                                          if isinstance(node, ast.Name) and node.id in function_names)
        pending = [name for name in graph if "cleanup" in name]
        # Any exception/finally edge is failure cleanup, including execute's
        # finally and stop_workers' error branch. Normal execute->run_cases is
        # deliberately not a cleanup root.
        for attempt in ast.walk(tree):
            if isinstance(attempt, (ast.Try, ast.TryStar)):
                for statement in [*attempt.finalbody, *attempt.handlers]:
                    pending.extend(node.attr for node in ast.walk(statement)
                                   if isinstance(node, ast.Attribute))
                    pending.extend(node.id for node in ast.walk(statement)
                                   if isinstance(node, ast.Name) and node.id in function_names)
        reached = set()
        while pending:
            name = pending.pop()
            if name in reached:
                continue
            reached.add(name)
            assert name != "cancel_no_ref"
            pending.extend(graph.get(name, set()) - reached)
    else:
        assert not methods


def _dag2_bare_runner(monkeypatch):
    from types import SimpleNamespace
    runner = m.Dag2Runner.__new__(m.Dag2Runner)
    runner.started = 100.0
    runner.deadline = 250.0
    runner.service_deadline = 340.0
    runner.cleanup_deadline = None
    runner.final_stop_deadline = None
    runner.cleanup_started = None
    runner.final_stop_started = None
    runner.diagnostic = m.DiagnosticState("a" * 40)
    runner.observed = m.Dag2Observations(clock=lambda: 100000000000)
    runner.rpc_pending = {}
    runner.rpc_rows = []
    runner.rpc_ids = set()
    runner.handles = {name: SimpleNamespace(id="fixture-" + name,
        run_id="11111111-1111-4111-8111-111111111111")
        for name in ("hosted-normal", "hosted-reconcile", "hosted-no-ref-cancel")}
    runner.pending = {}
    runner.unfinished_updates = set()
    runner.admission_closed = False
    runner.stop_uncertain = False
    runner.workers = []
    runner.worker_rows = []
    runner.worker_stops = []
    monkeypatch.setattr(m.time, "monotonic", lambda: 100.0)
    return runner


def test_dag2_independent_fixed_profile_constants():
    assert m.DAG2_CAPS == DAG2_LITERAL_CAPS
    assert m.DAG2_MISSIONS == ("hosted-normal", "hosted-reconcile", "hosted-no-ref-cancel")
    assert m.DAG2_STOP_ORDER == (2, 1, 4, 3, 6, 5, 8, 7)
    assert m.DAG2_FAILURE_TYPE == "DAG2_TEST_RESPONSE_UNAVAILABLE"


@pytest.mark.parametrize("event,profile,retain,nodes", [
    ("pull_request", "dag2", False, DAG2_LITERAL_NODES),
    ("push", "dag2", False, DAG2_LITERAL_NODES),
    ("workflow_dispatch", "reference", False, DAG2_LITERAL_NODES),
    ("workflow_dispatch", "batch200", False, DAG2_LITERAL_NODES),
    ("workflow_dispatch", "unknown", False, DAG2_LITERAL_NODES),
    ("workflow_dispatch", None, False, DAG2_LITERAL_NODES),
    ("workflow_dispatch", "dag2", True, DAG2_LITERAL_NODES),
    ("workflow_dispatch", "dag2", "false", DAG2_LITERAL_NODES),
    ("workflow_dispatch", "dag2", False, DAG2_LITERAL_NODES[:-1]),
    ("workflow_dispatch", "dag2", False, list(reversed(DAG2_LITERAL_NODES))),
    ("workflow_dispatch", "dag2", False, DAG2_LITERAL_NODES + DAG2_LITERAL_NODES[:1]),
], ids=["pr", "push", "reference", "batch", "unknown", "missing", "retention",
        "string-retention", "missing-node", "reordered", "duplicate"])
def test_dag2_selection_refuses_before_acquisition(event, profile, retain, nodes):
    with pytest.raises(m.GateRunError):
        m.dag2_selection(event, profile, retain, nodes)


def test_dag2_exact_manual_profile_selection():
    assert m.dag2_selection("workflow_dispatch", "dag2", False, DAG2_LITERAL_NODES) is None


def test_dag2_cancellation_guard_accepts_only_literal_same_run_gate():
    _assert_dag2_cancellation_boundary(ast.parse(DAG2_CANCEL_SOURCE), require_call=True)


@pytest.mark.parametrize("source", [
    "async def other():\n    cancel()\n",
    "async def cleanup(self):\n    self.task.cancel()\n",
    "async def cancel_no_ref(self):\n    self.handle.cancel()\n",
    DAG2_CANCEL_SOURCE.replace('self.handles["hosted-no-ref-cancel"]', 'self.handles["hosted-normal"]'),
    DAG2_CANCEL_SOURCE.replace("    self.require_cancel_quiescent(handle)\n", ""),
    DAG2_CANCEL_SOURCE.replace("lambda: handle.cancel", "lambda: self.task.cancel"),
    DAG2_CANCEL_SOURCE.replace("seconds=2", "seconds=3"),
    DAG2_CANCEL_SOURCE.replace("handle.cancel", "getattr(handle, 'cancel')"),
    DAG2_CANCEL_SOURCE.replace("    await self.rpc", "    alias = handle.cancel\n    await self.rpc"),
    DAG2_CANCEL_SOURCE + "\nasync def cleanup(self):\n    await self.cancel_no_ref()\n",
    DAG2_CANCEL_SOURCE + "\nasync def cleanup(self):\n    await self.helper()\n\nasync def helper(self):\n    await self.cancel_no_ref()\n",
    DAG2_CANCEL_SOURCE + "\nasync def cleanup(self):\n    action = self.helper\n    await action()\n\nasync def helper(self):\n    await self.cancel_no_ref()\n",
    DAG2_CANCEL_SOURCE + "\nasync def cleanup(self):\n    owner = self\n    await owner.cancel_no_ref()\n",
    DAG2_CANCEL_SOURCE + "\nasync def cleanup(self):\n    await getattr(self, 'cancel_no_ref')()\n",
    DAG2_CANCEL_SOURCE + "\nasync def run_no_ref(self):\n    try:\n        pass\n    finally:\n        await self.cancel_no_ref()\n",
    DAG2_CANCEL_SOURCE + "\nasync def run_no_ref(self):\n    try:\n        pass\n    except Exception:\n        await self.cancel_no_ref()\n",
    DAG2_CANCEL_SOURCE + "\nasync def other(self):\n    self.future.cancel()\n",
    DAG2_CANCEL_SOURCE.replace("    await self.rpc", "    handle = self.other\n    await self.rpc"),
    DAG2_CANCEL_SOURCE.replace("async def cancel_no_ref", "async def cleanup"),
], ids=["bare-call", "task", "unbound", "other-mission", "no-gate", "wrong-receiver", "timeout",
        "getattr", "alias", "cleanup-call", "indirect-cleanup", "aliased-cleanup", "owner-alias", "dynamic-wrapper", "finally", "error-handler", "extra-call", "rebind", "cleanup-scope"])
def test_dag2_cancellation_guard_rejects_every_other_scope_or_receiver(source):
    with pytest.raises(AssertionError):
        _assert_dag2_cancellation_boundary(ast.parse(source), require_call=True)


def test_dag2_live_cancellation_site_matches_frozen_exact_ast():
    _assert_dag2_cancellation_boundary(ast.parse((ROOT / "ci/run_temporal_server_gate.py").read_text()),
                                       require_call=True, require_live_caller=True)


@pytest.mark.parametrize("first,result,identifier", [
    ("", "", "fixed-workflow"),
    (None, None, "fixed-workflow"),
    ("11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222", "fixed-workflow"),
    ("11111111-1111-4111-8111-111111111111", "11111111-1111-4111-8111-111111111111", "foreign-workflow"),
    (True, True, "fixed-workflow"),
], ids=["empty", "unknown", "different-runs", "wrong-id", "boolean"])
def test_dag2_run_binding_refuses_unknown_or_foreign_identity(first, result, identifier):
    from types import SimpleNamespace
    client = SimpleNamespace(get_workflow_handle=lambda *a, **k: pytest.fail("must not bind"))
    handle = SimpleNamespace(id=identifier, first_execution_run_id=first, result_run_id=result)
    with pytest.raises(m.GateRunError):
        m.dag2_bind_handle(client, handle, "fixed-workflow")


def test_dag2_run_binding_uses_both_actual_run_guards():
    from types import SimpleNamespace
    calls = []
    sentinel = object()
    def get_handle(*args, **kwargs):
        calls.append((args, kwargs)); return sentinel
    client = SimpleNamespace(get_workflow_handle=get_handle)
    run = "11111111-1111-4111-8111-111111111111"
    handle = SimpleNamespace(id="fixed-workflow", first_execution_run_id=run, result_run_id=run)
    assert m.dag2_bind_handle(client, handle, "fixed-workflow") is sentinel
    assert calls == [(("fixed-workflow",), {"run_id": run, "first_execution_run_id": run})]


def test_dag2_rpc_retains_unresolved_original_and_late_settlement_is_sticky(monkeypatch):
    import asyncio
    async def exercise():
        runner = _dag2_bare_runner(monkeypatch)
        future = asyncio.get_running_loop().create_future()
        calls = []
        def issue(): calls.append(True); return future
        async def observer(task, *args, **kwargs):
            raise m.GateRunError("RPC_UNCONFIRMED")
        runner.bounded = observer
        with pytest.raises(m.GateRunError, match="RPC_UNCONFIRMED"):
            await runner.rpc("hosted-normal", "query", "normal-query-1", issue)
        assert calls == [True] and not future.cancelled()
        assert runner.admission_closed and len(runner.rpc_pending) == 1
        assert runner.rpc_pending["normal-query-1"] is future
        assert runner.rpc_rows[0]["settled_seq"] is None
        future.set_result({"actual": "late"})
        await runner.observe_pending_rpc()
        assert not runner.rpc_pending and runner.admission_closed
        assert runner.rpc_rows[0]["outcome"] == "UNCONFIRMED"
        assert runner.rpc_rows[0]["settled_seq"] is not None
        assert calls == [True]
    asyncio.run(exercise())


def test_dag2_rpc_never_resubmits_duplicate_application_operation(monkeypatch):
    import asyncio
    async def exercise():
        runner = _dag2_bare_runner(monkeypatch)
        calls = []
        async def result(): return "ack"
        def issue(): calls.append(True); return result()
        assert await runner.rpc("hosted-normal", "start", "normal-start", issue) == "ack"
        with pytest.raises(m.GateRunError, match="RPC_RESUBMITTED"):
            await runner.rpc("hosted-normal", "start", "normal-start", issue)
        assert calls == [True]
    asyncio.run(exercise())


def test_dag2_rpc_cap_is_checked_before_callback(monkeypatch):
    import asyncio
    runner = _dag2_bare_runner(monkeypatch)
    runner.rpc_rows = [{} for _ in range(64)]
    with pytest.raises(m.GateRunError, match="SIZE_LIMIT"):
        asyncio.run(runner.rpc("hosted-normal", "query", "too-many",
            lambda: pytest.fail("65th operation must not be issued")))


@pytest.mark.parametrize("kind", ["start", "query", "history", "result", "start_update", "update_result", "cancel"])
def test_dag2_every_rpc_kind_retains_actual_task(kind, monkeypatch):
    import asyncio
    async def exercise():
        runner = _dag2_bare_runner(monkeypatch)
        future = asyncio.get_running_loop().create_future()
        future.set_result("observed")
        assert await runner.rpc("hosted-normal", kind, "test-" + kind.replace("_", "-"), lambda: future) == "observed"
        row = runner.rpc_rows[0]
        assert row["kind"] == kind and row["application_submissions"] == 1
        assert row["follow_runs"] is False and row["rpc_timeout_seconds"] == 2
        assert row["observation_timeout_seconds"] == 3
        assert row["issued_seq"] < row["settled_seq"] and not runner.rpc_pending
    asyncio.run(exercise())


@pytest.mark.parametrize("fault", ["handler", "runtime", "adapter", "history", "rpc", "update", "uncertain"])
def test_dag2_quiescence_requires_all_independent_dimensions(fault, monkeypatch):
    runner = _dag2_bare_runner(monkeypatch)
    assert runner.quiescent()
    if fault == "handler": runner.observed.counts["handler_entries"] = 1
    if fault == "runtime": runner.observed.counts["runtime_entries"] = 1
    if fault == "adapter": runner.observed.counts["in_flight_calls"] = 1
    if fault == "history": runner.pending["hosted-normal"] = object()
    if fault == "rpc": runner.rpc_pending["unresolved"] = object()
    if fault == "update": runner.unfinished_updates.add("original")
    if fault == "uncertain": runner.observed.execution_uncertain = True
    assert not runner.quiescent()


def test_dag2_cleanup_has_single_cumulative_window(monkeypatch):
    runner = _dag2_bare_runner(monkeypatch)
    monkeypatch.setattr(m.time, "monotonic", lambda: 200.0)
    runner.begin_cleanup()
    assert runner.cleanup_started == 200.0 and runner.cleanup_deadline == 240.0
    assert runner.final_stop_deadline == 260.0
    monkeypatch.setattr(m.time, "monotonic", lambda: 230.0)
    runner.begin_cleanup()
    assert runner.cleanup_started == 200.0 and runner.cleanup_deadline == 240.0
    assert runner.final_stop_deadline == 260.0


def test_dag2_cleanup_deadlines_cannot_exceed_service_budget(monkeypatch):
    runner = _dag2_bare_runner(monkeypatch)
    monkeypatch.setattr(m.time, "monotonic", lambda: 325.0)
    runner.begin_cleanup()
    assert runner.cleanup_deadline <= 340.0 and runner.final_stop_deadline <= 340.0


def test_dag2_worker_stop_reuses_single_lifecycle_owner():
    assert m.Dag2Runner.stop_workers is m.Runner.stop_workers
    assert m.Dag2Runner.stop_server is m.Runner.stop_server
    assert m.Dag2Runner.start_server is m.Runner.start_server
    assert m.Dag2Runner.execute is m.Runner.execute


def test_dag2_public_stops_and_executor_completions_are_observed_once(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    async def exercise():
        runner = _dag2_bare_runner(monkeypatch)
        calls = []
        async def shutdown(generation): calls.append(("shutdown", generation))
        class Executor:
            def shutdown(self, *, wait): calls.append(("executor", wait))
        for generation in (1, 2):
            task = asyncio.get_running_loop().create_future(); task.set_result(None)
            async def stop(g=generation): await shutdown(g)
            row = {"generation": generation, "type": "workflow" if generation == 1 else "activity",
                   "public_shutdown_called": False, "public_shutdown_completed": False}
            runner.workers.append({"worker": SimpleNamespace(shutdown=stop), "task": task,
                "row": row, "executor": None if generation == 1 else Executor(),
                "mission": "hosted-normal", "start_seq": generation})
            runner.worker_rows.append(row)
        await runner.stop_workers()
        await runner.stop_workers()
        assert calls == [("shutdown", 2), ("executor", True), ("shutdown", 1)]
        assert [row["generation"] for row in runner.worker_stops] == [2, 1]
        assert [row["executor_shutdown_calls"] for row in runner.worker_stops] == [1, 0]
        assert all(row["public_shutdown_calls"] == 1 and row["worker_run_task_completed"]
                   for row in runner.worker_stops)
    asyncio.run(exercise())


def test_dag2_unconfirmed_shutdown_is_not_invoked_twice(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    async def exercise():
        runner = _dag2_bare_runner(monkeypatch)
        calls = []
        async def shutdown(): calls.append(True); raise RuntimeError("private failure")
        task = asyncio.get_running_loop().create_future(); task.set_result(None)
        runner.workers = [{"worker": SimpleNamespace(shutdown=shutdown), "task": task,
            "row": {"generation": 1, "type": "workflow", "public_shutdown_called": False,
                    "public_shutdown_completed": False}, "executor": None,
            "mission": "hosted-normal", "start_seq": 1}]
        with pytest.raises(RuntimeError): await runner.stop_workers()
        with pytest.raises(m.GateRunError, match="WORKER_STOP_UNCONFIRMED"):
            await runner.stop_workers()
        assert calls == [True] and runner.stop_uncertain
    asyncio.run(exercise())


def test_dag2_original_capture_preserves_independent_literal_bytes_and_origin():
    import copy
    observed = m.Dag2Observations(clock=lambda: 10)
    fixture = copy.deepcopy(DAG2_LITERAL_ORIGINAL)
    observed.capture_original("hosted-normal", "A", fixture["body"], fixture["reference"])
    original = observed.originals[("hosted-normal", "A")]
    assert original["body_bytes"] == DAG2_LITERAL_ORIGINAL["canonical_body_utf8"].encode()
    assert original["body_sha256"] == DAG2_LITERAL_ORIGINAL["body_sha256"]
    assert original["origin"] == DAG2_LITERAL_ORIGINAL["origin"]
    assert original["origin_sha256"] == DAG2_LITERAL_ORIGINAL["origin_sha256"]
    assert observed.counts["result_puts"] == 1 and observed.counts["observer_cas_reads"] == 0
    fixture["body"]["output"] = 99
    fixture["reference"]["sha256"] = "f" * 64
    assert original["body_bytes"] == DAG2_LITERAL_ORIGINAL["canonical_body_utf8"].encode()
    assert original["origin"] == DAG2_LITERAL_ORIGINAL["origin"]


def test_dag2_no_ref_put_does_not_encode_hash_retain_or_read(monkeypatch):
    observed = m.Dag2Observations(clock=lambda: 10)
    class MustNotInspect:
        def __getattribute__(self, name): raise AssertionError("no-ref data inspection")
    observed.capture_original("hosted-no-ref-cancel", "A", MustNotInspect(), MustNotInspect())
    assert observed.counts["result_puts"] == 1
    assert observed.counts["observer_cas_reads"] == 0
    assert not observed.originals


@pytest.mark.parametrize("mission,node,operation", [
    ("hosted-normal", "A", "execute"), ("hosted-normal", "B", "execute"),
    ("hosted-reconcile", "B", "execute"), ("hosted-reconcile", "A", "inspect"),
    ("hosted-no-ref-cancel", "A", "inspect"),
])
def test_dag2_fault_injection_is_exactly_two_a_execution_returns(mission, node, operation):
    assert not m.dag2_should_fail_response(mission, node, operation)


@pytest.mark.parametrize("mission", ["hosted-reconcile", "hosted-no-ref-cancel"])
def test_dag2_fault_is_nonretryable_and_requires_real_handler_and_adapter_return(mission):
    observed = m.Dag2Observations(clock=lambda: 10)
    assert m.dag2_should_fail_response(mission, "A", "execute")
    with pytest.raises(m.GateRunError):
        observed.require_fault_boundary(mission, "A")
    observed.counts["handler_entries"] = observed.counts["handler_returns"] = 1
    observed.counts["runtime_entries"] = observed.counts["runtime_returns"] = 1
    observed.counts["activity_entries"] = observed.counts["activity_returns"] = 1
    observed.returned.add((mission, "A", "execute"))
    assert observed.require_fault_boundary(mission, "A") is None


def test_dag2_observer_event_limit_is_checked_before_append():
    observed = m.Dag2Observations(clock=lambda: 10)
    observed.events = [{} for _ in range(512)]
    before = list(observed.events)
    with pytest.raises(m.GateRunError, match="SIZE_LIMIT"):
        observed.record("query_observed", mission="hosted-normal")
    assert observed.events == before and observed.execution_uncertain


def test_dag2_unknown_event_is_never_recorded():
    observed = m.Dag2Observations(clock=lambda: 10)
    with pytest.raises(m.GateRunError): observed.record("arbitrary_callback")
    assert observed.events == []


@pytest.mark.parametrize("bad", [True, 1.0, -1, 1000000000000000001])
def test_dag2_observer_requires_bounded_plain_monotonic_integer(bad):
    observed = m.Dag2Observations(clock=lambda: bad)
    with pytest.raises(m.GateRunError): observed.record("query_observed", mission="hosted-normal")
    assert observed.events == []


def test_dag2_observer_clocks_may_tie_but_never_regress():
    values = iter((10, 10, 9))
    observed = m.Dag2Observations(clock=lambda: next(values))
    observed.record("query_observed", mission="hosted-normal")
    observed.record("query_observed", mission="hosted-normal")
    with pytest.raises(m.GateRunError): observed.record("query_observed", mission="hosted-normal")
    assert [row["seq"] for row in observed.events] == [1, 2]


def test_dag2_bootstrap_precedes_pollers_and_original_update_by_source_order():
    tree = ast.parse((ROOT / "ci/run_temporal_server_gate.py").read_text())
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Dag2Runner")
    methods = {node.name: node for node in cls.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    start = ast.unparse(methods["start_mission"])
    assert start.index("dag2_bind_handle(") < start.index("self.construct_bootstrap(") < start.index("self.start_worker(")
    reconcile = ast.unparse(methods["run_reconcile"])
    assert reconcile.index("self.stop_workers(") < reconcile.index("self.construct_bootstrap(") < reconcile.index("self.submit_update(")
    assert "original_A=None" in ast.unparse(methods["start_mission"])
    assert "original_B=None" in ast.unparse(methods["construct_bootstrap"])


def test_dag2_replay_uses_default_sdk_and_never_fabricates_completion_result():
    source = (ROOT / "ci/run_temporal_server_gate.py").read_text()
    tree = ast.parse(source)
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Dag2Runner")
    replay = next(node for node in cls.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "replay_snapshot")
    text = ast.unparse(replay)
    assert "Replayer(" in text and "replay_failure" in text and "replay_workflow(" in text
    assert "workflow_runner=" not in text and "passthrough" not in text
    assert "activity_worker_count" in text and "counts_before" in text and "counts_after" in text
    assert not any(isinstance(node, ast.Attribute) and node.attr in {"result", "completion_result"}
                   for node in ast.walk(replay))


def test_dag2_owned_workflow_results_never_follow_another_run():
    tree = ast.parse((ROOT / "ci/run_temporal_server_gate.py").read_text())
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Dag2Runner")
    method = next(node for node in cls.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "workflow_result")
    calls = [node for node in ast.walk(method) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Attribute) and node.func.attr == "result"]
    assert len(calls) == 1
    assert any(keyword.arg == "follow_runs" and isinstance(keyword.value, ast.Constant)
               and keyword.value.value is False for keyword in calls[0].keywords)


def test_dag2_harness_has_no_cas_enumeration_or_failure_cleanup_cancel():
    tree = ast.parse((ROOT / "ci/run_temporal_server_gate.py").read_text())
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Dag2Runner")
    forbidden = {"rglob", "glob", "iterdir", "walk", "kill", "terminate", "reset_workflow_execution"}
    assert not any(isinstance(node, ast.Attribute) and node.attr in forbidden for node in ast.walk(cls))
    cleanup = next(node for node in cls.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "cleanup")
    assert not any(isinstance(node, ast.Attribute) and node.attr in
                   {"cancel", "cancel_no_ref", "start_mission", "submit_update", "start_workflow"}
                   for node in ast.walk(cleanup))


@pytest.mark.parametrize("kind", ["workflow", "activity"])
def test_dag2_worker_options_have_one_external_slot_and_no_eager_execution(kind):
    options = m.dag2_worker_options(kind)
    assert options["disable_eager_activity_execution"] is True
    assert options["graceful_shutdown_timeout"] == timedelta(seconds=5)
    if kind == "workflow":
        assert options["max_concurrent_workflow_tasks"] == 1
        assert options["max_concurrent_workflow_task_polls"] == 1
        assert options["max_cached_workflows"] == 0 and options["no_remote_activities"] is True
    else:
        assert options["max_concurrent_activities"] == 1
        assert options["max_concurrent_activity_task_polls"] == 1
    assert "workflow_runner" not in options and "sandboxed" not in options


def test_dag2_unknown_worker_kind_is_refused():
    with pytest.raises(m.GateRunError): m.dag2_worker_options("arbitrary")


def test_dag2_rpc_caller_cancellation_keeps_original_task_owned(monkeypatch):
    import asyncio
    async def exercise():
        runner = _dag2_bare_runner(monkeypatch)
        future = asyncio.get_running_loop().create_future()
        entered = asyncio.Event()
        calls = []
        def issue(): calls.append(True); return future
        async def wait(task, *args, **kwargs):
            entered.set()
            done, _ = await asyncio.wait({task})
            return next(iter(done)).result()
        runner.bounded = wait
        producer = asyncio.create_task(runner.rpc("hosted-normal", "start", "normal-start", issue))
        await entered.wait()
        producer.cancel()
        with pytest.raises(asyncio.CancelledError): await producer
        assert calls == [True] and not future.cancelled() and runner.admission_closed
        assert runner.rpc_pending["normal-start"] is future
        future.set_result("late-ack")
        await runner.observe_pending_rpc()
        assert runner.admission_closed and not runner.rpc_pending
        assert runner.rpc_rows[0]["outcome"] == "UNCONFIRMED"
    asyncio.run(exercise())


def test_dag2_expired_rpc_never_calls_factory(monkeypatch):
    import asyncio
    runner = _dag2_bare_runner(monkeypatch)
    runner.deadline = 99.0
    with pytest.raises(m.GateRunError):
        asyncio.run(runner.rpc("hosted-normal", "start", "normal-start",
            lambda: pytest.fail("expired work must never be scheduled")))
    assert not runner.rpc_pending


def test_dag2_trace_byte_cap_is_checked_before_appending(monkeypatch):
    observed = m.Dag2Observations(clock=lambda: 10)
    observed.trace_bytes = 262144
    with pytest.raises(m.GateRunError, match="SIZE_LIMIT"):
        observed.record("query_observed", mission="hosted-normal")
    assert observed.events == [] and observed.execution_uncertain


def test_dag2_private_evidence_writer_checks_bytes_before_creating_file(tmp_path):
    target = tmp_path / "oversize.json"
    with pytest.raises(m.GateRunError, match="SIZE_LIMIT"):
        m.write_dag2_json(target, {"fixed": "a" * 256}, 256)
    assert not target.exists()


def test_dag2_private_evidence_writer_rejects_overwrite(tmp_path):
    target = tmp_path / "fixed.json"
    target.write_bytes(b"previous-record")
    with pytest.raises((m.GateRunError, FileExistsError)):
        m.write_dag2_json(target, {"fixed": True}, 256)
    assert target.read_bytes() == b"previous-record"


def test_dag2_private_evidence_writer_has_restricted_mode(tmp_path):
    target = tmp_path / "fixed.json"
    m.write_dag2_json(target, {"fixed": True}, 256)
    assert target.read_bytes() == b'{"fixed":true}\n'
    assert target.stat().st_mode & 0o777 == 0o600


def test_dag2_profile_failure_happens_before_root_or_acquisition(monkeypatch, tmp_path):
    root = tmp_path / "fresh"
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    monkeypatch.setenv("OPENDOT_TEMPORAL_QUALIFICATION", "dag2")
    monkeypatch.setattr(m, "preflight", lambda *a, **k: pytest.fail("must not preflight"))
    with pytest.raises(m.GateRunError):
        m.run_dag2_gate(root, tmp_path / "temporal", DAG2_LITERAL_NODES)
    assert not root.exists()


@pytest.mark.parametrize("phase", ["observation_cleanup", "worker_shutdown", "server_shutdown"])
def test_dag2_cancellation_runtime_gate_refuses_cleanup_even_when_quiescent(phase, monkeypatch):
    runner = _dag2_bare_runner(monkeypatch)
    runner.cleanup_started = 100.0
    runner.diagnostic.phase = phase
    with pytest.raises(m.GateRunError, match="CANCEL_SCOPE"):
        runner.require_cancel_quiescent(runner.handles["hosted-no-ref-cancel"])



def test_dag2_cancellation_guard_allows_only_direct_scenario_caller():
    source = DAG2_CANCEL_SOURCE + "\nasync def run_no_ref(self):\n    await self.cancel_no_ref()\n"
    _assert_dag2_cancellation_boundary(ast.parse(source), require_call=True, require_live_caller=True)


@pytest.mark.parametrize("phase", ["selection", "preflight", "bootstrap", "start", "execution",
    "history", "query", "update", "replay", "observation_cleanup", "worker_shutdown",
    "server_shutdown", "evidence_write", "verification"])
def test_dag2_cancellation_runtime_phase_gate_is_independent_of_cleanup_started(phase, monkeypatch):
    runner = _dag2_bare_runner(monkeypatch)
    runner.cleanup_started = None
    runner.diagnostic.phase = phase
    with pytest.raises(m.GateRunError, match="CANCEL_SCOPE"):
        runner.require_cancel_quiescent(runner.handles["hosted-no-ref-cancel"])


@pytest.mark.parametrize("fault", ["closed-admission", "primary-failure", "stop-uncertain", "execution-uncertain"])
def test_dag2_cancellation_runtime_failure_gate_is_independent_of_cleanup_started(fault, monkeypatch):
    runner = _dag2_bare_runner(monkeypatch)
    runner.cleanup_started = None
    runner.diagnostic.phase = "cancel"
    if fault == "closed-admission": runner.admission_closed = True
    if fault == "primary-failure": runner.diagnostic.primary_failure = {"code": "INTERNAL_ERROR", "phase": "execution"}
    if fault == "stop-uncertain": runner.stop_uncertain = True
    if fault == "execution-uncertain": runner.observed.execution_uncertain = True
    with pytest.raises(m.GateRunError, match="CANCEL_SCOPE"):
        runner.require_cancel_quiescent(runner.handles["hosted-no-ref-cancel"])


@pytest.mark.parametrize("scope,edge", [("execute", "finally"), ("stop_workers", "except Exception")])
def test_dag2_cancellation_guard_rejects_indirect_owner_failure_edges(scope, edge):
    source = DAG2_CANCEL_SOURCE + "\nasync def run_no_ref(self):\n    await self.cancel_no_ref()\n"
    source += f"\nasync def {scope}(self):\n    try:\n        pass\n    {edge}:\n        await self.run_no_ref()\n"
    with pytest.raises(AssertionError):
        _assert_dag2_cancellation_boundary(ast.parse(source), require_call=True, require_live_caller=True)


def test_dag2_cancellation_guard_preserves_legitimate_execute_scenario_path():
    source = DAG2_CANCEL_SOURCE + "\nasync def run_no_ref(self):\n    await self.cancel_no_ref()\n"
    source += "\nasync def run_cases(self):\n    await self.run_no_ref()\n"
    source += "\nasync def execute(self):\n    try:\n        await self.run_cases()\n    finally:\n        await self.cleanup()\n"
    source += "\nasync def cleanup(self):\n    await self.stop_workers()\n"
    source += "\nasync def stop_workers(self):\n    pass\n"
    _assert_dag2_cancellation_boundary(ast.parse(source), require_call=True, require_live_caller=True)


def _dag2_cancellation_owner_fixture(extra_methods, layout):
    scenario = DAG2_CANCEL_SOURCE + "\nasync def run_no_ref(self):\n    await self.cancel_no_ref()\n"
    def indent(source):
        return "".join("    " + line if line.strip() else line for line in source.splitlines(keepends=True))
    if layout == "module":
        return scenario + extra_methods
    if layout == "owner":
        return "class Dag2Runner:\n" + indent(scenario + extra_methods)
    assert layout == "inherited"
    return "class Runner:\n" + indent(extra_methods) + "\nclass Dag2Runner(Runner):\n" + indent(scenario)


@pytest.mark.parametrize("layout", ["module", "owner", "inherited"])
@pytest.mark.parametrize("extra_methods", [
    "\nasync def cleanup(self):\n    alias = self\n    await alias.run_no_ref()\n",
    "\nasync def cleanup(self):\n    resolve = getattr\n    target = resolve(self, 'cancel_no_ref')\n    await target()\n",
    "\nasync def cleanup(self):\n    await getattr(self, 'cancel' + '_no_ref')()\n",
    "\nasync def cleanup(self):\n    await type(self).run_no_ref(self)\n",
    "\nasync def cleanup(self):\n    owner_type = type(self)\n    action = owner_type.run_no_ref\n    await action(self)\n",
    "\nasync def cleanup(self):\n    import builtins as resolver\n    await resolver.getattr(self, 'run_no_ref')()\n",
    "\nasync def cleanup(self):\n    action = self.run_no_ref\n    await invoke(action)\n",
    "\nasync def cleanup(self):\n    async def nested():\n        alias = self\n        await alias.run_no_ref()\n    await nested()\n",
    "\nasync def cleanup(self):\n    await self.helper()\n\nasync def helper(self):\n    alias = self\n    await alias.run_no_ref()\n",
    "\nasync def cleanup(self):\n    owner = self.__class__\n    await owner.run_no_ref(self)\n",
    "\nasync def cleanup(self):\n    await locals()['self'].run_no_ref()\n",
    "\nasync def execute(self):\n    try:\n        pass\n    finally:\n        alias = self\n        await alias.run_no_ref()\n",
    "\nasync def stop_workers(self):\n    try:\n        pass\n    except Exception:\n        resolve = getattr\n        await resolve(self, 'run_' + 'no_ref')()\n",
], ids=["cleanup-receiver-alias", "getattr-builtin-alias", "computed-getattr", "object-unbound-method",
        "rebound-class-alias", "builtins-getattr-alias", "escaped-bound-method", "nested-owner-alias",
        "helper-owner-alias", "owner-class-lookup", "owner-locals-lookup", "finally-owner-alias",
        "except-computed-resolver"])
def test_dag2_cancellation_guard_refuses_dynamic_cleanup_paths(extra_methods, layout):
    source = _dag2_cancellation_owner_fixture(extra_methods, layout)
    with pytest.raises(AssertionError):
        _assert_dag2_cancellation_boundary(ast.parse(source), require_call=True, require_live_caller=True)


@pytest.mark.parametrize("layout", ["module", "owner", "inherited"])
def test_dag2_cancellation_guard_keeps_direct_chain_and_unrelated_data_owner(layout):
    lifecycle = "\nasync def run_cases(self):\n    await self.run_no_ref()\n"
    lifecycle += "\nasync def execute(self):\n    try:\n        await self.run_cases()\n    finally:\n        await self.cleanup()\n"
    lifecycle += "\nasync def cleanup(self):\n    await self.stop_workers()\n"
    lifecycle += "\nasync def stop_workers(self):\n    pass\n"
    source = _dag2_cancellation_owner_fixture(lifecycle, layout)
    source += "\nclass DiagnosticData:\n    def read(self, field):\n        return getattr(self, field)\n"
    _assert_dag2_cancellation_boundary(ast.parse(source), require_call=True, require_live_caller=True)


def test_dag2_cancellation_guard_includes_existing_inherited_lifecycle():
    # Parse the unchanged owner only; never instantiate it or execute a service.
    source = (ROOT / "ci/run_temporal_server_gate.py").read_text()
    if not any(isinstance(node, ast.ClassDef) and node.name == "Dag2Runner" for node in ast.walk(ast.parse(source))):
        scenario = DAG2_CANCEL_SOURCE + "\nasync def run_no_ref(self):\n    await self.cancel_no_ref()\n"
        scenario += "\nasync def run_cases(self):\n    await self.run_no_ref()\n"
        source += "\nclass Dag2Runner(Runner):\n" + "".join("    " + line if line.strip() else line
                                                           for line in scenario.splitlines(keepends=True))
    _assert_dag2_cancellation_boundary(ast.parse(source), require_call=True, require_live_caller=True)


# Root-authorized v2 controls for independently reproduced runner v1 defects.
def test_dag2_final_stop_deadline_tightens_at_actual_phase_start(monkeypatch):
    import asyncio
    runner = _dag2_bare_runner(monkeypatch)
    runner.server = None
    runner.server_rows = []
    runner.cancel_calls = 0
    monkeypatch.setattr(m.time, "monotonic", lambda: 200.0)
    cleanup = asyncio.run(runner.cleanup())
    assert runner.cleanup_deadline == 240.0
    assert runner.final_stop_started == 200.0
    assert runner.final_stop_deadline == 220.0
    assert cleanup["cleanup_status"] == "PASS"


def test_dag2_evidence_rejection_persists_failure_after_completed_effect(monkeypatch, tmp_path):
    import asyncio
    import verify_temporal_server_gate as verifier
    runner = _dag2_bare_runner(monkeypatch)
    runner.root = tmp_path
    (tmp_path / "audit").mkdir()
    (tmp_path / "private").mkdir()
    runner.cli = tmp_path / "temporal"
    (tmp_path / "acquisition-receipt.json").write_bytes(b'{"FABRICATED_UNIT_DATA":true}')
    pip = tmp_path / "pip-report.json"
    pip.write_bytes(b'{"FABRICATED_UNIT_DATA":true}')
    monkeypatch.setenv("OPENDOT_TEMPORAL_PIP_REPORT", str(pip))
    runner.source_manifest = {"files": [{"path": name} for name in m.DAG2_SOURCE_CLOSURE]}
    runner.source_manifest_bytes = b'{"FABRICATED_UNIT_DATA":true}'
    runner.identity = {"fixture": "FABRICATED_UNIT_DATA"}
    runner.environment = {"server_version": "1.32.0"}
    runner.bootstraps, runner.histories, runner.updates, runner.replays = [], [], [], []
    runner.outcomes, runner.replay = [], None
    runner.raw_files = {}
    runner.worker_stops = [{"generation": value} for value in m.DAG2_STOP_ORDER]
    runner.diagnostic = m.Dag2DiagnosticState("a" * 40)
    runner.evidence_started_ns = m.time.monotonic_ns()
    completed_effect = tmp_path / "audit" / "normal-a.result.json"
    actual = []
    async def scenario():
        completed_effect.write_bytes(b'{"FABRICATED_UNIT_DATA":"completed-effect"}')
        runner.evidence_complete = True
    async def cleanup():
        actual.append("cleanup-observed")
        runner.diagnostic.cleanup_observation = "PASS"
        return {"cleanup_status": "PASS", "evidence_and_pytest_elapsed_ms": 0}
    def reject(*args, **kwargs):
        actual.append("record-validation-refused")
        raise verifier.GateError("HISTORY_MISMATCH")
    runner.run_cases, runner.cleanup = scenario, cleanup
    monkeypatch.setattr(m, "dag2_check_source", lambda *args: None)
    monkeypatch.setattr(verifier, "validate_dag2_records", reject)
    with pytest.raises(m.GateRunError, match="SERVER_GATE_FAILED"):
        asyncio.run(runner.execute())
    record = json.loads((tmp_path / "audit" / "dag2-diagnostic.json").read_bytes())
    assert actual == ["cleanup-observed", "record-validation-refused"]
    assert completed_effect.read_bytes() == b'{"FABRICATED_UNIT_DATA":"completed-effect"}'
    assert record["result"] == "FAIL" and record["evidence_status"] == "INCOMPLETE"
    assert record["cleanup_status"] == "PASS" and record["primary_failure"] is None
    assert record["cleanup_failure"] is None
    assert record["audit_failure"] == {"phase": "evidence_write", "code": "HISTORY_MISMATCH"}
    assert not (tmp_path / "audit" / "dag2-manifest.json").exists()


def test_dag2_unreadable_node_manifest_uses_unchained_fixed_fixture_error(monkeypatch):
    from types import SimpleNamespace
    spec = importlib.util.spec_from_file_location("dag2_acceptance_prerequisite_control",
        ROOT / "tests/acceptance/temporal_dag_recovery_gate.py")
    acceptance = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(acceptance)
    monkeypatch.setitem(sys.modules, "run_temporal_server_gate", m)
    monkeypatch.setattr(m, "run_dag2_gate", lambda *args, **kwargs: pytest.fail("scenario must not execute"))
    original_read = Path.read_text
    def unreadable(path, *args, **kwargs):
        if path.name == "temporal-dag-recovery-nodes.txt":
            raise OSError("FABRICATED_PRIVATE_MARKER /private/fixture secret=unit-only")
        return original_read(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", unreadable)
    request = SimpleNamespace(session=SimpleNamespace(items=[SimpleNamespace(nodeid=node)
        for node in m.DAG2_REQUIRED_NODES]))
    with pytest.raises(pytest.fail.Exception) as captured:
        acceptance.dag2_gate.__wrapped__(request)
    assert str(captured.value) == "DAG2_SETUP_OR_EVIDENCE_FAILED"
    assert captured.value.pytrace is False
    assert captured.value.__context__ is None and captured.value.__cause__ is None
