"""Opt-in acquisition checks on trusted local files, not a memory/time sandbox.

Uses the selected package import unchanged, so the same cases can qualify a
source package or a detached installed wheel. All objects are synthetic.
"""
from dataclasses import replace
import hashlib
import io
import os
from pathlib import Path
import subprocess
import sys

import pytest

from opendot_engineering.core import ArtifactIntegrityError, ArtifactRef, ArtifactStore
from opendot_engineering.core import artifacts, contracts


class IntSubclass(int):
    pass


class CoercionTrap:
    def __index__(self):
        pytest.fail("budget was coerced")

    def __int__(self):
        pytest.fail("budget was coerced")


@pytest.fixture
def store(tmp_path):
    return ArtifactStore(tmp_path / "cas")


def object_path(store, ref):
    return store.objects / ref.sha256[:2] / ref.sha256[2:]


def track_reads(monkeypatch, store, ref, budget, *, short=None):
    """Observe real unbuffered reads, optionally returning controlled short reads."""
    target = object_path(store, ref)
    original = Path.open
    records = {"requests": [], "returned": [], "closed": False, "opens": 0}

    class Traced:
        def __init__(self, raw):
            assert isinstance(raw, io.FileIO)
            self.raw = raw

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.raw.close()
            records["closed"] = self.raw.closed

        def read(self, size=-1):
            observed = sum(records["returned"])
            assert type(size) is int and 0 < size <= min(65536, budget + 1 - observed)
            records["requests"].append(size)
            data = self.raw.read(size if short is None else min(size, short))
            records["returned"].append(len(data))
            return data

    def opened(path, mode="r", *args, **kwargs):
        if path == target:
            assert mode == "rb" and not args and kwargs == {"buffering": 0}
            records["opens"] += 1
            return Traced(original(path, mode, **kwargs))
        return original(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", opened)
    monkeypatch.setattr(Path, "read_bytes", lambda *a: pytest.fail("whole-object read used"))
    return records


@pytest.mark.parametrize("size", [0, 255, 256, 257, 1024 * 1024])
@pytest.mark.parametrize("lookup", ["ref", "digest", "id"])
def test_real_bounded_boundaries(store, monkeypatch, size, lookup):
    data = b"x" * size
    ref = store.put_bytes(data)
    key = {"ref": ref, "digest": ref.sha256, "id": ref.artifact_id}[lookup]
    observed = track_reads(monkeypatch, store, ref, 256)
    if size > 256:
        monkeypatch.setattr(store, "sha256", lambda _: pytest.fail("oversize was hashed"))
        with pytest.raises(ArtifactIntegrityError, match="^artifact exceeds max_bytes$"):
            store.get_bytes(key, max_bytes=256)
    else:
        assert store.get_bytes(key, max_bytes=256) == data
        assert observed["returned"][-1] == 0
    assert sum(observed["returned"]) == min(size, 257)
    assert observed["opens"] == 1 and observed["closed"]
    if size == 256:
        assert observed["requests"][-1] == 1
    elif size > 256:
        assert observed["returned"][-1] > 0


@pytest.mark.parametrize("size", [0, 255, 256, 257])
@pytest.mark.parametrize("short", [1, 7, 64])
def test_short_reads_keep_cumulative_bound(store, monkeypatch, size, short):
    ref = store.put_bytes(b"y" * size)
    observed = track_reads(monkeypatch, store, ref, 256, short=short)
    if size > 256:
        with pytest.raises(ArtifactIntegrityError, match="exceeds max_bytes"):
            store.get_bytes(ref, max_bytes=256)
    else:
        assert store.get_bytes(ref, max_bytes=256) == b"y" * size
        assert observed["returned"][-1] == 0
    assert sum(observed["returned"]) == min(size, 257)
    assert observed["closed"]


@pytest.mark.parametrize("data", [b"", b"x"])
def test_zero_budget(store, monkeypatch, data):
    ref = store.put_bytes(data)
    observed = track_reads(monkeypatch, store, ref, 0)
    if data:
        with pytest.raises(ArtifactIntegrityError, match="exceeds max_bytes"):
            store.get_bytes(ref, max_bytes=0)
    else:
        assert store.get_bytes(ref, max_bytes=0) == b""
    assert observed["requests"] == [1] and observed["closed"]


@pytest.mark.parametrize("value", [True, False, 1.0, "1", b"1", IntSubclass(1), object(), CoercionTrap()])
def test_budget_type_refuses_before_reference_or_io(store, monkeypatch, value):
    monkeypatch.setattr(store, "_path", lambda _: pytest.fail("path accessed"))
    monkeypatch.setattr(store, "sha256", lambda _: pytest.fail("hash accessed"))
    with pytest.raises(TypeError, match="^max_bytes must be int or None$"):
        store.get_bytes(object(), max_bytes=value)


@pytest.mark.parametrize("value", [-1, -(2 ** 200)])
def test_negative_budget_refuses_before_reference_or_io(store, monkeypatch, value):
    monkeypatch.setattr(store, "_path", lambda _: pytest.fail("path accessed"))
    with pytest.raises(ValueError, match="^max_bytes must be nonnegative$"):
        store.get_bytes(object(), max_bytes=value)


def test_enormous_budget_only_requests_small_actual_reads(store, monkeypatch):
    ref = store.put_bytes(b"tiny")
    observed = track_reads(monkeypatch, store, ref, 2 ** 200)
    assert store.get_bytes(ref, max_bytes=2 ** 200) == b"tiny"
    assert observed["requests"] == [65536, 65536]
    assert sum(observed["returned"]) == 4 and observed["closed"]


@pytest.mark.parametrize("declared", [0, 1, 999])
def test_bound_ignores_reference_size_and_metadata(store, declared):
    ref = store.put_bytes(b"actual")
    metadata = store.meta / (ref.sha256 + ".json")
    metadata.chmod(0o600)
    metadata.write_bytes(b"not metadata")
    assert store.get_bytes(replace(ref, size_bytes=declared), max_bytes=6) == b"actual"


def test_false_declared_size_cannot_expand_actual_read(store, monkeypatch):
    ref = store.put_bytes(b"z" * 1024 * 1024)
    observed = track_reads(monkeypatch, store, ref, 256)
    with pytest.raises(ArtifactIntegrityError, match="exceeds max_bytes"):
        store.get_bytes(replace(ref, size_bytes=1), max_bytes=256)
    assert sum(observed["returned"]) == 257 and observed["closed"]


@pytest.mark.parametrize("oversized", [False, True])
def test_corruption_and_oversize_precedence(store, monkeypatch, oversized):
    ref = store.put_bytes(b"right")
    obj = object_path(store, ref)
    obj.chmod(0o600)
    obj.write_bytes(b"x" * (257 if oversized else 5))
    observed = track_reads(monkeypatch, store, ref, 256)
    if oversized:
        monkeypatch.setattr(store, "sha256", lambda _: pytest.fail("oversize was hashed"))
    with pytest.raises(ArtifactIntegrityError, match="exceeds max_bytes" if oversized else "failed integrity verification"):
        store.get_bytes(ref, max_bytes=256)
    assert observed["closed"]


def test_invalid_digest_and_missing_object_keep_errors(store):
    with pytest.raises(ArtifactIntegrityError, match="invalid artifact digest"):
        store.get_bytes("../escape", max_bytes=256)
    with pytest.raises(FileNotFoundError):
        store.get_bytes("0" * 64, max_bytes=256)


@pytest.mark.parametrize("explicit", [False, True])
def test_none_retains_legacy_whole_read(store, monkeypatch, explicit):
    ref = store.put_bytes(b"legacy" * 1024)
    calls = []
    original = Path.read_bytes
    def whole(path):
        calls.append(path)
        return original(path)
    monkeypatch.setattr(Path, "read_bytes", whole)
    options = {"max_bytes": None} if explicit else {}
    assert store.get_bytes(replace(ref, size_bytes=1), **options) == b"legacy" * 1024
    assert calls == [object_path(store, ref)]


def snapshot(root):
    return {str(p.relative_to(root)): (p.lstat().st_mode, p.lstat().st_mtime_ns,
            p.lstat().st_ctime_ns, os.readlink(p) if p.is_symlink() else
            p.read_bytes() if p.is_file() else None) for p in (root, *sorted(root.rglob("*")))}


@pytest.mark.parametrize("read_only", [False, True])
@pytest.mark.parametrize("budget", [2, 3])
def test_bounded_success_and_refusal_do_not_mutate(store, read_only, budget):
    ref = store.put_bytes(b"abc")
    reader = ArtifactStore(store.root, read_only=True) if read_only else store
    before = snapshot(store.root)
    if budget < 3:
        with pytest.raises(ArtifactIntegrityError):
            reader.get_bytes(ref, max_bytes=budget)
    else:
        assert reader.get_bytes(ref, max_bytes=budget) == b"abc"
    assert snapshot(store.root) == before


def test_bounded_read_follows_trusted_symlink(store, tmp_path):
    ref = store.put_bytes(b"trusted")
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(store.root, target_is_directory=True)
    except (OSError, NotImplementedError) as error:
        pytest.skip(str(error))
    reader = ArtifactStore(alias, read_only=True)
    assert reader.get_bytes(ref, max_bytes=7) == b"trusted"


def test_canonical_identity_and_default_import_closure():
    assert ArtifactStore is artifacts.ArtifactStore
    assert ArtifactRef is artifacts.ArtifactRef is contracts.ArtifactRef
    assert ArtifactIntegrityError is artifacts.ArtifactIntegrityError
    script = """
import sys
class NoOptionalImports:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'temporalio', 'openai', 'anthropic'}:
            raise AssertionError('optional dependency imported')
sys.meta_path.insert(0, NoOptionalImports())
from opendot_engineering.core import ArtifactStore
assert 'temporalio' not in sys.modules
"""
    # Honor the caller's package selection; do not insert a source path here.
    completed = subprocess.run([sys.executable, "-B", "-c", script], capture_output=True,
                               text=True, timeout=10)
    assert completed.returncode == 0, completed.stderr


def test_read_error_closes_and_keeps_original_error(store, monkeypatch):
    ref = store.put_bytes(b"error")
    original = Path.open
    opened = []
    failure = OSError("synthetic read failure")
    class Broken:
        def __init__(self, raw): self.raw = raw
        def __enter__(self): return self
        def __exit__(self, *args): self.raw.close()
        def read(self, size): raise failure
    def broken_open(path, mode="r", *args, **kwargs):
        raw = original(path, mode, *args, **kwargs)
        opened.append(raw)
        return Broken(raw)
    monkeypatch.setattr(Path, "open", broken_open)
    with pytest.raises(OSError) as caught:
        store.get_bytes(ref, max_bytes=256)
    assert caught.value is failure and len(opened) == 1 and opened[0].closed


def test_bound_is_keyword_only(store):
    ref = store.put_bytes(b"x")
    with pytest.raises(TypeError):
        store.get_bytes(ref, 1)
