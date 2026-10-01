# Optional read-only artifact verification increment

This source increment changes only the existing artifact owner and the worked
measurement replay caller. It is separate from the original a5 acceptance record;
old source/wheel/CI results are historical and do not accept these changed bytes.
The increment is now included in [unreleased a6](a6-candidate-verification.md).
Its original check scope remains distinct; no release acceptance is asserted.

## Declared contract and checks

- Input: trusted caller-controlled local root; keyword-only `read_only: bool`,
  default false; independently retained references/digests for verification
- Output: existing byte and boolean read APIs; unchanged measurement replay
  result fields and CLI exit conventions; public puts in read-only mode raise
  `PermissionError` before processing input
- No directory/file creation, content writes, deletion or mode changes through
  read-only construction, reads or refused public puts, including error paths
- Existing default writer initialization/publication and canonical reference
  identity remain unchanged; metadata is neither a read prerequisite nor verified
- Replay retains separate bundle/input/oracle pins, rejects missing, modified or
  substituted evidence, and does not create or execute a ToolRuntime

The new exact [node manifest](../ci/readonly-artifact-nodes.txt) selects the
synthetic tests in `tests/test_readonly_artifacts.py`. They inspect membership,
bytes, modes and write timestamps, trap filesystem-mutating calls, and cover
fresh-process success/refusal. Existing canonical/artifact and measurement tests
remain separate regressions, not extra distinct copies of these new nodes.

Source checks, fresh installed-wheel checks and independent review require their
own exact-source receipts outside this repository. No hosted run or independent
acceptance is implied by this check plan. No native backend, model, physical
device, remote write or consumer migration is exercised.

## Limits

Ordinary reads may update filesystem access timestamps. This API does not make
storage immutable, control unrelated writers or enforce private-helper access.
The caller controls the root and ancestors; symlinks remain followed. Cooperative
writers are required, and multiple reads are not an atomic snapshot. Hash pins
bind expected bytes, not authorship, authority, scientific quality or signatures.
See the [API contract](canonical-artifacts.md#optional-non-mutating-verification)
and [measurement workflow](../examples/measurement-review/README.md).
