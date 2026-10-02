"""Optional, offline-prepared A2A 1.0 code-candidate seam (ADR 007).

Trusted bootstrap supplies the sole transport callback, canonical runtime/store,
and independent pins. No network client, code execution, acceptance or recovery.
"""
from __future__ import annotations

import base64
import binascii
import json
from typing import Callable

from ..core.artifacts import ArtifactIntegrityError, ArtifactStore
from ..core.contracts import ArtifactRef
from ..tool_runtime import ToolCallReceipt, ToolRisk, ToolRuntime, ToolSpec
from .source_audit import (
    AuditRejected, _decode, _hash, _identifier, _keys, _relative, _require, _sha256,
)

TOOL_ID = "external_worker.code_candidate.v1"
PROFILE_SHA256 = "1af48e2d14636a762dc2cc056de3b54b82bcccac26f21966891a7610228d52bb"
REGISTRATION_SHA256 = "3160d0f0ec1b49efe5f58de13ca07c012a46b31b3025f170a0f757ab2ba5e043"
MAX_FILE_BYTES = 32768
MAX_TASK_BYTES = 4096
MAX_EXPLANATION_BYTES = 2048
MAX_WIRE_BYTES = 131072
MAX_RESULT_BYTES = 196608
PRODUCER = "opendot.a2a-worker-turn.v1"
# Authored application profile, not a copied protocol schema or authority grant.
_PROFILE_JSON = b'{"acceptance_profile":"external-code-review.v1","access":"public","allowed_tools":[],"binding":"JSON-RPC","input_paths":["parser.py","test_parser.txt"],"limits":{"explanation_bytes":2048,"input_file_bytes":32768,"input_files":2,"output_file_bytes":32768,"output_files":1,"request_bytes":131072,"response_bytes":131072,"result_bytes":196608,"task_bytes":4096},"name":"code_candidate.v1","output_path":"parser.py","protocol":"A2A","protocol_version":"1.0","release":"1.0.0","requested_budgets":{"cost":{"amount":"0.00","currency":"USD"},"deadline_seconds":45,"max_input_tokens":8192,"max_model_requests":1,"max_output_tokens":4096,"max_tool_calls":0},"role":"synthetic","worker_id":"operator.public-synthetic.v1"}'


def _encode(value: object, limit: int) -> bytes:
    try:
        data = json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise AuditRejected("INVALID_ENCODING") from None
    _require(len(data) <= limit, "ENCODED_SIZE")
    return data


def _text_bytes(value: object, limit: int, *, nonempty: bool = False) -> bytes:
    _require(type(value) is str, "INVALID_TEXT")
    try:
        data = value.encode("utf-8")
    except UnicodeError:
        raise AuditRejected("INVALID_ENCODING") from None
    _require(len(data) <= limit and (not nonempty or len(data) > 0), "TEXT_SIZE")
    return data


def _profile() -> dict:
    # Fresh plain objects prevent payload mutation from changing later requests.
    _require(_sha256(_PROFILE_JSON) == PROFILE_SHA256, "PROFILE_IMPLEMENTATION_PIN")
    return _decode(_PROFILE_JSON)


def _validate_input(document: object) -> None:
    _keys(document, {"schema", "profile_sha256", "task_id", "task", "task_sha256", "snapshot"})
    _require(document["schema"] == "opendot.a2a-worker-turn.input.v1", "INPUT_SCHEMA")
    _require(document["profile_sha256"] == PROFILE_SHA256, "PROFILE_PIN")
    _identifier(document["task_id"])
    task = _text_bytes(document["task"], MAX_TASK_BYTES, nonempty=True)
    _hash(document["task_sha256"], 64)
    _require(_sha256(task) == document["task_sha256"], "TASK_PIN")
    snapshot = document["snapshot"]
    _keys(snapshot, {"id", "sha256", "files"})
    _identifier(snapshot["id"])
    _hash(snapshot["sha256"], 64)
    files = snapshot["files"]
    _require(type(files) is list and len(files) == 2, "INPUT_FILE_COUNT")
    for record, path in zip(files, ("parser.py", "test_parser.txt")):
        _keys(record, {"path", "sha256", "size_bytes", "artifact_id"})
        _relative(record["path"])
        _require(record["path"] == path, "INPUT_PATH")
        _hash(record["sha256"], 64)
        _require(record["artifact_id"] == "sha256:" + record["sha256"], "INPUT_ARTIFACT_ID")
        _require(type(record["size_bytes"]) is int
                 and 0 <= record["size_bytes"] <= MAX_FILE_BYTES, "INPUT_FILE_SIZE")
    _require(_sha256(_encode(files, MAX_WIRE_BYTES)) == snapshot["sha256"], "SNAPSHOT_PIN")


