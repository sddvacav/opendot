# First useful result from the 0.3.0a2 prerelease

[简体中文](installed-quickstart.zh-CN.md) · [Source-only route](../README.md#run-the-synthetic-examples)

Run one permission-gated Python callable, store its synthetic result, and verify
the stored bytes independently. This first result needs only the released wheel;
it does not need a source checkout, model key, network service, native solver, or
device. These are finite local software examples, not an autonomous agent runtime.

## 1. Prepare one isolated environment

You need Python 3.12+ with `venv` and pip support and a trusted POSIX environment.
Earlier local checks used Linux and CPython 3.12; this is not a general
platform-support promise. Use a shell session in which `/tmp` is a suitable
trusted temporary parent.

Download the [opendot_engineering-0.3.0a2-py3-none-any.whl](https://github.com/sddvacav/opendot/releases/download/v0.3.0a2/opendot_engineering-0.3.0a2-py3-none-any.whl)
from the [0.3.0a2 ALPHA prerelease](https://github.com/sddvacav/opendot/releases/tag/v0.3.0a2)
to a trusted local directory. Its exact SHA-256 is pinned below and listed in the
release's [SHA256SUMS](https://github.com/sddvacav/opendot/releases/download/v0.3.0a2/SHA256SUMS).
This guide uses GitHub release assets; no PyPI publication is claimed. Do not
substitute a similarly named package or an earlier same-version build. A matching
digest checks the supplied bytes, not their authorship, safety or scientific validity.

The [release notes](https://github.com/sddvacav/opendot/releases/download/v0.3.0a2/RELEASE-NOTES.md)
bind these assets to public commit
[359f781a5aa1650ae92b1af81cf369a17c444045](https://github.com/sddvacav/opendot/commit/359f781a5aa1650ae92b1af81cf369a17c444045).
The [historical 0.3.0a1 verification record](structural-v2-candidate-verification.md)
and [historical 0.3.0a1 installed guide](https://github.com/sddvacav/opendot/blob/359f781a5aa1650ae92b1af81cf369a17c444045/docs/installed-quickstart.md)
retain their earlier versions and pins; they do not approve this wheel. Release
assets remain frozen at the linked source commit. Documentation inside those
assets retains its build-time download guidance; use this updated guide for the
0.3.0a2 pins. The breaking structural default is covered by the
[migration guide](structural-default-v2.md); this first-result journey uses the unchanged
callable/artifact profile. The [documentation check](documentation-checks.md)
compares the eight shell blocks below without executing them.

### Exact download identities

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `opendot_engineering-0.3.0a2-py3-none-any.whl` | 99,220 | `c1c35cb76557a3998e8ec26ca5d3097095835af832d565e3b79e3baf320d64d7` |
| `opendot_engineering-0.3.0a2.tar.gz` | 231,217 | `2b7520119edd698d98ab4ce0cb052d03d55b4ec02c9e3e62ba9dba85ad3fc0c8` |
| `opendot-engineering-0.3.0a2-source.tar.gz` | 611,307 | `928062b851e0431f493a6b7ae5d36b989323cb0e16e21198accbf928ba1bbdc2` |

The [packaging sdist](https://github.com/sddvacav/opendot/releases/download/v0.3.0a2/opendot_engineering-0.3.0a2.tar.gz)
is a separate build input, not the full-source archive used for examples in step 3.
This guide installs the wheel and does not build or install the sdist.

Replace only `WHEEL` with the absolute path to the downloaded wheel. If your Python
3.12+ executable has another name, change `PYTHON` too. Keep the pinned SHA-256
unchanged. Run all blocks in the same shell. Installation creates a fresh environment
and makes no dependency download.

```sh
set -eu
PYTHON=python3.12
WHEEL='/absolute/path/to/opendot_engineering-0.3.0a2-py3-none-any.whl'
EXPECTED_WHEEL_SHA256='c1c35cb76557a3998e8ec26ca5d3097095835af832d565e3b79e3baf320d64d7'

"$PYTHON" -I -B - "$WHEEL" "$EXPECTED_WHEEL_SHA256" <<'PYCODE'
import hashlib, pathlib, sys
if sys.version_info < (3, 12):
    raise SystemExit("Python 3.12 or newer is required")
wheel, expected = pathlib.Path(sys.argv[1]), sys.argv[2]
if hashlib.sha256(wheel.read_bytes()).hexdigest() != expected:
    raise SystemExit("Wheel hash mismatch: stop and check the reviewed artifact")
print("Pinned wheel bytes match")
PYCODE

JOURNEY=$(mktemp -d /tmp/opendot-first-run.XXXXXX)
"$PYTHON" -I -B -m venv "$JOURNEY/venv"
PY="$JOURNEY/venv/bin/python"
"$PY" -I -B -m pip install --no-index --no-deps --no-compile --no-cache-dir "$WHEEL"
cd "$JOURNEY"
"$PY" -I -B -c 'import importlib.metadata as m, opendot_engineering as p; print(m.version("opendot-engineering")); print(p.__file__)'
```

Expect version `0.3.0a2` and an import path inside the new environment's
`site-packages`. No shell activation or `PYTHONPATH` is needed. `-I` ignores
source-directory import shortcuts; `-B` avoids Python bytecode writes. There is
no `opendot` console command.

### Inspect package help and version

Use the same installed interpreter; no copied examples are needed:

```sh
"$PY" -I -B -m opendot_engineering --help
"$PY" -I -B -m opendot_engineering --version
```

Help lists API paths and separately invoked module entrypoints. Version prints
`opendot-engineering` followed by the imported package's code version. These
commands start no runtime, dispatch no tools and load no optional backends;
there are no registered `opendot` or `odot` console commands.
See [package help and option behavior](module-cli.md).

## 2. Create and inspect your first result

This block is self-contained. It creates a new output directory under a fresh
trusted parent; leave that directory and its ancestors under your control.

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

A successful run exits zero and prints `status: "COMPLETED"`,
`semantic_valid: true`, an `artifact_id` starting with `sha256:`, and
`independent_sha256_matches: true`. The `output_directory` points to the local
CAS tree you can inspect. `scientific_accepted` remains `false`.

The semantic validator here checks only the returned reference type. It does not
validate a scientific claim. Permissions are dispatch checks, not an OS sandbox.
The `REVERSIBLE_WRITE` label does not implement undo; CAS is trusted-root storage,
follows symlinks, and is not a transaction or recovery system.

## 3. Try success, refusal, and missing permission

The wheel contains the Python package, not the example scripts or fixtures.
Download the matching [full source archive](https://github.com/sddvacav/opendot/releases/download/v0.3.0a2/opendot-engineering-0.3.0a2-source.tar.gz)
from the same release and replace `SOURCE_ARCHIVE` with its absolute local path.
Use this named asset, not the narrower packaging sdist or GitHub's automatically
generated source links, which have different bytes. Keep the source SHA-256 pin
unchanged. The block verifies the archive before extracting it into the fresh
journey directory, then copies only public examples. Imports continue to come
from the installed wheel.

```sh
SOURCE_ARCHIVE='/absolute/path/to/opendot-engineering-0.3.0a2-source.tar.gz'
EXPECTED_SOURCE_SHA256='928062b851e0431f493a6b7ae5d36b989323cb0e16e21198accbf928ba1bbdc2'
"$PY" -I -B - "$SOURCE_ARCHIVE" "$EXPECTED_SOURCE_SHA256" "$JOURNEY/source" <<'PYCODE'
import hashlib, pathlib, sys, tarfile
archive, expected = pathlib.Path(sys.argv[1]), sys.argv[2]
if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
    raise SystemExit("Source archive hash mismatch: stop and check the released asset")
output = pathlib.Path(sys.argv[3])
output.mkdir(exist_ok=False)
with tarfile.open(archive, "r:gz") as source:
    source.extractall(output, filter="data")
print("Pinned source archive bytes match")
PYCODE
SOURCE="$JOURNEY/source/opendot-engineering-0.3.0a2"
cp -R "$SOURCE/examples" "$JOURNEY/examples"
"$PY" -I -B "$JOURNEY/examples/callable-artifacts/demo.py" \
  --output "$OUTPUT_PARENT/three-cases"
```

Expect `synthetic_software_assertions_passed: true` and `package_version:
"0.3.0a2"`. The three cases deliberately have different outcomes:

- `success`: `COMPLETED`, semantic-valid, independently hash-verified bytes
- `semantic_refusal`: `FAILED` with one intact **unaccepted** artifact retained
- `permission_refusal`: `BLOCKED/PermissionDenied`, zero handler calls and zero stored objects

These refusals are expected checks. Failed validation does not roll back effects.
The store constructor still creates empty directories in the permission case.

## 4. Check the included read-only fixtures

Continue with the same copied examples and fixed pins:

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

The audit prints `audit_accepted: true` and `scientific_accepted: false`.
Qualification prints `benchmark_contract_passed: true`; scientific acceptance,
device authority, and real-device qualification stay false. Its fixture includes
expected refusal cases. Neither command writes a result file unless you redirect
stdout yourself; keep any captured evidence outside the source repository.

The repeated `a` and `b` revisions are synthetic identifiers. For other inputs,
obtain expected revisions and hashes independently; do not change an expected
hash just to make an unfamiliar input pass.

## 5. Other lightweight examples

The [agent contracts example](../examples/agent-contracts/README.md) describes
`Capability` and `AgentManifest` metadata with explicit `.validate()` calls. Their
budgets and permissions are descriptive, with no execution enforcement or
existing-consumer migration. See the [API boundary](agent-contracts.md).

```sh
"$PY" -I -B "$JOURNEY/examples/callable-execution/demo.py"
"$PY" -I -B "$JOURNEY/examples/canonical-artifacts/roundtrip.py" \
  --output "$OUTPUT_PARENT/artifact-roundtrip"
```

The callable example checks five scenarios; its success output is `5` and its
explicit retry output is `8`. The artifact example prints `passed: true` and
intentionally retains one damaged synthetic object to demonstrate rejection.

Only the optional Git example needs trusted system Git >= 2.52.0. It searches
`/usr/local/bin:/usr/bin:/bin`, so a newer Git elsewhere on your normal `PATH`
is not sufficient. Check that fixed search path before running:

```sh
PATH=/usr/local/bin:/usr/bin:/bin git --version
"$PY" -I -B "$JOURNEY/examples/git-workspaces/demo.py"
```

Expect `receipt_ok`, `shared_fixed_base`, `second_is_clean`, and
`primary_checkout_unchanged` to be true. The fixture creates its own temporary
repository and removes its own temporary container on exit; no existing user
repository is needed. Read the [Git profile limits](git-workspaces.md) before
using its API on other repositories. Git failure does not block steps 1–4.

## Optional features are separate

The 0.3.0a2 package includes the [Gmsh file-size-limit repair](gmsh-cpu-ceiling.md)
and [bounded Temporal reference transport](temporal-reference-transport.md).
This walkthrough runs neither native backends nor Temporal. Default runtime
Python dependencies remain empty, and default imports do not load the optional
Temporal modules.

The optional `temporal` extra declares `temporalio==1.34.0`. Using it requires
separately approved, prepared SDK dependencies and an operator-owned service
configuration; the offline `--no-deps` installation above supplies none of them.
Installing the extra never starts or connects a server automatically. Its
qualified scope is only single-host loopback `synthetic.bounded_sum.v1`, queued
first delivery after a graceful quiescent restart, and recorded-result replay.
It does not establish in-flight crash recovery, multi-host operation, global
exactly-once effects, production deployment, scientific validity or device authority.
See the [capability and evidence limits](../CAPABILITIES.md); `NOT_SCORED` is unchanged.

## Recover from common first-run errors

- `No module named opendot_engineering`: use the exact `$PY` interpreter created
  above and inspect its import path. Do not add the source tree as a workaround
  for an installed-package check
- `ROOT_UNAVAILABLE` (exit 2): copy the matching examples and use the absolute
  `$JOURNEY/examples/source-audit` path; the wheel does not include fixtures
- `MANIFEST_HASH_MISMATCH` or `REVISION_OR_SCHEMA_MISMATCH` (exit 2): stop and check
  that your fixture and independently reviewed pins belong together
- `--output already exists` (exit 2): the `callable-artifacts/demo.py` and
  `canonical-artifacts/roundtrip.py` script CLIs report a detected existing file,
  directory or symlink, including a dangling symlink, on stderr before calling
  the demonstration. They leave that output untouched; choose a fresh path below
- `FileExistsError`: the inline Python block in step 2 and direct `demonstrate()`
  calls retain their original exception behavior. A collision after the script
  CLI's non-atomic preflight can also raise the original error. Preserve earlier
  results and choose a fresh path; the preflight adds no retry or cleanup
- `FileNotFoundError` for an output path: its parent must already exist; use the
  `mktemp -d` pattern rather than passing a missing multi-level path
- Missing `venv`/pip support: prepare it using your Python distributor's supported
  instructions, then restart setup. This guide does not install system software
- Unsupported POSIX operations or Git version: use an eligible reviewed host;
  do not weaken safety checks. Native-backend instructions are separate from
  this dependency-free path

To rerun the three-case example without deleting prior evidence:

```sh
OUTPUT_PARENT=$(mktemp -d /tmp/opendot-result.XXXXXX)
"$PY" -I -B "$JOURNEY/examples/callable-artifacts/demo.py" \
  --output "$OUTPUT_PARENT/three-cases"
```

Keep these local outputs private until reviewed: errors may contain local paths,
and other receipts may contain content. See [support](../SUPPORT.md),
[callable limits](callable-execution.md), and [storage limits](canonical-artifacts.md).
A successful local walkthrough is not hosted CI, public-download verification,
scientific review, or release acceptance.
