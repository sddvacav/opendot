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
    "adapters/source_audit.py": "c94737305b1e5a80453541ce890bde4fcb700a0074e32344fe839b237374bfa7",
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
    # Preserve old-v1 exact assertions on its original owner subtree.
    original = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                    and node.name == "ReferenceActivity")
    calls = [node for node in ast.walk(original) if isinstance(node, ast.Call)]
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


# Source-segment hashes captured before ADR 008 executable edits.
ORIGINAL_DEFINITIONS = {'temporal_activity': {'ReferenceActivity': '805952020fcc5b191deb0318e5a3a7c4c31f71bc0b45a40c38e8655c41fa7139',
                       '_bounded_json': '5a5514c17e109f54415a51ef3974f7c814a42be3db2d4d74337a793a15bebc06',
                       '_check_sdk': '6f49d6c52fa6e142726cad4a417e44c89ce27f90eb50d712f1582150c9172533',
                       '_failure': '3777a4daa9f3ac0054719fee52c79896506646247a8e306cb1eb301ad9fcb4e0',
                       '_hex': '2ebd8c02e24110e5bda515ce8ea9fdad762f295c3629e341f98d59b1e6929de9',
                       '_label': '3803b82fa2a032cec5af148543370ae05840fdf180b4547f514385e4b9814df5',
                       '_receipt_report': 'c35ae5a93ddb4d7418ea431812b23659db957ff2b13cd88f7417e1ef9a68fa09',
                       '_reference': 'f10f5ebe91597d2df3c8428b6702af2c6090d0b84c9c548ce591bafdb77eeaba',
                       '_reference_record': 'b5c237807904dd2d6a482ff50a9a24aaac211ac9d75ecd6b40277336f43f84d1',
                       '_require': '423556010d69884fa11029a80ac39698c12a20a285b5b11beecd6b3bf3135707',
                       '_shape': '7b9ac450629172b29dc6e0c66b5b34863ae59d53c20bac608af5341d026e39e1',
                       '_text': '9866416dd228c3b6ed1ba507acc1dab80b827f01ef1bdd61b223c8c7bb4c0a8c',
                       '_validate_payload': '3625d6116460701e2dd5ffc1314b390fbc5de1b81674fbcf699bc234c9c8a86e',
                       'bounded_sum': '07cd889e3963786941bd3c62f7ae0fcc6e45b5e5d530144060e44dfe990f222e',
                       'bounded_sum_valid': '4a38ac00b55f3733beda237dca5c91cdc7eb740a9f478444010465308e80bc9d'},
 'temporal_workflow': {'execute_reference': 'd5bc30f176b9111e98b27d4e02d40224f45b6c76d9c2607552dbdb23c68bb736'}}


@pytest.mark.parametrize("module", ["temporal_activity", "temporal_workflow"])
def test_every_original_v1_definition_remains_exact(module):
    text = (SOURCE / "adapters" / (module + ".py")).read_text()
    definitions = {node.name: node for node in ast.parse(text).body
                   if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    for name, expected in ORIGINAL_DEFINITIONS[module].items():
        assert hashlib.sha256(ast.get_source_segment(text, definitions[name]).encode()).hexdigest() == expected


def test_fixed_dag_activity_is_the_only_added_execution_owner():
    tree = ast.parse((SOURCE / "adapters/temporal_activity.py").read_text())
    assert [node.name for node in tree.body if isinstance(node, ast.ClassDef)] == [
        "ReferenceActivity", "DependentSumActivity"]
    owner = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                 and node.name == "DependentSumActivity")
    all_calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    execution = [node for node in all_calls if isinstance(node.func, ast.Attribute)
                 and node.func.attr == "execute"]
    assert len(execution) == 2  # original reference call plus exactly one fixed-DAG call site
    calls = [node for node in ast.walk(owner) if isinstance(node, ast.Call)]
    execute = [node for node in calls if isinstance(node.func, ast.Attribute) and node.func.attr == "execute"]
    assert len(execute) == 1
    assert ast.unparse(execute[0].func) == "self.runtime.execute"
    options = {keyword.arg: ast.unparse(keyword.value) for keyword in execute[0].keywords}
    assert options == {"granted_permissions": "self.granted_permissions", "approval_token": "None",
                       "backoff_base_s": "0.0", "attempt_limit": "1"}
    inspector = next(node for node in owner.body if isinstance(node, ast.FunctionDef)
                     and node.name == "inspect_result")
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                   and node.func.attr in {"execute", "put_json", "put_bytes", "register", "can_retry"}
                   for node in ast.walk(inspector))
    assert not any(isinstance(node.func, ast.Name) and node.func.id in {
        "ToolRuntime", "ArtifactStore", "_ObservedToolExecution", "ToolCallReceipt"} for node in all_calls)
    assert not any(isinstance(node.func, ast.Attribute) and node.func.attr in {
        "_dispatch", "_check_guard", "register", "can_retry", "reset", "set", "connect",
        "start", "start_activity", "start_workflow", "heartbeat", "sleep", "cancel"}
        for node in all_calls)
    assert not any(isinstance(node, ast.Attribute) and node.attr in {
        "_specs", "_handlers", "_guard_binding"} for node in ast.walk(tree))
    for call in all_calls:
        if isinstance(call.func, ast.Attribute) and call.func.attr == "get_bytes":
            values = {keyword.arg: keyword.value for keyword in call.keywords}
            assert set(values) == {"max_bytes"}
            assert isinstance(values["max_bytes"], ast.Constant)
            assert values["max_bytes"].value in {256, 16384}


def test_fixed_dag_exception_has_no_default_or_dependency_expansion():
    agents = (ROOT / "AGENTS.md").read_text()
    adr = (ROOT / "docs/decisions/008-fixed-dependent-temporal-recovery.md").read_text()
    assert "Narrow ADR 008" in agents and "at most two read-only inspections" in agents
    assert hashlib.sha256(adr.encode()).hexdigest() == "c7d18394d4a88b74e9b0b30ba5ba960bbc5177e19b2f6c115db91b23819b6737"
    for relative in ("__init__.py", "adapters/__init__.py", "core/__init__.py"):
        source = (SOURCE / relative).read_text()
        assert "temporal_workflow" not in source and "temporal_activity" not in source
