# ADR 008: fixed dependent synthetic Temporal recovery

Date: 2026-10-02. Design revision: 4 (terminal-drain reporting fence; all revision 3 byte/schema/resource pins unchanged). Status: **DESIGN FROZEN FOR INDEPENDENT REVIEW; IMPLEMENTATION AND QUALIFICATION NOT_RUN**.

This is a narrow proposed exception to ADR 004, not a general mission API. Root approved preparing the design within seven paths; executable edits need independent design acceptance and root's exact go-ahead. Publication, hosted execution, service acquisition and additional paths are not authorized by this document.

## Canonical-enum erratum (design revision 3)

The revision 2 design fixtures incorrectly used enum member names CLOSED/OPEN/HALF_OPEN for serialized breaker state. The unchanged canonical `BreakerState` values are `closed`, `open`, `half_open`, and the preserved `_receipt_report` serializes `.value`. The runtime/serializer were correct; this was a frozen-design/fixture error found before any qualification run. Revision 3 corrects only that new-profile receipt requirement and dependent fabricated A/B original-body/origin/B-effect hashes. Plan, source, registration, seed, input and output pins remain identical; no uppercase compatibility fallback is accepted. Uppercase breaker strings are an explicit RESULT_INVALID negative oracle. Prior freezes and pre-correction executable candidate are retained separately; no prior qualification is claimed.

## 1. Purpose and owner

The only graph is A → B in `synthetic.dependent_sum.v1`. A invokes the already reviewed `synthetic.bounded_sum` once on `{left: 2, right: 3, return_null: false}`, giving 5. B independently re-reads and validates A's accepted original result, then invokes the same handler once on `{left: 5, right: 1, return_null: false}`, giving 6. B depends on verified A; no client can choose nodes, tools, transforms, queues, retries, grants or policies in a message.

Temporal alone owns commands, delivery, Workflow state/history, timers and Workflow-task reconstruction. The existing optional `temporal_workflow.py` gains one fixed `DependentSumWorkflow`; the existing optional `temporal_activity.py` gains a fixed `DependentSumActivity` with `execute_step` and read-only `inspect_result` endpoints. The latter reuses the injected exact canonical ToolRuntime/ArtifactStore, canonical ArtifactRef and existing strict JSON/reference/receipt helpers. No database, checkpoint object, effect registry, journal, outbox, CAS scan, alternate scheduler, retry owner, copied store, cancellation backend or live-proof reconstruction is added. A state query is a detached projection of history-derived fields, never a second persistence layer.

The existing `execute_reference` function and `ReferenceActivity` endpoint, their exact v1 schemas, Activity identity, one-call semantics, and helper behavior remain unchanged. Existing owner tests must retain their assertions on that original subtree and add a precise allowlist for this exception. No default import, dependency, initializer, core/runtime/store/source-audit owner, CI/harness, installed guide or a3/a4/a5 asset changes.

## 2. Frozen encoding, plan and identities

Canonical encoding is `json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")`. Only finite, explicitly bounded plain JSON values are accepted; exact `type` checks exclude bool-as-int, float-as-int and subclasses. Dictionary keys are exact plain strings. No default serializer, arbitrary object, recursive user graph, duplicate JSON key or nonfinite value is permitted. The canonical source-audit `_decode` owner supplies strict raw JSON decoding. Each schema has an exact field set and rejects unknown fields, including authority fields.

The plan, schema literals, resource constants and independently prepared fixture vectors appear in section 12. The literal plan SHA-256 is **19843079a5da00754ec1b5399962c33874b907eb4d0d6fcf55cd3be2f4dffb63**. Production code must compare against this reviewed literal, not hash a supplied plan to set its own expectation. There is no wire field containing an arbitrary plan.

The reviewed handler-source pin is **a97dadac88bed7b09d2398516617216cb865ae97db411c12b72de01d7a78d1cb**: concatenate the exact AST source segments of `_validate_payload`, `bounded_sum`, `bounded_sum_valid` in that order, separated by two LF bytes, and append one LF. The 792-byte source fragment is from the unchanged original adapter. Its dependencies remain under source review. Bootstrap reviews source and registers the exact handler/validator, then supplies the literal plan/seed/source/declaration pins to the fixed adapter. The runtime's registration signature **5f2b1e81954530f31c7d2c83b9c582883b8391190ebe13b69b8bf91f044cb0c3** authenticates neither callable identity nor who executed it. A constructor comparison with a supplied source pin is a configuration gate, not independent measurement of runtime handler identity. Trusted bootstrap and a cooperative single operator are preconditions; private runtime registries must not be inspected or replaced.

Mission IDs are exact strings matching `[a-z0-9][a-z0-9-]{0,31}`. The sole Workflow ID is `opendot-dag2-` + mission ID + `-` + the literal plan digest. Namespace and task queue are trusted bootstrap bindings, exact `[A-Za-z0-9._-]+` strings of 1–128 characters. Actual run IDs are exact nonempty strings of at most 128 characters. They come from SDK context, never from start/update claims. Normal bootstrap starts with duplicate-ID rejection and binds the returned actual run ID; ambiguous start acknowledgment closes start admission and reads only that exact identity. No retry/reset/continue-as-new/new-ID loop is admitted. Duplicate-ID behavior depends on actual Temporal retention/configuration and is not permanent global deduplication.

The pure deterministic helper in `temporal_workflow.py`, reused by Activity validation, returns:

```
"sha256:" + SHA256(canonical({
  "schema_version": "opendot.effect.v1",
  "namespace": actual_namespace,
  "workflow_id": exact_workflow_id,
  "plan_sha256": literal_plan_digest,
  "node_id": "A" or "B",
  "parent_result_sha256": null for A, accepted_A_ref.sha256 for B
}))
```

Run IDs, attempts, workers, timestamps, tokens and grants do not enter this logical correlation identity. Run ID is nevertheless separately mandatory in every original-result binding. Effect identity provides no destination-side idempotency or process fencing. A's effect ID is available at admission; B's is absent until the original A result has been accepted. A concrete B fixture pin depends on the independently frozen original A fixture digest; genuine runtime result digests include variable call/observation IDs and latency and cannot be predicted before publication.

The fixed Workflow type is `opendot.synthetic.dependent-sum.v1`; execution Activity type is `opendot.synthetic.dependent-step.v1`; inspection type is `opendot.synthetic.dependent-inspect.v1`. Execution Activity ID is `dag2-execute-` + the 64 lowercase effect hex digits. Normal inspection ID is `dag2-inspect-normal-` + the same digits. Reconciliation inspection ID is `dag2-inspect-reconcile-` + those digits. Inspector SDK Activity identity and the original execution Activity identity in the result body are distinct checks.

## 3. Exact wire contracts

All request/response envelopes are at most 4096 canonical UTF-8 bytes. Scalar text/digest/reference rules apply before I/O or scheduling. New schema-version literals are distinct from all reference-profile v1 schemas.

### 3.1 Canonical wire references

Exactly these ten fields, preserving canonical ArtifactRef identity: `artifact_id`, `uri`, `mime_type`, `size_bytes`, `sha256`, `schema_version`, `producer`, `task_id`, `source_refs`, `integrity_verified`. Digest is exactly 64 lowercase hex; ID is `sha256:` + digest; URI is `artifact://sha256/` + digest; MIME `application/json`; ref schema `1.0.0`; size is an exact int, positive and within the appropriate cap. `source_refs` is a plain list of the exact expected artifact IDs in order. The new profile's canonical wire form always has `integrity_verified=false`, including after verified reads/puts; it is not an authority claim. Canonical in-memory ArtifactRef values may have true but are normalized to false for this wire.

