"""One fixed synthetic CAD → mesh → thermal recipe using the existing owners.

Source-only example, no scheduler, solver, native process wrapper or artifact store.
Plan and verify never import CAD/Gmsh or launch a native process. Run needs an
operator-approved existing native environment; no software is acquired here.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import sys

from opendot_engineering.adapters import source_audit as audit
from opendot_engineering.executors import geometry, gmsh_mesh, thermal_conduction

ROOT = Path(__file__).resolve().parents[2]
RECIPE = "example.cad_mesh_linear_thermal.v1"
PARAMETERS = {"length_m": 0.2, "width_m": 0.02, "thickness_m": 0.003}
DIVISIONS = (20, 4, 2)
TIMEOUT_S = 60
REQUIRED_CAD = {"build123d": "0.10.0", "cadquery-ocp": "7.8.1.1.post1"}
FLAGS = {"scientific_accepted": False, "device_control_authorized": False,
         "physical_validation": "NOT_PERFORMED", "independent_review": "NOT_EVALUATED",
         "mesh_independence": "NOT_ESTABLISHED"}
LIMITATIONS = [
    "Synthetic mathematical case only; no material qualification or physical validation",
    "One exactly representable linear field is not convergence or mesh independence",
    "Verification checks recorded evidence, not native execution authenticity",
    "Linear oracle checks end reaction sums and free nodes, not each constrained-node distribution",
    "CAD runs in process without a wall timeout; two 60-second limits do not bound the whole workflow",
    "No OS memory or aggregate-output cap, crash transaction, hostile-writer or process-tree guarantee",
    "Gmsh v2 native identity normally reads /proc/self/maps; execution requires that explicit scope",
    "Native dependency closure, reproducible install, licensing and scientific review remain unqualified",
    "Native packs can contain local executable/library paths; review before sharing",
]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_local(path):
    """Reuse the canonical bounded, no-symlink source-audit reader."""
    path = Path(path).absolute()
    fd = audit._root_fd(path.parent)
    try:
        return audit._read(fd, path.name, gmsh_mesh.MAX_BYTES)
    finally:
        os.close(fd)


def record(path):
    return audit._decode(read_local(path))


def pins(root, names):
    return {name: audit._sha256(read_local(root / name)) for name in sorted(names)}


def cad_versions():
    observed = {}
    for name in REQUIRED_CAD:
        try:
            observed[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            observed[name] = None
    return observed


def plan():
    """Metadata-only plan, never a native preflight or execution claim."""
    return {"recipe": RECIPE, "status": "NOT_EXECUTED", "parameters_m": dict(PARAMETERS),
            "divisions": list(DIVISIONS), "required_software": {
                "platform": "Linux", "reference_python": "3.12",
                "cad_current_interpreter": dict(REQUIRED_CAD),
                "explicit_gmsh_python": {"gmsh_wrapper": "4.15.2", "gmsh_native": "4.15.2"},
                "explicit_solver": {"CalculiX": "2.23"}},
            "observed_metadata_only": {"python": sys.version.split()[0], "platform": sys.platform,
                "cad_packages": cad_versions(), "gmsh_native": "NOT_CHECKED",
                "solver": "NOT_CHECKED"},
            "operations": ["export_beam once", "mesh_beam once", "run_thermal once",
                           "read-only canonical verification and lineage checks"],
            "resources": {
                "cad": {"wall_timeout": "NOT_PROVIDED", "cpu_limit": "NOT_PROVIDED",
                        "file_size_limit": "NOT_PROVIDED", "thread_policy": "NOT_PROVIDED"},
                "mesh": {"wall_timeout_s": TIMEOUT_S, "configured_threads": 1,
                    "cpu_limit": "minimum of 300 seconds and finite inherited limits",
                    "file_size_limit": "minimum of 32 MiB and finite inherited limits"},
                "solver": {"wall_timeout_s": TIMEOUT_S, "configured_threads": 1,
                    "cpu_limit": "minimum of 300 seconds and finite inherited limits",
                    "file_size_limit_bytes": gmsh_mesh.MAX_BYTES},
                "consumer_read_limit_bytes": gmsh_mesh.MAX_BYTES,
                "memory_limit": "NOT_PROVIDED", "retries": 0},
            "expected": {"nodes": 315, "hex8_cells": 160, "boundary_quad4": 256,
                "flux_integration_points": 1280, "volume_m3": 0.000012,
                "temperature_K": "300 + 500*x_m", "flux_W_m2": [-5000.0, 0.0, 0.0],
                "end_reactions_W": {"X_MIN": -0.3, "X_MAX": 0.3}},
            **FLAGS, "limitations": list(LIMITATIONS)}


def configured_executable(path, label):
    require(isinstance(path, (str, Path)) and bool(str(path)), label + " path required")
    path = Path(path)
    require(path.is_absolute() and path.is_file() and os.access(path, os.X_OK),
            label + " must be an explicit absolute existing executable path")
    return str(path)


def verify_cad(root):
    before = pins(root, geometry.REQUIRED_ARTIFACTS | {"manifest.json"})
    receipt = geometry.verify_artifacts(root)
    require(record(root / "parameters.json")["parameters"] == PARAMETERS,
            "Workflow requires the fixed SI beam parameters")
    require(pins(root, before) == before, "CAD artifacts changed during verification")
    return receipt, before


def verify_mesh(root, cad_root):
    before = pins(root, gmsh_mesh.FILES | {"manifest.json"})
    receipt = gmsh_mesh.verify_mesh_artifacts(root, require_native_identity=True)
    recipe = record(root / "recipe.json")
    require(receipt.get("timeout_s") == TIMEOUT_S, "Workflow requires the fixed mesh timeout")
    require(recipe["divisions"] == list(DIVISIONS), "Workflow requires the fixed 20x4x2 mesh")
    require(recipe["dimensions_m"] == list(PARAMETERS.values()), "Wrong fixed mesh dimensions")
    measured = receipt["measurements"]
    require((measured["nodes"], measured["volume_elements"], measured["boundary_elements"]) ==
            (315, 160, 256), "Wrong fixed mesh counts")
    for dst, src in (("beam.step", "beam.step"), ("cad-receipt.json", "receipt.json"),
                     ("cad-manifest.json", "manifest.json"), ("cad-parameters.json", "parameters.json")):
        require(read_local(root / dst) == read_local(cad_root / src), "CAD to mesh lineage mismatch")
    require(pins(root, before) == before, "Mesh artifacts changed during verification")
    return receipt, before


def verify(directory):
    """Read raw canonical packs and exact lineage; never trust a saved summary."""
    root = Path(directory).absolute()
    cad, cad_pins = verify_cad(root / "cad")
    mesh, mesh_pins = verify_mesh(root / "mesh", root / "cad")
    thermal_root = root / "thermal"
    thermal_pins = pins(thermal_root, thermal_conduction.FILES | {"manifest.json"})
    thermal = thermal_conduction.verify_thermal_artifacts(thermal_root)
    require(thermal["recipe"] == thermal_conduction.RECIPE,
            "Workflow requires the fixed linear conduction recipe")
    require(thermal["timeout_s"] == TIMEOUT_S, "Workflow requires the fixed solver timeout")
    for name in gmsh_mesh.FILES | {"manifest.json"}:
        require(read_local(thermal_root / "mesh" / name) == read_local(root / "mesh" / name),
                "Mesh to thermal lineage mismatch")
    oracle = record(thermal_root / "oracle.json")
    require((oracle["nodes"], oracle["elements"], oracle["integration_points"]) == (315, 160, 1280),
            "Wrong thermal result counts")
    require(pins(root / "cad", cad_pins) == cad_pins and
            pins(root / "mesh", mesh_pins) == mesh_pins and
            pins(thermal_root, thermal_pins) == thermal_pins,
            "Workflow artifacts changed during verification")
    return {"recipe": RECIPE, "status": "RECORDED_WORKFLOW_CONSISTENCY_PASS",
            "native_execution": "NOT_ESTABLISHED_BY_READ_ONLY_VERIFICATION",
            "stage_statuses": {"cad": cad["status"], "mesh": mesh["status"], "thermal": thermal["status"]},
            "recorded_mesh_native_identity": gmsh_mesh.native_provenance(mesh)["status"],
            "artifact_sha256": {"cad": cad_pins, "mesh": mesh_pins, "thermal": thermal_pins},
            "analytical_checks": oracle, **FLAGS, "limitations": list(LIMITATIONS)}


def run(directory, *, gmsh_python, solver):
    """Exactly three explicit adapter calls; no retries, recovery or alternate tools."""
    gmsh_python = configured_executable(gmsh_python, "Gmsh Python")
    solver = configured_executable(solver, "CalculiX")
    require(sys.platform == "linux", "Native workflow requires Linux")
    require(cad_versions() == REQUIRED_CAD, "Required CAD package metadata unavailable or unsupported")
    destination = Path(directory).expanduser().absolute()
    require(not destination.resolve().is_relative_to(ROOT), "Output must be outside this source checkout")
    root = geometry._new_output_directory(destination)
    geometry.export_beam(dict(PARAMETERS), root / "cad", cadquery_compatibility=False)
    verify_cad(root / "cad")
    gmsh_mesh.mesh_beam(root / "cad", root / "mesh", divisions=DIVISIONS,
                        python_executable=gmsh_python, timeout_s=TIMEOUT_S)
    verify_mesh(root / "mesh", root / "cad")
    thermal_conduction.run_thermal(root / "mesh", root / "thermal", solver_executable=solver,
                                  timeout_s=TIMEOUT_S, benchmark="linear")
    return verify(root)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("plan", help="Metadata-only plan; no native imports or execution")
    create = commands.add_parser("run", help="Execute once in an explicitly approved existing environment")
    create.add_argument("output_dir")
    create.add_argument("--gmsh-python", required=True)
    create.add_argument("--solver", required=True)
    check = commands.add_parser("verify", help="Read-only recorded artifact and analytical consistency")
    check.add_argument("output_dir")
    args = parser.parse_args(argv)
    if args.command == "plan":
        result = plan()
    elif args.command == "run":
        result = run(args.output_dir, gmsh_python=args.gmsh_python, solver=args.solver)
    else:
        result = verify(args.output_dir)
    print(json.dumps(result, sort_keys=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
