# Review a synthetic repeated-measurement batch

[简体中文](README.zh-CN.md)

A research engineer often receives a small table and a summary with unclear input
revision or review status. This worked example binds those pieces explicitly with
the existing `ToolRuntime` and canonical `ArtifactStore`. The candidate benefit is
fewer manual input/result/review mismatches; no external user study, time saving,
ROI, scientific result or superiority over another tool has been established.

The input is **six invented rows**, two conditions with three repetitions each,
using the arbitrary unit `au`. It is not experimental data. The independently
specified arithmetic is A: count 3, sum 6, mean 2; B: count 3, sum 12, mean 4.
No CAD, solver, model, instrument, task scheduler or new runtime owner runs.

## Compare A and B against a declared tolerance

[`compare.py`](compare.py) composes three fixed scripted roles: resolve tolerance,
summarize measurements, then independently check the arithmetic using `Fraction`.
It reuses the existing producers and canonical runtime/store. It is source-only,
requires Python 3.12+ and no optional packages, and runs from the source root on a
trusted local Linux/POSIX filesystem. It does not run autonomous agents.

### One-command synthetic comparison

Create an output parent outside the checkout, then pass a fresh child path;
do not create the child first:

```sh
CMP_PARENT=$(mktemp -d /tmp/opendot-comparison.XXXXXX)
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -B \
  examples/measurement-review/compare.py run --demo \
  --output "$CMP_PARENT/demo" > "$CMP_PARENT/demo-receipt.json"
cat "$CMP_PARENT/demo/summary.txt"
```

### Preview: a checked synthetic result

This excerpt from `$CMP_PARENT/demo/summary.txt` is produced by the command above:

```text
Measurement comparison: CHECKED
Evidence: synthetic (local/private by default)
A: count=3, sum=6.0, mean=2.0 au
B: count=3, sum=12.0, mean=4.0 au
Absolute mean difference: 2/1 au
Declared tolerance: 2/1 au
Within tolerance
Scientific acceptance: false; device control: false; independent review: NOT_EVALUATED
```

In `report.json`, the means are `summary.conditions.A.mean` and
`summary.conditions.B.mean`. Both `comparison.absolute_mean_difference` and
`comparison.tolerance` are `{"numerator": 2, "denominator": 1}`;
`comparison.within_tolerance=true`, `status="CHECKED"` and `checked=true`.
The agreeing tolerance sources contain `2` and `2.0`.

