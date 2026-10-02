"""SDK-only scheduling contracts; no service, native runtime or history replay.

The public-call spy proves the helper's submitted options. The test-only fake
SDK runtime additionally observes the tagged SDK's non-local scheduling path;
neither harness proves server command persistence, delivery or history replay.
"""
from __future__ import annotations

import ast
import asyncio
import copy
from datetime import timedelta
import importlib
from importlib.metadata import PackageNotFoundError, version
import inspect
from pathlib import Path
from unittest.mock import AsyncMock
from typing import Any

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "src/opendot_engineering/adapters/temporal_workflow.py"
)


@pytest.fixture
def bridge():
    # Qualification is explicitly outside Workflow execution. Static contracts
    # below still run when the optional SDK is not installed.
    try:
        installed = version("temporalio")
    except PackageNotFoundError:
        pytest.skip("optional Temporal SDK is not installed")
    if installed != "1.34.0":
        pytest.skip("exact optional Temporal SDK 1.34.0 is not installed")
    return importlib.import_module("opendot_engineering.adapters.temporal_workflow")


@pytest.fixture
def request_envelope():
    digest = "a" * 64
    return {
        "schema_version": "opendot.temporal.request.v1",
        "input_ref": {
            "artifact_id": "sha256:" + digest,
            "uri": "artifact://sha256/" + digest,
            "mime_type": "application/json",
            "size_bytes": 42,
            "sha256": digest,
            "schema_version": "1.0.0",
            "producer": "synthetic-producer",
            "task_id": "synthetic-task",
            "source_refs": [],
            "integrity_verified": False,
        },
    }


@pytest.fixture
def response_envelope(request_envelope):
    digest = "b" * 64
    return {
        "schema_version": "opendot.temporal.response.v1",
        "result_ref": {
            "artifact_id": "sha256:" + digest,
            "uri": "artifact://sha256/" + digest,
            "mime_type": "application/json",
            "size_bytes": 2048,
            "sha256": digest,
            "schema_version": "1.0.0",
            "producer": "opendot.temporal.reference.v1",
            "task_id": "c" * 24,
            "source_refs": [request_envelope["input_ref"]["artifact_id"]],
            "integrity_verified": False,
        },
    }


