# Exact portable CI boundary

Current **0.3.0a1**, unreleased and **NOT_SCORED**, selects **1,309 distinct
portable nodes**: a6's 1,183 plus 59 [structural-v2 cases](solver-crosscheck-nodes.txt)
and 48 new [source-conflict cases](source-boundary-nodes.txt), plus 19 fake-only
[Gmsh CPU ceiling cases](solver-crosscheck-nodes.txt). The existing nine
workflow manifests select each node exactly once. Adding 78 Git and 81 source-
provenance cases gives **1,468 controlled-local nodes**. These are selected counts,
not outcomes. [Exact successor scope](../docs/structural-v2-candidate-verification.md).

The frozen **0.2.0a6** local candidate record selected **1,183 distinct portable
nodes**: corrected a5's 1,104, [41 read-only artifact cases](readonly-artifact-nodes.txt),
and [38 source-boundary cases](source-boundary-nodes.txt). Adding the separately
supported 78 Git and 81 source-provenance nodes gives **1,342** controlled-local
nodes. These are selected counts, not outcomes; repeated installed tests and
subtests are not extra unique nodes. [Historical a6 scope](../docs/a6-candidate-verification.md).

The historical unreleased 0.2.0a5 selection added the [explicit solver cross-check manifest](solver-crosscheck-nodes.txt): 17 fake-resource CPU-ceiling cases and 54 optional elastic-energy cases. That a5 portable union was **1,104 distinct nodes**; adding the separately supported 78 Git and 81 source-provenance nodes gives **1,263**. These are selected counts, not pass claims. [Exact a5 scope and results](../docs/a5-candidate-verification.md). Earlier counts below retain their historical boundaries.

The read-only Python 3.12 workflow installs pinned test tooling only. Checkout
and setup actions remain pinned to full commits, credentials are not persisted,
bytecode/plugin autoload/cache are disabled, and JUnit/temp files stay outside
source. The definition has not run on hosted CI for this cut; no hosted success
is claimed.

## Deduplicated inherited integration selection

- [Portable manifest](portable-nodes.txt): 545 nodes = the existing 502 plus 43 CAS
- [Callable manifest](callable-nodes.txt): 143 retained/public callable nodes
- Inherited unique union: **688**, not 545 + 645; both predecessor candidates
  already contain the same 502 baseline nodes
- [Composition manifest](composition-nodes.txt): 7 new callable/CAS cases
- Original integrated portable selection: **695 unique nodes**, no duplicates

The original integration used these three manifests. The current source recipe
below also selects the metadata and public-regression manifests, matching the
hosted workflow definition. It reports actual passed, failed, errored, and
skipped tests separately; it does not discover an unrestricted full suite.
Manifest changes require review. The three private source-identity callable
tests remain excluded. See [historical local integration evidence](../docs/execution-core-verification.md).

## Current portable source selection

The [public-regression manifest](public-regression-nodes.txt) selects only reviewed,
fully collected case IDs from three new files:

- Demo output errors: 30 collected cases for existing-path refusal, preserving
  prior artifacts, normal JSON output, and propagation of later failures
- Read-only package module CLI: 20 collected help/version, argument-refusal, and
  guarded no-dispatch cases; these do not run the APIs described in help
- Research index: 44 collected offline consistency and negative cases, reusing
  source-audit helpers; no web requests, source-truth, or implementation claims

These are collection counts, not a combined test result. Collect and run the
exact final integrated selection before reporting its actual total or pass
count. This change establishes neither a hosted run nor release acceptance.
Symlink cases report skips on unsupported hosts; skips are not passes.

```sh
mapfile -t portable_nodes < ci/portable-nodes.txt
mapfile -t callable_nodes < ci/callable-nodes.txt
mapfile -t composition_nodes < ci/composition-nodes.txt
mapfile -t agent_contract_nodes < ci/agent-contract-nodes.txt
mapfile -t public_regression_nodes < ci/public-regression-nodes.txt
mapfile -t delivery_workflow_nodes < ci/delivery-workflow-nodes.txt
mapfile -t solver_crosscheck_nodes < ci/solver-crosscheck-nodes.txt
mapfile -t readonly_artifact_nodes < ci/readonly-artifact-nodes.txt
mapfile -t source_boundary_nodes < ci/source-boundary-nodes.txt
CHECK_OUTPUT=$(mktemp -d /tmp/opendot-check.XXXXXX)
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src \
  OPENDOT_TEST_SOURCE_ROOT="$PWD/src" python -B -m pytest -q -ra -p no:cacheprovider \
  "${portable_nodes[@]}" "${callable_nodes[@]}" "${composition_nodes[@]}" \
  "${agent_contract_nodes[@]}" "${public_regression_nodes[@]}" "${delivery_workflow_nodes[@]}" "${solver_crosscheck_nodes[@]}" "${readonly_artifact_nodes[@]}" "${source_boundary_nodes[@]}" \
  --basetemp="$CHECK_OUTPUT/pytest" --junitxml="$CHECK_OUTPUT/results.xml"
```

