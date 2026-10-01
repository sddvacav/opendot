# Security and responsible reporting

This is an unreleased bounded adapter package. Narrow local checks exist, but no comprehensive security audit, sandbox guarantee, supported-release policy, or private reporting destination is asserted.

## Reporting a vulnerability

Do not post exploit details, secrets, private traces, or customer data in a public issue or discussion. Until a private reporting destination is verified, retain the report securely and request a private channel without disclosing the vulnerability itself. No email address, response SLA, bounty, or supported-version guarantee is established here.

A minimal private report should identify the affected public version, impact, prerequisites, a synthetic reproducer, and a proposed mitigation if known. Share only what investigation requires.

## Current boundaries

The source-audit adapter checks bounded local files, independent expected pins, no-symlink reads, schema/role consistency, and declared access categories. Declared access is not content classification or authorization. A falsely labeled confidential file may still be confidential. The synthetic qualification adapter evaluates invented fixture records and retains explicit false scientific/device-qualification flags.

These read-only examples do not invoke models, networks, native solvers, or devices. Optional CAD/CAE adapters have a different execution boundary: separately prepared native tools and generated provenance require dedicated review. Recorded provenance may include absolute paths and enclosing Git metadata. Keep it outside source/distribution trees and inspect exports before sharing.

The optional [source-admission adapter](docs/source-admission.md) executes only
a captured, explicitly listed source snapshot after checking independent expected
pins. Source pins establish byte identity, not permission to execute or distribute
code. Reviewed Python retains normal absolute imports and file, network, or
process side effects. Namespace checks are cooperative bookkeeping; they do not
pin dependencies, prevent hostile interpreter mutation, or establish complete
executable-code identity. Failure cleanup removes only still-owned namespace
objects, not external effects. Reconcile effects before any retry, and keep
propagated source exceptions and diagnostic logs private.

An in-process wrapper is not a sandbox. The caller remains responsible for permissions, authorized inputs, dependency selection, artifact storage, and downstream actions. See the [current architecture](docs/architecture.md) and adapter references for contract details.

## Future runtime requirements

Broader agent/runtime work would add risks from untrusted content, external calls, repeated side effects, stale approval, spend, orphaned work, and disclosure in logs. Permission enforcement, isolation, resource limits, cancellation/cleanup, retention, and approval rechecks would require implementation and independent testing. These are future requirements, not current package protections.

## Publication hard gate

Review the actual outgoing source, archives, wheel members, images, logs, screenshots, metadata, any included history, notices, and destinations before release. Unresolved privacy, security, rights, or identity findings block publication. Automated scanning is a bounded check and cannot replace contextual review or authorize release. See the [release checklist](docs/release-checklist.md).

## 中文摘要

本包有有限范围的本地检查，但不声称完成全面安全审计或提供沙箱保证。访问标签不能自动识别机密内容；原生后端回执可能包含路径或 Git 元数据。私密漏洞报告渠道尚未核实，不要在公开渠道发布敏感细节。发现隐私、安全、权利或身份问题时必须停止发布并重新复核。

## Optional simulated lab boundary

The [simulated-lab adapter](docs/simulated-lab.md) constructs fake devices internally
and runs a finite fixed plan in an isolated Python child with a minimal environment,
dummy ophyd control layer, and an eight-second process timeout. These controls are
not an OS sandbox, hardware interlock, hard-real-time guarantee, or dependency
supply-chain audit. Verification checks the exact tested document profile and
independent manifest pin; it cannot authenticate measurements or authorize devices.
Dependency versions and declared simulation status are retained in evidence. Keep
generated bundles and dependency/build metadata outside public source until reviewed.
