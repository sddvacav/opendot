# Scope-limited description drafts

Current copy for the **0.3.0a2 ALPHA prerelease**, as of 2 October 2026.
These descriptions are for review; this file does not publish them. Keep the
release status and limits attached. Use the [announcement draft](../LAUNCH-COPY.md)
for the fuller bilingual update and historical copy.

## Short description

**English**

OpenDot Engineering is an experimental Python toolkit for local callable
execution and inspectable artifacts. Store outputs by SHA-256 and check byte
integrity separately from result acceptance. The 0.3.0a2 ALPHA prerelease is
available; it is not a complete agent runtime or a scientifically qualified platform.

**简体中文**

OpenDot Engineering 是一套用于本地函数执行和产物检查的实验性 Python 工具包。
按 SHA-256 保存输出，并分别检查字节完整性与结果验收。0.3.0a2 ALPHA
预发布版已可下载；它不是完整的智能体运行时，也不是经过科学资格验证的平台。

## First action to pair with the description

**English**

Try the [version-pinned installed quickstart](installed-quickstart.md). Its first
callable-to-artifact result needs only the released wheel and Python 3.12+ in a
trusted POSIX environment. No model key, service or native solver is needed.
The guide shows what success looks like, where bytes are saved, and how later
examples retain a rejected result or block a call with missing permission.

**简体中文**

试用[版本固定的安装入门](installed-quickstart.zh-CN.md)。在可信 POSIX 环境中，
第一个从函数到产物的结果只需已发布的 wheel 与 Python 3.12+，无需模型密钥、
服务或原生求解器。指南说明成功输出、字节保存位置，以及后续示例如何保留被拒绝
的结果或阻止缺少权限的调用。

## Release and review guardrails

- Link the [published a2 assets](https://github.com/sddvacav/opendot/releases/tag/v0.3.0a2),
  [exact release notes](https://github.com/sddvacav/opendot/releases/download/v0.3.0a2/RELEASE-NOTES.md)
  and [claim status](claim-status.md). No PyPI publication is claimed
- The later [bounded-read change](decisions/005-bounded-artifact-reads.md) is not in
  frozen a2 assets; current source documentation is not a new release
- Keep optional dependency and trust requirements with optional-feature claims.
  Permissions are dispatch checks, and trusted-root storage follows symlinks;
  neither establishes an OS sandbox or scientific/device authority
- Preserve **NOT_SCORED**. Do not infer production readiness, general recovery,
  unmeasured scale, security certification, adoption, support guarantees,
  endorsement, affiliation or peer integration from a local check or reference
- Preserve [LICENSE](../LICENSE), [NOTICE](../NOTICE) and the separate
  [artwork notice](../assets/brand/NOTICE). Do not invent badges, testimonials,
  source URLs, private contacts, adoption counts or launch dates
