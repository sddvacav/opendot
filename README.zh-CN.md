# OpenDot Engineering

## 当前实验性发布 · 0.3.0a5

**ALPHA / NOT_SCORED；[已发布预发布版](https://github.com/sddvacav/opendot/releases/tag/v0.3.0a5)。**
[a5 安装入门](docs/installed-quickstart.zh-CN.md)仅适用于匹配且已复核的五文件包，
并要求来自外部独立验收的 SHA256SUMS 摘要。源码、安装与指南执行资格需要各自的外部回执；
a4 验收不会转移到 a5。

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
- 安装默认 wheel 不会启动原生后端或服务。完整 CAD／热传导原生执行为 `NOT_RUN`；
  物理验证 `NOT_PERFORMED`、独立审查 `NOT_EVALUATED`、网格无关性 `NOT_ESTABLISHED`。
  科学／设备权限仍为 false；历史 Temporal 证据和 [a3 清单](docs/release-inventory/v0.3.0a3/README.md)
  保留各自范围，不新增智能体规模或 UI 声明

已发布的前一版为 [0.3.0a4](https://github.com/sddvacav/opendot/releases/tag/v0.3.0a4)，源码提交为
`2d16190a8121410bbeea252869b196f7891e1696`。其[固定版本安装指南](https://github.com/sddvacav/opendot/blob/2d16190a8121410bbeea252869b196f7891e1696/docs/installed-quickstart.zh-CN.md)
和[发行说明](https://github.com/sddvacav/opendot/releases/download/v0.3.0a4/RELEASE-NOTES.md)保留精确的历史产物与资格范围；冻结产物不变。

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/brand/opendot-readme-banner-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="assets/brand/opendot-readme-banner-light.svg">
  <img alt="OpenDot" src="assets/brand/opendot-readme-banner-light.svg" width="1280">
</picture>

[English](README.md) · [安装](docs/installed-quickstart.zh-CN.md) · [第一个结果](#运行合成示例) · [能力清单](CAPABILITIES.zh-CN.md) · [参与贡献](CONTRIBUTING.md)

OpenDot Engineering 是一套用于本地工具执行和结果检查的 Python 工具包。为函数声明权限与验收器，按 SHA-256 保存输出，再分别检查保存的字节是否完整、结果是否被接受。

它适合开发者与科研工程人员构建可复核的工作流原型：把函数输出连接到产物存储、复核合成测量数据的统计结果，或创建受控的本地 Git 工作副本。先运行下面的小示例，再按需要查看 [API 与示例](#按需要选择入口)。

**合成结果预览** · [运行示例并核验已保存的输出](examples/measurement-review/README.zh-CN.md#预览已复核的合成结果)

`A.mean=2.0` · `B.mean=4.0` · 精确差值 `2/1` · 容差 `2/1`（单位均为 `au`）  
`CHECKED` · `within_tolerance=true`

`summary.txt` 提供文字摘要；`report.json` 中的对应字段为 `summary.conditions`、
`comparison` 和 `status`。这是仅源码示例，不是安装 wheel 后的 API；
它使用六行虚构数据，并非实验数据。`CHECKED` 表示算术已复核，超出容差的结果也可以是
`CHECKED`，不代表科学验收。所有结果保持 `scientific_accepted=false`、
`device_control_authorized=false`、`independent_review="NOT_EVALUATED"`。

**历史实验性 alpha · 0.3.0a3 · NOT_SCORED。** 下载 [0.3.0a3 ALPHA 预发布版](https://github.com/sddvacav/opendot/releases/tag/v0.3.0a3)，按[精确产物安装指南](https://github.com/sddvacav/opendot/blob/8d5d8667d65734fb5c40fa0526709a3159b7f165/docs/installed-quickstart.zh-CN.md)取得已发布 wheel、匹配的源码示例并核验 SHA-256。要求 Python 3.12+；默认软件包没有运行时 Python 依赖。已复核的环境是 Linux。

**a3 产物新增：** 可选的[有界产物读取](docs/canonical-artifacts.md#optional-bounded-retrieval-unreleased-source-increment) `get_bytes(..., max_bytes=N)`，以及完整源码中的[纯软件有限批次准备](docs/temporal-batch-qualification.md)。有界读取最多取得 N+1 个实际对象字节以检测超限；省略或传入 `None` 时仍读取整个对象。批次 fixture 模拟 200 个固定合成任务、16 个尚未验证终态的预留／工作流，以及八个外部 Activity 槽位／executor worker；它们不证明实际 200 任务服务运行、智能体数量、吞吐量或生产调度器。链接 API 说明中的较早“unreleased”标签属于源码检查点；固定的 a3 wheel 已包含有界读取 API。

**沿用自 [0.3.0a2](https://github.com/sddvacav/opendot/releases/tag/v0.3.0a2)：** [Gmsh 单文件大小限制修复](docs/gmsh-cpu-ceiling.md)与[可选有限范围 Temporal 传输](docs/temporal-reference-transport.md)。默认安装仍无运行时 Python 依赖；Temporal extra 需要另行批准并准备依赖，且不会自动启动服务。未改动的 v0.3.0a1 产物不含这两项新增内容；其[历史安装指南](https://github.com/sddvacav/opendot/blob/359f781a5aa1650ae92b1af81cf369a17c444045/docs/installed-quickstart.zh-CN.md)保留原有固定值。

上方历史 a3 段落的安装与发行声明仅针对冻结的 a3 产物。后续 `main` 变更与 CI 不会改变或验证该软件包；其批次内容仍仅为纯软件准备。下方三角色测量比较 `compare.py` 属于后续 `main` 源码，不在 a3 wheel 或完整源码产物中；a3 完整源码仍包含原有单角色 `demo.py`。

## 运行合成示例

这个源码示例仅使用标准库，写入并检查一份小型文本产物，无需模型、服务或原生求解器。在 Linux/POSIX 与 Python 3.12+ 环境中，从源代码根目录运行；输出放在仓库外可信目录下的新路径中：

```sh
OUTPUT_PARENT=$(mktemp -d /tmp/opendot-composition.XXXXXX)
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -B \
  examples/callable-artifacts/demo.py --output "$OUTPUT_PARENT/result"
```

在打印的 JSON 中查找 `synthetic_software_assertions_passed: true`。其中包含三种结果：

- **COMPLETED：** 获准工具写入产物，保存的字节与 SHA-256 和返回引用一致
- **FAILED：** 语义验收拒绝结果；完整但未被接受的产物仍可检查
- **BLOCKED：** 缺少权限，处理函数没有运行

查看 `success.returned_ref` 中的产物引用，以及 `success.independent_sha256_matches` 中的字节检查结果。结果保存在 `$OUTPUT_PARENT/result` 下。这些是合成软件案例，不构成科学验收。产物存储会跟随符号链接，因此必须使用可信根目录；验收失败不会回滚已发生的作用。若脚本报告 `--output already exists`（退出码 2），保留之前的结果并选择新路径。[了解示例](examples/callable-artifacts/README.md)

**准备安装 wheel？** 请使用[完整安装指南](docs/installed-quickstart.zh-CN.md)，按说明复制匹配的示例并核验安装后的导入位置。wheel 包含软件包，示例文件保留在源代码材料中。

如需从 CSV 到统计结果的完整示例，请从[合成测量复核](examples/measurement-review/README.zh-CN.md)开始：运行 valid、wrong-mean、denied 三种案例，找到保留的结果字节，进行验证，并处理输出路径已存在的情况。

如需查看来源声明冲突的合成检查，见[来源边界示例](examples/source-boundary/README.md)及其[历史研究语境](docs/research/demand-gap-20261001/README.md)。

## 软件包帮助与版本

从源代码根目录运行：

```sh
PYTHONPATH=src python -B -m opendot_engineering --help
PYTHONPATH=src python -B -m opendot_engineering --version
```

这个只读模块入口打印静态说明或实际导入的软件包代码版本，不启动运行时、
不分发工具，也不加载可选后端。安装后的命令与参数说明见[软件包帮助](docs/module-cli.md)。

## 按需要选择入口

| 想完成的事 | 从这里开始 |
| --- | --- |
| 执行带有声明权限和验收器的函数 | [函数执行 API](docs/callable-execution.md) |
| 使用统一引用类型存储、核验本地字节 | [产物 API](docs/canonical-artifacts.md) |
| 创建独立本地工作副本并观察改动 | [Git 工作区示例](examples/git-workspaces/README.md) |
| 描述智能体元数据并显式验证 | [智能体契约 API](docs/agent-contracts.md) · [元数据示例](examples/agent-contracts/README.md) |
| 检查固定来源或人为构造的资格记录 | [来源审计](docs/local-source-audit.md) · [资格记录检查](docs/synthetic-lab-qualification.md) |
| 加载经过明确复核的本地 Python 模块 | [来源准入](docs/source-admission.md) |
| 运行有限的模拟仪器实验 | [模拟实验](docs/simulated-lab.md) |
| 探索有边界的几何、网格、导热与梁契约 | [CAD/CAE 指南](examples/cad_cae/README.md) |

Git API 仅包含 **create/status/diff**，要求可信、协作式使用的 POSIX 仓库与可信系统 **Git 2.52.0+**，不支持的特性会被拒绝。diff 仅覆盖已跟踪文件的未暂存改动；API 不提交、删除或同步仓库。[兼容范围与所有权规则](docs/git-workspaces.md)

可选模拟实验与原生 CAD/CAE 执行需要分别准备依赖。若干证据 API 需要 POSIX 文件操作。`opendot-engineering` 分发包提供 `opendot_engineering` 命名空间，通过 Python API 与模块入口使用，没有注册独立控制台命令。模块边界见[架构说明](docs/architecture.md)。

## 状态与证据

软件包支持可信的本地工作流。模型驱动的自主智能体、持久恢复、多主机运行和数百智能体性能尚未在此实现或证明。声明的权限与预算不构成操作系统沙箱；字节完整性不赋予科学验收或设备控制权限。

当前版本证据与具体范围见[能力与证据清单](CAPABILITIES.zh-CN.md)、[结构验证 v2](docs/structural-default-v2.md)及[历史 0.3.0a1 验证记录](docs/structural-v2-candidate-verification.md)。先前的 [a4 检查](docs/verifier-ci-verification.md)和[构建重复性记录](docs/build-toolchain.md)仍只适用于各自版本，不构成新源码或发行物的验收。

## 发展方向

OpenDot 的长期目标，是将科研与工程任务转化为可复核的成果，并明确记录人工决策、可恢复进度和资源使用。下一项里程碑是一条可以独立重放的完整工作流。[带日期的公开来源研究](docs/research/README.md)与[优先级映射](RESEARCH-MAP.zh-CN.md)说明这一研发方向，不将其当作已完成功能或机构背书。

## 参与贡献

可以从更清楚的文档、最小合成示例或范围明确的适配器测试开始。先阅读[贡献指南](CONTRIBUTING.md)，了解支持的范围与指定检查，再通过 [GitHub 议题](https://github.com/sddvacav/opendot/issues)提交非敏感建议或可复现的错误报告。分享敏感细节前，请先阅读[安全说明](SECURITY.md)。

## 项目信息

[版本概览](OVERVIEW.zh-CN.md) · [变更记录](CHANGELOG.md) · [参与贡献](CONTRIBUTING.md) · [安全](SECURITY.md) · [支持](SUPPORT.md) · [发布门槛](docs/release-checklist.md)

项目原始代码使用 [Apache-2.0](LICENSE)，另见 [NOTICE](NOTICE) 与独立的[品牌资源声明](assets/brand/NOTICE)。可选依赖保留各自义务。不承诺响应时限。
