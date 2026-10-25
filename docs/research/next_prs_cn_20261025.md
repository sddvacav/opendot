# OpenDot 下一波小 PR 清单（中文）

- 编制：2026-10-25（Asia/Shanghai）
- 原则：每个 PR **可独立合并、可独立验收**；默认不改发布资产哈希；禁用 Codex CLI/云任务；只用本机 / dot 额度
- 基线：公开仓 HEAD `71c1885`（含已合 PR #48/#49/#50 及 #51/#52 crosswalk）
- 禁止：把私密科研写入本仓；发帖到 X（安全确认未解）；声称满分或生产就绪

## 优先级总表

| ID | 标题（建议英文分支名） | 类型 | 依赖 | 验收要点 |
| --- | --- | --- | --- | --- |
| P-A | 持久任务恢复真实验收门禁 | test/ci | PR#48 源码已在 | 本机/Actions 真服务回执；非仅 pure |
| P-B | HTTPS 真实 worker 有界交换 | feat+test | 自有测试端点 | live 一次成功/受控失败；仍非通用互操作 |
| P-C | 首页合成示例入口 | docs | 无 | README 30 秒路径可复制 |
| P-D | 上手文档三种资产统一 | docs | 无 | EN/ZH 对照一致 |
| P-E | 宣传边界清单 | docs | 无 | 允许说/禁止说可机检或人工清单 |

---

## P-A · 持久任务恢复真实验收

**目标**：把 ADR 008 / PR #48 的固定 DAG 从「源码+pure/SDK」推进到**至少一条真实 Temporal 服务恢复回执**。

**建议范围（保持小）**：

1. 扩展现有 `temporal-server` 门禁：仅覆盖「A 发布后注入投递失败 → 对账 Update → B 在确认原结果后启动」一条正向路径 + 1～2 负例（缺 origin / 篡改 digest）
2. 回执写入仓库允许的公开路径（如 `docs/temporal-*-evidence.md` 增量段落），写清：SDK/CLI/server 版本、单机 loopback、**非**崩溃 fencing / 多机证明
3. CI：收集节点数与既有 1488/1484 计数策略对齐，避免 silently 扩大分母

**明确不做**：通用检查点框架、多 Workflow、真实外部副作用、杀进程 fencing 全矩阵。

**验收**：

- [ ] 有一次非 mock 的服务运行日志或 Actions run URL（公开）
- [ ] 文档同时保留「新 DAG 服务恢复此前 NOT_RUN」的历史表述与「本 PR 有界 PASS」的精确范围
- [ ] 失败时 fail-closed，不把 UNKNOWN 记成成功

**分支建议**：`test/dag-recovery-live-gate`

---

## P-B · HTTPS 真实 worker（有界）

**目标**：在 mock 合格之外，对**操作者自有** HTTPS 测试 worker 做一次有界 live 交换。

**建议范围**：

1. 测试用 worker 仅回显固定小 JSON；TLS 默认信任链；拒绝代理/自定义 CA 环境变量的现有行为保持
2. 新增 `tests/` 或 `ci/` 下 **opt-in** 标记（默认跳过）：需环境变量如 `OPENDOT_LIVE_HTTPS_URL`
3. 文档 `docs/a2a-http-transport.md`：增加「Live gate：PASS/NOT_RUN」表格；**不**把 live PASS 写成通用 provider/model 互操作

**明确不做**：接入第三方模型供应商；把密钥写入仓；Codex；宣称 A2A 生产就绪（候选仍 UNACCEPTED 除非协议改变并证明）。

**验收**：

- [ ] 默认 CI 仍全绿（live 跳过）
- [ ] 本地/dot 手动打开 live 时：字节上限、超时、非 2xx、超大 body 均有拒绝路径
- [ ] README/CAPABILITIES 仍写 live 默认 NOT_RUN，直至回执合并

**分支建议**：`test/https-live-worker-opt-in`

---

## P-C · 首页示例

**目标**：访客在 README 首屏 1 分钟内看到「如何得到第一个可核验合成结果」。

**建议范围**：

1. README / README.zh-CN 顶部增加指向 `examples/callable-artifacts/demo.py` 的最短命令（源码树）
2. 安装用户指向 `docs/installed-quickstart.md` 块 2–3，避免复制源码 `PYTHONPATH` 到已装环境
3. 可选：在 `examples/README.md`（若无则新建极短索引）列 3 个「最先跑」示例

**验收**：

- [ ] 文档检查器链接/标题片段通过
- [ ] 中英文命令与预期 JSON 关键字段一致
- [ ] 不引入私密路径或本机绝对路径

**分支建议**：`docs/homepage-first-example`

---

## P-D · 上手文档统一

**目标**：消除 wheel / sdist / full-source / GitHub 自动归档 的混淆。

**建议范围**：

1. 在 `docs/installed-quickstart.md` 与 `.zh-CN.md` 顶端加四行对照表：用途、是否含 examples、是否可 pip 安装、是否可用作指南验收
2. 明示：**不要用 GitHub Source code (zip/tar.gz) 自动归档替代** `opendot-engineering-0.3.0a5-source.tar.gz`
3. 与 Release 外部 `EXPECTED_SUMS_SHA256` 流程交叉链接；不把摘要写进可变正文冒充 pin（遵循现有「外部 pin」纪律）

**验收**：

- [ ] EN/ZH 八个 shell 块字面一致性不被破坏（文档检查器）
- [ ] 新贡献者按表选错资产时，指南在 pip 前失败（已有校验则仅文档强化）

**分支建议**：`docs/asset-choice-table`

---

## P-E · 宣传边界

**目标**：固定对外表述边界，降低越界风险。

**建议新增** `docs/public-claims-boundary.md`（中英短页）：

| 允许 | 禁止 |
| --- | --- |
| ALPHA / NOT_SCORED；引用具体 Release/PR/Actions | 声称满分、对标产品已追平、机构背书 |
| 「HTTPS mock 合格；live NOT_RUN」 | 「已支持任意外部智能体」 |
| 「固定 DAG 源码合并；服务恢复有界/未跑」 | 「已具备生产级持久恢复」 |
| 公开合成科研模板 | 私密课题数据、未脱敏日志、内部 GPU/机房细节 |
| 链到 CAPABILITIES / crosswalk | 发帖到 X（安全确认未解前） |

**验收**：

- [ ] CONTRIBUTING / SUPPORT 链到该页
- [ ] 列出「对外文案发布前核对」三问：有无回执？范围是否写清？是否触及私密科研？

**分支建议**：`docs/public-claims-boundary`

---

## 建议合并顺序

1. **P-E**（文档、零风险）→ **P-C** → **P-D**
2. **P-A**（需本机 Temporal；有回执再合）
3. **P-B**（需自有 worker；默认 CI 跳过）

## 明确延后（本波不做）

- 多机 / 多 Dot 真实规模测量（先文档协议，见 SCORECARD D8）
- 完整 CAD 原生链与物理验证
- PyPI 发布
- UI（历史排除项）
- 任何私密材料课题的公开「端到端科研」包装

## 与已合 PR 的关系（核验）

| PR | 状态 | 本波关系 |
| --- | ---: | --- |
| #48 fixed DAG 源码 | 已合 | P-A 在其上做真服务验收 |
| #49 a5 状态页对齐 | 已合 | P-D/P-E 保持其 NOT_SCORED 口径 |
| #50 saturated observer | 已合 | P-A 计数/观察器兼容 |
| #51/#52 crosswalk | 已合 | 新 PR 更新 crosswalk 时只加导航，不改写历史 NOT_RUN 为满分 |
