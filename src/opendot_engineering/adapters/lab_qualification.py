"""Offline synthetic qualification-record checks, never an instrument controller.

Consumes pinned local bytes using the source-audit reader. No runtime, artifact
store, scientific ingestion, device interface, or protocol compiler lives here.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import sys

from . import source_audit as a

SCHEMA = "opendot.synthetic-qualification.v1"
MAX_CASES = 32
MAX_SAMPLES = 256


def _number(value, *, positive=False):
    try:
        valid = type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        valid = False
    a._require(valid and (not positive or value > 0), "INVALID_NUMBER")
    return value


def _boolean(value):
    a._require(type(value) is bool, "INVALID_BOOLEAN")


def _quantity(value):
    a._keys(value, {"value_state", "value", "unit"})
    a._enum(value["value_state"], {"known", "unknown"}, "INVALID_VALUE_STATE")
    a._string(value["unit"])
    if value["value_state"] == "unknown":
        a._require(value["value"] is None, "UNKNOWN_MUST_STAY_NULL")
    else:
        a._require(_number(value["value"]) >= 0, "INVALID_NUMBER")


def _digest(value):
    return a._sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                allow_nan=False).encode("utf-8"))


def _evaluate(case):
    """Validate structure and evaluate recorded synthetic evidence, without I/O."""
    a._keys(case, {"case_id", "record", "evidence", "trace", "oracle"})
    a._identifier(case["case_id"])
    record, evidence, trace, oracle = (case[k] for k in ("record", "evidence", "trace", "oracle"))
    identity = {"sensor_id", "configuration_id", "reference_id"}
    observables = {"observable", "load_state", "strain_unit"}
    a._keys(record, identity | observables | {"target_kind", "trigger_value", "limits", "protocol_structure_status"})
    a._keys(evidence, {"calibration", "stop_response"})
    calibration, response = evidence["calibration"], evidence["stop_response"]
    a._keys(calibration, identity | {"evidence_id", "content_kind", "valid", "valid_from_s", "valid_until_s", "uncertainty"})
    a._keys(response, identity | {"evidence_id", "content_kind", "latency", "signal_loss_protection_verified", "clock_mapping_verified"})
    a._keys(trace, identity | observables | {"samples"})
    for obj in (record, calibration, response, trace):
        for key in identity:
            a._identifier(obj[key])
    for obj in (record, trace):
        for key in observables:
            a._string(obj[key])
    for obj in (calibration, response):
        a._identifier(obj["evidence_id"])
        a._require(obj["content_kind"] == "synthetic", "FALSE_EVIDENCE_PROMOTION")
    a._require(calibration["evidence_id"] != response["evidence_id"], "DUPLICATE_EVIDENCE_ID")
    a._string(record["target_kind"])
    a._enum(record["protocol_structure_status"], {"READY_FOR_HUMAN_EXECUTION", "WAITING_APPROVAL"}, "INVALID_STRUCTURE_STATUS")
    _number(record["trigger_value"], positive=True)
    limits = record["limits"]
    a._keys(limits, {"max_force_N", "max_travel_mm", "max_signal_gap_s", "max_stop_error_fraction"})
    for value in limits.values():
        _number(value, positive=True)
    _boolean(calibration["valid"])
    for key in ("valid_from_s", "valid_until_s"):
        _number(calibration[key])
    a._require(calibration["valid_from_s"] <= calibration["valid_until_s"], "INVALID_CALIBRATION_INTERVAL")
    for key in ("signal_loss_protection_verified", "clock_mapping_verified"):
        _boolean(response[key])
    _quantity(calibration["uncertainty"])
    _quantity(response["latency"])
    samples = trace["samples"]
    a._require(type(samples) is list and 2 <= len(samples) <= MAX_SAMPLES, "INVALID_SAMPLE_COUNT")
    for sample in samples:
        a._keys(sample, {"time_s", "sample_time_s", "strain", "force_N", "travel_mm", "signal_valid", "stop_ack"})
        for key in ("time_s", "sample_time_s", "strain", "force_N", "travel_mm"):
            _number(sample[key])
        _boolean(sample["signal_valid"])
        _boolean(sample["stop_ack"])
    a._keys(oracle, {"qualification_result", "reason_codes"})
    a._enum(oracle["qualification_result"], {"SYNTHETIC_PASS", "HOLD"}, "INVALID_ORACLE")
    a._require(type(oracle["reason_codes"]) is list and len(oracle["reason_codes"]) <= 32, "INVALID_ORACLE")
    for code in oracle["reason_codes"]:
        a._identifier(code)
    a._require(len(set(oracle["reason_codes"])) == len(oracle["reason_codes"]), "INVALID_ORACLE")

    reasons = set()
    def hold(condition, code):
        if condition:
            reasons.add(code)
    hold(any(obj[k] != record[k] for obj in (calibration, response, trace) for k in identity), "IDENTITY_MISMATCH")
    hold(record["observable"] != "engineering_strain" or trace["observable"] != record["observable"], "OBSERVABLE_MISMATCH")
    hold(record["load_state"] != "loaded" or trace["load_state"] != record["load_state"], "LOAD_STATE_MISMATCH")
    hold(record["target_kind"] != "peak_total", "TARGET_IS_NOT_PEAK_TOTAL")
    hold(record["protocol_structure_status"] != "READY_FOR_HUMAN_EXECUTION", "STRUCTURAL_APPROVAL_MISSING")
    units_ok = (record["strain_unit"] in {"fraction", "percent"}
                and trace["strain_unit"] == record["strain_unit"]
                and calibration["uncertainty"]["unit"] == record["strain_unit"]
                and response["latency"]["unit"] == "s")
    hold(not units_ok, "UNIT_MISMATCH")
    hold(not calibration["valid"], "CALIBRATION_INVALID")
    hold(any(not calibration["valid_from_s"] <= x["time_s"] <= calibration["valid_until_s"] for x in samples), "CALIBRATION_EXPIRED")
    hold(calibration["uncertainty"]["value_state"] == "unknown", "UNKNOWN_UNCERTAINTY")
    hold(response["latency"]["value_state"] == "unknown", "UNKNOWN_LATENCY")
    hold(not response["signal_loss_protection_verified"], "SIGNAL_LOSS_PROTECTION_UNVERIFIED")
    hold(not response["clock_mapping_verified"], "CLOCK_MAPPING_UNVERIFIED")
    hold(any(not x["signal_valid"] for x in samples), "SIGNAL_LOST")
    hold(any(x["time_s"] - x["sample_time_s"] > limits["max_signal_gap_s"] for x in samples), "STALE_SIGNAL")
    clock_bad = (any(x["sample_time_s"] > x["time_s"] for x in samples)
                 or any(right[k] <= left[k] for left, right in zip(samples, samples[1:]) for k in ("time_s", "sample_time_s")))
    hold(clock_bad, "CLOCK_RESET_OR_DUPLICATE")
    hold(any(right["sample_time_s"] - left["sample_time_s"] > limits["max_signal_gap_s"] for left, right in zip(samples, samples[1:])), "SIGNAL_GAP_EXCEEDED")
    hold(any(abs(x["force_N"]) > limits["max_force_N"] for x in samples), "FORCE_LIMIT_EXCEEDED")
    hold(any(abs(x["travel_mm"]) > limits["max_travel_mm"] for x in samples), "TRAVEL_LIMIT_EXCEEDED")
    acknowledgements = [i for i, x in enumerate(samples) if x["stop_ack"]]
    hold(len(acknowledgements) != 1 or acknowledgements[-1:] != [len(samples) - 1], "STOP_ACK_MISSING_OR_AMBIGUOUS")
    if units_ok and not clock_bad:
        scale = 0.01 if record["strain_unit"] == "percent" else 1.0
        target = record["trigger_value"] * scale
        crossings = [i for i, x in enumerate(samples) if x["strain"] * scale >= target]
        hold(not crossings, "TARGET_NOT_REACHED")
        hold(bool(crossings) and crossings[0] == 0, "TARGET_CROSSING_UNOBSERVED")
        if crossings and len(acknowledgements) == 1:
            crossing, ack = crossings[0], acknowledgements[0]
            hold(ack < crossing, "STOP_ACK_BEFORE_TARGET")
            latency = response["latency"]
            if latency["value_state"] == "known":
                hold(samples[ack]["time_s"] - samples[crossing]["sample_time_s"] > latency["value"], "STOP_LATENCY_EXCEEDED")
            uncertainty = calibration["uncertainty"]
            if uncertainty["value_state"] == "known":
                # Check the recorded maximum, not merely the final acknowledgement.
                overshoot = max(0.0, max(x["strain"] * scale for x in samples) - target)
                hold(overshoot + uncertainty["value"] * scale > limits["max_stop_error_fraction"], "STOP_ERROR_EXCEEDED")
    result = "HOLD" if reasons else "SYNTHETIC_PASS"
    return {"case_id": case["case_id"], "qualification_result": result,
            "reason_codes": sorted(reasons),
            "oracle_matched": result == oracle["qualification_result"] and reasons == set(oracle["reason_codes"]),
            "component_sha256": {k: _digest(case[k]) for k in ("record", "evidence", "trace", "oracle")},
            "protocol_structure_status": record["protocol_structure_status"],
            "protocol_structure_verified": False,
            "real_device_qualified": False, "device_control_authorized": False, "scientific_accepted": False}


def verify_bundle(root, manifest, *, expected_revision, expected_manifest_sha256):
    """Audit pinned synthetic bytes and compare outcomes with a pinned oracle.

    Pins come from trusted operator configuration, not the bundle itself. No
    source authenticity, physical qualification, or independent review is claimed.
    """
    a._hash(expected_revision, 40)
    a._hash(expected_manifest_sha256, 64)
    fd = a._root_fd(root)
    try:
        raw_manifest = a._read(fd, manifest, a.MAX_MANIFEST_BYTES)
        a._require(a._sha256(raw_manifest) == expected_manifest_sha256, "MANIFEST_HASH_MISMATCH")
        spec = a._decode(raw_manifest)
        a._keys(spec, {"schema", "source_revision", "access", "fixture"})
        a._require(spec["schema"] == SCHEMA and spec["source_revision"] == expected_revision, "REVISION_OR_SCHEMA_MISMATCH")
        a._enum(spec["access"], {"public"}, "INVALID_ACCESS_CATEGORY")
        source = spec["fixture"]
        a._keys(source, {"path", "sha256", "git_blob_sha1"})
        a._hash(source["sha256"], 64)
        a._hash(source["git_blob_sha1"], 40)
        raw = a._read(fd, source["path"], a.MAX_SOURCE_BYTES)
        a._require(a._sha256(raw) == source["sha256"], "SOURCE_SHA256_MISMATCH")
        a._require(a._git_blob(raw) == source["git_blob_sha1"], "SOURCE_BLOB_MISMATCH")
        fixture = a._decode(raw)
        a._keys(fixture, {"schema", "source_revision", "access", "content_kind", "cases"})
        a._require(fixture["schema"] == SCHEMA and fixture["source_revision"] == expected_revision, "REVISION_OR_SCHEMA_MISMATCH")
        a._require(fixture["access"] == spec["access"], "SOURCE_ACCESS_MISMATCH")
        a._require(fixture["content_kind"] == "synthetic", "FALSE_EVIDENCE_PROMOTION")
        a._require(type(fixture["cases"]) is list and 1 <= len(fixture["cases"]) <= MAX_CASES, "INVALID_CASE_COUNT")
        outcomes = [_evaluate(case) for case in fixture["cases"]]
        a._require(len({x["case_id"] for x in outcomes}) == len(outcomes), "DUPLICATE_CASE_ID")
        return {"schema": SCHEMA + ".receipt", "audit_accepted": True,
                "benchmark_contract_passed": all(x["oracle_matched"] for x in outcomes),
                "real_device_qualified": False, "device_control_authorized": False, "scientific_accepted": False,
                "owner_integration": "NOT_EVALUATED", "independent_review": "NOT_EVALUATED",
                "source_revision": expected_revision, "manifest_sha256": expected_manifest_sha256,
                "fixture_sha256": source["sha256"], "fixture_git_blob_sha1": source["git_blob_sha1"],
                "adapter_source_sha256": {name: a._sha256(path.read_bytes()) for name, path in (
                    ("lab_qualification.py", Path(__file__)), ("source_audit.py", Path(a.__file__)))},
                "cases": outcomes}
    finally:
        os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--manifest", default="manifest.json")
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = verify_bundle(args.root, args.manifest, expected_revision=args.expected_revision,
                               expected_manifest_sha256=args.expected_manifest_sha256)
    except a.AuditRejected as exc:
        print(json.dumps({"audit_accepted": False, "benchmark_contract_passed": False,
                          "real_device_qualified": False, "device_control_authorized": False,
                          "scientific_accepted": False, "error_code": exc.code}), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, indent=2, allow_nan=False))
    return 0 if result["benchmark_contract_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
