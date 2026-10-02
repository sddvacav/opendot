"""SDK-only finite synthetic contracts. No server, worker service or replay proof."""
from __future__ import annotations

import asyncio
import copy
from dataclasses import FrozenInstanceError, asdict, fields, replace
from datetime import timedelta
import json
import math
from types import SimpleNamespace
from typing import Any, get_type_hints

import pytest

pytest.importorskip("temporalio", reason="explicit temporal extra required")
from temporalio import activity
from temporalio.common import RetryPolicy
from temporalio.converter import DataConverter
from temporalio.exceptions import ApplicationError
from temporalio.testing import ActivityEnvironment

from opendot_engineering.adapters import temporal_activity as m
from opendot_engineering.core.artifacts import ArtifactStore
from opendot_engineering.core.contracts import ArtifactRef
from opendot_engineering.tool_runtime import ToolRuntime


class IntSubclass(int):
    pass


class ControlDenied(RuntimeError):
    pass


@pytest.fixture
def rig(tmp_path, monkeypatch):
    def build(*, handler=None, validator=None, grants=None, runtime_options=None, raw=None):
        counts = {"get": [], "put": [], "execute": [], "handler": []}
        runtime = ToolRuntime(**(runtime_options or {}))
        def counted(payload):
            counts["handler"].append(payload)
            return (handler or m.bounded_sum)(payload)
        spec = m.SYNTHETIC_SPEC if validator is None else replace(m.SYNTHETIC_SPEC, semantic_validator=validator)
        runtime.register(spec, counted)
        store = ArtifactStore(tmp_path / str(len(list(tmp_path.iterdir()))))
        raw = raw if raw is not None else b'{"left": 2, "right": 3, "return_null": false}'
        ref = store.put_bytes(raw, mime_type="application/json", producer="synthetic", task_id="input")
        request = {"schema_version": "opendot.temporal.request.v1",
                   "input_ref": {**asdict(ref), "source_refs": []}}
        original_get, original_put, original_execute = store.get_bytes, store.put_json, runtime.execute
        def get(ref):
            counts["get"].append(ref)
            return original_get(ref)
        def put(value, **kwargs):
            counts["put"].append((value, kwargs))
            return original_put(value, **kwargs)
        def execute(*args, **kwargs):
            counts["execute"].append((args, kwargs))
            return original_execute(*args, **kwargs)
        monkeypatch.setattr(store, "get_bytes", get)
        monkeypatch.setattr(store, "put_json", put)
        monkeypatch.setattr(runtime, "execute", execute)
        adapter = m.ReferenceActivity(
            runtime=runtime, store=store, tool_id=m.TOOL_ID,
            expected_registration_sha256=m.REGISTRATION_SHA256,
            granted_permissions=frozenset({"synthetic:read"}) if grants is None else grants,
            expected_namespace="synthetic", expected_task_queue="synthetic",
        )
        env = ActivityEnvironment()
        env.info = replace(ActivityEnvironment.default_info(),
                           activity_type=m.ACTIVITY_NAME, namespace="synthetic", task_queue="synthetic",
                           retry_policy=RetryPolicy(maximum_attempts=1),
                           start_to_close_timeout=m.START_TO_CLOSE,
                           schedule_to_close_timeout=m.SCHEDULE_TO_CLOSE)
        return SimpleNamespace(**locals())
    return build


def rejected(rig, category="TemporalAdmissionRejected"):
    with pytest.raises(ApplicationError) as error:
        rig.env.run(rig.adapter.run, rig.request)
    assert error.value.type == category and error.value.non_retryable is True
    assert set(error.value.details[0]) == {"phase", "code"}
    return error.value


def result(rig):
    response = rig.env.run(rig.adapter.run, rig.request)
    row = response["result_ref"]
    canonical = ArtifactRef(**{**row, "source_refs": tuple(row["source_refs"]), "integrity_verified": False})
    canonical.validate()
    raw = rig.original_get(canonical)
    assert len(raw) == canonical.size_bytes <= 16384
    return response, json.loads(raw)


