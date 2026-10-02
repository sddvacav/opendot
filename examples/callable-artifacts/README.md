# Callable writes a canonical artifact

This small standard-library example uses both existing owners from the single
`opendot-engineering==0.3.0a5` candidate distribution. Use its matching
[installed guide](../../docs/installed-quickstart.md); earlier results remain historical. It is finite local software work with
invented text. No model, native solver, device, controller, or remote service runs.

From the source root, choose a fresh directory outside the checkout:

```sh
OUTPUT_PARENT=$(mktemp -d /tmp/opendot-composition.XXXXXX)
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -B \
  examples/callable-artifacts/demo.py --output "$OUTPUT_PARENT/result"
```

After installing the reviewed wheel into a fresh environment, invoke the same
example file with that environment's `python -I -B`, from outside the source tree.
The example is source material, not a second installed package or controller.
The output directory must not exist; its parent and ancestors must be trusted.

The JSON separates three cases:

- Success: a permission-gated callable writes text with `ArtifactStore`, returns
  the same canonical `ArtifactRef`, and obtains a `COMPLETED`, semantic-valid
  `ToolCallReceipt`. The example reads bytes and independently computes SHA-256
- Semantic refusal: the callable writes before its validator rejects the result.
  The receipt is `FAILED`, semantic-invalid, and no result is returned. The local
  side-effect observation still locates an intact, hash-verified, unaccepted
  object. Failure is not rollback, and storage integrity is not task acceptance
- Missing permission: `BLOCKED/PermissionDenied`, zero handler calls, zero stored
  objects. The store constructor still creates empty local directories

`synthetic_software_assertions_passed` describes only these invented software
assertions. No scientific acceptance or real-consumer migration is established.
The example disables retries and declares the handler non-idempotent. Neither
that declaration nor the `REVERSIBLE_WRITE` risk label implements undo. Permissions
are checked at dispatch, not enforced by an OS sandbox or by CAS. See the
[callable](../../docs/callable-execution.md) and
[artifact](../../docs/canonical-artifacts.md) limits.
