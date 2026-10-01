"""Finite, local Bluesky/ophyd simulation and pinned raw-document verification.

Original Apache-2.0 integration. No hardware, injected devices, custom plans,
network transports, server, scheduler, resume, or physical qualification.
"""
from __future__ import annotations

import argparse
from importlib.metadata import PackageNotFoundError, version
import json
import math
import os
import re
from pathlib import Path
import subprocess
import sys
import time

from . import source_audit as a

SCHEMA = "opendot.simulated-lab.v1"
MAX_POINTS = 16
MAX_DOCUMENTS = MAX_POINTS + 3
MAX_RAW_BYTES = 256 * 1024
WORKER_TIMEOUT_S = 8
TESTED_VERSIONS = {"bluesky": "1.15.1", "ophyd": "1.11.2", "event-model": "1.24.0"}
SCENARIOS = {"normal", "fake_failure", "simulated_abort"}


def _claims():
    return {"mode": "SIMULATED_ONLY", "scientific_accepted": False,
            "device_authority": False, "device_control_authorized": False,
            "real_device_qualified": False, "physical_calibration": "NOT_IMPLEMENTED",
            "real_interlocks": "NOT_IMPLEMENTED", "resume": "NOT_IMPLEMENTED",
            "owner_integration": "NOT_EVALUATED", "independent_review": "NOT_EVALUATED"}


