# Peer documentation benchmark

Observation date: **2026-09-30 UTC**. Scope: official repository/documentation pages, re-opened while integrating this candidate. This is an editorial comparison of documentation structure, not a performance benchmark, security audit, product ranking, or OpenDot readiness certification. Recommendations are this review's synthesis.

## Source-linked patterns

### Repository metadata snapshot

GitHub's repository API was checked on **2026-10-01 UTC**: OpenHands Software
Agent SDK had **1,190** stars, Temporal **23,397**, and build123d **3,243**.
The [machine-readable snapshot](peer-repository-snapshot.json) records the exact
repositories, API sources and observation date. These changing counts establish
which public projects informed the comparison; they do not measure quality,
adoption of OpenDot, or any expected star count. The editorial observations below
retain their separate 2026-09-30 review date.

| Official reference | Observed pattern | Application to this bounded package |
| --- | --- | --- |
| [OpenHands Software Agent SDK README](https://github.com/OpenHands/software-agent-sdk#readme) | Usage example, explicit repository boundaries, and links to concepts, guides, API reference, and examples | Lead with the actual two module commands and distinguish the adapter package from future coordination work |
| [OpenHands getting started](https://docs.openhands.dev/sdk/getting-started) | Prerequisites, installation, first-agent output, and warnings about matched package versions | Put requirements and expected JSON fields beside the first example; keep optional backend versions separate from runtime-free checks |
| [Temporal server README](https://github.com/temporalio/temporal#readme) | Server scope and links for local startup, samples, and inspecting work | State what owns execution and what evidence the reader can inspect; do not inherit workflow durability claims from a reference |
| [build123d README](https://github.com/gumyr/build123d#readme) | Domain-oriented examples, installation paths, documentation, and contribution links | Connect optional adapter guides to a concrete synthetic domain contract and disclose backend requirements |
| [build123d documentation](https://build123d.readthedocs.io/en/latest/index.html) | Concepts, introductory examples, tutorials, and reference learning paths | Separate quickstart, architecture, contract references, and future evidence requirements |

## Where this candidate stands

The candidate provides bilingual runnable synthetic checks, module references, architecture boundaries, contribution/security/support pages, and release gates. Those are documentation and local-check improvements, not parity with any peer product. Public destinations, supported versions, native qualification, runtime lifecycle evidence, and independent release approval remain separate open requirements.

## Recommended sequence

1. Keep capability wording tied to actual code and scope-limited checks
2. Independently reproduce the small source and installed-wheel examples
3. Verify publication, support, private reporting, rights, and outgoing artifact contents
4. Add domain/native tutorials only after matching environments and evidence exist
5. Expand runtime claims only after separate implementation and reproducible evaluation

## Limits

These are live documentation URLs, not immutable source snapshots. The review did not execute peer installation commands, audit their source/security, or reproduce peer performance claims. No star-based ranking, score, logo, badge, copied example, endorsement, partnership, or integration claim is inferred. Recheck version-sensitive information before a later launch comparison.