The seed is exactly canonical bytes `{"left":2,"return_null":false,"right":3}` (40 bytes), digest `897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02`, producer `opendot.temporal.dag-seed.v1`, task ID `seed`, no sources. The result producer is `opendot.temporal.dag-result.v1`, task ID is the exact effect's lowercase 64 hex digits, and sources are `[seed.artifact_id]` for A or `[seed.artifact_id, accepted_A_ref.artifact_id]` for B. A new fixed-result reference validator must not reinterpret or change the old v1 call-ID metadata rule.

### 3.2 Start and step

Start (`opendot.temporal.dag-start.v1`) has exactly `schema_version`, `mission_id`, `plan_sha256`, `seed_ref`. Workflow validates exact plan/seed pins and actual SDK Workflow Info: type/name/ID, namespace/queue shapes, attempt exactly 1, retry policy maximum_attempts exactly 1, run_timeout and execution_timeout exactly 300 seconds, no cron, no continued_run_id, no parent, and `first_execution_run_id == original_execution_run_id == run_id`. This rejects retry, continue-as-new and reset lineage. No Workflow Activity is scheduled if start validation fails; failure is the fixed nonretryable `TemporalDagStartRejected`.

Step (`opendot.temporal.dag-step.v1`) has exactly `schema_version`, `mission_id`, `plan_sha256`, `node_id`, `effect_id`, `seed_ref`, `parent_result_ref`. Parent is null only for A; B's parent is the recorded accepted A reference. SDK supplies namespace/Workflow ID/run/queue. Step response (`opendot.temporal.dag-step-response.v1`) is exactly `schema_version`, `effect_id`, `result_ref`. A response is a candidate, never acceptance.

Both Activity endpoints check real `activity.Info` and real RetryPolicy identity before any per-invocation CAS I/O: attempt exactly 1, nonlocal mode exactly false, maximum_attempts exactly 1, 10-second start-to-close, 60-second schedule-to-close, exact configured namespace and task queue, exact derived Workflow ID and nonempty bounded run ID, expected Activity type and derived Activity ID. Fixed adapter bootstrap additionally binds `expected_workflow_id` and `expected_workflow_run_id` for this one mission/run, plus namespace/queue and plan/seed/source/declaration pins. This deliberately one-run binding prevents a foreign actual SDK run from passing before a read. Worker replacement for the same exact run is allowed; a fresh run requires fresh explicit admission outside this slice.

`execute_step` performs only the fixed one runtime call after gates. It reads seed at most 256 bytes and checks actual size, digest, strict decode and exact canonical seed bytes. B also reads A's exact original result at most 16384 bytes and uses the same read-only validation routine with expected A effect/domain/seed/input/output pins before forming B's fixed input. Per-call declaration and present worker grants are rechecked; original deny-only guard remains active; call options are `approval_token=None`, `backoff_base_s=0.0`, `attempt_limit=1`. No `can_retry` or second call follows any result or exception.

### 3.3 Original result body

`opendot.temporal.dag-result.v1` has exactly the following 21 fields:

`schema_version`, `profile`, `mission_id`, `node_id`, `effect_id`, `plan_sha256`, `namespace`, `workflow_id`, `workflow_run_id`, `activity_id`, `registration_sha256`, `seed_ref`, `parent_result_ref`, `input_payload_sha256`, `output`, `receipt_report`, `observation_provenance`, `scientific_validity`, `device_control_authority`, `independent_review`, `owner_integration`.

Values must match the recorded request, actual original execution SDK identity and fixed profile. `input_payload_sha256` is the frozen concrete node payload digest, separately verified against the unmodified original receipt's `input_hash`. This is distinct from the seed raw-byte digest for B. Output is finite plain int within the old synthetic bound, or null; positive acceptance requires exactly node A=5/B=6. Receipt is serialized by the existing `_receipt_report` without reconstructed live objects. Provenance is `serialized_runtime_report_not_live_proof`; scientific/device flags false, review/integration `NOT_EVALUATED`. Publication uses one canonical `put_json`, at most 16384 body bytes, correct fixed producer/effect task/sources. Encoding/publication/response conversion failure after runtime entry is UNKNOWN, even if bytes may exist. No repair, repeat put or second execute is allowed.

Receipt exact fields are the existing 13: `call_id`, `tool_id`, `tool_version`, `status`, `attempts`, `latency_s`, `input_hash`, `output_hash`, `semantic_valid`, `error_type`, `breaker_state`, `execution_observation`, `execution_liveness`. Validate plain scalar types, call ID 24 lowercase hex, exact tool/version/attempt=1, finite nonnegative latency, bounded error label or null, input hash literal, and one of `closed`, `open`, `half_open`. Observation, when present, has the existing eight fields: `execution_id`, `execution_kind`, `worker_pid`, `dispatcher_pid`, `input_sha256`, `review_target_sha256`, `read_only_declared`, `registration_sha256`. Positive completion requires 32-hex execution ID, in_process kind, positive exact integer PIDs, literal node input/declaration pins, null review target and read_only true. Serialized PIDs are data, not process probes. Positive completion also requires status COMPLETED, semantic_valid true, error_type null, breaker closed, output exact 5/6, and output_hash equal both actual encoded output digest and frozen node output digest.

Liveness must be a valid bounded plain map under the existing liveness key/value allowlist. Any nonempty liveness report or error_type TimeoutError is UNRESOLVED, even if its booleans appear favorable. This conservative profile never deduces termination from such fields. A well-formed BLOCKED/FAILED report with no liveness, output null, output_hash null, semantic_valid false and an error label is CONSISTENT_REJECTED. A completed, internally hash-consistent null/wrong finite output is also CONSISTENT_REJECTED. Invalid/missing hashes, invalid observation shape or inconsistent status/output/receipt are UNRESOLVED. Both rejected and unresolved outcomes block dependents.

### 3.4 Inspect and reconcile

Inspection request (`opendot.temporal.dag-inspect.v1`) has exactly `schema_version`, `mission_id`, `plan_sha256`, `node_id`, `effect_id`, `seed_ref`, `parent_result_ref`, `candidate_result_ref`, `mode`, `expected_revision`, `original_evidence_sha256`, `original_result_sha256`. Mode is `normal` or `reconcile`; revision is an exact positive integer at most 64. Normal mode requires the last two fields null. Reconcile mode requires exact digests that match independently injected trusted origin evidence, never a candidate-supplied expectation. Namespace/run/Workflow ID come from actual SDK context checked against fixed bootstrap binding. Original execution Activity ID is derived separately.

Inspection response (`opendot.temporal.dag-inspection.v1`) has exactly `schema_version`, `effect_id`, `mode`, `expected_revision`, `status`, `reason_code`, `result_ref`, `input_payload_sha256`, `output`, `original_evidence_sha256`. Status is `CONSISTENT_COMPLETED`, `CONSISTENT_REJECTED` or `UNRESOLVED`. `result_ref` is the unchanged candidate reference, not a replacement; input hash is the fixed node input pin; output is the fixed expected int only for CONSISTENT_COMPLETED and null otherwise. Evidence digest is null for normal, or the request digest for reconcile. The Workflow independently validates this whole envelope, exact reference/effect/revision/mode/input/output/evidence fields and allowed status/reason pair before changing acceptance. Inspector never writes CAS, executes the runtime, updates health, creates a receipt, fetches a URI, scans, repairs metadata or schedules anything.

