"""New, disposable local fixtures; no private initializer or test configuration."""
from dataclasses import fields, replace
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from opendot_engineering.git_workspace import (
    GitReceipt, GitWorkspace, GitWorkspaceCreationError, GitWorkspaceManager,
)

GIT = shutil.which("git", path=GitWorkspaceManager._SYSTEM_PATH)
ENV = {
    "PATH": GitWorkspaceManager._SYSTEM_PATH, "HOME": "/dev/null",
    "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null", "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C",
}


def git(repo, *args, check=True):
    return subprocess.run(
        [GIT, "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", *args],
        cwd=repo, env=ENV, check=check, capture_output=True, text=True,
        stdin=subprocess.DEVNULL,
    )


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "repository"
    path.mkdir()
    git(path, "init", "-b", "main")
    git(path, "config", "user.email", "fixture@example.invalid")
    git(path, "config", "user.name", "Synthetic Fixture")
    (path / "tracked.txt").write_text("initial\n")
    (path / "binary.bin").write_bytes(b"\x00initial\x00")
    git(path, "add", "--all")
    git(path, "commit", "-m", "synthetic baseline")
    return path


@pytest.fixture
def manager(repo, tmp_path):
    return GitWorkspaceManager(repo, tmp_path / "worktrees")


def sentinel(tmp_path, name):
    marker = tmp_path / f"{name}.ran"
    script = tmp_path / f"{name}.sh"
    script.write_text(f"#!/bin/sh\nprintf invoked >> '{marker}'\nexit 87\n")
    script.chmod(0o700)
    return script, marker


def test_preserved_contracts_and_omitted_writes(manager):
    assert [f.name for f in fields(GitReceipt)] == ["action", "returncode", "stdout", "stderr", "digest"]
    receipt = GitReceipt("a", 0, "b", "c", "d")
    assert receipt.ok and not replace(receipt, returncode=1).ok
    assert [f.name for f in fields(GitWorkspace)][:4] == ["goal_id", "branch", "path", "base_ref"]
    legacy = GitWorkspace("old", "agent/old", Path("old"), "HEAD")
    assert legacy.base_commit == ""
    with pytest.raises(ValueError, match="not issued"):
        manager.status(legacy)
    assert not hasattr(manager, "commit") and not hasattr(manager, "remove")


def test_two_worktrees_pinned_base_and_scope(manager, repo):
    base = git(repo, "rev-parse", "HEAD").stdout.strip()
    git(repo, "tag", "baseline")
    first = manager.create("First Task")
    second = manager.create("Second Task", base_ref="baseline")
    assert first.base_commit == second.base_commit == base
    assert manager.status(first).stdout == manager.status(second).stdout == ""
    (first.path / "tracked.txt").write_text("first edit\n")
    (first.path / "binary.bin").write_bytes(b"\x00changed\x00")
    (first.path / "untracked.txt").write_text("not in diff\n")
    status = manager.status(first)
    diff = manager.diff(first)
    assert status.ok and " M tracked.txt" in status.stdout and "?? untracked.txt" in status.stdout
    assert len(status.digest) == 64 and len(diff.digest) == 64
    assert "+first edit" in diff.stdout and "GIT binary patch" in diff.stdout
    assert "untracked.txt" not in diff.stdout
    assert manager.status(second).stdout == "" and manager.diff(second).stdout == ""
    assert (repo / "tracked.txt").read_text() == "initial\n"
    git(first.path, "add", "tracked.txt", "binary.bin")
    assert manager.diff(first).stdout == ""
    assert "M  tracked.txt" in manager.status(first).stdout
    (repo / "tracked.txt").write_text("new main\n")
    git(repo, "commit", "-am", "move main")
    assert git(repo, "rev-parse", "HEAD").stdout.strip() != base
    assert first.base_commit == second.base_commit == base
    assert git(first.path, "rev-parse", "HEAD").stdout.strip() == base
    assert manager.status(second).stdout == ""


def test_status_diff_do_not_refresh_index(manager):
    workspace = manager.create("No Refresh")
    gitdir = Path(git(workspace.path, "rev-parse", "--absolute-git-dir").stdout.strip())
    index = gitdir / "index"
    before = (index.read_bytes(), index.stat().st_mtime_ns)
    target = workspace.path / "tracked.txt"
    os.utime(target, ns=(target.stat().st_atime_ns, target.stat().st_mtime_ns + 1000000000))
    manager.status(workspace)
    manager.diff(workspace)
    assert before == (index.read_bytes(), index.stat().st_mtime_ns)