def test_workflow_imports_only_public_scheduling_dependencies():
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
    assert all(isinstance(node, ast.ImportFrom) and node.level == 0 for node in imports)
    actual = [(node.module, tuple((name.name, name.asname) for name in node.names)) for node in imports]
    original = [
        ("__future__", (("annotations", None),)),
        ("datetime", (("timedelta", None),)),
        ("typing", (("Any", None),)),
        ("temporalio", (("workflow", None),)),
        ("temporalio.common", (("RetryPolicy", None),)),
    ]
    added = [
        ("asyncio", (("CancelledError", None),)),
        ("copy", (("deepcopy", None),)),
        ("hashlib", (("sha256", None),)),
        ("json", (("dumps", None),)),
        ("re", (("fullmatch", None),)),
        ("temporalio.exceptions", (("ApplicationError", None),)),
    ]
    # The old public helper's imports remain exact and ordered. ADR 008 adds
    # only this deterministic stdlib/public-SDK allowlist, never an I/O owner.
    assert [item for item in actual if item in original] == original
    assert len(actual) == len(set(actual))
    assert set(actual) == set(original + added)
    assert all(isinstance(node, (ast.Expr, ast.ImportFrom, ast.Assign,
                                ast.AnnAssign, ast.FunctionDef, ast.AsyncFunctionDef,
                                ast.ClassDef)) for node in tree.body)
    assert all(isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
               for node in tree.body if isinstance(node, ast.Expr))
    assert [node.name for node in tree.body if isinstance(node, ast.ClassDef)] == ["DependentSumWorkflow"]
    helpers = {"execute_reference", "dag_workflow_id", "dag_effect_id", "_dag_check",
               "_dag_shape", "_dag_canonical", "_dag_hex", "_dag_label",
               "_dag_reference_fields", "_dag_validate_reference", "_dag_validate_step",
               "_dag_validate_inspection"}
    assert {node.name for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))} == helpers
    constants = {
        "DAG_PROFILE", "DAG_PLAN_SHA256", "DAG_HANDLER_SOURCE_SHA256", "DAG_REGISTRATION_SHA256",
        "DAG_SEED_SHA256", "DAG_INPUT_SHA256", "DAG_OUTPUT_SHA256", "DAG_WORKFLOW_NAME",
        "DAG_ACTIVITY_NAME", "DAG_INSPECT_ACTIVITY_NAME", "DAG_RESULT_PRODUCER",
        "_DAG_REF_FIELDS", "_DAG_STEP_FIELDS", "_DAG_INSPECT_FIELDS", "_DAG_UPDATE_FIELDS",
        "_DAG_TERMINAL", "_DAG_INSPECTION_REASONS",
    }
    assigned = set()
    def pure_constant(value):
        if isinstance(value, ast.Constant):
            return type(value.value) in {str, int, float, bool, type(None)}
        if isinstance(value, (ast.Tuple, ast.List, ast.Set)):
            return all(pure_constant(item) for item in value.elts)
        if isinstance(value, ast.Dict):
            return all(key is not None and pure_constant(key) and pure_constant(item)
                       for key, item in zip(value.keys, value.values))
        if isinstance(value, ast.Name):
            return value.id in assigned
        if isinstance(value, ast.BinOp):
            return isinstance(value.op, ast.BitOr) and pure_constant(value.left) and pure_constant(value.right)
        if isinstance(value, ast.Call):
            return (isinstance(value.func, ast.Name) and value.func.id == "frozenset"
                    and len(value.args) == 1 and not value.keywords and pure_constant(value.args[0]))
        return False
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            assert isinstance(node, ast.Assign) and len(node.targets) == 1
            assert isinstance(node.targets[0], ast.Name) and node.targets[0].id in constants
            assert node.targets[0].id not in assigned and pure_constant(node.value)
            assigned.add(node.targets[0].id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            assert not node.decorator_list
            assert all(pure_constant(value) for value in node.args.defaults)
            assert all(value is None or pure_constant(value) for value in node.args.kw_defaults)
    assert assigned == constants
    owner = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    assert [ast.unparse(value) for value in owner.decorator_list] == ["workflow.defn(name=DAG_WORKFLOW_NAME)"]
    assert not owner.bases and not owner.keywords
    allowed_decorators = {
        "dag_state": ["workflow.query(name='dag_state')"],
        "reconcile_result": ["workflow.update(name='reconcile_result')"],
        "validate_reconcile_result": ["reconcile_result.validator"],
        "run": ["workflow.run"],
    }
    for node in owner.body:
        if isinstance(node, ast.Expr):
            assert isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
        else:
            assert isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            assert [ast.unparse(value) for value in node.decorator_list] == allowed_decorators.get(node.name, [])
            assert all(pure_constant(value) for value in node.args.defaults)
            assert all(value is None or pure_constant(value) for value in node.args.kw_defaults)


def test_workflow_has_one_await_and_no_retry_io_or_override_path():
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    # Preserve every assertion on the original helper subtree; the new fixed
    # Workflow class is independently bounded below, never counted as v1.
    functions = [node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)
                 and node.name == "execute_reference"]
    assert len(functions) == 1
    function = functions[0]
    assert function.name == "execute_reference"
    assert not function.decorator_list
    assert not function.args.posonlyargs
    assert [arg.arg for arg in function.args.args] == ["request"]
    assert [arg.arg for arg in function.args.kwonlyargs] == ["task_queue"]
    assert function.args.vararg is None and function.args.kwarg is None
    assert not function.args.defaults and function.args.kw_defaults == [None]
    statements = [node for node in function.body if not (
        isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )]
    assert len(statements) == 1 and isinstance(statements[0], ast.Return)
    result = statements[0].value
    assert isinstance(result, ast.Await) and isinstance(result.value, ast.Call)
    call = result.value
    assert ast.unparse(call.func) == "workflow.execute_activity"
    assert [ast.unparse(node) for node in call.args] == [
        "'opendot.synthetic.reference.v1'", "request"
    ]
    assert [keyword.arg for keyword in call.keywords] == [
        "task_queue", "activity_id", "retry_policy",
        "start_to_close_timeout", "schedule_to_close_timeout",
    ]
    assert {keyword.arg: ast.unparse(keyword.value) for keyword in call.keywords} == {
        "task_queue": "task_queue",
        "activity_id": "'opendot-synthetic-reference-v1'",
        "retry_policy": "RetryPolicy(maximum_attempts=1)",
        "start_to_close_timeout": "timedelta(seconds=10)",
        "schedule_to_close_timeout": "timedelta(seconds=60)",
    }
    assert sorted(ast.unparse(node.func) for node in ast.walk(function)
                  if isinstance(node, ast.Call)) == [
        "RetryPolicy", "timedelta", "timedelta", "workflow.execute_activity"
    ]


