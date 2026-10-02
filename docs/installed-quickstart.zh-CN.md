# 从精确 0.3.0a5 候选得到第一个结果

[English](installed-quickstart.md) · [仅源码路径](../README.zh-CN.md#运行合成示例)

执行受权限检查的 Python callable，保存合成结果并独立核验存储字节。
首个结果仅需 wheel 和 Python 3.12+，不需要模型密钥、服务、原生求解器或设备。
状态为 ALPHA / NOT_SCORED。

## 1. 先建立外部信任输入，再离线安装

此捆绑指南在发布前冻结，只标明 a5 发布目标，不证明已经发布或验证公开下载。
需要可信 POSIX 环境、Python 3.12+（含 venv/pip）和可信 `/tmp` 父目录。
Linux/CPython 3.12 是本地参考环境，不是完整支持矩阵。

从已确认的 `sddvacav/opendot` 发布者取得[v0.3.0a5 发布页](https://github.com/sddvacav/opendot/releases/tag/v0.3.0a5)
的以下五个匹配文件（发布后），或使用经过单独复核的本地候选包：

- `opendot_engineering-0.3.0a5-py3-none-any.whl`
- `opendot_engineering-0.3.0a5.tar.gz`
- `opendot-engineering-0.3.0a5-source.tar.gz`
- `RELEASE-NOTES.md`
- `SHA256SUMS`

运行前，独立复核公开发布正文的来源前缀（或已接受的复核／发布凭据）。
核对仓库、标签 `v0.3.0a5`、已接受源码提交及源码树与复核记录一致。
从单独复核的前缀／凭据取得最终 SHA256SUMS 的 SHA-256，并将 shell 变量
`EXPECTED_SUMS_SHA256` 设为该精确的 64 位小写十六进制值。
发布正文提供提交／树链接和外部摘要，不需要访问私聊。没有独立接受的固定值就停止。
**绝不能从刚下载的 SHA256SUMS 自行计算“预期”摘要。**

此过程要求信任所确认的 GitHub 发布者。文件名、下载地址或 TLS 成功本身不构成认证。
不假设存在签名、证明或密码学发布者身份保证。哈希只说明相对于可信输入的字节一致性，
不证明作者身份、安全性或科学有效性。不要修改预期值来让陌生字节通过。

[发布说明](https://github.com/sddvacav/opendot/releases/download/v0.3.0a5/RELEASE-NOTES.md)
记录精确归档标识与完整双语操作步骤。
[SHA256SUMS](https://github.com/sddvacav/opendot/releases/download/v0.3.0a5/SHA256SUMS)
恰好包含三个归档和说明的摘要，不包含自身。清单摘要保留在这些文件之外，避免自哈希循环。
sdist 仅为构建输入，区别于完整源码归档；本指南不安装 sdist 或额外依赖。
不要使用 GitHub 自动生成的归档或 a3／a4 文件。

仅替换 `RELEASE_DIR` 为包含五个已复核文件的绝对目录，必要时替换 `PYTHON`。
按上述要求提供外部 `EXPECTED_SUMS_SHA256`，保持文件名与校验逻辑不变。
在同一个 shell 中运行。未设置／无效固定值，以及不匹配、重复、多余或缺失条目，
都会在创建环境、运行 pip 或提取源码之前停止。

```sh
set -eu
PYTHON=python3.12
RELEASE_DIR='/absolute/path/to/reviewed-a5-files'
EXPECTED_SUMS_SHA256=${EXPECTED_SUMS_SHA256-}
WHEEL="$RELEASE_DIR/opendot_engineering-0.3.0a5-py3-none-any.whl"
EXPECTED_SOURCE_SHA256=$("$PYTHON" -I -B - "$RELEASE_DIR" "$EXPECTED_SUMS_SHA256" <<'PYCODE'
import hashlib, pathlib, re, sys
if sys.version_info < (3, 12):
    raise SystemExit("Python 3.12 or newer is required")
root, expected = pathlib.Path(sys.argv[1]), sys.argv[2]
if not re.fullmatch(r"[0-9a-f]{64}", expected):
    raise SystemExit("Supply an independently reviewed external SHA256SUMS SHA-256")
names = {
    "opendot_engineering-0.3.0a5-py3-none-any.whl",
    "opendot_engineering-0.3.0a5.tar.gz",
    "opendot-engineering-0.3.0a5-source.tar.gz",
    "RELEASE-NOTES.md",
}
manifest = root / "SHA256SUMS"
if manifest.is_symlink() or not manifest.is_file():
    raise SystemExit("SHA256SUMS must be a regular local file")
raw = manifest.read_bytes()
if hashlib.sha256(raw).hexdigest() != expected:
    raise SystemExit("SHA256SUMS hash mismatch: stop")
try:
    text = raw.decode("ascii")
except UnicodeDecodeError:
    raise SystemExit("Checksum manifest must be ASCII") from None
entries = {}
for line in text.splitlines():
    match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_.-]+)", line)
    if match is None or match[2] not in names or match[2] in entries:
        raise SystemExit("Invalid, duplicate or unexpected checksum entry")
    entries[match[2]] = match[1]
if set(entries) != names or not text.endswith("\n") or "\r" in text:
    raise SystemExit("Checksum manifest must contain exactly four canonical entries")
for name, digest in entries.items():
    path = root / name
    if path.is_symlink() or not path.is_file():
        raise SystemExit("Payload must be a regular local file: " + name)
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise SystemExit("Payload hash mismatch: " + name)
print(entries["opendot-engineering-0.3.0a5-source.tar.gz"])
PYCODE
)
printf 'Externally pinned manifest and all four payloads match\n'
JOURNEY=$(mktemp -d /tmp/opendot-first-run.XXXXXX)
"$PYTHON" -I -B -m venv "$JOURNEY/venv"
PY="$JOURNEY/venv/bin/python"
"$PY" -I -B -m pip --isolated install --disable-pip-version-check \
  --no-index --no-deps --no-compile --no-cache-dir "$WHEEL"
cd "$JOURNEY"
"$PY" -I -B -c 'import importlib.metadata as m, pathlib, sys, opendot_engineering as p; assert p.__version__ == m.version("opendot-engineering") == "0.3.0a5"; assert pathlib.Path(p.__file__).is_relative_to(pathlib.Path(sys.prefix) / "lib"); print(p.__version__); print(p.__file__)'
```

预期版本为 `0.3.0a5`，导入路径位于新环境的 site-packages。
`-I` 忽略源码目录导入捷径，`-B` 避免字节码写入；无需激活环境或设置 PYTHONPATH。
没有注册 opendot 控制台命令。

### 查看软件包帮助与版本

```sh
"$PY" -I -B -m opendot_engineering --help
"$PY" -I -B -m opendot_engineering --version
```

帮助包含精确版本的首个结果／发布说明链接和静态 API 指引，不访问网络、读取用户文件、
导入可选后端或分派工具。显示链接不证明已发布。参见[选项行为](module-cli.md)。

## 2. 创建并检查首个结果

在可信父目录下使用新输出路径，并控制所有祖先目录。

```sh
OUTPUT_PARENT=$(mktemp -d /tmp/opendot-result.XXXXXX)
"$PY" -I -B - "$OUTPUT_PARENT/result" <<'PYCODE'
import hashlib, json, sys
from pathlib import Path
from opendot_engineering.core import ArtifactIntegrityError, ArtifactRef, ArtifactStore
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
stored_bytes = store.get_bytes(ref, max_bytes=256)
try:
    store.get_bytes(ref, max_bytes=len(stored_bytes) - 1)
except ArtifactIntegrityError as error:
    assert str(error) == "artifact exceeds max_bytes"
else:
    raise AssertionError("Oversize input should have been refused")
hash_matches = hashlib.sha256(stored_bytes).hexdigest() == ref.sha256
assert hash_matches
print(json.dumps({
    "status": receipt.status,
    "semantic_valid": receipt.semantic_valid,
    "artifact_id": ref.artifact_id,
    "independent_sha256_matches": hash_matches,
    "bounded_read_and_refusal_passed": True,
    "output_directory": str(output),
    "scientific_accepted": False,
}, indent=2))
PYCODE
```

预期 COMPLETED、semantic_valid 为 true、artifact_id 以 sha256: 开头，
independent_sha256_matches 与 bounded_read_and_refusal_passed 为 true。
scientific_accepted 仍为 false。语义检查仅验证引用类型；权限是分派检查而非 OS 沙箱。
写入标签不实现撤销；可信根 CAS 跟随符号链接，不是事务。
对于可信普通对象，max_bytes=N 至多取得 N+1 个实际字节以检测超限；省略／None 仍完整读取。
不承诺恒定内存、时间、恶意文件系统或执行级限制。见[有界读取](canonical-artifacts.md#optional-bounded-retrieval-unreleased-source-increment)。

## 3. 检查成功、语义拒绝与缺少权限

wheel 不包含示例。使用外部固定清单中取得的源码摘要再次核对归档，
只提取规范普通成员，再复制公开示例。这些轻量示例仍从安装 wheel 导入。

```sh
SOURCE_ARCHIVE="$RELEASE_DIR/opendot-engineering-0.3.0a5-source.tar.gz"
"$PY" -I -B - "$SOURCE_ARCHIVE" "$EXPECTED_SOURCE_SHA256" "$JOURNEY/source" <<'PYCODE'
import hashlib, pathlib, sys, tarfile
archive, expected = pathlib.Path(sys.argv[1]), sys.argv[2]
if archive.is_symlink() or hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
    raise SystemExit("Source archive hash mismatch: stop")
output = pathlib.Path(sys.argv[3])
with tarfile.open(archive, "r:gz") as source:
    seen = set()
    for member in source.getmembers():
        path = pathlib.PurePosixPath(member.name)
        if (not member.isfile() or member.name in seen
                or path.as_posix() != member.name or path.is_absolute()
                or ".." in path.parts or len(path.parts) < 2
                or path.parts[0] != "opendot-engineering-0.3.0a5"
                or member.mode not in (0o644, 0o755)):
            raise SystemExit("Noncanonical source member: stop")
        seen.add(member.name)
    output.mkdir(exist_ok=False)
    source.extractall(output, filter="data")
print("Pinned source archive bytes and member paths match")
PYCODE
SOURCE="$JOURNEY/source/opendot-engineering-0.3.0a5"
cp -R "$SOURCE/examples" "$JOURNEY/examples"
"$PY" -I -B "$JOURNEY/examples/callable-artifacts/demo.py" \
  --output "$OUTPUT_PARENT/three-cases"
```

预期 synthetic_software_assertions_passed 为 true，package_version 为 0.3.0a5。
成功案例为 COMPLETED 并独立核验字节；语义拒绝为 FAILED，保留一个完整但未接受的产物；
权限拒绝为 BLOCKED/PermissionDenied，处理器调用和存储对象数为零。
存储构造仍创建空目录，失败不回滚副作用。

## 4. 检查只读 fixture

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

预期 audit_accepted 为 true、scientific_accepted 为 false；随后 benchmark_contract_passed
为 true，科学／设备／真实设备权限为 false。a/b revision 与摘要是固定合成 fixture。
其他输入须独立取得固定值。除 shell 重定向外，这两个命令不写入凭据。

## 5. 其他轻量示例

```sh
"$PY" -I -B "$JOURNEY/examples/callable-execution/demo.py"
"$PY" -I -B "$JOURNEY/examples/canonical-artifacts/roundtrip.py" \
  --output "$OUTPUT_PARENT/artifact-roundtrip"
```

函数示例检查五个场景（成功 5，显式重试 8）；产物示例输出 passed: true 并保留故意损坏的合成对象。
[智能体契约](../examples/agent-contracts/README.md)仅为描述性元数据，不实现强制执行。
下面可选 Git 示例另行限制，本候选操作验证中为 **NOT_RUN**。
它需要固定路径中的可信系统 Git >= 2.52.0 和[Git 前提条件](git-workspaces.md)。

```sh
PATH=/usr/local/bin:/usr/bin:/bin git --version
"$PY" -I -B "$JOURNEY/examples/git-workspaces/demo.py"
```

单独授权且环境合格的运行应检查 receipt_ok、shared_fixed_base、second_is_clean 与
primary_checkout_unchanged 均为 true。它使用自己的临时仓库，其余七个代码块不构成 Git 验收。

## 匹配源码工作流与可选功能分别处理

完整归档包含[测量比较](../examples/measurement-review/README.zh-CN.md)。
按该文档从匹配源码根使用 `PYTHONPATH=src` 执行 demo/replay，规范所有者须确实从同一树导入。
复制 compare.py 并仅使用安装 wheel 不是此流程。合成均值为 2 与 4，差为 2/1，容差为 2/2.0；
CHECKED 只表示计算一致性，不代表科学有效性。

[CAD／热传导 plan](../examples/cad_cae/README.zh-CN.md)仅检查元数据，结果 NOT_EXECUTED，
原生版本 NOT_CHECKED。人工 fixture 不是真实原生证据。CAD／Gmsh／CalculiX 执行为 NOT_RUN；
物理验证 NOT_PERFORMED、独立审查 NOT_EVALUATED、网格无关性 NOT_ESTABLISHED。

完整源码中的[公开 STEP 参考](../examples/cad_cae/native-geometry-reference/README.md)
保留历史 a4 来源与标准库字节核验命令，不是可重放的原生证据包。
仅源码的[离线效用报告](../examples/measurement-review/README.zh-CN.md#离线增量效用夹具报告)
提供无额外依赖的 `history` 与 `profile` 命令；有限合成控制不证明真实收益。
真实 O3 仍为 PROPOSED / NOT_RUN，测量投入 UNKNOWN。这些示例、研究固定值与 STEP
不包含在 wheel 或构建用 sdist 中；请使用匹配的完整源码。

可选 [A2A worker turn](a2a-worker-turn.md)至多调用一次外部提供的回调，返回 UNACCEPTED 候选。
离线 fixture 不提供真实传输／提供方／模型执行结果；外部 live gate 为 NOT_RUN。
a5 wheel 包含显式导入的 [HTTPS 模块](a2a-http-transport.md)，仅经过有限 mock 检查；
打包不授权真实请求，也不证明真实互操作。默认导入与依赖不变。
[Temporal 批次工具](temporal-batch-qualification.md)仅为源码验证工具，不是生产 wheel API。
历史托管运行保持各自精确范围，不构成本候选验收；此处不执行新的服务／原生运行。
默认依赖仍为空，Temporal SDK 与模拟 extras 需要单独准备，安装不自动启动服务。
[a3 组件清单](release-inventory/v0.3.0a3/README.md)仅适用于 a3，不是 a5 SBOM。
科学与设备权限保持 false。

## 保留证据并处理错误

- 导入失败：使用精确的安装 `$PY`；不要通过添加源码路径让安装检查通过
- 清单／revision 不匹配：停止并检查匹配字节与独立复核的固定值
- 输出已存在：脚本 CLI 预检拒绝文件、目录和符号链接（包括悬空链接），保持原输出；内联 Python／直接调用保留 FileExistsError 行为，非原子预检后的竞争也可能报错
- 父目录缺失：使用可信 mktemp -d 父目录，保留旧结果并选择新子路径；没有重试、清理或回滚
- 缺少 venv/pip 或 POSIX/Git 不合格：使用单独准备的合格主机，不削弱检查

用新输出路径重跑三案例示例：

```sh
OUTPUT_PARENT=$(mktemp -d /tmp/opendot-result.XXXXXX)
"$PY" -I -B "$JOURNEY/examples/callable-artifacts/demo.py" \
  --output "$OUTPUT_PARENT/three-cases"
```

生成输出在复核前保持私密，错误与凭据可能含本地路径或输入。
参见[支持](../SUPPORT.md)、[函数边界](callable-execution.md)和[存储边界](canonical-artifacts.md)。
本地操作不是托管 CI、公开下载验证、独立发行验收或科学审查。

[历史 a4 指南](https://github.com/sddvacav/opendot/blob/2d16190a8121410bbeea252869b196f7891e1696/docs/installed-quickstart.zh-CN.md)与已发布 a4 产物保持不变，其操作记录不构成 a5 验收。

[历史 a3 修正版指南](https://github.com/sddvacav/opendot/blob/8d5d8667d65734fb5c40fa0526709a3159b7f165/docs/installed-quickstart.zh-CN.md)
与不可变产物保留各自固定值，a3 捆绑指南仍含 a2 文字；不要将历史步骤当作 a5 验收。
[文档检查](documentation-checks.md)只比较双语八个逐字一致的 shell 代码块，不执行它们。
