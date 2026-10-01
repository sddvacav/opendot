# Validate one descriptive manifest

This example uses the real public `Capability` and `AgentManifest` classes,
constructs illustrative text-summary metadata, explicitly validates it, and
prints JSON with immutable sets projected to sorted lists. It executes no agent,
model, tool, provider, or native backend and writes no output files itself.

From the source root with Python 3.12+:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -B examples/agent-contracts/demo.py
```

Expect `package_version: "0.2.0a4"`, `metadata_valid: true`, and both
`agent_execution_performed` and `runtime_enforcement_provided` to be `false`.
Reliability, cost, and latency are illustrative declarations, not observations;
no currency or latency unit is specified by these contracts.

For a wheel-only check, install the matching reviewed wheel using the
[installed quickstart](../../docs/installed-quickstart.md), copy this source
example outside the checkout, then use the isolated interpreter:

```sh
"$PY" -I -B "$JOURNEY/examples/agent-contracts/demo.py"
```

The wheel contains the package, not the example. `validate()` must be called
explicitly; construction alone accepts malformed values. Frozen dataclasses
are shallow, and declared permissions/budgets are not enforced at runtime.
The JSON projection is example output, not a newly defined wire protocol.
See [the API guide](../../docs/agent-contracts.md).
