# Provenance-integrated 0.1.0a1 candidate checks

Date: 2026-10-01 UTC. This is an **unreleased local source candidate** combining
the accepted source-admission/fake-only candidate with the independently accepted
Git-provenance correction. The preceding combination and repair each passed their
bounded independent reviews. This successor requires review at its own exact
identity; it is not a release, native-backend, scientific, or device acceptance.

The version remains `0.1.0a1` during this unreleased review sequence. Successive
builds with that version contain different bytes. Identify the exact source commit
and wheel/archive SHA-256 values, not the version or filename alone; detailed
artifact receipts are retained outside public source.

## Scope and preservation

The only executable changes from the accepted combination are the four previously
reviewed provenance files: the shared geometry helper and actual-adapter binding
in geometry, mesh, thermal, and structural routes. The complete new Git/stdlib
test file is retained from that repair. The source-admission implementation,
canonical source-audit/qualification owners, simulation modules/tests, remaining
CAD/CAE algorithms, package version, and dependency declarations are unchanged.

Two nonblocking findings from the combination review are corrected: current-use
links now point to the current CI manifest/reproduction guide, and qualification's
POSIX no-symlink prerequisite is stated consistently in its guide, getting-started
page, and both READMEs. Historical 350/459-case records remain historical.

## Current selected checks

Local checks used CPython 3.12.14 on Linux and existing pytest 9.1.1. Bytecode,
pytest plugin autoload, and cache were disabled; temporary files, fixtures,
reports, build staging, and installed environments were outside public source.

| Check | Result | Boundary |
| --- | --- | --- |
| Explicit portable manifest | 502 passed, zero failures/errors/skips | All 459 preceding nodes plus 43 Git/stdlib provenance nodes |
| Separate fake-only simulation file | 108 passed, zero failures/errors/skips | Finite internally constructed fake-device plans; overlaps portable scope by 17 cases |
| Fresh minimal wheel install | PASS | Only this distribution installed, no required runtime dependencies or console entrypoints; exact optional pins retained |
| Isolated imports and source admission | PASS | Installed source/standard library; no implicit optional imports or operator source; admission identity/cache/rejection checks retained |
| Installed pinned examples | PASS | Source audit and synthetic qualification outcomes retain false scientific/device flags |
| Installed fake-only scenarios | PASS | Normal 16-point, fake-failure, and simulated-abort runs using existing exact optional dependencies |
| Minimal offline fake verification | PASS | All three bundles verified without Bluesky, ophyd, event-model, or NumPy; bundle bytes unchanged |
| Installed provenance routes | PASS | All four actual-adapter route bindings report hash-only, null commit/dirty/worktree; no native execution |

The 502 and 108 scopes overlap by 17 cases and must not be summed as independent
totals. No full repository discovery or native/scientific replay was performed.
The [CI manifest](../ci/portable-nodes.txt) contains 502 fully collected explicit
node IDs. Use the [CI reproduction guide](../ci/README.md) for that selection;
actual simulation execution remains separately opt-in.

The repair's historical portable review omitted five old Python-child nodes,
producing 437 rather than 442 prior cases. This integration retains all five:
`502 = 437 + 5 + 17 + 43`. Those accepted helpers inherit bytecode suppression;
all new isolated children use `-I -B`. No exclusion is silently counted as a pass.
The five nodes and exact command/collection evidence are recorded externally.

After freezing a clean commit, the source-checkout acceptance condition is that
all four actual-adapter provenance routes return that exact commit, dirty=false,
and worktree=null, with the correct adapter hash. This check is a Git/stdlib-only
route probe stopped before native execution; its final identity and results are
part of the external artifact receipt, not a native solver or geometry run.

## Provenance semantics and compatibility

New source records verify the actual adapter's local index/HEAD membership.
Ignored or untracked installed copies, broken/non-owning nearer repositories,
uncertain state, and configured executable filters cannot supply an unrelated
clean commit. Inherited Git overrides are discarded. Raw changed adapter bytes
or index/HEAD differences conservatively produce dirty=true even when status
hides or normalizes an edit. The `worktree` field remains present but is null.

Consumers must accept null commit/dirty/worktree and the additional
`GIT_UNVERIFIED_SOURCE_HASH_RECORDED` fallback. Null dirty means unknown, not
clean. A recorded dirty base commit does not claim to contain uncommitted bytes.
Historical receipts and copied packs are untouched. Other native fields can
still contain paths and require export review. Membership does not authenticate
upstream authorship or provide an atomic snapshot or sandbox. See the
[full boundary](cad-geometry.md#evidence-and-deterministic-behavior) and
[historical repair checks](git-provenance-verification.md).

## Gates and exclusions

The prior combined and repair acceptance do not automatically approve their
successor or its rebuilt artifacts. Review the exact final source/wheel/archive,
privacy/rights boundaries, and destination before publication. Existing public
work authorization is not replaced by another consent gate.

No native CAD/solver, physical/scientific, private-consumer/runtime,
process-lifetime/recovery, live-model, real-device, hosted-CI, or broader supported-
platform acceptance is claimed. Previous native results remain bound to their
original artifacts and do not transfer to this revision. No comprehensive
transitive-license, dependency-chain, vulnerability, privacy, or malware audit
is claimed. No external publication occurred in this integration.
