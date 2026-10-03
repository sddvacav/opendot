# Finite synthetic batch: preparation protocol

**Current status pointer (2026-10-02).** This page preserves dated preparation
checkpoints. Later source-only live-batch and retained-public-projection results
are summarized in [the later qualification record](temporal-reference-transport.md#later-source-only-200-job-qualification-2026-10-02).
They do not change the frozen a3 assets. The retained run reports 200 accepted
synthetic jobs, Activity interval peak 3 and handler interval peak 1; handler
concurrency remains NOT_DEMONSTRATED, and original execution evidence is not
independently replayable from the projection. These results do not demonstrate
200 agents, CPU parallelism, multi-host operation or scientific acceptance.

**Historical preparation checkpoint.**
Decision date: 2026-10-02. LOCAL PREPARATION ONLY; hosted batch NOT RUN.
Base: main 26e301795bcd6bf2ad26274e25fed7c8fc2106a8, tree
6f2f8bdad9ab1dc7ff1c311fe3c581a5eec71634.

## Frozen expected verdicts (before implementation)

- Exactly 200 distinct ordered jobs batch-000 through batch-199 are valid. Inputs
  use left=i, right=199-i, return_null=false, giving equal sums of 199 but unique
  input references. Cohorts a/b alternate, 100 each. Any empty, malformed,
  reordered, duplicate, missing, extra or 201-job plan is refused before RPC or
  worker construction. Payload and result allowances are 256 and 16,384 bytes.
- Reserve the entire 200-attempt / 3,276,800-result-payload-byte allowance first.
  Each RPC consumes one reservation before entering its callback. No completion
  means exactly 16 calls regardless of repeated observation steps. A validated
  known terminal frees one slot; duplicate or unknown observations free none.
- Unknown acknowledgment, RPC exception after entry, timeout, transport loss,
  runtime exception, reconciliation_required or observer failure irrevocably
  stops future submission. Late success may account for known work but cannot
  erase the latch, refund attempts, retry or turn the run into a PASS.
- Exact external configuration: Activity slots/executor=8, workflow task cap=1,
  workflow cache=0, each poller=1, eager execution disabled, attempt=1 and exact
  10/60-second Activity deadlines. Missing/mismatched fields refuse preflight.
- Pure traces use contiguous sequence numbers and nondecreasing integer elapsed
  microseconds. Unique Activity begin/end and execute/handler enter/return events
  reconstruct occupancy. Sequential 200-job PASS has peak=1; controlled overlap
  PASS can have peak=2..8. Ninth concurrent Activity, repeated exits, missing
  entry, reused invocation, nonmonotonic order, duplicate execution, retry,
  reset/continue-as-new or unbalanced final trace never passes.
- Every accepted terminal links original job/input/Workflow/run/Activity/attempt
  to one original outcome, receipt and result reference. All sums intentionally
  match; exchanging result references still fails. Transport completion never
  promotes BLOCKED, FAILED, invalid semantics or uncertain liveness to success.
- Trace has at most 4,096 rows and 1,024 encoded bytes per row. Every result
  projection and emitted summary is strictly allowlisted; summary cap=64 KiB.
  Overlarge rows/files, unexpected text/path/token fields, wrong source/revision,
  altered protected owners, missing jobs and orphan outputs never pass. No
  truncation converts evidence failure into success.
- Queue waits, Activity durations and cohort completion are calculated only from
  the explicitly synthetic fixture clock; they are not real measurements. A
  missing/hung cohort fails with its missing/outstanding counts retained. No
  FIFO, fairness, queue-wait ceiling or speedup is inferred.
- The old seven-node manifest, schemas and Runner remain independent and exact in
  semantics. The new manifest selects only preparation tests. It cannot trigger
  service execution or substitute fixture evidence for hosted qualification.

## Ownership and limits

The admission component is finite test-bootstrap bookkeeping, never a production
API. Temporal remains the only scheduler; the canonical runtime/store and both
adapters remain byte-for-byte preserved. Pure helpers build/check fixed factory
arguments without importing the SDK or starting workers. This preparation does
not wire the component into Runner, a workflow, CLI or service.

The strict verifier uses a separate batch v1 schema labeled FABRICATED_UNIT_DATA;
its PASS means fixture invariants only. It cannot produce real-server acceptance.
A later approved candidate must gather received SDK metadata, private original
result/CAS validation, history links, source bindings and observed quiescence/
normal worker/server shutdown before claiming actual delivery. No service-ready
receipt or cleanup fact is fabricated here.

Configured eight slots and an observed peak are different quantities. Eight
outer Activity threads plus nested callable threads are not eight total threads.
Counts and payload ceilings are not memory/RSS/disk quotas or cost budgets.
Unknown execution means no hard thread/lifetime bound. No agent/model inference
count, multi-host, scientific acceptance, recovery, cancellation, exactly-once,
production backpressure or throughput claim is made.

## Implemented preparation interface and evidence boundary

The original expected-verdict section was frozen before implementation (initial
protocol SHA-256 `11068459cd1681891591df2c0026db4fbe7b5c6131252b835a64b3d08613f398`).
The initial separate preparation manifest selected 18 stdlib-unittest methods,
also collectable by pytest, in the two existing test files. The local JUnit
identity integration below extends that explicit selection to 23 methods. Each contains additional
fixed subtest mutations; these are not claimed as extra test nodes.

`BatchAdmission` validates/materializes the entire exact plan and profile at
construction. `submit_next` reserves the job/attempt/outstanding slot before its
single callback. It never constructs a task/coroutine queue. `acknowledge` binds
one fixed Workflow/run; `record_outcome` stores the independently supplied original
fixture projection without releasing capacity; `observe_terminal` must match
that original and its semantic verdict before releasing a slot once. Missing,
duplicate or mismatched observations latch admission closed. `mark_uncertain`
preserves the reservation and a fixed reason. Late positive observations may
reduce accounted outstanding work but never clear uncertainty or retry admission.
Snapshots are copies, and callback mutation cannot change the reserved fixture.

Worker/executor argument builders have no default real factories, SDK import,
client, worker lifecycle or service entrypoint. Tests inspect calls to their own
plain fake factories. Workflow cache/task/poller and Activity slot/poller fields
are explicit. This demonstrates correct argument preparation, not SDK capacity.

The new verifier takes exactly schema_version, evidence_kind, revision,
source_sha256, plan, profile, events and outcomes. Its only evidence_kind is
FABRICATED_UNIT_DATA. It independently reconstructs state; declared peaks or
free-text annotations are not accepted. Every event contains exactly sequence,
elapsed_us, job_id, kind and details. The allowed event kinds are reserve, ack,
activity_begin, execute_enter, handler_enter, handler_return, activity_end,
terminal and uncertain, each with its own exact details schema. Original outcome
projections are supplied separately and terminal references/receipts must match
those originals. Receipt/result reuse and orphan projections are rejected.

All original projections are synthetic input to a fixture test. A checksum or
projection is not independent proof of a live receipt or CAS validation. This
preparation deliberately provides no hosted acceptance path, original-result
reader, metadata extractor, cleanup assertion or publication command.

Time is an integer synthetic observation clock. For internal consistency,
handler enter-to-return must be at most one second and Activity begin-to-end at
most ten seconds. A conservative reservation-to-validated-terminal limit of
sixty seconds is also required; that larger enclosing interval is a preparation
criterion, not a claim to have observed Temporal's actual Activity scheduling
time. It includes client/Workflow delay and does not redefine the unchanged
schedule-to-close setting. Queue wait is reservation-to-observed-Activity-entry,
not a Temporal-server-only queue measurement. Durations, counts and cohort
completion remain explicitly synthetic; no measured performance is reported.

Positive traces require exact cardinality and balanced observations. A structurally
valid incomplete or uncertain trace returns FAIL with outstanding, unsubmitted,
uncertain and per-cohort missing counts. Malformed/oversize/private/source-mismatched
evidence raises only a fixed verifier code. The new schema does not weaken any
old seven-case validator, CLI acceptance or node selection.

## Initial eight-path verification disposition

**Historical preparation checkpoint, before hosted wiring.**

The exact 18-method preparation selection ran with Python 3.12.14's stdlib
unittest runner by compiling only each self-contained appended batch section.
No pytest substitute or fake pytest module was used. The inherited pytest cases
were not executed because pytest is unavailable in this environment. No package
installation, native process/service, Temporal SDK execution, hosted dispatch,
remote write or private input was used. The historical seven-case gate is
unchanged and has not been rerun for this preparation candidate.

Hosted wiring, SDK integration, actual received-metadata/result extraction and
end-to-end 200-job delivery remain unimplemented and NOT RUN. They require a
separate exact-candidate decision and cannot be inferred from these fixture tests.

Integration blocker: the existing hosted workflow collects these full test files
and checks a pinned expected collection count. The added preparation methods may
therefore change that collection even though the new manifest is separate. The
workflow is intentionally unchanged in this local eight-path candidate. Before
any PR/publication, obtain an independent actual pytest collection for the exact
integrated source, then explicitly review the corresponding workflow count change.
Do not assume a previous total plus eighteen, or treat this local candidate as
ready to publish. No workflow count or hosted-scope change is authorized here.


## Qualified local JUnit identity integration

The initial source's locked pytest qualification subsequently collected and
passed 836 six-file nodes and the 18-node preparation subset. This exposed a
separate workflow defect: reconstructing test IDs by replacing every JUnit
classname dot with a slash misidentified the 18 unittest-class methods. A count
change alone would still fail; the earlier collection blocker was substantive.

The approved local follow-on adds the workflow as a ninth changed path. It calls
`verify_collected_unit_junit` in the existing verifier. The helper builds an
explicit one-to-one mapping from known collected file/module, optional class
scopes and exact test/parameter names to JUnit `(classname, name)` pairs. It does
not infer class boundaries from dotted JUnit text. Literal parameter dots,
slashes and `::` are preserved. Ambiguous projections, duplicates, missing or
extra nodes, wrong scope and malformed identities fail closed. Existing large
parameter IDs are retained exactly under a 128 KiB per-node and 2 MiB aggregate
identity bound. The bounded shared JUnit parser is reused unchanged.

Five focused test methods cover module/class/nested-class identities, exact
parameter IDs, mapping collisions, duplicate-replacing-missing cases, wrong
scope/names, failures/errors/skips, malformed XML status and identity size bounds.
The helper returns real per-node outcomes; the workflow still independently
requires zero collection/test exit codes, exact expected/unique collected and
executed counts, exact matched node sets and all passed with no failure/error/skip.
No aggregate JUnit count, fabricated PASS or dropped node can satisfy that gate.

Fresh actual qualification with the already prepared exact locked environment
collected **841 unique six-file nodes**, SHA-256
`c66e656f5535d20ca799cd64c154cb4145214a3bb593793834113b9ad3b5a4a1`
over newline-joined collected IDs without a trailing newline. All **841 tests
and 131 subtests passed**. The workflow expected count was set to 841 only after
that actual collection, not by adding a guessed delta. The exact extracted
pure/SDK unit-contracts workflow block also ran locally and emitted PASS with
841 collected/executed/passed, zero failures/errors/skips, and both process exits
zero. The 23-method preparation selection is a subset, not extra unique coverage.

The six selected files and the subsequent CLI acquisition, seven-case service
selection and hosted acceptance steps remain unchanged. Only the pure-unit
identity mapping and its actual collected-count pin changed in the workflow.
No additional dependency installation occurred during this follow-on. No Temporal
CLI/server, actual hosted execution, remote publication or batch service wiring
was performed. The local collection/identity blocker is now qualified for this
exact source; any later integrated source change requires fresh qualification.
Hosted batch delivery and publication still require separate exact-candidate
approval and their own original-evidence/lifecycle implementation and review.

## V2 async preparation: frozen design before implementation

This is a separate local preparation candidate; the accepted v1 nine-path source
and receipts remain immutable. Causal requirements were reviewed with the live
batch design and independent verification owners before implementation.

- Both wrappers use one reservation and acknowledgment-settlement implementation.
  Exactly one attempt and outstanding slot are consumed before calling a start
  callback or creating/awaiting its returned operation; no 200-task queue exists
- `submit_next` remains the synchronous fixture wrapper. `submit_next_async` binds
  one event loop and producer task for its lifetime. Submission modes cannot mix;
  overlapping/reentrant producers and foreign-loop/thread mutations are refused
- The async wrapper owns at most one shielded start task. Caller cancellation
  independently latches uncertainty; the unresolved operation remains explicitly
  owned/observed. No replacement, replay, fabricated cleanup or cancellation of
  remote work is implied. No mutation lock is held across await
- Cancel before the async wrapper starts: no callback or reservation. An already
  cancelling producer entering the wrapper closes admission without issuing an
  RPC. After reservation, cancellation/timeout/exception/invalid acknowledgment
  consumes the allowance and closes admission. Control cancellation is re-raised
- Cancellation before/after await and a swallowed cancellation in the owned task
  must not yield clean admission. Already-done Futures from foreign loops are
  refused explicitly. These guarantees assume cooperative bootstrap callers,
  not hostile Python or external manipulation of Task cancellation state
- Completion settlement is idempotent. A valid late ack binds the original job/run
  once; unknown/duplicate/wrong ack never retries or frees a slot. Late valid
  terminal evidence may account for work but cannot clear uncertainty
- Client ack is independent of real Activity execution. A live Activity start/end
  or server-side completion may precede client ack. The unchanged v1 fabricated
  trace ordering is only a fixture assumption. Future live evidence must retain
  original arrival order and use separately approved correlation/buffering
- Validated-terminal settlement still requires ack/run identity plus original
  result validation. V2 does not add pre-ack live observation handling, real CAS/
  history extraction, cross-thread observer integration or hosted service wiring
- Tests use controllable Futures/events and explicit event-loop callbacks, with
  no real sleeps, service or native lifetime probes. Requalify the full six-file
  selection and exact manifest with existing locked tooling; set the workflow
  expected count only from fresh actual collection

V2 attempt-count clarification: the admission allowance counts application-level
submit-callback invocations. It does not count or bound physical network requests.
The pinned SDK's high-level `Client.start_workflow` enables its own transport
retry behavior; Workflow/Activity maximum_attempts=1 does not disable client RPC
retries. This pure preparation invokes no SDK/network method and neither adds a
private-internals workaround nor claims to govern callback-internal retries.
A future live integration must separately review the supported start transport,
request identity and retry/ambiguity policy before making a network-attempt claim.

### V2 implemented and locally qualified disposition

Both wrappers now call the same `_reserve_submission` and
`_settle_submission_ack` paths. The async wrapper retains one shielded operation
and an idempotent observer; completion or late failure is observed once without
another callback. Snapshots expose whether start observation remains pending.
No observer method can mutate from a foreign thread/loop, and the first async
producer task remains the sole submitter even after one submission completes.
Same-loop result/ack observations may settle known work; they are not permission
for another producer. Mixed sync/async submission is refused. No lock is held
across await, and no production API or cross-thread observer queue is introduced.

Eight new deterministic asyncio methods extend the explicit preparation manifest
to 31 methods. They cover reservation in both callback forms, pending and unstarted
cancellation, immediate/swallowed cancellation, one-time late ack, callback and
snapshot isolation, reentry/ownership boundaries, malformed/foreign awaitables,
exception/timeout uncertainty and the full 16-outstanding/200-job fixture. They
use controlled Futures/events and event-loop callbacks, never sleeps or a service.
Foreign exception attributes are not inspected while recording uncertainty.

Fresh actual locked collection found **849 unique six-file nodes**, SHA-256
`afe83675a96a6a7c69fdbf860924fa9b8976fc82ca770839981c851daf5a430c`
over newline-joined IDs without a trailing newline. All **849 tests and 138
subtests passed**. The workflow count was changed to 849 only after collection;
its strict one-to-one JUnit matching and explicit PASS counting are preserved.
The v1 verifier/fixture schema and seven-case service selection remain unchanged.
These local synthetic/SDK results are not real-service batch evidence. The
accepted v1 candidate and its original qualification records remain separate.

Cooperative callback precondition: the callback must create/start its operation
only after the wrapper invokes it. Returning an operation already launched before
admission cannot retroactively establish pre-dispatch reservation. V2 does not
claim to police hostile Python, previously escaped Tasks or arbitrary external
Task cancellation-state manipulation. A plain Future used solely as a test's
completion signal is not itself evidence that external work has started.

The async bound is finite admission and at most one owned start operation, not a
new wall-clock deadline. The callback or outer caller supplies any start timeout;
observed timeout/cancellation closes admission but does not prove remote work
stopped. Unresolved shielded work stays explicitly pending until observed. Live
RPC deadline/retry policy and loop-lifetime handling remain separate prerequisites.

## Historical real hosted batch preparation checkpoint (2026-10-02)

Historical status at this preparation checkpoint: **NOT RUN on a real service**.
The frozen v2 async preparation is the
base; its historical fabricated results remain unchanged. This candidate adds a
separate explicit four-node acceptance file and manual `batch200` workflow
choice. PR events and the default choice still select the original seven cases.
Actual hosted execution requires later root approval of the exact candidate and
manual dispatch. Neither a local unit pass nor an available workflow is approval.

### Causal observation and original binding

A single shared admission owner reserves attempts and a 16-job outstanding
window. Exactly 200 fixed synthetic payloads are seeded in the canonical store;
no all-at-once coroutine queue is constructed. One retained start operation and
at most 16 terminal observers account for reserved work. The public SDK's default
transport retries are declared explicitly: one logical application start is not
a count of physical transmissions. There is no application resubmission.

A shared brief lock serializes reservation, logical public-client entry and
thread-side uncertainty. Stop after reservation but before client entry consumes
that reservation without entering the client. A stop after entry can leave the
already-admitted retained operation in flight. The lock is never held over an
await, handler, CAS read or disk write. Missing observations independently close
admission; a failed recorder cannot accidentally produce acceptance.

The real stream samples `time.monotonic_ns()` under that lock and records elapsed
microseconds, permitting equal timestamps. Activity Info and a ContextVar bind
workflow/run/Activity/attempt through the SDK interceptor, outer executor and
nested canonical handler. Activity events may precede acknowledgment. Result
settlement requires acknowledgment plus all original receipt, input, output,
canonical bounded CAS and terminal history bindings. All sums are 199; equal
output alone never establishes association. Receipt native fields remain private,
and no native observation/probe is added.

### Fixed ceilings and scope

- 200 reserved application attempts; 16 unvalidated reservations; eight Activity
  slots and eight external executor workers; one Activity and one workflow poller
- Workflow task capacity one, cache zero, eager execution disabled; unchanged
  one-second callable, 10/60-second Activity and 120/120/10-second Workflow settings
- Existing 180-second work deadline, at most 40-second observation-only drain,
  existing bounded public shutdown and ten-minute hosted job limit
- Input at most 256 bytes; result at most 16,384 bytes; 3,276,800 result-payload
  bytes reserved before submission, maximum input-plus-result allowance 3,328,000
- Trace at most 4,096 rows / 1,024 bytes per row / 5 MiB; metadata and outcome rows
  at most 200 / 1,024 bytes each; no truncation-to-success
- Each terminal history at most 64 events / 64 KiB raw / 16 KiB projected;
  aggregates at most 16 MiB private raw and 4 MiB projected; public summary 64 KiB

These are evidence/payload allowances, not host memory/disk/thread quotas. No CPU
parallelism, speedup, native lifetime, multi-host, 200-agent, scientific/device or
general exactly-once claim follows.

### Evidence, verdicts and cleanup

Real evidence uses `opendot.temporal.real-batch.*.v1`,
`HOSTED_REAL_SERVICE` and `HOST_MONOTONIC_OBSERVATIONS`. Offline live-shaped test
fixtures must be `FABRICATED_UNIT_DATA` and cannot use the hosted verifier path.
Source closure includes the twelve candidate paths, protected canonical and
adapter owners, old selection, acquisition/pins and unit/default import closure.
The summary separately reports `delivery_admission_acceptance` and
`activity_overlap`. Natural peak one is `NOT_DEMONSTRATED`; peaks two through eight
show only overlap of instrumented Activity-call intervals. Handler overlap is
measured separately and does not prove CPU parallelism. No sleep, barrier, latch
or repeat-until-favorable experiment manufactures overlap.

On the first unknown start, observation/runtime fault, invalid original result or
transport interruption, admission stays closed. Observation-only cleanup retains
existing operations and never retries starts or terminal observations, cancels
remote workflows, resets, restarts, probes descendants or force-stops processes.
Public shutdown requires all possible reservations accounted for, no unresolved
operations, balanced handler observations, no execution/observer uncertainty, one
server generation and exactly one workflow/Activity pair. A late acknowledgment
can account for its original reservation without clearing qualification failure.
Unknown cleanup stays `UNCONFIRMED`. Private logs, histories, SQLite and CAS remain
job-local; only strictly validated bounded summaries may be published.

### Local disposition

Fresh six-file local collection/execution is **1,092 passed**, with **138 passing
subtests** (subtests are not extra nodes). The pure preparation manifest selects
274 collected identities, a subset of those 1,092. The four real acceptance nodes
are collection-only locally. Public SDK ActivityEnvironment, bounded fake worker
factories and public protobuf fixtures exercise observer/context/history edges;
the exact live Worker context path remains unrun. Independent exact-source review
and broader regressions are tracked in the external local qualification record.
At this historical checkpoint, hosted disposition was **NOT RUN** pending a
separately authorized manual experiment; see the first-run status below.

## First real batch status (2026-10-02)

The first separately authorized [manual run 36984666613](https://github.com/sddvacav/opendot/actions/runs/36984666613),
[job 110766846040](https://github.com/sddvacav/opendot/actions/runs/36984666613/job/110766846040),
on [PR 28](https://github.com/sddvacav/opendot/pull/28) completed successfully on
revision 1b2e417cf9b303413b0696f8b1a17ae0860518fb. Its source-bound trusted-host
receipt was accepted: 200 reported validated terminals, Activity interval peak 3,
handler interval peak 1 and outstanding-reservation peak 16. Handler overlap was
NOT_DEMONSTRATED; CPU parallelism stayed NOT_EVALUATED. No stronger claim follows.

**Historical first-run / pre-retention checkpoint.**

Only the published summary/table digests remain available for that run. The complete
per-job trace and tables are unavailable; their missing rows cannot be independently
rechecked, recovered from hashes or fabricated. This section preserves the first-run
receipt and its source epoch. The new retention candidate below does not recover or
retroactively strengthen that evidence and has NOT RUN in hosted CI.

## Optional public projection retention candidate (2026-10-02)

**Historical pre-run checkpoint.**
Status: LOCAL PREPARATION ONLY. No new hosted run, upload or publication has occurred.
A future evidence-retention run requires root approval of the exact candidate and
manual batch200 dispatch with retain_public_evidence=true. This boolean defaults
false; reference/default/PR qualification cannot upload. Its purpose is retaining a
reviewable projection, never rerunning until better overlap appears.

### Closed bundle and validation

The existing verifier accepts --public-bundle only for batch200. Before creating
output it validates exact collection and JUnit identities, environment/source pins,
all 200 job bindings, actual trace values and cleanup using its existing validation
owners. It reads bounded regular-file snapshots, rejects symlinks (including
ancestors), hardlinks, extra input files, unknown fields, invalid values, oversize,
source/identity changes and observed mutation. A fresh dedicated sibling staging
directory contains only canonical JSON from those already validated values, never
unchecked rereads or a copy of the audit directory. Any refusal prevents the upload
step. Failure summaries expose fixed codes rather than rejected contents.

Exactly eight public files are constructed:

- environment.json: existing closed environment and public source bindings, 64 KiB
- batch-trace.json: actual monotonic trace, fixed plan/profile and source digests, 5 MiB
- batch-metadata.json: validated received Activity metadata, 256 KiB
- batch-histories.json: validated allowlisted history projections, 4 MiB
- batch-outcomes.json: validated terminal/outcome projections, 256 KiB
- batch-cleanup.json: validated bounded observed-cleanup values, 64 KiB
- batch-summary.json: recomputed verdict, recorded passed node identities and explicit
  omitted-original/replay caveats, 64 KiB
- manifest.json: fixed PUBLIC_PROJECTION label, source/run identity, requested
  run attempt, fixed workflow path/digest, retention and SHA-256/byte length for each of the seven payload files, 16 KiB

All limits include each final newline; aggregate output is at most 10 MiB. Trace
and row/event ceilings remain the existing 200/16/8 bounded profile. No original
CAS objects/receipts, raw SDK histories, database, logs, JUnit diagnostics, pip
reports, credentials, headers or private paths are exported. History digests and
original-validation flags remain trusted-host consistency assertions about omitted
originals; they are not independently replayable originals. Source-tree paths are
only the verifier's fixed repository-relative public source allowlist.

The trusted cooperative POSIX host and caller-controlled paths remain preconditions.
Snapshot/identity checks reject observed mutation; they do not defeat a malicious
host, eliminate every filesystem race, provide an OS sandbox or freeze a directory
against hostile writes after verification. There is no second storage/runtime owner.

### Rechecking retained projection bytes

Use the exact reviewed source revision of the retained run, not a later verifier.
After obtaining and unpacking the artifact, run the stdlib-only command:

```sh
python -B ci/verify_temporal_server_gate.py recheck-public-bundle \
  --bundle /trusted/local/unpacked-public-bundle \
  --expected-revision REVIEWED_40_HEX_REVISION \
  --expected-run-url https://github.com/OWNER/REPOSITORY/actions/runs/RUN_ID \
  --expected-run-attempt 1
```

The verifier requires the eight-file allowlist and manifest hashes, repeats the
same environment/source/table/trace/cleanup value validators, and compares its
recomputed summary with the retained summary. Success is PUBLIC_PROJECTION
consistency only. It performs no service call, SDK replay, original CAS/receipt
revalidation or independent authentication of the original host/run assertions.
Natural Activity or handler peak one remains NOT_DEMONSTRATED. Fabricated unit
records retain FABRICATED_UNIT_DATA and cannot enter production export/recheck.

### Official action, access and expiry

Reviewed official [v7.0.1 release](https://github.com/actions/upload-artifact/releases/tag/v7.0.1),
[pinned action API](https://github.com/actions/upload-artifact/blob/043fb46d1a93c77aae656e7c1c64a875d1fc6a0a/action.yml),
[source](https://github.com/actions/upload-artifact/tree/043fb46d1a93c77aae656e7c1c64a875d1fc6a0a/src),
and [MIT license](https://github.com/actions/upload-artifact/blob/043fb46d1a93c77aae656e7c1c64a875d1fc6a0a/LICENSE).
The immutable pin is 043fb46d1a93c77aae656e7c1c64a875d1fc6a0a. It uses Node 24 on
GitHub-hosted ubuntu-24.04; no action source is copied into this repository.
Its MIT notice applies to copies/substantial portions. The declared inputs are
name, the exact dedicated public directory, if-no-files-found=error,
retention-days=30, compression-level=6, overwrite=false, include-hidden-files=false,
and archive=true. No glob, parent/audit directory or additional path is admitted.
The action uses its normal short-lived runner artifact service credentials, with
no saved credential, new token, OIDC grant or workflow-permission expansion.

Requested retention is fixed at 30 days. The export step refuses a reported
GITHUB_RETENTION_DAYS cap below 30 rather than silently requesting a shorter
period. GitHub repository/organization policy and later deletion still apply;
future run review must inspect actual artifact expires_at and the action's
artifact-id, artifact-url and artifact-digest outputs. The artifact archive digest
is distinct from the manifest's individual canonical JSON file digests.

GitHub's [download documentation](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts)
requires login and repository read access. PUBLIC_PROJECTION means the contents
are explicitly approved public-safe values; it does not promise an anonymous
URL. [Repository retention](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository)
limits and artifact/run/repository deletion can end access. This is bounded
retention, not permanent public archival. Download promptly within the actual
expiry window for later authorized review; no automatic external mirror is added.
