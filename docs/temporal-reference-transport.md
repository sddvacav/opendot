# Optional synthetic Temporal reference transport

Status: isolated implementation candidate, SDK-only qualification. No deployed functionality, server delivery/replay, owner integration or merge acceptance is established. See [ADR 004](decisions/004-temporal-reference-transport.md) and the [failure matrix](temporal-reference-failure-matrix.md).

## What is implemented

The explicit optional extra is `temporal = ["temporalio==1.34.0"]`. Default dependencies remain empty and root/core/adapter initializers do not import either optional module. Installing this extra does not start or connect anything.

- `adapters.temporal_activity.ReferenceActivity`: bind an existing exact canonical `ToolRuntime` and `ArtifactStore`, fixed tool ID, literal reviewed declaration signature, worker-local grants, namespace and queue. Register its synchronous `run` with caller-owned Temporal worker setup
- `adapters.temporal_workflow.execute_reference`: await one fixed non-local Activity scheduling call from consumer-owned Workflow code. It has fixed Activity name `opendot.synthetic.reference.v1`, ID `opendot-synthetic-reference-v1`, retry maximum 1, start-to-close 10 seconds and schedule-to-close 60 seconds. No scheduling overrides, loops or direct runtime/CAS operations

Both transport entrypoints use `dict[str, Any]` because the pinned SDK default JSON converter rejects nested values under `dict[str, object]`. This owner-approved annotation correction leaves all exact runtime wire checks intact; no custom converter is used.

The Activity module exposes `SYNTHETIC_SPEC`, `bounded_sum`, `bounded_sum_valid`, `TOOL_ID` and `REGISTRATION_SHA256` for reviewed explicit bootstrap registration through the existing runtime. It does not create or populate a runtime itself. The fixed declaration hash is `5f2b1e81954530f31c7d2c83b9c582883b8391190ebe13b69b8bf91f044cb0c3`. It hashes declarations, not handler/validator code. A different handler with the same declaration has the same signature: bootstrap source review remains mandatory, and this interface cannot introspect arbitrary tool risk or prove purity.

The finite pure profile accepts exactly integer `left` and `right` in [-1,000,000, 1,000,000], excluding booleans, plus exact boolean `return_null`. The reviewed handler returns their sum or legitimate null. Permission is `synthetic:read`; an empty configured grant set preserves the runtime's permission-denied outcome. Grants are detached into a frozenset and the binding is frozen. Cooperative trusted Python is assumed; this is not a sandbox or per-request authorization.

## Admission and I/O

The real SDK `activity.info()` is the metadata source. Attempt must be exact integer 1, mode non-local, actual RetryPolicy present with exact integer maximum 1, and both received timeouts exactly the fixed profile values. Activity type, namespace, queue and nonempty bounded Workflow/run IDs must match the admitted mode. Missing/unknown/malformed metadata refuses. Submission options alone are not evidence about actual received server metadata.

All those checks, strict request/reference checks and the declaration-signature recheck happen before per-invocation CAS access. Canonical references are reconstructed as the original ArtifactRef type; a claimed integrity flag is reset before canonical verified-byte retrieval. Input size is checked after that read. The canonical source-audit JSON decoder rejects duplicate keys/nonfinite literals, and exact schema validation rejects floating values, overflowing exponents, nested data, unexpected keys and booleans-as-integers.

Only after input checks does the sole runtime call execute with local grants, approval_token=None, backoff_base_s=0.0 and attempt_limit=1. The original deny-only guard is untouched. Every bound non-None context, even a false-like value, and resolver failures still deny. Configured control exceptions propagate unchanged to the SDK boundary. An admitted input read may already have happened when that guard refuses; no result put occurs. The adapter never resets context, substitutes another runtime or calls private dispatch.

## Result and failure interpretation

A delivered Activity response contains only `schema_version` and the canonical `result_ref`. The local CAS document contains the output plus all thirteen original receipt fields. Observation fields are serialized as plain reports, explicitly labeled `serialized_runtime_report_not_live_proof`; no live observation object is reconstructed. Original statuses, semantic validity, error type and liveness uncertainty are preserved. Scientific validity and device authority are false; independent review and owner integration remain NOT_EVALUATED.

COMPLETED, FAILED and BLOCKED tool outcomes may all be delivered successfully by the Activity. BLOCKED has attempts=1 even with zero handler calls. Completed null is a legitimate output. CAS integrity, runtime semantic validity and Temporal delivery are separate. Raw CAS input digest need not equal the runtime input hash because the runtime hashes its own JSON representation.

Adapter failures use non-retryable SDK ApplicationError types with bounded phase/code details only:

- TemporalAdmissionRejected: no per-invocation CAS or runtime call
- TemporalInputRejected: canonical read/decode/schema failed, no runtime call
- TemporalResultEncodingFailed: runtime returned, but its report/output or response could not be represented; a response-phase error can follow successful storage
- TemporalResultStoreFailed: canonical result publication failed; output and even complete object bytes may exist

Runtime exceptions are not wrapped. SDK conversion, completion, deadlines and missing acknowledgments remain SDK/transport concerns. A failure does not establish that the handler did nothing. No failure causes another execute call, repeated put, fallback, cleanup, repair, grant change or result reconstruction. Object/metadata publication is not transactional.

## Trust limits and unresolved integration gate

Only synthetic, nonsensitive data in one trusted operator domain is admitted. Producer, Workflow author, registrar, worker, store owner and reader need an independently owned authorization boundary. Anyone able to schedule this endpoint can exercise its fixed worker authority. Queue names/digests are not authentication. Only one trusted local CAS and one writer process with one concurrent profile Activity are admitted; no multi-host availability or multi-process safety is provided. Root ancestors and bounded objects are trusted. The canonical full-object read and SDK's prior decoding mean size limits are not adversarial preallocation bounds.

At most one runtime invocation is admitted per current Activity invocation. A separate submission can execute again, even with the same digest and fixed Activity ID. No global uniqueness, exactly-once effects, durable callable recovery, eventual delivery, arbitrary read-only introspection, scientific acceptance or independent acceptance is claimed. Temporal owns scheduling/history; OpenDot owns no new orchestrator, registry or store.

Before functionality or merge acceptance, an independently authorized specified server deployment must demonstrate actual received Info policy/timeouts, omitted-policy refusal, genuinely queued first delivery and completed-result history replay. Lost acknowledgment must remain uncertain, never converted to a recovery success. Consumer Workflow and operator controls must exclude retries, resets and resubmission loops for the admitted use. Matching local CAS access, reviewed exact handler/validator binding, worker concurrency and grants must be established. If a server omits or normalizes required metadata incompatibly, that deployment is NO-GO.

No server, native executable, solver, cancellation/recovery protocol or remote write was used for this candidate. SDK-only scheduling fakes and ActivityEnvironment tests do not close the server gate.

## Upstream attribution

The optional Temporal Python SDK is published by Temporal Technologies under the MIT license: [SDK 1.34.0 license](https://github.com/temporalio/sdk-python/blob/1.34.0/LICENSE). The SDK is an external pinned dependency; no SDK source is vendored into this candidate. Official wheel/source/license metadata and hashes are retained with the separate dependency qualification evidence. OpenDot's existing Apache license and NOTICE remain unchanged.
