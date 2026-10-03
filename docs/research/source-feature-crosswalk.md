# OpenDot source requirement feature and acceptance crosswalk

Documentation-only crosswalk · 2026-10-03 · Public-source research only · ALPHA / NOT_SCORED

This crosswalk joins all 22 existing compact-index needs to their 18 historical source records (17 with publication dates and one explicitly undated), current source/test locations, and narrowly scoped evidence. Every original requirement, priority, PROPOSED implementation field and NOT_RUN acceptance field is retained in the companion JSON. Existing code supplies partial mechanisms; it does not close the full source-inspired requirements. No institution-backed demand, buyer validation or scientific acceptance is established.

This three-path documentation integration adds the Markdown/JSON crosswalk and one research README navigation link. It changes no runtime, tests or historical manifest, and performs no product execution or remote edit. Source observations are inherited. The prior October 2 retrieval audit is not publicly available; its observations are attributed rather than presented as independently replayable evidence. The October 1 Lidang post remains BLOCKED_403/unverified on that later recheck, with no new body or quotation.

Public base: [commit f45f2be4c2bbc858055db2eebb08cf61fc92342f](https://github.com/sddvacav/opendot/commit/f45f2be4c2bbc858055db2eebb08cf61fc92342f), tree `8244ca5fd791f15c30a29ef3f420c7045447e338`. The companion JSON distinguishes these base identities from the README navigation addition. Current status pages report [0.3.0a5 published](https://github.com/sddvacav/opendot/releases/tag/v0.3.0a5) after [PR #49](https://github.com/sddvacav/opendot/pull/49); frozen preparation records remain historical. No release acceptance transfers between versions. All current file hashes and locators are refreshed against this base, with the appended README navigation line pinned separately as part of the documentation integration. Historical evidence revisions, outcomes and receipt URLs are unchanged; refreshed code and record-file pins do not transfer prior execution acceptance to the current source.

[PR #48](https://github.com/sddvacav/opendot/pull/48) merged the bounded fixed-DAG source and compatibility changes. Its [recorded compatibility run](https://github.com/sddvacav/opendot/actions/runs/37078409130) covered 1484 pure/SDK checks and the seven original reference service cases, not the new DAG service. New DAG service recovery remains NOT_RUN; actual crash/process fencing is NOT_EVALUATED and external-effect authenticity NOT_PROVED. These inherited CI/publication facts were not fetched or replayed for this document; [ADR 008](../decisions/008-fixed-dependent-temporal-recovery.md) defines the narrow source contract.

## Read the chain

1. A source entry preserves whose statement was recorded, its dates, reading scope and limitations
2. A need preserves the exact historical ID, inferred need, proposed feature, priority and oracle
3. A feature link identifies current code/tests by path and SHA-256; it is an editorial coverage link, not a new requirement or pass
4. An evidence link identifies the exact older revision or says no execution receipt is supplied. Full need acceptance remains NOT_RUN

P0 and P1 retain the historical project sequencing. The rationale added here is an editorial inference, never a source-authored specification or a delivery commitment. Document-local F/EV IDs organize this closed document; they add no production registry. Existing R IDs are related narrative requirements, not interchangeable aliases for the compact need IDs.

[Machine-readable crosswalk](source-feature-crosswalk.json) · [Historical 18-source / 22-need index](source-needs-index.json) · [Research map](../../RESEARCH-MAP.md) · [Capability record](../../CAPABILITIES.md)

## Priority and current coverage at a glance

| Existing need ID | Priority | Current feature links | Full historical oracle |
| --- | --- | --- | --- |
| [synthesis-reviewed-outcomes](#synthesis-reviewed-outcomes) | P0 | [F01](#feature-f01), [F02](#feature-f02), [F05](#feature-f05) | NOT_RUN |
| [policy-durable-execution](#policy-durable-execution) | P0 | [F12](#feature-f12), [F09](#feature-f09), [F10](#feature-f10) | NOT_RUN |
| [policy-industrial-adapter](#policy-industrial-adapter) | P1 | [F07](#feature-f07), [F08](#feature-f08) | NOT_RUN |
| [policy-science-evidence](#policy-science-evidence) | P1 | [F03](#feature-f03), [F02](#feature-f02) | NOT_RUN |
| [policy-data-boundaries](#policy-data-boundaries) | P0 | [F03](#feature-f03), [F06](#feature-f06), [F13](#feature-f13) | NOT_RUN |
| [lidang-independent-verification](#lidang-independent-verification) | P0 | [F01](#feature-f01), [F02](#feature-f02), [F05](#feature-f05) | NOT_RUN |
| [lidang-artifact-chain](#lidang-artifact-chain) | P1 | [F01](#feature-f01), [F02](#feature-f02) | NOT_RUN |
| [sequoia-domain-evaluation](#sequoia-domain-evaluation) | P1 | [F11](#feature-f11), [F15](#feature-f15) | NOT_RUN |
| [sequoia-supply-chain](#sequoia-supply-chain) | P0 | [F04](#feature-f04), [F03](#feature-f03) | NOT_RUN |
| [hongshan-oracle-boundaries](#hongshan-oracle-boundaries) | P0 | [F05](#feature-f05), [F02](#feature-f02), [F06](#feature-f06) | NOT_RUN |
| [hongshan-market-validation](#hongshan-market-validation) | P1 | [F14](#feature-f14), [F11](#feature-f11) | NOT_RUN |
| [hillhouse-industry-hypothesis](#hillhouse-industry-hypothesis) | P1 | [F07](#feature-f07), [F08](#feature-f08), [F14](#feature-f14) | NOT_RUN |
| [academic-controlled-benchmark](#academic-controlled-benchmark) | P0 | [F15](#feature-f15), [F11](#feature-f11) | NOT_RUN |
| [eda-continuous-verification](#eda-continuous-verification) | P0 | [F01](#feature-f01), [F02](#feature-f02), [F05](#feature-f05), [F06](#feature-f06) | NOT_RUN |
| [eda-recovery-reconciliation](#eda-recovery-reconciliation) | P0 | [F12](#feature-f12), [F09](#feature-f09), [F10](#feature-f10) | NOT_RUN |
| [eda-ip-governance](#eda-ip-governance) | P0 | [F03](#feature-f03), [F06](#feature-f06), [F13](#feature-f13) | NOT_RUN |
| [eda-tool-contracts](#eda-tool-contracts) | P1 | [F07](#feature-f07), [F03](#feature-f03) | NOT_RUN |
| [eda-fair-performance](#eda-fair-performance) | P1 | [F11](#feature-f11), [F15](#feature-f15) | NOT_RUN |
| [hillhouse-wangbei-reliable-execution](#hillhouse-wangbei-reliable-execution) | P0 | [F12](#feature-f12), [F09](#feature-f09), [F01](#feature-f01) | NOT_RUN |
| [hillhouse-wangbei-domain-validity](#hillhouse-wangbei-domain-validity) | P0 | [F07](#feature-f07), [F08](#feature-f08), [F02](#feature-f02), [F05](#feature-f05) | NOT_RUN |
| [hillhouse-wangbei-full-delivery-cost](#hillhouse-wangbei-full-delivery-cost) | P0 | [F11](#feature-f11), [F15](#feature-f15) | NOT_RUN |
| [hillhouse-liliang-human-handoff](#hillhouse-liliang-human-handoff) | P1 | [F14](#feature-f14), [F01](#feature-f01) | NOT_RUN |

## Source records

Publication, composition, event and consulted-version dates are distinct. Unknown dates and timezones remain unknown. A local summary heading is not an original-page paragraph locator; missing primary selectors are explicitly disclosed. Sequoia Capital and HongShan remain separate source families.

### cn-state-council-ai-plus-2025-11

[国务院关于深入实施人工智能加行动的意见](https://wap.miit.gov.cn/xwfb/szyw/art/2025/art_f8bd63905b384841a84e643c1b9455c7.html) · OFFICIAL_REPUBLICATION · S02

Dates: composition date: 2025-08-21; publication date: 2025-08-26. Publication timezone: unknown. Recorded access: 2026-10-01.
Origin: publisher 工业和信息化部官方转载; issuer 国务院; named author not retained; attributed speaker not retained.
Recorded source position: Policy direction for AI research, engineering implementation and applications; project qualification is not established.
Reading scope: Full official-republication text recorded; original central-government URL was blocked.
Primary-content locator: Official republication, II science and technology items 1–2, as retained in official-strategy.md.
Local record: [docs/research/official-strategy.md](official-strategy.md) → “A. 国务院“人工智能+”总纲” (snapshot pin in JSON).
Limits: 依据官方转载核验全文；中国政府网原地址在原研究中返回403; 政策背景不构成OpenDot资格、合规、采购或背书

### cn-miit-ai-software-2026-209

[人工智能加软件专项行动实施方案](https://www.miit.gov.cn/zwgk/zcwj/wjfb/tz/art/2026/art_49783ce685f042029111c8b6e94f0f30.html) · OFFICIAL_POLICY · S01

Dates: composition date: 2026-09-02; publication date: 2026-09-11. Publication timezone: unknown. Recorded access: 2026-10-01.
Origin: publisher 工业和信息化部; issuer 工业和信息化部; named author not retained; attributed speaker not retained.
Recorded source position: Policy directions include reliable task execution, industrial-software integration, traceable behavior and reusable resources.
Reading scope: MOFCOM official-republication attachment body recorded; MIIT notice metadata separately rechecked; issuer attachment bytes not verified equivalent.
Primary-content locator: Official-republication attachment: item (5) p3; items (7)–(9) pp4–5; item (19) p7. Need-specific details remain project inference.
Local record: [docs/research/official-strategy.md](official-strategy.md) → “B. “人工智能+软件”正式实施方案” (snapshot pin in JSON).
Limits: 全文阅读范围为商务部官方转载附件；工信部原附件直链未读取成功; 未验证两个附件副本的字节一致性；产品映射不是原文要求

October 2 audit overlay: issuer-page metadata and attachment entry confirmed; attachment content was not newly read. This is inherited audit evidence, not a new retrieval by this crosswalk.

### cn-miit-nda-model-data-2026-193

[2026年模数共振行动通知](https://www.nda.gov.cn/sjj/zwgk/tzgg/0428/20260428215540161552208_pc.html) · OFFICIAL_POLICY · S03

Dates: composition date: 2026-04-24; publication date: 2026-04-28. Publication timezone: unknown. Recorded access: 2026-10-01.
Origin: publisher 国家数据局; issuer 工业和信息化部办公厅、国家数据局综合司; named author not retained; attributed speaker not retained.
Recorded source position: Policy describes scenario evaluation and responsibilities for industry data collaboration.
Reading scope: Official notice body recorded; no OpenDot eligibility or compliance conclusion.
Primary-content locator: Notice II(2), II(3), II(4), as retained in official-strategy.md.
Local record: [docs/research/official-strategy.md](official-strategy.md) → “D. 2026年“模数共振”行动” (snapshot pin in JSON).
Limits: 通知面向指定主体；不可推断OpenDot已适格或已有申报窗口; 不得把转载日期写成首发日期

### x-lidang-2096078265534292180

[多agent独立质疑与测试观点](https://x.com/lidangzzz/status/2096078265534292180) · PUBLIC_SOCIAL_POST · S04

Dates: publication date: 2026-09-04. Publication timezone: unknown. Recorded access: 2026-10-01.
Origin: publisher X / @lidangzzz; issuer not identified / not applicable; named author lidang 立党 (@lidangzzz); attributed speaker lidang 立党 (@lidangzzz).
Recorded source position: Personal view that task boundaries, testing and independent scrutiny are needed to assess agent output.
Reading scope: Inherited original-post body observation; quantitative expressions not independently reproduced.
Primary-content locator: Whole linked original post; displayed 2026-09-04 20:29, timezone unspecified.
Local record: [docs/research/lidang.md](lidang.md) → “1 结果是否可信 是多 agent 的核心问题” (snapshot pin in JSON).
Limits: 原站显示9月4日20:29，界面时区未标示；未归一化为UTC; 为个人公开观点，未独立复现其数量或性能表达

### x-lidang-2098672784754819562

[The Last Math Competition发布规则](https://x.com/lidangzzz/status/2098672784754819562) · PUBLIC_SOCIAL_POST · S07

Dates: publication date: 2026-09-12. Publication timezone: unknown. Recorded access: 2026-10-01.
Origin: publisher X / @lidangzzz; issuer not identified / not applicable; named author lidang 立党 (@lidangzzz); attributed speaker lidang 立党 (@lidangzzz).
Recorded source position: Competition announcement proposes reviewed proof/counterexample artifacts and continuing result feedback.
Reading scope: Inherited original-post body observation; rules are not evidence of achieved scale or scientific results.
Primary-content locator: Whole linked original post; displayed 2026-09-12 00:19, timezone unspecified.
Local record: [docs/research/lidang.md](lidang.md) → “4 科学工作需要完整成果链” (snapshot pin in JSON).
Limits: 原站显示9月12日0:19，界面时区未标示；未归一化为UTC; 竞赛规则不证明规模已实现、科学突破或OpenDot需求

### sequoia-own-intelligence-20260819

[Own Your Intelligence](https://sequoiacap.com/article/own-your-intelligence-a-how-to-guide) · INVESTOR_OFFICIAL_ARTICLE · S09

Dates: publication date: 2026-08-19. Publication timezone: unknown. Recorded access: 2026-10-01.
Origin: publisher Sequoia Capital; issuer not identified / not applicable; named author not retained; attributed speaker not retained.
Recorded source position: Investor essay advocates domain evaluation and feedback, with quality, speed and cost considered together.
Reading scope: Article-level summary recorded; finer original-page section/paragraph selector not retained.
Primary-content locator: No finer original-page selector retained; local summary locator is not a primary-content locator.
Local record: [docs/research/sequoia-hongshan.md](sequoia-hongshan.md) → “一、已读取的机构官网材料与原始研究入口” (snapshot pin in JSON).
Limits: 机构观点不是独立效果验证; 不能推断需要自行训练基础模型或替换所有闭源模型

### sequoia-air-supply-chain-20260901

[Partnering with Air Securing the AI Supply Chain](https://sequoiacap.com/article/partnering-with-air-securing-the-ai-supply-chain) · INVESTOR_PORTFOLIO_ARTICLE · S10

Dates: publication date: 2026-09-01. Publication timezone: unknown. Recorded access: 2026-10-01.
Origin: publisher Sequoia Capital; issuer not identified / not applicable; named author not retained; attributed speaker not retained.
Recorded source position: Investment article highlights runtime supply-chain risks from agent skills, plugins and dependencies.
Reading scope: Article-level summary recorded; underlying security research not reproduced.
Primary-content locator: No finer original-page selector retained; local summary locator is not a primary-content locator.
Local record: [docs/research/sequoia-hongshan.md](sequoia-hongshan.md) → “一、已读取的机构官网材料与原始研究入口” (snapshot pin in JSON).
Limits: 为投资说明，存在投资关系背景; 原研究未复现文中安全研究；不是OpenDot安全认证

### hongshan-harnesseval-20260818

[HarnessEval评测文章](https://www.hongshan.com/article/harnesseval%EF%BC%9A%E5%BC%80%E5%90%AFrsi%E6%97%B6%E4%BB%A3%E7%9A%84%E6%96%B0%E8%AF%84%E6%B5%8B%E8%8C%83%E5%BC%8F/) · INVESTOR_OFFICIAL_ARTICLE · S12

Dates: publication date: 2026-08-18. Publication timezone: unknown. Recorded access: 2026-10-01.
Origin: publisher HongShan; issuer not identified / not applicable; named author not retained; attributed speaker not retained.
Recorded source position: Investor-hosted evaluation discussion emphasizes task-appropriate tools, evidence and evaluator limitations.
Reading scope: Article-level summary recorded; world-model evaluation is not engineering or science acceptance.
Primary-content locator: No finer original-page selector retained; local summary locator is not a primary-content locator.
Local record: [docs/research/sequoia-hongshan.md](sequoia-hongshan.md) → “一、已读取的机构官网材料与原始研究入口” (snapshot pin in JSON).
Limits: 世界模型评测案例不能直接等同工程仿真或科学发现验收; Sequoia与HongShan是分别记录的来源家族

### hongshan-early-users-20260710

[早期用户与目标市场](https://www.hongshan.com/article/%E6%97%A9%E6%9C%9F%E7%94%A8%E6%88%B7%E2%89%A0%E7%9B%AE%E6%A0%87%E5%B8%82%E5%9C%BA%EF%BC%9Aai%E5%88%9B%E4%B8%9A%E8%80%85%E9%A1%BB%E8%AD%A6%E6%83%95%E7%9A%84%E9%99%B7%E9%98%B1/) · INVESTOR_OFFICIAL_ARTICLE · S13

Dates: publication date: 2026-07-10. Publication timezone: unknown. Recorded access: 2026-10-01.
Origin: publisher HongShan; issuer not identified / not applicable; named author not retained; attributed speaker not retained.
Recorded source position: Book-based market discussion distinguishes early enthusiast interest from broader target-user demand.
Reading scope: Article-level summary recorded; no OpenDot market study.
Primary-content locator: No finer original-page selector retained; local summary locator is not a primary-content locator.
Local record: [docs/research/sequoia-hongshan.md](sequoia-hongshan.md) → “一、已读取的机构官网材料与原始研究入口” (snapshot pin in JSON).
Limits: 官网分享书中观点，不是机构对OpenDot的市场调研

### hillhouse-institution-home

[Hillhouse Investment机构首页](https://www.hillhouseinvestment.com/) · INSTITUTIONAL_WEBSITE · not in the historical S01–S20 register

Dates: undated. Publication timezone: unknown. Recorded access: 2026-10-01.
Origin: publisher Hillhouse Investment; issuer not identified / not applicable; named author not retained; attributed speaker not retained.
Recorded source position: Undated institutional homepage supplies general long-term industry/value orientation only.
Reading scope: General homepage statement; no dated recent AI speech or buyer requirement.
Primary-content locator: No finer original-page selector retained; local summary locator is not a primary-content locator.
Local record: [docs/research/hillhouse-industry.md](hillhouse-industry.md) → “核实结果” (snapshot pin in JSON).
Limits: 首页没有对应近期AI演讲日期; 只能说明一般长期取向；弱需求证据，非买方访谈或采购意向

### ruc-glventures-ai-salon-20260918

[人大高瓴人工智能学院与GL Ventures活动回顾](https://ai.ruc.edu.cn/xwgg/xyxw/635f4ab35d9b45518b03d944acf58904.htm) · UNIVERSITY_OFFICIAL_EVENT_REPORT · S15

Dates: publication date: 2026-09-18; event date: 2026-09-16. Publication timezone: unknown. Recorded access: 2026-10-01.
Origin: publisher 中国人民大学高瓴人工智能学院; issuer not identified / not applicable; named author not retained; attributed speaker 方静怡.
Recorded source position: University event report describes a joint AI salon and attributed discussion of deployment opportunities and long-term development.
Reading scope: University organizer report; not speech transcript; other participating companies are not Hillhouse speakers.
Primary-content locator: No finer original-page selector retained; local summary locator is not a primary-content locator.
Local record: [docs/research/hillhouse-industry.md](hillhouse-industry.md) → “核实结果” (snapshot pin in JSON).
Limits: 主办方报道，不是演讲全文；活动主要面向人才、职业发展和创业交流; 受邀企业观点不能全部归为高瓴；不能由参会推定投资或采购; 弱需求证据，未确认OpenDot支付意愿或部署需求

### astabench-2510-21652-v2

[AstaBench v2](https://arxiv.org/abs/2510.21652v2) · RESEARCH_PAPER_PREPRINT · S16

Dates: publication date: 2026-04-21; version: v2. Publication timezone: unknown. Recorded access: 2026-10-01.
Origin: publisher arXiv; research authors; issuer not identified / not applicable; named author not retained; attributed speaker not retained.
Recorded source position: Abstract-level research account motivates controlled tool access, budgets, reproducible tasks and adequate baselines.
Reading scope: Abstract and metadata only; no experiment reproduced.
Primary-content locator: arXiv 2510.21652v2 abstract and metadata.
Local record: [docs/research/academic-needs.md](academic-needs.md) → “一、来源与可采用的原则” (snapshot pin in JSON).
Limits: 继承阅读范围为摘要及元数据；原记录称条目注明ICLR2026; 未运行论文实验或基准；产品映射为研究建议

### scienceagentbench-2410-05080-v3

[ScienceAgentBench v3](https://arxiv.org/abs/2410.05080v3) · RESEARCH_PAPER_PREPRINT · S17

Dates: publication date: 2025-03-31; first publication date: 2024-10-07; version: v3. Publication timezone: unknown. Recorded access: 2026-10-01.
Origin: publisher arXiv; research authors; issuer not identified / not applicable; named author not retained; attributed speaker not retained.
Recorded source position: Abstract-level research account motivates reproducible programs/results, domain-checked tasks and cost evaluation.
Reading scope: Abstract plus official-repository verification; complete methods not audited; no benchmark run.
Primary-content locator: arXiv 2410.05080v3 abstract/metadata and linked official repository.
Local record: [docs/research/academic-needs.md](academic-needs.md) → “一、来源与可采用的原则” (snapshot pin in JSON).
Limits: 所列发布日期为v3更新；首次提交另列，不混用; 继承阅读范围为摘要及官方仓库核验；未运行基准

### siemens-fuse-launch-20260316

[Siemens launches Fuse EDA AI Agent](https://news.siemens.com/en-us/siemens-fuse-eda-ai-agent/) · VENDOR_PRESS_RELEASE · not in the historical S01–S20 register

Dates: publication date: 2026-03-16. Publication timezone: unknown. Recorded access: 2026-10-01.
Origin: publisher Siemens; issuer not identified / not applicable; named author not retained; attributed speaker not retained.
Recorded source position: Vendor announcement describes cross-tool EDA orchestration, recovery, IP governance and domain-format challenges.
Reading scope: Vendor press-release body recorded; not independent implementation or compatibility validation.
Primary-content locator: No finer original-page selector retained; local summary locator is not a primary-content locator.
Local record: [docs/research/industry-cases.md](industry-cases.md) → “S1 2026 年 3 月 16 日发布稿” (snapshot pin in JSON).
Limits: 厂商发布主张，不是独立性能验证或OpenDot兼容性证据; 不据此确定每项能力普遍可用；不构成合作或背书

### siemens-self-verifying-blog-20260729

[Self-verifying long-running EDA AI agents](https://blogs.sw.siemens.com/cicv/2026/07/29/self-verifying-eda-ai-agents/) · VENDOR_PRODUCT_BLOG · not in the historical S01–S20 register

Dates: publication date: 2026-07-29. Publication timezone: unknown. Recorded access: 2026-10-01.
Origin: publisher Siemens EDA; issuer not identified / not applicable; named author Emma-Jane Crozier; attributed speaker not retained.
Recorded source position: Vendor blog describes domain-engine checking of intermediate results and a library-characterization delivery workflow.
Reading scope: Product-blog body recorded; author is product marketing manager; demonstrations not reproduced.
Primary-content locator: No finer original-page selector retained; local summary locator is not a primary-content locator.
Local record: [docs/research/industry-cases.md](industry-cases.md) → “S2 2026 年 7 月 29 日产品博客” (snapshot pin in JSON).
Limits: 作者为Siemens EDA产品市场经理，属于厂商叙述; 阅读页面正文，未观看或复现演示；无人值守不取消签核责任; 概括性生产运行表述不足以确定全部扩展功能可用性

### siemens-nvidia-dac-20260726

[Siemens advances self-verifying agentic AI workflows](https://news.siemens.com/en-us/siemens-nvidia-dac-2026/) · VENDOR_PRESS_RELEASE · not in the historical S01–S20 register

Dates: publication date: 2026-07-26. Publication timezone: unknown. Recorded access: 2026-10-01.
Origin: publisher Siemens; issuer not identified / not applicable; named author not retained; attributed speaker not retained.
Recorded source position: Vendor announcement makes workflow time/cost claims and says expanded capabilities are intended for later releases.
Reading scope: Press-release body recorded; performance protocol incomplete, so no OpenDot comparison or general availability inference.
Primary-content locator: Body and Availability paragraph, as retained in industry-cases.md.
Local record: [docs/research/industry-cases.md](industry-cases.md) → “S3 2026 年 7 月 26 日相关发布稿” (snapshot pin in JSON).
Limits: 性能倍数为厂商自述，缺完整独立复现协议; Availability称扩展能力将在后续版本提供；部分客户引语为计划测试; 不可将厂商数字迁移为OpenDot性能、ROI或已实现能力

### glventures-wangbei-waves-20260624

[王蓓在WAVES 2026圆桌的发言整理稿](https://www.36kr.com/p/3866900608701449) · EVENT_ORGANIZER_EDITED_TRANSCRIPT · not in the historical S01–S20 register

Dates: publication date: 2026-06-24; event date: 2026-06-16. Publication timezone: unknown. Recorded access: 2026-10-01.
Origin: publisher 36氪; issuer not identified / not applicable; named author 未来一氪; attributed speaker 王蓓.
Recorded source position: Named investor remarks concern reliable paid work, engineering/data/scenario integration, physical constraints and economic outcomes.
Reading scope: Organizer-edited speaker-separated transcript; unedited video not checked; not a Hillhouse corporate strategy.
Primary-content locator: Consecutive Agent application, investment-judgment and AI-for-Science Q&A; Wang Bei answers only.
Local record: [docs/research/hillhouse-primary-addendum.zh-CN.md](hillhouse-primary-addendum.zh-CN.md) → “S1 王蓓在 WAVES 2026 的圆桌发言” (snapshot pin in JSON).
Limits: 发言归属限于高瓴创投合伙人王蓓的回答；主办方36氪整理编辑，不是高瓴官网声明或全机构统一政策; 未核对未经剪辑的原始录像；不归入同台其他嘉宾或主持人的判断及数字; 页面显示2026-06-24 16:17，时区未标明；活动为2026-06-16上午，不能混用发表日与活动日; 具名公开观点可直接核对，但对OpenDot用户需求仍仅有间接参考价值；没有采购、采用、投资或合作证据

### hillhouse-liliang-zgc-20260330

[李良在中关村论坛AI未来论坛的发言报道](https://www.chinaventure.com.cn/news/80-20260330-390728.html) · EVENT_ORGANIZER_ORIGINAL_REPORT · not in the historical S01–S20 register

Dates: publication date: 2026-03-30; event date: 2026-03-29. Publication timezone: unknown. Recorded access: 2026-10-01.
Origin: publisher 投中网; issuer not identified / not applicable; named author 张楠; attributed speaker 李良.
Recorded source position: Named investor remarks concern organizational collaboration, human–AI coexistence and transition costs.
Reading scope: Organizer original report with paraphrases and some quotes, not complete verbatim Q&A or institution-wide policy.
Primary-content locator: Paragraphs explicitly attributed to Li Liang in the linked original event report.
Local record: [docs/research/hillhouse-primary-addendum.zh-CN.md](hillhouse-primary-addendum.zh-CN.md) → “S2 李良在中关村论坛的发言报道” (snapshot pin in JSON).
Limits: 仅采用明确归于高瓴创始合伙人李良的发言；不作为高瓴全机构统一政策; 活动方网站原创报道包含作者转述及少量引语，不是完整逐字稿；证据强度低于逐人整理稿; 页面显示2026-03-30 17:32:37，时区未标明；活动为2026-03-29下午，不能混用发表日与活动日; 只提供组织采用的间接研究线索，不证明任何具体部署架构、软件采购要求或OpenDot合作意向

## Existing needs and acceptance

Every need below retains historical implementation PROPOSED and full-need acceptance NOT_RUN. Narrower feature/evidence descriptions do not change those states. The Chinese need/feature/oracle text below is preserved from the compact index. The current-coverage commentary and priority explanations are this crosswalk’s explicit project inferences. No original case ID existed in that index; the exact inline oracle and JSON pointer are retained rather than inventing case identifiers.

## synthesis-reviewed-outcomes

Priority: P0 · PROJECT_INFERENCE · related narrative: R1
Sources: [x-lidang-2096078265534292180](#x-lidang-2096078265534292180), [cn-miit-ai-software-2026-209](#cn-miit-ai-software-2026-209)
Inferred need: 任务完成需要可核对的结果和失败说明
Historical proposed feature: 任务验收项、成果及失败回执
Why this priority: Trustworthy completion must be distinguishable from tool exit and intact bytes before a professional task is accepted.
Original acceptance oracle: 独立检查路径验收成功案例，并在冻结错误集中拒绝不合格成果；报告错误接受和未知状态
Expected evidence: 成果清单; 独立验收回执; 负例结果
Current partial coverage: [F01](#feature-f01), [F02](#feature-f02), [F05](#feature-f05)
Acceptance gap: Task-wide independent acceptance and frozen error-acceptance outcomes remain unrun.
Authoritative record: [docs/research/source-needs-index.json](source-needs-index.json) → /needs/0; summary [docs/research/README.md](README.md) → “汇总后的产品决策建议”.

## policy-durable-execution

Priority: P0 · PROJECT_INFERENCE · related narrative: R5
Sources: [cn-miit-ai-software-2026-209](#cn-miit-ai-software-2026-209)
Inferred need: 复杂任务需要可恢复执行和清楚的中断状态
Historical proposed feature: 检查点、受控重试、取消传播、外部副作用对账
Why this priority: Unknown effects after interruption can duplicate work or cost; recovery is a prerequisite before long-task claims.
Original acceptance oracle: 在预先登记任务集中注入中断，记录恢复成功率、重复副作用及取消后残留任务
Expected evidence: 故障注入记录; 恢复回执; 任务分母与成本
Current partial coverage: [F12](#feature-f12), [F09](#feature-f09), [F10](#feature-f10)
Acceptance gap: The original interruption/reconciliation/cancellation oracle is NOT_RUN; graceful first delivery and recorded replay are narrower.
Authoritative record: [docs/research/source-needs-index.json](source-needs-index.json) → /needs/1; summary [docs/research/official-strategy.md](official-strategy.md) → “1. 可靠完成复杂任务，而非只展示一次输出”.

## policy-industrial-adapter

Priority: P1 · PROJECT_INFERENCE · related narrative: R7, R12
Sources: [cn-miit-ai-software-2026-209](#cn-miit-ai-software-2026-209)
Inferred need: 工程工具融合需要保持单位、参数、版本与失败语义
Historical proposed feature: 版本化CAD/CAE连接器和领域验收合同
Why this priority: Domain integration is a narrow scenario milestone after trust prerequisites.
Original acceptance oracle: 在声明的解析基准上测误差与网格收敛，拒绝单位错配；真实后端与合成fixture分开列示
Expected evidence: 输入配置; 工具版本; 解析对照结果; 拒绝案例
Current partial coverage: [F07](#feature-f07), [F08](#feature-f08)
Acceptance gap: Full native exact-environment CAD/mesh/solver contract and domain acceptance remain NOT_RUN.
Authoritative record: [docs/research/source-needs-index.json](source-needs-index.json) → /needs/2; summary [docs/research/official-strategy.md](official-strategy.md) → “3. CAD/CAE等工业工具的集成与边界清晰的验证”.

## policy-science-evidence

Priority: P1 · PROJECT_INFERENCE · related narrative: R3, R6
Sources: [cn-state-council-ai-plus-2025-11](#cn-state-council-ai-plus-2025-11)
Inferred need: 科研到工程应用需要关联来源、假设、计算与结论
Historical proposed feature: 假设卡、来源审计、复算入口及反例记录
Why this priority: A reproducible evidence chain supports a first research workflow; source identity is a foundation rather than scientific proof.
Original acceptance oracle: 独立复算已声明结果，检查每条结论的证据覆盖；生成内容不能自动提升为实验结果
Expected evidence: 来源清单; 参数清单; 复算回执; 结论证据映射
Current partial coverage: [F03](#feature-f03), [F02](#feature-f02)
Acceptance gap: Hypothesis/reference/counterexample completeness and qualified domain review are not established.
Authoritative record: [docs/research/source-needs-index.json](source-needs-index.json) → /needs/3; summary [docs/research/official-strategy.md](official-strategy.md) → “4. 支持科研到工程实现的证据链”.

## policy-data-boundaries

Priority: P0 · PROJECT_INFERENCE · related narrative: R3, R4
Sources: [cn-miit-nda-model-data-2026-193](#cn-miit-nda-model-data-2026-193)
Inferred need: 跨主体数据协作需要限定用途、范围和责任
Historical proposed feature: 数据用途声明、访问范围、保留期限及导出审批
Why this priority: Access and export boundaries must precede real-data pilots.
Original acceptance oracle: 跨项目隔离、撤权后拒绝及禁止导出字段检出测试；只用授权或合成样本
Expected evidence: 数据流说明; 隔离测试; 撤权回执
Current partial coverage: [F03](#feature-f03), [F06](#feature-f06), [F13](#feature-f13)
Acceptance gap: Cross-project isolation, revocation, retention and forbidden-export enforcement remain NOT_RUN.
Authoritative record: [docs/research/source-needs-index.json](source-needs-index.json) → /needs/4; summary [docs/research/official-strategy.md](official-strategy.md) → “7. 数据协作先明确边界和责任”.

Historical limitations: 数据审计组件不能自称可信数据空间认证

## lidang-independent-verification

Priority: P0 · PROJECT_INFERENCE · related narrative: R1, R6
Sources: [x-lidang-2096078265534292180](#x-lidang-2096078265534292180)
Inferred need: 大量agent产出仍需独立检查才能建立信任
Historical proposed feature: 可执行验收器、独立复核及明确失败状态
Why this priority: Independent error checks are a trust prerequisite when output quantity exceeds human review capacity.
Original acceptance oracle: 验证者读取原始产物，在冻结负例中检出已知错误；展示未通过项和仍未知项
Expected evidence: 验证日志; 原始产物; 失败说明
Current partial coverage: [F01](#feature-f01), [F02](#feature-f02), [F05](#feature-f05)
Acceptance gap: Fixed arithmetic/synthetic checks do not establish general independent human or scientific review.
Authoritative record: [docs/research/source-needs-index.json](source-needs-index.json) → /needs/5; summary [docs/research/lidang.md](lidang.md) → “1 结果是否可信 是多 agent 的核心问题”.

Historical limitations: 个人观点不是支付或采用意愿

## lidang-artifact-chain

Priority: P1 · PROJECT_INFERENCE · related narrative: R1, R10
Sources: [x-lidang-2098672784754819562](#x-lidang-2098672784754819562)
Inferred need: 协作研究需要可评审的成果包与质量反馈
Historical proposed feature: 按任务组织报告、源文件、验证项目及评审状态
Why this priority: A bounded inspectable artifact package is useful for a first scenario, before broader collaboration.
Original acceptance oracle: 自有示例从任务进入到成果包交付可重放，记录拒收原因与未完成项
Expected evidence: 成果包; 评审回执; 重放说明
Current partial coverage: [F01](#feature-f01), [F02](#feature-f02)
Acceptance gap: General task-to-delivery replay and accountable review workflow remain NOT_RUN; no third-party competition submission.
Authoritative record: [docs/research/source-needs-index.json](source-needs-index.json) → /needs/6; summary [docs/research/lidang.md](lidang.md) → “4 科学工作需要完整成果链”.

Historical limitations: 不向原竞赛自动提交内容；竞赛发布不等于已实现规模

## sequoia-domain-evaluation

Priority: P1 · PROJECT_INFERENCE · related narrative: R9
Sources: [sequoia-own-intelligence-20260819](#sequoia-own-intelligence-20260819)
Inferred need: 后端选择应由领域质量、成本与速度的共同评测支持
Historical proposed feature: 版本化评测协议与后端比较
Why this priority: Backend choice needs quality/cost/time comparisons under the same protocol.
Original acceptance oracle: 相同任务、验收标准及权限下比较全部尝试；失败进入分母
Expected evidence: 冻结协议; 版本清单; 质量成本耗时报告
Current partial coverage: [F11](#feature-f11), [F15](#feature-f15)
Acceptance gap: Real matched backend/model comparison and measured utility remain NOT_RUN; no model call executed.
Authoritative record: [docs/research/source-needs-index.json](source-needs-index.json) → /needs/7; summary [docs/research/sequoia-hongshan.md](sequoia-hongshan.md) → “二、OpenDot 的产品选择（我们的推断）”.

## sequoia-supply-chain

Priority: P0 · PROJECT_INFERENCE · related narrative: R4
Sources: [sequoia-air-supply-chain-20260901](#sequoia-air-supply-chain-20260901)
Inferred need: agent技能与插件引入需要管理的供应链风险
Historical proposed feature: 依赖及技能来源清单、许可记录和权限审查
Why this priority: Unreviewed executable inputs make provenance, licenses and authority prerequisites.
Original acceptance oracle: 检查来源、版本、许可与权限字段；越权和恶意输入测试单独报告
Expected evidence: 供应链清单; 许可清单; 权限测试
Current partial coverage: [F04](#feature-f04), [F03](#feature-f03)
Acceptance gap: Comprehensive authenticated supply-chain inventory, malicious-input isolation and permission governance remain unproven.
Authoritative record: [docs/research/source-needs-index.json](source-needs-index.json) → /needs/8; summary [docs/research/sequoia-hongshan.md](sequoia-hongshan.md) → “三、拟定演示与文档验收”.

Historical limitations: 哈希一致不能证明安全或授权；投资文章不是认证

## hongshan-oracle-boundaries

Priority: P0 · PROJECT_INFERENCE · related narrative: R1, R6
Sources: [hongshan-harnesseval-20260818](#hongshan-harnesseval-20260818)
Inferred need: 评测需要适合任务的工具和明确的评测者边界
Historical proposed feature: 任务专用验证器与证据关联
Why this priority: A validator must preserve unknowns and be challenged with known errors before its verdict is trusted.
Original acceptance oracle: 对已知正例、错误和超范围输入检验验证器，能力不足返回未知
Expected evidence: 验证器资格结果; 证据关联; 未知案例
Current partial coverage: [F05](#feature-f05), [F02](#feature-f02), [F06](#feature-f06)
Acceptance gap: A task/domain-general evaluator qualification and science-specific false-acceptance protocol remain NOT_RUN.
Authoritative record: [docs/research/source-needs-index.json](source-needs-index.json) → /needs/9; summary [docs/research/sequoia-hongshan.md](sequoia-hongshan.md) → “二、OpenDot 的产品选择（我们的推断）”.

Historical limitations: 世界模型评测经验不能直接当作工程验证结论

## hongshan-market-validation

Priority: P1 · PROJECT_INFERENCE · related narrative: R11
Sources: [hongshan-early-users-20260710](#hongshan-early-users-20260710)
Inferred need: 早期科技爱好者热情不足以代表目标市场
Historical proposed feature: 分人群访谈及真实任务试点协议
Why this priority: Adoption requires real target users and repeated task observations after a bounded workflow exists.
Original acceptance oracle: 取得经同意的真实任务、验收负责人和持续使用观察；无访谈不记作需求验证
Expected evidence: 访谈记录模板; 试点验收协议; 持续使用记录
Current partial coverage: [F14](#feature-f14), [F11](#feature-f11)
Acceptance gap: Real interviews, consented pilots, ongoing use and willingness to pay remain NOT_RUN; fixture reports do not validate demand.
Authoritative record: [docs/research/source-needs-index.json](source-needs-index.json) → /needs/10; summary [docs/research/sequoia-hongshan.md](sequoia-hongshan.md) → “二、OpenDot 的产品选择（我们的推断）”.

Historical limitations: 本轮未开展访谈、招募或外部联络

## hillhouse-industry-hypothesis

Priority: P1 · PROJECT_INFERENCE · related narrative: R7, R11
Sources: [hillhouse-institution-home](#hillhouse-institution-home), [ruc-glventures-ai-salon-20260918](#ruc-glventures-ai-salon-20260918)
Inferred need: 长期行业价值值得用可复现案例与实际流程效果检验
Historical proposed feature: 一个范围清楚的工程演示和后续用户验证计划
Why this priority: Indirect industry context merits one narrow reproducible case before user validation.
Original acceptance oracle: 外部使用者按公开数据重放；真实企业需求另立访谈及验收，不以机构文章或活动代替
Expected evidence: 公开重放包; 验证计划
Current partial coverage: [F07](#feature-f07), [F08](#feature-f08), [F14](#feature-f14)
Acceptance gap: External-user replay, real enterprise fit and business value remain NOT_RUN; institutional background is weak indirect evidence.
Authoritative record: [docs/research/source-needs-index.json](source-needs-index.json) → /needs/11; summary [docs/research/hillhouse-industry.md](hillhouse-industry.md) → “对OpenDot的可操作推断”.

Historical limitations: LIMITED_INDIRECT：机构一般表述与职业创业活动报道只提供弱背景; 没有高瓴或GL Ventures采购、采用、投资或合作证据

## academic-controlled-benchmark

Priority: P0 · PROJECT_INFERENCE · related narrative: R9
Sources: [astabench-2510-21652-v2](#astabench-2510-21652-v2), [scienceagentbench-2410-05080-v3](#scienceagentbench-2410-05080-v3)
Inferred need: 科研agent评测需要控制工具与预算并评价可复现实物结果
Historical proposed feature: 冻结数据、工具权限、预算和全部尝试分母的评测包
Why this priority: Controlled tools, budgets, denominators and independent criteria are prerequisites to meaningful research-agent comparisons.
Original acceptance oracle: 相同任务协议比较人工或脚本、单agent和并行agent；保留失败及成本，独立重放
Expected evidence: 基线协议; 任务分母; 独立重放; 成本账
Current partial coverage: [F15](#feature-f15), [F11](#feature-f11)
Acceptance gap: Manual/script, single-agent and parallel-agent trials and external benchmark reproductions remain NOT_RUN.
Authoritative record: [docs/research/source-needs-index.json](source-needs-index.json) → /needs/12; summary [docs/research/academic-needs.md](academic-needs.md) → “三、最小公开科研评测包提案”.

Historical limitations: 论文基准未运行；采用前需核验许可及污染风险

## eda-continuous-verification

Priority: P0 · PROJECT_INFERENCE · related narrative: R1, R6
Sources: [siemens-self-verifying-blog-20260729](#siemens-self-verifying-blog-20260729)
Inferred need: 专业工程中间结果需要由领域工具检查
Historical proposed feature: 执行、产物、领域验证、人工批准分层状态
Why this priority: Domain results need explicit accepted/rejected/unknown states before professional delivery.
Original acceptance oracle: 冻结合法、错误、缺证据和超时输入；未知不能被合并为通过
Expected evidence: 分层回执; 正负例矩阵
Current partial coverage: [F01](#feature-f01), [F02](#feature-f02), [F05](#feature-f05), [F06](#feature-f06)
Acceptance gap: No EDA domain signoff, authentic human approval or general professional validation is established.
Authoritative record: [docs/research/source-needs-index.json](source-needs-index.json) → /needs/13; summary [docs/research/industry-cases.md](industry-cases.md) → “需求 功能 验收 优先级映射”.

Historical limitations: 不是芯片签核能力证明

## eda-recovery-reconciliation

Priority: P0 · PROJECT_INFERENCE · related narrative: R5
Sources: [siemens-fuse-launch-20260316](#siemens-fuse-launch-20260316)
Inferred need: 长时编排需要可控恢复
Historical proposed feature: 检查点、持久状态与外部作业对账
Why this priority: Uncertain external-job identity must stop duplicate submissions rather than create unapproved cost.
Original acceptance oracle: 在提交前及提交后未记账时注入中断；不能确认作业身份时暂停，不盲目重复增加成本
Expected evidence: 中断记录; 作业身份; 对账及恢复回执
Current partial coverage: [F12](#feature-f12), [F09](#feature-f09), [F10](#feature-f10)
Acceptance gap: Original before/after-submit interruption and external-effect reconciliation protocol remains NOT_RUN.
Authoritative record: [docs/research/source-needs-index.json](source-needs-index.json) → /needs/14; summary [docs/research/industry-cases.md](industry-cases.md) → “需求 功能 验收 优先级映射”.

## eda-ip-governance

Priority: P0 · PROJECT_INFERENCE · related narrative: R4
Sources: [siemens-fuse-launch-20260316](#siemens-fuse-launch-20260316)
Inferred need: 设计IP需要可审计的访问和执行边界
Historical proposed feature: 任务权限、工具白名单、网络出口策略与敏感值遮蔽
Why this priority: Design IP and secrets require explicit boundaries before a real professional-tool pilot.
Original acceptance oracle: 阻断越界文件与未授权出口，日志不得含测试密钥；离线能力限定到实测流程
Expected evidence: 权限拒绝证据; 日志脱敏检查; 离线测试
Current partial coverage: [F03](#feature-f03), [F06](#feature-f06), [F13](#feature-f13)
Acceptance gap: No enforced network egress, comprehensive secret redaction, hostile-file isolation, air gap or security certification.
Authoritative record: [docs/research/source-needs-index.json](source-needs-index.json) → /needs/15; summary [docs/research/industry-cases.md](industry-cases.md) → “需求 功能 验收 优先级映射”.

Historical limitations: 未做隔离测试不得宣称气隙或安全认证

## eda-tool-contracts

Priority: P1 · PROJECT_INFERENCE · related narrative: R7, R12
Sources: [siemens-fuse-launch-20260316](#siemens-fuse-launch-20260316)
Inferred need: 异构专业工具需要保留数据语义
Historical proposed feature: 版本化工具契约、原生格式连接器及单位约束
Why this priority: A first domain workflow needs version, unit and lineage contracts before broader format/tool expansion.
Original acceptance oracle: 检查产物可读、参数传递和版本兼容；拒绝错误单位、过期格式及缺依赖输入
Expected evidence: 连接器契约; 版本矩阵; 负例记录
Current partial coverage: [F07](#feature-f07), [F03](#feature-f03)
Acceptance gap: Full native compatibility, native-format semantic preservation and actual EDA connectors remain NOT_RUN.
Authoritative record: [docs/research/source-needs-index.json](source-needs-index.json) → /needs/16; summary [docs/research/industry-cases.md](industry-cases.md) → “需求 功能 验收 优先级映射”.

## eda-fair-performance

Priority: P1 · PROJECT_INFERENCE · related narrative: R9, R11
Sources: [siemens-nvidia-dac-20260726](#siemens-nvidia-dac-20260726)
Inferred need: 效率主张应在相同结果质量门槛下比较
Historical proposed feature: 固定评测协议、全量成本账及耗时分解
Why this priority: Time/cost claims become meaningful only at an equal accepted-result threshold.
Original acceptance oracle: 冻结任务、工具、硬件、模型和预算；统计失败，分别列人工、排队、工具和模型耗时
Expected evidence: 基线协议; 全部尝试成本; 质量门槛; 阶段耗时
Current partial coverage: [F11](#feature-f11), [F15](#feature-f15)
Acceptance gap: Real frozen hardware/model/tool comparison, phase timing and all-attempt costs remain NOT_RUN; vendor multiples do not transfer.
Authoritative record: [docs/research/source-needs-index.json](source-needs-index.json) → /needs/17; summary [docs/research/industry-cases.md](industry-cases.md) → “需求 功能 验收 优先级映射”.

Historical limitations: 厂商倍数不移植为OpenDot性能；扩展功能可用性仍有限定

## hillhouse-wangbei-reliable-execution

Priority: P0 · PROJECT_INFERENCE · related narrative: R5
Sources: [glventures-wangbei-waves-20260624](#glventures-wangbei-waves-20260624)
Inferred need: 长任务中断后，用户需要判断结果是否有效、是否可恢复
Historical proposed feature: 持久任务状态、检查点、失败分类与受控恢复；执行状态和结果验收分开
Why this priority: Reliability and truthful failure status are prerequisites for long paid-task trials.
Original acceptance oracle: 固定同一工作流，注入进程退出、依赖超时和输出拒收；未验收结果不得报成功。恢复须证明外部副作用不会重复提交，无法确认时转人工
Expected evidence: 冻结工作流及故障注入协议; 恢复前后事件记录; 结果验收回执; 副作用核对或人工接管记录
Current partial coverage: [F12](#feature-f12), [F09](#feature-f09), [F01](#feature-f01)
Acceptance gap: Full injected exit/timeout/output-rejection recovery with nonduplicated effects and human takeover remains NOT_RUN.
Authoritative record: [docs/research/source-needs-index.json](source-needs-index.json) → /needs/18; summary [docs/research/hillhouse-primary-addendum.zh-CN.md](hillhouse-primary-addendum.zh-CN.md) → “来源到需求和验收的映射”.

Historical limitations: 王蓓的可靠性观点未指定检查点、重试或对账方案；这些均是OpenDot设计推断; 未实现持久恢复或证明幂等执行；不以元数据声明代替运行时保障

## hillhouse-wangbei-domain-validity

Priority: P0 · PROJECT_INFERENCE · related narrative: R6, R7
Sources: [glventures-wangbei-waves-20260624](#glventures-wangbei-waves-20260624)
Inferred need: 工程结果需要按明确领域标准复核
Historical proposed feature: 版本化输入与求解器、单位及适用范围校验、独立领域判定接口
Why this priority: Physical/engineering constraints require declared references and domain-specific rejection before a trial.
Original acceptance oracle: 公开可重放的有界算例附参考解或明确基准与预先声明的容差；错误单位、越界参数及不收敛样本应被拒收
Expected evidence: 版本化输入及求解器清单; 参考解或基准与容差; 独立重放结果; 拒收样本及回执
Current partial coverage: [F07](#feature-f07), [F08](#feature-f08), [F02](#feature-f02), [F05](#feature-f05)
Acceptance gap: Current native reference solution, convergence, independent numerical/domain and physical/scientific qualification remain open.
Authoritative record: [docs/research/source-needs-index.json](source-needs-index.json) → /needs/19; summary [docs/research/hillhouse-primary-addendum.zh-CN.md](hillhouse-primary-addendum.zh-CN.md) → “来源到需求和验收的映射”.

Historical limitations: 从王蓓关于科学与产业物理约束的观点推断，非其提出的具体软件规格; 软件通过与字节一致不等于实物、科学结论或真实工程部件被验证

## hillhouse-wangbei-full-delivery-cost

Priority: P0 · PROJECT_INFERENCE · related narrative: R9, R11
Sources: [glventures-wangbei-waves-20260624](#glventures-wangbei-waves-20260624)
Inferred need: 用户需要比较一个合格成果的完整交付成本
Historical proposed feature: 同任务基线与结果账本，记录全部尝试、失败、复核、运行资源和接入工作量
Why this priority: Complete accepted-delivery cost and review effort are prerequisites to judging economic benefit.
Original acceptance oracle: 相同输入和验收口径下，列全人工时间、总耗时、运行费用和合格结果数；公开失败分母与一次性接入成本
Expected evidence: 冻结基线与验收协议; 全部尝试及失败分母; 人工及运行成本账; 合格成果清单
Current partial coverage: [F11](#feature-f11), [F15](#feature-f15)
Acceptance gap: Actual all-attempt monetary/person-time and accepted-outcome comparison remains NOT_RUN; measured effort UNKNOWN.
Authoritative record: [docs/research/source-needs-index.json](source-needs-index.json) → /needs/20; summary [docs/research/hillhouse-primary-addendum.zh-CN.md](hillhouse-primary-addendum.zh-CN.md) → “来源到需求和验收的映射”.

Historical limitations: 从王蓓对经济效果的讨论推断验收方案，非机构要求的ROI模型; 本轮没有成本或利润提升实测；小样本不得外推为持续ROI

## hillhouse-liliang-human-handoff

Priority: P1 · PROJECT_INFERENCE · related narrative: R6, R11
Sources: [hillhouse-liliang-zgc-20260330](#hillhouse-liliang-zgc-20260330)
Inferred need: 人员需要把新流程接入日常职责并在出错时接管
Historical proposed feature: 可配置任务负责人、审批点、人工接管和交接记录，限定一个明确流程
Why this priority: Organizational handoff needs a consented scenario, responsibility agreement and observed burden after basic mechanics.
Original acceptance oracle: 经授权的试点用户独立完成首次任务与一次失败接管；记录培训、维护和复核负担，由用户确认责任分工
Expected evidence: 用户授权及试点范围; 首次任务和失败接管记录; 培训维护复核负担; 责任分工确认
Current partial coverage: [F14](#feature-f14), [F01](#feature-f01)
Acceptance gap: Actual unaided first task, failure takeover, training/maintenance/review observations and user confirmation remain NOT_RUN.
Authoritative record: [docs/research/source-needs-index.json](source-needs-index.json) → /needs/21; summary [docs/research/hillhouse-primary-addendum.zh-CN.md](hillhouse-primary-addendum.zh-CN.md) → “来源到需求和验收的映射”.

Historical limitations: 从报道中的李良组织协作观点推断，审批点和接管机制并非原文产品规格; 本轮未访谈、招募或外部联络；模拟演示不能代替真实采用、留存或付费证据

## Current feature and test locations

Every feature below has current exact-snapshot qualification NOT_RUN_BY_THIS_DRAFT and no new execution receipt; that legacy label means this document-only authoring pass. All source/test files below were inspected statically and SHA-256 pinned in JSON. Named test functions are locators, not collected parametrized node identities or an executed test count. No test or example was run for this document. Present file hashes do not transfer predecessor acceptance or accept an a5 artifact.

## Feature F01

Callable outcomes and retained artifacts · PARTIAL_SYNTHETIC · C1, C2, C3
Coverage: Separates permitted completion, semantic refusal with intact unaccepted bytes, and zero-dispatch permission refusal on fixed synthetic inputs.
Open boundary: No task-wide acceptance authority, independent human/scientific review, rollback, durable recovery or broad result guarantee. Historical example review belongs to its exact older bytes.
Source: [src/opendot_engineering/tool_runtime.py](../../src/opendot_engineering/tool_runtime.py); [src/opendot_engineering/core/artifacts.py](../../src/opendot_engineering/core/artifacts.py); [src/opendot_engineering/core/contracts.py](../../src/opendot_engineering/core/contracts.py); [examples/measurement-review/demo.py](../../examples/measurement-review/demo.py)
Scope record: [examples/measurement-review/README.md](../../examples/measurement-review/README.md) → “Existing single-role demo”
Test locator: [tests/test_callable_artifacts.py](../../tests/test_callable_artifacts.py) → `test_success_returns_canonical_reference_and_verified_bytes`, `test_semantic_refusal_retains_integrity_without_returning_result`, `test_missing_permission_never_invokes_handler_or_writes_object`
Test locator: [tests/test_measurement_review_example.py](../../tests/test_measurement_review_example.py) → `test_valid_roundtrip`, `test_wrong_mean_retains_unaccepted_bytes`, `test_denied_dispatch`, `test_expected_pin_mismatch`
Evidence: [EV01](#evidence-ev01), [EV02](#evidence-ev02)

## Feature F02

Six-row measurement comparison · PARTIAL_SYNTHETIC
Coverage: Exactly six invented A/B rows, fixed tolerance evidence and three scripted roles; rational arithmetic and saved-evidence bindings are checked.
Open boundary: CHECKED may be outside tolerance. No real measurement, native execution, autonomous agents, science acceptance or human review.
Source: [examples/measurement-review/compare.py](../../examples/measurement-review/compare.py); [examples/measurement-review/comparison-fixtures.json](../../examples/measurement-review/comparison-fixtures.json)
Scope record: [examples/measurement-review/README.md](../../examples/measurement-review/README.md) → “Compare A and B against a declared tolerance”
Test locator: [tests/test_measurement_comparison_example.py](../../tests/test_measurement_comparison_example.py) → `test_frozen_fraction_oracles`, `test_tolerance_blocks_dependents`, `test_deny_each_role_stops_dependents`, `test_wrong_computation_retains_rejected_bytes`, `test_independent_verifier_never_calls_producers_or_dispatch`, `test_resealed_report_forgery_refuses`
Evidence: [EV03](#evidence-ev03)

## Feature F03

Local source and adapter provenance · PARTIAL_SYNTHETIC · C5, C10
Coverage: Checks pinned local bytes, evidence roles, exact locators and conservative source membership; preserves unknown/nonmeasurement distinctions.
Open boundary: Declared access is not authorization/enforcement; hashes are not truth, rights or authenticated identity. No cross-project revocation, retention or export system.
Source: [src/opendot_engineering/adapters/source_audit.py](../../src/opendot_engineering/adapters/source_audit.py); [src/opendot_engineering/executors/geometry.py](../../src/opendot_engineering/executors/geometry.py)
Scope record: [docs/local-source-audit.md](../local-source-audit.md) → “Contract”
Test locator: [tests/test_source_audit.py](../../tests/test_source_audit.py) → `test_synthetic_read_only_receipt_is_not_science_acceptance`, `test_private_inputs_need_private_audience`, `test_censored_is_not_zero_or_known`, `test_synthetic_cannot_be_promoted`, `test_locators_fail_closed`, `test_claim_semantics_must_match_bound_source`
Test locator: [tests/test_adapter_provenance.py](../../tests/test_adapter_provenance.py) → `test_own_tracked_clean_and_modified_adapter`, `test_git_failure_returns_no_partial_repository_fields`
Evidence: [EV01](#evidence-ev01)

## Feature F04

Trusted local source admission · PARTIAL_SYNTHETIC · C6
Coverage: Explicit approved root, independently reviewed manifest pins and named original exports for trusted cooperative local Python modules.
Open boundary: No malicious-code sandbox, authenticated full supply-chain inventory, transitive-effect proof or broader governance.
Source: [src/opendot_engineering/adapters/source_admission.py](../../src/opendot_engineering/adapters/source_admission.py)
Scope record: [docs/source-admission.md](../source-admission.md) → “Optional operator-reviewed source admission”
Test locator: [tests/test_source_admission.py](../../tests/test_source_admission.py) → `test_all_hashes_checked_before_execution`, `test_source_owned_objects_and_initializer_skipped`, `test_manifest_is_rechecked_on_cache_hit`, `test_cached_namespace_tampering_is_not_adopted`
Evidence: [EV04](#evidence-ev04)

## Feature F05

Synthetic record qualification · PARTIAL_SYNTHETIC · C7
Coverage: Invented records tested against declared oracles; missing/unknown data and false scientific promotion are refused.
Open boundary: Correct refusal can pass a software contract. No real instrument, physical qualification or scientific acceptance.
Source: [src/opendot_engineering/adapters/lab_qualification.py](../../src/opendot_engineering/adapters/lab_qualification.py)
Scope record: [docs/synthetic-lab-qualification.md](../synthetic-lab-qualification.md) → “Input and meaning”
Test locator: [tests/test_lab_qualification.py](../../tests/test_lab_qualification.py) → `test_example_correct_refusals_pass_software_benchmark`, `test_unknown_is_retained_and_refused`, `test_false_promotion_fields_and_missing_evidence`, `test_incorrect_oracle_is_software_failure_even_with_valid_bytes`
Evidence: [EV01](#evidence-ev01)

## Feature F06

Source-boundary and parameter examples · PARTIAL_SYNTHETIC
Coverage: Seven named original synthetic protocols and six separately counted parameter fixtures; disagreement or missing applicability stops dependent dispatch.
Open boundary: Eight original protocols remain unimplemented/unrun; all 15 retain production_enforcement=NOT_IMPLEMENTED. Post-hoc trajectory checks do not prevent or roll back effects.
Source: [examples/source-boundary/demo.py](../../examples/source-boundary/demo.py); [examples/source-boundary/parameter-fixtures.json](../../examples/source-boundary/parameter-fixtures.json); [examples/source-boundary/proposals.json](../../examples/source-boundary/proposals.json)
Scope record: [examples/source-boundary/README.md](../../examples/source-boundary/README.md) → “What was executed”
Test locator: [tests/test_source_boundary_example.py](../../tests/test_source_boundary_example.py) → `test_seven_proposals_and_eight_explicit_gaps`, `test_missing_required_target_is_not_guessed_or_dispatched`, `test_untrusted_payload_cannot_grant_export_permission`, `test_correct_values_cannot_mask_process_failure`
Test locator: [tests/test_source_conflict_example.py](../../tests/test_source_conflict_example.py) → `test_exact_original_conflict_is_before_runtime_dispatch`, `test_missing_value_beside_known_zero_does_not_inherit_it`, `test_claimed_priority_or_pass_cannot_resolve_conflict`
Evidence: [EV05](#evidence-ev05)

## Feature F07

Fixed CAD mesh thermal composition · PARTIAL_SYNTHETIC · C9
Coverage: Source-only fixed 0.2 × 0.02 × 0.003 m, 20×4×2 linear steady-conduction recipe; fabricated fixtures check stage semantics/lineage. Plan is metadata-only.
Open boundary: Full native workflow NOT_RUN; physical validation NOT_PERFORMED; mesh independence NOT_ESTABLISHED; scientific/device authority false; independent review NOT_EVALUATED. No EDA/FMI/semantic-format interoperability claim.
Source: [examples/cad_cae/thermal_workflow.py](../../examples/cad_cae/thermal_workflow.py); [src/opendot_engineering/executors/geometry.py](../../src/opendot_engineering/executors/geometry.py); [src/opendot_engineering/executors/gmsh_mesh.py](../../src/opendot_engineering/executors/gmsh_mesh.py); [src/opendot_engineering/executors/thermal_conduction.py](../../src/opendot_engineering/executors/thermal_conduction.py)
Scope record: [examples/cad_cae/README.md](../../examples/cad_cae/README.md) → “Fixed CAD → mesh → thermal workflow”
Test locator: [tests/test_cad_thermal_workflow.py](../../tests/test_cad_thermal_workflow.py) → `test_complete_fabricated_flow_uses_real_canonical_verifiers_and_analytical_case`, `test_plan_is_metadata_only_and_explicit_not_executed`, `test_first_failure_stops_dependent_dispatch_without_retry`, `test_individually_valid_unrelated_pack_fails_lineage`, `test_legacy_native_claim_cannot_upgrade_to_workflow`
Evidence: [EV06](#evidence-ev06)

## Feature F08

Historical native STEP reference · HISTORICAL_NATIVE_REFERENCE · C9
Coverage: Static public projection records one historical native export/readback and one separate read-only review with the same Open CASCADE stack.
Open boundary: No fresh native run, independent-kernel check, replayable original receipt, mesh/solver/full-chain qualification, physical or scientific acceptance.
Source: [examples/cad_cae/native-geometry-reference/beam.step](../../examples/cad_cae/native-geometry-reference/beam.step); [examples/cad_cae/native-geometry-reference/evidence.json](../../examples/cad_cae/native-geometry-reference/evidence.json)
Scope record: [examples/cad_cae/native-geometry-reference/README.md](../../examples/cad_cae/native-geometry-reference/README.md) → “English”
Evidence: [EV07](#evidence-ev07)

## Feature F09

Finite Temporal reference transport · HISTORICAL_SERVICE_RECORD · C13
Coverage: Separate exact historical one-Activity synthetic profile demonstrated queued first delivery after graceful quiescent restart and recorded-result replay.
Open boundary: No in-flight crash recovery, global exactly-once effects, general cancellation, arbitrary tool/agent operation or current release acceptance. Current adapter files also contain the merged fixed dependent-DAG source; pure/SDK and original-reference compatibility do not establish new DAG service recovery, which remains NOT_RUN.
Source: [src/opendot_engineering/adapters/temporal_activity.py](../../src/opendot_engineering/adapters/temporal_activity.py); [src/opendot_engineering/adapters/temporal_workflow.py](../../src/opendot_engineering/adapters/temporal_workflow.py)
Scope record: [docs/temporal-reference-transport.md](../temporal-reference-transport.md) → “Optional synthetic Temporal reference transport”
Test locator: [tests/test_temporal_activity_contract.py](../../tests/test_temporal_activity_contract.py) → `test_round_trip_preserves_full_receipt_and_exact_call`, `test_permission_block_is_delivered_without_handler`, `test_semantic_failure_not_recovered_or_revalidated`
Test locator: [tests/test_temporal_workflow_contract.py](../../tests/test_temporal_workflow_contract.py) → `test_workflow_has_one_await_and_no_retry_io_or_override_path`, `test_scheduling_failure_propagates_identically_without_resubmission`
Evidence: [EV08](#evidence-ev08)

## Feature F10

Finite Temporal batch evidence · HISTORICAL_SERVICE_RECORD · C14
Coverage: Historical separately authorized batch record reports 200 validated synthetic workflow terminals, Activity interval peak 3 and outstanding peak 16.
Open boundary: Complete raw per-job evidence unavailable; no independent replay from digests. Handler overlap NOT_DEMONSTRATED, CPU parallelism NOT_EVALUATED; not 200 agents or utility/recovery proof.
Source: [ci/run_temporal_server_gate.py](../../ci/run_temporal_server_gate.py); [ci/verify_temporal_server_gate.py](../../ci/verify_temporal_server_gate.py); [tests/acceptance/temporal_real_batch_gate.py](../../tests/acceptance/temporal_real_batch_gate.py)
Scope record: [docs/temporal-batch-qualification.md](../temporal-batch-qualification.md) → “First real batch status (2026-10-02)”
Test locator: [tests/test_temporal_server_gate_verifier.py](../../tests/test_temporal_server_gate_verifier.py) → `test_fabricated_unit_records_validate_schema_only`, `test_every_receipt_is_required`, `test_stale_acceptance_does_not_override_missing_evidence`
Evidence: [EV09](#evidence-ev09)

## Feature F11

Offline O3 utility fixture report · PARTIAL_SYNTHETIC
Coverage: Read-only bounded two-slot, two-arm synthetic ledger report; separate retained-output counts, all-attempt costs and censored/missing effort. Reads four historical O3 cases without changing them.
Open boundary: Real O3 NOT_RUN; measured effort UNKNOWN. Synthetic inventory consistency is not complete real observations or authenticated reviewer authority; no ROI/customer/scale/science result.
Source: [examples/measurement-review/utility_report.py](../../examples/measurement-review/utility_report.py)
Scope record: [examples/measurement-review/README.md](../../examples/measurement-review/README.md) → “Offline incremental-utility fixture report”
Test locator: [tests/test_incremental_utility_report.py](../../tests/test_incremental_utility_report.py) → `test_original_four_records`, `test_positive_is_only_synthetic_consistency`, `test_frozen_negative_controls`, `test_no_dispatch_writes_network_or_input_mutation`, `test_unsuccessful_no_output_retains_trial_and_charge`, `test_censored_effort_remains_null`, `test_v2_output_and_attempt_counters_are_distinct`
Evidence: [EV10](#evidence-ev10)

## Feature F12

General durable recovery and reconciliation · PROPOSED_ONLY · C11
Coverage: Historical requirement for checkpoints, effect reconciliation and safe interruption remains a proposal.
Open boundary: No accepted in-flight interruption/effect-before-receipt recovery or cancellation-lifetime protocol; narrow F09/F10 are not substitutes. PR #48 adds a fixed synthetic two-node source protocol only; its new service gate is NOT_RUN, actual crash/process fencing NOT_EVALUATED and external-effect authenticity NOT_PROVED.
Source: No implementation path assigned; proposal only
Scope record: [RESEARCH-MAP.md](../../RESEARCH-MAP.md) → “Source to acceptance map”
Evidence: NOT_RUN; no implementation or execution receipt

## Feature F13

Data governance and controlled export · PROPOSED_ONLY
Coverage: Declared purposes, retention, cross-project access, revocation and export approval are proposed.
Open boundary: Source labels and trusted-caller permission gates do not establish enforced governance or a trusted-data-space certification.
Source: No implementation path assigned; proposal only
Scope record: [docs/research/official-strategy.md](official-strategy.md) → “7. 数据协作先明确边界和责任”
Evidence: NOT_RUN; no implementation or execution receipt

## Feature F14

Real user adoption and accountable handoff · PROPOSED_ONLY
Coverage: Consented target-user trial with named owner, approval points, failure handoff and setup/review burden remains proposed.
Open boundary: No interviews, actual adoption, retention, payment or accountable human handoff outcome; synthetic examples cannot satisfy the trial.
Source: No implementation path assigned; proposal only
Scope record: [docs/research/hillhouse-primary-addendum.zh-CN.md](hillhouse-primary-addendum.zh-CN.md) → “来源到需求和验收的映射”
Evidence: NOT_RUN; no implementation or execution receipt

## Feature F15

Controlled real task and backend comparison · PROPOSED_ONLY
Coverage: Frozen task/tools/versions/budgets and independent acceptance with all attempts, costs and human effort remains proposed.
Open boundary: No paper benchmark reproduction, matched manual/script versus live-agent trial, multi-host measurement or measured savings.
Source: No implementation path assigned; proposal only
Scope record: [docs/research/academic-needs.md](academic-needs.md) → “三、最小公开科研评测包提案”
Evidence: NOT_RUN; no implementation or execution receipt

## Evidence scopes

These records report earlier observations or describe current boundaries. They are not a fresh independent replay. External run links are copied from the supplied verified records; their current remote availability was not checked here. Missing original evidence stays missing. Counts from overlapping scopes are never summed.

## Evidence EV01

HISTORICAL_INDEPENDENT_REVIEW_SUMMARY
Recorded revision: c29fa49da0e7aa1f8c1382ffbc8d5f7fe2dffb25
E2 records 695 selected portable passes for the 0.2.0a0 integration, with independent installed probes; source doc preserves its author-record scope.
Record: [CAPABILITIES.md](../../CAPABILITIES.md) → “Historical verification ledger”
Receipt URL: No directly accessible original execution receipt supplied in this record
Limits: Underlying independent packet is outside this supplied public tree. No successor acceptance transfer. Not a new test total.

## Evidence EV02

HISTORICAL_INDEPENDENT_SYNTHETIC_COMPONENT_REVIEW
Recorded revision: Exact execution revision not recoverable from this selected record; do not infer it from present source hashes.
30 scoped checks each in source and installed 0.2.0a4 modes; overlapping coverage. Reviewed demo SHA-256 5740c91cc72334e729e5b6fcd5310191375c2e321e7fdeedba1866f65c46cec0.
Record: [docs/research/oss-workflows/INDEPENDENT-REVIEW.md](oss-workflows/INDEPENDENT-REVIEW.md) → “Predetermined oracle and identities / 预先冻结判据与身份”
Receipt URL: No directly accessible original execution receipt supplied in this record
Limits: Current demo bytes must not be silently accepted by this historical review; later read-only changes are separate. No savings/science outcome. Current demo SHA-256 8a363374fc05cf9fd93314c8814729e29653d0a997a22c74f652842e37904624 differs from the reviewed historical subject.

## Evidence EV03

CURRENT_DOCUMENTED_SYNTHETIC_SCOPE
Recorded revision: Exact execution revision not recoverable from this selected record; do not infer it from present source hashes.
Current overlay describes six invented rows and bounded arithmetic/input-evidence binding.
Record: [RESEARCH-MAP.md](../../RESEARCH-MAP.md) → “2026-10-02 current-status overlay”
Receipt URL: No directly accessible original execution receipt supplied in this record
Limits: No separate exact-current comparison execution receipt supplied here; current test/source pins are navigation only.

## Evidence EV04

HISTORICAL_SOURCE_ADMISSION_REVIEW_SUMMARY
Recorded revision: Exact execution revision not recoverable from this selected record; do not infer it from present source hashes.
Historical 0.1.0a0 narrow integration record reports 442 selected passes, including 91 synthetic admission cases and separate outgoing-artifact checks.
Record: [docs/source-admission-verification.md](../source-admission-verification.md) → “Selected checks”
Receipt URL: No directly accessible original execution receipt supplied in this record
Limits: No current exact artifact acceptance or comprehensive hostile-code isolation; do not add this count to any other scope.

## Evidence EV05

CURRENT_DOCUMENTED_SYNTHETIC_SCOPE
Recorded revision: Exact execution revision not recoverable from this selected record; do not infer it from present source hashes.
Seven original synthetic protocols covered; eight explicit remaining protocols; all production enforcement unimplemented.
Record: [examples/source-boundary/README.md](../../examples/source-boundary/README.md) → “Explicit gaps”
Receipt URL: No directly accessible original execution receipt supplied in this record
Limits: No current exact execution receipt here; source/test presence and narrated scope do not authenticate a run.

## Evidence EV06

CURRENT_DOCUMENTED_BOUNDARY
Recorded revision: Exact execution revision not recoverable from this selected record; do not infer it from present source hashes.
Full CAD/thermal native execution remains NOT_RUN; plan NOT_EXECUTED.
Record: [README.md](../../README.md) → “Current experimental release · 0.3.0a5”
Receipt URL: No directly accessible original execution receipt supplied in this record
Limits: README reports the published a5 prerelease; publication and fixture tests do not qualify native, physical or scientific results. Remote release status was not rechecked by this crosswalk.

## Evidence EV07

HISTORICAL_NATIVE_PUBLIC_PROJECTION
Recorded revision: 2d16190a8121410bbeea252869b196f7891e1696
Historical a4 source association; geometry module SHA-256 96e3626b68b86c21547cb930bba1591de7270f9bcffc3cdadfa0a9b9ac7a5edb; STEP SHA-256 6a58ae02b21d6f3c70505398c86193f7f3de4d4bbd20c36267400eeb08fa2ec9.
Record: [examples/cad_cae/native-geometry-reference/README.md](../../examples/cad_cae/native-geometry-reference/README.md) → “Public source association”
Receipt URL: No directly accessible original execution receipt supplied in this record
Limits: Release source association is separate from original exported-directory native receipt, whose Git fields remain null. Not a replayable full pack.

## Evidence EV08

HISTORICAL_HOSTED_ACCEPTANCE_RECORD
Recorded revision: 15bafbaa738941a916bf3329ba83c056ae70717b
818 SDK/pure checks and seven service nodes on Git tree 18a246f1dc6e6737b28455d4c3917d40dc139b2f; independent review of public audit, not service rerun.
Record: [docs/temporal-qualification-evidence.md](../temporal-qualification-evidence.md) → “Exact source and runs / 精确源码与执行”
Receipt URL: [Recorded run](https://github.com/sddvacav/opendot/actions/runs/36960635013)
Limits: Public bounded audit only; original raw histories/JUnit/CAS were not publicly retained. One fixed single-host profile; no in-flight crash recovery.

## Evidence EV09

HISTORICAL_HOSTED_SUMMARY_ONLY
Recorded revision: 1b2e417cf9b303413b0696f8b1a17ae0860518fb
200 reported validated terminals; Activity interval peak 3, handler interval peak 1, reservation peak 16.
Record: [docs/temporal-batch-qualification.md](../temporal-batch-qualification.md) → “First real batch status (2026-10-02)”
Receipt URL: [Recorded run](https://github.com/sddvacav/opendot/actions/runs/36984666613/job/110766846040)
Limits: Complete raw per-job trace/tables unavailable. Cannot independently replay missing rows; later retention preparation does not repair past evidence.

## Evidence EV10

CURRENT_DOCUMENTED_SYNTHETIC_SCOPE
Recorded revision: Exact execution revision not recoverable from this selected record; do not infer it from present source hashes.
Source-only finite fixture protocol; four original O3 NOT_RUN cases; real comparison NOT_RUN, measured effort UNKNOWN.
Record: [examples/measurement-review/README.md](../../examples/measurement-review/README.md) → “Offline incremental-utility fixture report”
Receipt URL: No directly accessible original execution receipt supplied in this record
Limits: No new execution receipt; positive fixture output cannot establish real gain, genuine complete cost observations or reviewer authority.

## Bounded supplement navigation

These are forward pointers to already existing proposals, not new entries in the 22-need scope. Their original statuses and counts remain unchanged. No combined source count is asserted.

| Existing supplemental need and oracle | Extends the exact historical needs | State |
| --- | --- | --- |
| [derived-data-role-and-split-lineage](delta-20261002/source-needs-delta.json) / O1-LINEAGE | `policy-science-evidence`, `policy-data-boundaries` | PROPOSED / NOT_RUN |
| [paired-virtual-validation](delta-20261002/source-needs-delta.json) / O2-PAIRED-VALIDATION | `policy-industrial-adapter`, `policy-science-evidence` | PROPOSED / NOT_RUN |
| [incremental-utility-before-expansion](delta-20261002/source-needs-delta.json) / O3-INCREMENTAL-UTILITY | `sequoia-domain-evaluation`, `hillhouse-wangbei-full-delivery-cost`, `hongshan-market-validation` | PROPOSED / NOT_RUN |
| [visible-human-review-and-decisions](delta-20261002/source-needs-delta.json) / O4-HUMAN-HANDOFF | `hillhouse-liliang-human-handoff`, `lidang-independent-verification`, `synthesis-reviewed-outcomes` | PROPOSED / NOT_RUN |
| [supplement-domain-scenario-mapping](delta-20261002/source-needs-delta.json) / O5-DOMAIN-CASE | `hillhouse-industry-hypothesis`, `hillhouse-wangbei-domain-validity` | PROPOSED / NOT_RUN |

### O3 source and utility separation

The exact existing need is incremental-utility-before-expansion, oracle O3-INCREMENTAL-UTILITY. Its four original cases are MORE-TOOLS-ONLY, UNACCEPTED-OUTPUT, UNKNOWN-REVIEW-EFFORT and FIXTURE-UTILITY-POSITIVE. They remain NOT_RUN in the frozen proposal. F11 is a finite source-only synthetic report mechanism, while real comparison is NOT_RUN and measured effort is UNKNOWN. Its narrow rule is a fixture choice, not a universal utility metric.

[Lidang original post](https://x.com/lidangzzz/status/2105835837418250465): the existing delta records a body observation and displayed 2026-10-01 18:42 with unknown timezone. The supplied audit later received 403 and no body. The later recheck is BLOCKED_403, body_read=false; it adds no quotation or newly verified content. The old observation is retained with its provenance, neither upgraded nor silently erased. No denial was bypassed.

[Quest Global announcement](https://www.questglobal.com/news/press-releases/hillhouse-to-invest-in-quest-global-the-largest-private-independent-pure-play-engineering-services-company/): the supplied October 2 audit confirmed the 2026-02-23 dateline, remarks attributed to Sean Carney, and closing conditions. This participant-hosted investor commentary is REFERENCE_ONLY for existing O3. It introduces no new need or priority and establishes no OpenDot demand, endorsement, technical result or transaction completion.

### Scoped human map navigation

Related R references in this crosswalk resolve to the source-to-acceptance table of [RESEARCH-MAP.md](../../RESEARCH-MAP.md). The S aliases retained here resolve by exact canonical URL to that map’s source register. The map and compact index are different sets, so absent aliases do not mean absent research. OSS T tickets and scaling G gates are separate proposal namespaces; this crosswalk does not relabel their scopes as closed compact-index requirements. Their authoritative entry points are [docs/research/oss-workflows/TICKETS.md](oss-workflows/TICKETS.md) and [docs/research/scaling-literature-20261002/README.md](scaling-literature-20261002/README.md).

## Additive corrections proposed

1. For synthesis-reviewed-outcomes, the frozen index says line 13. The stable [汇总后的产品决策建议](README.md#汇总后的产品决策建议) heading is currently line 23 in the matching research README. Use that stable heading plus its snapshot SHA-256, with line 23 only as secondary navigation. Do not rewrite the historical record or digest in this crosswalk
2. Add the dated 重庆日报 correction beside the older same-URL 上海证券报 attribution. Keep the distinct newspaper reports separate, and retain government-hosted news as indirect reporting
3. Label the R-map’s six-file count and C1–C11/E1–E3 legend as historical. Place later scope pointers beside affected recovery, scale and distribution rows rather than relying only on a distant overlay
4. Point the older Hillhouse information-gap paragraph to the edited-transcript and participant-announcement additions, preserving their precise authorship and reading limitations
5. Keep C13’s one-Activity profile, later batch summary, static native STEP reference, synthetic utility mechanism, exact release acceptance and real-user utility as separate evidence classes
6. Resolved by [PR #49](https://github.com/sddvacav/opendot/pull/49): current capability/status pages report a5 published. Preserve frozen preparation checkpoints and their historical evidence; publication remains distinct from qualification

## Validation and stopping condition

Accept this as a navigational crosswalk only if all 22 original need IDs and 18 original source IDs remain unique, all historical source→need edges are retained, all referenced paths/pointers/heading or test-symbol locators resolve against their pinned bytes, every relation resolves, and every full need remains NOT_RUN. The finite [documentation checker](../../ci/check_docs.py) checks repository-local links and heading fragments. Graph/pin validation must also compare the JSON against its unchanged authoritative records. No standalone validation artifact or inaccessible audit is linked as public evidence.

This crosswalk supplies navigation only. It does not authorize or perform product execution, new primary research, native/service/model work or remote publication.
