# ADR 006: Fixed measurement comparison composition

Date: 2026-10-02 UTC. Status: narrow local implementation exception accepted;
qualification results belong to separate version-bound evidence. This decision
does not claim that tests have passed, authorize publication or change ADR 004.

## Decision and source boundary

Add one source-only consumer that answers: what is the absolute difference
between the means of conditions A and B, and is it within the declared tolerance?
The existing parameter and measurement examples already supply the two producer
algorithms. The new consumer combines them with a separately implemented
arithmetic check. It is a finite scripted workflow with three fixed roles,
not three autonomous agents or a general coordination platform.

The only admitted source paths are:

1. `AGENTS.md`, for this narrow allowance
2. `docs/decisions/006-fixed-measurement-composition.md`
3. `examples/measurement-review/compare.py`
4. `examples/measurement-review/comparison-fixtures.json`
5. `examples/measurement-review/README.md`
6. `examples/measurement-review/README.zh-CN.md`
7. `tests/test_measurement_comparison_example.py`

Preserve every other file, including both existing `demo.py` producers, the
canonical owners, the original deny-only guard and ADR 004. Existing demo
instructions and their distinct receipt/exit semantics remain available.

## Fixed computation and dispatch

- Parameter role: reuse `examples/source-boundary/demo.py:parameter_readiness`
  for exactly `{"scenario":"bench-A","unit":"au"}`. Up to eight source
  records provide `source`, `scenario`, `unit` and `raw_value`; source names are
  unique and match `[A-Za-z0-9_-]{1,64}`. Preserve the resolver's numeric grammar:
  an optional minus sign, zero or at most six integer digits without leading
  zeroes, and optionally 1–12 fractional digits; at most 32 characters. Values
  are JSON strings, not JSON numbers. Do not extend tolerances to seven integer
  digits just because measurement values permit magnitude 1,000,000
- Missing/null/unknown applicability or values, conflicting values and invalid
  evidence block dependent calls. Known negative tolerance also blocks. Known
  zero is valid. Explicitly inapplicable sources are excluded by the existing
  resolver; absent applicable evidence cannot supply a tolerance. Do not average
  disagreement, convert units or substitute zero for missing evidence
- Analysis role: reuse `examples/measurement-review/demo.py:summarize`. Accept
  exactly six rows, one each of A/B × replicates 1/2/3, with the exact header
  `condition,replicate,value,unit` and unit `au`. Each measurement is decimal
  text of at most 32 characters and 12 fractional places, magnitude at most
  1,000,000; no exponent or nonfinite value. CSV and parameter JSON are each
  limited to 64 KiB. Retain the producer's actual count, float sum and float mean
- Compute the decision from Decimal sums and integer counts using precision 50:
  `abs(sum_B * n_A - sum_A * n_B) <= tolerance * n_A * n_B`. Never use rounded
  float means for the decision. Retain exact rational delta and tolerance
- Verifier role: independently parse captured original CSV/parameter bytes and
  calculate with `Fraction`. Do not call either producer or the comparison
  algorithm to obtain the expected numerical answer. Only finite observed
  summary floats receive the allowance
  `max(1/10^12, abs(exact_value)/10^15)`, evaluated using
  `Fraction.from_float(observed)`. Preserve observed bytes; the exact rational
  delta, selected tolerance and within/outside decision must match exactly
- Use exactly three explicit top-level `ToolRuntime.execute` call sites, each
  at most once with one attempt. Refusal, denial, failure, unresolved execution
  or an unaccepted result prevents dependent dispatch. No nested dispatch,
  retry, resubmit, dynamic graph, configurable tool or new execution owner

## Frozen arithmetic cases

The public fixture freezes inputs and expected outcomes before qualification;
its top-level `demo_parameters` contains the agreeing `2`/`2.0` tolerance
evidence. It is an arithmetic oracle, not measured evidence or an authority.

| Case | A | B | Tolerance | Exact absolute mean difference | Within |
| --- | --- | --- | --- | --- | --- |
| Demo | 1, 2, 3 | 2, 4, 6 | 2 (also 2.0) | 2/1 | true |
| Below boundary | 1, 2, 3 | 2, 4, 6 | 1.999 | 2/1 | false |
| Decimal | 0.1, 0.2, 0.3 | 0.2, 0.3, 0.4 | 0.1 | 1/10 | true |
| Indivisible | 0, 0, 1 | 0, 0, 2 | 0.333333333333 | 1/3 | false |
| Negative values | -3, -2, -1 | -6, -4, -2 | 2 | 2/1 | true |
| Cancellation | 1000000, -1000000, 0.000000000001 | 0, 0, 0 | 0 | 1/3000000000000 | false |
| Maximum | -1000000, -1000000, -999999.999999999999 | 1000000, 1000000, 999999.999999999999 | 999999 | 2999999999999999999/1500000000000 | false |

