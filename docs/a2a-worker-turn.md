# One bounded A2A worker turn: offline preparation

This optional adapter prepares one `code_candidate.v1` turn under
[ADR 007](decisions/007-bounded-external-worker-turn.md). Its first case is a
public synthetic parser task with a preauthored response and a requested budget
of USD 0.00. Every replacement remains **UNACCEPTED**. No live worker, model,
provider or transport implementation is included or qualified.

The source owner is
[`opendot_engineering.adapters.a2a_worker_turn`](../src/opendot_engineering/adapters/a2a_worker_turn.py).
It is imported explicitly; default imports, dependencies, initializers and the
canonical ToolRuntime, ArtifactStore, ArtifactRef and source-audit owners remain
unchanged. It adds no scheduler, registry, runtime, acceptance service or budget
ledger. This guide describes the prepared API, not authorization to contact an
external agent or a runnable live integration.

## API and trusted registration

The documented entry points and registration constants are `TOOL_ID`, `PROFILE_SHA256`,
`REGISTRATION_SHA256`, `WORKER_SPEC`, `transport_envelope_valid(output)`,
`make_worker_handler(exchange, *, worker_profile_sha256)` and the keyword-only
`run_worker_turn` function:

```python
run_worker_turn(
    *, runtime: ToolRuntime, store: ArtifactStore, input_ref: ArtifactRef,
    expected_input_sha256: str, expected_profile_sha256: str,
    expected_registration_sha256: str,
    granted_permissions: frozenset[str] = frozenset(),
    approval_token: str | None = None,
) -> tuple[ArtifactRef | None, ToolCallReceipt, dict]
```

Trusted bootstrap constructs the handler with the exact profile pin and
registers it once using the existing `runtime.register(WORKER_SPEC, handler)`.
The adapter does not register itself or choose an endpoint. The fixed ToolSpec is:

| Field | Value |
| --- | --- |
| `tool_id` | `external_worker.code_candidate.v1` |
| `version` | `"1"` |
| `input_schema` | `opendot.a2a-worker-turn.dispatch.v1` |
| `output_schema` | `opendot.a2a-worker-turn.envelope.v1` |
| `risk` | `ToolRisk.IRREVERSIBLE_WRITE` |
| `timeout_s` | `60.0` |
| `max_retries` | `0` |
| `idempotent` | `False` |
| `permissions` | `frozenset({"external-worker:invoke"})` |
| `semantic_validator` | `transport_envelope_valid` |

`run_worker_turn` compares the supplied registration pin with both the adapter's
fixed pin and `runtime.registration_signature(TOOL_ID)`. That signature hashes
the detached ToolSpec declaration and callable binding kind. It does **not**
authenticate the handler code, callback closure, semantic-validator code,
remote worker or destination. Trusted bootstrap is a precondition, not a
security property established by the hash. The callback is trusted Python code,
not sandboxed code; its own closure and external effects are outside these
declaration checks.

The caller supplies the existing runtime permission grant and approval token.
The token is an existing caller assertion, not a newly introduced approval
authority. Missing permission or approval, or runtime circuit refusal, returns
a BLOCKED receipt without invoking the callback. The original deny-only guard
is unchanged and its exceptions propagate. `attempt_limit=1` is passed to the
single `runtime.execute(...)` call; it is not a ToolSpec field.

## Pinned inputs and byte boundaries

`runtime`, `store` and `input_ref` must have the exact canonical types, not
subclasses. The caller provides independent expected input, profile and
registration SHA-256 pins. A pin copied from untrusted returned data is not an
independent check.

The input ArtifactRef must have the expected digest, matching
`sha256:<digest>` artifact ID and `artifact://sha256/<digest>` URI,
`application/json` MIME type and an exact positive integer byte length at most
131,072. Its bytes are acquired through
`store.get_bytes(input_ref, max_bytes=131072)` and must equal that length and the
canonical input encoding: UTF-8 JSON, sorted keys, compact separators, literal
Unicode and no nonfinite values. Extra fields and duplicate JSON keys are
rejected using the existing source-audit helpers.

