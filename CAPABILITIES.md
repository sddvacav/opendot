# OpenDot Engineering capabilities and evidence

[简体中文](CAPABILITIES.zh-CN.md) · [Overview](OVERVIEW.md) · [Research map](RESEARCH-MAP.md)

Snapshot: 2 October 2026. This matrix describes the frozen experimental 0.3.0a3 release boundary and preserves the exact scope of a4 and earlier evidence. It is a traceability map, not a score. “Implemented” means code is present; an independent predecessor pass does not independently approve successor changes.

**Experimental alpha: 0.3.0a3; NOT_SCORED.** This version
integrates [structural default verification v2](docs/structural-default-v2.md):
conditional per-element energy consistency, schema 2 and explicit historical
`artifact_v1` compatibility. Scientific acceptance remains false. The source-boundary
example covers seven original synthetic protocols, eight unimplemented proposals,
and six separately counted synthetic parameter fixtures; no production policy is added.
Canonical execution/reference owners and optional energy-API results are unchanged.
The [Gmsh resource-limit setup](docs/gmsh-cpu-ceiling.md) preserves inherited lower
CPU and per-file ceilings; fake-resource checks do not establish native/kernel enforcement.
The file-size repair and optional Temporal transport are packaged in 0.3.0a2;
unchanged v0.3.0a1 release assets contain neither and retain their original hashes.
[Historical 0.3.0a1 verification scope](docs/structural-v2-candidate-verification.md)

