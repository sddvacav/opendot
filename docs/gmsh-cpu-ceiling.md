# Gmsh worker inherited resource ceilings

The [0.3.0a2 ALPHA prerelease](https://github.com/sddvacav/opendot/releases/tag/v0.3.0a2) includes the inherited CPU and file-size ceiling setup described below. The
[released worker source](https://github.com/sddvacav/opendot/blob/359f781a5aa1650ae92b1af81cf369a17c444045/src/opendot_engineering/executors/_gmsh_worker.py) and
[release notes](https://github.com/sddvacav/opendot/releases/download/v0.3.0a2/RELEASE-NOTES.md) bind the packaged repair to exact a2 assets and scoped software checks. The file-size repair changes neither the default verifier, numerical tolerances nor the separate solver policy. It establishes no new kernel-enforcement or native acceptance.

Historical boundary: the CPU component was integrated into the resource-qualified
**0.3.0a1** successor; unchanged v0.3.0a1 release assets do not contain the later
file-size repair. The [historical verification scope](structural-v2-candidate-verification.md)
retains its earlier source/artifact identities; prior assets and receipts are unchanged.

Before importing Gmsh, the worker reads its inherited CPU soft and hard limits
and sets both to the minimum of 300 seconds and all finite inherited values.
The policy is identical to the already accepted solver callback: it does not
numerically increase either finite inherited CPU cap. Unlimited values are
recognized by comparison with `resource.RLIM_INFINITY`, not a guessed number.
Zero remains numerically zero; kernel timing and zero semantics are not verified.

File-size setup remains first. It now reads inherited `RLIMIT_FSIZE` and sets
both limits to the minimum of 32 MiB and all finite inherited soft/hard values,
using the same minimum policy as CPU setup. It cannot numerically increase
either finite inherited cap, including zero, and recognizes unlimited values
only through `resource.RLIM_INFINITY`. This replaces an unconditional 32-MiB
assignment that could raise a lower soft cap or fail on a lower hard cap.
Import, query, and set failures propagate before the Gmsh import, without retry
or fallback. File-size query/set failures occur before any CPU query or set.
The separate solver-child file-size assignment remains unchanged and can still
attempt to raise a lower inherited cap; this repair applies only to Gmsh.

`tests/test_gmsh_cpu_ceiling.py` executes only the source AST prefix before the
Gmsh import, with fake resource calls and an import-boundary sentinel. It covers
unlimited, finite, zero, boundary, alternate-sentinel, asymmetric-limit, and
exception-order cases for both resources. Its 35 nodes replace the prior
19-node Gmsh selection with 16 net additional nodes; subtests are not extra
nodes. The old lower-file-size refusal test is replaced by a preservation test.
These tests neither import the worker or Gmsh nor exercise native processes,
real resource calls, or kernel enforcement, including zero-limit semantics.
The test's two source-path constants must point to the actual installed worker
and solver module when used in a separately declared installed-package run.

The existing mesh adapter dynamically records the actual worker's SHA-256 in
the recipe's source identity. Future mesh creation must therefore record the
new worker hash. Earlier receipts and native outputs keep their original hashes;
this change does not retroactively rebind them or claim native execution coverage.
Independent review and separate run authorization remain required before native
use. No sandbox, total-job CPU budget, wall-time, physical-validity, or scientific
acceptance claim follows from these resource setup changes. Existing output
packs are not regenerated and their bytes and hashes remain unchanged.
