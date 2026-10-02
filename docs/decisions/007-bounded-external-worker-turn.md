# ADR 007: one bounded external-worker code-candidate turn

2026-10-02 · Accepted for OFFLINE PREPARATION ONLY before executable edits

## Decision and authorized closure

Root approved exactly seven paths on main `5213a93f875ebabae7046043dc1a8eb63a572893`
(tree `05a5cf992a60343c34784cbf6d986c2e62ee9770`): `AGENTS.md`, this ADR,
`src/opendot_engineering/adapters/a2a_worker_turn.py`,
`tests/test_a2a_worker_turn.py`, `tests/fixtures/a2a_worker_turn_v1.json`,
`docs/a2a-worker-turn.md`, and `docs/architecture.md`. All existing owner bytes,
initializers/re-exports, dependencies, Temporal, Git, admission, executors, examples,
and default imports stay unchanged. This exception does not relax other ADRs.

Prepare an optional A2A 1.0 JSON-RPC SendMessage adapter for the exact
`code_candidate.v1` public synthetic profile. One caller-owned canonical
ToolRuntime execution invokes one operator-supplied callback at most once. A
literal fake response supplies a parser replacement, stored through the existing
canonical CAS. Every candidate remains UNACCEPTED. There is no HTTP client, SDK,
model loop, provider, registry, scheduler, budget ledger, acceptance owner,
credential access, URI fetching, code application/import/compilation/execution,
private input, external-agent contact, installation or remote publication.

The trusted bootstrap registers the fixed irreversible-write ToolSpec once, using
`max_retries=0`, `idempotent=False`, `timeout_s=60.0` and permission
`external-worker:invoke`. The caller supplies the runtime's existing approval
assertion and independent pins. `attempt_limit=1` is supplied to `execute()`, not
ToolSpec. Registration signatures bind local declarations under a trusted
bootstrap; they authenticate neither handler closures nor remote destinations.
The original deny-only guard and its exception propagation remain unchanged.

## Frozen wire and application profile

