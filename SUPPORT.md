# Getting help with OpenDot Engineering

## Current 0.3.0a4 source/package candidate

**ALPHA / NOT_SCORED; local candidate, publication not established by this source.**
This coherent snapshot includes the optional [offline A2A worker-turn adapter](docs/a2a-worker-turn.md),
matching source examples and version-bound installation instructions. Default runtime
dependencies remain empty. Use the [a4 installed guide](docs/installed-quickstart.md)
with its externally reviewed checksum-manifest pin; final exact identities and
separately scoped qualification belong in the candidate's external release notes.

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

The public repository is [sddvacav/opendot](https://github.com/sddvacav/opendot). Use [GitHub Issues](https://github.com/sddvacav/opendot/issues) for non-sensitive usage questions, feature requests and minimal synthetic bug reports. A private security-reporting destination and response SLA are not established; do not publish sensitive details.

## Choose the right report

- Usage: the goal, documentation section, and unclear step
- Bug: expected and observed behavior, public version, environment category, and a small synthetic reproducer
- Feature: the problem, scope, acceptance criteria, and alternatives
- Security/privacy: follow [Security](SECURITY.md) without publishing sensitive details

Use [the issue template](templates/issue-report.md) in [GitHub Issues](https://github.com/sddvacav/opendot/issues). Remove secrets, confidential inputs, user identities, private paths, and hidden metadata. Do not paste complete environment dumps or conversation histories.

## Known limits

| Question | Current answer |
| --- | --- |
| Can I run anything now? | Yes: the [README callable/artifact example](README.md#run-the-synthetic-examples), [a4 candidate installed quickstart](docs/installed-quickstart.md), and [read-only help](docs/module-cli.md); their scopes are bounded |
| Is there a public installation destination? | Current a4 is a local candidate; publication is not established here. Historical a3: the [v0.3.0a3 ALPHA prerelease](https://github.com/sddvacav/opendot/releases/tag/v0.3.0a3) provides the released wheel and matching source assets. Follow the [version-pinned installed guide](https://github.com/sddvacav/opendot/blob/8d5d8667d65734fb5c40fa0526709a3159b7f165/docs/installed-quickstart.md) and its SHA-256 checks. Earlier releases remain version-bound; no PyPI publication is claimed |
| What has been checked? | The [a3 release notes](https://github.com/sddvacav/opendot/releases/download/v0.3.0a3/RELEASE-NOTES.md) bind exact released assets to separate source, installed and bounded optional-Temporal checks; [a3 main portable CI](https://github.com/sddvacav/opendot/actions/runs/36982326482) is source evidence. Later [retained 200-job evidence](docs/temporal-reference-transport.md#later-source-only-200-job-qualification-2026-10-02) is separate from the frozen release and is not an agent-count result. Historical [a6 main source CI](https://github.com/sddvacav/opendot/actions/runs/36885554336) passed 1,183 portable checks plus 49 separate subtests and retains its [own scope](docs/a6-candidate-verification.md). None proves scientific acceptance |
| Does the documentation checker run the examples? | No; it checks bounded local links/fragments, explicit HTML anchors and eight matching nonempty shell blocks per guide language. Installed execution is separate |
| What platforms are supported? | Local checks used Linux/CPython 3.12; a supported matrix is not established; source auditing requires POSIX no-symlink path operations |
| Do the examples need a model or native solver? | Lightweight examples and CAD `plan` do not; actual CAD/CAE `run` needs separately approved native backends. A2A live execution is NOT_RUN |
| Is this a complete agent runtime? | No; orchestration, durable recovery, and agent scale are outside this package |
| Are peer projects integrated? | The documentation comparison establishes no integration or affiliation |
| Can confidential inputs be shared? | No blanket confidential-data handling guarantee is made; never publish private inputs or receipts |
| When will I receive help? | No response commitment or SLA is established |

See [getting started](docs/getting-started.md#troubleshooting) for safe first checks and [claim status](docs/claim-status.md) for evidence boundaries.

## 中文摘要

当前为 0.3.0a4 本地候选，未据此声明已发布；请使用[a4 中文安装入门](docs/installed-quickstart.zh-CN.md)与外部复核的校验清单摘要。测量比较须从匹配完整源码导入；CAD plan 为 NOT_EXECUTED，原生执行和 A2A 外部 live gate 均为 NOT_RUN。以下 a3 结果仅为历史证据。

[v0.3.0a3 ALPHA 预发布版](https://github.com/sddvacav/opendot/releases/tag/v0.3.0a3)已提供 wheel 与匹配源码；请按[版本固定的中文安装入门](https://github.com/sddvacav/opendot/blob/8d5d8667d65734fb5c40fa0526709a3159b7f165/docs/installed-quickstart.zh-CN.md)核对 SHA-256。[a3 发布说明](https://github.com/sddvacav/opendot/releases/download/v0.3.0a3/RELEASE-NOTES.md)分别记录精确产物、源码、安装及有界可选 Temporal 检查，不能将范围相加或推导科学验收。a3 包含可选有界读取与纯批次准备；后续真实 200 任务及保留投影的证据属于源码范围，不改变冻结发布产物，也不是 200 个智能体。历史版本字节与证据不变；ALPHA、NOT_SCORED 不变，未声称已发布到 PyPI。[公开仓库](https://github.com/sddvacav/opendot)与[议题地址](https://github.com/sddvacav/opendot/issues)已核实；普通问题请提供最小合成复现，不要发布私密输入或环境转储。私密安全报告渠道尚未确立，也没有响应时限承诺。历史 a6 主分支源码 CI 通过 1,183 项检查及另计的 49 项子测试；安装、原生及科学证据的范围分别保留。文档一致性检查不会执行安装指南。
