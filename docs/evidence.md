# Evidence and benchmark reporting

The included local checks cover source auditing, invented qualification records, packaging, and selected portable tests within their stated scopes. No live agent/runtime benchmark was executed for this documentation integration. Peer documentation review is separate from software-performance comparison. See [source verification](verification-status.md) and [integration checks](integration-review.md).

## Scope boundaries

Source-audit checks, packaged-installation checks, synthetic workload checks, live agent evaluations, and scientific validation are separate forms of evidence. Passing one does not establish another. A synthetic command-line demonstration must be labeled as such, and may be published only after its standalone source and outputs have passed privacy review.

No result in this source candidate establishes simultaneous-agent scale, multi-host execution, live model quality, production readiness, or release approval. Prior development records must not be treated as a public release qualification without verifying the actual released artifact. Private source history and operational identifiers do not belong in public reports.

## Every published result needs a reproducible record

| Field | What to record |
| --- | --- |
| Artifact | Public software version, dependency versions, and build provenance |
| Workload | Input fixture, job definition, acceptance criteria, and synthetic/live distinction |
| Environment | Host count, worker count, resource classes, network topology, and constraints |
| Execution | Start/finish times, attempts, retries, cancellations, and terminal outcomes |
| Concurrency | Actual overlapping execution intervals, how calculated, and any sampling limits |
| Model involvement | Provider/model when used, actual calls, token usage/cost method, and failures |
| Correctness | Output validation, deterministic checks, review method, and failed cases |
| Reliability | Interruptions, restarts, injected failures, lost work, duplicates, and cleanup |
| Privacy | Public-fixture provenance, redaction review, and reviewed outgoing artifacts |
| Scope | What the result establishes and what it does not establish |

Queue depth, configured capacity, worker registrations, and actual concurrent execution are separate measures. Publish all relevant counts, rather than substituting one for another. A null or missing measurement is not zero.

## Suggested evidence ladder

1. Clean installation and entry-point verification
2. Deterministic model-free fixture with inspected evidence output
3. Lifecycle tests covering failure, cancellation, and documented resume behavior
4. Adapter contract tests against declared upstream versions
5. Small live model-backed work with declared costs and transmission
6. Multi-dot and multi-host trials only when those capabilities exist
7. Longer-duration qualification against a predeclared workload and acceptance criteria

Every step requires its own recorded outcomes. This sequence is a validation proposal, not a test-completion claim. Do not label any step passed until the actual evidence has been inspected.

## Comparative results

For a future comparison, choose equivalent tasks, versions, resources, budgets, evaluation rules, and failure handling before collecting results. Publish limitations and unsuccessful runs. Do not infer superiority from repository stars, feature lists, framework adoption, or a polished README.
