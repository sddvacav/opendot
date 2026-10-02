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
    assert [(node.module, [(name.name, name.asname) for name in node.names]) for node in imports] == [
        ("__future__", [("annotations", None)]),
        ("datetime", [("timedelta", None)]),
        ("typing", [("Any", None)]),
        ("temporalio", [("workflow", None)]),
        ("temporalio.common", [("RetryPolicy", None)]),
    ]
    # Importing this module performs no bootstrap, registration or I/O calls.
    assert all(isinstance(node, (ast.Expr, ast.ImportFrom, ast.AsyncFunctionDef)) for node in tree.body)
    assert all(isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
               for node in tree.body if isinstance(node, ast.Expr))


def test_workflow_has_one_await_and_no_retry_io_or_override_path():
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    functions = [node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)]
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
