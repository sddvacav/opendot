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
            "replay.json": replay, "cleanup.json": cleanup,
            "diagnostic.json": {"schema_version": gate.PREFIX + "diagnostic.v1", "requested_revision": REVISION,
                                "status": "COMPLETE", "primary_failure": None, "cleanup_failure": None,
                                "audit_failure": None}}


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


def _failure(phase="sdk_binding", reason="TYPE_ERROR", category="type_error"):
    return {"phase": phase, "reason_code": reason, "exception_category": category}


def _diagnostic(**changes):
    value = {"schema_version": gate.PREFIX + "diagnostic.v1", "requested_revision": REVISION,
             "status": "FAILED", "primary_failure": _failure(), "cleanup_failure": None,
             "audit_failure": None}
    value.update(changes)
    return value


def test_diagnostic_builder_validates_and_returns_fresh_fixed_records():
    failure = _failure()
    result = gate.build_diagnostic(REVISION, status="FAILED", primary_failure=failure)
    assert result == _diagnostic() and result["primary_failure"] is not failure
    failure["reason_code"] = "PRIVATE_CANARY"
    assert result["primary_failure"]["reason_code"] == "TYPE_ERROR"
    assert gate.build_diagnostic(REVISION, status="COMPLETE") == _diagnostic(status="COMPLETE", primary_failure=None)


@pytest.mark.parametrize("field,value", [
    ("schema_version", "PRIVATE_CANARY"), ("requested_revision", "b" * 40),
    ("requested_revision", None), ("requested_revision", REVISION.upper()),
    ("requested_revision", "a" * 41), ("requested_revision", True),
    ("status", "PASS"), ("status", "PRIVATE_CANARY"), ("status", True),
    ("primary_failure", "PRIVATE_CANARY"), ("primary_failure", True), ("primary_failure", []),
    ("cleanup_failure", False), ("audit_failure", 0),
])
def test_diagnostic_rejects_invalid_top_level_values(field, value):
    with pytest.raises(gate.GateError, match="^DIAGNOSTIC_INVALID$"):
        gate.validate_diagnostic(_diagnostic(**{field: value}), REVISION)


@pytest.mark.parametrize("field", ("primary_failure", "cleanup_failure", "audit_failure"))
@pytest.mark.parametrize("key", ("phase", "reason_code", "exception_category"))
def test_diagnostic_rejects_private_values_in_every_failure_field(field, key):
    failure = _failure("audit_write" if field == "audit_failure" else "cleanup" if field == "cleanup_failure" else "sdk_binding")
    failure[key] = "PRIVATE_CANARY_NOT_FOR_OUTPUT /private/path token=private"
    with pytest.raises(gate.GateError, match="^DIAGNOSTIC_INVALID$"):
        gate.validate_diagnostic(_diagnostic(**{field: failure}), REVISION)


@pytest.mark.parametrize("field", (None, "primary_failure", "cleanup_failure", "audit_failure"))
def test_diagnostic_rejects_every_extra_private_capable_field(field):
    value = _diagnostic(cleanup_failure=_failure("cleanup"), audit_failure=_failure("audit_write"))
    target = value if field is None else value[field]
    target["exception_text"] = "PRIVATE_CANARY_NOT_FOR_OUTPUT"
    with pytest.raises(gate.GateError, match="^DIAGNOSTIC_INVALID$"):
        gate.validate_diagnostic(value, REVISION)


@pytest.mark.parametrize("field", ("phase", "reason_code", "exception_category"))
@pytest.mark.parametrize("value", (True, 1, None, [], {}, "x" * 4097))
def test_diagnostic_failure_fields_are_exact_bounded_enums(field, value):
    diagnostic = _diagnostic()
    diagnostic["primary_failure"][field] = value
    with pytest.raises(gate.GateError, match="^DIAGNOSTIC_INVALID$"):
        gate.validate_diagnostic(diagnostic, REVISION)


@pytest.mark.parametrize("failure", [
    _failure("complete"), _failure(reason="TYPE_ERROR", category="gate_refusal"),
    _failure(reason="SDK_REPLAY", category="type_error"),
    _failure(reason="VALUE_ERROR", category="type_error"),
    _failure(reason="NOT_A_REVIEWED_CODE", category="gate_refusal"),
])
def test_diagnostic_rejects_unknown_or_inconsistent_failure_codes(failure):
    with pytest.raises(gate.GateError, match="^DIAGNOSTIC_INVALID$"):
        gate.validate_diagnostic(_diagnostic(primary_failure=failure), REVISION)


@pytest.mark.parametrize("category,reason", tuple(gate.DIAGNOSTIC_GENERIC_REASONS.items()))
def test_diagnostic_admits_only_matching_fixed_generic_category_and_code(category, reason):
    value = _diagnostic(primary_failure=_failure(reason=reason, category=category))
    assert gate.validate_diagnostic(value, REVISION) == value


def test_diagnostic_admits_all_reviewed_gate_codes_without_arbitrary_text():
    for reason in gate.DIAGNOSTIC_GATE_REASONS:
        value = _diagnostic(primary_failure=_failure(reason=reason, category="gate_refusal"))
        assert gate.validate_diagnostic(value, REVISION) == value


@pytest.mark.parametrize("field,phase", [
    ("cleanup_failure", "cleanup"), ("cleanup_failure", "worker_shutdown"),
    ("cleanup_failure", "server_shutdown"), ("audit_failure", "audit_write"),
])
def test_diagnostic_can_record_cleanup_or_audit_failure_without_primary(field, phase):
    value = _diagnostic(primary_failure=None, **{field: _failure(phase)})
    assert gate.validate_diagnostic(value, REVISION) == value


@pytest.mark.parametrize("field,phase", [("cleanup_failure", "sdk_binding"), ("audit_failure", "cleanup")])
def test_diagnostic_secondary_slots_have_fixed_phase_scope(field, phase):
    with pytest.raises(gate.GateError, match="^DIAGNOSTIC_INVALID$"):
        gate.validate_diagnostic(_diagnostic(**{field: _failure(phase)}), REVISION)


@pytest.mark.parametrize("field", ("primary_failure", "cleanup_failure", "audit_failure"))
def test_diagnostic_forged_complete_with_any_failure_is_rejected(field):
    phase = "cleanup" if field == "cleanup_failure" else "audit_write" if field == "audit_failure" else "sdk_binding"
    value = _diagnostic(status="COMPLETE", primary_failure=None)
    value[field] = _failure(phase)
    with pytest.raises(gate.GateError, match="^DIAGNOSTIC_INVALID$"):
        gate.validate_diagnostic(value, REVISION)


def test_diagnostic_failed_without_any_failure_is_rejected():
    with pytest.raises(gate.GateError, match="^DIAGNOSTIC_INVALID$"):
        gate.validate_diagnostic(_diagnostic(primary_failure=None), REVISION)


@pytest.mark.parametrize("field", tuple(_diagnostic()))
def test_diagnostic_requires_every_top_level_field(field):
    value = _diagnostic()
    del value[field]
    with pytest.raises(gate.GateError, match="^DIAGNOSTIC_INVALID$"):
        gate.validate_diagnostic(value, REVISION)


@pytest.mark.parametrize("field", tuple(_failure()))
def test_diagnostic_requires_every_nested_failure_field(field):
    value = _diagnostic()
    del value["primary_failure"][field]
    with pytest.raises(gate.GateError, match="^DIAGNOSTIC_INVALID$"):
        gate.validate_diagnostic(value, REVISION)


def test_diagnostic_null_revision_only_represents_missing_preflight_configuration():
    value = _diagnostic(requested_revision=None,
                        primary_failure=_failure("preflight", "KEY_ERROR", "key_error"))
    assert gate.validate_diagnostic(value, None) == value
    assert gate.build_diagnostic(None, status="FAILED", primary_failure=value["primary_failure"]) == value
    with pytest.raises(gate.GateError, match="^DIAGNOSTIC_INVALID$"):
        gate.validate_diagnostic(value, REVISION)


@pytest.mark.parametrize("change", ({"status": "COMPLETE", "primary_failure": None},
    {"primary_failure": _failure("sdk_binding", "KEY_ERROR", "key_error")},
    {"primary_failure": _failure("preflight", "VALUE_ERROR", "value_error")},
    {"primary_failure": None, "audit_failure": _failure("audit_write")},
    {"requested_revision": REVISION}))
def test_diagnostic_cannot_erase_revision_binding_for_other_failures(change):
    value = _diagnostic(requested_revision=None,
                        primary_failure=_failure("preflight", "KEY_ERROR", "key_error"))
    value.update(change)
    with pytest.raises(gate.GateError, match="^DIAGNOSTIC_INVALID$"):
        gate.validate_diagnostic(value, None)


@pytest.mark.parametrize("expected", (True, 0, [], {}, "PRIVATE_CANARY", "b" * 40, "A" * 40))
def test_diagnostic_rejects_wrong_or_nonexact_expected_revision(expected):
    with pytest.raises(gate.GateError, match="^DIAGNOSTIC_INVALID$"):
        gate.validate_diagnostic(_diagnostic(), expected)


@pytest.mark.parametrize("mutation", ("record", "failure", "key", "nested_key", "revision", "schema", "status", "phase", "reason", "category", "expected"))
def test_diagnostic_rejects_builtin_subclass_impersonation(mutation):
    class String(str):
        pass

    class Mapping(dict):
        pass

    value = _diagnostic()
    expected = REVISION
    if mutation == "record":
        value = Mapping(value)
    elif mutation == "failure":
        value["primary_failure"] = Mapping(value["primary_failure"])
    elif mutation in {"key", "nested_key"}:
        target, key = (value, "status") if mutation == "key" else (value["primary_failure"], "phase")
        original = target.pop(key)
        target[String(key)] = original
    elif mutation == "expected":
        expected = String(expected)
    else:
        key = {"revision": "requested_revision", "schema": "schema_version", "reason": "reason_code",
               "category": "exception_category"}.get(mutation, mutation)
        target = value if mutation in {"revision", "schema", "status"} else value["primary_failure"]
        target[key] = String(target[key])
    with pytest.raises(gate.GateError, match="^DIAGNOSTIC_INVALID$"):
        gate.validate_diagnostic(value, expected)


@pytest.mark.parametrize("raw", (
    b'', b'{"status":"FAILED","status":"COMPLETE"}', b'{"value":NaN}', b'{"value":Infinity}',
    b'{"value":-Infinity}', b'{"value":', b'\xff', b'{}\n{}\n', b' ' * (gate.DIAGNOSTIC_MAX_BYTES + 1),
    b'{"exception_text":"PRIVATE_CANARY_NOT_FOR_OUTPUT"}',
))
def test_safe_diagnostic_reader_rejects_invalid_bytes_without_echo(tmp_path, raw):
    (tmp_path / "diagnostic.json").write_bytes(raw)
    report = gate.read_safe_diagnostic(tmp_path, REVISION)
    assert report == {"schema_version": gate.PREFIX + "diagnostic-report.v1", "validation": "INVALID",
                      "reason_code": "DIAGNOSTIC_INVALID", "diagnostic": None}
    assert "PRIVATE_CANARY" not in gate._encode(report)


