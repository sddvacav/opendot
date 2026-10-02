# ADR 004: isolated optional Temporal reference transport candidate

Decision date: 2026-10-02 UTC
Status: ACCEPTED FOR ISOLATED IMPLEMENTATION AND SDK-ONLY QUALIFICATION ONLY. Deployment, merge and publication are NOT accepted.

## Narrow owner acceptance and change budget

The owner accepted the 2026-10-01 ADR proposal and failure matrix as the basis for this independent implementation candidate, with the matching AGENTS exception applied before implementation. The accepted scope is exactly the two optional Activity/Workflow interfaces, fixed synthetic.bounded_sum.v1 profile, Workflow-only non-local mode, single trusted operator/local CAS/single writer conditions, pre-guard input read boundary, metadata gates, schemas and failure distinctions described below. All stronger claims and other existing prohibitions remain in force.

Candidate baseline: commit 625b8038ed3fbfa95b68a0561ffdc412d4020dd9, exact tree 70da9e28a2ce61aaa66043a47e8d5fba598c67bc (public main d7042c26). This replaces only the historical source revision noted in the proposal; the three owner hashes below remain exact.

Permitted source-tree changes are AGENTS.md; the temporal optional extra in pyproject.toml; src/opendot_engineering/adapters/temporal_activity.py; src/opendot_engineering/adapters/temporal_workflow.py; tests/test_temporal_activity_contract.py; tests/test_temporal_workflow_contract.py; tests/test_temporal_transport_owner_boundaries.py; this ADR; docs/temporal-reference-transport.md; docs/temporal-reference-failure-matrix.md. No other existing files may change. Evidence and dependency artifacts live outside the candidate source tree.

The worker module also exposes the fixed pure handler, its finite validator, its declaration, and the independently computed literal declaration signature for trusted bootstrap registration through the existing ToolRuntime. These are fixed profile values/functions, not another registry or runtime bootstrap. The public construction and run interfaces remain as proposed. Signature equality attests declarations, never handler purity.

SDK-only ActivityEnvironment and fake-service/Workflow scheduling tests are permitted. Official PyPI dependencies may be installed into an isolated workspace virtualenv following metadata/version/license checks. Temporal servers, native binaries, solver processes, lifecycle/namespace/proc investigations, cancellation/recovery protocols, provider APIs, credentials, remote writes, and Codex CLI/cloud coding tasks remain excluded. Real server metadata, queue delivery and replay evidence are a separate gate before any functionality or merge claim.

## SDK qualification correction accepted 2026-10-02

The first combined Activity/Workflow run reported **175 passed and 2 failed**, not a clean pass. Both failures were genuine default SDK JSON-converter round trips: temporalio 1.34.0 cannot decode nested values under `dict[str, object]`. The owner explicitly approved only the two transport entrypoint annotations (`ReferenceActivity.run` and `execute_reference`, request and return) changing to `dict[str, Any]`. This is a converter-compatibility correction, not a wire-schema change. Exact runtime plain-type/field/size checks remain, no custom converter is introduced, and decoder-mediated malformed nested-value tests must prove the gates still refuse. Historical proposed annotations below are superseded by this paragraph only.

The remaining text records the accepted technical specification from the proposal. Its historical statements about authorizations and proposed status describe the 2026-10-01 review, superseded only by this narrow 2026-10-02 decision. No historical evidence is upgraded by that decision.

---

# ADR 004 proposal for optional Temporal reference transport

Date: 2026-10-01 UTC
Status: **PROPOSED ONLY. Implementation, installation, service execution and publication are not authorized.**
Audience: OpenDot callable, artifact and repository owners
Companion: [Failure matrix](../temporal-reference-failure-matrix.md)

## Decision requested

Approve or reject a precisely bounded exception allowing two optional adapters to connect the existing callable runtime to an externally owned Temporal deployment. The proposed first profile runs one reviewed, finite, pure synthetic callable in one trusted operator domain. Inputs and results stay in the same canonical local CAS. Temporal carries reference records and owns its scheduling/history; OpenDot gains no scheduler, registry, store, recovery or cancellation protocol.

**The current repository remains NO-GO for implementation.** Its AGENTS.md forbids connecting the callable owner to orchestration. This document does not amend that rule. The owner must explicitly accept this exception and a matching narrowly scoped AGENTS amendment before any implementation begins. Calling the connection a transport does not make it cease to be an orchestration connection. If the owner intends to prohibit every such connection, reject this ADR and leave integration to a separately owned consumer project.

The proposed guarantee is **at most one call to the existing runtime per admitted Activity invocation, with the runtime attempt limit fixed at one**. A path reaching dispatch calls it exactly once; refusals and interrupted pre-dispatch paths call it zero times. Neither statement means exactly-once business effects, durable callable execution, global duplicate suppression, eventual result delivery or one invocation across separate submissions.

## Baseline and preserved owners

Static inspection used source revision `6f44e17d8e723a34eb8a204f009ecbe6c28e3c19`. The working tree was clean. These implementation hashes match the prior owner-boundary review:

