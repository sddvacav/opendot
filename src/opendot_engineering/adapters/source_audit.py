"""Pinned local evidence audit. No network, scientific execution, or store owner.

The operator supplies the root and manifest pin independently. A passing receipt
establishes byte/role consistency, never scientific correctness or publication rights.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys

MANIFEST_SCHEMA = "opendot.local-source-audit.v1"
SOURCE_SCHEMA = "opendot.local-evidence.v1"
MAX_MANIFEST_BYTES = 256 * 1024
MAX_SOURCE_BYTES = 2 * 1024 * 1024
MAX_SOURCES = 32
MAX_CLAIMS = 256
ACCESS = frozenset({"public", "private"})
ROLES = frozenset({"synthetic", "measured", "model_prediction", "literature_prior", "posthoc_diagnostic"})
STATES = frozenset({"known", "unknown", "censored"})


class AuditRejected(ValueError):
    """A bounded code, safe to report without echoing private input or OS paths."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _require(condition, code):
    if not condition:
        raise AuditRejected(code)


def _keys(value, expected):
    _require(type(value) is dict and set(value) == set(expected), "INVALID_FIELDS")


def _string(value, code="INVALID_TEXT"):
    _require(type(value) is str and 0 < len(value) <= 1024 and not any(ord(c) < 32 for c in value), code)


