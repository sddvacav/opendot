"""Fabricated full-contract flow only. No CAD, Gmsh, solver or native identity probe.

Existing adapter bodies and all acceptance verifiers run unchanged. Only their
native boundaries and source-context queries are replaced with explicit fixtures.
These records are not genuine native execution evidence.
"""
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

from opendot_engineering.executors import geometry as g, gmsh_mesh as m
from opendot_engineering.executors import thermal_conduction as t
import test_solver_version_identity as fixtures
from test_gmsh_mesh import runtime_identity

PATH = Path(__file__).resolve().parents[1] / "examples/cad_cae/thermal_workflow.py"
spec = importlib.util.spec_from_file_location("cad_thermal_workflow", PATH)
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)


def write(path, value):
    path.write_bytes(g.canonical_bytes(value))


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


@pytest.fixture
def fabricated_native_boundaries(monkeypatch, tmp_path, runtime_identity):
    events = []
    state = {"fail": None}
    monkeypatch.setattr(w, "cad_versions", lambda: dict(w.REQUIRED_CAD))
    monkeypatch.setattr(g, "_source_provenance", lambda *a: {"adapter_sha256": "a" * 64})
    monkeypatch.setattr(g, "_environment", lambda *a: {"packages": dict(w.REQUIRED_CAD),
                                                    "scope": "FABRICATED TEST METADATA"})
    monkeypatch.setattr(m, "_source", lambda: {"adapter_sha256": "a" * 64, "worker_sha256": "b" * 64})

    def enter(stage):
        events.append(stage)
        if state["fail"] == stage:
            raise ValueError("fabricated " + stage + " failure")

    class Box:
        def __init__(self, *dims, align):
            enter("cad")
            assert dims == (200., 20., 3.)
            self.is_valid = True
            self.volume = 12000.

        def bounding_box(self):
            return SimpleNamespace(min=(0., 0., 0.), max=(200., 20., 3.))

        def solids(self): return [None]
        def faces(self): return [None] * 6
        def edges(self): return [None] * 12
        def vertices(self): return [None] * 8

    shape = object.__new__(Box)
    shape.is_valid, shape.volume = True, 12000.

    def export(shape, path, *, unit, timestamp):
        assert unit == "MM" and timestamp == g.STEP_TIMESTAMP
        path.write_text("/* FABRICATED TEST STEP; NO CAD EXECUTED */\n"
                        "LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI.,.METRE.);\n")
        return True

    backend = SimpleNamespace(Box=Box, Align=SimpleNamespace(MIN="MIN"),
        Unit=SimpleNamespace(MM="MM"), export_step=export, import_step=lambda p: shape)
    monkeypatch.setattr(g, "_load_build123d", lambda: backend)

    def gmsh_boundary(command, **kwargs):
        enter("mesh")
        out = Path(command[-1])
        assert kwargs["timeout"] == 60 and command[0] == sys.executable
        fixture_root = tmp_path / "FABRICATED_GRID"
        fixtures._synthetic_mesh(fixture_root, out.parent / "cad")
        shutil.copyfile(fixture_root / "beam.msh", out / "beam.msh")
        worker = json.loads((fixture_root / "worker.json").read_bytes())
        worker["gmsh_runtime"] = runtime_identity
        write(out / "worker.json", worker)
        recipe = json.loads((out / "recipe.json").read_bytes())
        assert recipe["divisions"] == [20, 4, 2]
        recipe["gmsh_runtime"] = runtime_identity
        write(out / "recipe.json", recipe)
        kwargs["stdout"].write(b"FABRICATED TEST: NO GMSH OR NATIVE IDENTITY PROBE\n")

    def solver_boundary(executable, out, timeout):
        enter("solver")
        assert executable == str(Path(sys.executable).resolve()) and timeout == 60
        nodes, cells, ends = t.mesh_data(out / "mesh/beam.msh")
        fixtures._write_raw(out, "thermal", fixtures._synthetic_data(nodes, cells, ends, "thermal"))

    monkeypatch.setattr(m.subprocess, "run", gmsh_boundary)
    monkeypatch.setattr(t, "_execute", solver_boundary)
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: pytest.fail("Native launch forbidden"))
    return events, state


