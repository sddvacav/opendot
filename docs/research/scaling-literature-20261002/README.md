# OpenDot: evidence needed before scaling an agent fleet

Checked 2026-10-02 UTC. Research supplement, not implementation or benchmark evidence. All proposed gates below are **PROPOSED / NOT_RUN**. No model-provider calls, experiments, paid services, or external posting were performed; this appendix changes documentation only.

[Public-source delta / 公开来源增量](../delta-20261002/README.md)

中文摘要：先验证一个可执行、有界的工作流，再以同预算基线、独立验收和完整成本判断协作收益。四篇论文均保留具体版本；六项验收门槛均为 PROPOSED / NOT_RUN，不构成 OpenDot 当前吞吐量、规模化、恢复或成本优势证据。

## Decision

First build and qualify one executable, bounded agent workflow. Then test whether collaboration improves independently accepted outcomes at the same total budget. A large worker count is a capacity experiment; a large team solving one task is a different quality experiment. Neither implies the other.

The existing research map already requires matched baselines, accepted throughput, complete attempt costs, and human review time (R9), and separately proposes recovery tests (R5). This supplement adds four primary sources absent from the reviewed public research collection and makes those requirements more operational. These are newly collected historical publications, not newly published papers. The historical 18-source / 22-need index and the separate policy/viewpoint delta retain their own counts. It does not replace the existing AstaBench, ScienceAgentBench, Co-Scientist, SciAgentArena, or AiiDA coverage.

Current boundary: C11 remains proposed. The current C13 document admits one concurrent fixed synthetic Activity, one writer process, a shared trusted local CAS, and loopback transport. Its graceful-restart/recorded-result replay evidence does not establish in-flight crash recovery, arbitrary agents, concurrent agent fleets, or global exactly-once effects. Metadata manifests are not an executor.

## Four primary sources

Primary metadata and selected full-text methods, results and limitations passages were inspected. Section links identify consulted locations; this is not a line-by-line paper audit or experimental replication.

### L1. Architecture and task structure, rather than count alone

