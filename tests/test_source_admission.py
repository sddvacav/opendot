"""Original synthetic fixtures, authored only for this review candidate."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import sys
from types import ModuleType

import pytest

from opendot_engineering.adapters import source_admission as admission
from opendot_engineering.adapters.source_admission import SourceAdmissionError, SourceLock


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def lock_for(tmp_path, sources=None, exports=None):
    sources = sources or {"helper": b"def twice(value):\n    return value * 2\n",
                          "api": b"from .helper import twice\nrun = twice\n"}
    rows = []
    for name, raw in sources.items():
        path = tmp_path / "original" / f"{name}.py"
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(raw)
        rows.append({"name": name, "path": f"original/{name}.py", "sha256": digest(raw)})
    # Must never be imported, even though the selected files live in this package.
    (tmp_path / "original" / "__init__.py").write_text("raise RuntimeError('initializer must not run')\n")
    spec = {"schema": admission.SCHEMA, "modules": rows,
            "exports": exports or {"run": {"module": list(sources)[-1], "attribute": "run"}}}
    return write_spec(tmp_path, spec), spec


def write_spec(root, spec):
    return write_raw(root, json.dumps(spec, allow_nan=False).encode())


def write_raw(root, raw):
    (root / "lock.json").write_bytes(raw)
    return SourceLock(root, "lock.json", digest(raw))


def namespace_for(lock):
    spec, _ = admission._capture(lock)
    return admission._namespace(lock, spec)


@pytest.fixture(autouse=True)
def restore_test_namespaces():
    before = set(sys.modules)
    yield
    for name in tuple(sys.modules):
        if name not in before and name.startswith("_opendot_source_"):
            del sys.modules[name]
    admission._CACHE.clear()


def test_source_owned_objects_and_initializer_skipped(tmp_path):
    lock, _ = lock_for(tmp_path)
    result = lock.load()
    assert result.exports["run"](8) == 16
    assert result.exports["run"] is result.modules["helper"].twice
    assert result.modules["api"].run is result.modules["helper"].twice
    assert sys.modules[result.namespace].__path__ == []
    assert "original" not in sys.modules
    assert lock.load() is result
    assert result.provenance()["sandbox"] is False
    assert result.provenance()["scientific_acceptance"] == "NOT_EVALUATED"
    with pytest.raises(TypeError):
        result.exports["other"] = 1


def test_compile_does_not_inherit_adapter_future_flags(tmp_path):
    lock, _ = lock_for(tmp_path, {"api": b"def run(value: int) -> int:\n    return value\n"})
    assert lock.load().exports["run"].__annotations__ == {"value": int, "return": int}


def test_required_configuration_and_absolute_root(tmp_path):
    with pytest.raises(TypeError):
        SourceLock()
    with pytest.raises(SourceAdmissionError, match="UNSAFE_ROOT"):
        SourceLock(Path("relative"), "lock.json", "a" * 64)
    with pytest.raises(SourceAdmissionError, match="UNSAFE_ROOT"):
        SourceLock(tmp_path / ".." / "elsewhere", "lock.json", "a" * 64)
    with pytest.raises(SourceAdmissionError, match="INVALID_PIN"):
        SourceLock(tmp_path, "lock.json", "A" * 64)


@pytest.mark.parametrize("raw,code", [
    (b'{"schema":1,"schema":2}', "DUPLICATE_JSON_KEY"),
    (b'{"outer":{"x":1,"x":2}}', "DUPLICATE_JSON_KEY"),
    (b'{"x":NaN}', "NONFINITE_JSON"),
    (b'{"x":Infinity}', "NONFINITE_JSON"),
    (b'{"x":-Infinity}', "NONFINITE_JSON"),
    (b'{"x":1e999}', "NONFINITE_JSON"),
    (b'{"x":-1e999}', "NONFINITE_JSON"),
    (b'\xff', "INVALID_JSON"),
    (b'{} trailing', "INVALID_JSON"),
    (b'[' * 1200 + b']' * 1200, "INVALID_JSON|JSON_STRUCTURE_TOO_LARGE"),
    (b'{"x":' + b'9' * 5000 + b'}', "INVALID_JSON"),
    (b'[' * 10 + b'0' + b']' * 10, "JSON_STRUCTURE_TOO_LARGE"),
    (b'{"x":"' + b'a' * 1025 + b'"}', "JSON_TEXT_TOO_LARGE"),
    (b'[' + b'0,' * 2048 + b'0]', "JSON_STRUCTURE_TOO_LARGE"),
], ids=["duplicate-root", "duplicate-nested", "nan", "infinity", "negative-infinity",
        "overflow", "negative-overflow", "invalid-utf8", "trailing-data", "deep",
        "huge-integer", "depth-limit", "text-limit", "node-limit"])
def test_strict_bounded_finite_json(tmp_path, raw, code):
    with pytest.raises(SourceAdmissionError, match=code):
        write_raw(tmp_path, raw).load()


def test_manifest_size_bound(tmp_path):
    with pytest.raises(SourceAdmissionError, match="INPUT_TOO_LARGE"):
        write_raw(tmp_path, b" " * (admission.MAX_MANIFEST_BYTES + 1)).load()


def test_hash_is_checked_before_json(tmp_path):
    lock = write_raw(tmp_path, b"invalid JSON")
    wrong = SourceLock(tmp_path, lock.manifest, "a" * 64)
    with pytest.raises(SourceAdmissionError, match="MANIFEST_HASH_MISMATCH"):
        wrong.load()


@pytest.mark.parametrize("mutate,code", [
    (lambda x: x.update(extra=True), "INVALID_FIELDS"),
    (lambda x: x.update(schema=True), "INVALID_SOURCE_LOCK_SCHEMA"),
    (lambda x: x.update(schema="unknown"), "INVALID_SOURCE_LOCK_SCHEMA"),
    (lambda x: x.update(modules={}), "INVALID_MODULE_COUNT"),
    (lambda x: x.update(modules=[]), "INVALID_MODULE_COUNT"),
    (lambda x: x.update(modules=x["modules"] * 17), "INVALID_MODULE_COUNT"),
    (lambda x: x.update(exports=[]), "INVALID_EXPORT_COUNT"),
    (lambda x: x.update(exports={}), "INVALID_EXPORT_COUNT"),
    (lambda x: x["modules"][0].update(extra=True), "INVALID_FIELDS"),
    (lambda x: x["modules"][0].update(name="nested.name"), "INVALID_PYTHON_IDENTIFIER"),
    (lambda x: x["modules"][0].update(name="class"), "INVALID_PYTHON_IDENTIFIER"),
    (lambda x: x["modules"][0].update(name=True), "INVALID_PYTHON_IDENTIFIER"),
    (lambda x: x["modules"][0].update(path="original/__init__.py"), "INVALID_MODULE_PATH"),
    (lambda x: x["modules"][0].update(path="original/helper.pyc"), "INVALID_MODULE_PATH"),
    (lambda x: x["modules"][0].update(sha256="A" * 64), "INVALID_PIN"),
    (lambda x: x["modules"][0].update(sha256=1), "INVALID_PIN"),
    (lambda x: x["modules"][1].update(name="helper"), "DUPLICATE_MODULE"),
    (lambda x: x["modules"][1].update(path="original/helper.py"), "DUPLICATE_MODULE"),
    (lambda x: x["exports"]["run"].update(module="missing"), "UNKNOWN_EXPORT_MODULE"),
    (lambda x: x["exports"]["run"].update(attribute="a.b"), "INVALID_PYTHON_IDENTIFIER"),
    (lambda x: x["exports"]["run"].update(attribute=False), "INVALID_PYTHON_IDENTIFIER"),
    (lambda x: x["exports"]["run"].update(extra=1), "INVALID_FIELDS"),
    (lambda x: x["exports"].update({str(i): {} for i in range(65)}), "INVALID_EXPORT_COUNT"),
])
def test_closed_schema_and_exact_types(tmp_path, mutate, code):
    _, spec = lock_for(tmp_path)
    mutate(spec)
    with pytest.raises(SourceAdmissionError, match=code):
        write_spec(tmp_path, spec).load()


@pytest.mark.parametrize("path", ["/absolute.py", "../escape.py", "a/../escape.py", "a//b.py",
                                  "./file.py", "a/./b.py", "a\\b.py", "C:/file.py", "bad\n.py", "", "bad\x7f.py", "bad\x85.py",
                                  "bad\x9f.py", "bad\ud800.py", "bad\udcff.py", "bad\udfff.py"])
def test_relative_paths_are_strict(tmp_path, path):
    _, spec = lock_for(tmp_path)
    spec["modules"][0]["path"] = path
    with pytest.raises(SourceAdmissionError, match="INVALID_LOCAL_PATH"):
        write_spec(tmp_path, spec).load()
    with pytest.raises(SourceAdmissionError, match="INVALID_LOCAL_PATH"):
        SourceLock(tmp_path, path, "a" * 64)


def test_all_hashes_checked_before_execution(tmp_path):
    marker = tmp_path / "executed"
    sources = {"first": f"from pathlib import Path\nPath({str(marker)!r}).touch()\nrun = 1\n".encode(),
               "second": b"run = 2\n"}
    lock, _ = lock_for(tmp_path, sources)
    (tmp_path / "original" / "second.py").write_bytes(b"run = 3\n")
    with pytest.raises(SourceAdmissionError, match="MODULE_HASH_MISMATCH"):
        lock.load()
    assert not marker.exists()


def test_exact_captured_bytes_used_after_source_changes(tmp_path):
    target = tmp_path / "original" / "second.py"
    replacement = b"run = 'replacement'\n"
    first = f"from pathlib import Path\nPath({str(target)!r}).write_bytes({replacement!r})\n".encode()
    lock, _ = lock_for(tmp_path, {"first": first, "second": b"run = 'captured'\n"})
    assert lock.load().exports["run"] == "captured"
    assert target.read_bytes() == replacement
    with pytest.raises(SourceAdmissionError, match="MODULE_HASH_MISMATCH"):
        lock.load()


def test_manifest_is_rechecked_on_cache_hit(tmp_path):
    lock, _ = lock_for(tmp_path)
    lock.load()
    with (tmp_path / "lock.json").open("ab") as stream:
        stream.write(b" ")
    with pytest.raises(SourceAdmissionError, match="MANIFEST_HASH_MISMATCH"):
        lock.load()


def test_precompiles_all_before_execution(tmp_path):
    marker = tmp_path / "executed"
    lock, _ = lock_for(tmp_path, {
        "first": f"from pathlib import Path\nPath({str(marker)!r}).touch()\n".encode(),
        "second": b"invalid python syntax!\n"})
    namespace = namespace_for(lock)
    with pytest.raises(SyntaxError):
        lock.load()
    assert not marker.exists()
    assert namespace not in sys.modules


@pytest.mark.parametrize("kind", ["source", "directory", "manifest", "root"])
def test_symlinks_rejected(tmp_path, kind):
    real = tmp_path / "real"
    real.mkdir()
    lock, _ = lock_for(real)
    if kind == "root":
        link = tmp_path / "link"
        link.symlink_to(real, target_is_directory=True)
        lock = SourceLock(link, lock.manifest, lock.expected_manifest_sha256)
    else:
        path = {"source": real / "original" / "api.py", "directory": real / "original",
                "manifest": real / "lock.json"}[kind]
        moved = path.with_name(path.name + ".moved")
        path.rename(moved)
        path.symlink_to(moved, target_is_directory=kind == "directory")
    with pytest.raises(SourceAdmissionError, match="ROOT_UNAVAILABLE|LOCAL_INPUT_UNAVAILABLE_OR_UNSAFE"):
        lock.load()


def test_nonregular_source_rejected_without_fifo_wait(tmp_path):
    lock, _ = lock_for(tmp_path)
    path = tmp_path / "original" / "helper.py"
    path.unlink()
    os.mkfifo(path)
    with pytest.raises(SourceAdmissionError, match="NOT_REGULAR_FILE"):
        lock.load()


def test_module_size_and_total_bounds(tmp_path, monkeypatch):
    lock, _ = lock_for(tmp_path)
    monkeypatch.setattr(admission, "MAX_MODULE_BYTES", 1)
    with pytest.raises(SourceAdmissionError, match="INPUT_TOO_LARGE"):
        lock.load()
    monkeypatch.setattr(admission, "MAX_MODULE_BYTES", 1024)
    monkeypatch.setattr(admission, "MAX_TOTAL_MODULE_BYTES", 1)
    with pytest.raises(SourceAdmissionError, match="MODULE_SET_TOO_LARGE"):
        lock.load()


@pytest.mark.parametrize("source", [b"from . import unlisted\nrun = 1\n",
                                   b"from .unlisted import run\n",
                                   b"from .nested.module import run\n"])
def test_relative_imports_cannot_search_source_directory(tmp_path, source):
    lock, _ = lock_for(tmp_path, {"api": source})
    (tmp_path / "original" / "unlisted.py").write_text("raise AssertionError('unlisted executed')\n")
    namespace = namespace_for(lock)
    with pytest.raises(ImportError):
        lock.load()
    assert not any(k == namespace or k.startswith(namespace + ".") for k in sys.modules)


def test_dependency_order_is_explicit_and_forward_import_unsupported(tmp_path):
    lock, _ = lock_for(tmp_path, {"api": b"from .helper import twice\nrun = twice\n",
                                "helper": b"def twice(x):\n    return x * 2\n"},
                       {"run": {"module": "api", "attribute": "run"}})
    with pytest.raises(ImportError):
        lock.load()


def test_missing_export_rolls_back_own_modules(tmp_path):
    lock, _ = lock_for(tmp_path, {"api": b"value = 1\n"})
    namespace = namespace_for(lock)
    with pytest.raises(SourceAdmissionError, match="MISSING_EXPORT_ATTRIBUTE"):
        lock.load()
    assert namespace not in admission._CACHE
    assert not any(k == namespace or k.startswith(namespace + ".") for k in sys.modules)


@pytest.mark.parametrize("suffix", ["", ".api", ".foreign"])
def test_foreign_namespace_collision_fails_closed(tmp_path, suffix):
    lock, _ = lock_for(tmp_path)
    namespace = namespace_for(lock)
    foreign = ModuleType(namespace + suffix)
    sys.modules[namespace + suffix] = foreign
    with pytest.raises(SourceAdmissionError, match="SOURCE_NAMESPACE_COLLISION"):
        lock.load()
    assert sys.modules[namespace + suffix] is foreign
    assert namespace not in admission._CACHE


@pytest.mark.parametrize("kind", ["package", "module", "child", "attribute"])
def test_cached_namespace_tampering_is_not_adopted(tmp_path, kind):
    lock, _ = lock_for(tmp_path)
    result = lock.load()
    foreign = ModuleType("foreign")
    if kind == "package":
        sys.modules[result.namespace] = foreign
    elif kind == "module":
        sys.modules[result.namespace + ".api"] = foreign
    elif kind == "child":
        sys.modules[result.namespace + ".foreign"] = foreign
    else:
        setattr(sys.modules[result.namespace], "api", foreign)
    with pytest.raises(SourceAdmissionError, match="SOURCE_NAMESPACE_COLLISION"):
        lock.load()


def test_rollback_does_not_remove_foreign_replacement_or_child(tmp_path):
    source = (b"import sys\nfrom types import ModuleType\n"
              b"sys.modules[__package__ + '.foreign'] = ModuleType('foreign')\n"
              b"sys.modules[__name__] = ModuleType('replacement')\n"
              b"raise RuntimeError('fixture failure')\n")
    lock, _ = lock_for(tmp_path, {"api": source})
    namespace = namespace_for(lock)
    with pytest.raises(RuntimeError, match="fixture failure"):
        lock.load()
    assert namespace not in sys.modules
    assert sys.modules[namespace + ".api"].__name__ == "replacement"
    assert sys.modules[namespace + ".foreign"].__name__ == "foreign"
    assert namespace not in admission._CACHE
    with pytest.raises(SourceAdmissionError, match="SOURCE_NAMESPACE_COLLISION"):
        lock.load()


def test_base_exception_cleanup(tmp_path):
    lock, _ = lock_for(tmp_path, {"api": b"raise KeyboardInterrupt()\n"})
    namespace = namespace_for(lock)
    with pytest.raises(KeyboardInterrupt):
        lock.load()
    assert namespace not in sys.modules
    assert namespace + ".api" not in sys.modules


def test_cache_binding_includes_root_manifest_and_module_identity(tmp_path):
    one, two = tmp_path / "one", tmp_path / "two"
    one.mkdir()
    two.mkdir()
    first, _ = lock_for(one)
    second, _ = lock_for(two)
    a, b = first.load(), second.load()
    assert a.namespace != b.namespace
    assert a.exports["run"] is not b.exports["run"]
    manifest_path = one / "lock.json"
    raw = manifest_path.read_bytes() + b"\n"
    same_sources = write_raw(one, raw).load()
    assert same_sources.namespace != a.namespace
    new, _ = lock_for(one, {"api": b"run = 42\n"})
    assert new.load().namespace != a.namespace
    assert new.load().exports["run"] == 42


def test_concurrent_loads_return_one_canonical_object(tmp_path):
    marker = tmp_path / "executions"
    source = (f"from pathlib import Path\nwith Path({str(marker)!r}).open('a') as stream:\n"
              "    stream.write('executed\\n')\ndef run(x):\n    return x\n").encode()
    lock, _ = lock_for(tmp_path, {"api": source})
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: lock.load(), range(24)))
    assert all(result is results[0] for result in results)
    assert marker.read_text() == "executed\n"


@pytest.mark.parametrize("character", ["\n", "\x7f", "\x85", "\ud800", "\udcff", "\udfff"])
def test_unsupported_root_unicode_fails_at_configuration(tmp_path, character):
    with pytest.raises(SourceAdmissionError, match="UNSAFE_ROOT"):
        SourceLock(tmp_path / ("root" + character), "lock.json", "a" * 64)


def test_normal_unicode_root_is_supported(tmp_path):
    root = tmp_path / "caf\u00e9"
    root.mkdir()
    lock, _ = lock_for(root)
    assert lock.load().exports["run"](5) == 10
