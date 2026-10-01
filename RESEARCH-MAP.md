# OpenDot research to feature priorities

[简体中文](RESEARCH-MAP.zh-CN.md) · [Current capability evidence](CAPABILITIES.md)

Snapshot: 1 October 2026. This map turns dated public-source research into testable product choices. Every user need and priority below is a **project inference**, not an instruction from the named source, a buyer interview, or institutional support. Implementation status comes from code and verification records, not from policy, investment commentary or papers.

The source dates and reading limits are carried forward from the six files in [the research collection](docs/research/README.md), reviewed on 1 October 2026. This editorial pass did not conduct a new web retrieval or reproduce external experiments. The collection's README is its synthesis; the other five files cover official strategy, Lidang, Sequoia/HongShan, Hillhouse-related material, and academic research.

**Priority meaning:** P0 = trust/acceptance prerequisites; P1 = a usable scenario or measured adoption/scale experiment; P2 = extension after the first useful workflow. These are sequencing recommendations, not a scoring rubric or delivery commitment. C1–C11 and E1–E3 refer to the capability matrix.

## Source to acceptance map

| ID / priority | Dated sources | User need inferred | Implemented or proposed response | Acceptance required |
| --- | --- | --- | --- | --- |
| R1 / P0 | [S04](#s04), [S09](#s09), [S12](#s12), [S17](#s17) | Know what was accepted and why | C1–C3 implemented: tool status, semantic result and independently checkable bytes. A task-level acceptance interface remains proposed. | Retain success, permission-blocked and semantic-refusal cases; require zero dispatch on refusal and show intact-but-unaccepted bytes after semantic failure. Independent E2 passes only the implemented subset. |
| R2 / P0 | [S01](#s01), [S06](#s06), [S11](#s11) | Change code in a known local working copy and inspect exactly what changed | C4 implemented: pinned create/status/diff, live-manager ownership. Commit, removal, adoption of external commits and remote workflows excluded. | Independent review of all 78 Git cases and installed examples; verify fixed OID/HEAD, two-worktree separation, unchanged index, feature refusals and reported residue. The R1 unknown-versus-absent repair passes the independent real permission-loss source probe; exact successor artifact review remains separate. |
| R3 / P0 | [S02](#s02), [S03](#s03), [S17](#s17) | Connect a reported result to its inputs without treating unknowns as measurements | C2/C5/C10 implemented: byte references, pinned source evidence, conservative adapter provenance. Full data-governance/export policy remains proposed. | Mutate source bytes, locators and declared roles; reject broken bindings; preserve unknown values and scientific=false. For private-data pilots, separately test access revocation and export boundaries. |
| R4 / P0 | [S08](#s08), [S10](#s10), [S11](#s11) | Understand which code and dependencies execute, and with what authority | C6 and declared optional dependency pins implemented. Host isolation, authenticated supply-chain inventory and comprehensive data controls remain proposed. | Check changed-module refusals and original-export identity; inspect exact distributions/notices; separately evaluate untrusted-code isolation. Never count a hash match as authorization or a sandbox. |
| R5 / P0 | [S01](#s01), [S05](#s05), [S20](#s20) | Resume long work without losing state or duplicating effects | Durable orchestration, checkpoints, reconciliation and cancellation propagation are proposed. Current callable state and Git ownership are process-local. | Predeclare interruption/restart cases; measure recovered outcomes, duplicate effects, orphan work and human interventions. Demonstrate safe decisions when effect state is unknown. No current recovery result. |
| R6 / P0 | [S06](#s06), [S18](#s18), [S19](#s19) | Separate automatic checks from judgments a researcher must make | C3 declared permission gate and C7 false scientific/device fields implemented. Task-level human decision points and scientific review workflow remain proposed. | Test missing permission before handler/validator execution; challenge validators with incorrect units, missing evidence and false promotion. Obtain domain review before scientific conclusions. |
| R7 / P1 | [S01](#s01), [S02](#s02), [S15](#s15) | Fit engineering tools into a reproducible useful task | C9 contains narrow domain adapters. A complete reviewed CAD→mesh→solver→result delivery workflow for the current exact environment remains a proposed milestone. | Freeze inputs, units, versions, boundary conditions and tolerances; run native stages separately; compare with an analytic/independent reference; record failures and manual steps. |
| R8 / P1 | [S14](#s14), [S18](#s18) | Rehearse a finite acquisition flow before considering real instruments | C8 implemented fake-only plan, raw documents and strict offline verifier. Real transports, calibration, interlocks and resume are outside it. | Keep current exact-version normal/failure/abort evidence and malformed-document rejection; label SIMULATED_ONLY. Real-device acceptance needs a separate safety and scientific protocol. |
| R9 / P1 | [S05](#s05), [S09](#s09), [S16](#s16), [S19](#s19) | Know whether parallel agents produce more accepted work for the same budget | C11 proposed; no current live-model, multi-host or hundreds-of-agent measurement. Test count and queue depth are not concurrency evidence. | Compare scripted, single-agent and parallel runs on frozen tasks/budgets/tools; measure actual overlap, accepted throughput, all-attempt cost, error acceptance and human review time. |
| R10 / P1 | [S02](#s02), [S07](#s07), [S13](#s13) | Reach the first inspectable result without reconstructing the environment | Bilingual source examples and isolated-wheel guides have a successful separate newcomer walkthrough; exact version and scope belong to its acceptance receipt. Public distribution routes remain unestablished. | The historical 0.2.0a3 a59419b walkthrough installed the exact wheel offline, checked isolated origins and replayed all eight blocks per language; that receipt does not automatically approve successors. Retain fresh-output recovery and extend platform evidence separately; this does not resolve R1. |
| R11 / P1 | [S13](#s13), [S15](#s15), [S20](#s20) | Establish value in a real research or engineering workflow | Buyer interviews, workflow baselines and recurring-use evidence are proposed. No customer, purchase, endorsement or measured savings are claimed. | Agree a real task and acceptance owner; compare all-attempt cost, accepted result quality and human review time with the existing workflow; retain negative and abandoned trials. |
| R12 / P2 | [S01](#s01), [S09](#s09), [S12](#s12) | Add a domain tool without duplicating storage or execution systems | One canonical artifact/callable owner and optional adapters are implemented. A governed skill catalogue and broad consumer migration remain proposed. | For each extension declare inputs/outputs, units, versions, licenses and refusal rules; test owner identity and regressions. Require migration evidence before claiming old consumers switched. |

## Recommended next decision

Finish exact-candidate independent review and the first-run journey, then select one narrow engineering or research reproduction task with a named acceptance owner. Keep recovery and scale as separate experiments with their own stopping rules and denominators. Do not promise speed, savings, unattended duration or scientific progress before those results exist.

## Source register

### S01

[MIIT Artificial Intelligence Plus Software plan](https://www.miit.gov.cn/zwgk/zcwj/wjfb/tz/art/2026/art_49783ce685f042029111c8b6e94f0f30.html) · **2026-09-02 document; 2026-09-11 publication**. Formal policy; attachment read through an official repost. Direction, not project approval.

### S02

[State Council Artificial Intelligence Plus opinion](https://wap.miit.gov.cn/xwfb/szyw/art/2025/art_f8bd63905b384841a84e643c1b9455c7.html) · **2025-08-21 document; 2025-08-26 publication**. Official repost of the formal opinion; no eligibility or compliance conclusion.

### S03

[MIIT and National Data Administration model and data action](https://www.nda.gov.cn/sjj/zwgk/tzgg/0428/20260428215540161552208_pc.html) · **2026-04-24 document; 2026-04-28 publication**. Official notice; scenario assessment and data responsibility are policy context.

### S04

[Lidang on acceptance and independent review](https://x.com/lidangzzz/status/2096078265534292180) · **2026-09-04 displayed date**. Public opinion; original page timezone unspecified; no performance experiment.

### S05

[Lidang on long parallel tasks](https://x.com/lidangzzz/status/2096364825072804152) · **2026-09-05 displayed date**. Opinion and self-report; cited agent counts and durations are not independently reproduced.

### S06

[Lidang on human judgment and local feedback](https://x.com/lidangzzz/status/2097081516371361994) · **2026-09-07 displayed date**. Public distinction between business decisions and locally testable work; not a buyer interview.

### S07

[The Last Math Competition announcement](https://x.com/lidangzzz/status/2098672784754819562) · **2026-09-12 displayed date**. Published workflow proposal and requested artifacts; no OpenDot use or scientific outcome inferred.

### S08

[Lidang on deployment trust](https://x.com/lidangzzz/status/2102102874876436926) · **2026-09-21 displayed date**. Market prediction; no universal deployment requirement inferred.

### S09

[Sequoia Own Your Intelligence](https://sequoiacap.com/article/own-your-intelligence-a-how-to-guide) · **2026-08-19**. Institutional opinion on domain evaluation and feedback; not independent product validation.

### S10

[Sequoia Air investment article](https://sequoiacap.com/article/partnering-with-air-securing-the-ai-supply-chain) · **2026-09-01**. Investment commentary on agent supply-chain risk; security research not reproduced.

### S11

[Sequoia Cymphony investment article](https://sequoiacap.com/article/partnering-with-cymphony-security-unlocks-adoption) · **2026-09-09**. Investment commentary on access visibility and governance.

### S12

[HongShan HarnessEval](https://www.hongshan.com/article/harnesseval%EF%BC%9A%E5%BC%80%E5%90%AFrsi%E6%97%B6%E4%BB%A3%E7%9A%84%E6%96%B0%E8%AF%84%E6%B5%8B%E8%8C%83%E5%BC%8F/) · **2026-08-18**. World-model evaluation discussion; not scientific or engineering acceptance for this package.

### S13

[HongShan early users and target market](https://www.hongshan.com/article/%E6%97%A9%E6%9C%9F%E7%94%A8%E6%88%B7%E2%89%A0%E7%9B%AE%E6%A0%87%E5%B8%82%E5%9C%BA%EF%BC%9Aai%E5%88%9B%E4%B8%9A%E8%80%85%E9%A1%BB%E8%AD%A6%E6%83%95%E7%9A%84%E9%99%B7%E9%98%B1/) · **2026-07-10**. Article sharing book-based ideas; no OpenDot market research.

### S14

[HongShan on agents in work and laboratories](https://www.hongshan.com/article/%E5%BD%93agent%E6%88%90%E4%B8%BA%E8%81%8C%E5%9C%BA%E5%92%8C%E5%AE%9E%E9%AA%8C%E5%AE%A4%E7%9A%84%E9%87%8D%E8%A6%81%E6%90%AD%E5%AD%90/) · **2026-07-08**. Report about other work; external statistics and outcomes do not transfer here.

### S15

[Renmin University Hillhouse AI School and GL Ventures salon report](https://ai.ruc.edu.cn/xwgg/xyxw/635f4ab35d9b45518b03d944acf58904.htm) · **2026-09-16 event; 2026-09-18 report**. Organizer report on technology, careers and entrepreneurship; not an industrial procurement interview.

### S16

[AstaBench](https://arxiv.org/abs/2510.21652v2) · **2026-04-21 v2**. Abstract and metadata reviewed; tool, budget and reproducibility principles, not rerun benchmark results.

### S17

[ScienceAgentBench](https://arxiv.org/abs/2410.05080v3) · **2025-03-31 v3; first submitted 2024-10-07**. Abstract, metadata and official repository reviewed; no experiment reproduced.

### S18

[Co-Scientist in Nature](https://www.nature.com/articles/s41586-026-10644-y) · **2026-05-19**. Abstract, architecture and discussion read; hypotheses require appropriate external experimental evidence.

### S19

[SciAgentArena](https://arxiv.org/abs/2606.12736v1) · **2026-06-10 v1 preprint**. Abstract and metadata only; structured versus open-ended task findings are author reports.

### S20

[Sequoia 2026 This is AGI](https://sequoiacap.com/article/2026-this-is-agi) · **2026-01-14**. Long-task and outcome-value thesis; definitions and forecasts remain author opinion.

## Material not promoted into demand evidence

Hillhouse's institutional website is an undated statement of general orientation; it is not a recent AI strategy announcement. The manufacturing-news item whose body could not be retrieved remains a lead, not a basis for quotations or requirements. Sequoia and HongShan are separate institutions. Investment articles and event participation do not establish a relationship with this project. Academic abstracts and other projects' self-reported agent counts do not establish OpenDot results.

No interviews, procurement commitments, institutional endorsements or scientific experiments were established by this research collection. Formal policy dates, publication dates, article dates, event dates and source-page display dates are deliberately distinguished.


## 2026-10-01 primary-source refresh annex

The sections above preserve the earlier editorial snapshot. A separate web retrieval on 1 October 2026 produced this [public-source refresh](docs/research/refresh-20261001/README.zh-CN.md) and [structured delta](docs/research/refresh-20261001/source-needs-delta.json). The historical compact index remains **18 sources and 22 needs**, byte-for-byte unchanged. This **UNMERGED** annex records **three sources new to the collection and one coverage improvement for an already-known document**, rather than four newly issued sources. In particular, MIIT document 279 was already recorded in the policy research; reading its official republication does not create a second policy. No aggregate source/need total is asserted.

The four mappings below comprise **two new specific hypotheses and two refinements of existing hypotheses**. Need IDs match the separate delta. Every function is **PROPOSED**, every acceptance protocol is **NOT_RUN**, and no row expands current implementation evidence. Priorities are research recommendations, not institutional requirements or delivery commitments.

| Need ID and priority | Source and date | Proposed function | Acceptance oracle and required evidence | State |
| --- | --- | --- | --- | --- |
| `hongshan-opt-in-skill-feedback` / P1 | [HongShan WorkBuddy event report](https://www.hongshan.com/article/%E7%BA%A2%E6%9D%89%E4%B8%AD%E5%9B%BD%E6%88%90%E5%91%98%E4%BC%81%E4%B8%9A%E8%B5%B0%E8%BF%9B%E8%85%BE%E8%AE%AFworkbuddy%EF%BC%8C%E5%85%B1%E6%8E%A2ai-agent%E5%BC%80%E6%94%BE%E7%94%9F%E6%80%81/), 2026-09-20; exact event date unspecified | With authorization, record minimal task-stage events and skill versions to distinguish friction, refusal, cancellation, completion and acceptance. This is a new specific hypothesis from a partner's reported feedback gap, not a HongShan procurement request. | On synthetic traces, inject duplicates, missing terminal events, retries and refusals. Check unique-task and attempt denominators separately; unknown remains unknown. Disable/export tests must demonstrate the declared collection boundary. Real-user demand needs a separate authorized pilot. | PROPOSED / NOT_RUN |
| `sequoia-bounded-context-freshness` / P0 | [Sequoia Empirik article](https://sequoiacap.com/article/partnering-with-empirik-building-the-autonomous-infrastructure-engineer), 2026-09-01 | For one bounded tool, declare observed state identity, time and scope; pause dependent actions when critical preconditions change or cannot be read. This is a new specific hypothesis, not an implemented monitor or recovery mechanism. | Freeze a read-only replay and mutate dependency versions, permissions and external-job state. Old observations must not count as current evidence; unreadable state is unknown; uncovered resources stay outside the claim. Retain change/refusal receipts. | PROPOSED / NOT_RUN |
| `policy-modular-delivery-handoff` / P1 | [MIIT service-provider action](https://wap.miit.gov.cn/jgsj/kjs/wjfb/art/2026/art_331b6f1d28ad410aa9df711acf42dbfe.html), document 414; written 2026-08-27, published 2026-08-31 | Refine existing delivery/handoff work into one versioned workflow package with dependencies, configuration, required authority, acceptance steps and failure-handoff instructions. | An authorized pilot operator independently runs it in a declared clean environment and rehearses a missing dependency and failed-step handoff. Retain all attempts and setup, operation, maintenance and review time. Technical replay alone does not establish adoption. | PROPOSED / NOT_RUN |
| `policy-scenario-acceptance-denominators` / P0 | [Official republication of MIIT document 279](https://sjj.sjz.gov.cn/columns/d3426a1d-930b-4b41-abe0-519a987eeab2/202601/13/8e4cf98c-1465-43e8-a96f-25fe2d938260.html), Appendix 2 sections 13–14, 18 and 20; written 2025-12-25, original publication 2026-01-07, republication 2026-01-13 | Refine existing evaluation work with a frozen scenario card separating tasks, attempts, generated candidates, reviewed candidates and accepted results, with a named acceptance role and criterion. | Inject duplicate, wrong-unit, unreviewed and rejected candidates. Preserve predeclared denominators and pending review; require an appropriate independent reference or domain judgment. Exit status and output counts cannot establish scientific acceptance. Retain trace and rejection evidence. | PROPOSED / NOT_RUN |

Source limits remain material: the HongShan page is an organizer's edited report and its platform response describes future work; the Sequoia page is an investment article; the manufacturing text is an official republication, while the original MIIT PDF remained unreadable and no byte-equivalence check was made. Document 414's 2026-12-01 reporting step applies to regional authorities, not an established application window or eligibility for this project. No policy compliance or endorsement is inferred.

The X profile returned 403 and the candidate original post did not yield text, so this refresh adds no Lidang quote, post date or demand claim. Hillhouse yielded no new usable primary evidence within the bounded search; this does not establish absence of newer statements. The existing State Council official republication was rechecked without adding a new formal document. Sequoia and HongShan remain separate source families.

A synthetic example cannot by itself establish real-user feedback, operational reconciliation, a manufacturing trial, market demand or scientific validity. This annex changes research documentation only; the historical index and implemented capability boundaries remain unchanged.
