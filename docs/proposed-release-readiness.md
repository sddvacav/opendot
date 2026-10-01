# Proposed OpenDot release readiness checklist

Proposal date: 2026-09-30 UTC. **Status: separate proposal for maintainer review. No current numeric aggregate is assigned.** The criteria and 100-point weighting below are a possible release-readiness aid; they have not been adopted as the project’s scoring basis.

This proposal does not replace an established project evaluation rubric, and its potential scores are not comparable with scores from other rubrics. It must not be used to reinterpret existing evaluations. Adoption would require an explicit maintainer decision, a stated purpose, and a separately versioned assessment method.

The proposed checklist concerns a public-release candidate and its documentation. Peer documentation observations inform the suggested criteria, but peers have not been scored or tested with this proposal.

## Proposed evidence levels

| Level | Evidence standard |
| --- | --- |
| 0 | Assessed and absent, contradicted, or unusable |
| 1 | A clear draft or design exists; implementation or operational validity is unverified |
| 2 | Aligned to the actual candidate, with inspected source or policy evidence and documented limitations |
| 3 | The criterion has been exercised or verified against the candidate with reviewable results |
| 4 | A reviewer independent of the change author has reproduced or independently verified the criterion, including relevant failure paths |
| Unknown | Required evidence has not been assessed or is unavailable; this is not zero and not a pass |

If maintainers adopt this proposal for a separate assessment, the suggested calculation is the sum of each criterion’s weight multiplied by its level divided by four. Before using that calculation, document the adopted method and its scope. Report the candidate version, evidence links, reviewers, and assessment date with any resulting total. If any criterion is unknown, do not publish a numerical aggregate. No calculation or candidate scoring has been performed here.

## Proposed criteria and weights

| Criterion | Weight | Required evidence | Current assessment |
| --- | ---: | --- | --- |
| Purpose and truthful capability claims | 10 | README purpose, explicit maturity, claim-to-evidence mapping, bilingual agreement | Unknown |
| First-run experience | 15 | Clean install, verified commands, actual expected result, inspection, stop and cleanup | Unknown |
| Architecture and adapter boundaries | 10 | Current interfaces, ownership, compatibility, contract tests, and failure handling | Unknown |
| Documentation usability | 10 | Working navigation, version-aware guides, examples, reference, and reader review | Unknown |
| Contributor workflow and test quality | 10 | Actual development setup, scoped test commands, change template, and reviewed checks | Unknown |
| Reliability and scientific evidence | 15 | Workload definition, measured execution, failure/recovery evidence, units and result validation | Unknown |
| Privacy and security | 10 | Implemented boundaries, threat model, negative tests, outgoing-artifact review, reporting channel | Unknown |
| Licensing and governance | 10 | Ownership, actual approved license, notices, dependency inventory, maintainer decisions | Unknown |
| Support and troubleshooting | 5 | Verified destinations, safe diagnostics, known problems, stated support scope | Unknown |
| Release operations | 5 | Packaged artifact identity, changelog, migration/rollback plan as applicable, verified publication | Unknown |
| Proposed weight total | 100 | A separate method must be adopted before assessment | **No aggregate assigned** |

## Non-negotiable release gates

A score does not authorize publication. Unresolved exposure of private data or secrets, missing redistribution rights, unverified source/artifact identity, and material unsupported capability claims block release regardless of any total. A security reporting channel must be established before inviting vulnerability submissions.

A high documentation score cannot demonstrate scientific correctness, runtime safety, or agent scale. Report the underlying scope, including whether execution was synthetic or model-backed and whether it ran on one host or several. Do not translate a queued-workload count into concurrent-agent capacity.

## Suggested application if adopted

1. Confirm adoption and version of this separate assessment method, then freeze the candidate and list the exact public artifact set
2. Collect privacy-safe evidence for each criterion and assign reviewers
3. Record a level only after inspecting the evidence; use Unknown when it is missing
4. Resolve hard-gate failures before considering release
5. Calculate a total only after all criteria are assessed
6. Reassess affected criteria after changes and verify the distributed artifacts after authorized publication
