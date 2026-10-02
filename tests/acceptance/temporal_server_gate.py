# SPDX-License-Identifier: Apache-2.0
"""Explicit-only service gate. This filename is outside default pytest discovery.

Select all seven exact nodes from ci/temporal-server-nodes.txt. Missing optional
packages, acquisition receipts, CI authorization or evidence FAIL, never skip.
"""
from pathlib import Path
import os
import pytest


@pytest.fixture(scope="session")
def real_gate(request):
    # No SDK imports at collection: missing dependencies still collect all nodes.
    from run_temporal_server_gate import run_gate
    nodes = [item.nodeid for item in request.session.items]
    required = (Path(__file__).resolve().parents[2] / "ci/temporal-server-nodes.txt").read_text().splitlines()
    if nodes != required:
        pytest.fail("TEMPORAL_GATE_NODE_SELECTION", pytrace=False)
    try:
        return run_gate(Path(os.environ["OPENDOT_TEMPORAL_GATE_ROOT"]),
                        Path(os.environ["OPENDOT_TEMPORAL_CLI"]), nodes)
    except Exception:
        pytest.fail("TEMPORAL_GATE_SETUP_FAILED", pytrace=False)


def outcome(real_gate, scenario):
    return next(row for row in real_gate["outcomes"] if row["scenario"] == scenario)


def test_real_received_metadata_and_valid_output(real_gate):
    assert len(real_gate["metadata"]) == 5
    for row in real_gate["metadata"]:
        assert row["metadata_source"] == "real_sdk_activity_info"
        assert type(row["attempt"]) is int and row["attempt"] == 1
        assert row["is_local"] is False and row["retry_policy_present"] is True
        assert type(row["maximum_attempts"]) is int and row["maximum_attempts"] == 1
        assert row["start_to_close_seconds"] == 10 and row["schedule_to_close_seconds"] == 60
    row = outcome(real_gate, "durability_replay")
    assert row["tool_status"] == "COMPLETED" and row["semantic_valid"] is True
    assert type(row["output_integer"]) is int and row["output_integer"] == 5


def test_queued_activity_survives_graceful_server_restart(real_gate):
    before, after = real_gate["histories"][:2]
    assert before["phase"] == "queued_before_restart" and after["phase"] == "queued_after_restart"
    assert before["workflow_run_id"] == after["workflow_run_id"]
    assert before["events"] == after["events"]
    assert before["counter_sequence"] == after["counter_sequence"] == 0
    assert before["activity_workers_started"] == after["activity_workers_started"] == 0
    assert real_gate["cleanup"]["cleanup_status"] == "PASS"


def test_recorded_result_replays_without_handler_reentry(real_gate):
    row = real_gate["replay"]
    assert row["same_completion_event_after_restart"] is True
    assert row["before_result_artifact_id"] == row["after_query_result_artifact_id"] == row["workflow_result_artifact_id"]
    assert row["handler_count_before"] == row["handler_count_after_live_replay"] == row["handler_count_after_sdk_replay"] == 1
    assert row["counter_sequence_before"] == row["counter_sequence_after_live_replay"] == row["counter_sequence_after_sdk_replay"] == 4
    assert row["activity_worker_present_during_replay"] is False and row["sdk_replay_failure"] is None


def test_completed_null_output_is_preserved(real_gate):
    row = outcome(real_gate, "null")
    assert row["tool_status"] == "COMPLETED" and row["semantic_valid"] is True
    assert row["output_kind"] == "null" and row["output_integer"] is None


def test_blocked_tool_is_not_promoted_to_success(real_gate):
    row = outcome(real_gate, "blocked")
    assert row["activity_transport_status"] == "COMPLETED"
    assert row["tool_status"] == "BLOCKED" and row["semantic_valid"] is False
    assert row["execute_count"] == 1 and row["handler_count"] == 0


def test_failed_tool_is_not_promoted_to_success(real_gate):
    row = outcome(real_gate, "failed_validation")
    assert row["activity_transport_status"] == "COMPLETED"
    assert row["tool_status"] == "FAILED" and row["semantic_valid"] is False
    assert row["test_only_validator_fault"] is True and row["handler_count"] == 1


def test_input_failure_is_transport_failure_without_dispatch(real_gate):
    row = outcome(real_gate, "missing_input")
    assert row["workflow_transport_status"] == row["activity_transport_status"] == "FAILED"
    assert row["result_ref_present"] is False and row["result_artifact_id"] is None
    assert row["execute_count"] == row["handler_count"] == 0