def test_safe_diagnostic_reader_enforces_exact_4096_byte_cap(tmp_path):
    raw = json.dumps(_diagnostic()).encode()
    path = tmp_path / "diagnostic.json"
    path.write_bytes(raw + b' ' * (gate.DIAGNOSTIC_MAX_BYTES - len(raw)))
    assert gate.read_safe_diagnostic(tmp_path, REVISION)["validation"] == "VALID"
    path.write_bytes(path.read_bytes() + b' ')
    assert gate.read_safe_diagnostic(tmp_path, REVISION)["reason_code"] == "DIAGNOSTIC_INVALID"


@pytest.mark.parametrize("mutation", ("missing_directory", "missing_file", "read_error", "unexpected_error", "file_symlink", "directory_symlink"))
def test_safe_diagnostic_reader_has_fixed_unavailable_or_invalid_reports(tmp_path, monkeypatch, mutation):
    audit = tmp_path / "audit"
    audit.mkdir()
    _write(audit / "diagnostic.json", _diagnostic())
    expected = "DIAGNOSTIC_UNAVAILABLE"
    if mutation == "missing_directory":
        audit = tmp_path / "absent"
    elif mutation == "missing_file":
        (audit / "diagnostic.json").unlink()
    elif mutation in {"read_error", "unexpected_error"}:
        def fail(*args, **kwargs):
            raise (OSError if mutation == "read_error" else RuntimeError)("PRIVATE_CANARY")
        monkeypatch.setattr(gate, "read_bytes", fail)
        if mutation == "unexpected_error":
            expected = "DIAGNOSTIC_INVALID"
    elif mutation == "file_symlink":
        target = tmp_path / "private.json"
        (audit / "diagnostic.json").rename(target)
        (audit / "diagnostic.json").symlink_to(target)
        expected = "DIAGNOSTIC_INVALID"
    else:
        link = tmp_path / "link"
        link.symlink_to(audit, target_is_directory=True)
        audit = link
        expected = "DIAGNOSTIC_INVALID"
    report = gate.read_safe_diagnostic(audit, REVISION)
    assert report["reason_code"] == expected and report["diagnostic"] is None
    assert "PRIVATE_CANARY" not in gate._encode(report) and str(tmp_path) not in gate._encode(report)


def test_failed_partial_audit_exposes_only_safe_diagnostic_and_preserves_failure(unit_bundle, tmp_path, capsys):
    audit, _, source = unit_bundle
    failure = _diagnostic()
    _write(audit / "diagnostic.json", failure)
    (audit / "activity-metadata.jsonl").write_bytes(b'')
    junit = _junit(tmp_path / "unit.xml", ['<error>PRIVATE_CANARY</error>'] * 7)
    summary = tmp_path / "summary.txt"
    assert gate.main(_main_args(audit, source, junit, summary)) == 1
    output = capsys.readouterr().out
    acceptance, report = [json.loads(line) for line in output.splitlines()]
    assert acceptance["acceptance"] == "FAIL" and acceptance["counts"]["ERROR"] == 7
    assert {"SIZE_LIMIT", "TEST_ERROR", "DIAGNOSTIC_FAILED"} <= set(acceptance["reason_codes"])
    assert not acceptance["evidence_complete"] and not acceptance["cleanup_verified"]
    assert report["validation"] == "VALID" and report["diagnostic"] == failure
    assert "PRIVATE_CANARY" not in output + summary.read_text()
    assert str(tmp_path) not in output + summary.read_text()
    assert json.loads(summary.read_text().splitlines()[-1]) == report
    assert set(acceptance) == {"schema_version", "candidate_revision", "required_node_count", "collected_node_count",
        "nodes", "counts", "evidence_complete", "privacy_check", "cleanup_verified", "acceptance", "reason_codes"}


def test_failed_diagnostic_cannot_pass_otherwise_complete_unit_audit(unit_bundle, tmp_path, capsys):
    audit, _, source = unit_bundle
    _write(audit / "diagnostic.json", _diagnostic())
    with pytest.raises(gate.GateError, match="^DIAGNOSTIC_FAILED$"):
        gate.validate_audit(audit, REVISION, gate.REQUIRED_NODES)
    assert gate.main(_main_args(audit, source, _junit(tmp_path / "unit.xml"))) == 1
    acceptance, report = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert acceptance["acceptance"] == "FAIL" and report["diagnostic"]["status"] == "FAILED"


@pytest.mark.parametrize("mutation", ("missing_receipt", "empty_rows", "incomplete_rows", "malformed_rows", "cleanup", "junit"))
def test_complete_diagnostic_cannot_override_any_partial_or_failed_gate(unit_bundle, tmp_path, capsys, mutation):
    audit, records, source = unit_bundle
    junit = _junit(tmp_path / "unit.xml")
    if mutation == "missing_receipt":
        (audit / "replay.json").unlink()
    elif mutation == "empty_rows":
        (audit / "activity-metadata.jsonl").write_bytes(b'')
    elif mutation == "incomplete_rows":
        _write(audit / "activity-metadata.jsonl", records["activity-metadata.jsonl"][:1])
    elif mutation == "malformed_rows":
        (audit / "activity-metadata.jsonl").write_bytes(b'{"private":"PRIVATE_CANARY"\n')
    elif mutation == "cleanup":
        records["cleanup.json"]["cleanup_status"] = "UNCONFIRMED"
        _write(audit / "cleanup.json", records["cleanup.json"])
    else:
        _junit(junit, ['<error>PRIVATE_CANARY</error>'] + [""] * 6)
    assert gate.main(_main_args(audit, source, junit)) == 1
    output = capsys.readouterr().out
    acceptance, report = [json.loads(line) for line in output.splitlines()]
    assert acceptance["acceptance"] == "FAIL"
    assert report["validation"] == "VALID" and report["diagnostic"]["status"] == "COMPLETE"
    assert '"audit_file"' not in output and "PRIVATE_CANARY" not in output


@pytest.mark.parametrize("mutation", ("missing", "private_field", "private_category", "wrong_revision", "oversized"))
def test_missing_or_invalid_diagnostic_never_prints_untrusted_fields(unit_bundle, tmp_path, capsys, mutation):
    audit, _, source = unit_bundle
    value = _diagnostic()
    expected = "DIAGNOSTIC_INVALID"
    if mutation == "missing":
        (audit / "diagnostic.json").unlink()
        expected = "DIAGNOSTIC_UNAVAILABLE"
    elif mutation == "oversized":
        (audit / "diagnostic.json").write_bytes(b'PRIVATE_CANARY' * 4096)
    else:
        if mutation == "private_field":
            value["traceback"] = "PRIVATE_CANARY_NOT_FOR_OUTPUT"
        elif mutation == "private_category":
            value["primary_failure"]["exception_category"] = "PRIVATE_CANARY_NOT_FOR_OUTPUT"
        else:
            value["requested_revision"] = "b" * 40
        _write(audit / "diagnostic.json", value)
    summary = tmp_path / "summary.txt"
    assert gate.main(_main_args(audit, source, _junit(tmp_path / "unit.xml"), summary)) == 1
    output = capsys.readouterr().out
    acceptance, report = [json.loads(line) for line in output.splitlines()]
    assert acceptance["acceptance"] == "FAIL" and expected in acceptance["reason_codes"]
    assert report["reason_code"] == expected and report["diagnostic"] is None
    assert "PRIVATE_CANARY" not in output + summary.read_text()
    assert '"audit_file"' not in output


# BATCH_PREPARATION_TESTS: self-contained stdlib section, also collectable by pytest.
# These are fabricated finite fixtures. No sleeps, SDK imports, process or service.
import unittest as _batch_unittest
import sys as _batch_sys
import importlib as _batch_importlib
from copy import deepcopy as _batch_copy
from pathlib import Path as _BatchPath
import hashlib as _batch_hashlib
import json as _batch_json

_batch_root = _BatchPath(__file__).resolve().parents[1]
if str(_batch_root / "ci") not in _batch_sys.path:
    _batch_sys.path.insert(0, str(_batch_root / "ci"))
_batch_gate = _batch_importlib.import_module("verify_temporal_server_gate")
_BATCH_REVISION = "a" * 40


def _batch_result(job):
    index = int(job["job_id"][-3:])
    return {"job_id": job["job_id"], "workflow_id": job["workflow_id"],
            "run_id": f"00000000-0000-0000-0000-{index + 1:012x}",
            "activity_id": _batch_gate.ACTIVITY_ID, "invocation_id": f"inv-{index:03d}",
            "attempt": 1, "receipt_id": f"{index + 1:024x}",
            "input_artifact_id": job["input_artifact_id"],
            "result_artifact_id": "sha256:" + _batch_hashlib.sha256(("result-" + job["job_id"]).encode()).hexdigest(),
            "result_input_artifact_id": job["input_artifact_id"], "result_size_bytes": 1024,
            "tool_status": "COMPLETED", "semantic_valid": True, "output": 199,
            "reconciliation_required": False, "transport_status": "COMPLETED"}


def _batch_fixture_trace(width=1):
    plan = _batch_gate.frozen_batch_plan()
    events, outcomes = [], []
    def add(job_id, kind, details):
        events.append({"sequence": len(events) + 1, "elapsed_us": len(events) * 10,
                       "job_id": job_id, "kind": kind, "details": details})
    for start in range(0, 200, width):
        group = plan["jobs"][start:start + width]
        for job in group:
            result = _batch_result(job)
            outcomes.append(result)
            add(job["job_id"], "reserve", {"attempt": 1, "output_allowance_bytes": 16384})
            add(job["job_id"], "ack", {"workflow_id": job["workflow_id"], "run_id": result["run_id"]})
        for job in group:
            result = _batch_result(job)
            add(job["job_id"], "activity_begin", {key: result[key] for key in
                ("workflow_id", "run_id", "activity_id", "invocation_id", "attempt")} |
                {"maximum_attempts": 1, "start_to_close_seconds": 10,
                 "schedule_to_close_seconds": 60, "is_local": False})
            add(job["job_id"], "execute_enter", {"invocation_id": result["invocation_id"]})
            add(job["job_id"], "handler_enter", {"invocation_id": result["invocation_id"]})
        for job in group:
            result = _batch_result(job)
            add(job["job_id"], "handler_return", {"invocation_id": result["invocation_id"]})
            add(job["job_id"], "activity_end", {"invocation_id": result["invocation_id"]})
            add(job["job_id"], "terminal", {"result_artifact_id": result["result_artifact_id"],
                                           "receipt_id": result["receipt_id"]})
    return {"schema_version": _batch_gate.BATCH_SCHEMA + "trace.v1",
            "evidence_kind": "FABRICATED_UNIT_DATA", "revision": _BATCH_REVISION,
            "source_sha256": _batch_gate.current_batch_source_digests(_batch_root),
            "plan": plan, "profile": dict(_batch_gate.BATCH_PROFILE),
            "events": events, "outcomes": outcomes}


def _batch_renumber(trace):
    for index, row in enumerate(trace["events"]):
        row["sequence"], row["elapsed_us"] = index + 1, index * 10


