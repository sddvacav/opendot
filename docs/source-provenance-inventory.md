# Source-only provenance inventory

The optional [source inventory tool](../ci/source_provenance.py) records every
regular file named by a trusted primary checkout's **current Git index**, once,
with a relative path, SHA-256, byte size, category and explicit evidence status.
It helps locate the remaining item-level provenance review work. It does not
complete that review or change N3, a quality score, release status or legal rights.

This is source-only CI/operator tooling. It is not part of the installed package
API and does not create a runtime, loader, scheduler, artifact store or permission
owner. No requirements file or hosted workflow is changed by this addition.

## Run against a trusted public-source checkout

Requirements: POSIX, Python 3.12+, and a trusted system Git 2.52+ executable in the
existing controlled Git owner's system search path. No optional Python dependency
is required by the generator. Use the source checkout, with the package's
canonical helper owner available through `PYTHONPATH`:

```sh
OUT="$(mktemp -d)"
PYTHONPATH=src python -B ci/source_provenance.py \
  --root . --output "$OUT/source-provenance.json"
```

The output parent must already exist. The output must be a **new file outside the
source root**. Existing files, output symlinks, symlinked parents and in-source
outputs refuse without overwriting them. The tool prints only the successful
file count and manifest SHA-256; it does not print the source/output absolute
paths. Rejected invocations print a fixed error code, without Git diagnostics or
input values, and exit nonzero. An output-write failure can leave a partial new
file. There is no retry, cleanup, transaction or rollback guarantee; inspect any
residue before choosing a fresh destination.

The new tool, tests and documentation must be added to the local index before
they themselves appear in the inventory. The tool never stages files. Untracked
files are explicitly `EXCLUDED_NOT_ENUMERATED`: they are not read, classified or
claimed to be covered. A passing result is not a claim that a directory contains
only those files.

## What the receipt proves and does not prove

The deterministic JSON schema is `opendot.source-provenance-inventory.v1`.
There are no timestamps, machine names, absolute root paths, remote URLs or
contributor identities in generated records. Item order is lexicographic by
relative path, and JSON serialization has stable ordering and formatting.

Each item records:

- `path`, `sha256`, `bytes` and `kind` for the observed working-file bytes
- `index_mode` and `index_blob_sha1` from the current index
- `working_bytes_match_index_blob` and either
  `INDEX_BLOB_AND_WORKING_BYTES_MATCH` or `WORKING_BYTES_DIFFER_FROM_INDEX`
- `rights_status`, `authorship_status` and `private_data_review_status`, all
  **`NOT_VERIFIED`**, including when a project Apache license is present
- hash-bound `source_pointers` marked `DECLARATION_REFERENCE_ONLY`

The manifest also hashes the canonical sorted index-entry list, reports counts
and total observed bytes, and always retains `commit_binding: NOT_VERIFIED`.
A staged change can match the index without belonging to any commit. An unstaged
byte change receives its new SHA-256 and an explicit mismatch, rather than being
rejected or mislabeled as clean. The mismatch concerns bytes, not all filesystem
metadata. No HEAD commit, author, log, remote or object-history retrieval is
performed. Administrative entry types and the index/configuration are inspected
for the declared safety profile; Git history contents are not inventoried.

The source pointers are the existing [LICENSE](../LICENSE), [NOTICE](../NOTICE)
and [public provenance account](PROVENANCE.md). Items under `assets/brand/` also
point to the existing [brand NOTICE](../assets/brand/NOTICE). These tracked files
must exist. Their current hashes change when their bytes change. The generator
does not infer individual authors, imported-source licenses, permission grants,
AI-training ownership, trademark rights or file-by-file signoff from these
project-level declarations. It does not inspect private upstream origins.

The top-level rights, authorship and privacy clearance fields stay
`NOT_VERIFIED`. Scientific acceptance and device authority are false; scientific
and independent-review status remain `NOT_EVALUATED`. Hashes establish observed
byte identity, not authenticity. This is not a full dependency SBOM, secret
scanner, rights clearance, scientific review or publication authorization. A
separate reviewer must assess origins, applicable rights and private-data risks
before an outgoing artifact can be approved.

## Explicit classification policy

Rules are applied in the following order. Unknown paths fail closed as
`UNCLASSIFIED_SOURCE_PATH`; no file is silently omitted or assigned a fallback
license or contributor. An extension is compared case-insensitively; path prefixes
and the named license/configuration files are case-sensitive.