def test_resolve_base_once_even_if_ref_moves(manager, repo, monkeypatch):
    old = git(repo, "rev-parse", "HEAD").stdout.strip()
    (repo / "tracked.txt").write_text("later\n")
    git(repo, "commit", "-am", "second")
    new = git(repo, "rev-parse", "HEAD").stdout.strip()
    git(repo, "tag", "moving", old)
    original = manager._git
    calls = []
    def move(*args, **kwargs):
        if args[:2] == ("worktree", "add"):
            calls.append(args)
            git(repo, "tag", "-f", "moving", new)
        return original(*args, **kwargs)
    monkeypatch.setattr(manager, "_git", move)
    workspace = manager.create("Pinned", base_ref="moving")
    assert len(calls) == 1 and calls[0][-1] == old
    assert workspace.base_commit == old
    assert git(workspace.path, "rev-parse", "HEAD").stdout.strip() == old


@pytest.mark.parametrize("base", ["--help", "-b", "", "HEAD~1", "main:path", "bad ref"])
def test_invalid_base_fails_before_writes(manager, repo, base):
    with pytest.raises((ValueError, RuntimeError)):
        manager.create("Invalid Base", base_ref=base)
    assert not (manager.worktree_root / "invalid-base").exists()
    assert git(repo, "show-ref", "--verify", "refs/heads/agent/invalid-base", check=False).returncode != 0


@pytest.mark.parametrize("goals", [("Same CASE", "same case"), ("a" * 80 + "X", "a" * 80 + "Y"), ("same!name", "same?name")])
def test_slug_collisions_are_not_reused(manager, goals):
    first = manager.create(goals[0])
    with pytest.raises(FileExistsError):
        manager.create(goals[1])
    assert manager.status(first).ok


def test_existing_branch_rejected(manager, repo):
    git(repo, "branch", "agent/existing")
    with pytest.raises(FileExistsError):
        manager.create("existing")
    assert not (manager.worktree_root / "existing").exists()


@pytest.mark.parametrize("kind", ["directory", "file", "dangling_symlink"])
def test_existing_path_rejected(manager, kind):
    path = manager.worktree_root / "existing"
    if kind == "directory":
        path.mkdir()
    elif kind == "file":
        path.write_text("keep")
    else:
        path.symlink_to(manager.worktree_root / "missing")
    with pytest.raises(FileExistsError):
        manager.create("existing")
    assert os.path.lexists(path)


def test_failed_add_is_single_attempt_and_reports_residue(manager, repo, monkeypatch):
    original = manager._git
    calls = []
    def fail(*args, **kwargs):
        if args[:2] == ("worktree", "add"):
            calls.append(args)
            # Simulate a failure after the real Git branch/worktree write.
            receipt = original(*args, **kwargs)
            assert receipt.ok
            return GitReceipt(receipt.action, 9, receipt.stdout, "injected partial failure", "0" * 64)
        return original(*args, **kwargs)
    monkeypatch.setattr(manager, "_git", fail)
    with pytest.raises(GitWorkspaceCreationError) as caught:
        manager.create("Interrupted")
    assert caught.value.residual_state == {"path_exists": True, "branch_exists": True, "registered": True}
    assert caught.value.path.is_dir()
    assert len(calls) == 1
    with pytest.raises(ValueError, match="previous creation failed"):
        manager.create("Interrupted")
    assert len(calls) == 1
    assert git(repo, "show-ref", "--verify", "refs/heads/agent/interrupted").returncode == 0


@pytest.mark.parametrize("observation_error", [PermissionError("inaccessible"), OSError("unobservable")],
                         ids=["permission", "other_os_error"])
def test_unobservable_residue_is_unknown(manager, repo, monkeypatch, observation_error):
    original_git = manager._git
    original_lstat = Path.lstat
    target = manager.worktree_root / "unknown"
    calls = []

    def observe(path, *args, **kwargs):
        if calls and path == target:
            raise observation_error
        return original_lstat(path, *args, **kwargs)

    def fail_after_add(*args, **kwargs):
        receipt = original_git(*args, **kwargs)
        if args[:2] == ("worktree", "add"):
            assert receipt.ok
            calls.append(args)
            return GitReceipt(receipt.action, 9, receipt.stdout, "injected partial failure", "0" * 64)
        return receipt

    monkeypatch.setattr(Path, "lstat", observe)
    monkeypatch.setattr(manager, "_git", fail_after_add)
    with pytest.raises(GitWorkspaceCreationError) as caught:
        manager.create("Unknown")
    assert caught.value.residual_state == {"path_exists": None, "branch_exists": True, "registered": True}
    monkeypatch.setattr(Path, "lstat", original_lstat)
    assert target.is_dir()
    assert git(repo, "show-ref", "--verify", "refs/heads/agent/unknown").returncode == 0
    with pytest.raises(ValueError, match="previous creation failed"):
        manager.create("Unknown")
    assert len(calls) == 1


