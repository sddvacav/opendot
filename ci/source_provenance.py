"""Source-only tracked-file inventory; no rights or release clearance is inferred."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys

from opendot_engineering.adapters import source_audit as audit
from opendot_engineering.git_workspace import GitWorkspaceManager

SCHEMA = "opendot.source-provenance-inventory.v1"
MAX_FILES = 1024
MAX_INDEX_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024
MAX_CONFIG_BYTES = 64 * 1024
SOURCE_POINTERS = ("LICENSE", "NOTICE", "docs/PROVENANCE.md")
BRAND_POINTER = "assets/brand/NOTICE"
KINDS = ("code", "test", "docs", "asset", "license", "config")


def _encoded(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _path(value):
    parts = audit._relative(value)
    audit._require(not any(ord(c) == 127 for c in value), "INVALID_LOCAL_PATH")
    audit._require(not any(p.lower() in {".git", ".gitmodules", ".gitattributes"} for p in parts),
                   "UNSUPPORTED_TRACKED_GIT_PATH")
    return parts


def classify_path(value):
    """An explicit, intentionally incomplete policy: unknown kinds refuse, not omit."""
    parts = _path(value)
    suffix = PurePosixPath(value).suffix.lower()
    if value in {"LICENSE", "NOTICE", BRAND_POINTER}:
        return "license"
    if parts[0] == "tests" and suffix in {".py", ".json", ".txt", ".md"}:
        return "test"
    if parts[0] == "examples" and suffix == ".csv":
        return "test"
    if suffix == ".md":
        return "docs"
    if parts[0] == "docs" and (suffix in {".json", ".csv"} or parts[-1] == "SHA256SUMS"):
        return "docs"
    if parts[0] in {"src", "ci", "examples"} and suffix == ".py":
        return "code"
    if parts[0] == "assets" and suffix in {".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico"}:
        return "asset"
    if value in {".gitignore", "pyproject.toml"}:
        return "config"
    if value.startswith(".github/workflows/") and suffix in {".yml", ".yaml"}:
        return "config"
    if parts[0] in {"ci", "examples"} and suffix in {".json", ".txt"}:
        return "config"
    raise audit.AuditRejected("UNCLASSIFIED_SOURCE_PATH")


def _git_environment():
    # Same trusted-system and deny-side-effect policy as the existing Git owner.
    # This source-only reader does not instantiate a manager or create worktrees.
    return {
        "PATH": GitWorkspaceManager._SYSTEM_PATH,
        "HOME": "/dev/null", "XDG_CONFIG_HOME": "/dev/null", "LC_ALL": "C", "LANG": "C",
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_SYSTEM": "/dev/null", "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_ATTR_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0", "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_NO_LAZY_FETCH": "1", "GIT_OPTIONAL_LOCKS": "0", "GIT_ALLOW_PROTOCOL": "",
        "GIT_PROTOCOL_FROM_USER": "0",
    }


def _trusted_git():
    executable = shutil.which("git", path=GitWorkspaceManager._SYSTEM_PATH)
    audit._require(executable is not None, "TRUSTED_GIT_UNAVAILABLE")
    try:
        path = Path(executable).resolve(strict=True)
        info = path.stat()
        audit._require(stat.S_ISREG(info.st_mode), "TRUSTED_GIT_UNAVAILABLE")
        return path, (info.st_dev, info.st_ino)
    except OSError:
        raise audit.AuditRejected("TRUSTED_GIT_UNAVAILABLE") from None


def _git(executable, identity, arguments, *, cwd, input_data=None):
    try:
        info = executable.stat()
        audit._require((info.st_dev, info.st_ino) == identity, "GIT_EXECUTABLE_CHANGED")
        command = [str(executable), "--no-pager", "--no-optional-locks", "--no-lazy-fetch"]
        for setting in GitWorkspaceManager._CONFIG:
            command.extend(("-c", setting))
        completed = subprocess.run(
            [*command, *arguments], cwd=cwd, env=_git_environment(),
            input=input_data, stdin=subprocess.DEVNULL if input_data is None else None,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15, check=False,
        )
        # Git output is never relayed: it can contain root/config/user data.
        audit._require(completed.returncode == 0 and not completed.stderr, "GIT_ENUMERATION_REJECTED")
        audit._require(len(completed.stdout) <= MAX_INDEX_BYTES, "GIT_OUTPUT_TOO_LARGE")
        return completed.stdout
    except (OSError, subprocess.SubprocessError):
        raise audit.AuditRejected("GIT_ENUMERATION_UNAVAILABLE") from None


def _configuration_safe(data):
    """Review parsed keys without exposing values or accepting includes/redirects."""
    try:
        entries = data.decode("utf-8").split("\0")
    except UnicodeError:
        raise audit.AuditRejected("GIT_CONFIGURATION_REJECTED") from None
    harmless_core = {"core.filemode", "core.logallrefupdates", "core.ignorecase",
                     "core.precomposeunicode", "core.symlinks", "core.abbrev"}
    for entry in entries:
        if not entry:
            continue
        key, separator, value = entry.partition("\n")
        key = key.lower()
        audit._require(bool(separator), "GIT_CONFIGURATION_REJECTED")
        allowed = (
            key in harmless_core
            or (key == "core.repositoryformatversion" and value == "0")
            or (key == "core.bare" and value.lower() == "false")
            or key in {"user.name", "user.email"}
            or re.fullmatch(r"remote\.[^.]+\.(?:url|fetch)", key) is not None
            or re.fullmatch(r"branch\.[^.]+\.(?:remote|merge)", key) is not None
        )
        audit._require(allowed, "GIT_CONFIGURATION_REJECTED")


def _tracked_entries(root, root_fd):
    git_fd = audit._root_fd(root / ".git")  # Primary checkout only; no .git links/files.
    os.close(git_fd)
    try:
        # Reuse the existing non-following administrative metadata scan. It reads
        # entry types, not history/object contents, and rejects every symlink.
        GitWorkspaceManager._scan(root / ".git", checkout=False)
    except (OSError, ValueError):
        raise audit.AuditRejected("GIT_METADATA_UNSAFE") from None
    for relative in ("commondir", "config.worktree", "shallow", "info/grafts", "info/attributes",
                     "objects/info/alternates", "objects/info/http-alternates", "info/sparse-checkout"):
        audit._require(not os.path.lexists(root / ".git" / relative), "GIT_METADATA_UNSUPPORTED")
    # Canonical descriptor reads reject index/config/HEAD links before Git runs.
    config = audit._read(root_fd, ".git/config", MAX_CONFIG_BYTES)
    audit._read(root_fd, ".git/HEAD", 4096)
    before = audit._read(root_fd, ".git/index", MAX_INDEX_BYTES)
    executable, identity = _trusted_git()
    version = _git(executable, identity, ["--version"], cwd=Path("/"))
    match = re.fullmatch(rb"git version (\d+)\.(\d+)\.(\d+)(?:[.\-][^\n]+)?\n?", version)
    audit._require(match is not None and tuple(int(n) for n in match.groups()) >= (2, 52, 0),
                   "GIT_VERSION_UNSUPPORTED")
    # Parse captured config on stdin outside the repository, with includes off.
    # No repository include file or inherited/global configuration is consulted.
    parsed_config = _git(executable, identity,
                         ["config", "--null", "--no-includes", "--file", "-", "--list"],
                         cwd=Path("/"), input_data=config)
    _configuration_safe(parsed_config)
    raw = _git(executable, identity, ["ls-files", "--stage", "--full-name", "-z"], cwd=root)
    audit._require(audit._read(root_fd, ".git/index", MAX_INDEX_BYTES) == before, "INDEX_CHANGED")
    try:
        records = raw.decode("utf-8").split("\0")
    except UnicodeError:
        raise audit.AuditRejected("INVALID_INDEX_PATH_ENCODING") from None
    audit._require(records[-1] == "" and 0 < len(records) - 1 <= MAX_FILES, "INVALID_INDEX_COUNT")
    rows, seen = [], set()
    for record in records[:-1]:
        metadata, separator, path = record.partition("\t")
        audit._require(bool(separator), "INVALID_INDEX_RECORD")
        fields = metadata.split(" ")
        audit._require(len(fields) == 3, "INVALID_INDEX_RECORD")
        mode, oid, stage = fields
        audit._require(mode in {"100644", "100755"}, "UNSUPPORTED_INDEX_MODE")
        audit._require(stage == "0", "UNMERGED_INDEX")
        audit._hash(oid, 40)
        _path(path)
        audit._require(path not in seen, "DUPLICATE_INDEX_PATH")
        seen.add(path)
        rows.append({"path": path, "mode": mode, "blob_sha1": oid})
    return sorted(rows, key=lambda row: row["path"]), before


def inventory_source(root):
    """Observe indexed working bytes, not a commit, authorship, rights or secrets."""
    root = Path(root).absolute()
    root_fd = audit._root_fd(root)
    try:
        entries, index_before = _tracked_entries(root, root_fd)
        paths = {row["path"] for row in entries}
        audit._require(set(SOURCE_POINTERS) | {BRAND_POINTER} <= paths, "SOURCE_POINTER_UNAVAILABLE")
        contents, items, total = {}, [], 0
        for row in entries:
            kind = classify_path(row["path"])
            data = audit._read(root_fd, row["path"], audit.MAX_SOURCE_BYTES)
            total += len(data)
            audit._require(total <= MAX_TOTAL_BYTES, "SOURCE_TOTAL_TOO_LARGE")
            digest = audit._sha256(data)
            contents[row["path"]] = digest
            matches = audit._git_blob(data) == row["blob_sha1"]
            items.append({
                "path": row["path"], "sha256": digest, "bytes": len(data), "kind": kind,
                "index_mode": row["mode"], "index_blob_sha1": row["blob_sha1"],
                "working_bytes_match_index_blob": matches,
                "evidence_status": "INDEX_BLOB_AND_WORKING_BYTES_MATCH" if matches else "WORKING_BYTES_DIFFER_FROM_INDEX",
                "rights_status": "NOT_VERIFIED", "authorship_status": "NOT_VERIFIED",
                "private_data_review_status": "NOT_VERIFIED",
            })
        audit._require(audit._read(root_fd, ".git/index", MAX_INDEX_BYTES) == index_before, "INDEX_CHANGED")
        for item in items:
            pointers = [*SOURCE_POINTERS]
            if item["path"].startswith("assets/brand/"):
                pointers.append(BRAND_POINTER)
            item["source_pointers"] = [{"path": p, "sha256": contents[p],
                                        "evidence_status": "DECLARATION_REFERENCE_ONLY"} for p in pointers]
        return {
            "schema": SCHEMA, "accepted": True, "scope": "CURRENT_INDEXED_WORKING_FILE_BYTES_ONLY",
            "indexed_entries_sha256": audit._sha256(_encoded(entries)),
            "counts": {"tracked_files": len(items), "total_bytes": total,
                       "working_index_mismatches": sum(not i["working_bytes_match_index_blob"] for i in items),
                       "by_kind": {kind: sum(i["kind"] == kind for i in items) for kind in KINDS}},
            "items": items, "untracked_files": "EXCLUDED_NOT_ENUMERATED",
            "commit_binding": "NOT_VERIFIED", "rights_clearance": "NOT_VERIFIED",
            "authorship_verification": "NOT_VERIFIED", "privacy_clearance": "NOT_VERIFIED",
            "scientific_accepted": False, "scientific_status": "NOT_EVALUATED",
            "device_control_accepted": False, "independent_review_status": "NOT_EVALUATED",
            "limits": [
                "Index membership and observed working bytes only; staged or unstaged changes are not a commit binding",
                "Untracked files, Git history, dependencies and external/private origins are not inventoried",
                "Notice pointers record existing declarations, not verified authorship, rights, privacy or legal clearance",
                "Trusted cooperative POSIX primary checkout and trusted system Git 2.52+; no hostile-concurrency guarantee",
                "Sequential reads are not an atomic filesystem snapshot; no source, index, configuration or history is written",
                "Not a full SBOM, secret scanner, scientific review, publication permission or release acceptance",
            ],
        }
    finally:
        os.close(root_fd)


def _output_parent(root, output):
    root, output = Path(root).absolute(), Path(output).absolute()
    audit._require(output != root and root not in output.parents, "OUTPUT_INSIDE_SOURCE")
    audit._relative(output.name)
    fd = audit._root_fd(output.parent)
    try:
        try:
            os.stat(output.name, dir_fd=fd, follow_symlinks=False)
        except FileNotFoundError:
            return fd, output.name
        raise audit.AuditRejected("OUTPUT_EXISTS")
    except BaseException:
        os.close(fd)
        raise


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise audit.AuditRejected("ARGUMENTS_INVALID")


def main(argv=None):
    parser = _Parser(prog="source_provenance", description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="trusted primary source checkout")
    parser.add_argument("--output", type=Path, required=True, help="new JSON file outside the source root")
    output_fd = None
    try:
        args = parser.parse_args(argv)
        output_fd, name = _output_parent(args.root, args.output)
        receipt = inventory_source(args.root)
        data = _encoded(receipt)
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=output_fd)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        print(json.dumps({"accepted": True, "tracked_files": receipt["counts"]["tracked_files"],
                          "manifest_sha256": audit._sha256(data)}, sort_keys=True))
        return 0
    except (audit.AuditRejected, OSError, ValueError, TypeError) as exc:
        code = exc.code if isinstance(exc, audit.AuditRejected) else "LOCAL_OPERATION_UNAVAILABLE"
        print("SOURCE_PROVENANCE_REJECTED: " + code, file=sys.stderr)
        return 1
    finally:
        if output_fd is not None:
            os.close(output_fd)


if __name__ == "__main__":
    raise SystemExit(main())
