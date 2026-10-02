# OpenDot: interoperability and deployability source delta

Checked **2026-10-02** · **SOURCE RESEARCH SUPPLEMENT · PROPOSED / NOT_RUN**

本增量只补充 CAD 语义交换、联合仿真时间契约、可移植来源记录和部署证据的具体缺口。四条均为**已有文献新纳入**，不是新近发布；三项细化已有需求，一项是后续扩展假设。历史来源/需求计数、现有能力及验收状态不变。

## What changes the next decision

1. A valid CAD file or matching annotation count does not establish preserved engineering meaning. If a workflow promises product and manufacturing information (PMI), check its associations and semantics separately from geometry
2. Exported provenance is not automatically replayable. Make missing fields, restricted resources and unsupported mappings visible to an independent reader
3. Declare deployment requirements separately from exact-environment test evidence. An intended platform remains untested until it has its own receipt
4. Keep FMI co-simulation as a later, bounded extension. A successful step can return an actual time different from the requested endpoint

These are project design inferences. None is a customer requirement, institutional endorsement, mandatory OpenDot specification or implemented feature.

## Four source additions

### D1. MIIT: compatible interfaces and deployment context

[Issuer notice](https://www.miit.gov.cn/jgsj/xgj/wjfb/art/2026/art_fe01c168527a406684144a921c5c948b.html), 工信厅信管〔2025〕76号. Written **2025-12-30**; published **2026-01-06 15:36**. Read the notice and [original seven-page attachment](https://www.miit.gov.cn/cms_files/filemanager/1226211233/attach/20261/6b2e7f276c5f4093a024c3b4104f8b2d.pdf), especially II(2)–(3), III(4)–(6), printed pp. 3–5. The [official republication](https://sdca.miit.gov.cn/zwgk/zcwj/wjfb/art/2026/art_cba8b40f5f1f44a1a0da3a7068adfe2e.html) is dated January 7, not the original publication date.

The plan discusses compatible data/platform interfaces, cloud/edge/device compute matching, industrial data sharing and model interfaces. This is **formal policy direction**, not empirical product evidence. The PDF search metadata has an older-looking title; the formal title and dates above follow the issuer notice and body. Text was read; inspectable screenshot images were unavailable.

**P1 proposal:** an exact-version deployment profile separating declared requirements, observed host capabilities and test receipts. Unsupported architecture, missing dependencies or prohibited network routes must not trigger silent fallback to another environment. An offline claim needs a separate authorized network-disabled test. No policy eligibility, funding or production deployment is inferred.

### D2. NIST-hosted original CAD interoperability investigation

[NIST GCR 16-003](https://nvlpubs.nist.gov/nistpubs/gcr/2016/NIST.GCR.16-003.pdf), *Validation for Downstream Computer Aided Manufacturing and Coordinate Metrology Processes*. Cover **September 2015**; [NIST publication record](https://www.nist.gov/publications/validation-downstream-computer-aided-manufacturing-and-coordinate-metrology-processes-0) **2016-08-01**. Read the disclaimer, printed pp. 7, 9–15 and 17–24, including Table 1 and failure examples.

The authors compared paired PMI structures and property values. They reported lost associations and altered identifiers; some representation changes needed better validator rules, and an angular discrepancy could arise in translation or validator display. This is **historical author-reported research**, not certification or an assessment of current vendors. The report explicitly disclaims automatic NIST endorsement.

**Conditional P1 proposal:** a source/target semantic diff with a declared supported subset. Keep counts unchanged while deleting a geometry link, changing a datum, dropping units or changing untoleranced-reference meaning: these fixtures must not pass. Also test equivalent representations so the validator does not reject harmless re-encoding. Unsupported or ambiguous semantics remain explicit. Apply this only when PMI preservation is promised; it is not a new prerequisite for an unannotated thermal example.

### D3. FMI 3.0.2: actual time and negotiated capabilities

[Original versioned specification](https://fmi-standard.org/docs/3.0.2/), **2024-11-27**. Read §§2.3.2, 2.5.1.4, 4.2.1 and 4.4/Table 39. This is a **technical interface contract**, not performance evidence; no claim is made that this is the latest release.

The specification negotiates Event Mode and early return, separates platform binaries/dependencies, and permits actual returned time to differ from the requested endpoint even after an OK step without early return. FMI does not define the importing coupling algorithm.

**P2 proposal:** a trace/capability checker for a future co-simulation adapter. Reject unsupported event/step combinations, preserve actual time, and require an explicit synchronization decision under a declared tolerance. Fixed-step alignment is guidance in the specification; a stricter project gate must be labeled accordingly. Successful contract checks cannot establish numerical stability or physical accuracy. No FMU was executed.

### D4. Original research: portable provenance with explicit losses

Leo et al., [*Recording provenance of workflow runs with RO-Crate*](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0309210), PLOS ONE, **2024-09-10**, DOI 10.1371/journal.pone.0309210. Read metadata, abstract, profile granularity, implementation limitations and §5.1/Table 3. The paper discusses profiles **0.5**.

The authors describe planned workflows and actual runs at different detail levels across workflow systems, including incomplete metadata transfer and restricted referenced resources. These are **author-reported implementations and observations**, not a reproduction conducted here.

**P1 proposal:** an offline export mapping with a field-level loss report. A separate consumer must recover the same input/output identities, tool/configuration identity, attempts and run relationships. Missing mandatory configuration or inaccessible payload yields NOT_REPLAYABLE. Keep planned steps separate from observed attempts and distinguish metadata validity, replay and scientific acceptance. This refines existing AiiDA coverage without creating a second runtime.

## Requested source families: no inflated counts

- **State Council:** re-opened the existing [AI+ official republication](https://wap.miit.gov.cn/xwfb/szyw/art/2025/art_f8bd63905b384841a84e643c1b9455c7.html), published 2025-08-26. No new State Council document added
- **Sequoia Capital:** re-read [Sonya Huang's 2026-08-19 original essay](https://sequoiacap.com/article/own-your-intelligence-a-how-to-guide). Its evaluation theme is already covered; it explicitly does not mandate leaving frontier services. No new need added; Sequoia and HongShan remain distinct
- **Hillhouse:** the [official news/insights index](https://www.hillhouseinvestment.com/news/) yielded no new detailed relevant original in this bounded check. This does not establish absence of newer views; prior organizer-edited attributed remarks retain their limits
- **Lidang:** direct fetch of the [known October 1 original](https://x.com/lidangzzz/status/2105835837418250465) failed without body text. No newly verified original, quote or date added. This retrieval failure does not invalidate the earlier successful original-page observation in the existing collection
- **Industry:** the NIST-hosted case adds specific transfer failure mechanisms. Existing Siemens statements are not duplicated or upgraded to independent validation

## Integration and evidence boundary

[Machine-readable delta](source-needs-delta.json) contains exact dates, URLs, evidence classes, reading scope, source limits, existing-need links and acceptance criteria. All four protocols remain **NOT_RUN**; every function is **PROPOSED**.

This source research supplement is linked from the [research collection](../README.md). Historical source/need rows, counts and earlier annexes are unchanged; only the existing overview digest in the compact index is updated to bind its added navigation link. The research and documentation integration install no software, run no CAD/CAE tools, invoke no providers and change no external accounts. No original source bytes are archived; these are reading observations, not publisher-authenticated archives.