@pytest.fixture
def workflow_pack(tmp_path, fabricated_native_boundaries):
    root = tmp_path / "FABRICATED_WORKFLOW_NOT_NATIVE_EVIDENCE"
    result = w.run(root, gmsh_python=sys.executable, solver=sys.executable)
    assert fabricated_native_boundaries[0] == ["cad", "mesh", "solver"]
    return root, result


def test_complete_fabricated_flow_uses_real_canonical_verifiers_and_analytical_case(workflow_pack):
    root, result = workflow_pack
    assert result["status"] == "RECORDED_WORKFLOW_CONSISTENCY_PASS"
    assert result["native_execution"] == "NOT_ESTABLISHED_BY_READ_ONLY_VERIFICATION"
    assert all(result[key] == value for key, value in w.FLAGS.items())
    assert result["recorded_mesh_native_identity"] == "VERIFIED_AT_EXECUTION"
    assert len(result["artifact_sha256"]["thermal"]) == len(t.FILES) + 1
    data = t.parse_dat(root / "thermal/thermal.dat")
    nodes, cells, ends = t.mesh_data(root / "mesh/beam.msh")
    # Independent closed-form constants: no expected value comes from plan/oracle.
    length, width, height, k, delta = map(Decimal, ("0.2", "0.02", "0.003", "10", "100"))
    flux = -k * delta / length
    power = -flux * width * height
    assert flux == Decimal("-5000") and power == Decimal("0.3")
    assert length * width * height == Decimal("0.000012")
    assert (len(nodes), len(cells), len(data["flux"])) == (315, 160, 1280)
    for n, xyz in nodes.items():
        expected = Decimal("300") + delta * Decimal(str(xyz[0])) / length
        assert abs(Decimal(str(data["temperature"][n][0])) - expected) <= Decimal("0.0001")
    assert set(data["flux"].values()) == {(float(flux), 0., 0.)}
    for side, sign in (("X_MIN", -1), ("X_MAX", 1)):
        actual = sum(Decimal(str(data["reaction"][n][0])) for n in ends[side])
        assert abs(actual - sign * power) <= Decimal("0.0000001")
    assert "FABRICATED" in (root / "cad/beam.step").read_text()
    assert "SYNTHETIC FIXTURE" in (root / "thermal/solver.log").read_text()


def test_verify_is_read_only_and_launch_free(workflow_pack, monkeypatch, capsys):
    root, expected = workflow_pack
    before = snapshot(root)
    for owner, name in ((g, "export_beam"), (m, "mesh_beam"), (t, "run_thermal")):
        monkeypatch.setattr(owner, name, lambda *a, **k: pytest.fail("Creation forbidden during verify"))
    monkeypatch.setattr(g, "_load_build123d", lambda: pytest.fail("CAD import forbidden"))
    assert w.verify(root) == expected
    w.main(["verify", str(root)])
    assert json.loads(capsys.readouterr().out) == expected
    assert snapshot(root) == before


def test_plan_is_metadata_only_and_explicit_not_executed(monkeypatch, capsys):
    monkeypatch.setattr(w, "cad_versions", lambda: {name: None for name in w.REQUIRED_CAD})
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: pytest.fail("No plan launch"))
    w.main(["plan"])
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "NOT_EXECUTED"
    assert report["observed_metadata_only"]["gmsh_native"] == "NOT_CHECKED"
    assert report["observed_metadata_only"]["solver"] == "NOT_CHECKED"
    assert report["resources"]["cad"]["wall_timeout"] == "NOT_PROVIDED"
    assert report["resources"]["cad"]["cpu_limit"] == "NOT_PROVIDED"
    assert report["resources"]["retries"] == 0
    assert report["expected"]["boundary_quad4"] == 256
    assert all(name not in sys.modules for name in ("build123d", "gmsh", "OCP"))


