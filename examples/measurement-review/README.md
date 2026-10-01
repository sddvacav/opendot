# Review a synthetic repeated-measurement batch

A research engineer often receives a small table and a summary with unclear input
revision or review status. This worked example binds those pieces explicitly with
the existing `ToolRuntime` and canonical `ArtifactStore`. The candidate benefit is
fewer manual input/result/review mismatches; no external user study, time saving,
ROI, scientific result or superiority over another tool has been established.

The input is **six invented rows**, two conditions with three repetitions each,
using the arbitrary unit `au`. It is not experimental data. The independently
specified arithmetic is A: count 3, sum 6, mean 2; B: count 3, sum 12, mean 4.
No CAD, solver, model, instrument, task scheduler or new runtime owner runs.

## Execute, inspect, and retrieve

From the reviewed source checkout, with its package installed or `PYTHONPATH=src`:

```sh
PARENT=$(mktemp -d /tmp/opendot-batch.XXXXXX)
PYTHONPATH=src python -B examples/measurement-review/demo.py run \
  --input examples/measurement-review/batch.csv --output "$PARENT/valid"
```

The output prints the bundle, input and oracle SHA-256 values. Record those values
through a trusted channel. The fixed fixture input digest is
`12fa76e2cb8defb752ce08a2fdd386b0f943579d1438e3022cb2e345bdcae0d9`.
The `bundle.json` contains the actual dispatch status and the canonical input and
result references. Objects live in its adjacent `artifacts` store.

In a **fresh Python process**, verify with the three independently retained values:

```sh
PYTHONPATH=src python -B examples/measurement-review/demo.py replay \
  --output "$PARENT/valid" --bundle-sha256 "$BUNDLE_SHA256" \
  --input-sha256 "$INPUT_SHA256" --oracle-sha256 "$ORACLE_SHA256"
```

Set those shell variables to the printed, separately retained values first. Do not
read purported expected pins exclusively from an untrusted bundle and call that
authentication. Replay checks the saved bytes, expected source identity, fixed
synthetic oracle, dispatch status and returned-reference observation. It does not
restart execution, resume a task, authenticate a signed receipt or recover a job.
With the reviewed wheel installed, the same source example can be run with that
virtual environment's `python -I -B` from outside the checkout; examples are not
additional installed packages.

## Compare explicit error cases

Run again with a **different fresh output path** and `--case wrong-mean` or
`--case denied`:

- `wrong-mean`: deliberately emits A.mean = 3. Stored bytes remain intact, but the
  fixed oracle causes ToolRuntime `FAILED`, semantic validity false, no returned
  accepted result, and a retained unaccepted reference. Replay refuses it
- `denied`: withholds `artifact:write`. Dispatch is `BLOCKED/PermissionDenied`,
  with zero handler calls and zero artifact objects. Empty store directories and
  the diagnostic bundle may still exist
- Editing source/result object bytes without their pinned hashes makes retrieval
  fail. Changing a source pin or oracle identity cannot reuse the original
  acceptance. The fixture parser refuses duplicate/missing repetitions, wrong
  units/conditions, invalid and nonfinite values before output creation

The `run` command exits zero when it has successfully produced a diagnostic
receipt, including expected failed/blocked cases. Inspect `status` and
`semantic_valid`; exit zero does **not** mean accepted analysis. `replay` exits
nonzero for refused results. All outputs keep `scientific_accepted=false`.

## Boundaries and ownership

This source-only demonstration supports a fixed small synthetic schema, at most
64 KiB input. Its independent expected values are hard-coded, not learned from
the same summarizer. New scientific protocols need their own evidence and oracle;
this example is not a generic laboratory data validator.

The output parent, ancestors, input and store are trusted cooperative local paths.
They are not a hostile-filesystem or concurrent-mutation boundary. ArtifactStore
construction can create directories and change their permissions, including on
verification replay; replay is not claimed to be strictly read-only. Canonical
metadata may retain the first writer's provenance; hashes establish byte identity,
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
