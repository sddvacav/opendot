# Added primary sources / 补充一手来源

Checked 2026-10-01 UTC against the existing public research directory and source-needs index. These three source URLs/identifiers were absent. They supplement, rather than replace, the existing AstaBench, ScienceAgentBench, Co-Scientist and Siemens material. No experiments in these sources were reproduced. All OpenDot mappings below are PROPOSED and are this report's inferences.

## A1 · AiiDA architecture and provenance, academic

- Source: Huber et al., [AiiDA 1.0, Scientific Data](https://www.nature.com/articles/s41597-020-00638-4), DOI 10.1038/s41597-020-00638-4; published **2020-09-08**; inspected abstract, architecture, process/workchain and provenance sections
- Evidence: the paper separates stored data, generating processes and workflow logic; workchains persist between steps. The paper also explains why a single ordinary Python function cannot provide interrupt-and-resume semantics
- Need → function → oracle: trace a result → explicit input/result/validator links (T1/T2) → mutate each binding and refuse stale acceptance. Longer work → separately owned checkpoints (T7) → crash tests at effect/receipt boundaries
- Limit: the historical paper's implementation and throughput results do not establish current OpenDot performance, scientific correctness or durable recovery

中文：该论文区分数据来源、生成过程与工作流逻辑。OpenDot 可先采用可核对的输入—结果—验证器绑定；持久恢复需另行实现与故障注入验证，不能由普通函数执行或保存文件推导。

## A2 · Brookhaven deployment account, first-party operational source

- Source: Brookhaven National Laboratory, [Software Developed at Brookhaven Lab Could Advance Synchrotron Science Worldwide](https://www.bnl.gov/newsroom/news.php?a=212470); published **2017-10-02**; inspected complete article
- Evidence: BNL describes incompatible beamline software as a comparison barrier, a modular stack over established controls, and development shaped by scientists at operating beamlines
- Need → function → oracle: preserve existing domain tools and review practices → one bounded adapter workflow (T1/T6), then an observed unaided-user journey (T5) → identical input/output checks plus a record of actual assistance and failures
- Limit: a laboratory's own deployment narrative is not a controlled usability study or transferable proof of OpenDot demand or ROI; no BNL relationship is implied

中文：该一手部署报道支持“适配现有工具、到用户工作现场验证”的研究方向；不能作为 OpenDot 客户需求、节时收益或机构背书。真人上手与对照测量仍需实际开展。

## A3 · SLSA v1.2, industry-consensus specification

- Source: [Build: Provenance, v1.2](https://slsa.dev/spec/v1.2/build-provenance); approved specification, release announced **2025-11-24** in the [official announcement](https://slsa.dev/blog/2025/11/announce-slsa-v1.2); inspected purpose, model, schema and verification sections. The release date is not asserted as the last edit date of every page
- Evidence: build provenance separates output identity, build definition, parameters, dependencies and trusted builder identity. Untrusted external parameters require downstream checks
- Need → function → oracle: verify delivery identity → exact-commit build/artifact binding and externally established expected identity (T3/T4) → reject wrong subject digest, source revision or untrusted builder
- Limit: an unsigned local JSON manifest is not authenticated provenance, a SLSA level, a complete dependency inventory, or evidence of semantic/scientific acceptance

中文：可借鉴构建定义、输入依赖、产物与构建者身份的分离。普通本地清单只能记录声明，不能称为签名证明、SLSA 达标或科学验收；验收应使用外部可信期望值，而非让清单自证。

## Status rule / 状态规则

Primary sources justify questions and design hypotheses. They do not confer implementation credit. Ticket acceptance must be established on the exact OpenDot candidate, with missing, failed and unrun evidence shown separately.