@pytest.mark.parametrize("changes", [
    *({"attempt": value} for value in (0, 2, -1, True, 1.0, IntSubclass(1), None)),
    *({"retry_policy": RetryPolicy(maximum_attempts=value)}
      for value in (0, 2, -1, True, 1.0, IntSubclass(1), None)),
    {"retry_policy": None}, {"retry_policy": SimpleNamespace(maximum_attempts=1)},
    *({"is_local": value} for value in (True, 0, None, "false")),
    *({key: value} for key in ("start_to_close_timeout", "schedule_to_close_timeout")
      for value in (None, 10, timedelta(0), timedelta(seconds=-1), timedelta(seconds=9))),
    {"activity_type": "wrong"}, {"namespace": "wrong"}, {"task_queue": "wrong"},
    *({key: value} for key in ("workflow_id", "workflow_run_id")
      for value in (None, "", 1, "x" * 257)),
])
def test_info_refusals_before_io(rig, changes):
    r = rig()
    r.env.info = replace(r.env.info, **changes)
    rejected(r)
    assert all(not values for values in r.counts.values())


@pytest.mark.parametrize("missing", ["attempt", "retry_policy", "is_local", "start_to_close_timeout",
    "schedule_to_close_timeout", "namespace", "task_queue", "activity_type", "workflow_id", "workflow_run_id"])
def test_absent_info_fields_refuse(rig, missing):
    r = rig()
    object.__delattr__(r.env.info, missing)  # Only the SDK test record is mutated.
    rejected(r)
    assert all(not values for values in r.counts.values())


def test_absent_policy_maximum_refuses(rig):
    r = rig()
    # Deleting the instance value exposes SDK class default zero, still refused.
    object.__delattr__(r.env.info.retry_policy, "maximum_attempts")
    rejected(r)
    assert all(not values for values in r.counts.values())


def test_direct_call_outside_activity_has_no_io(rig):
    r = rig()
    with pytest.raises(ApplicationError) as error:
        r.adapter.run(r.request)
    assert error.value.type == "TemporalAdmissionRejected"
    assert all(not values for values in r.counts.values())


@pytest.mark.parametrize("field,value", [
    ("sha256", "A" * 64), ("sha256", "a" * 63), ("sha256", "/tmp/input"),
    ("artifact_id", "sha256:" + "0" * 64), ("uri", "https://example.com/input"),
    ("uri", "artifact://sha256/" + "0" * 64 + "/x"),
    ("mime_type", "application/octet-stream"), ("schema_version", "2"),
    ("size_bytes", 0), ("size_bytes", 257), ("size_bytes", True),
    ("size_bytes", 42.0), ("size_bytes", IntSubclass(42)),
    ("producer", ""), ("producer", "x" * 81), ("producer", "../root"),
    ("task_id", "bad space"), ("task_id", "日本"),
    ("source_refs", ()), ("source_refs", ["sha256:" + "0" * 64]),
    ("integrity_verified", 1),
])
def test_malformed_reference_refuses_before_io(rig, field, value):
    r = rig()
    r.request["input_ref"][field] = value
    rejected(r)
    assert all(not values for values in r.counts.values())


@pytest.mark.parametrize("change", [
    lambda row: row.update(schema_version="wrong"),
    lambda row: row.update(granted_permissions=["synthetic:read"]),
    lambda row: row.update(approval_token="not-accepted"),
    lambda row: row.update(tool_id=m.TOOL_ID),
    lambda row: row.update(retry_policy={"maximum_attempts": 1}),
    lambda row: row["input_ref"].update(root="/tmp"),
    lambda row: row["input_ref"].pop("producer"),
    lambda row: row.pop("input_ref"),
])
def test_envelope_authority_fields_refuse(rig, change):
    r = rig(); change(r.request)
    rejected(r)
    assert all(not values for values in r.counts.values())


@pytest.mark.parametrize("wire_request", [None, [], {}, "x" * 5000])
def test_non_record_request_refuses(rig, wire_request):
    r = rig(); r.request = wire_request
    rejected(r)
    assert all(not values for values in r.counts.values())


def test_registration_checked_again_before_read(rig, monkeypatch):
    r = rig()
    monkeypatch.setattr(r.runtime, "registration_signature", lambda _: None)
    rejected(r)
    assert all(not values for values in r.counts.values())


