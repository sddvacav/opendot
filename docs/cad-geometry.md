# Optional build123d geometry adapter

## Scope and ownership

`opendot_engineering.executors.geometry` is a bounded, deterministic geometry
recipe adapter. build123d is the default CAD-as-code owner and delegates geometry
to the existing Open CASCADE kernel through CadQuery-OCP. This module adds no
kernel, solver, scheduler, agent runtime, remote executor or physical-device
control. CadQuery is an optional STEP compatibility reader, not a second geometry
generation/runtime owner.

The one supported recipe, `geometry.synthetic_beam.v1`, creates a synthetic
rectangular beam. It verifies its topology, analytical volume, bounding box and
STEP round trip. It does **not** establish full CAD/CAE execution, meshing, FEA,
material suitability, strength, manufacturing readiness, physical validation or
scientific acceptance. The receipt states these limits explicitly.

## API and SI/mm contract

```python
from opendot_engineering.executors.geometry import export_beam, verify_artifacts

receipt = export_beam(
    {"length_m": 0.2, "width_m": 0.02, "thickness_m": 0.003},
    "/tmp/opendot-new-geometry-run",
    cadquery_compatibility=True,  # optional; defaults to False
)
verified_receipt = verify_artifacts("/tmp/opendot-new-geometry-run")
```

Input is a dictionary with only `length_m`, `width_m`, `thickness_m`. Omitted
values use the example defaults. Strings, booleans, nulls, non-finite values,
unknown keys and values outside the bounded recipe are rejected before output
creation. Inclusive ranges are:

| Parameter | Minimum (m) | Maximum (m) | Default (m) |
|---|---:|---:|---:|
| length_m | 0.05 | 0.5 | 0.2 |
| width_m | 0.005 | 0.05 | 0.02 |
| thickness_m | 0.001 | 0.01 | 0.003 |

The adapter converts meters to millimeters **once**, creates an origin-aligned
box, calls `build123d.export_step(..., unit=Unit.MM)`, and checks the actual STEP
millimeter unit declaration. The default exchange artifact is **200 × 20 × 3 mm**,
not 0.2 × 0.02 × 0.003 mm. Its volume is 12,000 mm³ = 0.000012 m³.

Both the original shape and re-imported STEP must be valid, contain one solid,
six faces, twelve edges and eight vertices, and match the analytical origin,
bounds and volume. Volume tolerance is relative 1e-9 / absolute 1e-8 mm³; coordinate
tolerance is relative 1e-10 / absolute 1e-7 mm. These are geometry-exchange
checks, not physical tolerances or manufacturing recommendations. The optional
CadQuery import repeats the checks through a different API, but shares the same
OCCT kernel; it is not an independent-kernel validation.

The output directory must be new. Existing directories (even empty ones) and
symlinked output parents are refused. Filenames are fixed; parameters cannot
provide scripts, executable paths or imported geometry. Failed generated files
remain for diagnosis with `failure.json`; success receipts/manifests are removed
on handled failure. The manifest and receipt are staged, then the manifest is
published before the authoritative PASS receipt is atomically renamed into place
last. Staged `.pending` files are not success receipts. Hard process termination
may leave partial files; crash-durability/fsync is not claimed. Only a
complete, verified manifest and receipt represent a completed artifact set.

## Optional dependencies and retained version gates

The core package retains `dependencies = []`. Module import and pure contract
tests need no CAD package; heavy imports happen only when geometry is requested.
The module fails clearly when an optional dependency is missing. It does not
auto-install or upgrade anything. Invoke the existing module entrypoint directly:

```sh
PYTHONPATH=src python -m opendot_engineering.executors.geometry \
  /tmp/opendot-new-geometry-run --cadquery-compatibility
```

The retained optional pin set specifies Python 3.12 on Linux, build123d
**0.10.0**, CadQuery-OCP **7.8.1.1.post1**, VTK **9.3.1**, NumPy **2.3.5**, and
optional CadQuery **2.7.0**. It is a historical direct-dependency reference, not
an environment installed or tested for this source cut. Native execution and
clean-environment reproduction remain unrun qualification gates.

Runtime gates currently require build123d 0.10.0 and CadQuery-OCP 7.8.1.1.post1.
Other dependency versions are recorded; different environments require tests
before support is claimed. The optional [retained pin set](../examples/cad_cae/requirements-tested.txt)
records the historical direct dependencies and OCP/VTK. It is not a complete
transitive lock, wheel-hash set or native-library SBOM. Install it only in a
**separate CAD environment**, using official registry packages; do not upgrade a
validated solver environment in place. Clean-environment recreation has not been
executed as part of this adapter task.

## Evidence and deterministic behavior

Each completed run contains:

- `beam.step`: the real exported geometry
- `parameters.json`: normalized, finite SI parameters, recipe and unit contract
- `environment.json`: exact observed Python/platform and scoped package versions
- `receipt.json`: adapter source SHA-256, Git revision/worktree state when
  available, parameter/environment/STEP hashes, original and re-imported geometry
  measurements, executed checks and explicit limitations
