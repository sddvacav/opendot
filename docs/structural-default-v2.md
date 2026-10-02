# Structural default verification v2

Current release status, 2 October 2026: this default profile is retained in the
[0.3.0a2 ALPHA prerelease](https://github.com/sddvacav/opendot/releases/tag/v0.3.0a2); it predates a2. The
[released source](https://github.com/sddvacav/opendot/commit/359f781a5aa1650ae92b1af81cf369a17c444045) and [release notes](https://github.com/sddvacav/opendot/releases/download/v0.3.0a2/RELEASE-NOTES.md) bind the exact a2 assets to scoped source, installed and independent checks.
Its intentional result-schema/status change is not backported to the frozen
**0.2.0a6** source or artifacts. The [historical successor record](structural-v2-candidate-verification.md)
retains the earlier pre-release scope; earlier a6 evidence does not accept a2.

## What the default now checks

`structural_beam.verify_structural_artifacts(directory)` first performs the
same strict artifact, exact recipe/deck, execution, identity and numerical
benchmark admission. It then requires the already-reviewed per-element
[elastic-energy check](structural-elastic-energy.md). Both public APIs share
one private strict-admission implementation and the same unchanged energy
kernel in the existing structural owner. No second parser, store, runtime or
solver owner is introduced.

The default profile is `conditional_elastic_v2`. It returns a computed envelope:

- `schema_version: "2"`
- `verification_profile: "conditional_elastic_v2"`
- `status: "CONDITIONAL_STRUCTURAL_CONSISTENCY_PASS"`
- `artifact_schema_version: "1"` and `artifact_receipt`: the exact original
  admitted receipt, retained as archival evidence rather than a new decision
- `elastic_energy`: the existing detailed component report
- `scientific_accepted: false`, `physical_validation: "NOT_PERFORMED"`,
  `independent_review: "NOT_EVALUATED"`, `mesh_independence: "NOT_ESTABLISHED"`
- `conditional_assumptions`: the fixed material/history scope, no-underflow
  `ASSUMED_NOT_VERIFIED`, and formal arithmetic error bound `NOT_PROVED`

New authority flags/statuses are constructed explicitly. Arbitrary extra
archival metadata cannot override them. The nested energy report preserves its
historical optional-API wording for compatibility; in this new default profile
its check is required. Neither nested schema-1 report is promoted to a new
scientific, physical or independent run-level approval.

Unsupported profiles, recipe/deck changes, unsupported print precision and
failed per-element consistency raise `ValueError`. Unknown or non-string
profile arguments fail before any pack read/path conversion. There is no
fallback, configurable tolerance or force-accept option. Refusal for an
unsupported profile is not a claim that its physical model is invalid.

The same limited constitutive/output assumptions apply: fixed initially
unstressed/unstrained, zero-history, no-thermal-strain isotropic C3D8I linear
static, E=210 GPa and nu=0.3. All equations, actual eight-node Jacobians, Gauss/IP
ordering, E13.6 token budgets, zero treatment and `1e-10` relative arithmetic
policy remain unchanged. The no-underflow condition is an explicit assumption,
not something the DAT can prove; there is no absolute uncertainty floor.

## Explicit historical compatibility

The keyword-only `profile="artifact_v1"` preserves exactly the former strict
admission and receipt result. It deliberately retains the known E/ELSE gap and
must be described as historical admission, not current v2 acceptance. It is
never chosen automatically. This makes the breaking default change explicit
instead of silently attaching stronger claims to an old receipt.

Migration to the current default profile:

```python
from opendot_engineering.executors.structural_beam import verify_structural_artifacts

current = verify_structural_artifacts("supported-pack")
assert current["status"] == "CONDITIONAL_STRUCTURAL_CONSISTENCY_PASS"
assert current["scientific_accepted"] is False
solver_provenance = current["artifact_receipt"]["solver"]

# Only when exact historical admission/receipt semantics are required:
historical = verify_structural_artifacts("historical-pack", profile="artifact_v1")
```

Callers that formerly read `result["solver"]`, `result["source"]` or other receipt
fields migrate to `result["artifact_receipt"]` under v2. Callers comparing the
old status/schema must migrate explicitly. Valid existing source-format packs
need no rewriting; formerly accepted inconsistent or unsupported-format packs
can no longer pass the new default. Not every external consumer is claimed to
have migrated.

## Other claim-facing routes

- CLI `verify` always uses v2; there is no quiet legacy CLI flag
- `verify_elastic_energy(directory)` preserves its existing result and
  numerical/error semantics. It calls the same private admission directly,
  avoiding recursive public verification or repeated energy-kernel evaluation
- `run_structural(...)` returns the v2 envelope through its existing final
  verifier call. There is no historical-profile bypass for native creation.
  On-disk schema-1 recipe/receipt/derived files are unchanged. If the final
  required gate fails, the existing cleanup/failure path removes acceptance
  markers; this is not a new transaction or lifecycle guarantee
- `compare_refinement(coarse, refined)` requires v2 for both inputs and returns
  schema 2 / `CONDITIONAL_STRUCTURAL_REFINEMENT_PASS`, with false science
  authority and explicit conditional assumptions. Numerical comparison fields,
  thresholds and source receipt hashes remain unchanged
- `compare_refinement(coarse, refined, profile="artifact_v1")` preserves the
  exact historical comparison result/status. Its compatibility profile is also
  validated before reads and is never a fallback. CLI `compare` always uses v2

A stored positive receipt marker alone is not a v2 verification result. This
component never rewrites, migrates, reseals or retroactively approves old packs.
It does not change frozen a6 default behavior, new native execution permissions,
physical validation, material generality or mesh-independence claims.

## Verification scopes

New tests use fully synthetic, admitted coarse/refined packs plus the existing
analytic energy fixtures. They cover profile types, strict-before-energy
ordering, exactly one kernel call, optional-result compatibility, archival
metadata authority, zero/half strain, wrong shear factors, per-element
cancellation, unsupported precision/physics, CLI output/refusal, comparison
and injected generation failure cleanup without executing a native solver.

Historical fixture tests keep their old assertions and explicitly request
`artifact_v1` where that is the tested contract. Their default coarse mesh,
strain values and receipt thresholds are not refitted. A test-only divisions
parameter permits an additional true refined analytic fixture while preserving
the original default generator behavior.

Any cached genuine native pack replay is output-only and separately recorded;
it does not establish a new solve. Author tests, independent review, installed
acceptance, successor integration and publication remain separate scopes. The
actual a2 release disposition is linked above; this profile implies no score
transfer or broader scientific/native acceptance.
