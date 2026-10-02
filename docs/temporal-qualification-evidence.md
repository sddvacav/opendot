# Bounded Temporal qualification / 有限范围 Temporal 资格验证

Date / 日期: 2026-10-02 UTC. Status / 状态: **PASS for the finite hosted profile / 有限托管配置通过**.

[Transport contract](temporal-reference-transport.md) · [English capabilities](../CAPABILITIES.md) · [中文能力表](../CAPABILITIES.zh-CN.md) · [PR #18 and chronological receipts](https://github.com/sddvacav/opendot/pull/18)

## Exact source and runs / 精确源码与执行

| Identity / 标识 | Recorded value / 记录值 |
| --- | --- |
| Optional service run / 可选服务执行 | [36960635013](https://github.com/sddvacav/opendot/actions/runs/36960635013), attempt 1, job 110693320416 |
| PR head / PR 分支提交 | `8d219941c1288f76ccd844f93b70441c9f5227b2` |
| Actual tested PR merge revision / 实际测试的 PR 合并提交 | `15bafbaa738941a916bf3329ba83c056ae70717b` |
| Merged `main` revision / 合入 `main` 的提交 | `a4f7952b448910fb87d7c7a94021ab85a3ad0850` |
| Shared exact Git tree / 共同的精确 Git 树 | `18a246f1dc6e6737b28455d4c3917d40dc139b2f` |
| Hosted profile / 托管配置 | Ubuntu 24.04, Python 3.12.14, Temporal SDK 1.34.0, CLI 1.9.1, server 1.32.0 |
| Separate PR portable run / 单独的 PR 可移植执行 | [36960635029](https://github.com/sddvacav/opendot/actions/runs/36960635029): 1,325 passed / 141 subtests passed |
| Separate merged-main portable run / 单独的合并后主分支可移植执行 | [36960995247](https://github.com/sddvacav/opendot/actions/runs/36960995247): 1,325 passed / 141 subtests passed |

## Accepted observations

The optional service run passed **818 collected/executed SDK and pure-software
checks, then all seven required real-server nodes**, with zero failures, errors
or skips in those gates. The predeclared [seven-node selection](../ci/temporal-server-nodes.txt)
and the executed harness/verifier bind the reported result to the exact source
above. Independent review revalidated the public audit records and source hashes;
it did not rerun the service. The service job ran on the PR merge revision, not
on the later `main` commit; their exact Git trees match. The portable runs are
separate scopes, not additional unique Temporal coverage or a new summed total.

- One single-host loopback experiment used only the fixed `synthetic.bounded_sum.v1`
  profile and the same trusted local CAS and SQLite across restarts. Five actual
  SDK Info records have received attempt 1, retry maximum 1 and exact 10-second /
  60-second Activity deadlines. Eight history snapshots and 15 invocation-counter
  records were checked. The latter total five Activity entries, four runtime
  entries, three handler entries and three handler returns across all scenarios
- Queued history was unchanged across a graceful, observed-quiescent server
  restart, with no Activity worker or invocation before first delivery. This was
  queued first execution, not recovery of an interrupted handler
- Completed-result replay on a fresh server/Workflow worker and the SDK Replayer
  retained the same result reference with no Activity worker present. The
  durability scenario's handler count stayed **1**, and its counter sequence
  stayed **4 → 4 → 4**. This is distinct from the total three handler calls across
  all scenarios
- Completed null remained a legitimate, semantically valid result. BLOCKED and
  FAILED tool outcomes were delivered without becoming semantic successes.
  Missing input produced a non-retryable transport failure without runtime or
  handler dispatch
- All three server generations exited gracefully with code **0**; all **12**
  worker generations completed awaited shutdown. No forced termination was used

## Evidence and product limits

The public job log contains the bounded, cross-bound audit and acceptance
summary. No artifact bundle was uploaded: original JUnit/collection files, full
raw histories, CAS/SQLite and acquisition bytes were not publicly retained.
Independent acceptance therefore combines the reviewed executed harness/verifier
with its public audit; it does not reconstruct those private job-temporary files.
The public history projection is not a complete replayable history.

This establishes no multi-host availability, in-flight crash recovery, general
cancellation safety, global or effect exactly-once guarantee, arbitrary-handler
admission, production deployment, scientific validity or device authority.
Per-result scientific/device fields remain false and review/integration fields
remain `NOT_EVALUATED`; bounded transport review does not change those fields.
Canonical owners, the deny-only guard, default empty dependencies and optional
import isolation are unchanged. `NOT_SCORED` remains unchanged; this is not a full
MVP. Published v0.3.0a1 assets and hashes are unchanged and do not contain this
optional source feature. The released [installed guide](installed-quickstart.md)
is not an installation claim for the newer `main` source; no PyPI-latest claim is
made here.

## Earlier evidence remains historical / 先前证据仍属历史

| Run / 执行 | Preserved outcome / 保留的结果 |
| --- | --- |
| [36954216096](https://github.com/sddvacav/opendot/actions/runs/36954216096) | FAIL: 615 SDK/pure passes, seven service errors, zero service passes; cleanup unverified, evidence incomplete, privacy check failed; cause remains UNCLASSIFIED / 失败：615 项 SDK／纯软件通过，七项服务错误、零通过；清理未验证、证据不完整、隐私检查失败；原因仍为 UNCLASSIFIED |
| [36958858368](https://github.com/sddvacav/opendot/actions/runs/36958858368) | FAIL: 810 SDK/pure passes, seven service errors, zero service passes; recorded diagnostic remains `workflow_worker_start` / `UNKNOWN_ERROR`; its exact unavailable exception is not retrospectively asserted / 失败：810 项 SDK／纯软件通过，七项服务错误、零通过；保留原诊断，不倒推未取得的精确异常 |

The dated [ADR](decisions/004-temporal-reference-transport.md),
[failure matrix](temporal-reference-failure-matrix.md), earlier SDK-only checks
and `NOT_RUN` statements retain their original scope. The corrected candidate's
pass does not erase those failures or retroactively accept earlier mocked or
unexecuted evidence.

## 中文结论与限制

可选服务执行实际通过 **818 项收集并执行的 SDK／纯软件检查，以及全部七项必需的真实
服务检查**，这些门槛均无失败、错误或跳过。独立复核检查公开审计记录与源码哈希，
没有重跑服务。服务实际运行于上表 PR 合并提交；后续合入 `main` 的提交不同，但
精确 Git 树相同。两次可移植 CI 各为 1,325 项通过／141 项子测试通过，不与 Temporal
检查相加成为新的独立覆盖总数。

范围只有单主机、回环连接、固定 `synthetic.bounded_sum.v1`，重启沿用同一本地可信
CAS 和 SQLite。五条真实 SDK Info 均记录第 1 次尝试、最多 1 次尝试及 10／60 秒
期限；核验八份历史快照、15 条调用计数记录。所有场景合计五次 Activity 进入、四次
runtime 进入、三次处理函数进入与返回。排队工作在正常关闭、静止状态重启前后仍未
开始；之后是首次交付，不是被中断函数的恢复。

已记录结果在新服务／Workflow worker 和 SDK Replayer 中重放时，没有 Activity
worker，结果引用不变；该持久化场景处理函数计数始终为 **1**、计数序列为
**4 → 4 → 4**。完成的 null 仍是合法且语义有效的结果；BLOCKED 与 FAILED 工具
结果虽然交付成功，仍不属于语义成功。输入缺失是未调用 runtime／处理函数的不可重试
传输失败。三代服务均正常退出、
退出码 **0**，全部 **12** 代 worker 等待关闭完成，没有强制终止。

公开日志仅含限定的交叉绑定审计与验收摘要；没有上传产物包。原始 JUnit／收集文件、
完整原始历史、CAS／SQLite 与获取字节未公开保留，公开历史投影也不能直接完整重放。
独立验收依赖已复核的实际执行 harness／verifier 及其公开审计，不意味着重建这些临时
文件。两个早期失败、原 ADR／失败矩阵、SDK-only 和 `NOT_RUN` 记录均保持原范围。

本结果不证明多机可用性、执行中崩溃恢复、通用取消安全、全局或副作用恰好一次、任意
处理函数准入、生产部署、科学有效性或设备权限。逐结果科学／设备字段仍为 false，
复核／集成字段仍为 `NOT_EVALUATED`。既有核心所有者、只拒绝的 guard、默认空依赖和
可选导入隔离未变；`NOT_SCORED` 未变，也不是完整 MVP。已发布 v0.3.0a1 产物及哈希
未变，且不含这项可选源码功能；[已发布安装指南](installed-quickstart.zh-CN.md)不代表
安装了较新的 `main` 源码，此处不作 PyPI 最新版声明。
