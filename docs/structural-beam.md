# Synthetic linear-elastic cantilever: frozen benchmark contract

Pre-result protocol, 2026-09-30. This is a bounded external CalculiX benchmark,
not a new solver, physical experiment, material qualification, or strength claim.
The following physics and numerical criteria are fixed before running this case.

## Fixed case and element choice

- SI geometry: x = 0..0.2 m, y = 0..0.02 m, z = 0..0.003 m
- Synthetic isotropic elasticity: E = 210e9 Pa, Poisson ratio = 0.3
- Linear static small-displacement analysis, no gravity, temperature, contact,
  plasticity, geometric nonlinearity, MPCs, transformed coordinates, or dynamics
- Fully clamp all three translations on X_MIN
- Apply total Fz = -0.1 N as uniform transverse traction on X_MAX, represented
  by consistent bilinear face nodal loads: each rectangular face contributes
  Fz * face_area / total_end_area / 4 to each of its four nodes
- Other surfaces are traction-free; no extra end rotation constraint
- Preserve the verified Gmsh HEX8 corner node IDs and connectivity; select
  CalculiX C3D8I, its supported incompatible-mode brick, without manufacturing
  quadratic mesh provenance or implementing shape-function/solver machinery
- CalculiX 2.23 only, trusted caller-configured executable, one configured CPU,
  at most 60 s wall time and 10,000 cells per case, raw outputs retained

The official CalculiX manual describes C3D8 bending locking, recommends C3D8I
for bending with linear bricks, and says quadratic bricks generally give the
best results. This narrow affine rectangular grid is suitable for assessing
C3D8I; it is not evidence for distorted bricks, torsion, near incompressibility,
or general element quality. Version 2.23 release notes explicitly list a C3D8I
correction. C3D8 is run as a labeled diagnostic under the same accuracy bound,
not accepted merely because the process exits successfully.

## Reference and predeclared acceptance

Use Euler-Bernoulli displacement w(x) = Fz*x^2*(3L-x)/(6*E*I), I=b*h^3/12.
The end reference is -2.821869488536156e-5 m; linear strain energy is
0.5*Fz*w(L) = 1.410934744268078e-6 J. This is a slender-beam reference,
not the exact 3D elasticity solution of the fully clamped face. The ratio
L/h is 66.67; a rectangular-section shear estimate FL/(kGA), k=5/6,
is only 0.01755% of Euler-Bernoulli tip deflection. The prescribed 2% bound
allows finite-element and 3D clamp/end effects without fitting a tolerance
to measured results.

For each 20x4x2 and 40x8x4 mesh, all of the following must pass:

- Load-conjugate end displacement (sum of nodal load weights times Uz)
  agrees with the Euler-Bernoulli reference within 2% relative
- The load-conjugate displacement is negative; all displacements finite
- Max constrained displacement <= 1e-12 m
- Max displacement norm / L <= 0.01; max absolute integration-point strain
  component <= 0.001, used only as bounded small-deformation diagnostics
- Every original node has exactly one displacement and external-force result;
  every cell has its expected eight strain integration points and one energy
- Support resultant plus applied load residual, each component <= 1e-5 N
- Support moment about clamp-face centroid plus applied moment residual,
  each component <= 2e-6 N m
- Printed external forces on loaded/free nodes agree with prescribed CLOADs
  or zero, each component <= 1e-7 N
- Sum of printed per-element ELSE agrees with 0.5*sum(F_node dot U_node)
  within 1e-4 relative, with both energies positive and no negative cell energy
- Printed ELSE total also agrees with the beam-reference energy within 2%
- Solver process completes successfully, without warnings/errors and with
  expected version, completed-step/output-time evidence and CPU diagnostics

Pair-level: each axis is refined by exactly two and absolute change in weighted
end displacement / refined magnitude is <= 1%. This is a two-grid sensitivity
check only, not an asymptotic convergence order or mesh-independence proof.
Do not require monotonic convergence toward an approximate 1D reference.

## Force interpretation and narrow failure behavior

CalculiX RF is total external nodal force, including CLOADs. At the clamp,
there are no applied loads, so RF is the reaction. At X_MAX, RF must equal
the specified CLOAD, not zero. Sum RF over all nodes is the total external
force and should balance; moments use the undeformed small-strain geometry.
ELSE is whole-element internal energy; no fabricated energy inferred from
stress contours substitutes for the requested real output.

Missing/duplicate/nonfinite/time-mismatched data, altered input/mesh/BCs,
unsupported element/units, failed physics checks, timeout, nonzero exit,
false metadata, and altered figures/backing data fail closed. Failure artifacts
keep raw diagnostics and predeclared measurements, never a success receipt.
An unaccepted C3D8 locking diagnostic stays failed even if equilibrium passes.
No automatic tolerance relaxation or unbounded diagnostic retries.

## Provenance and interpretation limits

The inherited mesh verifier checks saved geometric/numerical identity and
bindings. Legacy v1 Gmsh packs lack verified native library identity. Structural receipts explicitly retain `NOT_VERIFIED` for historical
mesh-native identity; they do not upgrade it. Solver binary SHA-256 identifies
local executable bytes only, not its full dependency closure, license clearance,
or reproducible native build. Pack hashes do not authenticate a malicious
rewriter of all evidence. Configured CPU count is not measured resource use.

No maximum clamp stress or stress singularity is used for a strength claim.
Displacement figures must be produced from parsed solver data, preserve the
reference distinction, and label this synthetic small-strain case.

