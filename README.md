# OpenDot Engineering

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/brand/opendot-readme-banner-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="assets/brand/opendot-readme-banner-light.svg">
  <img alt="OpenDot" src="assets/brand/opendot-readme-banner-light.svg" width="1280" height="360">
</picture>

[简体中文](README.zh-CN.md) · [Install and run](docs/installed-quickstart.md) · [Capabilities](CAPABILITIES.md) · [Architecture](docs/architecture.md)

Run a declared Python tool, inspect its acceptance result, and retrieve the exact bytes it produced. OpenDot Engineering brings local callable execution, hash-addressed artifacts, evidence checks, and controlled Git workspaces into one package for developers and research engineers.

**0.2.0a6 ALPHA prerelease is available.** [Download](https://github.com/sddvacav/opendot/releases/tag/v0.2.0a6) · [Install](docs/installed-quickstart.md) · [Repository](https://github.com/sddvacav/opendot) · [Issues](https://github.com/sddvacav/opendot/issues)

The [tagged source](https://github.com/sddvacav/opendot/commit/965ed8c49c47d7b79716ba1843462b84ff21a27f) passed [1,183 portable CI checks](https://github.com/sddvacav/opendot/actions/runs/36885554336), with 49 subtests reported separately. This is an experimental, non-production-ready toolkit; the checks do not establish scientific acceptance.

These `main`-branch docs are ahead of the release. Published assets remain bound to the tagged source and its original README metadata; rebuilding `main` would change that metadata. [Version-bound evidence and limitations](CAPABILITIES.md) retain the historical test ledgers.

## Run the synthetic examples

The first example needs Python 3.12+ and no optional packages. From the source root on a tested Linux/POSIX setup, use a fresh output under a trusted directory outside the checkout:

```sh
OUTPUT_PARENT=$(mktemp -d /tmp/opendot-composition.XXXXXX)
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -B \
  examples/callable-artifacts/demo.py --output "$OUTPUT_PARENT/result"
```

The JSON should report `synthetic_software_assertions_passed: true` and show three outcomes:

- **COMPLETED:** a permitted tool writes an artifact; its bytes and SHA-256 match the returned reference
- **FAILED:** semantic validation rejects a result; its intact, unaccepted artifact remains visible
- **BLOCKED:** missing permission prevents the handler from running

These are deliberate synthetic software cases. The artifact store follows symlinks and needs trusted roots; failed validation does not roll back effects. Use a new output path for each run. If this script reports `--output already exists` (exit 2), keep the earlier result and choose a fresh path. [Understand the example](examples/callable-artifacts/README.md)

**Installing a wheel instead?** Follow the [complete installed quickstart](docs/installed-quickstart.md), including how to copy the matching examples and verify installed imports. Wheels contain the package; examples remain source material.

For a CSV-to-summary walkthrough, start with the [synthetic measurement review](examples/measurement-review/README.md): run valid, wrong-mean and denied cases, locate retained result bytes, verify them, and handle an existing output path.

For six bounded evidence/source/trajectory cases, see the [source-boundary example](examples/source-boundary/README.md) and its [historical research context](docs/research/demand-gap-20261001/README.md).

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
| Describe and explicitly validate agent metadata | [Agent contracts API](docs/agent-contracts.md) · [Metadata example](examples/agent-contracts/README.md) |
| Execute a callable with declared permissions and validation | [Callable API](docs/callable-execution.md) |
| Store and verify local bytes with one canonical reference type | [Artifact API](docs/canonical-artifacts.md) |
| Create separate local working copies and inspect changes | [Git workspace example](examples/git-workspaces/README.md) |
| Check pinned sources or invented qualification records | [Source audit](docs/local-source-audit.md) · [Qualification checks](docs/synthetic-lab-qualification.md) |
| Load explicitly reviewed local Python modules | [Source admission](docs/source-admission.md) |
| Run a finite fake-instrument experiment | [Simulated lab](docs/simulated-lab.md) |
| Explore bounded geometry, mesh, thermal and beam contracts | [CAD/CAE guide](examples/cad_cae/README.md) |

The Git API exposes only **create/status/diff**, requires trusted cooperative POSIX repositories and trusted system **Git 2.52.0+**, and refuses unsupported features. Its diff covers tracked unstaged changes; it does not commit, remove, or synchronize repositories. [Compatibility and ownership rules](docs/git-workspaces.md)

Default installation has no required runtime Python dependencies. Optional simulation and native CAD/CAE execution use separately prepared dependencies. Several evidence APIs need POSIX file operations; Linux is the reviewed environment. One distribution, `opendot-engineering`, provides the `opendot_engineering` namespace, with Python APIs and module entrypoints rather than a registered console command.

## Direction

OpenDot's longer-term goal is to turn science and engineering tasks into reviewable deliverables, with explicit decisions, recoverable progress, and measured resource use. The next milestone is one independently reproducible end-to-end workflow. [Dated public-source research](docs/research/README.md) and the [priority map](RESEARCH-MAP.md) explain the proposed direction without treating it as completed functionality or institutional endorsement.

## Project information

[Version overview](OVERVIEW.md) · [Changelog](CHANGELOG.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [Support](SUPPORT.md) · [Release gates](docs/release-checklist.md)

Original project code is [Apache-2.0](LICENSE); see [NOTICE](NOTICE) and the separate [artwork notice](assets/brand/NOTICE). Optional dependencies retain their own obligations. Public usage questions and synthetic bug reports belong in [GitHub Issues](https://github.com/sddvacav/opendot/issues). Do not post confidential or security-sensitive details; see [Security](SECURITY.md). No response SLA is promised.
