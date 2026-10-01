"""Synthetic-only contract tests; no research data, model, network or solver."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from opendot_engineering.adapters import source_audit as a

EXAMPLE = Path(__file__).parents[1] / "examples/source-audit"
REVISION = "a" * 40  # Deliberately synthetic, not a Git commit assertion.
PIN = "f4d81f12c83b7f222931348677b01b6f27df8905513cfbaebac3cf86cbfe26ae"


@pytest.fixture
def fixture(tmp_path):
    root = tmp_path / "inputs"
    shutil.copytree(EXAMPLE, root)
    return root


def load(root):
    return json.loads((root / "manifest.json").read_text()), json.loads((root / "sources/synthetic.json").read_text())


def write(root, spec, doc=None):
    if doc is not None:
        raw = (json.dumps(doc, indent=2) + "\n").encode()
        (root / "sources/synthetic.json").write_bytes(raw)
        spec["sources"][0]["sha256"] = a._sha256(raw)
        spec["sources"][0]["git_blob_sha1"] = a._git_blob(raw)
    raw = (json.dumps(spec, indent=2) + "\n").encode()
    (root / "manifest.json").write_bytes(raw)
    return a._sha256(raw)


def audit(root, pin=PIN, **kw):
    return a.audit_manifest(root, "manifest.json", expected_revision=REVISION,
                            expected_manifest_sha256=pin, **kw)


def rejected(root, code, pin=PIN, **kw):
    with pytest.raises(a.AuditRejected) as exc:
        audit(root, pin, **kw)
    assert exc.value.code == code


def test_synthetic_read_only_receipt_is_not_science_acceptance(fixture):
    before = {p.relative_to(fixture): p.read_bytes() for p in fixture.rglob("*") if p.is_file()}
    result = audit(fixture, audience="public")
    assert result["audit_accepted"] is True
    assert result["scientific_accepted"] is False
    assert result["scientific_status"] == "NOT_EVALUATED"
    assert result["manifest_sha256"] == PIN
    assert result["adapter_sha256"] == a._sha256(Path(a.__file__).read_bytes())
    assert [x["value_state"] for x in result["claims"]] == ["known", "unknown"]
    assert all(x["evidence_role"] == "synthetic" for x in result["claims"])
    assert "123.4" not in json.dumps(result)
    assert str(fixture) not in json.dumps(result)
    after = {p.relative_to(fixture): p.read_bytes() for p in fixture.rglob("*") if p.is_file()}
    assert before == after
    assert load(fixture)[1]["observations"][1]["value"] is None
    assert result == audit(fixture, audience="public")


def test_import_has_no_optional_dependency_or_network():
    code = (
        "import sys; before = set(sys.modules); "
        "import opendot_engineering.adapters.source_audit; "
        "assert all(n.split('.')[0] in sys.stdlib_module_names or "
        "n.split('.')[0] == 'opendot_engineering' for n in set(sys.modules) - before); "
        "assert not any(n in sys.modules for n in ('requests', 'numpy'))"
    )
    subprocess.run([sys.executable, "-c", code], check=True, capture_output=True, timeout=10)


def test_no_network_or_process_execution(monkeypatch, fixture):
    import socket
    def forbidden(*args, **kwargs):
        raise AssertionError("No external side effects allowed")
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    assert audit(fixture)["audit_accepted"]


def test_missing_inputs_and_independent_manifest_pin(fixture):
    rejected(fixture, "MANIFEST_HASH_MISMATCH", "0" * 64)
    (fixture / "sources/synthetic.json").unlink()
    rejected(fixture, "LOCAL_INPUT_UNAVAILABLE_OR_UNSAFE")
    (fixture / "manifest.json").unlink()
    rejected(fixture, "LOCAL_INPUT_UNAVAILABLE_OR_UNSAFE")


@pytest.mark.parametrize("value", [None, True, [], {}, "", "A" * 40, "g" * 40, "a" * 39])
def test_invalid_revision_pin(fixture, value):
    with pytest.raises(a.AuditRejected, match="INVALID_PIN"):
        a.audit_manifest(fixture, "manifest.json", expected_revision=value, expected_manifest_sha256=PIN)


@pytest.mark.parametrize("field,code", [("source_revision", "REVISION_OR_SCHEMA_MISMATCH"), ("source", "SOURCE_REVISION_MISMATCH"), ("document", "SOURCE_IDENTITY_MISMATCH")])
def test_revision_disagreement(fixture, field, code):
    spec, doc = load(fixture)
    if field == "source_revision": spec[field] = "b" * 40
    elif field == "source": spec["sources"][0]["revision"] = "b" * 40
    else: doc["source_revision"] = "b" * 40
    rejected(fixture, code, write(fixture, spec, doc))


@pytest.mark.parametrize("path", ["../outside.json", "/etc/passwd", "sources/../../outside", "sources//synthetic.json", "sources/./synthetic.json", "sources\\synthetic.json", "https://example.invalid/data", "sources/synthetic.json/", "", None, {}, []])
def test_path_escape_or_nonlocal_input(fixture, path):
    spec, _ = load(fixture)
    spec["sources"][0]["path"] = path
    rejected(fixture, "INVALID_LOCAL_PATH", write(fixture, spec))


@pytest.mark.parametrize("which", ["file", "directory", "root", "root_parent"])
def test_symlink_routes_fail_closed(fixture, tmp_path, which):
    if which == "file":
        original = fixture / "sources/synthetic.json"
        target = tmp_path / "source.json"
        original.rename(target)
        original.symlink_to(target)
        rejected(fixture, "LOCAL_INPUT_UNAVAILABLE_OR_UNSAFE")
    elif which == "directory":
        target = tmp_path / "source_dir"
        (fixture / "sources").rename(target)
        (fixture / "sources").symlink_to(target, target_is_directory=True)
        rejected(fixture, "LOCAL_INPUT_UNAVAILABLE_OR_UNSAFE")
    else:
        alias = tmp_path / "alias"
        alias.symlink_to(fixture if which == "root" else fixture.parent, target_is_directory=True)
        rejected(alias if which == "root" else alias / fixture.name, "ROOT_UNAVAILABLE")


def test_named_pipe_is_not_read_as_source(fixture):
    import os
    p = fixture / "sources/synthetic.json"
    p.unlink(); os.mkfifo(p)
    rejected(fixture, "NOT_REGULAR_FILE")


def test_source_sha_and_git_blob_are_both_required(fixture):
    spec, _ = load(fixture)
    spec["sources"][0]["git_blob_sha1"] = "0" * 40
    rejected(fixture, "SOURCE_BLOB_MISMATCH", write(fixture, spec))
    spec["sources"][0]["sha256"] = "0" * 64
    rejected(fixture, "SOURCE_SHA256_MISMATCH", write(fixture, spec))


@pytest.mark.parametrize("level", ["manifest", "source", "document"])
@pytest.mark.parametrize("category", ["internal", "secret", "PUBLIC", None, [], {}])
def test_unrecognized_access_categories(fixture, level, category):
    spec, doc = load(fixture)
    if level == "manifest": spec["access"] = category
    elif level == "source": spec["sources"][0]["access"] = category
    else: doc["access"] = category
    rejected(fixture, "SOURCE_ACCESS_MISMATCH" if level == "document" else "INVALID_ACCESS_CATEGORY", write(fixture, spec, doc))


def test_private_inputs_need_private_audience(fixture):
    spec, doc = load(fixture)
    spec["access"] = spec["sources"][0]["access"] = doc["access"] = "private"
    pin = write(fixture, spec, doc)
    rejected(fixture, "PRIVATE_INPUT_FOR_PUBLIC_AUDIENCE", pin, audience="public")
    assert audit(fixture, pin, audience="private")["scientific_accepted"] is False
    spec["access"] = "public"
    rejected(fixture, "PRIVATE_INPUT_FOR_PUBLIC_AUDIENCE", write(fixture, spec))


@pytest.mark.parametrize("state,value,uncertainty", [("unknown", 0, None), ("censored", 0, None), ("unknown", None, 0), ("known", None, None), ("known", True, None), ("known", "123.4", None), ("known", 123.4, True), ("known", 123.4, -1)])
def test_unknowns_non_numeric_values_and_uncertainty(fixture, state, value, uncertainty):
    spec, doc = load(fixture)
    row = doc["observations"][0]
    row.update(value_state=state, value=value, uncertainty=uncertainty, reason="unavailable" if state != "known" else None)
    pin = write(fixture, spec, doc)
    with pytest.raises(a.AuditRejected): audit(fixture, pin)


def test_censored_is_not_zero_or_known(fixture):
    spec, doc = load(fixture)
    doc["observations"][1]["value_state"] = "censored"
    spec["claims"][1]["value_state"] = "censored"
    result = audit(fixture, write(fixture, spec, doc))
    assert result["claims"][1]["value_state"] == "censored"
    assert load(fixture)[1]["observations"][1]["value"] is None


@pytest.mark.parametrize("role", ["measured", "model_prediction", "literature_prior", "posthoc_diagnostic"])
def test_synthetic_cannot_be_promoted(fixture, role):
    spec, doc = load(fixture)
    spec["claims"][0]["evidence_role"] = role
    rejected(fixture, "FALSE_EVIDENCE_PROMOTION", write(fixture, spec))
    doc["observations"][0]["evidence_role"] = role
    rejected(fixture, "FALSE_EVIDENCE_PROMOTION", write(fixture, spec, doc))


@pytest.mark.parametrize("role", ["model_prediction", "literature_prior", "posthoc_diagnostic"])
def test_reported_nonmeasurement_cannot_be_promoted(fixture, role):
    spec, doc = load(fixture)
    doc["content_kind"] = "reported"
    for row in doc["observations"]: row["evidence_role"] = role
    for claim in spec["claims"]: claim["evidence_role"] = role
    pin = write(fixture, spec, doc)
    assert audit(fixture, pin)["scientific_accepted"] is False
    spec["claims"][0]["evidence_role"] = "measured"
    rejected(fixture, "FALSE_EVIDENCE_PROMOTION", write(fixture, spec))


@pytest.mark.parametrize("locator", ["", "/observations/9", "/observations/00", "/observations/-1", "/observations/0/value", "/observations/~2", None, []])
def test_locators_fail_closed(fixture, locator):
    spec, _ = load(fixture)
    spec["claims"][0]["locator"] = locator
    with pytest.raises(a.AuditRejected): audit(fixture, write(fixture, spec))


@pytest.mark.parametrize("field,value", [("unit", "GPa"), ("quantity", "different_quantity"), ("value_state", "known")])
def test_claim_semantics_must_match_bound_source(fixture, field, value):
    spec, _ = load(fixture)
    spec["claims"][1][field] = value
    rejected(fixture, "FALSE_EVIDENCE_PROMOTION", write(fixture, spec))


def test_duplicate_ids_missing_source_and_unrequested_fields(fixture):
    spec, _ = load(fixture)
    original = copy.deepcopy(spec)
    spec["claims"].append(copy.deepcopy(spec["claims"][0]))
    rejected(fixture, "DUPLICATE_CLAIM", write(fixture, spec))
    spec = copy.deepcopy(original); spec["sources"].append(copy.deepcopy(spec["sources"][0]))
    rejected(fixture, "DUPLICATE_SOURCE", write(fixture, spec))
    spec = copy.deepcopy(original); spec["claims"][0]["source_id"] = "not-registered"
    rejected(fixture, "UNKNOWN_SOURCE_ID", write(fixture, spec))
    spec = copy.deepcopy(original); spec["scientific_accepted"] = True
    rejected(fixture, "INVALID_FIELDS", write(fixture, spec))


@pytest.mark.parametrize("raw,code", [(b'{"a":1,"a":2}', "DUPLICATE_JSON_KEY"), (b'{"value":NaN}', "NONFINITE_JSON"), (b'{"value":Infinity}', "NONFINITE_JSON"), (b'\xff', "INVALID_JSON")])
def test_malformed_json_is_bounded_and_rejected(fixture, raw, code):
    (fixture / "manifest.json").write_bytes(raw)
    rejected(fixture, code, a._sha256(raw))


def test_bounded_sizes(fixture, monkeypatch):
    monkeypatch.setattr(a, "MAX_MANIFEST_BYTES", 10)
    rejected(fixture, "INPUT_TOO_LARGE")
    monkeypatch.setattr(a, "MAX_MANIFEST_BYTES", 256 * 1024)
    monkeypatch.setattr(a, "MAX_SOURCE_BYTES", 10)
    rejected(fixture, "INPUT_TOO_LARGE")


def test_cli_success_and_rejection_do_not_echo_input_paths(fixture):
    command = [sys.executable, "-m", "opendot_engineering.adapters.source_audit", "--root", str(fixture), "--manifest", "manifest.json", "--expected-revision", REVISION, "--expected-manifest-sha256", PIN, "--audience", "public"]
    good = subprocess.run(command, text=True, capture_output=True, timeout=10)
    assert good.returncode == 0 and not good.stderr
    assert json.loads(good.stdout)["audit_accepted"] is True
    command[command.index("--manifest")+1] = "../private-name-do-not-echo"
    bad = subprocess.run(command, text=True, capture_output=True, timeout=10)
    assert bad.returncode == 2 and not bad.stdout
    assert json.loads(bad.stderr) == {"audit_accepted": False, "scientific_accepted": False, "error_code": "INVALID_LOCAL_PATH"}
    assert str(fixture) not in bad.stderr and "private-name" not in bad.stderr