@pytest.mark.parametrize("field,value", [
    ("tool_id", "another"), ("expected_registration_sha256", "0" * 64),
    ("granted_permissions", {"write"}), ("granted_permissions", ["synthetic:read"]),
    ("expected_namespace", ""), ("expected_task_queue", "x" * 256),
])
def test_invalid_worker_configuration(rig, field, value):
    r = rig()
    kwargs = {name: getattr(r.adapter, name) for name in (
        "runtime", "store", "tool_id", "expected_registration_sha256", "granted_permissions",
        "expected_namespace", "expected_task_queue")}
    kwargs[field] = value
    with pytest.raises(ValueError):
        m.ReferenceActivity(**kwargs)
    assert all(not values for values in r.counts.values())


def test_signature_pin_not_handler_authentication(rig):
    first = rig(); second = rig(handler=lambda _: 100)
    assert first.runtime.registration_signature(m.TOOL_ID) == second.runtime.registration_signature(m.TOOL_ID)
    assert result(first)[1]["output"] == 5
    assert result(second)[1]["output"] == 100


def test_detached_grants_and_frozen_binding(rig):
    grants = {"synthetic:read"}; r = rig(grants=grants); grants.clear()
    assert r.adapter.granted_permissions == frozenset({"synthetic:read"})
    with pytest.raises(FrozenInstanceError): r.adapter.granted_permissions = frozenset()
    assert result(r)[1]["receipt_report"]["status"] == "COMPLETED"


@pytest.mark.parametrize("raw", [
    b'{"left":1,"left":2,"right":3,"return_null":false}',
    b'{"left":NaN,"right":3,"return_null":false}',
    b'{"left":Infinity,"right":3,"return_null":false}',
    b'{"left":1e999,"right":3,"return_null":false}',
    b'{"left":1e0,"right":3,"return_null":false}',
    b'{"left":true,"right":3,"return_null":false}',
    b'{"left":1000001,"right":3,"return_null":false}',
    b'{"left":-1000001,"right":3,"return_null":false}',
    b'{"left":{},"right":3,"return_null":false}',
    b'{"left":1,"right":3,"return_null":0}', b'[]', b'null', b'{}', b'\xff', b'{',
])
def test_strict_input_rejected_after_one_verified_read(rig, raw):
    r = rig(raw=raw)
    rejected(r, "TemporalInputRejected")
    assert len(r.counts["get"]) == 1
    assert not r.counts["execute"] and not r.counts["put"] and not r.counts["handler"]


@pytest.mark.parametrize("fault", ["missing", "corrupt", "size", "oversized"])
def test_canonical_input_failures_no_dispatch(rig, monkeypatch, fault):
    r = rig()
    if fault == "size": r.request["input_ref"]["size_bytes"] -= 1
    elif fault == "oversized":
        big = r.store.put_bytes(b" " * 257, mime_type="application/json", producer="test", task_id="test")
        r.request["input_ref"] = {**asdict(big), "source_refs": [], "size_bytes": 256}
    else:
        def broken(_):
            r.counts["get"].append(_)
            if fault == "missing": raise FileNotFoundError("private path")
            from opendot_engineering.core.artifacts import ArtifactIntegrityError
            raise ArtifactIntegrityError("private digest")
        monkeypatch.setattr(r.store, "get_bytes", broken)
    error = rejected(r, "TemporalInputRejected")
    assert "private" not in str(error)
    assert len(r.counts["get"]) == 1 and not r.counts["execute"] and not r.counts["put"]


@pytest.mark.parametrize("null", [False, True])
def test_round_trip_preserves_full_receipt_and_exact_call(rig, null):
    r = rig(raw=json.dumps({"left": 2, "right": 3, "return_null": null}).encode())
    response, document = result(r)
    assert set(response) == {"schema_version", "result_ref"}
    assert response["schema_version"] == "opendot.temporal.response.v1"
    assert set(document) == {"schema_version", "profile", "input_ref", "output", "receipt_report",
        "observation_provenance", "scientific_validity", "device_control_authority", "independent_review", "owner_integration"}
    assert document["output"] == (None if null else 5)
    receipt = document["receipt_report"]
    assert set(receipt) == {f.name for f in fields(m.ToolCallReceipt)}
    assert receipt["status"] == "COMPLETED" and receipt["semantic_valid"] is True
    assert receipt["attempts"] == 1 and receipt["execution_liveness"] == {}
    assert len(receipt["execution_observation"]) == 8
    assert document["observation_provenance"] == "serialized_runtime_report_not_live_proof"
    assert document["scientific_validity"] is document["device_control_authority"] is False
    assert document["independent_review"] == document["owner_integration"] == "NOT_EVALUATED"
    assert type(r.counts["get"][0]) is ArtifactRef and r.counts["get"][0].integrity_verified is False
    assert document["input_ref"]["integrity_verified"] is True
    assert r.ref.sha256 != receipt["input_hash"]  # Stored whitespace is not runtime canonical JSON.
    assert len(r.counts["execute"]) == len(r.counts["handler"]) == len(r.counts["put"]) == 1
    args, kwargs = r.counts["execute"][0]
    assert args == (m.TOOL_ID, {"left": 2, "right": 3, "return_null": null})
    assert kwargs == {"granted_permissions": frozenset({"synthetic:read"}),
        "approval_token": None, "backoff_base_s": 0.0, "attempt_limit": 1}
    assert response["result_ref"]["producer"] == m.RESULT_PRODUCER
    assert response["result_ref"]["source_refs"] == [r.ref.artifact_id]
    # Real SDK JSON payload conversion remains separate from tool/CAS success.
    async def convert():
        encoded = await DataConverter.default.encode([response])
        return await DataConverter.default.decode(encoded, [get_type_hints(m.ReferenceActivity.run)["return"]])
    assert asyncio.run(convert()) == [response]


