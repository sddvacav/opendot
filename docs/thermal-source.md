# Bounded synthetic uniform-source conduction

This opt-in recipe extends the existing external CalculiX adapter. The default
linear recipe and its historical verifier remain unchanged. Use the existing
installed CalculiX 2.23; no native install, user subroutine or new solver is added.
New source runs use `thermal.synthetic_uniform_source.dc3d8.v2`. Existing v1
source packs remain verifiable under their original end-sum reaction contract;
the runner cannot create new v1 packs. The stronger v2 report is never retrofitted
into old solver evidence.

## Fixed physics and units

- Verified SI bar: 0.2 × 0.02 × 0.003 m, affine structured DC3D8
- Synthetic constant isotropic conductivity: 10 W/(m K)
- Synthetic uniform volumetric source Q: 50,000 W/m³
- Both x ends: 300 K; all other faces: natural adiabatic boundaries
- Steady state; no density, transient, phase change, laser model or material-qualification claim
- Canonical step card: `*DFLUX` / `BODY,BF,50000.`

The continuum solution is T=300+Qx(L−x)/(2k), q=(Q(x−L/2),0,0).
Peak temperature is 325 K, total source power 0.6 W, and each constrained end
removes 0.3 W. This is numerical verification, not physical validation.

## Why nodal agreement is insufficient

The uniform mesh can reproduce exact quadratic nodal temperatures, but its Q1
interpolation is piecewise linear. The oracle reconstructs that field from actual
NT and integrates squared error with 3×3×3 Gauss quadrature. Two-point temperature
quadrature underintegrates the quartic squared error and is deliberately excluded.

For x spacing h, the independently derived volume-normalized RMS errors are:

- Temperature: Qh²/(2k√30), in K
- Heat flux: Qh/√12, in W/m²

For Nx=20 and 40, these are 0.04564354646/0.01141088661 K and
144.3375673/72.16878365 W/m². Nonzero errors are required. Comparing two verified
packs with refinement factor two must give orders near 2 and 1. This qualifies
only this uniform-source structured recipe, not arbitrary-mesh accuracy or
general mesh independence. The per-pack receipt retains `mesh_independence=NOT_EVALUATED`.

The deck requests HFL and COORD in EL PRINT. Printed IP coordinates are checked
against the official numbered 2×2×2 scheme mapped through actual connectivity,
including permitted positive axis permutations. HFL is compared both to the exact
discrete element slope and to the continuum at the true IP, never at the centroid.
Temperature CSV retains parsed nodes and all reconstructed three-point quadrature
samples. Flux CSV retains every raw vector and its printed true IP coordinate.

## RFL correction and conservation

CalculiX prints RFL from fn(0,node), assembled as −∫grad(N)·q dV. With a body source
this is K·T, not a pure constrained reaction. Independently assemble the consistent
load b_i=Σadjacent Q V_e/8, then compute r_i=RFL_i−b_i. Require zero corrected free
reactions, −0.3 W at each end, source total 0.6 W, and Σr+QV=0. Raw RFL end sums
are −0.285 W for Nx20 and −0.2925 W for Nx40; their change is not nonconvergence.
Raw ΣRFL=0 alone does not establish the heat-generation balance.

Version 2 also checks each constrained node independently. Its tributary area is
the sum of one quarter of each adjacent boundary rectangle's area. The expected
corrected reaction is −Q L/2 times that area, at either end. End faces are found
from actual x-plane coordinates and the verified end-node sets; a four-corner
y/z rectangle, nonduplicated coverage and total area are required. No local
HEX8 face number or node-order assumption is used, so the admitted positive axis
permutations are supported. Ambiguous or incomplete mappings fail closed.
The existing 1e−7 W reaction tolerance remains unchanged. The report records the
new gate and maximum per-node error, while retaining free-node, end-sum and total
power checks. Tests reject a resealed +0.001/−0.001 W exchange between two nodes
on the same end, even though their end sum and global balance are unchanged.

## Execution and verification

```sh
PYTHONPATH=src python -m opendot_engineering.executors.thermal_conduction \
  /verified/mesh /new/source-output --solver /existing/ccx_2.23 \
  --benchmark uniform_source --timeout-s 60
```

The shared adapter retains verified mesh snapshot, bounded external subprocess,
raw DAT/STA/CVG/log checks, fixed deck identity, manifest binding and receipt-last
publication. Source recipe, material, load, BC and units are exact, not arbitrary
input. Receipts additionally bind the source-oracle module. No original evidence
is overwritten. Nonfinite/missing/duplicate result data are rejected by the shared
parser. DAT precision floors are 1e−4 K, 1e−3 W/m², 1e−7 W and 1e−7 m for printed
COORD. RMS deviations allow 1e−4 K and 0.002 W/m²; these do not replace the required
nonzero analytic discretization errors or the refinement check.

```python
from pathlib import Path
import json
from opendot_engineering.executors.thermal_conduction import verify_thermal_artifacts
from opendot_engineering.executors.thermal_source import refinement_report
roots = [Path('/source/coarse'), Path('/source/refined')]
for root in roots:
    verify_thermal_artifacts(root)
print(refinement_report(*(json.loads((root/'oracle.json').read_text()) for root in roots)))
```

Pure tests do not invoke a solver. Setting `OPENDOT_TEST_SOURCE_PACK` enables
reverification and resealed negative probes on an existing real source pack;
it never starts a solve. Existing linear integration tests remain separately opt-in.
The refinement helper consumes already verified reports; it is not an artifact
authenticator and cannot establish provenance for arbitrary supplied dictionaries.

## Primary references

- [Official CalculiX 2.23 manual](https://www.dhondt.de/ccx_2.23.pdf): *DFLUX
  (uniform BF in power/volume), *EL PRINT (HFL and COORD), *NODE PRINT (RFL),
  C3D8 fully integrated brick and heat-transfer equation
- [Official 2.23 HTML manual](https://www.dhondt.de/ccx_2.23.htm.tar.bz2):
  node267, node280, node326, node28 and node181 respectively
- [Official 2.23 source](https://www.dhondt.de/ccx_2.23.src.tar.bz2):
  printoutnode.f lines 114–118; resultstherm.f lines 584–603; gauss.f gauss3d2
- [Gmsh structured grids](https://gmsh.info/doc/texinfo/#Structured-grids)

The continuum and RMS formulas are independently derived, not claimed as an
upstream test result. Source archive SHA256:
`9c88385c10fb04f5dc6c4e98027a51bebdd8aee3920e05190d6c1dd08357d6e7`.
No upstream source or binary is copied into this repository. Existing subprocess
and native-dependency licensing/SBOM limitations remain in force.