@pytest.mark.parametrize("stage", ["cad", "mesh", "solver"])
def test_first_failure_stops_dependent_dispatch_without_retry(tmp_path, fabricated_native_boundaries, stage):
    events, state = fabricated_native_boundaries
    state["fail"] = stage
    out = tmp_path / "failed"
    with pytest.raises(ValueError, match="fabricated"):
        w.run(out, gmsh_python=sys.executable, solver=sys.executable)
    assert events == ["cad", "mesh", "solver"][:["cad", "mesh", "solver"].index(stage) + 1]
    failed = out / {"cad": "cad", "mesh": "mesh", "solver": "thermal"}[stage]
    assert (failed / "failure.json").is_file()
    assert not (failed / "receipt.json").exists()
    if stage == "cad": assert not (out / "mesh").exists()
    if stage == "mesh": assert not (out / "thermal").exists()
    with pytest.raises(ValueError): w.verify(out)


def test_existing_output_preserved_before_dispatch(workflow_pack, fabricated_native_boundaries):
    root, _ = workflow_pack
    before = snapshot(root)
    events = list(fabricated_native_boundaries[0])
    with pytest.raises(ValueError, match="must not exist"):
        w.run(root, gmsh_python=sys.executable, solver=sys.executable)
    assert snapshot(root) == before and fabricated_native_boundaries[0] == events


@pytest.mark.parametrize("mode", ["relative-gmsh", "relative-solver", "missing-gmsh", "missing-solver", "cad-metadata"])
def test_missing_or_implicit_environment_refuses_before_output(tmp_path, fabricated_native_boundaries, monkeypatch, mode):
    gmsh, solver = sys.executable, sys.executable
    if mode == "relative-gmsh": gmsh = "python"
    if mode == "relative-solver": solver = "ccx"
    if mode == "missing-gmsh": gmsh = "/nonexistent/gmsh-python"
    if mode == "missing-solver": solver = "/nonexistent/ccx"
    if mode == "cad-metadata": monkeypatch.setattr(w, "cad_versions", lambda: {})
    out = tmp_path / "unused"
    with pytest.raises(ValueError): w.run(out, gmsh_python=gmsh, solver=solver)
    assert not out.exists() and fabricated_native_boundaries[0] == []


@pytest.mark.parametrize("mode", ["deck-410K", "wrong-flux", "missing-cvg", "nonconverged-cvg"])
def test_resealed_thermal_semantic_failures_are_not_hash_passes(workflow_pack, mode):
    root, _ = workflow_pack
    thermal = root / "thermal"
    if mode == "deck-410K":
        p = thermal / "thermal.inp"
        p.write_text(p.read_text().replace("X_MAX,11,11,400.", "X_MAX,11,11,410."))
    elif mode == "wrong-flux":
        p = thermal / "thermal.dat"
        p.write_text(p.read_text().replace("-5000 0 0", "-4000 0 0", 1))
    else:
        (thermal / "thermal.cvg").write_text("" if mode == "missing-cvg" else "1 1 1 1 0 0 0 0 1\n")
    fixtures._reseal(thermal, t)
    with pytest.raises(ValueError): w.verify(root)


@pytest.mark.parametrize("mode", ["millimeters-as-meters", "reversed-hex", "missing-face"])
def test_resealed_mesh_semantic_failures_are_rejected(workflow_pack, mode):
    root, _ = workflow_pack
    path = root / "mesh/beam.msh"
    lines = path.read_text().splitlines()
    if mode == "millimeters-as-meters":
        start, end = lines.index("$Nodes") + 2, lines.index("$EndNodes")
        for index in range(start, end):
            fields = lines[index].split()
            lines[index] = fields[0] + " " + " ".join(str(float(v) * 1000) for v in fields[1:])
    elif mode == "reversed-hex":
        index = lines.index("$Elements") + 2
        fields = lines[index].split()
        fields[5], fields[6] = fields[6], fields[5]
        lines[index] = " ".join(fields)
    else:
        index = lines.index("$Elements") + 1
        lines[index] = str(int(lines[index]) - 1)
        del lines[lines.index("$EndElements") - 1]
    path.write_text("\n".join(lines) + "\n")
    fixtures._reseal(root / "mesh", m)
    with pytest.raises(ValueError): w.verify(root)


