# Documentation and asset integration checks

Review date: 2026-09-30 UTC. Scope: the local documentation/branding integration of the bounded `0.1.0a0` adapter source candidate. This historical record is not a current release decision; later integration checks are recorded [separately](combined-candidate-verification.md). This is not a full-platform, scientific, or security certification.

## Relationship to the adapter source checks

The [adapter source verification record](verification-status.md) describes the original 45-file bounded cut and its separately executed portable selection. This integration retains all package source, tests, packaging configuration, core license/notice, existing adapter reference pages, and fixtures byte-for-byte. The only edited pre-existing file is the root README; new documentation and assets extend the tree.

The earlier portable test result was not rerun or enlarged during this documentation integration. Its exclusions remain exclusions. The original documentation-only draft review is not included or reused as combined verification.

## Checks executed for this integration

- English and Chinese README shell examples match each other and preserve the two original fixed-pin module commands
- Both commands completed from the source root with their expected bounded JSON outcomes
- A new wheel was built in separate staging and installed without dependencies into a fresh virtual environment
- Isolated installed-wheel imports resolved to the package and standard library; distribution/version, no runtime requirements, and no console entrypoints were checked
- Both fixed-pin examples completed outside the source tree using the installed interpreter and separately copied synthetic fixtures
- Wheel package source, core LICENSE/NOTICE, and current README metadata were compared with this candidate
- Relative documentation/image links and Markdown heading anchors were checked locally
- The six SVGs matched the new asset inputs; XML structure, accessible labels, and absence of script, embedded raster/font, external-resource, and event-handler content were checked
- The matching six-asset rendered preview was visually inspected for mark/wordmark legibility, theme contrast, spacing, and clipping; this is not a browser-wide accessibility review
- Source, delivery archive members, wheel members, and local Git content were scanned for bounded known-private identifiers, local-path patterns, and common credential patterns
- The proposed checklist weights sum to 100 and remain unadopted, non-replacement, non-comparable, and without an assigned aggregate

Detailed command/build/provenance receipts are retained outside the public source tree. Pattern checks have limited coverage; absence of a match does not prove absence of all confidential content or establish redistribution rights.

## Not run or established

- No new full-suite or native CAD/solver test result
- No actual process-lifetime, cancellation/recovery, model, device, agent-scale, or multi-host evaluation
- No hosted CI, remote publication, registry upload, or supported-release approval
- No independent scientific qualification, complete legal/privacy clearance, or verified support/security-reporting destination

README results retain `scientific_accepted: false`; qualification results also retain `device_control_authorized: false` and `real_device_qualified: false`. Do not combine these local checks with unrelated development results to promote a stronger claim. Recheck affected artifacts after every further edit.
