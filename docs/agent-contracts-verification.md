# Agent metadata: local author verification

Date: 2026-10-01 UTC. Scope: unreleased `opendot-engineering` **0.2.0a2**.
This record describes author checks, not independent artifact acceptance,
publication, existing-consumer migration, or an agent execution benchmark.
Exact final source/archive/wheel identities belong to the separate delivery
receipt; previous-version evidence is not relabeled as this candidate.

## Selected checks

- **805 selected source tests passed**, zero failures/errors/skips: the inherited
  773-node selection plus 32 disjoint metadata-contract nodes. Host: Linux,
  CPython 3.12.14, Git 2.52.0, pytest 9.1.1
- One inherited artifact test changes only its class-list scope assertion to
  permit precisely `ArtifactRef`, `Capability`, and `AgentManifest`. Other
  inherited test files are unchanged; this is not a claim of unchanged bytes
  for all 773 selected nodes
- The 32 new nodes cover field order/defaults/annotations, canonical export
  identity, frozen assignment, equality/hash, asdict/pickle/explicit JSON
  projection, ordinary valid input, blank/wrong types, malformed mutable sets,
  overlap, negative/non-finite/boolean numbers, reliability bounds, integer turn
  limits, large finite integers, explicit validation, and the real metadata example
- Installed metadata selection: **32 passed**, zero failures/errors/skips in a
  fresh isolated environment with `-I -B`, outside source. These repeat the same
  nodes and do not increase the unique count
- Static extraction comparison preserves the declared fields/decorators/defaults
  of the two reviewed project classes while identifying changed validators.
  The previous `ArtifactRef` decorator/body is byte-identical; all other existing
  implementation owners are unchanged. Original private classes were never executed

## Reproduce and interpret

Use the exact [five-manifest recipe](../ci/README.md), with separately prepared
test tooling. Outputs and temporary directories stay outside the source tree;
bytecode, plugin autoload and pytest cache are disabled. The hosted workflow
now selects 727 portable nodes (695 inherited +32 metadata), excluding Git
requirements; no hosted execution is claimed.

Build the wheel from a separately staged copy of the exact source archive.
Install with `--no-index --no-deps --no-compile` into a fresh environment, verify
that imports resolve to that environment's `site-packages`, and run copied
examples/tests with `-I -B`. The wheel has one distribution and no required
runtime Python dependencies. The [metadata example](../examples/agent-contracts/README.md)
validates only declarations, without agent/tool/model execution.

The source and built-package review checks syntax without writing bytecode,
relative documentation links, bounded private-marker scans, package members,
source/payload equality, RECORD hashes, license/NOTICE, dependency metadata and
canonical imports. Pattern scans are bounded checks, not comprehensive privacy
or rights certification. Final artifact details and example outputs remain
outside the public source tree.

Optional simulated-device execution, native backends, models/providers,
job runtimes, consumer deployment, enforceable permissions/budgets, and broader
compatibility remain outside this work. Historical 0.2.0a1/0.2.0a0 evidence keeps
its original scope; no previous run is counted as a new run here.
