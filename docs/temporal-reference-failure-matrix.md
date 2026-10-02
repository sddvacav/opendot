Implementation target accepted 2026-10-02 for SDK-only candidate qualification; the historical matrix below is not a deployment test report. See the accepted ADR 004 scope.

# Temporal reference transport failure matrix

Date: 2026-10-01 UTC
Status: **Proposal only. No implementation or deployment acceptance.**
Contract: [ADR 004](decisions/004-temporal-reference-transport.md)

## How to read the matrix

Counts concern the current Activity invocation, not a previous or separately submitted invocation. `execute` means the existing public runtime method was entered; a count of one does not prove the handler ran. `BLOCKED` receipts retain attempts=1 even when handler calls are zero. Output means a value produced by the handler; a result document additionally includes the runtime report and can exist for a failed or blocked tool.

All paths prohibit adapter-driven redispatch and resubmission. Runtime attempt_limit=1 prevents its own retry loop in this invocation; actual Activity metadata must report attempt=1 and maximum_attempts=1 before CAS access. Separate submissions remain outside that guarantee. No report here implies rollback, strict handler termination or absence of effects after loss of observation.

## Refusals before any per-invocation CAS access

| Case | Execute calls | Handler calls | Could output or a result object from this invocation exist | Required outcome and why no redispatch |
| --- | --- | --- | --- | --- |
| Missing/incompatible SDK or required public API | 0 | 0 | No | Refuse bootstrap/binding. No weaker metadata path; qualification must precede use |
| Direct call outside Activity context, or Info retrieval fails | 0 | 0 | No | Refuse. Request-supplied metadata cannot replace SDK context |
| Missing retry policy or missing maximum_attempts | 0 | 0 | No | Refuse unknown policy. Absence is not evidence of no retries |
| Default/unlimited policy maximum 0; maximum 2 or another value; wrong type including true, 1.0 or integer subclass | 0 | 0 | No | Refuse unless an exact integer 1. No submission-time assertion substitutes for received metadata |
| Attempt 2 or later; attempt 0; boolean/non-exact integer | 0 | 0 | No new output; a prior invocation may have output/effects | Refuse. Do not read CAS looking for a completion marker or reinterpret as recovery |
| Local Activity, malformed local flag, or standalone Activity without Workflow identifiers | 0 | 0 | No | Refuse unsupported mode; no conversion to a different Activity mode |
| Missing, nonpositive, invalid or unequal received timeout | 0 | 0 | No | Refuse instead of silently accepting server-normalized/default deadlines |
| Wrong Activity type, namespace or task queue | 0 | 0 | No | Refuse worker-configuration mismatch. Matching values would still not authenticate a caller |
| Malformed/oversized decoded request, unknown version, extra authority fields | 0 | 0 | No | Refuse shape/bounds before I/O. Does not undo SDK deserialization already performed |
| Wrong reference fields, noncanonical digest/URI/ID, path/URL, boolean size, unexpected sources or labels | 0 | 0 | No | Refuse without attempting an alternate path or store |
| Locally bound tool ID or registration signature wrong/absent | 0 | 0 | No | Refuse declared-profile mismatch. Never inspect private registry, load a handler or select another runtime |
| A received integrity_verified=true with otherwise valid fields | 0 before reading | 0 before reading | Not yet | Not a success condition. Ignore/reset the claim and perform the normal canonical read/hash/size checks |

The last row is a normal continuation, included to make clear that an integrity flag confers no authority. A retained flag cannot bypass any gate.

## Input retrieval and runtime outcomes

