# Bounded simulated lab candidate

This optional adapter executes a finite plan on **internally constructed,
pure-Python ophyd simulated instruments** using the official Bluesky RunEngine.
This optional adapter was introduced in `0.1.0a1` and is included unchanged
in this package. It is not a physical lab controller. See the
[current overview](../OVERVIEW.md) and [installed guide](installed-quickstart.md)
for release status and version-pinned installation; the default guide does not
prepare or run the optional simulation. Earlier fake-only reviews retain their
original scope; the [capability ledger](../CAPABILITIES.md) identifies which
version was exercised. The [earlier combined record](combined-candidate-verification.md)
and [a4 candidate record](verifier-ci-verification.md) remain historical;
the latter adds no fake-device or native-execution acceptance.

## Scope and capabilities

- Accepts 1–16 numeric setpoints in the inclusive range `[-1, 1]`, in arbitrary
  simulated units. Rejects booleans, strings, nonfinite values, excessive counts,
  and out-of-range values before dependencies are loaded or execution starts.
- Constructs only `ophyd.sim.SynAxis` and `ophyd.sim.SynSignal`; the synthetic
  detector returns `2 * setpoint + 1`. No noise, calibration, or physical model
  is inferred from this intentionally trivial deterministic relationship.
- The fixed plan sets the fake axis, waits with a one-second limit, and triggers
  and reads the fake axis and detector. At most 19 raw documents are generated.
- `normal` emits genuine Bluesky start, descriptor, event, and success-stop
  documents. `fake_failure` raises a fixed detector fault before the first
  reading and emits a genuine failure-stop. `simulated_abort` pauses immediately
  after start, then calls RunEngine abort and emits a genuine abort-stop.
- The subprocess has an eight-second timeout, covering Python startup, optional
  imports, and the plan. Tested simulation runs finished in under ten seconds.
  This is an ordinary OS timeout, not a hard-real-time safety guarantee. A
  process timeout preserves partial raw bytes and writes an `incomplete`
  terminal record. It never fabricates a Bluesky stop document.
- Raw document envelopes are appended to an exclusively created local JSONL
  file and flushed with `fsync`. Terminal and manifest files are created once;
  the output directory must already exist and be empty; a nonempty directory is refused. This is application-level
  append-only writing, not immutable/WORM storage or a content-addressed store.
- The raw callback document fields are retained, including timestamps and UIDs;
  JSON object ordering is canonicalized. These nondeterministic fields mean raw
  byte hashes differ between runs even though synthetic readings repeat.
- SHA-256 binds raw documents and the terminal record. Verification requires a
  manifest hash supplied independently of the bundle, checks exact semantic
  claims and the bounded fixed-plan result, and does not need Bluesky, ophyd, or
  event-model.
  Hash agreement establishes consistency, not authenticity or scientific truth.
- The verifier accepts only the exact tested start/descriptor/event/stop profile:
  required UUID4 identifiers and unique document IDs, complete run/event links,
  finite ordered document times, bounded per-signal timestamps, exact stream and
  configuration keys, and fixed SIM source/dtype/shape declarations. Unexpected
  units or control-system source declarations are rejected structurally. Success
  requires the complete event sequence; injected failure/abort requires exactly
  start and the matching stop, including reason and counts. These checks validate
  declarations; they cannot authenticate where bytes or measurements originated.

Every start, terminal, manifest, and verification receipt explicitly retains
`SIMULATED_ONLY`, `scientific_accepted=false`, `device_authority=false`,
`device_control_authorized=false`, and `real_device_qualified=false`.
`resume`, `physical_calibration`, and `real_interlocks` are `NOT_IMPLEMENTED`.
Runtime receipt fields for owner integration and independent review remain
`NOT_EVALUATED`. Reviewing the source candidate does not independently review or
authorize every generated run.

There is no device-object injection, arbitrary plan endpoint, control-system
address, EPICS/SiLA/VISA transport, network service, scheduler, persistent
RunEngine, unattended server, remote execution, or external instrumentation.
The worker selects ophyd's dummy control layer before imports and disables
telemetry SDK export. The child interpreter does not inherit caller secrets,
`PYTHONPATH`, user site packages, or control-layer settings. This boundary is
not an OS security sandbox against malicious installed dependencies or hostile
modification of the adapter source.

## Existing contracts reused

The verifier uses the existing `source_audit` bounded descriptor-relative
no-symlink reader, strict JSON decoder, hash helpers, and refusal codes. It uses
the same conservative scientific/device status vocabulary as
`lab_qualification`. It does **not** manufacture strain traces, calibration
certificates, interlock evidence, or physical-qualification inputs for that
separate synthetic record checker. The existing adapter algorithms are unchanged.

## Run locally

These are POSIX-shell commands run from the source checkout root, using a
Python 3.12+ interpreter named `python`. Local review used CPython 3.12.14 on
Linux; a broader supported-platform matrix has not been established. The
source-audit file reader used by execution and verification requires POSIX
no-symlink descriptor-relative operations.

Create a separate environment outside the checkout and install the optional
extra from this source copy. Package installation can contact the configured
package index; simulation itself has no configured network destination.

```sh
LAB_ENV=$(mktemp -d /tmp/opendot-lab-env.XXXXXX)
python -B -m venv "$LAB_ENV"
"$LAB_ENV/bin/python" -B -m pip install '.[simulated-lab]'
```

