# Source-boundary acceptance example

This **source-only, synthetic example** runs six bounded cases from the 15-case
research proposal. It imports the existing `ToolRuntime`, `ToolSpec`,
`ArtifactStore`, and `ArtifactRef`; it changes none of their implementation bytes
and introduces no second registry, security runtime, permission owner, provider,
native backend, network access, or job/lifetime integration. The example itself
changes no owner bytes; integrated a6 separately includes the reviewed optional
read-only change in the same canonical artifact owner.

## Run

From the repository root, with the existing test tooling prepared:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -B examples/source-boundary/demo.py --output /tmp/source-boundary-new
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src python -B -m pytest -q -p no:cacheprovider tests/test_source_boundary_example.py --basetemp=/tmp/source-boundary-tests-new
```

Use a **new** output directory beneath an existing trusted parent. The runnable
example creates local evidence artifacts and in-memory synthetic effects only.
The source test requires pytest; the example itself uses the standard library
and the existing package. Integrated a6 selects its 38 tests in the explicit
[source-boundary manifest](../../ci/source-boundary-nodes.txt). The example files
remain source material, not wheel contents; any copied-example run against an
installed wheel is a separately recorded check.

## What was executed

- `EVIDENCE-PRESENT`, `EVIDENCE-MISSING`: an example-specific two-field precheck
  accepts one readable synthetic spec or refuses the dependent call before
  dispatch. A missing target is never guessed. The missing-input receipt has
  `runtime_status=NOT_DISPATCHED` and `receipt=null`; no runtime refusal is forged.
  Input evidence and reporting are still written. This is **not** a built-in
  required-evidence policy or an access-authority check in `ToolRuntime`.
- `TRUST-BENIGN`, `TRUST-EXTRA-EXPORT`: the canonical runtime executes a permitted
  summary, but refuses an explicitly attempted offline fake-export callable
  with `BLOCKED/PermissionDenied`. Caller grants remain fixed trusted Python
  configuration. Text, role labels, claimed receipts, approval tokens, and
  `granted_permissions` inside the payload do not become execute-keyword grants.
  A local sentinel observes whether the export handler actually ran. No model
  interprets the attack and no real export or third-party contact occurs.
- `TRAJECTORY-APPROVED`, `TRAJECTORY-UNAPPROVED`: a fixed, bounded handler replays
  events against two in-memory values and records those effects. A synthetic
  post-hoc oracle checks prior approval target/value/order separately from the
  observed final values. The existing semantic-validator hook returns
  `FAILED` even when both values are correct if process rules fail. The
  unaccepted result remains in CAS. **This does not prevent or roll back the
  simulated bad write**, and fixture `approval` events are not authentic user
  authorization. This oracle observes only the cooperating example handler.

Additional tests inject forged grants/roles/receipts, missing targets, wrong
approval scope/value/order, false final-state claims, malformed or absent events,
and utility failure despite zero export effects. These are deterministic
software checks, not prompt-injection immunity or a benchmark of an LLM.

## Explicit gaps

The nine remaining original proposals are `NOT_IMPLEMENTED` / `NOT_RUN`:
`EVIDENCE-CONFLICT`, `EVIDENCE-DENIED`, all four `GUI-*` cases,
`TRUST-ALL-REFUSED`, `TRAJECTORY-PARTIAL`, and `CONSISTENCY-ALL-TRIALS`.
Related negative unit tests do not promote those original protocols to executed
coverage. All 15 proposals retain `production_enforcement=NOT_IMPLEMENTED`.

The runtime receives grants from a trusted Python caller; it cannot authenticate
the caller or prevent a caller from explicitly granting an export permission.
It has no production required-evidence checklist, source-trust propagation,
authenticated approval ledger, complete effects monitor, or pre-effect process
policy enforcement. These are precise open boundaries, not solved by this
example. Missing process evidence is `UNKNOWN` and cannot pass. SHA-256/CAS
integrity proves stored-byte consistency only. The CAS root remains trusted and
caller-controlled, with its existing symlink/nontransactional limitations.

## Evidence and primary sources

[proposals.json](proposals.json) is the byte-for-byte original 15-case input
(SHA-256 `5a581f3a9e3d6e9a92e3cd95bb95692fa253aa6305d5163a022e3ef23562a4da`).
Its historical `NOT_EXECUTED` header is intentionally unchanged. New observed
coverage is recorded separately in the generated `report.json`; each case
stores its exact input and result through canonical `ArtifactRef` contracts,
links the result to its input source reference, and retains the actual runtime
receipt and observations. Generated receipts remain outside the source tree.
Hashes are not signatures or independently authenticated author evidence.

The source-to-need interpretation comes from the [historical 2026-10-01 research
annex](../../docs/research/demand-gap-20261001/README.md)
(`source-needs-delta.json` SHA-256
`f6b274298df5e150c7a277e8e4ff554b5feea1dffbf832c5d400048e4217d932`):

1. [Lidang's original post](https://x.com/lidangzzz/status/2086770543206785383),
   displayed 2026-08-10: organized, available business information motivates
   the required-evidence example. This is a design inference, not customer or
   procurement evidence and not a normative runtime specification.
2. [AgentDojo v3](https://arxiv.org/abs/2406.13352v3), 2024-11-24,
   sections 3.1 and 3.4: benign utility and unauthorized effects deserve
   separate evaluation. This example does not reproduce the benchmark.
3. [tau-bench v1](https://arxiv.org/abs/2406.12045v1), 2024-06-17, section 3:
   final-state agreement can miss a process-policy violation. Our local oracle
   illustrates that caveat; it is not the original benchmark's policy checker.

These are primary-source links carried from the annex; no new source retrieval,
publisher-byte archive, endorsement, model consensus, scientific acceptance,
device-control authority, or independent review is claimed.
