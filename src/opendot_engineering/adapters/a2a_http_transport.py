"""Optional no-auth HTTPS callback; finite mock qualification only (ADR 007).

The operator owns endpoint authorization and a cooperative environment. This is
an entity acquisition cap and cooperative deadline, not a wire/RSS/DNS sandbox.
No runtime, serializer, store, acceptance, retry or credential owner lives here.
"""
from __future__ import annotations

import http.client
import os
import re
import ssl
from time import monotonic as _monotonic
from typing import Callable

from .a2a_worker_turn import MAX_WIRE_BYTES, PROFILE_SHA256
from .source_audit import _require

_URL_BYTES = 2048
_READ_BYTES = 8192
_DEADLINE_S = 45
_CONNECT_S = 5
_HOST_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")
_URL = re.compile(r"https://([a-z0-9.-]+)(?::([0-9]+))?(/[A-Za-z0-9._~/-]*)\Z")
_MIME = re.compile(r'application/json(?:;[ \t]*charset=(?:utf-8|"utf-8"))?\Z', re.I)
_LENGTH = re.compile(r"(?:0|[1-9][0-9]*)\Z")


class HTTPSExchangeError(RuntimeError):
    """A fixed local refusal code, never original server/exception text."""


class _Refused(Exception):
    pass


def _endpoint(value: object) -> tuple[str, int, str]:
    _require(type(value) is str and 0 < len(value) <= _URL_BYTES, "HTTPS_ENDPOINT")
    _require(value.isascii() and not any(c.isspace() or ord(c) < 33 or ord(c) == 127
                                        for c in value), "HTTPS_ENDPOINT")
    match = _URL.fullmatch(value)
    _require(match is not None, "HTTPS_ENDPOINT")
    host, port_text, path = match.groups()
    labels = host.split(".")
    _require(len(host) <= 253 and all(_HOST_LABEL.fullmatch(label) for label in labels),
             "HTTPS_ENDPOINT")
    # Alphabetic final-label start also excludes legacy numeric/hex IPv4 forms.
    _require("a" <= labels[-1][0] <= "z", "HTTPS_ENDPOINT")
    _require(all(segment not in (".", "..") for segment in path.split("/")),
             "HTTPS_ENDPOINT")
    port = 443
    if port_text is not None:
        _require(len(port_text) <= 5 and port_text[0] != "0", "HTTPS_ENDPOINT")
        port = int(port_text)
        _require(1 <= port <= 65535, "HTTPS_ENDPOINT")
    return host, port, path


