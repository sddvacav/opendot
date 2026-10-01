# Disposable local Git example

From the source root with Python 3.12+ on POSIX and trusted system Git 2.52+:

```sh
PYTHONPATH=src python -B examples/git-workspaces/demo.py
```

After installing the reviewed wheel, run a copy of this example outside the
checkout with the chosen environment's `python -I -B demo.py`. No source import
path or private initializer is required.

The example creates its own temporary primary repository and two linked
worktrees. A tracked edit and untracked file in the first leave the second and
primary checkout unchanged. `status` sees both; `diff` contains tracked unstaged
content only. Results are JSON booleans without absolute paths or private source
identities. The fixture removes its own temporary container on exit; the owner
exposes no production removal/commit method.

This is a local software fixture, not a sandbox, adversarial-race test, scientific
result, credential service, or model/device execution. Read the
[API and compatibility boundary](../../docs/git-workspaces.md).
