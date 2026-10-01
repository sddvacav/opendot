"""Fast deterministic contract tests plus optional real CAD integration tests."""
from dataclasses import asdict
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

from opendot_engineering.executors import geometry as g


def _has_tested_build123d():
    try:
        return importlib.metadata.version("build123d") == g.TESTED_BUILD123D
    except importlib.metadata.PackageNotFoundError:
        return False


cad = pytest.mark.skipif(not _has_tested_build123d(), reason="optional tested build123d==0.10.0 environment unavailable")
cq = pytest.mark.skipif(importlib.util.find_spec("cadquery") is None, reason="optional CadQuery compatibility reader unavailable")


def test_import_does_not_load_optional_cad_backends():
    code = "import sys; import opendot_engineering.executors.geometry; assert not any(n in sys.modules for n in ('build123d','cadquery','OCP'))"
    subprocess.run([sys.executable, "-c", code], check=True, capture_output=True, text=True, timeout=10)


def test_si_contract_and_analytical_volume():
    spec = g.BeamGeometry.from_parameters({})
    assert spec.dimensions_mm == (200., 20., 3.)
    assert spec.volume_m3 == pytest.approx(1.2e-5)
    assert g.BeamGeometry.from_parameters({"length_m": 0.3}).dimensions_mm[0] == 300.
    assert g.canonical_bytes({"b": 2, "a": 1}) == g.canonical_bytes({"a": 1, "b": 2})


@pytest.mark.parametrize("parameters", [
    {"length_m": float("nan")}, {"width_m": float("inf")}, {"thickness_m": -float("inf")},
    {"length_m": True}, {"width_m": "0.02"}, {"thickness_m": None},
    {"length_m": 0}, {"width_m": -1}, {"thickness_m": 0.0001},
    {"length_m": 100}, {"width_m": 0.1}, {"thickness_m": 0.1},
    {"output": "/tmp/not-an-input-parameter"}, {"code": "print('never evaluated')"}, [], None,
    {"length_m": 10**1000},
])
def test_rejects_unbounded_or_non_numeric_parameters(parameters, tmp_path):
    with pytest.raises(ValueError):
        g.export_beam(parameters, tmp_path / "untouched")
    assert not (tmp_path / "untouched").exists()


@pytest.mark.parametrize("parameters", [
    {"length_m": .05, "width_m": .005, "thickness_m": .001},
    {"length_m": .5, "width_m": .05, "thickness_m": .01},
])
def test_bounds_are_explicit_and_inclusive(parameters):
    assert asdict(g.BeamGeometry.from_parameters(parameters)) == parameters


def test_output_refuses_existing_empty_nonempty_and_symlink(tmp_path):
    empty = tmp_path / "empty"; empty.mkdir()
    full = tmp_path / "full"; full.mkdir(); (full / "keep").write_text("unchanged")
    alias = tmp_path / "alias"; alias.symlink_to(full, target_is_directory=True)
    for path in (empty, full, alias):
        with pytest.raises(ValueError, match="must not exist"):
            g._new_output_directory(path)
    with pytest.raises(ValueError, match="Symlink"):
        g._new_output_directory(alias / "child")
    assert (full / "keep").read_text() == "unchanged"


def test_missing_optional_dependency_is_actionable(monkeypatch, tmp_path):
    def missing(name):
        raise ModuleNotFoundError(name)
    monkeypatch.setattr(g.importlib, "import_module", missing)
    with pytest.raises(RuntimeError, match="separate CAD environment"):
        g.export_beam({}, tmp_path / "not-created")
    assert not (tmp_path / "not-created").exists()


def test_measurements_reject_scale_topology_nonfinite_and_translation():
    spec = g.BeamGeometry()
    good = {"valid": True, "solids": 1, "faces": 6, "edges": 12, "vertices": 8,
            "volume_mm3": 12000., "bbox_min_mm": [0., 0., 0.], "bbox_max_mm": [200., 20., 3.]}
    assert g._check_measurements(good, spec)["volume_m3"] == pytest.approx(1.2e-5)
    for change in ({"volume_mm3": 1.2e-5}, {"solids": 2}, {"valid": False},
                   {"bbox_max_mm": [.2, .02, .003]}, {"bbox_min_mm": [1., 0., 0.]},
                   {"volume_mm3": float("nan")}):
        with pytest.raises(ValueError):
            g._check_measurements({**good, **change}, spec)


def test_step_unit_header_fails_closed(tmp_path):
    p = tmp_path / "unit.step"
    for text in ("", "LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT($,.METRE.)"):
        p.write_text(text)
        with pytest.raises(ValueError, match="millimeter"):
            g._check_step_units(p)
    p.write_text("LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI.,.METRE.)")
    g._check_step_units(p)


