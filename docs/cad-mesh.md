# Optional external Gmsh beam meshing adapter

## Scope and ownership

`opendot_engineering.executors.gmsh_mesh` consumes a verified artifact pack from
`geometry.synthetic_beam.v1`. New runs use `mesh.synthetic_beam.hex8.v2` and require
both the installed Gmsh Python wrapper and loaded native library to be **4.15.2** through
`_gmsh_worker.py` in a separate, explicitly configured Python subprocess. The core
adapter imports only the standard library and the lightweight geometry contract.
No meshing kernel, solver, runtime, scheduler or artifact storage service is added.
No Gmsh/native binary or upstream source is copied into this repository.

This is a **mesh-only synthetic rectangular structured HEX8 benchmark**. It does
not execute CalculiX, apply loads/materials, evaluate displacement/stress, establish
solver convergence or mesh independence, or claim scientific/physical acceptance.
HEX8 is a deliberately bounded initial mesh family, not a suitability
recommendation for bending analysis. The earlier numerical spike used quadratic
hexahedra; its solver results do not transfer to this mesh recipe.

## Contract

```python
from opendot_engineering.executors.gmsh_mesh import mesh_beam, verify_mesh_artifacts, native_provenance
receipt = mesh_beam(
    '/path/to/verified-cad-pack', '/path/to/new-mesh-run',
    divisions=(20, 4, 2), python_executable='/path/to/existing/gmsh/python',
    timeout_s=60,
)
verified = verify_mesh_artifacts('/path/to/new-mesh-run', require_native_identity=True)
identity = native_provenance(verified)
```

The three subdivisions are integers from 1 to 100 with product at most 100,000.
The default yields 160 HEX8 cells, 315 nodes and 256 boundary QUAD4 cells. Timeout
is 1–300 seconds. New generation is Linux-only (`resource` and `/proc/self/maps`), bounds each output file to
32 MiB and CPU time to 300 seconds, and uses one Gmsh thread. The parent imposes
wall time, kills/waits for the worker on timeout, writes logs directly to a file,
and rejects oversized input/output artifacts. These bounds are not a memory
sandbox or hostile-child process-tree isolation. The helper itself launches no
children. No optional dependency is installed, upgraded or fetched automatically.

The selected Python executable and inherited environment are **trusted local
execution configuration**. They must not come from external CAD metadata. The
caller selects its installed Gmsh environment; the CAD environment need not be
loaded. User Gmsh config files are disabled. Parent imports never load Gmsh.

1. Verify CAD manifest/receipt, recorded topology, units and bounded SI parameters
2. Snapshot fixed input files and bind the exact STEP, parameter and environment
   bytes to the verified CAD receipt; reject ordinary tampering or mismatches
3. Before geometry import or generation, compare the wrapper version with native
   `General.Version`. Identify the mapped files containing `gmshInitialize` and
   `gmshOptionGetString` by their actual symbol addresses, require the same native
   file, validate its device/inode against the opened file, and SHA-256 hash that
   file and the loaded wrapper's module file. Missing identity or mismatch fails
   closed. Bind this execution identity into the v2 recipe before meshing
4. Check the STEP millimeter declaration. Set `Geometry.OCCTargetUnit = "M"`
   **before** importing it, so 200 × 20 × 3 mm becomes 0.2 × 0.02 × 0.003 m
5. Verify actual Gmsh imported CAD topology, bounds (2e-7 m absolute for OCC box
   padding) and volume (1e-8 relative), then make the transfinite linear mesh
6. Assign BODY and all six coordinate boundary identities. X_MIN/X_MAX are purely
   geometric regions; no fixed support or load is implicitly assigned
7. Write ASCII MSH 2.2, then recheck both versions and rehash both files. A changed
   runtime cannot publish success. Independently inspect the saved coordinates/connectivity
   in the parent. Require a complete unique SI grid, all expected cuboid cells,
   positive HEX8 ordering, valid QUAD4 order, six complete boundary regions and
   consistent elementary entity tags
8. Compute actual cell volumes, Jacobian determinants and signed inverse condition
   numbers from saved cuboid coordinates. Compare Gmsh min/max/sum quality and
   actual total volume with CAD. No stdout-only success claim is accepted
9. Publish manifest and PASS receipt last; verify the published pack before return

Coordinate-to-grid tolerance is 1e-10 m. The cell affine/axis-alignment tolerance
is 1e-12 m. The saved coordinate cell volume uses the three actual orthogonal edge
lengths; its Jacobian determinant is volume/8, and SICN is
`3 / sqrt(sum(edge_length**2) * sum(1/edge_length**2))`. These formulas apply only
to this axis-aligned cuboid recipe. Quality aggregate agreement tolerance is 1e-7
relative; actual volume versus CAD is 1e-8 relative. No generic curved/unstructured
or higher-order mesh quality interpretation is claimed.

## Artifacts and provenance

