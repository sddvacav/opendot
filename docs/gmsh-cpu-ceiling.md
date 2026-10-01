# Gmsh worker inherited CPU ceiling

This component is integrated into a separately frozen resource-qualified
**unreleased 0.3.0a1** successor. It changes only the existing Gmsh worker's CPU
limit setup, with no package-version, default-verifier, or solver-policy change.
The [current verification scope](structural-v2-candidate-verification.md) records
new source/artifact identities; prior accepted artifacts are retained unchanged.

Before importing Gmsh, the worker reads its inherited CPU soft and hard limits
and sets both to the minimum of 300 seconds and all finite inherited values.
The policy is identical to the already accepted solver callback: it does not
numerically increase either finite inherited CPU cap. Unlimited values are
recognized by comparison with `resource.RLIM_INFINITY`, not a guessed number.
Zero remains numerically zero; kernel timing and zero semantics are not verified.

The existing unconditional 32-MiB file-size limit remains first. It can still
attempt to increase a lower inherited file-size cap and may fail before CPU
setup. That separate limitation is unchanged. Import, query, and set failures
propagate before the Gmsh import, without retry or fallback.

`tests/test_gmsh_cpu_ceiling.py` executes only the source AST prefix before the
Gmsh import, with fake resource calls and an import-boundary sentinel. It covers
unlimited, finite, zero, boundary, alternate-sentinel, and exception-order cases,
plus the unchanged file-size limitation. These tests neither import the worker
or Gmsh nor exercise native processes, real resource calls, or kernel enforcement.
The test's two source-path constants must point to the actual installed worker
and solver module when used in a separately declared installed-package run.

The existing mesh adapter dynamically records the actual worker's SHA-256 in
the recipe's source identity. Future mesh creation must therefore record the
new worker hash. Earlier receipts and native outputs keep their original hashes;
this change does not retroactively rebind them or claim native execution coverage.
Independent review and separate run authorization remain required before native
use. No sandbox, total-job CPU budget, wall-time, physical-validity, or scientific
acceptance claim follows from this CPU setup change.