**`CHECKED` means the arithmetic was checked, even if a result is outside tolerance.**
It does not mean an experiment or scientific conclusion was accepted. These are
six invented rows in arbitrary units `au`, with `evidence_role="synthetic"`,
`scientific_accepted=false`, `device_control_authorized=false` and
`independent_review="NOT_EVALUATED"`. The demo exits **0**; the [read-only
verification below](#verify-saved-output-without-writing-to-it) checks the saved
result against separately retained receipt pins.

The JSON receipt goes to stdout; the human summary goes to stderr and
`summary.txt`. The fresh output also contains `report.json` and canonical
`artifacts/` objects. The receipt supplies `report_sha256`, `input_sha256`,
`parameters_sha256` and `profile_sha256`. `report.json` records the status,
input/profile bindings, each role's outcome, comparison and available artifact
references, including rejected outputs. The report is capped at 64 KiB and
the summary at 8 KiB. A failure may retain useful artifacts without accepting
them; no rollback is promised.

### Supply your own matching local files

This complete example still uses invented data; it exercises the explicit-input
mode without extracting or modifying the frozen fixture:

```sh
cat > "$CMP_PARENT/input.csv" <<'CSV'
condition,replicate,value,unit
A,1,0.1,au
A,2,0.2,au
A,3,0.3,au
B,1,0.2,au
B,2,0.3,au
B,3,0.4,au
CSV
cat > "$CMP_PARENT/parameters.json" <<'JSON'
{
  "task": {"scenario": "bench-A", "unit": "au"},
  "sources": [
    {"source": "tolerance_note", "scenario": "bench-A", "unit": "au", "raw_value": "0.1"}
  ]
}
JSON
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -B \
  examples/measurement-review/compare.py run \
  --input "$CMP_PARENT/input.csv" --parameters "$CMP_PARENT/parameters.json" \
  --output "$CMP_PARENT/custom" > "$CMP_PARENT/custom-receipt.json"
cat "$CMP_PARENT/custom/summary.txt"
```

Expected exact means are 1/5 and 3/10, the absolute mean difference is **1/10**,
and the equality boundary passes. The observed float summaries are retained;
they are not used to decide the tolerance boundary. This mode is labelled
`user_supplied_unvalidated`, even when you supply synthetic rows. Do not combine
`--demo` with `--input` or `--parameters`.

- CSV: exact header shown above; exactly six rows, A/B × replicates 1/2/3 once
  each; `au` only; at most 64 KiB. Values are decimal text, at most 32 characters,
  at most 12 fractional digits, and absolute value at most 1,000,000. No exponent,
  NaN or infinity. Use canonical forms such as `0.1`, not `.1`
- Parameter JSON: at most 64 KiB; exactly the shown `task` and at most eight
  source records. Each source has `source`, `scenario`, `unit`, `raw_value`;
  source names are unique, 1–64 ASCII letters/digits/underscores/hyphens. Tolerance
  values are strings, with at most six integer digits, no leading zeroes except
  zero itself, up to 12 fractional digits and at most 32 characters. Use `0.1`,
  not `.1`, an exponent or a JSON number. The measurement limit of 1,000,000 does
  not extend the existing tolerance grammar to seven integer digits
- Unknown/null/missing values or applicability, conflicting or invalid evidence,
  and negative selected tolerance block dependent analysis. Zero is valid.
  Explicitly inapplicable sources are excluded; they cannot supply a tolerance
- Use only values genuinely represented in arbitrary units `au`; never silently
  relabel millimetres, seconds or other physical units. Larger datasets, other
  groups, unit conversion, statistical inference and data acquisition are outside
  this profile

### Verify saved output without writing to it

Keep all four expected pins through a separately trusted source. For this local
demo, the receipt captured outside the output directory is the retained expected
record. Protect it separately before treating the output as untrusted. A receipt
modified together with the output provides no independent trust. Never obtain
expected pins only from the candidate `report.json`.

In the same shell, use the trusted retained receipt:

```sh
receipt_pin() {
  python -B -c \
    'import json, sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' \
    "$CMP_PARENT/demo-receipt.json" "$1"
}
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -B \
  examples/measurement-review/compare.py verify --output "$CMP_PARENT/demo" \
  --report-sha256 "$(receipt_pin report_sha256)" \
  --input-sha256 "$(receipt_pin input_sha256)" \
  --parameters-sha256 "$(receipt_pin parameters_sha256)" \
  --profile-sha256 "$(receipt_pin profile_sha256)"
```

To verify the custom run, change both `demo` references to `custom` (the receipt
filename and output child). The profile binds the current consumer source,
canonical owners, producer sources and frozen fixtures. Changing source or
fixture bytes requires a matching reviewed profile, not a copied self-declared
hash. Verification reparses captured input/evidence with independent rational
arithmetic, checks receipt/reference bindings and uses bounded canonical reads
with `read_only=True`. It does not rerun producers or modify bytes, permissions
or directory entries. Ordinary reads may update atime.

### Interpret the comparison result

| Status | Exit | Meaning |
| --- | --- | --- |
| `CHECKED` | 0 | Computation checked, whether inside **or outside** tolerance |
| `BLOCKED` / `REFUSED` | 2 | Missing/conflicting/invalid evidence, denied work or refused input/configuration |
| `FAILED` | 1 | Execution or verification failed |

For the demo measurements, tolerance `1.999` gives `within_tolerance=false` and
still exits **0** when checked. Denial, error or unresolved execution prevents
dependent dispatch; each of the three roles is attempted at most once, with no
retry. An existing output path is preserved: choose a new child path rather than
reusing or deleting the old result. Nonzero exits may stop a shell using `set -e`.

These results are descriptive software checks. All outcomes keep
`scientific_accepted=false`, `device_control_authorized=false` and
`independent_review=NOT_EVALUATED`. An independent arithmetic implementation is
not scientific peer review, calibration or evidence of causation. Inputs, CAS
objects, receipts and reports are private by default, with no automatic upload;
numerical data may be sensitive even without identifiers. Paths and ancestors
must remain trusted and caller-controlled. Canonical CAS paths follow symlinks;
source/input/report reads reuse the existing symlink-refusing audit helpers. The exact
profile and source boundary are in [ADR 006](../../docs/decisions/006-fixed-measurement-composition.md).

## Existing single-role demo

The original `demo.py` cases below remain unchanged. Their diagnostic receipt,
`replay` command and exit conventions are separate from `compare.py` above.

## Start here: three source-example cases

Use Python 3.12+ on a trusted Linux/POSIX checkout. No optional packages are
needed. Run the following blocks in order, in the same shell, from the source
root. The [CSV](batch.csv) and [script](demo.py) are source files, **not wheel
contents or installed commands**. For package installation and isolated import
checks, use the [installed quickstart](../../docs/installed-quickstart.md); keep
this matching source example separately.

The first block creates a trusted output parent outside the checkout and a new
child path for each case. It also retains each command's printed receipt beside,
not inside, its bundle directory:

```sh
PARENT=$(mktemp -d /tmp/opendot-batch.XXXXXX)
cat examples/measurement-review/batch.csv
for CASE in valid wrong-mean denied; do
  PYTHONPATH=src python -B examples/measurement-review/demo.py run \
    --input examples/measurement-review/batch.csv --output "$PARENT/$CASE" \
    --case "$CASE" > "$PARENT/$CASE-receipt.json"
  printf '%s run exit=%s\n' "$CASE" "$?"
  cat "$PARENT/$CASE-receipt.json"
done
```

All three `run` commands exit **0**: this means a diagnostic receipt was produced,
not that the analysis was accepted. The printed JSON fields are:

| Case | `status` | `semantic_valid` | `scientific_accepted` |
| --- | --- | --- | --- |
| `valid` | `COMPLETED` | `true` | `false` |
| `wrong-mean` | `FAILED` | `false` | `false` |
| `denied` | `BLOCKED` | `false` | `false` |

## Find the input, result bytes, and rejected artifact

Each `$PARENT/<case>/bundle.json` records `receipt`, `source_ref`, `result_ref`,
`handler_calls`, `returned_result` and `retained_unaccepted_result`. Its adjacent
`artifacts/objects/<first two SHA-256 characters>/<remaining characters>` holds
the raw CSV and JSON bytes. Retrieve them through the existing canonical store:

```sh
PYTHONPATH=src python -B - "$PARENT" <<'PYTHON'
import json
from pathlib import Path
import sys
from opendot_engineering.core import ArtifactRef, ArtifactStore

for case in ("valid", "wrong-mean", "denied"):
    output = Path(sys.argv[1]) / case
    bundle = json.loads((output / "bundle.json").read_bytes())
    print(case, json.dumps({key: bundle[key] for key in
          ("receipt", "handler_calls", "returned_result", "retained_unaccepted_result")}))
    store = ArtifactStore(output / "artifacts", read_only=True)
    for key in ("source_ref", "result_ref"):
        if bundle[key] is not None:
            fields = dict(bundle[key])
            fields["source_refs"] = tuple(fields["source_refs"])
            ref = ArtifactRef(**fields)
            print(key, ref.artifact_id)
            print(store.get_bytes(ref).decode("utf-8"))
PYTHON
```

- `valid`: one handler call, `returned_result=true`, no retained unaccepted
  result; the retrieved summary has A.mean = 2 and B.mean = 4
- `wrong-mean`: one handler call, `returned_result=false`,
  `retained_unaccepted_result=true`; its intact stored result deliberately has
  A.mean = 3, which the fixed oracle rejects. Byte integrity is not semantic acceptance
- `denied`: `PermissionDenied`, zero handler calls, both references `null`,
  and zero artifact objects. Empty store directories and the diagnostic bundle may exist

## Verify in a fresh process

Keep the printed bundle/input/oracle SHA-256 values through a trusted channel.
The following uses the command receipts retained above and the fixed fixture's
input/oracle pins. Those local receipts are convenient for this trusted example,
not independent authentication: do not replace trusted expectations with values
read only from an untrusted bundle or co-modified receipt.

The wrong-mean and denied replay commands deliberately return nonzero. If your
shell uses `set -e`, run this comparison in a shell without that setting so all
three outcomes are shown:

```sh
INPUT_SHA256=12fa76e2cb8defb752ce08a2fdd386b0f943579d1438e3022cb2e345bdcae0d9
ORACLE_SHA256=60508ab267ad62422c8df302876f3a1a92290901900b73175d3f5c8f391430d2
for CASE in valid wrong-mean denied; do
  BUNDLE_SHA256=$(python -B -c \
    'import json, sys; print(json.load(open(sys.argv[1]))["bundle_sha256"])' \
    "$PARENT/$CASE-receipt.json")
  PYTHONPATH=src python -B examples/measurement-review/demo.py replay \
    --output "$PARENT/$CASE" --bundle-sha256 "$BUNDLE_SHA256" \
    --input-sha256 "$INPUT_SHA256" --oracle-sha256 "$ORACLE_SHA256"
  printf '%s replay exit=%s\n' "$CASE" "$?"
done
```

Expected: `valid replay exit=0` with `verification_replay_passed=true`,
`execution_restarted=false` and `scientific_accepted=false`. Both rejected cases
print `{"accepted": false, "error_type": "ValueError"}` and `replay exit=1`.
Replay checks saved bytes, source identity, the fixed synthetic oracle, dispatch
status and returned-reference observations. It does **not** restart execution,
resume a task, authenticate a signed receipt or recover a job.

## If the output path already exists

Rerunning `run` against an existing child path exits **1** and prints
`{"accepted": false, "error_type": "FileExistsError"}`. Keep the earlier output;
choose an unused child path instead (do not create that child first):

```sh
PYTHONPATH=src python -B examples/measurement-review/demo.py run \
  --input examples/measurement-review/batch.csv --output "$PARENT/valid-2"
```

This produces a new `COMPLETED` diagnostic receipt; it does not resume or repair
an earlier run. Start the first block again to get a new parent for a whole
comparison. Input parser failures occur before output creation; duplicate or
missing repetitions, wrong units/conditions, invalid and nonfinite values are
refused. Editing stored bytes or changing trusted input/oracle pins cannot reuse
the original acceptance.

## Boundaries and ownership

This source-only demonstration supports a fixed small synthetic schema, at most
64 KiB input. Its independent expected values are hard-coded, not learned from
the same summarizer. New scientific protocols need their own evidence and oracle;
this example is not a generic laboratory data validator.

The output parent, ancestors, input and store are trusted cooperative local paths.
They are not a hostile-filesystem or concurrent-mutation boundary. Replay and
the retrieval block use `ArtifactStore(..., read_only=True)`: they do not create
files/directories, change bytes or modes, or delete entries, including refusal
paths. Ordinary reads may update filesystem access timestamps (atime), which are
excluded from this non-mutating contract. Default `read_only=False` construction
still initializes a writer. Symlinks remain followed; the caller must control the
root and ancestors. Canonical metadata may retain the first writer's provenance;
hashes establish byte identity,
not authority or full metadata authenticity. The returned-reference observations
are trusted example code, not independent OS observations.

Permissions are dispatch checks, not an OS sandbox. `REVERSIBLE_WRITE` does not
implement undo. Retries are disabled and the handler is non-idempotent. A failure
may leave artifacts; there is no rollback, transaction, durable resume, model
coordination, native execution or consumer migration. Read the existing
[callable limits](../../docs/callable-execution.md) and
[artifact limits](../../docs/canonical-artifacts.md).

The CSV, example and focused tests are newly authored synthetic Apache-2.0 project
material. No private or third-party measurement is copied. Focused tests are in
`tests/test_measurement_review_example.py`; their counts are reported in separate
version-bound receipts, never promoted into a new platform benchmark.

## Offline incremental-utility fixture report

[`utility_report.py`](utility_report.py) is a separate source-only **offline fixture
protocol**. **Real O3 comparison: NOT_RUN.** It reads the four original O3 cases
from the pinned [research delta](../../docs/research/delta-20261002/source-needs-delta.json)
without changing their historical status. Their invented aggregate effort is
reported as `fixture_effort_units`, never measured minutes or savings. The positive
fixture's declared “all known” flag is not audited measurement coverage.

From the source root, using existing Python 3.12+ and no optional dependencies:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -B \
  examples/measurement-review/utility_report.py history
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -B \
  examples/measurement-review/utility_report.py profile
```

The frozen input contract and finite synthetic examples live in
[`test_incremental_utility_report.py`](../../tests/test_incremental_utility_report.py).
They define only two repeat slots of this existing measurement task, baseline and
candidate arms, three attempts per arm maximum, and eight effort/eight charge rows
per arm maximum. Each input/report is capped at 65,536 bytes and the text summary
at 8,192 bytes. No trial is executed; no producer, runtime, CAS writer, network,
model or native tool is invoked. All output goes to stdout/stderr; the script
never creates or edits files. If retaining output, redirect to a fresh destination
outside the checkout without overwriting prior evidence.

`ledger` requires explicit `--ledger`, `--inventory`, `--ledger-sha256`,
`--inventory-sha256` and `--profile-sha256`. Keep these pins independently of the
candidate report. `verify` takes the same inputs plus `--report` and
`--report-sha256`, recomputes the report read-only and refuses resealed changes
against those retained pins. A pin read only from the candidate report is not
independent evidence. `profile` binds exact source/rule/oracle bytes, including
this consumer; code changes require a newly reviewed profile. Inputs must be
trusted cooperative local regular files; reads reuse canonical symlink-refusing
helpers. Reads may change atime. No hostile-concurrent-filesystem claim is made.

The separately pinned synthetic inventory records attempts and expected accounting
rows; it detects omitted records only relative to that retained inventory. It
cannot prove real observation completeness or authenticate a reviewer. Both arms
use the same existing frozen summary contract and named `fixture-reviewer`
records, with no requirement for OpenDot's three role receipts. Correct hashes,
`COMPLETED`, a reported acceptance boolean or agreeing LLMs cannot accept a result.
Task acceptance counts once; every attempt, failed trial and repeated output stays
visible. Runtime receipt attempts and latency are not all-trial or total-cost data.

Person effort uses four explicitly invented observations: disjoint setup,
execution/rework and review person-minutes, plus a separate wall-clock envelope in
seconds. Setup is allocated wholly to the two admitted slots. The limited monetary
fixture includes setup plus one all-incremental compute/tool/storage/idle charge
per attempt, excluding monetized human labor. It is not a total project-cost model.
Exact non-integral derived values use numerator/denominator objects. Different
currencies are retained separately, never summed together. Missing/censored values
stay null with missing-path reasons; zero accepted tasks gives null cost per
accepted task. The strict fixture rule requires more accepted tasks and no added
person effort with complete required evidence. Equal acceptance with lower effort
does not pass this particular rule.

`INVALID`, `NOT_COMPARABLE`, `INDETERMINATE`, `NO_FIXTURE_IMPROVEMENT` and
`FIXTURE_IMPROVEMENT` are different outcomes. A produced classification exits 0,
including negative/indeterminate/invalid classifications; refused input/pins exit
2. A positive fixture classification establishes no real benefit, user study,
scientific acceptance or device authority. Every report keeps measured effort
`UNKNOWN`, real comparison `NOT_RUN`, science/device flags false and independent
review `NOT_EVALUATED`. This adds no new source priority, production evaluator,
benchmark, empirical false-acceptance estimate or utility claim.

Counter correction in the v2 preparation: `output_counts` now counts only retained
outputs. `candidate` counts non-null output bytes, and `inspected` counts those
outputs with an ACCEPTED/REJECTED reviewer decision. Its accepted/rejected/
unreviewed/pending buckets partition retained outputs, including repeated bytes.
Separate `attempt_acceptance_counts` buckets partition every observed attempt,
including FAILED/BLOCKED trials without outputs. Those trials remain in all-attempt
denominators, dispositions and costs. The v1 preparation incorrectly included
no-output rejected attempts under `output_counts.rejected`; v1 evidence is retained
as historical, and the corrected source has a new profile pin.