## Primary sources

- CalculiX User's Manual 2.21, sections 6.2.1/6.2.3, output variables,
  *STATIC, *NODE PRINT, *EL PRINT: https://www.dhondt.de/ccx_2.21.pdf
- CalculiX 2.23 release notes: https://www.dhondt.de/new_calc.htm
- Official solver and documentation entry point: https://www.dhondt.de/

The official 2.23 PDF endpoint was unavailable to the web reader during
preflight; element/output semantics were read from the official 2.21 manual
and the explicit 2.23 correction from its official release notes. Actual 2.23
output layout is checked against the bounded observed output, without changing
these physics acceptance criteria.

## Current default result and migration

The unreleased 0.3.0a1 [default v2 profile](structural-default-v2.md) additionally
requires the unchanged conditional per-element E/ELSE check after strict admission.
API/CLI verification returns schema 2 and
`CONDITIONAL_STRUCTURAL_CONSISTENCY_PASS`; comparison returns
`CONDITIONAL_STRUCTURAL_REFINEMENT_PASS`. Both retain false scientific authority.
Read archival fields through `result["artifact_receipt"]`. On-disk schema-1
receipt/recipe files are unchanged; their saved positive marker is not a current
v2 verification result. Explicit API `profile="artifact_v1"` retains historical
admission only; native creation and CLI verification do not expose this bypass.

## Adapter usage and output contract

Run from the source checkout with an explicitly selected installed CalculiX:

```sh
PYTHONPATH=src python -m opendot_engineering.executors.structural_beam run \
  /path/to/verified/coarse /new/output/coarse --solver /path/to/ccx_2.23
PYTHONPATH=src python -m opendot_engineering.executors.structural_beam run \
  /path/to/verified/refined /new/output/refined --solver /path/to/ccx_2.23
PYTHONPATH=src python -m opendot_engineering.executors.structural_beam compare \
  /new/output/coarse /new/output/refined
PYTHONPATH=src python -m opendot_engineering.executors.structural_beam verify \
  /new/output/coarse
```

The new output directory must not exist. `--element C3D8` is explicitly a
full-integration diagnostic and can never publish a success receipt. Success
packs retain input, DAT, STA, CVG, FRD, solver log, auxiliary native output,
complete verified mesh snapshot, frozen recipe, raw-derived oracle, nodal
CSV data, element energies, and deterministic SVG. The manifest
binds the receipt and artifacts; the receipt binds the input/output hashes,
using the existing receipt-last publication sequence. Failure
packs retain a failure record and hashes of available raw/derived evidence;
no success manifest or receipt survives a failure.

The shared thermal adapter remains the single external-process lifecycle,
verified snapshot, and pack-publication owner. Its job basename is the only
new subprocess option; the default stays `thermal`. Structural consistent
loads reuse the existing `thermal_source.end_node_tributary_areas` geometric
helper. Structural receipts bind every helper module used, the local source
revision/worktree state, solver executable hash, and configured CPU/wall bound.
New source records verify the structural adapter's own Git membership and retain
`worktree` as null. Uncertain context is hash-only under the shared
[source-provenance boundary](cad-geometry.md#evidence-and-deterministic-behavior).
Historical copied packs and native executable paths still require export review.

For a linear-static direct solve, the STA file records the completed single
step at time 1 and the CVG file is header-only. Requiring the nonlinear thermal
iteration history here would misinterpret a supported native procedure. The
DAT parser still requires complete U, RF, E, and ELSE blocks at final time 1.

Tests need no optional solver by default. Native tests opt in with
`OPENDOT_TEST_MESH_PACK`, `OPENDOT_TEST_REFINED_MESH_PACK`, and
`OPENDOT_TEST_CCX`; these must identify the prescribed verified grids and
trusted installed executable. Existing thermal/source tests remain unchanged.

### Newly verified mesh-native evidence

After the protocol freeze and first historical-mesh diagnostic, the existing
mesh owner gained schema v2 native-library identity verification. Structural
packs preserve its complete recorded `gmsh_runtime` and exact status from the
verified embedded mesh receipt. A legacy v1 input remains `NOT_VERIFIED`;
a new v2 input may report `VERIFIED_AT_EXECUTION` for that mesh execution.
This does not retroactively establish native identity for any older mesh run,
even when the saved mesh bytes are identical. No structural tolerance, load,
material, boundary condition, connectivity, or element choice changes.

### Shared diagnostic and elapsed-evidence gates

Both structural and thermal adapters reject standalone `ERROR` or `WARNING`
words in the native log regardless of a leading star, as well as wrong-version
or missing/duplicate completion markers. They share one elapsed-consistency
check: an accepted complete process call, measured from before creation through
wait/cleanup, must be nonnegative and no longer than its configured timeout.
No grace is added. A near-bound success may therefore be conservatively rejected.
This is an acceptance evidence bound, not proof of an operating-system hard
wall-time limit: process creation, scheduling and cleanup are not themselves
hard-bounded by Python's wait timeout. Failures retain their actual measured
elapsed diagnostic, and wall time is never converted into claimed CPU use.

## Verification status and limitations

No native structural execution is claimed for this source cut. See the
[current validation matrix](verification-status.md) for the checks performed.
The fixed criteria above are retained as contracts, not observed release results.

The Euler–Bernoulli reference remains an approximate slender-beam model. Two
accepted grids would not establish mesh independence or a convergence order,
and a synthetic numerical pass would not qualify a real material, component
strength, or physical experiment.
