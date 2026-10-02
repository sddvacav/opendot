# 复核一批合成重复测量数据

[English](README.md)

这个例子解决一个具体的软件问题：收到数据表和统计结果后，明确它们对应哪个输入版本、是否经过指定检查，以及结果能否按哈希找回。它复用现有 ToolRuntime 和 ArtifactStore，不增加运行时或调度器。

预期用途是减少输入、结果与复核记录之间的手工错配；尚无真实用户研究、节省时间、投资回报或优于其他工具的证据。

## 数据和验收值

batch.csv 是六行完全虚构的数据，A、B 各三次，单位为任意单位 au。独立预设的算术结果：A 的数量为 3、总和为 6、均值为 2；B 的数量为 3、总和为 12、均值为 4。它不是实验数据，所有输出的 scientific_accepted 都保持 false。

## 按给定容差比较 A、B

[`compare.py`](compare.py) 将三个固定脚本角色串联起来：解析容差、汇总数据、
用 `Fraction` 独立复核算术。它复用现有生产函数及 canonical runtime/store，
不是三个自治智能体。使用 Python 3.12+，不需要可选依赖；从源码根目录运行，
路径必须位于可信、由调用方控制的本地 Linux/POSIX 文件系统中。

### 一条命令运行合成比较

先在源码目录外创建输出父目录，再指定一个尚不存在的子路径；不要提前创建子目录：

```sh
CMP_PARENT=$(mktemp -d /tmp/opendot-comparison.XXXXXX)
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -B \
  examples/measurement-review/compare.py run --demo \
  --output "$CMP_PARENT/demo" > "$CMP_PARENT/demo-receipt.json"
cat "$CMP_PARENT/demo/summary.txt"
```

预期状态为 `CHECKED`，退出码 **0**。A：数量 3、总和 6、均值 2；
B：数量 3、总和 12、均值 4。精确均值绝对差为 **2/1**；两个容差来源
分别为 `2`、`2.0`，数值一致，`within_tolerance=true`。

JSON 回执输出到 stdout，文字摘要输出到 stderr 并保存为 `summary.txt`。
新输出目录还包含 `report.json` 和 canonical `artifacts/` 对象。
回执提供 `report_sha256`、`input_sha256`、`parameters_sha256`、`profile_sha256`。
报告记录状态、输入及 profile 绑定、各角色结果、比较值及可用产物引用，包括
未验收结果。报告上限为 64 KiB，摘要上限为 8 KiB。失败可以留下产物，不承诺回滚。

### 使用符合格式的本地文件

下面的完整例子仍使用虚构数据，通过显式输入模式运行，不需要从冻结 fixture
中提取字段或修改 fixture：

```sh
cat > "$CMP_PARENT/input.csv" <<'CSV'
condition,replicate,value,unit
A,1,0.1,au
A,2,0.2,au
A,3,0.3,au
B,1,0.2,au
B,2,0.3,au
B,3,0.4,au
CSV
cat > "$CMP_PARENT/parameters.json" <<'JSON'
{
  "task": {"scenario": "bench-A", "unit": "au"},
  "sources": [
    {"source": "tolerance_note", "scenario": "bench-A", "unit": "au", "raw_value": "0.1"}
  ]
}
JSON
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -B \
  examples/measurement-review/compare.py run \
  --input "$CMP_PARENT/input.csv" --parameters "$CMP_PARENT/parameters.json" \
  --output "$CMP_PARENT/custom" > "$CMP_PARENT/custom-receipt.json"
cat "$CMP_PARENT/custom/summary.txt"
```

精确均值为 1/5、3/10，均值绝对差为 **1/10**，等于容差，因此通过。
原汇总函数实际产生的浮点数会被保留，但不会用于容差边界判断。
显式输入始终标记为 `user_supplied_unvalidated`，即使提供的是合成数据。
`--demo` 不能与 `--input` 或 `--parameters` 混用。

