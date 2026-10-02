# Optional bounded HTTPS exchange: mock-qualified preparation

This explicit-import module provides a real stdlib HTTPS callback for the
[existing worker-turn seam](a2a-worker-turn.md), under the appended
[ADR 007 exception](decisions/007-bounded-external-worker-turn.md). It has only
finite mocked qualification. No live destination is selected or authorized;
live TLS/network/worker/model interoperability remains **NOT_RUN**.

The **0.3.0a5 candidate** includes this optional module in its wheel, sdist
and full source, with explicit import and no new dependency. Packaging does not
establish publication or live qualification; use the matching [a5 installed guide](installed-quickstart.md)
and exact-artifact receipts. It is absent from the published a4 wheel, sdist and
full-source assets; those frozen release artifacts remain unchanged. Qualification
remains finite and mocked only; the separate live gate remains **NOT_RUN**.

## API and ownership

The explicit import example is executable Python:

```python
from opendot_engineering.adapters.a2a_http_transport import make_https_exchange
```

The constructor signature below is descriptive text, not an executable Python call:

```text
make_https_exchange(*, endpoint_url: str, worker_profile_sha256: str) -> Callable
```

Construction validates and captures one trusted operator endpoint plus the exact
existing profile pin. It performs no network I/O. Trusted bootstrap may supply
the returned callback to the unchanged `make_worker_handler`. Only that handler
serializes requests; only the existing caller/ToolRuntime dispatches them. The
transport never registers a tool, invokes a model, creates a store, parses JSON,
applies source, or accepts a candidate. Default imports and initializers remain
unchanged. No SDK or new dependency is required.

The callback has the existing keyword-only contract:

```text
exchange(request_bytes, *, protocol_version, max_response_bytes, timeout_s) -> bytes
```

It accepts exact `bytes` of length 1..131072, exact string `"1.0"`, exact integer
`131072` and exact integer `45`. Booleans, float lookalikes, subclasses and
alternate settings are rejected. There are no per-call URLs, custom headers,
credentials, TLS flags, contexts or public connection-factory overrides.
Configuration and argument refusals use existing `AuditRejected` with fixed
codes, before creating a context or connection. Each separately authorized
invocation is a new exchange; this is not global deduplication.

## Destination, environment and trust

The URL must be an exact ASCII string, at most 2048 bytes, with lowercase
`https://`, lowercase DNS hostname, optional canonical decimal port 1..65535,
and explicit `/` path. DNS labels are 1..63 ASCII letters/digits/hyphens with
alphanumeric ends, total hostname at most 253 characters, and alphabetic
final-label start. This excludes IP literals and legacy numeric/hex IP forms.
Ports have no leading zero. Paths admit ASCII unreserved characters and `/`;
`.` and `..` path segments are refused. Whitespace, controls, non-ASCII,
userinfo, query, fragment, backslashes, percent escapes, trailing-dot or
empty-label hostnames are rejected. This intentionally refuses some valid URLs.

The endpoint is never learned from input text, a response, Location, Agent Card
or returned URI. Selecting and authorizing that endpoint is a trusted-bootstrap
precondition; the profile pin authenticates neither destination nor worker.
DNS can resolve a permitted hostname to local/private addresses and can change
between calls. This is not an SSRF sandbox or IP-pinning mechanism.

At construction and again before invocation, refuse nonempty case-insensitive
HTTP_PROXY, HTTPS_PROXY and ALL_PROXY, regardless of NO_PROXY. Refuse the
presence of SSLKEYLOGFILE, SSL_CERT_FILE, SSL_CERT_DIR and the current OpenSSL
named CA-override environment keys, including empty values. No environment
value is logged. This does not authorize bypassing mandated routing or any
access denial; deployments requiring a proxy cannot use this callback.

