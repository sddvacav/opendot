# Local evidence inspector

A dependency-free, read-only presentation of the fixed public Temporal batch
projection. This directory is a separate presentation allowance, not an expansion
of ADR 004, the Python runtime, scheduling, storage, or verification authority.
It does not create or modify a Site. Existing license and brand notices apply.

## Open locally

Open `index.html` from this directory in a browser that supports local classic
scripts and Web Crypto SHA-256. Keep `viewer.js` and `viewer.css` beside it.
The intended URL is `file://`; no server, build, dependency installation, account,
or Internet access is needed. If a browser or managed environment refuses local
files or SHA-256, stop and report the limitation. Do not disable browser security,
use file-access bypass flags, or treat another delivery method as preapproved.

Select all eight JSON files from **one already extracted public bundle** using
the file picker. No ZIP extraction is implemented. A raw audit directory, extra
files, duplicate names, and partial selections are refused. The file picker
allows replacement selections and Reset at any point.

The supported public contract is `opendot.temporal.real-batch.public-bundle.v1`:

| File | Maximum bytes |
| --- | ---: |
| `manifest.json` | 16,384 |
| `environment.json` | 65,536 |
| `batch-trace.json` | 5,242,880 |
| `batch-metadata.json` | 262,144 |
| `batch-histories.json` | 4,194,304 |
| `batch-outcomes.json` | 262,144 |
| `batch-cleanup.json` | 65,536 |
| `batch-summary.json` | 65,536 |

The aggregate ceiling is 10 MiB. Exact filenames, schemas, manifest fields, and
per-file byte counts are required. SHA-256 is calculated over the original selected
bytes, not parsed or reserialized JSON. All seven data files must match the supplied
manifest before any bundle data appears. The manifest itself has no independent
trust anchor.

## Read the result correctly

- **Selected bytes match supplied manifest** means byte consistency only. It
  does not authenticate the source or run, validate semantics, establish a
  scientific pass, or independently replay original CAS receipts/raw history.
- Delivery, cleanup, semantic validity, overlap and peaks are explicitly **reported
  assertions**. The browser does not reproduce the Python verifier's acceptance
  logic. Use the existing `ci/verify_temporal_server_gate.py` public-bundle recheck
  described in [batch qualification](../temporal-batch-qualification.md) for the
  authoritative projection-consistency check against the reviewed source.
  Even that recheck does not independently authenticate hosted assertions or
  replay omitted originals.
- A real-profile bundle presents the exact ordered 200-job plan. The ledger
  can filter cohorts without changing the loaded evidence. Missing/null fields
  remain distinct from zero and false. Missing or repeated interval endpoints
  produce no duration. Activity and handler duration are observed endpoint
  differences, not server-only queue time or wall-clock measurements.
- Trace rows must have contiguous sequence and nondecreasing integer elapsed
  microseconds for presentation. Equal timestamps retain sequence order. The
  detail panel shows one job's bounded event list, not an invented interpolation.
- Activity overlap and handler overlap are separate supplied quantities. Neither
  implies CPU parallelism, speedup, fairness, a multi-host result, or agent count.
- `FABRICATED_UNIT_DATA` bundles always carry a synthetic/unverified label. The
  built-in **three-job synthetic demo** is separate from bundle import: it performs
  no hashing and supplies no successful acceptance values. Its artificial equal
  timestamps and missing endpoints illustrate presentation only. It is not a
  complete 200-job run and cannot be exported as one.

## Local boundary and limits

The page has a fixed Content Security Policy and no automatic network requests,
external assets, providers, runtime controls, uploads, executable input links,
HTML interpretation, persistence APIs, or new Python owner. Even the recorded
workflow URL is text, not a generated link. Only fixed allowlisted values are
rendered with text nodes; unsupported values are labelled without echoing them.

Reads are sequential and capped with `File.slice(0, limit + 1)`. There is at most
one active read/hash chain and one coalesced latest pending selection. Replacement,
Reset, and Demo invalidate the active generation immediately; stale completion
cannot repaint the view. An in-flight browser read/hash may finish before its
memory is reclaimed, but no later files from that invalidated selection are read.
Reset clears the page's data references and file input; it is not secure erasure
of browser, operating-system, or developer-tool memory.

Strict bounded JSON parsing rejects duplicate/poison keys, excessive depth,
strings, array/object sizes, and nonfinite or overlarge numeric values. These are
presentation guards, not a security certification, hostile-filesystem guarantee,
constant-memory guarantee, or substitute for the existing Python recheck.
Unknown/nonpublic data must not be selected. Byte caps do not establish provenance.

## Separate qualification

From the repository root, with a preinstalled modern Node (qualified locally
with Node 24):

```sh
node --test tests/test_evidence_viewer.cjs
```

This uses only built-in Node modules. It neither installs packages nor runs a
Python, Temporal, service, provider, or scientific acceptance test. Keep these
counts separate from the existing portable/Python manifests. The tests include
synthetic file hashing/size checks, malformed input, explicit missing/null values,
equal timestamps, 200-row presentation, read bounds, replacement/reset races,
coalescing, and a minimal text-only DOM harness. A DOM harness is not browser QA.

Before merge, release, or visual acceptance, verify the **final exact files** in a supported browser:

1. Desktop and narrow mobile viewport: empty, loaded, malformed-selection, demo,
   reset and replacement states; no clipped instructions or inaccessible controls
2. Keyboard-only file selection, buttons, cohort filter, ledger scrolling and job
   detail focus; visible focus ring and meaningful table headers/captions
3. 200% zoom: readable reflow with intentional table scrolling, no page overflow
4. Equal timestamp ordering, missing/null display, synthetic warnings, and
   separately labelled Activity/handler overlap
5. No unwanted requests, console errors, or stale data after Reset or fast reselection

Current preparation: 30/30 Node tests passed; independent review is separate.
Browser visual, accessibility, and network QA is **NOT_RUN** because managed-browser
access restrictions prevented the review. Node and DOM checks do not qualify those
behaviors. This source is available for draft review only; merge, release, and visual
acceptance remain blocked until the authorized browser checklist above is completed.
