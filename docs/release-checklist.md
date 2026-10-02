# OpenDot release checklist

Current release, 2 October 2026: **[0.3.0a3 ALPHA prerelease](https://github.com/sddvacav/opendot/releases/tag/v0.3.0a3); NOT_SCORED**. The [released source commit](https://github.com/sddvacav/opendot/commit/30610de43da81801e7b88517459fbdf0f667ca2d), tree `95ca23d9d36558680c809f2382bef188c6fc2ae4`, and [release notes](https://github.com/sddvacav/opendot/releases/download/v0.3.0a3/RELEASE-NOTES.md) bind the exact assets to their separately scoped source, build, installed and independent checks. The [a3 main portable run](https://github.com/sddvacav/opendot/actions/runs/36982326482) and [a3 PR Temporal run](https://github.com/sddvacav/opendot/actions/runs/36981793339) are distinct source checks; the latter tested PR merge revision `7ab3c1f7be3dd22024239cf3d4d4813f7646a7d3` with the same source tree, not the later main commit. The five named public release downloads were checked against the accepted bytes. This does not establish production readiness, scientific acceptance or a supported-platform matrix.

The frozen a3 assets include the optional bounded-read API and pure finite-batch preparation. Later [source-only live-batch and retention evidence](temporal-reference-transport.md#later-source-only-200-job-qualification-2026-10-02), including merged [PR #30](https://github.com/sddvacav/opendot/pull/30), does not change those assets or add installed-release acceptance. The [current installed guide](installed-quickstart.md) is a later documentation follow-on with a3 pins; the frozen source archive retains its historical a2 guide text. Release-asset preparation wording and historical records remain unchanged.

The [bounded a3 component inventory](release-inventory/v0.3.0a3/README.md) is an additive custom-JSON supplement for the unchanged a3 assets; it is not a full transitive/native SBOM or legal/security certification.

Historical a2 release checks: the [a2 main portable run](https://github.com/sddvacav/opendot/actions/runs/36964156448) and [a2 PR Temporal run](https://github.com/sddvacav/opendot/actions/runs/36963928744) retain their own source scopes. The latter tested a PR merge revision with the a2 released source tree, not the later main commit. Their [a2 release notes](https://github.com/sddvacav/opendot/releases/download/v0.3.0a2/RELEASE-NOTES.md) do not qualify a3.

Historical pre-release checkpoint for the source-only follow-on to **0.3.0a1**:
**unreleased; NOT_SCORED** at that checkpoint. The
[historical successor verification scope](structural-v2-candidate-verification.md) declares
1,325 portable / 1,484 controlled-local nodes. Actual source, offline build,
installed and independent outcomes require exact-candidate external receipts.
No successor hosted run or publication was established at that checkpoint. Frozen a6 evidence remains
version-bound and is not an acceptance of the changed default schema/profile.

Historical release disposition for `0.2.0a4`: **unreleased source candidate; 1,066 selected author source checks passed with zero failures/errors/skips. Exact final outgoing-artifact and installed acceptance require separate receipts, and a publication destination remains unverified.** Separately accepted solver-gate and documentation-checker component reviews overlap the source selection; they are not additional unique coverage and do not accept the final artifacts. The 988-node portable CI definition excludes 78 local Git cases and has not run on hosted CI. See [historical a4 verification](verifier-ci-verification.md).

Predecessor source-admission, fake-only simulation, combined-artifact and Git-provenance repair reviews retain their narrow scopes. The historical 0.2.0a3 [source record](parallel-development-verification.md), final `a59419b` installed journeys through all eight blocks per language, and [same-host build experiment](build-toolchain.md) do not transfer to a4. Earlier scores are not reassigned to this candidate. Local [source checks](verification-status.md), [integration checks](integration-review.md), [artifact/callable checks](execution-core-verification.md), [Git residue repair](git-workspaces-residue-fix.md), [provenance-integrated checks](provenance-integration-verification.md) and [earlier combined record](combined-candidate-verification.md) remain version-bound.

This checklist does not create a new consent gate or revoke prior authorization; local integration and public publication remain distinct actions. The reusable checkboxes below are review prompts for a specific future release, not the status record for the published a3 assets. They are not automatically closed by component or predecessor checks; the exact a3 disposition is linked above.

## Source and integration

- [ ] Verify the canonical source, ownership, intended release contents, and public version
- [ ] Produce a standalone public source tree and review its provenance and privacy boundaries
- [ ] Review the exact adapter/documentation/asset integration diff; keep future runtime work outside this release scope
- [ ] Confirm dependencies and adapters against an explicit compatibility matrix
- [ ] Confirm the packaged artifact contains the intended files and working entry points
- [ ] Bind the reviewed source-selection outcomes to the exact outgoing revision; do not add overlapping component counts or transfer results after later changes

## Reproducibility and runtime

- [ ] Rebuild the exact candidate with the [pinned build backend](build-toolchain.md) and record fresh source, toolchain and output identities
- [ ] Run clean-environment installation outside the source tree
- [ ] Execute the documented first example from the installed artifact
- [ ] Check unit, integration, end-to-end, and packaging scopes separately
- [ ] Record passed, failed, skipped, and not-run checks with their exact scope
- [ ] Test timeouts, retries, interruption, cancellation, resume, and child-resource cleanup as applicable
- [ ] Verify resource limits and permission decisions, including after resume
- [ ] Validate scientific inputs, units, outputs, and acceptance checks for each example
- [ ] Publish performance claims only with the reproducible evidence defined in [Evidence](evidence.md)

## Privacy hard gate

- [ ] Inventory every outgoing file, archive member, example, image, log, trace, and generated document
- [ ] Check secrets, credentials, personal information, confidential content, and private operational identifiers
- [ ] Check private names, machine paths, metadata, screenshots, comments, and bundled history
- [ ] Inspect actual package/distribution contents, not only the source tree
- [ ] Review external data destinations and require the necessary authorization before transmission
- [ ] Run appropriate automated checks and a human/contextual review; record both scopes and limits
- [ ] Fix each finding and recheck the affected output
- [ ] Obtain an explicit release-review decision; unresolved privacy findings block publication

## Licensing and governance

- [ ] Verify rights to distribute all included source, fixtures, images, and documentation
- [ ] Verify redistribution rights against the retained Apache-2.0 LICENSE, core NOTICE, and new asset notice
- [ ] Inventory adapter and dependency licenses, attribution, and notice obligations
- [ ] Publish the actual contribution process and responsible maintainers
- [ ] Establish supported versions and verify a private vulnerability-reporting route
- [ ] Confirm any contributor agreement or conduct policy before stating that it applies

## Documentation and messaging

- [ ] Run the bounded [source-only documentation checks](documentation-checks.md); record local-link/fragment and explicit-anchor scope separately from command execution
- [ ] Recheck all eight bilingual shell blocks against the exact outgoing installed artifact; literal parity is not an executed walkthrough
- [ ] Review README translations for matching capabilities and limitations
- [ ] Reconcile every public capability statement with the [claim-status matrix](claim-status.md)
- [ ] Verify support, repository, download, and release-note destinations
- [ ] Remove misleading badges, testimonials, affiliation claims, unmeasured scores, and unsupported guarantees
- [ ] Record release changes, breaking changes, migration steps, known issues, and remaining limits

## Readiness assessment

The [proposed release-readiness checklist](proposed-release-readiness.md) is a separate, unadopted review aid. It does not replace the project’s established evaluation rubric or yield comparable scores. No current numeric aggregate is assigned. A numerical assessment can never override a privacy, security, licensing, or source-integrity blocker.

## Publication decision record

Record the reviewed version, artifact set, checks, privacy review, license review, accepted limitations, decision, date, and responsible approver. Keep private evidence private; expose only the approved public summary.

Do not publish automatically because all documents exist. Publication is a separate action requiring authorization and verified destinations. After authorized publication, verify that the delivered artifacts match what was reviewed.
