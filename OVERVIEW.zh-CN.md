# OpenDot Engineering 版本概览

## 当前 0.3.0a5 发布准备

**ALPHA / NOT_SCORED；候选准备，不是发布回执。**
[a5 安装入门](docs/installed-quickstart.zh-CN.md)仅适用于匹配且已复核的五文件包，
并要求来自外部独立验收的 SHA256SUMS 摘要。源码、安装与指南执行资格需要各自的外部回执；
a4 验收不会转移到本候选。

- Wheel：函数／产物 API、有界读取、只读帮助，以及可选、须显式导入的
  [HTTPS 交换模块](docs/a2a-http-transport.md)；默认运行时依赖仍为空。示例与文档不作为安装文件提供
- Sdist：用于重建 wheel 的输入，不是完整可运行示例或测试树
- 完整源码：[测量比较](examples/measurement-review/README.zh-CN.md)、仅元数据的
  [CAD／热传导计划](examples/cad_cae/README.zh-CN.md)（`NOT_EXECUTED`）、现有三文件
  [公开 STEP 参考](examples/cad_cae/native-geometry-reference/README.md#中文)，以及有限离线
  [效用 `history`／`profile`](examples/measurement-review/README.zh-CN.md#离线增量效用夹具报告)。
  这些工作流使用匹配源码树；STEP 保留历史 a4 来源，是静态投影，不是可重放的原生执行包
- HTTPS 仅有有限模拟资格验证；真实传输／worker／提供方／模型互通为 `NOT_RUN`。
  [A2A](docs/a2a-worker-turn.md)仍仅返回 `UNACCEPTED` 候选。
  真实 O3 保持 `PROPOSED / NOT_RUN`，实测投入为 `UNKNOWN`
- 本次准备不新增原生或服务运行。完整 CAD／热传导原生执行为 `NOT_RUN`；
  物理验证 `NOT_PERFORMED`、独立审查 `NOT_EVALUATED`、网格无关性 `NOT_ESTABLISHED`。
  科学／设备权限仍为 false；历史 Temporal 证据和 [a3 清单](docs/release-inventory/v0.3.0a3/README.md)
  保留各自范围，不新增智能体规模或 UI 声明

已发布的前一版为 [0.3.0a4](https://github.com/sddvacav/opendot/releases/tag/v0.3.0a4)，源码提交为
`2d16190a8121410bbeea252869b196f7891e1696`。其[固定版本安装指南](https://github.com/sddvacav/opendot/blob/2d16190a8121410bbeea252869b196f7891e1696/docs/installed-quickstart.zh-CN.md)
和[发行说明](https://github.com/sddvacav/opendot/releases/download/v0.3.0a4/RELEASE-NOTES.md)保留精确的历史产物与资格范围；冻结产物不变。

[English](OVERVIEW.md) · [能力与证据](CAPABILITIES.zh-CN.md) · [研究与优先级](RESEARCH-MAP.zh-CN.md)

**历史 0.3.0a3 版本 · 实验性 alpha · 证据截至 2026 年 10 月 2 日**

OpenDot Engineering 为本地工程工作提供一个便于检查的小型基础包：执行具有明确声明的 Python 工具、查看验收结果、按字节哈希保存产物，并为不同任务创建受控的 Git 工作区。它面向需要检查“执行了什么、产生了什么、哪些检查确实通过”的开发者和科研工程人员。

**历史实验性 alpha：0.3.0a3；NOT_SCORED。** 本版本整合
[结构默认验证 v2](docs/structural-default-v2.md)：在声明条件下要求逐单元能量一致性，
返回 schema 2，并仅通过显式 `artifact_v1` 保留历史兼容行为。科学验收仍为 false。
来源边界示例覆盖七项原始合成协议，其余八项仍未实现；六个合成参数场景另行计数，
没有新增生产策略。既有执行／引用所有者及可选能量 API 返回结果保持不变。
[Gmsh 资源限制设置](docs/gmsh-cpu-ceiling.md)保留较低的继承 CPU 与单文件大小限制；合成资源检查不证明原生或内核强制执行。
文件大小修复与[可选有限范围 Temporal 传输](docs/temporal-reference-transport.md)已打包进 0.3.0a2。未改动的 v0.3.0a1 发布产物不含这两项新增内容，原有哈希保持不变。
[历史 0.3.0a1 验证范围](docs/structural-v2-candidate-verification.md)

[0.3.0a3 ALPHA 预发布版](https://github.com/sddvacav/opendot/releases/tag/v0.3.0a3)现已提供。[精确产物安装指南](https://github.com/sddvacav/opendot/blob/8d5d8667d65734fb5c40fa0526709a3159b7f165/docs/installed-quickstart.zh-CN.md)固定其已发布 wheel、配套完整源码与 SHA-256。[历史 0.3.0a2 ALPHA 预发布版](https://github.com/sddvacav/opendot/releases/tag/v0.3.0a2)及其既有证据保持不变。[历史 0.3.0a1 安装指南](https://github.com/sddvacav/opendot/blob/359f781a5aa1650ae92b1af81cf369a17c444045/docs/installed-quickstart.zh-CN.md)与[历史 a6 安装指南](https://github.com/sddvacav/opendot/blob/eec73193594ee212ba091a9d7310c8762a4b0003/docs/installed-quickstart.zh-CN.md)保留各自独立的版本固定值；先前版本的结果不构成本次产物的验收。

a3 产物新增[可选有限读取](docs/canonical-artifacts.md#optional-bounded-retrieval-unreleased-source-increment)：
`get_bytes(..., max_bytes=N)` 最多取得 N+1 个实际对象字节以识别超限，省略参数或
传入 `None` 保留完整读取。可信普通文件与符号链接前提不变；它不提供恒定内存、时间、
沙箱或执行级保证。链接中“unreleased”属于先前源码检查点，固定 a3 wheel 已包含此 API。
完整源码中的[纯软件有限批量准备](docs/temporal-batch-qualification.md)仅检查精确
200 个冻结合成任务、16 个已预留／已提交但尚未验证终态的工作流，以及八个外部 Activity
槽位／执行器 worker；不是实际 200 任务服务执行、200 个智能体、实测并发或吞吐量。
本页安装与能力说明针对冻结的 a3 发布版。本次文档后续更新不重建或替换这些产物；
后续 `main` 改动及 CI 也不会改变或验收这些冻结产物。a3 仍只包含纯软件批量准备。

历史 a4 候选要求热学与结构验证器共享的日志门槛仅接受一个明确的 CalculiX 2.23 版本声明。新增纯源码文档检查器，检查有限范围的本地链接、片段与 HTML 锚点，以及每种安装指南语言中恰好八个非空、逐字一致的 shell 代码块。构建后端固定为 setuptools 84.0.0。这些改动不新增物理模型、运行时、原生执行或公开发布。见[历史 a4 验证记录](docs/verifier-ci-verification.md)、[文档检查边界](docs/documentation-checks.md)和[构建配置](docs/build-toolchain.md)。

历史证据保留版本边界：**0.2.0a1** Git 修复候选通过 **773 项指定作者检查**，无法检查的残留状态修复已通过独立源代码权限丢失反例复验，见[修复记录](docs/git-workspaces-residue-fix.md)。**0.2.0a0** 函数与产物集成另行通过 **695 项独立复跑的可移植检查**。这些结果不构成 **0.3.0a3** 的测试总数或独立验收、完整平台评分或公开发布。

**历史 a4 作者源码检查：1,066 项通过**，失败／错误／跳过均为零。**最终精确产物与安装验收以单独交付回执为准。** 独立组件结果存在重叠，不能叠加到该组合总数。历史 a4 可移植 CI 定义选择 988 项，不包含 78 项受控 Git 检查；该记录当时不证明托管执行。历史 0.3.0a2 托管执行的链接另见[能力清单](CAPABILITIES.zh-CN.md)。

历史 **0.2.0a3** 源码检查 **899 项通过**，失败／错误／跳过均为零。其最终 `a59419b` 回执覆盖新环境中每种语言全部八个 shell 代码块的安装实测；同一主机上的两个干净构建环境复现了该版精确 wheel。这些结果及前版评分不能转移到本候选。[先前开发记录](docs/parallel-development-verification.md)描述宿主协调的工作，不证明自治调度器。历史 0.2.0a2 作者检查通过 805 项指定源码测试；独立元数据检查在源码及其安装包上分别通过同一组 410 项，仍仅属于前版证据。

## 现在可以检查什么

### 显式验证的智能体元数据

[智能体契约 API](docs/agent-contracts.md)提供仅含元数据的 `Capability` 与 `AgentManifest`。需显式调用 `.validate()` 检查声明；创建契约不会启动智能体。[元数据示例](examples/agent-contracts/README.md)展示这一边界。预算与权限声明不会分配资源、授权工具调用或新增执行强制机制。

### 工具结果有明确的验收状态

[函数与产物组合示例](examples/callable-artifacts/README.md)执行获准的 Python 函数，保存合成输出，返回统一的产物引用，并独立验证保存的字节。它还展示两种重要情况：缺少权限时，处理函数不会被调用；语义验收拒绝时，磁盘上仍可能保留完整但未被接受的产物。

这个区分直接影响结果能否使用。文件保存正确，不代表内容满足任务验收条件。OpenDot 分开记录字节完整性、工具执行状态与语义接受结果。该示例不宣称科学有效性，也不会在失败后回滚已经发生的作用。

### 工作副本从固定提交开始

[Git 工作区配置](docs/git-workspaces.md)仅公开 **create、status 和 diff** 三种操作。创建时将选定的本地引用一次性解析为完整提交标识；后续观察继续检查工作区是否属于同一存活管理器，以及 HEAD 是否仍等于创建时的提交。

[一次性示例](examples/git-workspaces/README.md)创建两个工作树，并检查对第一个工作树的编辑没有改变第二个或主工作副本。此配置要求可信、协作式使用的 POSIX 本地仓库，以及可信系统 **Git 2.52.0 或更新版本**。作者在 Linux、Git 2.52.0 环境完成了检查。许多 Git 特性会被明确拒绝；当前没有承诺兼容任意仓库。

`diff` 只覆盖已跟踪文件相对索引的未暂存改动，不包含仅暂存的改动或未跟踪文件内容。API 不提供提交、删除工作树、拉取、推送、创建失败后的重试或残留清理。

### 证据检查与可选领域工具

- [本地来源审计](docs/local-source-audit.md)检查固定字节和声明的证据元数据，保留未知值
- [可信源代码准入](docs/source-admission.md)加载经过明确复核的本地 Python 模块，返回原有命名对象；代码仍具有普通 Python 进程权限
- [合成资格记录](docs/synthetic-lab-qualification.md)将人为构造的记录与声明的预期结果核对；正确拒绝与真实资格认证分别记录
- [模拟仪器实验](docs/simulated-lab.md)通过内部创建的 ophyd 假仪器运行固定 Bluesky 计划，最多 16 个设定与读取步骤，并支持离线文档验证
- [可选 CAD/CAE 契约](examples/cad_cae/README.md)覆盖范围受限的几何、网格、导热和梁示例，原生后端需要另外准备
- [可选 Temporal 参考传输](docs/temporal-reference-transport.md)仅交付固定的 `synthetic.bounded_sum.v1`：单主机回环、静止状态下正常重启后的排队首次交付、已记录结果重放；不证明执行中崩溃恢复、多主机或全局恰好一次

## 安装与首次运行

分发包名为 `opendot-engineering`，Python 导入命名空间为 `opendot_engineering`。默认安装没有必需的运行时 Python 依赖，要求 Python 3.12 或更新版本。若干文件检查 API 需要 POSIX 操作。可选 `temporal` extra 固定 `temporalio==1.34.0`；其依赖需另行批准并准备，安装不会启动服务。模拟实验执行使用可选的固定版本依赖；原生 CAD/CAE 执行有单独的后端环境要求。当前没有注册独立控制台命令。

先按 [精确 0.3.0a5 候选安装入门](docs/installed-quickstart.zh-CN.md)离线核验哈希并得到第一个结果。使用源码时，参见[入门说明](docs/getting-started.md)和[小型函数与产物组合示例](examples/callable-artifacts/README.md)。[Git 示例](examples/git-workspaces/README.md)仅适用于满足条件的本地主机。[公开仓库](https://github.com/sddvacav/opendot)与[议题](https://github.com/sddvacav/opendot/issues)已核实。[历史 a6 预发布版](https://github.com/sddvacav/opendot/releases/tag/v0.2.0a6)另行提供；安装前请在 [Releases](https://github.com/sddvacav/opendot/releases) 核对现有产物及其精确版本。

## 仍需遵守的边界

产物存储要求调用方控制可信根目录，会跟随符号链接，也不会将对象和元数据作为一个事务发布。函数权限与幂等性来自嵌入应用的声明。线程和 Git 子进程控制不是操作系统沙箱；函数超时不能保证任意 Python 代码已经终止。验收或创建失败仍可能留下需要检查的作用与文件。

任务编排、持久恢复、真实模型评估、实体设备控制，以及多机或数百智能体的性能均属于未来工作。既有使用方尚未完成迁移。相关合成适配器的科学与设备权限标记保持为假。指定范围的本地检查不能证明托管 CI、广泛平台支持、成本节省或生产可用性。

## 下一步

下一项有价值的里程碑，是让新使用者能够重放、让独立复核者能够验收的一条窄工作流。优先事项是当前精确候选版本的独立复核、首次运行体验、清晰的失败与权限边界，以及具有版本化输入和明确验收条件的完整领域案例。持久恢复和并行收益需要分别实现并实测。

[公开来源研究](docs/research/README.md)为这一方向提供产品假设，不代表机构背书、客户承诺或功能完成证明。项目原始代码保留 [Apache-2.0 许可证](LICENSE)与[相关声明](NOTICE)；可选依赖仍有各自的许可义务。

## 历史 a4 源码交付补充

当时的安装包实现保持已验收的 0.2.0a4 字节不变。[历史源码补充](docs/delivery-workflows-verification.md)
提供合成测量数据复核流程、测试依赖哈希锁、逐文件来源清单，以及有日期和出处的需求研究与开源对标附件。
组合源码的验收另附回执；历史 78 分不自动适用于后续每次修改。它不意味着新增多机、自治平台或科学验收能力。
