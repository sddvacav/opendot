# Canonical local artifacts

The canonical local artifact core was introduced in `0.2.0a0` and is included
in this package. The optional read-only increment changes only
the existing store owner; default writer behavior and the `ArtifactRef` body are
preserved. It provides one standard-library
content-addressed store and one immutable reference type. This is a migration
candidate: previous consumers have not been switched or accepted. It is not a
second runtime. Each version's source and review records retain their own scope;
neither the [historical a4 record](verifier-ci-verification.md) nor a changed
release inherits acceptance from earlier artifact receipts. See the
[current overview](../OVERVIEW.md) and [installed guide](installed-quickstart.md)
for release status and version-pinned installation.

```python
from opendot_engineering.core import ArtifactStore

store = ArtifactStore("/path/to/trusted/local/artifacts")
ref = store.put_json({"kind": "synthetic", "value": 7}, producer="example")
assert store.get_bytes(ref) == b'{"kind":"synthetic","value":7}'
assert store.verify(ref)
assert store.verify_id(ref.artifact_id)
```

`ArtifactStore`, `ArtifactIntegrityError`, and `ArtifactRef` are re-exported from
`opendot_engineering.core` without wrappers or duplicate classes. The two owner
modules are `core.artifacts` and `core.contracts`. There is no console command,
automatic backend discovery, database, execution engine, or service.

## Layout and semantics

`objects/<first-two-hex>/<remaining-hex>` contains raw bytes and
`meta/<sha256>.json` contains the first successfully recorded reference. Byte puts
require `bytes`. Text uses UTF-8. JSON uses sorted keys, compact separators, UTF-8,
and rejects NaN/Infinity. File puts read a whole caller-selected file and infer
MIME type from its filename. There are no streaming or size limits.

`get_bytes` accepts the canonical reference, a lowercase 64-hex digest, or a
`sha256:` identifier. It hashes retrieved bytes and raises
`ArtifactIntegrityError` on a digest mismatch; it raises `FileNotFoundError` for a
missing object. `verify` additionally validates reference identity and size;
`verify_id` requires the `sha256:` prefix. These checks do not read metadata.

Repeated byte puts validate existing bytes plus metadata digest/size if metadata
exists. They keep the first stored metadata but return a new reference with the
current caller-supplied producer, task, and source fields. Those fields are
untrusted declarations, not authenticated provenance. A stored byte hash does
not certify content, licensing, access rights, or scientific quality.

## Optional non-mutating verification

`ArtifactStore(root, read_only=True)` uses the same owner and reference type, skips
all directory creation and chmod, and refuses `put_bytes`, `put_text`, `put_json`
and `put_file` with `PermissionError` before input reading or serialization.
`read_only` is a keyword-only bool; other types raise `TypeError` before setup.
The default `False` retains the ordinary writer behavior. There is no second CAS.

Construction does not require the root to exist and does not repair it. Existing
`get_bytes`, `verify` and `verify_id` behavior is preserved: missing objects fail
retrieval, verification returns false for missing/corrupt objects, and metadata
is not checked. A caller must supply the expected reference or digest through
an independently trusted channel; reading an expected hash from the same
untrusted object is not authentication.

```python
reader = ArtifactStore("/path/to/trusted/local/artifacts", read_only=True)
assert reader.verify_id(independently_retained_artifact_id)
```

These public operations do not create, delete or write files/directories or change
permissions, including on refusal. Ordinary reads may update filesystem access
timestamps. This is an API behavior, not enforced filesystem immutability: other
writers, caller-modified objects and direct private-helper calls are outside this
contract. Symlinks are still followed. Roots, ancestors and concurrent writers
must remain trusted and cooperative. Reads do not constitute an atomic snapshot
or protect against hostile concurrent substitution.

The [measurement example](../examples/measurement-review/README.md) uses this path
for replay with separately retained bundle/input/oracle pins. The
[increment scope](readonly-artifacts-verification.md) keeps its evidence distinct
from earlier acceptance records.

## Trust and persistence limits

- The caller must control the root, all ancestors, and concurrent writers.
  Paths follow symlinks, including roots, object directories, objects and metadata.
  Digest validation only bounds lexical names; it is not filesystem containment
- Default writer construction creates directories and attempts chmod `0700`;
  publication attempts `0444` on files. Permission errors are ignored. File modes
  do not make storage immutable or provide authorization; chmod may affect a
  symlink's target. Use only a dedicated trusted root
- File contents are flushed and fsynced before per-file atomic replacement.
  Object and metadata are separate writes, directories are not fsynced, and
  failed metadata publication may leave an object. This is not a transaction,
  rollback protocol, power-loss guarantee, or durable-recovery implementation
- The re-entrant lock belongs to one store instance. Other instances/processes
  are not coordinated. No cross-process idempotence or race-free metadata claim
  is made; sequential repeats under cooperative use are the tested case
- Metadata is not authenticated, repaired, or comprehensively schema validated.
  Malformed JSON and digest/size mismatches are rejected by `put_bytes`; a valid
  non-object JSON value retains the existing `AttributeError` behavior. Reads and
  verification can succeed even when metadata is corrupt or absent
- `ArtifactRef.validate()` is the preserved lightweight validator, not a strict
  external-input parser. Type annotations are not runtime validation. In
  particular its regex can accept a trailing newline that the store's full
  digest check rejects. Callers must not treat it as a general validation boundary

No symlink, transaction, metadata-shape, or validation hardening is silently
introduced during this extraction. Such changes need separately reviewed
behavior changes and migration tests in the canonical owner.

## Check and migration boundary

The [public example](../examples/canonical-artifacts/README.md) performs real writes/reads
with invented bytes and deliberate corruption. The focused public tests include
success, malformed digests, corrupted bytes/metadata, atomic-write failure cleanup,
retained partial publication, reference identity, and trusted-root limitations.
No test imports another runtime, executes a solver/model/device, or simulates
runtime recovery events. Source tests and isolated installed-wheel checks are
separate evidence, described in [the validation record](canonical-artifacts-verification.md).

Future consumers must alias both store and reference type to this canonical
owner, with fault injection targeting the implementation module. That migration
and its private compatibility material are outside this distribution. Existing
adapters do not start using CAS implicitly. Earlier `0.1.0a1` test reports and
native receipts do not establish acceptance of `0.2.0a0`.

See [ADR 002](decisions/002-canonical-artifact-core.md) and
[attribution and modification scope](PROVENANCE.md).