Reconciliation Update (`reconcile_result`, schema `opendot.temporal.dag-reconcile.v1`) has exactly `schema_version`, `node_id`, `effect_id`, `expected_revision`, `candidate_result_ref`, `original_evidence_sha256`, `original_result_sha256`. It has no grants, tokens, origin claims, arbitrary output, Workflow/run override, retry flag or replacement plan. The SDK's Update ID is not user authority and does not enter effect identity. Recorded replay of the same accepted Update reconstructs the same reservation; a distinct stale/duplicate call is refused without inspection.

Update return (`opendot.temporal.dag-reconciliation.v1`) has exactly `schema_version`, `node_id`, `effect_id`, `status`, `reason_code`, `revision`, `mission_status`, `accepted_result_ref`. Status is `ACCEPTED`, `REJECTED`, `UNRESOLVED` or `REFUSED`. The last field is nonnull only for a currently accepted result, never for a canceled/late candidate. Refusal is a normal bounded handler result; malformed payload/unknown node fields are rejected by the validator with a fixed nonretryable `TemporalDagUpdateRejected` and no mutation. Both validator and handler repeat state gating; the validator never mutates or reserves.

## 4. Independent original-origin path

An exact result reference and a hash supplied together in one Update are circular evidence. They are not sufficient for positive reconciliation. In addition to matching actual acquired bytes to candidate reference hash/size, reconciliation requires the exact independently retained original reference and reviewed origin binding.

Trusted bootstrap may inject two optional immutable origin records, named `original_A` and `original_B`, each initially absent. These are fixed, detached immutable worker configuration for this one mission/run, not a mutable lookup service, registry, journal, CAS object or new persistence authority. Each record contains exactly `schema_version`=`opendot.temporal.dag-origin.v1`, `origin_kind`=`trusted-single-operator-synthetic-put-observer`, `capture_phase`=`original_put_return_before_response`, `mission_id`, `plan_sha256`, `node_id`, `effect_id`, `namespace`, `workflow_id`, `workflow_run_id`, `execution_activity_id`, `original_result_ref`. Their separately computed canonical digest is the evidence ID. There is no callback, pathname, URL, timestamp assertion, producer-label shortcut or setter. Inspector reads only its preconfigured record for the fixed A/B node and compares every binding against recorded expected identity and actual SDK domain. A string origin label by itself authenticates nothing.

Controlled positive tests use this order: (1) independently instrument the existing canonical put boundary in the test fixture; (2) after the original canonical `put_json` returns, retain its exact reference/body digest and operation/domain binding in a separate test observer; (3) immediately inject one bounded response-delivery failure; (4) observe the Workflow become UNKNOWN with execute allowance spent; (5) construct/replace the fixed inspector configuration from the already retained observer record, never from the later Update; (6) submit the matching Update; (7) assert acquired body hash equals candidate digest and independently retained original digest and exact original reference equality, A handler count stays exactly one, and only then B may start. Bootstrap replacement must preserve one Activity slot/executor and quiescent lifecycle; actual service qualification is separately gated and NOT_RUN here.

Missing origin record, mutated observer binding, candidate-populated evidence, copied-back Update digest, fabricated alternate result, object-only publication without returned original reference, or unknown provenance remains UNRESOLVED. No positive recovery when no original reference survived is promised. Runtime-derived result hashes are acquired by the independent original observer before the Update, not self-pinned from the candidate. The section 12 fabricated literal vectors test hashing/schema logic only and are explicitly not original live execution evidence.

This proves bounded byte/lineage/domain consistency in a trusted synthetic setup. **External-effect authenticity is NOT_PROVED.** No signature, durable destination effect lookup, external exactly-once effect, scientific validity or general authorization service is invented.

## 5. Exact state/query projection

The zero-argument read-only query is `dag_state`. It returns a detached canonical plain projection with schema `opendot.temporal.dag-state.v1`, at most 16384 bytes, and exactly:

`schema_version`, `profile`, `mission_id`, `plan_sha256`, `seed_ref`, `namespace`, `workflow_id`, `run_id`, `revision`, `mission_status`, `admission_closed`, `cancel_requested`, `deadline_unix_ms`, `nodes`, `resources`, `termination_status`, `external_effect_authenticity`, `scientific_validity`, `device_control_authority`, `independent_review`, `owner_integration`.

`termination_status` is always `NOT_ESTABLISHED`, external authenticity `NOT_PROVED`, science/device false, review/integration NOT_EVALUATED. Revision starts at 1 and increments exactly once per atomic state transition/reservation batch, never on query/refused Update/replay of an already recorded transition, with an upper bound of 64. Deadline is the actual deterministic Workflow start timestamp plus 300 seconds, represented as integer Unix milliseconds. Queries do not call CAS/runtime or mutate state; callers cannot alter live fields by mutating returned dictionaries.

`nodes` has exactly A and B. Each has exactly `effect_id`, `status`, `execute_reserved`, `normal_inspect_reserved`, `reconcile_inspect_reserved`, `inspect_reserved`, `candidate_result_ref`, `accepted_result_ref`, `parent_result_ref`, `reason_code`. Reservation flags are booleans; inspect_reserved is exact int equal to their sum (0–2). A has its effect ID at start and null parent; B has null effect/parent until A acceptance then derives both once. References are null or exact canonical wire references; accepted references never change. Candidate persists through failed inspection. Initial reason is `NOT_ADMITTED` and all flags false. Fixed node states are WAITING, RESERVED, EXECUTING, VERIFYING, ACCEPTED, REJECTED, UNKNOWN, CANCELLED_BEFORE_ADMISSION.

`resources` has exactly `execute_limit`=2, `normal_inspect_limit`=2, `reconcile_inspect_limit`=2, `activity_command_limit`=6, `result_bytes_reserved`=32768, `execute_used`, `normal_inspect_used`, `reconcile_inspect_used`, `activity_commands_used`. Usage starts at zero; increments at reservation before the corresponding scheduling call; counts never decrease, including command failure, unknown, cancellation, rejected result, replay or deadline. Limits/capacity and both result ceilings are reserved at Workflow start. At most two Updates can reserve reconciliation slots overall; refusal consumes none and performs no I/O. Resource caps bound authorized command admission and observed bytes, not physical memory, thread termination, transactional storage, or unbounded malicious request ingress/history traffic.

Mission states are RUNNING, PAUSED_UNKNOWN, COMPLETED, REJECTED, STOPPED_WITH_UNKNOWN. COMPLETED means both fixed results accepted, not science/device acceptance. A rejected/known-refused operation closes mission REJECTED and leaves dependent WAITING with reason DEPENDENCY_REJECTED. Cancellation closes STOPPED_WITH_UNKNOWN even when all nodes were unadmitted, preserving the fact that no process-termination claim is made. An UNKNOWN node closes admission and pauses; an exact positive reconciliation may reopen admission only for the unadmitted dependent, while previous execute reservations remain spent. Cancellation, observation deadline, terminal closure and exhausted failed reconciliation are sticky and cannot reopen.