def test_permission_block_is_delivered_without_handler(rig):
    r = rig(grants=frozenset()); _, doc = result(r)
    assert doc["receipt_report"]["status"] == "BLOCKED"
    assert doc["receipt_report"]["error_type"] == "PermissionDenied"
    assert doc["receipt_report"]["attempts"] == 1 and doc["receipt_report"]["semantic_valid"] is False
    assert len(r.counts["execute"]) == 1 and not r.counts["handler"]


def fail(_):
    raise ValueError("synthetic failure")


def test_failure_and_breaker_remain_tool_outcomes(rig):
    r = rig(handler=fail, runtime_options={"failure_threshold": 1})
    _, first = result(r); _, second = result(r)
    assert first["receipt_report"]["status"] == "FAILED"
    assert first["receipt_report"]["error_type"] == "ValueError"
    assert second["receipt_report"]["status"] == "BLOCKED"
    assert second["receipt_report"]["error_type"] == "CircuitOpen"
    assert len(r.counts["execute"]) == 2 and len(r.counts["handler"]) == 1


def test_semantic_failure_not_recovered_or_revalidated(rig):
    validations = []
    r = rig(handler=lambda _: 5, validator=lambda value: validations.append(value) or False)
    _, doc = result(r)
    assert doc["output"] is None and doc["receipt_report"]["status"] == "FAILED"
    assert doc["receipt_report"]["semantic_valid"] is False
    assert validations == [5] and len(r.counts["handler"]) == 1


@pytest.mark.parametrize("context", [False, 0, "", {}, [], ()])
def test_guard_false_like_context_denies_after_input_read(rig, context):
    r = rig(runtime_options={"guarded_embedding": True,
        "current_context_resolver": lambda: context, "control_error": ControlDenied})
    with pytest.raises(ControlDenied): r.env.run(r.adapter.run, r.request)
    assert len(r.counts["get"]) == len(r.counts["execute"]) == 1
    assert not r.counts["handler"] and not r.counts["put"]


@pytest.mark.parametrize("dispatch", [False, True])
def test_guard_exception_identity_preserved(rig, dispatch):
    marker = ControlDenied("guard denied"); checks = []
    def resolver():
        checks.append(1)
        if not dispatch or len(checks) == 2: raise marker
        return None
    r = rig(runtime_options={"guarded_embedding": True,
        "current_context_resolver": resolver, "control_error": ControlDenied})
    with pytest.raises(ControlDenied) as caught: r.env.run(r.adapter.run, r.request)
    assert caught.value is marker
    assert len(checks) == (2 if dispatch else 1)
    assert len(r.counts["get"]) == len(r.counts["execute"]) == 1
    assert not r.counts["handler"] and not r.counts["put"]


def test_resolver_ordinary_exception_fail_closed(rig):
    r = rig(runtime_options={"guarded_embedding": True,
        "current_context_resolver": lambda: 1 / 0, "control_error": ControlDenied})
    with pytest.raises(ControlDenied): r.env.run(r.adapter.run, r.request)
    assert len(r.counts["get"]) == len(r.counts["execute"]) == 1
    assert not r.counts["handler"] and not r.counts["put"]


