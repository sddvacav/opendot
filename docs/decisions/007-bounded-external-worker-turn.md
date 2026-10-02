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
