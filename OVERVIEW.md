# OpenDot Engineering release overview

[简体中文](OVERVIEW.zh-CN.md) · [Capabilities and evidence](CAPABILITIES.md) · [Research and priorities](RESEARCH-MAP.md)

**Version 0.3.0a2 · Experimental alpha · Evidence snapshot 2 October 2026**

OpenDot Engineering provides a small, inspectable foundation for local engineering work: run a declared Python tool, inspect its acceptance result, store the output by its byte hash, and create controlled Git workspaces for separate tasks. The package is designed for developers and research engineers who need to examine what ran, what it produced, and which checks actually passed.

**Experimental alpha: 0.3.0a2; NOT_SCORED.** This version
integrates [structural default verification v2](docs/structural-default-v2.md):
conditional per-element energy consistency, schema 2 and explicit historical
`artifact_v1` compatibility. Scientific acceptance remains false. The source-boundary
example covers seven original synthetic protocols, eight unimplemented proposals,
and six separately counted synthetic parameter fixtures; no production policy is added.
Canonical execution/reference owners and optional energy-API results are unchanged.
The [Gmsh resource-limit setup](docs/gmsh-cpu-ceiling.md) preserves inherited lower
CPU and per-file ceilings; fake-resource checks do not establish native/kernel enforcement.
The file-size repair and [optional bounded Temporal transport](docs/temporal-reference-transport.md)
are packaged in 0.3.0a2. The unchanged v0.3.0a1 assets contain neither addition
and retain their original hashes.
[Historical 0.3.0a1 verification scope](docs/structural-v2-candidate-verification.md)

