# OpenDot host orchestrated development receipt

On 1 October 2026, an external host coordinated three public-code changes using installed OpenDot 0.2.0a2. Two measured worker intervals overlapped; a third task followed later. All three changes received independent acceptance for integration and were merged with ordinary Git. **At this intermediate integration checkpoint, aggregate release tests and rebuilt integrated-wheel acceptance were pending.** The later candidate has [899 combined source passes](../parallel-development-verification.md); final exact-artifact acceptance remains separate.

The companion [JSON receipt](receipt.json) preserves full commit identities, file and evidence hashes, timing inputs, review results and claim boundaries.

## What OpenDot actually did

The installed package's GitWorkspaceManager created three distinct branches and worktrees from base commit `05f70828f6ec927b85bc5591a5bee1e0a84f7ebf`. Its live instance later ran status and diff successfully for every worktree.

- `demo-errors`: concise CLI errors for existing demo output paths
- `cli-help`: a read-only module help and version entrypoint
- `research-index`: offline research-index consistency tests, added in a later expansion

At the pre-integration seal, every HEAD still equaled the base, every index was empty, and unowned tracked files matched baseline bytes. These are checked Git worktree boundaries, not an OS sandbox. Task manifests described scope and budgets without enforcing them.

OpenDot ArtifactStore recorded the shared input inventory, seven reviewed output files and three manager-observation objects under SHA-256 identities. Output bytes matched the independently reviewed hashes and passed CAS verification and readback checks. The input inventory hash is `f56dae48062b6c1f0bfa489fce5e8ad8b0e0b5c553cabe0b83843051bbc47e9e`.

Manager diff covered tracked, unstaged changes only. The new files in cli-help and research-index therefore produced empty tracked diffs; their bytes were separately inventoried and sealed. Hash identities in the receipt are evidence identifiers, not public download URLs.

## Measured overlap

All intervals are on the same host, calculated from monotonic timestamps. Initial read-only orientation is outside the A/B intervals.

| Task | Recorded interval on 1 October 2026 UTC | Duration |
|---|---|---:|
| demo-errors | 08:07:01.996647–08:10:23.271796 | 201.275148216 s |
| cli-help | 08:07:17.258449–08:11:59.378928 | 282.120480639 s |
| research-index | 08:17:13.903269–08:22:24.511184 | 310.607912645 s |

The A/B overlap is **186.013346186 seconds**: the earlier finish minus the later start. Their combined elapsed window is 297.382282669 seconds. research-index began 314.524340105 seconds after that window ended, so it is a sequential expansion, not a third overlapping worker.

These measurements establish overlapping implementation and validation intervals. They do not establish simultaneous model inference or a speedup against a serial baseline.

## Independent acceptance

For A/B, acceptance cases and probes were frozen against the fixed base before inspecting the stopped workers' implementations.

- demo-errors: 18 independent probes passed; baseline probes had 8 expected failures. The reviewer reran 80 focused tests successfully
- cli-help: 7 independent source probes and 20 source tests passed. The 7 probes also passed against the author's locally installed 0.2.0a2 wheel; this repeats behavioral coverage and is not the integrated release wheel
- research-index: a later supplemental review passed 44 tests and rejected 10 additional invalid-fixture mutations. This review followed implementation and does not share the A/B implementation-blind claim

The demo preflight remains non-atomic. CLI passivity findings are scoped to reviewed code and commands. Research checks cover offline structural consistency, not source truth, live-link reachability, endorsement or feature acceptance. Test counts are not a count of unique cases across all runs.

## Integration and remaining gate

After sealing, the integrator used ordinary Git commits and merges, separately from the manager API:

- demo-errors: `041bc5f7812d8acafd805fb50f1da2830801b57b`
- cli-help: `c46ee21090ef6409c88deff5390575be7ea6d328`
- research-index: `dce8122d65ee095055783c2f1ac6105ec4c5ef71`
- Integrated commit: `1a5cb108ca264349dfc9f0775d4749ab70cbd797`

The integration record reports a clean working tree. Final acceptance must separately check the aggregate release commit, preserved worker bytes, release-owned changes, rebuilt artifacts and isolated installed behavior.

This is one-host, externally orchestrated development evidence. It does not demonstrate a standalone OpenDot orchestrator, multiple hosts, durable recovery, runtime quota enforcement or measured model/token/cost usage.
