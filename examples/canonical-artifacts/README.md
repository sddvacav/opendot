# Synthetic artifact round trip

This example calls the real canonical `ArtifactStore`. It writes an invented JSON
payload, reads it, checks its SHA-256 independently, checks reference/id
verification, and repeats the put. It then deliberately damages a separate
synthetic object and checks rejection on reading and reuse. The main object
remains intact; the demonstration tree intentionally retains the damaged object.

Use Python 3.12+ from the source root, with an existing trusted temporary parent:

```sh
OUTPUT_PARENT=$(mktemp -d /tmp/opendot-artifacts.XXXXXX)
PYTHONPATH=src python -B examples/canonical-artifacts/roundtrip.py \
  --output "$OUTPUT_PARENT/example"
```

After installing a reviewed wheel in a separate environment, the same script
can exercise that installed package from anywhere. Use its absolute script path
and the chosen environment's interpreter:

```sh
/path/to/environment/bin/python -I -B /path/to/source/examples/canonical-artifacts/roundtrip.py \
  --output /path/to/trusted-new-example-directory
```

`--output` must not already exist and its parent must exist. The example emits
JSON to stdout and creates only its new local tree. It does not contact a network,
invoke a model or solver, operate a device, run a runtime, or migrate consumers.
`passed: true` is limited to the listed synthetic storage checks. The installed
package version is reported; exact source commit and wheel bytes must be pinned
in separate validation evidence, not inferred from a version string.

Read the [storage limits](../../docs/canonical-artifacts.md) before using the API.
Unlike source admission, this CAS follows symlinks and trusts the entire root.
