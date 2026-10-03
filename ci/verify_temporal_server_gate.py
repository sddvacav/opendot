"""Strict, stdlib-only verifier for the optional real-server gate.

Unit-test records exercise this verifier; they are never real-server evidence.
Only independently validated bounded diagnostics may be exposed on failure.
No raw failed records, JUnit diagnostics, or exception text is exposed.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import tempfile
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "opendot.temporal.server-gate."
SCENARIOS = ("durability_replay", "null", "blocked", "failed_validation", "missing_input")
NODE_NAMES = (
    "test_real_received_metadata_and_valid_output",
    "test_queued_activity_survives_graceful_server_restart",
    "test_recorded_result_replays_without_handler_reentry",
    "test_completed_null_output_is_preserved",
    "test_blocked_tool_is_not_promoted_to_success",
    "test_failed_tool_is_not_promoted_to_success",
    "test_input_failure_is_transport_failure_without_dispatch",
)
REQUIRED_NODES = tuple("tests/acceptance/temporal_server_gate.py::" + n for n in NODE_NAMES)
OUTCOME_NAMES = ("PASS", "FAIL", "ERROR", "SKIP", "NOT_RUN")
CODES = frozenset({
    "OK", "MISSING_EVIDENCE", "READ_FAILED", "SIZE_LIMIT", "INVALID_JSON",
    "INVALID_SCHEMA", "INVALID_TYPE", "INVALID_VALUE", "PRIVACY_REJECTED",
    "REQUIRED_NODES", "COLLECTION_MISMATCH", "MISSING_JUNIT", "INVALID_JUNIT",
    "JUNIT_IDENTITY", "DUPLICATE_NODE", "UNEXPECTED_NODE", "TEST_FAILED",
    "TEST_ERROR", "TEST_SKIPPED", "NOT_RUN", "REVISION_MISMATCH", "CI_IDENTITY",
    "SOURCE_MISMATCH", "OWNER_MISMATCH", "VERSION_MISMATCH", "PIN_MISMATCH",
    "PREFLIGHT_FAILED", "METADATA_MISMATCH", "COUNTER_MISMATCH", "OUTCOME_MISMATCH",
    "HISTORY_MISMATCH", "HISTORY_LINKAGE", "REPLAY_MISMATCH", "CLEANUP_UNCONFIRMED",
    "INTERNAL_ERROR", "WRITE_FAILED", "ACQUISITION_UNVERIFIED",
    "DIAGNOSTIC_INVALID", "DIAGNOSTIC_UNAVAILABLE", "DIAGNOSTIC_FAILED",
})
DIAGNOSTIC_MAX_BYTES = 4096
DIAGNOSTIC_PHASES = frozenset({
    "preflight", "sdk_binding", "input_seeding", "server_launch", "client_connect",
    "server_readiness", "workflow_worker_start", "activity_worker_start", "workflow_submit",
    "history_read", "history_project", "result_query", "result_verify", "worker_shutdown",
    "server_shutdown", "workflow_signal", "workflow_result", "sdk_replay", "audit_write",
    "cleanup", "complete",
})
DIAGNOSTIC_GATE_REASONS = frozenset("""
    ACTIVITY_COMPLETION ACTIVITY_NOT_QUIESCENT CAS_INTEGRITY CI_REQUIRED CLEANUP_HISTORY
    CLEANUP_UNCONFIRMED CLIENT_CONNECT CLI_FILE CLI_FILE_HASH CLI_PIN CLI_RECEIPT
    DEPENDENCY_VERSION DIRTY_SOURCE DUPLICATE_JSON_KEY EXECUTION_NOT_ENABLED FAILURE_CATEGORY
    FRACTIONAL_TIMEOUT FRESH_GATE_ROOT_REQUIRED GATE_DEADLINE HISTORY_DEADLINE HISTORY_READ
    HISTORY_SIZE JSONL_SIZE JSON_SIZE NONFINITE_JSON NOT_QUIESCENT OWNER_HASH PLATFORM
    PREVIOUS_STOP_UNCONFIRMED QUERY_DEADLINE QUERY_NOT_READY QUEUED_ACTIVITY_STARTED
    QUEUED_COUNTERS QUEUED_DURABILITY QUEUED_PHASE_DEADLINE REPLAY_HISTORY_HASH REPLAY_REFERENCE
    RESPONSE_PAYLOAD RESPONSE_SCHEMA RESULT_INPUT_REFERENCE RESULT_OUTPUT_PROFILE
    RESULT_RECEIPT_IDENTITY RESULT_RECEIPT_SCHEMA RESULT_REFERENCE RESULT_SCHEMA REVISION
    RUNNER_TEMP_REQUIRED RUN_IDENTITY SCENARIO SDK_REPLAY SDK_WHEEL_HASH SDK_WHEEL_REPORT
    SERVER_EXITED SERVER_GATE_FAILED SERVER_READINESS SERVER_STOP_UNCONFIRMED SERVER_VERSION
    SIGNAL_DEADLINE TRANSPORT_FAILURE_EXPECTED UNEXPECTED_HISTORY_EVENT UNEXPECTED_NEW_RUN
    WORKER_STOP_UNCONFIRMED WORKFLOW_REFERENCE WORKFLOW_RESULT WORKFLOW_START
""".split())
DIAGNOSTIC_GENERIC_REASONS = {
    "dependency_error": "DEPENDENCY_ERROR", "type_error": "TYPE_ERROR",
    "value_error": "VALUE_ERROR", "attribute_error": "ATTRIBUTE_ERROR",
    "key_error": "KEY_ERROR", "os_error": "OS_ERROR", "timeout_error": "TIMEOUT_ERROR",
    "sdk_error": "SDK_ERROR", "unknown_error": "UNKNOWN_ERROR",
}
DIAGNOSTIC_REASON_CODES = DIAGNOSTIC_GATE_REASONS | frozenset(DIAGNOSTIC_GENERIC_REASONS.values())
DIAGNOSTIC_EXCEPTION_CATEGORIES = frozenset(DIAGNOSTIC_GENERIC_REASONS) | {"gate_refusal"}
OWNER_SHA256 = {
    "src/opendot_engineering/tool_runtime.py": "7c5011e02b2cf07e5f15ad7854905ce0738271e167b873bad9256a8ed169199c",
    "src/opendot_engineering/core/artifacts.py": "4606b7b11a81044267b30fee332d9b6fd6540d862726a9579655ee27c7d9a883",
    "src/opendot_engineering/core/contracts.py": "9462415baf84668825ad2c8cfc3f4f3df68332f65d1f1f4b301fbf01cf8537ca",
}
SDK_VERSIONS = {"temporalio": "1.34.0", "nexus-rpc": "1.4.0", "protobuf": "7.36.2",
                "types-protobuf": "7.35.1.20260906", "typing_extensions": "4.16.0"}
TOOL_VERSIONS = {"pytest": "9.1.1", "iniconfig": "2.3.0", "packaging": "26.3",
                 "pluggy": "1.6.0", "Pygments": "2.21.0"}
SDK_WHEEL_SHA256 = "540761f738bdfe5cb5bd7240b659e116a0b5094b94282aef09b8d8c2d66e9c52"
CLI_ARCHIVE_SHA256 = "09a0326a51db84d02735e53542b9ebd8c4758daf47482a9ab0abce15844e60d5"
CLI_CHECKSUMS_SHA256 = "cc22cb0df0a9bab358500dce212616e8622b0649df68317d9858867d7dc69bd2"
SDK_HASHES = {
    "temporalio": SDK_WHEEL_SHA256,
    "nexus-rpc": "14c953d3519113f8ccec533a9efdb6b10c28afef75d11cdd6d422640c40b3a49",
    "protobuf": "89f23aa53c24553a2416fd4fd1ec06f74fa42b14b546d8883128813f775bbfd2",
    "types-protobuf": "5155e48569e0dabff303fdf578db96cd31ea9a4a63b18018a4ceac6b0ae17462",
    "typing_extensions": "481caa481374e813c1b176ada14e97f1f67a4539ce9cfeb3f350d78d6370c2e8",
}
TOOL_HASHES = {
    "pytest": "37a86b45efb9a47a61a36449063e8e18d0cab3161329fc099eb21783169c4f0c",
    "iniconfig": "f631c04d2c48c52b84d0d0549c99ff3859c98df65b3101406327ecc7d53fbf12",
    "packaging": "d7193f7c8e4e93f444fde0262bf90af30e16fa0ad0ad44cb553c87339b23cd1c",
    "pluggy": "e920276dd6813095e9377c0bc5566d94c932c33b27a3e3945d8389c374dd4746",
    "Pygments": "2363c69b61c4a97c838da3b130dcd6468f4848992b21a82f2a63ec34377137d9",
}
HARNESS_SOURCE_PATHS = (
    ".github/workflows/temporal-server.yml", "ci/acquire_temporal_cli.py",
    "ci/run_temporal_server_gate.py", "ci/verify_temporal_server_gate.py",
    "ci/temporal-sdk-requirements.txt", "ci/temporal-server-nodes.txt",
    "tests/acceptance/temporal_server_gate.py", "tests/test_temporal_cli_acquisition.py",
    "tests/test_temporal_server_harness_unit.py", "tests/test_temporal_server_gate_verifier.py",
)
SERVER_PROFILE = {"frontend_ip": "127.0.0.1", "grpc_port": 7233, "http_port": 7243,
                  "metrics_port": 9090, "ui_enabled": False, "sqlite_id": "server-db-1",
                  "cas_id": "cas-1", "credentials_supplied": False}
ACTIVITY_TYPE = "opendot.synthetic.reference.v1"
ACTIVITY_ID = "opendot-synthetic-reference-v1"
RESPONSE_SCHEMA = "opendot.temporal.response.v1"
COUNTER_EVENTS = ("activity_enter", "execute_enter", "handler_enter", "handler_return")
EXPECTED_COUNTS = dict(zip(SCENARIOS, ((1, 1, 1, 1), (1, 1, 1, 1), (1, 1, 0, 0),
                                     (1, 1, 1, 1), (1, 0, 0, 0))))
AUDIT_FILES = ("environment.json", "activity-metadata.jsonl", "history-projection.json",
               "invocation-counters.jsonl", "outcomes.json", "replay.json", "cleanup.json",
               "diagnostic.json")


class GateError(Exception):
    """An exception containing only one fixed public failure code."""
    def __init__(self, code: str):
        self.code = code if code in CODES else "INTERNAL_ERROR"
        super().__init__(self.code)


def require(condition: bool, code: str = "INVALID_VALUE") -> None:
    if not condition:
        raise GateError(code)


def exact(value: object, expected: object, code: str = "INVALID_VALUE") -> None:
    require(type(value) is type(expected) and value == expected, code)


def shape(value: object, keys: str | set[str], code: str = "INVALID_SCHEMA") -> None:
    expected = set(keys.split()) if isinstance(keys, str) else keys
    require(type(value) is dict and value.keys() == expected, code)


def integer(value: object, lo: int = 1, hi: int = 256, code: str = "INVALID_TYPE") -> None:
    require(type(value) is int and lo <= value <= hi, code)


def finite(value: object, hi: float, code: str = "INVALID_TYPE") -> None:
    require(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= hi, code)


def match(value: object, pattern: str, code: str = "PRIVACY_REJECTED") -> None:
    require(type(value) is str and len(value) <= 256 and re.fullmatch(pattern, value) is not None, code)


def digest(value: object) -> None:
    match(value, r"[0-9a-f]{64}")


def artifact_id(value: object) -> None:
    match(value, r"sha256:[0-9a-f]{64}")


def schema(value: dict, kind: str) -> None:
    exact(value["schema_version"], PREFIX + kind + ".v1", "INVALID_SCHEMA")


def _duplicate_safe(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        require(key not in result, "INVALID_JSON")
        result[key] = value
    return result


def _reject_constant(_value: str) -> None:
    raise GateError("INVALID_JSON")


def read_bytes(path: Path, maximum: int, missing: str = "MISSING_EVIDENCE") -> bytes:
    try:
        require(not path.is_symlink(), "PRIVACY_REJECTED")
        require(path.is_file(), missing)
        with path.open("rb") as stream:
            value = stream.read(maximum + 1)
    except OSError:
        raise GateError("READ_FAILED") from None
    require(0 < len(value) <= maximum, "SIZE_LIMIT")
    return value


def strict_json(data: bytes) -> object:
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=_duplicate_safe,
                          parse_constant=_reject_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise GateError("INVALID_JSON") from None


def read_json(path: Path) -> object:
    return strict_json(read_bytes(path, 64 * 1024))


def read_jsonl(path: Path) -> list:
    lines = read_bytes(path, 256 * 1024).splitlines()
    require(0 < len(lines) <= 256 and all(lines), "SIZE_LIMIT")
    return [strict_json(line) for line in lines]


def _diagnostic_shape(value: object, fields: str) -> None:
    # Exact builtins also reject subclasses whose equality could impersonate an
    # allowlisted key or enum in an in-memory caller. JSON is checked separately.
    require(type(value) is dict and all(type(key) is str for key in value)
            and value.keys() == set(fields.split()), "DIAGNOSTIC_INVALID")


def _diagnostic_enum(value: object, allowed: frozenset) -> None:
    require(type(value) is str and len(value) <= 64 and value in allowed, "DIAGNOSTIC_INVALID")


def _diagnostic_failure(value: object, field: str) -> dict | None:
    if value is None:
        return None
    _diagnostic_shape(value, "phase reason_code exception_category")
    _diagnostic_enum(value["phase"], DIAGNOSTIC_PHASES - {"complete"})
    _diagnostic_enum(value["reason_code"], DIAGNOSTIC_REASON_CODES)
    _diagnostic_enum(value["exception_category"], DIAGNOSTIC_EXCEPTION_CATEGORIES)
    category = value["exception_category"]
    if category == "gate_refusal":
        require(value["reason_code"] in DIAGNOSTIC_GATE_REASONS, "DIAGNOSTIC_INVALID")
    else:
        exact(value["reason_code"], DIAGNOSTIC_GENERIC_REASONS[category], "DIAGNOSTIC_INVALID")
    if field == "cleanup_failure":
        require(value["phase"] in {"cleanup", "worker_shutdown", "server_shutdown"}, "DIAGNOSTIC_INVALID")
    elif field == "audit_failure":
        exact(value["phase"], "audit_write", "DIAGNOSTIC_INVALID")
    return {key: value[key] for key in ("phase", "reason_code", "exception_category")}


def validate_diagnostic(value: object, expected_revision: str | None) -> dict:
    """Return a fresh fixed-schema record; never retain arbitrary exception data.

    This only certifies the diagnostic's bounded form and revision binding. It
    cannot certify execution, cleanup, or real-server acceptance.
    """
    _diagnostic_shape(value, "schema_version requested_revision status primary_failure cleanup_failure audit_failure")
    exact(value["schema_version"], PREFIX + "diagnostic.v1", "DIAGNOSTIC_INVALID")
    _diagnostic_enum(value["status"], frozenset({"COMPLETE", "FAILED"}))
    failures = {field: _diagnostic_failure(value[field], field)
                for field in ("primary_failure", "cleanup_failure", "audit_failure")}
    if value["status"] == "COMPLETE":
        require(all(failure is None for failure in failures.values()), "DIAGNOSTIC_INVALID")
    else:
        require(any(failure is not None for failure in failures.values()), "DIAGNOSTIC_INVALID")
    if expected_revision is None:
        exact(value["requested_revision"], None, "DIAGNOSTIC_INVALID")
        exact(value["status"], "FAILED", "DIAGNOSTIC_INVALID")
        exact(failures["primary_failure"], {"phase": "preflight", "reason_code": "KEY_ERROR",
                                           "exception_category": "key_error"}, "DIAGNOSTIC_INVALID")
    else:
        require(type(expected_revision) is str and len(expected_revision) == 40
                and re.fullmatch(r"[0-9a-f]{40}", expected_revision) is not None, "DIAGNOSTIC_INVALID")
        exact(value["requested_revision"], expected_revision, "DIAGNOSTIC_INVALID")
    result = {"schema_version": PREFIX + "diagnostic.v1", "requested_revision": expected_revision,
              "status": value["status"], **failures}
    require(len(_encode(result).encode("utf-8")) <= DIAGNOSTIC_MAX_BYTES, "DIAGNOSTIC_INVALID")
    return result


def build_diagnostic(requested_revision: str | None, *, status: str,
                     primary_failure: dict | None = None, cleanup_failure: dict | None = None,
                     audit_failure: dict | None = None) -> dict:
    """Build through the same strict validator used for untrusted audit bytes."""
    return validate_diagnostic({"schema_version": PREFIX + "diagnostic.v1",
        "requested_revision": requested_revision, "status": status, "primary_failure": primary_failure,
        "cleanup_failure": cleanup_failure, "audit_failure": audit_failure}, requested_revision)


def read_safe_diagnostic(audit_dir: Path, expected_revision: str | None) -> dict:
    """Read diagnostics independently of failed or partial audit records.

    Always return a bounded public report. Unreadable/missing or invalid records
    yield fixed codes and no source bytes, paths, exception names, or messages.
    """
    report = {"schema_version": PREFIX + "diagnostic-report.v1", "validation": "INVALID",
              "reason_code": "DIAGNOSTIC_INVALID", "diagnostic": None}
    try:
        audit_dir = Path(audit_dir)
        require(not audit_dir.is_symlink(), "DIAGNOSTIC_INVALID")
        require(audit_dir.is_dir(), "DIAGNOSTIC_UNAVAILABLE")
        raw = read_bytes(audit_dir / "diagnostic.json", DIAGNOSTIC_MAX_BYTES, "DIAGNOSTIC_UNAVAILABLE")
        record = validate_diagnostic(strict_json(raw), expected_revision)
    except GateError as error:
        if error.code in {"DIAGNOSTIC_UNAVAILABLE", "READ_FAILED"}:
            report.update(validation="UNAVAILABLE", reason_code="DIAGNOSTIC_UNAVAILABLE")
    except OSError:
        report.update(validation="UNAVAILABLE", reason_code="DIAGNOSTIC_UNAVAILABLE")
    except Exception:
        pass
    else:
        report.update(validation="VALID", reason_code="OK", diagnostic=record)
    return report


def checked_required_nodes(nodes: object) -> tuple[str, ...]:
    require(type(nodes) in (list, tuple) and tuple(nodes) == REQUIRED_NODES, "REQUIRED_NODES")
    return REQUIRED_NODES


def read_required_nodes(path: Path) -> tuple[str, ...]:
    try:
        lines = read_bytes(path, 8192).decode("ascii").splitlines()
    except UnicodeError:
        raise GateError("REQUIRED_NODES") from None
    return checked_required_nodes(lines)


def verify_collection(path: Path, required_nodes: tuple[str, ...]) -> list[str]:
    checked_required_nodes(required_nodes)
    value = read_json(path)
    shape(value, "schema_version nodes")
    schema(value, "collection")
    require(type(value["nodes"]) is list and len(value["nodes"]) == 7
            and all(type(n) is str for n in value["nodes"])
            and set(value["nodes"]) == set(required_nodes), "COLLECTION_MISMATCH")
    return value["nodes"]


def parse_junit(path: Path, maximum: int = 256 * 1024) -> ET.Element:
    """Read bounded canonical UTF-8, no-DTD JUnit with exact tree structure.

    This parser does not certify testcase identities or success. Callers must
    independently verify their fixed expected identities and every outcome.
    """
    integer(maximum, 1, 2 * 1024 * 1024, "SIZE_LIMIT")
    raw = read_bytes(path, maximum, "MISSING_JUNIT")
    # Decode exactly once before scanning. Passing bytes to ElementTree lets it
    # autodetect UTF-16/32, which would evade an ASCII-byte DTD/entity check.
    require(b"\x00" not in raw and not raw.startswith(b"\xef\xbb\xbf"), "INVALID_JUNIT")
    try:
        xml = raw.decode("utf-8", errors="strict")
    except UnicodeError:
        raise GateError("INVALID_JUNIT") from None
    if xml.startswith("<?xml"):
        declaration = re.match(
            r"<\?xml[ \t\r\n]+version=(?:\"1\.0\"|'1\.0')"
            r"(?:[ \t\r\n]+encoding=(?:\"[Uu][Tt][Ff]-8\"|'[Uu][Tt][Ff]-8'))?"
            r"(?:[ \t\r\n]+standalone=(?:\"(?:yes|no)\"|'(?:yes|no)'))?[ \t\r\n]*\?>", xml)
        require(declaration is not None, "INVALID_JUNIT")
    require("<!DOCTYPE" not in xml.upper() and "<!ENTITY" not in xml.upper(), "INVALID_JUNIT")
    try:
        root = ET.fromstring(xml)
    except (ET.ParseError, ValueError, RecursionError):
        raise GateError("INVALID_JUNIT") from None
    require(root.tag in ("testsuite", "testsuites"), "INVALID_JUNIT")
    child_tags = {
        "testsuites": {"testsuite"},
        "testsuite": {"testsuite", "testcase", "properties", "system-out", "system-err"},
        "testcase": {"failure", "error", "skipped", "system-out", "system-err"},
        "properties": {"property"},
        "property": set(), "failure": set(), "error": set(), "skipped": set(),
        "system-out": set(), "system-err": set(),
    }
    for element in root.iter():
        require(element.tag in child_tags and all(child.tag in child_tags[element.tag] for child in element),
                "INVALID_JUNIT")
        if element.tag == "testcase":
            require(set(element.attrib) <= {"classname", "name", "time", "file", "line"}, "INVALID_JUNIT")
            require(sum(child.tag in {"failure", "error", "skipped"} for child in element) <= 1, "INVALID_JUNIT")
    return root


def verify_junit(path: Path, required_nodes: tuple[str, ...]) -> list[dict]:
    """Read actual testcases, never aggregate test-count attributes or diagnostics."""
    checked_required_nodes(required_nodes)
    root = parse_junit(path)
    results = {}
    cases = list(root.iter("testcase"))
    require(len(cases) <= 7, "DUPLICATE_NODE")
    for case in cases:
        require(set(case.attrib) <= {"classname", "name", "time", "file", "line"}, "INVALID_JUNIT")
        name = case.get("name")
        classname = case.get("classname")
        require(name in NODE_NAMES and classname == "tests.acceptance.temporal_server_gate", "JUNIT_IDENTITY")
        node_id = "tests/acceptance/temporal_server_gate.py::" + name
        require(node_id in required_nodes, "UNEXPECTED_NODE")
        require(node_id not in results, "DUPLICATE_NODE")
        children = list(case)
        # Per-case properties can carry xfail or foreign identity claims. Never expose them.
        require(all(c.tag in {"failure", "error", "skipped", "system-out", "system-err"}
                    for c in children), "INVALID_JUNIT")
        statuses = [c.tag for c in children if c.tag in {"failure", "error", "skipped"}]
        require(len(statuses) <= 1, "INVALID_JUNIT")
        outcome, reason = {"failure": ("FAIL", "TEST_FAILED"), "error": ("ERROR", "TEST_ERROR"),
                           "skipped": ("SKIP", "TEST_SKIPPED")}.get(
                               statuses[0] if statuses else "", ("PASS", "OK"))
        results[node_id] = {"node_id": node_id, "outcome": outcome, "reason_code": reason}
    return [results.get(n, {"node_id": n, "outcome": "NOT_RUN", "reason_code": "NOT_RUN"})
            for n in required_nodes]


def verify_collected_unit_junit(nodes: object, path: Path, *, files: tuple[str, ...],
                                expected_count: int) -> list[dict]:
    """Bind every testcase to exactly one known collected module/class/test node.

    JUnit classnames flatten Python module and class scopes with dots. Replacing
    those dots with slashes loses the collector boundary. Build the mapping from
    the independently collected IDs instead and refuse any ambiguous projection.
    Parameter suffixes (including dots, slashes and literal ``::``) stay exact.
    This returns observed outcomes; the caller must still require all PASS and
    zero collection/test process exit codes before accepting the unit gate.
    """
    integer(expected_count, 1, 4096, "COLLECTION_MISMATCH")
    require(type(files) is tuple and 0 < len(files) <= 32
            and all(type(file) is str and len(file) <= 256 and re.fullmatch(
                r"tests/(?:[A-Za-z_][A-Za-z0-9_]*/)*[A-Za-z_][A-Za-z0-9_]*\.py", file)
                is not None for file in files)
            and len(files) == len(set(files)), "COLLECTION_MISMATCH")
    require(type(nodes) is list and len(nodes) == expected_count
            and all(type(node) is str and 0 < len(node) <= 128 * 1024 for node in nodes),
            "COLLECTION_MISMATCH")
    # Existing fixed fixtures include long parameter IDs. Bound their total bytes
    # without shortening, escaping, normalizing or dropping any identity.
    require(sum(len(node.encode("utf-8")) + 1 for node in nodes) <= 2 * 1024 * 1024,
            "SIZE_LIMIT")
    require(len(nodes) == len(set(nodes)), "DUPLICATE_NODE")
    identities = {}
    for node in nodes:
        file, separator, qualified = node.partition("::")
        require(separator == "::" and file in files
                and not any(ord(char) < 32 or ord(char) == 127 for char in node), "JUNIT_IDENTITY")
        bare, parameter, suffix = qualified.partition("[")
        scopes = bare.split("::")
        require(all(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", scope) is not None for scope in scopes)
                and (not parameter or suffix.endswith("]")), "JUNIT_IDENTITY")
        classname = ".".join([file[:-3].replace("/", "."), *scopes[:-1]])
        name = scopes[-1] + parameter + suffix
        identity = (classname, name)
        require(identity not in identities, "JUNIT_IDENTITY")
        identities[identity] = node
    root = parse_junit(path, maximum=2 * 1024 * 1024)
    cases = list(root.iter("testcase"))
    require(len(cases) == expected_count, "COLLECTION_MISMATCH")
    results = {}
    for case in cases:
        identity = (case.get("classname"), case.get("name"))
        require(identity in identities, "JUNIT_IDENTITY")
        node = identities[identity]
        require(node not in results, "DUPLICATE_NODE")
        statuses = [child.tag for child in case if child.tag in {"failure", "error", "skipped"}]
        outcome, reason = {"failure": ("FAIL", "TEST_FAILED"), "error": ("ERROR", "TEST_ERROR"),
                           "skipped": ("SKIP", "TEST_SKIPPED")}.get(
                               statuses[0] if statuses else "", ("PASS", "OK"))
        results[node] = {"node_id": node, "outcome": outcome, "reason_code": reason}
    require(set(results) == set(nodes), "COLLECTION_MISMATCH")
    return [results[node] for node in nodes]


def _sha(path: Path) -> str:
    return hashlib.sha256(read_bytes(path, 2 * 1024 * 1024)).hexdigest()


def current_source_digests(source: Path | None = None) -> dict:
    source = ROOT if source is None else Path(source)
    files = {
        "tool_lock_sha256": "ci/requirements.txt",
        "sdk_lock_sha256": "ci/temporal-sdk-requirements.txt",
        "required_nodes_sha256": "ci/temporal-server-nodes.txt",
        "activity_source_sha256": "src/opendot_engineering/adapters/temporal_activity.py",
        "workflow_source_sha256": "src/opendot_engineering/adapters/temporal_workflow.py",
    }
    result = {key: _sha(source / path) for key, path in files.items()}
    records = sorted((path, _sha(source / path)) for path in HARNESS_SOURCE_PATHS)
    result["harness_source_sha256"] = hashlib.sha256(
        json.dumps(records, ensure_ascii=True, separators=(",", ":")).encode("ascii")).hexdigest()
    return result


def _lock_versions(path: Path) -> dict:
    try:
        lines = read_bytes(path, 65536).decode("ascii").splitlines()
    except UnicodeError:
        raise GateError("VERSION_MISMATCH") from None
    result = {}
    for line in lines:
        if not line.strip() or line.startswith("#"):
            continue
        parsed = re.fullmatch(r"([A-Za-z0-9_-]+)==([0-9]+(?:\.[0-9]+)+) --hash=sha256:([0-9a-f]{64})", line)
        require(parsed is not None and parsed[1] not in result, "VERSION_MISMATCH")
        result[parsed[1]] = parsed[2]
        require(parsed[1] in (SDK_HASHES | TOOL_HASHES), "VERSION_MISMATCH")
        exact(parsed[3], (SDK_HASHES | TOOL_HASHES)[parsed[1]], "PIN_MISMATCH")
    return result


def checked_revision() -> str:
    try:
        completed = subprocess.run(["git", "--no-optional-locks", "-C", str(ROOT), "rev-parse", "HEAD"],
                                   capture_output=True, timeout=5, check=False)
        require(completed.returncode == 0, "REVISION_MISMATCH")
        value = completed.stdout.decode("ascii").strip()
    except (OSError, UnicodeError, subprocess.SubprocessError):
        raise GateError("REVISION_MISMATCH") from None
    match(value, r"[0-9a-f]{40}", "REVISION_MISMATCH")
    return value


def trusted_run_url(expected_revision: str) -> str:
    match(expected_revision, r"[0-9a-f]{40}", "REVISION_MISMATCH")
    exact(os.environ.get("GITHUB_ACTIONS"), "true", "CI_IDENTITY")
    exact(os.environ.get("GITHUB_SHA"), expected_revision, "CI_IDENTITY")
    exact(os.environ.get("GITHUB_SERVER_URL"), "https://github.com", "CI_IDENTITY")
    repo = os.environ.get("GITHUB_REPOSITORY")
    run_id = os.environ.get("GITHUB_RUN_ID")
    match(repo, r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}", "CI_IDENTITY")
    match(run_id, r"[1-9][0-9]{0,19}", "CI_IDENTITY")
    return "https://github.com/" + repo + "/actions/runs/" + run_id


def validate_environment(value: object, expected_revision: str, *, recheck_run_url: str | None = None) -> None:
    shape(value, "schema_version candidate_revision requested_revision workflow_run_url source_kind "
          "python_version platform versions cli_version server_version cli_archive_sha256 "
          "cli_checksums_sha256 sdk_wheel_sha256 tool_lock_sha256 sdk_lock_sha256 "
          "required_nodes_sha256 harness_source_sha256 activity_source_sha256 workflow_source_sha256 "
          "owner_sha256 server_profile preflight_status preflight_code")
    schema(value, "environment")
    for name in ("candidate_revision", "requested_revision"):
        exact(value[name], expected_revision, "REVISION_MISMATCH")
    if recheck_run_url is None:
        exact(checked_revision(), expected_revision, "REVISION_MISMATCH")
        exact(value["workflow_run_url"], trusted_run_url(expected_revision), "CI_IDENTITY")
    else:
        # Offline projection consistency only; this cannot establish CI identity.
        match(expected_revision, r"[0-9a-f]{40}", "REVISION_MISMATCH")
        match(recheck_run_url, r"https://github\.com/[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}/actions/runs/[1-9][0-9]{0,19}", "CI_IDENTITY")
        exact(value["workflow_run_url"], recheck_run_url, "CI_IDENTITY")
    exact(value["source_kind"], "public_source_checkout")
    match(value["python_version"], r"3\.12\.[0-9]{1,3}", "VERSION_MISMATCH")
    exact(value["platform"], "linux-x86_64", "VERSION_MISMATCH")
    expected = SDK_VERSIONS | TOOL_VERSIONS
    shape(value["versions"], set(expected), "VERSION_MISMATCH")
    for name, version in expected.items():
        exact(value["versions"][name], version, "VERSION_MISMATCH")
    exact(_lock_versions(ROOT / "ci/requirements.txt"), TOOL_VERSIONS, "VERSION_MISMATCH")
    exact(_lock_versions(ROOT / "ci/temporal-sdk-requirements.txt"), SDK_VERSIONS, "VERSION_MISMATCH")
    exact(value["cli_version"], "1.9.1", "VERSION_MISMATCH")
    exact(value["server_version"], "1.32.0", "VERSION_MISMATCH")
    for name, pin in (("cli_archive_sha256", CLI_ARCHIVE_SHA256),
                      ("cli_checksums_sha256", CLI_CHECKSUMS_SHA256), ("sdk_wheel_sha256", SDK_WHEEL_SHA256)):
        exact(value[name], pin, "PIN_MISMATCH")
    read_required_nodes(ROOT / "ci/temporal-server-nodes.txt")
    for name, observed in current_source_digests().items():
        exact(value[name], observed, "SOURCE_MISMATCH")
    shape(value["owner_sha256"], set(OWNER_SHA256), "OWNER_MISMATCH")
    for name, pin in OWNER_SHA256.items():
        exact(value["owner_sha256"][name], pin, "OWNER_MISMATCH")
        exact(_sha(ROOT / name), pin, "OWNER_MISMATCH")
    shape(value["server_profile"], set(SERVER_PROFILE))
    for name, expected in SERVER_PROFILE.items():
        exact(value["server_profile"][name], expected)
    exact(value["preflight_status"], "PASS", "PREFLIGHT_FAILED")
    exact(value["preflight_code"], "OK", "PREFLIGHT_FAILED")


def validate_metadata(rows: object) -> dict:
    require(type(rows) is list and len(rows) == 5, "METADATA_MISMATCH")
    by_scenario = {}
    for position, row in enumerate(rows, 1):
        shape(row, "schema_version scenario entry_sequence activity_id activity_type namespace task_queue "
              "workflow_id workflow_run_id attempt is_local retry_policy_present maximum_attempts "
              "start_to_close_seconds schedule_to_close_seconds metadata_source")
        schema(row, "metadata")
        scenario = row["scenario"]
        require(type(scenario) is str and scenario in SCENARIOS and scenario not in by_scenario, "METADATA_MISMATCH")
        exact(scenario, SCENARIOS[position - 1], "METADATA_MISMATCH")
        for key, expected in {
            "entry_sequence": position, "activity_id": ACTIVITY_ID, "activity_type": ACTIVITY_TYPE,
            "namespace": "default", "task_queue": "opendot-temporal-gate",
            "workflow_id": "opendot-gate-" + scenario, "attempt": 1, "is_local": False,
            "retry_policy_present": True, "maximum_attempts": 1,
            "start_to_close_seconds": 10, "schedule_to_close_seconds": 60,
            "metadata_source": "real_sdk_activity_info",
        }.items():
            exact(row[key], expected, "METADATA_MISMATCH")
        match(row["workflow_run_id"], r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
        by_scenario[scenario] = row
    require(len({r["workflow_run_id"] for r in rows}) == 5, "METADATA_MISMATCH")
    return by_scenario


def validate_counters(rows: object) -> dict:
    require(type(rows) is list and len(rows) == 15, "COUNTER_MISMATCH")
    expected_order = [(scenario, event) for scenario in SCENARIOS
                      for event, count in zip(COUNTER_EVENTS, EXPECTED_COUNTS[scenario]) for _ in range(count)]
    counters = {scenario: Counter() for scenario in SCENARIOS}
    for sequence, (row, (scenario, event)) in enumerate(zip(rows, expected_order), 1):
        shape(row, "schema_version scenario sequence event runtime_generation handler_binding")
        schema(row, "counter")
        exact(row["scenario"], scenario, "COUNTER_MISMATCH")
        exact(row["event"], event, "COUNTER_MISMATCH")
        exact(row["sequence"], sequence, "COUNTER_MISMATCH")
        exact(row["handler_binding"], "bounded_sum_with_test_counter", "COUNTER_MISMATCH")
        exact(row["runtime_generation"], dict(zip(SCENARIOS, (3, 6, 8, 10, 12)))[scenario], "COUNTER_MISMATCH")
        counters[scenario][event] += 1
    for scenario in SCENARIOS:
        expected = EXPECTED_COUNTS[scenario]
        require(tuple(counters[scenario][event] for event in COUNTER_EVENTS) == expected, "COUNTER_MISMATCH")
        require(len({r["runtime_generation"] for r in rows if r["scenario"] == scenario}) == 1, "COUNTER_MISMATCH")
    require(tuple(sum(counters[s][event] for s in SCENARIOS) for event in COUNTER_EVENTS) == (5, 4, 3, 3),
            "COUNTER_MISMATCH")
    return counters


def validate_outcomes(value: object, counters: dict) -> dict:
    shape(value, "schema_version scenarios")
    schema(value, "outcomes")
    rows = value["scenarios"]
    require(type(rows) is list and len(rows) == 5, "OUTCOME_MISMATCH")
    result = {}
    for position, row in enumerate(rows):
        shape(row, "scenario workflow_transport_status activity_transport_status result_ref_present "
              "result_artifact_id cas_digest_verified cas_size_verified result_schema_verified tool_status "
              "semantic_valid output_kind output_integer runtime_receipt_attempts execute_count handler_count "
              "scientific_validity device_control_authority independent_review owner_integration test_only_validator_fault")
        scenario = SCENARIOS[position]
        exact(row["scenario"], scenario, "OUTCOME_MISMATCH")
        missing = scenario == "missing_input"
        for key in ("workflow_transport_status", "activity_transport_status"):
            exact(row[key], "FAILED" if missing else "COMPLETED", "OUTCOME_MISMATCH")
        exact(row["result_ref_present"], not missing, "OUTCOME_MISMATCH")
        exact(row["test_only_validator_fault"], scenario == "failed_validation", "OUTCOME_MISMATCH")
        exact(row["execute_count"], counters[scenario]["execute_enter"], "OUTCOME_MISMATCH")
        exact(row["handler_count"], counters[scenario]["handler_enter"], "OUTCOME_MISMATCH")
        if missing:
            for key in ("result_artifact_id", "cas_digest_verified", "cas_size_verified", "result_schema_verified",
                        "tool_status", "semantic_valid", "output_kind", "output_integer", "runtime_receipt_attempts",
                        "scientific_validity", "device_control_authority", "independent_review", "owner_integration"):
                exact(row[key], None, "OUTCOME_MISMATCH")
        else:
            artifact_id(row["result_artifact_id"])
            for key in ("cas_digest_verified", "cas_size_verified", "result_schema_verified"):
                exact(row[key], True, "OUTCOME_MISMATCH")
            exact(row["tool_status"], {"blocked": "BLOCKED", "failed_validation": "FAILED"}.get(scenario, "COMPLETED"),
                  "OUTCOME_MISMATCH")
            exact(row["semantic_valid"], scenario in ("durability_replay", "null"), "OUTCOME_MISMATCH")
            exact(row["output_kind"], "integer" if scenario == "durability_replay" else "null", "OUTCOME_MISMATCH")
            exact(row["output_integer"], 5 if scenario == "durability_replay" else None, "OUTCOME_MISMATCH")
            exact(row["runtime_receipt_attempts"], 1, "OUTCOME_MISMATCH")
            for key in ("scientific_validity", "device_control_authority"):
                exact(row[key], False, "OUTCOME_MISMATCH")
            for key in ("independent_review", "owner_integration"):
                exact(row[key], "NOT_EVALUATED", "OUTCOME_MISMATCH")
        result[scenario] = row
    require(len({row["result_artifact_id"] for row in rows if row["result_ref_present"]}) == 4, "OUTCOME_MISMATCH")
    return result


EVENT_FIELDS = {
    "WorkflowExecutionStarted": "workflow_type task_queue execution_timeout_seconds run_timeout_seconds task_timeout_seconds maximum_attempts",
    "WorkflowTaskScheduled": "",
    "WorkflowTaskStarted": "scheduled_event_id identity",
    "WorkflowTaskCompleted": "scheduled_event_id started_event_id identity",
    "ActivityTaskScheduled": "activity_type activity_id task_queue maximum_attempts start_to_close_seconds schedule_to_close_seconds",
    "ActivityTaskStarted": "scheduled_event_id attempt identity",
    "ActivityTaskCompleted": "scheduled_event_id started_event_id response_schema result_artifact_id result_sha256 result_size_bytes",
    "ActivityTaskFailed": "scheduled_event_id started_event_id failure_type non_retryable retry_state",
    "WorkflowExecutionSignaled": "signal_name",
    "WorkflowExecutionCompleted": "response_schema result_artifact_id result_sha256 result_size_bytes",
    "WorkflowExecutionFailed": "failure_type",
}


def _result_attributes(attrs: dict, expected_id: str) -> None:
    exact(attrs["response_schema"], RESPONSE_SCHEMA, "HISTORY_MISMATCH")
    artifact_id(attrs["result_artifact_id"])
    exact(attrs["result_artifact_id"], expected_id, "HISTORY_MISMATCH")
    digest(attrs["result_sha256"])
    exact(attrs["result_artifact_id"], "sha256:" + attrs["result_sha256"], "HISTORY_MISMATCH")
    integer(attrs["result_size_bytes"], 1, 16384, "HISTORY_MISMATCH")


def _history_events(events: object, scenario: str, phase: str, outcome: dict) -> dict:
    require(type(events) is list and 1 <= len(events) <= 128, "HISTORY_MISMATCH")
    found = {name: [] for name in EVENT_FIELDS}
    indexed = {}
    task_scheduled = set()
    task_started = set()
    task_completed = set()
    for expected_id, event in enumerate(events, 1):
        shape(event, "event_id event_type attributes")
        exact(event["event_id"], expected_id, "HISTORY_LINKAGE")
        event_type = event["event_type"]
        require(type(event_type) is str and event_type in EVENT_FIELDS, "HISTORY_MISMATCH")
        attrs = event["attributes"]
        shape(attrs, EVENT_FIELDS[event_type])
        if event_type == "WorkflowExecutionStarted":
            exact(expected_id, 1, "HISTORY_LINKAGE")
            for key, value in {"workflow_type": "ReferenceGateWorkflow", "task_queue": "opendot-temporal-gate",
                               "execution_timeout_seconds": 120, "run_timeout_seconds": 120,
                               "task_timeout_seconds": 10, "maximum_attempts": 1}.items():
                exact(attrs[key], value, "HISTORY_MISMATCH")
        elif event_type == "WorkflowTaskScheduled":
            task_scheduled.add(expected_id)
        elif event_type == "ActivityTaskScheduled":
            for key, value in {"activity_type": ACTIVITY_TYPE, "activity_id": ACTIVITY_ID,
                               "task_queue": "opendot-temporal-gate", "maximum_attempts": 1,
                               "start_to_close_seconds": 10, "schedule_to_close_seconds": 60}.items():
                exact(attrs[key], value, "HISTORY_MISMATCH")
            require(bool(found["WorkflowTaskCompleted"]), "HISTORY_LINKAGE")
        elif event_type in ("ActivityTaskStarted", "ActivityTaskCompleted", "ActivityTaskFailed",
                             "WorkflowTaskStarted", "WorkflowTaskCompleted"):
            scheduled_type = "ActivityTaskScheduled" if event_type.startswith("Activity") else "WorkflowTaskScheduled"
            integer(attrs["scheduled_event_id"], 1, expected_id - 1, "HISTORY_LINKAGE")
            scheduled = indexed.get(attrs["scheduled_event_id"])
            require(scheduled is not None and scheduled["event_type"] == scheduled_type, "HISTORY_LINKAGE")
            if event_type.endswith("Started"):
                if event_type.startswith("Activity"):
                    exact(attrs["attempt"], 1, "HISTORY_MISMATCH")
                    exact(attrs["identity"], "opendot-gate-activity-worker", "HISTORY_MISMATCH")
                else:
                    require(attrs["scheduled_event_id"] not in task_started, "HISTORY_LINKAGE")
                    task_started.add(attrs["scheduled_event_id"])
                    exact(attrs["identity"], "opendot-gate-workflow-worker", "HISTORY_MISMATCH")
            else:
                integer(attrs["started_event_id"], 1, expected_id - 1, "HISTORY_LINKAGE")
                started = indexed.get(attrs["started_event_id"])
                require(started is not None and started["event_type"] == scheduled_type.replace("Scheduled", "Started")
                        and started["attributes"]["scheduled_event_id"] == attrs["scheduled_event_id"], "HISTORY_LINKAGE")
                if event_type == "WorkflowTaskCompleted":
                    require(attrs["scheduled_event_id"] not in task_completed, "HISTORY_LINKAGE")
                    task_completed.add(attrs["scheduled_event_id"])
                    exact(attrs["identity"], "opendot-gate-workflow-worker", "HISTORY_MISMATCH")
                elif event_type == "ActivityTaskCompleted":
                    _result_attributes(attrs, outcome["result_artifact_id"])
                else:
                    exact(attrs["failure_type"], "TemporalInputRejected", "HISTORY_MISMATCH")
                    exact(attrs["non_retryable"], True, "HISTORY_MISMATCH")
                    exact(attrs["retry_state"], "RETRY_STATE_NON_RETRYABLE_FAILURE", "HISTORY_MISMATCH")
        elif event_type == "WorkflowExecutionSignaled":
            exact(attrs["signal_name"], "finish", "HISTORY_MISMATCH")
            require(scenario != "missing_input" and bool(found["ActivityTaskCompleted"]), "HISTORY_LINKAGE")
        elif event_type == "WorkflowExecutionCompleted":
            _result_attributes(attrs, outcome["result_artifact_id"])
            require(bool(found["ActivityTaskCompleted"]) and bool(found["WorkflowTaskCompleted"]), "HISTORY_LINKAGE")
            require(bool(found["WorkflowExecutionSignaled"]), "HISTORY_LINKAGE")
            require(indexed[expected_id - 1]["event_type"] == "WorkflowTaskCompleted"
                    and task_scheduled == task_started == task_completed, "HISTORY_LINKAGE")
            final_task = found["WorkflowTaskCompleted"][-1]
            require(final_task["event_id"] > found["WorkflowExecutionSignaled"][-1]["event_id"]
                    and final_task["event_id"] > found["ActivityTaskCompleted"][-1]["event_id"], "HISTORY_LINKAGE")
        elif event_type == "WorkflowExecutionFailed":
            exact(attrs["failure_type"], "TemporalInputRejected", "HISTORY_MISMATCH")
            require(scenario == "missing_input" and bool(found["ActivityTaskFailed"]), "HISTORY_LINKAGE")
            require(indexed[expected_id - 1]["event_type"] == "WorkflowTaskCompleted"
                    and task_scheduled == task_started == task_completed, "HISTORY_LINKAGE")
            require(found["WorkflowTaskCompleted"][-1]["event_id"] > found["ActivityTaskFailed"][-1]["event_id"],
                    "HISTORY_LINKAGE")
        require(not found["WorkflowExecutionCompleted"] and not found["WorkflowExecutionFailed"], "HISTORY_LINKAGE")
        found[event_type].append(event)
        indexed[expected_id] = event
    exact(len(found["WorkflowExecutionStarted"]), 1, "HISTORY_MISMATCH")
    exact(len(found["ActivityTaskScheduled"]), 1, "HISTORY_MISMATCH")
    queued = phase in ("queued_before_restart", "queued_after_restart")
    missing = scenario == "missing_input"
    for event_type, count in {
        "ActivityTaskStarted": 0 if queued else 1,
        "ActivityTaskCompleted": 0 if queued or missing else 1,
        "ActivityTaskFailed": 1 if missing else 0,
        "WorkflowExecutionCompleted": 1 if phase in ("terminal", "workflow_completed_after_replay") and not missing else 0,
        "WorkflowExecutionFailed": 1 if missing else 0,
        "WorkflowExecutionSignaled": 1 if phase in ("workflow_completed_after_replay", "terminal") and not missing else 0,
    }.items():
        exact(len(found[event_type]), count, "HISTORY_MISMATCH")
    if found["WorkflowExecutionCompleted"]:
        completed_attrs = found["ActivityTaskCompleted"][0]["attributes"]
        workflow_attrs = found["WorkflowExecutionCompleted"][0]["attributes"]
        for name in ("response_schema", "result_artifact_id", "result_sha256", "result_size_bytes"):
            exact(workflow_attrs[name], completed_attrs[name], "HISTORY_MISMATCH")
    return found


def validate_histories(value: object, metadata: dict, outcomes: dict) -> dict:
    shape(value, "schema_version snapshots")
    schema(value, "history")
    snapshots = value["snapshots"]
    phases = ("queued_before_restart", "queued_after_restart", "activity_result_recorded", "workflow_completed_after_replay")
    expected_order = [("durability_replay", p) for p in phases] + [(s, "terminal") for s in SCENARIOS[1:]]
    require(type(snapshots) is list and len(snapshots) == len(expected_order), "HISTORY_MISMATCH")
    indexed = {}
    for row, (scenario, phase) in zip(snapshots, expected_order):
        shape(row, "scenario phase workflow_id workflow_run_id server_generation raw_history_sha256 events "
              "counter_sequence activity_workers_started active_activity_calls")
        exact(row["scenario"], scenario, "HISTORY_MISMATCH")
        exact(row["phase"], phase, "HISTORY_MISMATCH")
        exact(row["workflow_id"], metadata[scenario]["workflow_id"], "HISTORY_MISMATCH")
        exact(row["workflow_run_id"], metadata[scenario]["workflow_run_id"], "HISTORY_MISMATCH")
        expected_generation = {"queued_before_restart": 1, "queued_after_restart": 2,
                               "activity_result_recorded": 2}.get(phase, 3)
        exact(row["server_generation"], expected_generation, "HISTORY_MISMATCH")
        expected_counter = {"queued_before_restart": 0, "queued_after_restart": 0,
                            "activity_result_recorded": 4, "workflow_completed_after_replay": 4}.get(
                                phase, {"null": 8, "blocked": 10, "failed_validation": 14, "missing_input": 15}.get(scenario))
        expected_workers = {"queued_before_restart": 0, "queued_after_restart": 0,
                            "activity_result_recorded": 1, "workflow_completed_after_replay": 1}.get(
                                phase, SCENARIOS.index(scenario) + 1)
        exact(row["counter_sequence"], expected_counter, "COUNTER_MISMATCH")
        exact(row["activity_workers_started"], expected_workers, "COUNTER_MISMATCH")
        exact(row["active_activity_calls"], 0, "CLEANUP_UNCONFIRMED")
        digest(row["raw_history_sha256"])
        _history_events(row["events"], scenario, phase, outcomes[scenario])
        indexed[(scenario, phase)] = row
    before, after, result, terminal = [indexed[("durability_replay", p)] for p in phases]
    exact(after["events"], before["events"], "HISTORY_MISMATCH")
    exact(after["raw_history_sha256"], before["raw_history_sha256"], "HISTORY_MISMATCH")
    require(result["events"][:len(after["events"])] == after["events"], "HISTORY_MISMATCH")
    require(terminal["events"][:len(result["events"])] == result["events"], "HISTORY_MISMATCH")
    require(len({before["raw_history_sha256"], result["raw_history_sha256"], terminal["raw_history_sha256"]}) == 3,
            "HISTORY_MISMATCH")
    return indexed


def validate_replay(value: object, histories: dict, outcomes: dict, metadata: dict) -> None:
    shape(value, "schema_version scenario workflow_run_id recorded_completion_event_id same_completion_event_after_restart "
          "before_result_artifact_id after_query_result_artifact_id workflow_result_artifact_id fresh_workflow_worker "
          "activity_worker_present_during_replay activity_schedule_count_before activity_schedule_count_after "
          "handler_count_before handler_count_after_live_replay handler_count_after_sdk_replay raw_history_sha256 "
          "sdk_replay_failure cas_reverified counter_sequence_before counter_sequence_after_live_replay "
          "counter_sequence_after_sdk_replay")
    schema(value, "replay")
    exact(value["scenario"], "durability_replay", "REPLAY_MISMATCH")
    exact(value["workflow_run_id"], metadata["durability_replay"]["workflow_run_id"], "REPLAY_MISMATCH")
    history = histories[("durability_replay", "workflow_completed_after_replay")]
    event = next(e for e in history["events"] if e["event_type"] == "ActivityTaskCompleted")
    exact(value["recorded_completion_event_id"], event["event_id"], "REPLAY_MISMATCH")
    for key in ("before_result_artifact_id", "after_query_result_artifact_id", "workflow_result_artifact_id"):
        exact(value[key], outcomes["durability_replay"]["result_artifact_id"], "REPLAY_MISMATCH")
    for key in ("same_completion_event_after_restart", "fresh_workflow_worker", "cas_reverified"):
        exact(value[key], True, "REPLAY_MISMATCH")
    exact(value["activity_worker_present_during_replay"], False, "REPLAY_MISMATCH")
    for key in ("activity_schedule_count_before", "activity_schedule_count_after", "handler_count_before",
                "handler_count_after_live_replay", "handler_count_after_sdk_replay"):
        exact(value[key], 1, "REPLAY_MISMATCH")
    exact(value["raw_history_sha256"], history["raw_history_sha256"], "REPLAY_MISMATCH")
    exact(value["sdk_replay_failure"], None, "REPLAY_MISMATCH")
    for key in ("counter_sequence_before", "counter_sequence_after_live_replay", "counter_sequence_after_sdk_replay"):
        exact(value[key], 4, "COUNTER_MISMATCH")


def validate_cleanup(value: object) -> None:
    shape(value, "schema_version server_generations worker_generations all_activity_calls_observed_terminal "
          "same_sqlite_across_restarts same_cas_across_restarts in_flight_shutdown_attempted forced_termination_used "
          "cleanup_status cleanup_code elapsed_seconds")
    schema(value, "cleanup")
    for name in ("all_activity_calls_observed_terminal", "same_sqlite_across_restarts", "same_cas_across_restarts"):
        exact(value[name], True, "CLEANUP_UNCONFIRMED")
    for name in ("in_flight_shutdown_attempted", "forced_termination_used"):
        exact(value[name], False, "CLEANUP_UNCONFIRMED")
    exact(value["cleanup_status"], "PASS", "CLEANUP_UNCONFIRMED")
    exact(value["cleanup_code"], "OK", "CLEANUP_UNCONFIRMED")
    finite(value["elapsed_seconds"], 240, "CLEANUP_UNCONFIRMED")
    servers = value["server_generations"]
    require(type(servers) is list and len(servers) == 3, "CLEANUP_UNCONFIRMED")
    for generation, row in enumerate(servers, 1):
        shape(row, "generation shutdown_requested_signal graceful_exit_observed exit_code readiness_seconds shutdown_seconds")
        exact(row["generation"], generation, "CLEANUP_UNCONFIRMED")
        exact(row["shutdown_requested_signal"], "SIGINT", "CLEANUP_UNCONFIRMED")
        exact(row["graceful_exit_observed"], True, "CLEANUP_UNCONFIRMED")
        exact(row["exit_code"], 0, "CLEANUP_UNCONFIRMED")
        finite(row["readiness_seconds"], 10, "CLEANUP_UNCONFIRMED")
        finite(row["shutdown_seconds"], 8, "CLEANUP_UNCONFIRMED")
    workers = value["worker_generations"]
    require(type(workers) is list and len(workers) == 12, "CLEANUP_UNCONFIRMED")
    seen = set()
    counts = Counter()
    expected_types = ("workflow", "workflow", "activity", "workflow", "workflow", "activity",
                      "workflow", "activity", "workflow", "activity", "workflow", "activity")
    for generation, (row, kind) in enumerate(zip(workers, expected_types), 1):
        shape(row, "generation type public_shutdown_called public_shutdown_completed")
        exact(row["generation"], generation, "CLEANUP_UNCONFIRMED")
        exact(row["type"], kind, "CLEANUP_UNCONFIRMED")
        key = (row["type"], row["generation"])
        require(key not in seen, "CLEANUP_UNCONFIRMED")
        seen.add(key)
        counts[row["type"]] += 1
        exact(row["public_shutdown_called"], True, "CLEANUP_UNCONFIRMED")
        exact(row["public_shutdown_completed"], True, "CLEANUP_UNCONFIRMED")
    require(counts["workflow"] >= 3 and counts["activity"] >= 1, "CLEANUP_UNCONFIRMED")


def validate_audit(audit_dir: Path, expected_revision: str, required_nodes: tuple[str, ...]) -> dict:
    """Validate every public field, all cross-links, current sources, and cleanup.

    Returns only the validated public records. Raw histories, SDK Info, install
    reports, acquisition receipts, JUnit diagnostics, and CAS never enter it.
    """
    audit_dir = Path(audit_dir)
    checked_required_nodes(required_nodes)
    try:
        require(audit_dir.is_dir() and not audit_dir.is_symlink(), "MISSING_EVIDENCE")
        require({p.name for p in audit_dir.iterdir()} <= set(AUDIT_FILES) | {"collection-receipt.json", "acceptance.json"},
                "PRIVACY_REJECTED")
    except OSError:
        raise GateError("READ_FAILED") from None
    verify_collection(audit_dir / "collection-receipt.json", required_nodes)
    records = {name: (read_jsonl(audit_dir / name) if name.endswith(".jsonl") else
                     strict_json(read_bytes(audit_dir / name, DIAGNOSTIC_MAX_BYTES)) if name == "diagnostic.json"
                     else read_json(audit_dir / name))
               for name in AUDIT_FILES}
    records["diagnostic.json"] = validate_diagnostic(records["diagnostic.json"], expected_revision)
    exact(records["diagnostic.json"]["status"], "COMPLETE", "DIAGNOSTIC_FAILED")
    validate_environment(records["environment.json"], expected_revision)
    metadata = validate_metadata(records["activity-metadata.jsonl"])
    counters = validate_counters(records["invocation-counters.jsonl"])
    outcomes = validate_outcomes(records["outcomes.json"], counters)
    histories = validate_histories(records["history-projection.json"], metadata, outcomes)
    validate_replay(records["replay.json"], histories, outcomes, metadata)
    validate_cleanup(records["cleanup.json"])
    return records


def _encode(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False)


def make_acceptance(expected_revision: str, nodes: list[dict], collected: int,
                    audit_verified: bool, reasons: list[str]) -> dict:
    counts = {name: sum(row["outcome"] == name for row in nodes) for name in OUTCOME_NAMES}
    passed = audit_verified and collected == 7 and counts["PASS"] == 7 and not reasons
    return {
        "schema_version": PREFIX + "acceptance.v1",
        "candidate_revision": expected_revision if type(expected_revision) is str
        and re.fullmatch(r"[0-9a-f]{40}", expected_revision) else None,
        "required_node_count": 7, "collected_node_count": collected,
        "nodes": nodes, "counts": counts, "evidence_complete": audit_verified,
        "privacy_check": "PASS" if audit_verified else "FAIL",
        "cleanup_verified": audit_verified, "acceptance": "PASS" if passed else "FAIL",
        "reason_codes": sorted(set(reasons)) if reasons else (["OK"] if passed else ["NOT_RUN"]),
    }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["recheck-public-bundle"]:
        return _public_bundle_main(argv[1:])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--required", required=True, type=Path)
    parser.add_argument("--junit", required=True, type=Path)
    parser.add_argument("--audit", required=True, type=Path)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--profile", choices=("reference", "batch200", "dag2"), default="reference")
    parser.add_argument("--public-bundle", type=Path,
                        help="Optional fresh public projection directory; batch200 only")
    parser.add_argument("--expected-identity", type=Path)
    parser.add_argument("--reviewed-source-manifest", type=Path)
    parser.add_argument("--expected-source-manifest-sha256")
    args = parser.parse_args(argv)
    if args.public_bundle is not None and args.profile != "batch200":
        parser.error("--public-bundle requires --profile batch200")
    if args.profile == "batch200":
        return _real_batch_main(args)
    if args.profile == "dag2":
        return _dag2_main(args)
    reasons = []
    nodes = [{"node_id": n, "outcome": "NOT_RUN", "reason_code": "NOT_RUN"} for n in REQUIRED_NODES]
    records = None
    collected = 0
    try:
        read_required_nodes(args.required)
    except GateError as error:
        reasons.append(error.code)
    except Exception:
        reasons.append("INTERNAL_ERROR")
    try:
        collected = len(verify_collection(args.audit / "collection-receipt.json", REQUIRED_NODES))
    except GateError as error:
        reasons.append(error.code)
    except Exception:
        reasons.append("INTERNAL_ERROR")
    try:
        nodes = verify_junit(args.junit, REQUIRED_NODES)
        reasons.extend(row["reason_code"] for row in nodes if row["outcome"] != "PASS")
    except GateError as error:
        reasons.append(error.code)
    except Exception:
        reasons.append("INTERNAL_ERROR")
    try:
        records = validate_audit(args.audit, args.expected_revision, REQUIRED_NODES)
    except GateError as error:
        reasons.append(error.code)
    except Exception:
        reasons.append("INTERNAL_ERROR")
    diagnostic_report = read_safe_diagnostic(args.audit, args.expected_revision)
    if diagnostic_report["validation"] != "VALID":
        reasons.append(diagnostic_report["reason_code"])
    elif diagnostic_report["diagnostic"]["status"] != "COMPLETE":
        reasons.append("DIAGNOSTIC_FAILED")
    acceptance = make_acceptance(args.expected_revision, nodes, collected, records is not None, reasons)
    try:
        require(not args.audit.is_symlink(), "WRITE_FAILED")
        args.audit.mkdir(parents=True, exist_ok=True)
        target = args.audit / "acceptance.json"
        require(not target.is_symlink(), "WRITE_FAILED")
        target.write_text(_encode(acceptance) + "\n", encoding="utf-8")
    except (OSError, GateError):
        acceptance["acceptance"] = "FAIL"
        acceptance["reason_codes"] = sorted(set(acceptance["reason_codes"]) - {"OK"} | {"WRITE_FAILED"})
    if args.summary:
        try:
            with args.summary.open("a", encoding="utf-8") as output:
                output.write("Temporal real-server gate: " + ("PASS" if acceptance["acceptance"] == "PASS"
                                                               else "NOT VERIFIED") + "\n" + _encode(acceptance) + "\n"
                             + _encode(diagnostic_report) + "\n")
        except OSError:
            acceptance["acceptance"] = "FAIL"
            acceptance["reason_codes"] = sorted(set(acceptance["reason_codes"]) - {"OK"} | {"WRITE_FAILED"})
            try:
                require(not args.audit.is_symlink() and not (args.audit / "acceptance.json").is_symlink(), "WRITE_FAILED")
                (args.audit / "acceptance.json").write_text(_encode(acceptance) + "\n", encoding="utf-8")
            except (OSError, GateError):
                pass
    # All emitted values below are freshly built fixed fields or completely validated records.
    print(_encode(acceptance))
    print(_encode(diagnostic_report))
    if records is not None and acceptance["acceptance"] == "PASS":
        for filename in AUDIT_FILES:
            if filename != "diagnostic.json":
                print(_encode({"audit_file": filename, "evidence": records[filename]}))
    return 0 if acceptance["acceptance"] == "PASS" else 1


# Finite batch v1 is preparation-only. It has no CLI path and cannot emit the
# historical real-server acceptance schema. All clocks below are fixture clocks.
BATCH_SCHEMA = "opendot.temporal.batch."
BATCH_JOB_COUNT = 200
BATCH_MAX_EVENTS = 4096
BATCH_EVENT_BYTES = 1024
BATCH_SUMMARY_BYTES = 65536
BATCH_TRACE_BYTES = 5 * 1024 * 1024
BATCH_PROFILE = {
    "job_count": 200, "outstanding_limit": 16, "activity_slots": 8,
    "executor_workers": 8, "workflow_task_slots": 1, "workflow_cache": 0,
    "activity_pollers": 1, "workflow_pollers": 1,
    "disable_eager_activity_execution": True, "maximum_attempts": 1,
    "callable_timeout_seconds": 1, "start_to_close_seconds": 10,
    "schedule_to_close_seconds": 60,
}
BATCH_UNCERTAINTY_REASONS = frozenset({
    "UNKNOWN_ACK", "RPC_EXCEPTION", "TIMEOUT", "TRANSPORT_LOSS",
    "RUNTIME_EXCEPTION", "RECONCILIATION_REQUIRED", "OBSERVER_FAILURE",
    "INVALID_TERMINAL", "DUPLICATE_ACK", "DUPLICATE_TERMINAL",
})
BATCH_OWNER_SHA256 = {
    **OWNER_SHA256,
    "src/opendot_engineering/adapters/temporal_activity.py":
        "3e084d5432c11d031385472b9eba32e1d62f06d4aa45e08acebd88bd803045f2",
    "src/opendot_engineering/adapters/temporal_workflow.py":
        "a1723c70ccd8e440475ff0c359a5dfb1fa6e41ad2dff9881d2727879231434ac",
}
BATCH_SOURCE_PATHS = tuple(sorted(set(HARNESS_SOURCE_PATHS) | set(BATCH_OWNER_SHA256) | {
    "AGENTS.md", "docs/decisions/004-temporal-reference-transport.md",
    "ci/temporal-batch-nodes.txt", "docs/temporal-batch-qualification.md",
}))


def _batch_encoded(value: object, maximum: int) -> bytes:
    """Bound exact plain data before serialization; no arbitrary object hooks."""
    remaining = [100000]
    def plain(item, depth=0):
        remaining[0] -= 1
        require(remaining[0] >= 0 and depth <= 10, "SIZE_LIMIT")
        if item is None or type(item) in (bool, int):
            if type(item) is int:
                require(abs(item) <= 10 ** 15, "SIZE_LIMIT")
            return
        if type(item) is str:
            require(len(item) <= 256, "SIZE_LIMIT")
            return
        if type(item) is list:
            require(len(item) <= BATCH_MAX_EVENTS, "SIZE_LIMIT")
            for child in item:
                plain(child, depth + 1)
            return
        require(type(item) is dict and len(item) <= 32, "INVALID_TYPE")
        for key, child in item.items():
            require(type(key) is str and len(key) <= 128, "INVALID_SCHEMA")
            plain(child, depth + 1)
    plain(value)
    data = json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")
    require(0 < len(data) <= maximum, "SIZE_LIMIT")
    return data


def frozen_batch_plan() -> dict:
    """Materialize the sole admitted fixture, not a configurable job source."""
    jobs = []
    for index in range(BATCH_JOB_COUNT):
        payload = {"left": index, "right": 199 - index, "return_null": False}
        data = _batch_encoded(payload, 256)
        jobs.append({"job_id": f"batch-{index:03d}", "cohort": "ab"[index % 2],
                     "workflow_id": f"opendot-batch-{index:03d}", "payload": payload,
                     "input_artifact_id": "sha256:" + hashlib.sha256(data).hexdigest(),
                     "input_size_bytes": len(data), "expected_output": 199,
                     "max_result_bytes": 16384})
    return {"schema_version": BATCH_SCHEMA + "plan.v1", "jobs": jobs,
            "attempt_allowance": 200, "output_allowance_bytes": 200 * 16384}


def validate_batch_plan(value: object) -> dict:
    _batch_encoded(value, 128 * 1024)
    expected = frozen_batch_plan()
    exact(_batch_encoded(value, 128 * 1024), _batch_encoded(expected, 128 * 1024), "INVALID_VALUE")
    return expected  # fresh internally built objects; no caller aliases survive


def validate_batch_profile(value: object) -> dict:
    _batch_encoded(value, 2048)
    shape(value, set(BATCH_PROFILE))
    for name, expected in BATCH_PROFILE.items():
        exact(value[name], expected)
    return dict(BATCH_PROFILE)


def current_batch_source_digests(source: Path | None = None) -> dict:
    source = ROOT if source is None else Path(source)
    result = {path: _sha(source / path) for path in BATCH_SOURCE_PATHS}
    for path, expected in BATCH_OWNER_SHA256.items():
        exact(result[path], expected, "OWNER_MISMATCH")
    return result


def validate_batch_terminal(value: object, job: dict, run_id: str) -> dict:
    """Validate original projection bindings; semantic acceptance is separate.

    The fixture projection is not a CAS read or a live receipt. A hosted consumer
    is deliberately absent until independently approved original-byte validation.
    """
    _batch_encoded(value, BATCH_EVENT_BYTES)
    shape(value, "job_id workflow_id run_id activity_id invocation_id attempt receipt_id "
          "input_artifact_id result_artifact_id result_input_artifact_id result_size_bytes "
          "tool_status semantic_valid output reconciliation_required transport_status")
    exact(value["job_id"], job["job_id"])
    exact(value["workflow_id"], job["workflow_id"])
    match(run_id, r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
    exact(value["run_id"], run_id)
    exact(value["activity_id"], ACTIVITY_ID)
    exact(value["invocation_id"], "inv-" + job["job_id"][-3:])
    exact(value["attempt"], 1)
    match(value["receipt_id"], r"[0-9a-f]{24}")
    exact(value["input_artifact_id"], job["input_artifact_id"])
    exact(value["result_input_artifact_id"], job["input_artifact_id"])
    artifact_id(value["result_artifact_id"])
    integer(value["result_size_bytes"], 1, job["max_result_bytes"])
    require(type(value["tool_status"]) is str
            and value["tool_status"] in {"COMPLETED", "FAILED", "BLOCKED"})
    require(type(value["transport_status"]) is str
            and value["transport_status"] in {"COMPLETED", "FAILED", "UNKNOWN"})
    require(type(value["semantic_valid"]) is bool
            and type(value["reconciliation_required"]) is bool)
    require(value["output"] is None or type(value["output"]) is int
            and -2000000 <= value["output"] <= 2000000)
    return dict(value)


def batch_terminal_accepted(value: dict) -> bool:
    return (value["transport_status"] == "COMPLETED"
            and value["tool_status"] == "COMPLETED" and value["semantic_valid"] is True
            and value["reconciliation_required"] is False
            and type(value["output"]) is int and value["output"] == 199)


def read_batch_trace(path: Path) -> object:
    return strict_json(read_bytes(path, BATCH_TRACE_BYTES))


def validate_batch_trace(value: object, expected_revision: str,
                         source: Path | None = None) -> dict:
    """Reconstruct a finite *fabricated* trace; never certify a service run.

    Malformed evidence raises a fixed GateError. Well-formed partial/uncertain
    observations yield a bounded FAIL summary retaining outstanding work. A late
    success can account for work but can never erase an uncertainty latch.
    """
    _batch_encoded(value, BATCH_TRACE_BYTES)
    shape(value, "schema_version evidence_kind revision source_sha256 plan profile events outcomes")
    exact(value["schema_version"], BATCH_SCHEMA + "trace.v1", "INVALID_SCHEMA")
    exact(value["evidence_kind"], "FABRICATED_UNIT_DATA", "INVALID_SCHEMA")
    match(expected_revision, r"[0-9a-f]{40}")
    exact(value["revision"], expected_revision, "REVISION_MISMATCH")
    exact(value["source_sha256"], current_batch_source_digests(source), "SOURCE_MISMATCH")
    plan = validate_batch_plan(value["plan"])
    profile = validate_batch_profile(value["profile"])
    events, originals = value["events"], value["outcomes"]
    require(type(events) is list and len(events) <= BATCH_MAX_EVENTS, "SIZE_LIMIT")
    require(type(originals) is list and len(originals) <= 200, "SIZE_LIMIT")
    jobs = {job["job_id"]: job for job in plan["jobs"]}
    states = {job_id: {"reserved": False, "run_id": None, "phase": 0,
              "terminal_seen": False, "accepted": False, "uncertain": False,
              "submit_us": None, "start_us": None, "end_us": None, "terminal_us": None,
              "handler_start_us": None, "handler_end_us": None}
              for job_id in jobs}
    outcomes, result_ids, receipts = {}, set(), set()
    for row in originals:
        require(type(row) is dict and type(row.get("job_id")) is str
                and row["job_id"] in jobs, "OUTCOME_MISMATCH")
        job_id = row["job_id"]
        require(job_id not in outcomes, "OUTCOME_MISMATCH")
        validated = validate_batch_terminal(row, jobs[job_id], row.get("run_id"))
        require(validated["result_artifact_id"] not in result_ids
                and validated["receipt_id"] not in receipts, "OUTCOME_MISMATCH")
        result_ids.add(validated["result_artifact_id"])
        receipts.add(validated["receipt_id"])
        outcomes[job_id] = validated
    reserved = outstanding = peak_outstanding = peak_activity = 0
    active, run_ids, invoked, observed_outcomes = set(), set(), set(), set()
    latched, last_us = False, 0
    for number, row in enumerate(events, 1):
        _batch_encoded(row, BATCH_EVENT_BYTES)
        shape(row, "sequence elapsed_us job_id kind details")
        exact(row["sequence"], number, "COUNTER_MISMATCH")
        integer(row["elapsed_us"], 0, 600000000)
        require(row["elapsed_us"] >= last_us, "COUNTER_MISMATCH")
        last_us = row["elapsed_us"]
        require(type(row["job_id"]) is str and row["job_id"] in jobs, "OUTCOME_MISMATCH")
        job_id, kind, details = row["job_id"], row["kind"], row["details"]
        require(type(kind) is str and kind in {"reserve", "ack", "activity_begin", "execute_enter",
                "handler_enter", "handler_return", "activity_end", "terminal", "uncertain"},
                "INVALID_SCHEMA")
        state, job = states[job_id], jobs[job_id]
        if kind == "reserve":
            shape(details, "attempt output_allowance_bytes")
            exact(details["attempt"], 1)
            exact(details["output_allowance_bytes"], 16384)
            require(not latched and not state["reserved"] and reserved < 200
                    and job_id == plan["jobs"][reserved]["job_id"]
                    and outstanding < profile["outstanding_limit"], "COUNTER_MISMATCH")
            state["reserved"], state["submit_us"] = True, row["elapsed_us"]
            reserved += 1
            outstanding += 1
            peak_outstanding = max(peak_outstanding, outstanding)
            continue
        require(state["reserved"], "COUNTER_MISMATCH")
        if kind == "uncertain":
            shape(details, "reason")
            require(type(details["reason"]) is str and details["reason"] in BATCH_UNCERTAINTY_REASONS)
            latched, state["uncertain"] = True, True
            continue
        if kind == "ack":
            shape(details, "workflow_id run_id")
            exact(details["workflow_id"], job["workflow_id"])
            match(details["run_id"], r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
            require(state["run_id"] is None and details["run_id"] not in run_ids, "HISTORY_LINKAGE")
            state["run_id"] = details["run_id"]
            run_ids.add(details["run_id"])
            continue
        require(state["run_id"] is not None, "HISTORY_LINKAGE")
        invocation = "inv-" + job_id[-3:]
        if kind == "activity_begin":
            shape(details, "workflow_id run_id activity_id invocation_id attempt maximum_attempts "
                  "start_to_close_seconds schedule_to_close_seconds is_local")
            for key, expected in {"workflow_id": job["workflow_id"], "run_id": state["run_id"],
                    "activity_id": ACTIVITY_ID, "invocation_id": invocation, "attempt": 1,
                    "maximum_attempts": 1, "start_to_close_seconds": 10,
                    "schedule_to_close_seconds": 60, "is_local": False}.items():
                exact(details[key], expected, "METADATA_MISMATCH")
            require(state["phase"] == 0 and invocation not in invoked, "COUNTER_MISMATCH")
            invoked.add(invocation)
            active.add(invocation)
            require(len(active) <= 8, "COUNTER_MISMATCH")
            peak_activity = max(peak_activity, len(active))
            state["phase"], state["start_us"] = 1, row["elapsed_us"]
        elif kind in {"execute_enter", "handler_enter", "handler_return", "activity_end"}:
            shape(details, "invocation_id")
            exact(details["invocation_id"], invocation, "HISTORY_LINKAGE")
            expected_phase = {"execute_enter": 1, "handler_enter": 2,
                              "handler_return": 3, "activity_end": 4}[kind]
            require(state["phase"] == expected_phase and invocation in active, "COUNTER_MISMATCH")
            state["phase"] += 1
            if kind == "handler_enter":
                state["handler_start_us"] = row["elapsed_us"]
            elif kind == "handler_return":
                state["handler_end_us"] = row["elapsed_us"]
                require(state["handler_end_us"] - state["handler_start_us"] <= 1000000, "METADATA_MISMATCH")
            if kind == "activity_end":
                active.remove(invocation)
                state["end_us"] = row["elapsed_us"]
                require(state["end_us"] - state["start_us"] <= 10000000, "METADATA_MISMATCH")
        else:  # terminal, tied to an independently supplied original projection
            shape(details, "result_artifact_id receipt_id")
            require(state["phase"] == 5 and not state["terminal_seen"]
                    and job_id in outcomes, "OUTCOME_MISMATCH")
            require(row["elapsed_us"] - state["submit_us"] <= 60000000, "METADATA_MISMATCH")
            outcome = validate_batch_terminal(outcomes[job_id], job, state["run_id"])
            exact(details["result_artifact_id"], outcome["result_artifact_id"], "OUTCOME_MISMATCH")
            exact(details["receipt_id"], outcome["receipt_id"], "OUTCOME_MISMATCH")
            state["terminal_seen"], state["terminal_us"] = True, row["elapsed_us"]
            observed_outcomes.add(job_id)
            if batch_terminal_accepted(outcome):
                state["accepted"] = True
                outstanding -= 1
            else:
                latched, state["uncertain"] = True, True
    require(observed_outcomes == set(outcomes), "OUTCOME_MISMATCH")
    accepted = sum(state["accepted"] for state in states.values())
    passed = (reserved == accepted == 200 and outstanding == 0 and not latched and not active
              and all(state["phase"] == 5 and state["terminal_seen"] for state in states.values()))
    rows = []
    for job_id, state in states.items():
        rows.append({"job_id": job_id, "cohort": jobs[job_id]["cohort"],
                     "submitted": state["reserved"], "validated_terminal": state["accepted"],
                     "uncertain": state["uncertain"],
                     "queue_wait_us": None if state["start_us"] is None else state["start_us"] - state["submit_us"],
                     "activity_duration_us": None if state["end_us"] is None else state["end_us"] - state["start_us"],
                     "handler_duration_us": None if state["handler_end_us"] is None else state["handler_end_us"] - state["handler_start_us"],
                     "terminal_us": state["terminal_us"]})
    cohorts = []
    for cohort in ("a", "b"):
        selected = [row for row in rows if row["cohort"] == cohort]
        terminal = [row["terminal_us"] for row in selected if row["validated_terminal"]]
        cohorts.append({"cohort": cohort, "planned": 100,
                        "submitted": sum(row["submitted"] for row in selected),
                        "validated_terminal": len(terminal), "missing": 100 - len(terminal),
                        "last_validated_terminal_us": max(terminal) if terminal else None})
    summary = {"schema_version": BATCH_SCHEMA + "fixture-verdict.v1",
               "evidence_kind": "FABRICATED_UNIT_DATA", "acceptance": "PASS" if passed else "FAIL",
               "revision": expected_revision, "planned": 200, "reserved_attempts": reserved,
               "validated_terminal": accepted, "outstanding": outstanding, "unsubmitted": 200 - reserved,
               "uncertainty_latched": latched, "uncertain_jobs": sum(s["uncertain"] for s in states.values()),
               "peak_outstanding": peak_outstanding, "configured_activity_slots": 8,
               "observed_activity_peak": peak_activity, "active_at_end": len(active),
               "clock_scope": "SYNTHETIC_FIXTURE_MICROSECONDS", "observed_duration_us": last_us,
               "tool_outcomes": {name: sum(row["tool_status"] == name for row in outcomes.values())
                                 for name in ("COMPLETED", "FAILED", "BLOCKED")},
               "cohorts": cohorts, "jobs": rows}
    _batch_encoded(summary, BATCH_SUMMARY_BYTES)
    return summary


# The live profile is a separate trust boundary. Pure tests must explicitly use
# FABRICATED_UNIT_DATA and never emit a hosted-service acceptance verdict.
REAL_BATCH_PREFIX = "opendot.temporal.real-batch."
REAL_BATCH_NODE_NAMES = (
    "test_real_batch_delivers_200_bound_results",
    "test_real_batch_reservations_never_exceed_16",
    "test_real_batch_records_received_metadata_and_occupancy",
    "test_real_batch_observed_quiescence_and_shutdown",
)
REAL_BATCH_REQUIRED_NODES = tuple(
    "tests/acceptance/temporal_real_batch_gate.py::" + name for name in REAL_BATCH_NODE_NAMES)
REAL_BATCH_SOURCE_PATHS = tuple(sorted(set(BATCH_SOURCE_PATHS) | {
    "ci/requirements.txt", "pyproject.toml", "ci/temporal-real-batch-nodes.txt",
    "tests/acceptance/temporal_real_batch_gate.py", "docs/temporal-reference-transport.md",
    "tests/test_temporal_activity_contract.py", "tests/test_temporal_workflow_contract.py",
    "tests/test_temporal_transport_owner_boundaries.py",
    "src/opendot_engineering/__init__.py", "src/opendot_engineering/core/__init__.py",
    "src/opendot_engineering/adapters/__init__.py",
    "src/opendot_engineering/adapters/source_audit.py",
}))
REAL_BATCH_RETRY_DECLARATION = {
    "policy": "SDK_DEFAULT", "retry_config_supplied": False,
    "high_level_start_retry": True, "physical_rpc_count_claimed": False,
}
REAL_BATCH_AUDIT_FILES = (
    "environment.json", "batch-trace.json", "batch-metadata.json",
    "batch-histories.json", "batch-outcomes.json", "batch-cleanup.json", "diagnostic.json",
)
REAL_BATCH_ERRORS = frozenset({"handler_error", "execute_error", "activity_error", "uncertainty"})
REAL_BATCH_EVENTS = frozenset({
    "reservation", "rpc_enter", "acknowledgment", "activity_enter", "execute_enter",
    "handler_enter", "handler_return", "execute_return", "activity_exit",
    "workflow_result", "validated_terminal",
}) | REAL_BATCH_ERRORS
_RUN_PATTERN = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


def _real_encoded(value: object, maximum: int) -> bytes:
    """Bound plain data without invoking hooks or exposing rejected values."""
    budget = [300000]
    def plain(item, depth=0):
        budget[0] -= 1
        require(budget[0] >= 0 and depth <= 12, "SIZE_LIMIT")
        if item is None or type(item) is bool:
            return
        if type(item) is int:
            require(abs(item) <= 10 ** 15, "SIZE_LIMIT")
            return
        if type(item) is float:
            require(math.isfinite(item) and abs(item) <= 10 ** 15, "INVALID_TYPE")
            return
        if type(item) is str:
            require(len(item) <= 256, "SIZE_LIMIT")
            return
        if type(item) is list:
            require(len(item) <= BATCH_MAX_EVENTS, "SIZE_LIMIT")
            for child in item:
                plain(child, depth + 1)
            return
        require(type(item) is dict and len(item) <= 64, "INVALID_TYPE")
        for key, child in item.items():
            require(type(key) is str and len(key) <= 128, "INVALID_SCHEMA")
            plain(child, depth + 1)
    plain(value)
    data = json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")
    require(0 < len(data) <= maximum, "SIZE_LIMIT")
    return data


def real_batch_source_digests(source: Path | None = None) -> dict:
    source = ROOT if source is None else Path(source)
    result = {path: _sha(source / path) for path in REAL_BATCH_SOURCE_PATHS}
    for path, expected in BATCH_OWNER_SHA256.items():
        exact(result[path], expected, "OWNER_MISMATCH")
    return result


def checked_real_batch_nodes(nodes: object) -> tuple[str, ...]:
    require(type(nodes) in (list, tuple) and all(type(n) is str for n in nodes)
            and tuple(nodes) == REAL_BATCH_REQUIRED_NODES, "REQUIRED_NODES")
    return REAL_BATCH_REQUIRED_NODES


def read_real_batch_nodes(path: Path) -> tuple[str, ...]:
    try:
        return checked_real_batch_nodes(read_bytes(path, 8192).decode("ascii").splitlines())
    except UnicodeError:
        raise GateError("REQUIRED_NODES") from None


def verify_real_batch_collection(path: Path) -> list[str]:
    value = read_json(path)
    shape(value, "schema_version nodes")
    exact(value["schema_version"], REAL_BATCH_PREFIX + "collection.v1", "INVALID_SCHEMA")
    checked_real_batch_nodes(value["nodes"])
    return value["nodes"]


def verify_real_batch_junit(path: Path) -> list[dict]:
    return verify_collected_unit_junit(list(REAL_BATCH_REQUIRED_NODES), path,
        files=("tests/acceptance/temporal_real_batch_gate.py",), expected_count=4)


def _real_rows(value: object, maximum: int) -> list:
    require(type(value) is list and len(value) <= 200, "SIZE_LIMIT")
    for row in value:
        _real_encoded(row, maximum)
    return value


def validate_real_batch_metadata(row: object, job: dict, run_id: str | None = None) -> dict:
    _real_encoded(row, 1024)
    shape(row, "job_id entry_sequence workflow_id run_id activity_id activity_type namespace task_queue "
          "attempt is_local retry_policy_present maximum_attempts start_to_close_seconds "
          "schedule_to_close_seconds input_artifact_id metadata_source")
    expected = {"job_id": job["job_id"], "workflow_id": job["workflow_id"],
        "activity_id": ACTIVITY_ID, "activity_type": ACTIVITY_TYPE,
        "namespace": "default", "task_queue": "opendot-temporal-gate", "attempt": 1,
        "is_local": False, "retry_policy_present": True, "maximum_attempts": 1,
        "start_to_close_seconds": 10, "schedule_to_close_seconds": 60,
        "input_artifact_id": job["input_artifact_id"], "metadata_source": "real_sdk_activity_info"}
    for key, value in expected.items():
        exact(row[key], value, "METADATA_MISMATCH")
    integer(row["entry_sequence"], 1, BATCH_MAX_EVENTS, "METADATA_MISMATCH")
    match(row["run_id"], _RUN_PATTERN, "METADATA_MISMATCH")
    if run_id is not None:
        exact(row["run_id"], run_id, "METADATA_MISMATCH")
    return dict(row)


def validate_real_batch_outcome(row: object, job: dict, run_id: str | None = None) -> dict:
    _real_encoded(row, 1024)
    shape(row, "terminal original_validation receipt_report_kind scientific_validity "
          "device_control_authority independent_review owner_integration")
    terminal = row["terminal"]
    require(type(terminal) is dict, "OUTCOME_MISMATCH")
    result = validate_batch_terminal(terminal, job,
        terminal.get("run_id") if run_id is None else run_id)
    for key, expected in {
        "original_validation": "CAS_RECEIPT_INPUT_BOUND",
        "receipt_report_kind": "serialized_runtime_report_not_live_proof",
        "scientific_validity": False, "device_control_authority": False,
        "independent_review": "NOT_EVALUATED", "owner_integration": "NOT_EVALUATED",
    }.items():
        exact(row[key], expected, "OUTCOME_MISMATCH")
    return result


def validate_real_batch_history(row: object, job: dict, run_id: str,
                                terminal_projection: dict) -> dict:
    """Check bounded server-event linkage, independently from host event order.

    Raw histories remain private. Their digests and size declarations are
    consistency projections, not independent replay or a malicious-host proof.
    """
    _real_encoded(row, 16384)
    shape(row, "job_id workflow_id run_id raw_history_sha256 raw_history_bytes events")
    for key, expected in {"job_id": job["job_id"], "workflow_id": job["workflow_id"],
                          "run_id": run_id}.items():
        exact(row[key], expected, "HISTORY_MISMATCH")
    match(run_id, _RUN_PATTERN, "HISTORY_MISMATCH")
    digest(row["raw_history_sha256"])
    integer(row["raw_history_bytes"], 1, 65536, "SIZE_LIMIT")
    terminal = validate_batch_terminal(terminal_projection, job, run_id)
    events = row["events"]
    require(type(events) is list and 1 <= len(events) <= 64, "SIZE_LIMIT")
    allowed = set(EVENT_FIELDS) - {"ActivityTaskFailed", "WorkflowExecutionFailed", "WorkflowExecutionSignaled"}
    found = {name: [] for name in allowed}
    indexed, scheduled, started, completed = {}, set(), set(), set()
    for number, event in enumerate(events, 1):
        shape(event, "event_id event_type attributes")
        exact(event["event_id"], number, "HISTORY_LINKAGE")
        name, attrs = event["event_type"], event["attributes"]
        require(type(name) is str and name in allowed, "HISTORY_MISMATCH")
        fields = EVENT_FIELDS[name]
        if name == "WorkflowExecutionStarted":
            fields += " workflow_id original_execution_run_id first_execution_run_id attempt continued_execution_run_id"
        shape(attrs, fields)
        require(not found["WorkflowExecutionCompleted"], "HISTORY_LINKAGE")
        if name == "WorkflowExecutionStarted":
            exact(number, 1, "HISTORY_LINKAGE")
            for key, expected in {"workflow_type": "ReferenceBatchWorkflow", "task_queue": "opendot-temporal-gate",
                "execution_timeout_seconds": 120, "run_timeout_seconds": 120,
                "task_timeout_seconds": 10, "maximum_attempts": 1,
                "workflow_id": job["workflow_id"], "original_execution_run_id": run_id,
                "first_execution_run_id": run_id, "attempt": 1, "continued_execution_run_id": ""}.items():
                exact(attrs[key], expected, "HISTORY_MISMATCH")
        elif name == "WorkflowTaskScheduled":
            scheduled.add(number)
        elif name == "ActivityTaskScheduled":
            require(bool(found["WorkflowTaskCompleted"]), "HISTORY_LINKAGE")
            for key, expected in {"activity_type": ACTIVITY_TYPE, "activity_id": ACTIVITY_ID,
                "task_queue": "opendot-temporal-gate", "maximum_attempts": 1,
                "start_to_close_seconds": 10, "schedule_to_close_seconds": 60}.items():
                exact(attrs[key], expected, "HISTORY_MISMATCH")
        elif name in {"ActivityTaskStarted", "ActivityTaskCompleted", "WorkflowTaskStarted", "WorkflowTaskCompleted"}:
            is_activity = name.startswith("Activity")
            schedule_type = "ActivityTaskScheduled" if is_activity else "WorkflowTaskScheduled"
            sid = attrs["scheduled_event_id"]
            integer(sid, 1, number - 1, "HISTORY_LINKAGE")
            require(indexed[sid]["event_type"] == schedule_type, "HISTORY_LINKAGE")
            if name.endswith("Started"):
                if is_activity:
                    exact(attrs["attempt"], 1, "HISTORY_MISMATCH")
                    exact(attrs["identity"], "opendot-gate-activity-worker", "HISTORY_MISMATCH")
                else:
                    require(sid not in started, "HISTORY_LINKAGE")
                    started.add(sid)
                    exact(attrs["identity"], "opendot-gate-workflow-worker", "HISTORY_MISMATCH")
            else:
                tid = attrs["started_event_id"]
                integer(tid, 1, number - 1, "HISTORY_LINKAGE")
                require(indexed[tid]["event_type"] == schedule_type.replace("Scheduled", "Started")
                        and indexed[tid]["attributes"]["scheduled_event_id"] == sid, "HISTORY_LINKAGE")
                if is_activity:
                    _result_attributes(attrs, terminal["result_artifact_id"])
                    exact(attrs["result_size_bytes"], terminal["result_size_bytes"], "HISTORY_MISMATCH")
                else:
                    require(sid not in completed, "HISTORY_LINKAGE")
                    completed.add(sid)
                    exact(attrs["identity"], "opendot-gate-workflow-worker", "HISTORY_MISMATCH")
        elif name == "WorkflowExecutionCompleted":
            _result_attributes(attrs, terminal["result_artifact_id"])
            exact(attrs["result_size_bytes"], terminal["result_size_bytes"], "HISTORY_MISMATCH")
            require(bool(found["ActivityTaskCompleted"]) and number > 1
                    and indexed[number - 1]["event_type"] == "WorkflowTaskCompleted"
                    and scheduled == started == completed, "HISTORY_LINKAGE")
            require(found["WorkflowTaskCompleted"][-1]["event_id"]
                    > found["ActivityTaskCompleted"][-1]["event_id"], "HISTORY_LINKAGE")
        indexed[number] = event
        found[name].append(event)
    for name in ("WorkflowExecutionStarted", "ActivityTaskScheduled", "ActivityTaskStarted",
                 "ActivityTaskCompleted", "WorkflowExecutionCompleted"):
        exact(len(found[name]), 1, "HISTORY_MISMATCH")
    require(scheduled == started == completed and len(completed) >= 2, "HISTORY_LINKAGE")
    return dict(row)


def validate_real_batch_cleanup(value: object) -> None:
    _real_encoded(value, 65536)
    shape(value, "schema_version server_generations worker_generations all_reservations_accounted "
          "unresolved_start_operations unresolved_result_operations active_activity_calls handler_entries "
          "handler_returns execution_uncertainty observation_uncertainty in_flight_shutdown_attempted "
          "forced_termination_used cleanup_status cleanup_code elapsed_seconds")
    exact(value["schema_version"], REAL_BATCH_PREFIX + "cleanup.v1", "INVALID_SCHEMA")
    exact(value["all_reservations_accounted"], True, "CLEANUP_UNCONFIRMED")
    for key in ("unresolved_start_operations", "unresolved_result_operations", "active_activity_calls"):
        exact(value[key], 0, "CLEANUP_UNCONFIRMED")
    for key in ("execution_uncertainty", "observation_uncertainty", "in_flight_shutdown_attempted", "forced_termination_used"):
        exact(value[key], False, "CLEANUP_UNCONFIRMED")
    integer(value["handler_entries"], 0, 200, "CLEANUP_UNCONFIRMED")
    exact(value["handler_returns"], value["handler_entries"], "CLEANUP_UNCONFIRMED")
    exact(value["cleanup_status"], "PASS", "CLEANUP_UNCONFIRMED")
    exact(value["cleanup_code"], "OK", "CLEANUP_UNCONFIRMED")
    finite(value["elapsed_seconds"], 240, "CLEANUP_UNCONFIRMED")
    servers = value["server_generations"]
    require(type(servers) is list and len(servers) == 1, "CLEANUP_UNCONFIRMED")
    for row in servers:
        shape(row, "generation shutdown_requested_signal graceful_exit_observed exit_code readiness_seconds shutdown_seconds")
        for key, expected in {"generation": 1, "shutdown_requested_signal": "SIGINT",
                               "graceful_exit_observed": True, "exit_code": 0}.items():
            exact(row[key], expected, "CLEANUP_UNCONFIRMED")
        finite(row["readiness_seconds"], 10, "CLEANUP_UNCONFIRMED")
        finite(row["shutdown_seconds"], 8, "CLEANUP_UNCONFIRMED")
    workers = value["worker_generations"]
    require(type(workers) is list and len(workers) == 2, "CLEANUP_UNCONFIRMED")
    for number, (row, kind) in enumerate(zip(workers, ("workflow", "activity")), 1):
        shape(row, "generation type public_shutdown_called public_shutdown_completed")
        for key, expected in {"generation": number, "type": kind,
                             "public_shutdown_called": True, "public_shutdown_completed": True}.items():
            exact(row[key], expected, "CLEANUP_UNCONFIRMED")


def validate_real_batch_trace(trace: object, plan: object, profile: object,
                              metadata: object, histories: object, outcomes: object, *,
                              allow_test_data: bool = False, expected_revision: str | None = None,
                              source: Path | None = None) -> dict:
    _real_encoded(trace, BATCH_TRACE_BYTES)
    shape(trace, "schema_version evidence_kind revision source_sha256 clock_scope sdk_transport_retries plan profile events")
    exact(trace["schema_version"], REAL_BATCH_PREFIX + "trace.v1", "INVALID_SCHEMA")
    exact(type(allow_test_data), bool, "INVALID_TYPE")
    evidence_kind = "FABRICATED_UNIT_DATA" if allow_test_data else "HOSTED_REAL_SERVICE"
    exact(trace["evidence_kind"], evidence_kind, "INVALID_SCHEMA")
    exact(trace["clock_scope"], "HOST_MONOTONIC_OBSERVATIONS", "INVALID_SCHEMA")
    match(trace["revision"], r"[0-9a-f]{40}", "REVISION_MISMATCH")
    if expected_revision is not None:
        exact(trace["revision"], expected_revision, "REVISION_MISMATCH")
    exact(trace["source_sha256"], real_batch_source_digests(source), "SOURCE_MISMATCH")
    shape(trace["sdk_transport_retries"], set(REAL_BATCH_RETRY_DECLARATION))
    for key, value in REAL_BATCH_RETRY_DECLARATION.items():
        exact(trace["sdk_transport_retries"][key], value, "METADATA_MISMATCH")
    plan, profile = validate_batch_plan(plan), validate_batch_profile(profile)
    exact(validate_batch_plan(trace["plan"]), plan, "INVALID_SCHEMA")
    exact(validate_batch_profile(trace["profile"]), profile, "INVALID_SCHEMA")
    jobs = {job["job_id"]: job for job in plan["jobs"]}
    metas, finals, history_rows = {}, {}, {}
    seen_receipts, seen_results, history_digests = set(), set(), set()
    for row in _real_rows(metadata, 1024):
        require(type(row) is dict and type(row.get("job_id")) is str
                and row["job_id"] in jobs and row["job_id"] not in metas, "METADATA_MISMATCH")
        metas[row["job_id"]] = validate_real_batch_metadata(row, jobs[row["job_id"]])
    for row in _real_rows(outcomes, 1024):
        require(type(row) is dict and type(row.get("terminal")) is dict, "OUTCOME_MISMATCH")
        job_id = row["terminal"].get("job_id")
        require(type(job_id) is str and job_id in jobs and job_id not in finals, "OUTCOME_MISMATCH")
        terminal = validate_real_batch_outcome(row, jobs[job_id])
        require(terminal["receipt_id"] not in seen_receipts and terminal["result_artifact_id"] not in seen_results,
                "OUTCOME_MISMATCH")
        seen_receipts.add(terminal["receipt_id"])
        seen_results.add(terminal["result_artifact_id"])
        finals[job_id] = terminal
    for row in _real_rows(histories, 16384):
        require(type(row) is dict and type(row.get("job_id")) is str
                and row["job_id"] in finals and row["job_id"] not in history_rows, "HISTORY_MISMATCH")
        job_id = row["job_id"]
        result = validate_real_batch_history(row, jobs[job_id], finals[job_id]["run_id"], finals[job_id])
        require(result["raw_history_sha256"] not in history_digests, "HISTORY_MISMATCH")
        history_digests.add(result["raw_history_sha256"])
        history_rows[job_id] = result
    _real_encoded(metadata, 256 * 1024)
    _real_encoded(outcomes, 256 * 1024)
    _real_encoded(histories, 4 * 1024 * 1024)
    require(sum(row["raw_history_bytes"] for row in history_rows.values()) <= 16 * 1024 * 1024, "SIZE_LIMIT")
    states = {job_id: {"reserved": False, "rpc": False, "ack": False, "run": None,
        "phase": 0, "result": False, "terminal": False, "failed": False, "entry": None}
        for job_id in jobs}
    runs, active, handlers = {}, set(), set()
    reserved = outstanding = peak_outstanding = peak_activity = peak_handler = 0
    pending_submission = None
    latched = False
    execution_uncertainty = observation_uncertainty = False
    last_us = 0
    events = trace["events"]
    require(type(events) is list and len(events) <= BATCH_MAX_EVENTS, "SIZE_LIMIT")
    for number, row in enumerate(events, 1):
        _real_encoded(row, 1024)
        shape(row, "sequence elapsed_us event job_id run_id activity_id attempt reason_code")
        exact(row["sequence"], number, "COUNTER_MISMATCH")
        integer(row["elapsed_us"], 0, 600000000, "COUNTER_MISMATCH")
        require(row["elapsed_us"] >= last_us, "COUNTER_MISMATCH")
        last_us = row["elapsed_us"]
        job_id, event = row["job_id"], row["event"]
        require(type(event) is str and event in REAL_BATCH_EVENTS, "INVALID_SCHEMA")
        if event in REAL_BATCH_ERRORS:
            require(type(row["reason_code"]) is str and row["reason_code"] in BATCH_UNCERTAINTY_REASONS,
                    "INVALID_VALUE")
            if row["reason_code"] == "OBSERVER_FAILURE":
                observation_uncertainty = True
            if event != "uncertainty" or row["reason_code"] in {"RUNTIME_EXCEPTION", "RECONCILIATION_REQUIRED"}:
                execution_uncertainty = True
        else:
            exact(row["reason_code"], "OK")
        if job_id is None:
            require(event == "uncertainty", "OUTCOME_MISMATCH")
            for key in ("run_id", "activity_id", "attempt"):
                exact(row[key], None, "HISTORY_LINKAGE")
            latched = True
            continue
        require(type(job_id) is str and job_id in jobs, "OUTCOME_MISMATCH")
        state = states[job_id]
        invocation_event = event.startswith(("activity_", "execute_", "handler_"))
        if invocation_event:
            exact(row["activity_id"], ACTIVITY_ID, "HISTORY_LINKAGE")
            exact(row["attempt"], 1, "HISTORY_LINKAGE")
        else:
            exact(row["activity_id"], None, "HISTORY_LINKAGE")
            exact(row["attempt"], None, "HISTORY_LINKAGE")
        if event in {"reservation", "rpc_enter"}:
            exact(row["run_id"], None, "HISTORY_LINKAGE")
        elif row["run_id"] is None:
            require(event == "uncertainty", "HISTORY_LINKAGE")
        else:
            match(row["run_id"], _RUN_PATTERN, "HISTORY_LINKAGE")
            require(row["run_id"] not in runs or runs[row["run_id"]] == job_id, "HISTORY_LINKAGE")
            require(state["run"] is None or state["run"] == row["run_id"], "HISTORY_LINKAGE")
            state["run"], runs[row["run_id"]] = row["run_id"], job_id
        if event == "reservation":
            require(not latched and not state["reserved"] and reserved < 200
                    and job_id == plan["jobs"][reserved]["job_id"] and outstanding < 16
                    and pending_submission is None,
                    "COUNTER_MISMATCH")
            pending_submission = job_id
            state["reserved"] = True
            reserved += 1
            outstanding += 1
            peak_outstanding = max(peak_outstanding, outstanding)
            continue
        require(state["reserved"], "COUNTER_MISMATCH")
        if event == "uncertainty":
            latched = True
            if row["reason_code"] in {"RUNTIME_EXCEPTION", "RECONCILIATION_REQUIRED", "OBSERVER_FAILURE"}:
                state["failed"] = True
            continue
        if event == "rpc_enter":
            require(not latched and not state["rpc"] and pending_submission == job_id, "COUNTER_MISMATCH")
            state["rpc"] = True
            continue
        require(state["rpc"], "COUNTER_MISMATCH")
        if event == "acknowledgment":
            require(not state["ack"] and pending_submission == job_id, "HISTORY_LINKAGE")
            state["ack"] = True
            pending_submission = None
        elif event == "activity_enter":
            require(state["phase"] == 0 and job_id in metas, "COUNTER_MISMATCH")
            validate_real_batch_metadata(metas[job_id], jobs[job_id], state["run"])
            exact(metas[job_id]["entry_sequence"], number, "METADATA_MISMATCH")
            state["phase"], state["entry"] = 1, number
            active.add(job_id)
            require(len(active) <= 8, "COUNTER_MISMATCH")
            peak_activity = max(peak_activity, len(active))
        elif event in {"execute_enter", "handler_enter", "handler_return", "handler_error",
                        "execute_return", "execute_error", "activity_exit", "activity_error"}:
            phase = {"execute_enter": 1, "handler_enter": 2, "handler_return": 3,
                "handler_error": 3, "execute_return": 4, "execute_error": 4,
                "activity_exit": 5, "activity_error": 5}[event]
            # An exception may prevent entry into the inner callable entirely.
            allowed_phases = {phase} if event not in {"execute_error", "activity_error"} else (
                {2, 4} if event == "execute_error" else {1, 5})
            require(state["phase"] in allowed_phases and job_id in active, "COUNTER_MISMATCH")
            state["phase"] = phase + 1
            if event == "handler_enter":
                handlers.add(job_id)
                peak_handler = max(peak_handler, len(handlers))
            elif event in {"handler_return", "handler_error"}:
                require(job_id in handlers, "COUNTER_MISMATCH")
                handlers.remove(job_id)
            elif event in {"activity_exit", "activity_error"}:
                active.remove(job_id)
            if event in REAL_BATCH_ERRORS:
                state["failed"] = latched = True
        elif event == "workflow_result":
            require(state["ack"] and state["phase"] == 6 and not state["result"], "HISTORY_LINKAGE")
            state["result"] = True
        elif event == "validated_terminal":
            require(state["ack"] and state["phase"] == 6 and state["result"] and not state["terminal"]
                    and job_id in metas and job_id in finals and job_id in history_rows, "OUTCOME_MISMATCH")
            validate_real_batch_metadata(metas[job_id], jobs[job_id], state["run"])
            terminal = validate_batch_terminal(finals[job_id], jobs[job_id], state["run"])
            require(batch_terminal_accepted(terminal) and not state["failed"], "OUTCOME_MISMATCH")
            state["terminal"] = True
            outstanding -= 1
    require(set(metas) == {j for j, s in states.items() if s["entry"] is not None}, "METADATA_MISMATCH")
    require(set(finals) <= {j for j, s in states.items() if s["result"]}, "OUTCOME_MISMATCH")
    accepted = sum(state["terminal"] for state in states.values())
    passed = (reserved == accepted == len(metas) == len(finals) == len(history_rows) == 200
        and not outstanding and not latched and not active and not handlers)
    tables = {"source": trace["source_sha256"], "metadata": metadata,
              "history": histories, "outcomes": outcomes}
    summary = {"schema_version": REAL_BATCH_PREFIX + ("fixture-verdict.v1" if allow_test_data else "verdict.v1"),
        "evidence_kind": evidence_kind, "revision": trace["revision"],
        "delivery_admission_acceptance": "PASS" if passed else "FAIL",
        "activity_overlap": "DEMONSTRATED" if peak_activity >= 2 and not active else "NOT_DEMONSTRATED",
        "handler_overlap": "DEMONSTRATED" if peak_handler >= 2 and not handlers else "NOT_DEMONSTRATED",
        "observed_activity_peak": peak_activity, "observed_handler_peak": peak_handler,
        "configured_activity_slots": 8, "planned": 200, "reserved_attempts": reserved,
        "peak_outstanding": peak_outstanding,
        "logical_application_starts": sum(state["rpc"] for state in states.values()),
        "validated_terminal": accepted, "outstanding": outstanding, "unsubmitted": 200 - reserved,
        "uncertainty_latched": latched, "active_at_end": len(active), "handlers_active_at_end": len(handlers),
        "handler_entries": sum(row["event"] == "handler_enter" for row in events),
        "handler_returns": sum(row["event"] == "handler_return" for row in events),
        "execution_uncertainty": execution_uncertainty, "observation_uncertainty": observation_uncertainty,
        "clock_scope": "HOST_MONOTONIC_OBSERVATIONS", "observed_duration_us": last_us,
        "sdk_transport_retries": dict(REAL_BATCH_RETRY_DECLARATION),
        "table_sha256": {key: hashlib.sha256(_real_encoded(value, 4 * 1024 * 1024)).hexdigest()
                         for key, value in tables.items()},
        "table_cardinalities": {key: len(value) for key, value in tables.items()},
        "cpu_parallelism": "NOT_EVALUATED", "scientific_validity": False,
        "device_control_authority": False, "independent_review": "NOT_EVALUATED"}
    _real_encoded(summary, BATCH_SUMMARY_BYTES)
    return summary


def _read_real_table(path: Path, kind: str, maximum: int) -> list:
    value = strict_json(read_bytes(path, maximum))
    shape(value, "schema_version rows")
    exact(value["schema_version"], REAL_BATCH_PREFIX + kind + ".v1", "INVALID_SCHEMA")
    require(type(value["rows"]) is list, "INVALID_TYPE")
    return value["rows"]


# An export is a fresh, bounded projection, never an upload of the audit tree.
PUBLIC_RETENTION_DAYS = 30
PUBLIC_WORKFLOW_PATH = ".github/workflows/temporal-server.yml"
# Updated only alongside an explicitly reviewed exact workflow candidate.
PUBLIC_WORKFLOW_SHA256 = "e5b80d0623c8628c8918a8a230fa2c1694fc667b12b96785f26500a859de64a7"


def validate_public_batch_workflow(source: bytes) -> None:
    # A closed byte contract is intentionally stricter than a permissive YAML
    # subset parser. Quotes, aliases, extra actions, broadened conditions or
    # permissions cannot bypass the guard by alternate YAML spelling.
    require(type(source) is bytes and 0 < len(source) <= 65536, "SIZE_LIMIT")
    exact(hashlib.sha256(source).hexdigest(), PUBLIC_WORKFLOW_SHA256, "SOURCE_MISMATCH")


PUBLIC_FILE_LIMITS = {
    "environment.json": 65536, "batch-trace.json": BATCH_TRACE_BYTES,
    "batch-metadata.json": 256 * 1024, "batch-histories.json": 4 * 1024 * 1024,
    "batch-outcomes.json": 256 * 1024, "batch-cleanup.json": 65536,
    "batch-summary.json": BATCH_SUMMARY_BYTES,
}
PUBLIC_TOTAL_BYTES = 10 * 1024 * 1024
PUBLIC_MANIFEST_BYTES = 16384


def _plain_directory(path: Path) -> None:
    # Trusted cooperative POSIX host only. Check ancestors too, without resolving
    # links away. These checks do not provide hostile-filesystem race exclusion.
    require(".." not in path.parts, "PRIVACY_REJECTED")
    for part in (path.absolute(), *path.absolute().parents):
        require(not part.is_symlink(), "PRIVACY_REJECTED")
        require(part.is_dir(), "MISSING_EVIDENCE")


def _file_identity(info) -> tuple:
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def _snapshot_file(path: Path, maximum: int) -> tuple[bytes, tuple]:
    _plain_directory(path.parent)
    try:
        before = path.lstat()
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1, "PRIVACY_REJECTED")
        require(0 < before.st_size <= maximum, "SIZE_LIMIT")
        with path.open("rb") as stream:
            opened = os.fstat(stream.fileno())
            exact(_file_identity(opened), _file_identity(before), "SOURCE_MISMATCH")
            data = stream.read(maximum + 1)
            exact(_file_identity(os.fstat(stream.fileno())), _file_identity(before), "SOURCE_MISMATCH")
        exact(_file_identity(path.lstat()), _file_identity(before), "SOURCE_MISMATCH")
    except FileNotFoundError:
        raise GateError("MISSING_EVIDENCE") from None
    except OSError:
        raise GateError("READ_FAILED") from None
    require(0 < len(data) <= maximum and len(data) == before.st_size, "SIZE_LIMIT")
    return data, _file_identity(before)


def _directory_names(path: Path) -> set[str]:
    _plain_directory(path)
    try:
        return {item.name for item in path.iterdir()}
    except OSError:
        raise GateError("READ_FAILED") from None


def _batch_snapshot(audit: Path) -> tuple[dict, dict, set]:
    limits = {name: limit for name, limit in PUBLIC_FILE_LIMITS.items() if name != "batch-summary.json"}
    limits.update({"diagnostic.json": DIAGNOSTIC_MAX_BYTES, "collection-receipt.json": 65536})
    names = _directory_names(audit)
    require(set(limits) <= names <= set(limits) | {"batch-acceptance.json"}, "PRIVACY_REJECTED")
    snapshot = {name: _snapshot_file(audit / name, limit) for name, limit in limits.items()}
    if "batch-acceptance.json" in names:
        # Optional prior CLI summary is not exported or trusted, but must still
        # be a stable bounded regular file rather than an ignored link.
        snapshot["batch-acceptance.json"] = _snapshot_file(audit / "batch-acceptance.json", BATCH_SUMMARY_BYTES)
    return {name: strict_json(pair[0]) for name, pair in snapshot.items()}, snapshot, names


def _same_snapshot(audit: Path, snapshot: dict, names: set) -> None:
    exact(_directory_names(audit), names, "SOURCE_MISMATCH")
    for name, (data, identity) in snapshot.items():
        observed, stamp = _snapshot_file(audit / name, len(data))
        exact(stamp, identity, "SOURCE_MISMATCH")
        exact(observed, data, "SOURCE_MISMATCH")


def _validate_real_batch_records(records: dict, expected_revision: str, *,
                                 recheck_run_url: str | None = None) -> dict:
    environment = records["environment.json"]
    if recheck_run_url is None:
        validate_environment(environment, expected_revision)
    else:
        validate_environment(environment, expected_revision, recheck_run_url=recheck_run_url)
    trace = records["batch-trace.json"]
    require(type(trace) is dict, "INVALID_SCHEMA")
    tables = []
    for name, kind in (("batch-metadata.json", "metadata"), ("batch-histories.json", "history"),
                       ("batch-outcomes.json", "outcomes")):
        value = records[name]
        shape(value, "schema_version rows")
        exact(value["schema_version"], REAL_BATCH_PREFIX + kind + ".v1", "INVALID_SCHEMA")
        tables.append(value["rows"])
    summary = validate_real_batch_trace(trace, trace.get("plan"), trace.get("profile"), *tables,
                                        expected_revision=expected_revision)
    cleanup = records["batch-cleanup.json"]
    validate_real_batch_cleanup(cleanup)
    for key in ("handler_entries", "handler_returns", "execution_uncertainty", "observation_uncertainty"):
        exact(cleanup[key], summary[key], "CLEANUP_UNCONFIRMED")
    exact(summary["outstanding"], 0, "CLEANUP_UNCONFIRMED")
    exact(summary["active_at_end"], cleanup["active_activity_calls"], "CLEANUP_UNCONFIRMED")
    exact(summary["handlers_active_at_end"], 0, "CLEANUP_UNCONFIRMED")
    if summary["delivery_admission_acceptance"] == "PASS":
        exact(cleanup["handler_entries"], 200, "CLEANUP_UNCONFIRMED")
    summary["cleanup_verified"] = True
    summary["workflow_run_url"] = environment["workflow_run_url"]
    _real_encoded(summary, BATCH_SUMMARY_BYTES)
    return summary


def _validate_real_batch_snapshot(records: dict, expected_revision: str) -> dict:
    read_real_batch_nodes(ROOT / "ci/temporal-real-batch-nodes.txt")
    collection = records["collection-receipt.json"]
    shape(collection, "schema_version nodes")
    exact(collection["schema_version"], REAL_BATCH_PREFIX + "collection.v1", "INVALID_SCHEMA")
    checked_real_batch_nodes(collection["nodes"])
    diagnostic = validate_diagnostic(records["diagnostic.json"], expected_revision)
    exact(diagnostic["status"], "COMPLETE", "DIAGNOSTIC_FAILED")
    return _validate_real_batch_records(records, expected_revision)


def validate_real_batch_audit(audit: Path, expected_revision: str) -> dict:
    audit = Path(audit)
    records, snapshot, names = _batch_snapshot(audit)
    summary = _validate_real_batch_snapshot(records, expected_revision)
    _same_snapshot(audit, snapshot, names)
    return summary


def _public_summary(summary: dict) -> dict:
    return {"schema_version": REAL_BATCH_PREFIX + "public-summary.v1",
        "projection_kind": "PUBLIC_PROJECTION", "summary": summary,
        "recorded_passed_nodes": list(REAL_BATCH_REQUIRED_NODES),
        "original_cas_receipts_and_raw_history_included": False,
        "independent_original_replay": "NOT_EVALUATED"}


def export_real_batch_public_bundle(audit: Path, required: Path, junit: Path,
                                    expected_revision: str, destination: Path) -> dict:
    """Validate frozen actual bytes, construct only eight named public files.

    No test-data switch, directory copying, raw evidence, or upload is performed.
    Existing validation owners establish the exact allowlisted shapes and values.
    """
    validate_public_batch_workflow(read_bytes(ROOT / PUBLIC_WORKFLOW_PATH, 65536))
    run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT")
    match(run_attempt, r"[1-9][0-9]{0,4}", "CI_IDENTITY")
    run_attempt = int(run_attempt)
    _plain_directory(destination.parent)
    require(not destination.exists() and not destination.is_symlink(), "WRITE_FAILED")
    require(destination.absolute() != audit.absolute()
            and audit.absolute() not in destination.absolute().parents, "PRIVACY_REJECTED")
    records, snapshot, names = _batch_snapshot(audit)
    required_snapshot = _snapshot_file(required, 8192)
    junit_snapshot = _snapshot_file(junit, 2 * 1024 * 1024)
    read_real_batch_nodes(required)
    nodes = verify_real_batch_junit(junit)
    require(all(row["outcome"] == "PASS" for row in nodes), "TEST_FAILED")
    summary = _validate_real_batch_snapshot(records, expected_revision)
    exact(summary["delivery_admission_acceptance"], "PASS", "OUTCOME_MISMATCH")
    # Serialization uses only values from the already validated snapshot, never
    # a second unchecked audit read. Canonical JSON strips source formatting.
    values = {name: records[name] for name in PUBLIC_FILE_LIMITS if name != "batch-summary.json"}
    values["batch-summary.json"] = _public_summary(summary)
    encoded = {name: _real_encoded(value, PUBLIC_FILE_LIMITS[name] - 1) + b"\n"
               for name, value in values.items()}
    manifest = {"schema_version": REAL_BATCH_PREFIX + "public-bundle.v1",
        "projection_kind": "PUBLIC_PROJECTION", "evidence_kind": summary["evidence_kind"],
        "revision": expected_revision, "workflow_run_url": summary["workflow_run_url"],
        "run_attempt": run_attempt, "workflow_path": PUBLIC_WORKFLOW_PATH,
        "workflow_sha256": records["batch-trace.json"]["source_sha256"][PUBLIC_WORKFLOW_PATH],
        "retention_days": PUBLIC_RETENTION_DAYS,
        "provenance": "RECORDED_HOSTED_ASSERTIONS_NOT_INDEPENDENT_PROOF",
        "files": {name: {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
                  for name, data in encoded.items()}}
    encoded["manifest.json"] = _real_encoded(manifest, PUBLIC_MANIFEST_BYTES - 1) + b"\n"
    require(sum(map(len, encoded.values())) <= PUBLIC_TOTAL_BYTES, "SIZE_LIMIT")
    _same_snapshot(audit, snapshot, names)
    exact(_snapshot_file(required, 8192), required_snapshot, "SOURCE_MISMATCH")
    exact(_snapshot_file(junit, 2 * 1024 * 1024), junit_snapshot, "SOURCE_MISMATCH")
    try:
        # Private sibling staging never matches the workflow's dedicated path.
        with tempfile.TemporaryDirectory(prefix=".opendot-public-stage-", dir=destination.parent) as staging:
            stage = Path(staging)
            for name, data in encoded.items():
                with (stage / name).open("xb") as output:
                    output.write(data)
            exact(_directory_names(stage), set(encoded), "WRITE_FAILED")
            for name, data in encoded.items():
                exact(_snapshot_file(stage / name, len(data))[0], data, "WRITE_FAILED")
            _same_snapshot(audit, snapshot, names)
            exact(_snapshot_file(required, 8192), required_snapshot, "SOURCE_MISMATCH")
            exact(_snapshot_file(junit, 2 * 1024 * 1024), junit_snapshot, "SOURCE_MISMATCH")
            require(not destination.exists() and not destination.is_symlink(), "WRITE_FAILED")
            exact(real_batch_source_digests(), records["batch-trace.json"]["source_sha256"], "SOURCE_MISMATCH")
            stage.rename(destination)
    except OSError:
        raise GateError("WRITE_FAILED") from None
    return manifest


def recheck_real_batch_public_bundle(bundle: Path, expected_revision: str, expected_run_url: str,
                                     expected_run_attempt: int) -> dict:
    """Recompute projection consistency against this exact reviewed source tree.

    This is not original CAS/receipt validation or SDK replay, and does not
    independently authenticate assertions made by the original trusted host.
    """
    integer(expected_run_attempt, 1, 99999, "CI_IDENTITY")
    names = _directory_names(bundle)
    exact(names, set(PUBLIC_FILE_LIMITS) | {"manifest.json"}, "PRIVACY_REJECTED")
    limits = PUBLIC_FILE_LIMITS | {"manifest.json": PUBLIC_MANIFEST_BYTES}
    snapshot = {name: _snapshot_file(bundle / name, maximum) for name, maximum in limits.items()}
    require(sum(len(pair[0]) for pair in snapshot.values()) <= PUBLIC_TOTAL_BYTES, "SIZE_LIMIT")
    values = {name: strict_json(pair[0]) for name, pair in snapshot.items()}
    manifest = values["manifest.json"]
    shape(manifest, "schema_version projection_kind evidence_kind revision workflow_run_url run_attempt workflow_path workflow_sha256 retention_days provenance files")
    for key, value in {"schema_version": REAL_BATCH_PREFIX + "public-bundle.v1",
        "projection_kind": "PUBLIC_PROJECTION", "evidence_kind": values["batch-trace.json"].get("evidence_kind"),
        "revision": expected_revision, "workflow_run_url": expected_run_url,
        "run_attempt": expected_run_attempt, "workflow_path": PUBLIC_WORKFLOW_PATH,
        "workflow_sha256": values["batch-trace.json"]["source_sha256"][PUBLIC_WORKFLOW_PATH],
        "retention_days": PUBLIC_RETENTION_DAYS,
        "provenance": "RECORDED_HOSTED_ASSERTIONS_NOT_INDEPENDENT_PROOF"}.items():
        exact(manifest[key], value, "INVALID_SCHEMA")
    shape(manifest["files"], set(PUBLIC_FILE_LIMITS))
    for name in PUBLIC_FILE_LIMITS:
        entry = manifest["files"][name]
        shape(entry, "sha256 bytes")
        data = snapshot[name][0]
        exact(entry["bytes"], len(data), "SIZE_LIMIT")
        exact(entry["sha256"], hashlib.sha256(data).hexdigest(), "SOURCE_MISMATCH")
    summary = _validate_real_batch_records(values, expected_revision, recheck_run_url=expected_run_url)
    exact(summary["delivery_admission_acceptance"], "PASS", "OUTCOME_MISMATCH")
    exact(_real_encoded(values["batch-summary.json"], BATCH_SUMMARY_BYTES),
          _real_encoded(_public_summary(summary), BATCH_SUMMARY_BYTES), "OUTCOME_MISMATCH")
    _same_snapshot(bundle, snapshot, names)
    return {"schema_version": REAL_BATCH_PREFIX + "public-recheck.v1",
        "projection_consistency": "PASS", "revision": expected_revision,
        "workflow_run_url": expected_run_url, "run_attempt": expected_run_attempt, "summary": summary,
        "independent_original_replay": "NOT_EVALUATED"}


def _public_bundle_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Offline public projection consistency only; no service or SDK replay")
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--expected-run-url", required=True)
    parser.add_argument("--expected-run-attempt", required=True, type=int)
    args = parser.parse_args(argv)
    try:
        result = recheck_real_batch_public_bundle(args.bundle, args.expected_revision, args.expected_run_url, args.expected_run_attempt)
    except GateError as error:
        result = {"projection_consistency": "FAIL", "reason_code": error.code}
    except Exception:
        result = {"projection_consistency": "FAIL", "reason_code": "INTERNAL_ERROR"}
    print(_encode(result))
    return 0 if result["projection_consistency"] == "PASS" else 1


def _real_batch_main(args) -> int:
    """Hosted batch route; optionally construct the exact validated public projection."""
    reasons, summary = [], None
    nodes = [{"node_id": node, "outcome": "NOT_RUN", "reason_code": "NOT_RUN"}
             for node in REAL_BATCH_REQUIRED_NODES]
    collected = 0
    for operation in (lambda: read_real_batch_nodes(args.required),
                      lambda: verify_real_batch_collection(args.audit / "collection-receipt.json")):
        try:
            result = operation()
            collected = len(result) if type(result) is list else collected
        except GateError as error:
            reasons.append(error.code)
        except Exception:
            reasons.append("INTERNAL_ERROR")
    try:
        nodes = verify_real_batch_junit(args.junit)
        reasons.extend(row["reason_code"] for row in nodes if row["outcome"] != "PASS")
    except GateError as error:
        reasons.append(error.code)
    except Exception:
        reasons.append("INTERNAL_ERROR")
    try:
        summary = validate_real_batch_audit(args.audit, args.expected_revision)
        if summary["delivery_admission_acceptance"] != "PASS":
            reasons.append("OUTCOME_MISMATCH")
    except GateError as error:
        reasons.append(error.code)
    except Exception:
        reasons.append("INTERNAL_ERROR")
    diagnostic = read_safe_diagnostic(args.audit, args.expected_revision)
    if diagnostic["validation"] != "VALID":
        reasons.append(diagnostic["reason_code"])
    elif diagnostic["diagnostic"]["status"] != "COMPLETE":
        reasons.append("DIAGNOSTIC_FAILED")
    # This distinct envelope has no unqualified PASS that could imply overlap.
    revision = args.expected_revision if type(args.expected_revision) is str and re.fullmatch(
        r"[0-9a-f]{40}", args.expected_revision) else None
    report = {"schema_version": REAL_BATCH_PREFIX + "acceptance.v1", "profile": "batch200",
        "evidence_kind": "HOSTED_REAL_SERVICE", "revision": revision,
        "required_node_count": 4, "collected_node_count": collected, "nodes": nodes,
        "delivery_admission_acceptance": "PASS" if not reasons and summary is not None else "FAIL",
        "activity_overlap": summary["activity_overlap"] if summary is not None else "NOT_DEMONSTRATED",
        "reason_codes": sorted(set(reasons)) or ["OK"], "summary": summary}
    def failed_write():
        report["delivery_admission_acceptance"] = "FAIL"
        report["reason_codes"] = sorted(set(report["reason_codes"]) - {"OK"} | {"WRITE_FAILED"})
    try:
        require(not args.audit.is_symlink(), "WRITE_FAILED")
        args.audit.mkdir(parents=True, exist_ok=True)
        target = args.audit / "batch-acceptance.json"
        require(not target.is_symlink(), "WRITE_FAILED")
        target.write_bytes(_real_encoded(report, BATCH_SUMMARY_BYTES - 1) + b"\n")
    except (OSError, GateError):
        failed_write()
    if args.public_bundle is not None and report["delivery_admission_acceptance"] == "PASS":
        try:
            export_real_batch_public_bundle(args.audit, args.required, args.junit,
                                            args.expected_revision, args.public_bundle)
        except GateError as error:
            report["delivery_admission_acceptance"] = "FAIL"
            report["reason_codes"] = sorted(set(report["reason_codes"]) - {"OK"} | {error.code})
        except Exception:
            report["delivery_admission_acceptance"] = "FAIL"
            report["reason_codes"] = sorted(set(report["reason_codes"]) - {"OK"} | {"INTERNAL_ERROR"})
        if report["delivery_admission_acceptance"] == "FAIL":
            try:
                target.write_bytes(_real_encoded(report, BATCH_SUMMARY_BYTES - 1) + b"\n")
            except (OSError, GateError):
                failed_write()
    if args.summary:
        try:
            require(not args.summary.is_symlink(), "WRITE_FAILED")
            with args.summary.open("a", encoding="utf-8") as output:
                output.write("Temporal batch delivery/admission: " + report["delivery_admission_acceptance"]
                    + "; Activity overlap: " + report["activity_overlap"] + "\n" + _encode(report) + "\n")
        except (OSError, GateError):
            failed_write()
            try:
                require(not args.audit.is_symlink() and not (args.audit / "batch-acceptance.json").is_symlink(), "WRITE_FAILED")
                (args.audit / "batch-acceptance.json").write_bytes(_real_encoded(report, BATCH_SUMMARY_BYTES - 1) + b"\n")
            except (OSError, GateError):
                pass
    print(_encode(report))
    print(_encode(diagnostic))
    return 0 if report["delivery_admission_acceptance"] == "PASS" else 1




# ADR 008 DAG2: bounded, closed evidence consistency checks.
# Tables copied verbatim from the sealed design; no runtime schema dependency.
DAG2_SCHEMAS = {'bootstrap': {'additionalProperties': False,
               'properties': {'activity_executor_threads': {'const': 1},
                              'activity_slots': {'const': 1},
                              'constructed_seq': {'maximum': 512,
                                                  'minimum': 1,
                                                  'type': 'integer',
                                                  'x-python-exact-type': 'int'},
                              'eager_activity_execution': {'const': False},
                              'first_execution_run_id': {'maxLength': 128, 'minLength': 1, 'type': 'string'},
                              'generation': {'maximum': 8,
                                             'minimum': 1,
                                             'type': 'integer',
                                             'x-python-exact-type': 'int'},
                              'handler_source_sha256': {'const': 'a97dadac88bed7b09d2398516617216cb865ae97db411c12b72de01d7a78d1cb'},
                              'immutable_config': {'const': True},
                              'mission': {'enum': ['hosted-normal',
                                                   'hosted-reconcile',
                                                   'hosted-no-ref-cancel']},
                              'namespace': {'const': 'default'},
                              'origin_capture_seq': {'anyOf': [{'maximum': 512,
                                                                'minimum': 1,
                                                                'type': 'integer',
                                                                'x-python-exact-type': 'int'},
                                                               {'type': 'null'}]},
                              'original_A_sha256': {'anyOf': [{'pattern': '^[0-9a-f]{64}$', 'type': 'string'},
                                                              {'type': 'null'}]},
                              'original_B_sha256': {'const': None},
                              'registration_sha256': {'const': '5f2b1e81954530f31c7d2c83b9c582883b8391190ebe13b69b8bf91f044cb0c3'},
                              'request_eager_start': {'const': False},
                              'run_id': {'maxLength': 128, 'minLength': 1, 'type': 'string'},
                              'source_verified': {'const': True},
                              'started_seq': {'maximum': 512,
                                              'minimum': 1,
                                              'type': 'integer',
                                              'x-python-exact-type': 'int'},
                              'task_queue': {'maxLength': 128,
                                             'minLength': 1,
                                             'pattern': '^[A-Za-z0-9._-]+$',
                                             'type': 'string'},
                              'workflow_id': {'maxLength': 128, 'minLength': 1, 'type': 'string'},
                              'workflow_task_slots': {'const': 1}},
               'required': ['mission',
                            'workflow_id',
                            'run_id',
                            'first_execution_run_id',
                            'namespace',
                            'task_queue',
                            'generation',
                            'constructed_seq',
                            'started_seq',
                            'handler_source_sha256',
                            'registration_sha256',
                            'original_A_sha256',
                            'original_B_sha256',
                            'origin_capture_seq',
                            'source_verified',
                            'immutable_config',
                            'activity_slots',
                            'activity_executor_threads',
                            'workflow_task_slots',
                            'eager_activity_execution',
                            'request_eager_start'],
               'type': 'object',
               'x-python-exact-type': 'dict'},
 'claims': {'additionalProperties': False,
            'properties': {'actual_crash_process_fencing': {'const': 'NOT_EVALUATED'},
                           'device_control_authority': {'const': False},
                           'external_effect_authenticity': {'const': 'NOT_PROVED'},
                           'independent_review': {'const': 'NOT_EVALUATED'},
                           'issue_7_closed': {'const': False},
                           'lost_network_ack': {'const': 'NOT_EVALUATED'},
                           'natural_300_second_deadline': {'const': 'NOT_EVALUATED'},
                           'owner_integration': {'const': 'NOT_EVALUATED'},
                           'scientific_validity': {'const': False},
                           'termination_status': {'const': 'NOT_ESTABLISHED'}},
            'required': ['external_effect_authenticity',
                         'termination_status',
                         'scientific_validity',
                         'device_control_authority',
                         'independent_review',
                         'owner_integration',
                         'actual_crash_process_fencing',
                         'lost_network_ack',
                         'natural_300_second_deadline',
                         'issue_7_closed'],
            'type': 'object',
            'x-python-exact-type': 'dict'},
 'cleanup': {'additionalProperties': False,
             'properties': {'accepted_updates_unfinished': {'const': 0},
                            'activity_executor_shutdown_calls': {'const': 4},
                            'all_scheduled_invocations_terminal': {'const': True},
                            'cleanup_status': {'const': 'PASS'},
                            'evidence_and_pytest_elapsed_ms': {'maximum': 30000,
                                                               'minimum': 0,
                                                               'type': 'integer',
                                                               'x-python-exact-type': 'int'},
                            'evidence_class': {'enum': ['FABRICATED_UNIT_DATA', 'OBSERVED_HOSTED_CANDIDATE']},
                            'final_stop_elapsed_ms': {'maximum': 20000,
                                                      'minimum': 0,
                                                      'type': 'integer',
                                                      'x-python-exact-type': 'int'},
                            'force_or_task_cancellation_calls': {'const': 0},
                            'handler_entries': {'const': 5},
                            'handler_returns': {'const': 5},
                            'in_flight_calls': {'const': 0},
                            'observation_cleanup_elapsed_ms': {'maximum': 40000,
                                                               'minimum': 0,
                                                               'type': 'integer',
                                                               'x-python-exact-type': 'int'},
                            'pending_rpc_tasks': {'const': 0},
                            'public_worker_shutdown_calls': {'const': 8},
                            'same_cas': {'const': True},
                            'same_sqlite': {'const': True},
                            'scenario_elapsed_ms': {'maximum': 150000,
                                                    'minimum': 0,
                                                    'type': 'integer',
                                                    'x-python-exact-type': 'int'},
                            'schema_version': {'const': 'opendot.temporal.dag2-gate.cleanup.v1'},
                            'server_exit_code': {'const': 0},
                            'server_generations': {'const': 1},
                            'server_shutdown_calls': {'const': 1},
                            'server_shutdown_elapsed_ms': {'maximum': 8000,
                                                           'minimum': 0,
                                                           'type': 'integer',
                                                           'x-python-exact-type': 'int'},
                            'server_shutdown_signal': {'const': 'SIGINT'},
                            'server_stop_observed': {'const': True},
                            'stop_uncertain': {'const': False},
                            'worker_stops': {'items': {'$ref': '#/$defs/worker_stop'},
                                             'maxItems': 8,
                                             'minItems': 8,
                                             'type': 'array',
                                             'x-python-exact-type': 'list'},
                            'workflow_handle_cancel_calls': {'const': 1}},
             'required': ['schema_version',
                          'evidence_class',
                          'worker_stops',
                          'public_worker_shutdown_calls',
                          'activity_executor_shutdown_calls',
                          'server_generations',
                          'server_shutdown_signal',
                          'server_shutdown_calls',
                          'server_exit_code',
                          'server_stop_observed',
                          'server_shutdown_elapsed_ms',
                          'scenario_elapsed_ms',
                          'observation_cleanup_elapsed_ms',
                          'final_stop_elapsed_ms',
                          'evidence_and_pytest_elapsed_ms',
                          'all_scheduled_invocations_terminal',
                          'in_flight_calls',
                          'pending_rpc_tasks',
                          'accepted_updates_unfinished',
                          'handler_entries',
                          'handler_returns',
                          'stop_uncertain',
                          'cleanup_status',
                          'force_or_task_cancellation_calls',
                          'workflow_handle_cancel_calls',
                          'same_cas',
                          'same_sqlite'],
             'type': 'object',
             'x-python-exact-type': 'dict'},
 'command': {'additionalProperties': False,
             'properties': {'activity_id': {'maxLength': 96, 'minLength': 1, 'type': 'string'},
                            'activity_type': {'enum': ['opendot.synthetic.dependent-step.v1',
                                                       'opendot.synthetic.dependent-inspect.v1']},
                            'attempt': {'const': 1},
                            'entry_seq': {'maximum': 512,
                                          'minimum': 1,
                                          'type': 'integer',
                                          'x-python-exact-type': 'int'},
                            'fault': {'enum': ['NONE', 'CONTROLLED_POST_RETURN_RESPONSE_FAILURE']},
                            'kind': {'enum': ['execute', 'normal_inspect', 'reconcile_inspect']},
                            'maximum_attempts': {'const': 1},
                            'mission': {'enum': ['hosted-normal',
                                                 'hosted-reconcile',
                                                 'hosted-no-ref-cancel']},
                            'node': {'enum': ['A', 'B']},
                            'request_sha256': {'pattern': '^[0-9a-f]{64}$', 'type': 'string'},
                            'response_sha256': {'anyOf': [{'pattern': '^[0-9a-f]{64}$', 'type': 'string'},
                                                          {'type': 'null'}]},
                            'return_seq': {'maximum': 512,
                                           'minimum': 1,
                                           'type': 'integer',
                                           'x-python-exact-type': 'int'},
                            'run_id': {'maxLength': 128, 'minLength': 1, 'type': 'string'},
                            'schedule_observed_seq': {'maximum': 512,
                                                      'minimum': 1,
                                                      'type': 'integer',
                                                      'x-python-exact-type': 'int'},
                            'schedule_to_close_seconds': {'const': 60},
                            'scheduled_event_id': {'maximum': 512,
                                                   'minimum': 1,
                                                   'type': 'integer',
                                                   'x-python-exact-type': 'int'},
                            'start_to_close_seconds': {'const': 10},
                            'started_event_id': {'maximum': 512,
                                                 'minimum': 1,
                                                 'type': 'integer',
                                                 'x-python-exact-type': 'int'},
                            'terminal_event_id': {'maximum': 512,
                                                  'minimum': 1,
                                                  'type': 'integer',
                                                  'x-python-exact-type': 'int'},
                            'terminal_observed_seq': {'maximum': 512,
                                                      'minimum': 1,
                                                      'type': 'integer',
                                                      'x-python-exact-type': 'int'},
                            'terminal_type': {'enum': ['ActivityTaskCompleted', 'ActivityTaskFailed']},
                            'worker_generation': {'maximum': 8,
                                                  'minimum': 1,
                                                  'type': 'integer',
                                                  'x-python-exact-type': 'int'},
                            'workflow_id': {'maxLength': 128, 'minLength': 1, 'type': 'string'}},
             'required': ['mission',
                          'node',
                          'kind',
                          'workflow_id',
                          'run_id',
                          'activity_id',
                          'activity_type',
                          'scheduled_event_id',
                          'started_event_id',
                          'terminal_event_id',
                          'terminal_type',
                          'attempt',
                          'maximum_attempts',
                          'start_to_close_seconds',
                          'schedule_to_close_seconds',
                          'schedule_observed_seq',
                          'entry_seq',
                          'return_seq',
                          'terminal_observed_seq',
                          'worker_generation',
                          'request_sha256',
                          'response_sha256',
                          'fault'],
             'type': 'object',
             'x-python-exact-type': 'dict'},
 'counts': {'additionalProperties': False,
            'properties': {'activity_entries': {'maximum': 18,
                                                'minimum': 0,
                                                'type': 'integer',
                                                'x-python-exact-type': 'int'},
                           'activity_returns': {'maximum': 18,
                                                'minimum': 0,
                                                'type': 'integer',
                                                'x-python-exact-type': 'int'},
                           'activity_schedules': {'maximum': 18,
                                                  'minimum': 0,
                                                  'type': 'integer',
                                                  'x-python-exact-type': 'int'},
                           'endpoint_cas_reads': {'maximum': 24,
                                                  'minimum': 0,
                                                  'type': 'integer',
                                                  'x-python-exact-type': 'int'},
                           'handler_entries': {'maximum': 6,
                                               'minimum': 0,
                                               'type': 'integer',
                                               'x-python-exact-type': 'int'},
                           'handler_returns': {'maximum': 6,
                                               'minimum': 0,
                                               'type': 'integer',
                                               'x-python-exact-type': 'int'},
                           'in_flight_calls': {'maximum': 1,
                                               'minimum': 0,
                                               'type': 'integer',
                                               'x-python-exact-type': 'int'},
                           'observer_cas_reads': {'maximum': 4,
                                                  'minimum': 0,
                                                  'type': 'integer',
                                                  'x-python-exact-type': 'int'},
                           'pending_rpc_tasks': {'maximum': 64,
                                                 'minimum': 0,
                                                 'type': 'integer',
                                                 'x-python-exact-type': 'int'},
                           'result_puts': {'maximum': 6,
                                           'minimum': 0,
                                           'type': 'integer',
                                           'x-python-exact-type': 'int'},
                           'runtime_entries': {'maximum': 6,
                                               'minimum': 0,
                                               'type': 'integer',
                                               'x-python-exact-type': 'int'},
                           'runtime_returns': {'maximum': 6,
                                               'minimum': 0,
                                               'type': 'integer',
                                               'x-python-exact-type': 'int'},
                           'seed_puts': {'maximum': 3,
                                         'minimum': 0,
                                         'type': 'integer',
                                         'x-python-exact-type': 'int'},
                           'verification_cas_reads': {'maximum': 4,
                                                      'minimum': 0,
                                                      'type': 'integer',
                                                      'x-python-exact-type': 'int'},
                           'workflow_starts': {'maximum': 3,
                                               'minimum': 0,
                                               'type': 'integer',
                                               'x-python-exact-type': 'int'}},
            'required': ['workflow_starts',
                         'activity_schedules',
                         'activity_entries',
                         'activity_returns',
                         'runtime_entries',
                         'runtime_returns',
                         'handler_entries',
                         'handler_returns',
                         'seed_puts',
                         'result_puts',
                         'endpoint_cas_reads',
                         'observer_cas_reads',
                         'verification_cas_reads',
                         'in_flight_calls',
                         'pending_rpc_tasks'],
            'type': 'object',
            'x-python-exact-type': 'dict'},
 'diagnostic': {'additionalProperties': False,
                'properties': {'audit_failure': {'anyOf': [{'$ref': '#/$defs/failure'}, {'type': 'null'}]},
                               'cleanup_failure': {'anyOf': [{'$ref': '#/$defs/failure'}, {'type': 'null'}]},
                               'cleanup_status': {'enum': ['PASS', 'UNCONFIRMED', 'NOT_STARTED']},
                               'evidence_class': {'enum': ['FABRICATED_UNIT_DATA',
                                                           'OBSERVED_HOSTED_CANDIDATE']},
                               'evidence_status': {'enum': ['COMPLETE', 'INCOMPLETE']},
                               'primary_failure': {'anyOf': [{'$ref': '#/$defs/failure'}, {'type': 'null'}]},
                               'result': {'enum': ['PASS', 'FAIL']},
                               'schema_version': {'const': 'opendot.temporal.dag2-gate.diagnostic.v1'}},
                'required': ['schema_version',
                             'evidence_class',
                             'primary_failure',
                             'cleanup_failure',
                             'audit_failure',
                             'cleanup_status',
                             'evidence_status',
                             'result'],
                'type': 'object',
                'x-python-exact-type': 'dict'},
 'digest': {'pattern': '^[0-9a-f]{64}$', 'type': 'string'},
 'environment': {'additionalProperties': False,
                 'properties': {'acquisition_receipt_sha256': {'pattern': '^[0-9a-f]{64}$', 'type': 'string'},
                                'adr008_sha256': {'const': 'c7d18394d4a88b74e9b0b30ba5ba960bbc5177e19b2f6c115db91b23819b6737'},
                                'base_tree': {'const': '3dc536c4487422d6706831ac954c91264d771d4b'},
                                'bootstrap': {'items': {'$ref': '#/$defs/bootstrap'},
                                              'maxItems': 4,
                                              'minItems': 4,
                                              'type': 'array',
                                              'x-python-exact-type': 'list'},
                                'claims': {'$ref': '#/$defs/claims'},
                                'cli_version': {'const': '1.9.1'},
                                'complete_tracked_manifest_sha256': {'pattern': '^[0-9a-f]{64}$',
                                                                     'type': 'string'},
                                'effective_proxy_refused': {'const': True},
                                'evidence_class': {'enum': ['FABRICATED_UNIT_DATA',
                                                            'OBSERVED_HOSTED_CANDIDATE']},
                                'fresh_private_root': {'const': True},
                                'identity': {'$ref': '#/$defs/identity'},
                                'pip_report_sha256': {'pattern': '^[0-9a-f]{64}$', 'type': 'string'},
                                'plan_sha256': {'const': '19843079a5da00754ec1b5399962c33874b907eb4d0d6fcf55cd3be2f4dffb63'},
                                'python_version': {'const': '3.12'},
                                'runner_os': {'const': 'ubuntu-24.04'},
                                'schema_version': {'const': 'opendot.temporal.dag2-gate.environment.v1'},
                                'sdk_transport_retry_policy': {'const': 'SDK_DEFAULT_NO_PHYSICAL_RPC_COUNT_CLAIM'},
                                'sdk_version': {'const': '1.34.0'},
                                'server_version': {'const': '1.32.0'},
                                'source_after_sha256': {'pattern': '^[0-9a-f]{64}$', 'type': 'string'},
                                'source_before_sha256': {'pattern': '^[0-9a-f]{64}$', 'type': 'string'},
                                'source_closure': {'items': {'$ref': '#/$defs/path_digest'},
                                                   'maxItems': 36,
                                                   'minItems': 36,
                                                   'type': 'array',
                                                   'x-python-exact-type': 'list'}},
                 'required': ['schema_version',
                              'evidence_class',
                              'identity',
                              'base_tree',
                              'adr008_sha256',
                              'plan_sha256',
                              'source_closure',
                              'complete_tracked_manifest_sha256',
                              'source_before_sha256',
                              'source_after_sha256',
                              'acquisition_receipt_sha256',
                              'pip_report_sha256',
                              'sdk_version',
                              'cli_version',
                              'server_version',
                              'python_version',
                              'runner_os',
                              'fresh_private_root',
                              'effective_proxy_refused',
                              'bootstrap',
                              'sdk_transport_retry_policy',
                              'claims'],
                 'type': 'object',
                 'x-python-exact-type': 'dict'},
 'event': {'additionalProperties': False,
           'properties': {'counts': {'$ref': '#/$defs/counts'},
                          'history_event_id': {'anyOf': [{'maximum': 512,
                                                          'minimum': 1,
                                                          'type': 'integer',
                                                          'x-python-exact-type': 'int'},
                                                         {'type': 'null'}]},
                          'kind': {'enum': ['seed_put_return',
                                            'workflow_start_issued',
                                            'workflow_start_acknowledged',
                                            'bootstrap_constructed',
                                            'worker_start',
                                            'activity_enter',
                                            'runtime_enter',
                                            'handler_enter',
                                            'handler_return',
                                            'runtime_return',
                                            'result_put_return',
                                            'original_capture',
                                            'adapter_return',
                                            'controlled_response_failure',
                                            'activity_terminal_observed',
                                            'snapshot_retained',
                                            'query_observed',
                                            'update_submit',
                                            'update_handle_returned',
                                            'update_refusal_observed',
                                            'update_accepted_observed',
                                            'update_result_observed',
                                            'cancel_submit',
                                            'cancel_acknowledged',
                                            'cancel_recorded_observed',
                                            'workflow_terminal_observed',
                                            'verification_read',
                                            'replay_begin',
                                            'replay_end',
                                            'worker_stop_requested',
                                            'worker_stop_completed',
                                            'activity_executor_completed',
                                            'server_start',
                                            'server_stop_requested',
                                            'server_stop_completed',
                                            'rpc_issued',
                                            'rpc_settled',
                                            'observer_failure']},
                          'mission': {'anyOf': [{'enum': ['hosted-normal',
                                                          'hosted-reconcile',
                                                          'hosted-no-ref-cancel']},
                                                {'type': 'null'}]},
                          'monotonic_ns': {'maximum': 1000000000000000000,
                                           'minimum': 0,
                                           'type': 'integer',
                                           'x-python-exact-type': 'int'},
                          'node': {'anyOf': [{'enum': ['A', 'B']}, {'type': 'null'}]},
                          'operation_id': {'anyOf': [{'maxLength': 64,
                                                      'minLength': 1,
                                                      'pattern': '^[a-z0-9-]+$',
                                                      'type': 'string'},
                                                     {'type': 'null'}]},
                          'seq': {'maximum': 512,
                                  'minimum': 1,
                                  'type': 'integer',
                                  'x-python-exact-type': 'int'},
                          'worker_generation': {'anyOf': [{'maximum': 8,
                                                           'minimum': 1,
                                                           'type': 'integer',
                                                           'x-python-exact-type': 'int'},
                                                          {'type': 'null'}]}},
           'required': ['seq',
                        'monotonic_ns',
                        'mission',
                        'kind',
                        'node',
                        'worker_generation',
                        'operation_id',
                        'history_event_id',
                        'counts'],
           'type': 'object',
           'x-python-exact-type': 'dict'},
 'external_readback': {'additionalProperties': False,
                       'properties': {'acceptance': {'enum': ['HOSTED_REAL_SERVICE_ACCEPTED', 'REJECTED']},
                                      'checked_out_commit': {'pattern': '^[0-9a-f]{40}$', 'type': 'string'},
                                      'claims': {'$ref': '#/$defs/claims'},
                                      'identity': {'$ref': '#/$defs/identity'},
                                      'job_conclusion': {'const': 'success'},
                                      'job_id': {'maximum': 1000000000000000,
                                                 'minimum': 1,
                                                 'type': 'integer',
                                                 'x-python-exact-type': 'int'},
                                      'job_name': {'const': 'temporal-server'},
                                      'local_record_summary_sha256': {'pattern': '^[0-9a-f]{64}$',
                                                                      'type': 'string'},
                                      'pr_base_commit': {'const': None},
                                      'pr_head_commit': {'const': None},
                                      'readback_capture_sha256': {'pattern': '^[0-9a-f]{64}$',
                                                                  'type': 'string'},
                                      'remote_commit_tree': {'pattern': '^[0-9a-f]{40}$', 'type': 'string'},
                                      'remote_complete_manifest_sha256': {'pattern': '^[0-9a-f]{64}$',
                                                                          'type': 'string'},
                                      'remote_workflow_blob_sha256': {'pattern': '^[0-9a-f]{64}$',
                                                                      'type': 'string'},
                                      'required_step_conclusions': {'items': {'additionalProperties': False,
                                                                              'properties': {'conclusion': {'enum': ['success',
                                                                                                                     'skipped']},
                                                                                             'step_name': {'maxLength': 128,
                                                                                                           'minLength': 1,
                                                                                                           'type': 'string'}},
                                                                              'required': ['step_name',
                                                                                           'conclusion'],
                                                                              'type': 'object',
                                                                              'x-python-exact-type': 'dict'},
                                                                    'maxItems': 32,
                                                                    'minItems': 1,
                                                                    'type': 'array',
                                                                    'x-python-exact-type': 'list'},
                                      'retrieved_via': {'enum': ['AUTHORIZED_GITHUB_CONNECTOR',
                                                                 'AUTHORIZED_GITHUB_BROWSER']},
                                      'reviewer_decision': {'enum': ['ACCEPT', 'REJECT']},
                                      'run_conclusion': {'const': 'success'},
                                      'run_status': {'const': 'completed'},
                                      'schema_version': {'const': 'opendot.temporal.dag2-gate.external-readback.v1'},
                                      'selected_attempt': {'maximum': 999,
                                                           'minimum': 1,
                                                           'type': 'integer',
                                                           'x-python-exact-type': 'int'},
                                      'selected_profile': {'const': 'dag2'},
                                      'source_review_receipt_sha256': {'pattern': '^[0-9a-f]{64}$',
                                                                       'type': 'string'},
                                      'workflow_active': {'const': True}},
                       'required': ['schema_version',
                                    'identity',
                                    'retrieved_via',
                                    'run_status',
                                    'run_conclusion',
                                    'job_id',
                                    'job_name',
                                    'job_conclusion',
                                    'workflow_active',
                                    'remote_commit_tree',
                                    'remote_workflow_blob_sha256',
                                    'remote_complete_manifest_sha256',
                                    'checked_out_commit',
                                    'pr_head_commit',
                                    'pr_base_commit',
                                    'selected_profile',
                                    'selected_attempt',
                                    'required_step_conclusions',
                                    'source_review_receipt_sha256',
                                    'local_record_summary_sha256',
                                    'readback_capture_sha256',
                                    'reviewer_decision',
                                    'acceptance',
                                    'claims'],
                       'type': 'object',
                       'x-python-exact-type': 'dict'},
 'failure': {'additionalProperties': False,
             'properties': {'code': {'enum': ['BOOTSTRAP_MISMATCH',
                                              'CANCEL_MISMATCH',
                                              'CANCEL_SCOPE',
                                              'CAUSAL_ORDER',
                                              'CI_IDENTITY',
                                              'CLAIM_MISMATCH',
                                              'CLEANUP_UNCONFIRMED',
                                              'COLLECTION_MISMATCH',
                                              'COUNTER_MISMATCH',
                                              'DEADLINE_EXHAUSTED',
                                              'DEPENDENCY_VIOLATION',
                                              'HISTORY_LINKAGE',
                                              'HISTORY_MISMATCH',
                                              'HISTORY_PAYLOAD',
                                              'HISTORY_PROJECTION_MISMATCH',
                                              'HOSTED_ORIGIN_UNAUTHENTICATED',
                                              'INTERNAL_ERROR',
                                              'INVALID_JSON',
                                              'INVALID_SCHEMA',
                                              'INVALID_TYPE',
                                              'INVALID_VALUE',
                                              'JUNIT_IDENTITY',
                                              'MISSING_EVIDENCE',
                                              'NOT_RUN',
                                              'NO_REF_REDISCOVERY',
                                              'OK',
                                              'ORIGINAL_MUTATED',
                                              'ORIGIN_MISMATCH',
                                              'ORIGIN_ORDER',
                                              'OWNER_MISMATCH',
                                              'PIN_MISMATCH',
                                              'PREFLIGHT_FAILED',
                                              'PRIVACY_REJECTED',
                                              'PROFILE_MISMATCH',
                                              'READ_FAILED',
                                              'REPLAY_MISMATCH',
                                              'REQUIRED_NODES',
                                              'RESOURCE_MISMATCH',
                                              'RESULT_INVALID',
                                              'RPC_RESUBMITTED',
                                              'RPC_UNCONFIRMED',
                                              'RUN_BINDING',
                                              'SIZE_LIMIT',
                                              'SOURCE_MISMATCH',
                                              'TEST_FAILED',
                                              'TEST_SKIPPED',
                                              'UPDATE_MISMATCH',
                                              'VERSION_MISMATCH',
                                              'WORKFLOW_MISMATCH',
                                              'WRITE_FAILED']},
                            'phase': {'enum': ['selection',
                                               'preflight',
                                               'bootstrap',
                                               'start',
                                               'execution',
                                               'history',
                                               'query',
                                               'update',
                                               'cancel',
                                               'replay',
                                               'observation_cleanup',
                                               'worker_shutdown',
                                               'server_shutdown',
                                               'evidence_write',
                                               'verification']}},
             'required': ['phase', 'code'],
             'type': 'object',
             'x-python-exact-type': 'dict'},
 'failure_summary': {'additionalProperties': False,
                     'properties': {'activity_schedules_observed': {'maximum': 18,
                                                                    'minimum': 0,
                                                                    'type': 'integer',
                                                                    'x-python-exact-type': 'int'},
                                    'audit_failure': {'anyOf': [{'$ref': '#/$defs/failure'},
                                                                {'type': 'null'}]},
                                    'claims': {'$ref': '#/$defs/claims'},
                                    'cleanup_failure': {'anyOf': [{'$ref': '#/$defs/failure'},
                                                                  {'type': 'null'}]},
                                    'cleanup_status': {'enum': ['PASS', 'UNCONFIRMED', 'NOT_STARTED']},
                                    'collected_nodes': {'maximum': 7,
                                                        'minimum': 0,
                                                        'type': 'integer',
                                                        'x-python-exact-type': 'int'},
                                    'count_evidence': {'enum': ['VALIDATED_PARTIAL', 'UNAVAILABLE']},
                                    'error_nodes': {'maximum': 7,
                                                    'minimum': 0,
                                                    'type': 'integer',
                                                    'x-python-exact-type': 'int'},
                                    'evidence_class': {'enum': ['FABRICATED_UNIT_DATA',
                                                                'OBSERVED_HOSTED_CANDIDATE']},
                                    'expected_nodes': {'const': 7},
                                    'failed_nodes': {'maximum': 7,
                                                     'minimum': 0,
                                                     'type': 'integer',
                                                     'x-python-exact-type': 'int'},
                                    'hosted_acceptance': {'const': 'REJECTED'},
                                    'missions_admitted': {'maximum': 3,
                                                          'minimum': 0,
                                                          'type': 'integer',
                                                          'x-python-exact-type': 'int'},
                                    'passed_nodes': {'maximum': 7,
                                                     'minimum': 0,
                                                     'type': 'integer',
                                                     'x-python-exact-type': 'int'},
                                    'primary_failure': {'$ref': '#/$defs/failure'},
                                    'record_validation': {'const': 'FAIL'},
                                    'runtime_entries_observed': {'maximum': 6,
                                                                 'minimum': 0,
                                                                 'type': 'integer',
                                                                 'x-python-exact-type': 'int'},
                                    'schema_version': {'const': 'opendot.temporal.dag2-gate.failure-summary.v1'},
                                    'skipped_nodes': {'maximum': 7,
                                                      'minimum': 0,
                                                      'type': 'integer',
                                                      'x-python-exact-type': 'int'}},
                     'required': ['schema_version',
                                  'evidence_class',
                                  'expected_nodes',
                                  'collected_nodes',
                                  'passed_nodes',
                                  'failed_nodes',
                                  'error_nodes',
                                  'skipped_nodes',
                                  'missions_admitted',
                                  'activity_schedules_observed',
                                  'runtime_entries_observed',
                                  'count_evidence',
                                  'record_validation',
                                  'hosted_acceptance',
                                  'cleanup_status',
                                  'primary_failure',
                                  'cleanup_failure',
                                  'audit_failure',
                                  'claims'],
                     'type': 'object',
                     'x-python-exact-type': 'dict'},
 'history_event_projection': {'oneOf': [{'additionalProperties': False,
                                         'properties': {'event_id': {'maximum': 512,
                                                                     'minimum': 1,
                                                                     'type': 'integer'},
                                                        'event_type': {'const': 'ActivityTaskCompleted'},
                                                        'extracted': {'additionalProperties': False,
                                                                      'properties': {'payload_sha256': {'$ref': '#/$defs/digest'},
                                                                                     'scheduled_event_id': {'maximum': 1000000000000000,
                                                                                                            'minimum': 1,
                                                                                                            'type': 'integer',
                                                                                                            'x-python-exact-type': 'int'},
                                                                                     'started_event_id': {'maximum': 1000000000000000,
                                                                                                          'minimum': 1,
                                                                                                          'type': 'integer',
                                                                                                          'x-python-exact-type': 'int'}},
                                                                      'required': ['payload_sha256',
                                                                                   'scheduled_event_id',
                                                                                   'started_event_id'],
                                                                      'type': 'object'}},
                                         'required': ['event_id', 'event_type', 'extracted'],
                                         'type': 'object'},
                                        {'additionalProperties': False,
                                         'properties': {'event_id': {'maximum': 512,
                                                                     'minimum': 1,
                                                                     'type': 'integer'},
                                                        'event_type': {'const': 'ActivityTaskFailed'},
                                                        'extracted': {'additionalProperties': False,
                                                                      'properties': {'failure_type': {'maxLength': 256,
                                                                                                      'minLength': 1,
                                                                                                      'type': 'string'},
                                                                                     'non_retryable': {'type': 'boolean'},
                                                                                     'scheduled_event_id': {'maximum': 1000000000000000,
                                                                                                            'minimum': 1,
                                                                                                            'type': 'integer',
                                                                                                            'x-python-exact-type': 'int'},
                                                                                     'started_event_id': {'maximum': 1000000000000000,
                                                                                                          'minimum': 1,
                                                                                                          'type': 'integer',
                                                                                                          'x-python-exact-type': 'int'}},
                                                                      'required': ['failure_type',
                                                                                   'non_retryable',
                                                                                   'scheduled_event_id',
                                                                                   'started_event_id'],
                                                                      'type': 'object'}},
                                         'required': ['event_id', 'event_type', 'extracted'],
                                         'type': 'object'},
                                        {'additionalProperties': False,
                                         'properties': {'event_id': {'maximum': 512,
                                                                     'minimum': 1,
                                                                     'type': 'integer'},
                                                        'event_type': {'const': 'ActivityTaskScheduled'},
                                                        'extracted': {'additionalProperties': False,
                                                                      'properties': {'activity_id': {'maxLength': 256,
                                                                                                     'minLength': 1,
                                                                                                     'type': 'string'},
                                                                                     'activity_type': {'maxLength': 256,
                                                                                                       'minLength': 1,
                                                                                                       'type': 'string'},
                                                                                     'maximum_attempts': {'maximum': 1000000000000000,
                                                                                                          'minimum': 1,
                                                                                                          'type': 'integer',
                                                                                                          'x-python-exact-type': 'int'},
                                                                                     'payload_sha256': {'$ref': '#/$defs/digest'},
                                                                                     'schedule_to_close_timeout': {'maxLength': 256,
                                                                                                                   'minLength': 1,
                                                                                                                   'type': 'string'},
                                                                                     'start_to_close_timeout': {'maxLength': 256,
                                                                                                                'minLength': 1,
                                                                                                                'type': 'string'},
                                                                                     'task_queue': {'maxLength': 256,
                                                                                                    'minLength': 1,
                                                                                                    'type': 'string'},
                                                                                     'workflow_task_completed_event_id': {'maximum': 1000000000000000,
                                                                                                                          'minimum': 1,
                                                                                                                          'type': 'integer',
                                                                                                                          'x-python-exact-type': 'int'}},
                                                                      'required': ['activity_id',
                                                                                   'activity_type',
                                                                                   'maximum_attempts',
                                                                                   'payload_sha256',
                                                                                   'schedule_to_close_timeout',
                                                                                   'start_to_close_timeout',
                                                                                   'task_queue',
                                                                                   'workflow_task_completed_event_id'],
                                                                      'type': 'object'}},
                                         'required': ['event_id', 'event_type', 'extracted'],
                                         'type': 'object'},
                                        {'additionalProperties': False,
                                         'properties': {'event_id': {'maximum': 512,
                                                                     'minimum': 1,
                                                                     'type': 'integer'},
                                                        'event_type': {'const': 'ActivityTaskStarted'},
                                                        'extracted': {'additionalProperties': False,
                                                                      'properties': {'attempt': {'maximum': 1000000000000000,
                                                                                                 'minimum': 1,
                                                                                                 'type': 'integer',
                                                                                                 'x-python-exact-type': 'int'},
                                                                                     'scheduled_event_id': {'maximum': 1000000000000000,
                                                                                                            'minimum': 1,
                                                                                                            'type': 'integer',
                                                                                                            'x-python-exact-type': 'int'}},
                                                                      'required': ['attempt',
                                                                                   'scheduled_event_id'],
                                                                      'type': 'object'}},
                                         'required': ['event_id', 'event_type', 'extracted'],
                                         'type': 'object'},
                                        {'additionalProperties': False,
                                         'properties': {'event_id': {'maximum': 512,
                                                                     'minimum': 1,
                                                                     'type': 'integer'},
                                                        'event_type': {'const': 'TimerCanceled'},
                                                        'extracted': {'additionalProperties': False,
                                                                      'properties': {'started_event_id': {'maximum': 1000000000000000,
                                                                                                          'minimum': 1,
                                                                                                          'type': 'integer',
                                                                                                          'x-python-exact-type': 'int'},
                                                                                     'timer_id': {'maxLength': 256,
                                                                                                  'minLength': 1,
                                                                                                  'type': 'string'},
                                                                                     'workflow_task_completed_event_id': {'maximum': 1000000000000000,
                                                                                                                          'minimum': 1,
                                                                                                                          'type': 'integer',
                                                                                                                          'x-python-exact-type': 'int'}},
                                                                      'required': ['started_event_id',
                                                                                   'timer_id',
                                                                                   'workflow_task_completed_event_id'],
                                                                      'type': 'object'}},
                                         'required': ['event_id', 'event_type', 'extracted'],
                                         'type': 'object'},
                                        {'additionalProperties': False,
                                         'properties': {'event_id': {'maximum': 512,
                                                                     'minimum': 1,
                                                                     'type': 'integer'},
                                                        'event_type': {'const': 'TimerFired'},
                                                        'extracted': {'additionalProperties': False,
                                                                      'properties': {'started_event_id': {'maximum': 1000000000000000,
                                                                                                          'minimum': 1,
                                                                                                          'type': 'integer',
                                                                                                          'x-python-exact-type': 'int'},
                                                                                     'timer_id': {'maxLength': 256,
                                                                                                  'minLength': 1,
                                                                                                  'type': 'string'}},
                                                                      'required': ['started_event_id',
                                                                                   'timer_id'],
                                                                      'type': 'object'}},
                                         'required': ['event_id', 'event_type', 'extracted'],
                                         'type': 'object'},
                                        {'additionalProperties': False,
                                         'properties': {'event_id': {'maximum': 512,
                                                                     'minimum': 1,
                                                                     'type': 'integer'},
                                                        'event_type': {'const': 'TimerStarted'},
                                                        'extracted': {'additionalProperties': False,
                                                                      'properties': {'timeout': {'maxLength': 256,
                                                                                                 'minLength': 1,
                                                                                                 'type': 'string'},
                                                                                     'timer_id': {'maxLength': 256,
                                                                                                  'minLength': 1,
                                                                                                  'type': 'string'},
                                                                                     'workflow_task_completed_event_id': {'maximum': 1000000000000000,
                                                                                                                          'minimum': 1,
                                                                                                                          'type': 'integer',
                                                                                                                          'x-python-exact-type': 'int'}},
                                                                      'required': ['timeout',
                                                                                   'timer_id',
                                                                                   'workflow_task_completed_event_id'],
                                                                      'type': 'object'}},
                                         'required': ['event_id', 'event_type', 'extracted'],
                                         'type': 'object'},
                                        {'additionalProperties': False,
                                         'properties': {'event_id': {'maximum': 512,
                                                                     'minimum': 1,
                                                                     'type': 'integer'},
                                                        'event_type': {'const': 'WorkflowExecutionCancelRequested'},
                                                        'extracted': {'additionalProperties': False,
                                                                      'properties': {},
                                                                      'required': [],
                                                                      'type': 'object'}},
                                         'required': ['event_id', 'event_type', 'extracted'],
                                         'type': 'object'},
                                        {'additionalProperties': False,
                                         'properties': {'event_id': {'maximum': 512,
                                                                     'minimum': 1,
                                                                     'type': 'integer'},
                                                        'event_type': {'const': 'WorkflowExecutionCompleted'},
                                                        'extracted': {'additionalProperties': False,
                                                                      'properties': {'payload_sha256': {'$ref': '#/$defs/digest'},
                                                                                     'workflow_task_completed_event_id': {'maximum': 1000000000000000,
                                                                                                                          'minimum': 1,
                                                                                                                          'type': 'integer',
                                                                                                                          'x-python-exact-type': 'int'}},
                                                                      'required': ['payload_sha256',
                                                                                   'workflow_task_completed_event_id'],
                                                                      'type': 'object'}},
                                         'required': ['event_id', 'event_type', 'extracted'],
                                         'type': 'object'},
                                        {'additionalProperties': False,
                                         'properties': {'event_id': {'maximum': 512,
                                                                     'minimum': 1,
                                                                     'type': 'integer'},
                                                        'event_type': {'const': 'WorkflowExecutionStarted'},
                                                        'extracted': {'additionalProperties': False,
                                                                      'properties': {'attempt': {'maximum': 1000000000000000,
                                                                                                 'minimum': 1,
                                                                                                 'type': 'integer',
                                                                                                 'x-python-exact-type': 'int'},
                                                                                     'execution_timeout': {'maxLength': 256,
                                                                                                           'minLength': 1,
                                                                                                           'type': 'string'},
                                                                                     'first_run_id': {'maxLength': 256,
                                                                                                      'minLength': 1,
                                                                                                      'type': 'string'},
                                                                                     'maximum_attempts': {'maximum': 1000000000000000,
                                                                                                          'minimum': 1,
                                                                                                          'type': 'integer',
                                                                                                          'x-python-exact-type': 'int'},
                                                                                     'payload_sha256': {'$ref': '#/$defs/digest'},
                                                                                     'run_id': {'maxLength': 256,
                                                                                                'minLength': 1,
                                                                                                'type': 'string'},
                                                                                     'run_timeout': {'maxLength': 256,
                                                                                                     'minLength': 1,
                                                                                                     'type': 'string'},
                                                                                     'task_queue': {'maxLength': 256,
                                                                                                    'minLength': 1,
                                                                                                    'type': 'string'},
                                                                                     'task_timeout': {'maxLength': 256,
                                                                                                      'minLength': 1,
                                                                                                      'type': 'string'},
                                                                                     'workflow_type': {'maxLength': 256,
                                                                                                       'minLength': 1,
                                                                                                       'type': 'string'}},
                                                                      'required': ['attempt',
                                                                                   'execution_timeout',
                                                                                   'first_run_id',
                                                                                   'maximum_attempts',
                                                                                   'payload_sha256',
                                                                                   'run_id',
                                                                                   'run_timeout',
                                                                                   'task_queue',
                                                                                   'task_timeout',
                                                                                   'workflow_type'],
                                                                      'type': 'object'}},
                                         'required': ['event_id', 'event_type', 'extracted'],
                                         'type': 'object'},
                                        {'additionalProperties': False,
                                         'properties': {'event_id': {'maximum': 512,
                                                                     'minimum': 1,
                                                                     'type': 'integer'},
                                                        'event_type': {'const': 'WorkflowExecutionUpdateAccepted'},
                                                        'extracted': {'additionalProperties': False,
                                                                      'properties': {'accepted_request_sequencing_event_id': {'maximum': 1000000000000000,
                                                                                                                              'minimum': 1,
                                                                                                                              'type': 'integer',
                                                                                                                              'x-python-exact-type': 'int'},
                                                                                     'payload_sha256': {'$ref': '#/$defs/digest'},
                                                                                     'protocol_instance_id': {'maxLength': 256,
                                                                                                              'minLength': 1,
                                                                                                              'type': 'string'},
                                                                                     'update_id': {'maxLength': 256,
                                                                                                   'minLength': 1,
                                                                                                   'type': 'string'},
                                                                                     'update_name': {'maxLength': 256,
                                                                                                     'minLength': 1,
                                                                                                     'type': 'string'}},
                                                                      'required': ['accepted_request_sequencing_event_id',
                                                                                   'payload_sha256',
                                                                                   'protocol_instance_id',
                                                                                   'update_id',
                                                                                   'update_name'],
                                                                      'type': 'object'}},
                                         'required': ['event_id', 'event_type', 'extracted'],
                                         'type': 'object'},
                                        {'additionalProperties': False,
                                         'properties': {'event_id': {'maximum': 512,
                                                                     'minimum': 1,
                                                                     'type': 'integer'},
                                                        'event_type': {'const': 'WorkflowExecutionUpdateCompleted'},
                                                        'extracted': {'additionalProperties': False,
                                                                      'properties': {'accepted_event_id': {'maximum': 1000000000000000,
                                                                                                           'minimum': 1,
                                                                                                           'type': 'integer',
                                                                                                           'x-python-exact-type': 'int'},
                                                                                     'payload_sha256': {'$ref': '#/$defs/digest'},
                                                                                     'update_id': {'maxLength': 256,
                                                                                                   'minLength': 1,
                                                                                                   'type': 'string'}},
                                                                      'required': ['accepted_event_id',
                                                                                   'payload_sha256',
                                                                                   'update_id'],
                                                                      'type': 'object'}},
                                         'required': ['event_id', 'event_type', 'extracted'],
                                         'type': 'object'},
                                        {'additionalProperties': False,
                                         'properties': {'event_id': {'maximum': 512,
                                                                     'minimum': 1,
                                                                     'type': 'integer'},
                                                        'event_type': {'const': 'WorkflowTaskCompleted'},
                                                        'extracted': {'additionalProperties': False,
                                                                      'properties': {'scheduled_event_id': {'maximum': 1000000000000000,
                                                                                                            'minimum': 1,
                                                                                                            'type': 'integer',
                                                                                                            'x-python-exact-type': 'int'},
                                                                                     'started_event_id': {'maximum': 1000000000000000,
                                                                                                          'minimum': 1,
                                                                                                          'type': 'integer',
                                                                                                          'x-python-exact-type': 'int'}},
                                                                      'required': ['scheduled_event_id',
                                                                                   'started_event_id'],
                                                                      'type': 'object'}},
                                         'required': ['event_id', 'event_type', 'extracted'],
                                         'type': 'object'},
                                        {'additionalProperties': False,
                                         'properties': {'event_id': {'maximum': 512,
                                                                     'minimum': 1,
                                                                     'type': 'integer'},
                                                        'event_type': {'const': 'WorkflowTaskScheduled'},
                                                        'extracted': {'additionalProperties': False,
                                                                      'properties': {'attempt': {'maximum': 1000000000000000,
                                                                                                 'minimum': 1,
                                                                                                 'type': 'integer',
                                                                                                 'x-python-exact-type': 'int'},
                                                                                     'task_queue': {'maxLength': 256,
                                                                                                    'minLength': 1,
                                                                                                    'type': 'string'},
                                                                                     'task_timeout': {'maxLength': 256,
                                                                                                      'minLength': 1,
                                                                                                      'type': 'string'}},
                                                                      'required': ['attempt',
                                                                                   'task_queue',
                                                                                   'task_timeout'],
                                                                      'type': 'object'}},
                                         'required': ['event_id', 'event_type', 'extracted'],
                                         'type': 'object'},
                                        {'additionalProperties': False,
                                         'properties': {'event_id': {'maximum': 512,
                                                                     'minimum': 1,
                                                                     'type': 'integer'},
                                                        'event_type': {'const': 'WorkflowTaskStarted'},
                                                        'extracted': {'additionalProperties': False,
                                                                      'properties': {'scheduled_event_id': {'maximum': 1000000000000000,
                                                                                                            'minimum': 1,
                                                                                                            'type': 'integer',
                                                                                                            'x-python-exact-type': 'int'}},
                                                                      'required': ['scheduled_event_id'],
                                                                      'type': 'object'}},
                                         'required': ['event_id', 'event_type', 'extracted'],
                                         'type': 'object'}]},
 'identity': {'additionalProperties': False,
              'properties': {'commit': {'pattern': '^[0-9a-f]{40}$', 'type': 'string'},
                             'event': {'const': 'workflow_dispatch'},
                             'qualification': {'const': 'dag2'},
                             'ref': {'maxLength': 256,
                                     'minLength': 1,
                                     'pattern': '^refs/(heads|tags)/[A-Za-z0-9._/-]+$',
                                     'type': 'string'},
                             'repository': {'maxLength': 256,
                                            'minLength': 1,
                                            'pattern': '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$',
                                            'type': 'string'},
                             'retain_public_evidence': {'const': False},
                             'run_attempt': {'maximum': 999,
                                             'minimum': 1,
                                             'type': 'integer',
                                             'x-python-exact-type': 'int'},
                             'run_id': {'maximum': 1000000000000000,
                                        'minimum': 1,
                                        'type': 'integer',
                                        'x-python-exact-type': 'int'},
                             'run_url': {'maxLength': 512,
                                         'minLength': 1,
                                         'pattern': '^https://github.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/actions/runs/[0-9]+/attempts/[0-9]+$',
                                         'type': 'string'},
                             'tree': {'pattern': '^[0-9a-f]{40}$', 'type': 'string'},
                             'workflow_id': {'maximum': 1000000000000000,
                                             'minimum': 1,
                                             'type': 'integer',
                                             'x-python-exact-type': 'int'},
                             'workflow_path': {'const': '.github/workflows/temporal-server.yml'},
                             'workflow_sha256': {'pattern': '^[0-9a-f]{64}$', 'type': 'string'}},
              'required': ['repository',
                           'event',
                           'ref',
                           'commit',
                           'tree',
                           'workflow_path',
                           'workflow_sha256',
                           'workflow_id',
                           'run_id',
                           'run_attempt',
                           'run_url',
                           'qualification',
                           'retain_public_evidence'],
              'type': 'object',
              'x-python-exact-type': 'dict'},
 'manifest': {'additionalProperties': False,
              'properties': {'aggregate_bytes': {'maximum': 27262976, 'minimum': 1, 'type': 'integer'},
                             'evidence_class': {'enum': ['FABRICATED_UNIT_DATA',
                                                         'OBSERVED_HOSTED_CANDIDATE']},
                             'files': {'items': {'additionalProperties': False,
                                                 'properties': {'file_id': {'enum': ['acquisition-receipt.json',
                                                                                     'collected-nodes.txt',
                                                                                     'dag-sdk-summary.json',
                                                                                     'dag2-cleanup.json',
                                                                                     'dag2-diagnostic.json',
                                                                                     'dag2-environment.json',
                                                                                     'dag2-originals.json',
                                                                                     'dag2-replays.json',
                                                                                     'dag2-trace.json',
                                                                                     'no-ref-cancel-final.history.json',
                                                                                     'no-ref-cancel-final.state.json',
                                                                                     'no-ref-unknown.history.json',
                                                                                     'no-ref-unknown.state.json',
                                                                                     'normal-a.result.json',
                                                                                     'normal-b.result.json',
                                                                                     'normal-final.history.json',
                                                                                     'normal-final.state.json',
                                                                                     'pip-report.json',
                                                                                     'reconcile-a.result.json',
                                                                                     'reconcile-b.result.json',
                                                                                     'reconcile-final.history.json',
                                                                                     'reconcile-final.state.json',
                                                                                     'reconcile-unknown-after-replacement.history.json',
                                                                                     'reconcile-unknown-after-replacement.state.json',
                                                                                     'reconcile-unknown-before-stop.history.json',
                                                                                     'reconcile-unknown-before-stop.state.json',
                                                                                     'reconcile-update-queued.history.json',
                                                                                     'reconcile-update-queued.state.json',
                                                                                     'required-nodes.txt',
                                                                                     'results.xml',
                                                                                     'shared-unit-summary.json',
                                                                                     'source-manifest.json']},
                                                                'sha256': {'$ref': '#/$defs/digest'},
                                                                'size_bytes': {'maximum': 2097152,
                                                                               'minimum': 1,
                                                                               'type': 'integer'}},
                                                 'required': ['file_id', 'sha256', 'size_bytes'],
                                                 'type': 'object'},
                                       'maxItems': 32,
                                       'minItems': 32,
                                       'type': 'array'},
                             'schema_version': {'const': 'opendot.temporal.dag2-gate.manifest.v1'}},
              'required': ['schema_version', 'evidence_class', 'files', 'aggregate_bytes'],
              'type': 'object'},
 'origin': {'additionalProperties': False,
            'properties': {'capture_phase': {'const': 'original_put_return_before_response'},
                           'effect_id': {'maxLength': 71,
                                         'minLength': 1,
                                         'pattern': '^sha256:[0-9a-f]{64}$',
                                         'type': 'string'},
                           'execution_activity_id': {'maxLength': 96, 'minLength': 1, 'type': 'string'},
                           'mission_id': {'enum': ['hosted-normal',
                                                   'hosted-reconcile',
                                                   'hosted-no-ref-cancel']},
                           'namespace': {'const': 'default'},
                           'node_id': {'enum': ['A', 'B']},
                           'origin_kind': {'const': 'trusted-single-operator-synthetic-put-observer'},
                           'original_result_ref': {'$ref': '#/$defs/ref'},
                           'plan_sha256': {'const': '19843079a5da00754ec1b5399962c33874b907eb4d0d6fcf55cd3be2f4dffb63'},
                           'schema_version': {'const': 'opendot.temporal.dag-origin.v1'},
                           'workflow_id': {'maxLength': 128, 'minLength': 1, 'type': 'string'},
                           'workflow_run_id': {'maxLength': 128, 'minLength': 1, 'type': 'string'}},
            'required': ['schema_version',
                         'origin_kind',
                         'capture_phase',
                         'mission_id',
                         'plan_sha256',
                         'node_id',
                         'effect_id',
                         'namespace',
                         'workflow_id',
                         'workflow_run_id',
                         'execution_activity_id',
                         'original_result_ref'],
            'type': 'object',
            'x-python-exact-type': 'dict'},
 'original': {'additionalProperties': False,
              'properties': {'adapter_return_seq': {'maximum': 512,
                                                    'minimum': 1,
                                                    'type': 'integer',
                                                    'x-python-exact-type': 'int'},
                             'body': {'$ref': '#/$defs/private_file'},
                             'capture_seq': {'maximum': 512,
                                             'minimum': 1,
                                             'type': 'integer',
                                             'x-python-exact-type': 'int'},
                             'input_sha256': {'pattern': '^[0-9a-f]{64}$', 'type': 'string'},
                             'mission': {'enum': ['hosted-normal', 'hosted-reconcile']},
                             'node': {'enum': ['A', 'B']},
                             'observation_execution_id': {'maxLength': 32,
                                                          'minLength': 1,
                                                          'pattern': '^[0-9a-f]{32}$',
                                                          'type': 'string'},
                             'origin': {'$ref': '#/$defs/origin'},
                             'origin_sha256': {'pattern': '^[0-9a-f]{64}$', 'type': 'string'},
                             'output': {'enum': [5, 6]},
                             'output_sha256': {'pattern': '^[0-9a-f]{64}$', 'type': 'string'},
                             'put_operation_id': {'maximum': 8,
                                                  'minimum': 1,
                                                  'type': 'integer',
                                                  'x-python-exact-type': 'int'},
                             'put_return_seq': {'maximum': 512,
                                                'minimum': 1,
                                                'type': 'integer',
                                                'x-python-exact-type': 'int'},
                             'receipt_call_id': {'maxLength': 24,
                                                 'minLength': 1,
                                                 'pattern': '^[0-9a-f]{24}$',
                                                 'type': 'string'},
                             'receipt_sha256': {'pattern': '^[0-9a-f]{64}$', 'type': 'string'},
                             'reference': {'$ref': '#/$defs/ref'}},
              'required': ['mission',
                           'node',
                           'put_operation_id',
                           'capture_seq',
                           'put_return_seq',
                           'adapter_return_seq',
                           'reference',
                           'body',
                           'origin',
                           'origin_sha256',
                           'receipt_sha256',
                           'receipt_call_id',
                           'observation_execution_id',
                           'input_sha256',
                           'output_sha256',
                           'output'],
              'type': 'object',
              'x-python-exact-type': 'dict'},
 'originals': {'additionalProperties': False,
               'properties': {'evidence_class': {'enum': ['FABRICATED_UNIT_DATA',
                                                          'OBSERVED_HOSTED_CANDIDATE']},
                              'no_ref': {'additionalProperties': False,
                                         'properties': {'adapter_returns': {'const': 1},
                                                        'cas_discovery_attempts': {'const': 0},
                                                        'handler_returns': {'const': 1},
                                                        'mission': {'const': 'hosted-no-ref-cancel'},
                                                        'origin_record': {'const': 'NOT_RETAINED'},
                                                        'original_body': {'const': 'NOT_RETAINED'},
                                                        'original_digest': {'const': 'NOT_RETAINED'},
                                                        'original_reference': {'const': 'NOT_RETAINED'},
                                                        'recovery_reference_reads': {'const': 0},
                                                        'result_puts': {'const': 1}},
                                         'required': ['mission',
                                                      'result_puts',
                                                      'handler_returns',
                                                      'adapter_returns',
                                                      'original_reference',
                                                      'original_body',
                                                      'original_digest',
                                                      'origin_record',
                                                      'cas_discovery_attempts',
                                                      'recovery_reference_reads'],
                                         'type': 'object',
                                         'x-python-exact-type': 'dict'},
                              'originals': {'items': {'$ref': '#/$defs/original'},
                                            'maxItems': 4,
                                            'minItems': 4,
                                            'type': 'array',
                                            'x-python-exact-type': 'list'},
                              'schema_version': {'const': 'opendot.temporal.dag2-gate.originals.v1'}},
               'required': ['schema_version', 'evidence_class', 'originals', 'no_ref'],
               'type': 'object',
               'x-python-exact-type': 'dict'},
 'path_digest': {'additionalProperties': False,
                 'properties': {'mode': {'enum': ['100644', '100755']},
                                'path': {'maxLength': 256,
                                         'minLength': 1,
                                         'pattern': '^[A-Za-z0-9._/-]+$',
                                         'type': 'string'},
                                'sha256': {'pattern': '^[0-9a-f]{64}$', 'type': 'string'},
                                'size_bytes': {'maximum': 4194304,
                                               'minimum': 1,
                                               'type': 'integer',
                                               'x-python-exact-type': 'int'}},
                 'required': ['path', 'sha256', 'size_bytes', 'mode'],
                 'type': 'object',
                 'x-python-exact-type': 'dict'},
 'private_file': {'additionalProperties': False,
                  'properties': {'file_id': {'maxLength': 80,
                                             'minLength': 1,
                                             'pattern': '^[a-z0-9.-]+$',
                                             'type': 'string'},
                                 'sha256': {'pattern': '^[0-9a-f]{64}$', 'type': 'string'},
                                 'size_bytes': {'maximum': 2097152,
                                                'minimum': 1,
                                                'type': 'integer',
                                                'x-python-exact-type': 'int'}},
                  'required': ['file_id', 'sha256', 'size_bytes'],
                  'type': 'object',
                  'x-python-exact-type': 'dict'},
 'ref': {'additionalProperties': False,
         'properties': {'artifact_id': {'maxLength': 71,
                                        'minLength': 1,
                                        'pattern': '^sha256:[0-9a-f]{64}$',
                                        'type': 'string'},
                        'integrity_verified': {'const': False},
                        'mime_type': {'const': 'application/json'},
                        'producer': {'enum': ['opendot.temporal.dag-seed.v1',
                                              'opendot.temporal.dag-result.v1']},
                        'schema_version': {'const': '1.0.0'},
                        'sha256': {'pattern': '^[0-9a-f]{64}$', 'type': 'string'},
                        'size_bytes': {'maximum': 16384,
                                       'minimum': 1,
                                       'type': 'integer',
                                       'x-python-exact-type': 'int'},
                        'source_refs': {'items': {'maxLength': 71,
                                                  'minLength': 1,
                                                  'pattern': '^sha256:[0-9a-f]{64}$',
                                                  'type': 'string'},
                                        'maxItems': 2,
                                        'minItems': 0,
                                        'type': 'array',
                                        'x-python-exact-type': 'list'},
                        'task_id': {'maxLength': 64, 'minLength': 1, 'type': 'string'},
                        'uri': {'maxLength': 82,
                                'minLength': 1,
                                'pattern': '^artifact://sha256/[0-9a-f]{64}$',
                                'type': 'string'}},
         'required': ['artifact_id',
                      'uri',
                      'mime_type',
                      'size_bytes',
                      'sha256',
                      'schema_version',
                      'producer',
                      'task_id',
                      'source_refs',
                      'integrity_verified'],
         'type': 'object',
         'x-python-exact-type': 'dict'},
 'replay': {'additionalProperties': False,
            'properties': {'activity_worker_count': {'const': 0},
                           'begin_seq': {'maximum': 512,
                                         'minimum': 1,
                                         'type': 'integer',
                                         'x-python-exact-type': 'int'},
                           'completion_payload_sha256': {'pattern': '^[0-9a-f]{64}$', 'type': 'string'},
                           'counts_after': {'$ref': '#/$defs/counts'},
                           'counts_before': {'$ref': '#/$defs/counts'},
                           'default_pinned_sdk_runner': {'const': True},
                           'end_seq': {'maximum': 512,
                                       'minimum': 1,
                                       'type': 'integer',
                                       'x-python-exact-type': 'int'},
                           'history_file_id': {'enum': ['normal-final.history.json',
                                                        'reconcile-final.history.json']},
                           'mission': {'enum': ['hosted-normal', 'hosted-reconcile']},
                           'replay_failure': {'const': None},
                           'replayer_input_sha256': {'pattern': '^[0-9a-f]{64}$', 'type': 'string'},
                           'result_api': {'const': 'WorkflowReplayResult.history_and_replay_failure'},
                           'retained_history_sha256': {'pattern': '^[0-9a-f]{64}$', 'type': 'string'}},
            'required': ['mission',
                         'history_file_id',
                         'retained_history_sha256',
                         'replayer_input_sha256',
                         'completion_payload_sha256',
                         'result_api',
                         'replay_failure',
                         'default_pinned_sdk_runner',
                         'activity_worker_count',
                         'counts_before',
                         'counts_after',
                         'begin_seq',
                         'end_seq'],
            'type': 'object',
            'x-python-exact-type': 'dict'},
 'replays': {'additionalProperties': False,
             'properties': {'evidence_class': {'enum': ['FABRICATED_UNIT_DATA', 'OBSERVED_HOSTED_CANDIDATE']},
                            'replays': {'items': {'$ref': '#/$defs/replay'},
                                        'maxItems': 2,
                                        'minItems': 2,
                                        'type': 'array',
                                        'x-python-exact-type': 'list'},
                            'schema_version': {'const': 'opendot.temporal.dag2-gate.replays.v1'}},
             'required': ['schema_version', 'evidence_class', 'replays'],
             'type': 'object',
             'x-python-exact-type': 'dict'},
 'rpc': {'additionalProperties': False,
         'properties': {'application_submissions': {'const': 1},
                        'follow_runs': {'const': False},
                        'issued_seq': {'maximum': 512,
                                       'minimum': 1,
                                       'type': 'integer',
                                       'x-python-exact-type': 'int'},
                        'kind': {'enum': ['start',
                                          'query',
                                          'history',
                                          'result',
                                          'start_update',
                                          'update_result',
                                          'cancel']},
                        'mission': {'enum': ['hosted-normal', 'hosted-reconcile', 'hosted-no-ref-cancel']},
                        'observation_timeout_seconds': {'maximum': 3,
                                                        'minimum': 1,
                                                        'type': 'integer',
                                                        'x-python-exact-type': 'int'},
                        'operation_id': {'maxLength': 64,
                                         'minLength': 1,
                                         'pattern': '^[a-z0-9-]+$',
                                         'type': 'string'},
                        'outcome': {'enum': ['SUCCESS', 'EXPECTED_VALIDATOR_REFUSAL', 'UNCONFIRMED']},
                        'rpc_timeout_seconds': {'const': 2},
                        'run_id': {'anyOf': [{'maxLength': 128, 'minLength': 1, 'type': 'string'},
                                             {'type': 'null'}]},
                        'settled_seq': {'anyOf': [{'maximum': 512,
                                                   'minimum': 1,
                                                   'type': 'integer',
                                                   'x-python-exact-type': 'int'},
                                                  {'type': 'null'}]},
                        'update_id': {'anyOf': [{'maxLength': 64, 'minLength': 1, 'type': 'string'},
                                                {'type': 'null'}]},
                        'workflow_id': {'maxLength': 128, 'minLength': 1, 'type': 'string'}},
         'required': ['operation_id',
                      'mission',
                      'kind',
                      'issued_seq',
                      'settled_seq',
                      'workflow_id',
                      'run_id',
                      'update_id',
                      'outcome',
                      'rpc_timeout_seconds',
                      'observation_timeout_seconds',
                      'application_submissions',
                      'follow_runs'],
         'type': 'object',
         'x-python-exact-type': 'dict'},
 'snapshot': {'additionalProperties': False,
              'properties': {'completion_payload_sha256': {'anyOf': [{'pattern': '^[0-9a-f]{64}$',
                                                                      'type': 'string'},
                                                                     {'type': 'null'}]},
                             'events': {'items': {'$ref': '#/$defs/history_event_projection'},
                                        'maxItems': 512,
                                        'minItems': 1,
                                        'type': 'array'},
                             'history': {'$ref': '#/$defs/private_file'},
                             'history_event_count': {'maximum': 512,
                                                     'minimum': 1,
                                                     'type': 'integer',
                                                     'x-python-exact-type': 'int'},
                             'last_event_id': {'maximum': 512,
                                               'minimum': 1,
                                               'type': 'integer',
                                               'x-python-exact-type': 'int'},
                             'mission': {'enum': ['hosted-normal',
                                                  'hosted-reconcile',
                                                  'hosted-no-ref-cancel']},
                             'observation_seq': {'maximum': 512,
                                                 'minimum': 1,
                                                 'type': 'integer',
                                                 'x-python-exact-type': 'int'},
                             'snapshot_id': {'enum': ['normal-final',
                                                      'reconcile-unknown-before-stop',
                                                      'reconcile-unknown-after-replacement',
                                                      'reconcile-update-queued',
                                                      'reconcile-final',
                                                      'no-ref-unknown',
                                                      'no-ref-cancel-final']},
                             'state': {'$ref': '#/$defs/private_file'},
                             'state_revision': {'maximum': 64,
                                                'minimum': 1,
                                                'type': 'integer',
                                                'x-python-exact-type': 'int'},
                             'state_status': {'enum': ['RUNNING',
                                                       'PAUSED_UNKNOWN',
                                                       'COMPLETED',
                                                       'STOPPED_WITH_UNKNOWN']}},
              'required': ['snapshot_id',
                           'mission',
                           'observation_seq',
                           'history',
                           'history_event_count',
                           'last_event_id',
                           'state',
                           'state_revision',
                           'state_status',
                           'completion_payload_sha256',
                           'events'],
              'type': 'object',
              'x-python-exact-type': 'dict'},
 'summary': {'additionalProperties': False,
             'properties': {'activity_executor_completions': {'const': 4},
                            'activity_schedules': {'const': 9},
                            'claims': {'$ref': '#/$defs/claims'},
                            'cleanup_status': {'const': 'PASS'},
                            'collected_nodes': {'const': 7},
                            'collection_sha256': {'pattern': '^[0-9a-f]{64}$', 'type': 'string'},
                            'endpoint_cas_reads': {'const': 11},
                            'error_nodes': {'const': 0},
                            'evidence_class': {'enum': ['FABRICATED_UNIT_DATA', 'OBSERVED_HOSTED_CANDIDATE']},
                            'evidence_manifest_sha256': {'pattern': '^[0-9a-f]{64}$', 'type': 'string'},
                            'expected_nodes': {'const': 7},
                            'failed_nodes': {'const': 0},
                            'handler_returns': {'const': 5},
                            'hosted_acceptance': {'const': 'REQUIRES_EXTERNAL_GITHUB_READBACK'},
                            'identity': {'$ref': '#/$defs/identity'},
                            'junit_sha256': {'pattern': '^[0-9a-f]{64}$', 'type': 'string'},
                            'mission_count': {'const': 3},
                            'node_manifest_sha256': {'pattern': '^[0-9a-f]{64}$', 'type': 'string'},
                            'original_result_puts': {'const': 5},
                            'passed_nodes': {'const': 7},
                            'reason_code': {'enum': ['BOOTSTRAP_MISMATCH',
                                                     'CANCEL_MISMATCH',
                                                     'CANCEL_SCOPE',
                                                     'CAUSAL_ORDER',
                                                     'CI_IDENTITY',
                                                     'CLAIM_MISMATCH',
                                                     'CLEANUP_UNCONFIRMED',
                                                     'COLLECTION_MISMATCH',
                                                     'COUNTER_MISMATCH',
                                                     'DEADLINE_EXHAUSTED',
                                                     'DEPENDENCY_VIOLATION',
                                                     'HISTORY_LINKAGE',
                                                     'HISTORY_MISMATCH',
                                                     'HISTORY_PAYLOAD',
                                                     'HISTORY_PROJECTION_MISMATCH',
                                                     'HOSTED_ORIGIN_UNAUTHENTICATED',
                                                     'INTERNAL_ERROR',
                                                     'INVALID_JSON',
                                                     'INVALID_SCHEMA',
                                                     'INVALID_TYPE',
                                                     'INVALID_VALUE',
                                                     'JUNIT_IDENTITY',
                                                     'MISSING_EVIDENCE',
                                                     'NOT_RUN',
                                                     'NO_REF_REDISCOVERY',
                                                     'OK',
                                                     'ORIGINAL_MUTATED',
                                                     'ORIGIN_MISMATCH',
                                                     'ORIGIN_ORDER',
                                                     'OWNER_MISMATCH',
                                                     'PIN_MISMATCH',
                                                     'PREFLIGHT_FAILED',
                                                     'PRIVACY_REJECTED',
                                                     'PROFILE_MISMATCH',
                                                     'READ_FAILED',
                                                     'REPLAY_MISMATCH',
                                                     'REQUIRED_NODES',
                                                     'RESOURCE_MISMATCH',
                                                     'RESULT_INVALID',
                                                     'RPC_RESUBMITTED',
                                                     'RPC_UNCONFIRMED',
                                                     'RUN_BINDING',
                                                     'SIZE_LIMIT',
                                                     'SOURCE_MISMATCH',
                                                     'TEST_FAILED',
                                                     'TEST_SKIPPED',
                                                     'UPDATE_MISMATCH',
                                                     'VERSION_MISMATCH',
                                                     'WORKFLOW_MISMATCH',
                                                     'WRITE_FAILED']},
                            'record_validation': {'const': 'PASS'},
                            'replays': {'const': 2},
                            'retained_originals': {'const': 4},
                            'runtime_entries': {'const': 5},
                            'schema_version': {'const': 'opendot.temporal.dag2-gate.summary.v1'},
                            'skipped_nodes': {'const': 0},
                            'source_manifest_sha256': {'pattern': '^[0-9a-f]{64}$', 'type': 'string'},
                            'worker_shutdowns': {'const': 8},
                            'xfail_nodes': {'const': 0}},
             'required': ['schema_version',
                          'evidence_class',
                          'identity',
                          'source_manifest_sha256',
                          'evidence_manifest_sha256',
                          'node_manifest_sha256',
                          'collection_sha256',
                          'junit_sha256',
                          'expected_nodes',
                          'collected_nodes',
                          'passed_nodes',
                          'failed_nodes',
                          'error_nodes',
                          'skipped_nodes',
                          'xfail_nodes',
                          'mission_count',
                          'activity_schedules',
                          'runtime_entries',
                          'handler_returns',
                          'original_result_puts',
                          'retained_originals',
                          'endpoint_cas_reads',
                          'replays',
                          'worker_shutdowns',
                          'activity_executor_completions',
                          'cleanup_status',
                          'record_validation',
                          'hosted_acceptance',
                          'reason_code',
                          'claims'],
             'type': 'object',
             'x-python-exact-type': 'dict'},
 'trace': {'additionalProperties': False,
           'properties': {'aggregate_counts': {'$ref': '#/$defs/counts'},
                          'commands': {'items': {'$ref': '#/$defs/command'},
                                       'maxItems': 9,
                                       'minItems': 9,
                                       'type': 'array',
                                       'x-python-exact-type': 'list'},
                          'events': {'items': {'$ref': '#/$defs/event'},
                                     'maxItems': 512,
                                     'minItems': 1,
                                     'type': 'array',
                                     'x-python-exact-type': 'list'},
                          'evidence_class': {'enum': ['FABRICATED_UNIT_DATA', 'OBSERVED_HOSTED_CANDIDATE']},
                          'rpc_operations': {'items': {'$ref': '#/$defs/rpc'},
                                             'maxItems': 64,
                                             'minItems': 1,
                                             'type': 'array',
                                             'x-python-exact-type': 'list'},
                          'schema_version': {'const': 'opendot.temporal.dag2-gate.trace.v1'},
                          'snapshots': {'items': {'$ref': '#/$defs/snapshot'},
                                        'maxItems': 7,
                                        'minItems': 7,
                                        'type': 'array',
                                        'x-python-exact-type': 'list'},
                          'updates': {'items': {'$ref': '#/$defs/update'},
                                      'maxItems': 5,
                                      'minItems': 5,
                                      'type': 'array',
                                      'x-python-exact-type': 'list'}},
           'required': ['schema_version',
                        'evidence_class',
                        'events',
                        'commands',
                        'rpc_operations',
                        'snapshots',
                        'updates',
                        'aggregate_counts'],
           'type': 'object',
           'x-python-exact-type': 'dict'},
 'update': {'additionalProperties': False,
            'properties': {'accepted_event_id': {'anyOf': [{'maximum': 512,
                                                            'minimum': 1,
                                                            'type': 'integer',
                                                            'x-python-exact-type': 'int'},
                                                           {'type': 'null'}]},
                           'actual_error_details': {'anyOf': [{'const': 'UPDATE_REFUSED'}, {'type': 'null'}]},
                           'actual_error_type': {'anyOf': [{'const': 'TemporalDagUpdateRejected'},
                                                           {'type': 'null'}]},
                           'bootstrap_constructed_seq': {'maximum': 512,
                                                         'minimum': 1,
                                                         'type': 'integer',
                                                         'x-python-exact-type': 'int'},
                           'completed_event_id': {'anyOf': [{'maximum': 512,
                                                             'minimum': 1,
                                                             'type': 'integer',
                                                             'x-python-exact-type': 'int'},
                                                            {'type': 'null'}]},
                           'endpoint_read_delta': {'const': 0},
                           'execute_delta': {'const': 0},
                           'expected_revision': {'enum': [3, 4]},
                           'mission': {'const': 'hosted-reconcile'},
                           'operation_id': {'enum': ['update-stale',
                                                     'update-original',
                                                     'update-repeat-same-id',
                                                     'update-distinct-busy',
                                                     'update-get-completed']},
                           'origin_capture_seq': {'maximum': 512,
                                                  'minimum': 1,
                                                  'type': 'integer',
                                                  'x-python-exact-type': 'int'},
                           'outcome': {'enum': ['VALIDATOR_REFUSED',
                                                'ACCEPTED_QUEUED',
                                                'SAME_UPDATE_QUEUED',
                                                'SAME_COMPLETED_RESULT']},
                           'post_revision': {'enum': [4, 5, 10]},
                           'pre_revision': {'enum': [4, 5, 10]},
                           'precondition_oracle': {'enum': ['STALE_REVISION',
                                                            'INSPECTION_BUSY',
                                                            'VALID_RECONCILIATION',
                                                            'RECORDED_SAME_ID']},
                           'request_sha256': {'pattern': '^[0-9a-f]{64}$', 'type': 'string'},
                           'reservation_delta': {'enum': [0, 1]},
                           'result_sha256': {'anyOf': [{'pattern': '^[0-9a-f]{64}$', 'type': 'string'},
                                                       {'type': 'null'}]},
                           'submit_seq': {'maximum': 512,
                                          'minimum': 1,
                                          'type': 'integer',
                                          'x-python-exact-type': 'int'},
                           'update_id': {'enum': ['dag2-reconcile-stale',
                                                  'dag2-reconcile-original',
                                                  'dag2-reconcile-busy']}},
            'required': ['operation_id',
                         'update_id',
                         'mission',
                         'expected_revision',
                         'pre_revision',
                         'post_revision',
                         'request_sha256',
                         'origin_capture_seq',
                         'bootstrap_constructed_seq',
                         'submit_seq',
                         'accepted_event_id',
                         'completed_event_id',
                         'result_sha256',
                         'outcome',
                         'precondition_oracle',
                         'actual_error_type',
                         'actual_error_details',
                         'reservation_delta',
                         'endpoint_read_delta',
                         'execute_delta'],
            'type': 'object',
            'x-python-exact-type': 'dict'},
 'worker_stop': {'additionalProperties': False,
                 'properties': {'activity_executor_completion_observed': {'type': 'boolean'},
                                'cumulative_stop_deadline_remaining_ms': {'maximum': 150000,
                                                                          'minimum': 0,
                                                                          'type': 'integer',
                                                                          'x-python-exact-type': 'int'},
                                'executor_shutdown_calls': {'enum': [0, 1]},
                                'generation': {'maximum': 8,
                                               'minimum': 1,
                                               'type': 'integer',
                                               'x-python-exact-type': 'int'},
                                'kind': {'enum': ['workflow', 'activity']},
                                'mission': {'enum': ['hosted-normal',
                                                     'hosted-reconcile',
                                                     'hosted-no-ref-cancel']},
                                'public_shutdown_calls': {'const': 1},
                                'public_shutdown_completed': {'const': True},
                                'quiescent_snapshot_seq': {'maximum': 512,
                                                           'minimum': 1,
                                                           'type': 'integer',
                                                           'x-python-exact-type': 'int'},
                                'run_task_wait_elapsed_ms': {'maximum': 1000,
                                                             'minimum': 0,
                                                             'type': 'integer',
                                                             'x-python-exact-type': 'int'},
                                'shutdown_elapsed_ms': {'maximum': 5000,
                                                        'minimum': 0,
                                                        'type': 'integer',
                                                        'x-python-exact-type': 'int'},
                                'start_seq': {'maximum': 512,
                                              'minimum': 1,
                                              'type': 'integer',
                                              'x-python-exact-type': 'int'},
                                'stop_completed_seq': {'maximum': 512,
                                                       'minimum': 1,
                                                       'type': 'integer',
                                                       'x-python-exact-type': 'int'},
                                'stop_requested_seq': {'maximum': 512,
                                                       'minimum': 1,
                                                       'type': 'integer',
                                                       'x-python-exact-type': 'int'},
                                'worker_run_task_completed': {'const': True}},
                 'required': ['generation',
                              'mission',
                              'kind',
                              'start_seq',
                              'stop_requested_seq',
                              'stop_completed_seq',
                              'quiescent_snapshot_seq',
                              'public_shutdown_calls',
                              'public_shutdown_completed',
                              'worker_run_task_completed',
                              'executor_shutdown_calls',
                              'activity_executor_completion_observed',
                              'shutdown_elapsed_ms',
                              'run_task_wait_elapsed_ms',
                              'cumulative_stop_deadline_remaining_ms'],
                 'type': 'object',
                 'x-python-exact-type': 'dict'}}

DAG2_RAW_RULES = {'event_common_allowed_keys': ['eventId',
                               'eventTime',
                               'eventType',
                               'version',
                               'taskId',
                               'workerMayIgnore',
                               'userMetadata',
                               'links',
                               'principal',
                               'eventGroupMarkers'],
 'event_required_keys': ['eventId', 'eventTime', 'eventType'],
 'events': {'ActivityTaskCompleted': {'attribute_allowed_keys': ['result',
                                                                 'scheduledEventId',
                                                                 'startedEventId',
                                                                 'identity',
                                                                 'workerVersion'],
                                      'attribute_key': 'activityTaskCompletedEventAttributes',
                                      'enum': 'EVENT_TYPE_ACTIVITY_TASK_COMPLETED',
                                      'required_extracted_paths': {'payload': 'result',
                                                                   'scheduled_event_id': 'scheduledEventId',
                                                                   'started_event_id': 'startedEventId'}},
            'ActivityTaskFailed': {'attribute_allowed_keys': ['failure',
                                                              'scheduledEventId',
                                                              'startedEventId',
                                                              'identity',
                                                              'retryState',
                                                              'workerVersion',
                                                              'cause'],
                                   'attribute_key': 'activityTaskFailedEventAttributes',
                                   'enum': 'EVENT_TYPE_ACTIVITY_TASK_FAILED',
                                   'required_extracted_paths': {'failure_type': 'failure/applicationFailureInfo/type',
                                                                'non_retryable': 'failure/applicationFailureInfo/nonRetryable',
                                                                'scheduled_event_id': 'scheduledEventId',
                                                                'started_event_id': 'startedEventId'}},
            'ActivityTaskScheduled': {'attribute_allowed_keys': ['activityId',
                                                                 'activityType',
                                                                 'taskQueue',
                                                                 'header',
                                                                 'input',
                                                                 'scheduleToCloseTimeout',
                                                                 'scheduleToStartTimeout',
                                                                 'startToCloseTimeout',
                                                                 'heartbeatTimeout',
                                                                 'workflowTaskCompletedEventId',
                                                                 'retryPolicy',
                                                                 'useWorkflowBuildId',
                                                                 'priority'],
                                      'attribute_key': 'activityTaskScheduledEventAttributes',
                                      'enum': 'EVENT_TYPE_ACTIVITY_TASK_SCHEDULED',
                                      'required_extracted_paths': {'activity_id': 'activityId',
                                                                   'activity_type': 'activityType/name',
                                                                   'maximum_attempts': 'retryPolicy/maximumAttempts',
                                                                   'payload': 'input',
                                                                   'schedule_to_close_timeout': 'scheduleToCloseTimeout',
                                                                   'start_to_close_timeout': 'startToCloseTimeout',
                                                                   'task_queue': 'taskQueue/name',
                                                                   'workflow_task_completed_event_id': 'workflowTaskCompletedEventId'}},
            'ActivityTaskStarted': {'attribute_allowed_keys': ['scheduledEventId',
                                                               'identity',
                                                               'requestId',
                                                               'attempt',
                                                               'lastFailure',
                                                               'workerVersion',
                                                               'buildIdRedirectCounter'],
                                    'attribute_key': 'activityTaskStartedEventAttributes',
                                    'enum': 'EVENT_TYPE_ACTIVITY_TASK_STARTED',
                                    'required_extracted_paths': {'attempt': 'attempt',
                                                                 'scheduled_event_id': 'scheduledEventId'}},
            'TimerCanceled': {'attribute_allowed_keys': ['timerId',
                                                         'startedEventId',
                                                         'workflowTaskCompletedEventId',
                                                         'identity'],
                              'attribute_key': 'timerCanceledEventAttributes',
                              'enum': 'EVENT_TYPE_TIMER_CANCELED',
                              'required_extracted_paths': {'started_event_id': 'startedEventId',
                                                           'timer_id': 'timerId',
                                                           'workflow_task_completed_event_id': 'workflowTaskCompletedEventId'}},
            'TimerFired': {'attribute_allowed_keys': ['timerId', 'startedEventId'],
                           'attribute_key': 'timerFiredEventAttributes',
                           'enum': 'EVENT_TYPE_TIMER_FIRED',
                           'required_extracted_paths': {'started_event_id': 'startedEventId',
                                                        'timer_id': 'timerId'}},
            'TimerStarted': {'attribute_allowed_keys': ['timerId',
                                                        'startToFireTimeout',
                                                        'workflowTaskCompletedEventId'],
                             'attribute_key': 'timerStartedEventAttributes',
                             'enum': 'EVENT_TYPE_TIMER_STARTED',
                             'required_extracted_paths': {'timeout': 'startToFireTimeout',
                                                          'timer_id': 'timerId',
                                                          'workflow_task_completed_event_id': 'workflowTaskCompletedEventId'}},
            'WorkflowExecutionCancelRequested': {'attribute_allowed_keys': ['cause',
                                                                            'externalInitiatedEventId',
                                                                            'externalWorkflowExecution',
                                                                            'identity'],
                                                 'attribute_key': 'workflowExecutionCancelRequestedEventAttributes',
                                                 'enum': 'EVENT_TYPE_WORKFLOW_EXECUTION_CANCEL_REQUESTED',
                                                 'required_extracted_paths': {}},
            'WorkflowExecutionCompleted': {'attribute_allowed_keys': ['result',
                                                                      'workflowTaskCompletedEventId',
                                                                      'newExecutionRunId'],
                                           'attribute_key': 'workflowExecutionCompletedEventAttributes',
                                           'enum': 'EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED',
                                           'required_extracted_paths': {'payload': 'result',
                                                                        'workflow_task_completed_event_id': 'workflowTaskCompletedEventId'}},
            'WorkflowExecutionStarted': {'attribute_allowed_keys': ['workflowType',
                                                                    'parentWorkflowNamespace',
                                                                    'parentWorkflowNamespaceId',
                                                                    'parentWorkflowExecution',
                                                                    'parentInitiatedEventId',
                                                                    'taskQueue',
                                                                    'input',
                                                                    'workflowExecutionTimeout',
                                                                    'workflowRunTimeout',
                                                                    'workflowTaskTimeout',
                                                                    'continuedExecutionRunId',
                                                                    'initiator',
                                                                    'continuedFailure',
                                                                    'lastCompletionResult',
                                                                    'originalExecutionRunId',
                                                                    'identity',
                                                                    'firstExecutionRunId',
                                                                    'retryPolicy',
                                                                    'attempt',
                                                                    'workflowExecutionExpirationTime',
                                                                    'cronSchedule',
                                                                    'firstWorkflowTaskBackoff',
                                                                    'memo',
                                                                    'searchAttributes',
                                                                    'prevAutoResetPoints',
                                                                    'header',
                                                                    'parentInitiatedEventVersion',
                                                                    'workflowId',
                                                                    'sourceVersionStamp',
                                                                    'completionCallbacks',
                                                                    'rootWorkflowExecution',
                                                                    'inheritedBuildId',
                                                                    'versioningOverride',
                                                                    'parentPinnedWorkerDeploymentVersion',
                                                                    'priority',
                                                                    'inheritedPinnedVersion',
                                                                    'inheritedAutoUpgradeInfo',
                                                                    'eagerExecutionAccepted',
                                                                    'declinedTargetVersionUpgrade',
                                                                    'timeSkippingConfig',
                                                                    'timeSkippingStatePropagation'],
                                         'attribute_key': 'workflowExecutionStartedEventAttributes',
                                         'enum': 'EVENT_TYPE_WORKFLOW_EXECUTION_STARTED',
                                         'required_extracted_paths': {'attempt': 'attempt',
                                                                      'execution_timeout': 'workflowExecutionTimeout',
                                                                      'first_run_id': 'firstExecutionRunId',
                                                                      'maximum_attempts': 'retryPolicy/maximumAttempts',
                                                                      'payload': 'input',
                                                                      'run_id': 'originalExecutionRunId',
                                                                      'run_timeout': 'workflowRunTimeout',
                                                                      'task_queue': 'taskQueue/name',
                                                                      'task_timeout': 'workflowTaskTimeout',
                                                                      'workflow_type': 'workflowType/name'}},
            'WorkflowExecutionUpdateAccepted': {'attribute_allowed_keys': ['protocolInstanceId',
                                                                           'acceptedRequestMessageId',
                                                                           'acceptedRequestSequencingEventId',
                                                                           'acceptedRequest'],
                                                'attribute_key': 'workflowExecutionUpdateAcceptedEventAttributes',
                                                'enum': 'EVENT_TYPE_WORKFLOW_EXECUTION_UPDATE_ACCEPTED',
                                                'required_extracted_paths': {'accepted_request_sequencing_event_id': 'acceptedRequestSequencingEventId',
                                                                             'payload': 'acceptedRequest/input/args',
                                                                             'protocol_instance_id': 'protocolInstanceId',
                                                                             'update_id': 'acceptedRequest/meta/updateId',
                                                                             'update_name': 'acceptedRequest/input/name'}},
            'WorkflowExecutionUpdateCompleted': {'attribute_allowed_keys': ['meta',
                                                                            'acceptedEventId',
                                                                            'outcome'],
                                                 'attribute_key': 'workflowExecutionUpdateCompletedEventAttributes',
                                                 'enum': 'EVENT_TYPE_WORKFLOW_EXECUTION_UPDATE_COMPLETED',
                                                 'required_extracted_paths': {'accepted_event_id': 'acceptedEventId',
                                                                              'payload': 'outcome/success',
                                                                              'update_id': 'meta/updateId'}},
            'WorkflowTaskCompleted': {'attribute_allowed_keys': ['scheduledEventId',
                                                                 'startedEventId',
                                                                 'identity',
                                                                 'binaryChecksum',
                                                                 'workerVersion',
                                                                 'sdkMetadata',
                                                                 'meteringMetadata',
                                                                 'deployment',
                                                                 'versioningBehavior',
                                                                 'workerDeploymentVersion',
                                                                 'workerDeploymentName',
                                                                 'deploymentVersion'],
                                      'attribute_key': 'workflowTaskCompletedEventAttributes',
                                      'enum': 'EVENT_TYPE_WORKFLOW_TASK_COMPLETED',
                                      'required_extracted_paths': {'scheduled_event_id': 'scheduledEventId',
                                                                   'started_event_id': 'startedEventId'}},
            'WorkflowTaskScheduled': {'attribute_allowed_keys': ['taskQueue',
                                                                 'startToCloseTimeout',
                                                                 'attempt'],
                                      'attribute_key': 'workflowTaskScheduledEventAttributes',
                                      'enum': 'EVENT_TYPE_WORKFLOW_TASK_SCHEDULED',
                                      'required_extracted_paths': {'attempt': 'attempt',
                                                                   'task_queue': 'taskQueue/name',
                                                                   'task_timeout': 'startToCloseTimeout'}},
            'WorkflowTaskStarted': {'attribute_allowed_keys': ['scheduledEventId',
                                                               'identity',
                                                               'requestId',
                                                               'suggestContinueAsNew',
                                                               'suggestContinueAsNewReasons',
                                                               'targetWorkerDeploymentVersionChanged',
                                                               'historySizeBytes',
                                                               'workerVersion',
                                                               'buildIdRedirectCounter'],
                                    'attribute_key': 'workflowTaskStartedEventAttributes',
                                    'enum': 'EVENT_TYPE_WORKFLOW_TASK_STARTED',
                                    'required_extracted_paths': {'scheduled_event_id': 'scheduledEventId'}}},
 'events_max': 512,
 'events_min': 1,
 'extracted_exact_keys': 'Exactly the keys of required_extracted_paths for that event; payload becomes '
                         'payload_sha256 after strict decoding. No caller-supplied override.',
 'integer_encoding': 'Raw protobuf int64 IDs are decimal strings with pattern ^[1-9][0-9]{0,14}$; known '
                     'int32 attempt/maximumAttempts are exact plain ints; reject bool/float. Convert IDs '
                     'only into bounded plain ints for projection.',
 'payload_contract': {'data': 'Strict canonical base64; decode to UTF-8 bytes, use existing '
                              'duplicate-key-rejecting JSON decoder, validate exact ADR008 shape and '
                              'canonical encoded byte cap; payload_sha256 is SHA-256 of canonical decoded '
                              'plain value. Never use decoded data as authority or remote instructions.',
                      'encoding_literal': 'anNvbi9wbGFpbg==',
                      'metadata_exact_keys': ['encoding'],
                      'payload_count': 1,
                      'payload_exact_keys': ['metadata', 'data'],
                      'wrapper_exact_keys': ['payloads']},
 'projected_event_exact_keys': ['event_id', 'event_type', 'extracted'],
 'root_allowed_keys': ['events'],
 'root_required_keys': ['events'],
 'schema_version': 'opendot.temporal.dag2-raw-history-extraction.v1',
 'sdk': '1.34.0',
 'sdk_source_file_sha256': 'a56f77261d45e0d04f5ac994fd6d6668e565159a70239438bc2b5443597b3753',
 'trust_limit': 'The stdlib verifier independently reconstructs and matches every closed extracted fact from '
                'retained raw bytes. General protobuf nested metadata not listed in extraction is '
                'interpreted only by the pinned SDK/harness and is not claimed independently checked by the '
                'stdlib verifier. Unknown root/event/per-event attribute keys are rejected using these '
                'frozen tables. No generic SDK parser is added.'}

DAG2_REQUIRED_NODES = ('tests/acceptance/temporal_dag_recovery_gate.py::test_dag2_real_a_to_b_and_original_receipts',
 'tests/acceptance/temporal_dag_recovery_gate.py::test_dag2_quiescent_worker_replacement_preserves_state',
 'tests/acceptance/temporal_dag_recovery_gate.py::test_dag2_recorded_history_replay_has_no_activity_execution',
 'tests/acceptance/temporal_dag_recovery_gate.py::test_dag2_original_put_reconciliation_never_reexecutes_a',
 'tests/acceptance/temporal_dag_recovery_gate.py::test_dag2_unknown_without_reference_blocks_b',
 'tests/acceptance/temporal_dag_recovery_gate.py::test_dag2_cancellation_keeps_unadmitted_b_closed',
 'tests/acceptance/temporal_dag_recovery_gate.py::test_dag2_duplicate_and_stale_updates_consume_no_allowance')

DAG2_SOURCE_CLOSURE = ('.github/workflows/temporal-server.yml',
 'AGENTS.md',
 'ci/acquire_temporal_cli.py',
 'ci/requirements.txt',
 'ci/run_temporal_server_gate.py',
 'ci/temporal-batch-nodes.txt',
 'ci/temporal-dag-recovery-nodes.txt',
 'ci/temporal-real-batch-nodes.txt',
 'ci/temporal-sdk-requirements.txt',
 'ci/temporal-server-nodes.txt',
 'ci/verify_temporal_server_gate.py',
 'docs/decisions/004-temporal-reference-transport.md',
 'docs/decisions/008-fixed-dependent-temporal-recovery.md',
 'docs/temporal-batch-qualification.md',
 'docs/temporal-reference-transport.md',
 'pyproject.toml',
 'src/opendot_engineering/__init__.py',
 'src/opendot_engineering/adapters/__init__.py',
 'src/opendot_engineering/adapters/source_audit.py',
 'src/opendot_engineering/adapters/temporal_activity.py',
 'src/opendot_engineering/adapters/temporal_workflow.py',
 'src/opendot_engineering/core/__init__.py',
 'src/opendot_engineering/core/artifacts.py',
 'src/opendot_engineering/core/contracts.py',
 'src/opendot_engineering/tool_runtime.py',
 'tests/acceptance/temporal_dag_recovery_gate.py',
 'tests/acceptance/temporal_real_batch_gate.py',
 'tests/acceptance/temporal_server_gate.py',
 'tests/test_a2a_worker_turn.py',
 'tests/test_temporal_activity_contract.py',
 'tests/test_temporal_cli_acquisition.py',
 'tests/test_temporal_dag_recovery.py',
 'tests/test_temporal_server_gate_verifier.py',
 'tests/test_temporal_server_harness_unit.py',
 'tests/test_temporal_transport_owner_boundaries.py',
 'tests/test_temporal_workflow_contract.py')

DAG2_INPUT_FILES = ('acquisition-receipt.json',
 'collected-nodes.txt',
 'dag-sdk-summary.json',
 'dag2-cleanup.json',
 'dag2-diagnostic.json',
 'dag2-environment.json',
 'dag2-originals.json',
 'dag2-replays.json',
 'dag2-trace.json',
 'no-ref-cancel-final.history.json',
 'no-ref-cancel-final.state.json',
 'no-ref-unknown.history.json',
 'no-ref-unknown.state.json',
 'normal-a.result.json',
 'normal-b.result.json',
 'normal-final.history.json',
 'normal-final.state.json',
 'pip-report.json',
 'reconcile-a.result.json',
 'reconcile-b.result.json',
 'reconcile-final.history.json',
 'reconcile-final.state.json',
 'reconcile-unknown-after-replacement.history.json',
 'reconcile-unknown-after-replacement.state.json',
 'reconcile-unknown-before-stop.history.json',
 'reconcile-unknown-before-stop.state.json',
 'reconcile-update-queued.history.json',
 'reconcile-update-queued.state.json',
 'required-nodes.txt',
 'results.xml',
 'shared-unit-summary.json',
 'source-manifest.json')

DAG2_SOURCE_PATHS = ('.github/workflows/portable.yml',
 '.github/workflows/temporal-server.yml',
 '.gitignore',
 'AGENTS.md',
 'CAPABILITIES.md',
 'CAPABILITIES.zh-CN.md',
 'CHANGELOG.md',
 'CONTRIBUTING.md',
 'LAUNCH-COPY.md',
 'LICENSE',
 'NOTICE',
 'OVERVIEW.md',
 'OVERVIEW.zh-CN.md',
 'README.md',
 'README.zh-CN.md',
 'RESEARCH-MAP.md',
 'RESEARCH-MAP.zh-CN.md',
 'SECURITY.md',
 'SUPPORT.md',
 'assets/brand/NOTICE',
 'assets/brand/README.md',
 'assets/brand/opendot-mark-dark.svg',
 'assets/brand/opendot-mark-light.svg',
 'assets/brand/opendot-readme-banner-dark.svg',
 'assets/brand/opendot-readme-banner-light.svg',
 'assets/brand/opendot-wordmark-dark.svg',
 'assets/brand/opendot-wordmark-light.svg',
 'ci/README.md',
 'ci/acquire_temporal_cli.py',
 'ci/agent-contract-nodes.txt',
 'ci/build-toolchain-requirements.txt',
 'ci/callable-nodes.txt',
 'ci/check_docs.py',
 'ci/composition-nodes.txt',
 'ci/delivery-workflow-nodes.txt',
 'ci/git-workspace-nodes.txt',
 'ci/portable-nodes.txt',
 'ci/public-regression-nodes.txt',
 'ci/readonly-artifact-nodes.txt',
 'ci/requirements.txt',
 'ci/run_temporal_server_gate.py',
 'ci/solver-crosscheck-nodes.txt',
 'ci/source-boundary-nodes.txt',
 'ci/source-provenance-nodes.txt',
 'ci/source_provenance.py',
 'ci/summarize_tests.py',
 'ci/temporal-batch-nodes.txt',
 'ci/temporal-dag-recovery-nodes.txt',
 'ci/temporal-real-batch-nodes.txt',
 'ci/temporal-sdk-requirements.txt',
 'ci/temporal-server-nodes.txt',
 'ci/verify_temporal_server_gate.py',
 'docs/PROVENANCE.md',
 'docs/a2a-http-transport.md',
 'docs/a2a-worker-turn.md',
 'docs/a5-candidate-verification.md',
 'docs/a6-candidate-verification.md',
 'docs/agent-contracts-verification.md',
 'docs/agent-contracts.md',
 'docs/architecture.md',
 'docs/build-toolchain.md',
 'docs/cad-geometry.md',
 'docs/cad-mesh.md',
 'docs/callable-execution-verification.md',
 'docs/callable-execution.md',
 'docs/canonical-artifacts-verification.md',
 'docs/canonical-artifacts.md',
 'docs/ci-toolchain.md',
 'docs/claim-status.md',
 'docs/combined-candidate-verification.md',
 'docs/decisions/001-source-admission.md',
 'docs/decisions/002-canonical-artifact-core.md',
 'docs/decisions/003-agent-metadata-contracts.md',
 'docs/decisions/004-temporal-reference-transport.md',
 'docs/decisions/005-bounded-artifact-reads.md',
 'docs/decisions/006-fixed-measurement-composition.md',
 'docs/decisions/007-bounded-external-worker-turn.md',
 'docs/decisions/008-fixed-dependent-temporal-recovery.md',
 'docs/delivery-workflows-verification.md',
 'docs/documentation-checks.md',
 'docs/documentation-plan.md',
 'docs/evidence.md',
 'docs/execution-core-verification.md',
 'docs/getting-started.md',
 'docs/git-provenance-verification.md',
 'docs/git-workspaces-residue-fix.md',
 'docs/git-workspaces-verification.md',
 'docs/git-workspaces.md',
 'docs/gmsh-cpu-ceiling.md',
 'docs/host-development/README.md',
 'docs/host-development/receipt.json',
 'docs/installed-quickstart.md',
 'docs/installed-quickstart.zh-CN.md',
 'docs/integration-review.md',
 'docs/local-source-audit.md',
 'docs/marketing-copy.md',
 'docs/metadata-predecessor-acceptance.md',
 'docs/module-cli.md',
 'docs/parallel-development-verification.md',
 'docs/peer-benchmark.md',
 'docs/peer-repository-snapshot.json',
 'docs/pr23-ci-evidence.json',
 'docs/proposed-release-readiness.md',
 'docs/provenance-integration-verification.md',
 'docs/readonly-artifacts-verification.md',
 'docs/release-checklist.md',
 'docs/release-inventory/v0.3.0a3/README.md',
 'docs/release-inventory/v0.3.0a3/SHA256SUMS',
 'docs/release-inventory/v0.3.0a3/build_inventory.py',
 'docs/release-inventory/v0.3.0a3/component-inventory.json',
 'docs/release-inventory/v0.3.0a3/generation-result.json',
 'docs/release-inventory/v0.3.0a3/hardening-review.json',
 'docs/release-inventory/v0.3.0a3/hardening.patch',
 'docs/release-inventory/v0.3.0a3/temporal-rust-lock-inventory.json',
 'docs/release-inventory/v0.3.0a3/test-details.txt',
 'docs/release-inventory/v0.3.0a3/test-result.json',
 'docs/release-inventory/v0.3.0a3/test_inventory.py',
 'docs/release-inventory/v0.3.0a3/upstream-license-evidence.json',
 'docs/release-inventory/v0.3.0a3/validation-results.json',
 'docs/release-inventory/v0.3.0a3/verification-result.json',
 'docs/research/README.md',
 'docs/research/academic-needs.md',
 'docs/research/delta-20261002/README.md',
 'docs/research/delta-20261002/source-needs-delta.json',
 'docs/research/demand-gap-20261001/README.md',
 'docs/research/demand-gap-20261001/README.zh-CN.md',
 'docs/research/demand-gap-20261001/acceptance-cases.json',
 'docs/research/demand-gap-20261001/source-needs-delta.json',
 'docs/research/hillhouse-delta-20261002/README.md',
 'docs/research/hillhouse-delta-20261002/source-needs-delta.json',
 'docs/research/hillhouse-industry.md',
 'docs/research/hillhouse-primary-addendum.zh-CN.md',
 'docs/research/industry-cases.md',
 'docs/research/interoperability-delta-20261002/README.md',
 'docs/research/interoperability-delta-20261002/source-needs-delta.json',
 'docs/research/lidang.md',
 'docs/research/official-strategy.md',
 'docs/research/oss-workflows/BENCHMARK.md',
 'docs/research/oss-workflows/INDEPENDENT-REVIEW.md',
 'docs/research/oss-workflows/PRIMARY-SOURCES.md',
 'docs/research/oss-workflows/PROJECTION.json',
 'docs/research/oss-workflows/README.md',
 'docs/research/oss-workflows/SHA256SUMS',
 'docs/research/oss-workflows/TICKETS.md',
 'docs/research/oss-workflows/VALIDATION.json',
 'docs/research/oss-workflows/WORKFLOW-SPEC.md',
 'docs/research/oss-workflows/evidence/repository-snapshot.json',
 'docs/research/oss-workflows/evidence/source-needs-additions.json',
 'docs/research/oss-workflows/frozen-oracle/SHA256SUMS',
 'docs/research/oss-workflows/frozen-oracle/case-oracles.json',
 'docs/research/oss-workflows/frozen-oracle/expected-summary.json',
 'docs/research/oss-workflows/frozen-oracle/measurements.csv',
 'docs/research/refresh-20261001/README.zh-CN.md',
 'docs/research/refresh-20261001/manifest.json',
 'docs/research/refresh-20261001/source-needs-delta.json',
 'docs/research/scaling-literature-20261002/README.md',
 'docs/research/scaling-literature-20261002/evidence.json',
 'docs/research/sequoia-hongshan.md',
 'docs/research/source-needs-index.json',
 'docs/simulated-lab.md',
 'docs/solver-cpu-ceiling.md',
 'docs/solver-version-gate.md',
 'docs/source-admission-verification.md',
 'docs/source-admission.md',
 'docs/source-lock-schema.md',
 'docs/source-provenance-inventory.md',
 'docs/structural-beam.md',
 'docs/structural-default-v2.md',
 'docs/structural-elastic-energy.md',
 'docs/structural-v2-candidate-verification.md',
 'docs/synthetic-lab-qualification.md',
 'docs/temporal-batch-qualification.md',
 'docs/temporal-qualification-evidence.md',
 'docs/temporal-reference-failure-matrix.md',
 'docs/temporal-reference-transport.md',
 'docs/thermal-conduction.md',
 'docs/thermal-source.md',
 'docs/verification-status.md',
 'docs/verifier-ci-verification.md',
 'examples/agent-contracts/README.md',
 'examples/agent-contracts/demo.py',
 'examples/cad_cae/README.md',
 'examples/cad_cae/README.zh-CN.md',
 'examples/cad_cae/beam.parameters.json',
 'examples/cad_cae/mesh-beam.json',
 'examples/cad_cae/native-geometry-reference/README.md',
 'examples/cad_cae/native-geometry-reference/beam.step',
 'examples/cad_cae/native-geometry-reference/evidence.json',
 'examples/cad_cae/requirements-tested.txt',
 'examples/cad_cae/thermal-benchmark.json',
 'examples/cad_cae/thermal_workflow.py',
 'examples/callable-artifacts/README.md',
 'examples/callable-artifacts/demo.py',
 'examples/callable-execution/README.md',
 'examples/callable-execution/demo.py',
 'examples/canonical-artifacts/README.md',
 'examples/canonical-artifacts/roundtrip.py',
 'examples/git-workspaces/README.md',
 'examples/git-workspaces/demo.py',
 'examples/lab-qualification/fixture.json',
 'examples/lab-qualification/manifest.json',
 'examples/measurement-review/README.md',
 'examples/measurement-review/README.zh-CN.md',
 'examples/measurement-review/batch.csv',
 'examples/measurement-review/compare.py',
 'examples/measurement-review/comparison-fixtures.json',
 'examples/measurement-review/demo.py',
 'examples/measurement-review/utility_report.py',
 'examples/simulated-lab/requirements-tested.txt',
 'examples/source-audit/manifest.json',
 'examples/source-audit/sources/synthetic.json',
 'examples/source-boundary/README.md',
 'examples/source-boundary/demo.py',
 'examples/source-boundary/parameter-fixtures.json',
 'examples/source-boundary/proposals.json',
 'pyproject.toml',
 'src/opendot_engineering/__init__.py',
 'src/opendot_engineering/__main__.py',
 'src/opendot_engineering/adapters/__init__.py',
 'src/opendot_engineering/adapters/_simulated_lab_worker.py',
 'src/opendot_engineering/adapters/a2a_http_transport.py',
 'src/opendot_engineering/adapters/a2a_worker_turn.py',
 'src/opendot_engineering/adapters/lab_qualification.py',
 'src/opendot_engineering/adapters/simulated_lab.py',
 'src/opendot_engineering/adapters/source_admission.py',
 'src/opendot_engineering/adapters/source_audit.py',
 'src/opendot_engineering/adapters/temporal_activity.py',
 'src/opendot_engineering/adapters/temporal_workflow.py',
 'src/opendot_engineering/core/__init__.py',
 'src/opendot_engineering/core/artifacts.py',
 'src/opendot_engineering/core/contracts.py',
 'src/opendot_engineering/executors/_gmsh_worker.py',
 'src/opendot_engineering/executors/geometry.py',
 'src/opendot_engineering/executors/gmsh_mesh.py',
 'src/opendot_engineering/executors/structural_beam.py',
 'src/opendot_engineering/executors/thermal_conduction.py',
 'src/opendot_engineering/executors/thermal_source.py',
 'src/opendot_engineering/git_workspace.py',
 'src/opendot_engineering/tool_runtime.py',
 'templates/change-request.md',
 'templates/issue-report.md',
 'tests/acceptance/temporal_dag_recovery_gate.py',
 'tests/acceptance/temporal_real_batch_gate.py',
 'tests/acceptance/temporal_server_gate.py',
 'tests/fixtures/a2a_worker_turn_v1.json',
 'tests/test_a2a_http_transport.py',
 'tests/test_a2a_worker_turn.py',
 'tests/test_adapter_provenance.py',
 'tests/test_agent_contracts.py',
 'tests/test_bounded_artifact_reads.py',
 'tests/test_cad_thermal_workflow.py',
 'tests/test_callable_artifacts.py',
 'tests/test_callable_cleanup_regressions.py',
 'tests/test_callable_contracts.py',
 'tests/test_callable_independent_regressions.py',
 'tests/test_callable_profile.py',
 'tests/test_callable_repaired_edges.py',
 'tests/test_canonical_artifacts.py',
 'tests/test_ci_summary.py',
 'tests/test_ci_toolchain_lock.py',
 'tests/test_demo_output_errors.py',
 'tests/test_documentation_checks.py',
 'tests/test_geometry.py',
 'tests/test_git_workspace.py',
 'tests/test_gmsh_cpu_ceiling.py',
 'tests/test_gmsh_mesh.py',
 'tests/test_incremental_utility_report.py',
 'tests/test_lab_qualification.py',
 'tests/test_measurement_comparison_example.py',
 'tests/test_measurement_review_example.py',
 'tests/test_module_cli.py',
 'tests/test_readonly_artifacts.py',
 'tests/test_research_index.py',
 'tests/test_simulated_lab.py',
 'tests/test_solver_cpu_ceiling.py',
 'tests/test_solver_version_identity.py',
 'tests/test_source_admission.py',
 'tests/test_source_audit.py',
 'tests/test_source_boundary_example.py',
 'tests/test_source_conflict_example.py',
 'tests/test_source_provenance.py',
 'tests/test_structural_beam.py',
 'tests/test_structural_default_v2.py',
 'tests/test_structural_elastic_energy.py',
 'tests/test_temporal_activity_contract.py',
 'tests/test_temporal_cli_acquisition.py',
 'tests/test_temporal_dag_recovery.py',
 'tests/test_temporal_server_gate_verifier.py',
 'tests/test_temporal_server_harness_unit.py',
 'tests/test_temporal_transport_owner_boundaries.py',
 'tests/test_temporal_workflow_contract.py',
 'tests/test_thermal_conduction.py',
 'tests/test_thermal_source.py')

DAG2_UNIT_IMMUTABLE_SOURCE = {'.github/workflows/portable.yml': ('93179aa62c32d527b2e51f7ff39d21dfa747c0249a61f1edf83c240cad116796',
                                    2776,
                                    '100644'),
 '.gitignore': ('5bc54a4d08ea5c8e82985212943bfeee3f2726e5c09f525d1e9edd81241eeb45', 108, '100644'),
 'CAPABILITIES.md': ('3151ff19ddb662fc6bf290f25449d1303dd798584ad2da41d23cab5ee38cc9ab', 21008, '100644'),
 'CAPABILITIES.zh-CN.md': ('a09e4f6a98e2bd081ff1dbd14129f444f6a670bc8fcf36652a5debc5b75e5ccf',
                           19272,
                           '100644'),
 'CHANGELOG.md': ('35823b5f6aac63e80692567d1e4e767d9ce4263bc5124e8de8ab948142443e85', 22579, '100644'),
 'CONTRIBUTING.md': ('64b817a16a53d07720f54461e22e10684d71a314f387b53b09500a50731f6428', 5487, '100644'),
 'LAUNCH-COPY.md': ('8ac025efd12a9cfb9773c315a4b0530361d81b2974d8fd8f4dc3cd6612f2dea3', 8648, '100644'),
 'LICENSE': ('cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30', 11358, '100644'),
 'NOTICE': ('735c9cf9950c633044b21a82d3508ecdc36b4eb6635ecfc38769418c50fc87d5', 2233, '100644'),
 'OVERVIEW.md': ('459c8261f7b1573f619ecb326048787f0c810aed44438f393fc98b31e65dae21', 14818, '100644'),
 'OVERVIEW.zh-CN.md': ('33a3fb95ae2ebc23b959b1e327b20e3326b2805f7e5bd0c768928126ea200903', 13922, '100644'),
 'README.md': ('34e19f89b05d07bfb13f27a8c19260d8670e5b7e093fafc5cdfc9998e36eec6e', 12662, '100644'),
 'README.zh-CN.md': ('0056d2211fcf0af701708139f0f3fa2c69350408da7ca116f4708d60c537ec70', 12144, '100644'),
 'RESEARCH-MAP.md': ('3a20b7622248b17ffd351f35e366fd86f74b2485e5c6eab9563c2314b64baa27', 22183, '100644'),
 'RESEARCH-MAP.zh-CN.md': ('1c1088a004efe86aef2b590867297f1b87957099c9b48d1e65078bb5af733a7b',
                           19285,
                           '100644'),
 'SECURITY.md': ('751a3b03025c70a64f1d978a50d1a96ce3c2eacb67719fcfeff3e72ae465ba72', 4534, '100644'),
 'SUPPORT.md': ('e8b388bff6c659af986740e85ba8d3a88333b09ee7c0af62d85548470906dc41', 8855, '100644'),
 'assets/brand/NOTICE': ('30e0bb23fb8c7773c8a5f7a26ab13f527bddac1ea102df648081c164ee65b293', 632, '100644'),
 'assets/brand/README.md': ('1c0ae59daa834f88b8946a6173e571ba2c6a66a3a403d96e50acd3f94cc0d8df',
                            1616,
                            '100644'),
 'assets/brand/opendot-mark-dark.svg': ('8aa7e9855bc04ed9c55a5d5b50bf2ea10700a358098f3fa14f64a9a0b138a561',
                                        740,
                                        '100644'),
 'assets/brand/opendot-mark-light.svg': ('48626473f3e84a64f61991b5196baffe86881e2fe3e503ae7ceeb99b7c9b35e4',
                                         741,
                                         '100644'),
 'assets/brand/opendot-readme-banner-dark.svg': ('cdbb61483de4bf5d08303adca2fdaae300c86cdfe2cf0c0daa366875ac0644d6',
                                                 1956,
                                                 '100644'),
 'assets/brand/opendot-readme-banner-light.svg': ('90d77a05284ad258f5ca36dd82c059888fdb5e37d8d4cc10d8a8c02a4bbe1c8d',
                                                  1957,
                                                  '100644'),
 'assets/brand/opendot-wordmark-dark.svg': ('a793e0a97c089f765c7e10e5cebfe9ecc855c086c3cb24fefb670fbb0a4815f7',
                                            1649,
                                            '100644'),
 'assets/brand/opendot-wordmark-light.svg': ('f81881545bb16424008c66b07cb40fff2a1cfeeb6ca87c6ceae7a0159dc74ba9',
                                             1650,
                                             '100644'),
 'ci/README.md': ('1a36f7b2c6ad5ccc6e337e63345419184a4ac6187a0e45cdc48994cdc2dde7bf', 12294, '100644'),
 'ci/acquire_temporal_cli.py': ('4283fe5927703ef8b9bbbfedd4a911e824cf4eb3888a80b78dfbe0c6c60779fb',
                                15673,
                                '100644'),
 'ci/agent-contract-nodes.txt': ('130b15599401b90a10d387c0b945cc44a48f57f2750a950e28bbf1037ce54d23',
                                 2960,
                                 '100644'),
 'ci/build-toolchain-requirements.txt': ('306c857c7ec3f3a6add61c31d85889e3e37289a3f2453d8a2bb346bb42616e4e',
                                         161,
                                         '100644'),
 'ci/callable-nodes.txt': ('132e7a9448eb315fe400b818ad6b4aa8b870415d1cd93437906720140217b026',
                           13323,
                           '100644'),
 'ci/check_docs.py': ('c38018d52abe87e03923dd8a3fd8776f8d084f4aad9a55c151a8c9c527f3bc23', 13205, '100644'),
 'ci/composition-nodes.txt': ('c5838be625dadd476d6f58b0e1df5af6c7a338435513a27274b68c9c8d58a3b0',
                              44619,
                              '100644'),
 'ci/delivery-workflow-nodes.txt': ('a9dab10d0546604e923b9c8c77d3c5f2b86b00b83d3c9460c174d3ea7b29d70c',
                                    70964,
                                    '100644'),
 'ci/git-workspace-nodes.txt': ('aa9aa95e003d98bf7c1bfd89fda90ee60bbab76582a089bea2e30cb53a7337a0',
                                6410,
                                '100644'),
 'ci/portable-nodes.txt': ('5487ce415fda1190c04064be52f20b224b8937160c296e3efb1d67fd773bfefd',
                           48778,
                           '100644'),
 'ci/public-regression-nodes.txt': ('0ff13bb8eefbfa9be744da77897f40e90495794690d5f16b7d7b9cb4d57abecd',
                                    27333,
                                    '100644'),
 'ci/readonly-artifact-nodes.txt': ('3352ae15611cf43e9501a9cfd61decceb54f0573dc8cb0e3b820759512646089',
                                    8633,
                                    '100644'),
 'ci/requirements.txt': ('d4a40a3a0837215c3ab557d110437034fc36e3de888a3720301ab7d40e433600', 700, '100644'),
 'ci/solver-crosscheck-nodes.txt': ('e8c801dc458f171865a567d0faac7f9f4d2aa79527e86f5419b8f6a7a4c75430',
                                    16694,
                                    '100644'),
 'ci/source-boundary-nodes.txt': ('43f1ee20eeb2aa69d9e8671c5d7951da15b1817b1b9feb4672df430195beaf8d',
                                  8590,
                                  '100644'),
 'ci/source-provenance-nodes.txt': ('45f235fec98c2e2268b0bb7e0433bab3384ab8663eea83393fed9a407d796303',
                                    7469,
                                    '100644'),
 'ci/source_provenance.py': ('ef49f4d72c79dfd2697aad50e7a9370b464b776362a257418b628eee0e09349a',
                             14137,
                             '100644'),
 'ci/summarize_tests.py': ('16de68818d286c79b306309593a03e0e52ea3009aa8547dec9ca4339cf9f33a4',
                           1146,
                           '100644'),
 'ci/temporal-batch-nodes.txt': ('95e46d92e349792635e6d18acc1815f981ddb80f325f244ddc3d84063c3b08e1',
                                 43719,
                                 '100644'),
 'ci/temporal-real-batch-nodes.txt': ('7ad383036ff782bf7b1c684c4857c5cb5f3952ea3e9fa1f72f5a975822c62b1d',
                                      377,
                                      '100644'),
 'ci/temporal-sdk-requirements.txt': ('f8ea76390c3f260bf48aa68ed64c4e80cf52e00bfb675d09be4eedd123748d89',
                                      788,
                                      '100644'),
 'ci/temporal-server-nodes.txt': ('315d557eda272ea471ca85b4e32b432d2c059b72ae6082bee529a54003acd37f',
                                  632,
                                  '100644'),
 'docs/PROVENANCE.md': ('26bc26f76c45efcefc30d99c7688b420294e6aeabb76a8e26d2565e5ad3c8273', 9195, '100644'),
 'docs/a2a-http-transport.md': ('4c23f8128ab1ae431c3dcc6122dd28ca7a6968d88f952da20a681063a4bef44f',
                                13112,
                                '100644'),
 'docs/a2a-worker-turn.md': ('8965a64eec08e8d62f9d0e7e1eacf3d03cda49282b5c0779a40d5781cb848d49',
                             17686,
                             '100644'),
 'docs/a5-candidate-verification.md': ('d99fa924a15c076be00eab499de87e4e22186fddd65dfc052e7b2ac9647c7c8e',
                                       6024,
                                       '100644'),
 'docs/a6-candidate-verification.md': ('c34846f0d707e813f109442ab7c57462faf6fef165a9ee47b3cb97b76929d60c',
                                       3889,
                                       '100644'),
 'docs/agent-contracts-verification.md': ('9db5f9da780bf1c9a3974fe1e34520831396f03a145de429d2b1afbbb44dd472',
                                          3390,
                                          '100644'),
 'docs/agent-contracts.md': ('bbdbb1bd9643941976593428768fe5dc3b063d1a9c163bc854ffab89f1d0aabd',
                             4925,
                             '100644'),
 'docs/architecture.md': ('f1a23fbd017b749dec39f791bd3397f3f9e51f209ed7326f2fbfff673a1961b7', 9780, '100644'),
 'docs/build-toolchain.md': ('cf5ff574709f156daa0c5536167c68af50e0def47b06d9fe7999ad6c797e902b',
                             1937,
                             '100644'),
 'docs/cad-geometry.md': ('0affb2ba226186e2c6e29bd0a8ff3397cb9a6ffcaca99fed4043355067482c79',
                          10629,
                          '100644'),
 'docs/cad-mesh.md': ('fa905cb5a88f141851e90359990eba7eade0c02f4c03a689f12e14d2e9379947', 11774, '100644'),
 'docs/callable-execution-verification.md': ('89427939cbd405686ee0b7cbc8f5bea87a62f68cf4cc964670508d563d1014e7',
                                             4898,
                                             '100644'),
 'docs/callable-execution.md': ('ac6a384f0652ab7414f95f7acd4179829fc2fd522a838de4325ca8a99a18f8d2',
                                7194,
                                '100644'),
 'docs/canonical-artifacts-verification.md': ('4b356a41ef52a28cb26792dbb13776b68efed1caf799a2955893230664e961fa',
                                              2908,
                                              '100644'),
 'docs/canonical-artifacts.md': ('524a312c6601db4d4215d8a562f05a5a29ca55bc234ab613c5f0c895b7bd6a36',
                                 9870,
                                 '100644'),
 'docs/ci-toolchain.md': ('7248d934830c1c2db824d31f19342104756bf24dc505f786cd8918ebe6436df1', 4692, '100644'),
 'docs/claim-status.md': ('54f50b447c74cea465d3f32e04ae2b3a9f6d9f9bf2d928c6f6d9d8c43d043c37',
                          23208,
                          '100644'),
 'docs/combined-candidate-verification.md': ('3595d49e0e274bb930ea13a422cfc90cf715b41fbbbd46b2b48125783d1c3a86',
                                             5803,
                                             '100644'),
 'docs/decisions/001-source-admission.md': ('4c899405c0d7329c10f2fa37f073a9f74eb70d31a7efbf0bcd8d0247c270758c',
                                            2050,
                                            '100644'),
 'docs/decisions/002-canonical-artifact-core.md': ('a4fa2869c982c742757f11514287743f0119b4cec66318dc12991c56094e9d3c',
                                                   3612,
                                                   '100644'),
 'docs/decisions/003-agent-metadata-contracts.md': ('ed6757a910c73e9ba0368e1384130630bfa3350e6d8982e2970e0fcf80bdda17',
                                                    2333,
                                                    '100644'),
 'docs/decisions/004-temporal-reference-transport.md': ('534b446d671444d076866aadcfd3905e54126561705f547eca2ff5f2684c0e9b',
                                                        50119,
                                                        '100644'),
 'docs/decisions/005-bounded-artifact-reads.md': ('8aa14f9073a7069b3356e2526410cfc71a213822a76ffb493a76b94ae3f85e5f',
                                                  7953,
                                                  '100644'),
 'docs/decisions/006-fixed-measurement-composition.md': ('793740b8ab48d022583a20068210aa1d545041321d43de1dd544db8867415a83',
                                                         9499,
                                                         '100644'),
 'docs/decisions/007-bounded-external-worker-turn.md': ('0c4b5e46852ea63ed3035fe75978f45d5f35f335a685786e16fc6c2781b83ecb',
                                                        16534,
                                                        '100644'),
 'docs/decisions/008-fixed-dependent-temporal-recovery.md': ('c7d18394d4a88b74e9b0b30ba5ba960bbc5177e19b2f6c115db91b23819b6737',
                                                             61183,
                                                             '100644'),
 'docs/delivery-workflows-verification.md': ('ee80e342473e7f48bc593269c7a82537845a23ec4801035000d64f87cc177a32',
                                             4996,
                                             '100644'),
 'docs/documentation-checks.md': ('e81cf680f223b165577a8949b22720a73cd326eadbc60bc4f1b133d0b2bbe745',
                                  7702,
                                  '100644'),
 'docs/documentation-plan.md': ('cb4b73b033c3e13656420a59b92d703283e2a857f3c3778b723626c73d27373a',
                                2065,
                                '100644'),
 'docs/evidence.md': ('7913fe230ede9e7fdcd9d4721e118784a8c510e35533a202be2a494d4447a415', 3462, '100644'),
 'docs/execution-core-verification.md': ('f3fbd9f156bd23b4a77b8aa5807719bb82611ebb4cd1a9d5d1751412d651d529',
                                         5166,
                                         '100644'),
 'docs/getting-started.md': ('b4a6c08be948fb8e927569e1bfb4d01acb84b82ab39ad42f2d3037962487b500',
                             10413,
                             '100644'),
 'docs/git-provenance-verification.md': ('63aa3bac0e591333f05c34cc5d71f372b42e46a3499807359d1d4940c0d3b458',
                                         4101,
                                         '100644'),
 'docs/git-workspaces-residue-fix.md': ('b5e0c3bf0f194a2478c31e51bc07ac7dbfd79b82f287413f22c67bd25ffb59b6',
                                        2114,
                                        '100644'),
 'docs/git-workspaces-verification.md': ('1ee7fb57a5ea5745ebea7f3f1bb4138a8a2c43680e2a8bc0b3e4046c234e9999',
                                         4305,
                                         '100644'),
 'docs/git-workspaces.md': ('8ea0e5df695fea7000fbfe4923607a8397a4123dcf9a11363b0e92916aea6158',
                            8205,
                            '100644'),
 'docs/gmsh-cpu-ceiling.md': ('3b7bb77a2ced31e9a611a73da4a2ddbbcbc7a3f4f4101f5962b75b0058ac4e89',
                              3710,
                              '100644'),
 'docs/host-development/README.md': ('46dd30813c84d2aaa37520e8720e78c681f8df3984294c2b44e007475ca86bc7',
                                     4854,
                                     '100644'),
 'docs/host-development/receipt.json': ('cb0a83ea625bbc71d3110371109695619df724c6fb9e3ad2a8ff09e2a6b9a362',
                                        12671,
                                        '100644'),
 'docs/installed-quickstart.md': ('79f818e68f8833a9b29df196e401f65151b5854ef1ee8202a9696d56a071be64',
                                  17608,
                                  '100644'),
 'docs/installed-quickstart.zh-CN.md': ('c75b4826af287adb2b0bfd2b0ab3beb81b88d10cbcc3a0dd2cd00d994b4e1827',
                                        16412,
                                        '100644'),
 'docs/integration-review.md': ('581fc65ff5371955a239621eacc563a1f6055268e1083618f339c89cb280538f',
                                3554,
                                '100644'),
 'docs/local-source-audit.md': ('ef599087ab44239e9fd48e0d9abac93f7b2c19da7fae8e04f4fca6d99c417202',
                                6092,
                                '100644'),
 'docs/marketing-copy.md': ('df5d7e66db74c94c4f5208dd29a48a4c4f582a7fcfaf1420e77bbde97c2eceb7',
                            3436,
                            '100644'),
 'docs/metadata-predecessor-acceptance.md': ('0aff710133ab6050ffb996fc183515a7f38a72f919bc0ebfb1fbefc3c59d069e',
                                             1952,
                                             '100644'),
 'docs/module-cli.md': ('f00a322e60fbf46b9f97cfecbe6ce90d91c182f76b10103e9c5f0294175acbf4', 2752, '100644'),
 'docs/parallel-development-verification.md': ('601b4af77f7bb7522c09d677cb4cd7497375f56fe9eee79d9c91dfea1230924f',
                                               3132,
                                               '100644'),
 'docs/peer-benchmark.md': ('ba5e5f9aab042898ca72a6e3034d01005a0aecd27668b3c2e90b0715cc6b3eb9',
                            3726,
                            '100644'),
 'docs/peer-repository-snapshot.json': ('c02db82c6445ca54d7d448a5f8d26faf68fdfdbf737290b38ca975e61300b212',
                                        1516,
                                        '100644'),
 'docs/pr23-ci-evidence.json': ('a6b71334adf3b11a7156bbf41b1ef0213b69096b8cabd21245d45c6975caeb24',
                                16944,
                                '100644'),
 'docs/proposed-release-readiness.md': ('0637320be0e65f8c693ff3e7c5e9ac59985598ce42be8324e08e48db2c455379',
                                        4837,
                                        '100644'),
 'docs/provenance-integration-verification.md': ('1155cf6ea90d80571ff06fd3dcc0002667b6837176b0aa43b57dc63d12cb6590',
                                                 6148,
                                                 '100644'),
 'docs/readonly-artifacts-verification.md': ('38ff65dc5ba1e9fbbe24b9dab56a8757485a895fb73bad0aef0f3404c14d5ecb',
                                             2559,
                                             '100644'),
 'docs/release-checklist.md': ('7b554d1243163c421fb9a797ebb10ed1ea73bd24a2362dcf3af7ddc35d48010a',
                               11761,
                               '100644'),
 'docs/release-inventory/v0.3.0a3/README.md': ('bee01b9bb465413b52fa9a605e7d418f671a5e07befe1e2fc7bc7125eb6e7ee6',
                                               7993,
                                               '100644'),
 'docs/release-inventory/v0.3.0a3/SHA256SUMS': ('96916b3980920574d91e116f09fe7f189fe7791537b365423abd0f0744b1e883',
                                                1139,
                                                '100644'),
 'docs/release-inventory/v0.3.0a3/build_inventory.py': ('dc7b5d11f1bf40ec3bb7d3517320675e1fd3cb80d070305c37183c537cf70381',
                                                        34510,
                                                        '100644'),
 'docs/release-inventory/v0.3.0a3/component-inventory.json': ('0f65712d1fe8ec6b9392ae0957d2fa39450ccf7de508e8eb13a36a0c7a25f434',
                                                              307191,
                                                              '100644'),
 'docs/release-inventory/v0.3.0a3/generation-result.json': ('2fe4039f75a97354ec0c003c6839b2c7e83649af0bb517f18de54107b4e2b8d3',
                                                            819,
                                                            '100644'),
 'docs/release-inventory/v0.3.0a3/hardening-review.json': ('a75bc8b57f8782082e336f5637a78b030c3f5f18a1a0cef450361da7c4a53107',
                                                           1898,
                                                           '100644'),
 'docs/release-inventory/v0.3.0a3/hardening.patch': ('46777d7e9fc8d5aaca7a47818687f9a7ab7a8099680cd9e623933b184e1cefd8',
                                                     10104,
                                                     '100644'),
 'docs/release-inventory/v0.3.0a3/temporal-rust-lock-inventory.json': ('4c1b7aae20e991a2ecf722afe3f21aa27f3df709395fb5e5317c71bfbf548827',
                                                                       99468,
                                                                       '100644'),
 'docs/release-inventory/v0.3.0a3/test-details.txt': ('d9afc1d4f5a34fbb7901af9155ea5ea40063ba799a9e4f96966e5cd04e95b851',
                                                      1746,
                                                      '100644'),
 'docs/release-inventory/v0.3.0a3/test-result.json': ('0b2be3754450e282ea320d07ce9a2c2bdee98ea77e8c0e3a895641207e4166a3',
                                                      175,
                                                      '100644'),
 'docs/release-inventory/v0.3.0a3/test_inventory.py': ('ad17db749f445a60e4290e55c31b7e8c044c789669471af2c355e4b782462b9c',
                                                       10847,
                                                       '100644'),
 'docs/release-inventory/v0.3.0a3/upstream-license-evidence.json': ('c244f272e6bb9c6e92c8a6937bf80ba2a7033368afd54c4a74669a2e8e202e61',
                                                                    5864,
                                                                    '100644'),
 'docs/release-inventory/v0.3.0a3/validation-results.json': ('6b12c93f283058f9022d987cd074bdd4495f471537073404bf307ca7fb51ba52',
                                                             3086,
                                                             '100644'),
 'docs/release-inventory/v0.3.0a3/verification-result.json': ('e7cd67d120f6439aba7cf70e690e69dcb9cce5ec22b725504a1442060ab54938',
                                                              817,
                                                              '100644'),
 'docs/research/README.md': ('a0f62e2b04f51eabc028b2f5bc25c4d798bfdaf11b4a1a77caf925f0c9204359',
                             4501,
                             '100644'),
 'docs/research/academic-needs.md': ('32c4265723aa88e95d1e5bfd5567174c2f1d69ee3fd70ba2fba46c61d355e9cb',
                                     3621,
                                     '100644'),
 'docs/research/delta-20261002/README.md': ('09a6f746b9f50a102f7b055fe9872febea1c5d03c7c4fa5996e713f1157964ee',
                                            11688,
                                            '100644'),
 'docs/research/delta-20261002/source-needs-delta.json': ('fcccb1cbec6d74e7bb40cd8a191dc69dd37a5b100569075895f9183d07bdfed7',
                                                          32979,
                                                          '100644'),
 'docs/research/demand-gap-20261001/README.md': ('f42e2b24ca85d4bc204f8b944a6f05419aac0a0b19d2cace56a0c4ce13383b22',
                                                 2975,
                                                 '100644'),
 'docs/research/demand-gap-20261001/README.zh-CN.md': ('bb8d860522d706cd539aad193bb95facc2a864b179a7f89ecc88a49e97b2901c',
                                                       7091,
                                                       '100644'),
 'docs/research/demand-gap-20261001/acceptance-cases.json': ('5a581f3a9e3d6e9a92e3cd95bb95692fa253aa6305d5163a022e3ef23562a4da',
                                                             5273,
                                                             '100644'),
 'docs/research/demand-gap-20261001/source-needs-delta.json': ('f6b274298df5e150c7a277e8e4ff554b5feea1dffbf832c5d400048e4217d932',
                                                               9653,
                                                               '100644'),
 'docs/research/hillhouse-delta-20261002/README.md': ('1ad79d0c68a99190878f9785de88a0b1d49ee9d5aab34cd1b6d8f892ea10d6c8',
                                                      4605,
                                                      '100644'),
 'docs/research/hillhouse-delta-20261002/source-needs-delta.json': ('3490040def92021a3bea55bb6a6d6449818f57dd2eb7581bb0049d9802659be4',
                                                                    6714,
                                                                    '100644'),
 'docs/research/hillhouse-industry.md': ('8ef3b5b8418d5897f3e651e1e5a37a1335ae5482b0897856f49daedeeb2faa74',
                                         3557,
                                         '100644'),
 'docs/research/hillhouse-primary-addendum.zh-CN.md': ('be16381bffdf7a78f94226fbf2de8d53307a3ec6102c391d73dac8c5dff7de80',
                                                       7676,
                                                       '100644'),
 'docs/research/industry-cases.md': ('144009ede34e5028d7039c7061a0f19453ca92b99bebf195dfa9db58763a9fd7',
                                     10245,
                                     '100644'),
 'docs/research/interoperability-delta-20261002/README.md': ('9b752f268faa35f05ade3ac8a49d4058213b91b6c651ce0c445805dd59fe9283',
                                                             8533,
                                                             '100644'),
 'docs/research/interoperability-delta-20261002/source-needs-delta.json': ('44a462109f858167850beb480e9395299c7f234ac8196d2aa681ed091ca76ad3',
                                                                           21086,
                                                                           '100644'),
 'docs/research/lidang.md': ('18e6211d65ba65f8da36fe7ee4bd599495800afd576fea9d84eea5a14e402d3c',
                             10707,
                             '100644'),
 'docs/research/official-strategy.md': ('eba63f5ced64624d007a54ec860accfe34af445077232ed2fece155d590fe737',
                                        13163,
                                        '100644'),
 'docs/research/oss-workflows/BENCHMARK.md': ('579334d0aa8faadaf6a058df710792f26c051161f1996bcb05a2e6d3b1d443f9',
                                              8214,
                                              '100644'),
 'docs/research/oss-workflows/INDEPENDENT-REVIEW.md': ('92f38dff6e93e254a2865f992dd9eb9f3c9d71d2bb2a0490a512c887c26ddfc4',
                                                       4241,
                                                       '100644'),
 'docs/research/oss-workflows/PRIMARY-SOURCES.md': ('4a5bfe359f4565f48d51ecf7125d61609bcaab0da2d574f50de2f1a4d96ab867',
                                                    4203,
                                                    '100644'),
 'docs/research/oss-workflows/PROJECTION.json': ('f75f94e0a8279eb0b7c751b12d1af18ae03cbf88790b0ba66f898d92960ece67',
                                                 1583,
                                                 '100644'),
 'docs/research/oss-workflows/README.md': ('f6b0e5b52b41cb5a926a8577f66f31125571e6472088bbd3885d561a8cf16a2f',
                                           3018,
                                           '100644'),
 'docs/research/oss-workflows/SHA256SUMS': ('dcf60026a6b0cee6059106420debdb558522cec2db659a7650885de6873e2481',
                                            1243,
                                            '100644'),
 'docs/research/oss-workflows/TICKETS.md': ('711600a48ad2d4830c390e3247e0a216eea0af2d221259b0d377cd55285b45d5',
                                            8064,
                                            '100644'),
 'docs/research/oss-workflows/VALIDATION.json': ('5d18d71fa8785d40de6a2db0f3d9204b9654131eb42bb75edee16e9ac9be376b',
                                                 826,
                                                 '100644'),
 'docs/research/oss-workflows/WORKFLOW-SPEC.md': ('165f5bcfa055e01ff6bc7c692013060b4bf1c2d91564f86e6adf91c8e97a3523',
                                                  7232,
                                                  '100644'),
 'docs/research/oss-workflows/evidence/repository-snapshot.json': ('c62250df3791aa5f48c8502c4e4b8ae6d0158f54864d9ef43a9b3f49000b01af',
                                                                   6957,
                                                                   '100644'),
 'docs/research/oss-workflows/evidence/source-needs-additions.json': ('c0de38a1543f3a8a477ae299c13a614ac837561587e7abfe87105c9aa86483d7',
                                                                      3483,
                                                                      '100644'),
 'docs/research/oss-workflows/frozen-oracle/SHA256SUMS': ('9c127f2f8ac08e5331d8aa1aa15e95c5ba8dbb5ab657c661ed7d4ed0e32732bd',
                                                          255,
                                                          '100644'),
 'docs/research/oss-workflows/frozen-oracle/case-oracles.json': ('2b17507cc2ef6e7861c8fbad90cf611dccccf64b828537dc09cb6b6b0a2731ed',
                                                                 2572,
                                                                 '100644'),
 'docs/research/oss-workflows/frozen-oracle/expected-summary.json': ('4df81c0c33cd274af97197d6d9eb2d3e05c63579e026eb41b2ef8718d41d63e5',
                                                                     238,
                                                                     '100644'),
 'docs/research/oss-workflows/frozen-oracle/measurements.csv': ('12fa76e2cb8defb752ce08a2fdd386b0f943579d1438e3022cb2e345bdcae0d9',
                                                                85,
                                                                '100644'),
 'docs/research/refresh-20261001/README.zh-CN.md': ('28ad58d64aaf5d81a1ef54470f6931eb28f0b6d21239bb065dbcd69633fb68bd',
                                                    4298,
                                                    '100644'),
 'docs/research/refresh-20261001/manifest.json': ('9f5edda686ab27d4a4c688109b03ca3173653cb152bf136d30acc2c479fb8056',
                                                  428,
                                                  '100644'),
 'docs/research/refresh-20261001/source-needs-delta.json': ('75adc941dab8a7a0c0134aba25d330915ad2f302df7adc29bcc11c9541dbabe9',
                                                            16749,
                                                            '100644'),
 'docs/research/scaling-literature-20261002/README.md': ('01c560a4c3d189b98768e89e7d853ba74e388e23f982d676953fe7b6effb0c66',
                                                         11286,
                                                         '100644'),
 'docs/research/scaling-literature-20261002/evidence.json': ('ac26911ec0b1cba021f38edbaf0ea591fc162f00a67a87248d99b32e7ab51fc8',
                                                             9470,
                                                             '100644'),
 'docs/research/sequoia-hongshan.md': ('1f1669f008a276b98e4d54e34ef276386cb096fca986f58970f9c74e68013518',
                                       6276,
                                       '100644'),
 'docs/research/source-needs-index.json': ('05cdaf2a1dbd50edb890c4455c8e371b14ba49741bf9292a98e1ad72a83b183b',
                                           55273,
                                           '100644'),
 'docs/simulated-lab.md': ('2abde03a46304cb79bb5dd7cda3b506ab57ea5d5f7eb573527c911a48e5cdecd',
                           11595,
                           '100644'),
 'docs/solver-cpu-ceiling.md': ('bee1d59d0d9571622662512bf63501aacb305b51eb54dbdebbc63077eeb46916',
                                3721,
                                '100644'),
 'docs/solver-version-gate.md': ('eb6c2d39b0748e58f94ca1011d2d6b78848dc274b31b0b8558b38371d108e7d8',
                                 1444,
                                 '100644'),
 'docs/source-admission-verification.md': ('0674d59713129285200595647c3774c827f0eba14f1475b5fcd4864117d4bb9c',
                                           3909,
                                           '100644'),
 'docs/source-admission.md': ('2b0da8769bc47bf042c063596b166a6f2c94361d3da1a6809b080ef306c0ff17',
                              4982,
                              '100644'),
 'docs/source-lock-schema.md': ('43f04b7d01a3452476555733b8b38984f85f8cc74d40db8de1ea28f263281aa9',
                                3513,
                                '100644'),
 'docs/source-provenance-inventory.md': ('1777fc135a584651958183e477ed7a4a4f5a797597072953ed28437dad72f424',
                                         9859,
                                         '100644'),
 'docs/structural-beam.md': ('f8172c935abd8d9c4e02bde14024c92e9a4fd8ad094026eaba6804306bd475aa',
                             11783,
                             '100644'),
 'docs/structural-default-v2.md': ('c4c28ead2f159d3be5fd186669a90831b2bdb752c692edd49e85f1050f5bfd7d',
                                   7258,
                                   '100644'),
 'docs/structural-elastic-energy.md': ('02c713e4b72f060f54c4f8e648527aaad1377ba493926c7eb1495c28820143d5',
                                       9173,
                                       '100644'),
 'docs/structural-v2-candidate-verification.md': ('c59e9fefb70410f6d9b45e45bfaac97d0ecea2383e32860a1d854ffd68286180',
                                                  7332,
                                                  '100644'),
 'docs/synthetic-lab-qualification.md': ('6da580f7bbb82503bcdd677f354f741b72f508e4cfe00f55a166fba8726d1217',
                                         6390,
                                         '100644'),
 'docs/temporal-batch-qualification.md': ('aff9ca328dfc97fe631ddfaf2e5258d289a2af5f441a84e1851ef150c5dc7a13',
                                          32084,
                                          '100644'),
 'docs/temporal-qualification-evidence.md': ('345bf3b682accfdb2f7936f08f71b342e881e967816cea22e46c16c220ebc2ee',
                                             8928,
                                             '100644'),
 'docs/temporal-reference-failure-matrix.md': ('a0b6a92abb09009266ce18dddbe1168d8892ed37d0317ad451dbf44d522fb95e',
                                               13344,
                                               '100644'),
 'docs/temporal-reference-transport.md': ('e55c1104dfeab40f374dc35cf3c907c86d4f4ed1410722ad3b4e802c8e7b96e8',
                                          16392,
                                          '100644'),
 'docs/thermal-conduction.md': ('2a8d9d0867bf341d545c6bddefbff9a5379c2a1dbaf3477e439508794bc8610d',
                                9490,
                                '100644'),
 'docs/thermal-source.md': ('1ef95be7706ee3503937dc03f14a043b1751f89da4d03c1612e3ec97807ac903',
                            6641,
                            '100644'),
 'docs/verification-status.md': ('3dccd0f8354d09cc8167b90040e7c11eab0063b63ad8cbe43a26cb969707d8d0',
                                 10836,
                                 '100644'),
 'docs/verifier-ci-verification.md': ('6059921dccfe90bbc499cbb00e8cea0d7382ce1eca5255fb8ade49c81e52d54a',
                                      4041,
                                      '100644'),
 'examples/agent-contracts/README.md': ('ed71cb85d0042848b77fe1c865abebf1db33d198b6765c33d0cc4f05a32fdb98',
                                        1407,
                                        '100644'),
 'examples/agent-contracts/demo.py': ('df9da208f39a1c8f55eaf6265024d3f6164dbb23611a3e13d745e4bbbcbff700',
                                      1331,
                                      '100644'),
 'examples/cad_cae/README.md': ('c6ba7614fc95a47767dbed82f9272843be41c83a07e8edf46ef68b9c39527bf3',
                                9352,
                                '100644'),
 'examples/cad_cae/README.zh-CN.md': ('b7725054bfb8e26ca3ba80806f80613cc32a9c12b8613f0fe09f338ed95fa773',
                                      6712,
                                      '100644'),
 'examples/cad_cae/beam.parameters.json': ('6c9292925a217698a004c07cff631018f53cbbd4b8cc171e703ed4b95dc15817',
                                           65,
                                           '100644'),
 'examples/cad_cae/mesh-beam.json': ('a9c919ca82cdb09d696886805528b536fd53c5e09b042634925b87ae5f8d26cb',
                                     365,
                                     '100644'),
 'examples/cad_cae/native-geometry-reference/README.md': ('d951920e159fce4800dc33c91a5f7de5b948a8e13a78e60c2948b8bcde54da79',
                                                          6343,
                                                          '100644'),
 'examples/cad_cae/native-geometry-reference/beam.step': ('6a58ae02b21d6f3c70505398c86193f7f3de4d4bbd20c36267400eeb08fa2ec9',
                                                          15366,
                                                          '100644'),
 'examples/cad_cae/native-geometry-reference/evidence.json': ('345e2a9ad27e786fd82f0339a974bfbe3e58854e65da45b083112ca25672a232',
                                                              4569,
                                                              '100644'),
 'examples/cad_cae/requirements-tested.txt': ('3666768a86346a91776a20c888ab4c2cf8a9f48ddcd0097ef294d81d04a7ad92',
                                              617,
                                              '100644'),
 'examples/cad_cae/thermal-benchmark.json': ('15a9f25950e08311404cb8019ccc465a90e8a9b81cbacd19cd2a36e19eaede9e',
                                             550,
                                             '100644'),
 'examples/cad_cae/thermal_workflow.py': ('90c13e6c9cbf0932be2383fe87c351b9bf1a0c7e546c9ea215c7f4e2ba084e75',
                                          10682,
                                          '100644'),
 'examples/callable-artifacts/README.md': ('4fbf9a5467f234ffae39c0ddbf2915aab9ea22eb3fa9ecdc3bc938213546efdd',
                                           2229,
                                           '100644'),
 'examples/callable-artifacts/demo.py': ('5796099bec60bb4cf9a3c46fce5b74c8ddf068572fecb7237e41a27df49b00d8',
                                         4898,
                                         '100644'),
 'examples/callable-execution/README.md': ('038348900b2321013a8fe6774b7314693a84769fba48731e4fe72e0859251953',
                                           668,
                                           '100644'),
 'examples/callable-execution/demo.py': ('1cccad24fa11854ac1c62fa3e500735518e438cc2368776738dc41a17c68dca2',
                                         3265,
                                         '100644'),
 'examples/canonical-artifacts/README.md': ('fb949cab9bac00427a661e6105f5e46cdf159a9f7a7af9aa8c118c24fab1c0d1',
                                            1671,
                                            '100644'),
 'examples/canonical-artifacts/roundtrip.py': ('3f6e4f3a974df5b002a3e0cff034caf5c87d67c5c815a916ba5275d15a4f45ed',
                                               3266,
                                               '100644'),
 'examples/git-workspaces/README.md': ('fddbdb326a73341a8b2fac399231d38784c838fe57986993b4cc608864e3e76b',
                                       1026,
                                       '100644'),
 'examples/git-workspaces/demo.py': ('ea127099f339f98d8d045f94c0e1c8263b6e014834146e61638f871c6244a1bc',
                                     3263,
                                     '100644'),
 'examples/lab-qualification/fixture.json': ('791516f90df6c8b004e02706752114f6628911396756ac86f6c19258a037f979',
                                             9261,
                                             '100644'),
 'examples/lab-qualification/manifest.json': ('1dcde9c63280f4f99e6c2ea9e3ca6d392399e4d0792a4a9e4f81d581d2ce817f',
                                              334,
                                              '100644'),
 'examples/measurement-review/README.md': ('4d8c62344f77fc82b64ce2c7fb65dcbb2f6c37100d3a5c2cdf38870fc3775362',
                                           21979,
                                           '100644'),
 'examples/measurement-review/README.zh-CN.md': ('07f49180f18df93bd74a9a7b490f324d1dfabcc9b0c935bdc3acb6446f56c1d6',
                                                 20029,
                                                 '100644'),
 'examples/measurement-review/batch.csv': ('12fa76e2cb8defb752ce08a2fdd386b0f943579d1438e3022cb2e345bdcae0d9',
                                           85,
                                           '100644'),
 'examples/measurement-review/compare.py': ('d5b3e28ca4f1b9eadd7454e58bde55f17979644d76b0a64f7d668d8b5812d67d',
                                            38615,
                                            '100644'),
 'examples/measurement-review/comparison-fixtures.json': ('dd72773f56886888be00c7f5a2c8ec461eb3f9e0eb984043bf20fdd5191cb1cd',
                                                          5404,
                                                          '100644'),
 'examples/measurement-review/demo.py': ('8a363374fc05cf9fd93314c8814729e29653d0a997a22c74f652842e37904624',
                                         9826,
                                         '100644'),
 'examples/measurement-review/utility_report.py': ('2ca99647c134f38c81fe24f726a4de48b7813ecbe008e573d0ce4131f6586594',
                                                   23608,
                                                   '100644'),
 'examples/simulated-lab/requirements-tested.txt': ('21c0631d58011d1b254ceba5bd866d859a1d013c2388b3e25b11c03978dcd2d9',
                                                    475,
                                                    '100644'),
 'examples/source-audit/manifest.json': ('f4d81f12c83b7f222931348677b01b6f27df8905513cfbaebac3cf86cbfe26ae',
                                         1000,
                                         '100644'),
 'examples/source-audit/sources/synthetic.json': ('d65f012d4b80a52bf3fdb01c19e4efecd0e5ec09df5854659b6d3e3767ebe781',
                                                  801,
                                                  '100644'),
 'examples/source-boundary/README.md': ('6ae832448f6b8f4b8c29ac5b0ab74de193e49f1fd152e830c0e4b503bf3e68aa',
                                        9510,
                                        '100644'),
 'examples/source-boundary/demo.py': ('fe70a4cfacbba3a69dd8f340057d5bb4a1486f3c2a470b853250008151601be1',
                                      18618,
                                      '100644'),
 'examples/source-boundary/parameter-fixtures.json': ('c163f3137817657efc344d362885a77d13264c0276b533253c287cb42c9497f3',
                                                      4113,
                                                      '100644'),
 'examples/source-boundary/proposals.json': ('5a581f3a9e3d6e9a92e3cd95bb95692fa253aa6305d5163a022e3ef23562a4da',
                                             5273,
                                             '100644'),
 'pyproject.toml': ('513e56fba610621e34ea8d850dbc46ad60ebbbae230ccc0d28056f693c65c5a5', 597, '100644'),
 'src/opendot_engineering/__init__.py': ('220b0324cfb1c2ba39d190a7857a850dae59dfce2cd5064028007ccb3dc6771d',
                                         108,
                                         '100644'),
 'src/opendot_engineering/__main__.py': ('d4b66a08d3ddf2fe00027dd0cd6caa2f5e360432e813a634bc00182271f183a3',
                                         3346,
                                         '100644'),
 'src/opendot_engineering/adapters/__init__.py': ('8c1b8c19884c2204c3ac30d898a48785e54a1694a59319be4b8bb7dd1619bd1b',
                                                  75,
                                                  '100644'),
 'src/opendot_engineering/adapters/_simulated_lab_worker.py': ('cf3c9f95f5cfcc7835483214fab7dc4da0e4634ee108c28301c674d5dddca4f4',
                                                               3155,
                                                               '100644'),
 'src/opendot_engineering/adapters/a2a_http_transport.py': ('abf6599baf3823991d88844d013a145a747b4e646b1db398a4f35ee90a2cbfc5',
                                                            9366,
                                                            '100644'),
 'src/opendot_engineering/adapters/a2a_worker_turn.py': ('ed6c2399da397850c608cd1bbec985553bd8364c3a2162cfa6f81754f9c4a4d9',
                                                         18709,
                                                         '100644'),
 'src/opendot_engineering/adapters/lab_qualification.py': ('a04bfcb78ee8aaef6af16bf3e387d8dcf13a80938895e71437af033388a22b9d',
                                                           12766,
                                                           '100644'),
 'src/opendot_engineering/adapters/simulated_lab.py': ('7f65a2fa0c1e8cc710cd13e62f5af7797d5f1953db5eb824a3a9e12e59f16fd2',
                                                       16738,
                                                       '100644'),
 'src/opendot_engineering/adapters/source_admission.py': ('829bbbb039cfac63d16ff06ae1f84f1e1c34240521728295585590f91d54b0a1',
                                                          10628,
                                                          '100644'),
 'src/opendot_engineering/adapters/source_audit.py': ('c94737305b1e5a80453541ce890bde4fcb700a0074e32344fe839b237374bfa7',
                                                      12998,
                                                      '100644'),
 'src/opendot_engineering/adapters/temporal_activity.py': ('3e084d5432c11d031385472b9eba32e1d62f06d4aa45e08acebd88bd803045f2',
                                                           41070,
                                                           '100644'),
 'src/opendot_engineering/adapters/temporal_workflow.py': ('a1723c70ccd8e440475ff0c359a5dfb1fa6e41ad2dff9881d2727879231434ac',
                                                           37598,
                                                           '100644'),
 'src/opendot_engineering/core/__init__.py': ('9224d4f77ea27f42ec63a05a490eae38aa51076ddc81aa8e0a486e7a36a71f5a',
                                              390,
                                              '100644'),
 'src/opendot_engineering/core/artifacts.py': ('4606b7b11a81044267b30fee332d9b6fd6540d862726a9579655ee27c7d9a883',
                                               9255,
                                               '100644'),
 'src/opendot_engineering/core/contracts.py': ('9462415baf84668825ad2c8cfc3f4f3df68332f65d1f1f4b301fbf01cf8537ca',
                                               3771,
                                               '100644'),
 'src/opendot_engineering/executors/_gmsh_worker.py': ('a478f69b2c7a3e5b36aaf754e07bb4dbbbe83a91d3423e305f3619e1397ab746',
                                                       8113,
                                                       '100644'),
 'src/opendot_engineering/executors/geometry.py': ('96e3626b68b86c21547cb930bba1591de7270f9bcffc3cdadfa0a9b9ac7a5edb',
                                                   21462,
                                                   '100644'),
 'src/opendot_engineering/executors/gmsh_mesh.py': ('5890ee43c71fdbbfe2a01e72548a9c0a6da78c09584428399011d5971df2d31f',
                                                    22676,
                                                    '100644'),
 'src/opendot_engineering/executors/structural_beam.py': ('0484f455d3991984a2e3187e8a2412af445f3dbd0b0473ba93e4ffe2f46cc47e',
                                                          34841,
                                                          '100644'),
 'src/opendot_engineering/executors/thermal_conduction.py': ('f5f8daf73d6d2aa662b84416da82356077bf9c1c4652f9c785febe890b4e48d4',
                                                             24794,
                                                             '100644'),
 'src/opendot_engineering/executors/thermal_source.py': ('44f0b06075f41e5346598794b932900d123105e4b36e8e6824b85671be2fd629',
                                                         14519,
                                                         '100644'),
 'src/opendot_engineering/git_workspace.py': ('02b4dff4d9382bcaf00df655f376799658d59482c017822458d3c6f9049b6ecc',
                                              21525,
                                              '100644'),
 'src/opendot_engineering/tool_runtime.py': ('7c5011e02b2cf07e5f15ad7854905ce0738271e167b873bad9256a8ed169199c',
                                             29040,
                                             '100644'),
 'templates/change-request.md': ('60fd80dd2043a339d973e3e25980f726b4bc3ee8caea5af72aee30fc1e613b73',
                                 1334,
                                 '100644'),
 'templates/issue-report.md': ('98f3d3055c9130f59cf455f6a098a01429bf4f45405de960b20a0dc0fd33154e',
                               1201,
                               '100644'),
 'tests/acceptance/temporal_real_batch_gate.py': ('de107abe5edee5ded184709982585cc323ba1d89ea2a31717257b730b9936f58',
                                                  1941,
                                                  '100644'),
 'tests/acceptance/temporal_server_gate.py': ('5167765cba580fb0e5bc0c1af77239e24c52b87c4c235443174b0aa33771273d',
                                              4338,
                                              '100644'),
 'tests/fixtures/a2a_worker_turn_v1.json': ('186974f72da383b35d0bb47de2163e3611b5612348140accfc9da5f70d4745e3',
                                            13571,
                                            '100644'),
 'tests/test_a2a_http_transport.py': ('687a6692eee9f8765797a458412b241b7603000f029eea0fe9bac89f28724282',
                                      36105,
                                      '100644'),
 'tests/test_adapter_provenance.py': ('7582d066504bdd08bdc7ca7984d59be3845b002bfd4c030eeaca1d9da5a13745',
                                      15905,
                                      '100644'),
 'tests/test_agent_contracts.py': ('e69f601e99ddd8988a1c60f5c4dcaffb9ed4412caa91269155f31ea24604ff3f',
                                   8511,
                                   '100644'),
 'tests/test_bounded_artifact_reads.py': ('32085875a7783af30586f4118a23fc00b94c380d194db815027417f1e73784d2',
                                          10836,
                                          '100644'),
 'tests/test_cad_thermal_workflow.py': ('6561e4055673e48e5e4e1d3dd66e20d9a2a9ec76f3b8886d3b0130273c9da533',
                                        15633,
                                        '100644'),
 'tests/test_callable_artifacts.py': ('601ff8a6fe09e44dc7ab7ab61b693b187de556a56815cab575c77560b6c1c4b0',
                                      4026,
                                      '100644'),
 'tests/test_callable_cleanup_regressions.py': ('5b542f9b305e75e41346bd73d8222bc54c0044529f63542d8fcede148fa924e2',
                                                3930,
                                                '100644'),
 'tests/test_callable_contracts.py': ('6fdf0a1b5901b8e8df8e7f7f634d658465c2f066e888c2380c460076a4167555',
                                      4023,
                                      '100644'),
 'tests/test_callable_independent_regressions.py': ('111247a14dd3c9c1d63ed047153cf9bc68a1c49e5f2cf059d263330bb63e113f',
                                                    15287,
                                                    '100644'),
 'tests/test_callable_profile.py': ('484b0e69cd9c0ea2d99333466f23e6a766e7a969cc921d993a1ef3ab8f99a8c7',
                                    40945,
                                    '100644'),
 'tests/test_callable_repaired_edges.py': ('0958d2a3cd5962bd7d89644051c790391d4d0dd4984486a5bc476c3cecacaee1',
                                           5892,
                                           '100644'),
 'tests/test_canonical_artifacts.py': ('87d28c4156badb30f0dedde193a1db206d762c32d3b4bbbcac9681d62aab33f8',
                                       11547,
                                       '100644'),
 'tests/test_ci_summary.py': ('de3852980fe94432ec63682da3d98450643e97688bcfa8de888033882a815e98',
                              902,
                              '100644'),
 'tests/test_ci_toolchain_lock.py': ('fe45a895d6896ea1da0cc0e05eea1fa63d2a7d409634558097faaa99155f8067',
                                     4340,
                                     '100644'),
 'tests/test_demo_output_errors.py': ('84c328678d60599531f3141fa6c2043761bab93957ed7a1eabea02f8f1b1113c',
                                      6818,
                                      '100644'),
 'tests/test_documentation_checks.py': ('eb904e0b802e0229bfb16e8f7e8ef8f545401846ca0e0ddf3b0716668dd6dbfd',
                                        16280,
                                        '100644'),
 'tests/test_geometry.py': ('7b55725c88edab1195aca61db224ab3a14996bdbde3634493f7fdc9eee9b540a',
                            8968,
                            '100644'),
 'tests/test_git_workspace.py': ('8377aa2c2085e94d8fb2ad4fb5e2dced081e2c4a876ccdb56eed898599307c85',
                                 25711,
                                 '100644'),
 'tests/test_gmsh_cpu_ceiling.py': ('49532240cc2529c31c5b195fb869315bfb33600df6c662b302477f2160cc93d9',
                                    13705,
                                    '100644'),
 'tests/test_gmsh_mesh.py': ('2dbe346af12cc9f4d18332cec6788585012a1692cb51de7797d3e3fce72a406f',
                             18968,
                             '100644'),
 'tests/test_incremental_utility_report.py': ('1da380d0075e388d0811d05864c2a22e58a7c8834298ebba3c5fb77f726ab424',
                                              23711,
                                              '100644'),
 'tests/test_lab_qualification.py': ('f180d4338368140eda55fed5ca2f3a8d0e2d7d1fe0f7736fe9db03585086e5df',
                                     14620,
                                     '100644'),
 'tests/test_measurement_comparison_example.py': ('2e7cad23db2d1f2f1304f2a563f5f6b293fecedd991fb64f7d12e4e425c93056',
                                                  18864,
                                                  '100644'),
 'tests/test_measurement_review_example.py': ('49eda9fde532db40a1d0cdc2c5d17ee9b62758a221938a0ceb003329864c84bb',
                                              6261,
                                              '100644'),
 'tests/test_module_cli.py': ('0781b2a84e414e16e88f980bb1962c18f4d3fa83713cc4d114cf491c7d1022c6',
                              6748,
                              '100644'),
 'tests/test_readonly_artifacts.py': ('da4556c425844ebd84083df14fe902ec9aa227f1ccf12f721eadcda2be0f62eb',
                                      11071,
                                      '100644'),
 'tests/test_research_index.py': ('6c4db38b2d35822c7401693adb47be440ee247c106094bc5ac37752e4a31f6b5',
                                  14210,
                                  '100644'),
 'tests/test_simulated_lab.py': ('c9f209d57e4a68eb3f9ed1023f0a596220327f9fea5708e3d8e306fb9a365fe9',
                                 17430,
                                 '100644'),
 'tests/test_solver_cpu_ceiling.py': ('7d5b628196bea01ce003a528de76b6470cfbde72709fc3758e143a678db1fa4b',
                                      6918,
                                      '100644'),
 'tests/test_solver_version_identity.py': ('adae18121e560ea965ceb0d676e04a059c2d8c4d916a57776a2a03f2fcdaae41',
                                           16188,
                                           '100644'),
 'tests/test_source_admission.py': ('cf87dfe5e98457087a52019dbea5a1e3042e9c643f06af9543af3b78fe45c3f6',
                                    16313,
                                    '100644'),
 'tests/test_source_audit.py': ('1ac4a7675568a7905b7f54296c20ce8b6d167e96fcbfa2bed99ac58568592adb',
                                12251,
                                '100644'),
 'tests/test_source_boundary_example.py': ('c37ab1b2857789e4d0572bdaf381eaad6f8d60a39d6b8487e29cacd44f9901fe',
                                           10472,
                                           '100644'),
 'tests/test_source_conflict_example.py': ('2cd0d670307c7ddd61a76f7b421b460a9e42987f9a8e5124065e86357f4d37df',
                                           8485,
                                           '100644'),
 'tests/test_source_provenance.py': ('715627867b1dba7f023b733d47770867b110393b97ec7c2e8c8ca6cb7a97da9c',
                                     20683,
                                     '100644'),
 'tests/test_structural_beam.py': ('893be8bb72c6da3f0346b3a04359584453fdab4c95bf9fff2aa2b7b1fa21d296',
                                   12120,
                                   '100644'),
 'tests/test_structural_default_v2.py': ('c63fe2f6d55cd4d66210ab8956f0abdde8a6333b08dca2759efd0c84919851ec',
                                         13985,
                                         '100644'),
 'tests/test_structural_elastic_energy.py': ('d96575cca83c830d430cf2025984d3b24cf2163171eddf052d94c2290c61e9c2',
                                             11118,
                                             '100644'),
 'tests/test_temporal_activity_contract.py': ('d721482e11aba8c4b1128bcb7ce453d94404f60aec7d6080b00eb2b91ced1ca0',
                                              26064,
                                              '100644'),
 'tests/test_temporal_cli_acquisition.py': ('a94e0125dcc9c43087b79da790a1dc56e62e755b21c66b64d1b7ae95ea63e1aa',
                                            34546,
                                            '100644'),
 'tests/test_temporal_dag_recovery.py': ('848430ec2840fb988a908927fd1279b021a408718b406f8206b377f8b3245249',
                                         99923,
                                         '100644'),
 'tests/test_temporal_transport_owner_boundaries.py': ('7764555cd343c11d28e10891e780bbed7afca8758a738216459019b66981a2c4',
                                                       13128,
                                                       '100644'),
 'tests/test_temporal_workflow_contract.py': ('2c0a531681d68d8bc9c9e896e89b98c76c72c6988da579c3c7e223f80dcce5af',
                                              19288,
                                              '100644'),
 'tests/test_thermal_conduction.py': ('df63f2ab3045bfe7f5439205eb1225ca02c883c9d4cbaea9ed993a65cd0add5b',
                                      8880,
                                      '100644'),
 'tests/test_thermal_source.py': ('d15266ca09325e5cd4cae9b203b18e01ec1f31fa79752743bfb903597be4baab',
                                  10631,
                                  '100644')}

DAG2_PREFIX = 'opendot.temporal.dag2-gate.'
DAG2_PLAN = '19843079a5da00754ec1b5399962c33874b907eb4d0d6fcf55cd3be2f4dffb63'
DAG2_SEED = '897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02'
DAG2_REGISTRATION = '5f2b1e81954530f31c7d2c83b9c582883b8391190ebe13b69b8bf91f044cb0c3'
DAG2_INPUTS = {'A': DAG2_SEED, 'B': '6d23a7a66975efd35356848b1f69b848e99c3c76dc5a3740e35328d41c05440a'}
DAG2_OUTPUTS = {'A': 'ef2d127de37b942baad06145e54b0c619a1f22327b2ebbcfbec78f5564afe39d', 'B': 'e7f6c011776e8db7cd330b54174fd76f7d0216b612387a5ffcfb81e6f0919683'}
DAG2_MISSIONS = ('hosted-normal', 'hosted-reconcile', 'hosted-no-ref-cancel')
DAG2_SNAPSHOTS = ('normal-final', 'reconcile-unknown-before-stop', 'reconcile-unknown-after-replacement', 'reconcile-update-queued', 'reconcile-final', 'no-ref-unknown', 'no-ref-cancel-final')
# Independently reviewed workflow bytes and fresh shared collection, frozen for this source candidate.
DAG2_REVIEWED_WORKFLOW_SHA256 = 'e5b80d0623c8628c8918a8a230fa2c1694fc667b12b96785f26500a859de64a7'
DAG2_REVIEWED_SHARED_RECEIPT = {'expected_node_count': 1851, 'collection_sha256': '32626f40c398b3bf58e91d6460615875283f7885b350892619b2936eb6e59c7b'}
DAG2_DAG_RECEIPT = {'expected_node_count': 314, 'collection_sha256': 'a605f5855ee77b508f236c0ba1356c90442c0bfb1fd082ae64e315c5975d2c6e'}
DAG2_CODES = frozenset(DAG2_SCHEMAS['failure']['properties']['code']['enum'])
CODES = CODES | DAG2_CODES


def _d2_fail(code, boundary='record_validation'):
    error = GateError(code)
    error.boundary = boundary
    raise error


def _d2_require(condition, code='INVALID_VALUE', boundary='record_validation'):
    if not condition:
        _d2_fail(code, boundary)


def _d2_equal(value, expected, code='INVALID_VALUE', boundary='record_validation'):
    # Python container equality conflates False/0 and integer/float leaves.
    # Evidence identity requires recursively identical plain types and values.
    _d2_require(type(value) is type(expected), code, boundary)
    if type(expected) is dict:
        _d2_require(all(type(k) is str for k in value) and value.keys() == expected.keys(), code, boundary)
        for key in expected:
            _d2_equal(value[key], expected[key], code, boundary)
    elif type(expected) in (list, tuple):
        _d2_require(len(value) == len(expected), code, boundary)
        for left, right in zip(value, expected):
            _d2_equal(left, right, code, boundary)
    else:
        _d2_require(value == expected, code, boundary)


def _d2_shape(value, keys, code='INVALID_SCHEMA'):
    keys = set(keys.split()) if type(keys) is str else set(keys)
    _d2_require(type(value) is dict and all(type(k) is str for k in value) and set(value) == keys, code)


def _d2_plain(value, depth=0):
    _d2_require(depth <= 64, 'SIZE_LIMIT')
    _d2_require(type(value) in (dict, list, str, int, float, bool, type(None)), 'INVALID_TYPE')
    if type(value) is dict:
        _d2_require(all(type(k) is str for k in value), 'INVALID_TYPE')
        for item in value.values():
            _d2_plain(item, depth + 1)
    elif type(value) is list:
        for item in value:
            _d2_plain(item, depth + 1)
    elif type(value) is float:
        _d2_require(math.isfinite(value), 'INVALID_TYPE')


def _d2_bytes(value, maximum=262144):
    _d2_plain(value)
    try:
        raw = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (ValueError, UnicodeError, RecursionError):
        _d2_fail('INVALID_JSON')
    _d2_require(len(raw) <= maximum, 'SIZE_LIMIT')
    return raw


def _d2_hash(value, maximum=262144):
    return hashlib.sha256(_d2_bytes(value, maximum)).hexdigest()


def _d2_schema(value, definition):
    if '$ref' in definition:
        return _d2_schema(value, DAG2_SCHEMAS[definition['$ref'].rsplit('/', 1)[1]])
    variants = definition.get('oneOf', definition.get('anyOf'))
    if variants is not None:
        accepted = 0
        for variant in variants:
            try:
                _d2_schema(value, variant)
                accepted += 1
            except GateError:
                pass
        _d2_require(accepted == 1 if 'oneOf' in definition else accepted > 0, 'INVALID_VALUE')
        return
    if 'const' in definition:
        expected = definition['const']
        _d2_require(type(value) is type(expected), 'INVALID_TYPE')
        _d2_equal(value, expected)
    if 'enum' in definition:
        _d2_require(any(type(value) is type(x) and value == x for x in definition['enum']), 'INVALID_VALUE')
    kind = definition.get('type')
    if kind is not None:
        kinds = {'object': dict, 'array': list, 'string': str, 'integer': int, 'boolean': bool, 'null': type(None)}
        _d2_require(kind in kinds and type(value) is kinds[kind], 'INVALID_TYPE')
    if kind == 'object':
        _d2_shape(value, definition['properties'])
        for key, item in value.items():
            _d2_schema(item, definition['properties'][key])
    elif kind == 'array':
        _d2_require(definition.get('minItems', 0) <= len(value) <= definition.get('maxItems', 4096), 'SIZE_LIMIT')
        for item in value:
            _d2_schema(item, definition['items'])
    elif kind == 'string':
        _d2_require(definition.get('minLength', 0) <= len(value) <= definition.get('maxLength', 1024), 'SIZE_LIMIT')
        if 'pattern' in definition:
            _d2_require(re.fullmatch(definition['pattern'], value) is not None, 'INVALID_VALUE')
    elif kind == 'integer':
        _d2_require(definition.get('minimum', 0) <= value <= definition.get('maximum', 10**18), 'INVALID_VALUE')


def dag2_validate_schema(value, definition_name):
    """Validate a sealed, closed plain-data schema; never authenticate origin."""
    _d2_require(type(definition_name) is str and definition_name in DAG2_SCHEMAS, 'INVALID_SCHEMA')
    _d2_plain(value)
    definition = DAG2_SCHEMAS[definition_name]
    if definition.get('type') == 'object':
        _d2_shape(value, definition['properties'])
    _d2_schema(value, definition)


def _d2_checked_schema(value, name, code):
    try:
        dag2_validate_schema(value, name)
    except GateError as error:
        if error.code == 'INVALID_TYPE':
            raise
        _d2_fail(code)


def _d2_reference(value, *, seed=False, effect=None, parent=None, code='RESULT_INVALID'):
    _d2_shape(value, DAG2_SCHEMAS['ref']['properties'])
    _d2_require(type(value['size_bytes']) is int, 'INVALID_TYPE')
    _d2_require(0 < value['size_bytes'] <= (256 if seed else 16384), 'SIZE_LIMIT')
    _d2_checked_schema(value, 'ref', code)
    h = value['sha256']
    _d2_equal(value['artifact_id'], 'sha256:' + h, code)
    _d2_equal(value['uri'], 'artifact://sha256/' + h, code)
    if seed:
        for key, expected in {'sha256': DAG2_SEED, 'size_bytes': 40, 'producer': 'opendot.temporal.dag-seed.v1', 'task_id': 'seed', 'source_refs': []}.items():
            _d2_equal(value[key], expected, code)
    else:
        _d2_equal(value['producer'], 'opendot.temporal.dag-result.v1', code)
        if effect is not None:
            _d2_equal(value['task_id'], effect[7:], code)
        if effect is not None:
            expected = ['sha256:' + DAG2_SEED] + ([] if parent is None else [parent['artifact_id']])
            _d2_equal(value['source_refs'], expected, code)
    return value


def _d2_workflow_id(mission):
    _d2_require(mission in DAG2_MISSIONS, 'RUN_BINDING')
    return 'opendot-dag2-' + mission + '-' + DAG2_PLAN


def _d2_effect(mission, node, parent=None):
    _d2_require(node in ('A', 'B'), 'RESULT_INVALID')
    return 'sha256:' + _d2_hash({'schema_version': 'opendot.effect.v1', 'namespace': 'default', 'workflow_id': _d2_workflow_id(mission), 'plan_sha256': DAG2_PLAN, 'node_id': node, 'parent_result_sha256': None if parent is None else parent['sha256']})


def _d2_bootstrap(context, mission, replacement=False):
    rows = context.get('bootstraps', [])
    rows = [r for r in rows if r.get('mission') == mission]
    _d2_require(rows, 'BOOTSTRAP_MISMATCH')
    return rows[-1] if replacement else rows[0]


def _d2_original_rows(context):
    value = context.get('originals', {})
    if type(value) is dict:
        value = value.get('originals', [row for key, row in value.items() if key != 'no_ref'])
    return value


def _d2_original_for(context, mission, node):
    matches = [r for r in _d2_original_rows(context) if r.get('mission') == mission and r.get('node') == node]
    _d2_require(len(matches) == 1, 'ORIGIN_MISMATCH')
    return matches[0]


def _d2_body(value, context):
    fields = 'schema_version profile mission_id node_id effect_id plan_sha256 namespace workflow_id workflow_run_id activity_id registration_sha256 seed_ref parent_result_ref input_payload_sha256 output receipt_report observation_provenance scientific_validity device_control_authority independent_review owner_integration'
    _d2_shape(value, fields, 'RESULT_INVALID')
    _d2_bytes(value, 16384)
    node, mission = value['node_id'], value['mission_id']
    _d2_require(type(node) is str and node in ('A', 'B') and type(mission) is str and mission in DAG2_MISSIONS[:2], 'RESULT_INVALID')
    # Semantic output and receipt checks precede reference-envelope consistency.
    _d2_equal(value['output'], 5 if node == 'A' else 6, 'RESULT_INVALID')
    receipt = value['receipt_report']
    _d2_shape(receipt, 'call_id tool_id tool_version status attempts latency_s input_hash output_hash semantic_valid error_type breaker_state execution_observation execution_liveness', 'RESULT_INVALID')
    fixed = {'tool_id': 'synthetic.bounded_sum', 'tool_version': '1', 'status': 'COMPLETED', 'attempts': 1, 'input_hash': DAG2_INPUTS[node], 'output_hash': DAG2_OUTPUTS[node], 'semantic_valid': True, 'error_type': None, 'breaker_state': 'closed', 'execution_liveness': {}}
    for key, expected in fixed.items():
        _d2_equal(receipt[key], expected, 'RESULT_INVALID')
    _d2_require(type(receipt['call_id']) is str and re.fullmatch('[0-9a-f]{24}', receipt['call_id']) is not None, 'RESULT_INVALID')
    _d2_require(type(receipt['latency_s']) in (int, float) and math.isfinite(receipt['latency_s']) and receipt['latency_s'] >= 0, 'RESULT_INVALID')
    obs = receipt['execution_observation']
    _d2_shape(obs, 'execution_id execution_kind dispatcher_pid worker_pid input_sha256 registration_sha256 review_target_sha256 read_only_declared', 'RESULT_INVALID')
    for key, expected in {'execution_kind': 'in_process', 'input_sha256': DAG2_INPUTS[node], 'registration_sha256': DAG2_REGISTRATION, 'review_target_sha256': None, 'read_only_declared': True}.items():
        _d2_equal(obs[key], expected, 'RESULT_INVALID')
    _d2_require(type(obs['execution_id']) is str and re.fullmatch('[0-9a-f]{32}', obs['execution_id']) is not None, 'RESULT_INVALID')
    for key in ('worker_pid', 'dispatcher_pid'):
        _d2_require(type(obs[key]) is int and 0 < obs[key] <= 2**31 - 1, 'RESULT_INVALID')
    _d2_reference(value['seed_ref'], seed=True)
    parent = value['parent_result_ref']
    if node == 'A':
        _d2_equal(parent, None, 'RESULT_INVALID')
    else:
        _d2_reference(parent, effect=_d2_effect(mission, 'A'))
        _d2_equal(parent, _d2_original_for(context, mission, 'A')['reference'], 'DEPENDENCY_VIOLATION')
    effect = _d2_effect(mission, node, parent)
    expected = {'schema_version': 'opendot.temporal.dag-result.v1', 'profile': 'synthetic.dependent_sum.v1', 'effect_id': effect, 'plan_sha256': DAG2_PLAN, 'namespace': 'default', 'workflow_id': _d2_workflow_id(mission), 'workflow_run_id': _d2_bootstrap(context, mission)['run_id'], 'activity_id': 'dag2-execute-' + effect[7:], 'registration_sha256': DAG2_REGISTRATION, 'input_payload_sha256': DAG2_INPUTS[node], 'observation_provenance': 'serialized_runtime_report_not_live_proof', 'scientific_validity': False, 'device_control_authority': False, 'independent_review': 'NOT_EVALUATED', 'owner_integration': 'NOT_EVALUATED'}
    for key, item in expected.items():
        _d2_equal(value[key], item, 'RESULT_INVALID')


def _d2_state(value, context):
    _d2_shape(value, 'schema_version profile mission_id plan_sha256 namespace workflow_id run_id revision mission_status admission_closed cancel_requested deadline_unix_ms seed_ref resources nodes external_effect_authenticity termination_status scientific_validity device_control_authority independent_review owner_integration')
    _d2_bytes(value, 16384)
    mission, revision = value['mission_id'], value['revision']
    _d2_require(type(mission) is str and mission in DAG2_MISSIONS, 'RUN_BINDING')
    limit = {'hosted-normal': 9, 'hosted-reconcile': 10, 'hosted-no-ref-cancel': 5}[mission]
    _d2_require(type(revision) is int and 1 <= revision <= limit, 'INVALID_TYPE')
    no_ref, reconcile = mission == DAG2_MISSIONS[2], mission == DAG2_MISSIONS[1]
    final = revision == limit
    cancel = no_ref and final
    unknown = mission != DAG2_MISSIONS[0] and revision == 4
    queued = reconcile and revision == 5
    status = 'STOPPED_WITH_UNKNOWN' if cancel else 'PAUSED_UNKNOWN' if unknown or queued else 'COMPLETED' if final else 'RUNNING'
    for key, expected in {'schema_version': 'opendot.temporal.dag-state.v1', 'profile': 'synthetic.dependent_sum.v1', 'plan_sha256': DAG2_PLAN, 'namespace': 'default', 'workflow_id': _d2_workflow_id(mission), 'run_id': _d2_bootstrap(context, mission)['run_id'], 'mission_status': status, 'admission_closed': final or unknown or queued, 'cancel_requested': cancel, 'external_effect_authenticity': 'NOT_PROVED', 'termination_status': 'NOT_ESTABLISHED', 'scientific_validity': False, 'device_control_authority': False, 'independent_review': 'NOT_EVALUATED', 'owner_integration': 'NOT_EVALUATED'}.items():
        _d2_equal(value[key], expected, 'CANCEL_MISMATCH' if key == 'cancel_requested' else 'RUN_BINDING' if key == 'run_id' else 'INVALID_VALUE')
    _d2_require(type(value['deadline_unix_ms']) is int and 1 <= value['deadline_unix_ms'] <= 10**15, 'INVALID_TYPE')
    _d2_reference(value['seed_ref'], seed=True)
    # Explicit fixed revision machine, not a stored PASS or caller oracle.
    a_phases = ['WAITING', 'RESERVED', 'EXECUTING']
    if no_ref:
        a_phases += ['UNKNOWN', 'UNKNOWN']
    elif reconcile:
        a_phases += ['UNKNOWN', 'VERIFYING'] + ['ACCEPTED'] * 5
    else:
        a_phases += ['VERIFYING'] + ['ACCEPTED'] * 5
    b_start = 7 if reconcile else 6
    b_status = 'CANCELLED_BEFORE_ADMISSION' if cancel else 'WAITING' if no_ref or revision < b_start else ['RESERVED', 'EXECUTING', 'VERIFYING', 'ACCEPTED'][revision - b_start]
    a_status = a_phases[revision - 1]
    a_inspect = (not no_ref) and revision >= (5 if reconcile else 4)
    b_inspect = b_status in ('VERIFYING', 'ACCEPTED')
    resources = {'execute_limit': 2, 'normal_inspect_limit': 2, 'reconcile_inspect_limit': 2, 'activity_command_limit': 6, 'result_bytes_reserved': 32768, 'execute_used': int(revision >= 2) + int(b_status in ('RESERVED', 'EXECUTING', 'VERIFYING', 'ACCEPTED')), 'normal_inspect_used': int(a_inspect and not reconcile) + int(b_inspect), 'reconcile_inspect_used': int(a_inspect and reconcile)}
    resources['activity_commands_used'] = resources['execute_used'] + resources['normal_inspect_used'] + resources['reconcile_inspect_used']
    _d2_shape(value['resources'], resources)
    _d2_require(all(type(x) is int for x in value['resources'].values()), 'INVALID_TYPE')
    _d2_equal(value['resources'], resources, 'RESOURCE_MISMATCH')
    _d2_shape(value['nodes'], {'A', 'B'})
    for node, phase, inspected in [('A', a_status, a_inspect), ('B', b_status, b_inspect)]:
        row = value['nodes'][node]
        _d2_shape(row, 'status effect_id parent_result_ref candidate_result_ref accepted_result_ref execute_reserved normal_inspect_reserved reconcile_inspect_reserved inspect_reserved reason_code')
        for ref_key in ('parent_result_ref', 'candidate_result_ref', 'accepted_result_ref'):
            if row[ref_key] is not None:
                _d2_reference(row[ref_key])
        _d2_equal(row['status'], phase, 'DEPENDENCY_VIOLATION')
        reserved = phase not in ('WAITING', 'CANCELLED_BEFORE_ADMISSION')
        reason = {'WAITING': 'NOT_ADMITTED', 'RESERVED': 'EXECUTE_RESERVED', 'EXECUTING': 'EXECUTING', 'UNKNOWN': 'CANCELLED' if cancel else 'EXECUTION_UNKNOWN', 'VERIFYING': 'RECONCILE_RESERVED' if node == 'A' and reconcile else 'INSPECT_RESERVED', 'ACCEPTED': 'RESULT_VERIFIED', 'CANCELLED_BEFORE_ADMISSION': 'CANCELLED'}[phase]
        for key, expected in {'execute_reserved': reserved, 'normal_inspect_reserved': inspected and not (node == 'A' and reconcile), 'reconcile_inspect_reserved': inspected and node == 'A' and reconcile, 'inspect_reserved': int(inspected), 'reason_code': reason}.items():
            _d2_equal(row[key], expected, 'RESOURCE_MISMATCH')
        parent = None if node == 'A' or a_status != 'ACCEPTED' else _d2_original_for(context, mission, 'A')['reference']
        _d2_equal(row['parent_result_ref'], parent, 'DEPENDENCY_VIOLATION')
        _d2_equal(row['effect_id'], _d2_effect(mission, node, parent) if node == 'A' or parent is not None else None, 'DEPENDENCY_VIOLATION')
        candidate = _d2_original_for(context, mission, node)['reference'] if inspected else None
        _d2_equal(row['candidate_result_ref'], candidate, 'ORIGIN_MISMATCH')
        _d2_equal(row['accepted_result_ref'], candidate if phase == 'ACCEPTED' else None, 'DEPENDENCY_VIOLATION')


def _d2_wire(value):
    """Closed ADR008 payload grammar; semantic linkage is checked from raw histories."""
    _d2_require(type(value) is dict and type(value.get('schema_version')) is str, 'HISTORY_PAYLOAD')
    schema_name = value['schema_version']
    shapes = {
        'opendot.temporal.dag-start.v1': 'schema_version mission_id plan_sha256 seed_ref',
        'opendot.temporal.dag-step.v1': 'schema_version mission_id plan_sha256 node_id effect_id seed_ref parent_result_ref',
        'opendot.temporal.dag-inspect.v1': 'schema_version mission_id plan_sha256 node_id effect_id seed_ref parent_result_ref candidate_result_ref mode expected_revision original_evidence_sha256 original_result_sha256',
        'opendot.temporal.dag-step-response.v1': 'schema_version effect_id result_ref',
        'opendot.temporal.dag-inspection.v1': 'schema_version effect_id mode expected_revision status reason_code result_ref input_payload_sha256 output original_evidence_sha256',
        'opendot.temporal.dag-reconcile.v1': 'schema_version node_id effect_id expected_revision candidate_result_ref original_evidence_sha256 original_result_sha256',
        'opendot.temporal.dag-reconciliation.v1': 'schema_version node_id effect_id status reason_code revision mission_status accepted_result_ref',
    }
    if schema_name == 'opendot.temporal.dag-state.v1':
        _d2_bytes(value, 16384)
        _d2_shape(value, 'schema_version profile mission_id plan_sha256 namespace workflow_id run_id revision mission_status admission_closed cancel_requested deadline_unix_ms seed_ref resources nodes external_effect_authenticity termination_status scientific_validity device_control_authority independent_review owner_integration', 'HISTORY_PAYLOAD')
        return
    _d2_require(schema_name in shapes, 'HISTORY_PAYLOAD')
    _d2_shape(value, shapes[schema_name], 'HISTORY_PAYLOAD')
    _d2_bytes(value, 4096)
    if 'seed_ref' in value:
        _d2_reference(value['seed_ref'], seed=True, code='HISTORY_PAYLOAD')
    if 'plan_sha256' in value:
        _d2_equal(value['plan_sha256'], DAG2_PLAN, 'HISTORY_PAYLOAD')
    if 'mission_id' in value:
        _d2_require(value['mission_id'] in DAG2_MISSIONS, 'HISTORY_PAYLOAD')
    if 'node_id' in value:
        _d2_require(value['node_id'] in ('A', 'B'), 'HISTORY_PAYLOAD')
    if 'effect_id' in value:
        _d2_require(type(value['effect_id']) is str and re.fullmatch('sha256:[0-9a-f]{64}', value['effect_id']) is not None, 'HISTORY_PAYLOAD')
    for key in ('parent_result_ref', 'candidate_result_ref', 'result_ref', 'accepted_result_ref'):
        if key in value and value[key] is not None:
            _d2_reference(value[key], code='HISTORY_PAYLOAD')


def _d2_payload(wrapper):
    import base64
    import binascii
    _d2_shape(wrapper, {'payloads'}, 'HISTORY_PAYLOAD')
    _d2_require(type(wrapper['payloads']) is list and len(wrapper['payloads']) == 1, 'HISTORY_PAYLOAD')
    payload = wrapper['payloads'][0]
    _d2_shape(payload, 'metadata data', 'HISTORY_PAYLOAD')
    _d2_shape(payload['metadata'], {'encoding'}, 'HISTORY_PAYLOAD')
    _d2_equal(payload['metadata']['encoding'], 'anNvbi9wbGFpbg==', 'HISTORY_PAYLOAD')
    _d2_require(type(payload['data']) is str, 'HISTORY_PAYLOAD')
    try:
        raw = base64.b64decode(payload['data'], validate=True)
    except (ValueError, binascii.Error):
        _d2_fail('HISTORY_PAYLOAD')
    _d2_equal(base64.b64encode(raw).decode('ascii'), payload['data'], 'HISTORY_PAYLOAD')
    _d2_require(len(raw) <= 16384, 'SIZE_LIMIT')
    try:
        value = strict_json(raw)
    except GateError:
        _d2_fail('HISTORY_PAYLOAD')
    _d2_require(len(raw) <= (16384 if type(value) is dict and value.get('schema_version') == 'opendot.temporal.dag-state.v1' else 4096), 'SIZE_LIMIT')
    _d2_wire(value)
    return value


def _d2_extract(raw_bytes):
    _d2_require(type(raw_bytes) is bytes, 'INVALID_TYPE')
    _d2_require(0 < len(raw_bytes) <= 2097152, 'SIZE_LIMIT')
    raw = strict_json(raw_bytes)
    _d2_shape(raw, {'events'}, 'HISTORY_MISMATCH')
    rows = raw['events']
    _d2_require(type(rows) is list and 1 <= len(rows) <= 512, 'SIZE_LIMIT')
    enum_map = {rule['enum']: (name, rule) for name, rule in DAG2_RAW_RULES['events'].items()}
    projection, payloads, last_id = [], {}, 0
    for row in rows:
        _d2_require(type(row) is dict and type(row.get('eventType')) is str and row['eventType'] in enum_map, 'HISTORY_MISMATCH')
        name, rule = enum_map[row['eventType']]
        keys = set(DAG2_RAW_RULES['event_common_allowed_keys']) | {rule['attribute_key']}
        _d2_require(set(row) <= keys and set(DAG2_RAW_RULES['event_required_keys']) | {rule['attribute_key']} <= set(row), 'HISTORY_MISMATCH')
        _d2_require(type(row['eventId']) is str and re.fullmatch('[1-9][0-9]{0,14}', row['eventId']) is not None, 'HISTORY_LINKAGE')
        event_id = int(row['eventId'])
        _d2_require(last_id < event_id <= 512, 'HISTORY_LINKAGE')
        last_id = event_id
        _d2_require(type(row['eventTime']) is str and re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z', row['eventTime']) is not None, 'HISTORY_MISMATCH')
        attributes = row[rule['attribute_key']]
        _d2_require(type(attributes) is dict and set(attributes) <= set(rule['attribute_allowed_keys']), 'HISTORY_MISMATCH')
        extracted = {}
        for key, path in rule['required_extracted_paths'].items():
            item = attributes
            for segment in path.split('/'):
                _d2_require(type(item) is dict and segment in item, 'HISTORY_MISMATCH')
                item = item[segment]
            if key == 'payload':
                decoded = _d2_payload(item)
                payloads[event_id] = decoded
                extracted['payload_sha256'] = _d2_hash(decoded, 16384)
            elif key.endswith('_event_id'):
                _d2_require(type(item) is str and re.fullmatch('[1-9][0-9]{0,14}', item) is not None, 'HISTORY_LINKAGE')
                extracted[key] = int(item)
            elif key in ('attempt', 'maximum_attempts'):
                _d2_require(type(item) is int and item == 1, 'HISTORY_MISMATCH')
                extracted[key] = item
            elif key == 'non_retryable':
                _d2_equal(item, True, 'HISTORY_MISMATCH')
                extracted[key] = item
            else:
                _d2_require(type(item) is str and 0 < len(item) <= 256, 'HISTORY_MISMATCH')
                extracted[key] = item
        if name == 'ActivityTaskFailed':
            _d2_equal(extracted['failure_type'], 'DAG2_TEST_RESPONSE_UNAVAILABLE', 'HISTORY_MISMATCH')
        for forbidden in ('continuedExecutionRunId', 'newExecutionRunId'):
            _d2_require(attributes.get(forbidden, '') == '', 'RUN_BINDING')
        projection.append({'event_id': event_id, 'event_type': name, 'extracted': extracted})
    _d2_bytes(projection, 262144)
    return projection, payloads


def dag2_extract_history(raw_bytes):
    """Reconstruct every projected fact from original bounded SDK JSON bytes."""
    return _d2_extract(raw_bytes)[0]


def _d2_claims(value):
    _d2_shape(value, DAG2_SCHEMAS['claims']['properties'], 'PRIVACY_REJECTED')
    _d2_checked_schema(value, 'claims', 'CLAIM_MISMATCH')


def _d2_environment(value, context, intent):
    _d2_shape(value, DAG2_SCHEMAS['environment']['properties'])
    _d2_require(value['evidence_class'] in ('FABRICATED_UNIT_DATA', 'OBSERVED_HOSTED_CANDIDATE'), 'INVALID_VALUE')
    if intent == 'HOSTED_CANDIDATE_ADMISSION':
        _d2_equal(value['evidence_class'], 'OBSERVED_HOSTED_CANDIDATE', 'HOSTED_ORIGIN_UNAUTHENTICATED', 'hosted_candidate_admission')
    else:
        _d2_equal(value['evidence_class'], 'FABRICATED_UNIT_DATA', 'INVALID_VALUE')
    identity = value['identity']
    _d2_shape(identity, DAG2_SCHEMAS['identity']['properties'])
    expected_identity = context['identity']
    for key in identity:
        code, boundary = ('PROFILE_MISMATCH', 'preflight') if key in ('event', 'qualification', 'retain_public_evidence') else ('SOURCE_MISMATCH', 'preflight') if key in ('commit', 'tree') else ('WORKFLOW_MISMATCH', 'record_validation') if key in ('workflow_sha256', 'workflow_path') else ('CI_IDENTITY', 'record_validation')
        _d2_equal(identity[key], expected_identity[key], code, boundary)
    for key, expected in {'event': 'workflow_dispatch', 'qualification': 'dag2', 'retain_public_evidence': False}.items():
        _d2_equal(identity[key], expected, 'PROFILE_MISMATCH', 'preflight')
    dag2_validate_schema(identity, 'identity')
    _d2_equal(identity['run_url'], 'https://github.com/' + identity['repository'] + '/actions/runs/' + str(identity['run_id']) + '/attempts/' + str(identity['run_attempt']), 'CI_IDENTITY')
    for key, expected in {'sdk_version': '1.34.0', 'cli_version': '1.9.1', 'server_version': '1.32.0', 'python_version': '3.12', 'runner_os': 'ubuntu-24.04'}.items():
        _d2_equal(value[key], expected, 'VERSION_MISMATCH', 'preflight')
    for key in ('effective_proxy_refused', 'fresh_private_root'):
        _d2_equal(value[key], True, 'PREFLIGHT_FAILED', 'preflight')
    for key in ('plan_sha256', 'adr008_sha256', 'base_tree'):
        _d2_equal(value[key], DAG2_SCHEMAS['environment']['properties'][key]['const'], 'PIN_MISMATCH')
    for key in ('source_before_sha256', 'source_after_sha256', 'complete_tracked_manifest_sha256'):
        _d2_equal(value[key], context['source_sha256'], 'SOURCE_MISMATCH', 'preflight')
    rows = value['source_closure']
    _d2_require(type(rows) is list and [r.get('path') for r in rows if type(r) is dict] == list(DAG2_SOURCE_CLOSURE), 'SOURCE_MISMATCH')
    immutable = DAG2_UNIT_IMMUTABLE_SOURCE if intent == 'UNIT_RECORD_CONSISTENCY' else context.get('reviewed_immutable_source', {})
    for row in rows:
        dag2_validate_schema(row, 'path_digest')
        if row['path'] in immutable:
            h, size, mode = immutable[row['path']]
            _d2_require((row['sha256'], row['size_bytes'], row['mode']) == (h, size, mode), 'OWNER_MISMATCH', 'preflight')
    if 'source_closure' in context:
        _d2_equal(rows, context['source_closure'], 'SOURCE_MISMATCH')
    bootstrap = value['bootstrap']
    _d2_require(type(bootstrap) is list and len(bootstrap) == 4, 'BOOTSTRAP_MISMATCH')
    expected_rows = context.get('bootstraps', bootstrap)
    for index, row in enumerate(bootstrap):
        _d2_shape(row, DAG2_SCHEMAS['bootstrap']['properties'])
        for key in ('activity_executor_threads', 'activity_slots', 'workflow_task_slots'):
            _d2_equal(row[key], 1, 'RESOURCE_MISMATCH')
        for key in ('handler_source_sha256', 'registration_sha256'):
            _d2_equal(row[key], DAG2_SCHEMAS['bootstrap']['properties'][key]['const'], 'OWNER_MISMATCH', 'preflight')
        for key, expected in {'immutable_config': True, 'source_verified': True, 'request_eager_start': False, 'eager_activity_execution': False, 'namespace': 'default', 'generation': (2, 4, 6, 8)[index], 'mission': (DAG2_MISSIONS[0], DAG2_MISSIONS[1], DAG2_MISSIONS[1], DAG2_MISSIONS[2])[index], 'original_B_sha256': None}.items():
            _d2_equal(row[key], expected, 'BOOTSTRAP_MISMATCH')
        _d2_require(type(row['run_id']) is str and re.fullmatch(r'[A-Za-z0-9._-]{1,128}', row['run_id']) is not None, 'BOOTSTRAP_MISMATCH')
        _d2_equal(row['first_execution_run_id'], row['run_id'], 'BOOTSTRAP_MISMATCH')
        _d2_equal(row['run_id'], expected_rows[index]['run_id'], 'BOOTSTRAP_MISMATCH')
        _d2_equal(row['workflow_id'], _d2_workflow_id(row['mission']), 'BOOTSTRAP_MISMATCH')
        _d2_equal(row['task_queue'], 'opendot-dag2-' + str(identity['run_id']) + '-' + str(identity['run_attempt']) + '-' + row['mission'], 'BOOTSTRAP_MISMATCH')
        _d2_require(type(row['constructed_seq']) is int and type(row['started_seq']) is int and row['constructed_seq'] < row['started_seq'], 'BOOTSTRAP_MISMATCH')
        if index == 2:
            original = _d2_original_for(context, row['mission'], 'A')
            _d2_equal(row['original_A_sha256'], original['origin_sha256'], 'ORIGIN_MISMATCH')
            _d2_equal(row['origin_capture_seq'], original['capture_seq'], 'ORIGIN_ORDER')
            _d2_require(original['capture_seq'] < row['constructed_seq'], 'ORIGIN_ORDER')
        else:
            _d2_equal(row['original_A_sha256'], None, 'BOOTSTRAP_MISMATCH')
            _d2_equal(row['origin_capture_seq'], None, 'BOOTSTRAP_MISMATCH')
    _d2_equal(bootstrap[1]['run_id'], bootstrap[2]['run_id'], 'BOOTSTRAP_MISMATCH')
    _d2_require(len({bootstrap[i]['run_id'] for i in (0, 1, 3)}) == 3, 'RUN_BINDING')
    _d2_claims(value['claims'])
    dag2_validate_schema(value, 'environment')


def _d2_original(value, context):
    _d2_shape(value, DAG2_SCHEMAS['original']['properties'])
    _d2_reference(value['reference'])
    origin = value['origin']
    _d2_shape(origin, DAG2_SCHEMAS['origin']['properties'])
    _d2_equal(origin['origin_kind'], 'trusted-single-operator-synthetic-put-observer', 'ORIGIN_MISMATCH')
    _d2_equal(origin['capture_phase'], 'original_put_return_before_response', 'ORIGIN_ORDER')
    mission, node = value['mission'], value['node']
    _d2_require(mission in DAG2_MISSIONS[:2] and node in ('A', 'B'), 'ORIGIN_MISMATCH')
    _d2_equal(origin['workflow_run_id'], _d2_bootstrap(context, mission)['run_id'], 'ORIGIN_MISMATCH')
    body = context['retained_bodies'][mission + '/' + node]
    _d2_body(body, context)
    encoded = _d2_bytes(body, 16384)
    _d2_equal(value['body']['sha256'], hashlib.sha256(encoded).hexdigest(), 'ORIGINAL_MUTATED')
    _d2_equal(value['body']['size_bytes'], len(encoded), 'ORIGINAL_MUTATED')
    _d2_equal(value['reference']['sha256'], value['body']['sha256'], 'ORIGINAL_MUTATED')
    _d2_equal(value['reference']['size_bytes'], len(encoded), 'ORIGINAL_MUTATED')
    _d2_reference(value['reference'], effect=body['effect_id'], parent=body['parent_result_ref'])
    for key, expected in {'schema_version': 'opendot.temporal.dag-origin.v1', 'mission_id': mission, 'plan_sha256': DAG2_PLAN, 'node_id': node, 'effect_id': body['effect_id'], 'namespace': 'default', 'workflow_id': body['workflow_id'], 'execution_activity_id': body['activity_id'], 'original_result_ref': value['reference']}.items():
        _d2_equal(origin[key], expected, 'ORIGIN_MISMATCH')
    _d2_equal(value['origin_sha256'], _d2_hash(origin), 'ORIGIN_MISMATCH')
    for key, expected in {'receipt_sha256': _d2_hash(body['receipt_report']), 'receipt_call_id': body['receipt_report']['call_id'], 'observation_execution_id': body['receipt_report']['execution_observation']['execution_id'], 'input_sha256': DAG2_INPUTS[node], 'output_sha256': DAG2_OUTPUTS[node], 'output': 5 if node == 'A' else 6}.items():
        _d2_equal(value[key], expected, 'RESULT_INVALID')
    _d2_require(all(type(value[k]) is int for k in ('put_return_seq', 'capture_seq', 'adapter_return_seq')), 'INVALID_TYPE')
    _d2_require(value['put_return_seq'] < value['capture_seq'] < value['adapter_return_seq'], 'ORIGIN_ORDER')
    dag2_validate_schema(value, 'original')


def _d2_command(value, context):
    _d2_shape(value, DAG2_SCHEMAS['command']['properties'])
    for key, expected in {'attempt': 1, 'maximum_attempts': 1, 'start_to_close_seconds': 10, 'schedule_to_close_seconds': 60}.items():
        _d2_equal(value[key], expected, 'HISTORY_MISMATCH')
    _d2_checked_schema(value, 'command', 'HISTORY_MISMATCH')
    _d2_require(value['scheduled_event_id'] < value['started_event_id'] < value['terminal_event_id'], 'HISTORY_LINKAGE')
    _d2_require(value['entry_seq'] < value['return_seq'] < value['terminal_observed_seq'], 'HISTORY_LINKAGE')
    mission, node, kind = value['mission'], value['node'], value['kind']
    b = _d2_bootstrap(context, mission, mission == DAG2_MISSIONS[1] and kind != 'execute' or mission == DAG2_MISSIONS[1] and node == 'B')
    _d2_equal(value['run_id'], b['run_id'], 'RUN_BINDING')
    _d2_equal(value['workflow_id'], b['workflow_id'], 'RUN_BINDING')
    _d2_equal(value['worker_generation'], b['generation'], 'BOOTSTRAP_MISMATCH')
    _d2_equal(value['activity_type'], 'opendot.synthetic.dependent-step.v1' if kind == 'execute' else 'opendot.synthetic.dependent-inspect.v1', 'HISTORY_MISMATCH')
    parent = _d2_original_for(context, mission, 'A')['reference'] if node == 'B' else None
    effect = _d2_effect(mission, node, parent)
    _d2_equal(value['activity_id'], ('dag2-execute-' if kind == 'execute' else 'dag2-inspect-' + ('normal-' if kind == 'normal_inspect' else 'reconcile-')) + effect[7:], 'HISTORY_MISMATCH')
    failed = mission != DAG2_MISSIONS[0] and node == 'A' and kind == 'execute'
    _d2_equal(value['terminal_type'], 'ActivityTaskFailed' if failed else 'ActivityTaskCompleted', 'HISTORY_MISMATCH')
    _d2_equal(value['fault'], 'CONTROLLED_POST_RETURN_RESPONSE_FAILURE' if failed else 'NONE', 'HISTORY_MISMATCH')
    if failed:
        _d2_equal(value['response_sha256'], None, 'HISTORY_MISMATCH')
    if kind == 'reconcile_inspect':
        _d2_require(value['schedule_observed_seq'] < b['started_seq'] < value['entry_seq'], 'HISTORY_LINKAGE')


def _d2_rpc(rows, context):
    _d2_require(type(rows) is list and 1 <= len(rows) <= 64, 'SIZE_LIMIT')
    _d2_require(all(type(row) is dict and type(row.get('operation_id')) is str for row in rows), 'INVALID_SCHEMA')
    _d2_require(len({row['operation_id'] for row in rows}) == len(rows), 'UPDATE_MISMATCH')
    for row in rows:
        _d2_shape(row, DAG2_SCHEMAS['rpc']['properties'])
        _d2_require(row['settled_seq'] is not None and row['outcome'] != 'UNCONFIRMED', 'RPC_UNCONFIRMED')
        _d2_equal(row['follow_runs'], False, 'RUN_BINDING')
        _d2_equal(row['application_submissions'], 1, 'RPC_RESUBMITTED')
        _d2_checked_schema(row, 'rpc', 'RPC_UNCONFIRMED')
        expected_refusal = row['kind'] == 'update_result' and row['operation_id'] in ('update-stale-result', 'update-distinct-busy-result')
        _d2_equal(row['outcome'], 'EXPECTED_VALIDATOR_REFUSAL' if expected_refusal else 'SUCCESS', 'UPDATE_MISMATCH' if row['kind'] == 'start_update' else 'RPC_UNCONFIRMED')
        if row['kind'] == 'start_update':
            allowed = {'update-stale': 'dag2-reconcile-stale', 'update-original': 'dag2-reconcile-original', 'update-repeat-same-id': 'dag2-reconcile-original', 'update-distinct-busy': 'dag2-reconcile-busy'}
            _d2_require(row['operation_id'] in allowed, 'UPDATE_MISMATCH')
            _d2_equal(row['update_id'], allowed[row['operation_id']], 'UPDATE_MISMATCH')
        elif row['kind'] == 'update_result':
            allowed = {'update-stale-result': 'dag2-reconcile-stale', 'update-distinct-busy-result': 'dag2-reconcile-busy', 'update-original-result': 'dag2-reconcile-original', 'update-get-completed': 'dag2-reconcile-original'}
            _d2_require(row['operation_id'] in allowed, 'UPDATE_MISMATCH')
            _d2_equal(row['update_id'], allowed[row['operation_id']], 'UPDATE_MISMATCH')
        _d2_require(row['issued_seq'] < row['settled_seq'], 'RPC_UNCONFIRMED')
        bootstrap = _d2_bootstrap(context, row['mission'])
        _d2_equal(row['workflow_id'], bootstrap['workflow_id'], 'RUN_BINDING')
        _d2_equal(row['run_id'], bootstrap['run_id'], 'RUN_BINDING')
        if row['kind'] not in ('start_update', 'update_result'):
            _d2_equal(row['update_id'], None, 'UPDATE_MISMATCH')
    _d2_require(len({r['operation_id'] for r in rows}) == len(rows), 'UPDATE_MISMATCH')


def _d2_update(value, context):
    _d2_shape(value, DAG2_SCHEMAS['update']['properties'])
    _d2_checked_schema(value, 'update', 'UPDATE_MISMATCH')
    cases = {
        'update-stale': ('dag2-reconcile-stale', 3, 4, 4, 'VALIDATOR_REFUSED', 'STALE_REVISION', 0),
        'update-original': ('dag2-reconcile-original', 4, 4, 5, 'ACCEPTED_QUEUED', 'VALID_RECONCILIATION', 1),
        'update-repeat-same-id': ('dag2-reconcile-original', 4, 5, 5, 'SAME_UPDATE_QUEUED', 'RECORDED_SAME_ID', 0),
        'update-distinct-busy': ('dag2-reconcile-busy', 4, 5, 5, 'VALIDATOR_REFUSED', 'INSPECTION_BUSY', 0),
        'update-get-completed': ('dag2-reconcile-original', 4, 10, 10, 'SAME_COMPLETED_RESULT', 'RECORDED_SAME_ID', 0),
    }
    for key, expected in zip(('update_id', 'expected_revision', 'pre_revision', 'post_revision', 'outcome', 'precondition_oracle', 'reservation_delta'), cases[value['operation_id']]):
        _d2_equal(value[key], expected, 'UPDATE_MISMATCH')
    origin = _d2_original_for(context, DAG2_MISSIONS[1], 'A')
    request = {'schema_version': 'opendot.temporal.dag-reconcile.v1', 'node_id': 'A', 'effect_id': origin['origin']['effect_id'], 'expected_revision': value['expected_revision'], 'candidate_result_ref': origin['reference'], 'original_evidence_sha256': origin['origin_sha256'], 'original_result_sha256': origin['reference']['sha256']}
    _d2_equal(value['request_sha256'], _d2_hash(request), 'UPDATE_MISMATCH')
    refused = value['outcome'] == 'VALIDATOR_REFUSED'
    for key, expected in {'actual_error_type': 'TemporalDagUpdateRejected' if refused else None, 'actual_error_details': 'UPDATE_REFUSED' if refused else None, 'endpoint_read_delta': 0, 'execute_delta': 0}.items():
        _d2_equal(value[key], expected, 'UPDATE_MISMATCH')
    if refused:
        for key in ('accepted_event_id', 'completed_event_id', 'result_sha256'):
            _d2_equal(value[key], None, 'UPDATE_MISMATCH')
    else:
        _d2_require(type(value['accepted_event_id']) is int and type(value['completed_event_id']) is int and value['accepted_event_id'] < value['completed_event_id'], 'UPDATE_MISMATCH')
        peers = [r for r in context.get('updates', []) if r.get('operation_id') == 'update-original']
        if peers:
            for key in ('accepted_event_id', 'completed_event_id', 'request_sha256'):
                _d2_equal(value[key], peers[0][key], 'UPDATE_MISMATCH')
    _d2_equal(value['origin_capture_seq'], origin['capture_seq'], 'ORIGIN_ORDER')
    _d2_equal(value['bootstrap_constructed_seq'], _d2_bootstrap(context, DAG2_MISSIONS[1], True)['constructed_seq'], 'ORIGIN_ORDER')
    _d2_require(value['origin_capture_seq'] < value['bootstrap_constructed_seq'] < value['submit_seq'], 'ORIGIN_ORDER')


def _d2_counts(value):
    _d2_shape(value, DAG2_SCHEMAS['counts']['properties'])
    expected = {'workflow_starts': 3, 'activity_schedules': 9, 'activity_entries': 9, 'activity_returns': 9, 'runtime_entries': 5, 'runtime_returns': 5, 'handler_entries': 5, 'handler_returns': 5, 'seed_puts': 3, 'result_puts': 5, 'endpoint_cas_reads': 11, 'observer_cas_reads': 0, 'verification_cas_reads': 4, 'in_flight_calls': 0, 'pending_rpc_tasks': 0}
    for key, number in expected.items():
        _d2_require(type(value[key]) is int, 'INVALID_TYPE')
        _d2_equal(value[key], number, 'NO_REF_REDISCOVERY' if key == 'verification_cas_reads' else 'COUNTER_MISMATCH')


def _d2_cleanup(value):
    _d2_shape(value, DAG2_SCHEMAS['cleanup']['properties'])
    for key, definition in DAG2_SCHEMAS['cleanup']['properties'].items():
        if key.endswith('_elapsed_ms'):
            _d2_require(type(value[key]) is int, 'INVALID_TYPE')
            _d2_require(0 <= value[key] <= definition['maximum'], 'DEADLINE_EXHAUSTED')
        elif 'const' in definition:
            _d2_require(type(value[key]) is type(definition['const']), 'INVALID_TYPE')
            _d2_equal(value[key], definition['const'], 'CANCEL_SCOPE' if key == 'force_or_task_cancellation_calls' else 'CANCEL_MISMATCH' if key == 'workflow_handle_cancel_calls' else 'CLEANUP_UNCONFIRMED')
    _d2_checked_schema(value, 'cleanup', 'CLEANUP_UNCONFIRMED')
    _d2_equal([r['generation'] for r in value['worker_stops']], [2, 1, 4, 3, 6, 5, 8, 7], 'CLEANUP_UNCONFIRMED')
    for row in value['worker_stops']:
        activity = row['generation'] % 2 == 0
        _d2_equal(row['kind'], 'activity' if activity else 'workflow', 'CLEANUP_UNCONFIRMED')
        _d2_equal(row['executor_shutdown_calls'], int(activity), 'CLEANUP_UNCONFIRMED')
        _d2_equal(row['activity_executor_completion_observed'], activity, 'CLEANUP_UNCONFIRMED')
        _d2_require(row['start_seq'] < row['quiescent_snapshot_seq'] < row['stop_requested_seq'] < row['stop_completed_seq'], 'CLEANUP_UNCONFIRMED')


def _d2_replays(rows):
    _d2_require(type(rows) is list and len(rows) == 2, 'REPLAY_MISMATCH')
    for index, row in enumerate(rows):
        _d2_require(type(row) is dict and row.get('replay_failure') is None, 'REPLAY_MISMATCH')
        _d2_checked_schema(row, 'replay', 'REPLAY_MISMATCH')
        _d2_equal(row['mission'], DAG2_MISSIONS[index], 'REPLAY_MISMATCH')
        _d2_equal(row['retained_history_sha256'], row['replayer_input_sha256'], 'REPLAY_MISMATCH')
        _d2_equal(row['counts_before'], row['counts_after'], 'REPLAY_MISMATCH')
        _d2_require(row['begin_seq'] < row['end_seq'], 'REPLAY_MISMATCH')
        _d2_equal(row['counts_before']['in_flight_calls'], 0, 'REPLAY_MISMATCH')
        _d2_equal(row['counts_before']['pending_rpc_tasks'], 0, 'REPLAY_MISMATCH')


def _d2_summary(value, failure=False):
    name = 'failure_summary' if failure else 'summary'
    _d2_shape(value, DAG2_SCHEMAS[name]['properties'], 'PRIVACY_REJECTED')
    _d2_claims(value['claims'])
    if failure:
        _d2_require(value['count_evidence'] in ('VALIDATED_PARTIAL', 'UNAVAILABLE'), 'INVALID_VALUE')
        if value['count_evidence'] == 'UNAVAILABLE':
            for key in ('collected_nodes', 'passed_nodes', 'failed_nodes', 'error_nodes', 'skipped_nodes', 'missions_admitted', 'activity_schedules_observed', 'runtime_entries_observed'):
                _d2_equal(value[key], 0, 'COUNTER_MISMATCH')
    else:
        _d2_equal(value['skipped_nodes'], 0, 'TEST_SKIPPED')
        for key in ('xfail_nodes', 'failed_nodes', 'error_nodes'):
            _d2_equal(value[key], 0, 'TEST_FAILED')
        _d2_equal(value['collected_nodes'], 7, 'COLLECTION_MISMATCH')
    dag2_validate_schema(value, name)
    _d2_bytes(value, 8192)


def _d2_diagnostic(value, *, allow_failure=False):
    _d2_shape(value, DAG2_SCHEMAS['diagnostic']['properties'], 'PRIVACY_REJECTED')
    for key in ('primary_failure', 'cleanup_failure', 'audit_failure'):
        if value[key] is not None:
            _d2_shape(value[key], {'code', 'phase'}, 'PRIVACY_REJECTED')
    dag2_validate_schema(value, 'diagnostic')
    _d2_bytes(value, 4096)
    if not allow_failure:
        if value['audit_failure'] is not None:
            _d2_fail('WRITE_FAILED')
        _d2_require(value['primary_failure'] is None and value['cleanup_failure'] is None and value['result'] == 'PASS' and value['cleanup_status'] == 'PASS' and value['evidence_status'] == 'COMPLETE', 'CLEANUP_UNCONFIRMED')


def _d2_events(rows):
    _d2_require(type(rows) is list and 1 <= len(rows) <= 512, 'SIZE_LIMIT')
    last = -1
    for seq, row in enumerate(rows, 1):
        _d2_shape(row, DAG2_SCHEMAS['event']['properties'])
        _d2_require(row['seq'] == seq and type(row['seq']) is int and type(row['monotonic_ns']) is int and row['monotonic_ns'] >= last, 'CAUSAL_ORDER')
        last = row['monotonic_ns']
        dag2_validate_schema(row, 'event')
        _d2_require(row['kind'] != 'observer_failure', 'CLEANUP_UNCONFIRMED')


def validate_dag2_component(name, value, *, context, validation_intent):
    """Bounded component consistency for unit fixtures and observed candidates."""
    _d2_require(validation_intent in ('UNIT_RECORD_CONSISTENCY', 'HOSTED_CANDIDATE_ADMISSION', 'EXTERNAL_ORIGIN_GATE_UNTRUSTED_INPUT'), 'INVALID_VALUE')
    try:
        if name == 'external_readback':
            if type(value) is dict and (value.get('run_status') != 'completed' or value.get('job_conclusion') != 'success'):
                _d2_fail('CI_IDENTITY', 'external_origin_gate')
            _d2_fail('HOSTED_ORIGIN_UNAUTHENTICATED', 'external_origin_gate')
        limits = {'history_bytes': 2097152, 'trace_bytes': 262144, 'evidence_bytes': 27262976, 'projection_bytes': 262144, 'result_bytes': 16384, 'wire_bytes': 4096, 'state_bytes': 16384, 'seed_bytes': 256}
        if name in limits:
            size = len(value) if type(value) is bytes else value
            _d2_require(type(size) is int and 0 <= size <= limits[name], 'SIZE_LIMIT')
        elif name == 'environment':
            _d2_environment(value, context, validation_intent)
        elif name == 'owner_pins':
            _d2_shape(value, {'activity_sha256'})
            _d2_equal(value['activity_sha256'], '3e084d5432c11d031385472b9eba32e1d62f06d4aa45e08acebd88bd803045f2', 'OWNER_MISMATCH', 'preflight')
        elif name == 'retained_body':
            _d2_body(value, context)
        elif name == 'state':
            _d2_state(value, context)
        elif name == 'original':
            _d2_original(value, context)
        elif name == 'no_ref':
            _d2_shape(value, DAG2_SCHEMAS['originals']['properties']['no_ref']['properties'])
            try:
                _d2_schema(value, DAG2_SCHEMAS['originals']['properties']['no_ref'])
            except GateError:
                _d2_fail('NO_REF_REDISCOVERY')
        elif name == 'command':
            _d2_command(value, context)
        elif name == 'commands':
            _d2_require(type(value) is list and len(value) == 9, 'COUNTER_MISMATCH')
            for row in value:
                _d2_command(row, context)
        elif name == 'rpc_operations':
            _d2_rpc(value, context)
        elif name == 'update':
            _d2_update(value, context)
        elif name == 'updates':
            _d2_require(type(value) is list and len(value) == 5, 'UPDATE_MISMATCH')
            for row in value:
                _d2_update(row, context)
        elif name == 'aggregate_counts':
            _d2_counts(value)
        elif name == 'cleanup':
            _d2_cleanup(value)
        elif name == 'replays':
            _d2_replays(value)
        elif name in ('summary', 'failure_summary'):
            _d2_summary(value, name == 'failure_summary')
        elif name == 'diagnostic':
            _d2_diagnostic(value)
        elif name == 'required_nodes':
            _d2_equal(value, list(DAG2_REQUIRED_NODES), 'REQUIRED_NODES')
        elif name == 'junit':
            _d2_shape(value, {'node_ids'})
            _d2_equal(value['node_ids'], list(DAG2_REQUIRED_NODES), 'JUNIT_IDENTITY')
        elif name == 'events':
            _d2_events(value)
        elif name == 'snapshots':
            _d2_require(type(value) is list and len(value) == 7, 'HISTORY_MISMATCH')
            for row in value:
                for key in ('history', 'state'):
                    _d2_require(type(row[key]['file_id']) is str and row[key]['file_id'] in DAG2_INPUT_FILES, 'PRIVACY_REJECTED')
                dag2_validate_schema(row, 'snapshot')
        elif name == 'raw_history':
            projection = dag2_extract_history(value)
            for row in projection:
                if row['event_type'] == 'WorkflowExecutionStarted':
                    _d2_equal(row['extracted']['run_id'], context['run_id'], 'RUN_BINDING')
                    _d2_equal(row['extracted']['first_run_id'], context['run_id'], 'RUN_BINDING')
            if context.get('projection') is not None:
                _d2_equal(projection, context['projection'], 'HISTORY_PROJECTION_MISMATCH')
        elif name == 'causal_order':
            _d2_require(value['origin_capture'] < value['bootstrap_constructed'] < value['update_submit'], 'ORIGIN_ORDER')
            _d2_require(value['bootstrap_constructed'] < value['worker_start'], 'BOOTSTRAP_MISMATCH')
            _d2_require(value['replacement_activity_worker_start'] < value['reconcile_activity_entry'], 'HISTORY_LINKAGE')
        elif name == 'history_order':
            _d2_require(value['A.accepted'] < value['B.scheduled'], 'DEPENDENCY_VIOLATION')
        else:
            _d2_fail('INVALID_SCHEMA')
    except GateError as error:
        if not hasattr(error, 'boundary'):
            error.boundary = 'record_validation'
        raise
    except (KeyError, TypeError, IndexError, ValueError, RecursionError):
        _d2_fail('INVALID_SCHEMA')
    if name == 'failure_summary':
        return 'VALID_FAILURE_DIAGNOSTIC_ONLY'
    return 'UNIT_RECORD_VALID' if validation_intent == 'UNIT_RECORD_CONSISTENCY' else 'RECORD_VALIDATION_PASS'


def _d2_request(command, context):
    mission, node, kind = command['mission'], command['node'], command['kind']
    parent = _d2_original_for(context, mission, 'A')['reference'] if node == 'B' else None
    seed = context['states']['normal-final']['seed_ref']
    request = {'schema_version': 'opendot.temporal.dag-step.v1', 'mission_id': mission, 'plan_sha256': DAG2_PLAN, 'node_id': node, 'effect_id': _d2_effect(mission, node, parent), 'seed_ref': seed, 'parent_result_ref': parent}
    if kind != 'execute':
        original = _d2_original_for(context, mission, node)
        reconcile = kind == 'reconcile_inspect'
        request.update(schema_version='opendot.temporal.dag-inspect.v1', mode='reconcile' if reconcile else 'normal', expected_revision=5 if reconcile else 4 if node == 'A' else 9 if mission == DAG2_MISSIONS[1] else 8, candidate_result_ref=original['reference'], original_evidence_sha256=original['origin_sha256'] if reconcile else None, original_result_sha256=original['reference']['sha256'] if reconcile else None)
    return request


def _d2_response(command, request, context):
    if command['terminal_type'] == 'ActivityTaskFailed':
        return None
    original = _d2_original_for(context, command['mission'], command['node'])
    if command['kind'] == 'execute':
        return {'schema_version': 'opendot.temporal.dag-step-response.v1', 'effect_id': request['effect_id'], 'result_ref': original['reference']}
    return {'schema_version': 'opendot.temporal.dag-inspection.v1', 'effect_id': request['effect_id'], 'mode': request['mode'], 'expected_revision': request['expected_revision'], 'status': 'CONSISTENT_COMPLETED', 'reason_code': 'RESULT_VERIFIED', 'result_ref': original['reference'], 'input_payload_sha256': DAG2_INPUTS[command['node']], 'output': 5 if command['node'] == 'A' else 6, 'original_evidence_sha256': request['original_evidence_sha256']}


def _d2_validate_history(snapshot, raw, state, context, *, final):
    projection, payloads = _d2_extract(raw)
    # The production deadline is anchored to the actual immutable Workflow start.
    from datetime import datetime
    raw_start = strict_json(raw)['events'][0]
    _d2_require(raw_start['eventType'] == 'EVENT_TYPE_WORKFLOW_EXECUTION_STARTED', 'HISTORY_MISMATCH')
    try:
        start_ms = int(datetime.fromisoformat(raw_start['eventTime'].replace('Z', '+00:00')).timestamp() * 1000)
    except (ValueError, OverflowError):
        _d2_fail('HISTORY_MISMATCH')
    _d2_equal(state['deadline_unix_ms'], start_ms + 300000, 'DEADLINE_EXHAUSTED')
    mission = snapshot['mission']
    bootstrap = _d2_bootstrap(context, mission)
    indexed, counts = {}, {}
    timers, ended_timers = {}, set()
    task_starts, task_completions = set(), set()
    commands = [r for r in context['commands'] if r['mission'] == mission]
    by_schedule = {r['scheduled_event_id']: r for r in commands}
    start_count = 0
    for event in projection:
        event_id, kind, extracted = event['event_id'], event['event_type'], event['extracted']
        counts[kind] = counts.get(kind, 0) + 1
        def linked(key, allowed):
            number = extracted[key]
            _d2_require(number in indexed and indexed[number]['event_type'] in allowed, 'HISTORY_LINKAGE')
            return indexed[number]
        if kind == 'WorkflowExecutionStarted':
            start_count += 1
            _d2_require(event_id == 1 and start_count == 1, 'HISTORY_LINKAGE')
            for key in ('run_id', 'first_run_id'):
                _d2_equal(extracted[key], bootstrap['run_id'], 'RUN_BINDING')
            for key, expected in {'task_queue': bootstrap['task_queue'], 'workflow_type': 'opendot.synthetic.dependent-sum.v1', 'execution_timeout': '300s', 'run_timeout': '300s', 'task_timeout': '10s', 'attempt': 1, 'maximum_attempts': 1}.items():
                _d2_equal(extracted[key], expected, 'HISTORY_MISMATCH')
            _d2_equal(payloads[event_id], {'schema_version': 'opendot.temporal.dag-start.v1', 'mission_id': mission, 'plan_sha256': DAG2_PLAN, 'seed_ref': state['seed_ref']}, 'HISTORY_PAYLOAD')
        elif kind == 'WorkflowTaskScheduled':
            _d2_equal(extracted['task_queue'], bootstrap['task_queue'], 'HISTORY_MISMATCH')
            _d2_equal(extracted['task_timeout'], '10s', 'HISTORY_MISMATCH')
        elif kind == 'WorkflowTaskStarted':
            linked('scheduled_event_id', ('WorkflowTaskScheduled',))
            _d2_require(extracted['scheduled_event_id'] not in task_starts, 'HISTORY_LINKAGE')
            task_starts.add(extracted['scheduled_event_id'])
        elif kind == 'WorkflowTaskCompleted':
            linked('scheduled_event_id', ('WorkflowTaskScheduled',))
            _d2_require(extracted['scheduled_event_id'] not in task_completions, 'HISTORY_LINKAGE')
            task_completions.add(extracted['scheduled_event_id'])
            started = linked('started_event_id', ('WorkflowTaskStarted',))
            _d2_equal(started['extracted']['scheduled_event_id'], extracted['scheduled_event_id'], 'HISTORY_LINKAGE')
        elif kind == 'ActivityTaskScheduled':
            linked('workflow_task_completed_event_id', ('WorkflowTaskCompleted',))
            _d2_require(event_id in by_schedule, 'HISTORY_MISMATCH')
            command = by_schedule[event_id]
            # Projection identity disagreement is distinguished from decoded payload corruption.
            _d2_equal(extracted['activity_id'], command['activity_id'], 'HISTORY_PROJECTION_MISMATCH')
            for key, expected in {'activity_type': command['activity_type'], 'task_queue': bootstrap['task_queue'], 'maximum_attempts': 1, 'start_to_close_timeout': '10s', 'schedule_to_close_timeout': '60s'}.items():
                _d2_equal(extracted[key], expected, 'HISTORY_MISMATCH')
            request = _d2_request(command, context)
            _d2_equal(payloads[event_id], request, 'HISTORY_PAYLOAD')
            _d2_equal(extracted['payload_sha256'], command['request_sha256'], 'HISTORY_PAYLOAD')
        elif kind in ('ActivityTaskStarted', 'ActivityTaskCompleted', 'ActivityTaskFailed'):
            linked('scheduled_event_id', ('ActivityTaskScheduled',))
            command = by_schedule[extracted['scheduled_event_id']]
            _d2_equal(event_id, command['started_event_id'] if kind == 'ActivityTaskStarted' else command['terminal_event_id'], 'HISTORY_LINKAGE')
            if kind != 'ActivityTaskStarted':
                started = linked('started_event_id', ('ActivityTaskStarted',))
                _d2_equal(started['extracted']['scheduled_event_id'], extracted['scheduled_event_id'], 'HISTORY_LINKAGE')
                _d2_equal(kind, command['terminal_type'], 'HISTORY_MISMATCH')
                if kind == 'ActivityTaskCompleted':
                    expected = _d2_response(command, _d2_request(command, context), context)
                    _d2_equal(payloads[event_id], expected, 'HISTORY_PAYLOAD')
                    _d2_equal(extracted['payload_sha256'], command['response_sha256'], 'HISTORY_PAYLOAD')
        elif kind == 'WorkflowExecutionCompleted':
            linked('workflow_task_completed_event_id', ('WorkflowTaskCompleted',))
            _d2_require(final and event_id == projection[-1]['event_id'], 'HISTORY_MISMATCH')
            _d2_equal(payloads[event_id], state, 'HISTORY_PAYLOAD')
            _d2_equal(snapshot['completion_payload_sha256'], extracted['payload_sha256'], 'HISTORY_PAYLOAD')
        elif kind == 'WorkflowExecutionUpdateAccepted':
            _d2_require(mission == DAG2_MISSIONS[1], 'UPDATE_MISMATCH')
            linked('accepted_request_sequencing_event_id', ('WorkflowTaskScheduled', 'WorkflowTaskStarted', 'WorkflowTaskCompleted'))
            update = context['updates'][1]
            _d2_equal(event_id, update['accepted_event_id'], 'UPDATE_MISMATCH')
            _d2_equal(extracted['update_id'], 'dag2-reconcile-original', 'UPDATE_MISMATCH')
            _d2_equal(extracted['protocol_instance_id'], extracted['update_id'], 'UPDATE_MISMATCH')
            _d2_equal(extracted['update_name'], 'reconcile_result', 'UPDATE_MISMATCH')
            _d2_equal(extracted['payload_sha256'], update['request_sha256'], 'HISTORY_PAYLOAD')
        elif kind == 'WorkflowExecutionUpdateCompleted':
            accepted = linked('accepted_event_id', ('WorkflowExecutionUpdateAccepted',))
            _d2_equal(extracted['update_id'], accepted['extracted']['update_id'], 'UPDATE_MISMATCH')
            update = context['updates'][4]
            _d2_equal(event_id, update['completed_event_id'], 'UPDATE_MISMATCH')
            original = _d2_original_for(context, mission, 'A')
            expected = {'schema_version': 'opendot.temporal.dag-reconciliation.v1', 'node_id': 'A', 'effect_id': original['origin']['effect_id'], 'status': 'ACCEPTED', 'reason_code': 'RESULT_VERIFIED', 'revision': 6, 'mission_status': 'RUNNING', 'accepted_result_ref': original['reference']}
            _d2_equal(payloads[event_id], expected, 'HISTORY_PAYLOAD')
            _d2_equal(update['result_sha256'], extracted['payload_sha256'], 'UPDATE_MISMATCH')
        elif kind == 'WorkflowExecutionCancelRequested':
            _d2_require(mission == DAG2_MISSIONS[2] and final and counts[kind] == 1, 'CANCEL_MISMATCH')
        elif kind == 'TimerStarted':
            linked('workflow_task_completed_event_id', ('WorkflowTaskCompleted',))
            _d2_require(extracted['timer_id'] not in timers and re.fullmatch(r'(?:[0-9]+(?:\.[0-9]{1,9})?)s', extracted['timeout']) is not None and 0 < float(extracted['timeout'][:-1]) <= 300, 'HISTORY_MISMATCH')
            timers[extracted['timer_id']] = event_id
        elif kind in ('TimerFired', 'TimerCanceled'):
            linked('started_event_id', ('TimerStarted',))
            _d2_equal(timers.get(extracted['timer_id']), extracted['started_event_id'], 'HISTORY_LINKAGE')
            _d2_require(extracted['timer_id'] not in ended_timers, 'HISTORY_LINKAGE')
            ended_timers.add(extracted['timer_id'])
            if kind == 'TimerCanceled':
                linked('workflow_task_completed_event_id', ('WorkflowTaskCompleted',))
        indexed[event_id] = event
    _d2_equal(start_count, 1, 'HISTORY_MISMATCH')
    _d2_equal(counts.get('WorkflowExecutionCompleted', 0), int(final), 'HISTORY_MISMATCH')
    if final:
        _d2_equal(counts.get('ActivityTaskScheduled', 0), len(commands), 'HISTORY_MISMATCH')
        _d2_equal(counts.get('ActivityTaskStarted', 0), len(commands), 'HISTORY_MISMATCH')
        _d2_equal(counts.get('ActivityTaskCompleted', 0) + counts.get('ActivityTaskFailed', 0), len(commands), 'HISTORY_MISMATCH')
        _d2_equal(counts.get('WorkflowExecutionUpdateAccepted', 0), int(mission == DAG2_MISSIONS[1]), 'UPDATE_MISMATCH')
        _d2_equal(counts.get('WorkflowExecutionUpdateCompleted', 0), int(mission == DAG2_MISSIONS[1]), 'UPDATE_MISMATCH')
        _d2_equal(counts.get('WorkflowExecutionCancelRequested', 0), int(mission == DAG2_MISSIONS[2]), 'CANCEL_MISMATCH')
    _d2_equal(projection, snapshot['events'], 'HISTORY_PROJECTION_MISMATCH')
    _d2_equal(len(projection), snapshot['history_event_count'], 'HISTORY_MISMATCH')
    _d2_equal(projection[-1]['event_id'], snapshot['last_event_id'], 'HISTORY_MISMATCH')
    return indexed


def _d2_causality(trace, environment, originals, cleanup, replays, histories):
    rows, commands, operations = trace['events'], trace['commands'], trace['rpc_operations']
    by_seq = {r['seq']: r for r in rows}
    rpc = {r['operation_id']: r for r in operations}
    exact_kind_counts = {'bootstrap_constructed': 4, 'worker_stop_requested': 8, 'worker_stop_completed': 8, 'activity_executor_completed': 4, 'replay_begin': 2, 'replay_end': 2, 'update_submit': 4, 'update_handle_returned': 4, 'update_refusal_observed': 2, 'update_result_observed': 2, 'cancel_submit': 1, 'cancel_acknowledged': 1, 'cancel_recorded_observed': 1, 'snapshot_retained': 7}
    for kind, expected_count in exact_kind_counts.items():
        _d2_equal(sum(r['kind'] == kind for r in rows), expected_count, 'COUNTER_MISMATCH')
    _d2_equal(sum(r['kind'] == 'update_accepted_observed' for r in rows), 2, 'UPDATE_MISMATCH')
    for update in trace['updates']:
        if update['outcome'] == 'VALIDATOR_REFUSED':
            _d2_require(update['operation_id'] in rpc and update['operation_id'] + '-result' in rpc, 'UPDATE_MISMATCH')
    for mission in DAG2_MISSIONS:
        _d2_require(sum(r['kind'] == 'result' and r['mission'] == mission for r in operations) == 1, 'RPC_UNCONFIRMED')
    _d2_equal({r['operation_id'] for r in operations if r['kind'] == 'start_update'}, {'update-stale', 'update-original', 'update-repeat-same-id', 'update-distinct-busy'}, 'UPDATE_MISMATCH')
    # Unit and observed classes differ in origin authority, never scenario obligations.
    mandatory_results = {'update-stale-result', 'update-distinct-busy-result', 'update-original-result', 'update-get-completed'}
    result_ids = {r['operation_id'] for r in operations if r['kind'] == 'update_result'}
    _d2_equal(result_ids, mandatory_results, 'UPDATE_MISMATCH')
    def event(seq, kind=None, mission=None, operation=None):
        _d2_require(seq in by_seq, 'CAUSAL_ORDER')
        e = by_seq[seq]
        if kind is not None:
            _d2_equal(e['kind'], kind, 'CAUSAL_ORDER')
        if mission is not None:
            _d2_equal(e['mission'], mission, 'RUN_BINDING')
        if operation is not None:
            _d2_equal(e['operation_id'], operation, 'UPDATE_MISMATCH')
        return e
    def unique(kind, mission=None, node=None, operation=None):
        matches = [r for r in rows if r['kind'] == kind and (mission is None or r['mission'] == mission) and (node is None or r['node'] == node) and (operation is None or r['operation_id'] == operation)]
        _d2_require(len(matches) == 1, 'CAUSAL_ORDER')
        return matches[0]
    for operation in operations:
        for key, kind in [('issued_seq', 'rpc_issued'), ('settled_seq', 'rpc_settled')]:
            event(operation[key], kind, operation['mission'], operation['operation_id'])
    # Pending task and in-flight counts are reconstructed, never accepted from cleanup alone.
    pending, in_flight, active_updates = set(), set(), set()
    count = {k: 0 for k in trace['aggregate_counts']}
    command_by_entry = {c['entry_seq']: c for c in commands}
    command_by_return = {c['return_seq']: c for c in commands}
    command_by_schedule = {c['schedule_observed_seq']: c for c in commands}
    increments = {'seed_put_return': 'seed_puts', 'workflow_start_acknowledged': 'workflow_starts', 'activity_enter': 'activity_entries', 'adapter_return': 'activity_returns', 'runtime_enter': 'runtime_entries', 'runtime_return': 'runtime_returns', 'handler_enter': 'handler_entries', 'handler_return': 'handler_returns', 'result_put_return': 'result_puts', 'verification_read': 'verification_cas_reads'}
    last_reads = 0
    command_read_baseline = {}
    optional_observers = set()
    for row in rows:
        seq, kind, op = row['seq'], row['kind'], row['operation_id']
        if kind == 'rpc_issued':
            _d2_require(op in rpc and op not in pending and rpc[op]['issued_seq'] == seq, 'RPC_UNCONFIRMED')
            pending.add(op)
        elif kind == 'rpc_settled':
            _d2_require(op in pending and rpc[op]['settled_seq'] == seq, 'RPC_UNCONFIRMED')
            pending.remove(op)
        if kind == 'activity_enter':
            _d2_require(seq in command_by_entry and not in_flight, 'COUNTER_MISMATCH')
            cmd = command_by_entry[seq]
            in_flight.add(cmd['activity_id'])
            command_read_baseline[cmd['activity_id']] = last_reads
        if kind == 'adapter_return':
            _d2_require(seq in command_by_return, 'COUNTER_MISMATCH')
            cmd = command_by_return[seq]
            _d2_require(cmd['activity_id'] in in_flight, 'COUNTER_MISMATCH')
            reads = 2 if cmd['kind'] == 'execute' and cmd['node'] == 'B' else 1
            _d2_equal(row['counts']['endpoint_cas_reads'] - command_read_baseline[cmd['activity_id']], reads, 'COUNTER_MISMATCH')
            in_flight.remove(cmd['activity_id'])
        if kind in increments:
            count[increments[kind]] += 1
        if seq in command_by_schedule:
            count['activity_schedules'] += 1
        reads = row['counts']['endpoint_cas_reads']
        _d2_require(type(reads) is int and reads >= last_reads, 'COUNTER_MISMATCH')
        if reads != last_reads:
            _d2_require(bool(in_flight) or kind == 'adapter_return', 'COUNTER_MISMATCH')
        last_reads = reads
        count['endpoint_cas_reads'] = reads
        count['pending_rpc_tasks'] = len(pending)
        count['in_flight_calls'] = len(in_flight)
        _d2_equal(row['counts'], count, 'COUNTER_MISMATCH')
        if kind == 'update_accepted_observed':
            raw_event = histories[row['mission']].get(row['history_event_id'], {})
            _d2_require(raw_event.get('event_type') == 'WorkflowExecutionUpdateAccepted', 'UPDATE_MISMATCH')
            active_updates.add((row['mission'], raw_event['extracted']['update_id']))
        elif kind == 'update_result_observed':
            owner = rpc.get(op)
            if owner is not None and owner['operation_id'] in ('update-original-result', 'update-get-completed'):
                active_updates.discard((row['mission'], owner['update_id']))
        if kind in ('worker_stop_requested', 'worker_stop_completed', 'activity_executor_completed'):
            _d2_require(not pending and not in_flight and not active_updates and count['handler_entries'] == count['handler_returns'] and count['runtime_entries'] == count['runtime_returns'], 'CLEANUP_UNCONFIRMED')
        if kind == 'activity_terminal_observed':
            owner = rpc.get(op)
            _d2_require(owner is not None and owner['kind'] == 'history' and owner['mission'] == row['mission'] and owner['settled_seq'] < seq, 'HISTORY_LINKAGE')
            _d2_equal(by_seq[owner['settled_seq']]['history_event_id'], row['history_event_id'], 'HISTORY_LINKAGE')
            _d2_require(histories[row['mission']].get(row['history_event_id'], {}).get('event_type') in ('ActivityTaskCompleted', 'ActivityTaskFailed'), 'HISTORY_LINKAGE')
        elif kind in ('update_accepted_observed', 'cancel_recorded_observed'):
            expected = 'WorkflowExecutionUpdateAccepted' if kind == 'update_accepted_observed' else 'WorkflowExecutionCancelRequested'
            _d2_equal(histories[row['mission']].get(row['history_event_id'], {}).get('event_type'), expected, 'UPDATE_MISMATCH' if kind == 'update_accepted_observed' else 'CANCEL_MISMATCH')
            _d2_require(any(r['kind'] == 'history' and r['mission'] == row['mission'] and r['settled_seq'] < seq and type(by_seq[r['settled_seq']]['history_event_id']) is int and by_seq[r['settled_seq']]['history_event_id'] >= row['history_event_id'] for r in operations), 'HISTORY_LINKAGE')
        elif kind in ('update_result_observed', 'query_observed'):
            owner = rpc.get(op)
            _d2_require(owner is not None and owner['kind'] == ('update_result' if kind == 'update_result_observed' else 'query') and owner['mission'] == row['mission'] and owner['settled_seq'] < seq, 'UPDATE_MISMATCH' if kind == 'update_result_observed' else 'RPC_UNCONFIRMED')
            _d2_require((kind, op) not in optional_observers, 'RPC_UNCONFIRMED')
            optional_observers.add((kind, op))
        elif kind == 'workflow_terminal_observed':
            owner = rpc.get(op)
            _d2_require(owner is not None and owner['kind'] == 'history' and owner['mission'] == row['mission'] and owner['outcome'] == 'SUCCESS' and owner['settled_seq'] < seq, 'RPC_UNCONFIRMED')
            _d2_require((kind, op) not in optional_observers, 'RPC_UNCONFIRMED')
            optional_observers.add((kind, op))
            _d2_equal(histories[row['mission']].get(row['history_event_id'], {}).get('event_type'), 'WorkflowExecutionCompleted', 'HISTORY_LINKAGE')
            _d2_equal(by_seq[owner['settled_seq']]['history_event_id'], row['history_event_id'], 'HISTORY_LINKAGE')
    _d2_require(not pending and not in_flight, 'RPC_UNCONFIRMED')
    _d2_equal(count, trace['aggregate_counts'], 'COUNTER_MISMATCH')
    _d2_equal(len([r for r in rows if r['kind'] == 'activity_terminal_observed']), 9, 'HISTORY_LINKAGE')
    for command in commands:
        mission, node = command['mission'], command['node']
        enter = event(command['entry_seq'], 'activity_enter', mission)
        returned = event(command['return_seq'], 'adapter_return', mission)
        for row in (enter, returned):
            _d2_equal(row['node'], node, 'HISTORY_LINKAGE')
            _d2_equal(row['worker_generation'], command['worker_generation'], 'BOOTSTRAP_MISMATCH')
        schedule = event(command['schedule_observed_seq'], 'rpc_settled', mission)
        owner = rpc.get(schedule['operation_id'])
        _d2_require(owner is not None and owner['kind'] == 'history' and owner['settled_seq'] == schedule['seq'], 'HISTORY_LINKAGE')
        _d2_equal(schedule['history_event_id'], command['scheduled_event_id'], 'HISTORY_LINKAGE')
        terminal = event(command['terminal_observed_seq'], 'activity_terminal_observed', mission)
        _d2_equal(terminal['history_event_id'], command['terminal_event_id'], 'HISTORY_LINKAGE')
        worker = [r for r in rows if r['kind'] == 'worker_start' and r['worker_generation'] == command['worker_generation']]
        _d2_require(len(worker) == 1 and worker[0]['seq'] < enter['seq'], 'BOOTSTRAP_MISMATCH')
        lifetimes = [r for r in cleanup['worker_stops'] if r['generation'] in (command['worker_generation'], command['worker_generation'] - 1)]
        _d2_require(len(lifetimes) == 2 and all(terminal['seq'] < r['stop_requested_seq'] for r in lifetimes), 'CLEANUP_UNCONFIRMED')
        if command['kind'] == 'execute':
            chain = [unique(k, mission, node) for k in ('runtime_enter', 'handler_enter', 'handler_return', 'runtime_return', 'result_put_return')]
            _d2_require(enter['seq'] < chain[0]['seq'] < chain[1]['seq'] < chain[2]['seq'] < chain[3]['seq'] < chain[4]['seq'] < returned['seq'], 'ORIGIN_ORDER')
            if command['fault'] != 'NONE':
                fault = unique('controlled_response_failure', mission, node)
                _d2_require(returned['seq'] < fault['seq'] < terminal['seq'], 'ORIGIN_ORDER')
    for original in originals['originals']:
        for key, kind in [('put_return_seq', 'result_put_return'), ('capture_seq', 'original_capture'), ('adapter_return_seq', 'adapter_return')]:
            row = event(original[key], kind, original['mission'])
            _d2_equal(row['node'], original['node'], 'ORIGIN_MISMATCH')
    _d2_require(not any(r['kind'] == 'original_capture' and r['mission'] == DAG2_MISSIONS[2] for r in rows), 'NO_REF_REDISCOVERY')
    for bootstrap in environment['bootstrap']:
        row = event(bootstrap['constructed_seq'], 'bootstrap_constructed', bootstrap['mission'])
        _d2_equal(row['worker_generation'], bootstrap['generation'], 'BOOTSTRAP_MISMATCH')
        row = event(bootstrap['started_seq'], 'worker_start', bootstrap['mission'])
        _d2_equal(row['worker_generation'], bootstrap['generation'], 'BOOTSTRAP_MISMATCH')
    for stop in cleanup['worker_stops']:
        for key, kind in [('start_seq', 'worker_start'), ('stop_requested_seq', 'worker_stop_requested'), ('stop_completed_seq', 'worker_stop_completed')]:
            row = event(stop[key], kind, stop['mission'])
            _d2_equal(row['worker_generation'], stop['generation'], 'CLEANUP_UNCONFIRMED')
        quiet = event(stop['quiescent_snapshot_seq'], 'snapshot_retained', stop['mission'])
        _d2_require(quiet['counts']['pending_rpc_tasks'] == quiet['counts']['in_flight_calls'] == 0 and quiet['counts']['handler_entries'] == quiet['counts']['handler_returns'], 'CLEANUP_UNCONFIRMED')
        _d2_require(all(c['terminal_observed_seq'] < stop['stop_requested_seq'] for c in commands if min(c['entry_seq'], c['schedule_observed_seq']) < stop['stop_requested_seq']), 'CLEANUP_UNCONFIRMED')
        if stop['kind'] == 'activity':
            completions = [r for r in rows if r['kind'] == 'activity_executor_completed' and r['worker_generation'] == stop['generation']]
            _d2_require(len(completions) == 1 and completions[0]['seq'] > stop['stop_completed_seq'], 'CLEANUP_UNCONFIRMED')
    for update in trace['updates']:
        operation_id = update['operation_id']
        owner = rpc.get(operation_id)
        _d2_require(owner is not None and owner['update_id'] == update['update_id'], 'UPDATE_MISMATCH')
        if update['outcome'] == 'SAME_COMPLETED_RESULT':
            observed = unique('update_result_observed', operation=operation_id)
            _d2_require(owner['kind'] == 'update_result' and update['submit_seq'] == owner['issued_seq'] < owner['settled_seq'] < observed['seq'], 'UPDATE_MISMATCH')
            continue
        submit = event(update['submit_seq'], 'update_submit', DAG2_MISSIONS[1], operation_id)
        returned = unique('update_handle_returned', operation=operation_id)
        _d2_require(owner['kind'] == 'start_update' and owner['outcome'] == 'SUCCESS' and submit['seq'] < owner['issued_seq'] < owner['settled_seq'] < returned['seq'], 'UPDATE_MISMATCH')
        if update['outcome'] != 'VALIDATOR_REFUSED':
            index = next(i for i, r in enumerate(trace['updates']) if r['operation_id'] == operation_id)
            next_submit = trace['updates'][index + 1]['submit_seq']
            accepted = [r for r in rows if r['kind'] == 'update_accepted_observed' and returned['seq'] < r['seq'] < next_submit]
            _d2_require(len(accepted) == 1, 'UPDATE_MISMATCH')
            observation = accepted[0]
            history_owner = rpc.get(observation['operation_id'])
            _d2_require(history_owner is not None and history_owner['kind'] == 'history' and history_owner['mission'] == owner['mission'] and history_owner['run_id'] == owner['run_id'] and history_owner['outcome'] == 'SUCCESS' and history_owner['settled_seq'] < observation['seq'], 'UPDATE_MISMATCH')
            _d2_equal(observation['history_event_id'], update['accepted_event_id'], 'UPDATE_MISMATCH')
            covered = by_seq[history_owner['settled_seq']]['history_event_id']
            _d2_require(type(covered) is int and covered >= update['accepted_event_id'], 'UPDATE_MISMATCH')
            if update['operation_id'] == 'update-repeat-same-id':
                _d2_equal(submit['counts'], observation['counts'], 'UPDATE_MISMATCH')
        if update['outcome'] == 'VALIDATOR_REFUSED':
            result = rpc.get(operation_id + '-result')
            refusal = unique('update_refusal_observed', operation=operation_id)
            _d2_require(result is not None and result['kind'] == 'update_result' and result['outcome'] == 'EXPECTED_VALIDATOR_REFUSAL' and result['update_id'] == update['update_id'] and result['mission'] == owner['mission'] and result['run_id'] == owner['run_id'] and result['workflow_id'] == owner['workflow_id'] and returned['seq'] < result['issued_seq'] < result['settled_seq'] < refusal['seq'], 'UPDATE_MISMATCH')
            _d2_equal(submit['counts'], refusal['counts'], 'UPDATE_MISMATCH')
    original_result = rpc['update-original-result']
    completed_result = rpc['update-get-completed']
    original_observation = unique('update_result_observed', operation='update-original-result')
    inspection = next(c for c in commands if c['kind'] == 'reconcile_inspect')
    _d2_require(inspection['return_seq'] < original_result['settled_seq'] < original_observation['seq'] < completed_result['issued_seq'], 'UPDATE_MISMATCH')
    _d2_require(environment['bootstrap'][2]['started_seq'] < original_result['issued_seq'], 'UPDATE_MISMATCH')
    _d2_equal(original_result['update_id'], completed_result['update_id'], 'UPDATE_MISMATCH')
    _d2_equal(original_result['run_id'], completed_result['run_id'], 'RUN_BINDING')
    cancels = [r for r in operations if r['kind'] == 'cancel']
    _d2_require(len(cancels) == 1 and cancels[0]['mission'] == DAG2_MISSIONS[2], 'CANCEL_MISMATCH')
    cancel = cancels[0]
    submit = unique('cancel_submit', DAG2_MISSIONS[2])
    ack = unique('cancel_acknowledged', DAG2_MISSIONS[2])
    recorded = unique('cancel_recorded_observed', DAG2_MISSIONS[2])
    no_ref_command = commands[-1]
    _d2_require(no_ref_command['terminal_observed_seq'] < submit['seq'] < cancel['issued_seq'] < cancel['settled_seq'] < ack['seq'] < recorded['seq'], 'CANCEL_MISMATCH')
    _d2_require(submit['counts']['in_flight_calls'] == submit['counts']['pending_rpc_tasks'] == 0 and submit['counts']['handler_entries'] == submit['counts']['handler_returns'], 'CLEANUP_UNCONFIRMED')
    for replay in replays['replays']:
        before = event(replay['begin_seq'], 'replay_begin', replay['mission'])
        after = event(replay['end_seq'], 'replay_end', replay['mission'])
        _d2_equal(before['counts'], replay['counts_before'], 'REPLAY_MISMATCH')
        _d2_equal(after['counts'], replay['counts_after'], 'REPLAY_MISMATCH')
        _d2_require(all(r['counts'] == before['counts'] for r in rows if before['seq'] <= r['seq'] <= after['seq']), 'REPLAY_MISMATCH')
        generations = (1, 2) if replay['mission'] == DAG2_MISSIONS[0] else (5, 6)
        _d2_require(all(s['stop_completed_seq'] < before['seq'] for s in cleanup['worker_stops'] if s['generation'] in generations), 'REPLAY_MISMATCH')
    _d2_equal(len([r for r in rows if r['kind'] == 'worker_start']), 8, 'BOOTSTRAP_MISMATCH')
    _d2_equal(len([r for r in rows if r['kind'] == 'server_start']), 1, 'CLEANUP_UNCONFIRMED')
    _d2_equal(len([r for r in rows if r['kind'] == 'server_stop_completed']), 1, 'CLEANUP_UNCONFIRMED')
    _d2_equal([(r['mission'], r['node']) for r in rows if r['kind'] == 'verification_read'], [(m, n) for m in DAG2_MISSIONS[:2] for n in ('A', 'B')], 'NO_REF_REDISCOVERY')
    _d2_equal(len([r for r in rows if r['kind'] == 'original_capture']), 4, 'ORIGIN_MISMATCH')
    _d2_equal(len([r for r in rows if r['kind'] == 'controlled_response_failure']), 2, 'ORIGIN_ORDER')
    # Every mission is one immutable start followed by its preconstructed pair;
    # preceding workers and their replay are finished before another mission.
    for index, mission in enumerate(DAG2_MISSIONS):
        starts = [r for r in operations if r['kind'] == 'start' and r['mission'] == mission]
        _d2_require(len(starts) == 1, 'RPC_RESUBMITTED')
        start = starts[0]
        issued = unique('workflow_start_issued', mission)
        ack = unique('workflow_start_acknowledged', mission)
        seed = unique('seed_put_return', mission)
        bootstrap = environment['bootstrap'][(0, 1, 3)[index]]
        wf_start = [r for r in rows if r['kind'] == 'worker_start' and r['worker_generation'] == bootstrap['generation'] - 1]
        _d2_require(len(wf_start) == 1 and seed['seq'] < issued['seq'] < start['issued_seq'] < start['settled_seq'] < ack['seq'] < bootstrap['constructed_seq'] < wf_start[0]['seq'] < bootstrap['started_seq'], 'BOOTSTRAP_MISMATCH')
        if index:
            previous = DAG2_MISSIONS[index - 1]
            _d2_require(all(stop['stop_completed_seq'] < seed['seq'] for stop in cleanup['worker_stops'] if stop['mission'] == previous), 'CLEANUP_UNCONFIRMED')
            _d2_require(all(replay['end_seq'] < seed['seq'] for replay in replays['replays'] if replay['mission'] == previous), 'REPLAY_MISMATCH')
    replacement = environment['bootstrap'][2]
    _d2_require(all(stop['stop_completed_seq'] < replacement['constructed_seq'] for stop in cleanup['worker_stops'] if stop['generation'] in (3, 4)), 'BOOTSTRAP_MISMATCH')
    snapshot_seqs = [r['observation_seq'] for r in trace['snapshots']]
    _d2_require(snapshot_seqs == sorted(set(snapshot_seqs)), 'CAUSAL_ORDER')
    _d2_equal(set(snapshot_seqs), {r['seq'] for r in rows if r['kind'] == 'snapshot_retained'}, 'HISTORY_LINKAGE')
    prior_snapshots = {}
    for snapshot in trace['snapshots']:
        retained = event(snapshot['observation_seq'], 'snapshot_retained', snapshot['mission'])
        _d2_require(retained['counts']['pending_rpc_tasks'] == retained['counts']['in_flight_calls'] == 0, 'CLEANUP_UNCONFIRMED')
        previous = prior_snapshots.get(snapshot['mission'], 0)
        for kind in ('history', 'query'):
            owned = [r for r in operations if r['mission'] == snapshot['mission'] and r['kind'] == kind and previous < r['issued_seq'] < r['settled_seq'] < retained['seq']]
            _d2_require(bool(owned), 'RPC_UNCONFIRMED')
        owner = rpc.get(retained['operation_id'])
        _d2_require(owner is not None and owner['kind'] == 'history' and owner['mission'] == snapshot['mission'] and owner['outcome'] == 'SUCCESS' and previous < owner['issued_seq'] < owner['settled_seq'] < retained['seq'], 'HISTORY_LINKAGE')
        _d2_equal(retained['history_event_id'], snapshot['last_event_id'], 'HISTORY_LINKAGE')
        _d2_equal(by_seq[owner['settled_seq']]['history_event_id'], snapshot['last_event_id'], 'HISTORY_LINKAGE')
        prior_snapshots[snapshot['mission']] = retained['seq']
    snapshots = {r['snapshot_id']: r['observation_seq'] for r in trace['snapshots']}
    stops = {r['generation']: r for r in cleanup['worker_stops']}
    _d2_require(snapshots['normal-final'] < stops[2]['stop_requested_seq'], 'CLEANUP_UNCONFIRMED')
    _d2_require(snapshots['reconcile-unknown-before-stop'] < stops[4]['stop_requested_seq'] < stops[3]['stop_completed_seq'] < replacement['constructed_seq'] < snapshots['reconcile-unknown-after-replacement'] < trace['updates'][0]['submit_seq'], 'CAUSAL_ORDER')
    _d2_require(trace['updates'][1]['submit_seq'] < snapshots['reconcile-update-queued'] < replacement['started_seq'] < snapshots['reconcile-final'], 'CAUSAL_ORDER')
    _d2_require(snapshots['no-ref-unknown'] < unique('cancel_submit', DAG2_MISSIONS[2])['seq'] < unique('cancel_recorded_observed', DAG2_MISSIONS[2])['seq'] < snapshots['no-ref-cancel-final'], 'CAUSAL_ORDER')
    stop_sequences = [r['stop_requested_seq'] for r in cleanup['worker_stops']]
    _d2_require(stop_sequences == sorted(set(stop_sequences)), 'CLEANUP_UNCONFIRMED')
    server_start = unique('server_start')
    server_request = unique('server_stop_requested')
    server_stop = unique('server_stop_completed')
    _d2_require(cleanup['worker_stops'][-1]['stop_completed_seq'] < server_request['seq'] < server_stop['seq'], 'CLEANUP_UNCONFIRMED')
    elapsed = lambda a, b: max(0, (b['monotonic_ns'] - a['monotonic_ns']) // 1000000)
    _d2_require(elapsed(server_request, server_stop) <= cleanup['server_shutdown_elapsed_ms'] + 2, 'DEADLINE_EXHAUSTED')
    _d2_require(elapsed(server_start, server_stop) <= 210000, 'DEADLINE_EXHAUSTED')
    no_ref_result = next(r for r in operations if r['kind'] == 'result' and r['mission'] == DAG2_MISSIONS[2])
    scenario_last_seq = max(no_ref_result['settled_seq'], snapshots['no-ref-cancel-final'], *(r['end_seq'] for r in replays['replays']))
    observed_scenario_ms = elapsed(server_start, by_seq[scenario_last_seq])
    _d2_require(observed_scenario_ms <= 150000 and observed_scenario_ms <= cleanup['scenario_elapsed_ms'] + 2, 'DEADLINE_EXHAUSTED')
    # The observed no-ref completion is a lower bound on scenario exit; the
    # one declared elapsed phase may account for final verification work only.
    _d2_require(elapsed(server_start, server_stop) <= cleanup['scenario_elapsed_ms'] + cleanup['observation_cleanup_elapsed_ms'] + cleanup['final_stop_elapsed_ms'] + 2, 'DEADLINE_EXHAUSTED')
    _d2_require(by_seq[cleanup['worker_stops'][6]['stop_requested_seq']]['seq'] > scenario_last_seq, 'CLEANUP_UNCONFIRMED')
    for index, stop in enumerate(cleanup['worker_stops']):
        begin, end = by_seq[stop['stop_requested_seq']], by_seq[stop['stop_completed_seq']]
        _d2_require(elapsed(begin, end) <= stop['shutdown_elapsed_ms'] + stop['run_task_wait_elapsed_ms'] + 2, 'DEADLINE_EXHAUSTED')
        if index < 6:
            _d2_require(elapsed(server_start, end) <= cleanup['scenario_elapsed_ms'] + 2 and elapsed(server_start, end) <= 150000, 'DEADLINE_EXHAUSTED')
            _d2_require(stop['cumulative_stop_deadline_remaining_ms'] + elapsed(server_start, begin) <= 150002, 'DEADLINE_EXHAUSTED')
        if index in (1, 2, 3, 4, 5, 7):
            _d2_require(stop['cumulative_stop_deadline_remaining_ms'] <= cleanup['worker_stops'][index - 1]['cumulative_stop_deadline_remaining_ms'], 'DEADLINE_EXHAUSTED')
    _d2_require(elapsed(by_seq[cleanup['worker_stops'][6]['stop_requested_seq']], server_stop) <= cleanup['final_stop_elapsed_ms'] + 2, 'DEADLINE_EXHAUSTED')


def _d2_source_manifest(value, environment, expected_identity, intent, reviewed=None, reviewed_sha=None):
    _d2_shape(value, 'schema_version commit tree files')
    _d2_equal(value['schema_version'], DAG2_PREFIX + 'source-manifest.v1', 'SOURCE_MISMATCH')
    for key in ('commit', 'tree'):
        _d2_equal(value[key], expected_identity[key], 'SOURCE_MISMATCH', 'preflight')
    rows = value['files']
    _d2_require(type(rows) is list and 1 <= len(rows) <= 512, 'SOURCE_MISMATCH')
    for row in rows:
        _d2_shape(row, 'path mode size_bytes sha256')
        dag2_validate_schema(row, 'path_digest')
        _d2_require(not row['path'].startswith('/') and all(s not in ('', '.', '..') for s in row['path'].split('/')), 'SOURCE_MISMATCH')
    paths = [r['path'] for r in rows]
    _d2_require(paths == sorted(set(paths)), 'SOURCE_MISMATCH')
    if intent == 'UNIT_RECORD_CONSISTENCY':
        _d2_equal(paths, list(DAG2_SOURCE_PATHS), 'SOURCE_MISMATCH')
        immutable = DAG2_UNIT_IMMUTABLE_SOURCE
    else:
        _d2_require(type(reviewed) is dict and type(reviewed_sha) is str, 'SOURCE_MISMATCH', 'preflight')
        _d2_equal(_d2_hash(reviewed, 131072), reviewed_sha, 'SOURCE_MISMATCH', 'preflight')
        _d2_equal(value, reviewed, 'SOURCE_MISMATCH', 'preflight')
        immutable = {row['path']: (row['sha256'], row['size_bytes'], row['mode']) for row in reviewed['files']}
        _d2_require(type(DAG2_REVIEWED_WORKFLOW_SHA256) is str and re.fullmatch('[0-9a-f]{64}', DAG2_REVIEWED_WORKFLOW_SHA256) is not None, 'WORKFLOW_MISMATCH', 'preflight')
        _d2_equal(expected_identity['workflow_sha256'], DAG2_REVIEWED_WORKFLOW_SHA256, 'WORKFLOW_MISMATCH', 'preflight')
        for path, expected in OWNER_SHA256.items():
            _d2_require(path in immutable and immutable[path][0] == expected, 'OWNER_MISMATCH', 'preflight')
        for path in ('src/opendot_engineering/adapters/temporal_activity.py', 'src/opendot_engineering/adapters/temporal_workflow.py', 'docs/decisions/008-fixed-dependent-temporal-recovery.md'):
            _d2_equal(immutable.get(path), DAG2_UNIT_IMMUTABLE_SOURCE[path], 'OWNER_MISMATCH', 'preflight')
    for row in rows:
        if row['path'] in immutable:
            _d2_equal((row['sha256'], row['size_bytes'], row['mode']), immutable[row['path']], 'OWNER_MISMATCH', 'preflight')
    by_path = {r['path']: r for r in rows}
    _d2_require(set(DAG2_SOURCE_CLOSURE) <= set(by_path), 'SOURCE_MISMATCH')
    _d2_equal(environment['source_closure'], [by_path[p] for p in DAG2_SOURCE_CLOSURE], 'SOURCE_MISMATCH')
    _d2_equal(by_path['.github/workflows/temporal-server.yml']['sha256'], expected_identity['workflow_sha256'], 'WORKFLOW_MISMATCH')
    return immutable


def validate_dag2_review_inputs(manifest, identity, expected_manifest_sha256):
    """Pre-acquisition consistency gate for explicit externally reviewed inputs.

    These inputs never authenticate themselves. The same exact contents must
    later pass independent GitHub readback before hosted origin is accepted.
    """
    dag2_validate_schema(identity, 'identity')
    _d2_shape(manifest, 'schema_version commit tree files')
    _d2_require(type(manifest['files']) is list and len(manifest['files']) <= 512, 'SOURCE_MISMATCH')
    rows = {r['path']: r for r in manifest['files'] if type(r) is dict and type(r.get('path')) is str}
    _d2_require(set(DAG2_SOURCE_CLOSURE) <= set(rows), 'SOURCE_MISMATCH')
    environment = {'source_closure': [rows[p] for p in DAG2_SOURCE_CLOSURE]}
    _d2_source_manifest(manifest, environment, identity, 'HOSTED_CANDIDATE_ADMISSION', manifest, expected_manifest_sha256)
    _d2_source_bytes(manifest)
    return 'REVIEWED_INPUT_CONSISTENCY_ONLY'


def _d2_source_bytes(manifest):
    """Read only explicit reviewed tracked filenames, never discover a source tree."""
    snapshot = {}
    for row in manifest['files']:
        path = ROOT / row['path']
        for part in (path, *path.parents):
            if part == ROOT.parent:
                break
            _d2_require(not part.is_symlink(), 'SOURCE_MISMATCH')
        raw = read_bytes(path, 4194304)
        try:
            mode = '100755' if path.stat().st_mode & 0o111 else '100644'
        except OSError:
            _d2_fail('READ_FAILED')
        _d2_equal((hashlib.sha256(raw).hexdigest(), len(raw), mode), (row['sha256'], row['size_bytes'], row['mode']), 'SOURCE_MISMATCH', 'preflight')
        snapshot[row['path']] = raw
    return snapshot


def _d2_phase_receipts(documents, expected):
    _d2_require(type(expected) is dict and set(expected) == {'shared', 'dag_sdk'}, 'COLLECTION_MISMATCH')
    for kind, filename in [('shared', 'shared-unit-summary.json'), ('dag_sdk', 'dag-sdk-summary.json')]:
        row = documents[filename]
        _d2_shape(row, 'schema_version expected_node_count collected_node_count executed_node_count passed_count failed_count error_count skipped_count collection_exit_code test_exit_code collection_sha256 acceptance reason_code')
        count = expected[kind]['expected_node_count']
        _d2_require(type(count) is int and 1 <= count <= 4096, 'COLLECTION_MISMATCH')
        for key in ('expected_node_count', 'collected_node_count', 'executed_node_count', 'passed_count'):
            _d2_equal(row[key], count, 'COLLECTION_MISMATCH')
        for key in ('failed_count', 'error_count', 'skipped_count', 'collection_exit_code', 'test_exit_code'):
            _d2_equal(row[key], 0, 'TEST_FAILED')
        _d2_equal(row['schema_version'], 'opendot.temporal.unit-gate.v1', 'COLLECTION_MISMATCH')
        _d2_equal(row['collection_sha256'], expected[kind]['collection_sha256'], 'COLLECTION_MISMATCH')
        _d2_equal(row['acceptance'], 'PASS', 'TEST_FAILED')
        _d2_equal(row['reason_code'], 'OK', 'TEST_FAILED')
    _d2_equal(expected['dag_sdk'], DAG2_DAG_RECEIPT, 'COLLECTION_MISMATCH')
    acquisition = documents['acquisition-receipt.json']
    _d2_shape(acquisition, 'schema_version platform cli_version archive checksums files')
    for key, expected_value in {'schema_version': 'opendot.temporal.cli-acquisition.v1', 'platform': 'linux-x86_64', 'cli_version': '1.9.1'}.items():
        _d2_equal(acquisition[key], expected_value, 'ACQUISITION_UNVERIFIED')
    for key, name, expected_hash in [('archive', 'temporal_cli_1.9.1_linux_amd64.tar.gz', CLI_ARCHIVE_SHA256), ('checksums', 'checksums.txt', CLI_CHECKSUMS_SHA256)]:
        row = acquisition[key]
        _d2_shape(row, 'name url sha256 size_bytes')
        _d2_equal(row['name'], name, 'ACQUISITION_UNVERIFIED')
        _d2_equal(row['url'], 'https://github.com/temporalio/cli/releases/download/v1.9.1/' + name, 'ACQUISITION_UNVERIFIED')
        _d2_equal(row['sha256'], expected_hash, 'ACQUISITION_UNVERIFIED')
        _d2_require(type(row['size_bytes']) is int and 0 < row['size_bytes'] <= 128 * 1024 * 1024, 'SIZE_LIMIT')
    _d2_shape(acquisition['files'], {'LICENSE', 'temporal'})
    for row in acquisition['files'].values():
        _d2_shape(row, 'sha256 size_bytes')
        digest(row['sha256'])
        _d2_require(type(row['size_bytes']) is int and 0 < row['size_bytes'] <= 256 * 1024 * 1024, 'SIZE_LIMIT')
    pip = documents['pip-report.json']
    _d2_require(type(pip) is dict and pip.get('version') == '1' and type(pip.get('install')) is list and len(pip['install']) == 10, 'VERSION_MISMATCH')
    seen = set()
    for row in pip['install']:
        _d2_require(type(row) is dict and type(row.get('metadata')) is dict and type(row.get('download_info')) is dict, 'VERSION_MISMATCH')
        name, version = row['metadata'].get('name'), row['metadata'].get('version')
        _d2_require(type(name) is str and name in SDK_VERSIONS | TOOL_VERSIONS and name not in seen, 'VERSION_MISMATCH')
        seen.add(name)
        _d2_equal(version, (SDK_VERSIONS | TOOL_VERSIONS)[name], 'VERSION_MISMATCH')
        archive = row['download_info'].get('archive_info', {})
        _d2_equal(archive.get('hashes', {}).get('sha256'), (SDK_HASHES | TOOL_HASHES)[name], 'VERSION_MISMATCH')
        url = row['download_info'].get('url')
        _d2_require(type(url) is str and url.startswith('https://files.pythonhosted.org/') and url.endswith('.whl'), 'VERSION_MISMATCH')


def validate_dag2_records(documents, raw_files, expected_identity, *, validation_intent, expected_unit_receipts=None, require_phase_receipts=False):
    """Shared session/whole-pack semantic checks; no service or origin authentication."""
    try:
        environment = documents['dag2-environment.json']
        trace = documents['dag2-trace.json']
        originals = documents['dag2-originals.json']
        cleanup = documents['dag2-cleanup.json']
        replays = documents['dag2-replays.json']
        context = {'identity': expected_identity, 'source_sha256': environment['complete_tracked_manifest_sha256'], 'bootstraps': environment['bootstrap'], 'originals': originals, 'updates': trace['updates'], 'commands': trace['commands'], 'retained_bodies': {}, 'states': {}}
        for mission, prefix in [('hosted-normal', 'normal'), ('hosted-reconcile', 'reconcile')]:
            for node in ('A', 'B'):
                context['retained_bodies'][mission + '/' + node] = documents[prefix + '-' + node.lower() + '.result.json']
        for snapshot_id in DAG2_SNAPSHOTS:
            context['states'][snapshot_id] = documents[snapshot_id + '.state.json']
        def component(name, value):
            return validate_dag2_component(name, value, context=context, validation_intent=validation_intent)
        component('environment', environment)
        for name, value in [('originals', originals), ('trace', trace), ('replays', replays), ('cleanup', cleanup), ('diagnostic', documents['dag2-diagnostic.json'])]:
            _d2_shape(value, DAG2_SCHEMAS[name]['properties'])
            _d2_equal(value['evidence_class'], environment['evidence_class'], 'INVALID_VALUE')
            _d2_equal(value['schema_version'], DAG2_PREFIX + name + '.v1', 'INVALID_SCHEMA')
        _d2_bytes(trace, 262144)
        _d2_bytes([s['events'] for s in trace['snapshots']], 262144)
        # Bound every retained reference before body linkage; semantics still precede digest checks.
        for original in originals['originals']:
            _d2_reference(original['reference'])
        # Independent original semantics precede changed envelope/history linkage.
        for body in context['retained_bodies'].values():
            component('retained_body', body)
        _d2_require(len(originals['originals']) == 4 and [(r['mission'], r['node']) for r in originals['originals']] == [(m, n) for m in DAG2_MISSIONS[:2] for n in ('A', 'B')], 'ORIGIN_MISMATCH')
        for row in originals['originals']:
            file_id = row['body']['file_id']
            expected_file = ('normal' if row['mission'] == DAG2_MISSIONS[0] else 'reconcile') + '-' + row['node'].lower() + '.result.json'
            _d2_equal(file_id, expected_file, 'PRIVACY_REJECTED')
            body_raw = _d2_bytes(context['retained_bodies'][row['mission'] + '/' + row['node']], 16384)
            if file_id in raw_files:
                _d2_equal(raw_files[file_id], body_raw, 'ORIGINAL_MUTATED')
            component('original', row)
        component('no_ref', originals['no_ref'])
        for state in context['states'].values():
            component('state', state)
        component('aggregate_counts', trace['aggregate_counts'])
        component('events', trace['events'])
        component('rpc_operations', trace['rpc_operations'])
        component('updates', trace['updates'])
        # A's actual inspection completion must precede B's actual schedule.
        for mission in DAG2_MISSIONS[:2]:
            commands = [c for c in trace['commands'] if c['mission'] == mission]
            _d2_require(len(commands) == 4, 'COUNTER_MISMATCH')
            _d2_require(commands[1]['terminal_event_id'] < commands[2]['scheduled_event_id'], 'DEPENDENCY_VIOLATION')
        component('commands', trace['commands'])
        expected_commands = [(DAG2_MISSIONS[0], 'A', 'execute'), (DAG2_MISSIONS[0], 'A', 'normal_inspect'), (DAG2_MISSIONS[0], 'B', 'execute'), (DAG2_MISSIONS[0], 'B', 'normal_inspect'), (DAG2_MISSIONS[1], 'A', 'execute'), (DAG2_MISSIONS[1], 'A', 'reconcile_inspect'), (DAG2_MISSIONS[1], 'B', 'execute'), (DAG2_MISSIONS[1], 'B', 'normal_inspect'), (DAG2_MISSIONS[2], 'A', 'execute')]
        _d2_equal([(c['mission'], c['node'], c['kind']) for c in trace['commands']], expected_commands, 'COUNTER_MISMATCH')
        component('snapshots', trace['snapshots'])
        _d2_equal([s['snapshot_id'] for s in trace['snapshots']], list(DAG2_SNAPSHOTS), 'HISTORY_MISMATCH')
        histories, prior, raw_prior = {}, {}, {}
        for index, snapshot in enumerate(trace['snapshots']):
            name = snapshot['snapshot_id']
            mission = DAG2_MISSIONS[0 if index == 0 else 1 if index <= 4 else 2]
            _d2_equal(snapshot['mission'], mission, 'RUN_BINDING')
            for kind in ('history', 'state'):
                _d2_equal(snapshot[kind]['file_id'], name + '.' + kind + '.json', 'PRIVACY_REJECTED')
                raw = raw_files[snapshot[kind]['file_id']] if snapshot[kind]['file_id'] in raw_files else _d2_bytes(documents[snapshot[kind]['file_id']], 16384)
                if kind == 'state':
                    _d2_equal(raw, _d2_bytes(documents[snapshot[kind]['file_id']], 16384), 'HISTORY_MISMATCH')
                _d2_equal(snapshot[kind]['sha256'], hashlib.sha256(raw).hexdigest(), 'HISTORY_MISMATCH')
                _d2_equal(snapshot[kind]['size_bytes'], len(raw), 'SIZE_LIMIT')
            state = context['states'][name]
            _d2_equal(snapshot['state_revision'], state['revision'], 'HISTORY_MISMATCH')
            _d2_equal(snapshot['state_status'], state['mission_status'], 'HISTORY_MISMATCH')
            final = name in ('normal-final', 'reconcile-final', 'no-ref-cancel-final')
            indexed = _d2_validate_history(snapshot, raw_files[name + '.history.json'], state, context, final=final)
            raw_events = strict_json(raw_files[name + '.history.json'])['events']
            if mission in raw_prior:
                _d2_equal(raw_events[:len(raw_prior[mission])], raw_prior[mission], 'HISTORY_MISMATCH')
            raw_prior[mission] = raw_events
            if mission in prior:
                for event_id, event in prior[mission].items():
                    _d2_equal(indexed.get(event_id), event, 'HISTORY_MISMATCH')
            prior[mission] = indexed
            if final:
                histories[mission] = indexed
            if not final:
                _d2_equal(snapshot['completion_payload_sha256'], None, 'HISTORY_MISMATCH')
        _d2_equal(context['states']['reconcile-unknown-before-stop'], context['states']['reconcile-unknown-after-replacement'], 'HISTORY_MISMATCH')
        _d2_equal(context['states']['reconcile-update-queued']['revision'], 5, 'UPDATE_MISMATCH')
        _d2_require(sum(len(raw_files[n + '.history.json']) for n in DAG2_SNAPSHOTS) <= 14680064, 'SIZE_LIMIT')
        component('cleanup', cleanup)
        component('replays', replays['replays'])
        component('diagnostic', documents['dag2-diagnostic.json'])
        for replay in replays['replays']:
            raw = raw_files[replay['history_file_id']]
            _d2_equal(replay['retained_history_sha256'], hashlib.sha256(raw).hexdigest(), 'REPLAY_MISMATCH')
            snapshot = next(s for s in trace['snapshots'] if s['history']['file_id'] == replay['history_file_id'])
            _d2_equal(replay['completion_payload_sha256'], snapshot['completion_payload_sha256'], 'REPLAY_MISMATCH')
        _d2_causality(trace, environment, originals, cleanup, replays, histories)
        if require_phase_receipts:
            _d2_phase_receipts(documents, expected_unit_receipts)
        return {'record_validation': 'UNIT_RECORD_VALID' if validation_intent == 'UNIT_RECORD_CONSISTENCY' else 'RECORD_VALIDATION_PASS', 'hosted_acceptance': 'REQUIRES_EXTERNAL_GITHUB_READBACK'}
    except GateError as error:
        if not hasattr(error, 'boundary'):
            error.boundary = 'record_validation'
        raise
    except (KeyError, TypeError, IndexError, ValueError, RecursionError):
        _d2_fail('INVALID_SCHEMA')


class _DAG2Validated(dict):
    """Internal validated snapshot, retained only in this verifier process."""
    def __init__(self, result, output, audit=None, snapshot=None, source_manifest=None, source_snapshot=None):
        super().__init__(result)
        self._output_bytes = _d2_bytes(output, 8192)
        self._audit = audit
        self._snapshot = snapshot
        self._source_manifest = source_manifest
        self._source_snapshot = source_snapshot


def _d2_file_limit(name):
    if name.endswith('.history.json'):
        return 2097152
    if name.endswith('.state.json') or name.endswith('.result.json'):
        return 16384
    if name == 'dag2-trace.json':
        return 262144
    if name == 'dag2-diagnostic.json':
        return 4096
    if name in ('required-nodes.txt', 'collected-nodes.txt'):
        return 8192
    return 2097152


def _d2_read(audit, name, maximum):
    _d2_require(type(name) is str and name in set(DAG2_INPUT_FILES) | {'dag2-manifest.json', 'dag2-summary.json', 'dag2-failure-summary.json'}, 'PRIVACY_REJECTED')
    for parent in (audit, *audit.parents):
        _d2_require(not parent.is_symlink(), 'PRIVACY_REJECTED')
    return read_bytes(audit / name, maximum)


def _d2_junit(path):
    root = parse_junit(path, 2097152)
    cases, found = list(root.iter('testcase')), []
    _d2_require(len(cases) == 7, 'JUNIT_IDENTITY')
    for case in cases:
        _d2_require(set(case.attrib) <= {'classname', 'name', 'time', 'file', 'line'}, 'JUNIT_IDENTITY')
        _d2_equal(case.get('classname'), 'tests.acceptance.temporal_dag_recovery_gate', 'JUNIT_IDENTITY')
        name = case.get('name')
        _d2_require(type(name) is str, 'JUNIT_IDENTITY')
        found.append('tests/acceptance/temporal_dag_recovery_gate.py::' + name)
        for child in case:
            _d2_require(child.tag in ('failure', 'error', 'skipped', 'system-out', 'system-err'), 'JUNIT_IDENTITY')
            _d2_require(child.tag != 'skipped', 'TEST_SKIPPED')
            _d2_require(child.tag not in ('failure', 'error'), 'TEST_FAILED')
    _d2_equal(found, list(DAG2_REQUIRED_NODES), 'JUNIT_IDENTITY')


def validate_dag2_audit(audit, expected_identity, *, validation_intent, expected_unit_receipts, untrusted_external_readback=None, reviewed_source_manifest=None, expected_source_manifest_sha256=None):
    """Validate one exact closed 32-file pack; authenticity remains external."""
    audit = Path(audit)
    try:
        if validation_intent == 'EXTERNAL_ORIGIN_GATE_UNTRUSTED_INPUT':
            validate_dag2_component('external_readback', untrusted_external_readback, context={}, validation_intent=validation_intent)
        _d2_require(validation_intent in ('UNIT_RECORD_CONSISTENCY', 'HOSTED_CANDIDATE_ADMISSION'), 'INVALID_VALUE')
        manifest_raw = _d2_read(audit, 'dag2-manifest.json', 16384)
        manifest = strict_json(manifest_raw)
        _d2_shape(manifest, DAG2_SCHEMAS['manifest']['properties'])
        _d2_require(type(manifest['aggregate_bytes']) is int and 0 < manifest['aggregate_bytes'] <= 27262976, 'SIZE_LIMIT')
        _d2_require(type(manifest['files']) is list, 'INVALID_SCHEMA')
        for row in manifest['files']:
            _d2_require(type(row) is dict and type(row.get('size_bytes')) is int and 0 < row['size_bytes'] <= 2097152, 'SIZE_LIMIT')
        dag2_validate_schema(manifest, 'manifest')
        _d2_equal([r['file_id'] for r in manifest['files']], list(DAG2_INPUT_FILES), 'INVALID_SCHEMA')
        raw_files = {name: _d2_read(audit, name, _d2_file_limit(name)) for name in DAG2_INPUT_FILES}
        for row in manifest['files']:
            raw = raw_files[row['file_id']]
            _d2_equal(row['size_bytes'], len(raw), 'SIZE_LIMIT')
            _d2_equal(row['sha256'], hashlib.sha256(raw).hexdigest(), 'SOURCE_MISMATCH')
        _d2_equal(manifest['aggregate_bytes'], sum(map(len, raw_files.values())), 'SIZE_LIMIT')
        _d2_require(manifest['aggregate_bytes'] + len(manifest_raw) <= 27262976, 'SIZE_LIMIT')
        documents = {name: strict_json(raw) for name, raw in raw_files.items() if name.endswith('.json') and not name.endswith('.history.json')}
        environment = documents['dag2-environment.json']
        _d2_shape(environment, DAG2_SCHEMAS['environment']['properties'])
        if validation_intent == 'HOSTED_CANDIDATE_ADMISSION':
            _d2_equal(environment['evidence_class'], 'OBSERVED_HOSTED_CANDIDATE', 'HOSTED_ORIGIN_UNAUTHENTICATED', 'hosted_candidate_admission')
        _d2_equal(manifest['evidence_class'], environment['evidence_class'], 'INVALID_VALUE')
        # Identity/closure errors are reported at their frozen boundary before envelope binding.
        source = documents['source-manifest.json']
        context = {'identity': expected_identity, 'source_sha256': hashlib.sha256(raw_files['source-manifest.json']).hexdigest(), 'bootstraps': environment['bootstrap'], 'originals': documents['dag2-originals.json']}
        _d2_environment(environment, context, validation_intent)
        _d2_source_manifest(source, environment, expected_identity, validation_intent, reviewed_source_manifest, expected_source_manifest_sha256)
        source_snapshot = _d2_source_bytes(source) if validation_intent == 'HOSTED_CANDIDATE_ADMISSION' else None
        for key, filename in [('complete_tracked_manifest_sha256', 'source-manifest.json'), ('pip_report_sha256', 'pip-report.json'), ('acquisition_receipt_sha256', 'acquisition-receipt.json')]:
            _d2_equal(environment[key], hashlib.sha256(raw_files[filename]).hexdigest(), 'SOURCE_MISMATCH')
        for filename, code in [('required-nodes.txt', 'REQUIRED_NODES'), ('collected-nodes.txt', 'COLLECTION_MISMATCH')]:
            _d2_equal(raw_files[filename], ('\n'.join(DAG2_REQUIRED_NODES) + '\n').encode(), code)
        _d2_junit(audit / 'results.xml')
        result = validate_dag2_records(documents, raw_files, expected_identity, validation_intent=validation_intent, expected_unit_receipts=expected_unit_receipts, require_phase_receipts=True)
        output = {key: definition['const'] for key, definition in DAG2_SCHEMAS['summary']['properties'].items() if 'const' in definition}
        output.update(evidence_class=environment['evidence_class'], identity=expected_identity, source_manifest_sha256=hashlib.sha256(raw_files['source-manifest.json']).hexdigest(), evidence_manifest_sha256=hashlib.sha256(manifest_raw).hexdigest(), node_manifest_sha256=hashlib.sha256(raw_files['required-nodes.txt']).hexdigest(), collection_sha256=hashlib.sha256(raw_files['collected-nodes.txt']).hexdigest(), junit_sha256=hashlib.sha256(raw_files['results.xml']).hexdigest(), reason_code='OK', claims={k: d['const'] for k, d in DAG2_SCHEMAS['claims']['properties'].items()})
        _d2_summary(output)
        _d2_require(manifest['aggregate_bytes'] + len(manifest_raw) + len(_d2_bytes(output)) <= 27262976, 'SIZE_LIMIT')
        snapshot = raw_files | {'dag2-manifest.json': manifest_raw}
        for name, original in snapshot.items():
            _d2_equal(_d2_read(audit, name, max(len(original), 1)), original, 'SOURCE_MISMATCH')
        if source_snapshot is not None:
            _d2_equal(_d2_source_bytes(source), source_snapshot, 'SOURCE_MISMATCH')
        result['summary'] = output
        validated = _DAG2Validated(result, output, audit, snapshot, source, source_snapshot)
        validate_dag2_public_output(output, validated_audit=validated)
        return validated
    except GateError as error:
        if not hasattr(error, 'boundary'):
            error.boundary = 'record_validation'
        raise
    except (KeyError, TypeError, IndexError, ValueError, RecursionError):
        _d2_fail('INVALID_SCHEMA')


def validate_dag2_failure_audit(audit, expected_identity, *, expected_nodes):
    """Truthful incomplete-pack output; unavailable counts never imply zero work."""
    _d2_equal(expected_nodes, 7, 'REQUIRED_NODES')
    dag2_validate_schema(expected_identity, 'identity')
    audit = Path(audit)
    raw = _d2_read(audit, 'dag2-diagnostic.json', 4096)
    diagnostic = strict_json(raw)
    _d2_diagnostic(diagnostic, allow_failure=True)
    _d2_equal(diagnostic['result'], 'FAIL', 'INVALID_VALUE')
    _d2_require(diagnostic['primary_failure'] is not None, 'INVALID_VALUE')
    output = {key: definition['const'] for key, definition in DAG2_SCHEMAS['failure_summary']['properties'].items() if 'const' in definition}
    output.update(evidence_class=diagnostic['evidence_class'], collected_nodes=0, passed_nodes=0, failed_nodes=0, error_nodes=0, skipped_nodes=0, missions_admitted=0, activity_schedules_observed=0, runtime_entries_observed=0, count_evidence='UNAVAILABLE', cleanup_status=diagnostic['cleanup_status'], primary_failure=diagnostic['primary_failure'], cleanup_failure=diagnostic['cleanup_failure'], audit_failure=diagnostic['audit_failure'], claims={k: d['const'] for k, d in DAG2_SCHEMAS['claims']['properties'].items()})
    _d2_summary(output, True)
    validated = _DAG2Validated({'record_validation': 'FAIL', 'hosted_acceptance': 'REJECTED', 'summary': output}, output, audit, {'dag2-diagnostic.json': raw})
    validate_dag2_public_output(output, validated_audit=validated)
    return validated


def validate_dag2_public_output(proposed, *, validated_audit):
    """The mandatory final stdout/summary boundary, shared with unit controls."""
    _d2_require(type(validated_audit) is _DAG2Validated, 'INVALID_VALUE')
    failure = validated_audit['record_validation'] == 'FAIL'
    _d2_summary(proposed, failure)
    _d2_equal(_d2_bytes(proposed, 8192), validated_audit._output_bytes, 'COUNTER_MISMATCH')
    if validated_audit._snapshot is not None:
        for name, raw in validated_audit._snapshot.items():
            _d2_equal(_d2_read(validated_audit._audit, name, max(len(raw), 1)), raw, 'SOURCE_MISMATCH')
    if validated_audit._source_snapshot is not None:
        _d2_equal(_d2_source_bytes(validated_audit._source_manifest), validated_audit._source_snapshot, 'SOURCE_MISMATCH')
    return proposed


def _dag2_main(args):
    """No public output is copied from a rejected document or exception string."""
    result = None
    reason = 'INTERNAL_ERROR'
    try:
        _d2_require(args.expected_identity is not None and args.reviewed_source_manifest is not None, 'SOURCE_MISMATCH', 'preflight')
        expected = strict_json(read_bytes(args.expected_identity, 8192))
        _d2_equal(expected['commit'], args.expected_revision, 'SOURCE_MISMATCH', 'preflight')
        reviewed_raw = read_bytes(args.reviewed_source_manifest, 131072)
        reviewed = strict_json(reviewed_raw)
        _d2_require(DAG2_REVIEWED_SHARED_RECEIPT is not None, 'COLLECTION_MISMATCH')
        result = validate_dag2_audit(args.audit, expected, validation_intent='HOSTED_CANDIDATE_ADMISSION', expected_unit_receipts={'shared': DAG2_REVIEWED_SHARED_RECEIPT, 'dag_sdk': DAG2_DAG_RECEIPT}, reviewed_source_manifest=reviewed, expected_source_manifest_sha256=args.expected_source_manifest_sha256)
        _d2_equal(read_bytes(args.required, 8192), _d2_read(args.audit, 'required-nodes.txt', 8192), 'REQUIRED_NODES')
        _d2_equal(read_bytes(args.junit, 2097152), _d2_read(args.audit, 'results.xml', 2097152), 'JUNIT_IDENTITY')
    except GateError as error:
        result = None
        reason = error.code
    except Exception:
        result = None
        reason = 'INTERNAL_ERROR'
    if result is None:
        try:
            result = validate_dag2_failure_audit(args.audit, expected, expected_nodes=7)
        except Exception:
            # Fixed diagnostic is the only fallback if even a truthful failure pack cannot be validated.
            diagnostic = {'schema_version': DAG2_PREFIX + 'diagnostic.v1', 'evidence_class': 'OBSERVED_HOSTED_CANDIDATE', 'primary_failure': {'phase': 'verification', 'code': reason if reason in DAG2_CODES else 'INTERNAL_ERROR'}, 'cleanup_failure': None, 'audit_failure': None, 'cleanup_status': 'UNCONFIRMED', 'evidence_status': 'INCOMPLETE', 'result': 'FAIL'}
            _d2_diagnostic(diagnostic, allow_failure=True)
            print(_d2_bytes(diagnostic, 4096).decode())
            return 1
    proposed = result['summary']
    try:
        validate_dag2_public_output(proposed, validated_audit=result)
        data = _d2_bytes(proposed, 8192)
        target = args.audit / ('dag2-failure-summary.json' if result['record_validation'] == 'FAIL' else 'dag2-summary.json')
        _d2_require(not target.is_symlink(), 'WRITE_FAILED')
        with target.open('xb') as stream:
            stream.write(data)
        validate_dag2_public_output(proposed, validated_audit=result)
        if args.summary is not None:
            _d2_require(not args.summary.is_symlink(), 'WRITE_FAILED')
            with args.summary.open('a', encoding='utf-8') as stream:
                stream.write(data.decode() + '\n')
        validate_dag2_public_output(proposed, validated_audit=result)
        print(data.decode())
    except Exception:
        # A fixed closed diagnostic, never an arbitrary exception or partial success.
        diagnostic = {'schema_version': DAG2_PREFIX + 'diagnostic.v1', 'evidence_class': 'OBSERVED_HOSTED_CANDIDATE', 'primary_failure': {'phase': 'evidence_write', 'code': 'WRITE_FAILED'}, 'cleanup_failure': None, 'audit_failure': {'phase': 'evidence_write', 'code': 'WRITE_FAILED'}, 'cleanup_status': 'UNCONFIRMED', 'evidence_status': 'INCOMPLETE', 'result': 'FAIL'}
        _d2_diagnostic(diagnostic, allow_failure=True)
        print(_d2_bytes(diagnostic, 4096).decode())
        return 1
    return int(result['record_validation'] == 'FAIL')


if __name__ == "__main__":
    sys.exit(main())
