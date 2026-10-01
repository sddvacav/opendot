# ADR 003: Two descriptive contracts in the existing owner

Date: 2026-10-01 UTC. Status: unreleased `0.2.0a2` extraction candidate.

## Decision

Admit precisely the reviewed `Capability` and `AgentManifest` dataclasses in
`opendot_engineering.core.contracts`, retaining their names, field order,
annotations, defaults, and frozen dataclass declaration. Re-export those same
class objects from `core`; do not create a `DotManifest` alias or another owner.
This supplements the [artifact exception](002-canonical-artifact-core.md) only
for this metadata closure. It does not lift the ban on broader contract/runtime
extraction. The existing `ArtifactRef` body and every other implementation owner
remain unchanged.

The two original validation methods are deliberately tightened for malformed
metadata: explicit nonblank strings, immutable string sets, disjoint tool sets,
finite nonnegative nonboolean numeric costs/latency, bounded reliability, and
positive nonboolean integer turn counts. Their standard-library validation
helpers live in this same owner. Construction remains unvalidated; consumers
must explicitly call `validate()`. See the [API contract](../agent-contracts.md)
for the invalid-input compatibility changes and numeric boundaries.

## Limits

- Metadata only: no registration, schema resolution, execution, scheduler,
  provider integration, model call, native backend, job runtime, or controller
- Permission, budget, turn, memory and oracle fields describe intentions; no
  consumer enforcement, currency unit, or measured reliability is supplied
- Frozen dataclasses provide shallow language-level immutability, not an OS
  security boundary or permission authority
- No old consumer is imported, migrated, or deployed; compatibility of external
  consumers requires separately scoped review
- No private initializer, original test harness, broader module, generic JSON
  helper, operational record, or separately owned implementation is included

The project Apache-2.0 authorization, retained notices, and modification scope
are recorded in [PROVENANCE](../PROVENANCE.md) and [NOTICE](../../NOTICE). Public
synthetic tests and the manifest example are newly authored. Exact extraction
mapping stays outside the source distribution. Publication and independent
artifact acceptance remain separate decisions.
