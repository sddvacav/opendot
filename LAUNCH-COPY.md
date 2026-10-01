# OpenDot Engineering announcement draft

Draft for a project update about an unreleased candidate. No publication or public repository creation is announced. Evidence snapshot: 1 October 2026.

## English

**Current candidate: 0.3.0a1, unreleased; NOT_SCORED.** This separate successor
integrates [structural default verification v2](docs/structural-default-v2.md):
conditional per-element energy consistency, schema 2 and explicit historical
`artifact_v1` compatibility. Scientific acceptance remains false. The source-boundary
example covers seven original synthetic protocols, eight unimplemented proposals,
and six separately counted synthetic parameter fixtures; no production policy is added.
Canonical execution/reference owners and optional energy-API results are unchanged.
The [Gmsh resource-limit setup](docs/gmsh-cpu-ceiling.md) preserves inherited lower
CPU and per-file ceilings; fake-resource checks do not establish native/kernel enforcement.
The file-size repair is an unreleased source-only follow-on; existing v0.3.0a1
release assets do not contain it and retain their original hashes.
[Current 0.3.0a1 verification scope](docs/structural-v2-candidate-verification.md)

### Historical a4 draft

OpenDot Engineering is building an inspectable foundation for local engineering work. The unreleased 0.2.0a4 candidate tightens the shared declared CalculiX 2.23 log gate, adds bounded offline documentation checks, and pins setuptools 84.0.0 as its build backend. Its metadata, callable, artifact and controlled Git APIs retain their existing boundaries.

The gate refuses ambiguous or repeated version headers. The source-only documentation helper checks local links, fragments and explicit HTML anchors within a documented subset, plus exactly eight nonempty, literal-identical shell blocks in each installed-guide language. It does not execute those commands. The historical a4 selected author source run passed 1,066 checks with zero failures/errors/skips. Component reviews have separate, overlapping scopes; exact final artifact and installed acceptance require their own delivery receipt. [Historical a4 verification](docs/verifier-ci-verification.md)

The predecessor's 899 source passes, final installed journeys and same-host build repeatability remain historical evidence. They do not accept this candidate or establish a new score. Durable recovery, live autonomous agents, physical-device authority, and large-scale agent performance remain future work. No new physics or native-execution result is announced.

## 简体中文

**当前候选：0.3.0a1，尚未发布；NOT_SCORED。** 本独立后继版本整合
[结构默认验证 v2](docs/structural-default-v2.md)：在声明条件下要求逐单元能量一致性，
返回 schema 2，并仅通过显式 `artifact_v1` 保留历史兼容行为。科学验收仍为 false。
来源边界示例覆盖七项原始合成协议，其余八项仍未实现；六个合成参数场景另行计数，
没有新增生产策略。既有执行／引用所有者及可选能量 API 返回结果保持不变。
[Gmsh 资源限制设置](docs/gmsh-cpu-ceiling.md)保留较低的继承 CPU 与单文件大小限制；合成资源检查不证明原生或内核强制执行。
文件大小修复仅属于尚未发布的源码后续变更；现有 v0.3.0a1 发布产物不含此修复，原有哈希保持不变。
[当前 0.3.0a1 验证范围](docs/structural-v2-candidate-verification.md)

### 历史 a4 草稿

OpenDot Engineering 正在构建便于检查的本地工程执行基础。尚未发布的 0.2.0a4 候选收紧共享的 CalculiX 2.23 日志版本声明门槛，新增有限范围的离线文档检查，并将构建后端固定为 setuptools 84.0.0。元数据、函数、产物和受控 Git API 保持既有边界。

日志门槛拒绝含糊或重复的版本头部。纯源码文档检查器在明确的语法子集内检查本地链接、片段和显式 HTML 锚点，并要求每种安装指南语言中恰好八个非空且逐字一致的 shell 代码块；它不执行这些命令。历史 a4 指定作者源码检查 1,066 项通过，失败／错误／跳过均为零。组件复核保留各自且存在重叠的范围；最终精确产物与安装验收以单独交付回执为准。[历史 a4 验证记录](docs/verifier-ci-verification.md)

前版的 899 项源码通过结果、最终安装实测与同主机构建重复性仍属于历史证据，不据此接受本候选或给出新评分。持久恢复、真实自主智能体、实体设备权限与大规模智能体性能仍需分别实现和验证。本次不发布新的物理模型或原生执行结果。

## Short description

**English:** Inspectable local engineering execution, artifacts, and evidence, with explicit acceptance boundaries. Unreleased candidate.

**简体中文：** 具有明确验收边界的本地工程执行、产物与证据基础。当前尚未发布。