## 6. State transitions and finite scheduling

Only the following command paths exist, written explicitly for A then B. There is no arbitrary graph walk or externally extendible task loop.

1. WAITING → RESERVED: validate all fixed prerequisites and current cancellation/deadline fence, set execute_reserved and increment execute/activity usage atomically before invoking the SDK scheduling call. B requires A ACCEPTED and the exact accepted original reference. RESERVED → EXECUTING is the scheduling-intent transition; a scheduling exception cannot refund the allowance. An interrupted Workflow-task reconstruction issues the same historical command/Activity ID, not a new logical call.
2. Delivered exact candidate response → VERIFYING: retain candidate and reserve the unique normal inspection before its command. Delivered malformed response or ambiguous execution exception → UNKNOWN/PAUSED_UNKNOWN. Known pre-runtime `TemporalDagAdmissionRejected` or `TemporalDagInputRejected` → REJECTED; other runtime/transport/publication/conversion exceptions are UNKNOWN. A transport-successful Activity with BLOCKED/FAILED/NULL output is not acceptance.
3. Normal inspection CONSISTENT_COMPLETED → ACCEPTED; CONSISTENT_REJECTED → REJECTED; missing/corrupt/foreign/inconsistent/failed/timed-out inspection → UNKNOWN. Each result needs post-await revision/cancel/deadline fencing. No malformed inspector result is trusted as success.
4. Reconcile gate requires current UNKNOWN node, exact effect and current revision, one available reconcile allowance, same current mission/run, no active inspection, no cancellation/terminal/deadline closure, and candidate equal to any already retained candidate. Different candidate is CONFLICTING_CANDIDATE, leaves UNKNOWN, schedules nothing. Handler reserves reconciliation and increments revision before its only read-only command; normal inspection cannot compete with this gate.
5. Reconcile CONSISTENT_COMPLETED at still-current fence → ACCEPTED; only this may unlock unadmitted B. CONSISTENT_REJECTED → REJECTED. UNRESOLVED or inspection exception with the sole reconcile allowance consumed → STOPPED_WITH_UNKNOWN, retaining UNKNOWN and all reservations. A new duplicate cannot consume another allowance. A canceled/deadline/changed revision completion is late evidence and cannot overwrite references or admit B.
6. When paused with no Update, wait only with deterministic Temporal wait/timer until the fixed observation deadline. At deadline close admission, mark unresolved admitted nodes UNKNOWN, mark unadmitted nodes CANCELLED_BEFORE_ADMISSION with reason OBSERVATION_DEADLINE, and end STOPPED_WITH_UNKNOWN. No automatic evidence lookup or replay occurs.

### Literal revision traces and refusal precedence

The normal successful trace is frozen: initialized revision 1; A execution reservation 2 (RESERVED); A command-intent 3 (EXECUTING); candidate retention plus normal-inspection reservation 4 (VERIFYING); A acceptance plus B effect/parent binding 5; B execution reservation 6; B command-intent 7; B candidate plus normal-inspection reservation 8; B acceptance plus mission COMPLETED/admission_closed=true 9. Each listed batch is one increment; setting the accepted result and mission/dependency projection within the same batch adds no increment. Counters are reserved only once before each scheduling call.

For an A execution-unknown case, revisions 1–3 are identical; ambiguity makes A UNKNOWN/mission PAUSED_UNKNOWN/admission_closed=true at revision 4. A valid Update expects 4, reserves reconciliation and changes A to VERIFYING at 5 (mission stays PAUSED_UNKNOWN and admission closed), then verified acceptance plus B binding/opening is 6. B reservation/command-intent/candidate-inspection/acceptance-completion are 7/8/9/10. Normal-inspection-unknown instead occurs at revision 5, then reconcile reservation at 6 and acceptance at 7. Reconciliation UNRESOLVED increments once to UNKNOWN/STOPPED_WITH_UNKNOWN while retaining the consumed allowance. Inspection response failure follows the same unresolved batch. Known rejection, cancellation or observation-deadline closure increments once at the current revision and closes the mission in that batch. Repeating an already latched identical terminal closure, processing a late fenced result, querying state or refusing an Update increments nothing.

For valid-shape Updates, refusal precedence is CANCELLED (including public recorded cancellation), OBSERVATION_DEADLINE, TERMINAL_CLOSED, INSPECTION_BUSY, STALE_REVISION, EFFECT_MISMATCH, STATE_NOT_UNKNOWN, INSPECTION_EXHAUSTED, CONFLICTING_CANDIDATE. A pending inspection is identified before the changed VERIFYING status, so a competing Update returns INSPECTION_BUSY. Malformed/unknown-node input is validator rejection without mutation; the read-only validator may reject an already unavailable gate, while the handler returns REFUSED if a gate closes after validation. Exact SDK validator rejection carries the fixed TemporalDagUpdateRejected type and fixed reason, never raw request content. All handler refusals preserve references/counters/revision, except a newly observed public cancellation or deadline first applies the one synchronous terminal-closure batch.

The production scheduling surface uses the public nonlocal `workflow.start_activity` handle API for the two fixed endpoint names, fixed IDs, current trusted Workflow task queue, RetryPolicy(maximum_attempts=1), fixed 10/60 timeouts, and TRY_CANCEL. One tracked Activity handle exists at a time. Public `workflow.wait_condition` with the remaining deterministic deadline bounds each handle/result wait and paused observation; no wall clock, custom thread, sleep loop, worker lease or polling scheduler. SDK RPC transport retry behavior is separate from these logical one-attempt reservations. Reconstruction/replay consumes recorded commands/results and restores state; it does not run the runtime or CAS. This pure/SDK slice can test decision reconstruction but cannot prove actual server persistence or history replay.

## 7. Cancellation, deadline and Update completion fence

Every awaited Activity result or pause is fenced by revision, cancel flag, terminal state and `workflow.time()`/`workflow.now()` against the fixed recorded deadline. Before every scheduling command and acceptance/Update gate, also read public `workflow.cancellation_reason()`: any value other than None, including the empty string, means cancellation is already recorded and closes admission before another command or acceptance. Do not use truthiness. SDK 1.34.0 records cancellation reason before deferring cancellation of the main task to the next event-loop iteration; catching CancelledError alone leaves a gap. A read-only Update validator rejects a recorded cancellation without mutating state; the main run/handler gate performs synchronous closure before any scheduling or post-await acceptance. Cancellation is not inferred solely from a thrown Activity exception: the main Workflow cancellation path first synchronously sets cancel_requested, admission_closed and terminal state, increments revision, preserves all consumed reservations, marks any unaccepted admitted effect UNKNOWN and unadmitted node CANCELLED_BEFORE_ADMISSION, then requests cancellation of the one tracked Activity handle using the SDK. Cancellation before the first scheduling call admits zero Activities. A handled late valid result after closure is evidence only and cannot reopen B.

### Revision 4: terminal reporting after a bounded drain

Every path returning the final state, including a successful `all_handlers_finished` drain return, rechecks public recorded cancellation and the deterministic observation deadline. A cancellation/deadline newly observed after node completion is a reporting-only closure: preserve all node statuses, accepted/candidate/parent references, per-node RESULT_VERIFIED reasons and every resource counter/reservation. Set admission_closed=true and mission_status=STOPPED_WITH_UNKNOWN; set cancel_requested=true only when public cancellation_reason is not None (including an empty string), otherwise preserve its existing value. Increment revision once only if this changes the projection. Repeating the same closure is idempotent and schedules/reads/retries nothing.

