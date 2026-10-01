# CalculiX declared-version gate

The bounded thermal and structural adapters share
`thermal_conduction._check_solver_log`. A log must contain exactly one
`CalculiX Version` marker and a complete header line beginning with
`CalculiX Version 2.23,`. Leading spaces/tabs and ordinary line endings are
accepted. The text after the comma is descriptive, not verified build identity.

Marker counting is case-insensitive and tolerates whitespace so a malformed
second declaration cannot hide behind a valid header. The accepted header uses
the exact spelling and version above. Missing, wrong, embedded, malformed,
contradictory, and repeated declarations (including identical repeats) are
rejected. Repeated headers may indicate concatenated runs; the verifier does
not choose one of them. The existing completion, error/warning, procedure,
thread-count, convergence and numerical checks still apply.

This is consistency checking of a declared version. It does not authenticate
logs, prove the identity or behavior of a solver binary, or establish physical
validation. A party that rewrites all evidence can fabricate a consistent pack.

`tests/test_solver_version_identity.py` exercises the shared gate and both
public pack verifiers using generated synthetic fixtures, including resealed
mutations. No native solver, mesh backend, or preserved solver outputs are used
by these tests; passing them is not native-execution or scientific evidence.
