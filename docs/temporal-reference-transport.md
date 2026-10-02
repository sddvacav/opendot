# Optional synthetic Temporal reference transport

Status, 2 October 2026: optional source feature merged in [PR #18](https://github.com/sddvacav/opendot/pull/18), with an independently accepted bounded real-server qualification. The [exact hosted run and bilingual evidence summary](temporal-qualification-evidence.md) record 818 SDK/pure passes and seven real-server passes on the exact tree merged to `main`. This establishes only single-host loopback queued first delivery after a graceful quiescent restart and recorded-result replay for `synthetic.bounded_sum.v1`. No in-flight crash recovery, multi-host execution, global exactly-once, production deployment, scientific validity or full MVP is established; `NOT_SCORED` is unchanged.

This is current-source functionality, absent from the unchanged published v0.3.0a1 assets. The [version-pinned installed guide](installed-quickstart.md) still describes those released artifacts. The dated [ADR 004](decisions/004-temporal-reference-transport.md) and [failure matrix](temporal-reference-failure-matrix.md) retain their historical decisions, SDK-only checkpoint and unexecuted cases; the new qualification does not retroactively turn them into passes.

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

## Trust limits and qualified integration scope

Only synthetic, nonsensitive data in one trusted operator domain is admitted. Producer, Workflow author, registrar, worker, store owner and reader need an independently owned authorization boundary. Anyone able to schedule this endpoint can exercise its fixed worker authority. Queue names/digests are not authentication. Only one trusted local CAS and one writer process with one concurrent profile Activity are admitted; no multi-host availability or multi-process safety is provided. Root ancestors and bounded objects are trusted. The canonical full-object read and SDK's prior decoding mean size limits are not adversarial preallocation bounds.

At most one runtime invocation is admitted per current Activity invocation. A separate submission can execute again, even with the same digest and fixed Activity ID. No global uniqueness, exactly-once effects, durable callable recovery, eventual delivery, arbitrary read-only introspection, scientific acceptance or per-result independent acceptance is claimed. Temporal owns scheduling/history; OpenDot owns no new orchestrator, registry or store.

The accepted hosted configuration used Ubuntu 24.04 / Python 3.12.14, SDK 1.34.0, CLI 1.9.1 and server 1.32.0, with the same trusted local CAS and SQLite across three server generations. Five actual received Info records, eight history snapshots and 15 invocation-counter records bind the finite experiment. All three servers exited gracefully with code 0; all 12 worker generations completed awaited shutdown. The recorded-result replay used no Activity worker, retained the same result reference, and left its handler count at one. The [qualification evidence](temporal-qualification-evidence.md) separates these observations from the still-unproven cases.

Lost acknowledgment remains uncertain, never converted to a recovery success. Consumer Workflow and operator controls must exclude retries, resets and resubmission loops for the admitted use. Matching local CAS access, reviewed exact handler/validator binding, worker concurrency and grants remain deployment-specific requirements. Omitted-policy refusal is covered by the SDK/pure contract checks; the hosted run's five received Info records contain the required policy and exact timeouts. If a different server configuration omits or normalizes required metadata incompatibly, that configuration is NO-GO. This finite qualification does not accept other deployments or arbitrary handlers.

### Historical SDK-only checkpoint

Before the hosted qualification, only scheduling fakes and ActivityEnvironment checks had run, and the real-server gate was unresolved. The earlier statement, “No server, native executable, solver, cancellation/recovery protocol or remote write was used for this candidate,” describes that SDK-only checkpoint. The later accepted run adds the explicitly scoped hosted server evidence above; it does not relabel historical `NOT_RUN` cases or the two earlier failed hosted runs. No service or native execution was performed for this documentation update.

## Upstream attribution

The optional Temporal Python SDK is published by Temporal Technologies under the MIT license: [SDK 1.34.0 license](https://github.com/temporalio/sdk-python/blob/1.34.0/LICENSE). The SDK is an external pinned dependency; no SDK source is vendored into this candidate. Official wheel/source/license metadata and hashes are retained with the separate dependency qualification evidence. OpenDot's existing Apache license and NOTICE remain unchanged.