The literal late-terminal traces are normal completion at revision 9 with both nodes ACCEPTED and usage 2/2/0/4, followed by recorded empty-string cancellation during a successful terminal drain: revision 10, STOPPED_WITH_UNKNOWN, cancel_requested=true, same nodes/references/reasons/resources and exactly four commands. With no recorded cancellation but the clock reaching the fixed deadline during that drain, the same reporting-only revision 10 has cancel_requested=false. The internal closure cause is OBSERVATION_DEADLINE; the exact public state schema has no mission-level reason field and is unchanged. This is not a new complete cause-reporting API. In these cases STOPPED_WITH_UNKNOWN describes mission termination/observation uncertainty; already accepted node outcomes remain known.

The final reporting fence also applies before returning when no drain wait is needed, and after a drain timeout/real cancellation before emitting an unresolved failure. It does not extend the 300-second ceiling or create another inspection. Internal/cache-eviction CancelledError with cancellation_reason=None, no local cancellation and positive remaining budget still propagates unchanged during drain, without changing the completed revision-9 projection. The current SDK control-flow distinction is not converted into persisted failure. An already-closed projection can additionally latch a newly observed external cancellation flag once, without refunding or changing accepted nodes.

The main run never reports normal completion while an accepted Update handler remains unfinished. On terminal/cancellation/deadline closure it first applies the synchronous acceptance fence and cancels the tracked handle. It then checks public `workflow.all_handlers_finished()`. If false, it may wait at most `min(1 second, max(0, deadline - workflow.time()))`, with no effect admission. There is no extension to 301 seconds. If the remaining budget is zero or drain expires with handlers unfinished, fail explicitly with nonretryable `DAG_HANDLERS_UNFINISHED` and the bounded STOPPED_WITH_UNKNOWN snapshot in error details. This is an unresolved Workflow failure, not proof a handler/thread/process was terminated or cleanup completed. Do not silently accept the SDK default WARN_AND_ABANDON as success. Repeated cancellation during drain preserves the same closure and reports this explicit unresolved failure if handlers cannot be observed finished.

A Temporal execution/run timeout may terminate the Workflow before its final report/drain event is recorded. That transport outcome remains UNKNOWN; it does not authorize another execution or establish physical termination. The in-process callable cannot be killed by these adapters. No process-kill/descendant/proc/namespace/native lifetime or cleanup probe is included.

## 8. Stable finite reason/failure vocabulary

Initial/transitional reasons are NOT_ADMITTED, EXECUTE_RESERVED, EXECUTING, RESULT_CANDIDATE, INSPECT_RESERVED, RECONCILE_RESERVED. Positive/rejected inspection reasons are RESULT_VERIFIED, TOOL_REJECTED, OUTPUT_REJECTED. Unresolved reasons are RESULT_UNAVAILABLE, RESULT_INVALID, ORIGIN_UNAVAILABLE, ORIGIN_MISMATCH, LIVENESS_UNKNOWN, INSPECTION_FAILED, EXECUTION_UNKNOWN, RESPONSE_INVALID. Lifecycle reasons are CANCELLED, OBSERVATION_DEADLINE, DEPENDENCY_REJECTED, INSPECTION_EXHAUSTED, HANDLERS_UNFINISHED. Update refusal reasons are STATE_NOT_UNKNOWN, STALE_REVISION, EFFECT_MISMATCH, CONFLICTING_CANDIDATE, INSPECTION_BUSY, INSPECTION_EXHAUSTED, CANCELLED, OBSERVATION_DEADLINE, TERMINAL_CLOSED.

No raw exception text, file path, token or arbitrary detail crosses the wire. Nonretryable fixed Activity failures use only category and `{phase, code}`: TemporalDagAdmissionRejected/admission/ADMISSION_REFUSED; TemporalDagInputRejected/input/INPUT_REFUSED; TemporalDagResultEncodingFailed/result_encoding/RESULT_UNREPRESENTABLE; TemporalDagResultStoreFailed/result_store/PUBLICATION_UNCONFIRMED; TemporalDagResultEncodingFailed/response_encoding/RESPONSE_UNREPRESENTABLE. Runtime control exceptions propagate unmodified and remain uncertain to the Workflow. Inspector ordinarily returns bounded UNRESOLVED for acquired-object/receipt/origin failure; its SDK/domain/request admission failures occur before reads.

## 9. Resources and authority

Exactly one Workflow, two execute allowances, one original execution and at most one normal plus one reconciliation inspection per node: at most six Activity commands. One externally configured Activity slot and one matching executor thread, one Workflow worker, Workflow/Activity retries limited to one attempt, runtime attempt_limit=1 and zero application retries. Each Activity retains 10/60-second deadlines. Seed read 256 bytes; original result read/write 16384; two result ceilings reserved up front (32768 total); request/response 4096; state projection 16384; fixed Workflow observation/run/execution timeout 300 seconds. Terminal drain uses at most one second already inside that budget. B parent validation adds a bounded read, not another command or execution.

Result/body caps are checked before canonical put; request/response caps are post-decode plain-object bounds and do not prove network converter pre-acquisition memory bounds. CAS object/metadata writes are not transactional. Slot/executor configuration does not prove timed-out underlying in-process work stopped. No refund or fresh execution follows timeout, cancellation, object absence, failed publication or unknown acknowledgment.

The tool is READ_ONLY synthetic. Every newly admitted A/B runtime call uses the current worker's configured `synthetic:read` grant, current declaration and original deny-only guard, with approval_token None. A prior receipt, accepted A, or origin evidence never grants B authority. Missing/revoked grants yield a canonical blocked result; a changed registration blocks before dispatch. Approval/token/grant/authority fields in any incoming protocol are rejected. This is not an issuer/expiry/revocation/spend/remote-approval service.

## 10. Frozen negative and positive acceptance oracles

No tests were executed to prepare this design. Implementation acceptance must use existing pytest and installed SDK 1.34.0 only, finite plain fixtures, ActivityEnvironment/default converter and already completed/canceled controlled futures. Counts must include every scheduling operation, runtime execute, actual handler call, canonical CAS read and put, state revision and consumed resource allowance. Test collection must be inspected before running.