| Owner | SHA-256 |
| --- | --- |
| `src/opendot_engineering/tool_runtime.py` | `7c5011e02b2cf07e5f15ad7854905ce0738271e167b873bad9256a8ed169199c` |
| `src/opendot_engineering/core/artifacts.py` | `91fde8d32f6f7498fc96c0e883b9ba658440e95b0cc92f69f172e4de3d7b7856` |
| `src/opendot_engineering/core/contracts.py` | `9462415baf84668825ad2c8cfc3f4f3df68332f65d1f1f4b301fbf01cf8537ca` |

All three files remain byte-identical. The six callable contracts remain owned by `tool_runtime.py`; canonical `ArtifactStore` and `ArtifactRef` remain the same class objects. `Capability` and `AgentManifest` remain descriptive metadata. No new canonical contract, alias, permission engine, registry, receipt owner or consumer migration is proposed. Root/core/adapter initializers, source-audit helpers, native adapters, existing contracts and existing tests remain unchanged.

## First admitted profile

The concrete proposed profile is `synthetic.bounded_sum.v1`. It is intentionally unsuitable for arbitrary tool routing.

- Tool ID: `synthetic.bounded_sum`; declaration version: `1`
- Input schema name: `synthetic.bounded_sum.input/v1`; output schema name: `synthetic.bounded_sum.output/v1`
- Declaration: `ToolRisk.READ_ONLY`, `timeout_s=1.0`, `max_retries=0`, `idempotent=True`, permissions exactly `frozenset({"synthetic:read"})`
- Input: one plain dictionary with exactly `left`, `right`, `return_null`. The first two values are exact integers, excluding booleans, each between -1,000,000 and 1,000,000 inclusive. `return_null` is an exact boolean
- Reviewed handler behavior: return `None` when `return_null` is true; otherwise return the integer sum. No filesystem, network, subprocess, device, model, clock, randomness, global mutation or other external effects
- Reviewed semantic validator: finite validation of an exact integer in [-2,000,000, 2,000,000] or `None`. It is trusted code, not a scientific-validity oracle
- Worker grants: a detached immutable subset of the one declared permission, configured by the worker owner. The normal qualified case grants that permission; the empty subset demonstrates runtime denial. No approval token is configured or accepted
- Input object bytes at most 256; decoded request envelope at most 4 KiB under the stated encoding; stored result document at most 16 KiB; response envelope at most 4 KiB. All participating Python values are reviewed plain built-ins

These are proposed constants for owner acceptance, not claims about a tool already registered in the inspected repository. Qualification must independently review the exact handler and validator sources and then record the expected declaration signature. **No signature value is invented in this ADR.** Supplying the runtime's current signature as its own expected value is not independent admission.

The bootstrap explicitly registers this known handler in the existing runtime, injects that runtime, and supplies the configured tool ID and reviewed declaration signature. The adapter checks `runtime.registration_signature(tool_id)` against that locally held signature at binding and before each input read. There is no public ToolSpec getter. The adapter does not inspect `_specs`, infer arbitrary tool risk, hash handler code, duplicate the registry or claim that signature equality proves purity. The existing signature describes declarations and omits the handler and semantic-validator implementation. Cooperative, unchanged bootstrap/handler binding is a trust assumption; hostile Python or mutation between checking and execution is outside scope.

A second tool or a consequential write tool requires a separate profile review. The two wrappers are not an extensible tool-hosting service.

## Trust and local dataflow

The producer, Workflow author, worker owner, runtime registrar, CAS owner and result consumer belong to **one trusted operator domain**. Every producer able to schedule this endpoint can exercise its worker-configured authority. Queue names, reference digests and descriptive manifests are not caller authentication or per-request approval. The operator owns Temporal access controls outside these adapters; no multi-tenant claim is made.

The admitted arrangement uses one trusted local host and one operator-controlled CAS root and ancestors. The worker holds the existing writable canonical store; producers seed bounded input objects through that canonical owner before processing, and readers use that same local root, optionally through canonical read-only instances. Only one writer process is active; worker setup limits this profile to one concurrently executing Activity. These are deployment conditions, not a new adapter lock or scheduler. No cross-host object availability, replication, remote CAS, concurrent multi-process write safety or filesystem sandbox is supplied. A remote result consumer without access to this root cannot resolve the result reference and is outside the first profile.

Dataflow:

1. The trusted producer writes the bounded input into the canonical local CAS before submission
2. The consumer-owned Workflow passes a reference-only request to the optional Workflow helper
3. Temporal schedules a non-local Workflow Activity and records its transport state
4. The worker adapter reads SDK-owned Activity metadata and applies all early gates
5. It checks the configured declaration, reconstructs the canonical input reference, reads verified bytes from the injected store, checks length and input schema, and calls the injected runtime once
6. It serializes the returned output and receipt as an explicitly reported result, writes one result document through the canonical store and returns its reference
7. The local result reader verifies the referenced bytes and examines the original tool outcome; a completed Activity alone is insufficient

