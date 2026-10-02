# Choose your first OpenDot result

For a first installation, use the **[0.3.0a5 installed quickstart](installed-quickstart.md)**
or **[中文安装入门](installed-quickstart.zh-CN.md)**. Steps 1–2 install the pinned wheel
and produce one inspectable result. The complete five-file bundle is verified first;
source extraction and optional dependencies are not needed for that first result.

You will run one permitted callable, store its output, and see `COMPLETED`,
`semantic_valid: true` and `independent_sha256_matches: true`. The guide identifies
the output directory and explains why `scientific_accepted` stays `false`.
The default package needs no model key, server or native solver.

## Choose the next step

- **Already have a source checkout?** Run the [callable/artifact example](../README.md#run-the-synthetic-examples)
  to inspect success, semantic refusal and missing permission
- **Want a concrete data workflow?** Follow the [synthetic CSV measurement review](../examples/measurement-review/README.md)
  for input/result provenance, retained rejected output and independent byte checks
- **Want read-only fixture checks?** Continue below with the two source-audit and
  qualification commands

## Current experimental release · 0.3.0a5

**ALPHA / NOT_SCORED; [published prerelease](https://github.com/sddvacav/opendot/releases/tag/v0.3.0a5).**
Use the [a5 installed guide](../docs/installed-quickstart.md) only with its matching
reviewed five-file bundle and independently accepted external SHA256SUMS digest.
Exact source, installed and guide qualification require separate external receipts;
no a4 acceptance transfers to a5.

- Wheel: callable/artifact APIs, bounded reads, read-only help and the optional
  explicit-import [HTTPS exchange](../docs/a2a-http-transport.md); default runtime
  dependencies remain empty. Examples and documentation are not installed files
- Sdist: wheel-rebuild input, not the complete runnable examples or test tree
- Full source: [measurement comparison](../examples/measurement-review/README.md),
  metadata-only [CAD/thermal plan](../examples/cad_cae/README.md) (`NOT_EXECUTED`),
  the existing three-file [public STEP reference](../examples/cad_cae/native-geometry-reference/README.md),
  and finite offline [utility `history`/`profile`](../examples/measurement-review/README.md#offline-incremental-utility-fixture-report).
  These use the matching source tree; the STEP retains historical a4 provenance
  and is a static projection, not a replayable native pack
- HTTPS has finite mocked qualification only; live transport/worker/provider/model
  interoperability is `NOT_RUN`. [A2A](../docs/a2a-worker-turn.md) still returns an
  `UNACCEPTED` candidate. Real O3 remains `PROPOSED / NOT_RUN`; measured effort is `UNKNOWN`
- Installing the default wheel starts no native backend or service. Full CAD/thermal native execution
  is `NOT_RUN`; physical validation `NOT_PERFORMED`, independent review `NOT_EVALUATED`,
  mesh independence `NOT_ESTABLISHED`. Scientific/device authority stays false;
  historical Temporal evidence and the [a3 inventory](../docs/release-inventory/v0.3.0a3/README.md)
  retain their own scopes, without new agent-scale or UI claims

The published predecessor is [0.3.0a4](https://github.com/sddvacav/opendot/releases/tag/v0.3.0a4), source commit
`2d16190a8121410bbeea252869b196f7891e1696`. Its [pinned installed guide](https://github.com/sddvacav/opendot/blob/2d16190a8121410bbeea252869b196f7891e1696/docs/installed-quickstart.md)
and [release notes](https://github.com/sddvacav/opendot/releases/download/v0.3.0a4/RELEASE-NOTES.md) retain the exact historical artifact and qualification scope;
those frozen assets are unchanged.

Historical a3 instructions and exact pins remain in the [corrected a3 guide](https://github.com/sddvacav/opendot/blob/8d5d8667d65734fb5c40fa0526709a3159b7f165/docs/installed-quickstart.md). The a3 full source had pure batch preparation and no three-role comparison; its bundled guides retained historical a2 pins. Those facts and earlier receipts are unchanged.

## Read-only synthetic source checks

The source-only route below validates invented local records; it does not start agents or control devices. Run from the source root with Python 3.12+ on a supported POSIX system. The installed route above keeps imports isolated from the source tree.

```sh
PYTHONPATH=src python -B -m opendot_engineering.adapters.source_audit \
  --root examples/source-audit --manifest manifest.json \
  --expected-revision aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
  --expected-manifest-sha256 f4d81f12c83b7f222931348677b01b6f27df8905513cfbaebac3cf86cbfe26ae \
  --audience public

PYTHONPATH=src python -B -m opendot_engineering.adapters.lab_qualification \
  --root examples/lab-qualification \
  --expected-revision bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb \
  --expected-manifest-sha256 1dcde9c63280f4f99e6c2ea9e3ca6d392399e4d0792a4a9e4f81d581d2ce817f
```


## Prerequisites and scope

- Python 3.12 or newer; local checks used CPython 3.12 on Linux
- A source copy with `src/` and the two synthetic example directories
- For both synthetic examples, POSIX descriptor-relative no-symlink file reads; unsupported platforms fail closed
- No model key, network service, native CAD backend, or solver is needed for these two examples

The default package has no required runtime Python dependencies. The current experimental release is the [0.3.0a5 ALPHA prerelease](https://github.com/sddvacav/opendot/releases/tag/v0.3.0a5). Use its [installed guide](installed-quickstart.md) only with the matching reviewed five-file bundle and external SHA256SUMS pin. No PyPI publication or broader supported-platform matrix is claimed. Do not substitute a similarly named package.

## What to inspect

The source-audit command prints JSON with `audit_accepted: true` and `scientific_accepted: false`. Known and unknown observations retain their distinct metadata. The synthetic revision string does not establish Git membership.

The qualification command prints `benchmark_contract_passed: true`; `scientific_accepted`, `device_control_authorized`, and `real_device_qualified` remain `false`. A correct refusal is a successful contract check, not a qualified physical device. Do not replace unknown values with zero.

Both adapters read their fixtures and print a bounded result. They do not create result files, call a model, start a solver, or control hardware. Capturing stdout creates a file only through the caller's shell. Keep any captured evidence outside the source repository and review it before sharing.

## Installed-artifact validation

The local packaging check builds a wheel in separate staging, installs it without dependencies into a fresh environment, and runs the same fixed inputs outside the source tree. Isolated Python execution disables source-tree import shortcuts. [Integration checks](integration-review.md) distinguish this result from source-root execution and from public-release qualification.

The wheel installs the Python package; examples and documentation require the matching full-source archive. The sdist is wheel-rebuild input, not the full examples or test tree. When testing an installed wheel, copy the public fixtures separately, clear source-tree `PYTHONPATH`, use the installed interpreter with `-I -B -m`, and keep the same published pins. No registered console script exists.

## Optional fake-only execution

The [simulated-lab guide](simulated-lab.md) is a separate opt-in path using exact-pinned
Bluesky/ophyd/event-model dependencies. It runs only a finite internally constructed
fake-device plan. Neither that path nor the read-only examples qualify hardware
or scientific results. Offline simulation verification needs no optional packages.

## Troubleshooting

- `No module named opendot_engineering`: for the source commands, run from the repository root with `PYTHONPATH=src`; for an installed check, verify the interpreter and distribution without falling back to source imports
- Pin or schema rejection: use the unchanged included fixture; do not recompute an expected pin from untrusted input and call that independent validation
- Unsupported path operations: use an explicitly tested POSIX environment; do not weaken no-symlink checks
- Optional CAD/solver errors: those backends are outside these two examples; read the adapter-specific guide before choosing an environment

Full shell environments and private paths do not belong in public bug reports. Use a small synthetic reproduction and [Support](../SUPPORT.md).

## Future first-run acceptance

A future runtime tutorial must separately demonstrate task permissions, resource limits, evidence inspection, cancellation, restart/resume where claimed, and child-resource cleanup. None of those lifecycle guarantees is implied by these short read-only adapter commands.

## 中文摘要

首次安装请先完成[中文安装入门](installed-quickstart.zh-CN.md)的第 1–2 步：先核验完整五文件包，再只用固定版本 wheel 生成并检查第一个本地产物，无需提取源码示例或准备可选依赖。若只想检查本地夹具，可运行本文上方的两条只读命令。模型、服务、原生求解器与设备均不是这些入门示例的前提。

当前安装指南对应[已发布的 0.3.0a5 ALPHA 预发布版](https://github.com/sddvacav/opendot/releases/tag/v0.3.0a5)，要求匹配的五文件包与外部独立验收的 SHA256SUMS 摘要。已发布的前一版 [0.3.0a4](https://github.com/sddvacav/opendot/releases/tag/v0.3.0a4)使用[固定提交的历史指南](https://github.com/sddvacav/opendot/blob/2d16190a8121410bbeea252869b196f7891e1696/docs/installed-quickstart.zh-CN.md)。a5 wheel 包含可选、显式导入的 HTTPS 模块，默认依赖仍为空；真实传输／worker／提供方／模型互通为 NOT_RUN。Sdist 仅供重建 wheel，不含完整示例／测试树。匹配完整源码另含测量比较、NOT_EXECUTED 的 CAD plan、保留历史 a4 来源的静态 STEP 参考，以及离线效用 history／profile。真实 O3 为 PROPOSED／NOT_RUN，实测投入 UNKNOWN；不新增原生或服务运行。历史 a3 产物仅含可选有界读取与纯批次准备，其捆绑指南保留历史 a2 固定值；应使用版本固定的历史 a3 修正版指南。后续真实批次与保留证据工作不改变 a3 产物。安装包检查与源目录检查分别记录；ALPHA、NOT_SCORED 不变，完整运行时的中断、恢复和清理行为仍需独立实现与验证。
