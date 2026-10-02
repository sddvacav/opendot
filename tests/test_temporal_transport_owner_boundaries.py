"""Static/default-path gates run without the optional Temporal distribution."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/opendot_engineering"
OWNERS = {
    "tool_runtime.py": "7c5011e02b2cf07e5f15ad7854905ce0738271e167b873bad9256a8ed169199c",
    "core/artifacts.py": "4606b7b11a81044267b30fee332d9b6fd6540d862726a9579655ee27c7d9a883",
    "core/contracts.py": "9462415baf84668825ad2c8cfc3f4f3df68332f65d1f1f4b301fbf01cf8537ca",
}


@pytest.mark.parametrize("path,digest", OWNERS.items())
def test_exact_owner_bytes(path, digest):
    assert hashlib.sha256((SOURCE / path).read_bytes()).hexdigest() == digest


def test_only_explicit_modules_import_temporal():
    for path in SOURCE.rglob("*.py"):
        if path.name in {"temporal_activity.py", "temporal_workflow.py"}:
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                assert all(not alias.name.startswith("temporalio") for alias in node.names)
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith("temporalio")
                assert not any("temporal_activity" in alias.name or "temporal_workflow" in alias.name
                               for alias in node.names)


def test_default_dependencies_empty_and_optional_pin_exact():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    assert project["dependencies"] == []
    assert project["optional-dependencies"]["temporal"] == ["temporalio==1.34.0"]


def test_fixed_declaration_signature_independently_computed():
    declaration = {
        "backend_binding": {"kind": "callable"}, "tool_id": "synthetic.bounded_sum",
        "version": "1", "input_schema": "synthetic.bounded_sum.input/v1",
        "output_schema": "synthetic.bounded_sum.output/v1", "risk": "read_only",
        "timeout_s": 1.0, "max_retries": 0, "idempotent": True,
        "permissions": ["synthetic:read"],
    }
    digest = hashlib.sha256(json.dumps(declaration, sort_keys=True, ensure_ascii=False,
        separators=(",", ":")).encode()).hexdigest()
    tree = ast.parse((SOURCE / "adapters/temporal_activity.py").read_text())
    pin = next(node.value.value for node in tree.body if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name) and node.targets[0].id == "REGISTRATION_SHA256")
    assert digest == pin == "5f2b1e81954530f31c7d2c83b9c582883b8391190ebe13b69b8bf91f044cb0c3"


def test_exactly_one_fixed_execute_call_and_canonical_owner_reuse():
    tree = ast.parse((SOURCE / "adapters/temporal_activity.py").read_text())
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    execute = [node for node in calls if isinstance(node.func, ast.Attribute) and node.func.attr == "execute"]
    assert len(execute) == 1
    call = execute[0]
    assert ast.unparse(call.func) == "self.runtime.execute"
    kwargs = {keyword.arg: ast.unparse(keyword.value) for keyword in call.keywords}
    assert kwargs == {"granted_permissions": "self.granted_permissions", "approval_token": "None",
        "backoff_base_s": "0.0", "attempt_limit": "1"}
    assert not any(isinstance(node.func, ast.Name) and node.func.id in {
        "ToolRuntime", "ArtifactStore", "_ObservedToolExecution", "ToolCallReceipt"} for node in calls)
    assert not any(isinstance(node.func, ast.Attribute) and node.func.attr in {
        "_dispatch", "_check_guard", "register", "can_retry", "reset", "set",
        "connect", "start", "start_activity", "start_workflow", "heartbeat", "sleep",
        "cancel", "shield_thread_cancel_exception"} for node in calls)
    assert not any(isinstance(node, ast.Attribute) and node.attr in {
        "_specs", "_handlers", "_guard_binding"} for node in ast.walk(tree))
    assert not any(isinstance(node, ast.ImportFrom) and node.module == "contextvars" for node in ast.walk(tree))
    assert not any(isinstance(node, ast.Import) and any(alias.name == "contextvars" for alias in node.names)
                   for node in ast.walk(tree))
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                   and node.func.id in {"eval", "exec", "__import__"} for node in ast.walk(tree))


def test_run_has_ordered_gates_one_read_and_one_put():
    tree = ast.parse((SOURCE / "adapters/temporal_activity.py").read_text())
    owner = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ReferenceActivity")
    run = next(node for node in owner.body if isinstance(node, ast.FunctionDef) and node.name == "run")
    calls = sorted((node for node in ast.walk(run) if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)), key=lambda node: node.lineno)
    names = [node.func.attr for node in calls]
    assert names.count("_admit") == names.count("get_bytes") == names.count("execute") == names.count("put_json") == 1
    assert names.index("_admit") < names.index("get_bytes") < names.index("execute") < names.index("put_json")
    read = next(node for node in calls if node.func.attr == "get_bytes")
    assert ast.unparse(read.func) == "self.store.get_bytes"
    assert {keyword.arg: ast.unparse(keyword.value) for keyword in read.keywords} == {"max_bytes": "256"}
    assert not any(isinstance(node, (ast.For, ast.While, ast.AsyncFor)) for node in ast.walk(run))
    # No catch encompasses the actual owner execute boundary.
    for node in ast.walk(run):
        if isinstance(node, ast.Try):
            assert not any(isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute)
                           and child.func.attr == "execute" for statement in node.body for child in ast.walk(statement))


def test_json_helper_is_imported_not_reimplemented():
    tree = ast.parse((SOURCE / "adapters/temporal_activity.py").read_text())
    assert any(isinstance(node, ast.ImportFrom) and node.module == "source_audit"
               and any(alias.name == "_decode" for alias in node.names) for node in tree.body)
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                   and node.func.attr in {"loads", "load", "read_bytes", "write_bytes"} for node in ast.walk(tree))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "dumps":
            assert not any(keyword.arg == "default" for keyword in node.keywords)
            assert any(keyword.arg == "allow_nan" and isinstance(keyword.value, ast.Constant)
                       and keyword.value.value is False for keyword in node.keywords)


def test_accepted_exception_preserves_scope():
    agents = (ROOT / "AGENTS.md").read_text()
    adr = (ROOT / "docs/decisions/004-temporal-reference-transport.md").read_text()
    assert "Do not connect it to orchestration" in agents
    assert "Narrow ADR 004 exception" in agents
    assert "Deployment, merge and publication are NOT accepted" in adr
    assert "single" in adr and "pre-guard" in adr
