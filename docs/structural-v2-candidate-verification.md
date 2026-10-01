# 0.3.0a1 candidate verification boundary

## Unreleased source-only file-size follow-on

The current source adds only inherited Gmsh file-size preservation to the frozen
resource-qualified predecessor described below. Before importing Gmsh, the
worker now takes the minimum of 32 MiB and finite inherited file-size soft/hard
limits, including zero. CPU setup and the separate solver-child file-size
assignment are unchanged. See [exact resource policy](gmsh-cpu-ceiling.md).

The updated manifest selects 35 fake-resource Gmsh nodes, 16 net additional
nodes: **1,325 portable / 1,484 controlled-local** distinct nodes. These are
selections, not pass counts; subtests are not additional nodes. A future changed
artifact's proposed installed selection would be 347 nodes, but no package
build, installed check, kernel enforcement or native execution is performed for
this component. Existing v0.3.0a1 release assets do not contain this repair.
Their receipts, outputs and hashes retain their exact predecessor scope.

### Subtest attribution erratum

The retained predecessor text below labels 49 subtests as "energy". Those 49
belong to `tests/test_solver_cpu_ceiling.py` (`SolverCpuCeilingTests`): eight
alternate-sentinel, 36 finite-boundary and five wall-timeout subtests. The other
44 predecessor subtests belong to `tests/test_gmsh_cpu_ceiling.py`; none of
these 93 subtests comes from the structural elastic-energy test module.
This is an attribution correction only; historical totals, packets and hashes
are unchanged. The current focused resource tests have 49 solver CPU plus 92
Gmsh resource subtests (141 total), separate from their 52 test nodes.

## Frozen predecessor scope (retained)

The original prepublication record below describes the prior 1,309 / 1,468-node
source and its separate artifacts. Its file-size limitation is superseded only
for Gmsh in the unreleased source follow-on above. It is not acceptance of that
follow-on, and its installed/build/guide selections are not new executions.

Date: 1 October 2026 UTC. Version: **0.3.0a1**, separate and **unreleased**.
Overall assessment: **NOT_SCORED**. Declared selections are not pass receipts.
Exact source identity, artifact hashes, executed outcomes and independent review
are recorded in separately delivered sanitized receipts.

## Intentional successor boundary

This resource-qualified successor preserves the previously accepted 0.3.0a1
source and artifacts at `12b17aa5a2c2f4982fc3f403493261bbf1930032`, and adds only
the separately reviewed Gmsh inherited-CPU component plus its tests/docs. That
predecessor began with immutable a6 and combined structural-v2 and source-conflict
components. This unreleased version has distinct source/artifact identities; no
previous receipt is rewritten or relabeled. Earlier source/artifact acceptance is not
transferred to this candidate; a6 bytes and historical evidence are not rewritten.

- [Structural default v2](structural-default-v2.md) intentionally changes the
  default verifier and refinement return dictionaries to schema 2 and conditional
  statuses. Strict admission is followed by the existing, unchanged per-element
  energy kernel in the same structural owner. Scientific acceptance stays false
- Explicit keyword-only `profile="artifact_v1"` preserves exact historical
  receipt/comparison behavior, including its known E/ELSE gap. No automatic
  fallback is added. CLI verification/comparison and native creation use v2
- The optional `verify_elastic_energy` API and its report, on-disk schema-1 packs,
  canonical artifact/reference/callable owners and reviewed failure boundaries
  remain unchanged. Cached old-pack replay is not a new native solve
- The [source-boundary example](../examples/source-boundary/README.md) now executes
  seven original synthetic protocols, leaves eight original protocols unimplemented,
  and counts six invented parameter fixtures separately. Conflict/unknown evidence
  is refused before dependent dispatch. This adds no generic policy owner,
  authentication, scientific applicability, security or production enforcement
- No-underflow is `ASSUMED_NOT_VERIFIED`; the formal arithmetic error bound is
  `NOT_PROVED`. The fixed zero-history isotropic linear-elastic case is not expanded
  to other constitutive models, geometries or experiments

The [Gmsh CPU callback](gmsh-cpu-ceiling.md) takes the minimum of 300 seconds
and finite inherited CPU soft/hard limits, including zero, before importing
Gmsh. Only fake-resource AST-prefix checks are performed. The earlier unconditional
32-MiB file-size cap and its lower-inherited-cap limitation remain unchanged.
Future native packs must bind the new worker helper bytes; old receipts/cache
are not rebound. Final source/installed review is not permission to launch a mesh
or solver. Any such run needs its own frozen protocol and authorization.

## Predeclared scopes

| Scope | Exact selection or contract | Outcome location |
| --- | --- | --- |
| Portable source | 1,309 distinct nodes = a6 1,183 + structural 59 + conflict 48 + Gmsh CPU 19, selected once through the existing nine workflow manifests | Separate author receipt |
| Controlled local source | 1,468 distinct nodes = portable 1,309 + Git 78 + source-provenance 81; trusted POSIX Git 2.52+ only | Separate author receipt |
| Installed regression | 331 distinct nodes = prior author 185 + prior independent-only module CLI 20 + structural 59 + conflict 48 + Gmsh CPU 19; fresh wheel-only environment, copied test/example fixtures, isolated imports | Separate installed receipt |
| Documentation | AST parse; local links/fragments; unique exact manifests; eight identical nonempty installed-guide blocks and four measurement-guide blocks per language | Separate documentation receipt |
| Offline build | Empty isolated environment; only cached hash-verified setuptools 84.0.0; wheel/sdist source payload, metadata, RECORD and license checks | Separate build receipt |
| English and Chinese installed guides | All eight blocks per language in independent fresh environments against the exact wheel | Separate guide receipt |
| English and Chinese measurement guides | All four blocks per language, including retained refusal bytes and existing-output preservation | Separate measurement receipt |
| Independent integration review | Final frozen source, installed profiles, artifacts, privacy and documented claim boundaries | Separate reviewer receipt, never implied by component review |
| Hosted CI / publication / native / GPU / model / device / browser / remote writes | Not performed in this local integration | NOT_RUN |

The 49 inherited energy and 44 Gmsh CPU subtests are not additional test nodes. Portable,
controlled-local, installed and guide checks overlap and must not be summed.
The controlled selection is not unrestricted discovery. Optional actual simulation,
native and lifetime execution are excluded; included fake/import/refusal checks
retain their exact scopes. No software pass establishes scientific qualification,
real-consumer migration, independent approval or a full-platform score.

Keep generated receipts outside source. Source hashes establish byte identity,
not authorship, authorization, confidentiality or scientific validity. The
[historical a6 record](a6-candidate-verification.md) stays version-bound.