- CSV：列名和顺序必须与上例完全一致；恰好六行，A/B 各含重复编号 1/2/3 一次；
  单位仅限 `au`，文件不超过 64 KiB。数值为十进制文本，最长 32 字符，最多
  12 位小数，绝对值不超过 1,000,000；禁止指数、NaN、无穷大。使用 `0.1` 等
  规范写法，不使用 `.1`
- 参数 JSON：不超过 64 KiB；`task` 固定如上，最多八条来源记录。每条包含
  `source`、`scenario`、`unit`、`raw_value`；来源名唯一，由 1–64 个 ASCII
  字母、数字、下划线或连字符组成。容差必须是字符串，整数部分最多六位，除
  `0` 本身外不得有前导零；最多 12 位小数、32 字符。使用 `"0.1"`，不能使用
  `.1`、指数或 JSON 数字。测量值允许 1,000,000，并不扩展既有容差的六位整数语法
- 值或适用条件缺失、为 null、未知，以及冲突、无效证据或负容差，都会阻止后续分析。
  已知零容差有效。明确不适用的来源会被排除，不能提供所需容差
- 数据必须真实地以任意单位 `au` 表示，不能把毫米、秒等物理单位直接改名为 `au`。
  更大数据集、其他分组、单位换算、统计推断及数据采集均不在本 profile 范围内

### 只读验证已有输出

四个预期哈希必须来自单独可信的来源。在这个本地示例中，保存在输出目录旁的
运行回执是保留的预期记录；将输出视为不可信之前，应单独保护这份回执。
若回执和输出被一起修改，就不具备独立可信性。不能仅从待验 `report.json`
获取预期哈希。

在同一个 shell 中，使用可信保留的回执：

```sh
receipt_pin() {
  python -B -c \
    'import json, sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' \
    "$CMP_PARENT/demo-receipt.json" "$1"
}
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -B \
  examples/measurement-review/compare.py verify --output "$CMP_PARENT/demo" \
  --report-sha256 "$(receipt_pin report_sha256)" \
  --input-sha256 "$(receipt_pin input_sha256)" \
  --parameters-sha256 "$(receipt_pin parameters_sha256)" \
  --profile-sha256 "$(receipt_pin profile_sha256)"
```

验证自定义运行时，将上面两处 `demo` 改为 `custom`，分别对应回执文件名和输出子目录。
Profile 绑定当前比较脚本、canonical owners、生产函数源码和冻结 fixture 的哈希。
源码或 fixture 改变后，需要对应的已复核 profile 预期值，不能照抄待验报告自报的哈希。
验证会重新解析捕获的输入和证据，用独立有理数算法复核并检查回执／引用绑定；
所有 CAS 读取有大小上限，并使用 `read_only=True`。它不重跑生产函数，不改写
字节、权限或目录项；普通读取可能更新 atime。

### 理解状态和退出码

| 状态 | 退出码 | 含义 |
| --- | --- | --- |
| `CHECKED` | 0 | 计算复核通过，可以在容差内，也可以超出容差 |
| `BLOCKED` / `REFUSED` | 2 | 证据缺失、冲突或无效，操作被拒绝，或输入／配置不被接受 |
| `FAILED` | 1 | 执行或验证失败 |

对于 demo 数据，容差为 `1.999` 时，`within_tolerance=false`，但正确复核后仍退出 **0**。
拒绝、错误或未决执行都会阻止后续角色分发；每个角色最多尝试一次，没有重试。
已有输出路径会原样保留；应选择新子路径，不要覆盖或删除旧结果。启用 `set -e`
的 shell 遇到非零退出码可能提前结束。