- Literal plan/source/declaration/seed/A-input/B-input/A-output/B-output/A-effect/B-effect/original-body/origin pins independently match the frozen vectors, including B's dependence on the exact frozen A original digest; no expectations imported/computed from candidate constants alone
- All start/step/inspect/update shapes, unknown/authority fields, extra/missing keys, type subclasses, bool/float integers, invalid refs/size/hash/URI/source order, changed plan/node/parent/effect/domain/queue/actual run/Activity ID/type, missing policy/attempt 2 and wrong timeouts refuse at their specified pre-I/O/pre-command boundary
- Normal A→B success: execute counts A=1/B=1, actual handler A=1/B=1, outputs 5/6; exactly four commands (execute A, inspect A, execute B, inspect B); two original result puts; all six allowances/32768 bytes reserved up front and usage exactly 2/2/0/4
- A BLOCKED/FAILED/NULL/wrong-output result never admits B; malformed response, liveness, missing/corrupt object, wrong input/output receipt hashes, forged observation, foreign original run/Activity/effect/seed/parent, inspection exception remain blocked without another execute
- Before-command decision reconstruction uses the same first Activity ID; replayed recorded schedule/result choices reproduce identical reservations, accepted refs and B command, with no new logical A. This finite fake-runtime oracle is not genuine history-replay evidence
- Original canonical put observer captures reference independently, injected post-publication failure yields UNKNOWN, immutable origin config is created before candidate Update, valid original reconciliation lets B run while A execute/handler remain 1. Candidate-only/absent/mutated origin, rehashed replacement bytes or copied-back Update pin cannot pass, including an internally self-consistent wrong-output document
- Normal inspection and reconciliation use distinct fixed Activity IDs; original execution body still binds the execute ID. Foreign inspector domain refuses before CAS; positive origin mode cannot fall back to normal mode
- Stale/duplicate/conflicting/malformed Updates, concurrent Update admission, and Update during normal verification perform zero extra reads/commands; their reservations/revisions/refusal results are exact. One normal and one reconcile allowance per node, no seventh command, no accepted-result replacement
- Cancellation already recorded as an empty public cancellation reason while local cancel_requested is still false gives zero commands/acceptances; the validator remains read-only, and the main/handler gate latches closure synchronously. Cancellation before admission gives zero commands; cancellation racing normal return and reconciliation closes synchronously, late acceptance does not reopen B, Update handlers drain or explicitly fail within remaining deadline; no-budget and drain-expiry cases yield DAG_HANDLERS_UNFINISHED with STOPPED_WITH_UNKNOWN. Requesting cancellation never asserts thread/process termination
- Successful terminal drain returning alongside recorded empty-string cancellation or the fixed deadline applies the exact reporting-only revision-9-to-10 transition, preserves accepted node outcomes/reasons/refs and 2/2/0/4 usage, and repeated observation adds no revision, command or read. Internal drain cancellation with no recorded cancel still propagates unchanged.
- Observation deadline expires with or without missing original evidence, preserves all usage and closes admission; no accepted late result/refund/retry. Query returns a detached bounded state and cannot mutate it. SDK timeout is UNKNOWN even if no final snapshot is recorded
- B's fresh grant/registration/guard refusal cannot be bypassed by accepted A, historical receipt/origin or a token. Existing v1 tests/semantics remain unchanged; canonical owner hashes/default imports/dependency pin gates still pass

## 11. Authorized paths and separately gated service work

Exactly seven source paths are permitted for this first slice:

1. AGENTS.md
2. docs/decisions/008-fixed-dependent-temporal-recovery.md
3. src/opendot_engineering/adapters/temporal_workflow.py
4. src/opendot_engineering/adapters/temporal_activity.py
5. tests/test_temporal_dag_recovery.py
6. tests/test_temporal_workflow_contract.py
7. tests/test_temporal_transport_owner_boundaries.py

Only the first two change during design preparation. All executable adapter/test changes await independent review and root go-ahead. Preserve exact ToolRuntime `7c5011e02b2cf07e5f15ad7854905ce0738271e167b873bad9256a8ed169199c`, ArtifactStore `4606b7b11a81044267b30fee332d9b6fd6540d862726a9579655ee27c7d9a883`, contracts `9462415baf84668825ad2c8cfc3f4f3df68332f65d1f1f4b301fbf01cf8537ca`, and source-audit `c94737305b1e5a80453541ce890bde4fcb700a0074e32344fe839b237374bfa7` bytes. Retain historical evidence, guides, assets and all other paths.

No hosted wiring or actual server change occurs in this slice. Later separate approval may extend only the existing six integration paths identified in the design assessment, reuse its checked acquisition/lifecycle/verifier, SDK 1.34.0/CLI 1.9.1/server 1.32.0 and ten-minute read-only hosted job. Future real histories, original CAS/ref pins and independent counts must establish actual fixed-DAG continuation, graceful observed-quiescent worker replacement and recorded-history replay without Activity execution. Finite injected post-publication failure is sufficient only for that narrow synthetic byte-reconciliation claim. It does not establish real kill/crash/lost-network-ack semantics, multi-host availability, stale-process fencing, external authenticity or issue #7 completion. Those fields remain NOT_EVALUATED.

No local service/CLI/server launch/acquisition, network or DNS experiment, installation, hanging handler, process/lifetime probe, Gmsh/native call, model/provider/Codex/cloud-task/external-agent/private input, dynamic mission or favorable-result rerun is allowed. Existing a3/a4/a5 assets remain immutable. Root's independently verified base is commit `77b4f73437896c9575056c2d4de40c394c014e8d`, tree `f0c5dede1dd539235efdf4eb5a1e1099d3dbc96b`; this design adds no remote-state claim of its own.

## 12. Independent literal contract fixtures

The following canonical plan and complete original-body/origin fixtures were constructed before executable adapter/test edits, using only stdlib encoding/hash calculations outside the candidate modules. These fabricated vectors are NOT_EXECUTED and NOT live-proof evidence. Their literal expected hashes, rather than a hash recomputed from the implementation under test, are the test oracle. The matching dynamic integration oracle must capture actual original result evidence independently before any Update as section 4 requires.

### Canonical plan bytes (no trailing newline)

```json
{"b_transform":{"left":"accepted_A.output","return_null":false,"right":1},"edges":[["A","B"]],"handler_source_encoding":"ast-source-segments:_validate_payload,bounded_sum,bounded_sum_valid;join=LF-LF;final=LF","handler_source_sha256":"a97dadac88bed7b09d2398516617216cb865ae97db411c12b72de01d7a78d1cb","limits":{"accepted_updates":2,"activity_attempts":1,"activity_commands":6,"activity_executor_threads":1,"activity_slots":1,"application_retries":0,"execute_per_node":1,"nodes":2,"normal_inspect_per_node":1,"observation_seconds":300,"reconcile_inspect_per_node":1,"request_response_bytes":4096,"result_bytes":16384,"result_bytes_reserved":32768,"schedule_to_close_seconds":60,"seed_bytes":256,"start_to_close_seconds":10,"state_bytes":16384,"terminal_drain_seconds_max":1,"tool_attempts":1,"workflow_attempts":1,"workflows":1},"profile":"synthetic.dependent_sum.v1","registration_sha256":"5f2b1e81954530f31c7d2c83b9c582883b8391190ebe13b69b8bf91f044cb0c3","schema_version":"opendot.temporal.dag-plan.v1","schemas":{"effect":"opendot.effect.v1","inspect":"opendot.temporal.dag-inspect.v1","inspection":"opendot.temporal.dag-inspection.v1","origin":"opendot.temporal.dag-origin.v1","plan":"opendot.temporal.dag-plan.v1","reconcile":"opendot.temporal.dag-reconcile.v1","reconciliation":"opendot.temporal.dag-reconciliation.v1","result":"opendot.temporal.dag-result.v1","start":"opendot.temporal.dag-start.v1","state":"opendot.temporal.dag-state.v1","step":"opendot.temporal.dag-step.v1","step_response":"opendot.temporal.dag-step-response.v1"},"seed_producer":"opendot.temporal.dag-seed.v1","seed_sha256":"897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02","seed_task_id":"seed","tasks":[{"input_payload_sha256":"897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02","node_id":"A","output_sha256":"ef2d127de37b942baad06145e54b0c619a1f22327b2ebbcfbec78f5564afe39d","parent":null},{"input_payload_sha256":"6d23a7a66975efd35356848b1f69b848e99c3c76dc5a3740e35328d41c05440a","node_id":"B","output_sha256":"e7f6c011776e8db7cd330b54174fd76f7d0216b612387a5ffcfb81e6f0919683","parent":"A"}],"tool_id":"synthetic.bounded_sum"}
```