@cad
def test_real_build123d_roundtrip_and_receipt(tmp_path):
    out = tmp_path / "beam"
    r = g.export_beam({}, out)
    assert r["status"] == "GEOMETRY_BENCHMARK_PASS"
    assert r["after_import"]["volume_m3"] == pytest.approx(1.2e-5)
    assert r["after_import"]["bbox_max_mm"] == pytest.approx([200., 20., 3.])
    assert r["before_export"] == r["after_import"]
    assert r["source"]["adapter_sha256"] == hashlib.sha256(Path(g.__file__).read_bytes()).hexdigest()
    assert r["reproducibility"]["byte_repeat_test"] == "NOT_RUN_BY_THIS_INVOCATION"
    assert r["scientific_acceptance"] == "NOT_EVALUATED"
    assert g.verify_artifacts(out) == r
    with pytest.raises(ValueError, match="must not exist"):
        g.export_beam({}, out)


@cad
def test_repeated_step_bytes_and_parameter_change(tmp_path):
    a = g.export_beam({}, tmp_path / "a")
    b = g.export_beam({}, tmp_path / "b")
    changed = g.export_beam({"length_m": .3}, tmp_path / "changed")
    assert a["step_sha256"] == b["step_sha256"]
    assert (tmp_path / "a" / "beam.step").read_bytes() == (tmp_path / "b" / "beam.step").read_bytes()
    assert a["parameter_sha256"] == b["parameter_sha256"]
    assert a["step_sha256"] != changed["step_sha256"]
    assert a["parameter_sha256"] != changed["parameter_sha256"]
    assert changed["after_import"]["volume_mm3"] == pytest.approx(18000.)


@cad
@cq
def test_cadquery_step_compatibility(tmp_path):
    r = g.export_beam({}, tmp_path / "compatibility", cadquery_compatibility=True)
    assert r["cadquery_compatibility"]["status"] == "PASS"
    assert r["cadquery_compatibility"]["measurements"] == r["after_import"]


@cad
def test_failed_export_preserves_diagnostics_without_pass(monkeypatch, tmp_path):
    backend = g._load_build123d()
    monkeypatch.setattr(backend, "export_step", lambda *args, **kwargs: False)
    out = tmp_path / "failed"
    with pytest.raises(RuntimeError, match="export"):
        g.export_beam({}, out)
    failure = json.loads((out / "failure.json").read_text())
    assert failure["status"] == "FAILED" and failure["phase"] == "STEP_EXPORT"
    assert not (out / "receipt.json").exists()
    assert not (out / "manifest.json").exists()


@cad
def test_manifest_requires_complete_regular_unchanged_files(tmp_path):
    out = tmp_path / "case"; g.export_beam({}, out)
    original = (out / "manifest.json").read_text()
    for bad in ({}, [], {"schema_version": "1", "hash_algorithm": "sha256", "artifacts": {}}):
        (out / "manifest.json").write_text(json.dumps(bad))
        with pytest.raises(ValueError):
            g.verify_artifacts(out)
    (out / "manifest.json").write_text(original)
    step = (out / "beam.step").read_bytes()
    (out / "beam.step").write_bytes(step + b"changed")
    with pytest.raises(ValueError, match="integrity"):
        g.verify_artifacts(out)
    (out / "beam.step").write_bytes(step)
    other = tmp_path / "outside.step"; other.write_bytes(step)
    (out / "beam.step").unlink(); (out / "beam.step").symlink_to(other)
    with pytest.raises(ValueError, match="regular"):
        g.verify_artifacts(out)


@cad
def test_rehashed_inconsistent_receipt_units_are_rejected(tmp_path):
    out = tmp_path / "case"; g.export_beam({}, out)
    r = json.loads((out / "receipt.json").read_text())
    r["units"]["parameters"] = "mm"
    (out / "receipt.json").write_bytes(g.canonical_bytes(r))
    manifest = json.loads((out / "manifest.json").read_text())
    data = (out / "receipt.json").read_bytes()
    manifest["artifacts"]["receipt.json"] = {"sha256": g.sha256(data), "bytes": len(data)}
    (out / "manifest.json").write_bytes(g.canonical_bytes(manifest))
    with pytest.raises(ValueError, match="unit contract"):
        g.verify_artifacts(out)


@cad
@pytest.mark.parametrize("filename", ["receipt.json", "manifest.json"])
def test_publication_failure_never_leaves_authoritative_pass(monkeypatch, tmp_path, filename):
    original = Path.replace
    def fail_publish(self, target):
        if Path(target).name == filename:
            raise OSError("synthetic publication failure")
        return original(self, target)
    monkeypatch.setattr(Path, "replace", fail_publish)
    out = tmp_path / "failed-publish"
    with pytest.raises(OSError, match="publication failure"):
        g.export_beam({}, out)
    assert not (out / "receipt.json").exists()
    assert not (out / "manifest.json").exists()
    failure = json.loads((out / "failure.json").read_text())
    assert failure["status"] == "FAILED" and failure["phase"] == "ARTIFACT_PACK_PUBLICATION"
