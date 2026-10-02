"""Finite fake connections and current-stdlib BytesIO parsing; no live I/O."""
from __future__ import annotations

import ast
from email.message import Message
import hashlib
import http.client
import io
import json
from pathlib import Path
import socket
import ssl

import pytest

from opendot_engineering.adapters import a2a_http_transport as transport
from opendot_engineering.adapters import a2a_worker_turn as worker
from opendot_engineering.adapters.source_audit import AuditRejected
from opendot_engineering.core.artifacts import ArtifactStore
from opendot_engineering.tool_runtime import ToolCallReceipt, ToolRuntime

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / 'tests/fixtures/a2a_worker_turn_v1.json').read_text())
LIMIT = 131072
ENDPOINT = 'https://worker.example/a2a'
OPTIONS = dict(protocol_version='1.0', max_response_bytes=LIMIT, timeout_s=45)


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


@pytest.fixture(autouse=True)
def no_network_and_clean_environment(monkeypatch):
    attempts = []
    def deny(*args, **kwargs):
        attempts.append(True)
        raise AssertionError('NETWORK_ACQUISITION_FORBIDDEN')
    for name in ('socket', 'create_connection', 'getaddrinfo'):
        monkeypatch.setattr(socket, name, deny)
    for key in list(transport.os.environ):
        if key.upper() in {'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'SSLKEYLOGFILE',
                           'SSL_CERT_FILE', 'SSL_CERT_DIR'}:
            monkeypatch.delenv(key)
    yield
    assert attempts == []


def exchange(url=ENDPOINT, pin=worker.PROFILE_SHA256):
    return transport.make_https_exchange(endpoint_url=url, worker_profile_sha256=pin)


class Clock:
    value = 10.0
    def __call__(self):
        return self.value


class FakeSocket:
    def __init__(self):
        self.timeouts = []
    def settimeout(self, timeout):
        self.timeouts.append(timeout)


class FakeResponse:
    def __init__(self, body=b'{}', headers=None, *, status=200, fragment=8192):
        self.body = body
        self.status = status
        self.headers = Message()
        for name, value in (headers if headers is not None else
                            [('Content-Type', 'application/json'), ('Content-Length', str(len(body)))]):
            self.headers[name] = value
        value = self.headers.get('Content-Length')
        try:
            self.length = int(value) if value is not None else None
        except ValueError:
            self.length = None
        self.chunked = self.headers.get('Transfer-Encoding', '').lower() == 'chunked'
        self.fragment = fragment
        self.reads = []
        self.delivered = 0
        self.closed = 0
        self.on_read = self.on_close = lambda: None
    def read1(self, amount):
        self.reads.append(amount)
        self.on_read()
        amount = min(amount, self.fragment)
        if self.length is not None:
            amount = min(amount, max(0, self.length))
        result, self.body = self.body[:amount], self.body[amount:]
        self.delivered += len(result)
        if self.length is not None:
            self.length -= len(result)
        return result
    def close(self):
        self.closed += 1
        self.on_close()


class FakeConnection:
    def __init__(self, response):
        self.response = response
        self.sock = FakeSocket()
        self.calls = []
        self.connected = self.closed = 0
        self.auto_open = 1
        self.on_connect = self.on_request = self.on_headers = self.on_close = lambda: None
    def set_debuglevel(self, level):
        self.debuglevel = level
    def connect(self):
        self.connected += 1
        self.on_connect()
    def request(self, method, path, *, body, headers):
        self.calls.append((method, path, body, headers.copy()))
        assert self.auto_open == 0
        self.on_request()
    def getresponse(self):
        self.on_headers()
        return self.response
    def close(self):
        self.closed += 1
        self.on_close()


