# Fixed CAD → mesh → thermal workflow

[中文](README.zh-CN.md)

One source-only command composes the existing geometry, Gmsh mesh and CalculiX
thermal adapters for a public synthetic bar. It replaces the three manual adapter
commands without adding a solver, scheduler, process wrapper or artifact store.

The qualification paragraph below retains the historical full-workflow preparation
status. A later, separate [native geometry reference](native-geometry-reference/README.md)
provides one reviewed static synthetic STEP and a new public evidence summary:
one CAD-only export/reimport plus an independently implemented check using the same
Open CASCADE stack. It does not qualify the full CAD/mesh/thermal workflow. That
reference's three fixed files are the sole reviewed static exception to this
page's generated-output exclusion; arbitrary runtime outputs, raw receipts,
dependency wheels and native binaries still do not belong in the source tree.

**Qualification for this candidate is fabricated contract tests only. Actual CAD,
Gmsh and CalculiX execution has not been performed.** The preparation environment
has Python 3.12.14 and a separate existing pytest 9.1.1 environment. The default
Python has build123d 0.10.0 and OCP 7.8.1.1.post1 metadata; native usability was
not tested. That interpreter has no Gmsh metadata, the six inspected workspace
environments have no CAD/Gmsh metadata, and no Gmsh/CalculiX is found on PATH.
No complete approved native environment has been identified. Historical dependency
references are not evidence that an executable is available.
There is no fixture-mode native success and no automatic installation.

## Inspect the fixed plan without native software

From this source checkout (the example is not a package-root command):

```sh
PYTHONPATH=src python examples/cad_cae/thermal_workflow.py plan
```

This reads current-interpreter distribution metadata without importing native
packages. The result is `NOT_EXECUTED`. Gmsh native and solver versions remain
`NOT_CHECKED`; metadata presence alone does not establish a usable native runtime.

The only case is a 0.2 × 0.02 × 0.003 m bar, exported as 200 × 20 × 3 mm STEP,
converted to SI before meshing, with 20 × 4 × 2 linear HEX8 subdivisions:

- 315 nodes, 160 volume cells, 256 boundary QUAD4 cells and 1,280 flux IP rows
- Volume 0.000012 m³, synthetic conductivity 10 W/(m K)
- X_MIN = 300 K, X_MAX = 400 K; four other faces adiabatic, no heat source
- Exact T(x) = 300 + 500 x K (x in meters), q = (−5000, 0, 0) W/m²
- External thermal end reactions −0.3 W and +0.3 W, with positive supplying heat

## Run once, only in a separately approved existing environment

The command below is a template, not a command executed for this candidate. Replace
all three executable paths with explicitly reviewed existing paths. No environment
discovery, download, installation or upgrade is performed. The calling CAD Python
requires build123d **0.10.0** and CadQuery-OCP **7.8.1.1.post1**. The separate Gmsh
Python requires wrapper and loaded library **4.15.2**. CalculiX must be **2.23**.
Linux and Python 3.12 are the retained reference platform. Native library identity,
full dependency closure and licensing still need their own execution review.

```sh
PYTHONPATH=src /approved/cad/bin/python examples/cad_cae/thermal_workflow.py run \
  /new/output/thermal-workflow \
  --gmsh-python /approved/gmsh/bin/python --solver /approved/bin/ccx_2.23
```

The output directory must not exist, must be outside this checkout, and cannot
have symlinked parents. Executable options must be absolute existing executable
paths supplied by the operator. Optional CadQuery comparison is not requested.

The consumer calls `export_beam`, `mesh_beam` and `run_thermal` exactly once each,
with canonical validation between stages. Any exception stops dependent stages;
there is no retry, fallback, resume, cleanup or rollback. Earlier valid packs and
the failing adapter's diagnostics remain. Existing output, including empty output,
is refused. Use a new directory only after understanding any failure.

Results are retained in `cad/`, `mesh/` and `thermal/`. The existing owners create
their original manifests/receipts and raw STEP/MSH/deck/DAT/STA/CVG/log outputs.
The thermal pack also contains parsed-result CSVs and labeled SVGs. The consumer's
summary is computed on stdout; it does not introduce another acceptance receipt.

## Reverify without native software

```sh
PYTHONPATH=src python examples/cad_cae/thermal_workflow.py verify \
  /existing/output/thermal-workflow
```

