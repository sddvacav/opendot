# OpenDot Engineering claim status

> Current unreleased **0.2.0a6** candidate; **NOT_SCORED**: corrected a5 plus
> optional read-only artifact verification, bilingual measurement guides, and six
> synthetic source-boundary protocols. The nine remaining proposals are
> `NOT_IMPLEMENTED`; all 15 have no production enforcement. [Exact a6 scope](a6-candidate-verification.md)
> declares 1,183 portable / 1,342 controlled-local nodes. These are selection
> counts, not pass claims. Default writes, execution/reference owners, optional
> energy-check limits, and scientific/physical non-acceptance are preserved.

> Historical boundaries: original a4 `4075ac17` owns the 1,066 source passes
> and 988-node hosted definition. The later
> [source-only delivery extension](delivery-workflows-verification.md) retained
> that package payload and selected 1,192 local / 1,033 portable cases.
> Its e5 record, the a189 CPU patch's 17 fake-resource passes, and the earlier
> source-only energy candidate's 1,104 selected passes plus 49 subtests retain
> their own scopes. None is exact-artifact acceptance for a5. The historical
> 78-point assessment is not a score for a5. The proposed a4 structural
> qualification under a 30-second hard CPU ceiling was blocked before launch.

Snapshot: 2026-10-01 UTC. This is a claim-to-evidence map, not a release approval or full-platform test report. [Adapter source checks](verification-status.md) and [documentation integration checks](integration-review.md) and [source-admission integration checks](source-admission-verification.md) have separate scopes. The [historical provenance-integrated candidate record](provenance-integration-verification.md) and [earlier combined record](combined-candidate-verification.md) cover successive `0.1.0a1` source cuts without promoting either to a release.

## Optional read-only artifact source increment

Included in the current source: `ArtifactStore(..., read_only=True)` skips setup
writes, rejects public puts, and is used by synthetic measurement replay with
independently supplied pins. Its [separate scope](readonly-artifacts-verification.md)
does not inherit earlier source, wheel, hosted-CI or release acceptance. Default
writer/reference behavior and metadata limitations remain unchanged. There is no
OS sandbox, authentication, hostile-concurrency or atomic-snapshot guarantee.

## Status definitions

- **Included**: present in this bounded source tree; not automatically exercised
- **Locally checked**: a specific check was executed in the stated environment; no broader guarantee
- **Goal**: intended direction outside the current package
- **Unverified**: the stated behavior or approval has not been established
- **Blocked**: required release evidence or a verified destination is missing

The artifact/callable core introduced in `0.2.0a0` remains a migration candidate. Its
[integration checks](execution-core-verification.md) are distinct from the separate
component records and historical `0.1.0a1` reports; prior results are not promoted.

The `0.2.0a1` successor added the [controlled Git profile](git-workspaces.md).
Its [fixture evidence](git-workspaces-verification.md) and [residue repair](git-workspaces-residue-fix.md) retain that version scope; prior CAS/callable results do not prove new Git behavior.

The historical `0.2.0a2` candidate introduced canonical
[agent metadata contracts](agent-contracts.md), `Capability` and `AgentManifest`.
Its [author record](agent-contracts-verification.md) reports 805 selected source
passes and 32 repeated installed metadata passes; its separate
[exact predecessor acceptance](metadata-predecessor-acceptance.md) preserves the
independent 410-case and fake-only scopes.

The historical `0.2.0a3` candidate added read-only module help/version,
example collision diagnostics and offline source-index checks. Its
[source record](parallel-development-verification.md) reports 899 selected passes;
the final `a59419b` receipt covered the predecessor artifacts and fresh installed
journeys through all eight shell blocks per language. Its
[same-host build experiment](build-toolchain.md) reproduced the exact predecessor
wheel in two clean environments. These results and any predecessor score do not
accept a later candidate. The recorded
[host-coordinated worktree development](host-development/README.md) does not establish
a standalone autonomous scheduler, multiple hosts or durable recovery.