@pytest.fixture
def mocks(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(transport, '_monotonic', clock)
    contexts = []
    def context():
        marker = object()
        contexts.append(marker)
        return marker
    monkeypatch.setattr(transport, '_context', context)
    instances = []
    constructor_calls = []
    response = FakeResponse()
    connection = FakeConnection(response)
    def make(host, **kwargs):
        constructor_calls.append((host, kwargs))
        instances.append(connection)
        return connection
    monkeypatch.setattr(transport.http.client, 'HTTPSConnection', make)
    return clock, contexts, constructor_calls, instances, connection, response


@pytest.mark.parametrize('url', [None, b'https://worker.example/a2a', '', 'http://worker.example/a2a',
    'HTTPS://worker.example/a2a', 'https://Worker.example/a2a', 'https://worker.example',
    'https://worker.example./a2a', 'https://worker..example/a2a', 'https://-worker.example/a2a',
    'https://' + 'a' * 64 + '.example/a2a', 'https://worker.example:0/a2a',
    'https://worker.example:65536/a2a', 'https://worker.example:0443/a2a',
    'https://user:secret@worker.example/a2a', 'https://worker.example/a?x=1',
    'https://worker.example/a#fragment', 'https://worker.example/a%2fb',
    'https://worker.example/a\\b', 'https://worker.example/./a', 'https://worker.example/a/../b',
    'https://127.0.0.1/a', 'https://[::1]/a', 'https://127.1/a', 'https://2130706433/a',
    'https://0x7f000001/a', 'https://worker.example/a\n', ' https://worker.example/a',
    'https://wörker.example/a', 'https://worker.example/a\x00', 'https://worker.example/a b',
    'https://worker.example/' + 'x' * 2048], ids=lambda value: repr(value)[:90])
def test_endpoint_refuses_before_acquisition(mocks, url):
    with pytest.raises(AuditRejected, match='HTTPS_ENDPOINT'):
        exchange(url)
    assert mocks[1:4] == ([], [], [])


@pytest.mark.parametrize('url,host,port,path', [
    (ENDPOINT, 'worker.example', 443, '/a2a'),
    ('https://worker.example:1/', 'worker.example', 1, '/'),
    ('https://worker.example:65535/a_b-2.~/', 'worker.example', 65535, '/a_b-2.~/'),
    ('https://worker.example/' + 'x' * (2048 - len('https://worker.example/')),
     'worker.example', 443, '/' + 'x' * (2048 - len('https://worker.example/'))),
], ids=['default-port', 'minimum-port-root', 'maximum-port-path', 'maximum-url-length'])
def test_valid_endpoint_is_captured_and_factory_is_io_free(mocks, url, host, port, path):
    callback = exchange(url)
    assert mocks[1:4] == ([], [], [])
    assert callback(b'{}', **OPTIONS) == b'{}'
    assert mocks[2][0][0] == host and mocks[2][0][1]['port'] == port
    assert mocks[4].calls[0][1] == path


@pytest.mark.parametrize('pin', [None, True, '', '0' * 64, worker.PROFILE_SHA256.upper()])
def test_profile_refuses_before_acquisition(mocks, pin):
    with pytest.raises(AuditRejected, match='PROFILE_PIN'):
        exchange(pin=pin)
    assert mocks[1:4] == ([], [], [])


@pytest.mark.parametrize('key,value', [('request_bytes', b''), ('request_bytes', b'x' * (LIMIT + 1)),
    ('request_bytes', bytearray(b'{}')), ('request_bytes', '{}'), ('protocol_version', 1),
    ('protocol_version', '0.3'), ('max_response_bytes', True), ('max_response_bytes', 131072.0),
    ('max_response_bytes', 131071), ('timeout_s', True), ('timeout_s', 45.0), ('timeout_s', 46)],
    ids=['empty-request', 'oversize-request', 'bytearray-request', 'text-request',
         'integer-version', 'unsupported-version', 'boolean-response-cap', 'float-response-cap',
         'wrong-response-cap', 'boolean-timeout', 'float-timeout', 'wrong-timeout'])
def test_callback_arguments_refuse_before_context_or_acquisition(mocks, key, value):
    callback = exchange()
    args = dict(request_bytes=b'{}', **OPTIONS)
    args[key] = value
    with pytest.raises(AuditRejected):
        callback(**args)
    assert mocks[1:4] == ([], [], [])


@pytest.mark.parametrize('key,value', [('HTTP_PROXY', 'http://proxy.example'), ('https_proxy', 'x'),
    ('aLl_PrOxY', ' '), ('SSLKEYLOGFILE', 'private.log'), ('SSLKEYLOGFILE', ''),
    ('SSL_CERT_FILE', 'ca.pem'), ('ssl_cert_dir', 'ca-directory'), ('SSL_CERT_DIR', '')])
@pytest.mark.parametrize('when', ['construction', 'invocation'])
def test_environment_refuses_without_no_proxy_bypass(mocks, monkeypatch, key, value, when):
    callback = exchange() if when == 'invocation' else None
    monkeypatch.setenv(key, value)
    monkeypatch.setenv('NO_PROXY', '*')
    with pytest.raises(AuditRejected, match='HTTPS_.*_ENVIRONMENT'):
        callback(b'{}', **OPTIONS) if callback is not None else exchange()
    assert mocks[1:4] == ([], [], [])


def test_empty_proxy_and_credential_discovery_variables_are_not_used(mocks, monkeypatch):
    monkeypatch.setenv('HTTPS_PROXY', '')
    monkeypatch.setenv('NETRC', '/does/not/exist')
    monkeypatch.setenv('AWS_ACCESS_KEY_ID', 'SYNTHETIC_UNRELATED_VALUE')
    assert exchange()(b'{}', **OPTIONS) == b'{}'
    assert 'SYNTHETIC_UNRELATED_VALUE' not in repr(mocks[4].calls)


def test_real_fresh_tls_context_uses_system_trust_without_keylog():
    first, second = transport._context(), transport._context()
    assert first is not second
    assert first.protocol == ssl.PROTOCOL_TLS_CLIENT
    assert first.check_hostname is True and first.verify_mode == ssl.CERT_REQUIRED
    assert first.minimum_version == ssl.TLSVersion.TLSv1_2
    assert first.keylog_filename is None
    # A system capath may lazily load anchors only during a handshake.
    assert type(first.cert_store_stats()['x509_ca']) is int


def test_tls_context_calls_exact_trust_and_alpn(monkeypatch):
    events = []
    class Context:
        def __init__(self, protocol):
            events.append(('create', protocol))
        def load_default_certs(self, purpose):
            events.append(('trust', purpose))
        def set_alpn_protocols(self, values):
            events.append(('alpn', values))
    monkeypatch.setattr(transport.ssl, 'SSLContext', Context)
    context = transport._context()
    assert events == [('create', ssl.PROTOCOL_TLS_CLIENT), ('trust', ssl.Purpose.SERVER_AUTH),
                      ('alpn', ['http/1.1'])]
    assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
    assert context.minimum_version == ssl.TLSVersion.TLSv1_2


@pytest.mark.parametrize('size', [1, LIMIT])
def test_exact_request_one_post_fixed_headers_and_closure(mocks, size):
    request = b'x' * size
    assert exchange()(request, **OPTIONS) == b'{}'
    _, contexts, made, instances, connection, response = mocks
    assert len(contexts) == len(made) == len(instances) == connection.connected == 1
    assert made == [('worker.example', dict(port=443, timeout=5, context=contexts[0]))]
    assert connection.calls == [('POST', '/a2a', request, {
        'Content-Type': 'application/json', 'Accept': 'application/json', 'A2A-Version': '1.0',
        'Content-Length': str(size), 'Accept-Encoding': 'identity', 'Connection': 'close'})]
    assert connection.debuglevel == 0 and connection.auto_open == 0
    assert response.closed == connection.closed == 1
    assert all(0 < timeout <= 45 for timeout in connection.sock.timeouts)


@pytest.mark.parametrize('framing', ['length', 'eof'])
@pytest.mark.parametrize('size', [0, 1, 8192, LIMIT, LIMIT + 1])
@pytest.mark.parametrize('fragment', [1, 8192])
def test_entity_exact_and_overflow_with_fragmentation(mocks, framing, size, fragment):
    response = mocks[5]
    headers = [('Content-Type', 'application/json')]
    if framing == 'length':
        headers.append(('Content-Length', str(size)))
    response.__init__(b'x' * size, headers, fragment=fragment)
    if size > LIMIT:
        with pytest.raises(transport.HTTPSExchangeError, match='ENTITY_TOO_LARGE'):
            exchange()(b'{}', **OPTIONS)
        assert response.delivered == (0 if framing == 'length' else LIMIT + 1)
    else:
        assert exchange()(b'{}', **OPTIONS) == b'x' * size
        assert response.delivered == size
    assert response.closed == mocks[4].closed == 1
    assert all(1 <= amount <= 8192 for amount in response.reads)


@pytest.mark.parametrize('headers,code', [
    ([], 'HTTP_CONTENT_TYPE'),
    ([('Content-Type', 'text/event-stream')], 'HTTP_CONTENT_TYPE'),
    ([('Content-Type', 'text/plain')], 'HTTP_CONTENT_TYPE'),
    ([('Content-Type', 'application/problem+json')], 'HTTP_CONTENT_TYPE'),
    ([('Content-Type', 'application/json; charset=latin1')], 'HTTP_CONTENT_TYPE'),
    ([('Content-Type', 'application/json; charset=utf-8; x=y')], 'HTTP_CONTENT_TYPE'),
    ([('Content-Type', 'application/json'), ('Content-Type', 'application/json')], 'HTTP_CONTENT_TYPE'),
    ([('Content-Encoding', 'gzip')], 'HTTP_CONTENT_ENCODING'),
    ([('Content-Encoding', 'identity'), ('Content-Encoding', 'identity')], 'HTTP_CONTENT_ENCODING'),
    ([('Content-Length', '-1')], 'HTTP_FRAMING'),
    ([('Content-Length', '+1')], 'HTTP_FRAMING'),
    ([('Content-Length', '01')], 'HTTP_FRAMING'),
    ([('Content-Length', '1, 1')], 'HTTP_FRAMING'),
    ([('Content-Length', '1 ')], 'HTTP_FRAMING'),
    ([('Content-Length', '1'), ('Content-Length', '1')], 'HTTP_FRAMING'),
    ([('Content-Length', '131073')], 'ENTITY_TOO_LARGE'),
    ([('Content-Length', '9' * 5000)], 'ENTITY_TOO_LARGE'),
    ([('Transfer-Encoding', 'chunked')], 'HTTP_FRAMING'),
    ([('Transfer-Encoding', '')], 'HTTP_FRAMING'),
    ([('Transfer-Encoding', 'identity')], 'HTTP_FRAMING'),
    ([('Transfer-Encoding', 'gzip, chunked')], 'HTTP_FRAMING'),
    ([('Transfer-Encoding', 'chunked'), ('Content-Length', '2')], 'HTTP_FRAMING'),
    ([('Transfer-Encoding', 'chunked'), ('Transfer-Encoding', 'chunked')], 'HTTP_FRAMING'),
])
def test_response_header_refusal_never_reads_body(mocks, headers, code):
    if headers and headers[0][0] != 'Content-Type':
        headers = [('Content-Type', 'application/json'), *headers]
    mocks[5].__init__(b'SYNTHETIC_PRIVATE_BODY', headers)
    with pytest.raises(transport.HTTPSExchangeError, match=code) as caught:
        exchange()(b'{}', **OPTIONS)
    assert mocks[5].reads == [] and mocks[5].closed == mocks[4].closed == 1
    assert caught.value.__context__ is caught.value.__cause__ is None


@pytest.mark.parametrize('mime', ['application/json', 'Application/JSON', 'application/json; charset=utf-8',
                                 'application/json;charset="UTF-8"'])
def test_allowed_mime_forms(mocks, mime):
    mocks[5].__init__(b'{}', [('Content-Type', mime)])
    assert exchange()(b'{}', **OPTIONS) == b'{}'


@pytest.mark.parametrize('status', [101, 201, 204, 301, 302, 307, 308, 400, 401, 403, 429, 500])
def test_non200_never_reads_redirects_authenticates_or_resends(mocks, status):
    mocks[5].__init__(b'SYNTHETIC_PRIVATE_BODY', [
        ('Content-Type', 'application/json'), ('Location', 'https://elsewhere.example/secret'),
        ('WWW-Authenticate', 'Basic realm="private"'), ('Set-Cookie', 'private=value')], status=status)
    with pytest.raises(transport.HTTPSExchangeError, match='HTTP_STATUS'):
        exchange()(b'{}', **OPTIONS)
    assert mocks[5].reads == [] and len(mocks[4].calls) == len(mocks[3]) == 1
    assert mocks[5].closed == mocks[4].closed == 1


@pytest.mark.parametrize('stage', ['connect', 'request', 'headers', 'read', 'response_close', 'connection_close'])
@pytest.mark.parametrize('error', [OSError, TimeoutError, ssl.SSLError, http.client.IncompleteRead])
def test_io_failures_never_retry_and_scrub_original_error(mocks, capsys, stage, error):
    _, _, _, made, connection, response = mocks
    def fail():
        raise error(b'SYNTHETIC_PRIVATE_DIAGNOSTIC')
    if stage == 'response_close':
        response.on_close = fail
    elif stage == 'connection_close':
        connection.on_close = fail
    else:
        setattr(response if stage == 'read' else connection, 'on_' + stage, fail)
    with pytest.raises(transport.HTTPSExchangeError) as caught:
        exchange()(b'{}', **OPTIONS)
    assert len(made) == connection.connected == connection.closed == 1
    assert len(connection.calls) == (0 if stage == 'connect' else 1)
    assert response.closed == (0 if stage in ('connect', 'request', 'headers') else 1)
    assert caught.value.__context__ is caught.value.__cause__ is None
    assert 'SYNTHETIC_PRIVATE' not in str(caught.value)
    assert capsys.readouterr() == ('', '')
    tb = caught.value.__traceback__
    frames = []
    while tb:
        frames.append(tb.tb_frame.f_code.co_name)
        tb = tb.tb_next
    assert '_perform' not in frames


@pytest.mark.parametrize('stage', ['context', 'connect', 'request', 'headers', 'read'])
def test_cooperative_deadline_expiry_and_closure(mocks, monkeypatch, stage):
    clock, _, _, made, connection, response = mocks
    def expire():
        clock.value += 45
    if stage == 'context':
        monkeypatch.setattr(transport, '_context', expire)
    else:
        setattr(response if stage == 'read' else connection, 'on_' + stage, expire)
    with pytest.raises(transport.HTTPSExchangeError, match='DEADLINE_EXPIRED'):
        exchange()(b'{}', **OPTIONS)
    assert len(made) == (0 if stage == 'context' else 1)
    assert len(connection.calls) == (0 if stage in ('context', 'connect') else 1)
    assert connection.closed == (0 if stage == 'context' else 1)
    assert response.closed == (1 if stage in ('headers', 'read') else 0)


def test_connect_and_later_socket_allowances_shrink_to_remaining(mocks, monkeypatch):
    clock, _, constructor, _, connection, response = mocks
    def prepare():
        clock.value += 42
        return object()
    monkeypatch.setattr(transport, '_context', prepare)
    connection.on_connect = lambda: setattr(clock, 'value', clock.value + 1)
    connection.on_request = lambda: setattr(clock, 'value', clock.value + 0.5)
    response.on_read = lambda: setattr(clock, 'value', clock.value + 0.1)
    response.fragment = 1
    assert exchange()(b'{}', **OPTIONS) == b'{}'
    assert constructor[0][1]['timeout'] == 3
    assert connection.sock.timeouts[:3] == [2, 1.5, 1.5]
    assert 0 < connection.sock.timeouts[-1] < 1.5


class WireBytes(io.BytesIO):
    def __init__(self, raw, fragment=None):
        super().__init__(raw)
        self.fragment = fragment
        self.on_close = lambda: None
        self.body_offset = raw.index(b'\r\n\r\n') + 4
        self.body_acquired = 0
        self.body_calls = []
        self.close_count = 0
    def read1(self, amount=-1):
        assert 0 <= amount <= 8192
        self.body_calls.append(amount)
        result = super().read1(amount if self.fragment is None else min(amount, self.fragment))
        self.body_acquired += len(result)
        return result
    def close(self):
        self.close_count += 1
        if not self.closed:
            super().close()
            self.on_close()


def parsed_connection(monkeypatch, raw, *, fragment=None):
    stream = WireBytes(raw, fragment=fragment)
    class WireSocket(FakeSocket):
        def __init__(self):
            super().__init__()
            self.sent = []
            self.closed = 0
            self.file_refs = 0
            self.physical_closed = False
            self.bad_fd_calls = 0
            self.events = []
        def settimeout(self, timeout):
            if self.physical_closed:
                self.bad_fd_calls += 1
                raise OSError(9, 'Bad file descriptor')
            super().settimeout(timeout)
        def sendall(self, data):
            self.sent.append(bytes(data))
        def makefile(self, mode):
            assert mode == 'rb'
            self.file_refs += 1
            self.events.append('makefile')
            stream.on_close = self.release_file
            return stream
        def release_file(self):
            self.file_refs -= 1
            self.events.append('release_file')
            if self.closed and not self.file_refs:
                self.physical_closed = True
                self.events.append('physical_close')
        def close(self):
            self.closed += 1
            self.events.append('logical_close')
            if not self.file_refs:
                self.physical_closed = True
                self.events.append('physical_close')
    wire_socket = WireSocket()
    instances = []
    class Connection(http.client.HTTPConnection):
        default_port = 443
        def __init__(self, host, *, port, timeout, context):
            super().__init__(host, port=port, timeout=timeout)
            self.posts = self.connects = 0
            instances.append(self)
        def connect(self):
            self.connects += 1
            self.sock = wire_socket
        def request(self, *args, **kwargs):
            self.posts += 1
            return super().request(*args, **kwargs)
    monkeypatch.setattr(transport.http.client, 'HTTPSConnection', Connection)
    return stream, wire_socket, instances


def http_bytes(body, headers=(), *, status=b'200 OK'):
    return (b'HTTP/1.1 ' + status + b'\r\nContent-Type: application/json\r\n'
            + b''.join(name + b': ' + value + b'\r\n' for name, value in headers)
            + b'Connection: close\r\n\r\n' + body)


@pytest.mark.parametrize('framing', ['length', 'eof'])
@pytest.mark.parametrize('size', [0, 8192, LIMIT, LIMIT + 1])
def test_actual_stdlib_length_and_eof_acquisition(monkeypatch, framing, size):
    body = b'x' * size
    headers = [(b'Content-Length', str(size).encode())] if framing == 'length' else []
    stream, sock, made = parsed_connection(monkeypatch, http_bytes(body, headers))
    if size > LIMIT:
        with pytest.raises(transport.HTTPSExchangeError, match='ENTITY_TOO_LARGE'):
            exchange()(b'{}', **OPTIONS)
        assert stream.body_acquired == (0 if framing == 'length' else LIMIT + 1)
    else:
        assert exchange()(b'{}', **OPTIONS) == body
        assert stream.body_acquired == size
    assert len(made) == made[0].posts == made[0].connects == 1
    assert stream.closed and sock.closed >= 1
    assert all(0 <= count <= 8192 for count in stream.body_calls)
    assert b''.join(sock.sent) == (b'POST /a2a HTTP/1.1\r\nHost: worker.example\r\n'
        b'Content-Type: application/json\r\nAccept: application/json\r\nA2A-Version: 1.0\r\n'
        b'Content-Length: 2\r\nAccept-Encoding: identity\r\nConnection: close\r\n\r\n{}')


@pytest.mark.parametrize('body', [b'2\r\n{}\r\n0\r\n\r\n', b'1\r\n{\r\n1\r\n}\r\n0\r\n\r\n',
    b'0\r\n\r\n', b'garbage\r\nprivate', b'-1\r\n' + b'x' * (LIMIT + 1),
    b'20001\r\n' + b'x' * (LIMIT + 1)], ids=['valid', 'fragmented', 'zero', 'malformed', 'negative', 'oversized'])
def test_actual_stdlib_every_chunked_response_refuses_before_body(monkeypatch, body):
    stream, sock, made = parsed_connection(monkeypatch, http_bytes(body, [(b'Transfer-Encoding', b'chunked')]))
    with pytest.raises(transport.HTTPSExchangeError, match='HTTP_FRAMING'):
        exchange()(b'{}', **OPTIONS)
    assert stream.body_acquired == 0 and stream.body_calls == []
    assert stream.closed and sock.closed >= 1 and made[0].posts == made[0].connects == 1


@pytest.mark.parametrize('headers', [[(b'Content-Length', b'2'), (b'Content-Length', b'2')],
    [(b'Transfer-Encoding', b'chunked'), (b'Content-Length', b'2')],
    [(b'Transfer-Encoding', b'chunked'), (b'Transfer-Encoding', b'chunked')],
    [(b'Content-Length', b'-1')], [(b'Content-Length', b' 2 ')], [(b'Content-Length', b'2, 2')]])
def test_actual_stdlib_ambiguous_or_malformed_framing_refuses(monkeypatch, headers):
    stream, _, _ = parsed_connection(monkeypatch, http_bytes(b'{}', headers))
    with pytest.raises(transport.HTTPSExchangeError, match='HTTP_FRAMING'):
        exchange()(b'{}', **OPTIONS)
    assert stream.body_acquired == 0 and stream.closed


def test_actual_stdlib_truncated_length_discards_partial_body(monkeypatch):
    stream, _, _ = parsed_connection(monkeypatch, http_bytes(b'private', [(b'Content-Length', b'20')]))
    with pytest.raises(transport.HTTPSExchangeError, match='HTTP_TRUNCATED') as caught:
        exchange()(b'{}', **OPTIONS)
    assert stream.body_acquired == 7 and stream.closed
    assert caught.value.__context__ is None and 'private' not in str(caught.value)


def test_actual_stdlib_false_short_length_only_captures_entity(monkeypatch):
    stream, sock, made = parsed_connection(monkeypatch, http_bytes(b'{}UNREAD_PRIVATE_WIRE', [(b'Content-Length', b'2')]))
    assert exchange()(b'{}', **OPTIONS) == b'{}'
    assert stream.body_acquired == 2 and stream.closed and sock.closed >= 1
    assert made[0].posts == made[0].connects == 1


def integration(tmp_path, callback):
    store = ArtifactStore(tmp_path / 'cas')
    store.put_bytes(FIXTURE['source_text'].encode())
    store.put_bytes(FIXTURE['test_description'].encode())
    ref = store.put_json(FIXTURE['input'])
    runtime = ToolRuntime()
    runtime.register(worker.WORKER_SPEC, worker.make_worker_handler(callback, worker_profile_sha256=worker.PROFILE_SHA256))
    kwargs = dict(runtime=runtime, store=store, input_ref=ref, expected_input_sha256=ref.sha256,
                  expected_profile_sha256=FIXTURE['profile_sha256'],
                  expected_registration_sha256=FIXTURE['registration_sha256'],
                  granted_permissions=frozenset({'external-worker:invoke'}), approval_token='synthetic-local-approval')
    return store, kwargs


def assert_unaccepted(report):
    assert report['acceptance'] == 'UNACCEPTED' and report['code_execution'] == 'NOT_PERFORMED'
    assert report['live_model_validation'] == report['independent_review'] == 'NOT_EVALUATED'
    assert report['scientific_accepted'] is report['device_control_authorized'] is False
    assert report['remote_spend'] == report['remote_model_requests'] == report['remote_termination'] == 'NOT_ESTABLISHED'


def test_frozen_fixture_through_real_parser_handler_runtime_cas_and_receipt(tmp_path, monkeypatch):
    body = encode(FIXTURE['response'])
    stream, sock, made = parsed_connection(monkeypatch, http_bytes(body, [(b'Content-Length', str(len(body)).encode())]))
    store, kwargs = integration(tmp_path, exchange())
    observed = []
    execute = ToolRuntime.execute
    def observe(self, *args, **options):
        assert options['attempt_limit'] == 1
        value = execute(self, *args, **options)
        observed.append(value)
        return value
    monkeypatch.setattr(ToolRuntime, 'execute', observe)
    result, receipt, report = worker.run_worker_turn(**kwargs)
    assert receipt is observed[0][1] and type(receipt) is ToolCallReceipt
    assert report['status'] == 'CANDIDATE' and receipt.semantic_valid is True
    assert receipt.attempts == report['callback_invocations'] == made[0].posts == made[0].connects == 1
    request = b''.join(sock.sent).split(b'\r\n\r\n', 1)[1]
    assert request == encode(FIXTURE['request'])
    assert digest(request) == report['wire_request_sha256'] == FIXTURE['request_sha256']
    assert store.get_bytes(report['raw_response']['artifact_id'], max_bytes=LIMIT) == body
    assert report['raw_response']['sha256'] == FIXTURE['response_sha256']
    candidate = store.get_bytes(report['candidate']['artifact_id'], max_bytes=32768)
    assert candidate == FIXTURE['candidate_text'].encode()
    assert report['candidate']['sha256'] == digest(candidate)
    assert json.loads(store.get_bytes(result, max_bytes=196608)) == report
    assert stream.closed and stream.body_acquired == len(body)
    assert_unaccepted(report)


@pytest.mark.parametrize('kind', ['http_error', 'overflow', 'partial_io', 'timeout', 'chunked'])
def test_transport_refusals_are_unknown_without_raw_or_candidate(tmp_path, mocks, monkeypatch, kind):
    clock, _, _, _, connection, response = mocks
    if kind == 'http_error':
        response.status = 401
    elif kind == 'overflow':
        response.__init__(b'x' * (LIMIT + 1), [('Content-Type', 'application/json')])
    elif kind == 'chunked':
        response.__init__(b'-1\r\nprivate', [('Content-Type', 'application/json'), ('Transfer-Encoding', 'chunked')])
    elif kind == 'partial_io':
        response.__init__(b'SYNTHETIC_PRIVATE', fragment=1)
        def partial():
            if len(response.reads) == 2:
                raise OSError('SYNTHETIC_PRIVATE_ERROR')
        response.on_read = partial
    else:
        response.on_read = lambda: setattr(clock, 'value', clock.value + 45)
    store, kwargs = integration(tmp_path, exchange())
    observed = []
    execute = ToolRuntime.execute
    def observe(self, *args, **options):
        value = execute(self, *args, **options)
        observed.append(value)
        return value
    monkeypatch.setattr(ToolRuntime, 'execute', observe)
    result, receipt, report = worker.run_worker_turn(**kwargs)
    assert receipt is observed[0][1] and receipt.error_type == 'HTTPSExchangeError'
    assert receipt.status == 'FAILED' and receipt.attempts == len(connection.calls) == 1
    assert report['status'] == 'UNKNOWN' and report['code'] == 'RUNTIME_OUTCOME_UNKNOWN'
    assert report['raw_response'] is report['candidate'] is report['callback_invocations'] is None
    assert 'SYNTHETIC_PRIVATE' not in encode(report).decode()
    assert json.loads(store.get_bytes(result, max_bytes=196608)) == report
    assert_unaccepted(report)


@pytest.mark.parametrize('body', [b'', b'SYNTHETIC_PRIVATE_MALFORMED_JSON'])
def test_successful_http_raw_retention_risk_is_explicit(tmp_path, mocks, body):
    mocks[5].__init__(body)
    store, kwargs = integration(tmp_path, exchange())
    _, receipt, report = worker.run_worker_turn(**kwargs)
    assert receipt.semantic_valid is True and report['status'] == 'UNKNOWN'
    assert store.get_bytes(report['raw_response']['artifact_id'], max_bytes=LIMIT) == body
    assert report['candidate'] is None
    assert_unaccepted(report)


def test_owner_pins_and_explicit_import_boundary_are_preserved():
    owners = {
        'src/opendot_engineering/adapters/a2a_worker_turn.py': 'ed6c2399da397850c608cd1bbec985553bd8364c3a2162cfa6f81754f9c4a4d9',
        'tests/fixtures/a2a_worker_turn_v1.json': '186974f72da383b35d0bb47de2163e3611b5612348140accfc9da5f70d4745e3',
        'src/opendot_engineering/tool_runtime.py': '7c5011e02b2cf07e5f15ad7854905ce0738271e167b873bad9256a8ed169199c',
        'src/opendot_engineering/core/artifacts.py': '4606b7b11a81044267b30fee332d9b6fd6540d862726a9579655ee27c7d9a883',
        'src/opendot_engineering/core/contracts.py': '9462415baf84668825ad2c8cfc3f4f3df68332f65d1f1f4b301fbf01cf8537ca',
        'src/opendot_engineering/adapters/source_audit.py': 'c94737305b1e5a80453541ce890bde4fcb700a0074e32344fe839b237374bfa7',
    }
    for name, expected in owners.items():
        assert digest((ROOT / name).read_bytes()) == expected
    for init in (ROOT / 'src').rglob('__init__.py'):
        assert 'a2a_http_transport' not in init.read_text()
    from opendot_engineering.adapters import source_audit
    assert transport._require is source_audit._require
    tree = ast.parse(Path(transport.__file__).read_text())
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    assert sum(isinstance(node.func, ast.Attribute) and node.func.attr == 'request' for node in calls) == 1
    assert not any(isinstance(node.func, ast.Attribute) and node.func.attr in
                   {'execute', 'read', 'load_cert_chain', 'load_verify_locations', 'set_tunnel'} for node in calls)
    assert not any(isinstance(node.func, ast.Name) and node.func.id in
                   {'exec', 'eval', 'compile', 'ArtifactStore', 'ToolRuntime'} for node in calls)


@pytest.mark.parametrize('values', [[], [b'1.0'], [b'0.3'], [b'2.0'], [b'1.0, 0.3'],
                                    [b'1.0', b'0.3'], [b'1.0', b'1.0'], [b'1.0 ']])
def test_actual_stdlib_optional_version_echo_defensive_profile(monkeypatch, values):
    headers = [(b'Content-Length', b'2')] + [(b'A2A-Version', value) for value in values]
    stream, _, made = parsed_connection(monkeypatch, http_bytes(b'{}', headers))
    if values in ([], [b'1.0']):
        assert exchange()(b'{}', **OPTIONS) == b'{}'
        assert stream.body_acquired == 2
    else:
        with pytest.raises(transport.HTTPSExchangeError, match='HTTP_VERSION'):
            exchange()(b'{}', **OPTIONS)
        assert stream.body_acquired == 0 and stream.body_calls == []
    assert stream.closed and made[0].posts == made[0].connects == 1


@pytest.mark.parametrize('kind', ['context', 'constructor'])
def test_preconnect_failures_are_safe_without_request(mocks, monkeypatch, kind):
    def fail(*args, **kwargs):
        raise OSError('SYNTHETIC_PRIVATE_CONFIGURATION')
    if kind == 'context':
        monkeypatch.setattr(transport, '_context', fail)
    else:
        monkeypatch.setattr(transport.http.client, 'HTTPSConnection', fail)
    with pytest.raises(transport.HTTPSExchangeError, match='IO_FAILURE') as caught:
        exchange()(b'{}', **OPTIONS)
    assert mocks[3] == [] and mocks[4].calls == []
    assert caught.value.__cause__ is caught.value.__context__ is None


@pytest.mark.parametrize('result', [bytearray(b'{}'), None, b'x' * 8193],
                         ids=['bytearray-result', 'none-result', 'oversize-chunk'])
def test_unexpected_body_reader_results_refuse_before_accumulation(mocks, result):
    mocks[5].read1 = lambda amount: result
    with pytest.raises(transport.HTTPSExchangeError, match='BODY_READ_SIZE'):
        exchange()(b'{}', **OPTIONS)
    assert mocks[5].closed == mocks[4].closed == 1


def test_malformed_header_defect_refuses_before_body(mocks):
    from email.errors import MissingHeaderBodySeparatorDefect
    mocks[5].headers.defects.append(MissingHeaderBodySeparatorDefect())
    with pytest.raises(transport.HTTPSExchangeError, match='HTTP_HEADERS'):
        exchange()(b'{}', **OPTIONS)
    assert mocks[5].reads == [] and mocks[5].closed == mocks[4].closed == 1


@pytest.mark.parametrize('size', [0, 2, LIMIT])
@pytest.mark.parametrize('fragment', [None, 73])
def test_fixed_length_completion_never_touches_physically_closed_socket(monkeypatch, size, fragment):
    body = b'x' * size
    stream, sock, made = parsed_connection(monkeypatch, http_bytes(
        body, [(b'Content-Length', str(size).encode())]), fragment=fragment)
    assert exchange()(b'{}', **OPTIONS) == body
    assert stream.body_acquired == size and stream.closed
    assert sock.file_refs == 0 and sock.physical_closed is True
    assert sock.events.index('logical_close') < sock.events.index('release_file')
    assert sock.events.index('release_file') < sock.events.index('physical_close')
    assert sock.bad_fd_calls == 0
    assert len(stream.body_calls) == (0 if size == 0 else
        (size + (fragment or 8192) - 1) // (fragment or 8192))
    assert len(made) == made[0].posts == made[0].connects == 1


def test_late_final_fixed_length_read_still_refuses_after_socket_closes(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(transport, '_monotonic', clock)
    stream, sock, made = parsed_connection(monkeypatch, http_bytes(
        b'{}', [(b'Content-Length', b'2')]))
    # makefile installs ownership release later; inject after the parser has
    # read headers through a real HTTPConnection subclass wrapper.
    factory = transport.http.client.HTTPSConnection
    class LateReadConnection(factory):
        def getresponse(self):
            response = super().getresponse()
            release = stream.on_close
            def close_and_expire():
                release()
                clock.value += 45
            stream.on_close = close_and_expire
            return response
    monkeypatch.setattr(transport.http.client, 'HTTPSConnection', LateReadConnection)
    with pytest.raises(transport.HTTPSExchangeError, match='DEADLINE_EXPIRED'):
        exchange()(b'{}', **OPTIONS)
    assert stream.body_acquired == 2 and stream.closed
    assert sock.physical_closed and sock.bad_fd_calls == 0
    assert made[0].posts == made[0].connects == 1