def test_failure_without_residue_is_still_not_retried(manager, monkeypatch):
    original = manager._git
    calls = []
    def fail(*args, **kwargs):
        if args[:2] == ("worktree", "add"):
            calls.append(args)
            return GitReceipt("worktree add", 1, "", "injected failure", "0" * 64)
        return original(*args, **kwargs)
    monkeypatch.setattr(manager, "_git", fail)
    with pytest.raises(GitWorkspaceCreationError) as caught:
        manager.create("Failure")
    assert caught.value.residual_state == {"path_exists": False, "branch_exists": False, "registered": False}
    assert len(calls) == 1


def test_inherited_git_and_path_pollution_is_ignored(repo, tmp_path, monkeypatch):
    other = tmp_path / "external"
    other.mkdir()
    git(other, "init", "-b", "main")
    external_index = tmp_path / "outside-index"
    external_index.write_bytes(b"DO NOT MODIFY")
    script, marker = sentinel(tmp_path, "environment")
    fakebin = tmp_path / "fake-bin"
    fakebin.mkdir()
    (fakebin / "git").write_text(script.read_text())
    (fakebin / "git").chmod(0o700)
    poison = {
        "PATH": str(fakebin), "HOME": str(other), "XDG_CONFIG_HOME": str(other),
        "GIT_DIR": str(other / ".git"), "GIT_WORK_TREE": str(other),
        "GIT_INDEX_FILE": str(external_index), "GIT_OBJECT_DIRECTORY": str(other / "objects"),
        "GIT_ALTERNATE_OBJECT_DIRECTORIES": str(other), "GIT_COMMON_DIR": str(other / ".git"),
        "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.fsmonitor",
        "GIT_CONFIG_VALUE_0": str(script), "GIT_CONFIG_PARAMETERS": "'core.fsmonitor'='bad'",
        "GIT_CONFIG_SYSTEM": str(script), "GIT_CONFIG_GLOBAL": str(script),
        "GIT_EXEC_PATH": str(fakebin), "GIT_EXTERNAL_DIFF": str(script),
        "GIT_ASKPASS": str(script), "SSH_ASKPASS": str(script), "GIT_SSH_COMMAND": str(script),
        "GIT_REPLACE_REF_BASE": "refs/evil", "GIT_TRACE": str(marker), "LD_PRELOAD": str(script),
    }
    original = {p.relative_to(other): p.read_bytes() for p in other.rglob("*") if p.is_file()}
    for key, value in poison.items():
        monkeypatch.setenv(key, value)
    manager = GitWorkspaceManager(repo, tmp_path / "worktrees")
    workspace = manager.create("Environment")
    (workspace.path / "tracked.txt").write_text("changed\n")
    assert manager.status(workspace).ok and manager.diff(workspace).ok
    assert external_index.read_bytes() == b"DO NOT MODIFY" and not marker.exists()
    assert original == {p.relative_to(other): p.read_bytes() for p in other.rglob("*") if p.is_file()}


def test_hooks_fsmonitor_diff_and_textconv_sentinels_never_run(repo, tmp_path):
    script, marker = sentinel(tmp_path, "commands")
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    (hooks / "post-checkout").write_text(script.read_text())
    (hooks / "post-checkout").chmod(0o700)
    git(repo, "config", "core.hooksPath", str(hooks))
    git(repo, "config", "core.fsmonitor", str(script))
    git(repo, "config", "diff.external", str(script))
    git(repo, "config", "diff.sentinel.textconv", str(script))
    manager = GitWorkspaceManager(repo, tmp_path / "worktrees")
    workspace = manager.create("Sentinels")
    (workspace.path / "tracked.txt").write_text("modified\n")
    assert manager.status(workspace).ok
    receipt = manager.diff(workspace)
    assert receipt.ok and "+modified" in receipt.stdout
    assert "--no-ext-diff" in receipt.action and "--no-textconv" in receipt.action
    assert not marker.exists()