This Bash recipe requires the separately prepared [test tooling](requirements.txt).
Run it from the reviewed public repository root. Source syntax checks use AST
parsing rather than bytecode generation. `OPENDOT_TEST_SOURCE_ROOT` explicitly
admits this checkout's public `src` for isolated CLI children; `PYTHONPATH` alone
is ignored by their `-I` mode. Do not point it at private or unrelated source.

Installed-artifact checks are separate: use a fresh environment and an external
working directory, with `OPENDOT_TEST_SOURCE_ROOT` and `PYTHONPATH` **unset**,
`-I -B`, plugin autoload disabled, and pytest's cache provider disabled. Admit
only separately prepared test tooling if required, never source import paths.
Copy only the reviewed CLI test when checking it against the wheel. The demo
and research tests locate repository examples/documents and are source checks;
do not present their source-backed subprocess runs as installed-wheel coverage.

The complete optional fake-only simulation selection has 108 cases, including
17 already in the portable manifest. Its remaining 91 are separately scoped;
its results are never added without subtracting that overlap. The workflow does
not install `simulated-lab` or run Bluesky plans. Portable import/refusal and
injected-timeout cases do not establish actual fake-device execution.

Optional native backend/lifetime tests, models, physical devices, remote writes,
and full platform acceptance remain outside this selection. A synthetic pass is
not scientific qualification, security certification, or real-consumer migration.
Do not place local JUnit files or generated receipts in a public source release.

## Controlled local Git profile (0.2.0a1)

The additional [Git manifest](git-workspace-nodes.txt) selects 78 disposable
local Git cases. Its historical union with the original 695 portable cases
was 773 unique cases. Only on an explicitly prepared POSIX host with trusted
system Git >= 2.52.0 may the current source recipe be extended with a separately
reviewed array from `ci/git-workspace-nodes.txt`. Collect that final union and
report its own results; do not reuse a historical total. Two cases cover the
[residue-reporting repair](../docs/git-workspaces-residue-fix.md). Output directories
must remain outside source.

The inherited hosted workflow was the 695-case boundary. The Git selection has not been
silently extended to runners with an unspecified/older Git version. The Git
profile fails closed on an unsupported Git executable; no unsafe fallback or
skip-to-pass path is provided. Hosted Git-profile CI and a broader version/OS
matrix are not established. See [new local checks](../docs/git-workspaces-verification.md).


## Descriptive agent contracts (0.2.0a2)

The reviewed [metadata manifest](agent-contract-nodes.txt) adds 32 disjoint,
synthetic cases. The metadata integration's hosted definition selected them with
the 695 inherited portable nodes: **727 unique nodes**, with no
Git/native/model/provider execution added. The current recipe above also includes
the public-regression manifest. No hosted run is claimed. One inherited artifact
test's class-list assertion now admits precisely ArtifactRef, Capability and
AgentManifest; other inherited test files remain unchanged.

The metadata-era local Git union was **805 nodes** (773 inherited selection plus
32 metadata cases). That historical total does not include the new
public-regression manifest and is not a result for the current candidate.

Installed metadata tests/examples are a separate fresh-environment `-I -B`
check; repeating those nodes is not additional unique coverage. See the
[0.2.0a2 record](../docs/agent-contracts-verification.md).

## Shared solver gate and offline documentation checks

The public regression manifest also includes 93 solver-declaration cases and
74 documentation-checker cases. These extend the selected source checks without
invoking native solvers or running documentation code blocks. The workflow runs
`ci/check_docs.py` before tests, using the canonical source-audit read helpers.
See [documentation checks](../docs/documentation-checks.md) and the
[declared-version gate](../docs/solver-version-gate.md). Current tested guide profile
requires exactly eight nonempty, identical shell blocks per language; changes to
that reviewed journey require a deliberate profile update. Hosted CI has not run.

## Source-only delivery workflow extension

The [delivery manifest](delivery-workflow-nodes.txt) adds 45 disjoint cases:
35 synthetic repeated-measurement example cases and ten test-toolchain lock
checks. The historical a4 hosted definition selected 1,033 nodes after this extension; no
hosted run is claimed. The example's installed-only reuse of the unchanged
0.2.0a4 wheel is a separate verification scope, not extra unique cases.

Test tools are acquired with exact official-wheel hashes and their selected
CPython 3.12/Linux dependency closure. See [the toolchain recipe](../docs/ci-toolchain.md).
This does not close optional/native/system dependencies or establish complete
vulnerability/license coverage. Source-only inventory checks using Git 2.52+
remain in a separate local manifest and are not silently run on older hosted Git.

The additional [source inventory manifest](source-provenance-nodes.txt) contains
81 controlled local Git/source-index cases. Its union with the 1,033 portable
nodes and the historical 78 controlled Git cases is **1,192 distinct selected
nodes**. This is a selection count, not a pass receipt. The 81 and 78 Git-bound
profiles are not part of the hosted workflow. Run them only on the supported
trusted Git 2.52+ POSIX environment, with output outside source.
