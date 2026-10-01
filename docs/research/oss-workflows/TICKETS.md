# Prioritized implementation tickets / 优先实现任务

Status at authorship: proposals only, except separately frozen test inputs. No score change is predicted. Priorities follow the fixed a4 gaps: release gates, current native/runtime boundaries, then user value and compatibility. Small source-only example work can proceed independently of publication decisions.

## T1 · P0, bounded example: make one reviewable result / 做出可核对的成果

**Scope:** one public synthetic repeated-measurement CSV → existing ToolRuntime callable → existing ArtifactStore → separately specified summary acceptance → readable manifest. No new scheduler, solver, model or service. Use [frozen oracle](frozen-oracle/case-oracles.json).

**Done when:** the seven predeclared cases match; a reviewer locates source bytes, the exact result and accepted/rejected status; failed semantics preserve effect evidence; no optional dependency required. Each expected count/sum/mean is checked independently of the generator.

**中文：** 首先交付完整的小例子，严格区分“已生成”“字节完整”“语义通过”；错误结果保留但不作为已验收成果。对真实用户有用仍是假设。

**Evidence links:** [AiiDA tutorial](https://github.com/aiidateam/aiida-core/blob/9a9cf9591785ba45eea7355ae3f716bce8decd95/docs/source/tutorials/basic.md), [workflow specification](WORKFLOW-SPEC.md). Relevant rubric: P5/O2/A4; no automatic full credit.

## T2 · P0, verifier: bind acceptance to trusted expectations / 将验收绑定到可信期望

**Scope:** source digest, result digest, validator ID and oracle digest in the example's verification contract. Read expected pins from reviewed code or explicit trusted arguments, never solely from the checked manifest. Fresh-process checking must disclose effects: the present CAS constructor can create directories/change permissions, so strictly read-only verification is a separate future improvement.

**Done when:** a valid bundle passes; input/result mutation, wrong validator/oracle, omitted expected pin and self-consistent substituted bundle are refused. Strictly validate manifest fields and paths appropriate to the documented trusted-root scope. Changed input or verifier must trigger new verification.

**中文：** 不能因旧结果还在、清单写了“通过”或哈希彼此一致，就沿用验收。缺少外部可信期望值须拒绝。哈希绑定不认证作者身份。

**Evidence:** [DVC run-cache semantics](https://dvc.org/doc/user-guide/project-structure/internal-files), [SLSA provenance](https://slsa.dev/spec/v1.2/build-provenance). Relevant rubric: T2/S1; not durable recovery.

## T3 · P0, owner gate: establish legitimate delivery and support / 确认合法发布与支持

**Scope:** accountable maintainer decisions for exact outgoing contents/rights, real publication destination, supported versions, verified private security-reporting route and response owner. These require owner input and authorization; invent no addresses or sign-offs.

**Done when:** signed-off inventory is complete; authorized public download matches exact reviewed hashes; authorized private route test reaches the responsible owner; support policy states actual supported scope. Do not invite vulnerability reports until a private route is verified.

**中文：** 文档和星数不能代替发布责任、权利确认或真实报告渠道。无负责人授权时保留为阻塞项。

**Evidence:** a4 prioritized gap 1; peer support/release entries in [benchmark](BENCHMARK.md). Relevant rubric: S5/N3–N5/G2/G4–G5; hard gates remain independent.

## T4 · P0, release engineering: exercise exact-commit delivery / 演练精确版本交付

**Scope:** authorized hosted CI for exact candidate; scoped dependency/native/license inventory; builder identity/attestation verification where supported; bounded install, update, rollback/revocation rehearsal. Do not merely add a badge or name an unsigned manifest “attestation.”

**Done when:** hosted run links bind the source commit and selected test denominator; outgoing bytes verify after download; changed subject/source/builder is refused; update/rollback outcome is exercised and recorded. User/owner must authorize publication or new external infrastructure/access.

**中文：** 需要可追溯的真实托管运行与下载后核对，不能把本机测试或 CI 配置当成云端执行结果。相关 rubric: T5/C3–C5/G5; [SLSA source](PRIMARY-SOURCES.md#a3--slsa-v12-industry-consensus-specification).

## T5 · P1, adoption evidence: observe a newcomer and fair baseline / 观察新人上手与公平基线

**Scope:** after a legitimate artifact route exists, recruit an actual first-time target user with consent. Freeze the task, expected output quality, manual/script baseline and assisted/unassisted rules before observing. A maintainer-operated replay is a different evidence class.

**Done when:** preserve the unaided acquisition-to-result session, confusion and assistance; fix issues and recheck. Record accepted-output quality, all attempts, active human time and elapsed time. Separate setup cost from repeated-run cost; compare equivalent checks, not a weak straw-man baseline.

**中文：** 不能虚构访谈、用户数量或节时比例。合成演示只验证机制，不完成真实采用验证。Relevant rubric: O5/P5; [BNL source](PRIMARY-SOURCES.md#a2--brookhaven-deployment-account-first-party-operational-source).

## T6 · P1, scientific integration: current exact native workflow / 当前版本原生流程

**Scope:** one authorized CAD → mesh → solver case using the declared backend versions and lawful fixtures. Keep the synthetic measurement example separate. Record units, boundary conditions, mesh sensitivity, solver identity and independent numerical/artifact oracle before running.

**Done when:** exact candidate/environment reproduces accepted numerical results, rejects wrong units/missing or nonconverged output, and preserves source/result identities. Document licensing, dependencies and scientific limitations. No current-native claim from predecessor logs or a pure-Python summary.

**中文：** 原生集成必须真正执行并独立验算；合成案例不能补齐该缺口。Relevant rubric: T4/L3/R3; a4 prioritized gap 2.

## T7 · P1, separately scoped runtime: own lifetime and reconciliation / 独立实现生命周期与对账

**Scope:** only after broader-runtime work is chosen and authorized: identify one task owner, persistent state schema, cancellation/process boundary and external effect ID. Specify which operations are replay-safe and where renewed approval/resources are checked. Reuse existing orchestration where suitable rather than copying an entire peer platform.

**Done when:** independent kill/restart tests before submission, after effect-before-receipt and during result observation show no unapproved duplicate effect; unresolved effects pause; cancellation verifies actual process termination/cleanup where promised. Measure the implemented system rather than simulations.

**中文：** receipt、CAS 文件或线程超时都不等于持久恢复与进程终止。Relevant rubric: L2/L4/L5; [Temporal](https://docs.temporal.io/encyclopedia/event-history), [Bluesky](https://github.com/bluesky/bluesky/blob/4b53ff3a1420fee87c8af671fb2b86a976ad9d7d/docs/state-machine.rst).

## T8 · P1, portability: test every supported environment / 验证声明支持的环境

**Scope:** declare the smallest support matrix actually intended, exact recipes and optional-backend exclusions. Test clean environments for every claimed Python/OS/Git combination; more virtual environments on one host do not prove another OS.

**Done when:** table entries link exact artifact identity, recipe, selected tests and passed/failed/skipped/not-run counts; unsupported combinations remain explicit. Relevant rubric: R3/R5; a4 prioritized gap 3.

**中文：** 只声明真正测过的组合，不用测试总数替代兼容性证据。