def _request(payload: object) -> bytes:
    _keys(payload, {"input_sha256", "input", "files"})
    _validate_input(payload["input"])
    _hash(payload["input_sha256"], 64)
    _require(_sha256(_encode(payload["input"], MAX_WIRE_BYTES)) == payload["input_sha256"],
             "INPUT_PIN")
    _require(type(payload["files"]) is list and len(payload["files"]) == 2, "INPUT_FILE_COUNT")
    for file, record in zip(payload["files"], payload["input"]["snapshot"]["files"]):
        _keys(file, {"path", "sha256", "size_bytes", "artifact_id", "text"})
        # Compare serialized field types too: bool/float must not equal an int.
        _require(_encode({k: file[k] for k in record}, MAX_WIRE_BYTES)
                 == _encode(record, MAX_WIRE_BYTES), "SOURCE_BINDING")
        data = _text_bytes(file["text"], MAX_FILE_BYTES)
        _require(len(data) == record["size_bytes"] and _sha256(data) == record["sha256"],
                 "SOURCE_BYTES")
    task_id = payload["input"]["task_id"]
    return _encode({
        "jsonrpc": "2.0", "id": task_id, "method": "SendMessage",
        "params": {"message": {
            "messageId": task_id, "role": "ROLE_USER", "parts": [{
                "data": {"profile": _profile(), **payload}, "mediaType": "application/json",
            }],
        }, "configuration": {"acceptedOutputModes": ["application/json"],
                             "historyLength": 0, "returnImmediately": False}},
    }, MAX_WIRE_BYTES)


