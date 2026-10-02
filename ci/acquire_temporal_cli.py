"""Acquire, verify and unpack the optional pinned CLI; never execute it.

This stdlib-only helper is inert on import. It accepts no configurable URL, pin,
platform or member name. A trusted, caller-owned parent directory is required;
this is not protection against concurrent hostile filesystem mutation. The
private receipt records hashes computed from the bytes actually acquired.
"""
from __future__ import annotations

import argparse
from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import dataclass
import errno
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import ssl
import tarfile
import tempfile
import time
from typing import BinaryIO, Iterator
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener, getproxies

CLI_VERSION = "1.9.1"
PLATFORM = "linux-x86_64"
RECEIPT_NAME = "acquisition-receipt.json"
SCHEMA_VERSION = "opendot.temporal.cli-acquisition.v1"
DOWNLOAD_SECONDS = 110.0
SOCKET_TIMEOUT_SECONDS = 10.0
CHUNK_BYTES = 64 * 1024
MEMBER_LIMITS = {"temporal": 192 * 1024 * 1024, "LICENSE": 64 * 1024}
MAX_TRAILING_ZERO_BYTES = 10 * 1024
RELEASE_BASE = "https://github.com/temporalio/cli/releases/download/v1.9.1/"


@dataclass(frozen=True)
class Asset:
    name: str
    size_bytes: int
    sha256: str

    @property
    def url(self) -> str:
        return RELEASE_BASE + self.name


ARCHIVE = Asset(
    "temporal_cli_1.9.1_linux_amd64.tar.gz", 45_298_806,
    "09a0326a51db84d02735e53542b9ebd8c4758daf47482a9ab0abce15844e60d5",
)
CHECKSUMS = Asset(
    "checksums.txt", 836,
    "cc22cb0df0a9bab358500dce212616e8622b0649df68317d9858867d7dc69bd2",
)


class AcquisitionError(Exception):
    """A fixed failure code, never a remote response or a private local path."""


def _failure_code(error: Exception) -> str:
    """Classify only exception types and recognized errno values, never text.

    urllib may wrap transport exceptions in URLError.reason. Inspect only a
    bounded chain of exception-valued reasons; strings, repr, response bodies,
    URLs and arbitrary exception causes are deliberately ignored. This is a
    category for this failure, not a diagnosis of prior acquisition attempts.
    """
    for _ in range(4):
        if isinstance(error, HTTPError):
            return "HTTP_ERROR"
        if isinstance(error, ssl.SSLCertVerificationError):
            return "TLS_VERIFICATION_FAILED"
        if isinstance(error, ssl.SSLError):
            return "TLS_ERROR"
        if isinstance(error, TimeoutError):
            return "NETWORK_TIMEOUT"
        if isinstance(error, OSError) and type(error.errno) is int:
            if error.errno in (errno.EACCES, errno.EPERM):
                return "PERMISSION_DENIED"
            if error.errno in (errno.ENETUNREACH, errno.EHOSTUNREACH, errno.ENETDOWN):
                return "NETWORK_UNREACHABLE"
        if not isinstance(error, URLError) or not isinstance(error.reason, Exception):
            break
        error = error.reason
    return "ACQUISITION_FAILED"