Each call creates a fresh SSLContext(PROTOCOL_TLS_CLIENT), explicitly retains
hostname checking and CERT_REQUIRED, sets minimum TLS 1.2, loads default system
trusted CAs and offers only `http/1.1` via ALPN. No client certificate is loaded,
no unverified fallback exists, and create_default_context's environment key-log
behavior is avoided. System trust directories may load anchors lazily; mock
checks do not establish an actual TLS handshake. The environment, system trust
and interpreter remain trusted/cooperative; concurrent environment or global
instrumentation mutation is not defended against.

There is no proxy/netrc/keychain/cookie/credential discovery. Debug level is
explicitly zero. No URL, request, response or original exception text is logged
by this owner. These controls do not prove server bytes are secret-free or
prevent logging by external instrumentation.

## One logical POST and response entity bound

Create one HTTPSConnection, connect explicitly, disable implicit auto-open, and
issue at most one POST to the captured path with exact request bytes. The fixed
headers are Content-Type and Accept `application/json`, A2A-Version `1.0`, exact
Content-Length, Accept-Encoding `identity` and Connection `close`; stdlib emits
the Host header. No second request, redirect, retry, reconnection, auth
negotiation, downgrade, polling, cancel or URI fetch is attempted. DNS address
attempts and TCP retransmission are distinct from application resends.

Only HTTP 200 is eligible. An absent response A2A-Version is eligible; if
present, require exactly one value equal to `1.0`. Other versions, comma lists
and duplicates refuse before entity acquisition. This present-header strictness
is our defensive profile, not a universal A2A requirement to echo a version;
there is no negotiation or fallback. Require exactly one Content-Type of application/json,
case-insensitively, optionally with one UTF-8 charset (quoted or unquoted).
Unknown MIME parameters, duplicate MIME values and SSE are refused. Content
encoding may be absent or exactly one `identity`; gzip/compression is refused.
Reject parser-reported malformed headers, duplicate Content-Length, noncanonical
decimal lengths, and any **Transfer-Encoding**, including valid chunked.

The root-approved framing narrowing is deliberate: the installed CPython parser
can turn a negative chunk size into an unsized backing read1. This increment
avoids that path entirely and adds no parser replacement, wrapper or global
patch. Some otherwise valid A2A responses will be refused. Header and body
parsing otherwise remain the current stdlib's behavior; strict whole-wire HTTP
grammar or general A2A conformance is not claimed.

Supported framing is validated Content-Length or connection EOF. Declared length
over 131072 refuses before body reads. Read with sized
`read1(min(8192, remaining + 1))` calls, checking each chunk before accumulation.
At most 131073 entity bytes enter acquisition, with the last byte only an
overflow probe; at most 131072 are returned. Empty entities are allowed and
reach the unchanged adapter's malformed-JSON/raw-retention handling. A longer
claimed length with premature EOF fails; a falsely short length defines the
stdlib entity boundary and extra unread wire bytes are discarded when closing.
Once validated Content-Length is fully acquired, stop after the final read's
deadline/type/overflow checks, without another saved-socket timeout/read. The
stdlib may close its final socket-file reference inside that completing read;
this ownership sequence is covered by finite reference-counted fake sockets.
A zero-length entity requires no body read. Every acquired response/connection
is closed without body draining or reuse.

This is an entity acquisition cap, not a total-wire/header/framing/TLS-buffer,
RSS or peak-memory bound. Stdlib header parsing happens before status/MIME
refusal. Its version-dependent header/interim-response limits are not this
module's entity bound. The finite test suite uses actual current HTTPConnection
serialization and HTTPResponse parsing over BytesIO, plus fake responses; it
never opens a socket or resolves DNS.

## Cooperative time and fixed failures

A monotonic 45-second deadline starts before TLS context/connection creation.
Connect/TLS gets at most a five-second socket allowance, reduced when less time
remains. Subsequent blocking stages receive at most the remaining allowance;
checks occur around connect/POST/headers and every body read. Socket timeouts
and after-stage checks refuse expired work.

