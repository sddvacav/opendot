"""Explicit optional, synthetic-only reference transport (ADR 004).

This is not a runtime, store, authorization service, or recovery protocol.
Only SDK-only qualification is established; a real-server gate remains open.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, fields, replace
from datetime import timedelta
from importlib.metadata import version
from typing import Any

from temporalio import activity
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

from ..core.artifacts import ArtifactStore
from ..core.contracts import ArtifactRef
from ..tool_runtime import (
    BreakerState, ToolCallReceipt, ToolRisk, ToolRuntime, ToolSpec,
    _ObservedToolExecution,  # Type identity only; never reconstruct a live proof.
)
from .source_audit import _decode

ACTIVITY_NAME = "opendot.synthetic.reference.v1"
PROFILE = "synthetic.bounded_sum.v1"
TOOL_ID = "synthetic.bounded_sum"
REGISTRATION_SHA256 = "5f2b1e81954530f31c7d2c83b9c582883b8391190ebe13b69b8bf91f044cb0c3"
START_TO_CLOSE = timedelta(seconds=10)
SCHEDULE_TO_CLOSE = timedelta(seconds=60)
RESULT_PRODUCER = "opendot.temporal.reference.v1"
_REF_FIELDS = frozenset({
    "artifact_id", "uri", "mime_type", "size_bytes", "sha256", "schema_version",
    "producer", "task_id", "source_refs", "integrity_verified",
})
_RECEIPT_FIELDS = (
    "call_id", "tool_id", "tool_version", "status", "attempts", "latency_s",
    "input_hash", "output_hash", "semantic_valid", "error_type", "breaker_state",
    "execution_observation", "execution_liveness",
)
_OBSERVATION_FIELDS = (
    "execution_id", "execution_kind", "worker_pid", "dispatcher_pid",
    "input_sha256", "review_target_sha256", "read_only_declared", "registration_sha256",
)
_LIVENESS_BOOLEAN_KEYS = frozenset({
    "timed_out", "dispatch_started", "termination_observed",
    "descendant_termination_observed", "reconciliation_required",
    "submission_entered", "return_handle_observed",
})
_LIVENESS_TEXT_KEYS = frozenset({
    "execution_id", "execution_kind", "termination_scope", "observation_error_type",
    "cleanup_error_type",
})


def _require(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError(code)


def _text(value: object, limit: int = 256) -> bool:
    return type(value) is str and 0 < len(value) <= limit


def _label(value: object, limit: int = 80) -> bool:
    return _text(value, limit) and re.fullmatch(r"[A-Za-z0-9._-]+", value) is not None


def _hex(value: object, length: int = 64) -> bool:
    return type(value) is str and re.fullmatch(r"[0-9a-f]{%d}" % length, value) is not None


def _shape(value: object, keys: frozenset[str]) -> None:
    _require(type(value) is dict and len(value) == len(keys), "INVALID_FIELDS")
    _require(all(type(key) is str for key in value) and value.keys() == keys, "INVALID_FIELDS")


def _bounded_json(value: object, limit: int) -> None:
    # All callers first reduce to known finite plain fields. Never default=str.
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    _require(0 < len(encoded) <= limit, "JSON_SIZE")


def _validate_payload(payload: object) -> None:
    _shape(payload, frozenset({"left", "right", "return_null"}))
    for key in ("left", "right"):
        _require(type(payload[key]) is int and -1_000_000 <= payload[key] <= 1_000_000,
                 "INPUT_INTEGER")
    _require(type(payload["return_null"]) is bool, "INPUT_BOOLEAN")


def bounded_sum(payload: dict[str, object]) -> int | None:
    """The reviewed finite pure handler; caller-owned bootstrap registers it."""
    _validate_payload(payload)
    return None if payload["return_null"] else payload["left"] + payload["right"]


def bounded_sum_valid(output: object) -> bool:
    """Finite profile validation, not scientific acceptance."""
    return output is None or (type(output) is int and -2_000_000 <= output <= 2_000_000)


SYNTHETIC_SPEC = ToolSpec(
    tool_id=TOOL_ID, version="1", input_schema="synthetic.bounded_sum.input/v1",
    output_schema="synthetic.bounded_sum.output/v1", risk=ToolRisk.READ_ONLY,
    timeout_s=1.0, max_retries=0, idempotent=True,
    permissions=frozenset({"synthetic:read"}), semantic_validator=bounded_sum_valid,
)


def _check_sdk() -> None:
    _require(version("temporalio") == "1.34.0", "SDK_VERSION")
    required = {
        "attempt", "is_local", "retry_policy", "start_to_close_timeout",
        "schedule_to_close_timeout", "activity_type", "namespace", "task_queue",
        "workflow_id", "workflow_run_id",
    }
    _require(required <= {field.name for field in fields(activity.Info)}, "SDK_INFO_API")
    _require("maximum_attempts" in {field.name for field in fields(RetryPolicy)}, "SDK_POLICY_API")
    _require(callable(activity.info) and callable(activity.defn), "SDK_ACTIVITY_API")


def _reference_record(ref: ArtifactRef) -> dict[str, object]:
    _require(type(ref) is ArtifactRef, "REFERENCE_IDENTITY")
    _require(type(ref.source_refs) is tuple, "REFERENCE_SOURCES")
    return {
        "artifact_id": ref.artifact_id, "uri": ref.uri, "mime_type": ref.mime_type,
        "size_bytes": ref.size_bytes, "sha256": ref.sha256,
        "schema_version": ref.schema_version, "producer": ref.producer,
        "task_id": ref.task_id, "source_refs": list(ref.source_refs),
        "integrity_verified": ref.integrity_verified,
    }


def _reference(row: object, *, result_call_id: str | None = None,
               input_artifact_id: str | None = None) -> ArtifactRef:
    _shape(row, _REF_FIELDS)
    digest = row["sha256"]
    _require(_hex(digest), "REFERENCE_DIGEST")
    _require(type(row["artifact_id"]) is str and row["artifact_id"] == "sha256:" + digest,
             "REFERENCE_ID")
    _require(type(row["uri"]) is str and row["uri"] == "artifact://sha256/" + digest,
             "REFERENCE_URI")
    _require(type(row["mime_type"]) is str and row["mime_type"] == "application/json",
             "REFERENCE_MIME")
    _require(type(row["schema_version"]) is str and row["schema_version"] == "1.0.0",
             "REFERENCE_SCHEMA")
    limit = 256 if result_call_id is None else 16384
    _require(type(row["size_bytes"]) is int and 1 <= row["size_bytes"] <= limit,
             "REFERENCE_SIZE")
    _require(type(row["integrity_verified"]) is bool, "REFERENCE_INTEGRITY_CLAIM")
    _require(_label(row["producer"]) and _label(row["task_id"]), "REFERENCE_LABEL")
    _require(type(row["source_refs"]) is list, "REFERENCE_SOURCES")
    if result_call_id is None:
        _require(len(row["source_refs"]) == 0, "REFERENCE_SOURCES")
    else:
        _require(row["producer"] == RESULT_PRODUCER and row["task_id"] == result_call_id
                 and _hex(result_call_id, 24), "RESULT_REFERENCE_LABEL")
        _require(len(row["source_refs"]) == 1 and type(row["source_refs"][0]) is str
                 and row["source_refs"][0] == input_artifact_id, "RESULT_REFERENCE_SOURCES")
    ref = ArtifactRef(
        artifact_id=row["artifact_id"], uri=row["uri"], mime_type=row["mime_type"],
        size_bytes=row["size_bytes"], sha256=digest, schema_version=row["schema_version"],
        producer=row["producer"], task_id=row["task_id"],
        source_refs=tuple(row["source_refs"]), integrity_verified=False,
    )
    ref.validate()
    return ref


def _receipt_report(receipt: ToolCallReceipt) -> dict[str, object]:
    _require(type(receipt) is ToolCallReceipt, "RECEIPT_IDENTITY")
    _require(tuple(field.name for field in fields(receipt)) == _RECEIPT_FIELDS, "RECEIPT_FIELDS")
    _require(vars(receipt).keys() == set(_RECEIPT_FIELDS), "RECEIPT_FIELDS")
    _require(_hex(receipt.call_id, 24) and receipt.tool_id == TOOL_ID
             and type(receipt.tool_id) is str and receipt.tool_version == "1"
             and type(receipt.tool_version) is str, "RECEIPT_ID")
    _require(type(receipt.status) is str and receipt.status in {"COMPLETED", "FAILED", "BLOCKED"},
             "RECEIPT_STATUS")
    _require(type(receipt.attempts) is int and receipt.attempts == 1, "RECEIPT_ATTEMPTS")
    _require(type(receipt.latency_s) in {int, float} and math.isfinite(receipt.latency_s)
             and receipt.latency_s >= 0, "RECEIPT_LATENCY")
    _require(_hex(receipt.input_hash) and (receipt.output_hash is None or _hex(receipt.output_hash)),
             "RECEIPT_HASH")
    _require(type(receipt.semantic_valid) is bool, "RECEIPT_SEMANTICS")
    _require(receipt.error_type is None or _text(receipt.error_type), "RECEIPT_ERROR")
    _require(type(receipt.breaker_state) is BreakerState, "RECEIPT_BREAKER")
    observation = receipt.execution_observation
    report = None
    if observation is not None:
        _require(type(observation) is _ObservedToolExecution, "OBSERVATION_IDENTITY")
        _require(tuple(field.name for field in fields(observation)) == _OBSERVATION_FIELDS
                 and vars(observation).keys() == set(_OBSERVATION_FIELDS), "OBSERVATION_FIELDS")
        _require(_text(observation.execution_id) and _text(observation.execution_kind),
                 "OBSERVATION_TEXT")
        _require(type(observation.worker_pid) is int and observation.worker_pid > 0
                 and type(observation.dispatcher_pid) is int and observation.dispatcher_pid > 0,
                 "OBSERVATION_PID")
        _require(_hex(observation.input_sha256)
                 and (observation.review_target_sha256 is None or _hex(observation.review_target_sha256))
                 and (observation.registration_sha256 is None or _hex(observation.registration_sha256)),
                 "OBSERVATION_HASH")
        _require(type(observation.read_only_declared) is bool, "OBSERVATION_READ_ONLY")
        report = {name: getattr(observation, name) for name in _OBSERVATION_FIELDS}
    liveness = receipt.execution_liveness
    _require(type(liveness) is dict and len(liveness) <= 16, "LIVENESS_FIELDS")
    for key, value in liveness.items():
        _require(type(key) is str and key in _LIVENESS_BOOLEAN_KEYS | _LIVENESS_TEXT_KEYS,
                 "LIVENESS_FIELDS")
        _require(type(value) is bool if key in _LIVENESS_BOOLEAN_KEYS else _text(value),
                 "LIVENESS_VALUE")
    result = {name: getattr(receipt, name) for name in _RECEIPT_FIELDS}
    result["breaker_state"] = receipt.breaker_state.value
    result["execution_observation"] = report
    result["execution_liveness"] = dict(liveness)
    return result


def _failure(category: str, phase: str, code: str) -> ApplicationError:
    # Fixed messages/details only: no payloads, paths, tokens, or exception text.
    return ApplicationError(category, {"phase": phase, "code": code},
                            type=category, non_retryable=True)


@dataclass(frozen=True, init=False)
class ReferenceActivity:
    """Bind reviewed canonical owners. Scheduling/worker bootstrap stays external.

    Worker grants are fixed at construction, not authenticated per request.
    Frozen configuration is cooperative Python discipline, not a security sandbox.
    """
    runtime: ToolRuntime
    store: ArtifactStore
    tool_id: str
    expected_registration_sha256: str
    granted_permissions: frozenset[str]
    expected_namespace: str
    expected_task_queue: str

    def __init__(self, *, runtime: ToolRuntime, store: ArtifactStore, tool_id: str,
                 expected_registration_sha256: str, granted_permissions: frozenset[str],
                 expected_namespace: str, expected_task_queue: str):
        _check_sdk()
        _require(type(runtime) is ToolRuntime and type(store) is ArtifactStore, "CANONICAL_OWNERS")
        _require(type(tool_id) is str and tool_id == TOOL_ID, "PROFILE_TOOL")
        _require(type(expected_registration_sha256) is str
                 and expected_registration_sha256 == REGISTRATION_SHA256, "PROFILE_SIGNATURE")
        _require(type(granted_permissions) in {set, frozenset} and len(granted_permissions) <= 1
                 and all(type(value) is str and value == "synthetic:read"
                         for value in granted_permissions), "PROFILE_GRANTS")
        _require(_label(expected_namespace, 255) and _label(expected_task_queue, 255), "PROFILE_DOMAIN")
        _require(runtime.registration_signature(tool_id) == expected_registration_sha256,
                 "REGISTRATION_MISMATCH")
        for name, value in {
            "runtime": runtime, "store": store, "tool_id": tool_id,
            "expected_registration_sha256": expected_registration_sha256,
            "granted_permissions": frozenset(value for value in granted_permissions),
            "expected_namespace": expected_namespace, "expected_task_queue": expected_task_queue,
        }.items():
            object.__setattr__(self, name, value)

    def _admit(self, request: object) -> ArtifactRef:
        info = activity.info()  # SDK context only, never request-supplied metadata.
        _require(type(info) is activity.Info, "ACTIVITY_INFO")
        _require(type(info.attempt) is int and info.attempt == 1, "ACTIVITY_ATTEMPT")
        _require(info.is_local is False, "ACTIVITY_MODE")
        policy = info.retry_policy
        _require(type(policy) is RetryPolicy and type(policy.maximum_attempts) is int
                 and policy.maximum_attempts == 1, "ACTIVITY_POLICY")
        _require(type(info.start_to_close_timeout) is timedelta
                 and info.start_to_close_timeout == START_TO_CLOSE
                 and type(info.schedule_to_close_timeout) is timedelta
                 and info.schedule_to_close_timeout == SCHEDULE_TO_CLOSE, "ACTIVITY_TIMEOUTS")
        _require(type(info.activity_type) is str and info.activity_type == ACTIVITY_NAME
                 and type(info.namespace) is str and info.namespace == self.expected_namespace
                 and type(info.task_queue) is str and info.task_queue == self.expected_task_queue,
                 "ACTIVITY_DOMAIN")
        _require(_text(info.workflow_id) and _text(info.workflow_run_id), "ACTIVITY_WORKFLOW")
        _shape(request, frozenset({"schema_version", "input_ref"}))
        _require(type(request["schema_version"]) is str
                 and request["schema_version"] == "opendot.temporal.request.v1", "REQUEST_SCHEMA")
        ref = _reference(request["input_ref"])
        _bounded_json(request, 4096)
        _require(self.runtime.registration_signature(self.tool_id) == self.expected_registration_sha256,
                 "REGISTRATION_MISMATCH")
        return ref

    @activity.defn(name=ACTIVITY_NAME)
    def run(self, request: dict[str, Any]) -> dict[str, Any]:
        try:
            ref = self._admit(request)
        except Exception:
            raise _failure("TemporalAdmissionRejected", "admission", "ADMISSION_REFUSED") from None
        try:
            data = self.store.get_bytes(ref, max_bytes=256)
            _require(type(data) is bytes and len(data) == ref.size_bytes and len(data) <= 256,
                     "INPUT_SIZE")
            payload = _decode(data)
            _validate_payload(payload)
        except Exception:
            raise _failure("TemporalInputRejected", "input", "INPUT_REFUSED") from None

        # The sole invocation. Original configured control exceptions propagate.
        # The original guard may refuse after the above admitted input CAS read.
        output, receipt = self.runtime.execute(
            self.tool_id, payload, granted_permissions=self.granted_permissions,
            approval_token=None, backoff_base_s=0.0, attempt_limit=1,
        )
        try:
            _require(output is None or (type(output) is int and -2_000_000 <= output <= 2_000_000),
                     "OUTPUT_PROFILE")
            document = {
                "schema_version": "opendot.temporal.result.v1", "profile": PROFILE,
                "input_ref": _reference_record(replace(ref, integrity_verified=True)),
                "output": output, "receipt_report": _receipt_report(receipt),
                "observation_provenance": "serialized_runtime_report_not_live_proof",
                "scientific_validity": False, "device_control_authority": False,
                "independent_review": "NOT_EVALUATED", "owner_integration": "NOT_EVALUATED",
            }
            _bounded_json(document, 16384)
        except Exception:
            raise _failure("TemporalResultEncodingFailed", "result_encoding", "RESULT_UNREPRESENTABLE") from None
        try:
            result_ref = self.store.put_json(
                document, producer=RESULT_PRODUCER, task_id=receipt.call_id,
                schema_version="1.0.0", source_refs=(ref.artifact_id,),
            )
        except Exception:
            raise _failure("TemporalResultStoreFailed", "result_store", "PUBLICATION_UNCONFIRMED") from None
        try:
            row = _reference_record(result_ref)
            _reference(row, result_call_id=receipt.call_id, input_artifact_id=ref.artifact_id)
            response = {"schema_version": "opendot.temporal.response.v1", "result_ref": row}
            _bounded_json(response, 4096)
            return response
        except Exception:
            # Stored bytes may exist. Do not repeat the put or the execution.
            raise _failure("TemporalResultEncodingFailed", "response_encoding", "RESPONSE_UNREPRESENTABLE") from None


# ADR 008 is a separate fixed profile. Keep every original v1 subtree above
# unchanged, including its call-ID reference rules and receipt serialization.
from hashlib import sha256 as _dag_sha256

from ..core.artifacts import ArtifactIntegrityError
from .temporal_workflow import (
    DAG_ACTIVITY_NAME, DAG_HANDLER_SOURCE_SHA256, DAG_INPUT_SHA256,
    DAG_INSPECT_ACTIVITY_NAME, DAG_OUTPUT_SHA256, DAG_PLAN_SHA256, DAG_PROFILE,
    DAG_REGISTRATION_SHA256, DAG_RESULT_PRODUCER, DAG_SEED_SHA256,
    _dag_canonical, _dag_check, _dag_reference_fields, _dag_shape,
    _dag_validate_inspection, _dag_validate_reference, _dag_validate_step,
    dag_effect_id, dag_workflow_id,
)

_DAG_RESULT_FIELDS = frozenset({
    "schema_version", "profile", "mission_id", "node_id", "effect_id",
    "plan_sha256", "namespace", "workflow_id", "workflow_run_id", "activity_id",
    "registration_sha256", "seed_ref", "parent_result_ref", "input_payload_sha256",
    "output", "receipt_report", "observation_provenance", "scientific_validity",
    "device_control_authority", "independent_review", "owner_integration",
})
_DAG_ORIGIN_FIELDS = frozenset({
    "schema_version", "origin_kind", "capture_phase", "mission_id", "plan_sha256",
    "node_id", "effect_id", "namespace", "workflow_id", "workflow_run_id",
    "execution_activity_id", "original_result_ref",
})


def _dag_artifact_ref(row: dict[str, object]) -> ArtifactRef:
    """Construct only the canonical owner from an already validated wire row."""
    ref = ArtifactRef(
        artifact_id=row["artifact_id"], uri=row["uri"], mime_type=row["mime_type"],
        size_bytes=row["size_bytes"], sha256=row["sha256"],
        schema_version=row["schema_version"], producer=row["producer"],
        task_id=row["task_id"], source_refs=tuple(row["source_refs"]),
        integrity_verified=False,
    )
    ref.validate()
    return ref


def _dag_freeze_origin(value: object) -> bytes | None:
    """Detach trusted pre-Update evidence; its domain binding is checked later."""
    if value is None:
        return None
    _dag_shape(value, _DAG_ORIGIN_FIELDS)
    for name in _DAG_ORIGIN_FIELDS - {"original_result_ref"}:
        _dag_check(_text(value[name], 128), "ORIGIN_FIELD")
    _dag_check(value["schema_version"] == "opendot.temporal.dag-origin.v1"
               and value["origin_kind"] == "trusted-single-operator-synthetic-put-observer"
               and value["capture_phase"] == "original_put_return_before_response",
               "ORIGIN_SCHEMA")
    _dag_check(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,31}", value["mission_id"]) is not None
               and _label(value["namespace"], 128), "ORIGIN_DOMAIN")
    _dag_check(value["node_id"] in {"A", "B"} and _hex(value["plan_sha256"])
               and value["effect_id"].startswith("sha256:")
               and _hex(value["effect_id"][7:]), "ORIGIN_IDENTITY")
    detached = {name: value[name] for name in _DAG_ORIGIN_FIELDS - {"original_result_ref"}}
    detached["original_result_ref"] = _dag_reference_fields(value["original_result_ref"], 16384)
    data = _dag_canonical(detached)
    _dag_check(len(data) <= 4096, "ORIGIN_SIZE")
    return data


def _dag_receipt_outcome(report: object, output: object, node_id: str) -> tuple[str, str, int | None]:
    """Validate serialized data only; never reconstruct a live observation."""
    _dag_shape(report, frozenset(_RECEIPT_FIELDS))
    _dag_check(_hex(report["call_id"], 24)
               and type(report["tool_id"]) is str and report["tool_id"] == TOOL_ID
               and type(report["tool_version"]) is str and report["tool_version"] == "1",
               "RECEIPT_ID")
    _dag_check(type(report["status"]) is str
               and report["status"] in {"COMPLETED", "FAILED", "BLOCKED"}, "RECEIPT_STATUS")
    _dag_check(type(report["attempts"]) is int and report["attempts"] == 1, "RECEIPT_ATTEMPTS")
    _dag_check(type(report["latency_s"]) in {int, float}
               and math.isfinite(report["latency_s"]) and report["latency_s"] >= 0,
               "RECEIPT_LATENCY")
    _dag_check(_hex(report["input_hash"]) and report["input_hash"] == DAG_INPUT_SHA256[node_id]
               and (report["output_hash"] is None or _hex(report["output_hash"])), "RECEIPT_HASH")
    _dag_check(type(report["semantic_valid"]) is bool, "RECEIPT_SEMANTICS")
    _dag_check(report["error_type"] is None or _label(report["error_type"], 256), "RECEIPT_ERROR")
    _dag_check(type(report["breaker_state"]) is str
               and report["breaker_state"] in {"closed", "open", "half_open"}, "RECEIPT_BREAKER")
    _dag_check(output is None or (type(output) is int and -2_000_000 <= output <= 2_000_000),
               "OUTPUT_PROFILE")
    observation = report["execution_observation"]
    if observation is not None:
        _dag_shape(observation, frozenset(_OBSERVATION_FIELDS))
        _dag_check(_hex(observation["execution_id"], 32)
                   and type(observation["execution_kind"]) is str
                   and observation["execution_kind"] == "in_process", "OBSERVATION_ID")
        _dag_check(type(observation["worker_pid"]) is int and observation["worker_pid"] > 0
                   and type(observation["dispatcher_pid"]) is int
                   and observation["dispatcher_pid"] > 0, "OBSERVATION_PID")
        _dag_check(_hex(observation["input_sha256"])
                   and observation["input_sha256"] == DAG_INPUT_SHA256[node_id]
                   and _hex(observation["registration_sha256"])
                   and observation["registration_sha256"] == DAG_REGISTRATION_SHA256
                   and observation["review_target_sha256"] is None
                   and observation["read_only_declared"] is True, "OBSERVATION_BINDING")
    liveness = report["execution_liveness"]
    _dag_check(type(liveness) is dict and len(liveness) <= 16, "LIVENESS_FIELDS")
    for key, value in liveness.items():
        _dag_check(type(key) is str and key in _LIVENESS_BOOLEAN_KEYS | _LIVENESS_TEXT_KEYS,
                   "LIVENESS_FIELDS")
        _dag_check(type(value) is bool if key in _LIVENESS_BOOLEAN_KEYS else _text(value),
                   "LIVENESS_VALUE")
    if liveness or report["error_type"] == "TimeoutError":
        return "UNRESOLVED", "LIVENESS_UNKNOWN", None
    if report["status"] in {"BLOCKED", "FAILED"}:
        _dag_check(output is None and report["output_hash"] is None
                   and report["semantic_valid"] is False and report["error_type"] is not None,
                   "REJECTED_RECEIPT")
        return "CONSISTENT_REJECTED", "TOOL_REJECTED", None
    _dag_check(observation is not None and report["semantic_valid"] is True
               and report["error_type"] is None and report["breaker_state"] == "closed",
               "COMPLETED_RECEIPT")
    _dag_check(report["output_hash"] == _dag_sha256(_dag_canonical(output)).hexdigest(),
               "OUTPUT_HASH")
    expected = 5 if node_id == "A" else 6
    if type(output) is int and output == expected:
        _dag_check(report["output_hash"] == DAG_OUTPUT_SHA256[node_id], "OUTPUT_PIN")
        return "CONSISTENT_COMPLETED", "RESULT_VERIFIED", expected
    return "CONSISTENT_REJECTED", "OUTPUT_REJECTED", None


@dataclass(frozen=True, init=False)
class DependentSumActivity:
    """One reviewed mission/run, canonical owners, and immutable origin evidence.

    The supplied source pin is a bootstrap configuration assertion. Serialized
    observations and origin labels are not independent external-effect proof.
    No timeout or cancellation here establishes physical termination.
    """
    runtime: ToolRuntime
    store: ArtifactStore
    expected_registration_sha256: str
    expected_handler_source_sha256: str
    expected_plan_sha256: str
    expected_seed_sha256: str
    granted_permissions: frozenset[str]
    expected_namespace: str
    expected_task_queue: str
    expected_workflow_id: str
    expected_workflow_run_id: str
    original_A: bytes | None
    original_B: bytes | None

    def __init__(self, *, runtime: ToolRuntime, store: ArtifactStore,
                 expected_registration_sha256: str, expected_handler_source_sha256: str,
                 expected_plan_sha256: str, expected_seed_sha256: str,
                 granted_permissions: frozenset[str], expected_namespace: str,
                 expected_task_queue: str, expected_workflow_id: str,
                 expected_workflow_run_id: str, original_A: dict[str, object] | None = None,
                 original_B: dict[str, object] | None = None):
        _check_sdk()
        _dag_check(type(runtime) is ToolRuntime and type(store) is ArtifactStore, "CANONICAL_OWNERS")
        for actual, expected in (
            (expected_registration_sha256, DAG_REGISTRATION_SHA256),
            (expected_handler_source_sha256, DAG_HANDLER_SOURCE_SHA256),
            (expected_plan_sha256, DAG_PLAN_SHA256), (expected_seed_sha256, DAG_SEED_SHA256),
        ):
            _dag_check(type(actual) is str and actual == expected, "DAG_CONFIGURATION_PIN")
        _dag_check(type(granted_permissions) in {set, frozenset} and len(granted_permissions) <= 1
                   and all(type(value) is str and value == "synthetic:read"
                           for value in granted_permissions), "PROFILE_GRANTS")
        _dag_check(_label(expected_namespace, 128) and _label(expected_task_queue, 128)
                   and _text(expected_workflow_id, 128) and _text(expected_workflow_run_id, 128),
                   "PROFILE_DOMAIN")
        mission_id = expected_workflow_id[len("opendot-dag2-"):-(len(DAG_PLAN_SHA256) + 1)]
        _dag_check(expected_workflow_id == dag_workflow_id(mission_id), "PROFILE_WORKFLOW")
        _dag_check(runtime.registration_signature(TOOL_ID) == expected_registration_sha256,
                   "REGISTRATION_MISMATCH")
        frozen_A, frozen_B = _dag_freeze_origin(original_A), _dag_freeze_origin(original_B)
        for name, value in {
            "runtime": runtime, "store": store,
            "expected_registration_sha256": expected_registration_sha256,
            "expected_handler_source_sha256": expected_handler_source_sha256,
            "expected_plan_sha256": expected_plan_sha256, "expected_seed_sha256": expected_seed_sha256,
            "granted_permissions": frozenset(value for value in granted_permissions),
            "expected_namespace": expected_namespace, "expected_task_queue": expected_task_queue,
            "expected_workflow_id": expected_workflow_id,
            "expected_workflow_run_id": expected_workflow_run_id,
            "original_A": frozen_A, "original_B": frozen_B,
        }.items():
            object.__setattr__(self, name, value)

    def _admit(self, request: object, *, inspection: bool) -> dict[str, object]:
        info = activity.info()
        _dag_check(type(info) is activity.Info, "ACTIVITY_INFO")
        _dag_check(type(info.attempt) is int and info.attempt == 1, "ACTIVITY_ATTEMPT")
        _dag_check(info.is_local is False, "ACTIVITY_MODE")
        policy = info.retry_policy
        _dag_check(type(policy) is RetryPolicy and type(policy.maximum_attempts) is int
                   and policy.maximum_attempts == 1, "ACTIVITY_POLICY")
        _dag_check(type(info.start_to_close_timeout) is timedelta
                   and info.start_to_close_timeout == START_TO_CLOSE
                   and type(info.schedule_to_close_timeout) is timedelta
                   and info.schedule_to_close_timeout == SCHEDULE_TO_CLOSE, "ACTIVITY_TIMEOUTS")
        expected_type = DAG_INSPECT_ACTIVITY_NAME if inspection else DAG_ACTIVITY_NAME
        _dag_check(type(info.activity_type) is str and info.activity_type == expected_type
                   and type(info.namespace) is str and info.namespace == self.expected_namespace
                   and type(info.task_queue) is str and info.task_queue == self.expected_task_queue,
                   "ACTIVITY_DOMAIN")
        _dag_check(_text(info.workflow_id, 128) and info.workflow_id == self.expected_workflow_id
                   and _text(info.workflow_run_id, 128)
                   and info.workflow_run_id == self.expected_workflow_run_id, "ACTIVITY_WORKFLOW")
        if inspection:
            row = _dag_validate_inspection(request, namespace=info.namespace, workflow_id=info.workflow_id)
            prefix = "dag2-inspect-" + row["mode"] + "-"
        else:
            row = _dag_validate_step(request, namespace=info.namespace, workflow_id=info.workflow_id)
            prefix = "dag2-execute-"
            _dag_check(self.runtime.registration_signature(TOOL_ID) == self.expected_registration_sha256,
                       "REGISTRATION_MISMATCH")
        _dag_check(type(info.activity_id) is str and info.activity_id == prefix + row["effect_id"][7:],
                   "ACTIVITY_ID")
        return row

    def _read_result(self, request: dict[str, object], candidate: dict[str, object], *,
                     original_result_sha256: str | None = None) -> tuple[str, str, int | None]:
        try:
            raw = self.store.get_bytes(_dag_artifact_ref(candidate), max_bytes=16384)
        except ArtifactIntegrityError:
            return "UNRESOLVED", "RESULT_INVALID", None
        except Exception:
            return "UNRESOLVED", "RESULT_UNAVAILABLE", None
        try:
            _dag_check(type(raw) is bytes and 0 < len(raw) == candidate["size_bytes"] <= 16384,
                       "RESULT_SIZE")
            acquired_sha256 = _dag_sha256(raw).hexdigest()
            _dag_check(acquired_sha256 == candidate["sha256"], "RESULT_HASH")
            if original_result_sha256 is not None:
                _dag_check(acquired_sha256 == original_result_sha256, "ORIGINAL_RESULT_HASH")
            body = _decode(raw)
            _dag_shape(body, _DAG_RESULT_FIELDS)
            expected = {
                "schema_version": "opendot.temporal.dag-result.v1", "profile": DAG_PROFILE,
                "mission_id": request["mission_id"], "node_id": request["node_id"],
                "effect_id": request["effect_id"], "plan_sha256": DAG_PLAN_SHA256,
                "namespace": self.expected_namespace, "workflow_id": self.expected_workflow_id,
                "workflow_run_id": self.expected_workflow_run_id,
                "activity_id": "dag2-execute-" + request["effect_id"][7:],
                "registration_sha256": DAG_REGISTRATION_SHA256,
                "input_payload_sha256": DAG_INPUT_SHA256[request["node_id"]],
                "observation_provenance": "serialized_runtime_report_not_live_proof",
                "independent_review": "NOT_EVALUATED", "owner_integration": "NOT_EVALUATED",
            }
            for name, value in expected.items():
                _dag_check(type(body[name]) is str and body[name] == value, "RESULT_BINDING")
            _dag_check(body["scientific_validity"] is False
                       and body["device_control_authority"] is False, "RESULT_AUTHORITY")
            seed = _dag_validate_reference(body["seed_ref"])
            _dag_check(seed == request["seed_ref"], "RESULT_SEED")
            if request["node_id"] == "A":
                _dag_check(body["parent_result_ref"] is None, "RESULT_PARENT")
            else:
                a_effect = dag_effect_id(namespace=self.expected_namespace,
                    workflow_id=self.expected_workflow_id, node_id="A", parent_result_sha256=None)
                parent = _dag_validate_reference(body["parent_result_ref"], seed_ref=seed,
                                                  effect_id=a_effect, parent_result_ref=None)
                _dag_check(parent == request["parent_result_ref"], "RESULT_PARENT")
            outcome = _dag_receipt_outcome(body["receipt_report"], body["output"], request["node_id"])
            _dag_check(raw == _dag_canonical(body), "RESULT_CANONICAL")
            return outcome
        except Exception:
            return "UNRESOLVED", "RESULT_INVALID", None

    def _origin_matches(self, request: dict[str, object]) -> tuple[dict[str, object] | None, str | None]:
        saved = self.original_A if request["node_id"] == "A" else self.original_B
        if saved is None:
            return None, "ORIGIN_UNAVAILABLE"
        try:
            origin = _decode(saved)
            _dag_check(_dag_sha256(saved).hexdigest() == request["original_evidence_sha256"],
                       "ORIGIN_EVIDENCE")
            expected = {
                "mission_id": request["mission_id"], "plan_sha256": DAG_PLAN_SHA256,
                "node_id": request["node_id"], "effect_id": request["effect_id"],
                "namespace": self.expected_namespace, "workflow_id": self.expected_workflow_id,
                "workflow_run_id": self.expected_workflow_run_id,
                "execution_activity_id": "dag2-execute-" + request["effect_id"][7:],
            }
            for name, value in expected.items():
                _dag_check(origin[name] == value, "ORIGIN_BINDING")
            original = _dag_validate_reference(origin["original_result_ref"],
                seed_ref=request["seed_ref"], effect_id=request["effect_id"],
                parent_result_ref=request["parent_result_ref"])
            _dag_check(original == request["candidate_result_ref"]
                       and original["sha256"] == request["original_result_sha256"], "ORIGIN_REFERENCE")
            return original, None
        except Exception:
            return None, "ORIGIN_MISMATCH"

    @activity.defn(name=DAG_ACTIVITY_NAME)
    def execute_step(self, request: dict[str, Any]) -> dict[str, Any]:
        try:
            row = self._admit(request, inspection=False)
        except Exception:
            raise _failure("TemporalDagAdmissionRejected", "admission", "ADMISSION_REFUSED") from None
        try:
            seed = _dag_artifact_ref(row["seed_ref"])
            data = self.store.get_bytes(seed, max_bytes=256)
            _dag_check(type(data) is bytes and len(data) == seed.size_bytes == 40
                       and _dag_sha256(data).hexdigest() == DAG_SEED_SHA256, "INPUT_BYTES")
            payload = _decode(data)
            _validate_payload(payload)
            _dag_check(data == b'{"left":2,"return_null":false,"right":3}', "INPUT_CANONICAL")
            if row["node_id"] == "B":
                parent_request = {
                    "mission_id": row["mission_id"], "node_id": "A", "seed_ref": row["seed_ref"],
                    "parent_result_ref": None,
                    "effect_id": dag_effect_id(namespace=self.expected_namespace,
                        workflow_id=self.expected_workflow_id, node_id="A", parent_result_sha256=None),
                }
                status, _, parent_output = self._read_result(parent_request, row["parent_result_ref"])
                _dag_check(status == "CONSISTENT_COMPLETED" and type(parent_output) is int
                           and parent_output == 5, "PARENT_UNACCEPTED")
                payload = {"left": parent_output, "right": 1, "return_null": False}
            _dag_check(_dag_sha256(_dag_canonical(payload)).hexdigest() == DAG_INPUT_SHA256[row["node_id"]],
                       "INPUT_PAYLOAD")
        except Exception:
            raise _failure("TemporalDagInputRejected", "input", "INPUT_REFUSED") from None

        # One new canonical call site. Original control exceptions escape intact.
        output, receipt = self.runtime.execute(
            TOOL_ID, payload, granted_permissions=self.granted_permissions,
            approval_token=None, backoff_base_s=0.0, attempt_limit=1,
        )
        try:
            report = _receipt_report(receipt)
            _dag_receipt_outcome(report, output, row["node_id"])
            document = {
                "schema_version": "opendot.temporal.dag-result.v1", "profile": DAG_PROFILE,
                "mission_id": row["mission_id"], "node_id": row["node_id"],
                "effect_id": row["effect_id"], "plan_sha256": DAG_PLAN_SHA256,
                "namespace": self.expected_namespace, "workflow_id": self.expected_workflow_id,
                "workflow_run_id": self.expected_workflow_run_id,
                "activity_id": "dag2-execute-" + row["effect_id"][7:],
                "registration_sha256": DAG_REGISTRATION_SHA256, "seed_ref": row["seed_ref"],
                "parent_result_ref": row["parent_result_ref"],
                "input_payload_sha256": DAG_INPUT_SHA256[row["node_id"]],
                "output": output, "receipt_report": report,
                "observation_provenance": "serialized_runtime_report_not_live_proof",
                "scientific_validity": False, "device_control_authority": False,
                "independent_review": "NOT_EVALUATED", "owner_integration": "NOT_EVALUATED",
            }
            encoded = _dag_canonical(document)
            _dag_check(len(encoded) <= 16384, "RESULT_SIZE")
        except Exception:
            raise _failure("TemporalDagResultEncodingFailed", "result_encoding", "RESULT_UNREPRESENTABLE") from None
        sources = (seed.artifact_id,) if row["node_id"] == "A" else (
            seed.artifact_id, row["parent_result_ref"]["artifact_id"],
        )
        try:
            result_ref = self.store.put_json(document, producer=DAG_RESULT_PRODUCER,
                task_id=row["effect_id"][7:], schema_version="1.0.0", source_refs=sources)
        except Exception:
            raise _failure("TemporalDagResultStoreFailed", "result_store", "PUBLICATION_UNCONFIRMED") from None
        try:
            result = _dag_validate_reference(
                _reference_record(replace(result_ref, integrity_verified=False)),
                seed_ref=row["seed_ref"], effect_id=row["effect_id"],
                parent_result_ref=row["parent_result_ref"],
            )
            _dag_check(result["sha256"] == _dag_sha256(encoded).hexdigest()
                       and result["size_bytes"] == len(encoded), "RESULT_PUBLICATION")
            response = {"schema_version": "opendot.temporal.dag-step-response.v1",
                        "effect_id": row["effect_id"], "result_ref": result}
            _dag_check(len(_dag_canonical(response)) <= 4096, "RESPONSE_SIZE")
            return response
        except Exception:
            raise _failure("TemporalDagResultEncodingFailed", "response_encoding", "RESPONSE_UNREPRESENTABLE") from None

    @activity.defn(name=DAG_INSPECT_ACTIVITY_NAME)
    def inspect_result(self, request: dict[str, Any]) -> dict[str, Any]:
        try:
            row = self._admit(request, inspection=True)
        except Exception:
            raise _failure("TemporalDagAdmissionRejected", "admission", "ADMISSION_REFUSED") from None
        original, origin_reason = None, None
        if row["mode"] == "reconcile":
            original, origin_reason = self._origin_matches(row)
        if origin_reason is not None:
            status, reason, output = "UNRESOLVED", origin_reason, None
        else:
            status, reason, output = self._read_result(row, row["candidate_result_ref"],
                original_result_sha256=None if original is None else original["sha256"])
        response = {
            "schema_version": "opendot.temporal.dag-inspection.v1", "effect_id": row["effect_id"],
            "mode": row["mode"], "expected_revision": row["expected_revision"],
            "status": status, "reason_code": reason, "result_ref": row["candidate_result_ref"],
            "input_payload_sha256": DAG_INPUT_SHA256[row["node_id"]], "output": output,
            "original_evidence_sha256": row["original_evidence_sha256"],
        }
        _dag_check(len(_dag_canonical(response)) <= 4096, "RESPONSE_SIZE")
        return response
