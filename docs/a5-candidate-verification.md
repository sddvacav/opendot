# 0.2.0a5 candidate verification boundary

Date: 1 October 2026 UTC. Version: **0.2.0a5**, separate and unreleased.
This page identifies the current candidate and its evidence requirements.
The local author checks below have separate source, installed and guide scopes.
Final source/artifact hashes and independent acceptance are recorded in the
external delivery receipts; predecessor evidence is not promoted to a5 acceptance.

## Changes and preserved behavior

- Inherit the [CPU-ceiling minimum fix](solver-cpu-ceiling.md) from `a189ecf`:
  the existing solver child uses the minimum of 300 seconds and finite inherited
  soft/hard CPU limits, including zero. Fake-resource tests do not prove kernel
  enforcement or native lifetime behavior
- Add [explicit optional energy consistency](structural-elastic-energy.md) in
  the existing structural owner. Strict artifact admission runs first, then
  each element's printed tensor strain E is compared with its whole-element ELSE
- A successful API report says `CONDITIONAL_ELASTIC_ENERGY_CONSISTENCY_PASS`,
  `scientific_accepted = false`, no-underflow `ASSUMED_NOT_VERIFIED` and arithmetic
  error bound `NOT_PROVED`. These conditions are not scientific acceptance
- Preserve existing default verifier bodies, report semantics, tolerances and
  command behavior. Calling the default verifier does not perform the optional
  check; its constitutive-energy and other numeric-field consistency gaps remain
  open. The inherited lower-hard-file-size-limit issue is also unchanged
- Keep the canonical artifact/callable owners, package namespace, licensing and
  required notices. No second runtime, permission, recovery or storage owner is
  introduced

## Current verification ledger

| Scope | Declared selection or purpose | Current a5 outcome |
| --- | --- | --- |
| Portable source | 1,104 explicit cases: 1,033 inherited + 17 CPU-ceiling + 54 elastic-energy | Included in the successful 1,263-case local union; not an additional pass total |
| Controlled local source | 1,263 explicit cases: portable 1,104 + 78 existing Git + 81 source-inventory | Author: 1,263 passed plus 49 subtests; zero failures/errors/skips on trusted POSIX Git 2.52.0 |
| Offline build | Isolated build with the pinned build toolchain; exact source, wheel and sdist identities | Author offline build passed: 19 Python payloads match source, wheel RECORD validates, LICENSE/NOTICE preserved; exact hashes in delivery receipt |
| Fresh installed checks | 71 selected installed checks, separate from source totals | Author: 71 passed plus 49 subtests; fresh installed origins verified |
| English installed guide | All eight shell blocks in a fresh environment and external working directory | Author: all eight blocks passed in a fresh installed environment |
| Chinese installed guide | All eight shell blocks in another fresh environment and external working directory | Author: all eight blocks passed in a fresh installed environment |
| Optional old native-pack replay | Read-only verification of an already generated pack; identify the old pack and current verifier separately | No new native execution; any replay needs its own receipt |
| Hosted CI, remote publication and scientific acceptance | Outside this local candidate verification | Not established |

Collection established 1,104 portable and 1,263 full-local unique selections.
Subtests and repeated installed checks are separate observations, not additional
unique test nodes. Source checks do not establish installed imports. Guide
parity checks do not execute commands. Build or installation success does not
constitute release approval.

The final delivery receipt identifies the exact checked source and build
inputs, actual commands/environment, wheel and sdist hashes, successful and
failed/skipped/not-run checks, installed import locations, and remaining limits.
Generated receipts and outputs remain outside the source tree. Source and installed
checks are repeated against the frozen final candidate, and final build outputs
are checked against its source bytes. No predecessor total is copied into a
current pass claim.

The 17 installed CPU cases retain their original fake-resource assertions; an
external runner binds only their `SOURCE` constant to the installed thermal
module before collection. This tests the installed callback AST, not kernel CPU
limits or a native process. The 54 energy cases use copied public synthetic
fixtures and installed package imports, without a source-tree import path.
The source union and installed reruns overlap; neither subtests nor guide
examples are added to the unique source-case count.

## Historical evidence stays historical

- Original a4 `4075ac17`: [1,066 selected author source passes](verifier-ci-verification.md)
  and a 988-node hosted definition; component results overlap that aggregate
- a4 source-only extension through `e5e7a9b`:
  [1,033 portable / 1,192 controlled-local selection](delivery-workflows-verification.md),
  with the original a4 package payload retained. Its wheel identity and delivery
  receipts do not identify the a5 payload
- CPU patch `a189ecf`: [17 fake-resource author tests](solver-cpu-ceiling.md)
  passed. No native rerun or installed-artifact acceptance is implied
- Earlier source-only energy candidate: 1,104 selected author tests plus 49
  subtests passed. That scope preceded this a5 build and is not exact-artifact
  acceptance of the current candidate
- The proposed a4 structural qualification under a 30-second hard CPU ceiling
  was blocked before launch. Reusing an older positive pack only checks existing
  output bytes; it does not establish a new native solve or physical validation

Historical a4/e5 assessments and earlier scores remain tied to their original
artifacts and rubrics. No current score, official public download, full-platform
qualification, native scientific result or release is established here.
