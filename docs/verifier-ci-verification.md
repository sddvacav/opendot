# Solver declaration and documentation CI candidate

> Version boundary: this page records the original 4075ac17 package candidate.
> A later [source-only delivery extension](delivery-workflows-verification.md)
> retains its exact package and README bytes while adding developer tools, examples
> and research documents. The original 1,066/988 selections and historical score
> are not the later extension's combined test or quality result.

Date: 1 October 2026 UTC. Version: **0.2.0a4**, unreleased.
Author combined-source checks: **1,066 passed**, with zero failures, errors or skips
on Linux, Python 3.12.14 and Git 2.52.0. The selected union is 899 inherited cases
plus 93 solver-declaration and 74 documentation cases. Exact-artifact/installed
acceptance remains separate. The hosted portable definition selects 988 cases
and excludes 78 controlled-Git cases; no hosted execution is claimed.

## Changes and bounded meaning

The existing shared `thermal_conduction._check_solver_log` owner now requires
exactly one complete declared CalculiX 2.23 header. Both thermal and structural
artifact verifiers use it. Missing, wrong, embedded, malformed, repeated and
contradictory headers are refused. Existing warning, completion, convergence and
numerical checks retain their prior semantics. This checks internal declaration
consistency, not authenticated logs or binary origin. See [the gate](solver-version-gate.md).

The source-only [documentation checker](documentation-checks.md) reuses the
canonical source-audit file helpers. It checks its documented local-link/fragment
subset, bounded explicit HTML anchors and exactly eight nonempty literal-identical
shell blocks per installed-guide language. It never executes links or blocks and
skips external URLs. The reviewed journey profile must be updated deliberately
when its command structure changes. It is not a complete Markdown renderer,
installed-walkthrough execution or a security sandbox.

The build declaration now pins setuptools 84.0.0, with a separate official-wheel
hash pin for controlled build acquisition. The [recorded build experiment](build-toolchain.md)
remains bound to predecessor a59419b; it does not automatically approve this version.
No runtime dependency, native binary, second parser/registry/runtime owner or new
physical model was added. The maximum-strain-only structural diagnostic limitation
remains; strain/displacement/constitutive consistency is not newly validated.

## Independent component evidence

- Solver gate: initial unchanged-baseline regression reproduced the contradiction;
  30 predeclared independent cases pass on the fix, including the preserved public
  historical 2.23 log and both complete synthetic artifact-verifier counterexamples
- Solver-related selection: 192 passed, 81 native opt-in skips, two external-process
  tests deselected. Skips are not passes; no native solve was run
- Documentation checker: initial independent result was 42/43, exposing an
  unsupported explicit HTML anchor. Original files and result were retained
- Repaired checker: original 43/43 and separately predeclared 8/8 HTML cases pass;
  author selection independently reran with 74 passes and no failures or skips
- The initial expectations were not weakened. No source/runtime/helper edits were
  made by the independent reviewers; unchanged files and exact additions were checked

These results overlap with the combined selected suite and are not additive unique
coverage. Exact component hashes and full commands belong to separate delivery
receipts. Final composition, rebuilt artifacts and installed behavior need their
own checks. Prior 0.2.0a3 tests, score and acceptance retain their original scope.

No provider/model, native solver, physical device, stopped runtime/lifetime/recovery
path, autonomous scheduler or multi-host benchmark is exercised by these checks.
Any separate standalone native benchmark must carry separate identities and evidence.
GitHub publication, hosted CI and public package distribution are not established.
