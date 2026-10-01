"""Git/stdlib-only provenance fixtures; no native backend or solver execution."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from opendot_engineering.executors import geometry as g
from opendot_engineering.executors import gmsh_mesh as m
from opendot_engineering.executors import structural_beam as s
from opendot_engineering.executors import thermal_conduction as t


def git(root, *args, env=None):
    clean = {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}
    clean.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_SYSTEM=os.devnull, GIT_CONFIG_GLOBAL=os.devnull,
                 GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0")
    clean.update(env or {})
    return subprocess.run(["git", "--no-pager", "-c", f"core.hooksPath={os.devnull}",
                           "-c", "core.fsmonitor=false", "-c", "submodule.recurse=false", *args],
                          cwd=root, env=clean, stdin=subprocess.DEVNULL, capture_output=True,
                          check=True, timeout=10).stdout


def repository(root, *, commit=True):
    root.mkdir()
    git(root, "init", "--quiet")
    (root / "notes.txt").write_text("Synthetic local fixture only\n")
    if commit:
        save(root)
    return root


def save(root):
    git(root, "add", "--all")
    git(root, "-c", "user.name=Provenance Fixture", "-c", "user.email=fixture@example.invalid",
        "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "Synthetic fixture")
    return git(root, "rev-parse", "HEAD").strip().decode("ascii")


def adapter(root, name="adapter.py"):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"# Synthetic adapter bytes, never executed\n")
    return path


def hash_only(source, result):
    assert result["adapter_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert result["repository_commit"] is None
    assert result["repository_dirty"] is None
    assert result["worktree"] is None
    assert result["revision_status"] != "RECORDED_WITH_WORKTREE_STATE"
    assert str(source.parent) not in json.dumps(result)


def recorded(source, result, commit, dirty):
    assert result == {"adapter_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                      "repository_commit": commit, "repository_dirty": dirty,
                      "worktree": None, "revision_status": "RECORDED_WITH_WORKTREE_STATE"}


@pytest.mark.parametrize("name", ["adapter.py", "space dir/odd[?]*.py", ":(glob)adapter.py", "tab\tline\n.py"])
def test_own_tracked_clean_and_modified_adapter(tmp_path, name):
    root = repository(tmp_path / "own")
    source = adapter(root, name)
    commit = save(root)
    recorded(source, g._source_provenance(source), commit, False)
    source.write_bytes(source.read_bytes() + b"# Uncommitted edit\n")
    recorded(source, g._source_provenance(source), commit, True)


@pytest.mark.parametrize("case", ["assume_unchanged", "skip_worktree", "normalized_line_endings", "staged"])
def test_raw_adapter_changes_are_never_reported_clean(tmp_path, case):
    root = repository(tmp_path / "own")
    source = adapter(root)
    if case == "normalized_line_endings":
        (root / ".gitattributes").write_text("adapter.py text eol=lf\n")
    commit = save(root)
    if case in ("assume_unchanged", "skip_worktree"):
        git(root, "update-index", "--" + case.replace("_", "-"), "adapter.py")
    source.write_bytes(source.read_bytes().replace(b"\n", b"\r\n") if case == "normalized_line_endings"
                       else source.read_bytes() + b"# Different raw source\n")
    if case == "staged":
        git(root, "add", "adapter.py")
    elif case in ("assume_unchanged", "skip_worktree"):
        assert not git(root, "status", "--porcelain")
    recorded(source, g._source_provenance(source), commit, True)


@pytest.mark.parametrize("kind", ["clean", "process"])
def test_repository_content_filter_commands_are_never_executed(tmp_path, kind):
    root = repository(tmp_path / "own")
    source = adapter(root)
    save(root)
    marker = tmp_path / "filter-was-executed"
    (root / ".gitattributes").write_text("adapter.py filter=fixture\n")
    git(root, "config", f"filter.fixture.{kind}", f"touch '{marker}'; cat")
    source.write_bytes(source.read_bytes() + b"# A filter would process this edit\n")
    hash_only(source, g._source_provenance(source))
    assert not marker.exists()


@pytest.mark.parametrize("ignored", [False, True])
def test_untracked_installed_adapter_is_not_enclosing_repository(tmp_path, ignored):
    root = repository(tmp_path / "unrelated")
    if ignored:
        (root / ".gitignore").write_text(".venv/\n")
        save(root)
    source = adapter(root, ".venv/lib/python3.12/site-packages/opendot_engineering/executors/geometry.py")
    assert not git(root, "ls-files", "--", str(source.relative_to(root)))
    assert not git(root, "ls-tree", "HEAD", "--", str(source.relative_to(root)))
    hash_only(source, g._source_provenance(source))


@pytest.mark.parametrize("case", ["unborn", "index_only", "removed_from_index", "head_symlink", "index_symlink", "unmerged"])
def test_missing_or_nonregular_membership_is_hash_only(tmp_path, case):
    root = repository(tmp_path / "own", commit=case != "unborn")
    source = adapter(root)
    if case in ("unborn", "index_only"):
        git(root, "add", "adapter.py")
    else:
        if case == "head_symlink":
            source.unlink()
            source.symlink_to("notes.txt")
            save(root)
            source.unlink()
            source.write_bytes(b"# Now a regular file\n")
            git(root, "add", "adapter.py")
        else:
            save(root)
            if case == "removed_from_index":
                git(root, "rm", "--cached", "adapter.py")
            elif case == "index_symlink":
                oid = git(root, "rev-parse", "HEAD:adapter.py").strip().decode("ascii")
                git(root, "update-index", "--cacheinfo", f"120000,{oid},adapter.py")
            elif case == "unmerged":
                # A conflicted index must never be accepted as a single stage-zero entry.
                (root / "adapter.py").write_bytes(b"# changed on the other branch\n")
                other = save(root)
                git(root, "reset", "--hard", "HEAD~1")
                source.write_bytes(b"# changed on this branch\n")
                ours = save(root)
                git(root, "read-tree", "-m", f"{ours}~1", ours, other)
    hash_only(source, g._source_provenance(source))


@pytest.mark.parametrize("marker", ["file", "empty_directory", "broken_symlink"])
def test_nearer_broken_git_marker_does_not_fall_back(tmp_path, marker):
    root = repository(tmp_path / "outer")
    source = adapter(root, "inner/adapter.py")
    save(root)
    path = source.parent / ".git"
    if marker == "file":
        path.write_text("not valid git metadata\n")
    elif marker == "empty_directory":
        path.mkdir()
    else:
        path.symlink_to("absent-git-directory")
    hash_only(source, g._source_provenance(source))


def test_nearer_nonowning_repository_does_not_fall_back(tmp_path):
    root = repository(tmp_path / "outer")
    source = adapter(root, "inner/adapter.py")
    save(root)
    git(source.parent, "init", "--quiet")
    (source.parent / "notes.txt").write_text("An unrelated nested repository\n")
    git(source.parent, "add", "notes.txt")
    git(source.parent, "-c", "user.name=Provenance Fixture", "-c", "user.email=fixture@example.invalid",
        "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "Unrelated fixture")
    hash_only(source, g._source_provenance(source))


def test_no_git_marker_is_hash_only(tmp_path, monkeypatch):
    source = adapter(tmp_path)
    # Do not depend on whether the external pytest directory has Git ancestors.
    monkeypatch.setattr(os.path, "lexists", lambda path: False)
    result = g._source_provenance(source)
    hash_only(source, result)
    assert result["revision_status"] == "UNAVAILABLE"


def test_linked_worktree_git_file_is_supported_without_path_disclosure(tmp_path):
    root = repository(tmp_path / "own")
    adapter(root)
    commit = save(root)
    linked = tmp_path / "linked"
    git(root, "worktree", "add", "--quiet", "--detach", str(linked), commit)
    assert (linked / ".git").is_file()
    recorded(linked / "adapter.py", g._source_provenance(linked / "adapter.py"), commit, False)


def test_configured_worktree_root_mismatch_is_hash_only(tmp_path):
    root = repository(tmp_path / "own")
    source = adapter(root)
    save(root)
    other = repository(tmp_path / "other")
    git(root, "config", "core.worktree", str(other))
    hash_only(source, g._source_provenance(source))


@pytest.mark.parametrize("override", ["repository", "index", "config_count", "config_parameters", "config_files", "objects", "discovery"])
def test_inherited_git_environment_cannot_change_source_context(tmp_path, monkeypatch, override):
    root = repository(tmp_path / "own")
    source = adapter(root)
    commit = save(root)
    other = repository(tmp_path / "other")
    if override == "repository":
        values = {"GIT_DIR": str(other / ".git"), "GIT_WORK_TREE": str(other), "GIT_COMMON_DIR": str(other / ".git")}
    elif override == "index":
        empty = tmp_path / "empty-index"
        git(root, "read-tree", "--empty", env={"GIT_INDEX_FILE": str(empty)})
        values = {"GIT_INDEX_FILE": str(empty)}
    elif override == "config_count":
        values = {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.worktree", "GIT_CONFIG_VALUE_0": str(other)}
    elif override == "config_parameters":
        values = {"GIT_CONFIG_PARAMETERS": f"'core.worktree={other}'"}
    elif override == "config_files":
        config = tmp_path / "foreign-config"
        config.write_text(f"[core]\n\tworktree = {other}\n")
        values = {"GIT_CONFIG_GLOBAL": str(config), "GIT_CONFIG_SYSTEM": str(config), "GIT_CONFIG_NOSYSTEM": "0"}
    elif override == "objects":
        values = {"GIT_OBJECT_DIRECTORY": str(other / ".git/objects"),
                  "GIT_ALTERNATE_OBJECT_DIRECTORIES": str(other / ".git/objects"), "GIT_REPLACE_REF_BASE": "refs/foreign/"}
    else:
        values = {"GIT_CEILING_DIRECTORIES": str(root), "GIT_DISCOVERY_ACROSS_FILESYSTEM": "0", "GIT_PREFIX": "wrong/"}
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    recorded(source, g._source_provenance(source), commit, False)


def test_every_git_call_uses_one_sanitized_environment(tmp_path, monkeypatch):
    root = repository(tmp_path / "own")
    source = adapter(root)
    commit = save(root)
    monkeypatch.setenv("GIT_UNUSED_FUTURE_ROUTING_VARIABLE", "must disappear")
    original = subprocess.run
    calls = []

    def capture(command, **kwargs):
        calls.append((command, kwargs))
        return original(command, **kwargs)

    monkeypatch.setattr(subprocess, "run", capture)
    recorded(source, g._source_provenance(source), commit, False)
    assert len(calls) == 8
    for command, kwargs in calls:
        assert kwargs["cwd"] == root
        assert kwargs["env"] is calls[0][1]["env"]
        assert kwargs["env"]["GIT_CONFIG_GLOBAL"] == os.devnull
        assert kwargs["env"]["GIT_CONFIG_SYSTEM"] == os.devnull
        assert kwargs["env"]["GIT_CONFIG_NOSYSTEM"] == "1"
        assert kwargs["env"]["GIT_OPTIONAL_LOCKS"] == "0"
        assert kwargs["env"]["GIT_NO_REPLACE_OBJECTS"] == "1"
        assert "GIT_UNUSED_FUTURE_ROUTING_VARIABLE" not in kwargs["env"]
        assert f"core.hooksPath={os.devnull}" in command
        assert "core.fsmonitor=false" in command
        assert "submodule.recurse=false" in command
        assert "--literal-pathspecs" in command


def test_git_failure_returns_no_partial_repository_fields(tmp_path, monkeypatch):
    root = repository(tmp_path / "own")
    source = adapter(root)
    save(root)
    original = subprocess.run

    def fail_status(command, **kwargs):
        if "status" in command:
            raise subprocess.TimeoutExpired(command, 5)
        return original(command, **kwargs)

    monkeypatch.setattr(subprocess, "run", fail_status)
    result = g._source_provenance(source)
    hash_only(source, result)
    assert result["revision_status"] == "GIT_UNAVAILABLE_SOURCE_HASH_RECORDED"


@pytest.mark.parametrize("changed", ["head", "source"])
def test_observed_identity_change_during_probe_is_hash_only(tmp_path, monkeypatch, changed):
    root = repository(tmp_path / "own")
    source = adapter(root)
    save(root)
    original = subprocess.run
    head_reads = 0

    def mutate(command, **kwargs):
        nonlocal head_reads
        result = original(command, **kwargs)
        if "HEAD^{commit}" in command:
            head_reads += 1
            if head_reads == 2:
                if changed == "head":
                    result.stdout = b"0" * 40 + b"\n"
                else:
                    source.write_bytes(source.read_bytes() + b"# raced\n")
        return result

    monkeypatch.setattr(subprocess, "run", mutate)
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    result = g._source_provenance(source)
    assert result["adapter_sha256"] == before
    assert result["repository_commit"] is result["repository_dirty"] is result["worktree"] is None
    assert result["revision_status"] == "GIT_UNVERIFIED_SOURCE_HASH_RECORDED"


def test_default_is_geometry_and_imports_remain_stdlib_only():
    source_root = str(Path(g.__file__).resolve().parents[2])
    code = (f"import sys; sys.path.insert(0, {source_root!r}); "
            "from opendot_engineering.executors import geometry as g, gmsh_mesh, thermal_conduction, structural_beam; "
            "assert g._source_provenance() == g._source_provenance(g.__file__); "
            "assert not any(n in sys.modules for n in ('build123d','gmsh','numpy','cadquery','OCP'))")
    subprocess.run([sys.executable, "-I", "-B", "-c", code], check=True, capture_output=True, timeout=30)


@pytest.mark.parametrize("module", [g, m, t, s], ids=["geometry", "mesh", "thermal", "structural"])
def test_each_route_passes_its_actual_adapter_file(tmp_path, monkeypatch, module):
    seen = []

    class ProbeComplete(Exception):
        pass

    def probe(path=None):
        seen.append(path)
        raise ProbeComplete

    monkeypatch.setattr(g, "_source_provenance", probe)
    if module is g:
        monkeypatch.setattr(g, "_load_build123d", lambda: object())
        invoke = lambda: g.export_beam({}, tmp_path / "not-built")
    elif module is t:
        fake_binary = adapter(tmp_path, "not-an-executable")
        monkeypatch.setattr(t.shutil, "which", lambda value: str(fake_binary))
        monkeypatch.setattr(t, "_snapshot_mesh", lambda root: ({"measurements": {"volume_elements": 1}}, {}))
        monkeypatch.setattr(m, "verify_mesh_artifacts", lambda root: None)
        monkeypatch.setattr(t, "mesh_data", lambda path: ({}, {}, {}))
        monkeypatch.setattr(t, "_json", lambda path: {"dimensions_m": [.2, .02, .003]})
        invoke = lambda: t.run_thermal("unused", tmp_path / "not-solved", solver_executable="unused")
    else:
        invoke = module._source
    with pytest.raises(ProbeComplete):
        invoke()
    assert seen == [module.__file__]


@pytest.mark.parametrize("module", [m, s], ids=["mesh", "structural"])
def test_wrapper_does_not_substitute_geometry_git_context(tmp_path, monkeypatch, module):
    root = repository(tmp_path / "geometry-checkout")
    geometry = adapter(root, "geometry.py")
    save(root)
    actual = adapter(root, Path(module.__file__).name)
    if module is m:
        adapter(root, "_gmsh_worker.py")
    monkeypatch.setattr(g, "__file__", str(geometry))
    monkeypatch.setattr(module, "__file__", str(actual))
    result = module._source()
    hash_only(actual, result)
