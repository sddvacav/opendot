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


def validate_environment(value: object, expected_revision: str) -> None:
    shape(value, "schema_version candidate_revision requested_revision workflow_run_url source_kind "
          "python_version platform versions cli_version server_version cli_archive_sha256 "
          "cli_checksums_sha256 sdk_wheel_sha256 tool_lock_sha256 sdk_lock_sha256 "
          "required_nodes_sha256 harness_source_sha256 activity_source_sha256 workflow_source_sha256 "
          "owner_sha256 server_profile preflight_status preflight_code")
    schema(value, "environment")
    for name in ("candidate_revision", "requested_revision"):
        exact(value[name], expected_revision, "REVISION_MISMATCH")
    exact(checked_revision(), expected_revision, "REVISION_MISMATCH")
    exact(value["workflow_run_url"], trusted_run_url(expected_revision), "CI_IDENTITY")
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--required", required=True, type=Path)
    parser.add_argument("--junit", required=True, type=Path)
    parser.add_argument("--audit", required=True, type=Path)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--profile", choices=("reference", "batch200"), default="reference")
    args = parser.parse_args(argv)
    if args.profile == "batch200":
        return _real_batch_main(args)
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
        "cd2c277266239e57c10cb5aab743052f3322acf75be1d48156d715cef6fae5ae",
    "src/opendot_engineering/adapters/temporal_workflow.py":
        "d9307d0e78e4a925d92f021c5316a0515040bb091013182419bc6ccbb6a5ea38",
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


def validate_real_batch_audit(audit: Path, expected_revision: str) -> dict:
    audit = Path(audit)
    require(audit.is_dir() and not audit.is_symlink(), "MISSING_EVIDENCE")
    try:
        require({path.name for path in audit.iterdir()} <= set(REAL_BATCH_AUDIT_FILES)
                | {"collection-receipt.json", "batch-acceptance.json"}, "PRIVACY_REJECTED")
    except OSError:
        raise GateError("READ_FAILED") from None
    read_real_batch_nodes(ROOT / "ci/temporal-real-batch-nodes.txt")
    verify_real_batch_collection(audit / "collection-receipt.json")
    environment = read_json(audit / "environment.json")
    validate_environment(environment, expected_revision)
    diagnostic = validate_diagnostic(read_json(audit / "diagnostic.json"), expected_revision)
    exact(diagnostic["status"], "COMPLETE", "DIAGNOSTIC_FAILED")
    trace = strict_json(read_bytes(audit / "batch-trace.json", BATCH_TRACE_BYTES))
    require(type(trace) is dict, "INVALID_SCHEMA")
    metadata = _read_real_table(audit / "batch-metadata.json", "metadata", 256 * 1024)
    histories = _read_real_table(audit / "batch-histories.json", "history", 4 * 1024 * 1024)
    outcomes = _read_real_table(audit / "batch-outcomes.json", "outcomes", 256 * 1024)
    summary = validate_real_batch_trace(trace, trace.get("plan"), trace.get("profile"), metadata, histories,
                                        outcomes, expected_revision=expected_revision)
    cleanup = read_json(audit / "batch-cleanup.json")
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


def _real_batch_main(args) -> int:
    """The only hosted batch CLI route. Never publish raw evidence tables."""
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


if __name__ == "__main__":
    sys.exit(main())
