"""Controlled local create/status/diff profile of the project Git workspace owner.

Copyright 2026 OpenDot Engineering contributors. Licensed under Apache-2.0.
Modified extraction: execution environment, refusals, pinned bases, ownership
checks, and failure reporting are new; commit/remove are deliberately omitted.
See docs/git-workspaces.md and docs/PROVENANCE.md. This is not an OS sandbox.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path

__all__ = ["GitWorkspace", "GitReceipt", "GitWorkspaceManager", "GitWorkspaceCreationError"]


@dataclass(frozen=True)
class GitWorkspace:
    goal_id: str
    branch: str
    path: Path
    base_ref: str
    base_commit: str = ""


@dataclass(frozen=True)
class GitReceipt:
    action: str
    returncode: int
    stdout: str
    stderr: str
    digest: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class GitWorkspaceCreationError(RuntimeError):
    """One failed creation; residue is reported, never retried or removed.

    `residual_state` is best-effort observation, not a recovery instruction.
    Unknown values require operator inspection. The manager quarantines the slug.
    """

    def __init__(self, message: str, *, branch: str, path: Path,
                 residual_state: dict[str, bool | None]) -> None:
        super().__init__(message)
        self.branch = branch
        self.path = path
        self.residual_state = residual_state


@dataclass(frozen=True)
class _Binding:
    workspace: GitWorkspace
    fields: tuple[str, str, Path, str, str]
    path_identity: tuple[int, int]
    gitdir: Path
    gitdir_identity: tuple[int, int]


class GitWorkspaceManager:
    """One owner for trusted, cooperative, local primary-checkout worktrees.

    POSIX; Git >= 2.52 with required switches. Only create/status/diff are public
    operations. Git and host system executable directories must be trusted.
    Repository/worktree ancestors must remain cooperative for each operation;
    these checks do not prevent hostile concurrent filesystem replacement.
    """

    # Do not resolve Git from the caller's inherited PATH or GIT_EXEC_PATH.
    _SYSTEM_PATH = "/usr/local/bin:/usr/bin:/bin"
    _CONFIG = (
        "core.hooksPath=/dev/null", "core.fsmonitor=false",
        "core.attributesFile=/dev/null", "core.pager=cat", "core.askPass=",
        "diff.external=", "diff.autoRefreshIndex=false", "submodule.recurse=false", "fetch.recurseSubmodules=false",
        "protocol.allow=never", "credential.helper=", "credential.interactive=false",
        "maintenance.auto=false", "gc.auto=0", "core.untrackedCache=false",
    )

    def __init__(self, repository: str | Path, worktree_root: str | Path) -> None:
        if os.name != "posix":
            raise RuntimeError("controlled Git workspaces currently require POSIX")
        self.repository = self._path(repository, require_directory=True)
        self.worktree_root = self._path(worktree_root)
        self._common = self._path(self.repository / ".git", require_directory=True)
        self._repository_identity = self._identity(self.repository)
        self._common_identity = self._identity(self._common)
        self._root_identity: tuple[int, int] | None = None
        self._issued: dict[str, _Binding] = {}
        self._failed: set[str] = set()
        executable = shutil.which("git", path=self._SYSTEM_PATH)
        if executable is None:
            raise RuntimeError("Git is required in a trusted system executable directory")
        self._executable = Path(executable).resolve(strict=True)
        self._executable_identity = self._identity(self._executable)
        self._environment = {
            "PATH": self._SYSTEM_PATH, "HOME": "/dev/null", "XDG_CONFIG_HOME": "/dev/null",
            "LC_ALL": "C", "LANG": "C", "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_SYSTEM": "/dev/null", "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_ATTR_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0",
            "GIT_NO_REPLACE_OBJECTS": "1", "GIT_NO_LAZY_FETCH": "1",
            "GIT_OPTIONAL_LOCKS": "0", "GIT_ALLOW_PROTOCOL": "",
            "GIT_PROTOCOL_FROM_USER": "0",
        }
        version = self._require(self._git("--version")).strip()
        match = re.fullmatch(r"git version (\d+)\.(\d+)\.(\d+)(?:[.\-].*)?", version)
        if not match or tuple(map(int, match.groups())) < (2, 52, 0):
            raise RuntimeError("controlled profile requires Git >= 2.52.0; no unsafe fallback")
        self.git_version = version
        # All boundary options are already exercised by the version probe above.
        self._verify_repository()
        for other in (self.repository, self._common):
            if self._overlaps(self.worktree_root, other):
                raise ValueError("worktree root overlaps repository or administrative directory")
        for registered in self._registrations():
            if self._overlaps(self.worktree_root, Path(registered["worktree"])):
                raise ValueError("worktree root overlaps an existing registered worktree")
        self.worktree_root.mkdir(parents=True, exist_ok=True)
        self._path(self.worktree_root, require_directory=True)
        self._root_identity = self._identity(self.worktree_root)

    @staticmethod
    def _identity(path: Path) -> tuple[int, int]:
        value = path.stat(follow_symlinks=False)
        return value.st_dev, value.st_ino

    @staticmethod
    def _path(value: str | Path, *, require_directory: bool = False) -> Path:
        path = Path(os.path.abspath(value))
        # Reject aliases instead of silently resolving through any symlink.
        for part in (*reversed(path.parents), path):
            if part.is_symlink():
                raise ValueError("symlink path is outside the controlled profile")
        if require_directory and not path.is_dir():
            raise ValueError("expected an existing directory")
        return path

    @staticmethod
    def _overlaps(left: Path, right: Path) -> bool:
        return left == right or left in right.parents or right in left.parents

    @staticmethod
    def _slug(value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("goal id must be text")
        slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-.").lower()
        if not slug:
            raise ValueError("goal id cannot form branch name")
        return slug[:80]

    def _git(self, *args: str, cwd: Path | None = None, timeout: float = 120.0) -> GitReceipt:
        if self._identity(self._executable) != self._executable_identity:
            raise RuntimeError("resolved Git executable was replaced")
        command = [str(self._executable), "--no-pager", "--no-optional-locks", "--no-lazy-fetch"]
        for setting in self._CONFIG:
            command.extend(("-c", setting))
        completed = subprocess.run(
            (*command, *args), cwd=cwd or self.repository,
            env=self._environment, capture_output=True, text=True,
            encoding="utf-8", errors="surrogateescape", timeout=timeout, check=False,
            stdin=subprocess.DEVNULL,
        )
        payload = f"{args}\n{completed.returncode}\n{completed.stdout}\n{completed.stderr}".encode(
            "utf-8", errors="surrogateescape"
        )
        return GitReceipt(" ".join(args), completed.returncode, completed.stdout,
                          completed.stderr, hashlib.sha256(payload).hexdigest())

    @staticmethod
    def _require(receipt: GitReceipt) -> str:
        if not receipt.ok:
            raise RuntimeError(receipt.stderr or receipt.stdout or "Git command failed")
        return receipt.stdout

    @staticmethod
    def _scan(path: Path, *, checkout: bool) -> None:
        def fail(error: OSError) -> None:
            raise error
        for directory, dirs, files in os.walk(path, followlinks=False, onerror=fail):
            for name in (*dirs, *files):
                entry = Path(directory) / name
                mode = entry.lstat().st_mode
                if stat.S_ISLNK(mode) or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
                    raise ValueError("symlinks and special files are outside the controlled profile")
                if checkout and name.lower() in (".gitattributes", ".gitmodules"):
                    raise ValueError("attributes and submodules require a separately reviewed profile")
                if checkout and name.lower() == ".git":
                    if Path(directory) != path:
                        raise ValueError("nested repositories are outside the controlled profile")
                    if name in dirs:
                        dirs.remove(name)

    def _check_configuration(self) -> None:
        output = self._require(self._git("config", "--null", "--no-includes", "--file",
                                         str(self._common / "config"), "--list"))
        for entry in output.split("\0"):
            if not entry:
                continue
            key, _, value = entry.partition("\n")
            key = key.lower()
            forbidden = (
                key.startswith(("include.", "includeif.", "filter.", "submodule.", "extensions."))
                or key in ("core.worktree", "core.sparsecheckout", "core.sparsecheckoutcone",
                           "core.attributesfile", "core.alternaterefscommand")
                or (key.startswith("remote.") and key.endswith((".promisor", ".partialclonefilter")))
                or (key == "core.bare" and value.lower() != "false")
                or (key == "core.repositoryformatversion" and value != "0")
            )
            if forbidden:
                raise ValueError(f"unsupported repository configuration: {key}")
        for relative in ("commondir", "config.worktree", "shallow", "info/grafts", "info/attributes",
                         "objects/info/alternates", "objects/info/http-alternates", "info/sparse-checkout"):
            if os.path.lexists(self._common / relative):
                raise ValueError(f"unsupported repository metadata: {relative}")
        if any((self._common / "objects").rglob("*.promisor")):
            raise ValueError("promisor object stores are not supported")
        if self._require(self._git("for-each-ref", "--format=%(refname)", "refs/replace")):
            raise ValueError("replacement objects are not supported")

    def _verify_repository(self) -> None:
        for path, expected in ((self.repository, self._repository_identity),
                               (self._common, self._common_identity)):
            self._path(path, require_directory=True)
            if self._identity(path) != expected:
                raise ValueError("repository or administrative directory identity changed")
        if self._root_identity is not None:
            self._path(self.worktree_root, require_directory=True)
            if self._identity(self.worktree_root) != self._root_identity:
                raise ValueError("worktree root identity changed")
        self._scan(self._common, checkout=False)
        self._check_configuration()
        self._scan(self.repository, checkout=True)
        top = self._require(self._git("rev-parse", "--show-toplevel")).strip()
        common = self._require(self._git("rev-parse", "--path-format=absolute", "--git-common-dir")).strip()
        if Path(top) != self.repository or Path(common) != self._common:
            raise ValueError("repository is not the verified primary checkout")
        if self._require(self._git("rev-parse", "--is-bare-repository")).strip() != "false":
            raise ValueError("bare repository is outside the controlled profile")
        self._check_index(self.repository)

    @staticmethod
    def _check_entry(mode: str, name: str) -> None:
        if mode not in ("100644", "100755", "040000"):
            raise ValueError("symlinks, submodules, and special tree modes are not supported")
        if any(part.lower() in (".gitattributes", ".gitmodules", ".git") for part in name.split("/")):
            raise ValueError("attributes, submodules, and nested repositories are not supported")

    def _check_index(self, cwd: Path) -> None:
        output = self._require(self._git("ls-files", "--stage", "-z", cwd=cwd))
        for entry in output.split("\0"):
            if not entry:
                continue
            metadata, name = entry.split("\t", 1)
            mode, oid, stage = metadata.split(" ")
            self._check_entry(mode, name)
            if stage != "0":
                raise ValueError("unmerged index is outside the controlled profile")
            # Index blobs may not be reachable from HEAD (staged-only changes).
            self._require(self._git("cat-file", "-e", oid, cwd=cwd))

    def _check_commit(self, oid: str, *, cwd: Path | None = None) -> None:
        output = self._require(self._git("rev-list", "--objects", "--no-object-names",
                                         "--missing=print", oid, "--", cwd=cwd))
        if any(line.startswith("?") for line in output.splitlines()):
            raise ValueError("required commit history/tree/blob objects are missing locally")
        tree = self._require(self._git("ls-tree", "-r", "-t", "-z", "--full-tree", oid, cwd=cwd))
        for entry in tree.split("\0"):
            if entry:
                metadata, name = entry.split("\t", 1)
                self._check_entry(metadata.split(" ", 1)[0], name)

    def _registrations(self) -> list[dict[str, str]]:
        result = []
        output = self._require(self._git("worktree", "list", "--porcelain", "-z"))
        for record in output.strip("\0").split("\0\0"):
            fields: dict[str, str] = {}
            for field in record.split("\0"):
                key, _, value = field.partition(" ")
                if key in fields:
                    raise ValueError("ambiguous worktree registration")
                fields[key] = value
            if "worktree" not in fields:
                raise ValueError("invalid worktree registration")
            result.append(fields)
        return result

    def _branch_exists(self, branch: str) -> bool:
        receipt = self._git("show-ref", "--verify", "--quiet", f"refs/heads/{branch}")
        if receipt.returncode not in (0, 1):
            self._require(receipt)
        return receipt.returncode == 0

    def _inspect_workspace(self, workspace: GitWorkspace, *, expected_head: str | None = None) -> Path:
        path = self._path(workspace.path, require_directory=True)
        if path.parent != self.worktree_root:
            raise ValueError("workspace escaped its manager root")
        self._scan(path, checkout=True)
        if not (path / ".git").is_file():
            raise ValueError("workspace is not a linked checkout")
        gitdir = Path(self._require(self._git("rev-parse", "--absolute-git-dir", cwd=path)).strip())
        self._path(gitdir, require_directory=True)
        if gitdir.parent != self._common / "worktrees":
            raise ValueError("workspace administrative ownership changed")
        common = self._require(self._git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=path)).strip()
        top = self._require(self._git("rev-parse", "--show-toplevel", cwd=path)).strip()
        if Path(common) != self._common or Path(top) != path:
            raise ValueError("workspace repository ownership changed")
        if Path((gitdir / "gitdir").read_text(encoding="utf-8").strip()) != path / ".git":
            raise ValueError("workspace reciprocal registration changed")
        branch = self._require(self._git("symbolic-ref", "-q", "HEAD", cwd=path)).strip()
        head = self._require(self._git("rev-parse", "--verify", "HEAD^{commit}", cwd=path)).strip()
        if branch != f"refs/heads/{workspace.branch}" or (expected_head and head != expected_head):
            raise ValueError("workspace branch or pinned base changed")
        registered = [record for record in self._registrations() if Path(record["worktree"]) == path]
        if len(registered) != 1 or registered[0].get("branch") != branch or registered[0].get("HEAD") != head:
            raise ValueError("workspace registration is not owned by this manager")
        if "prunable" in registered[0] or "bare" in registered[0] or "detached" in registered[0]:
            raise ValueError("workspace registration is not active")
        self._check_index(path)
        self._check_commit(head, cwd=path)
        return gitdir

    def _validate(self, workspace: GitWorkspace) -> None:
        if not isinstance(workspace, GitWorkspace):
            raise ValueError("workspace was not issued by this manager")
        binding = self._issued.get(workspace.branch)
        fields = (workspace.goal_id, workspace.branch, workspace.path, workspace.base_ref, workspace.base_commit)
        if binding is None or binding.workspace is not workspace or binding.fields != fields:
            raise ValueError("workspace was not issued by this manager or its record changed")
        self._verify_repository()
        self._path(workspace.path, require_directory=True)
        if self._identity(workspace.path) != binding.path_identity:
            raise ValueError("workspace path identity changed")
        gitdir = self._inspect_workspace(workspace, expected_head=workspace.base_commit)
        if gitdir != binding.gitdir or self._identity(gitdir) != binding.gitdir_identity:
            raise ValueError("workspace administrative identity changed")

    def create(self, goal_id: str, *, base_ref: str = "HEAD") -> GitWorkspace:
        self._verify_repository()
        slug = self._slug(goal_id)
        branch = f"agent/{slug}"
        path = self.worktree_root / slug
        self._require(self._git("check-ref-format", f"refs/heads/{branch}"))
        if not isinstance(base_ref, str) or not base_ref or base_ref.startswith("-"):
            raise ValueError("base_ref must be a plain local ref name or full commit OID")
        self._require(self._git("check-ref-format", "--allow-onelevel", base_ref))
        resolved = self._git("rev-parse", "--verify", "--end-of-options", f"{base_ref}^{{commit}}")
        oid = self._require(resolved).strip()
        if resolved.stderr or not re.fullmatch(r"[0-9a-f]{40}", oid):
            raise ValueError("base_ref is ambiguous or not a supported full SHA-1 commit OID")
        self._check_commit(oid)
        if slug in self._failed:
            raise ValueError("a previous creation failed; inspect residue with an independent operator")
        if os.path.lexists(path) or self._branch_exists(branch):
            raise FileExistsError("workspace path or branch already exists; no reuse or alternate name")
        for record in self._registrations():
            if self._overlaps(path, Path(record["worktree"])):
                raise FileExistsError("workspace path overlaps a registered checkout")
        workspace = GitWorkspace(goal_id, branch, path, base_ref, oid)
        try:
            # Exactly one creation attempt, using only the immutable resolved OID.
            self._require(self._git("worktree", "add", "-b", branch, str(path), oid))
            self._verify_repository()
            gitdir = self._inspect_workspace(workspace, expected_head=oid)
            self._issued[branch] = _Binding(
                workspace, (goal_id, branch, path, base_ref, oid), self._identity(path),
                gitdir, self._identity(gitdir),
            )
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            self._failed.add(slug)
            state: dict[str, bool | None] = {"path_exists": None,
                                           "branch_exists": None, "registered": None}
            try:
                path.lstat()
                state["path_exists"] = True
            except FileNotFoundError:
                state["path_exists"] = False
            except OSError:
                # An inaccessible path is unknown, not evidence of absence.
                pass
            try:
                self._verify_repository()
                state["branch_exists"] = self._branch_exists(branch)
                state["registered"] = any(Path(r["worktree"]) == path for r in self._registrations())
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
                pass
            raise GitWorkspaceCreationError(
                f"worktree creation failed; no retry or cleanup performed: {error}",
                branch=branch, path=path, residual_state=state,
            ) from error
        return workspace

    def status(self, workspace: GitWorkspace) -> GitReceipt:
        """Porcelain v1; no optional index refresh, no recursive submodule inspection."""
        self._validate(workspace)
        receipt = self._git("status", "--porcelain=v1", "--ignore-submodules=all", cwd=workspace.path)
        self._validate(workspace)
        return receipt

    def diff(self, workspace: GitWorkspace) -> GitReceipt:
        """Tracked unstaged worktree-vs-index diff; excludes staged-only/untracked content."""
        self._validate(workspace)
        receipt = self._git("diff", "--binary", "--no-ext-diff", "--no-textconv",
                            "--ignore-submodules=all", "--", cwd=workspace.path)
        self._validate(workspace)
        return receipt