The exact input fields are `schema`, `profile_sha256`, `task_id`, `task`,
`task_sha256` and `snapshot`. The schema is
`opendot.a2a-worker-turn.input.v1`. `task_sha256` binds the nonempty UTF-8 task.
The snapshot has exactly `id`, `sha256` and `files`; its digest binds the
canonical ordered file-record array. Each record has exactly `path`, `sha256`,
`size_bytes` and `artifact_id`, with artifact ID `sha256:<source digest>`.

There are exactly two records, in order: `parser.py`, then `test_parser.txt`.
Each object is read through the canonical store with `max_bytes=32768`, checked
against its recorded length/digest, decoded as UTF-8 and included inline in the
request. Paths are fixed relative names, not filesystem write destinations;
absolute paths, traversal, alternate paths and URI inputs are not supported.
Identifiers use the existing bounded source-audit identifier rule. A source
file may be empty; the task may not.

| Boundary | Actual byte limit |
| --- | ---: |
| Each of two input files | 32,768 |
| Nonempty task UTF-8 | 4,096 |
| One replacement `parser.py` UTF-8 | 32,768 |
| Explanation UTF-8, including a JSON-RPC error message | 2,048 |
| Input document and encoded request, each | 131,072 |
| Observed response bytes | 131,072 |
| Encoded result report | 196,608 |

Source, task and candidate digests bind bytes, including whitespace. Empty
replacement text is allowed as data. The fixed profile declares `access=public`
and `role=synthetic`; changed profile labels fail the pin. Honest operator input
selection is still required: neither labels nor hashes prove that content is
public, licensed, safe or authorized for disclosure.

## One operator-owned callback

`make_worker_handler` requires a callable and the exact profile pin. The handler
constructs and checks the request before its one possible callback invocation:

```text
exchange(request_bytes, *, protocol_version="1.0",
         max_response_bytes=131072, timeout_s=45) -> bytes
```

This is a callback contract only. HTTP, SDK use, authentication, destination
selection, version negotiation, redirects and transport retry behavior remain
operator-owned and **unimplemented** here. The prepared tests supply finite
preauthored responses rather than network requests. The adapter requests or
subscribes to no streams. Its constructed wire payload contains no approval
token or credentials; the existing runtime approval assertion stays local.

On return, the handler requires exact `bytes` and checks actual length before
base64 allocation or any response JSON decoding. It returns an envelope with
exactly `request_sha256`, `status`, `callback_invocations`, `response_b64` and
`response_sha256`. The status is `RETURNED_BYTES`, `RESPONSE_TOO_LARGE` or
`RESPONSE_NOT_BYTES`; the last two have null response fields. A valid bounded
response is carried losslessly as base64 with its digest. The handler has no
CAS handle and does not parse candidate content or store outputs.

This byte check occurs **after** the callback returns. The callback may already
have acquired an oversized body. Neither its requested acquisition limit nor
this check establishes pre-acquisition or peak-memory bounds. The 45-second
callback allowance is a request; the 60-second local runtime timeout does not
prove remote cancellation or process termination.

## Strict A2A 1.0 subset

The frozen wire is based on A2A release 1.0.0, JSON-RPC binding, as recorded in
ADR 007 and the [fixture](../tests/fixtures/a2a_worker_turn_v1.json). It is one
`SendMessage` call with matching JSON-RPC request/response IDs. The request uses
exactly `jsonrpc`, `id`, `method`, `params`; params contain `message` and
`configuration`. The message has `messageId`, `role=ROLE_USER` and one part
with `data` and `mediaType=application/json`. Its data contains the fixed
profile, input digest, input document and two inline source texts.
Configuration fixes `acceptedOutputModes=["application/json"]`,
`historyLength=0` and `returnImmediately=false`. Protocol version `1.0` is
passed to the transport callback. No taskId/contextId is sent for the new message.

A candidate-bearing response has exactly `jsonrpc`, matching `id` and `result`.
The result has exactly `task`; task has `id`, `status`, `artifacts`; status has
only `state=TASK_STATE_COMPLETED`. There is one artifact with `artifactId` and
`parts`, and one part with `data` and `mediaType=application/json`. Server
`Task.id` is a separate correlation identifier, not the application task ID.

