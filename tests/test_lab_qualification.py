"""Wholly synthetic admission/refusal tests; no scientific or device execution."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from opendot_engineering.adapters import lab_qualification as q
from opendot_engineering.adapters import source_audit as a

EXAMPLE = Path(__file__).parents[1] / "examples/lab-qualification"
REVISION = "b" * 40  # Synthetic fixture revision; not an asserted Git commit.
PIN = "1dcde9c63280f4f99e6c2ea9e3ca6d392399e4d0792a4a9e4f81d581d2ce817f"


@pytest.fixture
def root(tmp_path):
    result = tmp_path / "inputs"
    shutil.copytree(EXAMPLE, result)
    return result


def document(root):
    return json.loads((root / "fixture.json").read_text())


def set_value(obj, path, value):
    keys = path.split("/")
    for key in keys[:-1]:
        obj = obj[int(key)] if isinstance(obj, list) else obj[key]
    obj[int(keys[-1]) if isinstance(obj, list) else keys[-1]] = value


def repin(root, doc):
    raw = (json.dumps(doc, indent=2) + "\n").encode()
    (root / "fixture.json").write_bytes(raw)
    spec = json.loads((root / "manifest.json").read_text())
    spec["fixture"].update(sha256=a._sha256(raw), git_blob_sha1=a._git_blob(raw))
    manifest = (json.dumps(spec, indent=2) + "\n").encode()
    (root / "manifest.json").write_bytes(manifest)
    return a._sha256(manifest)


def verify(root, pin=PIN):
    return q.verify_bundle(root, "manifest.json", expected_revision=REVISION, expected_manifest_sha256=pin)


def negative(root, updates, reasons):
    doc = document(root)
    doc["cases"] = [doc["cases"][0]]
    for key, value in updates.items():
        set_value(doc["cases"][0], key, value)
    doc["cases"][0]["oracle"] = {"qualification_result": "HOLD", "reason_codes": reasons}
    result = verify(root, repin(root, doc))
    assert result["benchmark_contract_passed"] is True
    assert result["cases"][0]["qualification_result"] == "HOLD"
    assert result["cases"][0]["reason_codes"] == sorted(reasons)
    return result


def test_example_correct_refusals_pass_software_benchmark(root):
    before = {p.name: p.read_bytes() for p in root.iterdir()}
    result = verify(root)
    assert result == verify(root)
    assert result["audit_accepted"] and result["benchmark_contract_passed"]
    assert [c["qualification_result"] for c in result["cases"]] == ["SYNTHETIC_PASS", "HOLD", "HOLD"]
    for receipt in [result, *result["cases"]]:
        for key in ("real_device_qualified", "device_control_authorized", "scientific_accepted"):
            assert receipt[key] is False
    assert result["owner_integration"] == result["independent_review"] == "NOT_EVALUATED"
    assert result["cases"][0]["protocol_structure_status"] == "READY_FOR_HUMAN_EXECUTION"
    assert result["cases"][0]["protocol_structure_verified"] is False
    assert result["manifest_sha256"] == PIN
    assert result["adapter_source_sha256"] == {"lab_qualification.py": a._sha256(Path(q.__file__).read_bytes()), "source_audit.py": a._sha256(Path(a.__file__).read_bytes())}
    assert all(len(v) == 64 for c in result["cases"] for v in c["component_sha256"].values())
    assert str(root) not in json.dumps(result)
    assert before == {p.name: p.read_bytes() for p in root.iterdir()}


@pytest.mark.parametrize("path,value,reason", [
    ("record/target_kind", "residual_plan", "TARGET_IS_NOT_PEAK_TOTAL"),
    ("record/target_kind", "crosshead", "TARGET_IS_NOT_PEAK_TOTAL"),
    ("record/observable", "crosshead_displacement", "OBSERVABLE_MISMATCH"),
    ("trace/observable", "green_lagrange", "OBSERVABLE_MISMATCH"),
    ("record/load_state", "unloaded", "LOAD_STATE_MISMATCH"),
    ("trace/load_state", "unloaded", "LOAD_STATE_MISMATCH"),
    ("record/strain_unit", "percent", "UNIT_MISMATCH"),
    ("trace/strain_unit", "percent", "UNIT_MISMATCH"),
    ("evidence/calibration/uncertainty/unit", "percent", "UNIT_MISMATCH"),
    ("evidence/stop_response/latency/unit", "ms", "UNIT_MISMATCH"),
    ("record/protocol_structure_status", "WAITING_APPROVAL", "STRUCTURAL_APPROVAL_MISSING"),
    ("evidence/calibration/sensor_id", "other-sensor", "IDENTITY_MISMATCH"),
    ("evidence/stop_response/configuration_id", "other-config", "IDENTITY_MISMATCH"),
    ("trace/reference_id", "other-reference", "IDENTITY_MISMATCH"),
    ("evidence/calibration/valid", False, "CALIBRATION_INVALID"),
    ("evidence/calibration/valid_until_s", .03, "CALIBRATION_EXPIRED"),
    ("evidence/stop_response/signal_loss_protection_verified", False, "SIGNAL_LOSS_PROTECTION_UNVERIFIED"),
    ("evidence/stop_response/clock_mapping_verified", False, "CLOCK_MAPPING_UNVERIFIED"),
    ("trace/samples/1/signal_valid", False, "SIGNAL_LOST"),
    ("trace/samples/1/time_s", 0., "CLOCK_RESET_OR_DUPLICATE"),
    ("trace/samples/1/sample_time_s", 0., "CLOCK_RESET_OR_DUPLICATE"),
    ("trace/samples/3/stop_ack", False, "STOP_ACK_MISSING_OR_AMBIGUOUS"),
    ("evidence/stop_response/latency/value", .001, "STOP_LATENCY_EXCEEDED"),
    ("trace/samples/1/force_N", 51., "FORCE_LIMIT_EXCEEDED"),
    ("trace/samples/1/force_N", -51., "FORCE_LIMIT_EXCEEDED"),
    ("trace/samples/1/travel_mm", 1.1, "TRAVEL_LIMIT_EXCEEDED"),
    ("trace/samples/1/travel_mm", -1.1, "TRAVEL_LIMIT_EXCEEDED"),
    ("trace/samples/3/strain", .04, "STOP_ERROR_EXCEEDED"),
    ("record/trigger_value", .05, "TARGET_NOT_REACHED"),
    ("trace/samples/0/strain", .037, "TARGET_CROSSING_UNOBSERVED"),
])
def test_semantic_refusals(root, path, value, reason):
    negative(root, {path: value}, [reason])


@pytest.mark.parametrize("path,unit,reason", [
    ("evidence/calibration/uncertainty", "fraction", "UNKNOWN_UNCERTAINTY"),
    ("evidence/stop_response/latency", "s", "UNKNOWN_LATENCY"),
])
def test_unknown_is_retained_and_refused(root, path, unit, reason):
    negative(root, {path: {"value_state": "unknown", "value": None, "unit": unit}}, [reason])
    node = document(root)["cases"][0]
    for key in path.split("/"):
        node = node[key]
    assert node["value"] is None


def test_stale_and_gap_signals(root):
    negative(root, {"record/limits/max_signal_gap_s": .01,
                    "trace/samples/3/time_s": .08}, ["STALE_SIGNAL", "SIGNAL_GAP_EXCEEDED"])


def test_early_ack_and_transient_overshoot_are_not_hidden(root):
    negative(root, {"trace/samples/3/stop_ack": False, "trace/samples/1/stop_ack": True},
             ["STOP_ACK_MISSING_OR_AMBIGUOUS", "STOP_ACK_BEFORE_TARGET"])
    shutil.copyfile(EXAMPLE / "fixture.json", root / "fixture.json")
    negative(root, {"trace/samples/2/strain": .05}, ["STOP_ERROR_EXCEEDED"])


def test_explicit_consistent_percent_conversion(root):
    doc = document(root)
    doc["cases"] = [doc["cases"][0]]
    c = doc["cases"][0]
    c["record"]["strain_unit"] = c["trace"]["strain_unit"] = "percent"
    c["record"]["trigger_value"] *= 100
    c["evidence"]["calibration"]["uncertainty"]["unit"] = "percent"
    c["evidence"]["calibration"]["uncertainty"]["value"] *= 100
    for sample in c["trace"]["samples"]:
        sample["strain"] *= 100
    assert verify(root, repin(root, doc))["benchmark_contract_passed"]


@pytest.mark.parametrize("path", ["record/trigger_value", "evidence/calibration/uncertainty/value", "evidence/stop_response/latency/value", "trace/samples/0/time_s", "trace/samples/0/strain", "record/limits/max_force_N"])
@pytest.mark.parametrize("value", [None, True, "0", float("nan"), float("inf")])
def test_invalid_or_unknown_numeric_cannot_be_coerced(root, path, value):
    doc = document(root)
    set_value(doc["cases"][0], path, value)
    with pytest.raises(a.AuditRejected, match="INVALID_NUMBER|NONFINITE_JSON"):
        verify(root, repin(root, doc))


@pytest.mark.parametrize("path,value,code", [
    ("evidence/calibration", None, "INVALID_FIELDS"),
    ("evidence/stop_response/latency", {"value_state": "unknown", "value": 0, "unit": "s"}, "UNKNOWN_MUST_STAY_NULL"),
    ("evidence/calibration/valid", "true", "INVALID_BOOLEAN"),
    ("trace/samples/0/stop_ack", 0, "INVALID_BOOLEAN"),
    ("evidence/calibration/content_kind", "measured", "FALSE_EVIDENCE_PROMOTION"),
    ("evidence/stop_response/evidence_id", "synthetic-calibration", "DUPLICATE_EVIDENCE_ID"),
    ("trace/samples", [], "INVALID_SAMPLE_COUNT"),
    ("oracle/reason_codes", ["X", "X"], "INVALID_ORACLE"),
])
def test_structural_invalidity_is_not_a_qualification_outcome(root, path, value, code):
    doc = document(root)
    set_value(doc["cases"][0], path, value)
    with pytest.raises(a.AuditRejected, match=code):
        verify(root, repin(root, doc))


def test_false_promotion_fields_and_missing_evidence(root):
    for change in ("add_command", "add_release", "remove_latency", "remove_calibration"):
        doc = json.loads((EXAMPLE / "fixture.json").read_text())
        c = doc["cases"][0]
        if change == "add_command": c["record"]["device_command"] = "synthetic forbidden payload"
        if change == "add_release": c["record"]["real_device_qualified"] = True
        if change == "remove_latency": del c["evidence"]["stop_response"]["latency"]
        if change == "remove_calibration": del c["evidence"]["calibration"]
        with pytest.raises(a.AuditRejected, match="INVALID_FIELDS"):
            verify(root, repin(root, doc))


def test_incorrect_oracle_is_software_failure_even_with_valid_bytes(root):
    doc = document(root)
    doc["cases"][1]["oracle"] = {"qualification_result": "SYNTHETIC_PASS", "reason_codes": []}
    result = verify(root, repin(root, doc))
    assert result["audit_accepted"] is True
    assert result["benchmark_contract_passed"] is False
    assert result["cases"][1]["qualification_result"] == "HOLD"


def test_hashes_bind_every_input_component(root):
    before = verify(root)
    doc = document(root)
    doc["cases"][0]["trace"]["samples"][1]["force_N"] += 1
    result = verify(root, repin(root, doc))
    assert result["fixture_sha256"] != before["fixture_sha256"]
    assert result["cases"][0]["component_sha256"]["trace"] != before["cases"][0]["component_sha256"]["trace"]
    assert result["cases"][0]["component_sha256"]["oracle"] == before["cases"][0]["component_sha256"]["oracle"]


def test_missing_and_changed_input_fail_closed(root):
    with pytest.raises(a.AuditRejected, match="MANIFEST_HASH_MISMATCH"):
        verify(root, "0" * 64)
    (root / "fixture.json").write_text("{}")
    with pytest.raises(a.AuditRejected, match="SOURCE_SHA256_MISMATCH"):
        verify(root)
    (root / "fixture.json").unlink()
    with pytest.raises(a.AuditRejected, match="LOCAL_INPUT_UNAVAILABLE_OR_UNSAFE"):
        verify(root)


@pytest.mark.parametrize("path", ["../fixture.json", "/fixture.json", "https://example.invalid/file", "x/../fixture.json"])
def test_source_path_escape_refused(root, path):
    spec = json.loads((root / "manifest.json").read_text())
    spec["fixture"]["path"] = path
    raw = json.dumps(spec).encode()
    (root / "manifest.json").write_bytes(raw)
    with pytest.raises(a.AuditRejected, match="INVALID_LOCAL_PATH"):
        verify(root, a._sha256(raw))


def test_symlink_and_wrong_blob_refused(root, tmp_path):
    raw = (root / "fixture.json").read_bytes()
    (root / "fixture.json").unlink()
    outside = tmp_path / "outside.json"
    outside.write_bytes(raw)
    (root / "fixture.json").symlink_to(outside)
    with pytest.raises(a.AuditRejected, match="LOCAL_INPUT_UNAVAILABLE_OR_UNSAFE"):
        verify(root)
    (root / "fixture.json").unlink()
    (root / "fixture.json").write_bytes(raw)
    spec = json.loads((root / "manifest.json").read_text())
    spec["fixture"]["git_blob_sha1"] = "0" * 40
    data = json.dumps(spec).encode()
    (root / "manifest.json").write_bytes(data)
    with pytest.raises(a.AuditRejected, match="SOURCE_BLOB_MISMATCH"):
        verify(root, a._sha256(data))


@pytest.mark.parametrize("field,value,code", [("access", "private", "INVALID_ACCESS_CATEGORY"), ("access", "unknown", "INVALID_ACCESS_CATEGORY"), ("source_revision", "c" * 40, "REVISION_OR_SCHEMA_MISMATCH")])
def test_manifest_contract(root, field, value, code):
    spec = json.loads((root / "manifest.json").read_text())
    spec[field] = value
    raw = json.dumps(spec).encode()
    (root / "manifest.json").write_bytes(raw)
    with pytest.raises(a.AuditRejected, match=code):
        verify(root, a._sha256(raw))


def test_no_network_process_or_device_imports(root, monkeypatch):
    import socket
    def denied(*args, **kwargs):
        raise AssertionError("External operation forbidden")
    monkeypatch.setattr(socket, "socket", denied)
    monkeypatch.setattr(subprocess, "Popen", denied)
    assert verify(root)["benchmark_contract_passed"]
    assert not any(name in sys.modules for name in ("bluesky", "ophyd", "bluesky_queueserver"))


@pytest.mark.parametrize("mutation,code", [
    ("empty", "INVALID_CASE_COUNT"), ("too_many", "INVALID_CASE_COUNT"),
    ("duplicate", "DUPLICATE_CASE_ID"), ("too_many_samples", "INVALID_SAMPLE_COUNT"),
    ("measured", "FALSE_EVIDENCE_PROMOTION"), ("private", "SOURCE_ACCESS_MISMATCH"),
])
def test_bounded_fixture_and_source_identity(root, mutation, code):
    doc = document(root)
    if mutation == "empty": doc["cases"] = []
    if mutation == "too_many": doc["cases"] = [doc["cases"][0]] * 33
    if mutation == "duplicate": doc["cases"][1]["case_id"] = doc["cases"][0]["case_id"]
    if mutation == "too_many_samples": doc["cases"][0]["trace"]["samples"] *= 65
    if mutation == "measured": doc["content_kind"] = "measured"
    if mutation == "private": doc["access"] = "private"
    with pytest.raises(a.AuditRejected, match=code):
        verify(root, repin(root, doc))


def test_cli_pass_oracle_failure_and_invalid_input(root):
    command = [sys.executable, "-m", "opendot_engineering.adapters.lab_qualification", "--root", str(root),
               "--expected-revision", REVISION, "--expected-manifest-sha256", PIN]
    result = subprocess.run(command, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0
    assert json.loads(result.stdout)["benchmark_contract_passed"]
    doc = document(root)
    doc["cases"][0]["oracle"]["qualification_result"] = "HOLD"
    command[-1] = repin(root, doc)
    result = subprocess.run(command, capture_output=True, text=True, timeout=10)
    assert result.returncode == 1
    assert json.loads(result.stdout)["audit_accepted"]
    command[-1] = "0" * 64
    result = subprocess.run(command, capture_output=True, text=True, timeout=10)
    assert result.returncode == 2 and not result.stdout
    assert str(root) not in result.stderr
    assert json.loads(result.stderr)["real_device_qualified"] is False
