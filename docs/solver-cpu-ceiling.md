# Preserve inherited solver-child CPU ceilings

This is a separate, unreleased source-only patch based on public commit
`e5e7a9bfd41ccaeb8f4e942cb6dadacb484c9468`. It does not revise or inherit
acceptance of a previously built `0.2.0a4` artifact. The proposed a4 structural
qualification under a 30-second hard CPU ceiling was **BLOCKED BEFORE LAUNCH /
NOT EXECUTED**. Earlier native records retain their own source/artifact scope.

## Bounded change and resource contract

Only the CPU-limit assignment in the existing nested
`thermal_conduction._execute.limits` callback changes. The former unconditional
`setrlimit(RLIMIT_CPU, (300, 300))` could attempt to raise an inherited hard
limit, such as a trusted caller's 30-second ceiling, and fail during child setup.

The callback now reads inherited `RLIMIT_CPU` and sets both soft and hard CPU
limits to the minimum of:

- The existing 300-second maximum
- The inherited soft limit, unless equal to `resource.RLIM_INFINITY`
- The inherited hard limit, unless equal to `resource.RLIM_INFINITY`

No finite inherited limit increases. For `(30, 30)` the result is `(30, 30)`;
for `(10, 30)` it is `(10, 10)`; for two unlimited values it is `(300, 300)`.
A configured zero remains numerically zero. This is not a guarantee of zero
actual execution time: platform/kernel treatment of a zero CPU limit is outside
these fake-only checks. The wall timeout does not determine the CPU budget.

Resource read/write failures escape the callback without suppression, retry, or
fallback. Native `Popen` handling of a pre-execution failure is unchanged and
was not exercised. No launcher, wrapper, alternate source import, new helper
owner, process-group algorithm, cancellation, or recovery behavior is added.
Every source byte outside the replaced CPU assignment is preserved.

The existing file-size assignment remains exactly unchanged and occurs first.
It has a similar potential failure when the caller inherits a lower hard
`RLIMIT_FSIZE`; that separate issue is identified only and is **out of scope**.
No file-size cap is relaxed or repaired here.

## Focused fake-only verification

The standard-library test file `tests/test_solver_cpu_ceiling.py` parses the
public source AST and compiles only the nested callback against a fake resource
object. It neither imports the executor module nor calls real `resource`
functions, launches a process, or loads a solver/provider.

From the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python -B -m unittest discover \
  -s tests -p test_solver_cpu_ceiling.py -v
```

Author results on Python 3.12.14:

- Frozen baseline: the 17-method suite failed, reproducing attempted inherited
  cap increases and the missing CPU-limit read
- Patched callback: **17 test methods passed**, zero failures/errors/skips
- Coverage includes unlimited values, finite soft/hard caps, zero, 300 and
  larger caps, resource-specific unlimited constants, a finite no-increase
  matrix, timeout independence, get/set exception propagation, and the unchanged
  file-size call and its failure ordering
- Exact byte comparison: the single CPU-set line becomes three lines; the rest
  of `thermal_conduction.py` is unchanged

Parameterized subcases are included in these methods, not added as separate
tests. These checks establish callback calculations and call ordering only.
They do not establish OS enforcement, measured CPU consumption, subprocess
lifetime behavior, native scientific results, or installed-artifact acceptance.
The historical aggregate test counts do not describe this changed source.
No full-suite, native, model/provider, or private-code tests were run; no new
dependencies were installed, artifacts built, or publication performed.
