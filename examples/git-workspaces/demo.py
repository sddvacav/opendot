"""Create two disposable synthetic worktrees; never accepts a user repository."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from opendot_engineering.git_workspace import GitWorkspaceManager


def run_demo() -> dict[str, object]:
    executable = shutil.which("git", path="/usr/local/bin:/usr/bin:/bin")
    if executable is None:
        raise RuntimeError("a trusted system Git >= 2.52.0 is required")
    executable = str(Path(executable).resolve(strict=True))
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": "/dev/null", "LC_ALL": "C",
           "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
           "GIT_CONFIG_SYSTEM": "/dev/null", "GIT_TERMINAL_PROMPT": "0"}
    # The fixture owns this entire temporary container. The manager has no remove.
    with tempfile.TemporaryDirectory(prefix="opendot-synthetic-git-") as container:
        root = Path(container)
        repo = root / "repository"
        repo.mkdir()
        def fixture_git(*args: str) -> str:
            return subprocess.run(
                [executable, "-c", "core.hooksPath=/dev/null", *args], cwd=repo,
                env=env, check=True, stdin=subprocess.DEVNULL, capture_output=True,
                text=True,
            ).stdout
        fixture_git("init", "-b", "main")
        fixture_git("config", "user.name", "Synthetic Fixture")
        fixture_git("config", "user.email", "fixture@example.invalid")
        (repo / "example.txt").write_text("baseline\n", encoding="utf-8")
        fixture_git("add", "example.txt")
        fixture_git("commit", "-m", "synthetic baseline")
        manager = GitWorkspaceManager(repo, root / "worktrees")
        first = manager.create("First example")
        second = manager.create("Second example")
        (first.path / "example.txt").write_text("first worktree edit\n", encoding="utf-8")
        (first.path / "untracked.txt").write_text("excluded from diff\n", encoding="utf-8")
        status, diff = manager.status(first), manager.diff(first)
        result = {
            "profile": "trusted-cooperative-local-git-create-status-diff",
            "git_version": manager.git_version,
            "shared_fixed_base": first.base_commit == second.base_commit,
            "first_has_tracked_and_untracked_status": " M example.txt" in status.stdout and "?? untracked.txt" in status.stdout,
            "diff_is_tracked_unstaged_only": "+first worktree edit" in diff.stdout and "untracked.txt" not in diff.stdout,
            "second_is_clean": manager.status(second).stdout == "" and manager.diff(second).stdout == "",
            "primary_checkout_unchanged": (repo / "example.txt").read_text() == "baseline\n",
            "receipt_ok": status.ok and diff.ok,
            "scientific_accepted": False,
            "device_control_authorized": False,
            "os_sandbox": False,
        }
        assert all(result[name] for name in ("shared_fixed_base", "first_has_tracked_and_untracked_status",
                   "diff_is_tracked_unstaged_only", "second_is_clean", "primary_checkout_unchanged", "receipt_ok"))
        return result


if __name__ == "__main__":
    print(json.dumps(run_demo(), indent=2))
