# OpenDot Engineering claim status

> Historical package-candidate boundary: the “current” 1,066 author source
> checks and 988-node hosted definition below refer to original 4075ac17.
> The later [source-only delivery extension](delivery-workflows-verification.md)
> retains the exact package payload but selects 1,192 local / 1,033 portable
> cases; its exact outcomes are recorded in a separate delivery receipt.
> The 78-point assessment remains historical and is not a score for the extension.

Snapshot: 2026-10-01 UTC. This is a claim-to-evidence map, not a release approval or full-platform test report. [Adapter source checks](verification-status.md) and [documentation integration checks](integration-review.md) and [source-admission integration checks](source-admission-verification.md) have separate scopes. The [historical provenance-integrated candidate record](provenance-integration-verification.md) and [earlier combined record](combined-candidate-verification.md) cover successive `0.1.0a1` source cuts without promoting either to a release.

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

The current unreleased `0.2.0a4` candidate tightens the shared declared CalculiX
2.23 log gate, adds source-only bounded documentation checks, and pins setuptools
84.0.0 as the build backend. **Current author source checks: 1,066 passed**, with
zero failures/errors/skips. **Exact final artifact and installed acceptance require their own delivery receipt.** Component reviews overlap this aggregate and are not additive. The
988-node portable CI definition excludes 78 local Git cases; hosted CI has not run.
See [current verification](verifier-ci-verification.md). No new physics, native
execution, runtime/recovery, hosted-CI result or public release is established.

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
| Runnable examples | Predecessor checks recorded; current installed acceptance uses a separate receipt | README examples and help/installation commands have version-bound checks; a3 fresh journeys covered all eight blocks per language | Execute the current guide against the exact a4 artifact; source-only parity and predecessor execution do not approve it |
| Wheel identity and imports | Predecessor checks recorded; current artifact acceptance uses a separate receipt | Local wheel installation and isolated module checks retain their recorded version and artifact scope | Fresh exact-candidate checks, approved public distribution, supported platform matrix, and published release identity |
| Optional CAD/CAE adapters | Included | Fixed deterministic contracts and separately installed backends | Native execution and dependency/license review for each claimed environment |
| Shared CalculiX version-declaration gate | Included; component independently reviewed | One complete declared 2.23 header required; ambiguous and repeated declarations refused by both thermal and structural verifiers | Exact integrated and artifact review; declaration consistency does not authenticate a binary/log or validate new physics |
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

当前 a4 候选新增共享 CalculiX 2.23 日志版本声明门槛、纯源码文档检查和构建后端固定版本；本版作者源码检查 1,066 项通过，失败／错误／跳过均为零；组件复核与单独记录的最终精确产物／安装验收分别记录。组件数量不可叠加到总数，先前 a3 结果与评分不自动转移。本包已包含可运行的来源审计与合成资格记录示例，但检查范围有限。可选原生后端、完整智能体运行时、持久恢复、多机执行、科学验证和正式发布必须分别提供证据。许可证文本已保留；发布权利、对外文件与支持渠道仍需复核。
