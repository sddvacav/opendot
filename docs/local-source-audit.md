# Local source audit

This is a small, standard-library adapter for a read-only, operator-pinned local
evidence packet. It verifies source identity, byte integrity, exact observation
locators, declared access categories, and role consistency. It does not execute
a research pipeline or decide whether a scientific claim is true.

`audit_accepted: true` and `scientific_accepted: false` are deliberately separate.
A source-declared measurement is not independently authenticated by this audit.

## Run the public synthetic example

From the repository root, using Python 3.12 or newer on a POSIX system supporting
descriptor-relative `O_NOFOLLOW` reads:

```sh
PYTHONPATH=src python -m opendot_engineering.adapters.source_audit \
  --root examples/source-audit \
  --manifest manifest.json \
  --expected-revision aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
  --expected-manifest-sha256 f4d81f12c83b7f222931348677b01b6f27df8905513cfbaebac3cf86cbfe26ae \
  --audience public
```

The `a...a` revision is an explicitly synthetic fixture identifier, not a claim
that this Git commit exists. Both observations are marked synthetic. The second
value and its uncertainty remain `null`; the adapter never substitutes zero.
The output contains provenance and role metadata, not property values or source
text. No input or output files are created by the adapter. The caller may capture
stdout into its existing private artifact store.

For actual work, supply an authorized local root and obtain **both expected pins
from independently reviewed operator configuration**. Computing the expected
manifest hash from an untrusted packet immediately before using it is not an
independent trust check. The manifest is trusted to bind snapshot bytes to the
declared revision. Matching a Git blob hash does **not** prove commit membership,
source authorship, physical measurement, licensing, or scientific acceptance.

## Contract

The example files are the executable schema reference. Unknown fields are
rejected rather than silently interpreted as authority.

- Manifest: schema, source revision, access, nonempty sources and claims
- Source registration: source ID, relative path, revision, SHA-256, Git blob
  SHA-1, and access
- Local evidence document: schema, source ID, source revision, access,
  content kind (`synthetic` or `reported`), and observations
- Observation: quantity, unit, condition, evidence role, value state, value,
  uncertainty, and reason
- Claim: claim ID, source ID, exact `/observations/N` JSON pointer, expected
  evidence role, value state, quantity, and unit

Evidence roles are `synthetic`, `measured`, `model_prediction`,
`literature_prior`, and `posthoc_diagnostic`. Value states are `known`,
`unknown`, and `censored`. Known values must be finite numbers, not booleans or
numeric strings. Unknown and censored values must retain `null` for value and
uncertainty and give a reason. Known uncertainty may be a nonnegative finite
number or `null`; missing uncertainty does not imply zero. This version does not
encode censoring bounds, make unit conversions, or aggregate observations.

Each claim must match its bound source observation exactly in role, state,
quantity and unit. A synthetic observation cannot be presented as measured,
and a prediction, literature prior, or post-hoc diagnostic cannot be relabeled
as a measurement by the manifest. Changing both the source and its independent
operator pin is a new trust decision, not something this validator can prevent.

`public` and `private` are the only access categories. A public audience requires
a public manifest and public sources, and source-document access must match the
registration. The adapter verifies these declarations; it is not a content
classifier and cannot discover falsely labeled confidential material. Keep
private inputs and receipts outside public source trees and use private audience
explicitly in the calling mission.

## Safety boundary

- Only regular local files beneath the operator root are read
- Absolute paths, traversal, backslash/drive/URL paths and symlinks are rejected
- Root and source paths are walked using directory descriptors and `O_NOFOLLOW`
- Duplicate JSON keys, nonfinite constants, missing fields, unknown fields,
  duplicate IDs, absent locators, unused sources and hash mismatches are rejected
- Limits: 256 KiB manifest, 2 MiB per source, 32 sources, 256 claims and at most
  256 observations per source
- No network, subprocess, dependency installation, dynamic source import,
  database write, training, solver, or physical-device operation
- No new evidence graph, content-addressed store, scheduler, or runtime owner

Errors use bounded codes and do not echo input text or filesystem paths. CLI
success exits 0; rejection exits 2 and writes a small JSON error to stderr.
Unsupported platforms fail closed instead of falling back to unsafe path reads.

## Standalone integration boundary

This adapter uses its own small source/claim/locator contract. It does not copy
or require another evidence package. A later consumer may translate authorized,
reviewed metadata into its own schema, preserving source identity, evidence role,
access labels, and explicit unknown/censored values. Never invent missing
metadata or treat a retrieval score as a scientific decision gate.

Any future reuse of third-party implementation requires its applicable license
and attribution review. This source-only cut includes no such implementation.
A consumer remains responsible for storage, access control, and independent
review; this validator does not provide those services.

## Verify

```sh
PYTHONPATH=src python -m pytest tests/test_source_audit.py -q
PYTHONPATH=src python -m pytest -q
```

Tests use synthetic packets only. They cover happy path, repeatability,
unknown/censored preservation, malformed JSON, unsafe paths and symlinks,
wrong pins, role promotion, access mismatches, import isolation and CLI errors.
Passing software tests does not establish scientific validity, execution on a
workstation, multi-host operation, or a complete upstream integration.