The [0.3.0a3 ALPHA prerelease](https://github.com/sddvacav/opendot/releases/tag/v0.3.0a3) is available. The [exact-asset installation guide](docs/installed-quickstart.md) pins its released wheel and matching full source. The [historical 0.3.0a2 ALPHA prerelease](https://github.com/sddvacav/opendot/releases/tag/v0.3.0a2) and its existing evidence remain unchanged. The [historical 0.3.0a1 installation guide](https://github.com/sddvacav/opendot/blob/359f781a5aa1650ae92b1af81cf369a17c444045/docs/installed-quickstart.md) and [historical a6 installation guide](https://github.com/sddvacav/opendot/blob/eec73193594ee212ba091a9d7310c8762a4b0003/docs/installed-quickstart.md) retain their separate version-specific pins; earlier-version results do not accept these artifacts.

## 0.3.0a3 released asset scope

The released assets bind to [commit `30610de43da81801e7b88517459fbdf0f667ca2d`](https://github.com/sddvacav/opendot/commit/30610de43da81801e7b88517459fbdf0f667ca2d),
source tree `95ca23d9d36558680c809f2382bef188c6fc2ae4`. This documentation follow-on
does not rebuild or replace them. Later `main` changes and CI do not qualify or
change these frozen assets; a3 includes pure batch preparation only. They include the merged [bounded retrieval API](docs/canonical-artifacts.md#optional-bounded-retrieval-unreleased-source-increment)
and the full source includes [pure finite-batch preparation](docs/temporal-batch-qualification.md).
The API page's “unreleased” heading is an earlier source checkpoint, not a claim
that the pinned a3 wheel lacks that API. With a supplied exact nonnegative integer
N, retrieval acquires at most N+1 actual object bytes and refuses oversize input;
omitted/`None` keeps whole-object reads. Existing trusted-regular-file and symlink
assumptions remain. This is not a peak-memory, time, sandbox or execution-wide bound.

Batch preparation is test-only: exactly 200 fixed synthetic jobs, 16 reserved or
submitted-but-not-validated-terminal workflows, and eight external Activity
slots with eight executor workers. Reservation precedes submission; uncertainty
closes admission. Pure fixtures do not establish a real 200-job service run,
measured concurrency, agent count, throughput or a new production scheduler.
Earlier service evidence below retains its original version and seven-case scope.

## Optional Temporal qualification and 0.3.0a2 evidence

The [optional synthetic Temporal transport](docs/temporal-reference-transport.md)
is present on `main` after [PR #18](https://github.com/sddvacav/opendot/pull/18).
The earlier implementation's [bounded hosted qualification](docs/temporal-qualification-evidence.md) was
independently accepted on 2 October 2026: **818 SDK/pure checks and seven real-server
checks passed** on the exact tree merged to `main`. This is one single-host,
loopback-only `synthetic.bounded_sum.v1` profile with SDK 1.34.0, CLI 1.9.1 and
server 1.32.0. It demonstrates queued first delivery after a graceful quiescent
restart and replay of a recorded result without another handler call. The
separate portable CI result was 1,325 passed / 141 subtests passed; these scopes
are not combined into a new coverage total.

The 0.3.0a2 [optional qualification run](https://github.com/sddvacav/opendot/actions/runs/36963928744)
separately passed 818 SDK/pure checks and seven real-server checks; its
[main portable run](https://github.com/sddvacav/opendot/actions/runs/36964156448)
passed 1,325 checks / 141 subtests. These are separate scopes, not a new summed
total or new scientific/device acceptance. The [release notes](https://github.com/sddvacav/opendot/releases/download/v0.3.0a2/RELEASE-NOTES.md)
bind the released assets to their source and scoped evidence.

This optional packaged feature preserves empty default dependencies, default-import
isolation and the canonical execution/artifact/contracts owners. The `temporal`
extra pins `temporalio==1.34.0`; dependencies require separate approval and
preparation, and installation never starts a server. It does not
establish multi-host operation, in-flight crash recovery, global exactly-once
effects, production readiness, scientific validity or a complete MVP. It does
not change `NOT_SCORED` or accept the unchanged published 0.3.0a1 assets for this
feature. Earlier failures and `NOT_RUN` evidence remain historical; see the
[exact revisions, observations and limits](docs/temporal-qualification-evidence.md).

## Historical verification ledger

| Evidence | Exact scope | Outcome and interpretation |
| --- | --- | --- |
| E1 | Earlier 0.2.0a1 candidate `e033e8c34d196263fe111ca148fbaf5d8b450504`; author checks on Linux, CPython 3.12.14, Git 2.52.0 | 771 passed: 695 inherited portable cases + 76 disjoint Git cases; zero failures/errors/skips. The same 76 Git cases also passed against the installed wheel and are not additional unique coverage. Independent review reran the packaged selection but requests the R1 residue-reporting fix before acceptance. [Public local record](docs/git-workspaces-verification.md) |
| E2 | 0.2.0a0 callable/artifact integration `c29fa49da0e7aa1f8c1382ffbc8d5f7fe2dffb25`; independent review on 1 October 2026 | 695 selected portable cases passed, zero failures/errors/skips; independently rebuilt artifact and installed composition/component probes passed. Narrow integration PASS, not consumer migration or full-platform acceptance. [Scope and reproduction](docs/execution-core-verification.md) |
| E3 | Separate fake-only selection in that 0.2.0a0 independent review | 108 passed, zero failures/errors/skips; 17 overlap E2. Not rerun for the Git successor and not added to any successor total. [Simulation boundary](docs/simulated-lab.md) |
| E4 | Historical 0.2.0a1 residue-reporting repair candidate; Linux, Python 3.12.14, Git 2.52.0; module hash pinned in [repair record](docs/git-workspaces-residue-fix.md) | Author: 773 passed =695 inherited +78 Git, zero failures/errors/skips. The real permission-loss counterexample independently passes at source level. Exact archive/wheel acceptance remains a separate review receipt. |
| E5 | Historical 0.2.0a2 metadata candidate; Linux, CPython 3.12.14, Git 2.52.0 | Author: 805 selected source tests passed =773 inherited selection +32 metadata; zero failures/errors/skips. Installed metadata: the same 32 nodes passed separately. [Historical author record](docs/agent-contracts-verification.md); independent exact-artifact acceptance remains separate |
| E6 | Historical 0.2.0a3 source candidate and final `a59419b` delivery | 899 source checks passed; final fresh installed journeys covered all eight shell blocks per language. Two clean build environments on the same host reproduced the exact predecessor wheel. [Source record](docs/parallel-development-verification.md) and [build experiment](docs/build-toolchain.md); these do not accept a4 or transfer a predecessor score |
| E7 | Independently reviewed shared declared CalculiX 2.23 log gate; synthetic verifier evidence | 30 predeclared independent cases passed. A separate related selection had 192 passes, 81 native opt-in skips and two external-process deselections. Overlapping scopes, not additive coverage; no native solve or binary-authenticity proof. [Historical a4 component record](docs/verifier-ci-verification.md) |
| E8 | Independently reviewed source-only documentation checker | Repaired checker passed the original 43 independent probes and eight separately predeclared HTML probes; the 74-case author selection was independently rerun. These scopes overlap. This checks bounded consistency, not executed guide commands or source truth. [Historical a4 component record](docs/verifier-ci-verification.md) |

**Historical a4 author source aggregate: 1,066 passed**, with zero failures/errors/skips. **Exact final artifact and installed acceptance require their own delivery receipt.** E7/E8 overlap this aggregate and are not additional unique coverage. The 988-node portable CI definition omits 78 local Git cases and is not a hosted run. Component or source passes do not approve the final wheel, installed journeys or release. See [historical a4 verification](docs/verifier-ci-verification.md).

The historical `0.2.0a2` candidate added only [metadata contracts](docs/agent-contracts.md). E5 records its author checks; E1–E4 retain their earlier versions and scopes.

**Historical finding R1:** e033 required changes despite passing its selected tests. The successor preserves unknown on inaccessible residue; an independent real permission-loss reproduction now passes at source level. See E4 and the repair record. No final-artifact or release approval is inferred.

The independent E2/E3 results above summarize the separately reviewed evidence packet, which remains outside the source distribution; the linked integration page preserves its original author-record scope. Hosted CI and publication are not established by this historical ledger; the current Temporal run is recorded separately above. Proposed editorial text is not part of the frozen artifacts named above.

## Capability matrix

| ID | Capability and user value | Current status | Acceptance evidence | Material boundary |
| --- | --- | --- | --- | --- |
| C1 | [Callable and artifact composition](examples/callable-artifacts/README.md): Connect a tool result to inspectable stored bytes | Implemented; predecessor independently reviewed | E2; 7 composition nodes within the 695 baseline; installed probes separated accepted, rejected and permission-blocked outcomes | A semantic failure may retain an unaccepted artifact; no rollback or scientific acceptance |
| C2 | [Canonical local artifact store](docs/canonical-artifacts.md): Write, retrieve and independently check hash-addressed bytes | Implemented; a3 adds opt-in bounded retrieval in the same owner | E2 retains its historical scope; [bounded-read source evidence](docs/pr23-ci-evidence.json) and exact a3 installation checks are separate | Trusted regular local objects/roots; symlink following; per-instance lock; no transaction; `max_bytes=N` acquires at most N+1 object bytes, while default/None retrieval, `put_file` and verify retain whole reads; no constant-memory or execution-wide bound |
| C3 | [Callable-only execution](docs/callable-execution.md): Apply declared permissions, retries and semantic validation to Python functions | Implemented; preserved predecessor owner | E2; selected callable tests and installed examples; E1 repeats the unchanged inherited nodes | In-memory state; caller-declared authority and idempotence; no sandbox or guaranteed stop of arbitrary handlers |
| C4 | [Controlled local Git workspaces](docs/git-workspaces.md): Create separate working copies at one pinned starting commit, then inspect them | Implemented; R1 repaired and independently reproduced; final artifacts reviewed separately | E4; 78 Git cases; E1 preserves historical examples, real disposable two-worktree source/installed examples, index-byte/mtime checks and refusal sentinels | Create/status/diff only; trusted cooperative POSIX primary SHA-1 checkouts and system Git >=2.52.0; fixed HEAD; tracked unstaged diff only; no cleanup/retry/remote operations |
| C5 | [Local source audit](docs/local-source-audit.md): Check pinned inputs, declared evidence roles and exact observation locators | Implemented; inherited selected portable checks | E1/E2 portable selections; published synthetic manifest pins and installed fixture checks | Declared access is not access control; byte identity is not truth, authorship or rights |
| C6 | [Trusted-source admission](docs/source-admission.md): Capture pinned local Python modules and return original named exports | Implemented; inherited bounded checks | E1/E2 portable selections plus the scope-specific source-admission record | Trusted cooperative code with ordinary Python authority; unpinned absolute imports/effects; no sandbox or automatic failure retry |
| C7 | [Synthetic qualification records](docs/synthetic-lab-qualification.md): Check invented records against explicit expected outcomes | Implemented; inherited selected portable checks | E1/E2 portable selections and installed fixed-pin fixture example | Correct refusal can pass the software contract; no instrument simulation, physical qualification or device authority |
| C8 | [Finite fake-instrument simulation](docs/simulated-lab.md): Record and verify a fixed synthetic set/read experiment | Implemented; prior fake-only independent evidence | E3; 108 fake-only checks on the predecessor, with 17 overlapping portable; not rerun for E1 | Internally built fake devices; 1–16 setpoints; exact optional versions; no arbitrary plans, real hardware, resume or physical interlock |
| C9 | [Optional CAD/CAE contracts](examples/cad_cae/README.md): Inspect narrow geometry, mesh, thermal and beam contracts | Included; synthetic/portable checks are scoped | E1/E2 retain selected portable contract tests; E7 covers the shared declared-version gate with synthetic inputs; native execution needs separate evidence | No fresh native acceptance for this candidate; bounded synthetic numerical examples do not qualify real components or science |
| C10 | [Adapter source provenance](docs/git-provenance-verification.md): Bind new adapter provenance to actual local source membership | Implemented; inherited bounded checks | Selected provenance regressions in E1/E2; source hashes retained when Git context is uncertain | No upstream-authorship or atomic-snapshot proof; other native fields and historical evidence may still contain paths |
| C11 | [Durable tasks and agent-scale execution](docs/research/README.md): Recover long work and measure useful parallel delivery | General capability remains proposed | No accepted in-flight crash-recovery, live-model or multi-host experiment; C13 is a separate finite transport qualification | No unattended-duration, hundreds-of-agent, throughput or cost-saving claim |
| C12 | [Canonical agent metadata](docs/agent-contracts.md): Describe capabilities and agent manifests | Included; metadata-only extraction | E5; [synthetic metadata example](examples/agent-contracts/README.md); independent acceptance remains separate | `Capability` and `AgentManifest` require explicit `.validate()` calls; budgets/permissions are descriptive, with no execution enforcement or existing-consumer migration |
| C13 | [Optional Temporal reference transport](docs/temporal-reference-transport.md): Deliver one fixed synthetic Activity and reuse its recorded result | Packaged since 0.3.0a2; historical qualification scopes separated above | [Earlier implementation evidence](docs/temporal-qualification-evidence.md): 818 SDK/pure and seven real-server checks; three graceful server stops and 12 awaited worker shutdowns; replay handler count stays one. Separate 0.3.0a2 runs are linked above | Single host, loopback, same trusted local CAS/SQLite; queued first delivery and recorded-result replay only; not in-flight crash recovery, global exactly-once or general agent execution |
| C14 | [Finite-batch preparation](docs/temporal-batch-qualification.md): Check fixed synthetic admission and evidence rules | a3 full-source test-only preparation; not a production wheel API | Deterministic fixture/trace checks, explicitly FABRICATED_UNIT_DATA; no live batch qualification | 200 fixed jobs / 16 outstanding / eight configured Activity slots; no actual 200-job run, 200 agents, measured parallelism, throughput or service-ready receipt |

## Reading the results

A passing selected software test is not a successful customer task. An artifact hash is not scientific evidence or permission. The relevant adapters retain false scientific/device-authority fields. Real use adds host, dependency, data-rights, consumer-compatibility and domain-acceptance requirements. Public research references and evaluated adoption options do not establish installed integrations, endorsements, or paying users.

This matrix assigns no aggregate readiness grade. It preserves evidence scope rather than converting test counts into a product score.


## Historical 0.2.0a4 verifier and CI update

The [shared log gate](docs/solver-version-gate.md) rejects ambiguous or repeated CalculiX version declarations, including repeated identical headers. It checks a declared 2.23 version, not a binary identity or new physical model. The source-only [documentation helper](docs/documentation-checks.md) checks bounded local links/fragments, explicit HTML anchors, and exactly eight nonempty literal-identical shell blocks per installed-guide language; it executes none of them. The [build backend](docs/build-toolchain.md) is pinned to setuptools 84.0.0, without a new runtime dependency.

Component reviews and the author source aggregate remain separate from separately recorded exact outgoing-artifact and installed acceptance. No new native, runtime/recovery, hosted-CI, public-release or numeric readiness claim follows. Prior evidence rows retain their original versions.
