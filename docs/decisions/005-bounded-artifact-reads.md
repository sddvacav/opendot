# ADR 005: Opt-in bounded reads in the canonical artifact owner

Date: 2026-10-02 UTC. Status: narrow implementation exception accepted; this is
an unreleased source increment. Portable, SDK-only and installed-wheel
qualification are tracked separately from real-server qualification. The
published `0.3.0a2` assets remain unchanged, and their historical real-server
PASS is neither withdrawn nor evidence for these changed owner bytes.

## Failure and decision

The existing `ArtifactStore.get_bytes` reads the entire object before checking
its digest. The fixed synthetic Temporal Activity then compares actual input
length with its 1–256-byte declared size and profile limit. A digest-valid large
object with a false small declaration therefore reaches refusal only after a
whole-object read. The historical [ADR 004](004-temporal-reference-transport.md)
explicitly recorded that trusted bounded-content assumption.

Add a keyword-only option to the same canonical owner:

```python
get_bytes(self, ref: ArtifactRef | str, *, max_bytes: int | None = None) -> bytes
```

- Omitted or explicit `None` retains the existing whole-object read, digest
  verification and exception behavior
- A non-None budget must be an exact nonnegative `int`. Other types, including
  bools, int subclasses and coercible objects, raise
  `TypeError("max_bytes must be int or None")`; negatives raise
  `ValueError("max_bytes must be nonnegative")`. Validation precedes reference
  processing and filesystem access; no conversion hooks are called
- Zero permits only an empty object with a matching digest. Declared reference
  size, metadata and filesystem size declarations do not establish the bound
- Acquire through the existing object path using unbuffered binary reads.
  Each positive request is `min(65536, N + 1 - observed)` bytes. Accumulate short
  nonempty reads, stop at EOF, and refuse immediately upon observing N+1 bytes
- Oversize raises the existing
  `ArtifactIntegrityError("artifact exceeds max_bytes")` before hashing. A
  bounded complete object then uses the unchanged SHA-256 comparison; hash
  mismatch retains its existing exception/message. Ordinary missing/read/close
  errors propagate. No new exported exception, parser or storage owner is added

No arbitrary maximum budget is introduced. Exact Python integers are finite;
fixed-size requests avoid preallocating N bytes or overflowing a file-read size
argument for an enormous allowance. An allowance is caller-selected, not a
package-wide permission policy. The fixed Activity supplies literal 256, not
request-derived metadata, and retains its actual-vs-declared size check.

## Assurance boundary

For trusted, ordinary regular local objects, at most N+1 cumulative object bytes
are acquired into Python. `buffering=0` avoids Python buffered read-ahead. The
sum of requested sizes can exceed N+1 when reads are short; the sum of returned
bytes cannot. An exact-N object needs a further positive EOF probe, whereas
N+1 overflow stops without another read. Each read request is at most 64 KiB.

The fixed Activity input call therefore acquires at most 257 object bytes. An
oversize input is refused before hashing, decoding, runtime execution, handler
entry or result publication, through the existing sanitized nonretryable
`TemporalInputRejected` category. Input reading still precedes the original
runtime deny-only guard, whose behavior and exception identity remain unchanged.

Accumulation and final byte copying use O(N) memory for observed bytes with
allocator/copy overhead. This is not an exact RSS, kernel-I/O, wall-time,
constant-memory, OS-sandbox or authorization guarantee. Trusted roots and regular
objects remain preconditions; no hostile concurrent mutation, FIFO/device or
object-lifetime guarantee is added. Symlinks still follow the existing trusted
root contract. SDK message decoding occurs before the Activity entrypoint and
is not bounded by this change.

`put_file`, put collision comparisons, `verify`, `verify_id`, all other
unmigrated readers and default `get_bytes` keep whole-read behavior. Results
retain their current publication path and limits. No universal bounded-I/O
claim, broader execution-level qualification or general consumer migration is
implied.

## Exact exception and changed paths

This decision and the matching appended AGENTS exception supersede only the
prior exact-byte restriction needed for the optional read branch and fixed
Activity call. All earlier ADRs and evidence remain historical without edits.
The admitted path budget is:

- `src/opendot_engineering/core/artifacts.py`: optional read branch and contract
- `src/opendot_engineering/adapters/temporal_activity.py`: fixed 256-byte allowance
- `AGENTS.md`: matching narrow exception
- `docs/decisions/005-bounded-artifact-reads.md`: this decision
- `docs/PROVENANCE.md`: append-only increment provenance
- `docs/canonical-artifacts.md`: current API and compatibility boundary
- `docs/temporal-reference-transport.md`: current input bound and distinct status
- `docs/architecture.md`: same-owner boundary and distinct qualification
- `tests/test_bounded_artifact_reads.py`: portable synthetic regressions
- `tests/test_temporal_activity_contract.py`: strengthen existing fixed-read cases
- `tests/test_temporal_transport_owner_boundaries.py`: fixed keyword and reviewed
  ArtifactStore-only hash update
- `ci/readonly-artifact-nodes.txt`: append exact new portable test nodes
- `ci/README.md`: distinguish current 1,382-node selection from historical a2
- `ci/run_temporal_server_gate.py`: ArtifactStore-only owner pin update
- `ci/verify_temporal_server_gate.py`: matching ArtifactStore-only owner pin update

No workflow, server-node manifest, dependency, version, export, reference,
Workflow, ToolRuntime, guard, other source owner or historical asset changes
are admitted. The six-file SDK/pure gate keeps its existing 818 cases. Only the ArtifactStore
owner test's digest-bearing parameter ID changes with the approved pin; all
other 817 node IDs are unchanged.
Pin changes bind a changed owner; they do not supply real-server evidence.

## Reviewed owner identity

| Owner | Before | This increment |
| --- | --- | --- |
| ArtifactStore | `91fde8d32f6f7498fc96c0e883b9ba658440e95b0cc92f69f172e4de3d7b7856` | `4606b7b11a81044267b30fee332d9b6fd6540d862726a9579655ee27c7d9a883` |
| Activity | `64bfe8468b225a5882c9fbe16552454ed4f8b3b52ec7e151790f0760be0cbf99` | `cd2c277266239e57c10cb5aab743052f3322acf75be1d48156d715cef6fae5ae` |

ToolRuntime remains
`7c5011e02b2cf07e5f15ad7854905ce0738271e167b873bad9256a8ed169199c`;
contracts remains
`9462415baf84668825ad2c8cfc3f4f3df68332f65d1f1f4b301fbf01cf8537ca`.
Both owners, all six callable contracts, original guard and canonical re-exports
remain exact. The optional SDK is not imported by default.

## Qualification and exclusions

Required checks cover N−1/N/N+1, zero/empty, false declared size, corruption,
invalid budgets before access, huge allowances with tiny objects, actual
unbuffered read sizes/returned bytes, short reads, EOF probes, closure on errors,
legacy None behavior, readonly nonmutation, symlink compatibility, fixed Activity
256, refusal before decode/dispatch/publication, canonical identities and default
import closure. A detached newly built own-source wheel is tested with source
injection disabled and its origin/hash recorded; its unchanged numeric package
version does not make it a replacement for published a2 assets.

Only local portable and SDK-only checks using existing accepted tooling are
admitted here. Isolated offline installation of that own-source wheel is allowed
with `--no-index --no-deps`; no external dependency installation/download,
provider/model call, CLI/server/native service execution, deployment or public
commit/hosted run is authorized by this exception. Real-server qualification
for this changed source remains pending until separately approved and observed.