class BatchVerifierPreparationTests(_batch_unittest.TestCase):
    def verify(self, trace):
        return _batch_gate.validate_batch_trace(trace, _BATCH_REVISION, _batch_root)

    def rejects(self, trace):
        with self.assertRaises(_batch_gate.GateError):
            self.verify(trace)

    def test_batch_verifier_counts_actual_overlap_not_configured_slots(self):
        for width in (1, 2, 8):
            with self.subTest(width=width):
                result = self.verify(_batch_fixture_trace(width))
                self.assertEqual(result["acceptance"], "PASS")
                self.assertEqual(result["observed_activity_peak"], width)
                self.assertEqual(result["configured_activity_slots"], 8)
                self.assertEqual(result["validated_terminal"], 200)
                self.assertEqual(result["outstanding"], 0)
                self.assertEqual(result["evidence_kind"], "FABRICATED_UNIT_DATA")
                self.assertLessEqual(len(_batch_json.dumps(result).encode()), 65536)

    def test_batch_verifier_rejects_ninth_activity_and_unbalanced_trace(self):
        self.rejects(_batch_fixture_trace(9))
        trace = _batch_fixture_trace()
        trace["events"] = trace["events"][:-2]
        trace["outcomes"] = trace["outcomes"][:-1]
        result = self.verify(trace)
        self.assertEqual(result["acceptance"], "FAIL")
        self.assertEqual(result["active_at_end"], 1)
        self.assertEqual(result["outstanding"], 1)

    def test_batch_verifier_rejects_event_cardinality_and_sequence_faults(self):
        for kind in ("activity_begin", "execute_enter", "handler_enter", "handler_return", "activity_end", "terminal", "ack", "reserve"):
            with self.subTest(kind=kind):
                trace = _batch_fixture_trace()
                index = next(i for i, row in enumerate(trace["events"]) if row["kind"] == kind)
                trace["events"].insert(index, _batch_copy(trace["events"][index]))
                _batch_renumber(trace)
                self.rejects(trace)
        for mutation in ("missing_begin", "missing_exit", "exit_first", "sequence", "time", "boolean", "retry", "invocation", "reset"):
            with self.subTest(mutation=mutation):
                trace = _batch_fixture_trace()
                if mutation == "missing_begin": del trace["events"][2]
                if mutation == "missing_exit": del trace["events"][6]
                if mutation == "exit_first": trace["events"][2]["kind"] = "activity_end"
                if mutation == "sequence": trace["events"][1]["sequence"] = 1
                if mutation == "time": trace["events"][2]["elapsed_us"] = 0
                if mutation == "boolean": trace["events"][0]["sequence"] = True
                if mutation == "retry": trace["events"][2]["details"]["attempt"] = 2
                if mutation == "invocation": trace["events"][10]["details"]["invocation_id"] = "inv-000"
                if mutation == "reset": trace["events"][2]["kind"] = "continued_as_new"
                self.rejects(trace)

        for event_index, delta in ((5, 1000001), (6, 10000001), (7, 60000001)):
            with self.subTest(deadline_event=event_index):
                trace = _batch_fixture_trace()
                for event in trace["events"][event_index:]:
                    event["elapsed_us"] += delta
                self.rejects(trace)

    def test_batch_verifier_binds_every_job_to_original_outcome_and_artifacts(self):
        for field in ("result_artifact_id", "receipt_id"):
            with self.subTest(swap=field):
                trace = _batch_fixture_trace()
                first, second = trace["events"][7], trace["events"][15]
                first["details"][field], second["details"][field] = second["details"][field], first["details"][field]
                self.rejects(trace)
        for field, bad in (("job_id", "batch-001"), ("workflow_id", "opendot-batch-001"),
                ("run_id", "00000000-0000-0000-0000-000000000002"), ("attempt", 2),
                ("input_artifact_id", "sha256:" + "0" * 64),
                ("result_input_artifact_id", "sha256:" + "0" * 64),
                ("result_size_bytes", 16385), ("activity_id", "other"),
                ("invocation_id", "inv-001")):
            with self.subTest(field=field):
                trace = _batch_fixture_trace()
                trace["outcomes"][0][field] = bad
                self.rejects(trace)
        for mutation in ("orphan", "missing", "duplicate", "same_receipt", "same_output"):
            with self.subTest(mutation=mutation):
                trace = _batch_fixture_trace()
                if mutation == "orphan": trace["events"] = trace["events"][:-1]
                if mutation == "missing": trace["outcomes"].pop()
                if mutation == "duplicate": trace["outcomes"][1] = _batch_copy(trace["outcomes"][0])
                if mutation == "same_receipt": trace["outcomes"][1]["receipt_id"] = trace["outcomes"][0]["receipt_id"]
                if mutation == "same_output": trace["outcomes"][1]["result_artifact_id"] = trace["outcomes"][0]["result_artifact_id"]
                self.rejects(trace)

    def test_batch_verifier_preserves_unknowns_and_rejects_blind_replay(self):
        for reason in sorted(_batch_gate.BATCH_UNCERTAINTY_REASONS):
            with self.subTest(reason=reason):
                trace = _batch_fixture_trace()
                trace["events"] = trace["events"][:8]
                trace["outcomes"] = trace["outcomes"][:1]
                trace["events"].insert(2, {"job_id": "batch-000", "kind": "uncertain", "details": {"reason": reason}})
                _batch_renumber(trace)
                verdict = self.verify(trace)
                self.assertEqual(verdict["acceptance"], "FAIL")
                self.assertTrue(verdict["uncertainty_latched"])
                self.assertEqual(verdict["reserved_attempts"], 1)
                self.assertEqual(verdict["validated_terminal"], 1)
                trace["events"].append({"job_id": "batch-001", "kind": "reserve",
                                        "details": {"attempt": 1, "output_allowance_bytes": 16384}})
                _batch_renumber(trace)
                self.rejects(trace)

    def test_batch_verifier_never_promotes_transport_only_or_invalid_outcomes(self):
        for field, value in (("tool_status", "FAILED"), ("tool_status", "BLOCKED"),
                ("semantic_valid", False), ("output", 198), ("output", None),
                ("reconciliation_required", True), ("transport_status", "UNKNOWN")):
            with self.subTest(field=field, value=value):
                trace = _batch_fixture_trace()
                trace["events"] = trace["events"][:8]
                trace["outcomes"] = trace["outcomes"][:1]
                trace["outcomes"][0][field] = value
                verdict = self.verify(trace)
                self.assertEqual(verdict["acceptance"], "FAIL")
                self.assertEqual(verdict["validated_terminal"], 0)
                self.assertEqual(verdict["outstanding"], 1)
                self.assertTrue(verdict["uncertainty_latched"])

    def test_batch_reports_queue_wait_and_cohort_completion_without_fairness_claim(self):
        verdict = self.verify(_batch_fixture_trace(8))
        self.assertEqual(verdict["clock_scope"], "SYNTHETIC_FIXTURE_MICROSECONDS")
        self.assertEqual([row["validated_terminal"] for row in verdict["cohorts"]], [100, 100])
        self.assertGreater(verdict["jobs"][0]["queue_wait_us"], 0)
        self.assertGreater(verdict["jobs"][0]["activity_duration_us"], 0)
        for forbidden in ("throughput", "speedup", "agent_count", "fairness", "cpu_parallelism"):
            self.assertNotIn(forbidden, verdict)
        trace = _batch_fixture_trace()
        trace["events"] = trace["events"][:8]
        trace["outcomes"] = trace["outcomes"][:1]
        partial = self.verify(trace)
        self.assertEqual(partial["cohorts"][1]["missing"], 100)
        self.assertEqual(partial["acceptance"], "FAIL")

    def test_batch_verifier_reconstructs_sixteen_outstanding_without_trusting_counts(self):
        trace = _batch_fixture_trace()
        trace["events"], trace["outcomes"] = [], []
        for index in range(16):
            trace["events"].append({"job_id": f"batch-{index:03d}", "kind": "reserve",
                                    "details": {"attempt": 1, "output_allowance_bytes": 16384}})
        _batch_renumber(trace)
        verdict = self.verify(trace)
        self.assertEqual((verdict["outstanding"], verdict["peak_outstanding"]), (16, 16))
        trace["events"].append({"job_id": "batch-016", "kind": "reserve",
                                "details": {"attempt": 1, "output_allowance_bytes": 16384}})
        _batch_renumber(trace)
        self.rejects(trace)

    def test_batch_verifier_rejects_size_privacy_and_source_binding_failures(self):
        for mutation in ("source", "revision", "hosted", "private", "token", "large", "rows", "profile", "plan_bool"):
            with self.subTest(mutation=mutation):
                trace = _batch_fixture_trace()
                if mutation == "source": trace["source_sha256"]["ci/run_temporal_server_gate.py"] = "0" * 64
                if mutation == "revision": trace["revision"] = "b" * 40
                if mutation == "hosted": trace["evidence_kind"] = "REAL_SERVER"
                if mutation == "private": trace["private_path"] = "/private/canary"
                if mutation == "token": trace["events"][0]["details"]["token"] = "PRIVATE_CANARY"
                if mutation == "large": trace["events"][0]["details"]["extra"] = "x" * 1025
                if mutation == "rows": trace["events"] = [trace["events"][0]] * 4097
                if mutation == "profile": trace["profile"]["activity_slots"] = 9
                if mutation == "plan_bool": trace["plan"]["jobs"][0]["payload"]["left"] = False
                self.rejects(trace)
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}'):
            with self.subTest(raw=raw), self.assertRaises(_batch_gate.GateError):
                _batch_gate.strict_json(raw)
        with self.assertRaises(_batch_gate.GateError):
            _batch_gate._batch_encoded({"rows": ["x" * 256] * 256}, 65536)


# Strict collected-node/JUnit mapping for module functions and unittest methods.
import tempfile as _unit_tempfile
import xml.etree.ElementTree as _unit_et


