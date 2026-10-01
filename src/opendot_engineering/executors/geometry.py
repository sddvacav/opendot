"""Optional build123d geometry adapter; no scheduler, solver or device owner.

Input lengths are meters. Modeling and STEP exchange explicitly use millimeters.
Importing this module needs only the Python standard library.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import importlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import re
import subprocess

RECIPE = "geometry.synthetic_beam.v1"
TESTED_BUILD123D = "0.10.0"
TESTED_OCP = "7.8.1.1.post1"
STEP_TIMESTAMP = "2000-01-01T00:00:00"
UNITS = {"parameters": "m", "cad": "mm", "step": "mm", "volume": "m3"}
REQUIRED_ARTIFACTS = frozenset({"beam.step", "parameters.json", "environment.json", "receipt.json"})
DEPENDENCIES = ("build123d", "cadquery-ocp", "numpy", "vtk", "typing_extensions",
                "svgpathtools", "anytree", "ezdxf", "ipython", "lib3mf", "ocpsvg",
                "ocp_gordon", "trianglesolver", "sympy", "scipy", "webcolors")
LIMITATIONS = [
    "Geometry-only synthetic rectangular beam; no material, mesh, loads or solver",
    "No scientific, manufacturing, physical-device or safety acceptance",
    "Round-trip readers share Open CASCADE; they are not independent kernels",
    "Fixed STEP metadata timestamp is not the actual execution time",
    "Same-environment byte determinism is tested, not promised across releases or platforms",
    "Dependency inventory is not a complete native-library SBOM or redistribution clearance",
    "No scheduling, sandboxing, cancellation or remote runtime is implemented here",
]


def canonical_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def sha256(data):
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class BeamGeometry:
    length_m: float = 0.2
    width_m: float = 0.02
    thickness_m: float = 0.003

    def validate(self):
        bounds = {"length_m": (0.05, 0.5), "width_m": (0.005, 0.05), "thickness_m": (0.001, 0.01)}
        for name, value in asdict(self).items():
            try:
                finite = not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)
            except OverflowError:
                finite = False
            if not finite:
                raise ValueError(f"{name}: finite numeric meters required")
            low, high = bounds[name]
            if not low <= value <= high:
                raise ValueError(f"{name}: supported bounds are {low} to {high} m")

    @classmethod
    def from_parameters(cls, parameters):
        if not isinstance(parameters, dict) or set(parameters) - set(cls.__dataclass_fields__):
            raise ValueError("Only length_m, width_m and thickness_m parameters are supported")
        spec = cls(**parameters)
        spec.validate()
        return cls(**{key: float(value) for key, value in asdict(spec).items()})

    @property
    def dimensions_mm(self):
        return tuple(value * 1000 for value in (self.length_m, self.width_m, self.thickness_m))

    @property
    def volume_m3(self):
        return self.length_m * self.width_m * self.thickness_m


def _load_build123d():
    try:
        module = importlib.import_module("build123d")
    except ImportError as exc:
        raise RuntimeError("Optional geometry dependency unavailable; install build123d==0.10.0 in a separate CAD environment") from exc
    version = importlib.metadata.version("build123d")
    if version != TESTED_BUILD123D:
        raise RuntimeError(f"build123d {version} is not the tested adapter version {TESTED_BUILD123D}")
    ocp_version = importlib.metadata.version("cadquery-ocp")
    if ocp_version != TESTED_OCP:
        raise RuntimeError(f"cadquery-ocp {ocp_version} is not the tested adapter version {TESTED_OCP}; use a separate CAD environment")
    return module


def _environment(cadquery_compatibility):
    packages = {}
    for name in DEPENDENCIES + (("cadquery",) if cadquery_compatibility else ()):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    return {"python": platform.python_version(), "platform": platform.system(),
            "machine": platform.machine(), "packages": packages,
            "scope": "build123d direct dependencies plus OCP/VTK and optional CadQuery; not a complete transitive SBOM"}


def _source_provenance(source_path=None):
    """Hash this adapter; add verified local Git context, never a worktree path.

    Membership is not upstream authentication. A modified tracked source may
    record its base commit and dirty state, not a claim that HEAD has its bytes.
    """
    source = Path(__file__ if source_path is None else source_path).resolve()
    result = {"adapter_sha256": sha256(source.read_bytes()), "repository_commit": None,
              "repository_dirty": None, "worktree": None, "revision_status": "UNAVAILABLE"}
    # A broken nearer marker must not let discovery fall through to an ancestor.
    root = next((p for p in source.parents if os.path.lexists(p / ".git")), None)
    if root is not None:
        result["revision_status"] = "GIT_UNVERIFIED_SOURCE_HASH_RECORDED"
        try:
            env = {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}
            env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_SYSTEM=os.devnull,
                       GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0",
                       GIT_OPTIONAL_LOCKS="0", GIT_NO_REPLACE_OBJECTS="1")

            def git(*args):
                return subprocess.run(["git", "--no-pager", "--literal-pathspecs",
                                       "-c", f"core.hooksPath={os.devnull}",
                                       "-c", "core.fsmonitor=false", "-c", "submodule.recurse=false",
                                       *args], cwd=root, env=env, stdin=subprocess.DEVNULL,
                                      capture_output=True, timeout=5, check=True).stdout

            top = git("rev-parse", "--show-toplevel").removesuffix(b"\n")
            if Path(os.fsdecode(top)).resolve() != root:
                return result
            commit = git("rev-parse", "--verify", "HEAD^{commit}").strip().decode("ascii")
            if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", commit):
                return result
            relative = source.relative_to(root).as_posix()
            name = os.fsencode(relative)
            index = git("ls-files", "--stage", "-z", "--", relative).split(b"\0")
            tree = git("ls-tree", "-z", "--full-tree", commit, "--", relative).split(b"\0")
            # Require exactly one stage-zero regular file in both index and HEAD.
            if len(index) != 2 or index[-1] or len(tree) != 2 or tree[-1]:
                return result
            index_meta, index_name = index[0].split(b"\t", 1)
            tree_meta, tree_name = tree[0].split(b"\t", 1)
            index_mode, index_oid, stage = index_meta.split()
            tree_mode, kind, tree_oid = tree_meta.split()
            if (index_name != name or tree_name != name or stage != b"0" or kind != b"blob"
                    or index_mode not in (b"100644", b"100755") or tree_mode not in (b"100644", b"100755")):
                return result
            # Status may execute repository-local clean/process filters. Do not
            # run those commands or guess their effect on the worktree state.
            for entry in git("config", "--null", "--list").split(b"\0"):
                key, _, value = entry.partition(b"\n")
                if re.fullmatch(rb"filter\..*\.(clean|process)", key) and value.strip():
                    return result
            # Git can hide edits behind assume-unchanged/skip-worktree bits or
            # normalize them with attributes. Never call different raw adapter
            # bytes clean just because status does; normalization is conservative.
            source_changed = (index_mode != tree_mode or index_oid != tree_oid or
                              sha256(git("cat-file", "blob", tree_oid.decode("ascii"))) != result["adapter_sha256"])
            dirty = bool(git("status", "--porcelain=v1", "-z", "--untracked-files=normal", "--ignore-submodules=all")) or source_changed
            if git("rev-parse", "--verify", "HEAD^{commit}").strip().decode("ascii") != commit:
                return result
            if sha256(source.read_bytes()) != result["adapter_sha256"]:
                return result
            result.update(repository_commit=commit, repository_dirty=dirty,
                          revision_status="RECORDED_WITH_WORKTREE_STATE")
        except (OSError, ValueError, UnicodeError, subprocess.SubprocessError):
            result["revision_status"] = "GIT_UNAVAILABLE_SOURCE_HASH_RECORDED"
    return result


def _measure_build123d(shape):
    box = shape.bounding_box()
    return {"valid": bool(shape.is_valid), "solids": len(shape.solids()),
            "faces": len(shape.faces()), "edges": len(shape.edges()), "vertices": len(shape.vertices()),
            "volume_mm3": float(shape.volume),
            "bbox_min_mm": list(box.min), "bbox_max_mm": list(box.max)}


def _check_measurements(measurement, spec):
    if not measurement["valid"] or any(measurement[k] != n for k, n in (("solids", 1), ("faces", 6), ("edges", 12), ("vertices", 8))):
        raise ValueError("Geometry validity or rectangular-beam topology check failed")
    numbers = [measurement["volume_mm3"], *measurement["bbox_min_mm"], *measurement["bbox_max_mm"]]
    if len(numbers) != 7 or not all(math.isfinite(v) for v in numbers):
        raise ValueError("Non-finite or malformed geometry measurements")
    if not math.isclose(measurement["volume_mm3"], spec.volume_m3 * 1e9, rel_tol=1e-9, abs_tol=1e-8):
        raise ValueError("CAD/STEP volume does not match SI-to-mm conversion")
    expected = (0., 0., 0., *spec.dimensions_mm)
    actual = (*measurement["bbox_min_mm"], *measurement["bbox_max_mm"])
    if any(not math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-7) for a, b in zip(actual, expected)):
        raise ValueError("CAD/STEP bounds do not match SI-to-mm conversion")
    return {**measurement, "volume_m3": measurement["volume_mm3"] / 1e9}


def _check_step_units(path):
    text = Path(path).read_text(encoding="utf-8")
    units = re.findall(r"LENGTH_UNIT\(\)\s+NAMED_UNIT\(\*\)\s+SI_UNIT\(\s*([^)]*)\)", text)
    if not units or any(re.sub(r"\s+", "", unit) != ".MILLI.,.METRE." for unit in units):
        raise ValueError("STEP must explicitly declare millimeter length units")


def _measure_cadquery(path, cq):
    shape = cq.importers.importStep(str(path)).val()
    box = shape.BoundingBox()
    return {"valid": bool(shape.isValid()), "solids": len(shape.Solids()),
            "faces": len(shape.Faces()), "edges": len(shape.Edges()), "vertices": len(shape.Vertices()),
            "volume_mm3": float(shape.Volume()), "bbox_min_mm": [box.xmin, box.ymin, box.zmin],
            "bbox_max_mm": [box.xmax, box.ymax, box.zmax]}


def _new_output_directory(path):
    out = Path(path).expanduser().absolute()
    if out.exists() or out.is_symlink():
        raise ValueError("Output directory must not exist; existing work is never overwritten")
    if any(parent.is_symlink() for parent in out.parents):
        raise ValueError("Symlink output parents are not supported")
    out.mkdir(parents=True, exist_ok=False, mode=0o700)
    return out


def export_beam(parameters, output_dir, *, cadquery_compatibility=False):
    """Build a bounded beam, check STEP roundtrip, and write a geometry receipt.

    Fixed filenames only. No executable paths, expressions, model source or input
    files are accepted in parameters. The caller owns runtime isolation/budgets.
    """
    spec = BeamGeometry.from_parameters(parameters)
    if not isinstance(cadquery_compatibility, bool):
        raise ValueError("cadquery_compatibility must be boolean")
    b = _load_build123d()
    cq = None
    if cadquery_compatibility:
        try:
            cq = importlib.import_module("cadquery")
        except ImportError as exc:
            raise RuntimeError("Requested optional CadQuery STEP compatibility reader is unavailable") from exc
    source = _source_provenance(__file__)
    environment = _environment(cadquery_compatibility)
    parameter_record = {"schema_version": "1", "recipe": RECIPE, "parameters": asdict(spec), "units": UNITS}
    out = _new_output_directory(output_dir)
    phase = "PARAMETERS_WRITE"
    try:
        (out / "parameters.json").write_bytes(canonical_bytes(parameter_record))
        (out / "environment.json").write_bytes(canonical_bytes(environment))
        phase = "CAD_BUILD"
        shape = b.Box(*spec.dimensions_mm, align=(b.Align.MIN, b.Align.MIN, b.Align.MIN))
        shape.label = "OpenDot synthetic beam"
        original = _check_measurements(_measure_build123d(shape), spec)
        phase = "STEP_EXPORT"
        step = out / "beam.step"
        if b.export_step(shape, step, unit=b.Unit.MM, timestamp=STEP_TIMESTAMP) is not True:
            raise RuntimeError("build123d STEP export did not report success")
        _check_step_units(step)
        phase = "STEP_ROUNDTRIP"
        reopened = _check_measurements(_measure_build123d(b.import_step(step)), spec)
        compatibility = {"status": "NOT_REQUESTED"}
        if cq is not None:
            phase = "CADQUERY_COMPATIBILITY"
            compatibility = {"status": "PASS", "measurements": _check_measurements(_measure_cadquery(step, cq), spec)}
        receipt = {"schema_version": "1", "recipe": RECIPE, "status": "GEOMETRY_BENCHMARK_PASS",
                   "execution_time_utc": datetime.now(timezone.utc).isoformat(), "source": source,
                   "parameter_sha256": sha256((out / "parameters.json").read_bytes()),
                   "environment_sha256": sha256((out / "environment.json").read_bytes()),
                   "step_sha256": sha256(step.read_bytes()), "units": UNITS,
                   "expected_volume_m3": spec.volume_m3, "before_export": original, "after_import": reopened,
                   "cadquery_compatibility": compatibility,
                   "verification": {"finite_bounded_parameters": True, "single_valid_solid": True,
                                    "rectangular_topology": True, "step_mm_header": True,
                                    "analytic_volume_match": True, "analytic_bounds_match": True,
                                    "geometric_roundtrip": "PASS"},
                   "reproducibility": {"step_metadata_timestamp": STEP_TIMESTAMP,
                                       "timestamp_purpose": "Deterministic file metadata, not execution time",
                                       "byte_repeat_test": "NOT_RUN_BY_THIS_INVOCATION",
                                       "cross_version_byte_stability": "NOT_CLAIMED"},
                   "scientific_acceptance": "NOT_EVALUATED", "physical_validation": "NOT_PERFORMED",
                   "limitations": LIMITATIONS}
        phase = "RECEIPT_WRITE"
        receipt_bytes = canonical_bytes(receipt)
        receipt_pending = out / ".receipt.json.pending"
        receipt_pending.write_bytes(receipt_bytes)
        manifest = {"schema_version": "1", "hash_algorithm": "sha256", "artifacts": {
            name: {"sha256": sha256(receipt_bytes if name == "receipt.json" else (out / name).read_bytes()),
                   "bytes": len(receipt_bytes) if name == "receipt.json" else (out / name).stat().st_size}
            for name in sorted(REQUIRED_ARTIFACTS)}}
        phase = "MANIFEST_WRITE"
        manifest_pending = out / ".manifest.json.pending"
        manifest_pending.write_bytes(canonical_bytes(manifest))
        phase = "ARTIFACT_PACK_PUBLICATION"
        # Publish the authoritative PASS receipt last. A crash before this point
        # can leave diagnostics/incomplete files, but no completed PASS receipt.
        manifest_pending.replace(out / "manifest.json")
        receipt_pending.replace(out / "receipt.json")
        return receipt
    except Exception as exc:
        # Preserve failed artifacts for diagnosis; never fabricate a passing receipt.
        failure = {"schema_version": "1", "status": "FAILED", "phase": phase,
                   "error_type": type(exc).__name__, "message": str(exc), "source": source}
        try:
            (out / "receipt.json").unlink(missing_ok=True)
            (out / "manifest.json").unlink(missing_ok=True)
            (out / "failure.json").write_bytes(canonical_bytes(failure))
        except OSError:
            pass
        raise


def verify_artifacts(directory):
    """Verify local receipt bindings, not signature/authenticity or geometry anew."""
    root = Path(directory)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Artifact directory must be a real directory")
    manifest_file = root / "manifest.json"
    if manifest_file.is_symlink() or not manifest_file.is_file():
        raise ValueError("Missing or invalid artifact manifest")
    manifest = json.loads(manifest_file.read_text())
    if not isinstance(manifest, dict) or manifest.get("schema_version") != "1" or manifest.get("hash_algorithm") != "sha256":
        raise ValueError("Unsupported artifact manifest schema")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != REQUIRED_ARTIFACTS:
        raise ValueError("Missing or unexpected artifact manifest entries")
    for name, expected in artifacts.items():
        path = root / name
        if path.is_symlink() or not path.is_file() or path.resolve().parent != root.resolve():
            raise ValueError("Artifact must be a regular local file")
        if not isinstance(expected, dict) or not isinstance(expected.get("sha256"), str) or not re.fullmatch(r"[a-f0-9]{64}", expected["sha256"]):
            raise ValueError("Invalid artifact digest")
        data = path.read_bytes()
        if expected.get("bytes") != len(data) or expected["sha256"] != sha256(data):
            raise ValueError(f"Artifact integrity failed: {name}")
    receipt = json.loads((root / "receipt.json").read_text())
    if not isinstance(receipt, dict) or receipt.get("schema_version") != "1" or receipt.get("recipe") != RECIPE or receipt.get("status") != "GEOMETRY_BENCHMARK_PASS":
        raise ValueError("Invalid geometry receipt")
    for field, name in (("parameter_sha256", "parameters.json"), ("environment_sha256", "environment.json"), ("step_sha256", "beam.step")):
        if receipt.get(field) != artifacts[name]["sha256"]:
            raise ValueError(f"Receipt binding mismatch: {field}")
    parameters = json.loads((root / "parameters.json").read_text())
    environment = json.loads((root / "environment.json").read_text())
    if not isinstance(parameters, dict) or set(parameters) != {"schema_version", "recipe", "parameters", "units"} or parameters.get("schema_version") != "1" or parameters.get("recipe") != RECIPE:
        raise ValueError("Invalid parameter artifact contract")
    if parameters.get("units") != UNITS or receipt.get("units") != UNITS:
        raise ValueError("Inconsistent parameter/receipt unit contract")
    spec = BeamGeometry.from_parameters(parameters["parameters"])
    if not isinstance(environment, dict) or not isinstance(environment.get("packages"), dict) or environment["packages"].get("build123d") != TESTED_BUILD123D or environment["packages"].get("cadquery-ocp") != TESTED_OCP:
        raise ValueError("Unverified CAD dependency versions in receipt environment")
    if not isinstance(receipt.get("source"), dict) or not isinstance(receipt["source"].get("adapter_sha256"), str) or not re.fullmatch(r"[a-f0-9]{64}", receipt["source"]["adapter_sha256"]):
        raise ValueError("Missing or invalid adapter source digest")
    try:
        _check_measurements(receipt["before_export"], spec)
        _check_measurements(receipt["after_import"], spec)
    except (KeyError, TypeError) as exc:
        raise ValueError("Malformed receipt geometry measurements") from exc
    if receipt.get("scientific_acceptance") != "NOT_EVALUATED" or receipt.get("physical_validation") != "NOT_PERFORMED":
        raise ValueError("Unsupported scientific or physical acceptance claim")
    return receipt


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="Optional geometry-only synthetic beam STEP benchmark")
    parser.add_argument("output", type=Path, help="New output directory, preferably outside the source checkout")
    parser.add_argument("--length-m", type=float, default=0.2)
    parser.add_argument("--width-m", type=float, default=0.02)
    parser.add_argument("--thickness-m", type=float, default=0.003)
    parser.add_argument("--cadquery-compatibility", action="store_true")
    args = parser.parse_args(argv)
    report = export_beam({"length_m": args.length_m, "width_m": args.width_m, "thickness_m": args.thickness_m},
                         args.output, cadquery_compatibility=args.cadquery_compatibility)
    print(json.dumps({"status": report["status"], "step_sha256": report["step_sha256"], "output": str(args.output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
