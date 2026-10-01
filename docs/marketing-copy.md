# Scope-limited description drafts

These descriptions are for review. Nothing here authorizes publication or announces a supported public release. Keep the status sentence attached to the description.

## Short description

**English**

OpenDot Engineering is an early-stage standalone package for local source auditing, optional trusted-source admission, synthetic qualification-record checks, a finite fake-instrument simulation, and optional deterministic CAD/CAE contracts. The source candidate is unreleased; it is not a complete agent runtime or engineering platform.

**简体中文**

OpenDot Engineering 是一个早期独立软件包，提供本地来源审计、可选的可信源代码准入、合成资格记录检查、有限的模拟仪器实验，以及可选的确定性 CAD/CAE 契约。当前源代码候选版本尚未发布，不是完整的智能体运行时或工程平台。

## Longer introduction

**English**

Start with two small standard-library examples: audit pinned local synthetic evidence and check invented qualification records against explicit oracles. Optional source admission loads explicitly reviewed local Python modules with ordinary process authority; it is not a sandbox. The optional simulated-lab adapter runs a fixed Bluesky plan on internally constructed ophyd fake instruments, with at most 16 setpoint/read steps and separately verifiable raw documents. Running it requires the exact optional dependency versions. Scientific acceptance and physical-device authority remain false. Optional CAD/CAE contracts require separately prepared native backends. Task coordination, durable recovery, and live agent evaluation remain outside this package. Narrow local review results do not establish a supported public release.

**简体中文**

先从两个只需标准库的小型示例开始：审计固定的本地合成证据，并将人为构造的资格记录与明确的预期结果核对。可选来源准入以普通进程权限加载经过明确复核的本地 Python 模块，不提供沙箱。可选模拟实验适配器使用内部构造的 ophyd 假仪器执行固定 Bluesky 计划，最多包含 16 个设定与读取步骤，并生成可单独验证的原始文档；执行需要指定版本的可选依赖。科学认可和实体设备权限保持为假。可选 CAD/CAE 契约需要另外准备原生后端。任务协调、持久恢复和真实智能体评估仍在本包范围以外。范围受限的本地复核结果不代表已经正式公开发布或建立支持承诺。

## Review guardrails

Link claims to [claim status](claim-status.md). Keep [source-admission boundaries](source-admission.md) and [simulation limits](simulated-lab.md) attached when describing those options. Do not imply production readiness, unmeasured scale, sandboxing, security certification, scientific validation, support guarantees, or peer integration. Preserve the actual [LICENSE](../LICENSE), [NOTICE](../NOTICE), and [AI-assisted artwork notice](../assets/brand/NOTICE). Do not invent badges, endorsements, source URLs, private contacts, adoption counts, or launch dates.
