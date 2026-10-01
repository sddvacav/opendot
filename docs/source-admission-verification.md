# Source-admission integration checks

Date: 2026-10-01 UTC. Scope: the optional explicit source-admission API within the
unreleased `0.1.0a0` bounded adapter predecessor. A subsequent independent local
review accepted this narrow source-admission integration and reproduced the
442-case selection and outgoing-artifact checks. This historical record is not
a release approval. The `0.1.0a1` combination is recorded [separately](combined-candidate-verification.md). Nothing is published.

The original [portable verification record](verification-status.md) and
[documentation integration record](integration-review.md) remain historical
records of their stated scopes. This integration adds the reviewed adapter and
its 91 original synthetic tests, public-safe API/schema/attribution documentation,
and a narrow [scope decision](decisions/001-source-admission.md). The canonical
source-audit module, existing adapters, existing tests, and Apache license are
unchanged from the preceding bounded candidate. The preceding static mesh-example
regression test is retained.

## Selected checks

The local selection is the exact 350 portable cases listed in
[the original reproduction command](verification-status.md#reproduce-the-reviewed-portable-selection),
plus `tests/test_gmsh_mesh.py::test_documented_mesh_example_matches_current_recipe`
and `tests/test_source_admission.py` (91 cases). It is not the full suite.
Run with plugin autoload and bytecode writes disabled, pytest's cache provider
disabled, and a temporary directory and JUnit report outside the source tree.

Local checks used CPython 3.12.14 on Linux and the existing pytest 9.1.1 tooling:

| Check | Result | Boundary |
| --- | --- | --- |
| Reviewed portable selection | 442 passed, 0 failed, 0 skipped | 350 prior portable cases, 1 static mesh-example case, 91 synthetic admission cases; not the full suite |
| Source ownership and identity | PASS | Existing source-audit bytes and all prior package sources/tests unchanged; admission test bytes retained; only the new adapter's module header was editorially generalized, with all other AST nodes unchanged |
| Fresh wheel | PASS | Version `0.1.0a0`, no runtime requirements, no console entrypoints; package source and license/notice match this candidate |
| Isolated installed imports | PASS | Only this distribution installed in a clean environment; imports resolve to installed package/standard library; no operator source loaded at import time |
| Installed synthetic source admission | PASS | Original named-object identity and canonical cache return, skipped original initializer, changed-source rejection, false/NOT_EVALUATED receipt boundaries |
| Installed fixed-pin examples | PASS | Source audit accepted; qualification contract passed; scientific/device/real-device flags remain false |
| Static parsing and local links | PASS | Python syntax and relative documentation/image links/anchors checked |
| Bounded outgoing-content scans | PASS | Source, all source-archive/wheel members, and local Git blobs/commits scanned for known private identifiers, local paths, and common credentials |

No new tooling or native dependencies were installed for these checks. Only the
newly built local wheel was installed into the isolated smoke-test environment.
Generated command logs, source inventories, and build receipts remain outside
public source.

## Not established

No native backend, job engine, actual process-lifetime, runtime recovery, live
model, physical-device, external consumer, or hosted-CI acceptance is claimed.
There is no authorization, sandbox, complete-code-identity, or scientific
acceptance guarantee. Privacy pattern scans are bounded checks, not complete
confidentiality or redistribution-rights certification. Changed combined artifacts require their own outgoing-artifact review before
any publication; the predecessor review does not approve a later release.
