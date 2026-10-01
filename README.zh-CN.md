# OpenDot Engineering

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/brand/opendot-readme-banner-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="assets/brand/opendot-readme-banner-light.svg">
  <img alt="OpenDot" src="assets/brand/opendot-readme-banner-light.svg" width="1280">
</picture>

[English](README.md) · [安装与运行](docs/installed-quickstart.zh-CN.md) · [能力清单](CAPABILITIES.zh-CN.md) · [架构](docs/architecture.md)

执行具有明确声明的 Python 工具，查看验收结果，再取回它产生的准确字节。OpenDot Engineering 将本地函数执行、按哈希寻址的产物、证据检查和受控 Git 工作区放进同一个软件包，面向开发者与科研工程人员。

**0.2.0a6 ALPHA 预发布版已提供。** [下载](https://github.com/sddvacav/opendot/releases/tag/v0.2.0a6) · [安装](docs/installed-quickstart.zh-CN.md) · [仓库](https://github.com/sddvacav/opendot) · [议题](https://github.com/sddvacav/opendot/issues)

[标签对应源码](https://github.com/sddvacav/opendot/commit/965ed8c49c47d7b79716ba1843462b84ff21a27f)通过 [1,183 项可移植 CI 检查](https://github.com/sddvacav/opendot/actions/runs/36885554336)，另行报告 49 项子测试。本工具仍处于实验阶段，不具备生产就绪承诺；这些检查不构成科学验收。

当前 `main` 分支文档领先于发布版。已发布产物仍绑定标签源码及其原始 README 元数据；从 `main` 重建会改变这些元数据。[各版本证据与限制](CAPABILITIES.zh-CN.md)保留历史测试记录。

## 运行合成示例

第一个示例要求 Python 3.12+，不需要可选软件包。在经过检查的 Linux/POSIX 环境中，从源代码根目录运行；输出放在仓库外可信目录下的新路径中：

```sh
OUTPUT_PARENT=$(mktemp -d /tmp/opendot-composition.XXXXXX)
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -B \
  examples/callable-artifacts/demo.py --output "$OUTPUT_PARENT/result"
```

JSON 应显示 `synthetic_software_assertions_passed: true`，并呈现三种结果：

- **COMPLETED：** 获准工具写入产物，保存的字节与 SHA-256 和返回引用一致
- **FAILED：** 语义验收拒绝结果；完整但未被接受的产物仍可检查
- **BLOCKED：** 缺少权限，处理函数没有运行

这些是刻意构造的软件检查案例。产物存储会跟随符号链接，因此必须使用可信根目录；验收失败不会回滚已发生的作用。每次运行都选择新输出路径。若该脚本报告 `--output already exists`（退出码 2），保留之前的结果并选择新路径。[了解示例](examples/callable-artifacts/README.md)

**准备安装 wheel？** 请使用[完整安装指南](docs/installed-quickstart.zh-CN.md)，按说明复制匹配的示例并核验安装后的导入位置。wheel 包含软件包，示例文件保留在源代码材料中。

如需从 CSV 到统计结果的完整示例，请从[合成测量复核](examples/measurement-review/README.zh-CN.md)开始：运行 valid、wrong-mean、denied 三种案例，找到保留的结果字节，进行验证，并处理输出路径已存在的情况。

六项有限的证据／来源／轨迹案例见[来源边界示例](examples/source-boundary/README.md)，其[历史研究语境](docs/research/demand-gap-20261001/README.md)另行标明。

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
| 描述智能体元数据并显式验证 | [智能体契约 API](docs/agent-contracts.md) · [元数据示例](examples/agent-contracts/README.md) |
| 执行带有声明权限和验收器的函数 | [函数执行 API](docs/callable-execution.md) |
| 使用统一引用类型存储、核验本地字节 | [产物 API](docs/canonical-artifacts.md) |
| 创建独立本地工作副本并观察改动 | [Git 工作区示例](examples/git-workspaces/README.md) |
| 检查固定来源或人为构造的资格记录 | [来源审计](docs/local-source-audit.md) · [资格记录检查](docs/synthetic-lab-qualification.md) |
| 加载经过明确复核的本地 Python 模块 | [来源准入](docs/source-admission.md) |
| 运行有限的模拟仪器实验 | [模拟实验](docs/simulated-lab.md) |
| 探索有边界的几何、网格、导热与梁契约 | [CAD/CAE 指南](examples/cad_cae/README.md) |

Git API 仅包含 **create/status/diff**，要求可信、协作式使用的 POSIX 仓库与可信系统 **Git 2.52.0+**，不支持的特性会被拒绝。diff 仅覆盖已跟踪文件的未暂存改动；API 不提交、删除或同步仓库。[兼容范围与所有权规则](docs/git-workspaces.md)

默认安装没有必需的运行时 Python 依赖。可选模拟实验与原生 CAD/CAE 执行分别准备依赖。若干证据 API 需要 POSIX 文件操作；已复核的环境是 Linux。一个 `opendot-engineering` 分发包提供 `opendot_engineering` 命名空间，通过 Python API 与模块入口使用，没有注册独立控制台命令。

## 发展方向

OpenDot 的长期目标，是将科研与工程任务转化为可复核的成果，并明确记录人工决策、可恢复进度和资源使用。下一项里程碑是一条可以独立重放的完整工作流。[带日期的公开来源研究](docs/research/README.md)与[优先级映射](RESEARCH-MAP.zh-CN.md)说明这一研发方向，不将其当作已完成功能或机构背书。

## 项目信息

[版本概览](OVERVIEW.zh-CN.md) · [变更记录](CHANGELOG.md) · [参与贡献](CONTRIBUTING.md) · [安全](SECURITY.md) · [支持](SUPPORT.md) · [发布门槛](docs/release-checklist.md)

项目原始代码使用 [Apache-2.0](LICENSE)，另见 [NOTICE](NOTICE) 与独立的[品牌资源声明](assets/brand/NOTICE)。可选依赖保留各自义务。公开使用问题和合成错误复现可提交至 [GitHub 议题](https://github.com/sddvacav/opendot/issues)。不要公开机密或安全敏感细节；请阅读[安全说明](SECURITY.md)。不承诺响应时限。
