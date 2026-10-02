# Callable-only execution profile

This profile was introduced in `opendot-engineering` **0.2.0a0** and is included
unchanged in this package. See the [current overview](../OVERVIEW.md) and
[installed guide](installed-quickstart.md) for release status and version-pinned
installation. Each version's source and review records retain their own scope;
the [historical a4 record](verifier-ci-verification.md) and
[profile verification record](callable-execution-verification.md) remain version-bound. The single owner is
`opendot_engineering.tool_runtime.ToolRuntime`; this is a Python API, with no
separate distribution, console entrypoint, or automatic integration.

## Run a real, bounded callable example

From the source root:

```sh
PYTHONPATH=src python -B examples/callable-execution/demo.py
```

After installing the reviewed release into an environment, run the same example with
that environment's Python. It imports the installed module and invokes actual
pure Python functions. No model, external service, native backend, or device is
used. The JSON reports five checked scenarios:

- Addition succeeds with output `5` on one attempt
- A missing declared permission blocks dispatch with `PermissionDenied`
- A declared-idempotent callable fails once, then succeeds with output `8` on its
  second permitted attempt
- A non-idempotent callable fails once and is not retried, despite `max_retries=5`
- An explicit guard whose context resolver returns `False` refuses before handler
  dispatch; every non-`None` value refuses, and the configured exception propagates
  without a receipt

```python
from opendot_engineering.tool_runtime import ToolRisk, ToolRuntime, ToolSpec

runtime = ToolRuntime()
runtime.register(
    ToolSpec("add", "1", "input/v1", "output/v1", ToolRisk.READ_ONLY),
    lambda payload: payload["left"] + payload["right"],
)
output, receipt = runtime.execute("add", {"left": 2, "right": 3})
assert output == 5 and receipt.status == "COMPLETED"
```

## Contracts and trust boundary

The six retained contract types are `ToolRisk`, `BreakerState`, `ToolSpec`,
`_ObservedToolExecution`, `ToolCallReceipt`, and `ToolHealth`. The underscored
observation remains an implementation detail exposed on receipts, not a new
stable top-level export. Public contract tests pin fields, defaults, enums,
mutability, validation, and representative reliability behavior.

Registration snapshots permissions. Execution snapshots a baseline input and
copies it for each attempt. Contract hashes describe serialized declarations and
inputs, not callable code identity, external effects, or verified idempotence.
`input_schema` and `output_schema` are required names, not an implemented schema
validator. `semantic_validator`, when supplied, is trusted Python code.
Permissions, risk, idempotence, and a nonempty `approval_token` are caller/owner
assertions; the module does not authenticate an approver or enforce an OS sandbox.
A `BLOCKED` receipt has `attempts=1` under the retained contract even though the
handler was not dispatched. Treat `attempts` as receipt policy accounting, not
proof of a side effect or handler invocation count.

One runtime owns its registry, dispatch, receipts, health, and circuit breaker.
Health is in memory. Unique probe tokens and generations prevent stale completions
from changing a newer probe's breaker authority. Health observations still count
completed attempts. There is no second scheduler or execution database.

### Guarded embedding

Standalone construction cannot discover unknown ambient context variables. An
embedding that needs refusal under a bound context must supply its trusted
resolver and actual exception class explicitly:

```python
runtime = ToolRuntime(
    guarded_embedding=True,
    current_context_resolver=trusted_resolver,
    control_error=SpecificControlError,
)
```

The guard runs before payload/permission preparation and again in the worker's
copied context before dispatch. Resolver failure denies. Configured control
exceptions and their subclasses preserve object identity and are not ordinary
retryable tool failures. The binding cannot be reassigned through normal runtime
attribute access. Trusted in-process Python can still tamper with internals;
this is not a security boundary against hostile Python code.

### Retry, timeout, and result delivery

Ordinary observed failures can retry only within the declared idempotence,
`max_retries`, and optional positive `attempt_limit` policy. Semantic-validation
failures also follow that policy. The module does not prove effect idempotence.

Timeouts, lost submission handles, interrupted result delivery, and executor
cleanup failures require reconciliation and cannot automatically redispatch.
Successful worker completion alone does not prove that its result was observed.
An ordinary failure is accepted as an observed worker error only when its exact
exception object matches the retained completion Future. Cleanup cannot replace
an active configured control exception or non-`Exception` interruption with a
retryable failure.

Timeout receipt `termination_observed` describes only a Future-level observation.
Python thread timeout and `shutdown(wait=False)` do not stop a running handler,
undo effects, or prove descendant termination. Receipts do not promise a strict
wall-clock bound over arbitrary serializer, validator, or copy hooks. The demo
and tests use only finite controlled handlers and join their workers.

`can_retry` is a local predicate. It does not persist a hold or prevent a caller
from issuing a fresh `execute`. The API has no durable recovery, cancellation
backend, process-lifetime owner, recovery-event protocol, or private-consumer
integration. `register_backend` explicitly raises `NotImplementedError`;
`execute` accepts only `granted_permissions`, `approval_token`, `backoff_base_s`,
and `attempt_limit` keyword parameters. Full legacy-runtime API compatibility is
not claimed.

## Attribution and modification record

This module reuses the OpenDot project's existing callable execution owner under
the project's Apache-2.0 license. It is a modified, bounded extraction, not a new
implementation invented for this package. The extraction retains the six
contracts and the already-reviewed callable algorithm, result-observation and
cleanup safeguards, probe ownership, and deny-only guard. Non-callable backends
and orchestration integration are outside the profile.

For this public-source preparation, the implementation changes only its module
description. Synthetic behavior tests were made portable, public contract tests
and the finite demo were added, and packaging/documentation were updated. Source
identity checks that depend on nonpublic material remain outside this repository;
no replacement public provenance fixture or origin evidence was invented. The
existing copyright and attribution in [NOTICE](../NOTICE) and the complete
[Apache-2.0 license](../LICENSE) are retained.

See [verification and exclusions](callable-execution-verification.md). This
bounded extraction is not a model-driven agent, a full platform, a sandbox, or a
claim of independent acceptance of this new combined public distribution.
