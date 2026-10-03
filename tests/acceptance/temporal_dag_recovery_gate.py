# SPDX-License-Identifier: Apache-2.0
"""Seven explicitly selected hosted controls; collection has no SDK/service setup."""
from pathlib import Path
import os
import pytest


@pytest.fixture(scope="session")
def dag2_gate(request):
    try:
        from run_temporal_server_gate import run_dag2_gate
        nodes = [item.nodeid for item in request.session.items]
        required = (Path(__file__).resolve().parents[2] / "ci/temporal-dag-recovery-nodes.txt").read_text().splitlines()
        if nodes != required:
            pytest.fail("DAG2_REQUIRED_NODES", pytrace=False)
        result = run_dag2_gate(Path(os.environ["OPENDOT_TEMPORAL_GATE_ROOT"]),
                               Path(os.environ["OPENDOT_TEMPORAL_CLI"]), nodes)
        assert result["validated"]["record_validation"] == "RECORD_VALIDATION_PASS"
        assert result["validated"]["hosted_acceptance"] == "REQUIRES_EXTERNAL_GITHUB_READBACK"
        assert result["cleanup"]["cleanup_status"] == "PASS"
        assert result["cleanup"]["public_worker_shutdown_calls"] == 8
        assert result["cleanup"]["activity_executor_shutdown_calls"] == 4
        assert result["dag2"]["dag2-trace.json"]["aggregate_counts"]["activity_schedules"] == 9
        assert result["dag2"]["dag2-trace.json"]["aggregate_counts"]["result_puts"] == 5
        assert result["dag2"]["dag2-diagnostic.json"]["result"] == "PASS"
        return result["dag2"]
    except Exception:
        pass
    # Leave the exception scope so no private prerequisite error is chained.
    pytest.fail("DAG2_SETUP_OR_EVIDENCE_FAILED", pytrace=False)


def test_dag2_real_a_to_b_and_original_receipts(dag2_gate):
    state = dag2_gate["normal-final.state.json"]
    assert state["mission_status"] == "COMPLETED" and state["revision"] == 9
    assert dag2_gate["normal-a.result.json"]["output"] == 5
    assert dag2_gate["normal-b.result.json"]["output"] == 6
    assert state["nodes"]["B"]["parent_result_ref"] == state["nodes"]["A"]["accepted_result_ref"]


def test_dag2_quiescent_worker_replacement_preserves_state(dag2_gate):
    assert dag2_gate["reconcile-unknown-before-stop.state.json"] == dag2_gate["reconcile-unknown-after-replacement.state.json"]
    bootstrap = dag2_gate["dag2-environment.json"]["bootstrap"]
    assert bootstrap[1]["run_id"] == bootstrap[2]["run_id"]
    assert bootstrap[2]["origin_capture_seq"] < bootstrap[2]["constructed_seq"]


def test_dag2_recorded_history_replay_has_no_activity_execution(dag2_gate):
    rows = dag2_gate["dag2-replays.json"]["replays"]
    assert len(rows) == 2
    for row in rows:
        assert row["replay_failure"] is None and row["activity_worker_count"] == 0
        assert row["counts_before"] == row["counts_after"]
        assert row["retained_history_sha256"] == row["replayer_input_sha256"]
        assert row["result_api"] == "WorkflowReplayResult.history_and_replay_failure"


def test_dag2_original_put_reconciliation_never_reexecutes_a(dag2_gate):
    commands = [row for row in dag2_gate["dag2-trace.json"]["commands"] if row["mission"] == "hosted-reconcile"]
    assert [(row["node"], row["kind"]) for row in commands] == [
        ("A", "execute"), ("A", "reconcile_inspect"), ("B", "execute"), ("B", "normal_inspect")]
    assert dag2_gate["reconcile-final.state.json"]["revision"] == 10
    assert dag2_gate["reconcile-a.result.json"]["output"] == 5


def test_dag2_unknown_without_reference_blocks_b(dag2_gate):
    state = dag2_gate["no-ref-unknown.state.json"]
    assert state["revision"] == 4 and state["nodes"]["A"]["status"] == "UNKNOWN"
    assert state["nodes"]["A"]["candidate_result_ref"] is None
    assert state["nodes"]["B"]["status"] == "WAITING" and state["nodes"]["B"]["effect_id"] is None
    assert dag2_gate["dag2-originals.json"]["no_ref"]["original_reference"] == "NOT_RETAINED"


def test_dag2_cancellation_keeps_unadmitted_b_closed(dag2_gate):
    state = dag2_gate["no-ref-cancel-final.state.json"]
    assert state["mission_status"] == "STOPPED_WITH_UNKNOWN" and state["revision"] == 5
    assert state["cancel_requested"] is True
    assert state["nodes"]["B"]["status"] == "CANCELLED_BEFORE_ADMISSION"
    assert dag2_gate["dag2-cleanup.json"]["workflow_handle_cancel_calls"] == 1


def test_dag2_duplicate_and_stale_updates_consume_no_allowance(dag2_gate):
    rows = dag2_gate["dag2-trace.json"]["updates"]
    assert len(rows) == 5
    assert [row["reservation_delta"] for row in rows] == [0, 1, 0, 0, 0]
    assert rows[0]["precondition_oracle"] == "STALE_REVISION"
    assert rows[3]["precondition_oracle"] == "INSPECTION_BUSY"
    assert all(row["execute_delta"] == row["endpoint_read_delta"] == 0 for row in rows)
