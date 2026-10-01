"""Synthetic local checks of the canonical artifact owner; no runtime imports."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys

import pytest

from opendot_engineering.core import ArtifactIntegrityError, ArtifactRef, ArtifactStore
from opendot_engineering.core import artifacts, contracts


@pytest.fixture
def store(tmp_path):
    return ArtifactStore(tmp_path / "cas")


def object_path(store, ref):
    return store.objects / ref.sha256[:2] / ref.sha256[2:]


def overwrite(path, data):
    path.chmod(0o600)
    path.write_bytes(data)


@pytest.mark.parametrize("data", [b"", b"public-synthetic-artifact", bytes(range(256))])
def test_real_roundtrip_and_independent_hash(store, data):
    ref = store.put_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    assert type(ref) is ArtifactRef
    assert ref.artifact_id == "sha256:" + digest
    assert ref.uri == "artifact://sha256/" + digest
    assert ref.sha256 == digest and ref.size_bytes == len(data)
    assert ref.integrity_verified is True
    for lookup in (ref, digest, ref.artifact_id):
        assert store.get_bytes(lookup) == data
    assert store.verify(ref) and store.verify_id(ref.artifact_id)
    assert not store.verify_id(digest)
    metadata = json.loads((store.meta / (digest + ".json")).read_text())
    assert metadata["sha256"] == digest and metadata["size_bytes"] == len(data)


def test_single_reference_and_store_owner():
    assert artifacts.ArtifactRef is contracts.ArtifactRef is ArtifactRef
    assert ArtifactStore is artifacts.ArtifactStore
    assert ArtifactIntegrityError is artifacts.ArtifactIntegrityError


def test_reference_is_frozen(store):
    ref = store.put_bytes(b"immutable-reference")
    with pytest.raises(FrozenInstanceError):
        ref.size_bytes = 1


def test_sequential_repeat_keeps_first_metadata(store):
    first = store.put_bytes(b"same", producer="first", task_id="one")
    obj = object_path(store, first)
    metadata = store.meta / (first.sha256 + ".json")
    before = (obj.stat().st_mtime_ns, metadata.stat().st_mtime_ns, metadata.read_bytes())
    second = store.put_bytes(b"same", producer="second", task_id="two", source_refs=("synthetic",))
    assert second.artifact_id == first.artifact_id
    assert (obj.stat().st_mtime_ns, metadata.stat().st_mtime_ns, metadata.read_bytes()) == before
    assert json.loads(metadata.read_text())["producer"] == "first"
    assert second.producer == "second" and second.source_refs == ("synthetic",)


@pytest.mark.parametrize("value", ["text", bytearray(b"x"), memoryview(b"x"), None])
def test_non_bytes_rejected(store, value):
    with pytest.raises(TypeError, match="artifact data must be bytes"):
        store.put_bytes(value)


def test_corrupt_object_read_and_reuse_rejected(store):
    ref = store.put_bytes(b"right")
    overwrite(object_path(store, ref), b"wrong")
    with pytest.raises(ArtifactIntegrityError, match="failed integrity verification"):
        store.get_bytes(ref)
    with pytest.raises(ArtifactIntegrityError, match="corrupted existing object"):
        store.put_bytes(b"right")
    assert not store.verify(ref) and not store.verify_id(ref.artifact_id)


def test_forced_digest_collision_rejected(store, monkeypatch):
    ref = store.put_bytes(b"first")
    monkeypatch.setattr(store, "sha256", lambda data: ref.sha256)
    with pytest.raises(ArtifactIntegrityError, match="hash collision"):
        store.put_bytes(b"other")
    assert object_path(store, ref).read_bytes() == b"first"


@pytest.mark.parametrize("value", ["", "../escape", "/absolute", "f" * 63, "f" * 65,
                                   "A" * 64, "g" * 64, "f" * 64 + "\n",
                                   "artifact://sha256/" + "f" * 64])
def test_lexically_invalid_digest_rejected(store, value):
    with pytest.raises(ArtifactIntegrityError, match="invalid artifact digest"):
        store.get_bytes(value)
    assert not store.verify_id(value)


@pytest.mark.parametrize("value", [None, 3, b"sha256:abc"])
def test_verify_id_rejects_nonstring(store, value):
    assert store.verify_id(value) is False


def test_missing_object(store):
    digest = "0" * 64
    ref = ArtifactRef("sha256:" + digest, "artifact://sha256/" + digest,
                      "application/octet-stream", 0, digest)
    with pytest.raises(FileNotFoundError):
        store.get_bytes(ref)
    assert not store.verify(ref) and not store.verify_id(ref.artifact_id)


@pytest.mark.parametrize("metadata", [b"not json", b"\xff",
                                      b'{"sha256":"wrong","size_bytes":4}'])
def test_bad_metadata_rejected_on_put(store, metadata):
    ref = store.put_bytes(b"data")
    overwrite(store.meta / (ref.sha256 + ".json"), metadata)
    with pytest.raises(ArtifactIntegrityError):
        store.put_bytes(b"data")


def test_metadata_size_mismatch_rejected(store):
    ref = store.put_bytes(b"data")
    overwrite(store.meta / (ref.sha256 + ".json"),
              json.dumps({"sha256": ref.sha256, "size_bytes": 999}).encode())
    with pytest.raises(ArtifactIntegrityError, match="metadata does not match"):
        store.put_bytes(b"data")


def test_metadata_shape_behavior_is_preserved(store):
    ref = store.put_bytes(b"data")
    overwrite(store.meta / (ref.sha256 + ".json"), b"[]")
    with pytest.raises(AttributeError):
        store.put_bytes(b"data")


def test_read_verification_does_not_validate_metadata(store):
    ref = store.put_bytes(b"data")
    overwrite(store.meta / (ref.sha256 + ".json"), b"not json")
    assert store.get_bytes(ref) == b"data"
    assert store.verify(ref) and store.verify_id(ref.artifact_id)
    assert not store.verify(replace(ref, size_bytes=999))
    assert not store.verify(replace(ref, artifact_id="bad"))


def test_reference_validator_is_not_strict_external_input_parser(store):
    ref = store.put_bytes(b"validator-boundary")
    unusual = replace(ref, sha256=ref.sha256 + "\n",
                      artifact_id=ref.artifact_id + "\n", uri=ref.uri + "\n")
    unusual.validate()  # Existing regex semantics retained, not a hardening claim.
    with pytest.raises(ArtifactIntegrityError):
        store.get_bytes(unusual)
    assert store.verify(unusual) is False


def test_text_json_file_conveniences(store, tmp_path):
    text = store.put_text("café")
    assert store.get_bytes(text) == "café".encode()
    assert text.mime_type == "text/plain; charset=utf-8"
    first = store.put_json({"z": 1, "a": "é"})
    second = store.put_json({"a": "é", "z": 1})
    assert first.artifact_id == second.artifact_id
    assert store.get_bytes(first) == '{"a":"é","z":1}'.encode()
    assert first.mime_type == "application/json"
    source = tmp_path / "invented.txt"
    source.write_bytes(b"synthetic-file")
    file_ref = store.put_file(source)
    assert store.get_bytes(file_ref) == b"synthetic-file" and file_ref.mime_type == "text/plain"


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_nonfinite_json_rejected(store, value):
    with pytest.raises(ValueError):
        store.put_json(value)


def test_replace_failure_cleans_temporary(store, monkeypatch):
    def fail(*args):
        raise OSError("synthetic replace failure")
    monkeypatch.setattr(artifacts.os, "replace", fail)
    with pytest.raises(OSError, match="synthetic replace failure"):
        store.put_bytes(b"unpublished")
    assert list(store.objects.rglob(".tmp-*")) == []
    assert not store.verify_id("sha256:" + hashlib.sha256(b"unpublished").hexdigest())


def test_fsync_failure_cleans_temporary(store, monkeypatch):
    def fail(*args):
        raise OSError("synthetic fsync failure")
    monkeypatch.setattr(artifacts.os, "fsync", fail)
    with pytest.raises(OSError, match="synthetic fsync failure"):
        store.put_bytes(b"unpublished-fsync")
    assert list(store.objects.rglob(".tmp-*")) == []


def test_metadata_failure_can_leave_object_without_metadata(store, monkeypatch):
    original = store._atomic_write
    def fail_metadata(path, data, **kwargs):
        if path.parent == store.meta:
            raise OSError("synthetic metadata failure")
        return original(path, data, **kwargs)
    monkeypatch.setattr(store, "_atomic_write", fail_metadata)
    data = b"partial-publication"
    digest = hashlib.sha256(data).hexdigest()
    with pytest.raises(OSError, match="synthetic metadata failure"):
        store.put_bytes(data)
    assert store.get_bytes(digest) == data
    assert not (store.meta / (digest + ".json")).exists()
    assert store.verify_id("sha256:" + digest)


def test_symlink_can_leave_root_in_controlled_fixture(store, tmp_path):
    # Both roots are disposable synthetic directories owned by this test.
    sibling = tmp_path / "controlled-sibling"
    sibling.mkdir()
    data = b"symlink-boundary"
    digest = hashlib.sha256(data).hexdigest()
    prefix = store.objects / digest[:2]
    try:
        prefix.symlink_to(sibling, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(str(exc))
    ref = store.put_bytes(data)
    assert (sibling / digest[2:]).read_bytes() == data
    assert not object_path(store, ref).resolve().is_relative_to(store.root.resolve())
    assert store.verify(ref)


@pytest.mark.skipif(os.name != "posix", reason="POSIX mode semantics only")
def test_best_effort_modes_in_this_environment(store):
    ref = store.put_bytes(b"permissions")
    for path in (store.root, store.objects, store.meta, object_path(store, ref).parent):
        assert path.stat().st_mode & 0o777 == 0o700
    for path in (object_path(store, ref), store.meta / (ref.sha256 + ".json")):
        assert path.stat().st_mode & 0o777 == 0o444


def test_core_dependency_closure_is_stdlib_and_one_contract():
    for module in (artifacts, contracts):
        tree = ast.parse(Path(module.__file__).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(alias.name.split(".")[0] in sys.stdlib_module_names for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    assert module is artifacts and node.level == 1 and node.module == "contracts"
                    assert [alias.name for alias in node.names] == ["ArtifactRef"]
                else:
                    assert node.module.split(".")[0] in sys.stdlib_module_names
    classes = [node.name for node in ast.parse(Path(contracts.__file__).read_text()).body
               if isinstance(node, ast.ClassDef)]
    assert classes == ["ArtifactRef", "Capability", "AgentManifest"]


def test_public_example_real_calls_and_existing_output_refusal(tmp_path):
    path = Path(__file__).resolve().parents[1] / "examples/canonical-artifacts/roundtrip.py"
    spec = importlib.util.spec_from_file_location("public_artifact_example", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.demonstrate(tmp_path / "example")
    assert result["passed"] is True and all(result["checks"].values())
    assert result["scenario"] == "PUBLIC_SYNTHETIC_LOCAL_CAS"
    assert result["scientific_accepted"] is False
    assert result["device_control_authorized"] is False
    assert result["consumer_migration_status"] == "NOT_EVALUATED"
    with pytest.raises(FileExistsError):
        module.demonstrate(tmp_path / "example")