@pytest.mark.parametrize("key", ["filter.sentinel.clean", "filter.sentinel.smudge", "filter.sentinel.process",
                                  "remote.origin.promisor", "remote.origin.partialclonefilter",
                                  "extensions.partialclone", "extensions.worktreeConfig", "core.worktree",
                                  "core.attributesFile", "submodule.example.url", "core.sparseCheckout"])
def test_unsupported_configuration_fails_closed(repo, tmp_path, key):
    script, marker = sentinel(tmp_path, "config")
    git(repo, "config", key, str(script))
    with pytest.raises((ValueError, RuntimeError)):
        GitWorkspaceManager(repo, tmp_path / "worktrees")
    assert not marker.exists() and not (tmp_path / "worktrees").exists()


@pytest.mark.parametrize("name", ["info/attributes", "objects/info/alternates", "objects/info/http-alternates",
                                   "shallow", "info/grafts", "config.worktree", "objects/pack/test.promisor"])
def test_unsupported_metadata_fails_closed(repo, tmp_path, name):
    target = repo / ".git" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("")
    with pytest.raises((ValueError, RuntimeError)):
        GitWorkspaceManager(repo, tmp_path / "worktrees")
    assert not (tmp_path / "worktrees").exists()


def test_config_include_rejected(repo, tmp_path):
    script, marker = sentinel(tmp_path, "include")
    config = tmp_path / "included.config"
    config.write_text(f"[core]\nfsmonitor = {script}\n")
    git(repo, "config", "include.path", str(config))
    with pytest.raises(ValueError, match="configuration"):
        GitWorkspaceManager(repo, tmp_path / "worktrees")
    assert not marker.exists()


@pytest.mark.parametrize("name", [".gitattributes", "nested/.gitattributes", ".gitmodules"])
def test_untracked_attributes_or_modules_rejected(repo, tmp_path, name):
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("* filter=sentinel diff=sentinel\n")
    with pytest.raises(ValueError):
        GitWorkspaceManager(repo, tmp_path / "worktrees")


def test_committed_attributes_rejected_even_when_absent_from_current_checkout(manager, repo):
    (repo / ".gitattributes").write_text("* diff=sentinel\n")
    git(repo, "add", ".gitattributes")
    git(repo, "commit", "-m", "attribute history")
    git(repo, "tag", "with-attributes")
    git(repo, "rm", ".gitattributes")
    git(repo, "commit", "-m", "remove attributes")
    with pytest.raises(ValueError, match="attributes"):
        manager.create("Attributes", base_ref="with-attributes")
    assert not (manager.worktree_root / "attributes").exists()


def test_index_submodule_is_rejected(repo, tmp_path):
    oid = git(repo, "rev-parse", "HEAD").stdout.strip()
    git(repo, "update-index", "--add", "--cacheinfo", f"160000,{oid},module")
    with pytest.raises(ValueError, match="submodules"):
        GitWorkspaceManager(repo, tmp_path / "worktrees")


def test_tracked_symlink_is_rejected(repo, tmp_path):
    (repo / "link").symlink_to("tracked.txt")
    git(repo, "add", "link")
    with pytest.raises(ValueError, match="symlink"):
        GitWorkspaceManager(repo, tmp_path / "worktrees")


def test_missing_blob_refused_without_fetch(manager, repo, tmp_path):
    script, marker = sentinel(tmp_path, "credentials")
    git(repo, "config", "credential.helper", f"!{script}")
    git(repo, "config", "remote.origin.url", "https://invalid.example.invalid/never-fetch")
    # Remove a historical blob no longer in the index, so the closure check catches it.
    oid = git(repo, "rev-parse", "HEAD:tracked.txt").stdout.strip()
    (repo / "tracked.txt").write_text("new content\n")
    git(repo, "commit", "-am", "next")
    (repo / ".git" / "objects" / oid[:2] / oid[2:]).unlink()
    with pytest.raises((ValueError, RuntimeError)):
        manager.create("Missing")
    assert not marker.exists() and not (manager.worktree_root / "missing").exists()


@pytest.mark.parametrize("kind", ["forged", "other_manager", "modified_record"])
def test_only_exact_issued_record_is_accepted(manager, repo, tmp_path, kind):
    workspace = manager.create("Owned")
    if kind == "forged":
        workspace = replace(workspace)
    elif kind == "other_manager":
        other = GitWorkspaceManager(repo, tmp_path / "other-root")
        with pytest.raises(ValueError, match="not issued"):
            other.status(workspace)
        return
    else:
        object.__setattr__(workspace, "path", repo)
    with pytest.raises(ValueError, match="not issued"):
        manager.diff(workspace)


