"""Explicit, pinned admission of operator-reviewed local Python modules.

Modified derivative of the Apache-2.0 OpenDot Engineering integration adapter;
see docs/PROVENANCE.md. Filesystem/JSON validation retains the source_audit owner.
An optional operator-pinned adapter, not authorization or a Python sandbox.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import keyword
import math
import os
from pathlib import Path
import re
import sys
import threading
from types import MappingProxyType, ModuleType
from typing import Any, Mapping

from .source_audit import (
    AuditRejected as SourceAdmissionError,
    _decode, _hash, _keys, _read, _relative, _require, _root_fd, _sha256,
)

SCHEMA = "opendot.source-lock.v1"
MAX_MANIFEST_BYTES = 64 * 1024
MAX_MODULE_BYTES = 1024 * 1024
MAX_TOTAL_MODULE_BYTES = 8 * 1024 * 1024
MAX_MODULES = 32
MAX_EXPORTS = 64
MAX_JSON_NODES = 2048
MAX_JSON_DEPTH = 8
_LOCK = threading.RLock()
_CACHE: dict[str, "AdmittedSource"] = {}


def _identifier(value: Any) -> None:
    _require(type(value) is str and
             re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,79}", value) is not None and
             not keyword.iskeyword(value), "INVALID_PYTHON_IDENTIFIER")


def _path_text(value: str, code: str) -> None:
    # Source-lock policy rejects controls and non-scalar Unicode; filesystem
    # operations remain owned by source_audit rather than duplicated here.
    _require(not any(ord(char) < 32 or 0x7F <= ord(char) <= 0x9F or
                     0xD800 <= ord(char) <= 0xDFFF for char in value), code)


def _source_relative(value: Any) -> list[str]:
    parts = _relative(value)
    _path_text(value, "INVALID_LOCAL_PATH")
    return parts


def _bounded_json(value: Any) -> None:
    """Bound already size-limited JSON and reject overflowed numeric literals."""
    pending = [(value, 0)]
    count = 0
    while pending:
        item, depth = pending.pop()
        count += 1
        _require(count <= MAX_JSON_NODES and depth <= MAX_JSON_DEPTH,
                 "JSON_STRUCTURE_TOO_LARGE")
        if type(item) is str:
            _require(len(item) <= 1024, "JSON_TEXT_TOO_LARGE")
        elif type(item) is float:
            _require(math.isfinite(item), "NONFINITE_JSON")
        elif type(item) is dict:
            pending.extend((part, depth + 1) for pair in item.items() for part in pair)
        elif type(item) is list:
            pending.extend((part, depth + 1) for part in item)


@dataclass(frozen=True, slots=True)
class SourceLock:
    """Trusted startup configuration. Never construct from task or remote input.

    The operator must obtain expected_manifest_sha256 independently from the
    reviewed manifest. No default root, backend, manifest, or pin is provided.
    manifest is a POSIX relative path within approved_root.
    """
    approved_root: Path
    manifest: str
    expected_manifest_sha256: str

    def __post_init__(self) -> None:
        _require(isinstance(self.approved_root, (str, Path)), "UNSAFE_ROOT")
        root = Path(self.approved_root)
        _require(root.is_absolute() and ".." not in root.parts, "UNSAFE_ROOT")
        _path_text(str(root), "UNSAFE_ROOT")
        _source_relative(self.manifest)
        _hash(self.expected_manifest_sha256, 64)
        object.__setattr__(self, "approved_root", root)

    def load(self) -> "AdmittedSource":
        """Reverify all inputs, then return the canonical source-owned objects."""
        return load_source_lock(self)


@dataclass(frozen=True, slots=True)
class AdmittedSource:
    namespace: str
    manifest_sha256: str
    module_sha256: Mapping[str, str]
    modules: Mapping[str, ModuleType]
    exports: Mapping[str, Any]
    _package: ModuleType = field(repr=False)

    def provenance(self) -> dict[str, Any]:
        return {
            "schema": "opendot.source-admission.receipt.v1",
            "manifest_sha256": self.manifest_sha256,
            "module_sha256": dict(self.module_sha256),
            "load_mode": "captured_modules_without_package_initializer",
            "account_authorization": "NOT_EVALUATED",
            "license_permission": "NOT_EVALUATED",
            "scientific_acceptance": "NOT_EVALUATED",
            "sandbox": False,
        }


def _capture(lock: SourceLock) -> tuple[dict[str, Any], dict[str, bytes]]:
    _require(type(lock) is SourceLock, "INVALID_SOURCE_LOCK")
    fd = _root_fd(lock.approved_root)
    try:
        raw = _read(fd, lock.manifest, MAX_MANIFEST_BYTES)
        _require(_sha256(raw) == lock.expected_manifest_sha256,
                 "MANIFEST_HASH_MISMATCH")
        spec = _decode(raw)
        _bounded_json(spec)
        _keys(spec, {"schema", "modules", "exports"})
        _require(type(spec["schema"]) is str and spec["schema"] == SCHEMA,
                 "INVALID_SOURCE_LOCK_SCHEMA")
        rows = spec["modules"]
        _require(type(rows) is list and 0 < len(rows) <= MAX_MODULES,
                 "INVALID_MODULE_COUNT")
        exports = spec["exports"]
        _require(type(exports) is dict and 0 < len(exports) <= MAX_EXPORTS,
                 "INVALID_EXPORT_COUNT")
        seen, paths = set(), set()
        for row in rows:
            _keys(row, {"name", "path", "sha256"})
            _identifier(row["name"])
            parts = _source_relative(row["path"])
            _require(parts[-1].endswith(".py") and parts[-1] != "__init__.py",
                     "INVALID_MODULE_PATH")
            _hash(row["sha256"], 64)
            _require(row["name"] not in seen and row["path"] not in paths,
                     "DUPLICATE_MODULE")
            seen.add(row["name"])
            paths.add(row["path"])
        for alias, binding in exports.items():
            _identifier(alias)
            _keys(binding, {"module", "attribute"})
            _identifier(binding["module"])
            _identifier(binding["attribute"])
            _require(binding["module"] in seen, "UNKNOWN_EXPORT_MODULE")
        # Capture every exact byte string before any source is compiled/executed.
        sources, total = {}, 0
        for row in rows:
            data = _read(fd, row["path"], MAX_MODULE_BYTES)
            total += len(data)
            _require(total <= MAX_TOTAL_MODULE_BYTES, "MODULE_SET_TOO_LARGE")
            _require(_sha256(data) == row["sha256"], "MODULE_HASH_MISMATCH")
            sources[row["name"]] = data
        return spec, sources
    finally:
        os.close(fd)


def _namespace(lock: SourceLock, spec: dict[str, Any]) -> str:
    # Explicit framing binds the root, exact manifest bytes, and ordered pins.
    parts = [str(lock.approved_root), lock.expected_manifest_sha256]
    parts.extend(row[key] for row in spec["modules"] for key in ("name", "path", "sha256"))
    return "_opendot_source_" + _sha256("\0".join(parts).encode("utf-8"))


def _check_namespace(namespace: str, owned: Mapping[str, ModuleType]) -> None:
    present = {name for name in tuple(sys.modules)
               if name == namespace or name.startswith(namespace + ".")}
    _require(present == set(owned) and
             all(sys.modules.get(name) is module for name, module in owned.items()),
             "SOURCE_NAMESPACE_COLLISION")


def load_source_lock(lock: SourceLock) -> AdmittedSource:
    """Admit an explicit flat module list in its reviewed dependency order.

    Standard relative imports resolve only previously loaded listed siblings;
    forward imports and subpackages are deliberately unsupported. Absolute
    imports and source side effects are ordinary trusted Python execution.
    """
    spec, sources = _capture(lock)  # Also performed on every cache hit.
    namespace = _namespace(lock, spec)
    with _LOCK:
        cached = _CACHE.get(namespace)
        if cached is not None:
            owned = {namespace: cached._package}
            owned.update((f"{namespace}.{name}", module)
                         for name, module in cached.modules.items())
            _check_namespace(namespace, owned)
            _require(all(getattr(cached._package, name, None) is module
                         for name, module in cached.modules.items()),
                     "SOURCE_NAMESPACE_COLLISION")
            return cached
        _check_namespace(namespace, {})
        # Precompile the verified snapshot to reject syntax errors before execution.
        compiled = {row["name"]: compile(sources[row["name"]],
                    str(lock.approved_root / row["path"]), "exec", dont_inherit=True)
                    for row in spec["modules"]}
        package = ModuleType(namespace)
        package.__package__ = namespace
        package.__path__ = []  # No filesystem search for unlisted relative imports.
        owned = {namespace: package}
        sys.modules[namespace] = package
        loaded: dict[str, ModuleType] = {}
        try:
            for row in spec["modules"]:
                name = row["name"]
                qualified = f"{namespace}.{name}"
                _check_namespace(namespace, owned)
                module = ModuleType(qualified)
                module.__package__ = namespace
                module.__file__ = str(lock.approved_root / row["path"])
                owned[qualified] = module
                sys.modules[qualified] = module
                setattr(package, name, module)
                exec(compiled[name], module.__dict__)
                loaded[name] = module
            _check_namespace(namespace, owned)
            _require(all(getattr(package, name, None) is module
                         for name, module in loaded.items()), "SOURCE_NAMESPACE_COLLISION")
            exports = {}
            for alias, binding in spec["exports"].items():
                module = loaded[binding["module"]]
                _require(binding["attribute"] in module.__dict__, "MISSING_EXPORT_ATTRIBUTE")
                exports[alias] = module.__dict__[binding["attribute"]]
            result = AdmittedSource(
                namespace=namespace,
                manifest_sha256=lock.expected_manifest_sha256,
                module_sha256=MappingProxyType({row["name"]: row["sha256"] for row in spec["modules"]}),
                modules=MappingProxyType(loaded),
                exports=MappingProxyType(exports),
                _package=package,
            )
        except BaseException:
            # Never erase a replacement or an unrelated module inserted by source.
            for name, module in owned.items():
                if sys.modules.get(name) is module:
                    del sys.modules[name]
            raise
        _CACHE[namespace] = result
        return result
