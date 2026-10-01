# Run the bounded synthetic examples

For a first useful result from a reviewed local wheel, follow the complete
[installed quickstart](installed-quickstart.md) or
[中文安装入门](installed-quickstart.zh-CN.md). Its first example needs only the
wheel and standard library; later steps copy the matching public fixtures.

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

The default package has no required runtime Python dependencies. This is an unreleased source candidate, not an advertised registry download. Do not install a similarly named package or guess a repository URL. A verified public release destination and support matrix remain release gates.

## What to inspect

The source-audit command prints JSON with `audit_accepted: true` and `scientific_accepted: false`. Known and unknown observations retain their distinct metadata. The synthetic revision string does not establish Git membership.

The qualification command prints `benchmark_contract_passed: true`; `scientific_accepted`, `device_control_authorized`, and `real_device_qualified` remain `false`. A correct refusal is a successful contract check, not a qualified physical device. Do not replace unknown values with zero.

Both adapters read their fixtures and print a bounded result. They do not create result files, call a model, start a solver, or control hardware. Capturing stdout creates a file only through the caller's shell. Keep any captured evidence outside the source repository and review it before sharing.

## Installed-artifact validation

The local packaging check builds a wheel in separate staging, installs it without dependencies into a fresh environment, and runs the same fixed inputs outside the source tree. Isolated Python execution disables source-tree import shortcuts. [Integration checks](integration-review.md) distinguish this result from source-root execution and from public-release qualification.

The wheel installs the Python package; examples and documentation are source-distribution material. When testing an installed wheel, copy the public fixtures separately, clear source-tree `PYTHONPATH`, use the installed interpreter with `-I -B -m`, and keep the same published pins. No registered console script exists.

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

请运行本文上方的两条源码合成示例命令；它们只读取本地夹具并输出 JSON，不需要模型、网络、原生 CAD 后端或设备。[中文安装入门](installed-quickstart.zh-CN.md)另含实际写入本地产物的独立环境示例。安装包检查与源目录检查分别记录；完整运行时的中断、恢复和清理行为仍需独立实现与验证。