DNS resolution is not bounded by that timeout. Multiple resolved addresses,
internal header loops, TLS/socket behavior and slow progress may exceed elapsed
time expectations. This is not a hard wall-clock deadline. The unchanged outer
runtime uses 60 seconds; its Future timeout does not terminate this call or the
remote worker. Remote inference, spend, cancellation and termination are
**NOT_ESTABLISHED**.

Transport failures use `HTTPSExchangeError` carrying a fixed code:
HTTP_STATUS, HTTP_HEADERS, HTTP_VERSION, HTTP_CONTENT_TYPE, HTTP_CONTENT_ENCODING,
HTTP_FRAMING, ENTITY_TOO_LARGE, BODY_READ_SIZE, HTTP_TRUNCATED,
CONNECTION_STATE, DEADLINE_EXPIRED, IO_TIMEOUT, TLS_FAILURE, HTTP_FAILURE,
IO_FAILURE or CLOSE_FAILURE. Ordinary original exceptions and partial response
frames do not cross the callback boundary as cause/context; no partial/error
body is returned, stored or logged. Transient in-memory copies and external
instrumentation are outside this claim; this is not secure memory erasure.

The unchanged adapter returns the original receipt and UNKNOWN /
RUNTIME_OUTCOME_UNKNOWN for these transport failures, with no raw response or
candidate reference and unknown callback/submission outcome. It does not invent
a server response, refund budget or automatically retry. A failure cannot prove
whether submission reached the worker.

A complete eligible HTTP 200 body still reaches the original adapter, which
stores exact bounded raw bytes in canonical CAS **before** JSON validation.
Such bodies can contain unexpected sensitive or reasoning-like content, even
when JSON/candidate validation rejects them. No sanitizer or redaction guarantee
has been added. Raw evidence remains private and untrusted and is never
automatically published. Every candidate stays UNACCEPTED, code execution
NOT_PERFORMED, and live-model/independent review NOT_EVALUATED.

## Qualification and separate live gate

The separate v2 preparation repairs a lifecycle gap found after v1 qualification:
v1 made one extra saved-socket timeout call after a complete fixed-length body,
which could fail after stdlib closed the final file reference. The original
packet is preserved and superseded. v2 tests model logical socket closure,
remaining file references and physical closure, including fragmented exact
lengths, zero, truncation and deadline expiry on the final read.

The finite qualification covers strict URL/profile/arguments and environment
refusal before acquisition; exact request serialization; fresh TLS settings;
one logical send and closure through failures; length/EOF limits, fragmentation,
false lengths/truncation; all chunked responses refused before body acquisition;
MIME/status/compression refusal; fake-clock deadlines; fixed errors without
partial evidence; and frozen a4 request/response/candidate/receipt bindings
through the unchanged handler/runtime/CAS. All 99 original A2A nodes and exact
owner pins are preserved. The existing canonical executor is permitted for its
finite mocked tests; no new server/network/lifetime thread is used.

The preparation was qualified with Python 3.12.14 and OpenSSL 3.5.8 (25 Aug 2026),
using the already existing pytest 9.1.1 environment. These identify the tested
parser; they do not newly pin package-wide runtime dependencies. Collection and
execution evidence records actual counts; no test-count target or CI selection
was added. Reproduce only the selected finite files with existing tooling:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src \
  python -B -m pytest --collect-only -q -p no:cacheprovider \
  tests/test_a2a_http_transport.py tests/test_a2a_worker_turn.py
# Review the collected selection, then:
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src \
  python -B -m pytest -q -p no:cacheprovider \
  tests/test_a2a_http_transport.py tests/test_a2a_worker_turn.py
```

Live TLS/network, named-worker interoperability, model coding capability,
remote identity/enforcement/billing/termination and code acceptance integration
remain NOT_RUN. A live gate needs separate approval of the exact candidate,
environment, named operator-configured no-auth worker/destination, public
synthetic input pins, remote model/budget ownership, and independent private
raw-retention review. No such destination exists in this preparation. There is
no runnable live example, private input, installation, server/native process
probe, code application, acceptance or publication authorization here.
