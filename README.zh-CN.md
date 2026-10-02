# OpenDot Engineering

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/brand/opendot-readme-banner-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="assets/brand/opendot-readme-banner-light.svg">
  <img alt="OpenDot" src="assets/brand/opendot-readme-banner-light.svg" width="1280">
</picture>

[English](README.md) · [安装](docs/installed-quickstart.zh-CN.md) · [第一个结果](#运行合成示例) · [能力清单](CAPABILITIES.zh-CN.md) · [参与贡献](CONTRIBUTING.md)

OpenDot Engineering 是一套用于本地工具执行和结果检查的 Python 工具包。为函数声明权限与验收器，按 SHA-256 保存输出，再分别检查保存的字节是否完整、结果是否被接受。

它适合开发者与科研工程人员构建可复核的工作流原型：把函数输出连接到产物存储、复核合成测量数据的统计结果，或创建受控的本地 Git 工作副本。先运行下面的小示例，再按需要查看 [API 与示例](#按需要选择入口)。

**实验性 alpha · 0.3.0a1 · NOT_SCORED。** 下载 [0.3.0a1 预发布版](https://github.com/sddvacav/opendot/releases/tag/v0.3.0a1)，按[版本固定的安装指南](docs/installed-quickstart.zh-CN.md)取得 wheel、匹配的源码示例并核验 SHA-256。要求 Python 3.12+；默认软件包没有运行时 Python 依赖。已复核的环境是 Linux。

**源码与发行物不同：** 当前源码包含尚未发布的 [Gmsh 单文件大小限制修复](docs/gmsh-cpu-ceiling.md)。已发布的 v0.3.0a1 产物不含此修复，原有哈希保持不变。

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

具体范围见[能力与历史证据清单](CAPABILITIES.zh-CN.md)、[结构验证 v2](docs/structural-default-v2.md)及[当前源码验证记录](docs/structural-v2-candidate-verification.md)。先前的 [a4 检查](docs/verifier-ci-verification.md)和[构建重复性记录](docs/build-toolchain.md)仍只适用于各自版本，不构成新源码或发行物的验收。

## 发展方向

OpenDot 的长期目标，是将科研与工程任务转化为可复核的成果，并明确记录人工决策、可恢复进度和资源使用。下一项里程碑是一条可以独立重放的完整工作流。[带日期的公开来源研究](docs/research/README.md)与[优先级映射](RESEARCH-MAP.zh-CN.md)说明这一研发方向，不将其当作已完成功能或机构背书。

## 参与贡献

可以从更清楚的文档、最小合成示例或范围明确的适配器测试开始。先阅读[贡献指南](CONTRIBUTING.md)，了解支持的范围与指定检查，再通过 [GitHub 议题](https://github.com/sddvacav/opendot/issues)提交非敏感建议或可复现的错误报告。分享敏感细节前，请先阅读[安全说明](SECURITY.md)。

## 项目信息

[版本概览](OVERVIEW.zh-CN.md) · [变更记录](CHANGELOG.md) · [参与贡献](CONTRIBUTING.md) · [安全](SECURITY.md) · [支持](SUPPORT.md) · [发布门槛](docs/release-checklist.md)

项目原始代码使用 [Apache-2.0](LICENSE)，另见 [NOTICE](NOTICE) 与独立的[品牌资源声明](assets/brand/NOTICE)。可选依赖保留各自义务。不承诺响应时限。
