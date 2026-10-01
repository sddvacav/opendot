"""Read-only package help and code version; no runtime or tool dispatch."""
from __future__ import annotations

import argparse

from . import __version__


_GUIDE = """Python APIs (import explicitly):
  opendot_engineering.core.artifacts.ArtifactStore
    Canonical local bytes; trusted roots, no transaction or recovery guarantee.
  opendot_engineering.core.contracts.ArtifactRef, Capability, AgentManifest
    Artifact references and descriptive, explicitly validated agent metadata.
  opendot_engineering.tool_runtime.ToolRuntime
    Bounded callable-only execution; no autonomous agent runtime.
  opendot_engineering.git_workspace.GitWorkspaceManager
    Controlled local create/status/diff; trusted POSIX checkout, Git >= 2.52.0.
  opendot_engineering.adapters.source_admission
    Optional, explicitly operator-reviewed flat-module source admission.

Existing module entrypoints (invoke separately with --help):
  python -m opendot_engineering.adapters.source_audit --help
  python -m opendot_engineering.adapters.lab_qualification --help
  python -m opendot_engineering.adapters.simulated_lab --help
  python -m opendot_engineering.executors.geometry --help
  python -m opendot_engineering.executors.gmsh_mesh --help
  python -m opendot_engineering.executors.thermal_conduction --help
  python -m opendot_engineering.executors.structural_beam --help

Scope:
  Local source checks, synthetic qualification records, optional finite fake-only
  lab simulation, and bounded CAD/CAE adapters. Optional execution needs separately
  prepared dependencies; software checks do not establish scientific acceptance.
  This entrypoint prints help or the code version only. It does not inspect user
  files, load optional backends, dispatch tools, start a runtime, or call a network
  service or model. No opendot or odot console command is registered.
"""


def main(argv: list[str] | None = None) -> int:
    """Print static guidance or the package's code version, without dispatch."""
    parser = argparse.ArgumentParser(
        prog="python -m opendot_engineering",
        description=(
            "OpenDot Engineering: bounded local artifact storage, callable "
            "execution, and engineering adapters."
        ),
        epilog=_GUIDE,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
        allow_abbrev=False,
    )
    options = parser.add_mutually_exclusive_group()
    options.add_argument("-h", "--help", action="store_true", help="show this help and exit")
    options.add_argument("--version", action="store_true", help="show the package code version and exit")
    args = parser.parse_args(argv)
    if args.version:
        print(f"opendot-engineering {__version__}")
    else:
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
