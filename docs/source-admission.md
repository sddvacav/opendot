# Optional operator-reviewed source admission

`opendot_engineering.adapters.source_admission.SourceLock` is an optional Python
API for trusted, cooperative local source. It is not a CLI, a runtime, an
execution-authorization service, or a sandbox. Importing the adapter does not
load operator source. No default root, backend, manifest, source revision, source
pin, or export profile is supplied.

## Explicit startup configuration

The operator supplies all three inputs:

1. An approved absolute source root
2. A relative path to a reviewed source-lock manifest inside that root
3. The manifest's SHA-256 obtained through an independently trusted review

```python
from opendot_engineering.adapters.source_admission import SourceLock

lock = SourceLock(
    approved_root=operator_approved_absolute_root,
    manifest=operator_reviewed_relative_manifest,
    expected_manifest_sha256=independently_reviewed_manifest_sha256,
)
source = lock.load()
original_object = source.exports[operator_selected_export]
```

This is a configuration sketch, not a runnable bundled backend example. Never
populate these values from prompts, tasks, remote requests, source
self-description, adjacent untrusted checksum files, or automatic discovery.
Hashing the supplied manifest itself does not create an independent trust root.
The [manifest schema](source-lock-schema.md) defines the explicit ordered module
list, exact byte pins, export bindings, and bounded input policy.

## What the adapter checks

- Reuses the canonical source-audit descriptor-relative, no-symlink, bounded
  regular-file reads; supported POSIX APIs are required
- Rejects unknown fields, wrong types, duplicate JSON keys, module names/paths,
  nonfinite values, invalid path text, and excessive sizes or JSON structure
- Captures and verifies every module byte string before any execution, then
  precompiles that snapshot without inheriting adapter compiler flags
- Loads the reviewed flat module list in its declared dependency order, under
  a synthetic namespace with an empty package search path
- Does not execute the original package initializer; standard relative imports
  can use previously loaded listed siblings, but forward initialization imports,
  subpackages, implicit modules, and package resources are unsupported
- Binds cache identity to the approved root, exact manifest digest, and ordered
  module names, paths, and pins; rechecks every input hash on every load call
- Rejects foreign namespace collisions and returns unchanged named attributes
  from each module's own dictionary, with no inferred roles or behavior wrappers

`AdmittedSource` exposes its namespace, manifest digest, read-only module-digest,
module and export mappings, and a `provenance()` receipt. Read-only mappings do
not make the exported modules or values immutable. Receipts keep
`account_authorization`, `license_permission`, and `scientific_acceptance` at
`NOT_EVALUATED` and `sandbox` at `false`.

## Execution, failure, and retry limits

Pins establish captured byte identity only. They do not authenticate an account,
prove authorization or redistribution rights, validate scientific results, or
establish complete executable-code identity. Reviewed Python executes with the
current process's normal authority. Absolute imports, third-party dependencies,
file/network/process effects, and runtime object mutation are ordinary Python
behavior. The interpreter, import hooks, dependencies, and absolute imports are
not pinned or isolated. Do not use this API to run untrusted code.

Namespace ownership checks are cooperative bookkeeping, not a defense against
hostile code or interpreter mutation. A failed load removes only namespace
objects still identical to those created by that attempt. Foreign replacements
and external effects are not removed or rolled back. A later call may execute
source again after an earlier failure. Do not automatically retry a failed load:
first reconcile external effects and inspect the failure under the caller's own
reviewed recovery policy. No such recovery policy or runtime is supplied here.

Admission validation uses bounded `SourceAdmissionError` codes; the exception is
an alias of the existing source-audit rejection type. Python syntax/execution
exceptions propagate unchanged and may expose paths or source details. Keep
raw exceptions, diagnostics, and receipts private until separately reviewed.

## Scope and validation

Executable examples are original synthetic fixtures authored in
`tests/test_source_admission.py`, created outside the source tree during testing.
No external source, backend implementation, runtime, or research data is bundled
or exercised. Existing source owners retain responsibility for their behavior;
consumer compatibility requires its own tests. No new runtime dependency is
added. See [integration checks](source-admission-verification.md),
[the scope decision](decisions/001-source-admission.md), and
[Apache attribution](PROVENANCE.md).
