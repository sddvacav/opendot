"""Pure validator fault tests. Every record here is FABRICATED UNIT DATA.

These tests import no Temporal SDK, execute no native process or server, and
cannot establish real-server acceptance, replay, acquisition, or cleanup.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("temporal_gate_verifier", SOURCE / "ci/verify_temporal_server_gate.py")
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)
REVISION = "a" * 40


def _digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def _write(path, value):
    if path.suffix == ".jsonl":
        path.write_text("".join(json.dumps(row) + "\n" for row in value))
    else:
        path.write_text(json.dumps(value))


def _run_id(index):
    return f"00000000-0000-0000-0000-{index:012d}"


def _artifact(scenario):
    return "sha256:" + _digest("fabricated-unit-result-" + scenario)


def _base_history(scenario):
    events = []

    def add(kind, **attributes):
        events.append({"event_id": len(events) + 1, "event_type": kind, "attributes": attributes})

    add("WorkflowExecutionStarted", workflow_type="ReferenceGateWorkflow", task_queue="opendot-temporal-gate",
        execution_timeout_seconds=120, run_timeout_seconds=120, task_timeout_seconds=10, maximum_attempts=1)
    add("WorkflowTaskScheduled")
    add("WorkflowTaskStarted", scheduled_event_id=2, identity="opendot-gate-workflow-worker")
    add("WorkflowTaskCompleted", scheduled_event_id=2, started_event_id=3, identity="opendot-gate-workflow-worker")
    add("ActivityTaskScheduled", activity_type=gate.ACTIVITY_TYPE, activity_id=gate.ACTIVITY_ID,
        task_queue="opendot-temporal-gate", maximum_attempts=1, start_to_close_seconds=10, schedule_to_close_seconds=60)
    queued = deepcopy(events)
    add("ActivityTaskStarted", scheduled_event_id=5, attempt=1, identity="opendot-gate-activity-worker")
    result = dict(response_schema=gate.RESPONSE_SCHEMA, result_artifact_id=_artifact(scenario),
                  result_sha256=_artifact(scenario)[7:], result_size_bytes=100)
    if scenario == "missing_input":
        add("ActivityTaskFailed", scheduled_event_id=5, started_event_id=6, failure_type="TemporalInputRejected",
            non_retryable=True, retry_state="RETRY_STATE_NON_RETRYABLE_FAILURE")
    else:
        add("ActivityTaskCompleted", scheduled_event_id=5, started_event_id=6, **result)
    add("WorkflowTaskScheduled")
    add("WorkflowTaskStarted", scheduled_event_id=8, identity="opendot-gate-workflow-worker")
    add("WorkflowTaskCompleted", scheduled_event_id=8, started_event_id=9, identity="opendot-gate-workflow-worker")
    recorded = deepcopy(events)
    if scenario == "missing_input":
        add("WorkflowExecutionFailed", failure_type="TemporalInputRejected")
    else:
        add("WorkflowExecutionSignaled", signal_name="finish")
        add("WorkflowTaskScheduled")
        add("WorkflowTaskStarted", scheduled_event_id=12, identity="opendot-gate-workflow-worker")
        add("WorkflowTaskCompleted", scheduled_event_id=12, started_event_id=13, identity="opendot-gate-workflow-worker")
        add("WorkflowExecutionCompleted", **result)
    return queued, recorded, events


def _fabricated_records():
    metadata = []
    counters = []
    outcomes = []
    histories = []
    for index, scenario in enumerate(gate.SCENARIOS, 1):
        metadata.append({"schema_version": gate.PREFIX + "metadata.v1", "scenario": scenario,
                         "entry_sequence": index, "activity_id": gate.ACTIVITY_ID, "activity_type": gate.ACTIVITY_TYPE,
                         "namespace": "default", "task_queue": "opendot-temporal-gate",
                         "workflow_id": "opendot-gate-" + scenario, "workflow_run_id": _run_id(index),
                         "attempt": 1, "is_local": False, "retry_policy_present": True, "maximum_attempts": 1,
                         "start_to_close_seconds": 10, "schedule_to_close_seconds": 60,
                         "metadata_source": "real_sdk_activity_info"})
        for event, count in zip(gate.COUNTER_EVENTS, gate.EXPECTED_COUNTS[scenario]):
            for _ in range(count):
                counters.append({"schema_version": gate.PREFIX + "counter.v1", "scenario": scenario,
                                 "sequence": len(counters) + 1, "event": event,
                                 "runtime_generation": (3, 6, 8, 10, 12)[index - 1],
                                 "handler_binding": "bounded_sum_with_test_counter"})
        missing = scenario == "missing_input"
        outcomes.append({"scenario": scenario, "workflow_transport_status": "FAILED" if missing else "COMPLETED",
                         "activity_transport_status": "FAILED" if missing else "COMPLETED",
                         "result_ref_present": not missing, "result_artifact_id": None if missing else _artifact(scenario),
                         "cas_digest_verified": None if missing else True, "cas_size_verified": None if missing else True,
                         "result_schema_verified": None if missing else True,
                         "tool_status": None if missing else {"blocked": "BLOCKED", "failed_validation": "FAILED"}.get(scenario, "COMPLETED"),
                         "semantic_valid": None if missing else scenario in ("durability_replay", "null"),
                         "output_kind": None if missing else "integer" if scenario == "durability_replay" else "null",
                         "output_integer": 5 if scenario == "durability_replay" else None,
                         "runtime_receipt_attempts": None if missing else 1,
                         "execute_count": gate.EXPECTED_COUNTS[scenario][1], "handler_count": gate.EXPECTED_COUNTS[scenario][2],
                         "scientific_validity": None if missing else False,
                         "device_control_authority": None if missing else False,
                         "independent_review": None if missing else "NOT_EVALUATED",
                         "owner_integration": None if missing else "NOT_EVALUATED",
                         "test_only_validator_fault": scenario == "failed_validation"})
        queued, recorded, terminal = _base_history(scenario)
        phases = [("terminal", terminal, 3, len(counters), index)] if index > 1 else [
            ("queued_before_restart", queued, 1, 0, 0), ("queued_after_restart", queued, 2, 0, 0),
            ("activity_result_recorded", recorded, 2, 4, 1), ("workflow_completed_after_replay", terminal, 3, 4, 1)]
        for phase, events, server_generation, sequence, workers in phases:
            histories.append({"scenario": scenario, "phase": phase, "workflow_id": "opendot-gate-" + scenario,
                              "workflow_run_id": _run_id(index), "server_generation": server_generation,
                              "raw_history_sha256": _digest(json.dumps(events)), "events": deepcopy(events),
                              "counter_sequence": sequence, "activity_workers_started": workers, "active_activity_calls": 0})
    replay = {"schema_version": gate.PREFIX + "replay.v1", "scenario": "durability_replay", "workflow_run_id": _run_id(1),
              "recorded_completion_event_id": 7, "same_completion_event_after_restart": True,
              "before_result_artifact_id": _artifact("durability_replay"),
              "after_query_result_artifact_id": _artifact("durability_replay"),
              "workflow_result_artifact_id": _artifact("durability_replay"),
              "fresh_workflow_worker": True, "activity_worker_present_during_replay": False,
              "activity_schedule_count_before": 1, "activity_schedule_count_after": 1,
              "handler_count_before": 1, "handler_count_after_live_replay": 1, "handler_count_after_sdk_replay": 1,
              "raw_history_sha256": histories[3]["raw_history_sha256"], "sdk_replay_failure": None, "cas_reverified": True,
              "counter_sequence_before": 4, "counter_sequence_after_live_replay": 4, "counter_sequence_after_sdk_replay": 4}
    kinds = ("workflow", "workflow", "activity", "workflow", "workflow", "activity",
             "workflow", "activity", "workflow", "activity", "workflow", "activity")
    cleanup = {"schema_version": gate.PREFIX + "cleanup.v1",
               "server_generations": [{"generation": i, "shutdown_requested_signal": "SIGINT", "graceful_exit_observed": True,
                                       "exit_code": 0, "readiness_seconds": 1.0, "shutdown_seconds": 1.0} for i in range(1, 4)],
               "worker_generations": [{"generation": i, "type": kind, "public_shutdown_called": True,
                                       "public_shutdown_completed": True} for i, kind in enumerate(kinds, 1)],
               "all_activity_calls_observed_terminal": True, "same_sqlite_across_restarts": True,
               "same_cas_across_restarts": True, "in_flight_shutdown_attempted": False,
               "forced_termination_used": False, "cleanup_status": "PASS", "cleanup_code": "OK", "elapsed_seconds": 20.0}
    return {"activity-metadata.jsonl": metadata, "invocation-counters.jsonl": counters,
            "outcomes.json": {"schema_version": gate.PREFIX + "outcomes.v1", "scenarios": outcomes},
            "history-projection.json": {"schema_version": gate.PREFIX + "history.v1", "snapshots": histories},
            "replay.json": replay, "cleanup.json": cleanup}


@pytest.fixture
def unit_bundle(tmp_path, monkeypatch):
    """Build isolated invented records. Never use these as an acceptance artifact."""
    source = tmp_path / "fabricated-source"
    for relative in tuple(gate.OWNER_SHA256) + ("src/opendot_engineering/adapters/temporal_activity.py",
                                               "src/opendot_engineering/adapters/temporal_workflow.py",
                                               "ci/requirements.txt"):
        target = source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((SOURCE / relative).read_bytes())
    sdk_lines = [name + "==" + version + " --hash=sha256:" +
                 gate.SDK_HASHES[name]
                 for name, version in gate.SDK_VERSIONS.items()]
    (source / "ci/temporal-sdk-requirements.txt").write_text("\n".join(sdk_lines) + "\n")
    (source / "ci/temporal-server-nodes.txt").write_text("\n".join(gate.REQUIRED_NODES) + "\n")
    (source / "ci/run_temporal_server_gate.py").write_text("# FABRICATED UNIT DATA ONLY\n")
    (source / "tests/acceptance").mkdir(parents=True)
    (source / "tests/acceptance/temporal_server_gate.py").write_text("# FABRICATED UNIT DATA ONLY\n")
    for relative in gate.HARNESS_SOURCE_PATHS:
        target = source / relative
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("# FABRICATED UNIT DATA ONLY\n")
    monkeypatch.setattr(gate, "ROOT", source)
    # This pure test never executes git or another process.
    monkeypatch.setattr(gate, "checked_revision", lambda: REVISION)
    for key, value in {"GITHUB_ACTIONS": "true", "GITHUB_SHA": REVISION, "GITHUB_SERVER_URL": "https://github.com",
                       "GITHUB_REPOSITORY": "unit-fixture/unit-fixture", "GITHUB_RUN_ID": "123"}.items():
        monkeypatch.setenv(key, value)
    records = _fabricated_records()
    records["environment.json"] = {"schema_version": gate.PREFIX + "environment.v1",
        "candidate_revision": REVISION, "requested_revision": REVISION,
        "workflow_run_url": "https://github.com/unit-fixture/unit-fixture/actions/runs/123",
        "source_kind": "public_source_checkout", "python_version": "3.12.0", "platform": "linux-x86_64",
        "versions": gate.SDK_VERSIONS | gate.TOOL_VERSIONS, "cli_version": "1.9.1", "server_version": "1.32.0",
        "cli_archive_sha256": gate.CLI_ARCHIVE_SHA256, "cli_checksums_sha256": gate.CLI_CHECKSUMS_SHA256,
        "sdk_wheel_sha256": gate.SDK_WHEEL_SHA256, **gate.current_source_digests(),
        "owner_sha256": gate.OWNER_SHA256.copy(), "server_profile": gate.SERVER_PROFILE.copy(),
        "preflight_status": "PASS", "preflight_code": "OK"}
    audit = tmp_path / "fabricated-unit-audit"
    audit.mkdir()
    for name, record in records.items():
        _write(audit / name, record)
    _write(audit / "collection-receipt.json", {"schema_version": gate.PREFIX + "collection.v1",
                                             "nodes": list(gate.REQUIRED_NODES)})
    return audit, records, source


def _junit(path, statuses=None, attributes='tests="999" failures="999"'):
    statuses = statuses or [""] * 7
    cases = ''.join(f'<testcase classname="tests.acceptance.temporal_server_gate" name="{name}" time="0.1">{status}</testcase>'
                    for name, status in zip(gate.NODE_NAMES, statuses))
    path.write_text(f'<testsuites><testsuite {attributes}>{cases}</testsuite></testsuites>')
    return path


def _main_args(audit, source, junit, summary=None):
    args = ["--required", str(source / "ci/temporal-server-nodes.txt"), "--junit", str(junit),
            "--audit", str(audit), "--expected-revision", REVISION]
    return args + (["--summary", str(summary)] if summary else [])


def test_fabricated_unit_records_validate_schema_only(unit_bundle):
    audit, records, _ = unit_bundle
    assert gate.validate_audit(audit, REVISION, gate.REQUIRED_NODES) == records
    assert records["outcomes.json"]["scenarios"][3]["tool_status"] == "FAILED"


@pytest.mark.parametrize("missing", gate.AUDIT_FILES + ("collection-receipt.json",))
def test_every_receipt_is_required(unit_bundle, missing):
    audit, _, _ = unit_bundle
    (audit / missing).unlink()
    with pytest.raises(gate.GateError, match="MISSING_EVIDENCE"):
        gate.validate_audit(audit, REVISION, gate.REQUIRED_NODES)


@pytest.mark.parametrize("field,value", [
    ("attempt", True), ("attempt", 2), ("is_local", 0), ("is_local", True),
    ("retry_policy_present", None), ("maximum_attempts", None), ("maximum_attempts", 0),
    ("start_to_close_seconds", 10.0), ("schedule_to_close_seconds", 61),
    ("metadata_source", "fabricated_info"), ("workflow_id", "/private/task-token"),
])
def test_rejects_absent_coerced_or_wrong_received_metadata(unit_bundle, field, value):
    audit, records, _ = unit_bundle
    records["activity-metadata.jsonl"][0][field] = value
    _write(audit / "activity-metadata.jsonl", records["activity-metadata.jsonl"])
    with pytest.raises(gate.GateError, match="METADATA_MISMATCH"):
        gate.validate_audit(audit, REVISION, gate.REQUIRED_NODES)


@pytest.mark.parametrize("file,field", [("environment.json", "api_token"), ("replay.json", "history_bytes"),
                                        ("cleanup.json", "host_path")])
def test_unknown_private_capable_fields_rejected(unit_bundle, file, field):
    audit, records, _ = unit_bundle
    records[file][field] = "PRIVATE_CANARY_NOT_FOR_OUTPUT"
    _write(audit / file, records[file])
    with pytest.raises(gate.GateError, match="INVALID_SCHEMA"):
        gate.validate_audit(audit, REVISION, gate.REQUIRED_NODES)


@pytest.mark.parametrize("field,value,code", [
    ("candidate_revision", "b" * 40, "REVISION_MISMATCH"),
    ("requested_revision", "b" * 40, "REVISION_MISMATCH"),
    ("workflow_run_url", "https://github.com/unit-fixture/unit-fixture/actions/runs/124", "CI_IDENTITY"),
    ("python_version", "3.13.1", "VERSION_MISMATCH"), ("server_version", "1.9.1", "VERSION_MISMATCH"),
    ("cli_archive_sha256", "0" * 64, "PIN_MISMATCH"),
    ("sdk_wheel_sha256", "0" * 64, "PIN_MISMATCH"),
    ("harness_source_sha256", "0" * 64, "SOURCE_MISMATCH"),
    ("preflight_status", "FAIL", "PREFLIGHT_FAILED"),
])
def test_environment_source_pin_and_preflight_fail_closed(unit_bundle, field, value, code):
    audit, records, _ = unit_bundle
    records["environment.json"][field] = value
    _write(audit / "environment.json", records["environment.json"])
    with pytest.raises(gate.GateError, match=code):
        gate.validate_audit(audit, REVISION, gate.REQUIRED_NODES)


def test_current_owner_bytes_are_checked(unit_bundle):
    audit, _, source = unit_bundle
    (source / "src/opendot_engineering/tool_runtime.py").write_text("# changed unit fixture\n")
    with pytest.raises(gate.GateError, match="OWNER_MISMATCH"):
        gate.validate_audit(audit, REVISION, gate.REQUIRED_NODES)


def test_current_harness_bytes_are_checked(unit_bundle):
    audit, _, source = unit_bundle
    (source / "ci/run_temporal_server_gate.py").write_text("# stale unit fixture\n")
    with pytest.raises(gate.GateError, match="SOURCE_MISMATCH"):
        gate.validate_audit(audit, REVISION, gate.REQUIRED_NODES)


def test_exact_tool_lock_versions_required(unit_bundle):
    audit, records, source = unit_bundle
    lock = source / "ci/requirements.txt"
    lock.write_text(lock.read_text().replace("pytest==9.1.1", "pytest==8.4.2"))
    records["environment.json"].update(gate.current_source_digests())
    _write(audit / "environment.json", records["environment.json"])
    with pytest.raises(gate.GateError, match="VERSION_MISMATCH"):
        gate.validate_audit(audit, REVISION, gate.REQUIRED_NODES)


@pytest.mark.parametrize("scenario_index,field,value", [
    (0, "output_integer", True), (0, "scientific_validity", True),
    (1, "semantic_valid", False), (2, "tool_status", "COMPLETED"),
    (2, "handler_count", 1), (3, "tool_status", "COMPLETED"),
    (3, "test_only_validator_fault", False), (4, "tool_status", "FAILED"),
    (4, "result_ref_present", True), (4, "execute_count", 1),
])
def test_outcome_separation_and_null_fields_enforced(unit_bundle, scenario_index, field, value):
    audit, records, _ = unit_bundle
    records["outcomes.json"]["scenarios"][scenario_index][field] = value
    _write(audit / "outcomes.json", records["outcomes.json"])
    with pytest.raises(gate.GateError, match="OUTCOME_MISMATCH"):
        gate.validate_audit(audit, REVISION, gate.REQUIRED_NODES)


@pytest.mark.parametrize("mutation", ["duplicate", "sequence", "generation", "handler", "missing"])
def test_independent_counters_are_exact(unit_bundle, mutation):
    audit, records, _ = unit_bundle
    rows = records["invocation-counters.jsonl"]
    if mutation == "duplicate":
        rows.append(deepcopy(rows[-1]))
    elif mutation == "missing":
        rows.pop()
    else:
        key, value = {"sequence": ("sequence", 0), "generation": ("runtime_generation", 1),
                      "handler": ("event", "handler_enter")}[mutation]
        rows[0][key] = value
    _write(audit / "invocation-counters.jsonl", rows)
    with pytest.raises(gate.GateError, match="COUNTER_MISMATCH"):
        gate.validate_audit(audit, REVISION, gate.REQUIRED_NODES)


@pytest.mark.parametrize("mutation,code", [
    ("link", "HISTORY_LINKAGE"), ("event_order", "HISTORY_LINKAGE"), ("attempt", "HISTORY_MISMATCH"),
    ("queued_counter", "COUNTER_MISMATCH"), ("queued_worker", "COUNTER_MISMATCH"),
    ("inflight", "CLEANUP_UNCONFIRMED"), ("prefix", "HISTORY_MISMATCH"),
    ("raw_hash", "HISTORY_MISMATCH"), ("private_attribute", "INVALID_SCHEMA"),
    ("new_run", "HISTORY_MISMATCH"),
])
def test_history_order_linkage_and_quiescent_boundaries(unit_bundle, mutation, code):
    audit, records, _ = unit_bundle
    snapshots = records["history-projection.json"]["snapshots"]
    if mutation == "link":
        snapshots[2]["events"][6]["attributes"]["started_event_id"] = 5
    elif mutation == "event_order":
        snapshots[2]["events"][6]["event_id"] = 6
    elif mutation == "attempt":
        snapshots[2]["events"][5]["attributes"]["attempt"] = 2
    elif mutation == "queued_counter":
        snapshots[0]["counter_sequence"] = 1
    elif mutation == "queued_worker":
        snapshots[1]["activity_workers_started"] = 1
    elif mutation == "inflight":
        snapshots[2]["active_activity_calls"] = 1
    elif mutation == "prefix":
        snapshots[1]["events"][4]["attributes"]["schedule_to_close_seconds"] = 59
    elif mutation == "raw_hash":
        snapshots[1]["raw_history_sha256"] = "0" * 64
    elif mutation == "private_attribute":
        snapshots[2]["events"][5]["attributes"]["task_token"] = "PRIVATE_CANARY"
    else:
        snapshots[3]["events"][-1]["event_type"] = "WorkflowExecutionContinuedAsNew"
    _write(audit / "history-projection.json", records["history-projection.json"])
    with pytest.raises(gate.GateError, match=code):
        gate.validate_audit(audit, REVISION, gate.REQUIRED_NODES)


@pytest.mark.parametrize("field,value,code", [
    ("after_query_result_artifact_id", "sha256:" + "0" * 64, "REPLAY_MISMATCH"),
    ("sdk_replay_failure", "FAILED", "REPLAY_MISMATCH"),
    ("raw_history_sha256", "0" * 64, "REPLAY_MISMATCH"),
    ("activity_worker_present_during_replay", True, "REPLAY_MISMATCH"),
    ("handler_count_after_live_replay", 2, "REPLAY_MISMATCH"),
    ("counter_sequence_after_sdk_replay", 5, "COUNTER_MISMATCH"),
])
def test_live_and_sdk_replay_preserve_references_and_counts(unit_bundle, field, value, code):
    audit, records, _ = unit_bundle
    records["replay.json"][field] = value
    _write(audit / "replay.json", records["replay.json"])
    with pytest.raises(gate.GateError, match=code):
        gate.validate_audit(audit, REVISION, gate.REQUIRED_NODES)


@pytest.mark.parametrize("mutation", ["forced", "status", "worker", "server", "late", "missing_generation", "bool_exit"])
def test_cleanup_is_required_for_all_owned_generations(unit_bundle, mutation):
    audit, records, _ = unit_bundle
    cleanup = records["cleanup.json"]
    if mutation == "forced":
        cleanup["forced_termination_used"] = True
    elif mutation == "status":
        cleanup["cleanup_status"] = "UNCONFIRMED"
    elif mutation == "worker":
        cleanup["worker_generations"][-1]["public_shutdown_completed"] = False
    elif mutation == "server":
        cleanup["server_generations"][-1]["exit_code"] = None
    elif mutation == "late":
        cleanup["server_generations"][0]["shutdown_seconds"] = 8.01
    elif mutation == "bool_exit":
        cleanup["server_generations"][0]["exit_code"] = False
    else:
        cleanup["worker_generations"].pop()
    _write(audit / "cleanup.json", cleanup)
    with pytest.raises(gate.GateError, match="CLEANUP_UNCONFIRMED"):
        gate.validate_audit(audit, REVISION, gate.REQUIRED_NODES)


@pytest.mark.parametrize("raw,code", [
    (b'{"schema_version":1,"schema_version":2}', "INVALID_JSON"),
    (b'{"value": NaN}', "INVALID_JSON"), (b'{"value": Infinity}', "INVALID_JSON"),
    (b'{"value":', "INVALID_JSON"), (b'\xff', "INVALID_JSON"), (b' ' * 65537, "SIZE_LIMIT"),
])
def test_json_is_strict_and_bounded(tmp_path, raw, code):
    path = tmp_path / "invalid.json"
    path.write_bytes(raw)
    with pytest.raises(gate.GateError, match=code):
        gate.read_json(path)


def test_jsonl_rejects_more_than_256_rows(tmp_path):
    path = tmp_path / "invalid.jsonl"
    path.write_text("{}\n" * 257)
    with pytest.raises(gate.GateError, match="SIZE_LIMIT"):
        gate.read_jsonl(path)


def test_junit_uses_testcase_children_not_aggregate_counts(tmp_path):
    rows = gate.verify_junit(_junit(tmp_path / "unit.xml"), gate.REQUIRED_NODES)
    assert len(rows) == 7 and all(row["outcome"] == "PASS" for row in rows)


@pytest.mark.parametrize("status,outcome", [("<failure>PRIVATE</failure>", "FAIL"),
                                           ("<error>PRIVATE</error>", "ERROR"),
                                           ('<skipped type="pytest.xfail">PRIVATE</skipped>', "SKIP")])
def test_junit_failure_error_skip_and_xfail_never_pass(tmp_path, status, outcome):
    rows = gate.verify_junit(_junit(tmp_path / "unit.xml", [status] + [""] * 6), gate.REQUIRED_NODES)
    assert rows[0]["outcome"] == outcome and "PRIVATE" not in str(rows)


@pytest.mark.parametrize("mutation,code", [("duplicate", "DUPLICATE_NODE"), ("extra", "JUNIT_IDENTITY"),
                                          ("class", "JUNIT_IDENTITY"), ("double_status", "INVALID_JUNIT"),
                                          ("entity", "INVALID_JUNIT"), ("properties", "INVALID_JUNIT")])
def test_junit_rejects_ambiguous_identity_or_status(tmp_path, mutation, code):
    path = _junit(tmp_path / "unit.xml")
    raw = path.read_text()
    if mutation == "duplicate":
        raw = raw.replace(gate.NODE_NAMES[1], gate.NODE_NAMES[0])
    elif mutation == "extra":
        raw = raw.replace(gate.NODE_NAMES[0], "test_unexpected")
    elif mutation == "class":
        raw = raw.replace("tests.acceptance.temporal_server_gate", "untrusted.module", 1)
    elif mutation == "double_status":
        raw = raw.replace('</testcase>', '<failure/><skipped/></testcase>', 1)
    elif mutation == "entity":
        raw = '<!DOCTYPE testsuites [<!ENTITY private "SECRET">]>' + raw
    else:
        raw = raw.replace('</testcase>', '<properties><property name="xfail" value="true"/></properties></testcase>', 1)
    path.write_text(raw)
    with pytest.raises(gate.GateError, match=code):
        gate.verify_junit(path, gate.REQUIRED_NODES)


def test_missing_junit_cases_explicitly_not_run(tmp_path):
    path = tmp_path / "unit.xml"
    path.write_text('<testsuite tests="7"/>')
    rows = gate.verify_junit(path, gate.REQUIRED_NODES)
    assert len(rows) == 7 and all(row["outcome"] == "NOT_RUN" for row in rows)


@pytest.mark.parametrize("mutation", ["duplicate", "unexpected", "missing", "wrong_schema"])
def test_exact_collection_receipt_required(unit_bundle, mutation):
    audit, _, _ = unit_bundle
    value = json.loads((audit / "collection-receipt.json").read_text())
    if mutation == "duplicate":
        value["nodes"][1] = value["nodes"][0]
    elif mutation == "unexpected":
        value["nodes"][0] = "tests/private.py::test_secret"
    elif mutation == "missing":
        value["nodes"].pop()
    else:
        value["schema_version"] = "other.v1"
    _write(audit / "collection-receipt.json", value)
    with pytest.raises(gate.GateError):
        gate.verify_collection(audit / "collection-receipt.json", gate.REQUIRED_NODES)


def test_missing_everything_still_writes_fail_with_seven_not_run(tmp_path, capsys):
    audit = tmp_path / "missing-audit"
    result = gate.main(["--required", str(tmp_path / "absent.txt"), "--junit", str(tmp_path / "absent.xml"),
                        "--audit", str(audit), "--expected-revision", REVISION])
    acceptance = json.loads((audit / "acceptance.json").read_text())
    assert result == 1 and acceptance["acceptance"] == "FAIL"
    assert acceptance["counts"] == {"PASS": 0, "FAIL": 0, "ERROR": 0, "SKIP": 0, "NOT_RUN": 7}
    assert acceptance["privacy_check"] == "FAIL" and not acceptance["cleanup_verified"]
    assert str(tmp_path) not in capsys.readouterr().out


def test_only_complete_validator_unit_data_can_reach_unit_pass(unit_bundle, tmp_path, capsys):
    audit, _, source = unit_bundle
    path = _junit(tmp_path / "fabricated-unit.xml")
    summary = tmp_path / "fabricated-unit-summary.txt"
    assert gate.main(_main_args(audit, source, path, summary)) == 0
    # This is solely a test of verifier control flow, not an acceptance run.
    acceptance = json.loads((audit / "acceptance.json").read_text())
    assert acceptance["acceptance"] == "PASS" and acceptance["counts"]["PASS"] == 7
    assert "PRIVATE" not in capsys.readouterr().out


def test_invalid_audit_and_junit_private_text_are_never_exposed(unit_bundle, tmp_path, capsys):
    audit, records, source = unit_bundle
    records["replay.json"]["sdk_replay_failure"] = "PRIVATE_CANARY_NOT_FOR_OUTPUT"
    _write(audit / "replay.json", records["replay.json"])
    junit = _junit(tmp_path / "unit.xml", ['<failure message="PRIVATE_CANARY_NOT_FOR_OUTPUT">SECRET_TRACE</failure>'] + [""] * 6)
    summary = tmp_path / "summary.txt"
    assert gate.main(_main_args(audit, source, junit, summary)) == 1
    emitted = capsys.readouterr().out + summary.read_text() + (audit / "acceptance.json").read_text()
    assert "PRIVATE_CANARY" not in emitted and "SECRET_TRACE" not in emitted and '"audit_file"' not in emitted
    assert '"FAIL":1' in emitted


def test_stale_acceptance_does_not_override_missing_evidence(unit_bundle, tmp_path, capsys):
    audit, _, source = unit_bundle
    (audit / "environment.json").unlink()
    _write(audit / "acceptance.json", {"acceptance": "PASS", "private": "PRIVATE_CANARY"})
    assert gate.main(_main_args(audit, source, _junit(tmp_path / "unit.xml"))) == 1
    assert json.loads((audit / "acceptance.json").read_text())["acceptance"] == "FAIL"
    assert "PRIVATE_CANARY" not in capsys.readouterr().out


def test_unknown_audit_file_and_symlinks_fail_privacy(unit_bundle, tmp_path):
    audit, _, _ = unit_bundle
    (audit / "server.log").write_text("PRIVATE")
    with pytest.raises(gate.GateError, match="PRIVACY_REJECTED"):
        gate.validate_audit(audit, REVISION, gate.REQUIRED_NODES)
    (audit / "server.log").unlink()
    value = (audit / "replay.json").read_bytes()
    (audit / "replay.json").unlink()
    target = tmp_path / "private.json"
    target.write_bytes(value)
    (audit / "replay.json").symlink_to(target)
    with pytest.raises(gate.GateError, match="PRIVACY_REJECTED"):
        gate.validate_audit(audit, REVISION, gate.REQUIRED_NODES)


def test_gate_error_never_carries_arbitrary_exception_text():
    assert str(gate.GateError("PRIVATE_CANARY")) == "INTERNAL_ERROR"


@pytest.mark.parametrize("parent,child", [
    ("system-out", "failure"), ("system-err", "error"), ("failure", "skipped"),
    ("skipped", "testcase"), ("properties", "testcase"), ("testcase", "testsuite"),
])
def test_junit_rejects_misnested_status_and_diagnostic_elements(tmp_path, parent, child):
    path = _junit(tmp_path / "unit.xml")
    raw = path.read_text().replace('</testcase>', f'<{parent}><{child}/></{parent}></testcase>', 1)
    path.write_text(raw)
    with pytest.raises(gate.GateError, match="INVALID_JUNIT"):
        gate.verify_junit(path, gate.REQUIRED_NODES)


@pytest.mark.parametrize("dependency", tuple(gate.SDK_HASHES) + tuple(gate.TOOL_HASHES))
def test_every_reviewed_wheel_hash_is_pinned(unit_bundle, dependency):
    audit, records, source = unit_bundle
    filename = "ci/temporal-sdk-requirements.txt" if dependency in gate.SDK_HASHES else "ci/requirements.txt"
    path = source / filename
    expected = (gate.SDK_HASHES | gate.TOOL_HASHES)[dependency]
    path.write_text(path.read_text().replace(expected, "0" * 64))
    records["environment.json"].update(gate.current_source_digests())
    _write(audit / "environment.json", records["environment.json"])
    with pytest.raises(gate.GateError, match="PIN_MISMATCH"):
        gate.validate_audit(audit, REVISION, gate.REQUIRED_NODES)


@pytest.mark.parametrize("relative", gate.HARNESS_SOURCE_PATHS)
def test_full_ten_file_harness_closure_digest_changes(unit_bundle, relative):
    _, _, source = unit_bundle
    before = gate.current_source_digests()["harness_source_sha256"]
    target = source / relative
    target.write_bytes(target.read_bytes() + b"\n# changed fabricated unit source\n")
    assert gate.current_source_digests()["harness_source_sha256"] != before


def test_current_node_manifest_cannot_drift_even_with_refreshed_digest(unit_bundle):
    audit, records, source = unit_bundle
    manifest = source / "ci/temporal-server-nodes.txt"
    manifest.write_text(manifest.read_text().replace(gate.NODE_NAMES[0], "test_other"))
    records["environment.json"].update(gate.current_source_digests())
    _write(audit / "environment.json", records["environment.json"])
    with pytest.raises(gate.GateError, match="REQUIRED_NODES"):
        gate.validate_audit(audit, REVISION, gate.REQUIRED_NODES)


def test_summary_write_failure_preserves_fail_receipt(unit_bundle, tmp_path, capsys):
    audit, _, source = unit_bundle
    summary = tmp_path / "missing-directory" / "summary.txt"
    assert gate.main(_main_args(audit, source, _junit(tmp_path / "unit.xml"), summary)) == 1
    receipt = json.loads((audit / "acceptance.json").read_text())
    assert receipt["acceptance"] == "FAIL" and "WRITE_FAILED" in receipt["reason_codes"]
    first_stdout_record = json.loads(capsys.readouterr().out.splitlines()[0])
    assert first_stdout_record["acceptance"] == "FAIL"


@pytest.mark.parametrize("snapshot_index", (3, 4, 5, 6, 7))
def test_terminal_history_requires_final_task_closure(unit_bundle, snapshot_index):
    audit, records, _ = unit_bundle
    events = records["history-projection.json"]["snapshots"][snapshot_index]["events"]
    assert events[-2]["event_type"] == "WorkflowTaskCompleted"
    del events[-2]
    events[-1]["event_id"] -= 1
    _write(audit / "history-projection.json", records["history-projection.json"])
    with pytest.raises(gate.GateError, match="HISTORY_LINKAGE"):
        gate.validate_audit(audit, REVISION, gate.REQUIRED_NODES)


@pytest.mark.parametrize("encoding", ("utf-16", "utf-16-le", "utf-16-be", "utf-32", "utf-32-le", "utf-32-be"))
@pytest.mark.parametrize("with_entity", (False, True))
def test_junit_rejects_utf16_and_utf32_before_xml_parsing(tmp_path, monkeypatch, encoding, with_entity):
    path = _junit(tmp_path / "unit.xml")
    xml = path.read_text()
    if with_entity:
        xml = '<!DOCTYPE testsuites [<!ENTITY unit "unit-fixture">]>' + xml.replace(
            '</testcase>', '<system-out>&unit;</system-out></testcase>', 1)
    path.write_bytes(xml.encode(encoding))
    # Both a clean alternate encoding and its small internal-entity variant must
    # fail before the parser can autodetect the encoding or expand any entity.
    monkeypatch.setattr(gate.ET, "fromstring", lambda _xml: pytest.fail("XML parser must not be called"))
    with pytest.raises(gate.GateError, match="INVALID_JUNIT"):
        gate.verify_junit(path, gate.REQUIRED_NODES)


@pytest.mark.parametrize("encoding", ("UTF-16", "UTF-32", "ISO-8859-1", "US-ASCII", "utf8"))
@pytest.mark.parametrize("quote", ('"', "'"))
def test_junit_rejects_conflicting_or_noncanonical_encoding_declaration(tmp_path, monkeypatch, encoding, quote):
    path = _junit(tmp_path / "unit.xml")
    declaration = f'<?xml version="1.0" encoding={quote}{encoding}{quote}?>'
    path.write_bytes((declaration + path.read_text()).encode("utf-8"))
    monkeypatch.setattr(gate.ET, "fromstring", lambda _xml: pytest.fail("XML parser must not be called"))
    with pytest.raises(gate.GateError, match="INVALID_JUNIT"):
        gate.verify_junit(path, gate.REQUIRED_NODES)


@pytest.mark.parametrize("prefix", (b"\xef\xbb\xbf", b"\x00", b"\xff"))
def test_junit_rejects_bom_nul_and_invalid_utf8_before_parsing(tmp_path, monkeypatch, prefix):
    path = _junit(tmp_path / "unit.xml")
    path.write_bytes(prefix + path.read_bytes())
    monkeypatch.setattr(gate.ET, "fromstring", lambda _xml: pytest.fail("XML parser must not be called"))
    with pytest.raises(gate.GateError, match="INVALID_JUNIT"):
        gate.verify_junit(path, gate.REQUIRED_NODES)


@pytest.mark.parametrize("declaration", (
    '<?xml version="1.0" encoding="utf-8"?>',
    "<?xml version='1.0' encoding='UTF-8'?>",
    '<?xml version="1.0"?>',
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
))
def test_junit_accepts_canonical_utf8_and_explicit_utf8_declarations(tmp_path, declaration):
    path = _junit(tmp_path / "unit.xml")
    path.write_bytes((declaration + path.read_text()).encode("utf-8"))
    rows = gate.verify_junit(path, gate.REQUIRED_NODES)
    assert len(rows) == 7 and all(row["outcome"] == "PASS" for row in rows)


def test_shared_junit_parser_supports_bounded_large_unit_suite_without_weakening_seven_nodes(tmp_path):
    path = tmp_path / "fabricated-large-unit-suite.xml"
    cases = ''.join(f'<testcase classname="unit.fixture" name="test_unit_{index}"/>' for index in range(523))
    path.write_text('<testsuites><testsuite>' + cases + '</testsuite></testsuites>', encoding="utf-8")
    root = gate.parse_junit(path, maximum=2 * 1024 * 1024)
    assert len(list(root.iter("testcase"))) == 523
    with pytest.raises(gate.GateError, match="DUPLICATE_NODE"):
        gate.verify_junit(path, gate.REQUIRED_NODES)


@pytest.mark.parametrize("maximum", (0, -1, True, 1.0, 2 * 1024 * 1024 + 1))
def test_shared_junit_parser_byte_limit_is_exact_and_bounded(tmp_path, maximum):
    path = _junit(tmp_path / "unit.xml")
    with pytest.raises(gate.GateError, match="SIZE_LIMIT"):
        gate.parse_junit(path, maximum=maximum)


def test_shared_junit_parser_enforces_requested_byte_limit(tmp_path):
    path = _junit(tmp_path / "unit.xml")
    with pytest.raises(gate.GateError, match="SIZE_LIMIT"):
        gate.parse_junit(path, maximum=path.stat().st_size - 1)


def test_shared_junit_parser_rejects_multiple_statuses_without_identity_validation(tmp_path):
    path = tmp_path / "unit.xml"
    path.write_text('<testsuite><testcase classname="unit.fixture" name="test_unit"><error/><failure/></testcase></testsuite>')
    with pytest.raises(gate.GateError, match="INVALID_JUNIT"):
        gate.parse_junit(path)