Candidate data has exactly these fields:

- `profile_sha256`, `input_sha256`, `task_id`, `task_sha256`
- `snapshot_id`, `snapshot_sha256`, `worker_id`, `acceptance_profile`
- `path`, `original_sha256`, `text`, `sha256`, `explanation`

The echoed pins must match the prepared input/profile, worker label
`operator.public-synthetic.v1`, acceptance-profile label
`external-code-review.v1`, path `parser.py` and original parser digest.
The replacement digest must match its UTF-8 text. These bindings do not judge
the text's behavior. Instructions, malicious source and claimed PASS inside
text remain inert data; there is no application, import, compilation or execution.

Noncompleted tasks have exactly `id` and `status`, with no artifacts. Recognized
states are FAILED, CANCELED, REJECTED, INPUT_REQUIRED, AUTH_REQUIRED, SUBMITTED,
WORKING and UNSPECIFIED, each with the `TASK_STATE_` prefix. A JSON-RPC error
instead has exactly `jsonrpc`, matching `id` and `error`; error has only an exact
integer `code` and bounded string `message`. Result/error combinations, extra
fields, inline URI/file parts, multiple artifacts/parts and mismatched pins
are rejected. Unsupported optional fields can be valid A2A elsewhere; they are
outside this strict profile. There is no streaming, history polling, second
message, negotiation or broad A2A conformance claim.

## Receipt, report and storage are separate evidence

The return value is `(result_ref, original_receipt, report)`. The original
ToolCallReceipt is returned unchanged. `receipt.semantic_valid` establishes
only local envelope validity; it can be true even for a bounded refusal
envelope such as RESPONSE_TOO_LARGE, and does not establish remote completion
or code correctness. Runtime input/output hashes cover runtime payload/envelope
representations. They are separate from `wire_request_sha256`, the raw response
digest and candidate digest.

Only the caller-returned path publishes artifacts, in this order:

1. Store exact bounded observed response bytes as `application/octet-stream`,
   with the input artifact as source, **before** protocol decoding/validation
2. If bindings validate, store the literal replacement as
   `text/plain; charset=utf-8`, sourced from the input and raw response
3. Store the bounded JSON result report, sourced from the input and all known
   raw/candidate references

All use producer `opendot.a2a-worker-turn.v1` and the application task ID. The
raw response retains malformed or rejected bounded bytes, including any worker
error message. Oversized or unobserved returns have no full-capture guarantee.
Treat all retained raw response bytes as private, untrusted evidence: unexpected
sensitive or reasoning-like text may be present even in a rejected response.
There is no semantic sanitizer or guaranteed exclusion of such content from
raw rejection evidence. Those exact bytes remain unchanged and are not made
safe to publish by their digest, declared public input profile or rejection.
The report itself exposes only safe bounded codes, hashes, reference records
and bounded local metadata, not raw response/error text, credentials or thought
streams. Each reference record contains artifact ID, digest, byte length and
MIME type. Evidence retention and any separately authorized sharing remain the
operator's responsibility.

The report schema is `opendot.a2a-worker-turn.result.v1`. Its status mapping is:

| Report `status` | `code` and meaning |
| --- | --- |
| `BLOCKED` | `RUNTIME_BLOCKED`; zero callback invocations |
| `CANDIDATE` | `BOUND_CANDIDATE`; a bound replacement was stored, still UNACCEPTED |
| `UNKNOWN` | `RUNTIME_OUTCOME_UNKNOWN` for other/failed runtime outcomes |
| `UNKNOWN` | `RESPONSE_TOO_LARGE`, `RESPONSE_NOT_BYTES` or a bounded validation rejection code |
| `UNKNOWN` | `WORKER_REPORTED_ERROR` or `WORKER_REPORTED_<state>`; a narrow worker claim, not verified execution/termination |
| `UNKNOWN` | `PUBLICATION_FAILED` or `RESULT_PUBLICATION_FAILED`; storage was incomplete |