Temporal history receives reference metadata and the response reference, not raw tool input/output bytes. Reference metadata is still information visible to the deployment's authorized history readers. The profile permits only synthetic, non-sensitive data. No API key, task token, approval token, credential, local path or arbitrary URL is included in the records.

CAS roots follow symlinks, permissions are best effort, and object/metadata writes are not transactional. `get_bytes` reads the whole object before the adapter can compare its size. The byte limits are post-read checks plus a **trusted bounded-content assumption**, not adversarial memory limits or protection against a malicious oversized object. The SDK also decodes its message before entering this adapter; the envelope limit does not promise a pre-deserialization memory bound.

## Exact optional module interfaces

These are proposed interfaces, not executable implementation supplied by this ADR.

### Worker module

File: `src/opendot_engineering/adapters/temporal_activity.py`

Public construction signature:

`ReferenceActivity(*, runtime: ToolRuntime, store: ArtifactStore, tool_id: str, expected_registration_sha256: str, granted_permissions: frozenset[str], expected_namespace: str, expected_task_queue: str)`

The constructor accepts only the canonical runtime/store identities and the fixed profile ID; all other values are bounded trusted operator configuration. It snapshots permissions into an immutable value and checks the reviewed signature. It does not construct/register a runtime, create a CAS, load code, start workers or connect to a service. A preconstructed store's bootstrap initialization is outside the per-Activity I/O gate.

Activity method: `ReferenceActivity.run(request: dict[str, object]) -> dict[str, object]`, registered by the caller-owned worker under the fixed name `opendot.synthetic.reference.v1`. It is a synchronous threaded Activity using an executor owned by the existing Temporal worker bootstrap. The adapter owns no executor lifetime. The request has no injected Info, permissions, root, tool selection, code path, approval token or scheduling kwargs.

Exactly one production call site may invoke:

`runtime.execute(tool_id, payload, granted_permissions=local_grants, approval_token=None, backoff_base_s=0.0, attempt_limit=1)`

No alternative call site, fallback runtime, private dispatch, retry loop, `can_retry` decision, result-publication loop or re-entry after a failure is admitted.

### Workflow module

File: `src/opendot_engineering/adapters/temporal_workflow.py`

Public signature: `async execute_reference(request: dict[str, object], *, task_queue: str) -> dict[str, object]`

This helper is called only from a consumer-owned Workflow. The queue is a trusted, stable Workflow-code configuration value, not a field selected by an external request. Each consumer Workflow run may call this helper once. The helper uses the fixed Activity name and fixed Activity ID `opendot-synthetic-reference-v1`, and schedules one non-local `workflow.execute_activity` command with `RetryPolicy(maximum_attempts=1)`, `start_to_close_timeout=10 seconds`, and `schedule_to_close_timeout=60 seconds`. It has no override kwargs, retry/resubmit loop, standalone-client path or Local Activity path. It returns the plain response or propagates the SDK failure.

The helper imports no worker module, runtime or CAS code. It performs no filesystem/CAS access, runtime execution, permission lookup, environment/version lookup, clocks or random ID generation during Workflow execution. SDK scheduling and replay remain Temporal-owned. The trusted consumer Workflow is reviewed to exclude retries of this operation, Workflow retry/new-run loops, reset/continue-as-new resubmission and failure-to-resubmit logic. These conditions are not globally enforceable by the helper and are not a global duplicate guarantee.

Both modules are explicit optional imports. The proposed extra is exactly `temporal = ["temporalio==1.34.0"]`; default dependencies stay empty. No default-path re-export, automatic discovery, plugin registration or import-time network/startup work is allowed. The Workflow module uses ordinary public SDK APIs only. Later qualification must verify its exact tagged-version API and deterministic scheduling behavior rather than relying solely on latest API documentation.

## Activity admission before CAS access

The worker obtains metadata itself from `temporalio.activity.info()` inside the Activity. No public adapter argument or request field can substitute an Info object. A qualified worker uses exactly SDK 1.34.0; a missing dependency, version mismatch or unavailable required public API refuses without a compatibility fallback. Version/API qualification occurs in trusted bootstrap, outside Workflow replay.

The invocation must pass all of the following before any per-invocation CAS read/write or runtime execute:

1. A real SDK Activity context exists; metadata retrieval succeeds
2. `type(info.attempt) is int` and `info.attempt == 1`
3. `info.is_local is False`
4. `info.retry_policy` is present and is the SDK's public RetryPolicy object; its public `maximum_attempts` is an exact integer equal to 1, excluding booleans
5. Both received timeout fields are present, finite, positive durations and equal the profile values: start-to-close 10 seconds and schedule-to-close 60 seconds. Unknown or server-normalized unequal values refuse
6. The actual activity type, namespace and task queue match the fixed type and worker-local configuration. Workflow ID and Workflow run ID are present, bounded, nonempty strings. Standalone Activities are outside this first mode
7. The decoded request has exactly the allowed plain fields and bounded values; reference metadata passes the checks below. Any unexpected authority/override field refuses
8. The locally configured tool ID still has the independently reviewed registration signature through the existing public API

