# 从 0.3.0a1 预发布版得到第一个结果

[English](installed-quickstart.md) · [仅使用源码的路径](../README.zh-CN.md#运行合成示例)

执行一个受权限检查的 Python callable，保存合成结果，并独立核对存储字节。
第一个示例只需要已发布的 wheel，不需要源码仓库、模型密钥、网络服务、原生求解器或设备。
这是有限的本地软件操作，不是自治智能体运行时。

结构默认返回值已变更，详见[迁移指南](structural-default-v2.md)。本入门教程仍使用行为未变的函数／产物流程。

## 1. 准备独立环境

需要 Python 3.12+（含 `venv` 和 pip 支持）以及可信 POSIX 环境。
先前本地检查使用 Linux 和 CPython 3.12，不代表承诺支持所有平台。
以下命令假设 `/tmp` 适合作为你信任的临时父目录。

从 [0.3.0a1 ALPHA 预发布版](https://github.com/sddvacav/opendot/releases/tag/v0.3.0a1)下载
[opendot_engineering-0.3.0a1-py3-none-any.whl](https://github.com/sddvacav/opendot/releases/download/v0.3.0a1/opendot_engineering-0.3.0a1-py3-none-any.whl)，
保存到可信的本地目录。其精确 SHA-256 固定在下方命令中，也列于发布包的
[SHA256SUMS](https://github.com/sddvacav/opendot/releases/download/v0.3.0a1/SHA256SUMS)。
本文使用 GitHub 发布产物，不声明已发布到 PyPI。不要替换为名字相似的软件包，
或先前具有相同版本号的构建。摘要一致仅核对文件字节，不能证明作者身份、安全性或科学有效性。

[发布说明](https://github.com/sddvacav/opendot/releases/download/v0.3.0a1/RELEASE-NOTES.md)将这些产物绑定至公开提交
[49891de448f0bf80c47c035aab4742e1d32221d9](https://github.com/sddvacav/opendot/commit/49891de448f0bf80c47c035aab4742e1d32221d9)。
[0.3.0a1 发布前验证记录](structural-v2-candidate-verification.md)保留源码、离线构建、安装检查
和教程实测的独立范围；先前版本的结果不批准本 wheel。
[文档检查](documentation-checks.md)仅比较下方八个 shell 代码块，不执行这些命令。

只将 `WHEEL` 替换为已下载 wheel 的绝对路径。若 Python 3.12+ 的可执行文件
名称不同，也请修改 `PYTHON`。保留固定 SHA-256 不变。所有代码块在同一个 shell
会话运行。安装使用新环境，不下载任何依赖。

```sh
set -eu
PYTHON=python3.12
WHEEL='/absolute/path/to/opendot_engineering-0.3.0a1-py3-none-any.whl'
EXPECTED_WHEEL_SHA256='53ba4398939dce8d037be21656bfadf6686abdd9bcc1134d85efa44a9b5c1207'

"$PYTHON" -I -B - "$WHEEL" "$EXPECTED_WHEEL_SHA256" <<'PYCODE'
import hashlib, pathlib, sys
if sys.version_info < (3, 12):
    raise SystemExit("Python 3.12 or newer is required")
wheel, expected = pathlib.Path(sys.argv[1]), sys.argv[2]
if hashlib.sha256(wheel.read_bytes()).hexdigest() != expected:
    raise SystemExit("Wheel hash mismatch: stop and check the reviewed artifact")
print("Released wheel bytes match")
PYCODE

JOURNEY=$(mktemp -d /tmp/opendot-first-run.XXXXXX)
"$PYTHON" -I -B -m venv "$JOURNEY/venv"
PY="$JOURNEY/venv/bin/python"
"$PY" -I -B -m pip install --no-index --no-deps --no-compile --no-cache-dir "$WHEEL"
cd "$JOURNEY"
"$PY" -I -B -c 'import importlib.metadata as m, opendot_engineering as p; print(m.version("opendot-engineering")); print(p.__file__)'
```

应看到版本 `0.3.0a1` 和位于新环境 `site-packages` 内的导入路径。
无需激活环境或设置 `PYTHONPATH`；`-I` 忽略源码目录导入捷径，`-B` 避免写入 Python
字节码。软件包没有名为 `opendot` 的独立控制台命令。

### 查看软件包帮助与版本

使用同一个已安装解释器；不需要复制示例：

```sh
"$PY" -I -B -m opendot_engineering --help
"$PY" -I -B -m opendot_engineering --version
```

帮助列出 API 路径和单独调用的模块入口。版本命令输出 `opendot-engineering`，
后接实际导入的软件包代码版本。这些命令不启动运行时、不分发工具，也不加载可选后端；
没有注册 `opendot` 或 `odot` 独立控制台命令。详见[软件包帮助与参数行为](module-cli.md)。

## 2. 创建并检查第一个结果

下列代码完整自包含。它在新建的可信父目录下创建输出目录；该目录及其祖先目录必须
由你控制并信任。

```sh
OUTPUT_PARENT=$(mktemp -d /tmp/opendot-result.XXXXXX)
"$PY" -I -B - "$OUTPUT_PARENT/result" <<'PYCODE'
import hashlib, json, sys
from pathlib import Path
from opendot_engineering.core import ArtifactRef, ArtifactStore
from opendot_engineering.tool_runtime import ToolRisk, ToolRuntime, ToolSpec

output = Path(sys.argv[1])
output.mkdir(exist_ok=False)
store = ArtifactStore(output / "cas")
runtime = ToolRuntime()
runtime.register(
    ToolSpec(
        "write-result", "1", "text/v1", "artifact-ref/v1",
        ToolRisk.REVERSIBLE_WRITE, timeout_s=5.0, max_retries=0,
        idempotent=False, permissions=frozenset({"artifact:write"}),
        semantic_validator=lambda ref: isinstance(ref, ArtifactRef),
    ),
    lambda payload: store.put_text(payload["text"], producer="first-run"),
)
ref, receipt = runtime.execute(
    "write-result", {"text": "OpenDot synthetic result\n"},
    granted_permissions=frozenset({"artifact:write"}),
)
assert receipt.status == "COMPLETED" and receipt.semantic_valid
assert ref is not None
stored_bytes = store.get_bytes(ref)
hash_matches = hashlib.sha256(stored_bytes).hexdigest() == ref.sha256
assert hash_matches
print(json.dumps({
    "status": receipt.status,
    "semantic_valid": receipt.semantic_valid,
    "artifact_id": ref.artifact_id,
    "independent_sha256_matches": hash_matches,
    "output_directory": str(output),
    "scientific_accepted": False,
}, indent=2))
PYCODE
```

成功时退出码为零，输出 `status: "COMPLETED"`、`semantic_valid: true`、以
`sha256:` 开头的 `artifact_id` 和 `independent_sha256_matches: true`。
`output_directory` 指向可检查的本地 CAS 目录；`scientific_accepted` 保持 `false`。

此处语义检查器仅检查返回引用的类型，不验证科学结论。权限检查发生在分发时，并非
操作系统沙箱。`REVERSIBLE_WRITE` 标签不实现撤销；CAS 信任存储根目录、跟随符号
链接，也不是事务或恢复系统。

## 3. 观察成功、语义拒绝与缺少权限

wheel 包含 Python 包，但不包含示例脚本和夹具。从同一版本下载配套的
[完整源码归档](https://github.com/sddvacav/opendot/releases/download/v0.3.0a1/opendot-engineering-0.3.0a1-source.tar.gz)，
将 `SOURCE_ARCHIVE` 替换为其绝对本地路径。请使用这个具名产物，而非范围更窄的打包
sdist 或 GitHub 自动生成的源码链接；它们的字节不同。保留固定源码 SHA-256 不变。
代码块先验证归档，再解压到全新的教程目录中，然后仅复制公开示例。
Python 仍从已安装 wheel 导入。

```sh
SOURCE_ARCHIVE='/absolute/path/to/opendot-engineering-0.3.0a1-source.tar.gz'
EXPECTED_SOURCE_SHA256='bd7dfa520e1a176b48bf4cebaafbddb02dfb90aad5c7be759595ed13d3c7a73c'
"$PY" -I -B - "$SOURCE_ARCHIVE" "$EXPECTED_SOURCE_SHA256" "$JOURNEY/source" <<'PYCODE'
import hashlib, pathlib, sys, tarfile
archive, expected = pathlib.Path(sys.argv[1]), sys.argv[2]
if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
    raise SystemExit("Source archive hash mismatch: stop and check the released asset")
output = pathlib.Path(sys.argv[3])
output.mkdir(exist_ok=False)
with tarfile.open(archive, "r:gz") as source:
    source.extractall(output, filter="data")
print("Released source archive bytes match")
PYCODE
SOURCE="$JOURNEY/source/opendot-engineering-0.3.0a1"
cp -R "$SOURCE/examples" "$JOURNEY/examples"
"$PY" -I -B "$JOURNEY/examples/callable-artifacts/demo.py" \
  --output "$OUTPUT_PARENT/three-cases"
```

应看到 `synthetic_software_assertions_passed: true` 和 `package_version:
"0.3.0a1"`。三个场景的结果有意不同：

- `success`：`COMPLETED`、语义有效、字节通过独立哈希核对
- `semantic_refusal`：`FAILED`，仍保留一个完整但**未获接受**的产物
- `permission_refusal`：`BLOCKED/PermissionDenied`，零 handler 调用、零存储对象

上述拒绝是预期的检查结果；验证失败不回滚副作用。缺少权限的场景中，存储构造函数
仍会创建空目录。

## 4. 检查随附的只读夹具

继续使用已复制的示例和下列固定值：

```sh
"$PY" -I -B -m opendot_engineering.adapters.source_audit \
  --root "$JOURNEY/examples/source-audit" --manifest manifest.json \
  --expected-revision aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
  --expected-manifest-sha256 f4d81f12c83b7f222931348677b01b6f27df8905513cfbaebac3cf86cbfe26ae \
  --audience public

"$PY" -I -B -m opendot_engineering.adapters.lab_qualification \
  --root "$JOURNEY/examples/lab-qualification" \
  --expected-revision bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb \
  --expected-manifest-sha256 1dcde9c63280f4f99e6c2ea9e3ca6d392399e4d0792a4a9e4f81d581d2ce817f
```

来源审计输出 `audit_accepted: true` 和 `scientific_accepted: false`。
资格检查输出 `benchmark_contract_passed: true`，科学接受、设备控制授权和实体
设备资格保持 false；夹具中包含预期拒绝场景。这两条命令不会自行创建结果文件；
如需用 shell 重定向 stdout，请将文件保存在源码仓库外。

重复的 `a` 和 `b` 是合成修订标识符。处理其他输入时，应独立取得预期修订和摘要；
不要为了使不熟悉的输入通过而直接修改预期哈希。

## 5. 其他轻量示例

[智能体契约示例](../examples/agent-contracts/README.md)描述 `Capability` 与
`AgentManifest` 元数据，并显式调用 `.validate()`。预算与权限仅作描述，不新增执行
强制机制，也未迁移既有使用方。详见 [API 边界](agent-contracts.md)。

```sh
"$PY" -I -B "$JOURNEY/examples/callable-execution/demo.py"
"$PY" -I -B "$JOURNEY/examples/canonical-artifacts/roundtrip.py" \
  --output "$OUTPUT_PARENT/artifact-roundtrip"
```

callable 示例检查五种场景，成功输出为 `5`，显式重试输出为 `8`。
产物示例输出 `passed: true`，并有意保留一个已损坏的合成对象以演示拒绝行为。

只有可选 Git 示例需要可信系统 Git >= 2.52.0。它使用固定搜索路径
`/usr/local/bin:/usr/bin:/bin`；仅在普通 `PATH` 的其他位置安装新版 Git 不够。
运行前先检查固定路径：

```sh
PATH=/usr/local/bin:/usr/bin:/bin git --version
"$PY" -I -B "$JOURNEY/examples/git-workspaces/demo.py"
```

`receipt_ok`、`shared_fixed_base`、`second_is_clean` 和
`primary_checkout_unchanged` 应为 true。示例自行创建临时仓库，并在退出时移除自己
创建的临时容器，不需要使用你的现有仓库。在其他仓库使用 API 前，请阅读
[Git 适用边界](git-workspaces.md)。Git 环境不满足条件不会阻止步骤 1–4。

## 常见首次运行错误

- `No module named opendot_engineering`：使用上面创建的准确 `$PY` 解释器并检查
  导入路径；不要用添加源码导入路径的方式代替安装包验证
- `ROOT_UNAVAILABLE`（退出码 2）：先复制配套示例，再使用绝对路径
  `$JOURNEY/examples/source-audit`；wheel 本身不含夹具
- `MANIFEST_HASH_MISMATCH` 或 `REVISION_OR_SCHEMA_MISMATCH`（退出码 2）：停止操作，
  确认夹具与独立复核的固定值配套
- `--output already exists`（退出码 2）：`callable-artifacts/demo.py` 和
  `canonical-artifacts/roundtrip.py` 脚本 CLI 在调用演示函数前，若发现已有文件、
  目录或符号链接（包括悬空链接），会在 stderr 报错并保留该输出不变；按下方选择新路径
- `FileExistsError`：步骤 2 的内联 Python 代码及直接 `demonstrate()` 调用保留
  原有异常行为。脚本 CLI 的非原子预检查之后发生的路径冲突，也可能抛出原始错误。
  保留之前的结果并选择新路径；预检查不增加重试或清理
- 输出路径出现 `FileNotFoundError`：父目录必须先存在；使用 `mktemp -d`，不要
  直接指定尚不存在的多级路径
- 缺少 `venv` 或 pip：按 Python 发行方支持的方式准备环境，再重新开始安装；
  本文不会安装系统软件
- POSIX 操作或 Git 版本不受支持：换用符合条件并已复核的环境，不要削弱安全检查。
  原生后端指南与此无依赖路径分开

不删除旧证据，重新运行三个场景：

```sh
OUTPUT_PARENT=$(mktemp -d /tmp/opendot-result.XXXXXX)
"$PY" -I -B "$JOURNEY/examples/callable-artifacts/demo.py" \
  --output "$OUTPUT_PARENT/three-cases"
```

检查前不要公开分享本地输出：错误可能含本地路径，其他回执也可能含输入内容。
另见[支持说明](../SUPPORT.md)、[callable 边界](callable-execution.md)和
[存储边界](canonical-artifacts.md)。本地教程成功不代表托管 CI、公开下载验证、
科学复核或发布验收通过。