| Case | Execute calls | Handler calls | Could output or a result object from this invocation exist | Required outcome and why no redispatch |
| --- | --- | --- | --- | --- |
| Missing input object or local I/O error | 0 | 0 | No | Transport input failure; no alternate store, fetch, retry or resubmission |
| Corrupt input bytes or digest mismatch | 0 | 0 | No | Canonical integrity failure; do not repair objects or execute on unchecked bytes |
| Claimed length mismatch or actual object over 256 bytes | 0 | 0 | No | Refuse after canonical full-object read. The read itself is not adversarially memory-bounded |
| Invalid UTF-8/JSON, duplicate keys, nonfinite/overflowing numeric input, incorrect schema or value limits | 0 | 0 | No | Refuse before execute using canonical JSON helper plus finite profile validation |
| Bound control context or resolver error at execute entry | 1 | 0 | No result document; input has already been read | Propagate configured control error unchanged to SDK boundary. No fallback or result put; runtime guard is not a pre-CAS-read guard |
| Guard refuses in copied dispatch context | 1 | 0 | No handler output/result document | Same control refusal; no suppression, clearing or re-entry |
| Runtime permission denied or unexpected approval requirement | 1 | 0 | A BLOCKED result document may be written/delivered | Preserve original receipt and attempts=1. Never add a grant/token or retry to obtain success |
| Runtime breaker blocks admission | 1 | 0 | A BLOCKED result document may be written/delivered | Preserve CircuitOpen report. No reset, wait-and-retry or replacement runtime |
| Finite handler completes with valid integer output | 1 | 1 | Output exists; result object exists if publication succeeds | Preserve COMPLETED/semantic_valid. No duplicate call even if later publication fails |
| Finite handler completes with legitimate null output | 1 | 1 | Null is the output; result object may be written | Use receipt status/semantic_valid, not output-nullness, to interpret completion |
| Handler throws an ordinary observed exception | 1 | 1 | Partial computation/effects cannot be inferred away; FAILED report may be written | Preserve error and FAILED/semantic_valid=false. Attempt limit forbids even an ordinarily retry-eligible call |
| Handler returns but semantic validation fails | 1 | 1 | A raw handler value existed; runtime may withhold it and return None; FAILED report may be written | Preserve failed semantic outcome. Do not capture/reconstruct the withheld value or rerun validator/handler to obtain another answer |
| Preparation timeout before dispatch | 1 | 0 if runtime observation establishes not started | FAILED report may be written; no handler output established | Preserve original timeout/liveness report. Timeout does not authorize redispatch |
| Handler timeout, lost submission handle, interrupted result observation or cleanup failure | 1 | 0 or 1, possibly still active | Output/effects may exist later; FAILED report may be written if runtime returns one | Preserve liveness uncertainty; no thread-kill, rollback, reconciliation event or fresh execute |
| Runtime raises without a returned receipt after execution may have begun | 1 | Unknown within 0 or 1 | Output/effects may exist; no invented result report | Propagate failure. Missing receipt is not proof that dispatch did not happen |

The accepted handler is pure and synthetic, so external business effects are not expected under its reviewed behavior. The failure language deliberately does not promote that trust assumption into a transport-enforced guarantee. Unexpected effects or unknown binding invalidate the profile; they are not repaired by resubmission.

## Serialization storage and transport outcomes

