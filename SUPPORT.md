# Getting help with OpenDot Engineering

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
| Can I run anything now? | Yes: the [README callable/artifact example](README.md#run-the-synthetic-examples), [installed quickstart](docs/installed-quickstart.md), and [read-only help](docs/module-cli.md); their scopes are bounded |
| Is there a public installation destination? | The [v0.2.0a6 ALPHA prerelease](https://github.com/sddvacav/opendot/releases/tag/v0.2.0a6) provides reviewed wheel/source assets; follow the [installed guide](docs/installed-quickstart.md). No PyPI installation is claimed |
| What has been checked? | The [a6 main source CI](https://github.com/sddvacav/opendot/actions/runs/36885554336) passed 1,183 portable checks plus 49 separate subtests. Local source, build and installed checks retain their [own scopes](docs/a6-candidate-verification.md); source CI does not prove scientific acceptance |
| Does the documentation checker run the examples? | No; it checks bounded local links/fragments, explicit HTML anchors and eight matching nonempty shell blocks per guide language. Installed execution is separate |
| What platforms are supported? | Local checks used Linux/CPython 3.12; a supported matrix is not established; source auditing requires POSIX no-symlink path operations |
| Do the examples need a model or native solver? | No; optional CAD/CAE adapters have separate backend requirements |
| Is this a complete agent runtime? | No; orchestration, durable recovery, and agent scale are outside this package |
| Are peer projects integrated? | The documentation comparison establishes no integration or affiliation |
| Can confidential inputs be shared? | No blanket confidential-data handling guarantee is made; never publish private inputs or receipts |
| When will I receive help? | No response commitment or SLA is established |

See [getting started](docs/getting-started.md#troubleshooting) for safe first checks and [claim status](docs/claim-status.md) for evidence boundaries.

## 中文摘要

当前可从 [v0.2.0a6 ALPHA 预发布版](https://github.com/sddvacav/opendot/releases/tag/v0.2.0a6)取得 wheel 与匹配源码，再使用安装指南、README 示例或只读帮助入口。[公开仓库](https://github.com/sddvacav/opendot)与[议题地址](https://github.com/sddvacav/opendot/issues)已核实；普通问题请提供最小合成复现，不要发布私密输入或环境转储。私密安全报告渠道尚未确立，也没有响应时限承诺。a6 主分支源码 CI 通过 1,183 项检查及另计的 49 项子测试；安装、原生及科学证据的范围分别保留。文档一致性检查不会执行安装指南。
