# Canonical agent metadata contracts

Introduced in `0.2.0a2` and retained unchanged in this package,
`Capability` and `AgentManifest` belong to the
existing `opendot_engineering.core.contracts` owner. `core` re-exports the same
class objects. There is no `DotManifest` alias or second contract owner.
The [metadata review record](agent-contracts-verification.md) and
[historical a4 record](verifier-ci-verification.md) retain separate
version-bound scopes; earlier acceptance does not approve a successor. See the
[current overview](../OVERVIEW.md) and [installed guide](installed-quickstart.md)
for release status and version-pinned installation.

These are descriptive frozen dataclasses, not an executable agent API. A manifest
does not register capabilities, resolve schemas or tools, invoke a provider,
execute work, or enforce permissions, budgets, turn limits, memory scope, or an
oracle. Existing consumers have not migrated to these objects.

## Construct and explicitly validate

```python
from opendot_engineering.core import AgentManifest, Capability

capability = Capability("summarize", "1", 0.9, 0.0, 0.1)
manifest = AgentManifest(
    "summary-agent", "Summarize supplied text", frozenset({"summarize"}),
    frozenset({"read-text"}), frozenset({"send-message"}), "text/v1", "summary/v1",
)
capability.validate()
manifest.validate()
```

Construction does not validate. Call `validate()` explicitly at the boundary
where metadata is accepted; it returns `None` for valid values and raises
`ValueError` for the invalid built-in values described below. Validation does
not normalize strings, resolve identifiers, measure reliability, or inspect a
permission authority. Descriptor strings are opaque and case-sensitive.

## Declared shape

Field order, names, annotations, and defaults are retained from the reviewed
project contracts. Required fields precede the following optional defaults:

| Class | Required fields in order | Optional fields in order |
| --- | --- | --- |
| `Capability` | `name: str`, `version: str`, `reliability: float`, `cost: float`, `latency: float` | `permissions: frozenset[str] = frozenset()`, `tags: frozenset[str] = frozenset()` |
| `AgentManifest` | `agent_id: str`, `purpose: str`, `capabilities: frozenset[str]`, `allowed_tools: frozenset[str]`, `denied_tools: frozenset[str]`, `input_schema: str`, `output_schema: str` | `max_turns: int = 20`, `max_cost: float = 5.0`, `memory_scope: str = "session"`, `oracle: str = "default"` |

Cost and latency units are not specified by these contracts. In particular, no
currency or conversion between `cost` and `max_cost` is defined. Values and
reliability are caller-supplied metadata, not measured guarantees.

## Validation and compatibility

- Every string field, including `memory_scope` and `oracle`, must be a nonempty,
  non-whitespace string. Leading/trailing whitespace in otherwise nonblank
  strings is retained
- `permissions`, `tags`, `capabilities`, `allowed_tools`, and `denied_tools` must
  be `frozenset` values containing only nonblank strings. Empty sets are valid;
  mutable sets, lists, tuples, and individual strings are rejected
- Allowed and denied tool sets must be disjoint
- Reliability must be a finite number in `[0, 1]`
- Cost, latency, and maximum cost must be finite nonnegative numbers. Zero is
  valid; ordinary Python integers and floats are accepted, excluding booleans.
  Integers have no added size ceiling
- `max_turns` must be a positive Python integer, excluding booleans and floats

These are deliberate invalid-input compatibility changes from the previous
project validators: wrong types, blank descriptors, mutable or malformed sets,
non-finite numbers, booleans, and fractional turn counts are now rejected.
Valid declared field shapes/defaults remain intact. The existing `ArtifactRef`
body and behavior are unchanged; these stricter rules are not retrofitted onto it.

`frozen=True` is shallow Python immutability. It prevents ordinary field assignment,
not hostile mutation or construction with wrong types. It is not OS security,
a sandbox, an authorization grant, or a guarantee that a consumer validates.

## Serialization and example

`dataclasses.asdict()` preserves `frozenset` values, so the result is not directly
JSON serializable. The [small example](../examples/agent-contracts/README.md)
explicitly projects them to sorted arrays for display, with non-finite JSON
numbers disabled. That display is not a newly versioned wire format or bundled
schema validator. Callers reconstructing records must restore the immutable
sets and explicitly validate again.

Read [ADR 003](decisions/003-agent-metadata-contracts.md) for the exact admission
boundary and [verification](agent-contracts-verification.md) for candidate-bound
checks. No original initializer, registry, execution harness, provider/runtime
integration, or authority-enforcement layer accompanies this extraction.