def test_public_signature_is_narrow_and_async(bridge):
    signature = inspect.signature(bridge.execute_reference)
    assert inspect.iscoroutinefunction(bridge.execute_reference)
    assert list(signature.parameters) == ["request", "task_queue"]
    assert signature.parameters["request"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert signature.parameters["task_queue"].kind is inspect.Parameter.KEYWORD_ONLY
    assert all(parameter.default is inspect.Parameter.empty for parameter in signature.parameters.values())
    assert inspect.get_annotations(bridge.execute_reference, eval_str=True) == {
        "request": dict[str, Any], "task_queue": str, "return": dict[str, Any]
    }


def test_one_nonlocal_call_has_exact_fixed_options(
    bridge, monkeypatch, request_envelope, response_envelope
):
    before_request = copy.deepcopy(request_envelope)
    before_response = copy.deepcopy(response_envelope)
    schedule = AsyncMock(return_value=response_envelope)
    monkeypatch.setattr(bridge.workflow, "execute_activity", schedule)
    monkeypatch.setattr(bridge.workflow, "execute_local_activity", AsyncMock(
        side_effect=AssertionError("Local Activities are forbidden")))
    result = asyncio.run(bridge.execute_reference(request_envelope, task_queue="reviewed-queue"))
    schedule.assert_awaited_once_with(
        "opendot.synthetic.reference.v1",
        request_envelope,
        task_queue="reviewed-queue",
        activity_id="opendot-synthetic-reference-v1",
        retry_policy=bridge.RetryPolicy(maximum_attempts=1),
        start_to_close_timeout=timedelta(seconds=10),
        schedule_to_close_timeout=timedelta(seconds=60),
    )
    assert schedule.call_args.args[1] is request_envelope
    assert result is response_envelope
    assert request_envelope == before_request and response_envelope == before_response
    assert type(schedule.call_args.kwargs["retry_policy"].maximum_attempts) is int
    bridge.workflow.execute_local_activity.assert_not_called()


def test_real_sdk_public_api_reaches_one_nonlocal_fake_schedule(
    bridge, monkeypatch, request_envelope, response_envelope
):
    # This is a pinned, test-only interception point. Production uses no private
    # SDK APIs. No Workflow worker, native bridge, service or server is started.
    from temporalio.workflow import _activities

    class FakeRuntime:
        def __init__(self):
            self.schedules = []

        def workflow_start_activity(self, *args, **kwargs):
            self.schedules.append((args, kwargs))
            result = asyncio.get_running_loop().create_future()
            result.set_result(response_envelope)
            return result

        def workflow_start_local_activity(self, *args, **kwargs):
            raise AssertionError("Local Activities are forbidden")

    runtime = FakeRuntime()
    monkeypatch.setattr(_activities._Runtime, "current", staticmethod(lambda: runtime))
    result = asyncio.run(bridge.execute_reference(request_envelope, task_queue="reviewed-queue"))
    assert result is response_envelope
    assert len(runtime.schedules) == 1
    args, options = runtime.schedules[0]
    assert args == ("opendot.synthetic.reference.v1", request_envelope)
    assert args[1] is request_envelope
    assert options == {
        "task_queue": "reviewed-queue",
        "result_type": None,
        "schedule_to_close_timeout": timedelta(seconds=60),
        "schedule_to_start_timeout": None,
        "start_to_close_timeout": timedelta(seconds=10),
        "heartbeat_timeout": None,
        "retry_policy": bridge.RetryPolicy(maximum_attempts=1),
        "cancellation_type": bridge.workflow.ActivityCancellationType.TRY_CANCEL,
        "activity_id": "opendot-synthetic-reference-v1",
        "versioning_intent": None,
        "summary": None,
        "event_groups": None,
        "priority": _activities.temporalio.common.Priority.default,
    }


@pytest.mark.parametrize("failure_kind", ["application", "activity", "ordinary", "cancelled"])
def test_scheduling_failure_propagates_identically_without_resubmission(
    bridge, monkeypatch, request_envelope, failure_kind
):
    from temporalio.exceptions import ActivityError, ApplicationError, RetryState

    activity_failure = ActivityError(
        "synthetic", scheduled_event_id=1, started_event_id=2,
        identity="synthetic-worker", activity_type="opendot.synthetic.reference.v1",
        activity_id="opendot-synthetic-reference-v1", retry_state=RetryState.NON_RETRYABLE_FAILURE,
    )
    activity_failure.__cause__ = ApplicationError(
        "synthetic", type="TemporalInputRejected", non_retryable=True
    )
    failure = {
        "application": ApplicationError("synthetic", type="TemporalAdmissionRejected", non_retryable=True),
        "activity": activity_failure,
        "ordinary": RuntimeError("synthetic"),
        "cancelled": asyncio.CancelledError("synthetic"),
    }[failure_kind]
    original_cause = failure.__cause__
    schedule = AsyncMock(side_effect=failure)
    monkeypatch.setattr(bridge.workflow, "execute_activity", schedule)
    with pytest.raises(type(failure)) as raised:
        asyncio.run(bridge.execute_reference(request_envelope, task_queue="reviewed-queue"))
    assert raised.value is failure
    assert raised.value.__cause__ is original_cause
    assert schedule.call_count == schedule.await_count == 1


@pytest.mark.parametrize("override", [
    "activity", "activity_id", "retry_policy", "start_to_close_timeout",
    "schedule_to_close_timeout", "schedule_to_start_timeout", "heartbeat_timeout",
    "cancellation_type", "result_type", "args", "is_local", "runtime", "store",
    "permissions", "approval_token",
])
def test_no_scheduling_or_authority_override_kwargs(bridge, monkeypatch, request_envelope, override):
    schedule = AsyncMock()
    monkeypatch.setattr(bridge.workflow, "execute_activity", schedule)
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        bridge.execute_reference(request_envelope, task_queue="reviewed-queue", **{override: object()})
    schedule.assert_not_called()


def test_queue_is_required_keyword_only(bridge, monkeypatch, request_envelope):
    schedule = AsyncMock()
    monkeypatch.setattr(bridge.workflow, "execute_activity", schedule)
    with pytest.raises(TypeError):
        bridge.execute_reference(request_envelope)
    with pytest.raises(TypeError):
        bridge.execute_reference(request_envelope, "reviewed-queue")
    schedule.assert_not_called()


def test_off_workflow_call_uses_sdk_refusal_without_client_fallback(bridge, request_envelope):
    from temporalio.workflow import _NotInWorkflowEventLoopError

    with pytest.raises(_NotInWorkflowEventLoopError):
        asyncio.run(bridge.execute_reference(request_envelope, task_queue="reviewed-queue"))


def test_fixed_dag_uses_only_reviewed_public_workflow_surface():
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    owner = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                 and node.name == "DependentSumWorkflow")
    public = {"defn", "run", "update", "query", "info", "Info", "time", "now",
              "cancellation_reason", "all_handlers_finished", "wait_condition",
              "start_activity", "ActivityCancellationType", "HandlerUnfinishedPolicy"}
    attrs = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
             and isinstance(node.value, ast.Name) and node.value.id == "workflow"}
    assert attrs <= public | {"execute_activity"}  # execute_activity belongs to the unchanged v1 helper.
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                   and node.func.id in {"open", "eval", "exec", "__import__"}
                   for node in ast.walk(tree))
    calls = [node for node in ast.walk(owner) if isinstance(node, ast.Call)]
    assert any(ast.unparse(node.func) == "workflow.start_activity" for node in calls)
    assert any(ast.unparse(node.func) == "workflow.wait_condition" for node in calls)
    assert any(ast.unparse(node.func) == "workflow.cancellation_reason" for node in calls)
    assert any(ast.unparse(node.func) == "workflow.all_handlers_finished" for node in calls)
    assert not any(isinstance(node, (ast.AsyncFor, ast.For)) for node in ast.walk(owner)
                   if any(isinstance(call, ast.Call) and ast.unparse(call.func) == "workflow.start_activity"
                          for call in ast.walk(node)))
    for call in calls:
        if ast.unparse(call.func) == "workflow.start_activity":
            options = {keyword.arg: ast.unparse(keyword.value) for keyword in call.keywords}
            assert options["retry_policy"] == "RetryPolicy(maximum_attempts=1)"
            assert options["start_to_close_timeout"] == "timedelta(seconds=10)"
            assert options["schedule_to_close_timeout"] == "timedelta(seconds=60)"
            assert options["cancellation_type"] == "workflow.ActivityCancellationType.TRY_CANCEL"
            assert set(options) == {"activity_id", "task_queue", "retry_policy",
                                    "start_to_close_timeout", "schedule_to_close_timeout", "cancellation_type"}