The tagged SDK source includes retry-policy information in Activity Info, warns that the received policy may differ from the submitted policy, and treats omitted policy information as unknown rather than safe. The tagged worker populates it only when the incoming message contains the field. This makes the gate expressible; it does not prove what any untested server deployment reports. [SDK 1.34.0 Activity Info](https://raw.githubusercontent.com/temporalio/sdk-python/1.34.0/temporalio/activity.py), [SDK 1.34.0 worker metadata conversion](https://raw.githubusercontent.com/temporalio/sdk-python/1.34.0/temporalio/worker/_activity.py)

Setting a policy at submission is necessary but insufficient. Receiving attempt 1 alone is insufficient. Default, unlimited, missing, malformed or greater-than-one policies all refuse. Temporal defines a one-attempt policy as disabling Activity retries; zero is unlimited. No claim is made about later administrative policy changes or separately scheduled invocations. [Temporal retry policies](https://docs.temporal.io/encyclopedia/retry-policies)

Adapter-created SDK ApplicationErrors are non-retryable and use only these fixed type categories: `TemporalAdmissionRejected` before CAS; `TemporalInputRejected` for input retrieval/decoding/schema failure; `TemporalResultEncodingFailed` after a runtime return that cannot be represented; and `TemporalResultStoreFailed` for canonical result publication failure. Details contain only a bounded phase/code, never input bytes, filesystem paths or a claim that the handler did not run. These are transport failures, not new tool receipts. Configured runtime control exceptions and other exceptions escaping execute propagate unchanged to the SDK boundary. SDK-owned conversion, timeout and completion failures retain their SDK categories. An off-context direct call refuses before I/O. No malicious-request memory/sandbox claim is added by these checks.

## Guard and transport I/O boundary

The proposed exception permits Temporal metadata as transport context only. It **does not authorize changing the existing owner's definition of a forbidden bound control context**. If the injected resolver regards that embedding as forbidden, execution must deny and the deployment is unusable under this proposal. Never clear context, replace its resolver with a null-returning resolver, suppress the configured exception, build an unguarded substitute or call a private guard/dispatch method.

The original runtime guard remains at its existing public execute boundary and copied dispatch context. Every non-None resolver result, including false-like results, denies; resolver errors deny. The adapter propagates the original configured control exception unchanged up to the SDK boundary, without wrapping it as an ordinary tool failure or result document. Network error serialization cannot preserve Python exception object identity across processes and is not claimed to.

Input CAS retrieval and decoding happen before `execute`, so a forbidden control context can already have caused a transport CAS **read**. This ADR expressly proposes allowing that read within the trusted operator domain; it makes no claim that the runtime guard denies all transport I/O. There is no result CAS write after an execute-boundary guard refusal. If the owner requires denial before every CAS read, reject this two-wrapper proposal; no private guard preflight or new permission owner is admitted.

## Wire and result contract

### Request and canonical references

Request keys are exactly `schema_version` and `input_ref`. The version is `opendot.temporal.request.v1`; there are no optional authority fields.

`input_ref` is a plain record containing exactly the ten canonical ArtifactRef field names: `artifact_id`, `uri`, `mime_type`, `size_bytes`, `sha256`, `schema_version`, `producer`, `task_id`, `source_refs`, `integrity_verified`.

- `sha256` is exactly 64 lowercase hexadecimal characters; `artifact_id` equals `sha256:` plus that digest, and `uri` equals `artifact://sha256/` plus that digest, with no alternative spelling or extra path components
- `size_bytes` is an exact integer in [1, 256]; `mime_type` is exactly `application/json`; reference `schema_version` is exactly `1.0.0`
- `producer` and `task_id` are nonempty bounded text identifiers, at most 80 characters, restricted to letters, digits, dot, underscore and hyphen. They are untrusted descriptive labels, never routing, grant, provenance or uniqueness evidence
- `source_refs` is an empty JSON array for this first input profile; `integrity_verified` is an exact boolean, accepted only as a transmitted claim and never relied on

The worker reconstructs the canonical `core.contracts.ArtifactRef`, converts `source_refs` to its canonical tuple, resets the received integrity claim to false, calls its existing validation, and uses injected `ArtifactStore.get_bytes(ref)`. That method verifies the byte digest; the adapter separately checks actual length against declared length and the profile limit. No request-derived path, URL, alternate store or private CAS reader is used.

Strict input decoding reuses the existing `adapters.source_audit._decode` helper unchanged, including duplicate-key and nonfinite-constant refusal. This is a narrow dependency on the canonical parser, not a copied parser. Its filesystem helpers are not substituted for the CAS reader. The adapter then enforces the exact bounded input schema above; numeric exponents, floats, booleans-as-integers, nested objects and unexpected keys fail. This closes values such as an overflowing JSON exponent even where generic JSON parsing yields a float. No filesystem/JSON helper implementation is forked.

The request-envelope contract applies to the SDK-decoded plain record. It does not claim to detect duplicate keys that an upstream SDK decoder has already collapsed. The trusted producer and qualified SDK converter are part of this profile.

### Stored result document

The worker stores one strict JSON document through canonical `ArtifactStore.put_json`, with these exact top-level keys:

- `schema_version`: `opendot.temporal.result.v1`
- `profile`: `synthetic.bounded_sum.v1`
- `input_ref`: normalized canonical input reference record, with the integrity result of this worker's byte/size check explicitly reported
- `output`: the value returned by execute, including legitimate `None`
- `receipt_report`: all thirteen ToolCallReceipt fields, preserving original status, attempts, hashes, semantic-valid flag, error type, breaker state and execution-liveness values
- `observation_provenance`: `serialized_runtime_report_not_live_proof`
- `scientific_validity`: false
- `device_control_authority`: false
- `independent_review`: `NOT_EVALUATED`
- `owner_integration`: `NOT_EVALUATED`

Receipt enums become their original string values. A non-null execution observation becomes a plain report of its eight original fields, not a reconstructed `_ObservedToolExecution`; a null observation stays null. `execution_liveness` is preserved as reported, without deriving stronger termination/effect claims. Serialization is explicit over these known fields and reviewed plain built-ins; no arbitrary `default=str`, callable hooks, dataclass reconstruction, lossy field dropping or handler re-entry is permitted. Receipt/observation strings are at most 256 characters; numeric fields must be finite with exact integer/boolean types where their contracts require them. The liveness map has at most 16 existing owner-produced keys with bounded string/boolean/scalar values, and no nested arbitrary objects. Unknown keys or values fail instead of being discarded. A pure strict-JSON encoding/size preflight over this finite record precedes the canonical put; it is not a new CAS writer or digest algorithm. An unknown/unrepresentable field or out-of-bounds document fails publication after dispatch.

`COMPLETED`, `FAILED` and `BLOCKED` runtime outcomes can all produce a successfully delivered Activity result. A failed or blocked tool is not rewritten as success. In particular, `BLOCKED` can have `attempts=1` with zero handler calls, and completed null output is legitimate. The bridge does not recover a raw output that the runtime withheld after semantic failure. Consumers must inspect both status and semantic-validity fields, separately from storage integrity and Temporal outcome.

For the result put, producer is fixed to `opendot.temporal.reference.v1`, task ID is the runtime receipt call ID, reference schema is `1.0.0`, and `source_refs` contains only the input artifact ID. The result store retains its existing first-write metadata semantics; returned metadata is not authenticated provenance. Response keys are exactly `schema_version` (`opendot.temporal.response.v1`) and `result_ref` (the canonical reference serialized as a plain record). The result reference uses exactly the same ten field names and canonical digest/ID/URI spelling; its exact-integer size is in [1, 16384], MIME is `application/json`, reference schema is `1.0.0`, producer is the fixed value above, task ID is the 24-character lowercase-hex receipt call ID, and its one source reference is the input artifact ID. Its transmitted integrity flag is again only a claim until consumer verification. Input-only size and empty-source rules are not reused for a result. This is reference-in/reference-out, not a new execution receipt API.

A local consumer reconstructs the same canonical ArtifactRef type, verifies bytes through the same store, checks the 16 KiB limit, actual length and result schema, and treats observation JSON as a report only. This is a consumer obligation, not a third adapter. A Workflow must not resolve that reference itself.

Raw CAS input digests identify stored bytes. Runtime input/output hashes identify the runtime's own serialization. Equality is neither required nor advertised; differing JSON whitespace alone can distinguish the input digest from its runtime hash. CAS integrity does not establish semantic acceptance, authorship, scientific validity or authorization.

## Failures replay and uncertain execution

There are four distinct states, not one generic replay promise:

1. **Queued and not started:** an Activity already scheduled in durable history can be delivered when an admitted worker becomes available, subject to deadlines and server behavior. That is its initial attempt, not recovery of an executed callable. If its scheduling command was never recorded, deterministic Workflow re-execution can generate the command; no tool execution is thereby established
2. **Completed result recorded:** ordinary Workflow history replay consumes the recorded Activity response and does not call the handler again. It may later find the local CAS bytes unavailable; history durability is not CAS durability
3. **Invocation running or completed but acknowledgment unknown:** worker loss, transport timeout, serialization/storage failure, cancellation or missing completion acknowledgment can leave execution or publication uncertain. A Temporal failure is not evidence of no handler effects. No automatic redispatch, resubmission or CAS scan-to-recover occurs
4. **A new scheduling operation:** another Workflow run, reset, manual retry, separately submitted Activity or repeated helper invocation can create another accepted invocation with attempt 1. No CAS digest, Activity ID, runtime call ID, signature or stored report suppresses it

The history-replay distinction follows Temporal's documented model. The refusal of recovery, additional publication attempts and global uniqueness are conservative choices of this proposed adapter contract. [Activity replay and idempotency](https://docs.temporal.io/activity-definition), [Workflow history and execution](https://docs.temporal.io/workflow-execution)

No adapter-created heartbeat, cancellation, thread-kill, process supervisor, rollback, reconciliation event, durable completion marker or resume protocol is introduced. Ordinary SDK cancellation/shutdown may interrupt delivery; existing runtime threads may remain active after a timeout. The original liveness uncertainty must survive in a stored report if one is available. The operator may inspect history and local artifacts read-only outside this protocol; an unacknowledged or missing report never authorizes a rerun. Manual submission is a separate decision with its own duplicate/effect risk.

Serialization or result write failure does not call execute again. Canonical object publication can precede metadata failure, leaving an object without a returnable reference. A returned result reference can exist even if Temporal did not record the completion. No cleanup deletes those bytes and no publication repair protocol is proposed. The companion matrix separates runtime invocation, handler execution, possible output and delivery for each failure.

## Proposed future change budget

Only after explicit owner acceptance and a separately approved scoped AGENTS amendment:

- Add the two optional source modules named above
- Add `tests/test_temporal_activity_contract.py`, `tests/test_temporal_workflow_contract.py` and `tests/test_temporal_transport_owner_boundaries.py`
- Add the accepted ADR, `docs/temporal-reference-transport.md` and its failure-matrix/acceptance documentation
- Add only the pinned `temporal` optional dependency to `pyproject.toml`; default dependencies and existing extras stay unchanged

No other implementation file is in budget. The owner must approve the exact final path list before edits; numbering and documentation filenames are tentative until that acceptance. A subsequent version/release/publication change is a separate scope. No package CLI, service launcher, example bootstrap executable, code loader, database, second CAS, transport registry, model backend, native lifetime owner or recovery system is allowed. Preserve notices, license and provenance; do not import private execution code or receipts.

## Acceptance plan and stopping gates

### Before implementation

The owner must accept the orchestration exception itself; the exact two APIs and Workflow-only mode; the fixed synthetic profile and its independently reviewed declaration/handler evidence; the single-domain/single-local-CAS and single-writer assumptions; the pre-guard CAS-read boundary; the corrected one-invocation claim; the schemas, bounds, timeout constants and failure matrix; and the file budget. A matching AGENTS amendment must be separately accepted and applied under explicit authorization. No SDK installation, server startup, deployment or native execution follows merely from reviewing this proposal.

### Later static and SDK-only synthetic qualification

- Hash all three owners and compare the baseline; preserve all six callable contracts and canonical class identities. Inspect AST/import closure for exactly one execute call site, no private runtime calls, no owner replacement, no default Temporal imports and no service startup
- Use SDK 1.34.0 `ActivityEnvironment.default_info` customized with `dataclasses.replace`. Exercise genuine RetryPolicy objects, absent policy, 0/default/unlimited, negative, 2, boolean and non-exact-integer maximums, malformed fields, attempt 2, local mode, absent or unequal timeouts, off-context calls, wrong namespace/type/queue and standalone invocation. Assert zero CAS reads/writes and zero execute calls for every early refusal
- Use spies and finite real synthetic handlers to establish the exact execute kwargs, zero/one counts, detached local grants and absence of authority fields. Test configured-signature mismatch and explicitly demonstrate that identical declaration signatures alone do not authenticate two different handler functions
- Test the guard's false-like bound values, resolver exceptions and dispatch-context denial without changing its binding. Assert exception identity to the SDK boundary, no handler invocation, permitted prior input read, no result put and no alternate runtime
- Test canonical reference reconstruction, strict shape/digest/URI/length validation, corrupt/missing objects, duplicate input keys, Unicode/nonfinite/exponent/number cases, legitimate completed null output, all runtime outcomes, receipt fields, liveness and observation-report wording
- Inject output serialization failure, object-put failure, metadata failure and response-conversion failure. Assert no second execute call, no forced success, no rollback and explicit post-dispatch uncertainty. Exercise all matrix rows within the applicable harness
- Qualify Workflow command generation and history replay against the exact SDK pin. Assert one non-local command, fixed name/ID/timeouts/policy and no forbidden I/O/imports or retry loop. A synthetic replay is not evidence of server reporting
- Run existing portable callable/artifact/contract regressions separately from optional SDK checks, with authorized tooling. No native integration is part of this plan

### Separately authorized deployment evidence

Specify the exact Temporal server version and controlled operator deployment. Confirm actual received Info values and policy normalization, including refusal when policy information is omitted. Observe queued delivery and completed-result replay separately from a worker-loss/missing-ack case; do not convert the latter into a successful recovery claim. Confirm every worker and reader uses the same local CAS and permitted writer arrangement. Review the consumer Workflow and operator controls against separate submission/reset/retry risks.

If the chosen server does not expose the required policy/timeouts, that deployment is **NO-GO**. Mocked Info tests do not waive the requirement. Unsupported SDK versions, inaccessible local CAS, unknown handler binding, required pre-read control denial, global exactly-once requirements or consequential effects are also **NO-GO as scoped**.

Final acceptance requires owner review of code, claims and outgoing evidence. SDK-only success, a signature, a stored hash or this proposal is not independent acceptance or deployment fitness. Scientific validity and device authority remain false; independent review and owner integration remain NOT_EVALUATED unless a separate, appropriately scoped review supplies evidence.

## Evidence and limits of this proposal

The proposal was written outside the repository using AGENTS.md, the existing owner-boundary review, ADRs 001–003, callable/artifact documentation, canonical source and official Temporal documentation. No repository file was changed, SDK installed/imported, tests or server run, handler executed, native action taken or remote state changed.

Local source facts were checked at the baseline above. The public tagged Activity Info and worker conversion files were retrieved; the exact tagged Workflow implementation could not be retrieved through the available documentation fetch, so its detailed API/replay behavior remains an explicit later qualification item. Current public Workflow API documentation corroborates the general scheduling interface but is not substituted for pin-specific acceptance evidence. [Public Workflow API](https://python.temporal.io/temporalio.workflow.html#execute_activity)


## Bounded hosted CI qualification amendment (2026-10-02)

Status: APPROVED FOR INTEGRATION-CANDIDATE PREPARATION ONLY. Actual hosted execution requires root approval of the final candidate. The real-server gate is NOT RUN / NOT VERIFIED. Historical SDK-only acceptance and the failed converter receipt are preserved; this amendment does not retroactively expand those decisions or evidence.

The only additional proposed qualification scope is the reviewed optional GitHub Actions ubuntu-24.04 / Python 3.12 job with temporalio 1.34.0, Temporal CLI 1.9.1 and embedded server 1.32.0, verified from fixed official dependency/acquisition pins. The entire job is bounded to ten minutes. This is one loopback-only synthetic test profile, one trusted local CAS and one persistent SQLite path within that job. Activity start-to-close remains ten seconds and schedule-to-close sixty seconds, with maximum_attempts=1 and actual received Info gates unchanged.

The service experiment may cover genuine queued initial delivery after a graceful server restart while no Activity invocation is active, and recorded-result replay after graceful quiescent worker/server restarts. Quiescence must be observed, including fail-closed latching of runtime liveness uncertainty, before a planned restart. A missing acknowledgment or unknown in-flight execution is not evidence for recovery, termination or repeat dispatch. The separately reviewed, explicitly labeled negative semantic-validator fixture is test-only and does not extend the production profile.

Protected production adapter modules, ToolRuntime, ArtifactStore, contracts, original deny-only guard, default dependency set and default import closure remain exact. This amendment adds only the accepted test/acquisition/evidence boundary and optional hosted workflow, not an execution backend, registry, store or permission system.

The reviewed harness first runs the explicit six SDK/pure test files, requiring the exact independently reviewed collection and its pinned passing-node total without failures/errors/skips. The acquirer must refuse effective proxy/credential-routing configuration before network access; it may not discard inherited routing to force a direct connection, retry through another route, or reinterpret a prior failure as proof of a general network condition. Native service execution remains gated behind successful install, unit qualification and verified CLI acquisition. The seven explicitly selected service cases fail closed on missing prerequisites rather than skipping. Ordinary pytest discovery must not accidentally start the service gate. Raw service logs, history, SQLite and CAS remain private to job temporary storage; only the reviewed bounded allowlisted evidence can be emitted after validation.

Explicit exclusions remain: local service or CLI/native executable execution; in-flight kill; proc, namespace, descendant or lifetime investigation; arbitrary tool profiles; general cancellation/recovery protocols; deployment; credentials/providers; and general durability, exactly-once effects, global duplicate suppression or scientific acceptance claims. No local install or new acquisition is authorized by preparing this integration. This candidate may not be pushed, merged, dispatched or otherwise executed in hosted CI until root approves its exact final identity.

The CI change budget adds only .github/workflows/temporal-server.yml, ci/acquire_temporal_cli.py, ci/run_temporal_server_gate.py, ci/temporal-sdk-requirements.txt, ci/temporal-server-nodes.txt, ci/verify_temporal_server_gate.py, tests/acceptance/temporal_server_gate.py, tests/test_temporal_cli_acquisition.py, tests/test_temporal_server_gate_verifier.py and tests/test_temporal_server_harness_unit.py. AGENTS.md and this ADR receive only the matching bounded amendment. The historical ten-path production candidate remains otherwise exact. Current public-main README English/Chinese bytes and every unrelated current-main file must be preserved.

## Finite batch preparation amendment (2026-10-02)

Status: APPROVED FOR LOCAL PREPARATION ONLY. This append-only decision does not
change historical seven-case evidence or authorize hosted execution.

The existing test-only harness/verifier may prepare exactly 200 frozen synthetic
jobs on one trusted host and canonical CAS, with at most 16 reserved or submitted
workflows lacking validated terminal evidence, eight external Temporal Activity
slots, and a matching eight-worker executor. One helper call and one Activity
attempt per Workflow, exact 10/60-second Activity deadlines, and the original
one-second callable policy remain unchanged. Reserve all finite job/attempt/output
allowances before any RPC. Unknown acknowledgment or liveness never refunds a
reservation or permits blind replay; it latches new admission closed.

Preserve exact ToolRuntime, ArtifactStore, contracts, Activity, Workflow and
deny-only guard bytes. No production owner, scheduler, registry or service is
added. The only admitted change paths are AGENTS.md, this ADR,
ci/run_temporal_server_gate.py, ci/verify_temporal_server_gate.py,
ci/temporal-batch-nodes.txt, tests/test_temporal_server_harness_unit.py,
tests/test_temporal_server_gate_verifier.py and docs/temporal-batch-qualification.md.
Freeze expected fixture verdicts before implementation. Preparation admits only
pure deterministic fixture/trace tests, with no sleeps or native probes. The
existing hosted workflow, seven-case acceptance file, node manifest and transport
guide remain unchanged. A later separately approved exact candidate must wire
and qualify the hosted path; this preparation provides no service evidence.

No local Temporal service/CLI, native process/namespace/descendant/lifetime or
recovery investigation, models/providers, paid/private input, remote action,
multi-host deployment, device action, lease or permission owner is authorized.
Configured slots are not observed overlap; 200 jobs are not 200 agents. No
throughput, speedup, fairness, hard memory/thread limit, termination, cancellation,
recovery, general exactly-once or scientific acceptance claim follows.

The pre-implementation acceptance matrix and schema are frozen in
[the batch protocol](../temporal-batch-qualification.md).

### Local collection-identity integration follow-on (2026-10-02)

After actual locked pytest qualification of the initial preparation source, a
confirmed integration defect was found: replacing dots in a JUnit classname
with slashes does not reconstruct collected unittest-class node IDs. Local
preparation may therefore additionally modify .github/workflows/temporal-server.yml
only to reuse a pure strict one-to-one collected-node/JUnit identity helper in
the existing verifier and set the pure/SDK expected count from a fresh actual
collection after its focused tests are added. Preserve the six-file selection,
count/uniqueness/all-pass gates, acquisition and seven-case service path. This is
a ninth-path local allowance, not hosted execution or publication approval. The
initial eight-path preparation results remain historical with their exact scope.

### V2 asynchronous admission preparation (2026-10-02)

Root approved a separate local v2 preparation candidate, preserving the accepted
nine-path v1 candidate and receipts. Within those same nine paths, the existing
test-only BatchAdmission may share one reservation/ack settlement implementation
between its synchronous fixture wrapper and a bounded asynchronous start wrapper.
Reservation precedes callback invocation and await. An explicit single-thread,
single-loop, single-producer policy excludes mixed submission modes and concurrent
producers; it does not add arbitrary cross-thread mutation or a lock across await.

Cancellation/timeout/unknown acknowledgment after reservation consumes the attempt
and outstanding slot and permanently closes admission. At most one shielded start
operation may remain owned for bounded-identity late observation, without retry or
replacement. A valid late ack binds only its original reservation and cannot clear
uncertainty or release capacity. A cancellation request already pending before
admission issues no RPC; a task cancelled before wrapper entry does no work.

Activity execution and server-side completion can precede the client's observed
start ack. The existing ack-before-entry FABRICATED_UNIT_DATA schema remains
fixture-only and unchanged. Live correlation/buffering and cross-thread observation
need separate future review; no event may be fabricated or reordered to satisfy
that fixture. No new live evidence, service/native execution, hosted wiring or
publication is authorized. Deterministic future-controlled tests and fresh actual
locked pytest collection must precede any workflow-count adjustment.

## 2026-10-02 real-batch local preparation amendment

This amendment authorizes only local preparation of a separate manually selected
hosted `batch200` profile. It preserves every earlier historical decision and
receipt. The foundation is the frozen v2 async preparation source; preparation is
not evidence of publication, merge, or real service execution.

One shared `BatchAdmission` owns reservations, acknowledgments, uncertainty and
validated-terminal release. A short lock serializes thread-side closure with
reservation and logical public-client entry. A reserved but prevented start stays
consumed. No lock spans an SDK await, canonical CAS operation, callable, or file
write. Monotonic observations retain actual order, including Activity entry or
exit before client acknowledgment. Original receipt, result bytes, received Info,
run identity and terminal history must bind before a slot is released.

The new `opendot.temporal.real-batch.*.v1` schema cannot be selected by fabricated
preparation evidence. Configuration remains 200/16/8 with the existing 180-second
work deadline, at most 40 seconds observation-only cleanup, fixed 10/60-second
Activity settings and one attempt. Existing acquisition, preflight and observed
public shutdown are reused; the seven reference cases are unchanged. No source
owner, dependency pin or default import changes. The public SDK's default
transport retry behavior is recorded separately from application submissions.

The path ceiling is AGENTS.md; this ADR; the existing harness and verifier;
ci/temporal-batch-nodes.txt; the new ci/temporal-real-batch-nodes.txt and explicit
acceptance file; the two existing harness/verifier unit owners; the existing
Temporal workflow; docs/temporal-batch-qualification.md; and the transport guide.
No hosted execution, acquisition, publication, native lifetime probe or provider
operation is authorized by this amendment. Later execution needs exact-candidate
approval and explicit manual dispatch. See the batch protocol for limits.