| Kind | Accepted paths |
| --- | --- |
| license | Exactly `LICENSE`, `NOTICE`, `assets/brand/NOTICE` |
| test | Under `tests/`, with `.py`, `.json`, `.txt` or `.md` suffix; `.csv` fixtures under `examples/` |
| docs | Any `.md` file; `.json`/`.csv` evidence and files named exactly `SHA256SUMS` under `docs/` |
| code | Python files under `src/`, `ci/` or `examples/` |
| asset | Under `assets/`, with `.svg`, `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif` or `.ico` suffix |
| config | Exactly `.gitignore` or `pyproject.toml`; `.yml`/`.yaml` under `.github/workflows/`; `.json`/`.txt` under `ci/` or `examples/` |

For example, a brand README is documentation, its NOTICE is a license/notice
record, a test fixture JSON is a test, and a source-audit example manifest is
configuration. A CSV under `examples/`, such as
`examples/measurement-review/batch.csv`, is classified as a test fixture. This
organizational label does not prove that its data are synthetic or grant rights;
its provenance, authorship, rights and privacy still require review. CSV files under `docs/`, including
`docs/research/oss-workflows/frozen-oracle/measurements.csv`, are instead
documentation evidence. Files named exactly `SHA256SUMS` under `docs/` are also
documentation evidence. These are organizational rules only: no CSV values or
checksum declarations are independently validated, and no extra rights or
privacy assertion is made. CSV files outside `examples/` and `docs/`, and
`SHA256SUMS` files outside `docs/`, remain unclassified. A new root-level Python script or a new binary/document format
requires an explicit policy update and review. Classification is organizational,
not a rights or data-sensitivity judgment.

## Safety and resource boundary

The canonical [source-audit owner](../src/opendot_engineering/adapters/source_audit.py)
provides descriptor-relative, no-follow root/file reads, relative-path checking,
hashing and bounded rejection codes. Its implementation is unchanged. The tool
reuses the existing [controlled Git owner](../src/opendot_engineering/git_workspace.py)
for trusted executable-search/configuration policy constants and the no-follow
administrative-entry scan. It does not instantiate a workspace manager.

Git runs with a freshly constructed controlled environment, no inherited Git
variables or caller PATH, no interactive authentication, no optional index locks,
no lazy fetch and disabled protocols, hooks, fsmonitor, external diff, credentials
and automatic maintenance. The local config is first read safely and parsed on
stdin outside the repository with includes disabled. Only narrowly documented
harmless core metadata, user name/email declarations, ordinary remote URL/fetch
and branch remote/merge configuration are accepted. Values are never emitted.
Includes, filters, external worktrees, repository extensions, sparse checkout,
alternate object stores and other unsupported configuration refuse before
index enumeration. The current implementation conservatively rejects remote
or branch configuration names containing a dot.

Only a primary checkout with a real `.git` directory is supported. Root,
administrative, tracked-file and tracked-parent symlinks refuse; so do missing
tracked files, submodule/index link modes, unmerged stages, invalid/duplicate
paths, invalid UTF-8 index names and tracked `.git`, `.gitmodules` or
`.gitattributes` path components. The index must remain unchanged during the
scan. No source/index/configuration/history mutation is performed.

Limits are 1,024 indexed files, an 8 MiB index/Git-output bound, a 64 KiB local
config bound, the canonical 2 MiB limit per source file and 32 MiB of total
source-file bytes. Exceeding a limit refuses the inventory; it does not produce
a partial accepted result. The Git-output size bound is checked after capture,
not an operating-system memory limit. Administrative entry scanning is inherited
from the trusted-checkout profile and is not a bounded history-size scan.

The checkout, Git executable directories and their ancestors must remain trusted
and cooperative. Sequential reads and preflight checks are not an atomic snapshot
or protection against hostile concurrent replacement. No OS sandbox, adversarial
resource limit or complete filesystem security claim is made.

## Focused validation

The [synthetic tests](../tests/test_source_provenance.py) use disposable local Git
indexes without commits or network operations. They check deterministic coverage,
changed bytes and index mismatches, category boundaries, notices, untracked
exclusion, unsafe paths and links, unsupported configuration, controlled execution,
output refusal and path-safe errors. They do not validate private source origins,
legal rights, hosted CI, published downloads or the package's other behaviors.

```sh
PYTHONPATH=src python -B -m pytest -q -p no:cacheprovider tests/test_source_provenance.py
```
