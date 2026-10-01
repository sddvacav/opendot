# Git workspace residue reporting: successor check

Date: 2026-10-01 UTC. Scope: the unreleased `0.2.0a1` successor to
`e033e8c34d196263fe111ca148fbaf5d8b450504`.

## Finding and repair

An independent review reproduced a reporting defect after a successful local
worktree add followed by loss of directory search permission. The path still
existed, but `os.path.lexists` suppressed the observation error and reported
`path_exists: false`. Branch and registration observations remained true.
The original candidate therefore required changes despite passing its 771
selected tests. No cleanup, repeated creation or containment escape was observed.

The successor checks the residual path with `lstat`: a successful observation
means true, `FileNotFoundError` means false, and other OS errors leave the value
unknown (`null`). This is best-effort observation, not proof of an atomic snapshot.
Single-attempt creation, quarantine and the prohibition on cleanup/retry remain
unchanged.

## Executed checks

- Author selection: **773 passed**, zero failed/errors/skipped, consisting of
  695 inherited portable nodes plus 78 Git nodes
- The two new regressions inject permission and other OS observation failures
  after a real successful disposable Git worktree add; residue remains and a
  repeated create is refused
- Independent source-level reproduction used an unprivileged process and actual
  directory search-permission loss: the repaired result is unknown, retained
  branch/registration are true, and the path is present after permission restoration
- The repaired Git module SHA-256 is
  `02b4dff4d9382bcaf00df655f376799658d59482c017822458d3c6f9049b6ecc`

The checks above do not constitute final wheel or release approval. Consult the
exact source/archive/wheel review receipt supplied with the candidate for that
separate decision. The predecessor's failure and passing checks retain their
original scopes in [the earlier local record](git-workspaces-verification.md).
There was no user-repository, model, native solver, device, network operation,
durable-recovery test or public release in this repair.