结果只是描述性的计算检查。所有结果保持 `scientific_accepted=false`、
`device_control_authorized=false`、`independent_review=NOT_EVALUATED`。
独立算术实现不等于科学同行评审、仪器校准或因果证据。输入、CAS 对象、回执和
报告默认私密，不自动上传；去掉身份标识也不保证数值数据不敏感。
路径及祖先必须可信且由调用方控制。Canonical CAS 路径仍跟随符号链接；
源码、输入和报告读取复用既有审计辅助函数，会拒绝符号链接。完整范围见
[ADR 006](../../docs/decisions/006-fixed-measurement-composition.md)。

## 原有单角色示例

下方 `demo.py` 操作说明保持不变。其诊断回执、`replay` 命令和退出码约定
与上面的 `compare.py` 不同。

## 从这里开始：三种源码示例

在可信的 Linux/POSIX 源码目录中使用 Python 3.12+，不需要可选软件包。
从仓库根目录，在同一个 shell 中依次执行以下命令。[CSV](batch.csv) 和
[脚本](demo.py) 都是源码文件，**不包含在 wheel 中，也不是安装后的命令**。
安装软件包及隔离导入检查见[安装指南](../../docs/installed-quickstart.zh-CN.md)；
请单独保留匹配的源码示例。

第一段命令在仓库外创建可信输出父目录，每个案例使用一个新的子路径，
并把命令打印的回执保存在对应 bundle 目录旁边：

```sh
PARENT=$(mktemp -d /tmp/opendot-batch.XXXXXX)
cat examples/measurement-review/batch.csv
for CASE in valid wrong-mean denied; do
  PYTHONPATH=src python -B examples/measurement-review/demo.py run \
    --input examples/measurement-review/batch.csv --output "$PARENT/$CASE" \
    --case "$CASE" > "$PARENT/$CASE-receipt.json"
  printf '%s run exit=%s\n' "$CASE" "$?"
  cat "$PARENT/$CASE-receipt.json"
done
```

三个 `run` 命令的退出码均为 **0**，只表示生成了诊断回执，不代表分析获准。
打印的 JSON 字段如下：

| 案例 | `status` | `semantic_valid` | `scientific_accepted` |
| --- | --- | --- | --- |
| `valid` | `COMPLETED` | `true` | `false` |
| `wrong-mean` | `FAILED` | `false` | `false` |
| `denied` | `BLOCKED` | `false` | `false` |

## 找到输入、结果字节和被拒绝的产物

每个 `$PARENT/<case>/bundle.json` 记录 `receipt`、`source_ref`、`result_ref`、
`handler_calls`、`returned_result` 和 `retained_unaccepted_result`。
旁边的 `artifacts/objects/<SHA-256 前两位>/<其余位>` 保存原始 CSV 和 JSON 字节。
以下命令通过现有 canonical store 取回它们：

```sh
PYTHONPATH=src python -B - "$PARENT" <<'PYTHON'
import json
from pathlib import Path
import sys
from opendot_engineering.core import ArtifactRef, ArtifactStore

for case in ("valid", "wrong-mean", "denied"):
    output = Path(sys.argv[1]) / case
    bundle = json.loads((output / "bundle.json").read_bytes())
    print(case, json.dumps({key: bundle[key] for key in
          ("receipt", "handler_calls", "returned_result", "retained_unaccepted_result")}))
    store = ArtifactStore(output / "artifacts", read_only=True)
    for key in ("source_ref", "result_ref"):
        if bundle[key] is not None:
            fields = dict(bundle[key])
            fields["source_refs"] = tuple(fields["source_refs"])
            ref = ArtifactRef(**fields)
            print(key, ref.artifact_id)
            print(store.get_bytes(ref).decode("utf-8"))
PYTHON
```

- `valid`：处理函数调用一次，`returned_result=true`，没有保留未验收结果；取回的统计结果为 A.mean = 2、B.mean = 4
- `wrong-mean`：处理函数调用一次，`returned_result=false`、`retained_unaccepted_result=true`；完整的已存结果故意写入 A.mean = 3，固定 oracle 将其拒绝。字节完整不等于语义验收通过
- `denied`：`PermissionDenied`，处理函数调用次数为零，两个引用均为 `null`，artifact 对象数为零；空目录和诊断 bundle 可以存在