## Canonical ownership, binding and local interface

Execution remains in `tool_runtime.py`, storage in `core/artifacts.py`, references
and contracts in `core/contracts.py`, and bounded JSON/filesystem helpers in
`adapters/source_audit.py`. Reuse those exact owners and canonical class
identities. No second CAS, receipt type, registry, permission system or scheduler
is admitted. Load public producer functions only from fixed repository-relative
paths; no discovery, caller-selected modules or default optional imports.

The fixed profile binds hashes of the canonical owners, producer files, frozen
fixture oracle and current comparison source. It records the numerical limits
and allowance. A source or fixture change therefore requires a matching reviewed
profile expectation; a candidate report's own profile claim is insufficient.

The interface is:

```text
compare.py run --demo --output FRESH
compare.py run --input CSV --parameters JSON --output FRESH
compare.py verify --output DIR --report-sha256 PIN --input-sha256 PIN --parameters-sha256 PIN --profile-sha256 PIN
```

Demo and custom-input modes are mutually exclusive. The run prints a JSON receipt
and human summary, and leaves `report.json` (at most 64 KiB), `summary.txt` (at
most 8 KiB) and canonical artifact objects in a fresh output directory outside
the checkout. An existing output path is preserved, never overwritten. Retain
available unaccepted artifacts and their references; failure is not rollback.
Use allowlisted error codes; omit raw exception messages, host/user names,
absolute paths and process identifiers from reports.

Every consumer CAS read supplies `max_bytes`. Standalone verification opens the
canonical store with `read_only=True`, validates original-byte/reference/receipt
bindings and rechecks the arithmetic. It performs no producer execution and
does not create, modify, chmod or remove files, including on rejection. Ordinary
read access times are outside this non-mutating promise. The report, input,
parameter and profile pins must come from separately trusted configuration or
a retained run receipt protected independently from the candidate output. Never
derive trust solely from the candidate report or a co-modified receipt.

| Status | Exit | Meaning |
| --- | --- | --- |
| `CHECKED` | 0 | Accepted computation, either inside or outside tolerance |
| `BLOCKED` / `REFUSED` | 2 | Unusable tolerance, refused input/configuration or denied dependent work |
| `FAILED` | 1 | Execution or verification failure |

All outcomes retain `scientific_accepted=false`,
`device_control_authorized=false` and `independent_review=NOT_EVALUATED`.
An independently implemented arithmetic check is not independent human review.

## Qualification and assurance limits

Use only public synthetic fixtures and existing local Python/pytest. Explicitly
select the focused portable tests; test selection, execution and resulting
evidence remain distinguishable. Cover the frozen cases, missing/null/conflict/
inapplicable/negative/zero parameters, malformed/oversized inputs, denial and
pure failure/unresolved fixtures at each role, incorrect observed floats beyond
the allowance, wrong exact deltas/decisions, retained rejected bytes, mutations
of source/input/result/profile/pins, strict receipt/metadata binding, collisions,
read-only byte/mode preservation, exact owner identities/hashes, unchanged
producer demos and absence of optional imports. A fresh Python process may
verify saved output; this does not authorize native lifecycle probing.

The local input, output parent, ancestors and CAS remain trusted cooperative
paths. Canonical symlink behavior is unchanged. This is not an OS sandbox,
hostile-concurrent-filesystem defense, transaction, crash recovery or proof of
handler termination. Hashes establish bounded consistency, not authorship,
authorization, calibrated accuracy or scientific acceptance.

Demo input is labelled `synthetic`; explicitly supplied data is
`user_supplied_unvalidated`. The comparison is descriptive, with no statistical
significance, causation, data acquisition or unit conversion claim. Never relabel
physical units as `au`. Inputs, artifact objects, receipts and reports are private
by default; numerical values can remain sensitive even without identifiers.
No automatic upload or public evidence bundle is admitted.

No installation, model/provider call, credential, network request, local service,
native solver/device action, private-project work, publication, native process/
namespace/descendant/lifetime probe, Temporal profile expansion or hosted wiring
is authorized. ADR 004, its transport and test harness remain unchanged.
