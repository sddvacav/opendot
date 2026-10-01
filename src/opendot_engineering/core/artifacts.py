# Extraction and documentation changes: OpenDot Engineering contributors, 2026
# SPDX-License-Identifier: Apache-2.0
# Extracted canonical artifact closure; see docs/PROVENANCE.md for changes.

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import tempfile
import threading
from pathlib import Path
from typing import Any

from .contracts import ArtifactRef

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ArtifactIntegrityError(RuntimeError):
    pass


class ArtifactStore:
    """Canonical SHA-256 store for a trusted, caller-controlled local root.

    Atomic replacement is per file, not an object/metadata transaction. Paths
    follow symlinks; this store is not a sandbox or an access-control boundary.
    See docs/canonical-artifacts.md for persistence and metadata limitations.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.objects = self.root / "objects"
        self.meta = self.root / "meta"
        self._write_lock = threading.RLock()
        self.objects.mkdir(parents=True, exist_ok=True)
        self.meta.mkdir(parents=True, exist_ok=True)
        for directory in (self.root, self.objects, self.meta):
            try:
                os.chmod(directory, 0o700)
            except OSError:
                pass

    @staticmethod
    def sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def _atomic_write(path: Path, data: bytes, *, mode: int = 0o444) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(path.parent, 0o700)
        except OSError:
            pass
        # Keep the temporary basename short.  Content-addressed targets already
        # carry a 62/64-character digest, and reusing that digest as the prefix
        # can push an otherwise valid Windows target beyond MAX_PATH.
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                "wb", dir=path.parent, prefix=".tmp-", delete=False
            ) as handle:
                temporary = Path(handle.name)
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.chmod(temporary, mode)
            except OSError:
                pass
            os.replace(temporary, path)
        except BaseException as error:
            if temporary is not None:
                try:
                    try:
                        temporary.unlink(missing_ok=True)
                    except PermissionError:
                        # Windows cannot unlink a read-only unpublished file.
                        os.chmod(temporary, 0o600)
                        temporary.unlink(missing_ok=True)
                except OSError as cleanup_error:
                    error.add_note(f"Could not remove unpublished artifact temporary {temporary}: {cleanup_error}")
            raise

    def put_bytes(
        self,
        data: bytes,
        *,
        mime_type: str = "application/octet-stream",
        producer: str = "unknown",
        task_id: str = "unknown",
        schema_version: str = "1.0.0",
        source_refs: tuple[str, ...] = (),
    ) -> ArtifactRef:
        if not isinstance(data, bytes):
            raise TypeError("artifact data must be bytes")
        with self._write_lock:
            return self._put_bytes_locked(
                data,
                mime_type=mime_type,
                producer=producer,
                task_id=task_id,
                schema_version=schema_version,
                source_refs=source_refs,
            )

    def _put_bytes_locked(
        self,
        data: bytes,
        *,
        mime_type: str,
        producer: str,
        task_id: str,
        schema_version: str,
        source_refs: tuple[str, ...],
    ) -> ArtifactRef:
        digest = self.sha256(data)
        path = self.objects / digest[:2] / digest[2:]
        if path.exists():
            if path.read_bytes() != data:
                raise ArtifactIntegrityError("hash collision or corrupted existing object")
        else:
            self._atomic_write(path, data)
        ref = ArtifactRef(
            artifact_id=f"sha256:{digest}",
            uri=f"artifact://sha256/{digest}",
            mime_type=mime_type,
            size_bytes=len(data),
            sha256=digest,
            schema_version=schema_version,
            producer=producer,
            task_id=task_id,
            source_refs=source_refs,
            integrity_verified=True,
        )
        ref.validate()
        metadata_path = self.meta / f"{digest}.json"
        if metadata_path.exists():
            try:
                previous = json.loads(metadata_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ArtifactIntegrityError("corrupt artifact metadata") from exc
            if previous.get("sha256") != digest or previous.get("size_bytes") != len(data):
                raise ArtifactIntegrityError("artifact metadata does not match object")
        else:
            self._atomic_write(
                metadata_path,
                (json.dumps(ref.__dict__, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
            )
        return ref

    def put_text(self, text: str, **kwargs: Any) -> ArtifactRef:
        return self.put_bytes(text.encode("utf-8"), mime_type="text/plain; charset=utf-8", **kwargs)

    def put_json(self, value: Any, **kwargs: Any) -> ArtifactRef:
        data = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
        return self.put_bytes(data, mime_type="application/json", **kwargs)

    def put_file(self, path: str | Path, **kwargs: Any) -> ArtifactRef:
        path = Path(path)
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        return self.put_bytes(path.read_bytes(), mime_type=mime, **kwargs)

    def _path(self, digest: str) -> Path:
        digest = digest.removeprefix("sha256:")
        if not _SHA256.fullmatch(digest):
            raise ArtifactIntegrityError("invalid artifact digest")
        return self.objects / digest[:2] / digest[2:]

    def get_bytes(self, ref: ArtifactRef | str) -> bytes:
        digest = ref.sha256 if isinstance(ref, ArtifactRef) else ref.removeprefix("sha256:")
        data = self._path(digest).read_bytes()
        if self.sha256(data) != digest:
            raise ArtifactIntegrityError(f"artifact {digest} failed integrity verification")
        return data

    def verify(self, ref: ArtifactRef) -> bool:
        try:
            ref.validate()
            data = self.get_bytes(ref)
        except (OSError, ValueError, ArtifactIntegrityError):
            return False
        return len(data) == ref.size_bytes and self.sha256(data) == ref.sha256

    def verify_id(self, artifact_id: str) -> bool:
        """Verify that a SHA-256 reference resolves to matching bytes in this store."""
        if not isinstance(artifact_id, str) or not artifact_id.startswith("sha256:"):
            return False
        try:
            data = self.get_bytes(artifact_id)
            digest = artifact_id.removeprefix("sha256:")
        except (OSError, ValueError, ArtifactIntegrityError):
            return False
        return self.sha256(data) == digest
