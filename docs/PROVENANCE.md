# Source-admission attribution and modifications

Copyright 2026 OpenDot Engineering contributors. The existing [Apache-2.0
license](../LICENSE) and [NOTICE](../NOTICE) apply to this integration code.

The optional source-admission adapter is a modified derivative of the original
Apache-2.0 OpenDot Engineering integration adapter. It retains the original
integration ownership for captured source loading, synthetic package/module
construction, canonical source-owned exports, serialized caching, and cleanup
on failure. Generalization adds explicit operator-selected roots, manifests and
exports, strict bounded schema validation, dependency-ordered flat modules,
precompilation of the captured snapshot, and narrower namespace ownership checks.

The canonical `source_audit.py` is retained unchanged. Source admission imports
its descriptor-relative file reading, relative-path checking, JSON decoding,
digest validation, and rejection helpers. Source-lock-specific schema and text
policies remain in the admission adapter; no second filesystem implementation is
introduced. Future helper changes require coordinated review in that owner.

The adapter header describes the generic operator-pinned boundary. The source
candidate retains all executable behavior of the reviewed adapter. Inclusion in
this unreleased package does not establish public release acceptance, consumer
compatibility, or scientific acceptance. The [current integration checks](source-admission-verification.md)
state the status.

All executable source-admission fixtures are newly authored synthetic modules in
the test suite. No external implementation, source revision pin, backend profile,
research data, or generated acceptance receipt is bundled. Separately supplied
source remains subject to its own licenses, permissions, review, and acceptance.

## Optional simulated-lab addition

The fake-only simulation integration adds original Apache-2.0 adapter and worker
code, synthetic tests, a dependency recipe, and documentation. The source-audit
and qualification-record algorithms remain unchanged; no source loader, runtime
owner, hardware transport, or private backend implementation is introduced.
Direct optional dependency versions and separately installed license attribution
are in [NOTICE](../NOTICE) and the [simulation guide](simulated-lab.md). No upstream
dependency implementation is vendored.

## Canonical local artifact closure (0.2.0a0 candidate)

The canonical `core.artifacts` implementation and sole `ArtifactRef` definition
in `core.contracts` are extracted from the existing project implementation under
the project's Apache-2.0 authorization. Review of this specific standard-library
closure found no separately owned dependency implementation or additional
third-party attribution in these files. This is a bounded source/rights review,
not a certification of unrelated source or all release obligations. The existing
project copyright notice and full Apache-2.0 license are retained.

Changes are limited to module placement, the minimal contract closure, canonical
re-exports, extraction notices, and clarification of the store's docstring. The
store methods, reference fields, and validator behavior are retained. Public
synthetic examples/tests and boundary documentation are new. This source adds no
broader contract module, private package initializer, execution harness, original
source manifest, runtime compatibility patch, or private operational data.

The source snapshot has one store and one reference class. Existing consumers
remain on their previous owner until a separate coordinated migration is accepted.
The [decision](decisions/002-canonical-artifact-core.md) and
[contract](canonical-artifacts.md) make that limitation explicit.

## Integrated callable/artifact core (0.2.0a0)

The callable-only owner and its six contracts are incorporated with the exact
reviewed public-candidate bytes; see [callable changes](callable-execution.md).
The canonical artifact implementation, reference contract, and exports are also
retained byte-for-byte from their reviewed public candidate. The small
[composition example](../examples/callable-artifacts/README.md) is newly authored
Apache-2.0 integration code and introduces no new execution/storage owner.
Both cores belong to this single distribution. Component review does not itself
approve this combined source or imply that old consumers have migrated.

## Controlled local Git workspace extraction (0.2.0a1)

The existing project GitWorkspaceManager and its GitReceipt/GitWorkspace data
contracts are reused under the project owner's explicit Apache-2.0 migration
authorization. The fixed source tree did not itself contain a root Apache
LICENSE or NOTICE; authorization, rather than a claim about that historical
tree, is the basis for this bounded transfer. Review found only standard-library
imports in this owner, no bundled third-party implementation, and no file-level
additional third-party notice. This is not a certification of unrelated source
or third-party rights. Existing target LICENSE, copyright, and NOTICE remain.

The owner's public module placement and safe profile are modified: a resolved
system Git executable and controlled environment, hooks/fsmonitor/external-diff/
textconv controls, conservative config/attributes/filter/submodule/object-store
refusals, fixed base OIDs, no retry/reuse, live-manager record binding and path/
branch/common-directory validation. Commit/remove and their recursive-delete
fallback are omitted, not preserved behind a hidden export. Receipt field order
and ok semantics are retained; base_commit is appended to the workspace record.
New tests, the disposable example, and documentation are newly authored.

The only observed receipt consumer constructs five positional fields and reads
ok/stdout; no consumer implementation is included or migrated. Search coverage
was incomplete, so this is not an exhaustive consumer-closure proof. No private
initializer, conftest, original source manifest, source repository identity,
external reference implementation, scheduler, runtime, or recovery protocol is
bundled. Git remains a separately installed executable with its own license.

## Canonical agent metadata closure (0.2.0a2)

`Capability` and `AgentManifest` are a modified extraction of two existing
project dataclasses under the project owner's explicit Apache-2.0 migration
authorization. The source snapshot did not itself supply a root Apache LICENSE
or NOTICE; that authorization is the basis for this bounded transfer. Review of
this closure found only standard-library/builtin dependencies and no bundled
third-party implementation or file-level additional third-party notice. This
is not a certification of unrelated source or all release obligations.

The canonical owner is the existing `core.contracts` module; public `core`
exports retain object identity. Class names, field order, annotations, defaults,
and frozen declarations are retained. Validation is deliberately stricter for
invalid strings, sets, numeric values, overlap, and turn limits as documented in
[the API guide](agent-contracts.md). Validation remains explicit. The existing
`ArtifactRef` body and other implementation owners are unchanged. One inherited
test's class-list assertion is updated for this admitted closure; no historical
test result is relabeled as a new-candidate run. New tests/examples are original
synthetic Apache-2.0 work.

No original package initializer, broader contracts, resource registry, generic
serialization helper, runtime harness, private source identity, original source
manifest, operational data, or consumer implementation is bundled. No consumer
migration, execution enforcement, or publication is claimed. See
[ADR 003](decisions/003-agent-metadata-contracts.md).