class UnitJunitIdentityTests(_batch_unittest.TestCase):
    def verify_rows(self, nodes, rows, *, files=("tests/test_fixed.py",), expected_count=None):
        root = _unit_et.Element("testsuite", {"tests": "999", "failures": "999"})
        for classname, name, status in rows:
            attrs = {}
            if classname is not None: attrs["classname"] = classname
            if name is not None: attrs["name"] = name
            case = _unit_et.SubElement(root, "testcase", attrs)
            for tag in status:
                _unit_et.SubElement(case, tag).text = "PRIVATE_DIAGNOSTIC"
        with _unit_tempfile.TemporaryDirectory(prefix="opendot-unit-junit-") as directory:
            path = _BatchPath(directory) / "results.xml"
            path.write_bytes(_unit_et.tostring(root, encoding="utf-8"))
            return _batch_gate.verify_collected_unit_junit(nodes, path, files=files,
                expected_count=len(nodes) if expected_count is None else expected_count)

    def test_unit_junit_matches_module_class_and_exact_parameter_identities(self):
        nodes = ["tests/test_fixed.py::test_same",
                 "tests/test_fixed.py::Case::test_same",
                 "tests/test_fixed.py::Case::Nested::test_same",
                 "tests/test_fixed.py::test_param[a.b/c::d[e]]",
                 "tests/test_fixed.py::Case::test_param[a.b/c::d[e]]"]
        rows = [("tests.test_fixed", "test_same", ()),
                ("tests.test_fixed.Case", "test_same", ()),
                ("tests.test_fixed.Case.Nested", "test_same", ()),
                ("tests.test_fixed", "test_param[a.b/c::d[e]]", ()),
                ("tests.test_fixed.Case", "test_param[a.b/c::d[e]]", ())]
        result = self.verify_rows(nodes, rows[::-1])
        self.assertEqual([row["node_id"] for row in result], nodes)
        self.assertTrue(all(row["outcome"] == "PASS" for row in result))
        long_name = "test_long[" + " " * 65536 + "]"
        self.assertEqual(self.verify_rows(["tests/test_fixed.py::" + long_name],
            [("tests.test_fixed", long_name, ())])[0]["outcome"], "PASS")

    def test_unit_junit_rejects_ambiguous_or_invalid_collected_identities(self):
        files = ("tests/test_fixed.py", "tests/test_fixed/Case.py")
        ambiguous = ["tests/test_fixed.py::Case::test_same", "tests/test_fixed/Case.py::test_same"]
        with self.assertRaises(_batch_gate.GateError):
            self.verify_rows(ambiguous, [("tests.test_fixed.Case", "test_same", ())] * 2, files=files)
        for nodes, selected, expected in ((["tests/test_fixed.py::test_a"] * 2, ("tests/test_fixed.py",), 2),
                (["tests/foreign.py::test_a"], ("tests/test_fixed.py",), 1),
                (["tests/test_fixed.py::Case::::test_a"], ("tests/test_fixed.py",), 1),
                (["tests/test_fixed.py::test_a[unclosed"], ("tests/test_fixed.py",), 1),
                (["tests/test_fixed.py::test_a\n"], ("tests/test_fixed.py",), 1),
                (["tests/test_fixed.py::test_a"], ("tests/test_fixed.py",) * 2, 1),
                (["tests/test_fixed.py::test_a"], ("tests/test_fixed.py",), True),
                (["tests/test_fixed.py::test_a"], ("tests/test_fixed.py",), 2)):
            with self.subTest(nodes=nodes, files=selected, expected=expected), self.assertRaises(_batch_gate.GateError):
                self.verify_rows(nodes, [("tests.test_fixed", "test_a", ())], files=selected, expected_count=expected)

    def test_unit_junit_rejects_duplicate_missing_extra_or_mismatched_cases(self):
        nodes = ["tests/test_fixed.py::test_a", "tests/test_fixed.py::Case::test_b[x::y.z/q]"]
        correct = [("tests.test_fixed", "test_a", ()), ("tests.test_fixed.Case", "test_b[x::y.z/q]", ())]
        variants = [correct[:1], correct + correct[:1], correct[:1] * 2,
                    [("tests.test_fixed.Case", "test_a", ()), correct[1]],
                    [correct[0], ("tests.test_fixed/Case", "test_b[x::y.z/q]", ())],
                    [correct[0], ("tests.test_fixed.Case", "test_b[x/y/z/q]", ())],
                    [correct[0], (None, "test_b[x::y.z/q]", ())],
                    [correct[0], ("tests.test_fixed.Case", None, ())]]
        for rows in variants:
            with self.subTest(rows=rows), self.assertRaises(_batch_gate.GateError):
                self.verify_rows(nodes, rows)

    def test_unit_junit_preserves_failure_error_and_skip_outcomes(self):
        for tag, expected in (("failure", "FAIL"), ("error", "ERROR"), ("skipped", "SKIP")):
            with self.subTest(tag=tag):
                result = self.verify_rows(["tests/test_fixed.py::Case::test_a"],
                    [("tests.test_fixed.Case", "test_a", (tag,))])
                self.assertEqual(result[0]["outcome"], expected)
                self.assertNotEqual(result[0]["reason_code"], "OK")
                self.assertNotIn("PRIVATE_DIAGNOSTIC", repr(result))
        with self.assertRaises(_batch_gate.GateError):
            self.verify_rows(["tests/test_fixed.py::test_a"],
                             [("tests.test_fixed", "test_a", ("failure", "error"))])

    def test_unit_junit_identity_limits_fail_without_normalizing_or_truncating(self):
        with self.assertRaises(_batch_gate.GateError):
            self.verify_rows(["tests/test_fixed.py::test_a[" + "x" * (128 * 1024) + "]"], [])
        nodes = [f"tests/test_fixed.py::test_a[{index:02d}" + "x" * 100000 + "]" for index in range(22)]
        with self.assertRaises(_batch_gate.GateError):
            self.verify_rows(nodes, [])
        with self.assertRaises(_batch_gate.GateError):
            self.verify_rows([True], [])

# Live-shaped fixtures deliberately retain FABRICATED_UNIT_DATA. They exercise
# only the independent pure validator, never hosted acceptance or a service.
def _real_batch_fixture(width=1, *, early_activity=False):
    plan = gate.frozen_batch_plan()
    events, metadata, histories, outcomes = [], [], [], []
    def add(job, event):
        terminal = _batch_result(job)
        invocation = event.startswith(("activity_", "execute_", "handler_"))
        row = {"sequence": len(events) + 1, "elapsed_us": len(events) * 10,
            "event": event, "job_id": job["job_id"],
            "run_id": None if event in {"reservation", "rpc_enter"} else terminal["run_id"],
            "activity_id": gate.ACTIVITY_ID if invocation else None,
            "attempt": 1 if invocation else None, "reason_code": "OK"}
        events.append(row)
        if event == "activity_enter":
            metadata.append({"job_id": job["job_id"], "entry_sequence": row["sequence"],
                "workflow_id": job["workflow_id"], "run_id": terminal["run_id"],
                "activity_id": gate.ACTIVITY_ID, "activity_type": gate.ACTIVITY_TYPE,
                "namespace": "default", "task_queue": "opendot-temporal-gate", "attempt": 1,
                "is_local": False, "retry_policy_present": True, "maximum_attempts": 1,
                "start_to_close_seconds": 10, "schedule_to_close_seconds": 60,
                "input_artifact_id": job["input_artifact_id"], "metadata_source": "real_sdk_activity_info"})
    for start in range(0, 200, width):
        group = plan["jobs"][start:start + width]
        for job in group:
            add(job, "reservation")
            add(job, "rpc_enter")
            if early_activity:
                for event in ("activity_enter", "execute_enter", "handler_enter"):
                    add(job, event)
                if width == 1:
                    for event in ("handler_return", "execute_return", "activity_exit"):
                        add(job, event)
            add(job, "acknowledgment")
        if not early_activity:
            for job in group:
                for event in ("activity_enter", "execute_enter", "handler_enter"):
                    add(job, event)
        for job in group:
            if not early_activity or width != 1:
                for event in ("handler_return", "execute_return", "activity_exit"):
                    add(job, event)
            add(job, "workflow_result")
            add(job, "validated_terminal")
            terminal = _batch_result(job)
            outcomes.append({"terminal": terminal, "original_validation": "CAS_RECEIPT_INPUT_BOUND",
                "receipt_report_kind": "serialized_runtime_report_not_live_proof",
                "scientific_validity": False, "device_control_authority": False,
                "independent_review": "NOT_EVALUATED", "owner_integration": "NOT_EVALUATED"})
            # The old fixture helper supplies the common SDK event shape only.
            _, original, _ = _base_history("durability_replay")
            projected = deepcopy(original)
            projected[0]["attributes"]["workflow_type"] = "ReferenceBatchWorkflow"
            projected[0]["attributes"].update(workflow_id=job["workflow_id"],
                original_execution_run_id=terminal["run_id"], first_execution_run_id=terminal["run_id"],
                attempt=1, continued_execution_run_id="")
            result = {"response_schema": gate.RESPONSE_SCHEMA,
                "result_artifact_id": terminal["result_artifact_id"],
                "result_sha256": terminal["result_artifact_id"][7:],
                "result_size_bytes": terminal["result_size_bytes"]}
            projected[6]["attributes"].update(result)
            projected.append({"event_id": 11, "event_type": "WorkflowExecutionCompleted", "attributes": result})
            raw = json.dumps(projected).encode()
            histories.append({"job_id": job["job_id"], "workflow_id": job["workflow_id"],
                "run_id": terminal["run_id"], "raw_history_sha256": hashlib.sha256(raw).hexdigest(),
                "raw_history_bytes": len(raw), "events": projected})
    trace = {"schema_version": gate.REAL_BATCH_PREFIX + "trace.v1",
        "evidence_kind": "FABRICATED_UNIT_DATA", "revision": REVISION,
        "source_sha256": {path: gate.BATCH_OWNER_SHA256.get(path, _digest("fabricated-" + path))
                          for path in gate.REAL_BATCH_SOURCE_PATHS},
        "clock_scope": "HOST_MONOTONIC_OBSERVATIONS",
        "sdk_transport_retries": dict(gate.REAL_BATCH_RETRY_DECLARATION),
        "plan": plan, "profile": dict(gate.BATCH_PROFILE), "events": events}
    return trace, metadata, histories, outcomes


def _verify_real_fixture(bundle, monkeypatch):
    trace, metadata, histories, outcomes = bundle
    sources = {path: gate.BATCH_OWNER_SHA256.get(path, _digest("fabricated-" + path))
               for path in gate.REAL_BATCH_SOURCE_PATHS}
    monkeypatch.setattr(gate, "real_batch_source_digests", lambda source=None: sources)
    return gate.validate_real_batch_trace(trace, gate.frozen_batch_plan(), dict(gate.BATCH_PROFILE),
        metadata, histories, outcomes, allow_test_data=True, expected_revision=REVISION)


def _real_cleanup():
    historical = _fabricated_records()["cleanup.json"]
    return {"schema_version": gate.REAL_BATCH_PREFIX + "cleanup.v1",
        "server_generations": historical["server_generations"][:1],
        "worker_generations": [{"generation": i, "type": kind, "public_shutdown_called": True,
            "public_shutdown_completed": True} for i, kind in enumerate(("workflow", "activity"), 1)],
        "all_reservations_accounted": True, "unresolved_start_operations": 0,
        "unresolved_result_operations": 0, "active_activity_calls": 0,
        "handler_entries": 200, "handler_returns": 200, "execution_uncertainty": False,
        "observation_uncertainty": False, "in_flight_shutdown_attempted": False,
        "forced_termination_used": False, "cleanup_status": "PASS", "cleanup_code": "OK",
        "elapsed_seconds": 20.0}


@pytest.mark.parametrize("width", (1, 2, 8))
@pytest.mark.parametrize("early_activity", (False, True))
def test_real_batch_fixture_partial_order_and_measured_overlap(monkeypatch, width, early_activity):
    result = _verify_real_fixture(_real_batch_fixture(width, early_activity=early_activity), monkeypatch)
    assert result["delivery_admission_acceptance"] == "PASS"
    assert result["observed_activity_peak"] == result["observed_handler_peak"] == width
    assert result["activity_overlap"] == ("NOT_DEMONSTRATED" if width == 1 else "DEMONSTRATED")
    assert result["evidence_kind"] == "FABRICATED_UNIT_DATA"
    assert result["schema_version"].endswith("fixture-verdict.v1")
    assert result["clock_scope"] == "HOST_MONOTONIC_OBSERVATIONS"
    assert result["cpu_parallelism"] == "NOT_EVALUATED"
    assert result["sdk_transport_retries"]["physical_rpc_count_claimed"] is False
    assert "acceptance" not in result and len(gate._real_encoded(result, 65536)) < 65536


def test_real_batch_fabricated_data_cannot_enter_hosted_verifier(monkeypatch):
    trace, metadata, histories, outcomes = bundle = _real_batch_fixture()
    _verify_real_fixture(bundle, monkeypatch)
    with pytest.raises(gate.GateError, match="INVALID_SCHEMA"):
        gate.validate_real_batch_trace(trace, trace["plan"], trace["profile"], metadata, histories, outcomes)
    # Opting into test mode cannot relabel a hosted record into a fixture pass.
    trace["evidence_kind"] = "HOSTED_REAL_SERVICE"
    with pytest.raises(gate.GateError, match="INVALID_SCHEMA"):
        _verify_real_fixture(bundle, monkeypatch)


