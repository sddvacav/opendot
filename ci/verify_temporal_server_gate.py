"""Strict, stdlib-only verifier for the optional real-server gate.

Unit-test records exercise this verifier; they are never real-server evidence.
Nothing from failed validation, JUnit diagnostics, or exception text is exposed.
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
})
OWNER_SHA256 = {
    "src/opendot_engineering/tool_runtime.py": "7c5011e02b2cf07e5f15ad7854905ce0738271e167b873bad9256a8ed169199c",
    "src/opendot_engineering/core/artifacts.py": "91fde8d32f6f7498fc96c0e883b9ba658440e95b0cc92f69f172e4de3d7b7856",
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
               "invocation-counters.jsonl", "outcomes.json", "replay.json", "cleanup.json")


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
    records = {name: (read_jsonl(audit_dir / name) if name.endswith(".jsonl") else read_json(audit_dir / name))
               for name in AUDIT_FILES}
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
    args = parser.parse_args(argv)
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
                                                               else "NOT VERIFIED") + "\n" + _encode(acceptance) + "\n")
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
    if records is not None:
        for filename in AUDIT_FILES:
            print(_encode({"audit_file": filename, "evidence": records[filename]}))
    return 0 if acceptance["acceptance"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
