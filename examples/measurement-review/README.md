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
