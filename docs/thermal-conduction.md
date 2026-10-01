# Optional external CalculiX steady-conduction benchmark

`opendot_engineering.executors.thermal_conduction` is a bounded, standard-library
adapter to an **existing, explicitly configured CalculiX 2.23 executable**. It
consumes verified `mesh.synthetic_beam.hex8.v1` or `.v2` artifact packs. Historical
v1 mesh geometry remains usable numerical evidence, but its loaded Gmsh native
identity is `NOT_VERIFIED`; numerical verification never upgrades that provenance.
New meshes use v2 with wrapper/native identity captured at execution. It adds no
solver, mesh generator, scheduler, runtime, database or physical-device owner.
No installation, upgrade, remote execution or solver redistribution occurs.

## Precisely scoped numerical question

Does this actual saved structured HEX8 bar, translated without changing its
coordinates, node IDs, element IDs or local node order, reproduce the elementary
steady one-dimensional conduction solution? This is a synthetic mathematical
verification case, not a material characterization, physical experiment,
engineering safety approval or broader scientific claim.

- Coordinates: meters; geometry dimensions come from the verified mesh recipe
- Synthetic homogeneous isotropic conductivity: 10 W/(m K), constant
- X_MIN temperature: 300 K; X_MAX temperature: 400 K
- Other four faces: adiabatic natural boundaries, with no applied surface flux
- No heat source, convection, radiation, contact or temperature-dependent property
- CalculiX DC3D8, full eight-point integration; temperature degree of freedom 11
- Steady state only; no density/specific heat or transient claim

The analytical oracle is T(x) = 300 + 100 x/L K and q = (-1000/L, 0, 0) W/m².
For the 0.2 × 0.02 × 0.003 m default bar, qx = -5000 W/m² and the external
thermal reactions are -0.3 W at X_MIN and +0.3 W at X_MAX. A positive reaction
supplies heat. Heat leaves at the cold end and enters at the hot end.

The linear temperature field is exactly representable by this element family.
Passing on one or two grids is therefore **not evidence of mesh independence**,
a convergence rate or accuracy for bending, nonlinear fields or arbitrary meshes.
The earlier C3D20 mechanical spike is not reused as DC3D8 evidence.

## API and execution

```python
from opendot_engineering.executors.thermal_conduction import (
    run_thermal, verify_thermal_artifacts,
)
receipt = run_thermal(
    '/path/to/verified-mesh', '/path/to/new-thermal-output',
    solver_executable='/path/to/installed/ccx_2.23', timeout_s=60,
)
verified = verify_thermal_artifacts('/path/to/new-thermal-output')
```

```sh
PYTHONPATH=src python -m opendot_engineering.executors.thermal_conduction \
  /path/to/verified-mesh /path/to/new-thermal-output \
  --solver /path/to/installed/ccx_2.23 --timeout-s 60
```

Any compatibility library path must be configured explicitly by the caller in
LD_LIBRARY_PATH. Executable and inherited library environment are trusted local
configuration; neither comes from CAD/mesh metadata. The existing environment is
preserved. No executable or shared library is copied into a receipt pack.

Unix only: the external process runs without a shell in a new process group,
with 1–300 s caller wall timeout, 300 s CPU limit and 32 MiB per-file output
limit. The timeout kills and waits for the process group. The case is capped at
10,000 elements. OpenMP, OpenBLAS, MKL and CalculiX result/equation-solver thread
environment variables are set to 1. Solver CPU-count messages are checked too.
These are configured limits, not measured CPU-core-hours or a hostile-code
sandbox. Memory and aggregate directory size are not OS-limited. The Unix
pre-exec resource hook is intended for a single-threaded CLI/process, not a
multithreaded application launcher.

## Verification and publication

1. Invoke the existing mesh verifier, snapshot its complete fixed artifact pack,
   recheck exact byte bindings, and verify the snapshot again
2. Read saved mesh coordinates/connectivity/physical end-face regions; emit the
   exact DC3D8 mapping and prescribed thermal deck, retaining IDs and ordering
3. Run the installed executable externally; capture its hash before and after,
   command, version from actual log, bounded log/output and monotonic wall time
4. Require successful process completion, no solver error/warning, complete STA
   step at time 1, sequential CVG iterations agreeing with STA, and final log
   convergence. The stricter benchmark CVG gate requires final residual flux and
   temperature correction each <= 1e-5 percent
