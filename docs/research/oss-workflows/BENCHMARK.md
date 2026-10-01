# Bilingual workflow benchmark / 双语工作流对标

Observation: 2026-10-01 UTC, 11:31–11:34. All stars came from the official GitHub repository API during that window, not README marketing text. Full commit IDs and metadata URLs: [snapshot](evidence/repository-snapshot.json). Latest release means GitHub's latest non-prerelease endpoint; it is not a verified install or support guarantee. Peer quickstarts were read, not run.

## Attention and release evidence / 关注度与发行证据

| Project and scope / 项目与范围 | Stars | Observed HEAD | Inspected root license / 主许可证 | Latest release observed (UTC) |
|---|---:|---|---|---|
| OpenHands/OpenHands: Agent Canvas, currently beta | 89,697 | [a8c05584](https://github.com/OpenHands/OpenHands/commit/a8c05584ec6bb063a0857460b9cbff48e136919f) | [MIT](https://github.com/OpenHands/OpenHands/blob/a8c05584ec6bb063a0857460b9cbff48e136919f/LICENSE) | [v1.24.0](https://github.com/OpenHands/OpenHands/releases/tag/v1.24.0), 2026-09-25; desktop assets listed |
| temporalio/temporal: durable execution service / 持久执行服务 | 23,397 | [fc437260](https://github.com/temporalio/temporal/commit/fc4372605ce23f333b7e1a43eef303ff002c2ef1) | [MIT](https://github.com/temporalio/temporal/blob/fc4372605ce23f333b7e1a43eef303ff002c2ef1/LICENSE) | [v1.32.0](https://github.com/temporalio/temporal/releases/tag/v1.32.0), 2026-09-11; binaries and checksums listed |
| treeverse/dvc: data and pipeline versioning / 数据与流水线版本化 | 15,895 | [56e59829](https://github.com/treeverse/dvc/commit/56e59829512ff134aa269099a2099587b810b4dd) | [Apache-2.0](https://github.com/treeverse/dvc/blob/56e59829512ff134aa269099a2099587b810b4dd/LICENSE) | [3.67.1](https://github.com/treeverse/dvc/releases/tag/3.67.1), 2026-03-31; changelog, no attached assets |
| aiidateam/aiida-core: scientific workflow provenance / 科研工作流与来源记录 | 591 | [9a9cf959](https://github.com/aiidateam/aiida-core/commit/9a9cf9591785ba45eea7355ae3f716bce8decd95) | [MIT text](https://github.com/aiidateam/aiida-core/blob/9a9cf9591785ba45eea7355ae3f716bce8decd95/LICENSE.txt); API says NOASSERTION | [v2.9.2](https://github.com/aiidateam/aiida-core/releases/tag/v2.9.2), 2026-09-03; links changelog |
| bluesky/bluesky: experiment orchestration, not social network / 实验编排，非社交平台 | 241 | [4b53ff3a](https://github.com/bluesky/bluesky/commit/4b53ff3a1420fee87c8af671fb2b86a976ad9d7d) | [BSD-3-Clause](https://github.com/bluesky/bluesky/blob/4b53ff3a1420fee87c8af671fb2b86a976ad9d7d/LICENSE) | [v1.15.1](https://github.com/bluesky/bluesky/releases/tag/v1.15.1), 2026-05-06; wheel/source assets listed |

Root licenses do not describe every dependency or bundled component. No license compatibility or distribution-rights conclusion is made. A release list is not proof that its artifacts, signatures or hosted CI passed verification. AiiDA and Bluesky are lower-star domain references; the first three are the high-star comparison set. “Mature” is not scored from stars, age or badges.

## Useful workflow differences / 对 OpenDot 有用的差异

| Reference | Evidence-backed workflow / 官方描述的流程 | Useful OpenDot ticket / 可借鉴任务 | Non-parity boundary / 不可混同 |
|---|---|---|---|
| [OpenHands pinned README](https://github.com/OpenHands/OpenHands/blob/a8c05584ec6bb063a0857460b9cbff48e136919f/README.md) | Start work, choose a backend and inspect conversations from one control surface; quickstart differentiates unsandboxed access from Docker options. 从启动、选择后端到查看工作都有明确入口与权限提示 | T1/T5: one acquisition-to-review journey; state who owns each step. 把上手与成果审阅连起来，标明责任边界 | Canvas is the control center; SDK/Agent Server and automation live elsewhere. OpenDot has no corresponding persistent agent platform |
| [Temporal pinned README](https://github.com/temporalio/temporal/blob/fc4372605ce23f333b7e1a43eef303ff002c2ef1/README.md), [event-history docs](https://docs.temporal.io/encyclopedia/event-history) | Start local service, run a sample, inspect workflow history; recorded events support state reconstruction. 可查看的执行历史服务于恢复 | T7: define durable owner, effect reconciliation and failure-injection protocol before claiming restart. 先实现状态所有者与副作用对账 | A Python receipt and a fresh-process file check do not constitute event-history replay or durable workflow recovery |
| [DVC pinned README](https://github.com/treeverse/dvc/blob/56e59829512ff134aa269099a2099587b810b4dd/README.rst), [run-cache docs](https://dvc.org/doc/user-guide/project-structure/internal-files) | Track data, declare dependency/command/output relations, rerun affected stages and compare experiments. Run-cache reuse assumes deterministic commands. 版本化输入与步骤，变更后识别受影响结果 | T2: bind source, parameters and validator identity before reusing acceptance. 不能仅凭产物存在而沿用通过状态 | OpenDot CAS preserves bytes; it does not implement a dependency DAG, invalidation engine or DVC-compatible cache |
| [AiiDA provenance tutorial](https://github.com/aiidateam/aiida-core/blob/9a9cf9591785ba45eea7355ae3f716bce8decd95/docs/source/tutorials/basic.md) | Track data and calculations together, inspect process status and trace how outputs were produced. 同时记录数据与计算过程 | T1/T2: make input → computation → output → verification links inspectable, initially in one explicit manifest. 先用小型清单展示证据链 | AiiDA has an actual database/engine and scientific plugins; declarative CAS metadata is neither authenticated provenance nor that engine |
| [Bluesky interruption docs](https://github.com/bluesky/bluesky/blob/4b53ff3a1420fee87c8af671fb2b86a976ad9d7d/docs/state-machine.rst) | Distinguishes resume, abort/cleanup and immediate halt, preserving acquired data; resumability depends on safe checkpoints. 明确区分恢复、清理后终止与立即停止 | T7: distinguish effects, accepted result and termination observations. 将副作用、验收、终止分开 | Thread timeout is not device stop; retained artifacts are not interrupted-experiment recovery; no lab safety claim |

## Quickstart and support evidence / 上手与支持入口

| Project | Entry evidence / 已读入口 | Support evidence / 已读支持链接 |
|---|---|---|
| OpenHands | Pinned README requires Node 24+/uv for npm launch; Docker route separately described. An unsandboxed route explicitly warns of filesystem access | README points to GitHub issues and [project Slack](https://openhands.dev/joinslack) |
| Temporal | Pinned README: local CLI development server, sample repositories, CLI listing and Web UI | [Community forum](https://community.temporal.io), linked from README |
| DVC | Pinned README: install → data tracking → stages → experiment comparison, with separate sharing steps | [Forum](https://discuss.dvc.org/), [chat](https://dvc.org/chat), linked from README |
| AiiDA | [Pinned quick installation](https://github.com/aiidateam/aiida-core/blob/9a9cf9591785ba45eea7355ae3f716bce8decd95/docs/source/installation/guide_quick.rst): package → profile → status; explicit database/broker limitations. README warns against using main as an installation release | [Discourse](https://aiida.discourse.group/), linked from README |
| Bluesky | [Pinned tutorial](https://github.com/bluesky/bluesky/blob/4b53ff3a1420fee87c8af671fb2b86a976ad9d7d/docs/tutorial.rst): environment → simulated experiment → stream callbacks/storage. It warns against replacing a facility-configured RunEngine | [Project chat](https://blueskyproject.io/matrix/), linked from tutorial |

These are verified links appearing in official material, not tested support responsiveness, private security-reporting routes or endorsed setup instructions for OpenDot. Live rendered documentation can advance independently of pinned source and release tags.

支持链接的存在不等于响应能力、私密安全报告渠道或 OpenDot 的安装指南。本轮未安装同行软件、联系维护者、下载核验发行物或复现同行性能。