@pytest.mark.parametrize("output", [object(), float("nan"), float("inf"), True, "5", [5], 2_000_001])
def test_unrepresentable_output_has_no_retry_or_put(rig, output):
    r = rig(handler=lambda _: output, validator=lambda _: True)
    rejected(r, "TemporalResultEncodingFailed")
    assert len(r.counts["execute"]) == len(r.counts["handler"]) == 1
    assert not r.counts["put"]


@pytest.mark.parametrize("changes", [
    {"latency_s": math.nan}, {"attempts": True}, {"attempts": 2},
    {"semantic_valid": 1}, {"error_type": "x" * 257}, {"output_hash": "x" * 64},
    {"execution_liveness": {"new_unknown_owner_key": True}},
    {"execution_liveness": {"timed_out": 1}},
    {"execution_liveness": {"cleanup_error_type": {"nested": "bad"}}},
])
def test_unrepresentable_receipt_no_lossy_serialization(rig, monkeypatch, changes):
    r = rig(); original = r.runtime.execute
    def altered(*args, **kwargs):
        output, receipt = original(*args, **kwargs)
        return output, replace(receipt, **changes)
    monkeypatch.setattr(r.runtime, "execute", altered)
    rejected(r, "TemporalResultEncodingFailed")
    assert len(r.counts["execute"]) == len(r.counts["handler"]) == 1 and not r.counts["put"]


def test_reported_liveness_not_strengthened(rig, monkeypatch):
    r = rig(); original = r.runtime.execute
    uncertainty = {"execution_kind": "in_process", "timed_out": True,
        "termination_observed": False, "termination_scope": "in_process_handler",
        "descendant_termination_observed": False, "reconciliation_required": True}
    def altered(*args, **kwargs):
        _, receipt = original(*args, **kwargs)
        return None, replace(receipt, status="FAILED", semantic_valid=False,
            output_hash=None, error_type="TimeoutError", execution_observation=None,
            execution_liveness=uncertainty)
    monkeypatch.setattr(r.runtime, "execute", altered)
    _, doc = result(r)
    assert doc["receipt_report"]["execution_liveness"] == uncertainty
    assert doc["receipt_report"]["execution_observation"] is None
    assert len(r.counts["execute"]) == 1


@pytest.mark.parametrize("stage", ["json", "object", "metadata", "response"])
def test_postdispatch_publication_failure_never_repeats(rig, monkeypatch, stage):
    r = rig()
    objects_before = set(r.store.objects.rglob("*"))
    if stage == "json":
        def broken(*args, **kwargs):
            r.counts["put"].append((args, kwargs)); raise TypeError("serialization")
        monkeypatch.setattr(r.store, "put_json", broken)
    elif stage in {"object", "metadata"}:
        original = r.store._atomic_write
        def broken(path, data, **kwargs):
            if (stage == "metadata") == (path.parent == r.store.meta):
                raise OSError("synthetic storage failure")
            return original(path, data, **kwargs)
        monkeypatch.setattr(r.store, "_atomic_write", broken)
    else:
        original = r.store.put_json
        def broken(*args, **kwargs):
            return replace(original(*args, **kwargs), size_bytes=True)
        monkeypatch.setattr(r.store, "put_json", broken)
    rejected(r, "TemporalResultEncodingFailed" if stage == "response" else "TemporalResultStoreFailed")
    assert len(r.counts["execute"]) == len(r.counts["handler"]) == len(r.counts["put"]) == 1
    if stage in {"metadata", "response"}:
        assert set(r.store.objects.rglob("*")) > objects_before


def test_runtime_escape_is_unchanged_and_not_published(rig, monkeypatch):
    r = rig(); original = r.runtime.execute; marker = RuntimeError("delivery unknown")
    def lose_result(*args, **kwargs):
        original(*args, **kwargs); raise marker
    monkeypatch.setattr(r.runtime, "execute", lose_result)
    with pytest.raises(RuntimeError) as error: r.env.run(r.adapter.run, r.request)
    assert error.value is marker and len(r.counts["execute"]) == len(r.counts["handler"]) == 1
    assert not r.counts["put"]


def test_separate_submission_not_deduplicated(rig):
    r = rig(); first = result(r)[1]; second = result(r)[1]
    assert len(r.counts["execute"]) == len(r.counts["handler"]) == 2
    assert first["receipt_report"]["call_id"] != second["receipt_report"]["call_id"]


