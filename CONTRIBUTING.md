# Contributing to OpenDot Engineering

Focus contributions on the bounded adapter package, reproducible synthetic examples, and clear documentation. The canonical submission destination and maintainer governance are not verified here. Do not infer them from the project name or submit confidential material to an unverified channel.

## Start with the current boundary

Read [the architecture](docs/architecture.md), [claim status](docs/claim-status.md), and [AGENTS.md](AGENTS.md). Keep the package import namespace and module entrypoints stable unless a reviewed change explicitly requires otherwise. A model-driven agent runtime, scheduler, device controller, database, or managed evidence service is outside this source cut. The bounded callable-only owner is retained unchanged; do not add a second execution owner. The sole local storage exception is the canonical artifact closure in [ADR 002](docs/decisions/002-canonical-artifact-core.md); do not add another storage owner.

Useful changes include clearer explanations, a minimal public fixture, a narrowly scoped adapter contract, or a synthetic rejection/failure test. Peer documentation references are not requests to integrate those projects.

## Local development and checks

Python 3.12 or newer is required. The source-root [callable/artifact example](README.md#run-the-synthetic-examples) and [read-only package help](docs/module-cli.md) use the standard library; [installed guidance](docs/installed-quickstart.md) covers wheel use. Test tooling is separate, pinned in [CI requirements](ci/requirements.txt); optional native backends are not core development dependencies.

Review test selection before execution. [Portable CI selection](ci/README.md) gives the exact current node manifest and reproduction command; [current a5 verification](docs/a5-candidate-verification.md) separates the declared 1,104 portable / 1,263 controlled-local selections from actual source, build and installed outcomes. The [historical a4 record](docs/verifier-ci-verification.md) retains its 1,066-pass author source aggregate and overlapping component scopes. The [a3 development record](docs/parallel-development-verification.md) remains historical. The [earlier combined checks](docs/combined-candidate-verification.md) remain a separate historical scope. Broad test commands elsewhere in adapter reference pages are not the authorization or selection used for this integration. Native backend runs, actual process-lifetime tests, live model calls, and external services need separately scoped environments and evidence.

Documentation changes use the bounded [source-only checker](docs/documentation-checks.md). Keep the two installed guides at exactly eight nonempty, literal-identical ordered `sh` blocks unless a reviewed journey/profile change deliberately updates that contract. A consistency pass does not execute the blocks, check remote links or prove source truth. Packaging uses the [pinned build backend](docs/build-toolchain.md); the predecessor repeatability experiment does not accept a new wheel.

For every change:

1. Describe the problem, smallest result, acceptance criteria, and excluded scope
2. Change the relevant source, tests, examples, and documentation together
3. Exercise expected and relevant failure behavior within the authorized scope
4. Report commands and outcomes as passed, failed, skipped, or not run
5. Check installed-package behavior separately when packaging, imports, metadata, or README content changes
6. Update [claim status](docs/claim-status.md) and both README languages when capabilities or limits change

A package import is not a working console script. A source-tree test is not a clean installed-artifact test. A successful synthetic contract is not scientific validation or verified runtime recovery.

## Privacy, licensing, and review

Use the [change request template](templates/change-request.md). Keep receipts outside the source tree and review actual outgoing file bytes, archive members, metadata, and any included history. Remove secrets, user identities, private project names, machine paths, confidential data, and private operational identifiers. Pattern scanning alone is not publication clearance.

Preserve [LICENSE](LICENSE), [NOTICE](NOTICE), and required third-party attribution. Follow the separate [new artwork notice](assets/brand/NOTICE) for the six AI-assisted SVGs. Do not relabel upstream code or imply trademark rights.

Maintainers must confirm ownership, review policy, supported versions, conduct policy, and reporting channels before release. No CLA, DCO, maintainer roster, response time, or license-ownership certification is invented here. Publication requires an explicit review decision and separate authorization.

## 中文摘要

贡献范围是独立适配器、合成示例与文档。先阅读实际模块边界和经过审查的测试选择，再执行有限范围的检查。分别报告通过、失败、跳过和未执行的项目；修改能力声明时同步更新中英文 README。保留许可与归属声明，不公开私密回执或未经复核的文件。正式提交渠道和治理规则仍需确认。
