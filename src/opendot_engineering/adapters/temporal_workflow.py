"""Optional, fixed non-local Activity scheduling for the ADR 004 reference profile.

Import explicitly from a consumer-owned Workflow using the qualified Temporal
SDK 1.34.0. Version/API qualification belongs to trusted bootstrap, outside
Workflow execution. This module neither loads the worker nor resolves artifacts.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy


async def execute_reference(
    request: dict[str, Any], *, task_queue: str
) -> dict[str, Any]:
    """Await one fixed non-local Activity, returning its response unchanged.

    The consumer supplies a stable, trusted queue and calls this helper at most
    once per Workflow run. The consumer must also exclude retry/resubmit and
    new-run loops; the fixed Activity ID is not global duplicate suppression.
    SDK failures propagate without rescheduling or resolving the response ref.
    """
    return await workflow.execute_activity(
        "opendot.synthetic.reference.v1",
        request,
        task_queue=task_queue,
        activity_id="opendot-synthetic-reference-v1",
        retry_policy=RetryPolicy(maximum_attempts=1),
        start_to_close_timeout=timedelta(seconds=10),
        schedule_to_close_timeout=timedelta(seconds=60),
    )


# ADR 008 is an explicit, fixed-profile exception. The original helper above is
# unchanged; nothing in the package's default import path imports this module.
from asyncio import CancelledError
from copy import deepcopy
from hashlib import sha256
from json import dumps
from re import fullmatch

from temporalio.exceptions import ApplicationError

DAG_PROFILE = "synthetic.dependent_sum.v1"
DAG_PLAN_SHA256 = "19843079a5da00754ec1b5399962c33874b907eb4d0d6fcf55cd3be2f4dffb63"
DAG_HANDLER_SOURCE_SHA256 = "a97dadac88bed7b09d2398516617216cb865ae97db411c12b72de01d7a78d1cb"
DAG_REGISTRATION_SHA256 = "5f2b1e81954530f31c7d2c83b9c582883b8391190ebe13b69b8bf91f044cb0c3"
DAG_SEED_SHA256 = "897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02"
DAG_INPUT_SHA256 = {
    "A": "897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02",
    "B": "6d23a7a66975efd35356848b1f69b848e99c3c76dc5a3740e35328d41c05440a",
}
DAG_OUTPUT_SHA256 = {
    "A": "ef2d127de37b942baad06145e54b0c619a1f22327b2ebbcfbec78f5564afe39d",
    "B": "e7f6c011776e8db7cd330b54174fd76f7d0216b612387a5ffcfb81e6f0919683",
}
DAG_WORKFLOW_NAME = "opendot.synthetic.dependent-sum.v1"
DAG_ACTIVITY_NAME = "opendot.synthetic.dependent-step.v1"
DAG_INSPECT_ACTIVITY_NAME = "opendot.synthetic.dependent-inspect.v1"
DAG_RESULT_PRODUCER = "opendot.temporal.dag-result.v1"
_DAG_REF_FIELDS = frozenset({
    "artifact_id", "uri", "mime_type", "size_bytes", "sha256", "schema_version",
    "producer", "task_id", "source_refs", "integrity_verified",
})
_DAG_STEP_FIELDS = frozenset({
    "schema_version", "mission_id", "plan_sha256", "node_id", "effect_id",
    "seed_ref", "parent_result_ref",
})
_DAG_INSPECT_FIELDS = _DAG_STEP_FIELDS | frozenset({
    "candidate_result_ref", "mode", "expected_revision",
    "original_evidence_sha256", "original_result_sha256",
})
_DAG_UPDATE_FIELDS = frozenset({
    "schema_version", "node_id", "effect_id", "expected_revision",
    "candidate_result_ref", "original_evidence_sha256", "original_result_sha256",
})
_DAG_TERMINAL = frozenset({"COMPLETED", "REJECTED", "STOPPED_WITH_UNKNOWN"})
_DAG_INSPECTION_REASONS = {
    "CONSISTENT_COMPLETED": frozenset({"RESULT_VERIFIED"}),
    "CONSISTENT_REJECTED": frozenset({"TOOL_REJECTED", "OUTPUT_REJECTED"}),
    "UNRESOLVED": frozenset({"RESULT_UNAVAILABLE", "RESULT_INVALID", "ORIGIN_UNAVAILABLE",
        "ORIGIN_MISMATCH", "LIVENESS_UNKNOWN", "INSPECTION_FAILED"}),
}


def _dag_check(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError(code)


def _dag_shape(value: object, keys: frozenset[str]) -> None:
    _dag_check(type(value) is dict and len(value) == len(keys), "INVALID_FIELDS")
    _dag_check(all(type(key) is str for key in value) and value.keys() == keys,
               "INVALID_FIELDS")


def _dag_canonical(value: object) -> bytes:
    # Callers first validate known finite plain fields, not a generic user graph.
    return dumps(value, ensure_ascii=False, sort_keys=True,
                 separators=(",", ":"), allow_nan=False).encode("utf-8")


def _dag_hex(value: object) -> bool:
    return type(value) is str and fullmatch(r"[0-9a-f]{64}", value) is not None


def _dag_label(value: object, limit: int = 128) -> bool:
    return (type(value) is str and 0 < len(value) <= limit
            and fullmatch(r"[A-Za-z0-9._-]+", value) is not None)


def dag_workflow_id(mission_id: str) -> str:
    _dag_check(type(mission_id) is str
               and fullmatch(r"[a-z0-9][a-z0-9-]{0,31}", mission_id) is not None,
               "MISSION_ID")
    return "opendot-dag2-" + mission_id + "-" + DAG_PLAN_SHA256


def dag_effect_id(*, namespace: str, workflow_id: str, node_id: str,
                  parent_result_sha256: str | None) -> str:
    _dag_check(_dag_label(namespace) and _dag_label(workflow_id, 256), "EFFECT_DOMAIN")
    _dag_check(type(node_id) is str and node_id in {"A", "B"}, "NODE_ID")
    _dag_check(parent_result_sha256 is None if node_id == "A"
               else _dag_hex(parent_result_sha256), "EFFECT_PARENT")
    return "sha256:" + sha256(_dag_canonical({
        "schema_version": "opendot.effect.v1", "namespace": namespace,
        "workflow_id": workflow_id, "plan_sha256": DAG_PLAN_SHA256,
        "node_id": node_id, "parent_result_sha256": parent_result_sha256,
    })).hexdigest()


def _dag_reference_fields(row: object, limit: int) -> dict[str, Any]:
    _dag_shape(row, _DAG_REF_FIELDS)
    digest = row["sha256"]
    _dag_check(_dag_hex(digest), "REFERENCE_DIGEST")
    _dag_check(type(row["artifact_id"]) is str and row["artifact_id"] == "sha256:" + digest,
               "REFERENCE_ID")
    _dag_check(type(row["uri"]) is str and row["uri"] == "artifact://sha256/" + digest,
               "REFERENCE_URI")
    for key, expected in (("mime_type", "application/json"), ("schema_version", "1.0.0")):
        _dag_check(type(row[key]) is str and row[key] == expected, "REFERENCE_SCHEMA")
    _dag_check(type(row["size_bytes"]) is int and 0 < row["size_bytes"] <= limit,
               "REFERENCE_SIZE")
    _dag_check(row["integrity_verified"] is False, "REFERENCE_INTEGRITY_CLAIM")
    _dag_check(_dag_label(row["producer"], 80) and _dag_label(row["task_id"], 80),
               "REFERENCE_LABEL")
    sources = row["source_refs"]
    _dag_check(type(sources) is list and len(sources) <= 2, "REFERENCE_SOURCES")
    _dag_check(all(type(value) is str and value.startswith("sha256:")
                   and _dag_hex(value[7:]) for value in sources), "REFERENCE_SOURCES")
    return deepcopy(row)


def _dag_validate_reference(row: object, *, seed_ref: dict[str, Any] | None = None,
                            effect_id: str | None = None,
                            parent_result_ref: dict[str, Any] | None = None) -> dict[str, Any]:
    result = _dag_reference_fields(row, 256 if seed_ref is None else 16384)
    if seed_ref is None:
        _dag_check(result["sha256"] == DAG_SEED_SHA256 and result["size_bytes"] == 40
                   and result["producer"] == "opendot.temporal.dag-seed.v1"
                   and result["task_id"] == "seed" and result["source_refs"] == [],
                   "SEED_PIN")
    else:
        seed = _dag_validate_reference(seed_ref)
        _dag_check(type(effect_id) is str and effect_id.startswith("sha256:")
                   and _dag_hex(effect_id[7:]), "EFFECT_ID")
        sources = [seed["artifact_id"]]
        if parent_result_ref is not None:
            parent = _dag_reference_fields(parent_result_ref, 16384)
            sources.append(parent["artifact_id"])
        _dag_check(result["producer"] == DAG_RESULT_PRODUCER
                   and result["task_id"] == effect_id[7:]
                   and result["source_refs"] == sources, "RESULT_REFERENCE_BINDING")
    return result


def _dag_validate_step(request: object, *, namespace: str,
                       workflow_id: str) -> dict[str, Any]:
    _dag_shape(request, _DAG_STEP_FIELDS)
    _dag_check(type(request["schema_version"]) is str
               and request["schema_version"] == "opendot.temporal.dag-step.v1", "STEP_SCHEMA")
    _dag_check(type(request["plan_sha256"]) is str
               and request["plan_sha256"] == DAG_PLAN_SHA256, "PLAN_PIN")
    _dag_check(dag_workflow_id(request["mission_id"]) == workflow_id, "WORKFLOW_ID")
    node = request["node_id"]
    _dag_check(type(node) is str and node in {"A", "B"}, "NODE_ID")
    seed = _dag_validate_reference(request["seed_ref"])
    parent = None
    if node == "A":
        _dag_check(request["parent_result_ref"] is None, "PARENT_REFERENCE")
    else:
        parent = _dag_validate_reference(request["parent_result_ref"], seed_ref=seed,
            effect_id=dag_effect_id(namespace=namespace, workflow_id=workflow_id,
                                    node_id="A", parent_result_sha256=None))
    expected = dag_effect_id(namespace=namespace, workflow_id=workflow_id,
        node_id=node, parent_result_sha256=parent["sha256"] if parent else None)
    _dag_check(type(request["effect_id"]) is str and request["effect_id"] == expected,
               "EFFECT_ID")
    _dag_check(len(_dag_canonical(request)) <= 4096, "REQUEST_SIZE")
    result = deepcopy(request)
    result["seed_ref"], result["parent_result_ref"] = seed, parent
    return result


def _dag_validate_inspection(request: object, *, namespace: str,
                             workflow_id: str) -> dict[str, Any]:
    _dag_shape(request, _DAG_INSPECT_FIELDS)
    _dag_check(type(request["schema_version"]) is str
               and request["schema_version"] == "opendot.temporal.dag-inspect.v1",
               "INSPECT_SCHEMA")
    step = {key: request[key] for key in _DAG_STEP_FIELDS}
    step["schema_version"] = "opendot.temporal.dag-step.v1"
    step = _dag_validate_step(step, namespace=namespace, workflow_id=workflow_id)
    _dag_check(type(request["mode"]) is str and request["mode"] in {"normal", "reconcile"},
               "INSPECT_MODE")
    _dag_check(type(request["expected_revision"]) is int
               and 1 <= request["expected_revision"] <= 64, "STATE_REVISION")
    candidate = _dag_validate_reference(request["candidate_result_ref"],
        seed_ref=step["seed_ref"], effect_id=step["effect_id"],
        parent_result_ref=step["parent_result_ref"])
    if request["mode"] == "normal":
        _dag_check(request["original_evidence_sha256"] is None
                   and request["original_result_sha256"] is None, "NORMAL_ORIGIN")
    else:
        _dag_check(_dag_hex(request["original_evidence_sha256"])
                   and _dag_hex(request["original_result_sha256"]), "ORIGIN_DIGEST")
    _dag_check(len(_dag_canonical(request)) <= 4096, "REQUEST_SIZE")
    result = deepcopy(request)
    result["seed_ref"], result["parent_result_ref"] = step["seed_ref"], step["parent_result_ref"]
    result["candidate_result_ref"] = candidate
    return result


@workflow.defn(name=DAG_WORKFLOW_NAME)
class DependentSumWorkflow:
    """Only fixed A then B; Temporal history is the sole durable state owner."""

    def __init__(self) -> None:
        self._state: dict[str, Any] | None = None
        self._active_handle: Any = None

    def _bump(self) -> None:
        _dag_check(self._state["revision"] < 64, "STATE_REVISION")
        self._state["revision"] += 1

    def _remaining(self) -> float:
        return max(0.0, self._state["deadline_unix_ms"] / 1000 - workflow.time())

    def _cancel_active(self) -> None:
        if self._active_handle is not None:
            try:
                self._active_handle.cancel()
            except Exception:
                # Failure to request cancellation cannot reopen acceptance.
                pass

    def _close(self, reason: str, *, cancelled: bool = False) -> None:
        state = self._state
        if state["mission_status"] in _DAG_TERMINAL:
            # V4: a final reporting fence can observe cancellation/deadline
            # after both node outcomes are already known. Preserve those rows.
            if reason in {"CANCELLED", "OBSERVATION_DEADLINE"}:
                cancel_requested = state["cancel_requested"] or cancelled
                if (state["mission_status"] != "STOPPED_WITH_UNKNOWN"
                        or cancel_requested != state["cancel_requested"]):
                    state["mission_status"] = "STOPPED_WITH_UNKNOWN"
                    state["admission_closed"] = True
                    state["cancel_requested"] = cancel_requested
                    self._bump()
                    self._cancel_active()
            return
        state["admission_closed"] = True
        state["cancel_requested"] = state["cancel_requested"] or cancelled
        state["mission_status"] = "STOPPED_WITH_UNKNOWN"
        for node in state["nodes"].values():
            if node["status"] != "ACCEPTED":
                node["status"] = "UNKNOWN" if node["execute_reserved"] else "CANCELLED_BEFORE_ADMISSION"
                node["reason_code"] = reason
        self._bump()
        self._cancel_active()

    def _gate(self) -> bool:
        # SDK records this before deferring primary task cancellation. Empty
        # string is still a recorded cancellation, never a false-y non-event.
        if workflow.cancellation_reason() is not None:
            self._close("CANCELLED", cancelled=True)
            return False
        if self._state["cancel_requested"]:
            self._close("CANCELLED", cancelled=True)
            return False
        if self._remaining() <= 0:
            self._close("OBSERVATION_DEADLINE")
            return False
        return self._state["mission_status"] not in _DAG_TERMINAL

    def _current(self, revision: int) -> bool:
        return self._gate() and self._state["revision"] == revision

    def _initialize(self, request: object) -> None:
        _dag_shape(request, frozenset({"schema_version", "mission_id", "plan_sha256", "seed_ref"}))
        _dag_check(type(request["schema_version"]) is str
                   and request["schema_version"] == "opendot.temporal.dag-start.v1", "START_SCHEMA")
        _dag_check(type(request["plan_sha256"]) is str
                   and request["plan_sha256"] == DAG_PLAN_SHA256, "PLAN_PIN")
        seed = _dag_validate_reference(request["seed_ref"])
        _dag_check(len(_dag_canonical(request)) <= 4096, "REQUEST_SIZE")
        info = workflow.info()
        _dag_check(type(info) is workflow.Info, "WORKFLOW_INFO")
        _dag_check(type(info.attempt) is int and info.attempt == 1, "WORKFLOW_ATTEMPT")
        _dag_check(type(info.retry_policy) is RetryPolicy
                   and type(info.retry_policy.maximum_attempts) is int
                   and info.retry_policy.maximum_attempts == 1, "WORKFLOW_POLICY")
        _dag_check(type(info.workflow_id) is str
                   and info.workflow_id == dag_workflow_id(request["mission_id"])
                   and type(info.workflow_type) is str
                   and info.workflow_type == DAG_WORKFLOW_NAME, "WORKFLOW_ID")
        _dag_check(_dag_label(info.namespace) and _dag_label(info.task_queue), "WORKFLOW_DOMAIN")
        _dag_check(type(info.run_id) is str and 0 < len(info.run_id) <= 128
                   and type(info.first_execution_run_id) is str
                   and type(info.original_execution_run_id) is str
                   and info.first_execution_run_id == info.original_execution_run_id == info.run_id
                   and info.continued_run_id is None and info.cron_schedule is None
                   and info.parent is None, "WORKFLOW_LINEAGE")
        _dag_check(type(info.execution_timeout) is timedelta
                   and type(info.run_timeout) is timedelta
                   and info.execution_timeout == info.run_timeout == timedelta(seconds=300),
                   "WORKFLOW_TIMEOUT")
        nodes = {name: {"effect_id": None, "status": "WAITING", "execute_reserved": False,
            "normal_inspect_reserved": False, "reconcile_inspect_reserved": False,
            "inspect_reserved": 0, "candidate_result_ref": None, "accepted_result_ref": None,
            "parent_result_ref": None, "reason_code": "NOT_ADMITTED"} for name in ("A", "B")}
        nodes["A"]["effect_id"] = dag_effect_id(namespace=info.namespace,
            workflow_id=info.workflow_id, node_id="A", parent_result_sha256=None)
        self._state = {"schema_version": "opendot.temporal.dag-state.v1", "profile": DAG_PROFILE,
            "mission_id": request["mission_id"], "plan_sha256": DAG_PLAN_SHA256,
            "seed_ref": seed, "namespace": info.namespace, "workflow_id": info.workflow_id,
            "run_id": info.run_id, "revision": 1, "mission_status": "RUNNING",
            "admission_closed": False, "cancel_requested": False,
            "deadline_unix_ms": int(info.workflow_start_time.timestamp() * 1000) + 300000,
            "nodes": nodes, "resources": {"execute_limit": 2, "normal_inspect_limit": 2,
                "reconcile_inspect_limit": 2, "activity_command_limit": 6,
                "result_bytes_reserved": 32768, "execute_used": 0, "normal_inspect_used": 0,
                "reconcile_inspect_used": 0, "activity_commands_used": 0},
            "termination_status": "NOT_ESTABLISHED", "external_effect_authenticity": "NOT_PROVED",
            "scientific_validity": False, "device_control_authority": False,
            "independent_review": "NOT_EVALUATED", "owner_integration": "NOT_EVALUATED"}

    @workflow.query(name="dag_state")
    def dag_state(self) -> dict[str, Any]:
        _dag_check(self._state is not None, "STATE_NOT_STARTED")
        snapshot = deepcopy(self._state)
        _dag_check(len(_dag_canonical(snapshot)) <= 16384, "STATE_SIZE")
        return snapshot

    def _step_request(self, name: str) -> dict[str, Any]:
        node = self._state["nodes"][name]
        return {"schema_version": "opendot.temporal.dag-step.v1",
            "mission_id": self._state["mission_id"], "plan_sha256": DAG_PLAN_SHA256,
            "node_id": name, "effect_id": node["effect_id"],
            "seed_ref": deepcopy(self._state["seed_ref"]),
            "parent_result_ref": deepcopy(node["parent_result_ref"])}

    def _reserve(self, name: str, kind: str) -> bool:
        if not self._gate():
            return False
        node, resources = self._state["nodes"][name], self._state["resources"]
        flag = "execute_reserved" if kind == "execute" else kind + "_reserved"
        if (node[flag] or resources[kind + "_used"] >= resources[kind + "_limit"]
                or resources["activity_commands_used"] >= 6):
            self._close("INSPECTION_EXHAUSTED")
            return False
        node[flag] = True
        resources[kind + "_used"] += 1
        resources["activity_commands_used"] += 1
        if kind == "execute":
            node["status"], node["reason_code"] = "RESERVED", "EXECUTE_RESERVED"
        else:
            node["inspect_reserved"] += 1
            node["status"] = "VERIFYING"
            node["reason_code"] = "INSPECT_RESERVED" if kind == "normal_inspect" else "RECONCILE_RESERVED"
        self._bump()
        return True

    async def _command(self, activity_name: str, request: dict[str, Any],
                       activity_id: str, revision: int) -> tuple[str, Any]:
        if not self._current(revision):
            return "CLOSED", None
        handle = None
        try:
            handle = workflow.start_activity(activity_name, request,
                task_queue=workflow.info().task_queue, activity_id=activity_id,
                retry_policy=RetryPolicy(maximum_attempts=1),
                start_to_close_timeout=timedelta(seconds=10),
                schedule_to_close_timeout=timedelta(seconds=60),
                cancellation_type=workflow.ActivityCancellationType.TRY_CANCEL)
            self._active_handle = handle
            try:
                await workflow.wait_condition(handle.done, timeout=self._remaining())
            except TimeoutError:
                # Only our observation timer closes the whole deadline. A
                # delivered Activity TimeoutError below is execution ambiguity.
                self._close("OBSERVATION_DEADLINE")
                return "CLOSED", None
            if not self._current(revision):
                return "CLOSED", None
            result = await handle
            if not self._current(revision):
                return "CLOSED", None
            return "RESULT", result
        except CancelledError:
            if (workflow.cancellation_reason() is None and not self._state["cancel_requested"]
                    and self._remaining() > 0
                    and self._state["mission_status"] not in _DAG_TERMINAL):
                # Cache eviction/internal task cancellation is SDK control flow.
                # Do not fabricate a server cancellation or refund a reservation.
                raise
            self._gate()
            self._cancel_active()
            return "CLOSED", None
        except Exception as error:
            if not self._current(revision):
                return "CLOSED", None
            return "ERROR", error
        finally:
            if self._active_handle is handle:
                self._active_handle = None

    def _known_input_refusal(self, error: Exception) -> bool:
        for value in (error, error.__cause__):
            if type(value) is ApplicationError and value.non_retryable is True:
                if value.type == "TemporalDagAdmissionRejected" and value.details == (
                        {"phase": "admission", "code": "ADMISSION_REFUSED"},):
                    return True
                if value.type == "TemporalDagInputRejected" and value.details == (
                        {"phase": "input", "code": "INPUT_REFUSED"},):
                    return True
        return False

    def _unknown(self, name: str, reason: str, *, exhausted: bool = False) -> None:
        node = self._state["nodes"][name]
        node["status"], node["reason_code"] = "UNKNOWN", reason
        self._state["admission_closed"] = True
        self._state["mission_status"] = "STOPPED_WITH_UNKNOWN" if exhausted else "PAUSED_UNKNOWN"
        self._bump()

    def _reject(self, name: str, reason: str) -> None:
        node = self._state["nodes"][name]
        node["status"], node["reason_code"] = "REJECTED", reason
        self._state["mission_status"], self._state["admission_closed"] = "REJECTED", True
        if name == "A":
            self._state["nodes"]["B"]["reason_code"] = "DEPENDENCY_REJECTED"
        self._bump()

    def _accept(self, name: str) -> None:
        node = self._state["nodes"][name]
        node["status"], node["reason_code"] = "ACCEPTED", "RESULT_VERIFIED"
        node["accepted_result_ref"] = deepcopy(node["candidate_result_ref"])
        if name == "A":
            dependent = self._state["nodes"]["B"]
            dependent["parent_result_ref"] = deepcopy(node["accepted_result_ref"])
            dependent["effect_id"] = dag_effect_id(namespace=self._state["namespace"],
                workflow_id=self._state["workflow_id"], node_id="B",
                parent_result_sha256=node["accepted_result_ref"]["sha256"])
            self._state["mission_status"], self._state["admission_closed"] = "RUNNING", False
        else:
            self._state["mission_status"], self._state["admission_closed"] = "COMPLETED", True
        self._bump()

    def _inspection_request(self, name: str, mode: str,
                            update: dict[str, Any] | None = None) -> dict[str, Any]:
        request = self._step_request(name)
        request.update(schema_version="opendot.temporal.dag-inspect.v1", mode=mode,
            expected_revision=self._state["revision"],
            candidate_result_ref=deepcopy(self._state["nodes"][name]["candidate_result_ref"]),
            original_evidence_sha256=update["original_evidence_sha256"] if update else None,
            original_result_sha256=update["original_result_sha256"] if update else None)
        return request

    def _inspection_response(self, value: object, request: dict[str, Any]) -> dict[str, Any]:
        _dag_shape(value, frozenset({"schema_version", "effect_id", "mode", "expected_revision",
            "status", "reason_code", "result_ref", "input_payload_sha256", "output",
            "original_evidence_sha256"}))
        _dag_check(type(value["schema_version"]) is str
                   and value["schema_version"] == "opendot.temporal.dag-inspection.v1", "INSPECTION_SCHEMA")
        for key in ("effect_id", "mode", "original_evidence_sha256"):
            _dag_check(type(value[key]) is type(request[key]) and value[key] == request[key],
                       "INSPECTION_BINDING")
        _dag_check(type(value["expected_revision"]) is int
                   and value["expected_revision"] == request["expected_revision"], "STATE_REVISION")
        _dag_check(type(value["status"]) is str and value["status"] in _DAG_INSPECTION_REASONS,
                   "INSPECTION_STATUS")
        _dag_check(type(value["reason_code"]) is str
                   and value["reason_code"] in _DAG_INSPECTION_REASONS[value["status"]], "INSPECTION_REASON")
        ref = _dag_validate_reference(value["result_ref"], seed_ref=request["seed_ref"],
            effect_id=request["effect_id"], parent_result_ref=request["parent_result_ref"])
        _dag_check(ref == request["candidate_result_ref"], "INSPECTION_REFERENCE")
        _dag_check(type(value["input_payload_sha256"]) is str
                   and value["input_payload_sha256"] == DAG_INPUT_SHA256[request["node_id"]], "INPUT_PIN")
        _dag_check((type(value["output"]) is int and value["output"] == {"A": 5, "B": 6}[request["node_id"]])
                   if value["status"] == "CONSISTENT_COMPLETED" else value["output"] is None,
                   "OUTPUT_PIN")
        _dag_check(len(_dag_canonical(value)) <= 4096, "RESPONSE_SIZE")
        return deepcopy(value)

    async def _inspect(self, name: str, mode: str,
                       update: dict[str, Any] | None = None) -> None:
        request = self._inspection_request(name, mode, update)
        revision = self._state["revision"]
        kind, value = await self._command(DAG_INSPECT_ACTIVITY_NAME, request,
            "dag2-inspect-" + mode + "-" + request["effect_id"][7:], revision)
        if kind == "CLOSED" or not self._current(revision):
            return
        if kind == "ERROR":
            self._unknown(name, "INSPECTION_FAILED", exhausted=mode == "reconcile")
            return
        try:
            result = self._inspection_response(value, request)
        except Exception:
            self._unknown(name, "RESPONSE_INVALID", exhausted=mode == "reconcile")
            return
        if not self._current(revision):
            return
        if result["status"] == "CONSISTENT_COMPLETED":
            self._accept(name)
        elif result["status"] == "CONSISTENT_REJECTED":
            self._reject(name, result["reason_code"])
        else:
            self._unknown(name, result["reason_code"], exhausted=mode == "reconcile")

    async def _wait_unknown(self, name: str) -> None:
        if self._state["nodes"][name]["status"] != "UNKNOWN" or not self._gate():
            return
        try:
            await workflow.wait_condition(lambda: (
                self._state["nodes"][name]["status"] in {"ACCEPTED", "REJECTED"}
                or self._state["mission_status"] in _DAG_TERMINAL
                or workflow.cancellation_reason() is not None), timeout=self._remaining())
            self._gate()
        except TimeoutError:
            self._close("OBSERVATION_DEADLINE")

    async def _run_node(self, name: str) -> None:
        node = self._state["nodes"][name]
        if (not self._gate() or self._state["admission_closed"]
                or node["status"] != "WAITING" or node["execute_reserved"]):
            return
        if name == "B" and self._state["nodes"]["A"]["status"] != "ACCEPTED":
            return
        if not self._reserve(name, "execute"):
            return
        node["status"], node["reason_code"] = "EXECUTING", "EXECUTING"
        self._bump()
        revision = self._state["revision"]
        request = self._step_request(name)
        kind, value = await self._command(DAG_ACTIVITY_NAME, request,
            "dag2-execute-" + node["effect_id"][7:], revision)
        if kind == "CLOSED" or not self._current(revision):
            return
        if kind == "ERROR":
            if self._known_input_refusal(value):
                self._reject(name, "TOOL_REJECTED")
            else:
                self._unknown(name, "EXECUTION_UNKNOWN")
        else:
            try:
                _dag_shape(value, frozenset({"schema_version", "effect_id", "result_ref"}))
                _dag_check(type(value["schema_version"]) is str
                           and value["schema_version"] == "opendot.temporal.dag-step-response.v1"
                           and type(value["effect_id"]) is str
                           and value["effect_id"] == node["effect_id"], "STEP_RESPONSE")
                candidate = _dag_validate_reference(value["result_ref"],
                    seed_ref=self._state["seed_ref"], effect_id=node["effect_id"],
                    parent_result_ref=node["parent_result_ref"])
                _dag_check(len(_dag_canonical(value)) <= 4096, "RESPONSE_SIZE")
            except Exception:
                self._unknown(name, "RESPONSE_INVALID")
            else:
                node["candidate_result_ref"] = candidate
                if self._reserve(name, "normal_inspect"):
                    await self._inspect(name, "normal")
        await self._wait_unknown(name)

    def _parse_update(self, request: object) -> dict[str, Any]:
        _dag_shape(request, _DAG_UPDATE_FIELDS)
        _dag_check(type(request["schema_version"]) is str
                   and request["schema_version"] == "opendot.temporal.dag-reconcile.v1", "UPDATE_SCHEMA")
        _dag_check(type(request["node_id"]) is str and request["node_id"] in {"A", "B"}, "NODE_ID")
        _dag_check(type(request["effect_id"]) is str and request["effect_id"].startswith("sha256:")
                   and _dag_hex(request["effect_id"][7:]), "EFFECT_ID")
        _dag_check(type(request["expected_revision"]) is int
                   and 1 <= request["expected_revision"] <= 64, "STATE_REVISION")
        _dag_check(_dag_hex(request["original_evidence_sha256"])
                   and _dag_hex(request["original_result_sha256"]), "ORIGIN_DIGEST")
        _dag_reference_fields(request["candidate_result_ref"], 16384)
        _dag_check(len(_dag_canonical(request)) <= 4096, "REQUEST_SIZE")
        return deepcopy(request)

    def _update_refusal(self, request: dict[str, Any], *, mutate: bool) -> str | None:
        state = self._state
        if state is None:
            return "TERMINAL_CLOSED"
        if workflow.cancellation_reason() is not None or state["cancel_requested"]:
            if mutate:
                self._close("CANCELLED", cancelled=True)
            return "CANCELLED"
        if self._remaining() <= 0:
            if mutate:
                self._close("OBSERVATION_DEADLINE")
            return "OBSERVATION_DEADLINE"
        if state["mission_status"] in _DAG_TERMINAL:
            return "TERMINAL_CLOSED"
        if any(row["status"] == "VERIFYING" for row in state["nodes"].values()):
            return "INSPECTION_BUSY"
        if request["expected_revision"] != state["revision"]:
            return "STALE_REVISION"
        node = state["nodes"][request["node_id"]]
        if request["effect_id"] != node["effect_id"]:
            return "EFFECT_MISMATCH"
        if node["status"] != "UNKNOWN":
            return "STATE_NOT_UNKNOWN"
        if node["reconcile_inspect_reserved"] or state["resources"]["activity_commands_used"] >= 6:
            return "INSPECTION_EXHAUSTED"
        if node["candidate_result_ref"] is not None and request["candidate_result_ref"] != node["candidate_result_ref"]:
            return "CONFLICTING_CANDIDATE"
        return None

    def _update_result(self, request: dict[str, Any], status: str,
                       reason: str) -> dict[str, Any]:
        node = self._state["nodes"][request["node_id"]]
        result = {"schema_version": "opendot.temporal.dag-reconciliation.v1",
            "node_id": request["node_id"], "effect_id": request["effect_id"],
            "status": status, "reason_code": reason, "revision": self._state["revision"],
            "mission_status": self._state["mission_status"],
            "accepted_result_ref": deepcopy(node["accepted_result_ref"])
                if node["status"] == "ACCEPTED" else None}
        _dag_check(len(_dag_canonical(result)) <= 4096, "RESPONSE_SIZE")
        return result

    @workflow.update(name="reconcile_result")
    async def reconcile_result(self, request: dict[str, Any]) -> dict[str, Any]:
        try:
            request = self._parse_update(request)
        except Exception:
            raise ApplicationError("TemporalDagUpdateRejected", "INVALID_FIELDS",
                type="TemporalDagUpdateRejected", non_retryable=True) from None
        refusal = self._update_refusal(request, mutate=True)
        if refusal is not None:
            return self._update_result(request, "REFUSED", refusal)
        name = request["node_id"]
        node = self._state["nodes"][name]
        try:
            candidate = _dag_validate_reference(request["candidate_result_ref"],
                seed_ref=self._state["seed_ref"], effect_id=node["effect_id"],
                parent_result_ref=node["parent_result_ref"])
        except Exception:
            raise ApplicationError("TemporalDagUpdateRejected", "INVALID_FIELDS",
                type="TemporalDagUpdateRejected", non_retryable=True) from None
        node["candidate_result_ref"] = candidate
        if not self._reserve(name, "reconcile_inspect"):
            return self._update_result(request, "REFUSED", node["reason_code"])
        await self._inspect(name, "reconcile", request)
        self._gate()
        status = {"ACCEPTED": "ACCEPTED", "REJECTED": "REJECTED"}.get(node["status"], "UNRESOLVED")
        return self._update_result(request, status, node["reason_code"])

    @reconcile_result.validator
    def validate_reconcile_result(self, request: dict[str, Any]) -> None:
        try:
            request = self._parse_update(request)
            refusal = self._update_refusal(request, mutate=False)
            if refusal is not None:
                raise ValueError(refusal)
            node = self._state["nodes"][request["node_id"]]
            _dag_validate_reference(request["candidate_result_ref"], seed_ref=self._state["seed_ref"],
                effect_id=node["effect_id"], parent_result_ref=node["parent_result_ref"])
        except Exception:
            raise ApplicationError("TemporalDagUpdateRejected", "UPDATE_REFUSED",
                type="TemporalDagUpdateRejected", non_retryable=True) from None

    async def _finish(self) -> dict[str, Any]:
        self._gate()
        if workflow.all_handlers_finished():
            return self.dag_state()
        self._cancel_active()
        remaining = min(1.0, self._remaining())
        try:
            if remaining > 0:
                await workflow.wait_condition(workflow.all_handlers_finished, timeout=remaining)
            self._gate()
            if workflow.all_handlers_finished():
                return self.dag_state()
        except CancelledError:
            if (workflow.cancellation_reason() is None and not self._state["cancel_requested"]
                    and self._remaining() > 0):
                # Terminal drain is still SDK control flow during cache eviction.
                # Preserve the same completed/closed projection and exception.
                raise
            self._gate()
        except TimeoutError:
            self._gate()
        # Explicit unresolved failure, never a successful abandoned Update.
        if self._state["mission_status"] != "STOPPED_WITH_UNKNOWN":
            self._state["mission_status"] = "STOPPED_WITH_UNKNOWN"
            self._state["admission_closed"] = True
            self._bump()
        raise ApplicationError("DAG_HANDLERS_UNFINISHED", self.dag_state(),
            type="DAG_HANDLERS_UNFINISHED", non_retryable=True)

    @workflow.run
    async def run(self, request: dict[str, Any]) -> dict[str, Any]:
        try:
            self._initialize(request)
        except Exception:
            raise ApplicationError("TemporalDagStartRejected", "START_REFUSED",
                type="TemporalDagStartRejected", non_retryable=True) from None
        try:
            await self._run_node("A")
            if self._gate() and self._state["nodes"]["A"]["status"] == "ACCEPTED":
                await self._run_node("B")
        except CancelledError:
            if (workflow.cancellation_reason() is None and not self._state["cancel_requested"]
                    and self._remaining() > 0
                    and self._state["mission_status"] not in _DAG_TERMINAL):
                raise
            self._gate()
            self._cancel_active()
        return await self._finish()
