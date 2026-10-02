# 固定 CAD → 网格 → 热传导工作流

[English](README.md)

一个源码示例命令顺序调用现有 geometry、Gmsh 网格和 CalculiX 热传导适配器，
运行公开的合成长方体算例。它不增加求解器、调度器、进程包装器或制品存储。

**此候选只通过伪造数据的接口契约测试，未执行真实 CAD、Gmsh 或 CalculiX。**
准备环境已有 Python 3.12.14 和单独的 pytest 9.1.1 环境。默认 Python 中存在
build123d 0.10.0 和 OCP 7.8.1.1.post1 的元数据，但尚未测试原生可用性。
该解释器没有 Gmsh 元数据，所检查的六个工作区环境也没有 CAD/Gmsh 元数据，
PATH 中没有发现 Gmsh/CalculiX。尚未确认完整、获批的原生环境。历史版本表
不代表软件当前可用。没有模拟数据冒充真实求解的运行模式，也不会自动安装软件。

## 无需原生软件的计划查看

在源码检出目录中运行（本示例不是包根命令）：

```sh
PYTHONPATH=src python examples/cad_cae/thermal_workflow.py plan
```

该命令只读取当前解释器的发行包元数据，不导入原生软件。输出为 `NOT_EXECUTED`；
Gmsh 原生库和求解器版本仍为 `NOT_CHECKED`。元数据存在不等于原生环境可执行。

唯一算例为 0.2 × 0.02 × 0.003 m 长方体。STEP 输出为 200 × 20 × 3 mm，
划分网格前转换为 SI 单位，使用 20 × 4 × 2 的线性 HEX8 网格：

- 315 个节点、160 个体单元、256 个边界 QUAD4 单元、1,280 行积分点热流
- 体积 0.000012 m³，合成导热系数 10 W/(m K)
- X_MIN 为 300 K、X_MAX 为 400 K，其余四面绝热，无体热源
- 解析温度 T(x) = 300 + 500 x K，x 以米计；热流 (−5000, 0, 0) W/m²
- 两端外部热反力分别为 −0.3 W、+0.3 W；正号表示供热

## 仅在另行批准的现有环境中运行一次

下面是命令模板，本候选未执行此命令。三个可执行文件路径都须由操作者明确配置并审核。
调用命令的 CAD Python 需要 build123d **0.10.0**、CadQuery-OCP **7.8.1.1.post1**；
单独的 Gmsh Python 需要包装器和实际加载的原生库均为 **4.15.2**；CalculiX
必须为 **2.23**。保留的参考平台为 Linux / Python 3.12。不会发现、下载、安装或
升级依赖；原生身份、完整依赖闭包和许可证仍需单独审核。

```sh
PYTHONPATH=src /approved/cad/bin/python examples/cad_cae/thermal_workflow.py run \
  /new/output/thermal-workflow \
  --gmsh-python /approved/gmsh/bin/python --solver /approved/bin/ccx_2.23
```

输出目录必须不存在、位于本检出目录之外，父目录不得为符号链接。两个命令行软件路径
必须是操作者提供的绝对路径，且已存在、可执行。不请求可选的 CadQuery 兼容性检查。

依次调用 `export_beam`、`mesh_beam`、`run_thermal`，每个仅一次，各阶段之间
使用现有验证器。任何失败都阻止后续阶段；不重试、不回退、不恢复、不清理或回滚。
先前有效制品和失败适配器的诊断保留。已有输出（包括空目录）会被拒绝。
理解失败原因后，才应选择新的输出目录。

结果保存在 `cad/`、`mesh/`、`thermal/` 中，由原有组件生成原始清单、回执及
STEP/MSH/输入卡/DAT/STA/CVG/日志。热传导包还包含由解析结果生成的 CSV 和有标注的
SVG。工作流摘要实时计算并写到标准输出，不新增一套验收回执。

## 无需原生软件的只读复验

```sh
PYTHONPATH=src python examples/cad_cae/thermal_workflow.py verify \
  /existing/output/thermal-workflow
```

复验调用全部现有制品验证器，要求固定尺寸、网格、线性算例和超时时间，要求 v2 网格
记录的身份状态为 `VERIFIED_AT_EXECUTION`，逐字节比对 CAD 到网格的输入副本，以及
网格到热传导包的完整快照。前后重复读取和哈希可拒绝一般的持续修改。消费者复用
现有有界、拒绝符号链接的读取器，每文件最多 32 MiB。原验证器保持不变；输入仍须是
可信、协作式、稳定的文件，不保证抵御恶意并发修改。

原始结果检查全部节点温度（绝对容差 0.0001 K）、每单元全部八个积分点的热流向量
（0.001 W/m²）、端面反力总和、自由节点反力和整体能量平衡（1e-7 W），并检查真实格式
的完成/收敛记录和固定输入卡/图表一致性。**它不检查每个受约束节点的反力分布**：
同一端面上等量反向误差可在求和时抵消。一个线性场网格通过不是收敛性、网格无关性、
材料验证或物理实验。

结果为 `RECORDED_WORKFLOW_CONSISTENCY_PASS`。记录的原生身份不构成执行真实性
认证，内部一致的伪造记录也可能通过。哈希不能防止能重写全部证据的人。
`scientific_accepted` 与 `device_control_authorized` 保持 false；物理验证为
`NOT_PERFORMED`、独立审查为 `NOT_EVALUATED`、网格无关性为 `NOT_ESTABLISHED`。
已保存的摘要不会被作为可信输入。

## 资源与权限边界

- CAD 在调用进程中运行，不新增墙钟/CPU/文件大小/线程限制
- 网格和求解各请求 60 秒墙钟时间、一个配置线程；原有 CPU 上限为 300 秒与继承的有限上限中的较小值
- 网格保留继承的较低文件大小限制或使用 32 MiB；原有求解器直接设置 32 MiB，不保留更低继承限制
- 不保证整个工作流的时间、内存/总输出上限、恶意子进程隔离、进程树、崩溃事务或实际 CPU 核时
- Gmsh v2 的现有身份检查通常读取 `/proc/self/maps`；本次不运行，原生执行和此范围需另行批准
- 原生制品可能包含本地路径；分享前需单独审查，本例不提供脱敏或发布授权

## 便携契约测试

```sh
PYTHONPATH=src python -m pytest tests/test_cad_thermal_workflow.py -q
```

测试仅将原生边界替换为明确标注的伪造数据，同时执行未修改的适配器主体和原始制品
验证器。覆盖固定数量/解析常量、单位/连接/边界、重新封装哈希的输入卡/热流/CVG
错误、分别有效却不属于同一条链的制品、旧身份拒绝、失败阻止后续调用、保留已有输出、
只读复验。测试不导入 CAD/Gmsh、不启动求解器或身份探测、不做网格加密或进程寿命测试。
测试通过不代表实际原生运行已合格。

详见现有[几何](../../docs/cad-geometry.md)、[网格](../../docs/cad-mesh.md)和
[热传导](../../docs/thermal-conduction.md)契约。独立的 geometry-only 配方和历史依赖
说明保留在[英文说明](README.md#geometry-only-beam-recipe-existing-adapter)中。
