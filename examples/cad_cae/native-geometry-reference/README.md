# Native geometry reference: public synthetic beam

[English](#english) · [中文](#中文) · [Parent workflow](../README.md)

## English

This **PUBLIC_PROJECTION** contains one unchanged [STEP file](beam.step), a new
allowlisted [evidence summary](evidence.json), and this README. It is a static
public synthetic reference, not a rewritten canonical native pack or an
independently replayable execution receipt. No private environment records, raw
receipts or logs are distributed here.

The beam is 200 × 20 × 3 mm (input 0.2 × 0.02 × 0.003 m), origin aligned, with
volume 12,000 mm³ = 0.000012 m³. The producer performed one native export and
same-kernel reimport. A separately implemented reviewer performed one additional
read-only import, without adapter measurement/verifier helpers. Both observed
one valid solid, six faces, twelve edges and eight vertices, with bounds
[0, 0, 0] to [200, 20, 3] mm. The review used the **same Open CASCADE stack**;
it is not independent-kernel validation.

Recorded metadata: Python 3.12.14, build123d 0.10.0, cadquery-ocp 7.8.1.1.post1,
NumPy 2.3.5 and VTK 9.3.1. These selected distribution versions are not a complete
dependency/SBOM or native-binary identity record. The fixed STEP timestamp
`2000-01-01T00:00:00` is normalized metadata, not the execution time.

### Public source association

The [public geometry adapter](../../../src/opendot_engineering/executors/geometry.py)
is 21,462 bytes, SHA-256
`96e3626b68b86c21547cb930bba1591de7270f9bcffc3cdadfa0a9b9ac7a5edb`.
The separately verified [a4 release commit](https://github.com/sddvacav/opendot/commit/2d16190a8121410bbeea252869b196f7891e1696)
is `2d16190a8121410bbeea252869b196f7891e1696`, tree
`c6c2b015fc1e016b1dea2fb09990e53dc2af4996`.
This association comes from release provenance and a complete exported-source
comparison, separately from the native receipt. The native source directory was
an exported snapshot, not a Git checkout: its receipt's commit, dirty and worktree
fields remain null, with `GIT_UNAVAILABLE_SOURCE_HASH_RECORDED`.

### Read-only byte check with standard Python

Run from the repository root. This command reads only local public files, uses
the Python standard library, and makes no network request, CAD import/export,
installation or file write. It checks the fixed STEP and adapter byte identities
and their public JSON declarations. It does **not** validate geometry or prove
the historical native execution.

```sh
python -I -S -B - <<'PY'
import hashlib
import json
from pathlib import Path

root = Path("examples/cad_cae/native-geometry-reference")
evidence = json.loads((root / "evidence.json").read_text(encoding="utf-8"))
checks = (
    (root / "beam.step", 15366,
     "6a58ae02b21d6f3c70505398c86193f7f3de4d4bbd20c36267400eeb08fa2ec9",
     evidence["artifact"]),
    (Path("src/opendot_engineering/executors/geometry.py"), 21462,
     "96e3626b68b86c21547cb930bba1591de7270f9bcffc3cdadfa0a9b9ac7a5edb",
     evidence["source"]),
)
for path, size, expected, record in checks:
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if (len(data) != size or digest != expected
            or record["bytes"] != size or record["sha256"] != expected):
        raise SystemExit("Byte identity mismatch: " + str(path))
    print(str(path), len(data), digest)
print("PUBLIC_REFERENCE_BYTE_CHECK_PASS (not a geometry or execution check)")
PY
```

The supplied STEP is exactly 15,366 bytes, SHA-256
`6a58ae02b21d6f3c70505398c86193f7f3de4d4bbd20c36267400eeb08fa2ec9`.
Readers can recompute these STEP/source byte checks and inspect the STEP's
explicit millimeter declaration. A separately chosen CAD reader can inspect
geometry, but that cannot authenticate or replay the original run. The summarized
historical observations and package versions are not independently established
by this byte check. Hashes provide consistency, not authorship or authorization.

The existing canonical geometry full-pack verifier requires the original pack's
manifest, parameters, environment and receipt. It **does not consume this
three-file public projection**. This reference adds no alternate full-pack
verifier or acceptance owner.

### Limits and attribution

- No repeated-export determinism or cross-version byte-stability result
- No CadQuery compatibility run, independent kernel, mesh, thermal/structural
  solve, refinement or qualification of the full CAD → mesh → thermal workflow
- No physical, scientific, manufacturing, safety or device-control acceptance
- Exchange tolerances in the summary are not manufacturing tolerances
- No hard execution resource bound, native-lifetime or cleanup guarantee
- No native verification command is run or required by the portable byte check

The STEP's existing Open CASCADE/build123d metadata and generic attribution are
preserved byte for byte. See the project's [Apache-2.0 license](../../../LICENSE)
and [NOTICE](../../../NOTICE); separately installed backends retain their own
licenses. No native libraries, executables or dependency wheels are included.

## 中文

这是新的公开合成示例摘要（PUBLIC_PROJECTION），包含原样 STEP、白名单字段的
evidence.json 和本说明，不是重写后的原始执行包。梁尺寸为 200 × 20 × 3 mm，
体积 12,000 mm³；历史上完成了一次原生导出及回读，另一次独立实现的只读复核
确认了 1 个有效实体、6 个面、12 条边和 8 个顶点。两次检查使用相同的
Open CASCADE 软件栈，不代表独立内核验证。

上面的标准 Python 命令只读本地公开文件，不联网、不调用 CAD、不安装软件、
不写文件。它可重算 STEP 和公开源码的大小及哈希，但不能证明历史原生执行、
软件版本或几何有效性。a4 发布提交与源码树的对应关系是单独核实的；原始回执的
Git 字段仍为空。STEP 中的 2000 年时间是规范化元数据，不是运行时间。

未测试重复导出的字节确定性，也未进行独立内核、网格、热学或结构求解，以及
物理、科学、制造或安全验收；完整 CAD → 网格 → 热学流程仍未由本示例获得验证。
原有完整包校验器不适用于这三个文件。保留 STEP 归属信息和项目许可，未包含
原生二进制、私密环境信息或原始日志。
