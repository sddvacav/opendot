# First useful result from the exact 0.3.0a5 candidate

[简体中文](installed-quickstart.zh-CN.md) · [Source-only route](../README.md#run-the-synthetic-examples)

Run one permission-gated Python callable, store a synthetic result, and check the
stored bytes independently. The first result uses only the wheel and Python 3.12+;
no model key, service, native solver or device is needed. ALPHA / NOT_SCORED.

## 1. Establish the external trust input, then install offline

This bundled guide is frozen before publication. It names the a5 release target,
not a claim that publication or public-download verification has happened.
Use a trusted POSIX environment with Python 3.12+ (`venv` and pip), and a trusted
`/tmp` parent. Linux/CPython 3.12 is the local reference, not a platform matrix.

Obtain the five matching files from the identified `sddvacav/opendot` publisher's
[v0.3.0a5 release](https://github.com/sddvacav/opendot/releases/tag/v0.3.0a5)
when published, or from the separately reviewed local candidate bundle:

- `opendot_engineering-0.3.0a5-py3-none-any.whl`
- `opendot_engineering-0.3.0a5.tar.gz`
- `opendot-engineering-0.3.0a5-source.tar.gz`
- `RELEASE-NOTES.md`
- `SHA256SUMS`

Before running anything, independently review the public release body's provenance
prefix (or the accepted review/publication receipt). Verify the exact repository,
tag `v0.3.0a5`, accepted source commit and source tree against that review. Obtain
the final SHA256SUMS SHA-256 from that separately reviewed prefix/receipt and set
`EXPECTED_SUMS_SHA256` in your shell to that exact lowercase 64-hex value. The
release body links the exact commit/tree and carries the external digest; private
chat access is not required. If no independently accepted pin exists, stop.
**Never derive the expected digest from the downloaded SHA256SUMS itself.**

This requires trusting the identified GitHub publisher. A matching filename,
location or TLS download alone is not self-authentication. No signature,
attestation or cryptographic publisher-identity guarantee is presumed. Hashes
establish byte consistency relative to the trusted input, not authorship, safety
or scientific validity. Do not change a pin to make unfamiliar bytes pass.

The [release notes](https://github.com/sddvacav/opendot/releases/download/v0.3.0a5/RELEASE-NOTES.md)
record exact archive identities and the complete bilingual recipe.
[SHA256SUMS](https://github.com/sddvacav/opendot/releases/download/v0.3.0a5/SHA256SUMS)
hashes exactly the three archives and notes, never itself. Its digest is kept
outside those payloads to avoid a self-hash cycle. The packaging sdist is a build
input, distinct from the complete source archive; this guide installs neither
sdist nor dependencies. Do not substitute GitHub-generated archives or files from a3/a4.

Replace only `RELEASE_DIR` with the absolute directory containing all five reviewed
files and `PYTHON` if necessary. Supply the external `EXPECTED_SUMS_SHA256` as
above. Keep all filenames and verification logic unchanged. Run the blocks in
one shell. Invalid/unset pins or mismatched/duplicate/extra/missing entries stop
before environment creation, pip installation or source extraction.

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

Expect `0.3.0a5` and an import path in the new environment's `site-packages`.
`-I` ignores source-directory shortcuts and `-B` avoids bytecode writes. No shell
activation or `PYTHONPATH` is needed; no `opendot` console command is registered.

### Inspect package help and version

```sh
"$PY" -I -B -m opendot_engineering --help
"$PY" -I -B -m opendot_engineering --version
```

Help includes the exact-version first-result/release-note links and prints static
API guidance. It performs no network access, user-file reads, optional imports or
dispatch. Link text does not verify that the target has been published.
See [option behavior](module-cli.md).

## 2. Create and inspect your first result

Use a new output path under a trusted parent; keep its ancestors under your control.

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

Expect `COMPLETED`, `semantic_valid: true`, an `artifact_id` beginning `sha256:`,
`independent_sha256_matches: true` and `bounded_read_and_refusal_passed: true`.
`scientific_accepted` remains false. The semantic check only validates the returned
reference type; permissions are dispatch checks, not an OS sandbox. The write
label implements no undo. CAS follows symlinks in trusted roots and is not a transaction.
For trusted regular objects, `max_bytes=N` acquires at most N+1 actual bytes to
detect excess; omitted/None retains whole reads. No constant-memory, wall-time,
hostile-filesystem or execution-wide bound is promised. See [bounded reads](canonical-artifacts.md#optional-bounded-retrieval-unreleased-source-increment).

## 3. Try success, refusal and missing permission

The wheel excludes examples. Recheck the full-source bytes against the digest
obtained from the externally pinned manifest, extract canonical regular members,
and copy public examples. These lightweight examples still import the installed wheel.

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

Expect `synthetic_software_assertions_passed: true` and `package_version: "0.3.0a5"`.
Success is COMPLETED with independently verified bytes. Semantic refusal is FAILED
with one intact unaccepted artifact retained. Permission refusal is BLOCKED/
PermissionDenied with zero handler calls and stored objects; store construction
still creates empty directories. Failure does not roll back effects.

## 4. Check included read-only fixtures

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

Expect `audit_accepted: true` / `scientific_accepted: false`, then
`benchmark_contract_passed: true` with scientific/device/real-device authority false.
The a/b revisions and pins are fixed synthetic fixtures. Obtain pins independently
for other inputs. Neither command writes a receipt unless the shell redirects output.

## 5. Other lightweight examples

```sh
"$PY" -I -B "$JOURNEY/examples/callable-execution/demo.py"
"$PY" -I -B "$JOURNEY/examples/canonical-artifacts/roundtrip.py" \
  --output "$OUTPUT_PARENT/artifact-roundtrip"
```

The callable example covers five cases (success 5, explicit retry 8). The artifact
example prints `passed: true` and retains a deliberately damaged synthetic object.
[Agent contracts](../examples/agent-contracts/README.md) are descriptive metadata,
not enforcement. The optional Git example below is separately gated and **NOT_RUN**
in this candidate walkthrough. It needs trusted system Git >= 2.52.0 in the fixed
search path and the [Git profile preconditions](git-workspaces.md).

```sh
PATH=/usr/local/bin:/usr/bin:/bin git --version
"$PY" -I -B "$JOURNEY/examples/git-workspaces/demo.py"
```

A separately authorized eligible run would require `receipt_ok`, `shared_fixed_base`,
`second_is_clean` and `primary_checkout_unchanged` true. It uses its own disposable
repository. No Git-workspace acceptance is inferred from the seven other blocks.

## Matching-source workflows and optional features are separate

The full archive includes [measurement comparison](../examples/measurement-review/README.md).
Run that documented demo/replay from its matching source root with `PYTHONPATH=src`:
canonical owner imports must originate in that same tree. Copying compare.py and
using only the installed wheel is not this workflow. Synthetic means are 2 and 4,
difference 2/1 and tolerance 2/2.0; CHECKED is computation consistency, not science.

The [CAD/thermal plan](../examples/cad_cae/README.md) is metadata-only NOT_EXECUTED;
native versions remain NOT_CHECKED. Fabricated tests are not genuine native evidence.
CAD/Gmsh/CalculiX execution is NOT_RUN; physical validation NOT_PERFORMED,
independent review NOT_EVALUATED and mesh independence NOT_ESTABLISHED.

The full-source [public STEP reference](../examples/cad_cae/native-geometry-reference/README.md)
retains its historical a4 provenance and standard-library byte-check recipe. It is
not a replayable native evidence pack. The source-only [offline utility report](../examples/measurement-review/README.md#offline-incremental-utility-fixture-report)
provides dependency-free `history` and `profile` commands; its finite synthetic
controls do not establish real benefit. Real O3 remains PROPOSED / NOT_RUN,
measured effort UNKNOWN. These examples, research pins and STEP are absent from
the wheel and packaging sdist; use the matching complete source.

The optional [A2A worker turn](a2a-worker-turn.md) uses at most one externally supplied
callback and returns an UNACCEPTED candidate. Offline fixtures supply no live
transport/provider/model result; the external live gate remains NOT_RUN. The a5
wheel includes the explicit-import [HTTPS module](a2a-http-transport.md), qualified
only with finite mocks; packaging does not authorize a live request or establish
live interoperability. Default imports and dependencies are unchanged.
The [Temporal tools](temporal-batch-qualification.md) are source-only qualification
tools, not a production wheel API. Historical hosted runs keep their exact prior
scope and do not qualify this candidate. No fresh service/native run occurs here.
Default dependencies remain empty. Temporal SDK and simulation extras are separate,
explicitly prepared environments; installation never starts a server automatically.
The [a3 component inventory](release-inventory/v0.3.0a3/README.md) remains a3-only,
not an a5 SBOM. Scientific and device authority stay false.

## Recover without deleting evidence

- Import failure: use the exact installed `$PY`; do not add a source path to make an installed check pass
- Manifest or revision mismatch: stop and check matching bytes and independently reviewed pins
- Existing output: the script CLI refuses a detected file/directory/symlink (including dangling links) before demonstration, leaving it untouched. Inline Python/direct calls keep FileExistsError behavior; a race after non-atomic preflight can also raise it
- Missing parent: use a trusted `mktemp -d` parent. Preserve prior results and choose a new child; no retry, cleanup or rollback is supplied
- Missing venv/pip or unsupported POSIX/Git: use a separately prepared eligible host, without weakening checks

To rerun the three-case example with a fresh output:

```sh
OUTPUT_PARENT=$(mktemp -d /tmp/opendot-result.XXXXXX)
"$PY" -I -B "$JOURNEY/examples/callable-artifacts/demo.py" \
  --output "$OUTPUT_PARENT/three-cases"
```

Keep generated outputs private until reviewed; errors and receipts may contain
local paths or input content. See [support](../SUPPORT.md), [callable limits](callable-execution.md)
and [storage limits](canonical-artifacts.md). A local walkthrough is not hosted CI,
public-download verification, independent release acceptance or scientific review.

Historical [a4 guide](https://github.com/sddvacav/opendot/blob/2d16190a8121410bbeea252869b196f7891e1696/docs/installed-quickstart.md) and published a4 assets remain unchanged; their walkthrough does not accept a5.

Historical [a3 corrected guide](https://github.com/sddvacav/opendot/blob/8d5d8667d65734fb5c40fa0526709a3159b7f165/docs/installed-quickstart.md)
and its immutable assets retain their own pins; a3's bundled guide still had a2
text. Do not use either historical recipe as a5 acceptance. The [documentation checker](documentation-checks.md)
compares eight literal-identical bilingual shell blocks without executing them.