`callback_invocations` is zero for BLOCKED, one after a valid returned envelope
and request binding, otherwise null/unknown. It counts the prepared callback
boundary, not remote tools, inference calls or transport internals. All reports
retain `acceptance=UNACCEPTED`, `code_execution=NOT_PERFORMED`,
`live_model_validation=NOT_EVALUATED`, `independent_review=NOT_EVALUATED`,
`scientific_accepted=false`, `device_control_authorized=false`, and
`remote_spend`, `remote_model_requests`, `remote_termination` each set to
`NOT_ESTABLISHED`.

Pre-dispatch validation errors raise `AuditRejected`; input acquisition errors
can also propagate before any dispatch. Runtime/control exceptions are not
wrapped. Where no receipt is returned, the adapter does not invent one.
Publication failures return UNKNOWN with known references in the in-memory
report. If final report publication fails, `result_ref` is `None`; even a known
candidate reference does not make that outcome accepted. Canonical CAS writes
are not transactional, so partial/unreferenced objects may also remain. There
is no rollback, cleanup, automatic retry or durable recovery claim. The CAS
root and ancestors are trusted and caller-controlled; inherited symlink
behavior and best-effort permissions do not provide a sandbox.

## First fixture and remaining live gate

The fixture freezes a task to repair key/value row parsing: ignore blank/comment
rows, split the first equals sign, trim surrounding whitespace, reject empty or
duplicate keys and return one parser replacement. `test_parser.txt` is a
synthetic specification, not an executed test. The preauthored replacement is
delivered as bytes; delivery is not evidence of model coding ability or semantic
acceptance. Stable pins for that first fixture are:

| Pin | SHA-256 |
| --- | --- |
| Profile | `1af48e2d14636a762dc2cc056de3b54b82bcccac26f21966891a7610228d52bb` |
| Registration | `3160d0f0ec1b49efe5f58de13ca07c012a46b31b3025f170a0f757ab2ba5e043` |
| Input document | `e4024be08b7ded8cd61852c9cb40cc09d09abf8348b7122d301acb056e7819a3` |
| Encoded request | `1015740365051b0abe9c9dcf55db7e27336f91074c902f8a4026d5a135ed202d` |
| Preauthored response | `82391f800dcf089600e75076eac1f4d951475cf800a883dadf59d7c9d876f67e` |
| Replacement | `9bacbdbd530f83fe488399d28b3a6d0bab33950f57aadac5796536b40481e0e0` |

The profile requests no tools, zero tool calls, one model request, at most
8,192 input/4,096 output tokens, a 45-second remote deadline and USD 0.00.
These requests are not enforced remote budgets, a cost ceiling or a spend
receipt. Missing usage and cost remain unknown. Local invocation count does
not prove remote inference count. Worker labels, echoed pins and server IDs
are claims/correlation, not authenticated identity.

Only finite offline fixture/controlled-Future qualification is admitted by this
preparation. Such checks can examine refusal, exact/+1 byte limits, corrupted
wire data, partial storage, guard propagation and late-result handling without
launching a service or executing returned code. The adapter's late handler
completion has no CAS publication route; this does not confine arbitrary effects
inside an operator-supplied callback. Future-level observations do not establish process,
remote worker or model termination. Separate caller invocations are separate
attempts: no global deduplication or at-most-once external effects are promised.
Ambiguity remains UNKNOWN, with no automatic retry, poll, cancel, refund,
resubmission, fallback or late candidate publication.

Live worker interoperability, transport acquisition/retry/redirect/TLS/auth
behavior, remote identity, budget enforcement, billing, termination, model
coding capability and code-acceptance integration are **NOT_RUN**. A future
live gate needs separate approval of the exact worker, environment, destination,
inputs, credentials, model and cost limits, plus transport review. An existing
external verifier interface needs its own review before acceptance integration.
Raw-retaining mode is qualified only for the public synthetic fixtures. A private
CAS does not make secret retention safe. Before live use, independently review
credential/error handling and response retention/redaction, including accidental
sensitive output; received bytes are never automatically published.
The prepared seam neither authorizes that gate nor supplies a runnable live
example.
