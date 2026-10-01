# Controlled Git profile: local verification scope

Historical author record for `e033e8c34d196263fe111ca148fbaf5d8b450504`.
Subsequent independent review requested a residue-reporting correction despite
the passing tests below. See the [successor repair and 773-case checks](git-workspaces-residue-fix.md).

Date: 2026-10-01 UTC. Unreleased `0.2.0a1` author-checked candidate. This record
covers newly authored, disposable local Git fixtures on Linux, Python 3.12.14,
and Git 2.52.0. It is not independent release approval or a supported-platform
matrix. The [API boundary](git-workspaces.md) is part of every result below.

## Actual software checks

- 76 new Git-profile cases: passed, including the two-worktree isolation example,
  porcelain/status and tracked-unstaged diff scope, binary patch output,
  staged-only/untracked exclusions, fixed base after ref movement, and index
  bytes/mtime remaining unchanged after observations
- Environment/path/config redirection and executable sentinels: passed within
  synthetic fixtures. Hooks/fsmonitor/external-diff commands never execute;
  potentially active textconv and clean/smudge/process behavior is disabled or
  refused before execution. Unsupported attributes, config includes, submodule
  entries, promisor/shallow/alternates metadata and missing objects are refused
- Ownership/refusal cases: passed for forged/other-manager/modified records,
  replaced paths, root and administrative identity, changed branches or reciprocal registration,
  external commits and unrelated-history resets that change the pinned HEAD,
  root overlap and symlinks, normalized/truncated collisions, preexisting branches,
  and single-attempt partial creation with explicitly retained residue
- Required-switch and old-version refusals: passed with injected incompatible
  Git responses, without fallback commands or creation side effects
- Inherited exact 695-node portable selection: rerun successfully with the new
  Git cases. No existing CAS/callable owner or test bytes changed
- The complete local selection is 771 distinct tests: 695 inherited + 76 new,
  771 passed, zero failed/errors/skipped. The manifests are disjoint
- Source example and isolated installed-wheel example both actually create two
  disposable worktrees, observe real edits and produce passing JSON assertions
- Source syntax, package/source/license identity, wheel RECORD, default-dependency
  absence, isolated installed origins, and bounded outgoing-content checks passed

An initial test caught Git diff refreshing its index despite the global
no-optional-locks setting. The runner now also sets `diff.autoRefreshIndex=false`;
the byte/mtime regression and final selection pass. A later review also tightened
HEAD ownership: external commits/resets are now rejected instead of treating the
base OID only as a creation snapshot. Both forms have explicit regression cases. The initial failing check is
not counted as successful evidence.

## Separate evidence and not-run boundaries

The exact `0.2.0a0` artifact/callable predecessor was independently accepted in
its own scope. That result is not inherited as proof of this new Git behavior.
The prior optional fake-only 108-case run (17 overlapping portable) was not
rerun for this Git change and is not added to the 771 new-candidate total.
No optional native/CAD/lifetime/recovery-event tests, private initializer/conftest,
original private test suite, user repository, model, Codex, device, remote write,
or publication was run. Hosted CI was not run; the existing workflow remains
its previously explicit 695-case selection. The new Git manifest requires a
separately prepared trusted Git >= 2.52.0 host.

Generated logs, temporary repositories, JUnit, wheel, source export, installed
environment, and private audit evidence remain outside the source tree. The
published source, if later accepted, includes only new synthetic fixtures and
sanitized scope/attribution documents. Receipt text is not a privacy filter.

These checks demonstrate bounded local behavior. They do not establish
protection against malicious concurrent mutation or compromised Git/host code,
OS sandboxing, scientific validity, real-consumer migration, remote operation,
crash cleanup, durable recovery, full-platform readiness, or release approval.