| Case | Execute calls | Handler calls | Could output or a result object from this invocation exist | Required outcome and why no redispatch |
| --- | --- | --- | --- | --- |
| Returned output/receipt cannot be represented faithfully or exceeds result bounds | 1 | 0 or 1 according to runtime outcome | Handler output may exist; no new result put has started | Non-retryable result-encoding failure. No coercion to str, field dropping, fresh receipt, handler/validator rerun or execute retry |
| Canonical result JSON serialization fails | 1 | 0 or 1 | Handler output may exist; no successful result publication established | Distinct storage/serialization failure. Tool outcome is not changed to success or erased |
| CAS object write fails | 1 | 0 or 1 | Handler output may exist; object presence depends on failure point and is not assumed absent | Distinct result-store failure; no repeated put, execute, cleanup or receipt-lock protocol |
| Object write succeeds and metadata write/check fails | 1 | 0 or 1 | Complete object bytes may exist without usable metadata or a returned reference | Result-store failure with possible orphan bytes. Object/metadata operations are not a transaction; no recovery or rollback |
| Result object/reference produced, but response validation/SDK conversion fails | 1 | 0 or 1 | Stored result may exist; Temporal success is not established | Post-dispatch transport failure. Never execute or republish automatically |
| Completion acknowledgment lost or uncertain after return | 1 if execute had been reached; otherwise unknown to caller | Unknown to caller | Output and complete result may exist; history may or may not record completion | Report unknown transport outcome if evidence permits. SDK reporting behavior is external; no wrapper retry/resubmit |
| Worker crashes or disconnects while Activity is in flight | 0 or 1, unknown to caller | 0 or 1, unknown to caller | Partial work, complete output or stored result may exist | One-attempt policy does not stop already running work or guarantee delivery. Preserve uncertainty; no new invocation to discover what happened |
| Activity/Workflow cancellation or transport deadline | 0 or 1 depending on progress | 0 or 1; handler may remain active | Output/result may exist before or after observed deadline | Let existing SDK/runtime semantics stand; no cancellation backend, rollback or automatic recovery |
| Delivered reference cannot be resolved later, or bytes/length/schema fail consumer checks | No new call | No new call | Original result may have existed and been removed/corrupted | Consumer storage failure. Temporal history durability does not restore local CAS; never rerun to rebuild it |

A result-store error may arise from a read-only store, corruption, permissions, capacity or ordinary I/O. The adapter does not alter permissions, repair metadata, delete objects, switch roots or weaken canonical checks.

## Queued work replay and separate submissions

| Case | Execute calls caused by this event | Possible output/result | Required interpretation |
| --- | --- | --- | --- |
| Scheduled Activity is queued and has not started; a worker becomes available before its deadline | 0 until delivery; then at most 1 after all gates | No prior output from this invocation; a first result may then be produced | Initial queued delivery, not rerun/recovery of a previous handler |
| Schedule-to-close expires while work is genuinely queued and never started | 0 | None from this invocation | A transport deadline without dispatch; operator must not assume every generic timeout has this evidence |
| Workflow Task re-executes before the Activity scheduling command was durably recorded | At most the eventual first admitted Activity invocation; no callable in Workflow code | No output is established by Workflow code re-execution | Deterministic scheduling reconciliation is Temporal-owned, not an adapter duplicate lock |
| Ordinary Workflow replay with Activity completion/result already in history | 0 additional | Recorded reference reused; CAS availability must still be checked by a local reader | No handler rerun. Result history is distinct from live observation and local object retention |
| Workflow replay while the Activity has no recorded terminal result | No callable from replay itself; Activity progress remains separate | In-flight output/publication may be unknown | Do not infer that replay authorizes another Activity or proves absence of effects |
| SDK/server unexpectedly presents attempt 2 | 0 on the refused invocation | Earlier output may exist | Early metadata refusal blocks new CAS/runtime work; it does not erase earlier uncertainty |
| Operator resets, retries manually, starts a new Workflow, repeats the helper or separately submits the Activity | Each separately admitted invocation can call execute once | Another result/output can exist even for the same input digest | Outside cross-invocation guarantee. The wrappers do not suppress new commands using IDs, hashes, receipts or CAS objects |

## Required evidence for accepting these rows

Later tests must count both execute and actual handler calls and spy on every CAS operation. Early gates require zero I/O. Guard refusals explicitly allow the prior input read but prohibit result writes. Post-dispatch fault injection must establish no second execute/handler call; success reports must preserve the exact original outcome. Real ActivityEnvironment cases use SDK-created default Info plus dataclass replacement, never request-supplied authority. Deployment observations are separately required for actual server metadata, queued delivery and history replay; a mock cannot prove them.

This matrix is a proposed acceptance target, not a test report. No experiment, deployment failure injection or repository change was performed to produce it.