@pytest.mark.parametrize("section,key,value", (
    ("trace", "schema_version", gate.BATCH_SCHEMA + "trace.v1"),
    ("trace", "evidence_kind", "HOSTED_REAL_SERVICE"),
    ("trace", "clock_scope", "SYNTHETIC_FIXTURE_MICROSECONDS"),
    ("trace", "revision", "b" * 40),
    ("trace", "private_token", "PRIVATE_CANARY"),
    ("profile", "activity_slots", 9), ("profile", "outstanding_limit", 17),
    ("profile", "executor_workers", 9), ("profile", "job_count", 201),
    ("profile", "disable_eager_activity_execution", False),
    ("profile", "maximum_attempts", True),
    ("retry", "physical_rpc_count_claimed", True), ("retry", "retry_config_supplied", True),
    ("retry", "high_level_start_retry", False), ("retry", "policy", "DISABLED"),
    ("metadata", "attempt", 2), ("metadata", "attempt", True),
    ("metadata", "maximum_attempts", 2), ("metadata", "retry_policy_present", False),
    ("metadata", "start_to_close_seconds", 11), ("metadata", "schedule_to_close_seconds", 61),
    ("metadata", "is_local", True), ("metadata", "namespace", "private"),
    ("metadata", "task_queue", "other"), ("metadata", "activity_type", "arbitrary.tool"),
    ("metadata", "workflow_id", "opendot-batch-199"),
    ("metadata", "run_id", _run_id(999)), ("metadata", "entry_sequence", 1),
    ("metadata", "input_artifact_id", "sha256:" + "e" * 64),
    ("metadata", "metadata_source", "fixture"), ("metadata", "task_token", "PRIVATE_CANARY"),
    ("outcome", "original_validation", "OUTPUT_ONLY"),
    ("outcome", "receipt_report_kind", "live_proof"),
    ("outcome", "scientific_validity", True), ("outcome", "device_control_authority", True),
    ("outcome", "owner_integration", "PASS"), ("outcome", "independent_review", "PASS"),
    ("terminal", "workflow_id", "opendot-batch-199"),
    ("terminal", "run_id", _run_id(999)), ("terminal", "attempt", 2),
    ("terminal", "input_artifact_id", "sha256:" + "e" * 64),
    ("terminal", "result_input_artifact_id", "sha256:" + "e" * 64),
    ("terminal", "result_size_bytes", 16385), ("terminal", "tool_status", "BLOCKED"),
    ("terminal", "tool_status", "FAILED"), ("terminal", "semantic_valid", False),
    ("terminal", "output", 200), ("terminal", "reconciliation_required", True),
    ("terminal", "transport_status", "UNKNOWN"),
    ("history", "workflow_id", "opendot-batch-199"),
    ("history", "run_id", _run_id(999)), ("history", "raw_history_bytes", 65537),
    ("history", "raw_history_sha256", "PRIVATE_CANARY"),
    ("history", "raw_history", "PRIVATE_CANARY"),
))
def test_real_batch_rejects_unbound_or_unapproved_fields(monkeypatch, section, key, value):
    trace, metadata, histories, outcomes = bundle = _real_batch_fixture()
    row = {"trace": trace, "profile": trace["profile"], "retry": trace["sdk_transport_retries"],
           "metadata": metadata[0], "outcome": outcomes[0], "terminal": outcomes[0]["terminal"],
           "history": histories[0]}[section]
    row[key] = value
    with pytest.raises(gate.GateError):
        _verify_real_fixture(bundle, monkeypatch)


@pytest.mark.parametrize("mutation", (
    "source_missing", "source_extra", "source_digest", "metadata_missing", "metadata_duplicate",
    "outcome_missing", "outcome_duplicate", "history_missing", "history_duplicate",
    "reused_receipt", "reused_result", "swapped_outcomes", "swapped_histories", "duplicate_raw_history",
    "ninth_activity", "event_duplicate", "event_missing", "clock_regression", "sequence_gap",
    "private_event", "row_oversize", "trace_oversize", "metadata_oversize", "outcome_oversize",
    "history_event_limit", "history_row_limit", "table_row_limit", "unknown_job", "no_reservation",
    "no_rpc", "no_ack", "ack_run_mismatch", "two_acks", "terminal_before_result", "handler_before_execute",
))
def test_real_batch_adversarial_trace_and_table_bindings(monkeypatch, mutation):
    trace, metadata, histories, outcomes = bundle = _real_batch_fixture(9 if mutation == "ninth_activity" else 1)
    if mutation.startswith("source_"):
        if mutation == "source_missing":
            trace["source_sha256"].pop(next(iter(trace["source_sha256"])))
        elif mutation == "source_extra":
            trace["source_sha256"]["/PRIVATE_CANARY"] = "0" * 64
        else:
            trace["source_sha256"][next(iter(trace["source_sha256"]))] = "0" * 64
    elif mutation.endswith("_missing") and mutation.split("_")[0] in {"metadata", "outcome", "history"}:
        {"metadata": metadata, "outcome": outcomes, "history": histories}[mutation.split("_")[0]].pop(0)
    elif mutation.endswith("_duplicate") and mutation.split("_")[0] in {"metadata", "outcome", "history"}:
        rows = {"metadata": metadata, "outcome": outcomes, "history": histories}[mutation.split("_")[0]]
        rows[-1] = deepcopy(rows[0])
    elif mutation in {"reused_receipt", "reused_result"}:
        key = "receipt_id" if mutation == "reused_receipt" else "result_artifact_id"
        outcomes[1]["terminal"][key] = outcomes[0]["terminal"][key]
    elif mutation == "swapped_outcomes":
        for key in ("result_artifact_id", "receipt_id"):
            outcomes[0]["terminal"][key], outcomes[1]["terminal"][key] = outcomes[1]["terminal"][key], outcomes[0]["terminal"][key]
    elif mutation == "swapped_histories":
        histories[0]["events"], histories[1]["events"] = histories[1]["events"], histories[0]["events"]
    elif mutation == "duplicate_raw_history":
        histories[1]["raw_history_sha256"] = histories[0]["raw_history_sha256"]
    elif mutation == "event_duplicate":
        trace["events"][4] = deepcopy(trace["events"][3])
    elif mutation == "event_missing":
        trace["events"].pop(4)
    elif mutation == "clock_regression":
        trace["events"][4]["elapsed_us"] = 0
    elif mutation == "sequence_gap":
        trace["events"][4]["sequence"] += 1
    elif mutation == "private_event":
        trace["events"][4]["exception"] = "PRIVATE_CANARY"
    elif mutation == "row_oversize":
        trace["events"][4]["reason_code"] = "x" * 1025
    elif mutation == "trace_oversize":
        trace["events"] = trace["events"] * 2
    elif mutation == "metadata_oversize":
        metadata[0]["task_queue"] = "x" * 1025
    elif mutation == "outcome_oversize":
        outcomes[0]["original_validation"] = "x" * 1025
    elif mutation == "history_event_limit":
        histories[0]["events"] *= 6
    elif mutation == "history_row_limit":
        histories[0]["events"] = [dict(histories[0]["events"][0], attributes={"extra": "x" * 256})] * 64
    elif mutation == "table_row_limit":
        metadata.append(deepcopy(metadata[0]))
    elif mutation == "unknown_job":
        trace["events"][0]["job_id"] = "batch-999"
    elif mutation in {"no_reservation", "no_rpc", "no_ack"}:
        idx = {"no_reservation": 0, "no_rpc": 1, "no_ack": 2}[mutation]
        trace["events"][idx]["event"] = "uncertainty"
        trace["events"][idx]["reason_code"] = "UNKNOWN_ACK"
    elif mutation == "ack_run_mismatch":
        trace["events"][2]["run_id"] = _run_id(999)
    elif mutation == "two_acks":
        trace["events"][3].update(event="acknowledgment", activity_id=None, attempt=None)
    elif mutation == "terminal_before_result":
        trace["events"][9]["event"] = "validated_terminal"
    elif mutation == "handler_before_execute":
        trace["events"][4]["event"] = "handler_enter"
    with pytest.raises(gate.GateError):
        _verify_real_fixture(bundle, monkeypatch)


@pytest.mark.parametrize("event_index,key,value", (
    (0, "workflow_type", "ReferenceGateWorkflow"), (0, "maximum_attempts", 2),
    (0, "execution_timeout_seconds", 121), (0, "run_timeout_seconds", 121),
    (0, "task_timeout_seconds", 11), (0, "task_queue", "other"),
    (0, "workflow_id", "opendot-batch-199"), (0, "original_execution_run_id", _run_id(999)),
    (0, "first_execution_run_id", _run_id(999)), (0, "attempt", 2),
    (0, "continued_execution_run_id", _run_id(999)),
    (4, "maximum_attempts", 2), (4, "start_to_close_seconds", 11),
    (4, "schedule_to_close_seconds", 61), (4, "activity_id", "other"),
    (5, "scheduled_event_id", 2), (5, "attempt", 2), (5, "identity", "other"),
    (6, "started_event_id", 3), (6, "scheduled_event_id", 2),
    (6, "result_size_bytes", 1025), (6, "result_sha256", "0" * 64),
    (9, "started_event_id", 3), (10, "result_size_bytes", 1025),
    (10, "new_execution_run_id", _run_id(999)),
))
def test_real_batch_history_exact_configuration_and_linkage(monkeypatch, event_index, key, value):
    bundle = _real_batch_fixture()
    bundle[2][0]["events"][event_index]["attributes"][key] = value
    with pytest.raises(gate.GateError):
        _verify_real_fixture(bundle, monkeypatch)


@pytest.mark.parametrize("event_type", ("ActivityTaskTimedOut", "ActivityTaskFailed", "ActivityTaskCanceled",
    "WorkflowExecutionContinuedAsNew", "WorkflowExecutionFailed", "WorkflowExecutionTimedOut",
    "WorkflowExecutionCanceled", "WorkflowExecutionTerminated", "WorkflowExecutionSignaled"))
def test_real_batch_history_rejects_extra_service_paths(monkeypatch, event_type):
    bundle = _real_batch_fixture()
    bundle[2][0]["events"][6]["event_type"] = event_type
    with pytest.raises(gate.GateError):
        _verify_real_fixture(bundle, monkeypatch)


def test_real_batch_timestamps_are_observations_not_timeout_proofs(monkeypatch):
    bundle = _real_batch_fixture(2, early_activity=True)
    # Equal samples are legal; measured edges are not SDK timeout enforcement.
    for row in bundle[0]["events"]:
        row["elapsed_us"] = 123
    assert _verify_real_fixture(bundle, monkeypatch)["delivery_admission_acceptance"] == "PASS"
    bundle = _real_batch_fixture()
    for row in bundle[0]["events"]:
        row["elapsed_us"] = 0 if row["sequence"] < 7 else 11_000_001
    assert _verify_real_fixture(bundle, monkeypatch)["delivery_admission_acceptance"] == "PASS"


def test_real_batch_no_completion_preserves_sixteen_reservations(monkeypatch):
    trace, _, _, _ = _real_batch_fixture()
    selected = [row for row in trace["events"] if int(row["job_id"][-3:]) < 16
                and row["event"] in {"reservation", "rpc_enter", "acknowledgment"}]
    trace["events"] = selected
    for number, row in enumerate(selected, 1):
        row["sequence"] = number
    result = _verify_real_fixture((trace, [], [], []), monkeypatch)
    assert result["delivery_admission_acceptance"] == "FAIL"
    assert result["reserved_attempts"] == result["outstanding"] == result["peak_outstanding"] == 16
    assert result["unsubmitted"] == 184
    row = deepcopy(selected[0])
    row.update(sequence=49, job_id="batch-016", elapsed_us=2000)
    selected.append(row)
    with pytest.raises(gate.GateError, match="COUNTER_MISMATCH"):
        _verify_real_fixture((trace, [], [], []), monkeypatch)