Verification is read-only. It invokes all original pack verifiers, requires the
fixed dimensions/divisions/linear recipe/timeouts, requires the v2 mesh's recorded
`VERIFIED_AT_EXECUTION` identity, compares exact CAD input bytes against mesh copies,
and compares the full exact mesh pack against the thermal snapshot. It rereads
and hashes fixed files to reject ordinary persistent mutation. Consumer reads use
the canonical bounded no-symlink reader with a 32-MiB per-file ceiling. Original
verifier implementations remain unchanged; trusted cooperative stable files are
required and hostile concurrent mutation is not solved.

Raw numerical verification checks all nodal temperatures (absolute tolerance
0.0001 K), all eight-IP flux vectors per cell (0.001 W/m²), end reaction sums,
free-node reactions and global balance (1e-7 W), plus actual final solver
completion/convergence records and exact deck/figure identity. It does **not**
check each constrained-node reaction distribution: equal/opposite errors at the
same end can cancel in its sum. A one-grid linear-field pass is not convergence,
mesh independence, material validation or a physical experiment.

The result is `RECORDED_WORKFLOW_CONSISTENCY_PASS`. Recorded identity is not an
independent assertion that native execution happened; fabricated coherent records
can also pass. Integrity hashes are not authentication against a party rewriting
all evidence. `scientific_accepted` and `device_control_authorized` stay false;
physical validation is `NOT_PERFORMED`, independent review `NOT_EVALUATED`, and
mesh independence `NOT_ESTABLISHED`. A saved summary is never trusted as input.

## Resource and permission boundaries

- CAD runs in the calling process with no added wall/CPU/file-size/thread policy
- Mesh and solver each request 60 s wall time and one configured thread; their
  unchanged owners preserve the lower finite inherited CPU cap or 300 s
- The existing mesh worker preserves lower inherited file-size caps or 32 MiB;
  the existing solver hook sets 32 MiB without preserving a lower inherited cap
- No overall workflow deadline, memory/aggregate-output cap, hostile-child sandbox,
  process-tree guarantee, crash transaction or measured CPU/core-hour claim
- Gmsh v2's existing identity mechanism normally reads `/proc/self/maps`; this
  preparation does not run it. Native execution and that scope need separate approval
- Native packs may include local paths. Review packs separately before sharing;
  this example does not redact or authorize publication

## Portable contract tests

```sh
PYTHONPATH=src python -m pytest tests/test_cad_thermal_workflow.py -q
```

Tests replace native boundaries with explicitly fabricated data while traversing
unchanged adapter bodies and canonical raw-pack verifiers. They cover fixed
counts/analytical constants, units/connectivity/boundaries, resealed deck/flux/CVG
failures, unrelated-but-individually-valid lineage, legacy identity refusal,
early failure with no dependent dispatch, output preservation and read-only replay.
They never import native CAD/Gmsh or run a solver, identity probe, refinement or
process-lifetime test. Passing these tests does not close the actual native-run gate.

See the [geometry](../../docs/cad-geometry.md), [mesh](../../docs/cad-mesh.md) and
[thermal](../../docs/thermal-conduction.md) owner contracts for exact inherited
behavior and remaining qualification limits.

## Geometry-only beam recipe (existing adapter)

`beam.parameters.json` contains synthetic dimensions in **meters**. The optional
build123d adapter converts once to millimeters and explicitly exports STEP in mm.
Default dimensions are 200 × 20 × 3 mm, volume 12,000 mm³ = 0.000012 m³.

From a checkout in a separate CAD environment with build123d 0.10.0 installed:

```sh
PYTHONPATH=src python -m opendot_engineering.executors.geometry \
  /tmp/opendot-geometry-example --cadquery-compatibility
```

The optional compatibility flag additionally requires CadQuery; omit it for a
build123d-only run. Choose a new directory outside the repository. Existing
directories, including empty ones, are refused. No generated STEP, receipts,
dependency wheels, or native binaries belong in this source directory.

Programmatic parameters:

```python
import json
from pathlib import Path
from opendot_engineering.executors.geometry import export_beam

parameters = json.loads(Path("examples/cad_cae/beam.parameters.json").read_text())
receipt = export_beam(parameters, Path("/tmp/opendot-geometry-programmatic"))
```

This is a deterministic geometry recipe and STEP compatibility check. No mesh,
FEA, physical test, material choice, strength claim or scientific acceptance is
included. See [the geometry contract](../../docs/cad-geometry.md).