def _check_deadline(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise AcquisitionError("ACQUISITION_DEADLINE")
    return min(SOCKET_TIMEOUT_SECONDS, remaining)


def _official_url(url: str) -> bool:
    """Allow only GitHub's release download and release-asset TLS origins."""
    try:
        value = urlsplit(url)
        if (value.scheme != "https" or value.username is not None
                or value.password is not None or value.port not in (None, 443)
                or value.fragment or any(ord(c) <= 32 or ord(c) == 127 for c in url)):
            return False
        if value.hostname == "github.com":
            return url in (ARCHIVE.url, CHECKSUMS.url)
        return value.hostname == "release-assets.githubusercontent.com" and bool(value.path)
    except ValueError:
        return False


class _OfficialRedirects(HTTPRedirectHandler):
    max_repeats = 1
    max_redirections = 3

    def redirect_request(self, request, fp, code, msg, headers, newurl):
        if not _official_url(newurl):
            raise AcquisitionError("UNAPPROVED_DOWNLOAD_REDIRECT")
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def _proxy_environment() -> Mapping[str, str]:
    # Separate read seam for synthetic tests; never mutate the real environment.
    return os.environ


def _require_unconfigured_proxy_routing() -> None:
    """Refuse configured or unreadable routing without inspecting credentials.

    Read raw names as well as urllib's effective/platform configuration: CGI
    rules, lowercase overrides and NO_PROXY can hide nonempty environment
    values from getproxies(). Empty environment values are admitted only when
    the effective mapping is empty too. No routing setting is changed.
    """
    try:
        environment = _proxy_environment()
        if not isinstance(environment, Mapping):
            raise ValueError
        for name, value in environment.items():
            if type(name) is not str or type(value) is not str:
                raise ValueError
            if name.lower().endswith("_proxy") and value != "":
                raise ValueError
        effective = getproxies()
        if not isinstance(effective, Mapping) or len(effective) != 0:
            raise ValueError
    except Exception:
        raise AcquisitionError("PROXY_CONFIGURATION_REFUSED") from None


def _build_opener():
    # Admission precedes even opener construction. Normal urllib handlers keep
    # their default routing and verified TLS; no proxy handler is overridden.
    _require_unconfigured_proxy_routing()
    opener = build_opener(_OfficialRedirects())
    try:
        # urllib reads configuration again during construction. Refuse routing
        # that appeared in that interval before any request can be made.
        for handler in opener.handlers:
            if isinstance(handler, ProxyHandler):
                if not isinstance(handler.proxies, Mapping) or len(handler.proxies) != 0:
                    raise ValueError
    except Exception:
        raise AcquisitionError("PROXY_CONFIGURATION_REFUSED") from None
    # urllib does not load netrc, cookies or browser credentials here. This is
    # a trusted-process check, not protection against later hostile mutation.
    return opener


@contextmanager
def _private_file(path: Path) -> Iterator[BinaryIO]:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        yield stream
        stream.flush()
        os.fsync(stream.fileno())


def _download(asset: Asset, path: Path, opener, deadline: float) -> dict:
    request = Request(asset.url, headers={
        "Accept-Encoding": "identity", "User-Agent": "OpenDot-Temporal-CI-Acquisition/1",
    })
    digest = hashlib.sha256()
    size = 0
    with opener.open(request, timeout=_check_deadline(deadline)) as response:
        if response.status != 200 or not _official_url(response.geturl()):
            raise AcquisitionError("UNAPPROVED_DOWNLOAD_RESPONSE")
        encoding = response.headers.get("Content-Encoding")
        if encoding not in (None, "identity"):
            raise AcquisitionError("UNEXPECTED_CONTENT_ENCODING")
        length = response.headers.get("Content-Length")
        if length is not None and length != str(asset.size_bytes):
            raise AcquisitionError("DOWNLOAD_SIZE_MISMATCH")
        # HTTPResponse.read1 performs at most one network read, unlike read(n),
        # so a slow trickle cannot reset the per-read timeout indefinitely.
        with _private_file(path) as destination:
            while True:
                _check_deadline(deadline)
                chunk = response.read1(min(CHUNK_BYTES, asset.size_bytes - size + 1))
                _check_deadline(deadline)
                if not chunk:
                    break
                size += len(chunk)
                if size > asset.size_bytes:
                    raise AcquisitionError("DOWNLOAD_SIZE_MISMATCH")
                destination.write(chunk)
                digest.update(chunk)
    actual_hash = digest.hexdigest()
    if size != asset.size_bytes:
        raise AcquisitionError("DOWNLOAD_SIZE_MISMATCH")
    if actual_hash != asset.sha256:
        raise AcquisitionError("DOWNLOAD_HASH_MISMATCH")
    return {"name": asset.name, "url": asset.url,
            "size_bytes": size, "sha256": actual_hash}


def _verify_manifest(path: Path) -> None:
    try:
        text = path.read_bytes().decode("ascii", errors="strict")
    except UnicodeError:
        raise AcquisitionError("INVALID_CHECKSUM_MANIFEST") from None
    names = set()
    matched = False
    for line in text.splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_.-]+)", line)
        if match is None or match[2] in names:
            raise AcquisitionError("INVALID_CHECKSUM_MANIFEST")
        names.add(match[2])
        if match[2] == ARCHIVE.name:
            if match[1] != ARCHIVE.sha256:
                raise AcquisitionError("CHECKSUM_ARCHIVE_MISMATCH")
            matched = True
    if not matched:
        raise AcquisitionError("CHECKSUM_ARCHIVE_MISSING")


def _read_exact(stream: BinaryIO, length: int, deadline: float) -> bytes:
    # Callers request at most CHUNK_BYTES, never an untrusted member size.
    output = bytearray()
    while len(output) < length:
        _check_deadline(deadline)
        chunk = stream.read(length - len(output))
        if not chunk:
            raise AcquisitionError("TRUNCATED_ARCHIVE")
        output.extend(chunk)
    return bytes(output)


