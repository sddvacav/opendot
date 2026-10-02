# SPDX-License-Identifier: Apache-2.0
"""Explicit manually selected real batch; excluded from default discovery."""
from pathlib import Path
import os
import pytest


@pytest.fixture(scope="session")
def real_batch_gate(request):
    from run_temporal_server_gate import run_real_batch_gate
    nodes = [item.nodeid for item in request.session.items]
    required = (Path(__file__).resolve().parents[2] / "ci/temporal-real-batch-nodes.txt").read_text().splitlines()
    if nodes != required:
        pytest.fail("TEMPORAL_BATCH_NODE_SELECTION", pytrace=False)
    try:
        return run_real_batch_gate(Path(os.environ["OPENDOT_TEMPORAL_GATE_ROOT"]),
                                   Path(os.environ["OPENDOT_TEMPORAL_CLI"]), nodes)
    except Exception:
        pytest.fail("TEMPORAL_BATCH_SETUP_FAILED", pytrace=False)


def test_real_batch_delivers_200_bound_results(real_batch_gate):
    assert len(real_batch_gate["outcomes"]) == len(real_batch_gate["histories"]) == 200
    assert real_batch_gate["summary"]["delivery_admission_acceptance"] == "PASS"


def test_real_batch_reservations_never_exceed_16(real_batch_gate):
    assert real_batch_gate["summary"]["peak_outstanding"] <= 16
    assert real_batch_gate["summary"]["logical_application_starts"] == 200


def test_real_batch_records_received_metadata_and_occupancy(real_batch_gate):
    assert len(real_batch_gate["metadata"]) == 200
    summary = real_batch_gate["summary"]
    assert 1 <= summary["observed_activity_peak"] <= 8
    assert summary["activity_overlap"] == ("DEMONSTRATED" if summary["observed_activity_peak"] > 1
                                           else "NOT_DEMONSTRATED")


def test_real_batch_observed_quiescence_and_shutdown(real_batch_gate):
    assert real_batch_gate["cleanup"]["cleanup_status"] == "PASS"
    assert len(real_batch_gate["cleanup"]["server_generations"]) == 1
    assert len(real_batch_gate["cleanup"]["worker_generations"]) == 2