@pytest.mark.parametrize("stage", ["cad", "mesh"])
def test_individually_valid_unrelated_pack_fails_lineage(workflow_pack, stage):
    root, _ = workflow_pack
    if stage == "cad":
        receipt = json.loads((root / "cad/receipt.json").read_bytes())
        receipt["source"]["adapter_sha256"] = "f" * 64
        write(root / "cad/receipt.json", receipt)
        manifest = json.loads((root / "cad/manifest.json").read_bytes())
        raw = (root / "cad/receipt.json").read_bytes()
        manifest["artifacts"]["receipt.json"] = {"sha256": g.sha256(raw), "bytes": len(raw)}
        write(root / "cad/manifest.json", manifest)
        g.verify_artifacts(root / "cad")
    else:
        (root / "mesh/process.log").write_text("ANOTHER FABRICATED BUT INDIVIDUALLY VALID PACK\n")
        fixtures._reseal(root / "mesh", m)
        m.verify_mesh_artifacts(root / "mesh", require_native_identity=True)
    with pytest.raises(ValueError, match="lineage"): w.verify(root)


def test_legacy_native_claim_cannot_upgrade_to_workflow(workflow_pack):
    root, _ = workflow_pack
    mesh = root / "mesh"
    for name in ("recipe.json", "receipt.json"):
        value = json.loads((mesh / name).read_bytes())
        value.update(schema_version="1", recipe=m.LEGACY_RECIPE)
        value.pop("gmsh_runtime")
        if name == "receipt.json": value["worker"].pop("gmsh_runtime")
        write(mesh / name, value)
    value = json.loads((mesh / "worker.json").read_bytes())
    value.pop("gmsh_runtime")
    write(mesh / "worker.json", value)
    fixtures._reseal(mesh, m)
    assert m.native_provenance(m.verify_mesh_artifacts(mesh))["status"] == "NOT_VERIFIED"
    with pytest.raises(ValueError, match="Legacy"): w.verify(root)


def test_source_and_symlink_outputs_refused(tmp_path, fabricated_native_boundaries, monkeypatch):
    monkeypatch.setattr(w, "ROOT", tmp_path / "source")
    with pytest.raises(ValueError, match="outside"):
        w.run(w.ROOT / "out", gmsh_python=sys.executable, solver=sys.executable)
    (tmp_path / "real").mkdir()
    (tmp_path / "alias").symlink_to(tmp_path / "real", target_is_directory=True)
    with pytest.raises(ValueError, match="Symlink"):
        w.run(tmp_path / "alias/out", gmsh_python=sys.executable, solver=sys.executable)
    assert fabricated_native_boundaries[0] == []


def test_workflow_summary_is_computed_and_untrusted_saved_summary_ignored(workflow_pack):
    root, expected = workflow_pack
    write(root / "summary.json", {"scientific_accepted": True, "status": "PHYSICALLY_VALIDATED"})
    assert w.verify(root) == expected


@pytest.mark.parametrize("mode", ["duplicate", "nonfinite"])
def test_duplicate_or_nonfinite_recipe_json_refused(workflow_pack, mode):
    root, _ = workflow_pack
    path = root / "mesh/recipe.json"
    if mode == "duplicate":
        path.write_text(path.read_text().replace('"divisions":', '"divisions": [20,4,2], "divisions":', 1))
    else:
        path.write_text(path.read_text().replace('"dimensions_m":', '"nonfinite": NaN, "dimensions_m":', 1))
    fixtures._reseal(root / "mesh", m)
    with pytest.raises(ValueError): w.verify(root)


@pytest.mark.parametrize("stage", ["mesh", "thermal"])
def test_other_valid_timeout_does_not_match_fixed_recipe(workflow_pack, stage):
    root, _ = workflow_pack
    path = root / stage / "receipt.json"
    value = json.loads(path.read_bytes())
    value["timeout_s"] = 120
    write(path, value)
    fixtures._reseal(root / stage, m if stage == "mesh" else t)
    with pytest.raises(ValueError, match="fixed .* timeout"): w.verify(root)


def test_consumer_bounded_reader_refuses_large_file(tmp_path, monkeypatch):
    p = tmp_path / "bounded"
    p.write_bytes(b"12345")
    monkeypatch.setattr(m, "MAX_BYTES", 4)
    with pytest.raises(ValueError, match="INPUT_TOO_LARGE"): w.read_local(p)


def test_symlinked_verification_input_refused(workflow_pack, tmp_path):
    root, _ = workflow_pack
    alias = tmp_path / "alias"
    alias.symlink_to(root, target_is_directory=True)
    with pytest.raises(ValueError): w.verify(alias)
