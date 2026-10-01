# Current architecture and future goals

This document describes the bounded `opendot-engineering` package and separates it from proposed broader OpenDot work. It does not describe a shipping coordination platform.

## Included package

| Component | Current source | Responsibility and boundary |
| --- | --- | --- |
| Descriptive agent metadata | `opendot_engineering.core.contracts.Capability` and `AgentManifest` | Explicit structural validation only; no agent execution or permission/budget enforcement; [API](agent-contracts.md) |
| Canonical local artifact core | `opendot_engineering.core.artifacts` and `core.contracts.ArtifactRef` | One extracted SHA-256 owner; trusted local roots, per-file replacement, no transactions or consumer migration |
| Local source audit | `opendot_engineering.adapters.source_audit` | Read-only local-byte and declared-metadata checks; no scientific decision, storage service, or access-control service |
| Callable-only execution | `opendot_engineering.tool_runtime` | Existing bounded callable owner, six contracts, in-memory health and deny-only guard; no model, durable recovery, sandbox, or automatic consumer integration |
| Optional source admission | `opendot_engineering.adapters.source_admission` | Explicit operator-reviewed flat-module byte capture and named exports; ordinary trusted Python execution, no authorization service or sandbox |
| Synthetic qualification records | `opendot_engineering.adapters.lab_qualification` | Compare invented fixture outcomes with declared oracles; no instrument simulator, device authorization, or physical qualification |
| Optional simulated lab | `opendot_engineering.adapters.simulated_lab` and internal `_simulated_lab_worker` | A finite fixed Bluesky plan using internally constructed ophyd fake devices; strict offline verification; no real-device control, resume, service, or scientific qualification |
| CAD geometry | `opendot_engineering.executors.geometry` | Bounded synthetic beam geometry through separately installed optional backends |
| Structured meshing | `opendot_engineering.executors.gmsh_mesh` and internal `_gmsh_worker` | Synthetic mesh contract and recorded native identity; a mesh pass is not a solver or science pass |
| Thermal contracts | `opendot_engineering.executors.thermal_conduction` and `thermal_source` | Fixed conduction/source benchmarks with explicit assumptions and acceptance boundaries |
| Structural contract | `opendot_engineering.executors.structural_beam` | Fixed beam benchmark through a separately prepared solver environment |

The default distribution has no required runtime Python dependencies or registered console script. Its import namespace is `opendot_engineering`. The module entrypoints and executable synthetic fixture commands are in the [README](../README.md); optional native requirements live in [the CAD/CAE example guide](../examples/cad_cae/README.md).

The caller owns approved input selection, independent expected pins, trusted artifact roots, evidence retention, access control, dependency preparation, and consequential decisions. This package does not provide a scheduler, agent runtime, database, mission kernel, managed evidence service, or device controller. It makes no sandboxing guarantee. Hash equality proves a bounded byte relationship, not truth, identity, licensing, authorization, or safe publication.

The narrow [canonical artifact core](canonical-artifacts.md) is admitted by
[ADR 002](decisions/002-canonical-artifact-core.md). It follows symlinks, trusts its
root, and does not make object/metadata transactions or durable-recovery claims.
Existing consumers have not switched owners. The [callable-only profile](callable-execution.md)
and CAS ship in one distribution. The [composition example](../examples/callable-artifacts/README.md)
adds no controller: tool status/semantic validity and byte integrity remain separate.
A semantic refusal can leave an intact unaccepted object; no rollback is supplied.

Source admission remains an optional in-process adapter, with no bundled backend
or automatic discovery. It reuses the canonical source-audit helpers rather than
creating a second filesystem-validation owner. Failed execution may already have
external effects; do not retry automatically without reconciling them. See the
[source-admission contract](source-admission.md) and [scope decision](decisions/001-source-admission.md).

The optional [simulated lab](simulated-lab.md) reuses the same canonical source-audit
read/JSON/hash helpers. Its one-shot child runs a fixed fake-device plan with
explicit bounds; it is not an application scheduler or second runtime owner.
Bluesky, ophyd, and event-model are exact-pinned optional dependencies. The strict
verifier remains dependency-free and does not promote simulation into physical
qualification. Runtime receipts retain `NOT_EVALUATED` owner-integration and
independent-review fields; a source review does not certify an individual run.

The `0.2.0a2` [agent metadata contracts](agent-contracts.md) add only `Capability`
and `AgentManifest`. Call `.validate()` explicitly; their budget and permission
fields do not allocate resources or enforce execution. The
[metadata example](../examples/agent-contracts/README.md) adds no agent runtime,
and existing consumers have not been migrated.

## Future direction, outside this package

OpenDot aims to support long-running science and engineering work with explicit tasks and reviewable evidence. Proposed concepts include a bounded work unit (a dot), execution attempts, evidence records, and adapters with inspectable contracts. These are design concepts, not classes or commands in this package.

Future work may address coordination, durable state, human approvals, runtime integration, and independently measured multi-worker or multi-host behavior. None is established by the current adapter checks. A future coordination layer must remain a separately reviewed integration rather than being implied by this package name.

## Proposed adapter contract

A future integration should state versions and licenses; input and output types; units and tolerances; permissions and data destinations; timeout, retry, cancellation, cleanup, and idempotency semantics; structured errors; and evidence fields. Tests should include public/synthetic successes and deliberate failures. Domain tools retain responsibility for calculations and formats; their invocation is not independent scientific review.

[OpenHands, Temporal, and build123d](peer-benchmark.md) are documentation references. Naming them does not establish runtime integration, inherited guarantees, partnership, or endorsement.

## Questions for future runtime work

- Which states persist, and how are updates made atomic?
- What happens to approvals and budgets when work changes or restarts?
- How are child work, cancellation, duplicate side effects, and cleanup verified?
- How is actual overlapping execution measured rather than inferred from queue depth?
- Which data is retained, exported, or removed, and under whose authority?

Answers require implementation and evidence. The current source/fixture checks do not answer these lifecycle questions.

## Controlled local Git workspace profile

The [local profile introduced in 0.2.0a1](git-workspaces.md) reuses the project workspace owner
in an independent module with only create/status/diff. It is not wired into the
CAS/callable owners, a scheduler, a permission authority, or recovery events.
Trusted cooperative local repository/filesystem assumptions remain; required
Git switches and fail-closed refusals do not create an OS sandbox.
