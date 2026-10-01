# Review a synthetic measurement batch / 审阅合成测量批次

Protocol frozen before implementation results: 2026-10-01 11:33 UTC. The frozen inputs are in [frozen expected summary](frozen-oracle/expected-summary.json). Subsequent implementation review is recorded separately in [review report](INDEPENDENT-REVIEW.md); it does not retrospectively change the expected results.

## 1. User and concrete outcome / 用户与成果

Intended user: a research/software engineer checking a small table and a computed summary before passing it to a colleague. This is a hypothetical target-user task, not an observed user interview.

Outcome: a reviewable bundle identifying the exact input CSV and output bytes, the fixed synthetic acceptance rule, whether the tool result was accepted, and which failed artifacts still exist. A later process can inspect the saved bundle against separately retained trusted expectations.

目标是减少输入版本、计算结果和审阅记录之间的人工错配。该价值假设尚未经过真人用户研究；交付物是可核对的证据包，不是科学结论。

## 2. Fixed public input and independent oracle / 固定公开输入与独立判据

- Six invented CSV rows; headers: condition,replicate,value,unit
- A rows: (1,1,au), (2,2,au), (3,3,au); B rows: (1,2,au), (2,4,au), (3,6,au)
- Source digest: 12fa76e2cb8defb752ce08a2fdd386b0f943579d1438e3022cb2e345bdcae0d9
- Independently specified A count/sum/mean = 3/6/2; B = 3/12/4; total rows = 6; unit = au
- Inner result schema: measurement-review-result/v1; validator ID: measurement-review/v1
- No experimental measurements, personal data, fitted model, material property, native solver or instrument are involved

The [human-readable expected summary](frozen-oracle/expected-summary.json) has SHA-256 4df81c0c33cd274af97197d6d9eb2d3e05c63579e026eb41b2ef8718d41d63e5. This is the hash of that exact file, including whitespace. An implementation may separately hash canonical JSON of its validator identity plus the same expected values; it must explain that distinct encoding and independently verify the values. These two different hash formats must never be silently conflated.

独立判据在运行实现前写定，不能通过调用同一个汇总函数生成“预期答案”。JSON 文件字节哈希与规范化验证器描述哈希是不同身份，必须区分。

## 3. Workflow / 流程

1. Check the small fixture's syntax, repeated-row identity and explicit unit
2. Execute a finite callable with declared artifact-write permission, no retries and no model
3. Save original CSV and result JSON in existing CAS; preserve the returned source/result references
4. Compare the result with the separately specified expected summary; distinguish generation from acceptance
5. Emit a manifest with source/result identities, validator identity, invocation observations and the bounded receipt
6. Retain trusted expected bundle/source/oracle hashes outside the bundle; in a fresh Python process verify them and retrieve exact bytes

Use only fresh output directories under a trusted cooperative parent. The example may cap fixture input size; that does not harden the underlying whole-object CAS or establish hostile-filesystem containment. Hashes and metadata declarations do not authenticate their producer. The runtime's declared permissions are not an OS sandbox.

## 4. Frozen seven-case oracle / 七个冻结场景

| Case / 场景 | Expected / 预期 |
|---|---|
| Valid / 合法结果 | COMPLETED; exact source binding and independent count/sum/mean pass; accepted result ref exists |
| Wrong mean / 故意错误均值 | A.mean=3; CAS bytes remain valid but semantic acceptance is FAILED; artifact retained as unaccepted |
| Missing permission / 缺少权限 | BLOCKED/PermissionDenied; zero handler calls and zero produced artifact objects; diagnostic directories/bundle are allowed |
| Corrupt result / 篡改产物 | Changed object bytes with old expected hash are refused |
| Changed input / 更改输入 | Changed source or expected source binding cannot reuse the prior acceptance |
| Changed validator / 更改验证器 | A new validator ID or oracle digest with old trusted expectations is refused |
| Fresh-process verification / 新进程核对 | Correct retained bytes and trusted expectations verify; no execution restart or recovery claim |

Additional blind controls should cover duplicated/missing row keys, wrong units, nonfinite values, extreme exponents, missing required expected pins and existing-output preservation. Record each result separately; the result is not a general false-accept rate.

## 5. Why this can help beyond manual steps / 相对人工步骤的候选价值

A manual reviewer can perform every same check with ordinary scripts and a checklist. The proposed package benefit is that one documented path associates the checks with the exact artifacts and preserves the distinction between “present,” “intact,” “accepted,” and “rejected but retained.” It can expose deliberate summary and identity mismatches in a reproducible demonstration. CAS alone cannot know that a mean is wrong; a semantic validator alone cannot prove that later bytes are the bytes previously accepted.

人工流程也可以完成全部同等检查。本方案候选优势是把这些步骤与具体产物统一关联：哈希完整不等于均值正确，验证通过也不能保证后续文件未被替换。组合机制演示不等于证实更快、更易用或更有商业价值。

## 6. Fair evaluation and stopping rules / 公平评估与停止条件

For this synthetic stage, report only source/installed import identity, individual status/error outcomes, retained artifacts and fresh-process verification. Do not infer human time saved from command count or compare against a baseline that omits validation. No latency, throughput, cost, adoption or ROI claim without an actual declared measurement protocol.

A later real-user evaluation must freeze equivalent output quality, fixtures, assistance rules, acquisition/setup treatment and the existing manual/script workflow. Record all attempts, active human effort, total elapsed time, mistakes and whether each output meets the same oracle. Use counterbalanced task order where appropriate and disclose learning/setup effects. Consent, recruitment and an actual session are still required; this document invents neither participants nor outcomes.

Completion here means the frozen software cases match on the declared candidate and environment. Stop for any failed binding, unexpected accepted negative or required permission gap. Broader native execution, lifecycle recovery, public delivery, supported-platform coverage and user-value evidence remain separate.

## 7. Implemented verification caveat / 已实现核对的限制

The reviewed implementation calls the canonical ArtifactStore constructor during verification. That constructor can create directories or alter permissions. Therefore verification is **not strictly read-only**, even though it does not restart the measured computation. A future non-mutating verifier requires a separately scoped implementation change; no current read-only claim is permitted.