### Literal vector manifest and complete original fixtures

```json
{
  "fixture_mission_id": "frozen-example",
  "fixture_namespace": "synthetic",
  "fixture_workflow_id": "opendot-dag2-frozen-example-19843079a5da00754ec1b5399962c33874b907eb4d0d6fcf55cd3be2f4dffb63",
  "fixture_workflow_run_id": "11111111-1111-4111-8111-111111111111",
  "nonpositive_output_pins": {
    "null": "74234e98afe7498fb5daf1f36ac2d78acc339464f950703b8c019892f982b90b"
  },
  "plan_sha256": "19843079a5da00754ec1b5399962c33874b907eb4d0d6fcf55cd3be2f4dffb63",
  "seed_ref": {
    "artifact_id": "sha256:897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02",
    "integrity_verified": false,
    "mime_type": "application/json",
    "producer": "opendot.temporal.dag-seed.v1",
    "schema_version": "1.0.0",
    "sha256": "897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02",
    "size_bytes": 40,
    "source_refs": [],
    "task_id": "seed",
    "uri": "artifact://sha256/897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02"
  },
  "vectors": {
    "A": {
      "effect_id": "sha256:85b56651dc0114baa5ad1068d538337dffa6848ecfb892e782f53006d9f5ba24",
      "input_bytes": "{\"left\":2,\"return_null\":false,\"right\":3}",
      "input_sha256": "897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02",
      "origin_evidence_sha256": "980cc0c21a3d089c96833c9a7ba0fa479d470a741c4be4ef8456edf7670013ab",
      "original_origin_record": {
        "capture_phase": "original_put_return_before_response",
        "effect_id": "sha256:85b56651dc0114baa5ad1068d538337dffa6848ecfb892e782f53006d9f5ba24",
        "execution_activity_id": "dag2-execute-85b56651dc0114baa5ad1068d538337dffa6848ecfb892e782f53006d9f5ba24",
        "mission_id": "frozen-example",
        "namespace": "synthetic",
        "node_id": "A",
        "origin_kind": "trusted-single-operator-synthetic-put-observer",
        "original_result_ref": {
          "artifact_id": "sha256:ac56ef93531558b0a770c283d0c3ecc1c1b1795468ffe7150065819e5178a07a",
          "integrity_verified": false,
          "mime_type": "application/json",
          "producer": "opendot.temporal.dag-result.v1",
          "schema_version": "1.0.0",
          "sha256": "ac56ef93531558b0a770c283d0c3ecc1c1b1795468ffe7150065819e5178a07a",
          "size_bytes": 2223,
          "source_refs": [
            "sha256:897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02"
          ],
          "task_id": "85b56651dc0114baa5ad1068d538337dffa6848ecfb892e782f53006d9f5ba24",
          "uri": "artifact://sha256/ac56ef93531558b0a770c283d0c3ecc1c1b1795468ffe7150065819e5178a07a"
        },
        "plan_sha256": "19843079a5da00754ec1b5399962c33874b907eb4d0d6fcf55cd3be2f4dffb63",
        "schema_version": "opendot.temporal.dag-origin.v1",
        "workflow_id": "opendot-dag2-frozen-example-19843079a5da00754ec1b5399962c33874b907eb4d0d6fcf55cd3be2f4dffb63",
        "workflow_run_id": "11111111-1111-4111-8111-111111111111"
      },
      "original_result_body": {
        "activity_id": "dag2-execute-85b56651dc0114baa5ad1068d538337dffa6848ecfb892e782f53006d9f5ba24",
        "device_control_authority": false,
        "effect_id": "sha256:85b56651dc0114baa5ad1068d538337dffa6848ecfb892e782f53006d9f5ba24",
        "independent_review": "NOT_EVALUATED",
        "input_payload_sha256": "897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02",
        "mission_id": "frozen-example",
        "namespace": "synthetic",
        "node_id": "A",
        "observation_provenance": "serialized_runtime_report_not_live_proof",
        "output": 5,
        "owner_integration": "NOT_EVALUATED",
        "parent_result_ref": null,
        "plan_sha256": "19843079a5da00754ec1b5399962c33874b907eb4d0d6fcf55cd3be2f4dffb63",
        "profile": "synthetic.dependent_sum.v1",
        "receipt_report": {
          "attempts": 1,
          "breaker_state": "closed",
          "call_id": "aaaaaaaaaaaaaaaaaaaaaaaa",
          "error_type": null,
          "execution_liveness": {},
          "execution_observation": {
            "dispatcher_pid": 101,
            "execution_id": "cccccccccccccccccccccccccccccccc",
            "execution_kind": "in_process",
            "input_sha256": "897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02",
            "read_only_declared": true,
            "registration_sha256": "5f2b1e81954530f31c7d2c83b9c582883b8391190ebe13b69b8bf91f044cb0c3",
            "review_target_sha256": null,
            "worker_pid": 101
          },
          "input_hash": "897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02",
          "latency_s": 0.0,
          "output_hash": "ef2d127de37b942baad06145e54b0c619a1f22327b2ebbcfbec78f5564afe39d",
          "semantic_valid": true,
          "status": "COMPLETED",
          "tool_id": "synthetic.bounded_sum",
          "tool_version": "1"
        },
        "registration_sha256": "5f2b1e81954530f31c7d2c83b9c582883b8391190ebe13b69b8bf91f044cb0c3",
        "schema_version": "opendot.temporal.dag-result.v1",
        "scientific_validity": false,
        "seed_ref": {
          "artifact_id": "sha256:897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02",
          "integrity_verified": false,
          "mime_type": "application/json",
          "producer": "opendot.temporal.dag-seed.v1",
          "schema_version": "1.0.0",
          "sha256": "897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02",
          "size_bytes": 40,
          "source_refs": [],
          "task_id": "seed",
          "uri": "artifact://sha256/897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02"
        },
        "workflow_id": "opendot-dag2-frozen-example-19843079a5da00754ec1b5399962c33874b907eb4d0d6fcf55cd3be2f4dffb63",
        "workflow_run_id": "11111111-1111-4111-8111-111111111111"
      },
      "original_result_ref": {
        "artifact_id": "sha256:ac56ef93531558b0a770c283d0c3ecc1c1b1795468ffe7150065819e5178a07a",
        "integrity_verified": false,
        "mime_type": "application/json",
        "producer": "opendot.temporal.dag-result.v1",
        "schema_version": "1.0.0",
        "sha256": "ac56ef93531558b0a770c283d0c3ecc1c1b1795468ffe7150065819e5178a07a",
        "size_bytes": 2223,
        "source_refs": [
          "sha256:897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02"
        ],
        "task_id": "85b56651dc0114baa5ad1068d538337dffa6848ecfb892e782f53006d9f5ba24",
        "uri": "artifact://sha256/ac56ef93531558b0a770c283d0c3ecc1c1b1795468ffe7150065819e5178a07a"
      },
      "output_bytes": "5",
      "output_sha256": "ef2d127de37b942baad06145e54b0c619a1f22327b2ebbcfbec78f5564afe39d"
    },
    "B": {
      "effect_id": "sha256:639ecb03da5d305b5feda86c6b0ac26b446ce803753a11866b206c68f671e77d",
      "input_bytes": "{\"left\":5,\"return_null\":false,\"right\":1}",
      "input_sha256": "6d23a7a66975efd35356848b1f69b848e99c3c76dc5a3740e35328d41c05440a",
      "origin_evidence_sha256": "4706934b1088a939b19c363de42b0ea9567a9fa07d762c042465486a543dcd0e",
      "original_origin_record": {
        "capture_phase": "original_put_return_before_response",
        "effect_id": "sha256:639ecb03da5d305b5feda86c6b0ac26b446ce803753a11866b206c68f671e77d",
        "execution_activity_id": "dag2-execute-639ecb03da5d305b5feda86c6b0ac26b446ce803753a11866b206c68f671e77d",
        "mission_id": "frozen-example",
        "namespace": "synthetic",
        "node_id": "B",
        "origin_kind": "trusted-single-operator-synthetic-put-observer",
        "original_result_ref": {
          "artifact_id": "sha256:adb5d50840b20d03149b27c6867f963736ae54a904658f6239e7e37666489204",
          "integrity_verified": false,
          "mime_type": "application/json",
          "producer": "opendot.temporal.dag-result.v1",
          "schema_version": "1.0.0",
          "sha256": "adb5d50840b20d03149b27c6867f963736ae54a904658f6239e7e37666489204",
          "size_bytes": 2787,
          "source_refs": [
            "sha256:897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02",
            "sha256:ac56ef93531558b0a770c283d0c3ecc1c1b1795468ffe7150065819e5178a07a"
          ],
          "task_id": "639ecb03da5d305b5feda86c6b0ac26b446ce803753a11866b206c68f671e77d",
          "uri": "artifact://sha256/adb5d50840b20d03149b27c6867f963736ae54a904658f6239e7e37666489204"
        },
        "plan_sha256": "19843079a5da00754ec1b5399962c33874b907eb4d0d6fcf55cd3be2f4dffb63",
        "schema_version": "opendot.temporal.dag-origin.v1",
        "workflow_id": "opendot-dag2-frozen-example-19843079a5da00754ec1b5399962c33874b907eb4d0d6fcf55cd3be2f4dffb63",
        "workflow_run_id": "11111111-1111-4111-8111-111111111111"
      },
      "original_result_body": {
        "activity_id": "dag2-execute-639ecb03da5d305b5feda86c6b0ac26b446ce803753a11866b206c68f671e77d",
        "device_control_authority": false,
        "effect_id": "sha256:639ecb03da5d305b5feda86c6b0ac26b446ce803753a11866b206c68f671e77d",
        "independent_review": "NOT_EVALUATED",
        "input_payload_sha256": "6d23a7a66975efd35356848b1f69b848e99c3c76dc5a3740e35328d41c05440a",
        "mission_id": "frozen-example",
        "namespace": "synthetic",
        "node_id": "B",
        "observation_provenance": "serialized_runtime_report_not_live_proof",
        "output": 6,
        "owner_integration": "NOT_EVALUATED",
        "parent_result_ref": {
          "artifact_id": "sha256:ac56ef93531558b0a770c283d0c3ecc1c1b1795468ffe7150065819e5178a07a",
          "integrity_verified": false,
          "mime_type": "application/json",
          "producer": "opendot.temporal.dag-result.v1",
          "schema_version": "1.0.0",
          "sha256": "ac56ef93531558b0a770c283d0c3ecc1c1b1795468ffe7150065819e5178a07a",
          "size_bytes": 2223,
          "source_refs": [
            "sha256:897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02"
          ],
          "task_id": "85b56651dc0114baa5ad1068d538337dffa6848ecfb892e782f53006d9f5ba24",
          "uri": "artifact://sha256/ac56ef93531558b0a770c283d0c3ecc1c1b1795468ffe7150065819e5178a07a"
        },
        "plan_sha256": "19843079a5da00754ec1b5399962c33874b907eb4d0d6fcf55cd3be2f4dffb63",
        "profile": "synthetic.dependent_sum.v1",
        "receipt_report": {
          "attempts": 1,
          "breaker_state": "closed",
          "call_id": "bbbbbbbbbbbbbbbbbbbbbbbb",
          "error_type": null,
          "execution_liveness": {},
          "execution_observation": {
            "dispatcher_pid": 102,
            "execution_id": "dddddddddddddddddddddddddddddddd",
            "execution_kind": "in_process",
            "input_sha256": "6d23a7a66975efd35356848b1f69b848e99c3c76dc5a3740e35328d41c05440a",
            "read_only_declared": true,
            "registration_sha256": "5f2b1e81954530f31c7d2c83b9c582883b8391190ebe13b69b8bf91f044cb0c3",
            "review_target_sha256": null,
            "worker_pid": 102
          },
          "input_hash": "6d23a7a66975efd35356848b1f69b848e99c3c76dc5a3740e35328d41c05440a",
          "latency_s": 0.0,
          "output_hash": "e7f6c011776e8db7cd330b54174fd76f7d0216b612387a5ffcfb81e6f0919683",
          "semantic_valid": true,
          "status": "COMPLETED",
          "tool_id": "synthetic.bounded_sum",
          "tool_version": "1"
        },
        "registration_sha256": "5f2b1e81954530f31c7d2c83b9c582883b8391190ebe13b69b8bf91f044cb0c3",
        "schema_version": "opendot.temporal.dag-result.v1",
        "scientific_validity": false,
        "seed_ref": {
          "artifact_id": "sha256:897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02",
          "integrity_verified": false,
          "mime_type": "application/json",
          "producer": "opendot.temporal.dag-seed.v1",
          "schema_version": "1.0.0",
          "sha256": "897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02",
          "size_bytes": 40,
          "source_refs": [],
          "task_id": "seed",
          "uri": "artifact://sha256/897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02"
        },
        "workflow_id": "opendot-dag2-frozen-example-19843079a5da00754ec1b5399962c33874b907eb4d0d6fcf55cd3be2f4dffb63",
        "workflow_run_id": "11111111-1111-4111-8111-111111111111"
      },
      "original_result_ref": {
        "artifact_id": "sha256:adb5d50840b20d03149b27c6867f963736ae54a904658f6239e7e37666489204",
        "integrity_verified": false,
        "mime_type": "application/json",
        "producer": "opendot.temporal.dag-result.v1",
        "schema_version": "1.0.0",
        "sha256": "adb5d50840b20d03149b27c6867f963736ae54a904658f6239e7e37666489204",
        "size_bytes": 2787,
        "source_refs": [
          "sha256:897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02",
          "sha256:ac56ef93531558b0a770c283d0c3ecc1c1b1795468ffe7150065819e5178a07a"
        ],
        "task_id": "639ecb03da5d305b5feda86c6b0ac26b446ce803753a11866b206c68f671e77d",
        "uri": "artifact://sha256/adb5d50840b20d03149b27c6867f963736ae54a904658f6239e7e37666489204"
      },
      "output_bytes": "6",
      "output_sha256": "e7f6c011776e8db7cd330b54174fd76f7d0216b612387a5ffcfb81e6f0919683"
    }
  }
}
```
