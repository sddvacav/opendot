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