## 在新进程中验证

通过可信渠道保留命令打印的 bundle、input、oracle 三个 SHA-256。
以下命令使用刚才保存的命令回执及固定合成输入／oracle 的预设哈希。
这些本地回执便于可信示例操作，不构成独立身份认证；不能用不可信 bundle
或被一同修改的回执自报的哈希替换可信预期值。

wrong-mean 和 denied 的 replay 命令故意返回非零。如果 shell 启用了
`set -e`，请在未启用该设置的 shell 中运行比较，以显示全部三种结果：

```sh
INPUT_SHA256=12fa76e2cb8defb752ce08a2fdd386b0f943579d1438e3022cb2e345bdcae0d9
ORACLE_SHA256=60508ab267ad62422c8df302876f3a1a92290901900b73175d3f5c8f391430d2
for CASE in valid wrong-mean denied; do
  BUNDLE_SHA256=$(python -B -c \
    'import json, sys; print(json.load(open(sys.argv[1]))["bundle_sha256"])' \
    "$PARENT/$CASE-receipt.json")
  PYTHONPATH=src python -B examples/measurement-review/demo.py replay \
    --output "$PARENT/$CASE" --bundle-sha256 "$BUNDLE_SHA256" \
    --input-sha256 "$INPUT_SHA256" --oracle-sha256 "$ORACLE_SHA256"
  printf '%s replay exit=%s\n' "$CASE" "$?"
done
```

预期：`valid replay exit=0`，并显示 `verification_replay_passed=true`、
`execution_restarted=false`、`scientific_accepted=false`。另两个拒绝案例均打印
`{"accepted": false, "error_type": "ValueError"}`，并显示 `replay exit=1`。
replay 复核已有字节、输入身份、固定预期值、分发状态与返回引用观察；
它**不是**重新执行、任务续跑、签名认证或故障恢复。

## 输出路径已存在时

对已有子路径再次执行 `run`，退出码为 **1**，打印
`{"accepted": false, "error_type": "FileExistsError"}`。保留原结果，改用尚不存在的
子路径（不要先创建该子目录）：

```sh
PYTHONPATH=src python -B examples/measurement-review/demo.py run \
  --input examples/measurement-review/batch.csv --output "$PARENT/valid-2"
```

这会产生一份新的 `COMPLETED` 诊断回执，不是续跑或修复旧任务。
若要重新比较全部案例，可重新执行第一段命令，获得新的父目录。
输入解析失败发生在创建输出之前：重复或缺失的重复编号、错误单位或条件、
无效数字及非有限值都会被拒绝。修改存储字节或可信输入／oracle 哈希后，
不能沿用旧验收。

## 明确限制

仅支持固定的六行合成模式，输入上限 64 KiB，不是通用实验室数据校验器。
路径、根目录及其祖先必须由可信调用方控制；仍会跟随符号链接，不提供恶意文件系统隔离或并发修改防护。
replay 与取回命令显式使用 `ArtifactStore(..., read_only=True)`，包括拒绝路径在内，
不创建文件或目录、不写入字节、不修改权限、不删除条目。普通读取可能更新访问时间（atime），
该时间不在非修改契约内。默认 `read_only=False` 构造仍初始化写入器。

哈希证明字节一致，不证明科学正确、作者身份或完整元数据真实性；CAS 可能保留首次写入者的元数据。权限只在分发时检查，没有操作系统沙箱。风险标签不实现撤销，重试关闭，失败可以留下产物，没有事务或自动回滚。

没有模型、设备、原生求解器、多机、自治智能体或生产消费者迁移。代码、CSV 和测试均为新写的合成 Apache-2.0 项目材料，不包含私密测量数据。完整边界见[执行器](../../docs/callable-execution.md)和[产物存储](../../docs/canonical-artifacts.md)。