Kim et al., [Towards a Science of Scaling Agent Systems, v3](https://arxiv.org/abs/2512.08296v3). First submitted 2025-12-09; v3 2026-04-08. DOI: 10.48550/arXiv.2512.08296.

The authors report 260 configurations, five architectures, three model families, and six benchmarks: Finance Agent, BrowseComp-Plus, WorkBench, PlanCraft, SWE-bench Verified, and Terminal-Bench. Their agent-count exploration reaches nine. Gains depend on decomposability and coordination; sequential planning can deteriorate. Read [§§4–5 and Appendices D–F](https://arxiv.org/html/2512.08296v3).

Limits: v3 supersedes widely circulated v1 statistics. Some overhead findings become directional under clustered inference; coding/terminal cells use only 20 tasks. The paper states budget controls, but this review did not audit its implementation or reproduce results. No threshold, fitted curve, error-amplification ratio, or preferred team size transfers to OpenDot or hundreds of agents.

### L2. Failure diagnosis must survive successful delivery

Cemri et al., [Why Do Multi-Agent LLM Systems Fail?, v3](https://arxiv.org/abs/2503.13657v3). First submitted 2025-03-17; v3 2025-10-26. DOI: 10.48550/arXiv.2503.13657.

MAST-Data contains 1,642 traces from seven systems; initial taxonomy development examined 150 traces with expert participation. Fourteen modes cover system design, inter-agent misalignment, and verification, including missing information, repetition, premature termination, and incorrect checks. Read [§§3–5 and Appendix A](https://arxiv.org/html/2503.13657v3).

Limits: much of the expanded labeling uses an LLM judge; agreement is not infallible ground truth. Different systems use different tasks, so their failure distributions are not a matched leaderboard. The taxonomy is not exhaustive and is not a distributed-systems recovery protocol.

### L3. Diversity must be measured against strong baselines

Zhang et al., [Stop Overvaluing Multi-Agent Debate—We Must Rethink Evaluation and Embrace Model Heterogeneity, v3](https://arxiv.org/abs/2502.08788v3). First submitted 2025-02-12; v3 2025-06-21. DOI: 10.48550/arXiv.2502.08788.

The study compares five debate methods on nine knowledge, math, and programming benchmarks with four models, including reasoning and self-consistency baselines. It examines both corrected answers and initially correct answers subsequently spoiled. Heterogeneous combinations benefit from complementary errors but struggle when both constituent methods fail. Read [§§3–5, PDF pp. 5–14](https://arxiv.org/pdf/2502.08788v3#page=5).

Limits: these are mostly static answer-generation tasks, not durable tool-using fleets. Call-count matching does not establish identical token expenditure. Reported heterogeneity gains use averaged constituent baselines; they do not establish superiority over the strongest constituent at equal cost. Different models or role names do not prove independent errors.

### L4. Cost and reproducibility are part of the result

Kapoor et al., [AI Agents That Matter, v1](https://arxiv.org/abs/2407.01502v1), submitted 2024-07-01. DOI: 10.48550/arXiv.2407.01502. Date follows arXiv submission history, not the HTML renderer’s body date.

The paper studies HumanEval agents and simpler baselines, HotPotQA cost/accuracy optimization, NovelQA, and WebArena evaluation problems; it also surveys 17 agent benchmarks. It distinguishes optimization costs from per-run costs and argues for holdouts appropriate to the generalization claim. Read [§§2–6 and Appendices A, G, I](https://arxiv.org/html/2407.01502v1).

Limits: historical models/prices and selected tasks are not current OpenDot economics. Broader maintenance and human costs are not comprehensively measured. Appendix A excludes one timed-out run’s time/cost; OpenDot should disclose and retain such resource consumption, rather than inherit that exclusion.

## Proposed acceptance additions

These are project recommendations synthesized from the sources and current contracts, not requirements issued by the authors.

1. **G1 — Freeze the comparison.** Predeclare task IDs, public inputs and licenses, environment/tool versions, permissions, model versions, prompts, acceptance oracle, budget and termination rules. Include separable subtasks, sequential dependencies, and tasks with shared mutable state. Reserve untouched tasks matching the intended generalization claim. Compare a script where applicable, a capable single agent with equal retry/search opportunity, independent candidates plus the same verifier, and a coordinated team. For mixed models, include each constituent and the strongest affordable one. Equal-call, equal-token, equal-dollar, and equal-deadline comparisons are distinct experiments; label them accurately.

2. **G2 — Count accepted tasks and complete costs.** Keep unique admitted tasks, attempts, candidates, inspected candidates, accepted results, rejected results, blocked tasks, cancellations, timeouts, and unresolved outcomes distinct. Use independent acceptance on final artifacts and required end state; transport completion or unanimous votes are insufficient. Report accepted/admitted, false acceptance on deliberately invalid controls, elapsed and review time, and total cost per accepted task. When none are accepted, report the denominator and undefined cost-per-acceptance, not zero. Include coordinator, verifier, failed/cancelled calls, retries, tool/compute/storage charges and idle resources; report build/tuning cost separately. Record raw usage and dated prices, with unknown charges explicitly unknown.

3. **G3 — Measure correlated failure and coordination loss.** Preserve candidates before communication, then evaluate after aggregation. On the same tasks, report jointly wrong pairs, correction and corruption transitions, redundant work, message/token overhead, verifier disagreement and concentration on a shared wrong source. Add harmless fixtures where one worker versus all workers receives the same false premise. Compare independent generation with communicating teams at matched budgets. A majority sharing one source is one evidential dependency, not independent confirmation. Measure diversity instead of inferring it from agent count or model labels.

4. **G4 — Make failure and acceptance orthogonal.** Log observable phase transitions and artifact identities, not just a final success flag. Challenge the verifier with wrong units, incomplete output, stale references, contradictory worker outputs and premature completion. Separately record transport delivery, tool execution outcome, artifact integrity, semantic verdict and human/independent acceptance. A delivered BLOCKED or FAILED receipt remains blocked or failed. Diagnostic labels supplement evidence; they must not fabricate a known root cause or turn unknown execution into success.

5. **G5 — Qualify effects before recovery claims.** In a separately authorized disposable implementation, inject interruption before execution, during execution, after an effect but before its receipt, during result storage, and after publication but before acknowledgment. Also test cancellation, duplicate submission and a late worker completion. Verify external effect state independently of the result receipt. If an effect cannot be reconciled, retain UNKNOWN and suppress automatic retry of non-idempotent actions. Acceptance requires accounting for duplicate effects, surviving work, orphaned artifacts, manual intervention and final task outcome. Replaying an already-recorded result covers only that replay case.

6. **G6 — Gate every increase in scale.** Define workers, team members, model calls and actual concurrent work separately. Measure overlap from start/end events, peak and sustained concurrency, queued time, backpressure, memory, resource ceilings and accepted end-to-end throughput. Keep team-size scaling separate from running many independent tasks. Move to a larger cell only after small-cell correctness, budget, cancellation and effect-accounting gates pass. Publish paired task-level uncertainty across repeated runs; do not treat correlated agents as independent statistical samples. Predeclare a minimum useful gain and maximum false-acceptance/cost/review burden; conclude inconclusive when evidence cannot distinguish the alternatives. A future hundred-agent claim needs measured hundred-agent execution and accepted results on the exact implementation.

## Deliverables and stopping boundary

The companion `evidence.json` records source versions, reading scope, public repository input hashes, requirement mappings and evidence status. No external performance number is an OpenDot measurement. The next justified artifact is an executable-workflow specification and unrun acceptance protocol; live fleet execution needs an actual implementation, independently reviewed authority boundaries, an approved workload and an explicit spending/resource limit.
