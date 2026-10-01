# Adapter Git provenance repair checks

Historical repair record, checked locally on 2026-10-01 using CPython 3.12.14, Git 2.52.0 and pytest 9.1.1.
The exact repair later passed independent bounded review; its combination with
the accepted fake-only candidate is recorded [separately](provenance-integration-verification.md).
This repair extends the existing geometry provenance helper and updates its
geometry, mesh, thermal and structural callers. It does not add a source owner
or modify the canonical source-audit implementation.

## Executed scope

- 43 new Git/stdlib-only cases passed: actual clean/dirty membership; ignored or
  untracked installed copies; literal unusual paths; unborn/index-only/removed,
  symlink and conflicted entries; linked worktrees; nearer broken/non-owning
  markers; root mismatch; inherited Git routing/index/config/object/discovery
  overrides; null worktree paths; failed or changing probes; all four call sites
- Raw byte changes hidden by assume-unchanged, skip-worktree or line-ending
  normalization still report dirty when membership is verified
- Configured clean/process filters return hash-only without executing their
  harmless fixture sentinel commands
- 437 existing selected portable cases passed, including source admission,
  source audit, synthetic qualification and portable CAD/CAE contracts
- Combined selection: **480 passed, 0 failed, 0 skipped**
- All retained Python source/test files parsed; Git whitespace checks passed
- A fresh wheel was built outside the checkout, installed without dependencies
  into a new virtual environment, and checked using `python -I -B`
- Installed package imports stayed isolated and loaded no optional native
  backends; all four installed adapters returned hash-only Git provenance
- Installed source-audit and qualification examples passed their bounded
  software contracts; scientific/device-control/real-device flags remained false
- Wheel source bytes and LICENSE/NOTICE matched the candidate; no runtime
  dependencies or console-script entry points were added

The 437 existing cases use the 92-node selection in
[the earlier portable report](verification-status.md#reproduce-the-reviewed-portable-selection),
excluding its five Python-child import/CLI nodes, plus the complete
`test_source_admission.py` and documented mesh-example test. The five nodes were
excluded to avoid invoking their unflagged Python children; separate isolated
`-I -B` installed import and CLI smoke checks were performed instead. Pytest
caches and bytecode were disabled, and fixture/build/report outputs were outside
the source tree. The new regression file can be selected independently:

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -B -m pytest -q -ra -p no:cacheprovider \
  tests/test_adapter_provenance.py --basetemp=/tmp/opendot-provenance-fixtures
```

Use a new owned external base directory for each run. Git fixture commands are
local and synthetic; no native backend is required.

## Compatibility and limits

The source-record keys are unchanged. `worktree` remains present but is always
null in new adapter source records. `GIT_UNVERIFIED_SOURCE_HASH_RECORDED` is an
additional fallback status; repository commit and dirty fields remain null on
uncertainty. Content-filter configurations conservatively fall back to hash-only.
Line-ending-normalized raw adapter bytes may conservatively report dirty.

Historical receipts and copied parent packs remain unchanged and readable.
This repair does not remove paths from other native fields, rewrite old source
metadata, authenticate upstream authorship, or make repository reads atomic.
See [the exact provenance boundary](cad-geometry.md#evidence-and-deterministic-behavior).

No native CAD, mesh or solver run, physical/scientific acceptance, process-lifetime
or recovery work, hosted CI or publication was performed. Prior native evidence
does not transfer to this source revision or its successor. Independent review
of each changed combined artifact and any exact-revision native claim remain
separate gates.