def test_real_batch_late_accounting_keeps_uncertainty_sticky(monkeypatch):
    trace, metadata, histories, outcomes = _real_batch_fixture(1, early_activity=True)
    trace["events"] = trace["events"][:11]
    row = deepcopy(trace["events"][0])
    row.update(event="uncertainty", reason_code="UNKNOWN_ACK")
    trace["events"].insert(2, row)
    for number, event in enumerate(trace["events"], 1):
        event.update(sequence=number, elapsed_us=number * 10)
    metadata[0]["entry_sequence"] += 1
    result = _verify_real_fixture((trace, metadata[:1], histories[:1], outcomes[:1]), monkeypatch)
    assert result["validated_terminal"] == 1 and result["outstanding"] == 0
    assert result["uncertainty_latched"] and result["delivery_admission_acceptance"] == "FAIL"
    next_row = deepcopy(row)
    next_row.update(sequence=13, elapsed_us=130, event="reservation", job_id="batch-001", reason_code="OK")
    trace["events"].append(next_row)
    with pytest.raises(gate.GateError):
        _verify_real_fixture((trace, metadata[:1], histories[:1], outcomes[:1]), monkeypatch)


def test_real_batch_global_observer_failure_is_bounded_and_sticky(monkeypatch):
    trace, _, _, _ = _real_batch_fixture()
    trace["events"] = [{"sequence": 1, "elapsed_us": 0, "event": "uncertainty", "job_id": None,
        "run_id": None, "activity_id": None, "attempt": None, "reason_code": "OBSERVER_FAILURE"}]
    result = _verify_real_fixture((trace, [], [], []), monkeypatch)
    assert result["uncertainty_latched"] and result["reserved_attempts"] == 0
    assert result["delivery_admission_acceptance"] == "FAIL"


@pytest.mark.parametrize("key,value", (
    ("schema_version", gate.PREFIX + "cleanup.v1"), ("all_reservations_accounted", False),
    ("unresolved_start_operations", 1), ("unresolved_result_operations", 1), ("active_activity_calls", 1),
    ("handler_returns", 199), ("execution_uncertainty", True), ("observation_uncertainty", True),
    ("in_flight_shutdown_attempted", True), ("forced_termination_used", True),
    ("cleanup_status", "UNCONFIRMED"), ("cleanup_code", "CLEANUP_UNCONFIRMED"),
    ("elapsed_seconds", 241), ("elapsed_seconds", float("nan")),
    ("private_path", "PRIVATE_CANARY"),
))
def test_real_batch_cleanup_refuses_unknown_or_unsafe_state(key, value):
    value_row = _real_cleanup()
    value_row[key] = value
    with pytest.raises(gate.GateError):
        gate.validate_real_batch_cleanup(value_row)


@pytest.mark.parametrize("mutation", ("server_count", "worker_count", "worker_type", "worker_call",
                                      "worker_complete", "server_exit", "server_signal", "generation"))
def test_real_batch_cleanup_requires_single_service_and_public_shutdown(mutation):
    value = _real_cleanup()
    if mutation == "server_count":
        value["server_generations"] *= 2
    elif mutation == "worker_count":
        value["worker_generations"] *= 2
    elif mutation == "worker_type":
        value["worker_generations"][1]["type"] = "workflow"
    elif mutation in {"worker_call", "worker_complete"}:
        key = "public_shutdown_called" if mutation == "worker_call" else "public_shutdown_completed"
        value["worker_generations"][1][key] = False
    elif mutation == "server_exit":
        value["server_generations"][0]["exit_code"] = 1
    elif mutation == "server_signal":
        value["server_generations"][0]["shutdown_requested_signal"] = "SIGKILL"
    else:
        value["server_generations"][0]["generation"] = 2
    with pytest.raises(gate.GateError):
        gate.validate_real_batch_cleanup(value)


def test_real_batch_cleanup_allows_observed_partial_accounting_without_qualification():
    value = _real_cleanup()
    gate.validate_real_batch_cleanup(value)
    value["handler_entries"] = value["handler_returns"] = 1
    gate.validate_real_batch_cleanup(value)


def test_real_batch_source_closure_is_explicit_and_pins_unchanged_owners(tmp_path):
    required = {"AGENTS.md", "docs/decisions/004-temporal-reference-transport.md",
        "ci/run_temporal_server_gate.py", "ci/verify_temporal_server_gate.py", "ci/temporal-batch-nodes.txt",
        "ci/temporal-real-batch-nodes.txt", "tests/acceptance/temporal_real_batch_gate.py",
        "tests/test_temporal_server_harness_unit.py", "tests/test_temporal_server_gate_verifier.py",
        ".github/workflows/temporal-server.yml", "docs/temporal-batch-qualification.md",
        "docs/temporal-reference-transport.md"}
    assert required <= set(gate.REAL_BATCH_SOURCE_PATHS)
    assert set(gate.BATCH_SOURCE_PATHS) <= set(gate.REAL_BATCH_SOURCE_PATHS)
    for path in gate.REAL_BATCH_SOURCE_PATHS:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((SOURCE / path).read_bytes() if path in gate.BATCH_OWNER_SHA256 else b"fabricated source\n")
    digests = gate.real_batch_source_digests(tmp_path)
    assert set(digests) == set(gate.REAL_BATCH_SOURCE_PATHS)
    owner = next(iter(gate.BATCH_OWNER_SHA256))
    (tmp_path / owner).write_bytes(b"changed\n")
    with pytest.raises(gate.GateError, match="OWNER_MISMATCH"):
        gate.real_batch_source_digests(tmp_path)


@pytest.mark.parametrize("mutation", ("reference", "reordered", "duplicate", "missing", "extra"))
def test_real_batch_manifest_is_separate_and_exact(tmp_path, mutation):
    nodes = list(gate.REAL_BATCH_REQUIRED_NODES)
    if mutation == "reference":
        nodes = list(gate.REQUIRED_NODES)
    elif mutation == "reordered":
        nodes.reverse()
    elif mutation == "duplicate":
        nodes[1] = nodes[0]
    elif mutation == "missing":
        nodes.pop()
    else:
        nodes.append(gate.REQUIRED_NODES[0])
    manifest = tmp_path / "nodes.txt"
    manifest.write_text("\n".join(nodes) + "\n")
    with pytest.raises(gate.GateError, match="REQUIRED_NODES"):
        gate.read_real_batch_nodes(manifest)


def test_real_batch_four_node_collection_and_junit_bindings(tmp_path):
    nodes = list(gate.REAL_BATCH_REQUIRED_NODES)
    receipt = tmp_path / "collection.json"
    _write(receipt, {"schema_version": gate.REAL_BATCH_PREFIX + "collection.v1", "nodes": nodes})
    assert gate.verify_real_batch_collection(receipt) == nodes
    junit = tmp_path / "junit.xml"
    cases = ['<testcase classname="tests.acceptance.temporal_real_batch_gate" name="' + name + '"/>'
             for name in gate.REAL_BATCH_NODE_NAMES]
    junit.write_text("<testsuite>" + "".join(cases) + "</testsuite>")
    assert all(row["outcome"] == "PASS" for row in gate.verify_real_batch_junit(junit))
    junit.write_text("<testsuite>" + "".join(cases[:-1] + cases[:1]) + "</testsuite>")
    with pytest.raises(gate.GateError):
        gate.verify_real_batch_junit(junit)


@pytest.mark.parametrize("payload", (b'{"a":1,"a":2}', b'{"value":NaN}', b'{"value":Infinity}', b'\xff'))
def test_real_batch_strict_reader_refuses_invalid_json(payload):
    with pytest.raises(gate.GateError, match="INVALID_JSON"):
        gate.strict_json(payload)


def test_real_batch_cli_fails_safely_without_evidence_and_never_emits_raw_data(tmp_path, capsys):
    audit, manifest, junit = tmp_path / "audit", tmp_path / "nodes.txt", tmp_path / "unit.xml"
    manifest.write_text("\n".join(gate.REAL_BATCH_REQUIRED_NODES) + "\n")
    junit.write_text('<testsuite><testcase classname="PRIVATE_CANARY" name="PRIVATE_CANARY"/></testsuite>')
    summary = tmp_path / "summary.txt"
    result = gate.main(["--profile", "batch200", "--required", str(manifest), "--junit", str(junit),
        "--audit", str(audit), "--expected-revision", "PRIVATE_CANARY", "--summary", str(summary)])
    assert result == 1
    output = capsys.readouterr().out
    report, diagnostic = [json.loads(line) for line in output.splitlines()]
    assert report["delivery_admission_acceptance"] == "FAIL" and report["summary"] is None
    assert report["revision"] is None and report["profile"] == "batch200"
    assert "PRIVATE_CANARY" not in output + summary.read_text() + (audit / "batch-acceptance.json").read_text()
    assert '"audit_file"' not in output and diagnostic["validation"] != "VALID"


def test_real_batch_only_one_logical_start_can_await_ack(monkeypatch):
    bundle = _real_batch_fixture(2)
    trace = bundle[0]
    # The second reservation cannot begin while the first logical start lacks
    # an ack, even though the aggregate outstanding limit would allow it.
    trace["events"][2], trace["events"][3] = trace["events"][3], trace["events"][2]
    for number, row in enumerate(trace["events"], 1):
        row.update(sequence=number, elapsed_us=number)
    with pytest.raises(gate.GateError, match="COUNTER_MISMATCH"):
        _verify_real_fixture(bundle, monkeypatch)


@pytest.mark.parametrize("index", (0, 1))
def test_real_batch_closure_forbids_reservation_and_rpc_entry(monkeypatch, index):
    trace, _, _, _ = _real_batch_fixture()
    trace["events"] = trace["events"][:2]
    stop = {"sequence": index + 1, "elapsed_us": index, "event": "uncertainty", "job_id": None,
            "run_id": None, "activity_id": None, "attempt": None, "reason_code": "OBSERVER_FAILURE"}
    trace["events"].insert(index, stop)
    for number, row in enumerate(trace["events"], 1):
        row.update(sequence=number, elapsed_us=number)
    with pytest.raises(gate.GateError, match="COUNTER_MISMATCH"):
        _verify_real_fixture((trace, [], [], []), monkeypatch)


def test_real_batch_unmatched_intervals_never_demonstrate_overlap(monkeypatch):
    trace, metadata, _, _ = _real_batch_fixture(2)
    trace["events"] = trace["events"][:12]
    result = _verify_real_fixture((trace, metadata[:2], [], []), monkeypatch)
    assert result["observed_activity_peak"] == result["observed_handler_peak"] == 2
    assert result["activity_overlap"] == result["handler_overlap"] == "NOT_DEMONSTRATED"
    assert result["delivery_admission_acceptance"] == "FAIL"