@pytest.mark.parametrize("field,value", [
    ("size_bytes", {"nested": 42}), ("sha256", ["a" * 64]),
    ("producer", {"arbitrary": "label"}), ("integrity_verified", [True]),
    ("source_refs", [{"permission": "synthetic:read"}]),
])
def test_any_annotations_still_refuse_decoded_nested_wire_values(rig, field, value):
    r = rig(); r.request["input_ref"][field] = value
    async def convert():
        encoded = await DataConverter.default.encode([r.request])
        return await DataConverter.default.decode(encoded, [get_type_hints(m.ReferenceActivity.run)["request"]])
    r.request = asyncio.run(convert())[0]
    rejected(r)
    assert all(not values for values in r.counts.values())


def test_actual_entrypoint_sdk_request_decode_and_execution(rig):
    r = rig()
    async def convert():
        encoded = await DataConverter.default.encode([r.request])
        return await DataConverter.default.decode(encoded, [get_type_hints(m.ReferenceActivity.run)["request"]])
    r.request = asyncio.run(convert())[0]
    assert result(r)[1]["output"] == 5


def test_original_object_annotation_regression_is_explicit(rig):
    r = rig()
    async def incompatible():
        encoded = await DataConverter.default.encode([r.request])
        return await DataConverter.default.decode(encoded, [dict[str, object]])
    with pytest.raises(TypeError):
        asyncio.run(incompatible())
    assert all(not values for values in r.counts.values())


@pytest.mark.parametrize("fault", ["version", "public_info"])
def test_bootstrap_sdk_mismatch_has_no_fallback(rig, monkeypatch, fault):
    r = rig()
    kwargs = {name: getattr(r.adapter, name) for name in (
        "runtime", "store", "tool_id", "expected_registration_sha256", "granted_permissions",
        "expected_namespace", "expected_task_queue")}
    if fault == "version": monkeypatch.setattr(m, "version", lambda _: "1.33.0")
    else: monkeypatch.setattr(m.activity, "info", None)
    with pytest.raises(ValueError): m.ReferenceActivity(**kwargs)
    assert all(not values for values in r.counts.values())


@pytest.mark.parametrize("fault", ["missing", "corrupt"])
def test_real_local_cas_integrity_failure(rig, fault):
    r = rig()
    path = r.store.objects / r.ref.sha256[:2] / r.ref.sha256[2:]
    if fault == "missing": path.unlink()
    else:
        path.chmod(0o600)
        path.write_bytes(b"corrupt")
    rejected(r, "TemporalInputRejected")
    assert len(r.counts["get"]) == 1
    assert not r.counts["execute"] and not r.counts["handler"] and not r.counts["put"]


def test_sdk_result_conversion_failure_preserves_completed_local_result(rig, monkeypatch):
    r = rig(); response, document = result(r)
    marker = TypeError("synthetic SDK conversion failure")
    def broken(_): raise marker
    converter = DataConverter.default
    monkeypatch.setattr(converter.payload_converter, "to_payloads", broken)
    with pytest.raises(TypeError) as caught:
        asyncio.run(converter.encode([response]))
    assert caught.value is marker
    assert len(r.counts["execute"]) == len(r.counts["handler"]) == len(r.counts["put"]) == 1
    assert json.loads(r.original_get(response["result_ref"]["sha256"])) == document


def test_success_validator_not_called_again_during_publication(rig):
    validations = []
    r = rig(validator=lambda value: validations.append(value) or True)
    assert result(r)[1]["receipt_report"]["status"] == "COMPLETED"
    assert validations == [5]


@pytest.mark.parametrize("changes", [
    {"execution_id": "x" * 257}, {"worker_pid": True},
    {"registration_sha256": "x" * 64}, {"read_only_declared": 1},
])
def test_malformed_observation_not_coerced_or_reconstituted(rig, monkeypatch, changes):
    r = rig(); original = r.runtime.execute
    def altered(*args, **kwargs):
        output, receipt = original(*args, **kwargs)
        return output, replace(receipt, execution_observation=replace(receipt.execution_observation, **changes))
    monkeypatch.setattr(r.runtime, "execute", altered)
    rejected(r, "TemporalResultEncodingFailed")
    assert len(r.counts["execute"]) == len(r.counts["handler"]) == 1 and not r.counts["put"]
