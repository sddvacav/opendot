# Getting help with OpenDot Engineering

Canonical public support and private security-reporting destinations are not verified for this source candidate. Do not guess an address or repository from the project name. Maintainers must verify and test the actual destinations before inviting reports.

## Choose the right report

- Usage: the goal, documentation section, and unclear step
- Bug: expected and observed behavior, public version, environment category, and a small synthetic reproducer
- Feature: the problem, scope, acceptance criteria, and alternatives
- Security/privacy: follow [Security](SECURITY.md) without publishing sensitive details

Use [the issue template](templates/issue-report.md) only through a verified destination. Remove secrets, confidential inputs, user identities, private paths, and hidden metadata. Do not paste complete environment dumps or conversation histories.

## Known limits

| Question | Current answer |
| --- | --- |
| Can I run anything now? | Yes: the [README callable/artifact example](README.md#run-the-synthetic-examples), [installed quickstart](docs/installed-quickstart.md), and [read-only help](docs/module-cli.md); their scopes are bounded |
| Is there a public installation destination? | Not verified; a locally checked wheel is not a published release |
| Is the current candidate accepted? | The unreleased a4 candidate has 1,066 selected author source passes; exact final artifact and installed acceptance are [pending](docs/verifier-ci-verification.md). Predecessor passes do not approve it |
| Does the documentation checker run the examples? | No; it checks bounded local links/fragments, explicit HTML anchors and eight matching nonempty shell blocks per guide language. Installed execution is separate |
| What platforms are supported? | Local checks used Linux/CPython 3.12; a supported matrix is not established; source auditing requires POSIX no-symlink path operations |
| Do the examples need a model or native solver? | No; optional CAD/CAE adapters have separate backend requirements |
| Is this a complete agent runtime? | No; orchestration, durable recovery, and agent scale are outside this package |
| Are peer projects integrated? | The documentation comparison establishes no integration or affiliation |
| Can confidential inputs be shared? | No blanket confidential-data handling guarantee is made; never publish private inputs or receipts |
| When will I receive help? | No response commitment or SLA is established |

See [getting started](docs/getting-started.md#troubleshooting) for safe first checks and [claim status](docs/claim-status.md) for evidence boundaries.

## 中文摘要

当前可以运行 README 中的函数／产物示例，使用完整安装指南或只读帮助入口；尚未核实公开下载和正式支持地址。不要根据名称猜测仓库或邮箱。普通问题使用最小合成复现；安全与隐私问题只向经过核实的私密渠道报告。当前 a4 有 1,066 项指定作者源码检查通过，最终精确产物与安装验收仍待完成；文档一致性检查不会执行安装指南。没有承诺平台支持范围或响应期限。