def test_real_batch_audit_and_cli_reject_complete_fabricated_fixture(tmp_path, monkeypatch, capsys):
    trace, metadata, histories, outcomes = bundle = _real_batch_fixture()
    _verify_real_fixture(bundle, monkeypatch)
    audit = tmp_path / "audit"
    audit.mkdir()
    # Isolate environment reads only. There is deliberately no test-mode switch
    # in either hosted audit or CLI, even with every file present.
    monkeypatch.setattr(gate, "validate_environment", lambda value, revision: None)
    _write(audit / "environment.json", {})
    _write(audit / "diagnostic.json", {"schema_version": gate.PREFIX + "diagnostic.v1",
        "requested_revision": REVISION, "status": "COMPLETE", "primary_failure": None,
        "cleanup_failure": None, "audit_failure": None})
    _write(audit / "collection-receipt.json", {"schema_version": gate.REAL_BATCH_PREFIX + "collection.v1",
        "nodes": list(gate.REAL_BATCH_REQUIRED_NODES)})
    _write(audit / "batch-trace.json", trace)
    for filename, kind, rows in (("batch-metadata.json", "metadata", metadata),
                                ("batch-histories.json", "history", histories),
                                ("batch-outcomes.json", "outcomes", outcomes)):
        _write(audit / filename, {"schema_version": gate.REAL_BATCH_PREFIX + kind + ".v1", "rows": rows})
    _write(audit / "batch-cleanup.json", _real_cleanup())
    manifest = tmp_path / "nodes.txt"
    manifest.write_text("\n".join(gate.REAL_BATCH_REQUIRED_NODES) + "\n")
    monkeypatch.setattr(gate, "read_real_batch_nodes", lambda path: gate.REAL_BATCH_REQUIRED_NODES)
    with pytest.raises(gate.GateError, match="INVALID_SCHEMA"):
        gate.validate_real_batch_audit(audit, REVISION)
    junit = tmp_path / "junit.xml"
    junit.write_text("<testsuite>" + "".join('<testcase classname="tests.acceptance.temporal_real_batch_gate" name="'
        + name + '"/>' for name in gate.REAL_BATCH_NODE_NAMES) + "</testsuite>")
    assert gate.main(["--profile", "batch200", "--required", str(manifest), "--junit", str(junit),
        "--audit", str(audit), "--expected-revision", REVISION]) == 1
    report, _ = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert report["delivery_admission_acceptance"] == "FAIL"
    assert report["summary"] is None and "INVALID_SCHEMA" in report["reason_codes"]


def test_real_batch_acceptance_file_cap_includes_final_newline(tmp_path, monkeypatch, capsys):
    manifest = tmp_path / "nodes.txt"
    manifest.write_text("\n".join(gate.REAL_BATCH_REQUIRED_NODES) + "\n")
    for summary_failure in (False, True):
        def run(label):
            audit = tmp_path / (str(summary_failure) + "-" + label)
            args = ["--profile", "batch200", "--required", str(manifest),
                    "--junit", str(tmp_path / "missing.xml"), "--audit", str(audit),
                    "--expected-revision", REVISION]
            if summary_failure:
                args += ["--summary", str(tmp_path / "missing-parent" / "summary.txt")]
            assert gate.main(args) == 1
            report = json.loads(capsys.readouterr().out.splitlines()[0])
            return audit / "batch-acceptance.json", report
        monkeypatch.setattr(gate, "BATCH_SUMMARY_BYTES", 65536)
        baseline, _ = run("baseline")
        maximum = baseline.stat().st_size
        monkeypatch.setattr(gate, "BATCH_SUMMARY_BYTES", maximum)
        exact_file, exact_report = run("exact")
        assert exact_file.stat().st_size == maximum
        assert exact_file.read_bytes().endswith(b"\n")
        assert json.loads(exact_file.read_bytes()) == exact_report
        monkeypatch.setattr(gate, "BATCH_SUMMARY_BYTES", maximum - 1)
        over_file, over_report = run("over")
        assert "WRITE_FAILED" in over_report["reason_codes"]
        assert not over_file.exists() or over_file.stat().st_size <= maximum - 1

# Export mechanics use clearly labelled FABRICATED_UNIT_DATA throughout. This
# fixture replaces only the existing hosted trace kind boundary for pure tests;
# production export/audit/recheck/CLI expose no test-mode switch.
@pytest.fixture
def public_projection_fixture(tmp_path, monkeypatch):
    trace, metadata, histories, outcomes = _real_batch_fixture(1)
    trace["source_sha256"] = gate.real_batch_source_digests()
    original_validator = gate.validate_real_batch_trace
    def fixture_validator(*args, **kwargs):
        assert args[0]["evidence_kind"] == "FABRICATED_UNIT_DATA"
        return original_validator(*args, allow_test_data=True, **kwargs)
    monkeypatch.setattr(gate, "validate_real_batch_trace", fixture_validator)
    monkeypatch.setattr(gate, "checked_revision", lambda: REVISION)
    for key, value in {"GITHUB_ACTIONS": "true", "GITHUB_SHA": REVISION,
        "GITHUB_SERVER_URL": "https://github.com", "GITHUB_REPOSITORY": "unit-fixture/unit-fixture",
        "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1"}.items():
        monkeypatch.setenv(key, value)
    environment = {"schema_version": gate.PREFIX + "environment.v1",
        "candidate_revision": REVISION, "requested_revision": REVISION,
        "workflow_run_url": "https://github.com/unit-fixture/unit-fixture/actions/runs/123",
        "source_kind": "public_source_checkout", "python_version": "3.12.0", "platform": "linux-x86_64",
        "versions": gate.SDK_VERSIONS | gate.TOOL_VERSIONS, "cli_version": "1.9.1", "server_version": "1.32.0",
        "cli_archive_sha256": gate.CLI_ARCHIVE_SHA256, "cli_checksums_sha256": gate.CLI_CHECKSUMS_SHA256,
        "sdk_wheel_sha256": gate.SDK_WHEEL_SHA256, **gate.current_source_digests(),
        "owner_sha256": gate.OWNER_SHA256.copy(), "server_profile": gate.SERVER_PROFILE.copy(),
        "preflight_status": "PASS", "preflight_code": "OK"}
    records = {"environment.json": environment, "batch-trace.json": trace,
        "batch-cleanup.json": _real_cleanup(), "diagnostic.json": _fabricated_records()["diagnostic.json"],
        "collection-receipt.json": {"schema_version": gate.REAL_BATCH_PREFIX + "collection.v1",
                                    "nodes": list(gate.REAL_BATCH_REQUIRED_NODES)}}
    for name, kind, rows in (("batch-metadata.json", "metadata", metadata),
        ("batch-histories.json", "history", histories), ("batch-outcomes.json", "outcomes", outcomes)):
        records[name] = {"schema_version": gate.REAL_BATCH_PREFIX + kind + ".v1", "rows": rows}
    audit = tmp_path / "fabricated-audit"
    audit.mkdir()
    for name, value in records.items():
        _write(audit / name, value)
    required = SOURCE / "ci/temporal-real-batch-nodes.txt"
    junit = tmp_path / "fabricated-junit.xml"
    junit.write_text('<testsuite>' + ''.join('<testcase classname="tests.acceptance.temporal_real_batch_gate" name="'
        + name + '"><system-out>PRIVATE_CANARY</system-out></testcase>'
        for name in gate.REAL_BATCH_NODE_NAMES) + '</testsuite>')
    return audit, required, junit, records, original_validator


def _export_public(fixture, destination):
    audit, required, junit, _, _ = fixture
    return gate.export_real_batch_public_bundle(audit, required, junit, REVISION, destination)


def _recheck_public(path):
    return gate.recheck_real_batch_public_bundle(path, REVISION,
        "https://github.com/unit-fixture/unit-fixture/actions/runs/123", 1)


def test_public_projection_fixture_roundtrip_retains_rows_hashes_and_peak_one(public_projection_fixture, tmp_path):
    bundle = tmp_path / "public"
    manifest = _export_public(public_projection_fixture, bundle)
    assert manifest["evidence_kind"] == "FABRICATED_UNIT_DATA"
    assert manifest["projection_kind"] == "PUBLIC_PROJECTION" and manifest["retention_days"] == 30
    assert set(p.name for p in bundle.iterdir()) == set(gate.PUBLIC_FILE_LIMITS) | {"manifest.json"}
    result = _recheck_public(bundle)
    assert result["projection_consistency"] == "PASS"
    summary = result["summary"]
    assert summary["evidence_kind"] == "FABRICATED_UNIT_DATA"
    assert summary["validated_terminal"] == 200 and summary["observed_activity_peak"] == 1
    assert summary["activity_overlap"] == summary["handler_overlap"] == "NOT_DEMONSTRATED"
    assert result["independent_original_replay"] == "NOT_EVALUATED"
    all_bytes = b"".join(p.read_bytes() for p in bundle.iterdir())
    assert b"PRIVATE_CANARY" not in all_bytes and str(tmp_path).encode() not in all_bytes
    assert b"system-out" not in all_bytes and b"diagnostic.json" not in all_bytes
    for name, row in manifest["files"].items():
        actual = (bundle / name).read_bytes()
        assert row == {"sha256": hashlib.sha256(actual).hexdigest(), "bytes": len(actual)}
    assert sum(p.stat().st_size for p in bundle.iterdir()) <= gate.PUBLIC_TOTAL_BYTES


@pytest.mark.parametrize("stage", ("audit", "export", "recheck"))
def test_public_projection_never_accepts_fixture_as_hosted(public_projection_fixture, tmp_path, monkeypatch, stage):
    bundle = tmp_path / "public"
    if stage == "recheck":
        _export_public(public_projection_fixture, bundle)
    monkeypatch.setattr(gate, "validate_real_batch_trace", public_projection_fixture[4])
    with pytest.raises(gate.GateError, match="INVALID_SCHEMA"):
        if stage == "audit": gate.validate_real_batch_audit(public_projection_fixture[0], REVISION)
        elif stage == "export": _export_public(public_projection_fixture, bundle)
        else: _recheck_public(bundle)
    assert stage == "recheck" or not bundle.exists()


@pytest.mark.parametrize("name", tuple(gate.PUBLIC_FILE_LIMITS)[:-1] + ("diagnostic.json", "collection-receipt.json"))
def test_public_projection_unknown_fields_fail_before_output(public_projection_fixture, tmp_path, name):
    audit, _, _, records, _ = public_projection_fixture
    records[name]["private_token"] = "PRIVATE_CANARY"
    _write(audit / name, records[name])
    with pytest.raises(gate.GateError): _export_public(public_projection_fixture, tmp_path / "public")
    assert not (tmp_path / "public").exists()


@pytest.mark.parametrize("fault", ("extra_file", "extra_dir", "symlink_file", "symlink_parent", "hardlink",
                                  "oversize", "malformed_json", "duplicate_json", "incomplete_cleanup", "failed_junit"))
def test_public_projection_rejects_unsafe_or_invalid_inputs(public_projection_fixture, tmp_path, fault):
    audit, required, junit, records, validator = public_projection_fixture
    selected = public_projection_fixture
    if fault == "extra_file": (audit / "private.log").write_text("PRIVATE_CANARY")
    if fault == "extra_dir": (audit / "raw-history").mkdir()
    if fault == "symlink_file":
        target = audit / "batch-trace.json"
        target.rename(tmp_path / "trace.json")
        target.symlink_to(tmp_path / "trace.json")
    if fault == "symlink_parent":
        alias = tmp_path / "alias"; alias.symlink_to(audit, target_is_directory=True)
        selected = (alias, required, junit, records, validator)
    if fault == "hardlink":
        import os
        os.link(audit / "batch-trace.json", tmp_path / "hardlink.json")
    if fault == "oversize": (audit / "batch-trace.json").write_bytes(b" " * (gate.BATCH_TRACE_BYTES + 1))
    if fault == "malformed_json": (audit / "batch-trace.json").write_bytes(b"PRIVATE_CANARY")
    if fault == "duplicate_json": (audit / "batch-trace.json").write_bytes(b'{"private":1,"private":2}')
    if fault == "incomplete_cleanup":
        records["batch-cleanup.json"]["active_activity_calls"] = 1
        _write(audit / "batch-cleanup.json", records["batch-cleanup.json"])
    if fault == "failed_junit": junit.write_text(junit.read_text().replace('<system-out>', '<failure/> <system-out>', 1))
    with pytest.raises(gate.GateError): _export_public(selected, tmp_path / "public")
    assert not (tmp_path / "public").exists()


