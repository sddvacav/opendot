"""Source-only checks for the bounded CPython 3.12/Linux CI tool lock.

No network access, installer calls, native backends or OpenDot imports.
Offline pip refusal/install controls live in the separately retained evidence.
"""
import importlib.metadata
from pathlib import Path
import re
import shlex
import sys
import tomllib

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
import pytest


ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "pytest": ("9.1.1", "37a86b45efb9a47a61a36449063e8e18d0cab3161329fc099eb21783169c4f0c"),
    "iniconfig": ("2.3.0", "f631c04d2c48c52b84d0d0549c99ff3859c98df65b3101406327ecc7d53fbf12"),
    "packaging": ("26.3", "d7193f7c8e4e93f444fde0262bf90af30e16fa0ad0ad44cb553c87339b23cd1c"),
    "pluggy": ("1.6.0", "e920276dd6813095e9377c0bc5566d94c932c33b27a3e3945d8389c374dd4746"),
    "pygments": ("2.21.0", "2363c69b61c4a97c838da3b130dcd6468f4848992b21a82f2a63ec34377137d9"),
}


def read_lock(text):
    result = {}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([0-9.]+) --hash=sha256:([0-9a-f]{64})", line)
        if match is None:
            raise ValueError("Expected one exact version and SHA-256 per requirement")
        name, version, digest = match.groups()
        name = canonicalize_name(name)
        if name in result:
            raise ValueError("Duplicate requirement")
        result[name] = (version, digest)
    return result


def test_exact_hash_lock():
    assert read_lock((ROOT / "ci/requirements.txt").read_text()) == EXPECTED


@pytest.mark.parametrize("text", [
    "pytest>=9.1.1 --hash=sha256:" + "0" * 64,
    "pytest==9.1.1",
    "pytest==9.1.1 --hash=md5:" + "0" * 32,
    "pytest==9.1.1 --hash=sha256:" + "g" * 64,
    "--extra-index-url https://example.invalid/simple",
    "pytest==9.1.1 --hash=sha256:" + "0" * 64 + "\npytest==9.1.1 --hash=sha256:" + "1" * 64,
])
def test_lock_parser_rejects_incomplete_or_ambiguous_lines(text):
    with pytest.raises(ValueError):
        read_lock(text)


def test_portable_install_enforces_hashes_and_wheels():
    workflow = (ROOT / ".github/workflows/portable.yml").read_text()
    commands = [line.split("run: ", 1)[1] for line in workflow.splitlines()
                if "run: " in line and "-r ci/requirements.txt" in line]
    assert len(commands) == 1
    command = shlex.split(commands[0])
    assert command[:7] == ["PIP_CONFIG_FILE=/dev/null", "python", "-B", "-m", "pip", "--isolated", "install"]
    for token in ("--require-hashes", "--only-binary=:all:", "--no-cache-dir", "--no-compile", "--disable-pip-version-check"):
        assert token in command
    assert command[command.index("--index-url") + 1] == "https://pypi.org/simple"
    assert "--no-deps" not in command
    assert "--trusted-host" not in command
    assert "--extra-index-url" not in command


def test_selected_installed_dependency_closure():
    if sys.implementation.name != "cpython" or sys.version_info[:2] != (3, 12) or sys.platform != "linux":
        pytest.skip("This closure is selected only for CPython 3.12/Linux")
    environment = default_environment()
    environment["extra"] = ""
    edges = {}
    for name, (version, _) in EXPECTED.items():
        distribution = importlib.metadata.distribution(name)
        assert distribution.version == version
        edges[name] = []
        for literal in distribution.requires or []:
            requirement = Requirement(literal)
            if requirement.marker is not None and not requirement.marker.evaluate(environment):
                continue
            target = canonicalize_name(requirement.name)
            assert target in EXPECTED
            assert EXPECTED[target][0] in requirement.specifier
            edges[name].append(target)
    assert edges == {"pytest": ["iniconfig", "packaging", "pluggy", "pygments"],
                     "iniconfig": [], "packaging": [], "pluggy": [], "pygments": []}


def test_runtime_dependencies_remain_empty():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert project["project"]["dependencies"] == []
    assert project["build-system"]["requires"] == ["setuptools==84.0.0"]