For the exact recorded dependency set, instead use this installation command in
a fresh environment after creating it as above:

```sh
"$LAB_ENV/bin/python" -B -m pip install \
  -r examples/simulated-lab/requirements-tested.txt '.[simulated-lab]'
```

The [recorded version set](../examples/simulated-lab/requirements-tested.txt)
includes test tooling and transitive dependencies. It is not a hash-locked
supply-chain attestation. Bluesky, ophyd, and event-model are version-checked
before each run. Dependency implementation is installed separately and is not
vendored into this project. Do not substitute latest versions for the tested pins.

The adapter requires an existing empty output directory. Create a fresh one
outside the checkout, then run the fixed example:

```sh
LAB_OUTPUT=$(mktemp -d /tmp/opendot-lab.XXXXXX)
"$LAB_ENV/bin/python" -B -m opendot_engineering.adapters.simulated_lab run \
  "$LAB_OUTPUT" --setpoints 0 0.5 -0.5
```

The JSON result includes `manifest_sha256`. Preserve that value separately from
the bundle at creation time. Replace the placeholder below with that retained
value; do not obtain a new expected hash from potentially changed bundle bytes.
Then verify without modifying any output:

```sh
"$LAB_ENV/bin/python" -B -m opendot_engineering.adapters.simulated_lab verify \
  "$LAB_OUTPUT" --manifest-sha256 THE_INDEPENDENTLY_SAVED_HASH
```

A retained hash tests later byte consistency against the original result. It
does not authenticate the producer. The verifier uses only the default package
and standard library, although this example reuses the simulation environment.

Use a different fresh empty output directory for each fixed fault scenario:
`--scenario fake_failure` or `--scenario simulated_abort`. Failure and abort
are expected outcomes of those scenarios, not successful measurements. An
expected and fully recorded scenario has CLI exit code 0; an incomplete worker
outcome returns 1; rejected input or evidence returns 2. A zero CLI status does
not mean the run's `exit_status` is `success`.

## 中文运行说明

在源代码根目录中，使用 Python 3.12 或更新版本和 POSIX shell 执行上述命令。
`LAB_ENV` 是仓库外的新虚拟环境；默认安装不需要模拟依赖，只有执行模拟计划时才安装
`simulated-lab` 可选依赖。精确复现版本的命令另外使用记录的依赖文件，其中也包含测试工具；
该文件不是带哈希的供应链认证。安装可能访问配置的软件包索引。

`LAB_OUTPUT` 必须是已经存在的空目录，示例通过 `mktemp -d` 创建；每种场景都使用新目录。
保存首次运行返回的 `manifest_sha256`，再用该独立保留的值验证，不要从可能已变化的证据包
重新生成预期哈希。输出仍仅为模拟结果；退出码 0 也可能代表预期的故障或中止已被正确记录。

## Validation boundary

Run tests from an external directory, with bytecode disabled and pytest's cache
and temporary output also external. The new tests cover actual normal/failure/
abort runs, maximum point/document limits, pre-execution admission refusals,
lazy imports, missing/wrong dependencies, no arbitrary devices/plans, raw and
manifest tampering, independently rehashed missing/malformed identities, times,
links, descriptors, source/configuration declarations, scenario-specific terminal
profiles, malformed envelope names, false scientific promotion, symlink refusal, output
non-overwrite, and a worker with outbound socket operations actively refused.
The timeout preservation test injects `TimeoutExpired`; it tests the incomplete
receipt path, not real-time guarantees or physical stopping behavior.

Optional execution tests skip explicitly when the exact direct dependencies
are absent. A portable-only pass must not be called a Bluesky execution pass.
See [combined candidate checks](combined-candidate-verification.md) for the local
integration selection and the distinction between predecessor and current checks.

## Upstream references and licensing

Official sources consulted on 2026-10-01, alongside installed package signatures
and source for `run_wrapper`, `SynSignal.trigger`, and the wheel license files:

- [Bluesky tutorial: pure-Python simulated hardware](https://blueskyproject.io/bluesky/main/tutorial.html)
- [RunEngine interruption and abort behavior](https://blueskyproject.io/bluesky/main/state-machine.html)
- [Bluesky set plan-stub API](https://blueskyproject.io/bluesky/main/generated/bluesky.plan_stubs.abs_set.html)
- [Official SynAxis/SynSignal example](https://blueskyproject.io/bluesky/v1.13.1/magics.html)
- [Bluesky 1.15.1 package](https://pypi.org/project/bluesky/1.15.1/)
- [ophyd 1.11.2 package](https://pypi.org/project/ophyd/1.11.2/)
- [event-model 1.24.0 package](https://pypi.org/project/event-model/1.24.0/)

New integration code is original and covered by this project's Apache-2.0
license. Bluesky 1.15.1's installed license is BSD-3-Clause, copyright 2015
Brookhaven National Laboratory; ophyd 1.11.2's installed license is BSD-3-Clause,
copyright 2014 Brookhaven National Laboratory. The separately installed
event-model 1.24.0 license is BSD-3-Clause, copyright 2015 Brookhaven National
Laboratory. Each dependency and its own
transitive components retain their licenses. No dependency code or installed
package files are distributed in this candidate. The PyPI Bluesky classifier
says Apache while its wheel license text says BSD-3-Clause; the checked wheel
license text is the basis of this attribution.