The exact newly authored profile, request, response, task/source bytes, hashes,
and test oracles are frozen in `tests/fixtures/a2a_worker_turn_v1.json` before
executable edits. Official references checked on 2026-10-02:
[versioned specification](https://a2a-protocol.org/v1.0.0/specification/) and
[tagged schema](https://github.com/a2aproject/A2A/blob/v1.0.0/specification/a2a.proto).
Only protocol field names/semantics are used; no implementation/schema is copied.

Request: `jsonrpc,id,method,params`; method `SendMessage`; params
`message,configuration`; message `messageId,role,parts`, role `ROLE_USER`;
configuration `acceptedOutputModes=["application/json"],historyLength=0,
returnImmediately=false`; one part with `data,mediaType`. Version `1.0` is a
transport parameter. No taskId/contextId is sent for the new message.
Response: matching JSON-RPC ID and exactly one result/error. Candidate-bearing
result is exactly `task`, with `id,status,artifacts`; status is exactly
`state=TASK_STATE_COMPLETED`; exactly one artifact `artifactId,parts`, with one
`data,mediaType` part. Server Task.id is not the application task ID. Unsupported
optional fields are rejected for this narrow profile; they are not generally
invalid A2A. Completed application data must echo input, task, snapshot, source,
profile, worker label and acceptance-profile pins and contain one source
replacement. Worker labels and server IDs are claims/correlation, not identity
proof or persistent duplicate suppression.

The first profile contains exactly `parser.py` and `test_parser.txt`, each <=32
KiB, task <=4 KiB, one replacement `parser.py` <=32 KiB, explanation <=2 KiB,
encoded request and observed response each <=128 KiB, stored report <=192 KiB.
Empty replacement is allowed as data. Fixed profile requests no tools, zero tool
calls, one model request, 8192 input/4096 output tokens, 45-second remote deadline
and synthetic USD 0.00. These are requests, not enforcement or spend evidence.
The declared public/synthetic labels require honest operator input selection;
content cannot be proven public by a hash or label.

## Evidence and failure boundary

Bounded canonical input reads precede dispatch. Existing strict JSON, digest and
relative-path helpers are reused. The handler has no CAS handle and never parses
returned candidate content. It checks actual byte length before any response JSON
parse, then returns a bounded lossless base64 envelope. This is a post-return
check; pre-acquisition/peak-memory bounds belong to the future transport.
Only the caller-returned path stores bounded observed raw bytes before protocol
validation, then a bound candidate and result report. Failed decode/validation
retains raw evidence. Oversized/unobserved bytes have no full-capture guarantee.
Retained raw bytes are private and untrusted: they may contain unexpected sensitive
or reasoning-like text. No semantic sanitizer or guaranteed exclusion of that
text from rejected raw evidence is claimed. No reasoning stream is requested or
subscribed; credentials and approval assertions are never wire fields.
CAS writes are not a transaction; on publication failure, known refs survive in
the in-memory outcome, and additional unreferenced partial artifacts may exist.

The original ToolCallReceipt is returned unchanged. Its semantic_valid field
means local transport-envelope validity only, not remote task success or code
correctness. Runtime payload/output hashes are distinct from wire/raw/candidate
hashes. Reports have only bounded codes, hashes and references, never raw error
text, credentials or thought streams. All report outcomes retain UNACCEPTED,
NOT_PERFORMED code execution, NOT_EVALUATED live model/independent review, false
scientific acceptance and false device authority.

After an ambiguous submission/return, including malformed data or publication
failure, outcome is UNKNOWN unless the exact finite response establishes a
narrower worker-reported state. No retry, poll, cancel, refund, resubmit, second
message, fallback, automatic late publication or global at-most-once claim.
Future-level termination observations do not prove process, remote worker or
model termination. Missing usage/cost remain unknown. External callers can
invoke twice; the adapter does not deduplicate them.

## Frozen acceptance and live gap

The fixture oracles require useful preauthored replacement delivery; no action
from malicious/wrong code; pre-dispatch pin/path/permission/size refusals; strict
A2A mismatch rejection; terminal/interrupted distinctions; pure controlled
Future timeout/late completion; exact-limit/+1 and partial-storage failures;
owner/guard/default-import preservation; repeated-call honesty; and separation
of byte integrity, local envelope validity and acceptance. Only finite selected
pytest checks with the existing venv are authorized, with collection reviewed
first. No hanging thread, server, subprocess lifetime or native lifecycle probe.

Live worker interoperability, remote enforcement/identity/billing/termination,
model coding capability and code acceptance integration are NOT_RUN. An existing
external verifier interface must be reviewed separately before acceptance can be
integrated. Live use needs a separately approved worker/environment/destination,
inputs, credentials, model and cost limits, plus verified transport acquisition,
retry/redirect/TLS/auth behavior. Raw-retaining mode is qualified only for public synthetic fixtures. A private CAS
does not make secret retention safe. Live use additionally requires independent
credential/error-handling and response-retention/redaction review; received bytes
are never automatically published. None of that is authorized or claimed here.


## Accepted narrow HTTPS-exchange preparation amendment (2026-10-02)

Root approved implementation and finite mock qualification of the six-path
proposal on published a4 main `2d16190a8121410bbeea252869b196f7891e1696`
(tree `c6c2b015fc1e016b1dea2fb09990e53dc2af4996`). This appended exception
supersedes only the historical no-HTTP-implementation limit for the optional
`adapters.a2a_http_transport` module. Historical evidence and limits above remain.
The six paths are `AGENTS.md`, this ADR,
`src/opendot_engineering/adapters/a2a_http_transport.py`,
`tests/test_a2a_http_transport.py`, `docs/a2a-http-transport.md` and
`docs/a2a-worker-turn.md`. Every other source byte stays unchanged, including
the worker adapter/profile/fixture, canonical runtime/storage/contracts/helpers,
deny-only guard, CI selections, dependencies and default imports.

The explicit factory accepts only a trusted operator HTTPS URL and the exact
existing profile pin. It performs no network I/O. Its callback accepts exact
bytes of length 1..131072, version `1.0`, integer cap `131072` and integer
allowance `45`; it neither serializes requests nor dispatches a runtime itself.
Only the unchanged caller/runtime owns dispatch and acceptance remains absent.
The operator URL is ASCII, at most 2048 bytes, canonical HTTPS, lowercase DNS,
optional canonical decimal port 1..65535 and explicit restricted origin path;
no userinfo/query/fragment/escapes/IP literal/trailing dot/dot segment. Endpoint
authorization, cooperative environment and trustworthy system roots remain
preconditions; this is not an SSRF boundary, DNS pin or worker identity proof.

Refuse effective HTTP/HTTPS/ALL proxy variables regardless of NO_PROXY, key-log
and OpenSSL CA-override variables; never bypass mandated routing/access controls.
Use fresh verified TLS client context, system roots, hostname/CERT_REQUIRED,
TLS >=1.2, HTTP/1.1 ALPN, no client certificate and debug level zero. One explicit
connection, at most one POST, fixed JSON/version/length/identity/close headers,
no automatic reconnection, auth, redirect, retry, polling or URI fetch. Close
response and connection on all acquired paths without draining a refused body.

Only HTTP 200 with exactly one application/json MIME value (optional UTF-8
charset), no nonidentity content encoding, and strict unambiguous length/EOF or
exact chunked framing is eligible. Reject oversized declared length before
body reads. Sized read1 calls of at most min(8192, remaining + 1) acquire at most
131073 entity bytes; overflow never reaches the JSON parser/adapter. Check
truncation and delivered length. A falsely short declared length defines the
stdlib parser boundary; unread wire bytes are discarded with the connection.
No bound is claimed for total wire bytes, headers/interim responses/chunk framing,
TLS/socket buffering, RSS or peak memory. The actual interpreter/OpenSSL identity
must accompany qualification; use the stdlib parser, not a replacement parser.

Start a 45-second cooperative monotonic deadline before connection. Connect/TLS
uses at most five seconds per socket allowance; later stages use at most the
remaining allowance, with checks around connect/POST/headers/every body read.
DNS, multiple addresses, internal header/chunk loops and slow progress can exceed
elapsed-time expectations. The existing 60-second runtime timeout does not stop
the call or remote worker. No hard termination, inference/spend or at-most-once
remote execution guarantee is established.

HTTP/refusal/partial/timeout/I/O failures cross the callback boundary only as
fixed local exception codes without original exception context or retained
partial body evidence. This is not secure memory erasure or a guarantee about
external instrumentation. The unchanged adapter returns UNKNOWN with original
receipt and no invented response; complete eligible HTTP bodies still reach its
raw-retaining CAS before JSON validation and can contain sensitive data. No
second evidence store, schema or sanitizer is added.

Frozen oracles before implementation: strict endpoint/profile/argument refusal
before acquisition; byte-exact POST/headers; at most one send under failures;
verified TLS/environment refusals; limit and +1 for length/EOF/chunked and
fragmented/truncated/malformed bodies; gzip/SSE/MIME/status refusal before body;
fake-clock expiry at each blocking stage; closure and exception scrubbing; real
current-stdlib HTTPResponse over finite BytesIO; frozen fixture integration via
unchanged handler/runtime/CAS with request/raw/candidate hashes and original
receipt identity; unchanged 99 A2A cases and exact canonical owner pins.
Collection is reviewed before execution; counts come from actual collection.
The existing canonical executor used by finite mocked tests is allowed; no new
server/network/lifetime threads, sockets, DNS, sleeps, installs or native probes.

Mock qualification is not live interoperability. No live destination exists.
Live TLS/network/worker/model coding and remote identity/enforcement/billing/
termination remain NOT_RUN. A later gate requires separate approval of the exact
candidate, environment, named no-auth destination/worker, public synthetic input
pins, remote model/budget ownership and independent private raw-retention review.
Code application/acceptance and publication are not authorized here.


### Root-approved framing narrowing before tests (2026-10-02)

Independent inspection of the installed CPython 3.12.14 parser found that a
negative chunk size can become `fp.read1(-1)` despite a sized outer read1 call.
Root therefore narrowed this increment before qualification: reject **every**
Transfer-Encoding header, including valid `chunked`, before any body read. Only
validated Content-Length or connection-EOF framing is supported. The earlier
chunked proposal and amendment text remain historical, superseded here. No
backing-reader wrapper, mutable parser-internal guard, replacement HTTP parser
or global production patch is admitted. Some valid A2A HTTP responses will be
refused; general interoperability remains unqualified. Frozen added oracles:
valid, fragmented, zero, malformed, negative and oversized chunk frames all
refuse from headers with zero entity/framing body acquisition, as do duplicate
or conflicting Transfer-Encoding/Content-Length headers. The current stdlib
parser still owns header and length/EOF parsing; no stricter whole-wire grammar
claim is made.


### Root-approved response version check before final qualification (2026-10-02)

The [A2A 1.0 versioning rules](https://a2a-protocol.org/v1.0.0/specification/#36-versioning)
require the client's requested version and server processing/error behavior,
not an echoed response version header. An absent response A2A-Version is
eligible. Root approved a defensive narrower profile: if that response header
is present, require exactly one value equal to `1.0`; reject other, combined
or duplicate values before entity acquisition. This is our defensive profile,
not a universal A2A response-echo requirement. The request header remains `1.0`;
there is no version negotiation or fallback. Frozen additional oracles cover
absent and exact valid echo, `0.3`, `2.0`, comma lists, identical/conflicting
duplicates and whitespace-modified values, through finite actual-parser fixtures.


### Root-approved v2 fixed-length socket lifecycle repair (2026-10-02)

After the v1 packet was frozen, root identified and independent finite tests
confirmed a missed stdlib lifecycle edge. For Content-Length plus Connection:
close, getresponse detaches/closes the connection socket while the response file
retains a socket I/O reference. A final read1 satisfying the declared length
closes that file and releases the last reference. A subsequent settimeout on the
saved socket can therefore fail even though the complete entity was received.
The earlier fake sockets did not model physical closure after final-reference
release, so their passing results did not establish this behavior. The v1
source/evidence is preserved separately and is superseded by this repair.

Root authorized the minimal repair within the same six paths: stop the read loop
when the accumulated bytes reach validated Content-Length, after the final
read's deadline, exact-byte-type and overflow checks. Retain the final declared
length check and EOF-framed behavior. A zero-length entity needs no body read.
Frozen added finite oracles use real HTTPConnection/HTTPResponse with BytesIO
and a fake socket that tracks logical closure, file references and physical
closure and raises EBADF on post-closure settimeout. Cover lengths zero/two/limit,
fragmentation, false-short/truncated lengths and deadline expiry on the final
read. No live socket, DNS, parser replacement, lifecycle/native process probe
or publication is involved. Earlier evidence stays historical; all live gaps
and response-retention risks remain.
