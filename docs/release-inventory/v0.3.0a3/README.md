# OpenDot 0.3.0a3: bounded component and license inventory

This is an additive review supplement for the exact published a3 packet. It does
not replace, edit or re-certify the release assets. It is deliberately a custom
JSON inventory, **not an SPDX/CycloneDX document, full transitive SBOM, security
scan or legal certification**.

## What is verified

- The five release packet files and all 350 regular archive members: 249 full
  source files, 74 packaging-sdist files and 27 wheel files
- The computed source Git tree
  `95ca23d9d36558680c809f2382bef188c6fc2ae4` and the published source manifest
  digest; the merged commit identity comes from the exact release notes
- All 21 wheel Python modules byte-match the corresponding project source
- Wheel RECORD membership, every payload hash and size, metadata, and included
  Apache LICENSE/NOTICE; no default external Python requirements
- Eleven existing external wheels byte-match the source's hash locks; all their
  top-level RECORD payload hashes/sizes and metadata are checked without
  importing or installing those packages
- The CPython 3.12.14/Linux x86_64, no-extras Python distribution dependency
  closure for the three specific build, CI-test and Temporal-CI locks
- Twelve nested setuptools distribution metadata records, three additional
  notice-identified code records, and their visible license/notice file hashes
- Both source-declared optional version recipes and six explicitly excluded
  native/external tool references

The a3 release wheel's SHA-256 remains
`d5e08c8ee38b94b35707ac25f0e8b04fbd4cf46a539542e1e6ab95d19d51ea59`.
See the [exact a3 release](https://github.com/sddvacav/opendot/releases/tag/v0.3.0a3)
and [source commit](https://github.com/sddvacav/opendot/commit/30610de43da81801e7b88517459fbdf0f667ca2d).
Public URLs identify the expected objects; this work checked locally available
bytes and did not independently re-download every public asset or re-attest the
Git commit/tag.

## Files

- `component-inventory.json`: artifact/source member hashes, component identity,
  raw license declarations, notice evidence, scoped relationships and gaps
- `temporal-rust-lock-inventory.json`: the 369 name/version/source/checksum
  entries extracted from the inspected Temporal wheel's Cargo.lock; explicitly
  **not** a list of proven shipped/compiled crates and not license-audited
- `upstream-license-evidence.json`: exact root LICENSE text read from the Bluesky
  1.15.1, ophyd 1.11.2 and event-model 1.24.0 official release tags, with Git blob
  hashes and verified source URLs
- `build_inventory.py`: reproducible read-only generator and exact-byte verifier
- `test_inventory.py`: deterministic positive/refusal controls
- `validation-results.json`: fresh generation/recheck and refusal-test results
- `SHA256SUMS`: supplement file hashes; this file does not hash itself
- `hardening-review.json`: exact pre/post hardening identities and the sole
  inventory JSON change, `/generator/script_sha256`
- `pre-hardening-evidence/`: unchanged earlier files, report, checksums and
  sealed bundle, retained separately for review history and excluded from the
  current delivery archive

## License interpretation

`license_expression_declared` records a package's declaration or a specifically
identified source notice. Legacy license strings and classifiers are retained
separately. `license_concluded` is deliberately null. A root package declaration
is **not** an aggregate license expression for everything inside its wheel.
Source member hashes establish identity, not permission or original authorship.

The inspected setuptools wheel declares MIT but also contains separately
identified LGPLv3, MPL-2.0 and BSD material. It is an external build tool, not
part of OpenDot's runtime wheel. Temporal's external wheel contains a native
bridge plus Rust source/lock records. Package-level MIT does not complete a
license audit of that bridge's compiled dependencies.

The upstream [Bluesky tag LICENSE](https://github.com/bluesky/bluesky/blob/v1.15.1/LICENSE)
confirms BSD-3-Clause despite the release's conflicting PyPI Apache classifier.
This resolves only the root-license declaration. Distribution contents,
additional notices and the whole optional simulation dependency closure remain
outside this review. ophyd and event-model also have exact-tag root-license
evidence. CAD wrapper license statements carried from OpenDot's source guide
are labeled as such, without pretending to inspect those distributions.

The [Gmsh license page](https://gmsh.info/#Licensing) describes GPL version 2 or
later with an additional exception. The [CalculiX project](https://www.dhondt.de/)
links GPL version 2 and documents additional solver dependencies. Neither
native binary nor its linked libraries was inspected here. A separate process
is an execution choice, not automatic GPL clearance.

## Remaining work before claiming a complete SBOM

1. Choose and resolve each actual installation/platform profile, including
   artifact hashes and all relevant optional/transitive packages
2. Map native binary contents, vendored code, generated-code provenance and
   embedded licenses to the actual shipped builds, including Temporal's Rust
   bridge and any CAD/solver stack
3. Inventory the interpreter, OS/system libraries, bootstrap and hosted build
   environment separately where they are part of the intended scope
4. Review exact distribution notices and rights/compatibility obligations;
   retain required notices when those distributions are actually redistributed
5. If a standard SBOM is needed, choose a defined spec version and validate the
   final bounded document with a conforming validator. This custom inventory
   makes no such conformance claim

This helper is for the exact trusted, hash-pinned local inputs described above.
It does not impose generic source-tree, file-size or archive-expansion resource
limits. The added raw-path, all-entry and Unix-type refusals are bounded parser
hardening, not a general archive-security certification. It never extracts archive
contents or runs archive code.

The complete exclusions are machine-readable under `known_gaps`. Empty default
Python requirements do not imply an empty system dependency graph. A recipe's
version pin is not an artifact hash or a proven dependency closure.

## Reproduce without downloads or installation

Prerequisites: an existing Python 3.12 environment with `packaging` 26.3, the
unchanged a3 full source tree and five-file packet, the existing ten locked
CI/Temporal wheels, and the separately pinned setuptools 84.0.0 wheel. No code is loaded from the inspected wheels, and no native backend, service,
model or provider is invoked. Existing installed `packaging` 26.3 is deliberately
imported as inventory tooling. The JSON field
`generator.inventoried_package_code_imported: false` means no code is imported
from the inspected archive inputs; it does not deny use of that installed
`packaging` tool.
The supplied generator version is identified by its own SHA-256; its tool fields
record the actual Python and packaging versions used.

```sh
python -I -B build_inventory.py verify \
  --source "$SOURCE_DIR" \
  --dist "$RELEASE_PACKET_DIR" \
  --test-wheelhouse "$EXISTING_CI_TEMPORAL_WHEELHOUSE" \
  --build-wheelhouse "$EXISTING_BUILD_WHEELHOUSE" \
  --upstream-evidence upstream-license-evidence.json \
  --output .
python -I -B test_inventory.py
```

`generate` uses the same arguments and writes only the two inventory JSON files
to the selected output directory. `verify` recomputes from the supplied inputs
and requires exact output-byte equality. The verifier intentionally rejects a
changed source tree, unexpected packet membership, missing hash-locked wheel,
changed declared dependency closure, RECORD mismatch or changed inventory. It
does not execute package source, resolve dependencies online or run a legal
analysis. Do not use a future successful run to transfer a3 evidence to a
changed release.