def _identifier(value):
    _require(type(value) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", value) is not None, "INVALID_ID")


def _enum(value, choices, code):
    _require(type(value) is str and value in choices, code)


def _hash(value, length):
    _require(type(value) is str and re.fullmatch(r"[0-9a-f]{%d}" % length, value) is not None, "INVALID_PIN")


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _git_blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def _relative(value):
    _string(value, "INVALID_LOCAL_PATH")
    _require("\\" not in value and ":" not in value, "INVALID_LOCAL_PATH")
    parts = value.split("/")
    _require(not PurePosixPath(value).is_absolute() and all(p not in ("", ".", "..") for p in parts), "INVALID_LOCAL_PATH")
    return parts


def _root_fd(root):
    # Descriptor-relative O_NOFOLLOW walking prevents symlink substitutions from
    # redirecting a checked path outside the operator's trusted root.
    _require(hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY") and os.open in os.supports_dir_fd, "UNSUPPORTED_PLATFORM")
    fd = None
    try:
        root = Path(root).absolute()
        _require(root.anchor == "/" and all(p not in (".", "..") for p in root.parts[1:]), "UNSAFE_ROOT")
        fd = os.open(root.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        for part in root.parts[1:]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        return fd
    except (OSError, TypeError, ValueError) as exc:
        if fd is not None:
            os.close(fd)
        if isinstance(exc, AuditRejected):
            raise
        raise AuditRejected("ROOT_UNAVAILABLE") from None


def _read(root_fd, relative, limit):
    parts = _relative(relative)
    fd = os.dup(root_fd)
    try:
        for part in parts[:-1]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        file_fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        with os.fdopen(file_fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            _require(stat.S_ISREG(info.st_mode), "NOT_REGULAR_FILE")
            _require(info.st_size <= limit, "INPUT_TOO_LARGE")
            data = stream.read(limit + 1)
            _require(len(data) <= limit, "INPUT_TOO_LARGE")
            return data
    except OSError:
        raise AuditRejected("LOCAL_INPUT_UNAVAILABLE_OR_UNSAFE") from None
    finally:
        os.close(fd)


def _decode(data):
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, "DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    def constant(_):
        raise AuditRejected("NONFINITE_JSON")
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        if isinstance(exc, AuditRejected):
            raise
        raise AuditRejected("INVALID_JSON") from None


def _pointer(document, pointer):
    _string(pointer, "INVALID_LOCATOR")
    _require(pointer.startswith("/"), "INVALID_LOCATOR")
    node = document
    for token in pointer[1:].split("/"):
        _require(re.search(r"~(?![01])", token) is None, "INVALID_LOCATOR")
        token = token.replace("~1", "/").replace("~0", "~")
        if type(node) is dict:
            _require(token in node, "LOCATOR_NOT_FOUND")
            node = node[token]
        elif type(node) is list:
            _require(re.fullmatch(r"0|[1-9][0-9]*", token) is not None and len(token) < 10, "INVALID_LOCATOR")
            index = int(token)
            _require(index < len(node), "LOCATOR_NOT_FOUND")
            node = node[index]
        else:
            raise AuditRejected("LOCATOR_NOT_FOUND")
    return node


def _observation(row, kind):
    _keys(row, {"quantity", "unit", "condition", "evidence_role", "value_state", "value", "uncertainty", "reason"})
    _string(row["quantity"])
    _string(row["condition"])
    _enum(row["evidence_role"], ROLES, "INVALID_EVIDENCE_ROLE")
    _enum(row["value_state"], STATES, "INVALID_VALUE_STATE")
    _require(kind != "synthetic" or row["evidence_role"] == "synthetic", "FALSE_EVIDENCE_PROMOTION")
    _require(kind != "reported" or row["evidence_role"] != "synthetic", "INCONSISTENT_SOURCE_KIND")
    _string(row["unit"])
    value, uncertainty = row["value"], row["uncertainty"]
    def finite(x):
        try:
            return type(x) in (int, float) and math.isfinite(x)
        except OverflowError:
            return False
    _require(uncertainty is None or (finite(uncertainty) and uncertainty >= 0), "INVALID_UNCERTAINTY")
    if row["value_state"] == "known":
        _require(finite(value), "INVALID_KNOWN_VALUE")
        _require(row["reason"] is None, "INVALID_KNOWN_REASON")
    else:
        _require(value is None and uncertainty is None, "UNKNOWN_OR_CENSORED_MUST_STAY_NULL")
        _string(row["reason"], "MISSING_UNKNOWN_REASON")


def audit_manifest(root, manifest, *, expected_revision, expected_manifest_sha256, audience="private"):
    """Return a metadata-only receipt; no files are written and no code is imported.

    Both expected pins must come from the operator's independently reviewed
    configuration. Git blob hashes alone do not prove membership in a commit.
    """
    _hash(expected_revision, 40)
    _hash(expected_manifest_sha256, 64)
    _enum(audience, ACCESS, "INVALID_ACCESS_CATEGORY")
    root_fd = _root_fd(root)
    try:
        raw_manifest = _read(root_fd, manifest, MAX_MANIFEST_BYTES)
        _require(_sha256(raw_manifest) == expected_manifest_sha256, "MANIFEST_HASH_MISMATCH")
        spec = _decode(raw_manifest)
        _keys(spec, {"schema", "source_revision", "access", "sources", "claims"})
        _require(spec["schema"] == MANIFEST_SCHEMA and spec["source_revision"] == expected_revision, "REVISION_OR_SCHEMA_MISMATCH")
        _enum(spec["access"], ACCESS, "INVALID_ACCESS_CATEGORY")
        _require(audience != "public" or spec["access"] == "public", "PRIVATE_INPUT_FOR_PUBLIC_AUDIENCE")
        _require(type(spec["sources"]) is list and 0 < len(spec["sources"]) <= MAX_SOURCES, "INVALID_SOURCE_COUNT")
        _require(type(spec["claims"]) is list and 0 < len(spec["claims"]) <= MAX_CLAIMS, "INVALID_CLAIM_COUNT")
        documents, sources, paths = {}, [], set()
        for source in spec["sources"]:
            _keys(source, {"source_id", "path", "revision", "sha256", "git_blob_sha1", "access"})
            sid = source["source_id"]
            _identifier(sid)
            _relative(source["path"])
            _require(sid not in documents and source["path"] not in paths, "DUPLICATE_SOURCE")
            _require(source["revision"] == expected_revision, "SOURCE_REVISION_MISMATCH")
            _hash(source["sha256"], 64)
            _hash(source["git_blob_sha1"], 40)
            _enum(source["access"], ACCESS, "INVALID_ACCESS_CATEGORY")
            _require(spec["access"] != "public" or source["access"] == "public", "PRIVATE_INPUT_FOR_PUBLIC_AUDIENCE")
            data = _read(root_fd, source["path"], MAX_SOURCE_BYTES)
            _require(_sha256(data) == source["sha256"], "SOURCE_SHA256_MISMATCH")
            _require(_git_blob(data) == source["git_blob_sha1"], "SOURCE_BLOB_MISMATCH")
            doc = _decode(data)
            _keys(doc, {"schema", "source_id", "source_revision", "access", "content_kind", "observations"})
            _require(doc["schema"] == SOURCE_SCHEMA and doc["source_id"] == sid and doc["source_revision"] == expected_revision, "SOURCE_IDENTITY_MISMATCH")
            _require(doc["access"] == source["access"], "SOURCE_ACCESS_MISMATCH")
            _enum(doc["content_kind"], {"synthetic", "reported"}, "INVALID_SOURCE_KIND")
            _require(type(doc["observations"]) is list and 0 < len(doc["observations"]) <= MAX_CLAIMS, "INVALID_OBSERVATION_COUNT")
            for observation in doc["observations"]:
                _observation(observation, doc["content_kind"])
            documents[sid] = doc
            paths.add(source["path"])
            sources.append({key: source[key] for key in ("source_id", "revision", "sha256", "git_blob_sha1", "access")})
        claims, seen, referenced = [], set(), set()
        for claim in spec["claims"]:
            _keys(claim, {"claim_id", "source_id", "locator", "evidence_role", "value_state", "quantity", "unit"})
            _identifier(claim["claim_id"])
            _identifier(claim["source_id"])
            _string(claim["locator"], "INVALID_LOCATOR")
            _require(claim["claim_id"] not in seen, "DUPLICATE_CLAIM")
            _require(claim["source_id"] in documents, "UNKNOWN_SOURCE_ID")
            _require(re.fullmatch(r"/observations/(0|[1-9][0-9]*)", claim["locator"]) is not None, "INVALID_LOCATOR")
            doc = documents[claim["source_id"]]
            row = _pointer(doc, claim["locator"])
            _observation(row, doc["content_kind"])
            _require(all(claim[k] == row[k] for k in ("evidence_role", "value_state", "quantity", "unit")), "FALSE_EVIDENCE_PROMOTION")
            seen.add(claim["claim_id"])
            referenced.add(claim["source_id"])
            claims.append({k: claim[k] for k in ("claim_id", "source_id", "locator", "evidence_role", "value_state")})
        _require(referenced == set(documents), "UNREFERENCED_SOURCE")
        return {
            "schema": "opendot.local-source-audit.receipt.v1",
            "audit_accepted": True,
            "scientific_accepted": False,
            "scientific_status": "NOT_EVALUATED",
            "source_revision": expected_revision,
            "manifest_sha256": expected_manifest_sha256,
            "adapter_sha256": _sha256(Path(__file__).read_bytes()),
            "audience": audience,
            "sources": sources,
            "claims": claims,
            "limits": ["Operator pins are trusted; Git commit membership is not proved",
                       "Source-declared roles and access are checked, not independently authenticated",
                       "No scientific validation, numeric unit conversion, or unknown-value imputation",
                       "No network, training, solver, instrument, registry, or artifact-store mutation"],
        }
    finally:
        os.close(root_fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--manifest", required=True, help="POSIX relative path inside root")
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--audience", choices=sorted(ACCESS), default="private")
    args = parser.parse_args(argv)
    try:
        result = audit_manifest(args.root, args.manifest, expected_revision=args.expected_revision,
                                expected_manifest_sha256=args.expected_manifest_sha256, audience=args.audience)
    except AuditRejected as exc:
        print(json.dumps({"audit_accepted": False, "scientific_accepted": False, "error_code": exc.code}), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
