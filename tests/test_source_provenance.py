"""Synthetic local-index tests; no commits, external origins or native backends."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("source_provenance", ROOT / "ci/source_provenance.py")
provenance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(provenance)


def git(root, *args, input_data=None):
    executable, _ = provenance._trusted_git()
    result = subprocess.run([str(executable), *args], cwd=root,
                            env=provenance._git_environment(), input=input_data,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return result.stdout


@pytest.fixture
def repository(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    git(root, "init", "--quiet", "--object-format=sha1")
    files = {"LICENSE": b"Synthetic license declaration, not legal clearance.\n",
             "NOTICE": b"Synthetic fixture attribution.\n",
             "docs/PROVENANCE.md": b"# Synthetic provenance declaration\n",
             "assets/brand/NOTICE": b"Synthetic artwork notice.\n",
             "assets/brand/mark.svg": b"<svg/>\n",
             "README.md": b"# Synthetic project\n",
             "src/example.py": b"VALUE = 1\n",
             "tests/test_example.py": b"def test_example(): assert True\n",
             "pyproject.toml": b"[project]\nname = 'synthetic-fixture'\n"}
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    git(root, "add", ".")
    return root


def reject(root, code):
    with pytest.raises(provenance.audit.AuditRejected, match="^" + code + "$"):
        provenance.inventory_source(root)


def test_every_indexed_file_has_deterministic_kind_hash_and_unknown_rights(repository, tmp_path):
    before = {p.relative_to(repository): p.read_bytes() for p in repository.rglob("*") if p.is_file()}
    first = provenance.inventory_source(repository)
    assert first == provenance.inventory_source(repository)
    tracked = set(git(repository, "ls-files", "-z").decode().strip("\0").split("\0"))
    assert [i["path"] for i in first["items"]] == sorted(tracked)
    assert first["counts"]["tracked_files"] == len(tracked) == 9
    assert set(i["kind"] for i in first["items"]) == set(provenance.KINDS)
    for row in first["items"]:
        assert row["sha256"] == provenance.audit._sha256((repository / row["path"]).read_bytes())
        assert row["evidence_status"] == "INDEX_BLOB_AND_WORKING_BYTES_MATCH"
        assert row["rights_status"] == row["authorship_status"] == row["private_data_review_status"] == "NOT_VERIFIED"
        assert len(row["source_pointers"]) == (4 if row["path"].startswith("assets/brand/") else 3)
        for pointer in row["source_pointers"]:
            assert pointer["sha256"] == provenance.audit._sha256((repository / pointer["path"]).read_bytes())
            assert pointer["evidence_status"] == "DECLARATION_REFERENCE_ONLY"
    assert first["counts"]["working_index_mismatches"] == 0
    assert first["commit_binding"] == first["rights_clearance"] == first["privacy_clearance"] == "NOT_VERIFIED"
    assert first["scientific_accepted"] is first["device_control_accepted"] is False
    assert first["scientific_status"] == first["independent_review_status"] == "NOT_EVALUATED"
    assert "source_commit" not in first
    assert str(tmp_path) not in json.dumps(first)
    after = {p.relative_to(repository): p.read_bytes() for p in repository.rglob("*") if p.is_file()}
    assert before == after


def test_working_change_is_hashed_and_flagged_without_commit_promotion(repository):
    before = provenance.inventory_source(repository)
    (repository / "src/example.py").write_bytes(b"VALUE = 2\n")
    after = provenance.inventory_source(repository)
    left = next(i for i in before["items"] if i["path"] == "src/example.py")
    right = next(i for i in after["items"] if i["path"] == "src/example.py")
    assert left["sha256"] != right["sha256"]
    assert left["index_blob_sha1"] == right["index_blob_sha1"]
    assert right["working_bytes_match_index_blob"] is False
    assert right["evidence_status"] == "WORKING_BYTES_DIFFER_FROM_INDEX"
    assert after["counts"]["working_index_mismatches"] == 1
    assert before["indexed_entries_sha256"] == after["indexed_entries_sha256"]
    assert after["commit_binding"] == "NOT_VERIFIED"
    git(repository, "add", "src/example.py")
    staged = provenance.inventory_source(repository)
    assert staged["counts"]["working_index_mismatches"] == 0
    assert staged["indexed_entries_sha256"] != before["indexed_entries_sha256"]
    assert staged["commit_binding"] == "NOT_VERIFIED"


def test_untracked_files_are_explicitly_excluded_without_reading(repository, monkeypatch):
    (repository / "untracked-secret.bin").write_bytes(b"synthetic, not a real secret")
    original = provenance.audit._read
    def guarded(fd, name, limit):
        assert name != "untracked-secret.bin"
        return original(fd, name, limit)
    monkeypatch.setattr(provenance.audit, "_read", guarded)
    receipt = provenance.inventory_source(repository)
    assert receipt["untracked_files"] == "EXCLUDED_NOT_ENUMERATED"
    assert all(i["path"] != "untracked-secret.bin" for i in receipt["items"])


@pytest.mark.parametrize(("path", "kind"), [
    ("LICENSE", "license"), ("NOTICE", "license"), ("assets/brand/NOTICE", "license"),
    ("src/package/module.py", "code"), ("ci/check.py", "code"), ("examples/demo.py", "code"),
    ("tests/test_a.py", "test"), ("tests/data.json", "test"), ("tests/README.md", "test"),
    ("examples/measurement-review/batch.csv", "test"),
    ("docs/research/oss-workflows/frozen-oracle/measurements.csv", "docs"),
    ("docs/research/oss-workflows/SHA256SUMS", "docs"), ("docs/SHA256SUMS", "docs"),
    ("docs/data.json", "docs"), ("README.zh-CN.md", "docs"), ("assets/brand/README.md", "docs"),
    ("assets/brand/mark.svg", "asset"), ("assets/image.png", "asset"),
    (".gitignore", "config"), ("pyproject.toml", "config"), (".github/workflows/test.yml", "config"),
    ("ci/nodes.txt", "config"), ("examples/input.json", "config"),
])
def test_classification_policy(path, kind):
    assert provenance.classify_path(path) == kind


@pytest.mark.parametrize("path", ["new.bin", "run.py", "src/unclassified.data", "docs/unknown.docx"])
def test_unclassified_tracked_file_refuses_entire_inventory(repository, path):
    target = repository / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"synthetic unknown")
    git(repository, "add", path)
    reject(repository, "UNCLASSIFIED_SOURCE_PATH")


@pytest.mark.parametrize("path", ["../escape.py", "/absolute.py", "src//empty.py", "src/./dot.py",
                                  "src/a\\b.py", "src/a:b.py", "src/new\nline.py", "src/del\x7f.py"])
def test_unsafe_relative_path_refuses(path):
    with pytest.raises(provenance.audit.AuditRejected, match="INVALID_LOCAL_PATH"):
        provenance.classify_path(path)


@pytest.mark.parametrize("path", [".git/config", "src/.GIT/config", ".gitmodules", "src/.gitattributes"])
def test_git_internal_paths_never_classified(path):
    with pytest.raises(provenance.audit.AuditRejected, match="UNSUPPORTED_TRACKED_GIT_PATH"):
        provenance.classify_path(path)


def test_deleted_indexed_file_refuses(repository):
    (repository / "README.md").unlink()
    reject(repository, "LOCAL_INPUT_UNAVAILABLE_OR_UNSAFE")


def test_missing_notice_refuses_instead_of_fabricating_pointer(repository):
    git(repository, "update-index", "--force-remove", "NOTICE")
    reject(repository, "SOURCE_POINTER_UNAVAILABLE")


def test_indexed_symlink_refuses_without_following_target(repository, tmp_path):
    target = tmp_path / "outside.txt"
    target.write_text("synthetic outside bytes")
    link = repository / "docs/link.md"
    link.symlink_to(target)
    git(repository, "add", "docs/link.md")
    reject(repository, "UNSUPPORTED_INDEX_MODE")


def test_replaced_working_file_and_parent_symlinks_refuse(repository, tmp_path):
    target = tmp_path / "outside"
    target.mkdir()
    (target / "example.py").write_bytes(b"synthetic outside")
    (repository / "src/example.py").unlink()
    (repository / "src").rmdir()
    (repository / "src").symlink_to(target, target_is_directory=True)
    reject(repository, "LOCAL_INPUT_UNAVAILABLE_OR_UNSAFE")


def test_submodule_mode_and_unmerged_stage_refuse(repository):
    oid = git(repository, "hash-object", "README.md").decode().strip()
    git(repository, "update-index", "--add", "--cacheinfo", "160000," + oid + ",submodule")
    reject(repository, "UNSUPPORTED_INDEX_MODE")
    git(repository, "update-index", "--force-remove", "submodule")
    git(repository, "update-index", "--index-info", input_data=("100644 " + oid + " 1\tconflict.md\n").encode())
    reject(repository, "UNMERGED_INDEX")


@pytest.mark.parametrize("metadata", ["index", "config", "HEAD"])
def test_administrative_symlink_refuses_before_git_or_target_read(repository, tmp_path, metadata, monkeypatch):
    inside = repository / ".git" / metadata
    outside = tmp_path / "outside-administration"
    outside.write_bytes(inside.read_bytes())
    inside.unlink()
    inside.symlink_to(outside)
    def forbidden(*args, **kwargs):
        pytest.fail("Git must not run before administrative symlink rejection")
    monkeypatch.setattr(provenance, "_trusted_git", forbidden)
    reject(repository, "GIT_METADATA_UNSAFE")


def test_root_symlink_and_linked_checkout_refuse(repository, tmp_path):
    alias = tmp_path / "alias"
    alias.symlink_to(repository, target_is_directory=True)
    reject(alias, "ROOT_UNAVAILABLE")
    fake = tmp_path / "linked"
    fake.mkdir()
    (fake / ".git").write_text("gitdir: " + str(repository / ".git") + "\n")
    reject(fake, "ROOT_UNAVAILABLE")


@pytest.mark.parametrize(("key", "value"), [("include.path", "outside-config"), ("core.worktree", "/outside"),
    ("core.fsmonitor", "synthetic-command"), ("filter.synthetic.clean", "synthetic-command"),
    ("extensions.worktreeConfig", "true"), ("core.repositoryformatversion", "1")])
def test_unsafe_configuration_refuses_before_index_enumeration(repository, monkeypatch, key, value):
    git(repository, "config", key, value)
    original = provenance._git
    def guard(executable, identity, arguments, **kwargs):
        assert arguments[0] != "ls-files", "unsafe configuration reached index enumeration"
        return original(executable, identity, arguments, **kwargs)
    monkeypatch.setattr(provenance, "_git", guard)
    reject(repository, "GIT_CONFIGURATION_REJECTED")


def test_inherited_git_environment_and_path_are_not_used(repository, tmp_path, monkeypatch):
    malicious = tmp_path / "fake-bin"
    malicious.mkdir()
    (malicious / "git").write_text("#!/bin/sh\nexit 91\n")
    (malicious / "git").chmod(0o755)
    monkeypatch.setenv("PATH", str(malicious))
    monkeypatch.setenv("GIT_INDEX_FILE", str(tmp_path / "not-the-index"))
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "not-the-repo"))
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "include.path")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", str(tmp_path / "outside-config"))
    assert provenance.inventory_source(repository)["accepted"] is True


def test_index_change_during_inventory_refuses(repository, monkeypatch):
    original = provenance.audit._read
    reads = 0
    def changing(fd, name, limit):
        nonlocal reads
        data = original(fd, name, limit)
        if name == ".git/index":
            reads += 1
            if reads >= 3:
                return data + b"synthetic-change"
        return data
    monkeypatch.setattr(provenance.audit, "_read", changing)
    reject(repository, "INDEX_CHANGED")


def test_file_and_total_caps_refuse_without_omitting(repository, monkeypatch):
    monkeypatch.setattr(provenance.audit, "MAX_SOURCE_BYTES", 5)
    reject(repository, "INPUT_TOO_LARGE")
    monkeypatch.setattr(provenance.audit, "MAX_SOURCE_BYTES", 2 * 1024 * 1024)
    monkeypatch.setattr(provenance, "MAX_TOTAL_BYTES", 5)
    reject(repository, "SOURCE_TOTAL_TOO_LARGE")


def test_cli_writes_fresh_outside_json_with_no_absolute_path(repository, tmp_path, capsys):
    output = tmp_path / "inventory.json"
    assert provenance.main(["--root", str(repository), "--output", str(output)]) == 0
    captured = capsys.readouterr()
    summary = json.loads(captured.out)
    assert captured.err == ""
    assert summary["manifest_sha256"] == provenance.audit._sha256(output.read_bytes())
    assert output.read_bytes() == provenance._encoded(provenance.inventory_source(repository))
    assert str(tmp_path) not in output.read_text() + captured.out
    assert provenance.main(["--root", str(repository), "--output", str(output)]) == 1
    assert capsys.readouterr().err == "SOURCE_PROVENANCE_REJECTED: OUTPUT_EXISTS\n"


@pytest.mark.parametrize("case", ["inside", "parent_symlink", "output_symlink"])
def test_cli_unsafe_output_refuses_without_overwrite(repository, tmp_path, capsys, case):
    protected = repository / "README.md"
    original = protected.read_bytes()
    if case == "inside":
        output = repository / "inventory.json"
    elif case == "parent_symlink":
        alias = tmp_path / "output-alias"
        alias.symlink_to(repository, target_is_directory=True)
        output = alias / "inventory.json"
    else:
        output = tmp_path / "inventory-link.json"
        output.symlink_to(protected)
    assert provenance.main(["--root", str(repository), "--output", str(output)]) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and str(tmp_path) not in captured.err
    assert protected.read_bytes() == original
    assert not (repository / "inventory.json").exists()


def test_cli_errors_do_not_echo_private_root_or_arguments(tmp_path, capsys):
    assert provenance.main(["--root", str(tmp_path / "private-root"),
                            "--output", str(tmp_path / "result.json")]) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and str(tmp_path) not in captured.err
    assert not (tmp_path / "result.json").exists()
    assert provenance.main(["--unexpected-private-argument"]) == 1
    assert capsys.readouterr().err == "SOURCE_PROVENANCE_REJECTED: ARGUMENTS_INVALID\n"


def test_current_source_is_complete_without_importing_candidate_files():
    receipt = provenance.inventory_source(ROOT)
    expected = set(git(ROOT, "ls-files", "-z").decode().strip("\0").split("\0"))
    assert set(i["path"] for i in receipt["items"]) == expected
    assert receipt["counts"]["tracked_files"] >= 164
    assert receipt["rights_clearance"] == receipt["privacy_clearance"] == "NOT_VERIFIED"


def test_changed_notice_changes_all_bound_pointers_without_claiming_rights(repository):
    before = provenance.inventory_source(repository)
    (repository / "NOTICE").write_bytes(b"A changed synthetic declaration.\n")
    after = provenance.inventory_source(repository)
    before_hash = next(i["sha256"] for i in before["items"] if i["path"] == "NOTICE")
    after_hash = next(i["sha256"] for i in after["items"] if i["path"] == "NOTICE")
    assert before_hash != after_hash
    for item in after["items"]:
        pointer = next(p for p in item["source_pointers"] if p["path"] == "NOTICE")
        assert pointer["sha256"] == after_hash
        assert item["rights_status"] == "NOT_VERIFIED"


def test_configured_synthetic_identity_and_remote_are_never_emitted(repository):
    git(repository, "config", "user.name", "Synthetic Contributor Marker")
    git(repository, "config", "user.email", "synthetic-user@example.invalid")
    git(repository, "config", "remote.origin.url", "https://example.invalid/synthetic-origin")
    encoded = provenance._encoded(provenance.inventory_source(repository))
    for marker in (b"Synthetic Contributor Marker", b"synthetic-user@example.invalid",
                   b"https://example.invalid/synthetic-origin"):
        assert marker not in encoded


def test_only_version_config_and_index_git_commands_are_used(repository, monkeypatch):
    original = provenance._git
    commands = []
    def capture(executable, identity, arguments, **kwargs):
        commands.append(arguments)
        return original(executable, identity, arguments, **kwargs)
    monkeypatch.setattr(provenance, "_git", capture)
    provenance.inventory_source(repository)
    assert commands == [["--version"],
                        ["config", "--null", "--no-includes", "--file", "-", "--list"],
                        ["ls-files", "--stage", "--full-name", "-z"]]


def test_git_failure_diagnostics_are_not_echoed(repository, tmp_path, monkeypatch, capsys):
    def refused(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 1, b"synthetic private stdout", b"synthetic private stderr")
    monkeypatch.setattr(provenance.subprocess, "run", refused)
    assert provenance.main(["--root", str(repository), "--output", str(tmp_path / "inventory.json")]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "SOURCE_PROVENANCE_REJECTED: GIT_ENUMERATION_REJECTED\n"


def test_control_character_in_actual_index_path_refuses(repository):
    name = "docs/control\nname.md"
    (repository / name).write_text("# Synthetic\n")
    git(repository, "add", name)
    reject(repository, "INVALID_LOCAL_PATH")


def test_file_count_cap_refuses_without_partial_result(repository, monkeypatch):
    monkeypatch.setattr(provenance, "MAX_FILES", 2)
    reject(repository, "INVALID_INDEX_COUNT")


def test_existing_output_refuses_before_source_or_git_reads(repository, tmp_path, monkeypatch, capsys):
    output = tmp_path / "existing.json"
    output.write_text("preserve existing bytes")
    def forbidden(*args, **kwargs):
        pytest.fail("existing output must refuse at preflight")
    monkeypatch.setattr(provenance, "inventory_source", forbidden)
    assert provenance.main(["--root", str(repository), "--output", str(output)]) == 1
    assert output.read_text() == "preserve existing bytes"
    assert capsys.readouterr().err == "SOURCE_PROVENANCE_REJECTED: OUTPUT_EXISTS\n"


def test_indexed_example_csv_is_test_fixture_without_rights_promotion(repository):
    name = "examples/measurement-review/batch.csv"
    path = repository / name
    path.parent.mkdir(parents=True)
    data = b"sample,value\nsynthetic-1,2.0\n"
    path.write_bytes(data)
    git(repository, "add", name)
    receipt = provenance.inventory_source(repository)
    row = next(item for item in receipt["items"] if item["path"] == name)
    assert row["kind"] == "test"
    assert row["sha256"] == provenance.audit._sha256(data)
    assert row["evidence_status"] == "INDEX_BLOB_AND_WORKING_BYTES_MATCH"
    assert row["rights_status"] == row["authorship_status"] == row["private_data_review_status"] == "NOT_VERIFIED"
    assert receipt["counts"]["tracked_files"] == 10


@pytest.mark.parametrize("path", ["batch.csv", "src/batch.csv", "assets/batch.csv"])
def test_csv_policy_rejects_undeclared_roots(path):
    with pytest.raises(provenance.audit.AuditRejected, match="UNCLASSIFIED_SOURCE_PATH"):
        provenance.classify_path(path)


def test_indexed_documentation_csv_and_checksum_evidence_are_included(repository):
    paths = {"docs/research/oss-workflows/frozen-oracle/measurements.csv": b"case,value\nsynthetic,1.0\n",
             "docs/research/oss-workflows/SHA256SUMS": b"synthetic checksum declaration, not verified\n"}
    for name, data in paths.items():
        path = repository / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        git(repository, "add", name)
    receipt = provenance.inventory_source(repository)
    for name, data in paths.items():
        row = next(item for item in receipt["items"] if item["path"] == name)
        assert row["kind"] == "docs"
        assert row["sha256"] == provenance.audit._sha256(data)
        assert row["evidence_status"] == "INDEX_BLOB_AND_WORKING_BYTES_MATCH"
        assert row["rights_status"] == row["authorship_status"] == row["private_data_review_status"] == "NOT_VERIFIED"
    assert receipt["counts"]["tracked_files"] == 11


@pytest.mark.parametrize("path", ["SHA256SUMS", "examples/SHA256SUMS", "assets/SHA256SUMS"])
def test_checksum_file_policy_rejects_undeclared_roots(path):
    with pytest.raises(provenance.audit.AuditRejected, match="UNCLASSIFIED_SOURCE_PATH"):
        provenance.classify_path(path)