def _envelope_bytes(envelope: object) -> bytes | None:
    _keys(envelope, {"request_sha256", "status", "callback_invocations",
                     "response_b64", "response_sha256"})
    _hash(envelope["request_sha256"], 64)
    _require(type(envelope["callback_invocations"]) is int
             and envelope["callback_invocations"] == 1, "ENVELOPE_COUNT")
    if envelope["status"] in ("RESPONSE_TOO_LARGE", "RESPONSE_NOT_BYTES"):
        _require(envelope["response_b64"] is None and envelope["response_sha256"] is None,
                 "ENVELOPE_FIELDS")
        return None
    _require(envelope["status"] == "RETURNED_BYTES", "ENVELOPE_STATUS")
    encoded = envelope["response_b64"]
    _require(type(encoded) is str and len(encoded) <= 4 * ((MAX_WIRE_BYTES + 2) // 3),
             "ENVELOPE_SIZE")
    _hash(envelope["response_sha256"], 64)
    try:
        data = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise AuditRejected("ENVELOPE_ENCODING") from None
    _require(len(data) <= MAX_WIRE_BYTES, "RESPONSE_TOO_LARGE")
    _require(base64.b64encode(data).decode("ascii") == encoded, "ENVELOPE_ENCODING")
    _require(_sha256(data) == envelope["response_sha256"], "ENVELOPE_HASH")
    return data


def transport_envelope_valid(output: object) -> bool:
    """Local finite envelope validity only; remote bytes remain uninterpreted."""
    try:
        _envelope_bytes(output)
        return True
    except (AuditRejected, TypeError):
        return False


WORKER_SPEC = ToolSpec(
    tool_id=TOOL_ID, version="1", input_schema="opendot.a2a-worker-turn.dispatch.v1",
    output_schema="opendot.a2a-worker-turn.envelope.v1", risk=ToolRisk.IRREVERSIBLE_WRITE,
    timeout_s=60.0, max_retries=0, idempotent=False,
    permissions=frozenset({"external-worker:invoke"}),
    semantic_validator=transport_envelope_valid,
)


def make_worker_handler(exchange: Callable, *, worker_profile_sha256: str) -> Callable:
    """Bind one trusted callback, without storing or authenticating its closure.

    exchange(request_bytes, *, protocol_version, max_response_bytes, timeout_s)
    returns bytes. No HTTP/SDK/version negotiation/retry is supplied here.
    The timeout and acquisition limit are requests to the callback, not guarantees.
    """
    _require(callable(exchange), "TRANSPORT_REQUIRED")
    _require(worker_profile_sha256 == PROFILE_SHA256, "PROFILE_PIN")

    def handler(payload: dict) -> dict:
        request = _request(payload)
        response = exchange(request, protocol_version="1.0",
                            max_response_bytes=MAX_WIRE_BYTES, timeout_s=45)
        # The callback may already have acquired an oversized body. Refuse before
        # base64 allocation or JSON parsing; never return/store over-cap bytes.
        status = ("RESPONSE_NOT_BYTES" if type(response) is not bytes else
                  "RESPONSE_TOO_LARGE" if len(response) > MAX_WIRE_BYTES else "RETURNED_BYTES")
        return {"request_sha256": _sha256(request), "status": status,
                "callback_invocations": 1,
                "response_b64": base64.b64encode(response).decode("ascii")
                    if status == "RETURNED_BYTES" else None,
                "response_sha256": _sha256(response) if status == "RETURNED_BYTES" else None}

    return handler


def _ref_record(ref: ArtifactRef | None) -> dict | None:
    if ref is None:
        return None
    return {"artifact_id": ref.artifact_id, "sha256": ref.sha256,
            "size_bytes": ref.size_bytes, "mime_type": ref.mime_type}


def _candidate(response: bytes, document: dict, input_sha256: str) -> tuple[bytes | None, str]:
    # Called only after the bounded exact raw bytes have reached canonical CAS.
    message = _decode(response)
    _require(type(message) is dict, "RESPONSE_FIELDS")
    if "error" in message:
        _keys(message, {"jsonrpc", "id", "error"})
    else:
        _keys(message, {"jsonrpc", "id", "result"})
    _require(message["jsonrpc"] == "2.0" and message["id"] == document["task_id"],
             "RESPONSE_BINDING")
    if "error" in message:
        _keys(message["error"], {"code", "message"})
        _require(type(message["error"]["code"]) is int, "ERROR_CODE")
        _text_bytes(message["error"]["message"], MAX_EXPLANATION_BYTES)
        return None, "WORKER_REPORTED_ERROR"
    _keys(message["result"], {"task"})
    task = message["result"]["task"]
    _require(type(task) is dict and set(task) in ({"id", "status"}, {"id", "status", "artifacts"}),
             "TASK_FIELDS")
    _identifier(task["id"])
    _keys(task["status"], {"state"})
    state = task["status"]["state"]
    states = {"TASK_STATE_COMPLETED", "TASK_STATE_FAILED", "TASK_STATE_CANCELED",
              "TASK_STATE_REJECTED", "TASK_STATE_INPUT_REQUIRED", "TASK_STATE_AUTH_REQUIRED",
              "TASK_STATE_SUBMITTED", "TASK_STATE_WORKING", "TASK_STATE_UNSPECIFIED"}
    _require(type(state) is str and state in states, "TASK_STATE")
    if state != "TASK_STATE_COMPLETED":
        _require("artifacts" not in task, "NONCOMPLETED_ARTIFACTS")
        # These are worker claims; no binding completion/cost/stop is inferred.
        return None, "WORKER_REPORTED_" + state.removeprefix("TASK_STATE_")
    artifacts = task.get("artifacts")
    _require(type(artifacts) is list and len(artifacts) == 1, "ARTIFACT_COUNT")
    artifact = artifacts[0]
    _keys(artifact, {"artifactId", "parts"})
    _identifier(artifact["artifactId"])
    _require(type(artifact["parts"]) is list and len(artifact["parts"]) == 1, "PART_COUNT")
    part = artifact["parts"][0]
    _keys(part, {"data", "mediaType"})
    _require(part["mediaType"] == "application/json", "PART_MEDIA_TYPE")
    candidate = part["data"]
    _keys(candidate, {"profile_sha256", "input_sha256", "task_id", "task_sha256",
                      "snapshot_id", "snapshot_sha256", "worker_id", "acceptance_profile",
                      "path", "original_sha256", "text", "sha256", "explanation"})
    profile = _profile()
    expected = {"profile_sha256": PROFILE_SHA256, "input_sha256": input_sha256,
                "task_id": document["task_id"], "task_sha256": document["task_sha256"],
                "snapshot_id": document["snapshot"]["id"],
                "snapshot_sha256": document["snapshot"]["sha256"],
                "worker_id": profile["worker_id"], "acceptance_profile": profile["acceptance_profile"],
                "path": "parser.py", "original_sha256": document["snapshot"]["files"][0]["sha256"]}
    _relative(candidate["path"])
    _require(all(type(candidate[k]) is str and candidate[k] == v for k, v in expected.items()),
             "CANDIDATE_BINDING")
    data = _text_bytes(candidate["text"], MAX_FILE_BYTES)
    _text_bytes(candidate["explanation"], MAX_EXPLANATION_BYTES)
    _hash(candidate["sha256"], 64)
    _require(_sha256(data) == candidate["sha256"], "CANDIDATE_HASH")
    return data, "BOUND_CANDIDATE"


def run_worker_turn(*, runtime: ToolRuntime, store: ArtifactStore, input_ref: ArtifactRef,
                    expected_input_sha256: str, expected_profile_sha256: str,
                    expected_registration_sha256: str,
                    granted_permissions: frozenset[str] = frozenset(),
                    approval_token: str | None = None) -> tuple[ArtifactRef | None, ToolCallReceipt, dict]:
    """One canonical dispatch; return (result_ref, original receipt, safe report).

    Pre-dispatch input errors raise AuditRejected. Runtime/control exceptions
    propagate untouched. Publication errors return UNKNOWN and known references.
    There is no automatic retry or candidate publication after a late completion.
    """
    _require(type(runtime) is ToolRuntime and type(store) is ArtifactStore, "OWNER_IDENTITY")
    _require(type(input_ref) is ArtifactRef, "REFERENCE_IDENTITY")
    _hash(expected_input_sha256, 64)
    _require(expected_profile_sha256 == PROFILE_SHA256, "PROFILE_PIN")
    _require(expected_registration_sha256 == REGISTRATION_SHA256
             and runtime.registration_signature(TOOL_ID) == expected_registration_sha256,
             "REGISTRATION_PIN")
    _require(input_ref.sha256 == expected_input_sha256
             and input_ref.artifact_id == "sha256:" + expected_input_sha256
             and input_ref.uri == "artifact://sha256/" + expected_input_sha256
             and input_ref.mime_type == "application/json"
             and type(input_ref.size_bytes) is int and 0 < input_ref.size_bytes <= MAX_WIRE_BYTES,
             "INPUT_REFERENCE")
    raw_input = store.get_bytes(input_ref, max_bytes=MAX_WIRE_BYTES)
    _require(len(raw_input) == input_ref.size_bytes, "INPUT_LENGTH")
    document = _decode(raw_input)
    _validate_input(document)
    # Canonical encoding is part of this input profile, making its wire pin exact.
    _require(_encode(document, MAX_WIRE_BYTES) == raw_input, "INPUT_ENCODING")
    files = []
    for record in document["snapshot"]["files"]:
        data = store.get_bytes(record["artifact_id"], max_bytes=MAX_FILE_BYTES)
        _require(len(data) == record["size_bytes"], "SOURCE_LENGTH")
        try:
            text = data.decode("utf-8")
        except UnicodeError:
            raise AuditRejected("SOURCE_ENCODING") from None
        files.append({**record, "text": text})
    payload = {"input_sha256": expected_input_sha256, "input": document, "files": files}
    request = _request(payload)
    # Do not wrap: the canonical deny-only guard's original exception must escape.
    output, receipt = runtime.execute(TOOL_ID, payload, granted_permissions=granted_permissions,
                                      approval_token=approval_token, attempt_limit=1)
    report = {
        "schema": "opendot.a2a-worker-turn.result.v1", "status": "UNKNOWN",
        "code": "RUNTIME_OUTCOME_UNKNOWN", "acceptance": "UNACCEPTED",
        "code_execution": "NOT_PERFORMED", "live_model_validation": "NOT_EVALUATED",
        "scientific_accepted": False, "device_control_authorized": False,
        "independent_review": "NOT_EVALUATED", "remote_spend": "NOT_ESTABLISHED",
        "remote_model_requests": "NOT_ESTABLISHED", "remote_termination": "NOT_ESTABLISHED",
        "task_id": document["task_id"], "task_sha256": document["task_sha256"],
        "snapshot_sha256": document["snapshot"]["sha256"], "profile_sha256": PROFILE_SHA256,
        "input_sha256": expected_input_sha256, "wire_request_sha256": _sha256(request),
        "raw_response": None, "candidate": None, "callback_invocations": None,
        "local_receipt": {"call_id": receipt.call_id, "status": receipt.status,
                          "attempts": receipt.attempts, "input_hash": receipt.input_hash,
                          "output_hash": receipt.output_hash,
                          "transport_envelope_valid": receipt.semantic_valid},
    }
    raw_ref = candidate_ref = None
    try:
        if receipt.status == "BLOCKED":
            report.update(status="BLOCKED", code="RUNTIME_BLOCKED", callback_invocations=0)
        elif receipt.status == "COMPLETED" and receipt.semantic_valid:
            data = _envelope_bytes(output)
            _require(output["request_sha256"] == report["wire_request_sha256"], "REQUEST_BINDING")
            report["callback_invocations"] = 1
            if data is None:
                report["code"] = output["status"]
            else:
                raw_ref = store.put_bytes(data, mime_type="application/octet-stream",
                                          producer=PRODUCER, task_id=document["task_id"],
                                          source_refs=(input_ref.artifact_id,))
                report["raw_response"] = _ref_record(raw_ref)
                candidate, code = _candidate(data, document, expected_input_sha256)
                report["code"] = code
                if candidate is not None:
                    candidate_ref = store.put_bytes(candidate, mime_type="text/plain; charset=utf-8",
                                                    producer=PRODUCER, task_id=document["task_id"],
                                                    source_refs=(input_ref.artifact_id, raw_ref.artifact_id))
                    report.update(status="CANDIDATE", candidate=_ref_record(candidate_ref))
    except AuditRejected as exc:
        report.update(status="UNKNOWN", code=exc.code)
    except (OSError, ArtifactIntegrityError, ValueError, TypeError):
        report.update(status="UNKNOWN", code="PUBLICATION_FAILED")
    try:
        encoded = _encode(report, MAX_RESULT_BYTES)
        sources = tuple(ref.artifact_id for ref in (input_ref, raw_ref, candidate_ref) if ref is not None)
        result_ref = store.put_bytes(encoded, mime_type="application/json", producer=PRODUCER,
                                     task_id=document["task_id"], source_refs=sources)
    except (OSError, ArtifactIntegrityError, ValueError, TypeError):
        report.update(status="UNKNOWN", code="RESULT_PUBLICATION_FAILED")
        result_ref = None
    return result_ref, receipt, report