def _extract_archive(path: Path, output: Path, deadline: float) -> dict:
    """Interpret only ordinary tar file headers and copy two fixed filenames.

    Deliberately do not use extract/extractall or tarfile's metadata expansion:
    PAX/GNU long-name and sparse headers are rejected before their payload is
    read. This also bounds decompression of hostile metadata and archive bombs.
    """
    files = {}
    with path.open("rb") as compressed, gzip.GzipFile(fileobj=compressed, mode="rb") as stream:
        while True:
            header = _read_exact(stream, tarfile.BLOCKSIZE, deadline)
            if header == bytes(tarfile.BLOCKSIZE):
                if _read_exact(stream, tarfile.BLOCKSIZE, deadline) != bytes(tarfile.BLOCKSIZE):
                    raise AcquisitionError("INVALID_ARCHIVE_END")
                trailing_size = 0
                while True:
                    _check_deadline(deadline)
                    padding = stream.read(min(CHUNK_BYTES, MAX_TRAILING_ZERO_BYTES - trailing_size + 1))
                    if not padding:
                        break
                    trailing_size += len(padding)
                    if trailing_size > MAX_TRAILING_ZERO_BYTES or any(padding):
                        raise AcquisitionError("UNEXPECTED_ARCHIVE_TRAILER")
                break
            try:
                member = tarfile.TarInfo.frombuf(header, "utf-8", "strict")
            except (tarfile.HeaderError, UnicodeError, ValueError):
                raise AcquisitionError("INVALID_ARCHIVE_HEADER") from None
            if member.type not in (tarfile.REGTYPE, tarfile.AREGTYPE) or member.linkname:
                raise AcquisitionError("UNSAFE_ARCHIVE_MEMBER")
            if member.name not in MEMBER_LIMITS:
                raise AcquisitionError("UNEXPECTED_ARCHIVE_MEMBER")
            if member.name in files:
                raise AcquisitionError("DUPLICATE_ARCHIVE_MEMBER")
            if not 0 < member.size <= MEMBER_LIMITS[member.name]:
                raise AcquisitionError("ARCHIVE_MEMBER_SIZE")
            if member.mode & ~0o777:
                raise AcquisitionError("UNSAFE_ARCHIVE_MODE")
            digest = hashlib.sha256()
            remaining = member.size
            target = output / member.name
            with _private_file(target) as destination:
                while remaining:
                    chunk = _read_exact(stream, min(CHUNK_BYTES, remaining), deadline)
                    destination.write(chunk)
                    digest.update(chunk)
                    remaining -= len(chunk)
            padding_size = (-member.size) % tarfile.BLOCKSIZE
            if padding_size and any(_read_exact(stream, padding_size, deadline)):
                raise AcquisitionError("INVALID_ARCHIVE_PADDING")
            files[member.name] = {"size_bytes": member.size, "sha256": digest.hexdigest()}
        if set(files) != set(MEMBER_LIMITS):
            raise AcquisitionError("MISSING_ARCHIVE_MEMBER")
    # Enable only the owner execute bit after complete structural validation and
    # gzip checksum/trailer validation. Nothing is ever executed by this helper.
    (output / "temporal").chmod(0o700)
    return files


def acquire(output_dir: Path) -> dict:
    """Create a fresh private directory and acquire the fixed Linux amd64 CLI.

    The caller/CI retains an external two-minute step timeout. Monotonic checks
    bound chunk/parse work to 110 seconds and each network blocking operation
    has a ten-second timeout; OS DNS resolution is subject to the host resolver.
    No background worker or subprocess is created to enforce a hard kill bound.
    """
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise AcquisitionError("UNSUPPORTED_PLATFORM")
    output = Path(output_dir)
    try:
        output.mkdir(mode=0o700, parents=False, exist_ok=False)
    except OSError:
        raise AcquisitionError("OUTPUT_NOT_FRESH") from None
    try:
        output.chmod(0o700)
        deadline = time.monotonic() + DOWNLOAD_SECONDS
        opener = _build_opener()
        with tempfile.TemporaryDirectory(prefix=".download-", dir=output) as temporary:
            temporary_path = Path(temporary)
            manifest_path = temporary_path / CHECKSUMS.name
            checksum_record = _download(CHECKSUMS, manifest_path, opener, deadline)
            _verify_manifest(manifest_path)
            archive_path = temporary_path / ARCHIVE.name
            archive_record = _download(ARCHIVE, archive_path, opener, deadline)
            files = _extract_archive(archive_path, output, deadline)
        receipt = {
            "schema_version": SCHEMA_VERSION, "cli_version": CLI_VERSION,
            "platform": PLATFORM, "archive": archive_record,
            "checksums": checksum_record, "files": files,
        }
        encoded = (json.dumps(receipt, sort_keys=True, allow_nan=False, indent=2) + "\n").encode("utf-8")
        with _private_file(output / RECEIPT_NAME) as destination:
            destination.write(encoded)
        return receipt
    except Exception as error:
        try:
            shutil.rmtree(output)
        except OSError:
            raise AcquisitionError("ACQUISITION_CLEANUP_UNCONFIRMED") from None
        if isinstance(error, AcquisitionError):
            raise
        raise AcquisitionError(_failure_code(error)) from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", "--output-dir", dest="output_dir", type=Path, required=True)
    arguments = parser.parse_args(argv)
    try:
        acquire(arguments.output_dir)
    except AcquisitionError as error:
        print(str(error))
        return 1
    print("TEMPORAL_CLI_ACQUIRED_NOT_EXECUTED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