5. Parse actual `thermal.dat` NT (all nodal temperatures), RFL (all external
   concentrated heat sources), and HFL (all eight integration-point flux vectors
   per element). Reject missing/duplicate/nonfinite/wrong IDs or result times
6. Independently compare each computed temperature and flux with the analytical
   field, check both end temperatures, both summed thermal reactions, free-node
   reactions and global energy balance
7. Generate CSV/SVG figures only from the parsed results, with separately labeled
   analytical reference; regeneration must exactly match stored CSV/SVG bytes
8. Stage manifest and receipt; publish the manifest then authoritative PASS
   receipt last. Reverify before returning

Temperature absolute tolerance is 0.0001 K. Flux-component tolerance is
0.001 W/m². End-sum/free-node reaction and global energy-balance tolerances are
1e-7 W. These accommodate printed DAT precision for this bounded synthetic
recipe; they are numerical checks, not physical uncertainty estimates.

No external source loads are present, so RFL values are boundary reactions.
HFL values are integration-point heat-flux vectors, not extrapolated nodal data.
The flux figure positions each integration-point result at its element centroid
for readability, labels that convention, and retains element/integration-point
identities and all vector components in CSV. The oracle checks every vector.
The FRD, 12d and spooles diagnostic files are preserved and hash-bound but are
not independently interpreted as scientific evidence; DAT, STA, CVG and log
are the acceptance inputs.

The complete mesh pack is included under `mesh/`; raw deck/output/log, normalized
recipe, oracle result, temperature/flux CSV and SVG files are manifest-bound.
The receipt separately records the figure-generation source hash, allowing plots
to be refreshed from preserved raw results without changing the original solver
execution source binding. The receipt binds adapter source hash, Git commit/worktree state, mesh/CAD
lineage, executable hash, version, command, limits and measured wall time. A dirty
base commit does not claim to contain uncommitted source. Native libraries and
transitive environment are not a complete lock or SBOM. A previously produced
pack can be checked without running its executable, but this does not attest that
the currently available executable has that historical hash.
New source records verify this thermal adapter's own Git membership and keep
`worktree` null; uncertain context is hash-only. The shared
[source-provenance boundary](cad-geometry.md#evidence-and-deterministic-behavior)
also applies to uniform-source runs. Historical copied packs and solver paths
still require independent export review.

Output must be a new directory with nonsymlink parents. Handled failures retain
`failure.json` and diagnostic files but remove receipt/manifest/pending success
files. A lone receipt or pending publication is never sufficient. Atomic rename
is used; crash durability/fsync and malicious concurrent-writer protection are
not claimed. Coherently rewriting every artifact can forge evidence; immutable
caller-owned storage is needed for stronger provenance.

## Tests

```sh
PYTHONPATH=src python -m pytest tests/test_thermal_conduction.py -q
OPENDOT_TEST_MESH_PACK=/path/to/verified-default-mesh \
OPENDOT_TEST_CCX=/path/to/installed/ccx_2.23 \
PYTHONPATH=src python -m pytest tests/test_thermal_conduction.py -q
```

Pure tests need no solver. Integration tests are explicitly skipped without both
configured paths and are designed for the default beam dimensions. With real
CalculiX enabled they cover actual solving, ordinary/resealed artifact tampering,
wrong BC/deck identity, wrong thermal field/flux, false metadata, nonconverged or
missing outputs, process timeout cleanup, existing-output refusal and incomplete
receipt publication. Test fixtures and injected failure processes are explicitly
not presented as solver evidence. Generated files stay outside the source tree.

## Official semantics and licensing

The retained implementation references the official [CalculiX 2.23 manual](https://www.dhondt.de/ccx_2.23.pdf):

- Section 7.17: isotropic conductivity and its dimensional units
- Sections 6.2.1 and 7.50: C3D8 ordering/full integration; DC3D8 compatibility name
- Section 7.4: temperature boundary degree of freedom 11
- Section 7.53: HFL integration-point output through EL PRINT
- Section 7.73: HEAT TRANSFER, STEADY STATE and final loading
- Section 7.99: NODE PRINT NT and RFL output in DAT

The official [CalculiX project](https://www.dhondt.de/) distributes the solver
under GPL terms. A subprocess boundary is not licensing clearance. No solver
binary, native library or upstream source is added to this repository; any future
binary/container distribution requires its own version-specific license, notice
and SBOM review. This source-only adapter does not resolve those obligations.
