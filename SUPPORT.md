# Getting help with OpenDot Engineering

## Current 0.3.0a5 release preparation

**ALPHA / NOT_SCORED; candidate preparation, not a publication receipt.**
Use the [a5 installed guide](docs/installed-quickstart.md) only with its matching
reviewed five-file bundle and independently accepted external SHA256SUMS digest.
Exact source, installed and guide qualification require separate external receipts;
no a4 acceptance transfers to this candidate.

- Wheel: callable/artifact APIs, bounded reads, read-only help and the optional
  explicit-import [HTTPS exchange](docs/a2a-http-transport.md); default runtime
  dependencies remain empty. Examples and documentation are not installed files
- Sdist: wheel-rebuild input, not the complete runnable examples or test tree
- Full source: [measurement comparison](examples/measurement-review/README.md),
  metadata-only [CAD/thermal plan](examples/cad_cae/README.md) (`NOT_EXECUTED`),
  the existing three-file [public STEP reference](examples/cad_cae/native-geometry-reference/README.md),
  and finite offline [utility `history`/`profile`](examples/measurement-review/README.md#offline-incremental-utility-fixture-report).
  These use the matching source tree; the STEP retains historical a4 provenance
  and is a static projection, not a replayable native pack
- HTTPS has finite mocked qualification only; live transport/worker/provider/model
  interoperability is `NOT_RUN`. [A2A](docs/a2a-worker-turn.md) still returns an
  `UNACCEPTED` candidate. Real O3 remains `PROPOSED / NOT_RUN`; measured effort is `UNKNOWN`
- This preparation adds no native or service run. Full CAD/thermal native execution
  is `NOT_RUN`; physical validation `NOT_PERFORMED`, independent review `NOT_EVALUATED`,
  mesh independence `NOT_ESTABLISHED`. Scientific/device authority stays false;
  historical Temporal evidence and the [a3 inventory](docs/release-inventory/v0.3.0a3/README.md)
  retain their own scopes, without new agent-scale or UI claims

The published predecessor is [0.3.0a4](https://github.com/sddvacav/opendot/releases/tag/v0.3.0a4), source commit
`2d16190a8121410bbeea252869b196f7891e1696`. Its [pinned installed guide](https://github.com/sddvacav/opendot/blob/2d16190a8121410bbeea252869b196f7891e1696/docs/installed-quickstart.md)
and [release notes](https://github.com/sddvacav/opendot/releases/download/v0.3.0a4/RELEASE-NOTES.md) retain the exact historical artifact and qualification scope;
those frozen assets are unchanged.

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
| Can I run anything now? | Yes: the [README callable/artifact example](README.md#run-the-synthetic-examples), [a5 candidate installed quickstart](docs/installed-quickstart.md), and [read-only help](docs/module-cli.md); their scopes are bounded |
| Is there a public installation destination? | Current a5 is release preparation; publication is not established here. The published predecessor [v0.3.0a4](https://github.com/sddvacav/opendot/releases/tag/v0.3.0a4) has a [commit-pinned guide](https://github.com/sddvacav/opendot/blob/2d16190a8121410bbeea252869b196f7891e1696/docs/installed-quickstart.md). Historical a3: the [v0.3.0a3 ALPHA prerelease](https://github.com/sddvacav/opendot/releases/tag/v0.3.0a3) provides the released wheel and matching source assets. Follow the [version-pinned installed guide](https://github.com/sddvacav/opendot/blob/8d5d8667d65734fb5c40fa0526709a3159b7f165/docs/installed-quickstart.md) and its SHA-256 checks. Earlier releases remain version-bound; no PyPI publication is claimed |
| What has been checked? | The [published a4 notes](https://github.com/sddvacav/opendot/releases/download/v0.3.0a4/RELEASE-NOTES.md) preserve the predecessor's exact-artifact checks; they do not qualify a5. Historical evidence: the [a3 release notes](https://github.com/sddvacav/opendot/releases/download/v0.3.0a3/RELEASE-NOTES.md) bind exact released assets to separate source, installed and bounded optional-Temporal checks; [a3 main portable CI](https://github.com/sddvacav/opendot/actions/runs/36982326482) is source evidence. Later [retained 200-job evidence](docs/temporal-reference-transport.md#later-source-only-200-job-qualification-2026-10-02) is separate from the frozen release and is not an agent-count result. Historical [a6 main source CI](https://github.com/sddvacav/opendot/actions/runs/36885554336) passed 1,183 portable checks plus 49 separate subtests and retains its [own scope](docs/a6-candidate-verification.md). None proves scientific acceptance |
| Does the documentation checker run the examples? | No; it checks bounded local links/fragments, explicit HTML anchors and eight matching nonempty shell blocks per guide language. Installed execution is separate |
| What platforms are supported? | Local checks used Linux/CPython 3.12; a supported matrix is not established; source auditing requires POSIX no-symlink path operations |
| Do the examples need a model or native solver? | Lightweight examples and CAD `plan` do not; actual CAD/CAE `run` needs separately approved native backends. A2A live execution is NOT_RUN |
| Is this a complete agent runtime? | No; orchestration, durable recovery, and agent scale are outside this package |
| Are peer projects integrated? | The documentation comparison establishes no integration or affiliation |
| Can confidential inputs be shared? | No blanket confidential-data handling guarantee is made; never publish private inputs or receipts |
| When will I receive help? | No response commitment or SLA is established |

See [getting started](docs/getting-started.md#troubleshooting) for safe first checks and [claim status](docs/claim-status.md) for evidence boundaries.

## 中文摘要

当前为 0.3.0a5 发布准备，未据此声明已发布；[a5 中文安装入门](docs/installed-quickstart.zh-CN.md)要求匹配的五文件包与外部独立验收的校验清单摘要。已发布的前一版 [0.3.0a4](https://github.com/sddvacav/opendot/releases/tag/v0.3.0a4)保留[固定提交的指南](https://github.com/sddvacav/opendot/blob/2d16190a8121410bbeea252869b196f7891e1696/docs/installed-quickstart.zh-CN.md)与原有证据。a5 wheel 新增须显式导入、仅经有限模拟验证的 HTTPS 模块，默认依赖不变；真实传输／worker／提供方／模型互通为 NOT_RUN。Sdist 仅为重建 wheel 的输入；完整源码包含测量比较、NOT_EXECUTED 的 CAD plan、保留历史 a4 来源的静态 STEP 参考及离线效用 history／profile。真实 O3 仍为 PROPOSED／NOT_RUN，实测投入为 UNKNOWN；不新增原生或服务运行。以下 a3 结果仅为历史证据。

[v0.3.0a3 ALPHA 预发布版](https://github.com/sddvacav/opendot/releases/tag/v0.3.0a3)已提供 wheel 与匹配源码；请按[版本固定的中文安装入门](https://github.com/sddvacav/opendot/blob/8d5d8667d65734fb5c40fa0526709a3159b7f165/docs/installed-quickstart.zh-CN.md)核对 SHA-256。[a3 发布说明](https://github.com/sddvacav/opendot/releases/download/v0.3.0a3/RELEASE-NOTES.md)分别记录精确产物、源码、安装及有界可选 Temporal 检查，不能将范围相加或推导科学验收。a3 包含可选有界读取与纯批次准备；后续真实 200 任务及保留投影的证据属于源码范围，不改变冻结发布产物，也不是 200 个智能体。历史版本字节与证据不变；ALPHA、NOT_SCORED 不变，未声称已发布到 PyPI。[公开仓库](https://github.com/sddvacav/opendot)与[议题地址](https://github.com/sddvacav/opendot/issues)已核实；普通问题请提供最小合成复现，不要发布私密输入或环境转储。私密安全报告渠道尚未确立，也没有响应时限承诺。历史 a6 主分支源码 CI 通过 1,183 项检查及另计的 49 项子测试；安装、原生及科学证据的范围分别保留。文档一致性检查不会执行安装指南。