@pytest.mark.parametrize("target", ("batch-trace.json", "junit", "required", "new_file", "output"))
def test_public_projection_detects_mutation_before_publish(public_projection_fixture, tmp_path, monkeypatch, target):
    audit, required, junit, records, validator = public_projection_fixture
    if target == "required":
        copy = tmp_path / "required.txt"; copy.write_bytes(required.read_bytes())
        public_projection_fixture = (audit, copy, junit, records, validator)
        required = copy
    original = gate._same_snapshot
    calls = 0
    def changed(path, snapshot, names):
        nonlocal calls
        calls += 1
        if calls == 2:
            if target == "new_file": (audit / "private.log").write_text("PRIVATE_CANARY")
            elif target == "output": (tmp_path / "public").mkdir()
            else:
                selected = junit if target == "junit" else required if target == "required" else audit / target
                selected.write_bytes(selected.read_bytes() + b" ")
        return original(path, snapshot, names)
    monkeypatch.setattr(gate, "_same_snapshot", changed)
    with pytest.raises(gate.GateError): _export_public(public_projection_fixture, tmp_path / "public")
    assert not (tmp_path / "public").exists() or not list((tmp_path / "public").iterdir())
    assert not list(tmp_path.glob(".opendot-public-stage-*"))


@pytest.mark.parametrize("fault", ("existing", "symlink", "parent_symlink", "inside_audit", "write_failure"))
def test_public_projection_rejects_output_contamination(public_projection_fixture, tmp_path, monkeypatch, fault):
    destination = tmp_path / "public"
    if fault == "existing": destination.mkdir(); (destination / "private.log").write_text("PRIVATE_CANARY")
    if fault == "symlink": destination.symlink_to(tmp_path / "absent")
    if fault == "parent_symlink":
        alias = tmp_path / "alias"; alias.symlink_to(tmp_path, target_is_directory=True); destination = alias / "public"
    if fault == "inside_audit": destination = public_projection_fixture[0] / "public"
    if fault == "write_failure":
        original = gate.Path.open
        def fail(path, *args, **kwargs):
            if args == ("xb",): raise OSError("PRIVATE_CANARY")
            return original(path, *args, **kwargs)
        monkeypatch.setattr(gate.Path, "open", fail)
    with pytest.raises(gate.GateError): _export_public(public_projection_fixture, destination)
    assert not list(tmp_path.glob(".opendot-public-stage-*"))


@pytest.mark.parametrize("fault", ("row_mutation", "rehash_mutation", "extra_field", "missing_file", "extra_file",
                                  "manifest_retention", "manifest_revision", "manifest_kind", "summary_bool", "source_changed"))
def test_public_projection_recheck_rejects_tampering(public_projection_fixture, tmp_path, monkeypatch, fault):
    bundle = tmp_path / "public"; manifest = _export_public(public_projection_fixture, bundle)
    if fault in {"row_mutation", "rehash_mutation", "extra_field", "summary_bool"}:
        name = "batch-summary.json" if fault == "summary_bool" else "batch-metadata.json"
        data = json.loads((bundle / name).read_bytes())
        if fault == "extra_field": data["private_token"] = "PRIVATE_CANARY"
        elif fault == "summary_bool": data["summary"]["outstanding"] = False
        else: data["rows"][0]["attempt"] = 2
        _write(bundle / name, data)
        if fault != "row_mutation":
            raw = (bundle / name).read_bytes()
            manifest["files"][name] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    if fault == "missing_file": (bundle / "batch-outcomes.json").unlink()
    if fault == "extra_file": (bundle / "private.log").write_text("PRIVATE_CANARY")
    if fault == "manifest_retention": manifest["retention_days"] = 90
    if fault == "manifest_revision": manifest["revision"] = "b" * 40
    if fault == "manifest_kind": manifest["projection_kind"] = "ORIGINAL_EVIDENCE"
    if fault == "source_changed": monkeypatch.setattr(gate, "real_batch_source_digests", lambda source=None: {})
    _write(bundle / "manifest.json", manifest)
    with pytest.raises(gate.GateError): _recheck_public(bundle)


def test_public_projection_cli_failure_emits_fixed_code_only(tmp_path, capsys):
    assert gate.main(["recheck-public-bundle", "--bundle", str(tmp_path / "PRIVATE_CANARY"),
        "--expected-revision", "PRIVATE_CANARY", "--expected-run-url", "PRIVATE_CANARY", "--expected-run-attempt", "1"]) == 1
    output = capsys.readouterr().out
    assert "PRIVATE_CANARY" not in output
    assert json.loads(output)["projection_consistency"] == "FAIL"


def test_public_projection_cli_is_opt_in_and_reference_refuses(tmp_path):
    with pytest.raises(SystemExit):
        gate.main(["--required", "unused", "--junit", "unused", "--audit", str(tmp_path),
            "--expected-revision", REVISION, "--public-bundle", str(tmp_path / "public")])


@pytest.mark.parametrize("attempt", (None, "0", "-1", "01", "1.0", "100000", "PRIVATE_CANARY"))
def test_public_projection_export_requires_bounded_run_attempt(public_projection_fixture, tmp_path, monkeypatch, attempt):
    if attempt is None: monkeypatch.delenv("GITHUB_RUN_ATTEMPT", raising=False)
    else: monkeypatch.setenv("GITHUB_RUN_ATTEMPT", attempt)
    with pytest.raises(gate.GateError, match="CI_IDENTITY"):
        _export_public(public_projection_fixture, tmp_path / "public")
    assert not (tmp_path / "public").exists()


@pytest.mark.parametrize("field,value", (("run_attempt", 2), ("run_attempt", True),
    ("workflow_path", ".github/workflows/private.yml"), ("workflow_sha256", "b" * 64)))
def test_public_projection_recheck_binds_run_attempt_and_workflow(public_projection_fixture, tmp_path, field, value):
    bundle = tmp_path / "public"; manifest = _export_public(public_projection_fixture, bundle)
    manifest[field] = value; _write(bundle / "manifest.json", manifest)
    with pytest.raises(gate.GateError): _recheck_public(bundle)


@pytest.mark.parametrize("before,after", (
    ("steps.batch_evidence.outcome == 'success' }}", "steps.batch_evidence.outcome == 'success' || true }}"),
    ("        with:\n          name: temporal-batch200", "        with:\n          name: temporal-batch200" + "\n      - uses: 'actions/upload-artifact@other'\n#"),
    ("043fb46d1a93c77aae656e7c1c64a875d1fc6a0a", "ea165f8d65b6e75b540449e92b4886f43607fa02"),
    ("path: ${{ runner.temp }}/opendot-temporal-batch200-public", "path: ${{ runner.temp }}/opendot-temporal-batch200-gate/audit"),
    ("path: ${{ runner.temp }}/opendot-temporal-batch200-public", "path: ${{ runner.temp }}/**"),
    ("contents: read", "contents: write"),
    ("permissions:\n  contents: read", "permissions:\n  contents: read\n  actions: write"),
    ("include-hidden-files: false", "include-hidden-files: true"),
    ("overwrite: false", "overwrite: true"), ("retention-days: 30", "retention-days: 90"),
    ("inputs.qualification == 'batch200' && inputs.retain_public_evidence", "inputs.qualification == 'reference' && inputs.retain_public_evidence"),
    ("if-no-files-found: error", "if-no-files-found: ignore"),
))
def test_public_projection_workflow_closed_guard_rejects_semantic_or_spelling_bypass(before, after):
    source = (SOURCE / gate.PUBLIC_WORKFLOW_PATH).read_bytes()
    gate.validate_public_batch_workflow(source)
    assert before.encode() in source and before != after
    with pytest.raises(gate.GateError, match="SOURCE_MISMATCH"):
        gate.validate_public_batch_workflow(source.replace(before.encode(), after.encode()))


@pytest.mark.parametrize("fault", ("none", "export_error", "summary_error"))
def test_public_projection_main_gates_output_and_fails_closed(public_projection_fixture, tmp_path, monkeypatch, capsys, fault):
    audit, required, junit, _, _ = public_projection_fixture
    destination = tmp_path / "public"
    summary = tmp_path / "summary.txt" if fault != "summary_error" else tmp_path / "absent" / "summary.txt"
    if fault == "export_error":
        def fail(*args, **kwargs): raise gate.GateError("PRIVACY_REJECTED")
        monkeypatch.setattr(gate, "export_real_batch_public_bundle", fail)
    result = gate.main(["--profile", "batch200", "--required", str(required), "--junit", str(junit),
        "--audit", str(audit), "--expected-revision", REVISION, "--summary", str(summary),
        "--public-bundle", str(destination)])
    report = json.loads(capsys.readouterr().out.splitlines()[0])
    assert result == (0 if fault == "none" else 1)
    assert (report["delivery_admission_acceptance"] == "PASS") == (fault == "none")
    assert json.loads((audit / "batch-acceptance.json").read_bytes()) == report
    if destination.exists():
        manifest = json.loads((destination / "manifest.json").read_bytes())
        assert manifest["evidence_kind"] == "FABRICATED_UNIT_DATA"
    assert fault != "export_error" or not destination.exists()


def test_public_projection_default_main_has_no_export_side_effect(public_projection_fixture, tmp_path, capsys):
    audit, required, junit, _, _ = public_projection_fixture
    assert gate.main(["--profile", "batch200", "--required", str(required), "--junit", str(junit),
        "--audit", str(audit), "--expected-revision", REVISION]) == 0
    capsys.readouterr()
    assert not list(tmp_path.glob("*public*")) and not list(tmp_path.glob(".opendot-public-stage-*"))


def test_public_projection_successful_offline_cli_does_not_consult_host_identity(public_projection_fixture, tmp_path, monkeypatch, capsys):
    destination = tmp_path / "public"; _export_public(public_projection_fixture, destination)
    def forbidden(*args, **kwargs): raise AssertionError("host identity must not be consulted for offline recheck")
    monkeypatch.setattr(gate, "checked_revision", forbidden)
    monkeypatch.setattr(gate, "trusted_run_url", forbidden)
    for key in ("GITHUB_ACTIONS", "GITHUB_SHA", "GITHUB_RUN_ATTEMPT"):
        monkeypatch.delenv(key, raising=False)
    assert gate.main(["recheck-public-bundle", "--bundle", str(destination), "--expected-revision", REVISION,
        "--expected-run-url", "https://github.com/unit-fixture/unit-fixture/actions/runs/123",
        "--expected-run-attempt", "1"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["projection_consistency"] == "PASS" and result["summary"]["evidence_kind"] == "FABRICATED_UNIT_DATA"
    assert result["independent_original_replay"] == "NOT_EVALUATED"
