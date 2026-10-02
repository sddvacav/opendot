# OpenDot Engineering claim status

> Current release, 2 October 2026: **[0.3.0a2 ALPHA prerelease](https://github.com/sddvacav/opendot/releases/tag/v0.3.0a2); NOT_SCORED**. The
> [released source commit](https://github.com/sddvacav/opendot/commit/359f781a5aa1650ae92b1af81cf369a17c444045) and [release notes](https://github.com/sddvacav/opendot/releases/download/v0.3.0a2/RELEASE-NOTES.md) bind exact assets to their separately scoped source, installed and independent checks.
> The structural schema-2 default predates a2; the explicit
> [structural v2 migration](structural-default-v2.md) requires conditional
> per-element consistency by default, with schema 2 and false scientific authority.
> Historical `artifact_v1` behavior is available only by explicit API selection.
> Seven original synthetic source-boundary protocols are exercised; eight remain
> unimplemented, with six synthetic parameter fixtures counted separately and
> no production enforcement. The [historical successor scope](structural-v2-candidate-verification.md)
> declares 1,325 portable / 1,484 controlled-local nodes, not pass claims.

The [a2 main portable run](https://github.com/sddvacav/opendot/actions/runs/36964156448) and [a2 PR Temporal run](https://github.com/sddvacav/opendot/actions/runs/36963928744) retain distinct scopes. The optional Temporal run tested a PR merge revision with the same tree as the released source, not the later main commit. The packaged [finite Temporal transport](temporal-reference-transport.md) and [Gmsh file-size repair](gmsh-cpu-ceiling.md) are present in a2 and absent from unchanged a1 release assets. Bounded queued first delivery after graceful quiescent restart and recorded-result replay do not establish in-flight crash recovery, global exactly-once, native resource enforcement, or scientific/device authority.

> Historical boundaries: original a4 `4075ac17` owns the 1,066 source passes
> and 988-node hosted definition. The later
> [source-only delivery extension](delivery-workflows-verification.md) retained
> that package payload and selected 1,192 local / 1,033 portable cases.
> Its e5 record, the a189 CPU patch's 17 fake-resource passes, and the earlier
> source-only energy candidate's 1,104 selected passes plus 49 subtests retain
> their own scopes. None is exact-artifact acceptance for a5. The historical
> 78-point assessment is not a score for a5. The proposed a4 structural
> qualification under a 30-second hard CPU ceiling was blocked before launch.

Current status updated: 2026-10-02 UTC. Historical evidence entries retain their original version/date scopes. This is a claim-to-evidence map, not a release approval or full-platform test report. [Adapter source checks](verification-status.md) and [documentation integration checks](integration-review.md) and [source-admission integration checks](source-admission-verification.md) have separate scopes. The [historical provenance-integrated candidate record](provenance-integration-verification.md) and [earlier combined record](combined-candidate-verification.md) cover successive `0.1.0a1` source cuts without promoting either to a release.

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

The historical `0.2.0a5` candidate introduced the CPU-minimum repair and optional
per-element printed E/ELSE check, retained without result changes in this successor.
`verify_elastic_energy` still returns `CONDITIONAL_ELASTIC_ENERGY_CONSISTENCY_PASS`.
The new default structural profile requires that same conditional check and returns
`CONDITIONAL_STRUCTURAL_CONSISTENCY_PASS`; scientific acceptance stays false,
no-underflow remains `ASSUMED_NOT_VERIFIED`, and the arithmetic bound remains
`NOT_PROVED`. This closes only the bounded declared-case default E/ELSE gap;
explicit `artifact_v1` retains the historical gap. General material/physics
qualification, native execution and the solver-child inherited file-size ceiling
issue remain outside this change. Rechecking an older pack is output-only evidence.

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
| Runnable examples | Released a2 installed checks and current guide checks are separately scoped | The [a2 release notes](https://github.com/sddvacav/opendot/releases/download/v0.3.0a2/RELEASE-NOTES.md) record exact-artifact installed checks; the [current guide](installed-quickstart.md) uses a2 pins. Historical a3 fresh journeys covered all eight blocks per language | Retain the exact guide revision, asset identities and executed scope; source-only parity and predecessor execution do not approve a changed guide |
| Wheel identity and imports | Released a2 assets and scoped checks recorded | The [a2 release notes](https://github.com/sddvacav/opendot/releases/download/v0.3.0a2/RELEASE-NOTES.md) identify the exact wheel, matching source assets and isolated installed checks; public download bytes were verified | Separate supported-platform evidence and fresh exact-artifact review for changed releases; no PyPI publication is claimed |
| Optional CAD/CAE adapters | Included | Fixed deterministic contracts and separately installed backends | Native execution and dependency/license review for each claimed environment |
| Shared CalculiX version-declaration gate | Included; component independently reviewed | One complete declared 2.23 header required; ambiguous and repeated declarations refused by both thermal and structural verifiers | Exact integrated and artifact review; declaration consistency does not authenticate a binary/log or validate new physics |
| Gmsh worker resource ceilings | Included; 35 fake-only cases; subtests are not extra nodes | Existing worker setup takes the minimum of each existing ceiling (32 MiB per file, 300 CPU seconds) and its finite inherited soft/hard limits, including zero, before Gmsh import | No native import or kernel-limit enforcement is tested; the separate solver-child FSIZE limitation and native-run authorization remain |
| Solver-child CPU ceiling | Included; 17 fake-resource predecessor checks | Existing callback takes the minimum of 300 seconds and finite inherited soft/hard limits, including zero | Version-bound software checks in the [a2 release notes](https://github.com/sddvacav/opendot/releases/download/v0.3.0a2/RELEASE-NOTES.md); separate OS/native enforcement evidence remains required; unchanged inherited file-size-limit issue is not repaired |
| Default structural v2 | Included; intentional schema/status migration | Strict artifact admission plus the unchanged conditional per-element check; explicit historical `artifact_v1` only | Exact a2 source/installed scope is recorded in the [release notes](https://github.com/sddvacav/opendot/releases/download/v0.3.0a2/RELEASE-NOTES.md); no generalized physics, proved arithmetic error bound, physical validation or scientific acceptance |
| Optional structural E/ELSE consistency | Included; conditional opt-in API | Unchanged strict admission precedes per-element tensor-strain/whole-element-energy comparison under declared print and arithmetic assumptions | Exact a2 source/artifact scope is recorded in the [release notes](https://github.com/sddvacav/opendot/releases/download/v0.3.0a2/RELEASE-NOTES.md); no-underflow is assumed, arithmetic bound is not proved; the new default requires this same check only within its declared case and grants no scientific acceptance |
| Source-only documentation checker | Included; component independently reviewed | Bounded local-link/fragment and explicit HTML-anchor checks; exactly eight nonempty literal-identical shell blocks in both installed guides | Exact integrated review and separate installed-journey execution; no complete Markdown, remote-link, source-truth or hosted-CI claim |
| Pinned build backend | Included; predecessor repeatability recorded separately | setuptools 84.0.0 and a separate hash-pinned acquisition recipe; two-environment same-host evidence applies only to a59419b | Fresh candidate build identities and acceptance; no cross-platform, full-hermeticity or runtime-dependency claim |
| Adapter Git provenance | Included; narrow repair independently reviewed before integration; [local combined checks](provenance-integration-verification.md) | Actual adapter path checked in local index/HEAD; inherited Git overrides discarded; uncertain context hash-only; new worktree field null | Exact successor artifact review; native evidence remains separate; no upstream authorship or atomic-snapshot claim |
| Agent coordination and durable recovery | Goal | Proposed broader direction only | Runtime implementation, interruption/restart evidence, and bounded resource use |
| Live model quality, agent scale, and multi-host execution | Unverified | No result is established by this package | Predeclared workload, actual execution evidence, topology, measured overlap, cost, and acceptance rules |
| Privacy and security | Bounded a2 outgoing-artifact review recorded | The [release notes](https://github.com/sddvacav/opendot/releases/download/v0.3.0a2/RELEASE-NOTES.md) describe bounded privacy/license review; local path/metadata checks and publication scans do not guarantee confidentiality | Broader threat-model and security review; independent inspection of every changed outgoing artifact |
| Optional simulation dependencies | Separately installed; direct versions and license texts checked in the reviewed lab environment | Bluesky 1.15.1, ophyd 1.11.2, event-model 1.24.0; no dependency code vendored | Transitive-license, vulnerability, and supply-chain review for the chosen distribution/environment |
| Core license | Included | Existing Apache-2.0 text and NOTICE are retained | Distribution-rights and third-party obligations review before publication |
| New artwork | Included | Six newly authored AI-assisted SVGs with an asset notice | Independent outgoing-artifact review and any required trademark decision |
| Public repository and release downloads | Verified a2 release and public asset bytes | [Repository](https://github.com/sddvacav/opendot), [Issues](https://github.com/sddvacav/opendot/issues) and [a2 ALPHA release](https://github.com/sddvacav/opendot/releases/tag/v0.3.0a2); earlier releases retain their exact version-bound assets | New releases need separate artifact/publication review; private security reporting and response SLA are not established |
| Production readiness or support SLA | Unverified | No such promise | Defined operational/support scope and approved evidence or policy |

## Promotion rules

For any stronger statement, record the exact artifact/configuration, evidence, reviewer, date, and limits. Keep passed, failed, skipped, and not-run results distinct. Do not substitute source checks for installed-artifact checks, synthetic fixtures for scientific validation, or configured capacity for actual concurrent execution. A document edit alone cannot promote a runtime claim.

## 中文摘要

当前为已发布的 [0.3.0a2 ALPHA 预发布版](https://github.com/sddvacav/opendot/releases/tag/v0.3.0a2)，NOT_SCORED。[发布说明](https://github.com/sddvacav/opendot/releases/download/v0.3.0a2/RELEASE-NOTES.md)分别记录精确产物、源码、安装与独立检查；主分支可移植执行和同树 PR 的可选 Temporal 执行不能互换或相加。a2 包含 Gmsh 文件大小上限修复与固定合成 Temporal 传输；未改变的 a1 发布产物不含这两项。a2 保留先前已引入的结构默认 schema 2，在声明的材料、历史与输出条件下要求逐单元能量一致性；科学验收仍为 false，无下溢仍为未验证假设，算术误差界限未证明。历史 artifact_v1 仅可显式选择，不自动回退。来源边界覆盖七项原始合成协议、八项未实现协议与另行计数的六个合成参数场景，仍无生产强制机制。历史后继候选预声明选择为 1,325 项可移植节点、1,484 项受控本地节点，结果由精确候选回执记录。历史 a6 字节与证据不变，不转移评分或验收；历史失败与 NOT_RUN 保持原状。可选 Temporal 的有界托管检查不证明运行中崩溃恢复、全局恰好一次或完整运行时。本次文档更新未执行原生求解、模型、设备或新托管检查。
