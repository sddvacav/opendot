"""Read-only package CLI checks, reusable against source or an installed wheel.

Source runs explicitly admit OPENDOT_TEST_SOURCE_ROOT. Without that variable,
children use the interpreter's installed package and never add a source path.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest

import opendot_engineering


_GUARD = """
import argparse
import os
import sys

class BoundedImports:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith('opendot_engineering.') and fullname != 'opendot_engineering.__main__':
            raise AssertionError('Runtime/API import attempted: ' + fullname)
        if fullname.split('.')[0] not in sys.stdlib_module_names | {'opendot_engineering'}:
            raise AssertionError('Optional import attempted: ' + fullname)

sys.meta_path.insert(0, BoundedImports())
def audit(event, args):
    if event.startswith(('socket.', 'subprocess.')) or event in {'os.system', 'os.listdir', 'os.scandir'}:
        raise AssertionError('External execution or file discovery attempted: ' + event)
    if event == 'open':
        path, mode, flags = args
        if isinstance(path, str) and os.path.abspath(path).startswith(os.getcwd() + os.sep):
            raise AssertionError('User file read attempted')
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            raise AssertionError('File write attempted')
sys.addaudithook(audit)
"""


def _run_cli(tmp_path: Path, *args: str, guarded: bool = False):
    source = os.environ.get("OPENDOT_TEST_SOURCE_ROOT")
    command = [sys.executable, "-I", "-B"]
    if source or guarded:
        # Only an explicitly admitted source root can alter isolated imports.
        code = "import runpy, sys\n"
        if source:
            root = Path(source).resolve(strict=True)
            assert Path(opendot_engineering.__file__).resolve() == root / "opendot_engineering/__init__.py"
            code += "sys.path.insert(0, sys.argv.pop(1))\n"
        if guarded:
            # Warm Python's import caches before refusing directory discovery.
            code += "import opendot_engineering\n"
            code += "import importlib.util\nimportlib.util.find_spec('opendot_engineering.__main__')\n"
            code += _GUARD
        code += "sys.argv[0] = 'opendot_engineering'\n"
        code += "runpy.run_module('opendot_engineering', run_name='__main__')\n"
        command += ["-c", code]
        if source:
            command.append(str(root))
    else:
        command += ["-m", "opendot_engineering"]
    command += args
    env = dict(os.environ)
    env.update({"HOME": str(tmp_path), "OPENDOT_TEST_SECRET": "synthetic-do-not-print"})
    return subprocess.run(command, cwd=tmp_path, env=env, text=True,
                          capture_output=True, timeout=10, check=False)


@pytest.mark.parametrize("args", [(), ("--help",), ("-h",)])
def test_help_is_successful_and_describes_the_bounded_package(tmp_path, args):
    result = _run_cli(tmp_path, *args)
    assert result.returncode == 0
    assert result.stderr == ""
    for text in (
        "usage: python -m opendot_engineering", "--help", "--version",
        "First useful result (0.3.0a4, ALPHA / NOT_SCORED)",
        "https://github.com/sddvacav/opendot/releases/tag/v0.3.0a4",
        "https://github.com/sddvacav/opendot/releases/download/v0.3.0a4/RELEASE-NOTES.md",
        "independently reviewed external SHA256SUMS pin",
        "does not verify publication",
        "bounded local artifact storage", "callable-only", "descriptive",
        "Git >= 2.52.0", "fake-only", "scientific acceptance",
        "opendot_engineering.core.artifacts.ArtifactStore",
        "opendot_engineering.core.contracts.ArtifactRef, Capability, AgentManifest",
        "opendot_engineering.tool_runtime.ToolRuntime",
        "opendot_engineering.git_workspace.GitWorkspaceManager",
        "opendot_engineering.adapters.source_admission",
        "opendot_engineering.adapters.source_audit --help",
        "opendot_engineering.adapters.lab_qualification --help",
        "opendot_engineering.adapters.simulated_lab --help",
        "opendot_engineering.executors.geometry --help",
        "opendot_engineering.executors.gmsh_mesh --help",
        "opendot_engineering.executors.thermal_conduction --help",
        "opendot_engineering.executors.structural_beam --help",
        "No opendot or odot console command is registered",
    ):
        assert text in result.stdout
    for private in (str(tmp_path), str(Path(opendot_engineering.__file__).parent),
                    "synthetic-do-not-print"):
        assert private not in result.stdout + result.stderr


def test_no_arguments_and_explicit_help_match(tmp_path):
    assert _run_cli(tmp_path).stdout == _run_cli(tmp_path, "--help").stdout


def test_version_comes_from_package_code(tmp_path):
    result = _run_cli(tmp_path, "--version")
    assert result.returncode == 0
    assert result.stdout == f"opendot-engineering {opendot_engineering.__version__}\n"
    assert result.stderr == ""


@pytest.mark.parametrize("args", [
    ("run",), ("--unknown",), ("--ver",), ("--hel",), ("--version=1",),
    ("--help", "run"), ("--help", "--unknown"), ("--version", "--unknown"),
    ("--", "run"),
])
def test_unknown_arguments_fail_without_dispatch(tmp_path, args):
    result = _run_cli(tmp_path, *args)
    assert result.returncode == 2
    assert result.stdout == ""
    assert "usage: python -m opendot_engineering" in result.stderr
    assert "error:" in result.stderr
    assert "Traceback" not in result.stderr


def test_help_and_version_are_mutually_exclusive(tmp_path):
    result = _run_cli(tmp_path, "--help", "--version")
    assert result.returncode == 2
    assert "not allowed with argument" in result.stderr
    assert result.stdout == ""


@pytest.mark.parametrize("args", [(), ("--help",), ("--version",), ("run",)])
def test_no_runtime_optional_imports_network_user_reads_or_writes(tmp_path, args):
    sentinel = tmp_path / "private-input.txt"
    sentinel.write_text("synthetic-private-file\n")
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    result = _run_cli(tmp_path, *args, guarded=True)
    assert result.returncode == (2 if args == ("run",) else 0), result.stderr
    assert "synthetic-private-file" not in result.stdout + result.stderr
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


def test_import_is_silent_and_main_returns_zero(capsys):
    from opendot_engineering.__main__ import main
    assert capsys.readouterr() == ("", "")
    assert main([]) == 0
    assert "usage: python -m opendot_engineering" in capsys.readouterr().out
