# Examples · start here

Smallest paths to a checked synthetic result. All are **source-tree** material unless an installed guide says otherwise. No private paths; use a fresh output directory outside the checkout.

## 1. Callable + artifact (recommended first)

Permission-gated write, three outcomes (`COMPLETED` / `FAILED` / `BLOCKED`), independent SHA-256 check:

```sh
OUTPUT_PARENT=$(mktemp -d /tmp/opendot-composition.XXXXXX)
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -B \
  examples/callable-artifacts/demo.py --output "$OUTPUT_PARENT/result"
```

[English notes](callable-artifacts/README.md)

## 2. Measurement comparison (synthetic)

One-command A/B comparison against a declared tolerance (`compare.py --demo`):

```sh
CMP_PARENT=$(mktemp -d /tmp/opendot-comparison.XXXXXX)
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -B \
  examples/measurement-review/compare.py run --demo \
  --output "$CMP_PARENT/demo"
```

[English](measurement-review/README.md) · [简体中文](measurement-review/README.zh-CN.md)

## 3. Callable execution only

Five controlled pure-Python scenarios on stdout (no artifact store):

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -B \
  examples/callable-execution/demo.py
```

[Notes](callable-execution/README.md)

## Installed wheel

After installing the reviewed `opendot-engineering` wheel, follow [installed quickstart §2–§3](../docs/installed-quickstart.md#2-create-and-inspect-your-first-result) (EN) / [安装入门第 2–3 节](../docs/installed-quickstart.zh-CN.md#2-创建并检查首个结果) (ZH). Do not reuse `PYTHONPATH=src` from source commands in that environment.

## Other directories

`cad_cae/`, `git-workspaces/`, `lab-qualification/`, `simulated-lab/`, `source-audit/`, `source-boundary/`, `agent-contracts/`, `canonical-artifacts/` — see each folder README. Scope stays ALPHA / NOT_SCORED unless a linked receipt says otherwise.
