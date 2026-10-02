# OpenDot Engineering

## Current 0.3.0a4 experimental prerelease

**ALPHA / NOT_SCORED; [published experimental prerelease](https://github.com/sddvacav/opendot/releases/tag/v0.3.0a4).**
The accepted release source is commit `2d16190a8121410bbeea252869b196f7891e1696`.
The release includes the optional [offline A2A worker-turn adapter](docs/a2a-worker-turn.md),
matching source examples and version-bound installation instructions. Default runtime
dependencies remain empty. Use the [a4 installed guide](docs/installed-quickstart.md)
with the independently reviewed checksum-manifest pin on the [release page](https://github.com/sddvacav/opendot/releases/tag/v0.3.0a4).
Exact artifact identities and separately scoped qualification are recorded in the
[released notes](https://github.com/sddvacav/opendot/releases/download/v0.3.0a4/RELEASE-NOTES.md).

- Installed wheel: one dependency-free callable/artifact result, bounded reads,
  read-only help and copied lightweight public fixtures; no source imports
- Matching complete source: [measurement comparison](examples/measurement-review/README.md)
  uses `PYTHONPATH=src` and verifies canonical import origins in that same source;
  it is not an installed-wheel workflow
- [CAD/thermal plan](examples/cad_cae/README.md) is metadata-only `NOT_EXECUTED`.
  Fabricated contract checks do not establish native execution. Native CAD/Gmsh/
  CalculiX is `NOT_RUN`; physical validation `NOT_PERFORMED`, independent review
  `NOT_EVALUATED`, mesh independence `NOT_ESTABLISHED`
- A2A uses at most one externally supplied callback and returns an `UNACCEPTED`
  candidate; its external live gate is `NOT_RUN`. No included transport, provider,
  model, autonomous-agent or native-agent qualification is claimed
- Source-only Temporal batch tools and historical hosted runs retain their own
  evidence scopes; this candidate performs no fresh service run. The historical
  [a3 component inventory](docs/release-inventory/v0.3.0a3/README.md) is a3-only,
  not an a4 SBOM. Scientific and device authority remain false; UI changes are excluded

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/brand/opendot-readme-banner-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="assets/brand/opendot-readme-banner-light.svg">
  <img alt="OpenDot" src="assets/brand/opendot-readme-banner-light.svg" width="1280">
</picture>

[简体中文](README.zh-CN.md) · [Install](docs/installed-quickstart.md) · [First result](#run-the-synthetic-examples) · [Capabilities](CAPABILITIES.md) · [Contribute](CONTRIBUTING.md)

OpenDot Engineering is a Python toolkit for local tool execution and inspectable results. Run a function with declared permissions and a validator, store its output by SHA-256, and check the saved bytes separately from whether the result was accepted.

Use it to prototype reviewable developer and research-engineering workflows: connect a callable to an artifact, review a synthetic measurement summary, or create a controlled local Git working copy. Start with the small example below, then explore the [APIs and examples](#explore-the-package).

**Synthetic result preview** · [Run it and verify the saved output](examples/measurement-review/README.md#preview-a-checked-synthetic-result)

`A.mean=2.0` · `B.mean=4.0` · exact difference `2/1` · tolerance `2/1` (all `au`)  
`CHECKED` · `within_tolerance=true`

`summary.txt` is the human view; `report.json` records `summary.conditions`,
`comparison` and `status`. This source-only example uses six invented rows, not
experimental data; it is not an installed-wheel API. `CHECKED` means arithmetic checked,
even for an outside-tolerance result, not scientific acceptance. All results keep
`scientific_accepted=false`, `device_control_authorized=false` and
`independent_review="NOT_EVALUATED"`.

**Historical experimental alpha · 0.3.0a3 · NOT_SCORED.** The [0.3.0a3 ALPHA prerelease](https://github.com/sddvacav/opendot/releases/tag/v0.3.0a3) is available. Follow the [exact-asset installation guide](https://github.com/sddvacav/opendot/blob/8d5d8667d65734fb5c40fa0526709a3159b7f165/docs/installed-quickstart.md) for the released wheel, matching source examples and SHA-256 checks. Python 3.12+ is required; the default package has no runtime Python dependencies. Linux is the reviewed environment.

**New in the a3 assets:** opt-in [bounded artifact acquisition](docs/canonical-artifacts.md#optional-bounded-retrieval-unreleased-source-increment) with `get_bytes(..., max_bytes=N)`, plus [pure finite-batch preparation](docs/temporal-batch-qualification.md) in the full source. A bounded read acquires at most N+1 actual object bytes to detect excess; omitted/`None` retains whole-read behavior. The batch fixtures model 200 fixed synthetic jobs, 16 outstanding reservations/workflows and eight external Activity slots/executor workers. They do not demonstrate an actual 200-job service run, agent count, throughput or a production scheduler. Earlier “unreleased” labels in the linked API notes are source checkpoints; the pinned a3 wheel includes the bounded-read API.

**Retained from [0.3.0a2](https://github.com/sddvacav/opendot/releases/tag/v0.3.0a2):** the [Gmsh file-size-limit repair](docs/gmsh-cpu-ceiling.md) and [optional bounded Temporal transport](docs/temporal-reference-transport.md). The default install remains dependency-free; the Temporal extra needs separately approved dependencies and never starts a server automatically. The unchanged v0.3.0a1 assets contain neither addition; their [historical installation guide](https://github.com/sddvacav/opendot/blob/359f781a5aa1650ae92b1af81cf369a17c444045/docs/installed-quickstart.md) preserves the original pins.

The historical a3 paragraphs above describe the frozen a3 assets.
Later `main` changes and CI do not alter or qualify that package; its batch
content remains pure preparation only.

## Run the synthetic examples

From a source checkout, this standard-library example writes and checks a small text artifact. It needs no model, service or native solver. On Linux/POSIX with Python 3.12+, run from the source root and use a fresh output under a trusted directory outside the checkout:

```sh
OUTPUT_PARENT=$(mktemp -d /tmp/opendot-composition.XXXXXX)
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -B \
  examples/callable-artifacts/demo.py --output "$OUTPUT_PARENT/result"
```

Look for `synthetic_software_assertions_passed: true` in the printed JSON. It includes three outcomes:

- **COMPLETED:** a permitted tool writes an artifact; its bytes and SHA-256 match the returned reference
- **FAILED:** semantic validation rejects a result; its intact, unaccepted artifact remains visible
- **BLOCKED:** missing permission prevents the handler from running

Inspect `success.returned_ref` for the artifact reference and `success.independent_sha256_matches` for the byte check. Results stay under `$OUTPUT_PARENT/result`. These are synthetic software cases, not scientific acceptance. The artifact store follows symlinks and needs trusted roots; failed validation does not roll back effects. If the script reports `--output already exists` (exit 2), keep the earlier result and choose a fresh path. [Understand the example](examples/callable-artifacts/README.md)

**Installing a wheel instead?** Follow the [complete installed quickstart](docs/installed-quickstart.md), including how to copy the matching examples and verify installed imports. Wheels contain the package; examples remain source material.

For a CSV-to-summary walkthrough, start with the [synthetic measurement review](examples/measurement-review/README.md): run valid, wrong-mean and denied cases, locate retained result bytes, verify them, and handle an existing output path.

For synthetic checks of conflicting source claims, see the [source-boundary example](examples/source-boundary/README.md) and its [historical research context](docs/research/demand-gap-20261001/README.md).

## Package help and version

From the source root:

```sh
PYTHONPATH=src python -B -m opendot_engineering --help
PYTHONPATH=src python -B -m opendot_engineering --version
```

This read-only module entrypoint prints static guidance or the imported package's
code version. It starts no runtime, dispatches no tools and loads no optional
backends. For installed commands and option details, see [package help](docs/module-cli.md).

## Explore the package

| What you want to do | Start here |
| --- | --- |
| Execute a callable with declared permissions and validation | [Callable API](docs/callable-execution.md) |
| Store and verify local bytes with one canonical reference type | [Artifact API](docs/canonical-artifacts.md) |
| Create separate local working copies and inspect changes | [Git workspace example](examples/git-workspaces/README.md) |
| Describe and explicitly validate agent metadata | [Agent contracts API](docs/agent-contracts.md) · [Metadata example](examples/agent-contracts/README.md) |
| Check pinned sources or invented qualification records | [Source audit](docs/local-source-audit.md) · [Qualification checks](docs/synthetic-lab-qualification.md) |
| Load explicitly reviewed local Python modules | [Source admission](docs/source-admission.md) |
| Run a finite fake-instrument experiment | [Simulated lab](docs/simulated-lab.md) |
| Explore bounded geometry, mesh, thermal and beam contracts | [CAD/CAE guide](examples/cad_cae/README.md) |

The Git API exposes only **create/status/diff**, requires trusted cooperative POSIX repositories and trusted system **Git 2.52.0+**, and refuses unsupported features. Its diff covers tracked unstaged changes; it does not commit, remove, or synchronize repositories. [Compatibility and ownership rules](docs/git-workspaces.md)

Optional simulation and native CAD/CAE execution need separately prepared dependencies. Several evidence APIs require POSIX file operations. The `opendot-engineering` distribution provides the `opendot_engineering` namespace, with Python APIs and module entrypoints rather than a registered console command. See the [architecture](docs/architecture.md) for module boundaries.

## Status and evidence

This package supports trusted local workflows. Autonomous model-driven agents, durable recovery, multi-host operation and hundreds-of-agent performance are not implemented or demonstrated here. Declared permissions and budgets are not an OS sandbox; stored-byte integrity does not confer scientific or device-control authority.

For current release evidence and precise scope, see the [capability and evidence ledger](CAPABILITIES.md), [structural verification v2](docs/structural-default-v2.md), and [historical 0.3.0a1 verification](docs/structural-v2-candidate-verification.md). Earlier [a4 checks](docs/verifier-ci-verification.md) and [build-repeatability records](docs/build-toolchain.md) remain tied to their own versions; they do not accept new source or release artifacts.

## Direction

OpenDot's longer-term goal is to turn science and engineering tasks into reviewable deliverables, with explicit decisions, recoverable progress, and measured resource use. The next milestone is one independently reproducible end-to-end workflow. [Dated public-source research](docs/research/README.md) and the [priority map](RESEARCH-MAP.md) explain the proposed direction without treating it as completed functionality or institutional endorsement.

## Contribute

Good starting points are clearer documentation, a minimal synthetic example, or a narrowly scoped adapter test. Read [Contributing](CONTRIBUTING.md) for the supported scope and selected checks, then use [GitHub Issues](https://github.com/sddvacav/opendot/issues) for a non-sensitive proposal or reproducible bug report. See [Security](SECURITY.md) before sharing sensitive details.

## Project information

[Version overview](OVERVIEW.md) · [Changelog](CHANGELOG.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [Support](SUPPORT.md) · [Release gates](docs/release-checklist.md)

Original project code is [Apache-2.0](LICENSE); see [NOTICE](NOTICE) and the separate [artwork notice](assets/brand/NOTICE). Optional dependencies retain their own obligations. No response SLA is promised.
