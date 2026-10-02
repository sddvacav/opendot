# Historical public-source demand-gap annex

This annex was researched on 1 October 2026 and is included as documentation in
**0.2.0a6, unreleased; NOT_SCORED**. The [original Chinese record](README.zh-CN.md),
[source-to-need interpretations](source-needs-delta.json), and
[15-case proposal](acceptance-cases.json) retain their original bytes and original
`UNMERGED` / `NOT_RUN` / `NOT_EXECUTED` historical status. Those headers describe
the research snapshot, not the status of every later implementation.

At the historical **0.2.0a6 checkpoint**, the separate
[source-boundary example](../../../examples/source-boundary/README.md) implemented
**six** bounded synthetic protocols, with **nine** original proposals still
`NOT_IMPLEMENTED` / `NOT_RUN`.

**Current source, 2026-10-02:** the linked example and its
[coverage regression](../../../tests/test_source_boundary_example.py) now exercise
**seven original synthetic protocols / eight remaining**. The additional original
case is `EVIDENCE-CONFLICT`, checked before runtime dispatch by the
[conflict regression](../../../tests/test_source_conflict_example.py). Six separate
parameter fixtures do not close further original proposals. The eight remaining
cases retain `NOT_IMPLEMENTED` / `NOT_RUN`; all 15 retain production enforcement
`NOT_IMPLEMENTED`. This does not rewrite the original proposal record. A
missing-evidence precheck is example logic; source labels and fixture approvals
are not authenticated permissions. Post-hoc process checks cannot prevent or
undo effects.

The public posts and papers are sources for design inferences, not customer
interviews, purchases, adoption, investment interest, endorsement, model benchmarks,
scientific acceptance, or proof of prompt-injection immunity. No raw browser logs,
screenshots, private project records, or generated execution receipts are included.
Public-source reading observations are not publisher-signed source archives.

## 中文说明

本附录是 2026 年 10 月 1 日的历史研究快照，作为未发布 a6 的文档收录。
三个原始文件保持原字节；其中“未合入／未执行”标记描述当时状态。
历史 **0.2.0a6 检查点**的合成示例实现六项协议，其余九项为
`NOT_IMPLEMENTED`／`NOT_RUN`。

**2026-10-02 当前源代码：**[示例](../../../examples/source-boundary/README.md)及
[覆盖回归测试](../../../tests/test_source_boundary_example.py)现执行 **七项原始合成协议，余下八项**。
新增原始案例为 `EVIDENCE-CONFLICT`，[冲突回归测试](../../../tests/test_source_conflict_example.py)
确认它在运行时分派前被阻断。另有六项参数样例，不抵销更多原始提案。
余下八项仍为 `NOT_IMPLEMENTED`／`NOT_RUN`；十五项的生产强制机制均为
`NOT_IMPLEMENTED`，原始提案记录不改写。证据缺口预检查不构成生产权限验证。
来源观点、需求推断、示例执行和生产验收分别记录，不互相替代。
