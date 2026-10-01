# ADR 002: One canonical local artifact core

Date: 2026-10-01 UTC. Status: unreleased `0.2.0a0` migration candidate.
Existing consumers have not switched owners; integration acceptance is open.

## Decision

Allow precisely `opendot_engineering.core.artifacts` and its sole contract,
`opendot_engineering.core.contracts.ArtifactRef`, in this package. This extracts
the existing canonical SHA-256 store without redesigning its behavior or adding
a second storage implementation. The package initializer only re-exports those
same class objects. Existing adapters and their source-audit helper owner remain
unchanged. This is a narrow exception to the previous no-content-addressed-store
scope, not permission to import broader execution code or contracts.

The extracted closure uses the Python standard library. Its project copyright,
Apache-2.0 license, and modification notice are retained in
[PROVENANCE](../PROVENANCE.md) and [NOTICE](../../NOTICE). Public examples and tests
are newly authored synthetic cases. No original source manifest, broader contract
module, runtime harness, or compatibility patch is bundled.

## Consequences

- The canonical core owns storage logic and `ArtifactRef` identity. Future
  consumers must import or alias these objects together; a copied reference class
  is not the same runtime type. No existing consumer migration is claimed here
- The root, ancestors, and stored paths must be controlled by a trusted caller.
  Paths follow symlinks. Best-effort chmod and lexical digest checks do not
  establish containment, authorization, confidentiality, or a sandbox
- Atomic replacement applies to one file. Object and metadata publication is not
  transactional; the directories are not fsynced. A failed put may leave an
  object without metadata. There is no power-loss or durable-recovery guarantee
- An instance-local lock serializes its puts; separate instances/processes are
  not coordinated. Metadata records the first write while later returned
  references can carry different caller-supplied context
- Hash/size verification does not authenticate provenance, validate metadata,
  establish scientific truth, or grant execution/device authority

No scheduler, job runtime, recovery protocol, native-lifetime owner, remote
service, or model/device execution is introduced. Existing evidence for earlier
versions remains historical. New checks must identify this source revision and
its actual built distribution separately; see [the contract](../canonical-artifacts.md).

The separately reviewed [callable-only scope](../callable-execution.md) is also
admitted in the integrated candidate. That does not broaden this storage
exception or authorize other execution code. See [integration verification](../execution-core-verification.md).

The later [ADR 003](003-agent-metadata-contracts.md) admits only two descriptive
metadata contracts into the same contract owner; it preserves ArtifactRef and
this storage boundary. The historical sole-contract wording above describes
the original artifact extraction, not an authorization for broader contracts.
