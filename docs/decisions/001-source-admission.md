# ADR 001: Optional explicit source admission

Date: 2026-10-01 UTC. Status: local integration candidate; independent integrated
artifact review and a public release decision remain open.

## Decision

Allow the reviewed `SourceLock` flat-module adapter within this bounded package.
The operator explicitly supplies an approved absolute root, a relative reviewed
manifest, and its independently trusted SHA-256. The manifest names every module,
its digest, dependency order, and named exports. The adapter verifies and captures
all bytes, precompiles the snapshot, and returns the original exported objects.
It does not discover a backend, run at import time, infer runtime roles, or wrap
those objects' behavior. Synthetic executable fixtures belong only in tests.

The existing source-audit module remains the single unchanged owner of shared
filesystem and JSON parsing helpers. Existing Apache ownership is retained in
[the attribution record](../PROVENANCE.md).

## Consequences and limits

This is an optional trusted-code admission boundary, not a scheduler, agent
runtime, job engine, database, content-addressed store, or private implementation
copy. It grants no account authorization, source license permission, sandboxing,
scientific acceptance, or complete executable-code identity. Ordinary Python
absolute imports and side effects retain the current process's authority.

Namespace checks assume trusted, cooperative code. Rollback removes only objects
still owned by this attempt; it cannot undo external effects or safely erase
foreign replacements. Callers must reconcile a failed load before retrying it;
automatic retry is outside this decision. Original package initializers are not
executed by the adapter. Consumer compatibility and any external behavior need
separate acceptance evidence.

See [the API contract](../source-admission.md), [schema](../source-lock-schema.md),
and [integration checks](../source-admission-verification.md). This narrow
allowance does not relax the package's no-runtime and no-private-code rules.