The historical unreleased `0.2.0a4` candidate tightened the shared declared CalculiX
2.23 log gate, added source-only bounded documentation checks, and pinned setuptools
84.0.0 as the build backend. **Historical a4 author source checks: 1,066 passed**, with
zero failures/errors/skips. **Exact final artifact and installed acceptance require their own delivery receipt.** Component reviews overlap this aggregate and are not additive. The
988-node portable CI definition excludes 78 local Git cases; hosted CI has not run.
See [historical a4 verification](verifier-ci-verification.md). No new physics, native
execution, runtime/recovery, hosted-CI result or public release is established.

The historical `0.2.0a5` candidate introduced, and a6 retains, the CPU-minimum repair and opt-in
per-element printed E/ELSE check. Its successful API status is
`CONDITIONAL_ELASTIC_ENERGY_CONSISTENCY_PASS`; `scientific_accepted` stays false,
no-underflow remains `ASSUMED_NOT_VERIFIED`, and the arithmetic bound is
`NOT_PROVED`. Source selection, build identities, installed checks and guide
execution must be recorded against a6 itself. No new native solve is included;
rechecking an older pack is output-only evidence. The unchanged default
numeric-field consistency gap and inherited file-size ceiling issue remain open.

## Claims and limits

| Claim | Status | Supported statement | Requirement for stronger wording |
| --- | --- | --- | --- |
| Canonical agent metadata | Included; metadata-only contracts | `Capability` and `AgentManifest` with explicit `.validate()` calls; budgets and permissions are descriptive | Exact-candidate review; no execution enforcement, agent runtime, or existing-consumer migration |
| Controlled local Git workspaces | Included; bounded cooperative-local profile | Existing owner with create/status/diff, fixed base, controlled process and ownership checks | Independent exact-candidate review and supported-platform evidence; no OS sandbox, hostile-race, commit/remove, arbitrary-repository, remote, or consumer-migration claim |
| Canonical local artifact core | Included; migration candidate | One standard-library store/reference owner, real synthetic byte round trips and corruption refusal | Exact successor review and consumer migration acceptance; no sandbox, transaction, cross-process locking, or durable-recovery claim |
| Callable-only execution | Included; bounded migration candidate | One preserved callable owner and six contracts; in-memory receipts, explicit permissions/retry declarations and deny-only guard | Exact integration review and real-consumer acceptance; no sandbox, durable control, native lifetime or recovery-event guarantee |
| Callable/CAS composition | Included; synthetic software example | Actual writes, canonical returned refs, independent digest verification, permission refusal and semantic refusal with retained unaccepted bytes | Byte integrity must not imply tool or scientific acceptance; failed calls do not roll back effects |
| Local source auditing | Included; locally checked | Standard-library checks of pinned synthetic local evidence and metadata | Independent review for new input classes, platforms, and security claims |
| Optional source admission | Included; locally checked; narrow predecessor integration independently reviewed | Explicit root, independently reviewed manifest digest, flat pinned modules, and source-owned named exports; ordinary trusted Python authority | Review of each changed outgoing artifact; separate acceptance for each consumer; no inference of authorization, sandboxing, or complete code identity |
| Synthetic qualification records | Included; locally checked | Invented fixture oracles can be checked; science/device flags stay false | Separate physical/scientific evidence for real qualification |
| Optional simulated lab | Included; fake-only scope independently reviewed before combination | Internally constructed fake devices; finite fixed plan and strict pinned-document checks; runtime authority flags stay false | Exact combined-artifact review and separate evidence for any new platform or capability; no physical/scientific qualification |
| Runnable examples | Predecessor checks recorded; current installed acceptance uses a separate receipt | README examples and help/installation commands have version-bound checks; a3 fresh journeys covered all eight blocks per language | Execute the current guide against the exact a6 artifact; source-only parity and predecessor execution do not approve it |
| Wheel identity and imports | Predecessor checks recorded; current artifact acceptance uses a separate receipt | Local wheel installation and isolated module checks retain their recorded version and artifact scope | Fresh exact-candidate checks, approved public distribution, supported platform matrix, and published release identity |
| Optional CAD/CAE adapters | Included | Fixed deterministic contracts and separately installed backends | Native execution and dependency/license review for each claimed environment |
| Shared CalculiX version-declaration gate | Included; component independently reviewed | One complete declared 2.23 header required; ambiguous and repeated declarations refused by both thermal and structural verifiers | Exact integrated and artifact review; declaration consistency does not authenticate a binary/log or validate new physics |
| Solver-child CPU ceiling | Included; 17 fake-resource predecessor checks | Existing callback takes the minimum of 300 seconds and finite inherited soft/hard limits, including zero | Exact a6 checks and separate OS/native enforcement evidence; unchanged inherited file-size-limit issue is not repaired |
| Optional structural E/ELSE consistency | Included; conditional opt-in API | Unchanged strict admission precedes per-element tensor-strain/whole-element-energy comparison under declared print and arithmetic assumptions | Exact a6 source/artifact checks; no-underflow is assumed, arithmetic bound is not proved, and default verifier numerical-consistency or scientific acceptance gaps remain open |
| Source-only documentation checker | Included; component independently reviewed | Bounded local-link/fragment and explicit HTML-anchor checks; exactly eight nonempty literal-identical shell blocks in both installed guides | Exact integrated review and separate installed-journey execution; no complete Markdown, remote-link, source-truth or hosted-CI claim |
| Pinned build backend | Included; predecessor repeatability recorded separately | setuptools 84.0.0 and a separate hash-pinned acquisition recipe; two-environment same-host evidence applies only to a59419b | Fresh candidate build identities and acceptance; no cross-platform, full-hermeticity or runtime-dependency claim |
| Adapter Git provenance | Included; narrow repair independently reviewed before integration; [local combined checks](provenance-integration-verification.md) | Actual adapter path checked in local index/HEAD; inherited Git overrides discarded; uncertain context hash-only; new worktree field null | Exact successor artifact review; native evidence remains separate; no upstream authorship or atomic-snapshot claim |
| Agent coordination and durable recovery | Goal | Proposed broader direction only | Runtime implementation, interruption/restart evidence, and bounded resource use |
| Live model quality, agent scale, and multi-host execution | Unverified | No result is established by this package | Predeclared workload, actual execution evidence, topology, measured overlap, cost, and acceptance rules |
| Privacy and security | Limited checks; release review open | Local path/metadata checks and bounded publication scans do not guarantee confidentiality | Threat-model review and independent inspection of every outgoing artifact |
| Optional simulation dependencies | Separately installed; direct versions and license texts checked in the reviewed lab environment | Bluesky 1.15.1, ophyd 1.11.2, event-model 1.24.0; no dependency code vendored | Transitive-license, vulnerability, and supply-chain review for the chosen distribution/environment |
| Core license | Included | Existing Apache-2.0 text and NOTICE are retained | Distribution-rights and third-party obligations review before publication |
| New artwork | Included | Six newly authored AI-assisted SVGs with an asset notice | Independent outgoing-artifact review and any required trademark decision |
| Public repository, downloads, support/security channels | Blocked | Canonical destinations are not verified here | Verified ownership, access, and tested reporting routes |
| Production readiness or support SLA | Unverified | No such promise | Defined operational/support scope and approved evidence or policy |

## Promotion rules

For any stronger statement, record the exact artifact/configuration, evidence, reviewer, date, and limits. Keep passed, failed, skipped, and not-run results distinct. Do not substitute source checks for installed-artifact checks, synthetic fixtures for scientific validation, or configured capacity for actual concurrent execution. A document edit alone cannot promote a runtime claim.

## 中文摘要

当前独立未发布候选为 a6，NOT_SCORED。在修正后的 a5 上整合可选只读产物验证、双语测量教程与六项合成来源边界协议；其余九项拟议协议仍未实现，十五项均无生产强制机制。选择范围为 1,183 项可移植节点与 1,342 项受控本地节点，实际结果记录在单独精确产物回执中。默认写入行为、函数及引用所有者保持不变；只读模式仍需可信根目录，读取可能更新 atime。继承的可选能量检查不构成科学验收，数值一致性与文件大小上限的既有缺口未关闭。历史版本结果与评分不转移至 a6；未运行新原生求解、模型、设备、远程写入或托管 CI，也未公开发布。