@pytest.mark.parametrize("kind", ["symlink", "replacement_directory", "branch", "gitdir", "root"])
def test_changed_workspace_ownership_is_rejected(manager, repo, tmp_path, kind):
    workspace = manager.create("Owned")
    if kind in ("symlink", "replacement_directory"):
        workspace.path.rename(tmp_path / "moved")
        if kind == "symlink":
            workspace.path.symlink_to(repo, target_is_directory=True)
        else:
            workspace.path.mkdir()
    elif kind == "branch":
        git(workspace.path, "checkout", "-b", "other-branch")
    elif kind == "gitdir":
        (workspace.path / ".git").write_text(f"gitdir: {repo / '.git'}\n")
    else:
        manager.worktree_root.rename(tmp_path / "old-root")
        manager.worktree_root.mkdir()
    with pytest.raises((ValueError, RuntimeError)):
        manager.status(workspace)


@pytest.mark.parametrize("where", ["repository", "ancestor", "administrative", "symlink"])
def test_root_overlap_and_aliases_rejected(repo, tmp_path, where):
    if where == "repository":
        root = repo / "child"
    elif where == "ancestor":
        root = tmp_path
    elif where == "administrative":
        root = repo / ".git" / "worktrees"
    else:
        root = tmp_path / "alias"
        root.symlink_to(tmp_path / "target", target_is_directory=True)
    with pytest.raises(ValueError):
        GitWorkspaceManager(repo, root)


def test_repository_must_be_primary_checkout(repo, tmp_path):
    subdir = repo / "nested"
    subdir.mkdir()
    with pytest.raises(ValueError):
        GitWorkspaceManager(subdir, tmp_path / "worktrees")
    linked = tmp_path / "linked"
    git(repo, "worktree", "add", "-b", "linked", str(linked))
    with pytest.raises(ValueError):
        GitWorkspaceManager(linked, tmp_path / "worktrees")


@pytest.mark.parametrize("kind", ["attributes", "filter", "promisor", "missing_index_blob", "symlink"])
def test_safety_rechecked_for_each_observation(manager, repo, tmp_path, kind):
    workspace = manager.create("Observe")
    script, marker = sentinel(tmp_path, "later")
    if kind == "attributes":
        (workspace.path / ".gitattributes").write_text("* diff=sentinel\n")
    elif kind == "filter":
        git(repo, "config", "filter.sentinel.clean", str(script))
    elif kind == "promisor":
        (repo / ".git" / "objects" / "pack" / "later.promisor").write_text("")
    elif kind == "missing_index_blob":
        (workspace.path / "tracked.txt").write_text("staged-only\n")
        git(workspace.path, "add", "tracked.txt")
        oid = git(workspace.path, "rev-parse", ":tracked.txt").stdout.strip()
        (repo / ".git" / "objects" / oid[:2] / oid[2:]).unlink()
    else:
        (workspace.path / "link").symlink_to(tmp_path / "external")
    with pytest.raises((ValueError, RuntimeError)):
        manager.status(workspace)
    with pytest.raises((ValueError, RuntimeError)):
        manager.diff(workspace)
    assert not marker.exists()


def test_unsupported_git_version_fails_closed(repo, tmp_path, monkeypatch):
    original = GitWorkspaceManager._git
    def older(self, *args, **kwargs):
        if args == ("--version",):
            return GitReceipt("--version", 0, "git version 2.43.0\n", "", "0" * 64)
        return original(self, *args, **kwargs)
    monkeypatch.setattr(GitWorkspaceManager, "_git", older)
    with pytest.raises(RuntimeError, match="no unsafe fallback"):
        GitWorkspaceManager(repo, tmp_path / "worktrees")
    assert not (tmp_path / "worktrees").exists()


def test_reciprocal_registration_replacement_is_rejected(manager, tmp_path):
    workspace = manager.create("Registration")
    gitdir = Path(git(workspace.path, "rev-parse", "--absolute-git-dir").stdout.strip())
    (gitdir / "gitdir").write_text(str(tmp_path / "elsewhere" / ".git") + "\n")
    with pytest.raises((ValueError, RuntimeError)):
        manager.status(workspace)


