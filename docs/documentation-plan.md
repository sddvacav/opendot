# Documentation maintenance plan

This plan concerns the bounded adapter package. It does not schedule or authorize publication.

## Reader paths

| Reader | Question | Start |
| --- | --- | --- |
| New visitor | What is included and what is future work? | [README](../README.md) and [claim status](claim-status.md) |
| Evaluator | Can I run a small example and inspect the result? | [Getting started](getting-started.md), [source checks](verification-status.md), and [integration checks](integration-review.md) |
| Contributor | Where should a change live and how is it tested? | [Contributing](../CONTRIBUTING.md) and [architecture](architecture.md) |
| Integrator | What does an adapter actually guarantee? | Adapter references linked from the README; their limitations remain authoritative |
| Reporter | Where can I safely ask for help? | [Support](../SUPPORT.md) and [Security](../SECURITY.md) |

## Decisions still needed

- Verify canonical source/download destinations, maintainer ownership, review process, and private reporting
- Establish supported platform and optional-backend matrices from actual checks
- Review distribution rights, outgoing files, dependency notices, and asset policy
- Approve a scope-limited release with known issues and any applicable migration guidance
- Keep any broader runtime/API proposal separate from this package's documented capabilities

## Maintenance rule

Update affected source, tests, fixtures, commands, references, limitations, and both README languages together. Rebuild and inspect the wheel when metadata or README content changes. Recheck relative links, anchors, images, SVG resource safety, and final package members after edits. Automated checks complement contextual review; they do not prove privacy or runtime safety.

A command that no longer has matching evidence must be labeled and removed from the recommended path until revalidated. Keep failed, skipped, and not-run results visible. The [proposed readiness checklist](proposed-release-readiness.md) remains unadopted and assigns no aggregate.