def _environment() -> None:
    paths = ssl.get_default_verify_paths()
    trust_keys = {"SSLKEYLOGFILE", "SSL_CERT_FILE", "SSL_CERT_DIR",
                  paths.openssl_cafile_env.upper(), paths.openssl_capath_env.upper()}
    for key, value in os.environ.items():
        upper = key.upper()
        _require(not (upper in {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"} and value),
                 "HTTPS_PROXY_ENVIRONMENT")
        _require(upper not in trust_keys, "HTTPS_TLS_ENVIRONMENT")


def _context() -> ssl.SSLContext:
    # Unlike create_default_context(), this does not enable SSLKEYLOGFILE.
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_default_certs(ssl.Purpose.SERVER_AUTH)
    context.set_alpn_protocols(["http/1.1"])
    return context


def _remaining(deadline: float) -> float:
    remaining = deadline - _monotonic()
    if remaining <= 0:
        raise _Refused("DEADLINE_EXPIRED")
    return remaining


def _headers(response: http.client.HTTPResponse) -> int | None:
    if response.status != 200:
        raise _Refused("HTTP_STATUS")
    if response.headers.defects:
        raise _Refused("HTTP_HEADERS")
    versions = response.headers.get_all("A2A-Version", [])
    # A2A does not require an echo. Present-header strictness is our profile.
    if versions and versions != ["1.0"]:
        raise _Refused("HTTP_VERSION")
    values = {name: response.headers.get_all(name, []) for name in
              ("Content-Type", "Content-Encoding", "Content-Length", "Transfer-Encoding")}
    mime = values["Content-Type"]
    if len(mime) != 1 or _MIME.fullmatch(mime[0].strip(" \t")) is None:
        raise _Refused("HTTP_CONTENT_TYPE")
    encoding = values["Content-Encoding"]
    if encoding and (len(encoding) != 1 or encoding[0].lower() != "identity"):
        raise _Refused("HTTP_CONTENT_ENCODING")
    lengths, transfers = values["Content-Length"], values["Transfer-Encoding"]
    if len(lengths) > 1 or transfers or response.chunked:
        raise _Refused("HTTP_FRAMING")
    # Deliberately refuse all Transfer-Encoding before body reads. CPython's
    # chunk parser can turn a negative size into an unsized backing read1().
    # A backing-reader shim or replacement parser is outside this increment.
    if lengths:
        value = lengths[0]
        if _LENGTH.fullmatch(value) is None:
            raise _Refused("HTTP_FRAMING")
        if len(value) > 6 or int(value) > MAX_WIRE_BYTES:
            raise _Refused("ENTITY_TOO_LARGE")
        length = int(value)
        if response.length != length:
            raise _Refused("HTTP_FRAMING")
        return length
    if response.length is not None:
        raise _Refused("HTTP_FRAMING")
    return None


def _perform(host: str, port: int, path: str, request: bytes) -> tuple[bytes | None, str | None]:
    """Keep original error/response/partial frames out of the raised exception."""
    connection = response = None
    collected = bytearray()
    result = None
    failure = None
    try:
        deadline = _monotonic() + _DEADLINE_S
        context = _context()
        connection = http.client.HTTPSConnection(
            host, port=port, timeout=min(_CONNECT_S, _remaining(deadline)), context=context)
        connection.set_debuglevel(0)
        connection.connect()
        _remaining(deadline)
        sock = connection.sock
        if sock is None:
            raise _Refused("CONNECTION_STATE")
        # http.client.send() may otherwise connect implicitly if sock is absent.
        connection.auto_open = 0
        sock.settimeout(_remaining(deadline))
        connection.request("POST", path, body=request, headers={
            "Content-Type": "application/json", "Accept": "application/json",
            "A2A-Version": "1.0", "Content-Length": str(len(request)),
            "Accept-Encoding": "identity", "Connection": "close",
        })
        sock.settimeout(_remaining(deadline))
        response = connection.getresponse()
        _remaining(deadline)
        declared = _headers(response)
        # A completed fixed-length response can close its last socket-file
        # reference inside read1(). Do not touch that socket again afterward.
        while declared is None or len(collected) < declared:
            sock.settimeout(_remaining(deadline))
            amount = min(_READ_BYTES, MAX_WIRE_BYTES - len(collected) + 1)
            chunk = response.read1(amount)
            _remaining(deadline)
            if type(chunk) is not bytes or len(chunk) > amount:
                raise _Refused("BODY_READ_SIZE")
            if len(collected) + len(chunk) > MAX_WIRE_BYTES:
                raise _Refused("ENTITY_TOO_LARGE")
            if not chunk:
                break
            collected.extend(chunk)
        if declared is not None and len(collected) != declared:
            raise _Refused("HTTP_TRUNCATED")
        result = bytes(collected)
    except _Refused as refusal:
        failure = refusal.args[0]
    except TimeoutError:
        failure = "IO_TIMEOUT"
    except ssl.SSLError:
        failure = "TLS_FAILURE"
    except http.client.HTTPException:
        failure = "HTTP_FAILURE"
    except Exception:
        failure = "IO_FAILURE"
    finally:
        # Never drain a refused body, log exception text or preserve partial data.
        for resource in (response, connection):
            if resource is not None:
                try:
                    resource.close()
                except Exception:
                    if failure is None:
                        failure = "CLOSE_FAILURE"
        collected.clear()
    return (None, failure) if failure is not None else (result, None)


def make_https_exchange(*, endpoint_url: str, worker_profile_sha256: str) -> Callable:
    """Capture a trusted no-auth endpoint; construction performs no network I/O.

    Invocation is only authorized after the separate ADR 007 live gate. Mocks
    establish local mechanics, not TLS/worker interoperability or remote budgets.
    """
    _require(type(worker_profile_sha256) is str and worker_profile_sha256 == PROFILE_SHA256,
             "PROFILE_PIN")
    host, port, path = _endpoint(endpoint_url)
    _environment()

    def exchange(request_bytes, *, protocol_version, max_response_bytes, timeout_s) -> bytes:
        _require(type(request_bytes) is bytes and 1 <= len(request_bytes) <= MAX_WIRE_BYTES,
                 "HTTPS_REQUEST_BYTES")
        _require(type(protocol_version) is str and protocol_version == "1.0", "HTTPS_VERSION")
        _require(type(max_response_bytes) is int and max_response_bytes == MAX_WIRE_BYTES,
                 "HTTPS_RESPONSE_CAP")
        _require(type(timeout_s) is int and timeout_s == _DEADLINE_S, "HTTPS_TIMEOUT")
        _environment()
        result, failure = _perform(host, port, path, request_bytes)
        if failure is not None:
            # Raised after _perform returns: no original exception context or
            # traceback holding a partial response body crosses this boundary.
            raise HTTPSExchangeError(failure)
        return result

    return exchange
