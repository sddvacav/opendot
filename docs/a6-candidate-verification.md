# 0.2.0a6 candidate verification boundary

Date: 1 October 2026 UTC. Version: **0.2.0a6**, separate and unreleased.
Overall assessment: **NOT_SCORED**. This page freezes the declared contract;
actual results, final source identity, artifact hashes and independent review are
recorded in separately delivered sanitized receipts. No planned count is a pass.

## Integrated changes

- Begin with corrected a5 `365ea900` and preserve its qualified
  [historical verification](a5-candidate-verification.md), CPU-ceiling minimum
  repair and opt-in conditional elastic-energy API
- Include the accepted [read-only increment](readonly-artifacts-verification.md)
  in the same canonical artifact owner. `read_only` is keyword-only, strict bool,
  default false. True avoids setup/write/mode/delete effects and refuses public
  puts before input processing. Reads may update atime; roots/ancestors remain
  trusted, symlinks are followed, and metadata remains outside byte verification
- Preserve the issue-1 bilingual [measurement walkthrough](../examples/measurement-review/README.md)
  with valid, wrong-mean and denied cases, independent pins, exact replay exits,
  retained rejected bytes and existing-output refusal; retrieval/replay use the
  new explicit read-only mode
- Add the [source-boundary example](../examples/source-boundary/README.md): six
  synthetic protocols, nine NOT_IMPLEMENTED/NOT_RUN original proposals, and all
  15 production-enforcement fields NOT_IMPLEMENTED. Fixed caller grants are not
  authentication; post-hoc trajectory checks do not prevent or undo bad effects
- Preserve the dated [public research annex](research/demand-gap-20261001/README.md)
  as source context; no raw browser evidence or private operational logs are shipped

## Predeclared verification scopes

| Scope | Exact selection or contract | Outcome location |
| --- | --- | --- |
| Portable source | 1,183 distinct nodes = corrected a5 1,104 + read-only 41 + source-boundary 38 | Separate a6 author receipt |
| Controlled local source | 1,342 distinct nodes = portable 1,183 + local Git 78 + source-provenance 81, trusted POSIX Git 2.52+ only | Separate a6 author receipt |
| Offline source/docs checks | AST parse, local links/fragments, eight identical installed-guide shell blocks per language, four identical measurement-guide blocks per language, unique explicit node manifests | Separate documentation receipt |
| Offline build | Empty isolated build environment; hash-verified cached setuptools 84.0.0 only; wheel and sdist metadata/payload/RECORD/licenses | Separate build receipt |
| Installed API/examples | Fresh wheel-only environment, isolated imports, copied reviewed examples/test fixtures; no source import paths; strict read-only refusal and no-mutation contract plus synthetic examples | Separate installed receipt |
| English and Chinese installed guides | All eight shell blocks per language in independent fresh environments | Separate guide receipt |
| English and Chinese measurement guides | All four shell blocks per language plus refusal/preservation checks | Separate measurement receipt |
| Release/hosted CI/native/model/GPU/device/browser/remote writes | Not run or authorized by this local integration | NOT_RUN; release remains unpublished |

The source and installed scopes overlap. Repeated checks and 49 existing energy
subtests must never be added as distinct coverage. A controlled-local pass is not
an unrestricted test-discovery pass. Optional native and simulation profiles are
excluded; only the selected portable fake/import/refusal boundaries are covered.

Keep final generated outputs outside source. Source integrity and hashes do not
prove authorship, authorization, scientific validity, production security or
independent acceptance. Historical accepted components do not automatically
approve an integrated wheel or confer a full-platform score.