- `manifest.json`: required artifact names, byte sizes and SHA-256 digests,
  including the receipt

The adapter source hash covers the actual `geometry.py` bytes. Git fields are
optional local context: the resolved nearest Git worktree must match the adapter
location, and its exact relative path must be a stage-zero regular file in both
the current index and HEAD tree. An ignored or untracked installed copy under an
unrelated repository therefore records only its source hash. A nearer broken or
non-owning repository never falls through to an enclosing repository.

The geometry, mesh, thermal and structural routes share this one helper and each
passes its own adapter file. Git subprocesses discard inherited `GIT_*` variables
and disable global/system config, hooks, fsmonitor, optional locks, replacement
objects and submodule traversal. Repositories configuring executable clean or
process filters fall back to hash-only rather than executing those commands.
Failed or uncertain root/membership/state checks also leave repository fields
null. `revision_status` distinguishes absent Git context (`UNAVAILABLE`), failed
Git probes (`GIT_UNAVAILABLE_SOURCE_HASH_RECORDED`), unverified context
(`GIT_UNVERIFIED_SOURCE_HASH_RECORDED`) and recorded local context
(`RECORDED_WITH_WORKTREE_STATE`).

For verified membership, changed raw adapter bytes or index/HEAD differences
force a dirty result even if Git status hides or normalizes the change. This is
conservative for line-ending normalization. The base commit does not claim to
contain uncommitted bytes. New source records retain the `worktree` key as null;
no absolute worktree path is emitted. Historical receipts are unchanged and
remain readable. Other native provenance fields can still contain paths and
need separate export review. Local membership, including a deliberately tracked
vendored copy, does not authenticate upstream authorship or scientific validity.
These checks do not provide an atomic snapshot against concurrent repository
mutation or a sandbox for untrusted Git installations.

`verify_artifacts` rejects missing entries, digest mismatches, artifact symlinks,
inconsistent receipt bindings, wrong units, unsupported tested backend versions
and inconsistent recorded geometry. It does not re-run CAD, provide cryptographic
signatures or protect against a malicious actor who can rewrite the entire
receipt and manifest. Caller-owned immutable storage is needed for stronger
provenance and concurrency protection.

The STEP metadata timestamp is fixed to `2000-01-01T00:00:00` solely to make
same-environment exports byte-repeatable. Actual execution time is separately
recorded in UTC. Tests compare repeated STEP bytes/hashes as well as geometric
equivalence. A single-run receipt states its repeat test was **not run by that
invocation**. Repeated-run test evidence is separate. Geometric equivalence does
not imply byte equality across platforms or package releases; neither is promised
without further tests. Receipts themselves include actual times and need not be
byte-identical.

## Tests and remaining gaps

```sh
PYTHONPATH=src python -m pytest tests/test_geometry.py -q
PYTHONPATH=src python -m pytest -q
```

In a core-only environment, CAD integration cases are explicitly skipped while
parameter, lazy-import, unit, output-refusal and contract tests still run. When explicitly configured, integration cases exercise real build123d and CadQuery,
parameter changes, roundtrip topology/volume/bounds, deterministic STEP bytes,
bad unit scales, non-finite data, corrupt manifests, symlinks and failed exports.
Optional packages are never installed by tests.

Remaining gaps: clean isolated install/lock verification, additional supported
platforms, other CAD versions and shapes, independent-kernel comparison, robust
upstream process isolation/time limits, complete transitive/native SBOM and
license review, and all downstream CAD/CAE/scientific acceptance. No generated
evidence, solver binaries, wheels, private upstream code or user research data is
included in Git by this task.

## Official sources and licensing caveats

Retained official API and licensing references (no native environment was
inspected or executed for this source cut):

- [build123d 0.10.0 export/import API](https://build123d.readthedocs.io/en/v0.10.0/import_export.html)
- [build123d 0.10.0 dependency declarations](https://github.com/gumyr/build123d/blob/v0.10.0/pyproject.toml)
- [build123d official project and Apache-2.0 license notice](https://github.com/gumyr/build123d)
- [CadQuery-OCP wrapper license](https://github.com/CadQuery/OCP/blob/master/LICENSE)
- [Open CASCADE licensing](https://occt3d.com/open-cascade-technology/index.html)

build123d and the wrapper are Apache-2.0, while the underlying Open CASCADE library
uses LGPL 2.1 with an additional exception. The wrapper's license does not
relicense its native dependencies. VTK, NumPy, bundled numerical/native runtimes,
and other transitive packages have their own notices and obligations. Review
the exact installed distributions and bundled libraries before use or sharing.
Optional execution or process separation is not a blanket redistribution exemption. Any later wheel,
container or binary distribution needs a version-specific SBOM and license/notice
review. No CAD/native/solver binaries are distributed by this source-only adapter.
