# Synthetic laboratory qualification-record verifier

This is an **offline software benchmark**, not an instrument simulator or a
controller. Its synthetic records and numbers are invented fixture values, not
specimen recipes, calibration data or recommended device settings. Nothing here
connects to hardware, emits a motion command, derives a real trigger setting,
compiles an operator protocol or admits data to a scientific queue.

## Run the pinned fixture

From the source checkout root with Python 3.12 or newer on a supported POSIX
system with descriptor-relative no-symlink file operations:

```sh
PYTHONPATH=src python -m opendot_engineering.adapters.lab_qualification \
  --root examples/lab-qualification \
  --expected-revision bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb \
  --expected-manifest-sha256 1dcde9c63280f4f99e6c2ea9e3ca6d392399e4d0792a4a9e4f81d581d2ce817f
```

The revision above is explicitly synthetic; it does not assert membership in a
Git commit. The operator supplies both pins independently. Do not calculate a
replacement pin from unreviewed input and treat that as independent verification.

The three included cases are:

- a consistent synthetic record: `SYNTHETIC_PASS`
- a residual planning target supplied as a total-strain trigger: `HOLD`
- unknown stop latency: `HOLD`, with the unknown still stored as null

All three should match their separately declared fixture oracles. CLI exit 0
means every oracle matched; exit 1 means readable, pinned inputs produced an
oracle mismatch; exit 2 means admission/structure failed. Errors expose bounded
codes, not paths or raw input. The function `verify_bundle(root, manifest,
expected_revision=..., expected_manifest_sha256=...)` returns the same receipt
without writing files.

## Input and meaning

The exact-field manifest binds one bounded JSON fixture by SHA-256 and Git blob
SHA-1. The fixture is public and synthetic only. It contains at most 32 cases,
each with a record, evidence, a trace of 2–256 samples and an expected outcome.
The existing source-audit reader handles local paths, descriptor-relative
no-symlink reads, size limits, duplicate JSON keys and hashes. No second file
reader, registry, artifact store or runtime is introduced.

Each case binds sensor, configuration and reference IDs across all components.
The supported observable is engineering strain in the loaded state. Fraction
and percent are accepted only when explicitly and consistently declared across
the record, trace and uncertainty; the conversion is exactly 1 percent = 0.01.
The trigger must be explicitly `peak_total`. A residual plan, crosshead value,
other observable or other state is refused, without inference or conversion.

The fixed numerical fields carry units in their names: force in N, travel in mm,
times in s, and the stop-error limit in dimensionless fraction. Calibration must
be marked valid for the entire trace interval. Uncertainty and response latency
use explicit known/unknown states. Known values must be finite, numeric and
nonnegative; unknown values must be null and cause `HOLD`. Boolean numbers are
rejected. These are synthetic declarations, not authenticated certificates.

Trace checks require strictly increasing event and sample times, nonfuture and
fresh samples, bounded gaps, valid signal, and bounded absolute force/travel.
There must be a recorded below-target sample before the first threshold crossing
and exactly one final stop acknowledgement. Acknowledgement latency is measured
from that crossing sample's timestamp. The largest recorded strain overshoot
plus declared uncertainty must fit the synthetic error limit; a transient peak
cannot be hidden by a lower final reading. No interpolation, guessed sampling
rate, latency substitution or missing-value imputation is performed.

`protocol_structure_status` is a declared upstream-style status, recorded with
`protocol_structure_verified=false`. Its READY value cannot override any failed
domain check. This benchmark does not execute or alter upstream protocol
validation semantics.

## Receipt and trust boundary

- `audit_accepted` means the bounded synthetic input passed byte and structural
  admission; it does not mean the qualification case or software oracle passed
- `qualification_result` is `SYNTHETIC_PASS` or `HOLD`, with explicit reason codes
- `benchmark_contract_passed` means every outcome and exact reason set matched
  the pinned oracle; a correct refusal can therefore pass the software benchmark
- Every receipt, including case and error receipts, retains
  `real_device_qualified=false`, `device_control_authorized=false` and
  `scientific_accepted=false`
- The receipt binds the manifest/fixture, each case's record/evidence/trace/oracle
  and both the adapter and reused source-audit module by SHA-256

Pins, access labels and synthetic declarations are trusted operator inputs.
Hashes establish consistency, not authorship, licensing, calibration truth or
scientific validity. Replacing a fixture and its oracle with newly approved pins
is a new trust decision. This same-process calculation is not an independent
review, an authenticated calibration, or an OS sandbox.

## Standalone integration boundary

This implementation is a bounded offline record check. It reports
`owner_integration=NOT_EVALUATED` and `independent_review=NOT_EVALUATED`.
No runtime compatibility or independently observed review is claimed.

A later consumer may call the verifier with authorized, pinned local fixtures
and store the returned receipt. Storage, workflow admission, human approval,
protocol execution, and laboratory ingestion remain outside this package.
Any integration requires its own acceptance evidence and authorization; these
synthetic checks cannot grant device control or scientific acceptance.

No device backend or optional package is needed for this fixed offline check.

## Tests

```sh
PYTHONPATH=src python -m pytest tests/test_lab_qualification.py -q
PYTHONPATH=src python -m pytest -q -ra
```

The tests cover correct negative outcomes, units/state/identity mismatch,
calibration and latency gaps, signal timing/loss, missing acknowledgements,
limits and transient peaks, false evidence promotion, unsafe/changed input and
CLI outcomes. Passing synthetic tests does not qualify an instrument or validate
a scientific experiment. Optional integrations elsewhere in the suite may skip.