The [0.3.0a2 ALPHA prerelease](https://github.com/sddvacav/opendot/releases/tag/v0.3.0a2) is available. Follow the [version-pinned installation guide](docs/installed-quickstart.md) for its exact wheel, matching source examples and SHA-256 checks. The [historical 0.3.0a1 installation guide](https://github.com/sddvacav/opendot/blob/359f781a5aa1650ae92b1af81cf369a17c444045/docs/installed-quickstart.md) and [historical a6 installation guide](https://github.com/sddvacav/opendot/blob/eec73193594ee212ba091a9d7310c8762a4b0003/docs/installed-quickstart.md) retain their separate version-specific pins; earlier-version results do not accept these artifacts.

The historical a4 candidate requires an unambiguous single CalculiX 2.23 version declaration in logs checked by the shared thermal/structural gate. It adds a source-only documentation checker for bounded local links, fragments and HTML anchors, plus exactly eight nonempty, literal-identical shell blocks in each installed-guide language. The build backend is pinned to setuptools 84.0.0. These changes add no physics model, runtime, native execution or public release. See the [historical a4 verification record](docs/verifier-ci-verification.md), [documentation-checking boundary](docs/documentation-checks.md), and [build profile](docs/build-toolchain.md).

Historical evidence remains version-bound: the **0.2.0a1** Git repair candidate passed **773 selected author checks**. Its inaccessible-residue fix passed an independent source-level permission-loss reproduction; see the [repair record](docs/git-workspaces-residue-fix.md). The **0.2.0a0** callable/artifact integration separately passed **695 independently rerun portable checks**. These results do not establish a test total or independent acceptance for **0.3.0a2**, a full-platform rating, or a public release.

**Historical a4 author source checks: 1,066 passed**, with zero failures/errors/skips. **Exact final artifact and installed acceptance require their own delivery receipt.** Independent component results overlap and must not be added to that aggregate. The historical a4 portable CI definition selected 988 cases and omitted the 78 controlled-Git cases; that record did not establish a hosted run. Current 0.3.0a2 hosted runs are separately linked in [Capabilities](CAPABILITIES.md).

Historical **0.2.0a3** source checks passed **899** cases with zero failures/errors/skips. Its final `a59419b` receipt covered fresh installed journeys through all eight shell blocks per language; two clean build environments on the same host reproduced its exact wheel. Those results and any predecessor score do not transfer to this candidate. The [earlier development record](docs/parallel-development-verification.md) describes host-coordinated work, not an autonomous scheduler. Historical 0.2.0a2 author checks passed 805 selected source tests; its independent metadata review passed 410 cases on source and the same 410 on its installed wheel. These remain predecessor evidence.

## What you can inspect today

### Agent metadata with explicit validation

The [agent contracts API](docs/agent-contracts.md) provides `Capability` and `AgentManifest` as metadata-only contracts. Call `.validate()` explicitly to check a declaration; creating a contract does not start an agent. The [metadata example](examples/agent-contracts/README.md) shows this boundary. Declared budgets and permissions do not allocate resources, authorize tool calls, or add execution enforcement.

### A tool result with an explicit acceptance outcome

The [callable and artifact example](examples/callable-artifacts/README.md) runs a permitted Python function, stores synthetic output, returns a canonical artifact reference, and verifies the stored bytes independently. It also shows two important failure cases: a missing permission blocks the handler, while a semantic rejection can leave an intact but unaccepted artifact behind.

That distinction matters. A file can be stored correctly even when its contents fail the task's acceptance test. OpenDot keeps byte integrity, tool status, and semantic acceptance separate. The example does not claim scientific validation or roll back effects after failure.

### Separate local working copies with a fixed starting commit

The [Git workspace profile](docs/git-workspaces.md) exposes only **create, status, and diff**. Creation resolves the selected local ref once to a full commit ID. Later observations check that the worktree still belongs to the same live manager and that HEAD has not moved from that starting commit.

The [disposable example](examples/git-workspaces/README.md) creates two worktrees and shows that editing the first leaves the second and the primary checkout unchanged. This profile requires trusted cooperative POSIX repositories and trusted system **Git 2.52.0 or newer**. Local author checks used Git 2.52.0 on Linux. Many Git features are intentionally refused; there is no general repository compatibility promise.

`diff` covers tracked, unstaged changes against the index. It excludes staged-only changes and untracked contents. The API does not commit, remove worktrees, fetch, push, retry failed creation, or clean up creation residue.

### Evidence checks and optional domain tools

- [Local source auditing](docs/local-source-audit.md) checks pinned bytes and declared evidence metadata, preserving unknown values
- [Trusted-source admission](docs/source-admission.md) loads explicitly reviewed local Python modules and returns their original named objects; execution has ordinary Python process authority
- [Synthetic qualification records](docs/synthetic-lab-qualification.md) check invented records against declared oracles; correct refusals are distinct from real qualification
- [Fake-instrument simulation](docs/simulated-lab.md) runs a fixed Bluesky plan on internally created ophyd simulated instruments, with at most 16 setpoint/read steps and offline document verification
- [Optional CAD/CAE contracts](examples/cad_cae/README.md) cover bounded geometry, mesh, thermal, and beam examples with separately prepared native backends
- [Optional Temporal reference transport](docs/temporal-reference-transport.md) delivers only the fixed `synthetic.bounded_sum.v1` profile: single-host loopback, queued first delivery after a graceful quiescent restart, and recorded-result replay; no in-flight crash recovery, multi-host or global exactly-once claim

## Installation and first example

The distribution is `opendot-engineering`; its Python import namespace is `opendot_engineering`. The default installation has no required runtime Python dependencies and needs Python 3.12 or newer. Several file-checking APIs require POSIX operations. The optional `temporal` extra pins `temporalio==1.34.0`; its dependencies need separate approval and preparation, and installation never starts a server. Simulation execution has an optional, pinned dependency set; native CAD/CAE execution requires its own backend environment. There is no registered console command.

Start with the [0.3.0a2 installed quickstart](docs/installed-quickstart.md) for offline hash verification and a first result. For source use, see [Getting started](docs/getting-started.md) and the [small callable/artifact example](examples/callable-artifacts/README.md). Use the [Git example](examples/git-workspaces/README.md) only on an eligible local host. The [public repository](https://github.com/sddvacav/opendot) and [issues](https://github.com/sddvacav/opendot/issues) are verified. The [historical a6 prerelease](https://github.com/sddvacav/opendot/releases/tag/v0.2.0a6) is separate; use [Releases](https://github.com/sddvacav/opendot/releases) to verify the available artifacts and their exact version before installation.

## The boundary that remains

The artifact store uses a trusted caller-controlled root, follows symlinks, and does not transactionally publish objects and metadata. Callable permissions and idempotence are declarations supplied by the embedding application. Threads and Git subprocess controls are not an OS sandbox, and a callable timeout cannot guarantee termination of arbitrary Python code. Failed validation or creation can leave effects that need inspection.

Task orchestration, persistent recovery, live model evaluation, real-device control, and multi-host or hundreds-of-agent performance remain future work. Existing consumers have not been migrated. Scientific/device authority flags remain false in the relevant synthetic adapters. Hosted CI, broad platform support, cost savings, and production readiness are not established by the selected local checks.

## What comes next

The next useful milestone is a narrow workflow that a new user can reproduce and an independent reviewer can accept. Priorities are exact-candidate review, first-run usability, transparent failures and permissions, and a complete domain example with versioned inputs and explicit acceptance criteria. Durable recovery and measured parallel benefit require their own implementation and experiments.

[Public-source research](docs/research/README.md) informs this direction. It supplies product hypotheses, not institutional endorsements, customer commitments, or proof that a feature is complete. The original project code retains its [Apache-2.0 license](LICENSE) and [notices](NOTICE); optional dependencies retain their own obligations.

## Historical a4 source-only delivery extension

That extension retained the accepted 0.2.0a4 package payload. Its
[worked measurement-review workflow and delivery tooling](docs/delivery-workflows-verification.md)
adds a concrete synthetic user journey, test dependency hashes, source inventory
and dated research/benchmark annexes. Its integrated acceptance is recorded
separately; the earlier 78-point score is not a score for every later edit.