def test_primary_administrative_directory_replacement_is_rejected(manager, repo, tmp_path):
    (repo / ".git").rename(tmp_path / "old-git-dir")
    (repo / ".git").mkdir()
    with pytest.raises(ValueError, match="identity changed"):
        manager.create("Replaced")


def test_new_manager_cannot_adopt_existing_root(repo, tmp_path):
    root = tmp_path / "worktrees"
    manager = GitWorkspaceManager(repo, root)
    workspace = manager.create("Existing")
    with pytest.raises(ValueError, match="overlaps"):
        GitWorkspaceManager(repo, root)
    assert manager.status(workspace).ok


def test_attributes_filter_sentinel_refused_before_checkout(repo, tmp_path):
    script, marker = sentinel(tmp_path, "smudge-checkout")
    (repo / ".gitattributes").write_text("* filter=sentinel\n")
    git(repo, "add", ".gitattributes")
    git(repo, "commit", "-m", "synthetic attributes")
    git(repo, "config", "filter.sentinel.smudge", str(script))
    with pytest.raises(ValueError):
        GitWorkspaceManager(repo, tmp_path / "worktrees")
    assert not marker.exists() and not (tmp_path / "worktrees").exists()


def test_textconv_attribute_activation_is_refused(manager, repo, tmp_path):
    script, marker = sentinel(tmp_path, "textconv-active")
    git(repo, "config", "diff.sentinel.textconv", str(script))
    workspace = manager.create("Textconv")
    (workspace.path / ".gitattributes").write_text("* diff=sentinel\n")
    (workspace.path / "tracked.txt").write_text("change\n")
    with pytest.raises(ValueError):
        manager.diff(workspace)
    assert not marker.exists()


def test_executable_identity_replacement_is_rejected(manager, monkeypatch):
    original = manager._identity
    def changed(path):
        current = original(path)
        if path == manager._executable:
            return current[0], current[1] + 1
        return current
    monkeypatch.setattr(manager, "_identity", changed)
    with pytest.raises(RuntimeError, match="executable was replaced"):
        manager.create("Changed executable")


def test_missing_required_switch_has_no_fallback(repo, tmp_path, monkeypatch):
    original = subprocess.run
    calls = []
    def unsupported(command, *args, **kwargs):
        if "--no-lazy-fetch" in command:
            calls.append(command)
            return subprocess.CompletedProcess(command, 129, "", "unknown option: --no-lazy-fetch")
        return original(command, *args, **kwargs)
    monkeypatch.setattr(subprocess, "run", unsupported)
    with pytest.raises(RuntimeError, match="unknown option"):
        GitWorkspaceManager(repo, tmp_path / "worktrees")
    assert len(calls) == 1 and not (tmp_path / "worktrees").exists()


def test_no_shell_in_any_profile_git_call(manager, monkeypatch):
    original = subprocess.run
    calls = []
    def observe(command, *args, **kwargs):
        calls.append((command, kwargs))
        return original(command, *args, **kwargs)
    monkeypatch.setattr(subprocess, "run", observe)
    workspace = manager.create("Observed")
    manager.status(workspace)
    manager.diff(workspace)
    assert calls
    for command, kwargs in calls:
        assert Path(command[0]).is_absolute() and command[0] == str(manager._executable)
        assert "--no-lazy-fetch" in command and "--no-optional-locks" in command
        assert kwargs.get("shell", False) is False
        assert kwargs["env"] == manager._environment
        assert kwargs["stdin"] == subprocess.DEVNULL


@pytest.mark.parametrize("drift", ["external_commit", "unrelated_history"])
def test_fixed_head_rejects_external_advancement_or_unrelated_reset(manager, repo, drift):
    workspace = manager.create("Pinned HEAD")
    if drift == "external_commit":
        (workspace.path / "tracked.txt").write_text("external advancement\n")
        git(workspace.path, "commit", "-am", "external advancement")
    else:
        tree = git(repo, "rev-parse", "HEAD^{tree}").stdout.strip()
        unrelated = git(repo, "commit-tree", tree, "-m", "unrelated synthetic root").stdout.strip()
        git(repo, "update-ref", f"refs/heads/{workspace.branch}", unrelated)
    assert git(workspace.path, "rev-parse", "HEAD").stdout.strip() != workspace.base_commit
    with pytest.raises(ValueError, match="pinned base changed"):
        manager.status(workspace)
    with pytest.raises(ValueError, match="pinned base changed"):
        manager.diff(workspace)