Each successful run contains the STEP snapshot, copied CAD receipt/manifest/
parameters, recipe, saved mesh, worker measurements, process log, mesh receipt and
manifest. Recipe/receipt bind CAD revision/worktree/source, STEP/parameter hashes,
all mesh input/output/log hashes, parent/helper source hashes, separate wrapper and
native versions, resolved file paths, byte counts and SHA-256 identities,
command, timeout, measured monotonic subprocess wall time, configured Gmsh thread
count, counts, region physical and entity tags, bounds/volume, quality,
execution time and limitations. Failure diagnostics retain elapsed subprocess time
when the process was attempted. Configured threads are not measured CPU use; CPU
time, CPU-core-hours, GPU use and cost are explicitly not measured or inferred.
Source hashes identify executed uncommitted code;
a base Git revision is not represented as containing dirty changes. Historical
receipts can be verified after code changes; source hash syntax and bindings are
checked rather than requiring equality to the currently installed adapter.
New mesh source records use the actual mesh adapter's verified local Git
membership, with a null `worktree` field and hash-only fallback on uncertainty;
see the shared [source-provenance boundary](cad-geometry.md#evidence-and-deterministic-behavior).
Copied historical CAD provenance and native-library paths are not redacted by
this change and still require export review.

The identical `gmsh_runtime` record is bound into v2 recipe, worker report and
receipt. `VERIFIED_AT_EXECUTION` means the worker captured and checked this
identity before and after this mesh run. Archive verification checks its recorded
structure and bindings without loading Gmsh or requiring the original installation
paths to still exist. It does not authenticate the publisher or prove a complete
transitive dependency identity. The wrapper hash identifies the loaded module's
on-disk file, not an in-memory Python bytecode attestation.

Historical `mesh.synthetic_beam.hex8.v1` packs remain read-only geometry/numerical
evidence. Their `gmsh_version` was the wrapper's version only and cannot establish
which native version produced the saved mesh. `verify_mesh_artifacts` preserves
the original receipt exactly, and `native_provenance(receipt)` explicitly reports
`NOT_VERIFIED` for these packs. `require_native_identity=True` rejects them. A new
matching installation never upgrades an old receipt; regenerate into a new output
directory for v2 evidence. Default legacy geometry verification is not historical
native identity verification. Unknown native identity is not a failed geometry or
numerical result.

The geometry environment artifact is hash-bound by the copied CAD receipt and
manifest but is not duplicated in the mesh pack. Keep the original verified CAD
pack for its full environment inventory. Mesh provenance is not a complete
transitive/native environment lock or SBOM.

Output directories must be new; existing directories and symlink parents are
refused. Handled failures retain diagnostic artifacts and `failure.json`, remove
success receipt/manifest/pending publications, and re-raise the error. A nonzero or
timed-out process, missing mesh, corrupted regions, invalid quality or incomplete
publication never produces a valid PASS receipt. Hard termination can leave
incomplete files; a receipt alone is insufficient without manifest verification.
Atomic renames are used, but fsync/crash-durable transactions are not claimed.

Hashes provide local integrity and lineage, not authenticated third-party
attestation. A party able to rewrite all evidence can forge it. Caller-owned
immutable storage is required against hostile concurrent writers; this adapter
is not a security sandbox or a new CAS owner.

## Running and tests

```sh
PYTHONPATH=src:/path/to/existing/optional-dependencies \
  /path/to/existing/gmsh/python -m opendot_engineering.executors.gmsh_mesh \
  /path/to/verified-cad /path/to/new-output --divisions 20 4 2
PYTHONPATH=src python -m pytest tests/test_gmsh_mesh.py -q
# Enable real subprocess tests only with a verified real STEP pack and Gmsh 4.15.2:
OPENDOT_TEST_CAD_PACK=/path/to/verified-cad PYTHONPATH=src:/path/to/gmsh-packages \
  /path/to/gmsh/python -m pytest tests/test_gmsh_mesh.py -q
```

Contract tests exercise bounds, lazy imports, saved coordinate scaling, invalid
HEX/QUAD ordering, incorrect regions, truncated/nonfinite data, artifact tampering,
existing output refusal, missing output, nonzero process and timeout failures.
Opt-in integration tests run real meshes and refinement, a coherently resealed CAD
receipt whose actual STEP disagrees, resealed quality mismatch, and receipt
publication failure. No installation occurs in tests. Refinement evidence proves
that a larger mesh was generated and checked, not that any solution converged.
Native identity tests also cover mismatched loaded versions, missing/changed
mapping identities, resealed identity disagreements, legacy read-only assessment,
and strict native-provenance rejection. Set `OPENDOT_TEST_MISMATCH_GMSH_PATH` to an
existing known wrapper-4.15.2/native-4.13.1 installation to exercise the real
pre-meshing refusal; tests install nothing.

Separate bounded [thermal](thermal-conduction.md) and [structural](structural-beam.md)
adapters now consume the verified mesh artifacts; their solver acceptance is not
part of this mesh-only recipe. Remaining work includes higher-order mesh recipes,
additional platforms, memory isolation, independent-kernel validation,
clean install recreation, complete package/native locks, and license review before
any redistribution. No native execution is claimed for this source cut.

## Official references and licensing

The retained implementation references the official [Gmsh manual](https://gmsh.info/doc/texinfo/)
for STEP target units, transfinite constraints, physical groups, first-order
HEX8/MSH2.2 ordering and `getElementQualities`; its native version gate is 4.15.2. Tutorial 20 documents the STEP unit
conversion; API sections document mesh quality and generation. These upstream APIs
are called, not copied into the adapter.

[Gmsh licensing](https://gmsh.info/#Licensing) uses the GNU GPL, with commercial
licensing available from its authors. A subprocess boundary is an execution and
optional-dependency choice, **not licensing clearance**. It does not automatically
resolve distribution, linking, source/notice or combined-work obligations. No
solver/native binaries are distributed in this source-only change.
