# OpenDot 公开宣传边界清单（中文）

- 编制：2026-10-25（Asia/Shanghai）
- 对应：NEXT_PRS **P-E**；SCORECARD **D10**；已合 `scorecard_cn_20261025.md` / `desensitize_cn_20261025.md` / `next_prs_cn_20261025.md`
- 性质：**项目自研对外表述闸门**，不是法务意见、机构背书或营销授权
- 官方状态硬约束：仓库声明 **ALPHA / NOT_SCORED**；**禁止声称满分、生产就绪或已获买方/机构验收**
- 适用范围：README、Release notes、Issue/Discussion、对外演示口播、邮件/社交文案草稿、第三方转载摘要

## 0. 三问（对外文案发布前必答）

任一文案在发出或合入公开仓前，必须书面可答「是」：

1. **有无回执？** 主张是否绑定可核验出处（Release 标签、已合 PR、Actions run URL、指南块 PASS 记录）？无回执 → 不得升格为「已具备」。
2. **范围是否写清？** 是否写明 mock / 合成 / 单机 loopback / NOT_RUN / 有界，而不是暗示通用能力？
3. **是否触及私密科研？** 是否含未脱敏课题数据、内部 GPU/机房、未发表材料/计算？触及 → **禁止入公开主张**（见脱敏清单）。

任一问答「否」或「不确定」→ **不得发布**。

---

## 1. 允许说（Allowed）

| 类别 | 允许表述（示例口径） | 必须同时保留的限定 |
| --- | --- | --- |
| 官方状态 | 「OpenDot 当前为 **ALPHA / NOT_SCORED**」 | 不得省略 NOT_SCORED |
| 证据锚点 | 「见 Release `v0.3.0a5` / PR #N / Actions run …」 | 只引用公开可打开的 URL |
| 记分卡 | 「项目自研十维导航记分卡；非机构打分」 | 明示自研推断、禁止当满分证明 |
| HTTPS | 「HTTPS **mock** 有界合格；**live worker / provider / model NOT_RUN**」 | 不得删掉 live NOT_RUN |
| 持久恢复 | 「固定 DAG **源码已合**；真实服务恢复为有界/未跑（见 ADR / crosswalk）」 | 不得写成生产级恢复 |
| Temporal | 「历史单机 loopback 有界证据；多机 / 崩溃 fencing 未评」 | 不得把历史批次当规模证明 |
| 安装指南 | 「a5 双语指南块 1–6、8 PASS；Git 块 7 NOT_RUN」 | 保留块级粒度 |
| 合成科研 | 「公开**合成**科研模板 / fixture；`scientific_accepted=false`」 | 标明 synthetic；禁止暗示真实课题验收 |
| 能力缺口 | 「真实外部智能体 / 多机协同 / 科研端到端仍为最大缺口」 | 与 SCORECARD 最大缺口一致 |
| 导航 | 「详见 CAPABILITIES、source-feature-crosswalk、本边界页」 | 用链接，不改写历史 NOT_RUN 为满分 |
| Codex | 「本项目推进禁用 Codex CLI/云任务」 | 与仓库约束一致时可陈述 |

---

## 2. 禁止说（Forbidden）

| 类别 | 禁止表述（触发即拒） | 原因 |
| --- | --- | --- |
| 满分 / 完成 | 「已满分」「十维闭环」「对标产品已追平」 | 官方 NOT_SCORED；记分卡非背书 |
| 机构背书 | 「某部委/基金/买方已验收或推荐」 | 无此类回执；政策链接≠背书 |
| 生产就绪 | 「生产级持久恢复」「可上生产互操作」 | D3/D4 仍为级 2；恢复与 live NOT_RUN |
| 任意智能体 | 「已支持任意外部智能体 / 任意模型供应商」 | 仅有限 mock；live NOT_RUN |
| 通用 A2A | 「A2A 生产就绪 / 已 ACCEPTED」 | 候选仍 UNACCEPTED（除非协议与证明变更） |
| 科学验收 | 「科学验收通过」「端到端科研已跑通」 | `scientific_accepted` 公开侧恒 false；端到端 NOT_RUN |
| 私密科研入公开主张 | 未发表配方/显微/DFT·MD 轨迹、试样编号、私有仓路径、内部 GPU UUID/机房/队列账号 | 硬规则：私密科研不得进入公开主张或公开仓 |
| 未脱敏日志 | 主机名、内网 IP、PID、真名通讯录、Token | 见脱敏清单 §2 |
| X 发帖 | 在安全确认未解前发帖到 X / 同步营销帖 | 用户约束：禁止 |
| 静默升格 | 把历史 NOT_RUN / PROPOSED 改写成 PASS 而不附新回执 | fail-closed；禁止证据漂移 |
| PyPI / UI | 「已上 PyPI」「已有正式 UI」 | 本波明确延后项 |

---

## 3. 与 SCORECARD / 脱敏的对齐（摘要）

| 来源 | 对本页的约束 |
| --- | --- |
| SCORECARD D10 | 主张边界与公开发布纪律；对外传播脱离证据易越界 |
| SCORECARD 总览 | 最大缺口：真实外部智能体 · 多机 · 科研端到端——宣传不得假装已补齐 |
| DESENSITIZE | 私密科研材料不得进入公开仓；公开侧只用合成/公开权利清晰数据 |
| NEXT_PRS 禁止项 | 不声称满分或生产就绪；不把私密科研写入本仓；安全确认前不发 X |

---

## 4. 文案模板（可复制）

**安全短述（推荐默认）**：

> OpenDot 是 ALPHA / NOT_SCORED 的开源工程运行时。当前公开证据覆盖有界合成示例与部分单机合格项；HTTPS live、真实服务级持久恢复、多机协同与科研端到端仍为 NOT_RUN。详情见 CAPABILITIES 与公开记分卡（自研导航，非机构打分）。

**禁止改写为**：

> OpenDot 已具备生产级多智能体协同与完整科研验收。

---

## 5. 合入 / 发布检查（PR 描述可勾选）

- [ ] 全文保留 **ALPHA / NOT_SCORED**
- [ ] 每个「已具备」类动词都有公开回执链接或明确「有界 / mock / 合成」限定
- [ ] 未把 live / 服务恢复 / 多机 / 科学验收写成已完成
- [ ] 未引入私密科研指纹（材料、路径、机房、未发表结论）
- [ ] 未计划在安全确认前发帖到 X
- [ ] 若更新 crosswalk / CAPABILITIES：只加导航，不静默改写历史 NOT_RUN

## 6. 相关链接（仓内）

- `docs/research/scorecard_cn_20261025.md`
- `docs/research/next_prs_cn_20261025.md`
- `docs/research/desensitize_cn_20261025.md`
- `docs/research/source-feature-crosswalk.md`
- CAPABILITIES（仓库根或 docs 内既有页）

---

*本页随证据更新而修订；升级任何「允许说」条目时必须同步回执，否则保持禁止升格。*