def _json(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def _request(setpoints, scenario):
    # Do not accept arbitrary iterators, callbacks, device objects or coercible values.
    a._require(type(setpoints) in (list, tuple) and 1 <= len(setpoints) <= MAX_POINTS,
               "INVALID_SETPOINT_COUNT")
    values = []
    for item in setpoints:
        try:
            valid = type(item) in (int, float) and math.isfinite(item) and -1 <= item <= 1
        except OverflowError:
            valid = False
        a._require(valid, "SETPOINT_OUT_OF_BOUNDS")
        values.append(float(item))
    a._enum(scenario, SCENARIOS, "INVALID_SCENARIO")
    return {"setpoints": values, "scenario": scenario}


def _versions():
    try:
        versions = {name: version(name) for name in TESTED_VERSIONS}
    except PackageNotFoundError:
        raise a.AuditRejected("SIMULATION_DEPENDENCY_MISSING") from None
    a._require(versions == TESTED_VERSIONS, "SIMULATION_DEPENDENCY_VERSION_UNTESTED")
    return versions


def _write_new(fd, name, data):
    file_fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                      0o600, dir_fd=fd)
    with os.fdopen(file_fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def run_simulation(output_root, *, setpoints=(0.0, 0.5, -0.5), scenario="normal"):
    """Run one fixed simulation; output_root must be an existing empty directory.

    Validate before creating output or starting a worker. The fixed worker has an
    eight-second subprocess timeout. A timeout records incomplete evidence; it
    never invents a Bluesky stop document. Local disk/OS failures may leave a
    partial bundle, which verification rejects. Outputs are exclusively created.
    """
    request = _request(setpoints, scenario)
    versions = _versions()
    root_fd = a._root_fd(output_root)
    try:
        a._require(not os.listdir(root_fd), "OUTPUT_DIRECTORY_NOT_EMPTY")
        raw_fd = os.open("documents.jsonl", os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                         os.O_APPEND | os.O_NOFOLLOW, 0o600, dir_fd=root_fd)
        started = time.monotonic()
        failure = None
        # Isolated interpreter prevents caller PYTHONPATH/user-site injection.
        # No control-layer auto-detection, telemetry export, or inherited secrets.
        env = {"OPHYD_CONTROL_LAYER": "dummy", "OTEL_SDK_DISABLED": "true",
               "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1"}
        try:
            completed = subprocess.run(
                [sys.executable, "-I", "-B", str(Path(__file__).with_name("_simulated_lab_worker.py")), str(raw_fd)],
                input=_json(request), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                env=env, pass_fds=(raw_fd,), timeout=WORKER_TIMEOUT_S, check=False,
            )
            if completed.returncode != 0:
                failure = "WORKER_FAILED"
        except subprocess.TimeoutExpired:
            failure = "WORKER_TIMEOUT"
        except OSError:
            failure = "WORKER_UNAVAILABLE"
        finally:
            os.close(raw_fd)
        elapsed = time.monotonic() - started
        raw = a._read(root_fd, "documents.jsonl", MAX_RAW_BYTES)
        # Preserve raw bytes, including a partial last line after process termination.
        status = "incomplete"
        stop_uid = None
        if failure is None:
            try:
                summary = a._decode(completed.stdout)
                a._keys(summary, {"exit_status", "stop_uid"})
                a._enum(summary["exit_status"], {"success", "fail", "abort"}, "INVALID_WORKER_RESULT")
                a._string(summary["stop_uid"])
                status, stop_uid = summary["exit_status"], summary["stop_uid"]
            except a.AuditRejected:
                failure = "INVALID_WORKER_RESULT"
        terminal = {"schema": SCHEMA, **_claims(), "request": request,
                    "exit_status": status, "error_code": failure, "stop_uid": stop_uid,
                    "elapsed_s": elapsed, "worker_timeout_s": WORKER_TIMEOUT_S,
                    "versions": versions}
        terminal_raw = _json(terminal)
        _write_new(root_fd, "terminal.json", terminal_raw)
        manifest = {"schema": SCHEMA, **_claims(), "files": {
            "documents.jsonl": {"sha256": a._sha256(raw), "bytes": len(raw)},
            "terminal.json": {"sha256": a._sha256(terminal_raw), "bytes": len(terminal_raw)},
        }}
        manifest_raw = _json(manifest)
        _write_new(root_fd, "manifest.json", manifest_raw)
        os.fsync(root_fd)
        return {**terminal, "manifest_sha256": a._sha256(manifest_raw)}
    finally:
        os.close(root_fd)


def verify_run(root, *, expected_manifest_sha256):
    """Read only: verify a pin supplied independently of the bundle.

    Byte consistency is not authenticity, immutable storage, scientific validity,
    permission to operate devices, or calibration. No optional imports required.
    """
    a._hash(expected_manifest_sha256, 64)
    root_fd = a._root_fd(root)
    try:
        manifest_raw = a._read(root_fd, "manifest.json", 16 * 1024)
        a._require(a._sha256(manifest_raw) == expected_manifest_sha256, "MANIFEST_HASH_MISMATCH")
        manifest = a._decode(manifest_raw)
        a._keys(manifest, {"schema", "files", *_claims()})
        a._require(manifest["schema"] == SCHEMA, "SCHEMA_MISMATCH")
        _check_claims(manifest)
        a._keys(manifest["files"], {"documents.jsonl", "terminal.json"})
        contents = {}
        for name, entry in manifest["files"].items():
            a._keys(entry, {"sha256", "bytes"})
            a._hash(entry["sha256"], 64)
            a._require(type(entry["bytes"]) is int and 0 <= entry["bytes"] <= MAX_RAW_BYTES,
                       "INVALID_BYTE_COUNT")
            raw = a._read(root_fd, name, MAX_RAW_BYTES)
            a._require(len(raw) == entry["bytes"] and a._sha256(raw) == entry["sha256"],
                       "RAW_HASH_MISMATCH")
            contents[name] = raw
    finally:
        os.close(root_fd)
    terminal = a._decode(contents["terminal.json"])
    a._keys(terminal, {"schema", *_claims(), "request", "exit_status", "error_code", "stop_uid",
                       "elapsed_s", "worker_timeout_s", "versions"})
    a._require(terminal["schema"] == SCHEMA, "SCHEMA_MISMATCH")
    _check_claims(terminal)
    a._keys(terminal["request"], {"setpoints", "scenario"})
    request = _request(**terminal["request"])
    a._require(_same(terminal["versions"], TESTED_VERSIONS) and
               type(terminal["worker_timeout_s"]) is int and terminal["worker_timeout_s"] == WORKER_TIMEOUT_S,
               "UNTESTED_RUNTIME")
    a._require(type(terminal["elapsed_s"]) in (float, int) and
               0 <= terminal["elapsed_s"] <= 10 and math.isfinite(terminal["elapsed_s"]),
               "RUN_DURATION_EXCEEDED")
    a._require(terminal["error_code"] is None and terminal["exit_status"] != "incomplete",
               "INCOMPLETE_RUN")
    raw = contents["documents.jsonl"]
    a._require(raw.endswith(b"\n"), "TRUNCATED_DOCUMENTS")
    lines = raw.splitlines()
    a._require(2 <= len(lines) <= MAX_DOCUMENTS, "INVALID_DOCUMENT_COUNT")
    records = [a._decode(line) for line in lines]
    for record in records:
        a._keys(record, {"name", "doc"})
        a._enum(record["name"], {"start", "descriptor", "event", "stop"}, "INVALID_DOCUMENT_NAME")
        a._require(type(record["doc"]) is dict, "INVALID_DOCUMENT")
    expected, event_count = _validate_documents(records, terminal, request)
    return {"schema": SCHEMA, **_claims(), "audit_accepted": True,
            "manifest_sha256": expected_manifest_sha256, "exit_status": expected,
            "documents": len(records), "events": event_count}


def _same(value, expected):
    """JSON structural equality with exact types, so bool is never an integer."""
    if type(value) is not type(expected):
        return False
    if type(expected) is dict:
        return value.keys() == expected.keys() and all(_same(value[k], v) for k, v in expected.items())
    if type(expected) is list:
        return len(value) == len(expected) and all(_same(x, y) for x, y in zip(value, expected))
    return value == expected


def _fixed(value, expected):
    a._require(_same(value, expected), "DOCUMENT_SCHEMA_MISMATCH")


def _uid(value):
    a._require(type(value) is str and re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", value) is not None,
        "INVALID_DOCUMENT_UID")


def _timestamp(value, lower, upper):
    # Comparison before isfinite also safely rejects enormous JSON integers.
    a._require(type(value) in (int, float) and 0 < lower <= value <= upper < 1e20 and
               math.isfinite(value), "INVALID_DOCUMENT_TIME")


def _signal_schema(name, *, object_name=None, integer=False):
    result = {"dtype": "integer" if integer else "number", "shape": [], "source": "SIM:" + name}
    if not integer:
        result["precision"] = 3
    if object_name is not None:
        result["object_name"] = object_name
    return result


def _validate_documents(records, terminal, request):
    """Validate this fixed producer's exact declarations, not physical origin.

    This deliberately narrower profile is not a general Event Model validator.
    Source strings, units, timestamps and UUIDs remain unauthenticated claims.
    """
    expected = {"normal": "success", "fake_failure": "fail", "simulated_abort": "abort"}[request["scenario"]]
    count = len(request["setpoints"]) if expected == "success" else 0
    names = [record["name"] for record in records]
    profile = ["start", "descriptor", *(["event"] * count), "stop"] if count else ["start", "stop"]
    a._require(names == profile, "INVALID_DOCUMENT_ORDER")
    start, stop = records[0]["doc"], records[-1]["doc"]
    a._keys(start, {*_claims(), "plan_name", "plan_type", "scan_id", "simulation_request", "time", "uid", "versions"})
    a._keys(stop, {"exit_status", "num_events", "reason", "run_start", "time", "uid"})
    _check_claims(start)
    _fixed(start["plan_name"], "bounded_simulated_set_read")
    _fixed(start["plan_type"], "generator")
    _fixed(start["scan_id"], 1)
    _fixed(start["versions"], {"bluesky": TESTED_VERSIONS["bluesky"],
                              "ophyd": TESTED_VERSIONS["ophyd"], "event_model": TESTED_VERSIONS["event-model"]})
    a._require(_same(start["simulation_request"], request), "REQUEST_MISMATCH")
    _uid(terminal["stop_uid"])
    # Require presence, valid UUID4 syntax, uniqueness, and chronological document times.
    seen = set()
    last_time = 1e-12
    for record in records:
        document = record["doc"]
        a._require("uid" in document and "time" in document, "MISSING_DOCUMENT_IDENTITY")
        _uid(document["uid"])
        a._require(document["uid"] not in seen, "DUPLICATE_DOCUMENT_UID")
        seen.add(document["uid"])
        _timestamp(document["time"], last_time, 1e19)
        last_time = document["time"]
    a._require(stop["time"] - start["time"] <= WORKER_TIMEOUT_S, "RUN_DURATION_EXCEEDED")
    a._require(terminal["exit_status"] == stop["exit_status"] == expected and
               terminal["stop_uid"] == stop["uid"] and stop["run_start"] == start["uid"], "TERMINAL_MISMATCH")
    _fixed(stop["reason"], "INJECTED_FAKE_DETECTOR_FAILURE" if expected == "fail" else "")
    _fixed(stop["num_events"], {"primary": count} if count else {})
    if not count:
        return expected, count
    descriptor = records[1]["doc"]
    a._keys(descriptor, {"configuration", "data_keys", "hints", "name", "object_classes", "object_keys", "run_start", "time", "uid"})
    _fixed(descriptor["run_start"], start["uid"])
    _fixed(descriptor["name"], "primary")
    _fixed(descriptor["object_classes"], {})
    _fixed(descriptor["object_keys"], {"sim_axis": ["sim_axis", "sim_axis_setpoint"], "sim_detector": ["sim_detector"]})
    _fixed(descriptor["hints"], {"sim_axis": {"fields": ["sim_axis"]}, "sim_detector": {"fields": []}})
    fields = {"sim_axis": "sim_axis", "sim_axis_setpoint": "sim_axis", "sim_detector": "sim_detector"}
    _fixed(descriptor["data_keys"], {name: _signal_schema(name, object_name=owner) for name, owner in fields.items()})
    configuration = descriptor["configuration"]
    a._keys(configuration, {"sim_axis", "sim_detector"})
    fixed_config = {"sim_axis": {"sim_axis_acceleration": 1, "sim_axis_velocity": 1},
                    "sim_detector": {"sim_detector": 2 * request["setpoints"][0] + 1}}
    for name, data in fixed_config.items():
        entry = configuration[name]
        a._keys(entry, {"data", "data_keys", "timestamps"})
        _fixed(entry["data"], data)
        _fixed(entry["data_keys"], {key: _signal_schema(key, integer=name == "sim_axis") for key in data})
        a._keys(entry["timestamps"], data.keys())
        for timestamp in entry["timestamps"].values():
            # Axis configuration was initialized shortly before run start.
            _timestamp(timestamp, max(1e-12, start["time"] - terminal["elapsed_s"]), descriptor["time"])
    previous_timestamps = {key: start["time"] for key in fields}
    for index, (record, point) in enumerate(zip(records[2:-1], request["setpoints"]), 1):
        event = record["doc"]
        a._keys(event, {"data", "descriptor", "filled", "seq_num", "time", "timestamps", "uid"})
        _fixed(event["descriptor"], descriptor["uid"])
        _fixed(event["filled"], {})
        a._require(type(event["seq_num"]) is int and event["seq_num"] == index and
                   _same(event["data"], {"sim_axis": point, "sim_axis_setpoint": point, "sim_detector": 2 * point + 1}),
                   "SIMULATED_DATA_MISMATCH")
        a._keys(event["timestamps"], fields.keys())
        for key, timestamp in event["timestamps"].items():
            _timestamp(timestamp, previous_timestamps[key], event["time"])
        previous_timestamps = event["timestamps"]
    _fixed(configuration["sim_detector"]["timestamps"]["sim_detector"],
           records[2]["doc"]["timestamps"]["sim_detector"])
    return expected, count


def _check_claims(value):
    a._require(all(type(value.get(k)) is type(v) and value[k] == v for k, v in _claims().items()),
               "FALSE_EVIDENCE_PROMOTION")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("output_root")
    run.add_argument("--setpoints", type=float, nargs="+", default=[0, .5, -.5])
    run.add_argument("--scenario", choices=sorted(SCENARIOS), default="normal")
    verify = commands.add_parser("verify")
    verify.add_argument("root")
    verify.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            result = run_simulation(args.output_root, setpoints=args.setpoints, scenario=args.scenario)
        else:
            result = verify_run(args.root, expected_manifest_sha256=args.manifest_sha256)
        print(json.dumps(result, sort_keys=True, allow_nan=False))
        return 0 if result.get("error_code") is None else 1
    except a.AuditRejected as exc:
        print(json.dumps({"error_code": exc.code, **_claims()}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
