# 复核一批合成重复测量数据

[English](README.md)

这个例子解决一个具体的软件问题：收到数据表和统计结果后，明确它们对应哪个输入版本、是否经过指定检查，以及结果能否按哈希找回。它复用现有 ToolRuntime 和 ArtifactStore，不增加运行时或调度器。

预期用途是减少输入、结果与复核记录之间的手工错配；尚无真实用户研究、节省时间、投资回报或优于其他工具的证据。

## 数据和验收值

batch.csv 是六行完全虚构的数据，A、B 各三次，单位为任意单位 au。独立预设的算术结果：A 的数量为 3、总和为 6、均值为 2；B 的数量为 3、总和为 12、均值为 4。它不是实验数据，所有输出的 scientific_accepted 都保持 false。

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
