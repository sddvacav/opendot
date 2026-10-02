# Controlled local Git workspace profile

`opendot_engineering.git_workspace` is the bounded, modified extraction of the
existing project `GitWorkspaceManager` owner. Its only public operations are:

```python
from opendot_engineering.git_workspace import GitWorkspaceManager

manager = GitWorkspaceManager(primary_checkout, separate_worktree_root)
workspace = manager.create("one task", base_ref="HEAD")
status_receipt = manager.status(workspace)
diff_receipt = manager.diff(workspace)
```

Run the [self-contained disposable example](../examples/git-workspaces/README.md)
first. This profile was introduced in `0.2.0a1` and is included unchanged in the
package. It is deliberately narrower than general Git; earlier review records
retain their own version-bound scope. See the [Git review record](git-workspaces-verification.md),
[residue repair](git-workspaces-residue-fix.md), and [historical a4 record](verifier-ci-verification.md).
The [current overview](../OVERVIEW.md) and [installed guide](installed-quickstart.md)
provide release status and version-pinned installation.

## Supported domain and responsibility

- Python 3.12+, POSIX, trusted Git >= 2.52.0 found in the fixed system search path
  `/usr/local/bin:/usr/bin:/bin`; the resolved executable is pinned for this manager
- A trusted, cooperative local **primary**, non-bare SHA-1 checkout with a real
  `.git` directory and all reachable history/tree/blob objects present locally
- A separate trusted worktree root whose ancestry does not contain symlinks and
  does not overlap a checkout or administrative directory
- Plain local ref names, tags, `HEAD`, or full SHA-1 commit OIDs; revision
  expressions such as `HEAD~1` are intentionally excluded
- Serialized calls and cooperative filesystem/configuration changes; no claim
  that concurrent hostile mutations, interpreter tampering, hard-link attacks,
  or executable replacement in place are prevented

This is ordinary local Git subprocess control, **not an OS sandbox**, an
arbitrary-untrusted-repository analyzer, a permission authority, or a service.
It has no scheduler, runtime, lifetime/recovery integration, model, or device
control. The caller owns and trusts the process, filesystem, Git binary, and host.
Large repositories may be expensive: safety preflights traverse checkout and
administrative files and verify object closure; no scale guarantee is made.

Windows, linked input checkouts, bare repositories, SHA-256 repositories, shallow
or partial/promisor repositories, alternate object stores, sparse checkout,
submodules, nested repositories, symlinks/special files, worktree-specific config,
config includes, and replace/graft histories are refused in this first profile.
All `.gitattributes`/`.gitmodules` files, even untracked or empty, and all configured
filter drivers are refused. Empty administrative attributes/alternates markers
are also rejected rather than interpreted. This conservative refusal is a
compatibility limit, not a promise to audit those features.

## Process and execution boundary

The owner supplies a new minimal environment, not the inherited environment.
Inherited `GIT_*`, PATH, loader variables, credential prompts, SSH helpers,
config injection, external diff, object-directory redirects, and trace paths
are not copied. Global/system config and system/global attributes are disabled.
Repository config is checked on every operation; includes and unsupported
features are rejected.

Every Git invocation uses `--no-lazy-fetch`, `--no-optional-locks`, and controlled
configuration disabling hooks, fsmonitor, external diff, credential helpers,
network protocols, maintenance, and submodule recursion. Diff adds both
`--no-ext-diff` and `--no-textconv`; `diff.autoRefreshIndex=false` additionally
prevents its index-refresh behavior. Preflights check locally reachable objects
and staged-only index blobs. Missing objects fail without fetching or prompting.

The constructor actually invokes the required global switches and checks the
version; command-specific options are exercised directly and command errors are
never retried with weaker controls. Git older than 2.52.0 is rejected even if
some individual switches exist. Local validation used Git 2.52.0/Linux only;
Git 2.52+ is a conservative admission floor, not a tested platform/version matrix.

Official mechanisms: [Git process options](https://git-scm.com/docs/git),
[worktree registration](https://git-scm.com/docs/git-worktree),
[diff options](https://git-scm.com/docs/git-diff), and
[object traversal](https://git-scm.com/docs/git-rev-list).

## Creation and ownership

Creation first validates the ref and resolves it to one full commit OID. The
single `worktree add -b` call receives that OID, never the movable ref label.
A preexisting branch, path (including dangling symlinks), normalized/truncated
slug collision, or conflicting registration fails. No branch reuse, detached
fallback, alternate name, automatic retry, or deletion occurs.

Creation validates HEAD, branch, path, reciprocal administrative registration,
and common directory after Git returns. A partial failure raises
`GitWorkspaceCreationError` with `branch`, `path`, and a best-effort
`residual_state` (`path_exists`, `branch_exists`, `registered`; `None` means
unknown). The slug is quarantined in that manager, including failures with no
visible residue. An operator must inspect residue independently. No cleanup is
implied, and this is not durable recovery state.

Only the exact object returned by that live manager is accepted. A copied,
manually reconstructed, previous-process, or other-manager workspace record is
refused. Each status/diff validates the original record, root/repository/path
identities, branch, exact pinned HEAD, common-dir, reciprocal registration and Git state before and
after the command. Ordinary completed path/branch replacement is detected;
these checks do not close malicious concurrent filesystem races. No persistent
registry or second permission system is introduced.

## Contract and observation semantics

- `GitWorkspace(goal_id, branch, path, base_ref, base_commit="")`: the original
  four positional fields remain; `base_commit` is appended. Old records can be
  constructed, but they do not grant manager ownership
- `GitReceipt(action, returncode, stdout, stderr, digest)`: the original five
  positional fields and `ok == (returncode == 0)` are preserved
- `digest` hashes the command arguments, exit code and output in the preserved
  receipt layout. It is consistency metadata, **not validation, authorization,
  authorship, a signature, or proof that all effects are acceptable**
- `status`: porcelain v1 Git status; optional index refresh is disabled
- `diff`: binary-capable **tracked unstaged worktree-versus-index** diff. It does
  not report staged-only changes or untracked file contents. Status may therefore
  be nonempty when diff is empty
- HEAD must remain equal to the immutable `base_commit` during every observation.
  External commits, resets (including unrelated history), branch switches, or
  registration replacement are refused; this profile does not adopt new baselines
- Receipts/error text can contain filenames, diffs, and paths. Review before
  sharing; they are not automatically privacy-redacted

There is no public `commit` or `remove` method and no recursive-delete fallback.
A boolean verification flag from the original broader owner is not accepted as
authority. The only removal in the example/tests belongs to the disposable test
container, not production lifecycle code.

## Extraction and checks

The original owner's name and retained data contracts are reused; process
control, safety checks, ownership binding, fixed-base creation, and refusal
behavior are modified. Broader consumers are not migrated. The target package's
Apache-2.0 license/NOTICE remain; [provenance](PROVENANCE.md) states the bounded
authorization and modification scope without embedding private source records.

See [local validation](git-workspaces-verification.md). A fixture pass does not
establish arbitrary-repository safety, scientific validity, real-consumer
compatibility, hosted-CI success, or public release acceptance.
