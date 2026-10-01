# Combined 0.1.0a1 candidate checks

Historical record, dated 2026-10-01 UTC. This **unreleased local combined candidate**
later passed independent bounded review with two documentation findings. The
[current successor](provenance-integration-verification.md) corrects those findings
and integrates the separately accepted Git-provenance repair. This predecessor
combines the independently accepted source-admission predecessor with the
independently accepted finite fake-only simulation delta. It is not a full
platform, scientific, physical-device, native-backend, or release acceptance.

## Preserved ownership and executable scope

- The accepted `source_admission` implementation and its synthetic tests are
  unchanged, as are canonical `source_audit`, `lab_qualification`, and the
  pre-existing CAD/CAE executable modules and tests
- The two simulation modules, simulation tests, and exact tested dependency recipe
  are byte-identical to the independently accepted fake-only successor
- The package version changes from `0.1.0a0` to `0.1.0a1`. Shared documentation,
  attribution, and optional-dependency metadata are reconciled. No scheduler,
  runtime owner, source discovery, arbitrary plan/device endpoint, or resume is added
- Runtime flags stay false or `NOT_IMPLEMENTED`/`NOT_EVALUATED` as specified. Source
  review acceptance does not independently review a generated run or grant authority

## Local checks for the historical combination

Checks used CPython 3.12.14 on Linux with existing pytest 9.1.1. Bytecode writes,
pytest plugin autoload, and pytest cache were disabled. Generated fixtures,
reports, wheel staging, and installed environments were outside public source.

| Check | Result | Scope |
| --- | --- | --- |
| Explicit portable CI node manifest | 459 passed; zero failures, errors, or skips | Exactly the preceding 442 reviewed cases plus 17 dependency-free simulation cases |
| Optional simulation test file | 108 passed; zero failures, errors, or skips | Finite actual fake-device normal/failure/abort execution, bounded admission and strict-profile refusal cases; includes the same 17 portable simulation cases |
| Fresh default wheel installation | PASS | Wheel installed without dependencies in a fresh pip-free environment; only this distribution installed; no required runtime requirements or console entrypoints |
| Isolated installed imports/admission | PASS | Installed package/standard library only; no optional backend or operator source imported implicitly; source-owned object/cache identity and rejection behavior retained |
| Installed fixed-pin README examples | PASS | Source audit accepted and synthetic qualification contract passed; science/device flags remain false |
| Installed optional simulation | PASS | Same wheel in a separate installed target with existing exact optional dependencies; normal 16-point run, fake failure, and simulated abort verified |
| Dependency-free installed verification | PASS | Minimal environment verifies the generated normal bundle without importing Bluesky, ophyd, event-model, or NumPy |

The portable and simulation counts overlap by 17 cases and must not be added as
independent totals. The old 442-case scope was wholly contained in the then-current
459-case manifest. The full repository test suite was not run. The workflow used
fully collected explicit node IDs rather than unrestricted pytest discovery.
The [current manifest](../ci/portable-nodes.txt) has since grown to 502 cases for
the provenance-integrated successor. No hosted-CI execution is claimed.

The [current CI reproduction instructions](../ci/README.md) run the successor
selection; they do not reproduce this historical artifact or its 459-case scope.
Run `tests/test_simulated_lab.py` separately only in the exact optional environment
described in the [simulation guide](simulated-lab.md), with bytecode/plugin/cache
writes disabled and external temporary/JUnit paths. Optional tests may skip when
dependencies are absent; a skipped run is not an execution result.

## Relationship to predecessor reviews

The source-admission predecessor independently passed 442 selected cases and
installed/outgoing-artifact checks. The fake-only lab successor independently
passed 60 additional review cases and 288 selected producer/core cases, plus a
1,733-mutation structural sweep with no accepted malformed semantic mutation.
Those are historical predecessor scopes, not additional tests rerun or summed
into the current combined result. Their detailed private-context-free summaries
are reflected in [source-admission checks](source-admission-verification.md) and
the [simulation contract](simulated-lab.md). Detailed review evidence is retained
outside the public tree.

The prior native geometry, mesh, and linear-thermal work belongs to separate
reviewed artifacts/environments. No new native execution was performed for this
combination, and native-qualified status is not inherited by this revision.

## Remaining gates and limits

At this historical snapshot, Git-provenance remediation was a separate pending
change and was not included. The [successor record](provenance-integration-verification.md)
tracks its integration; each changed outgoing artifact needs its own review. A verified
publication destination and any applicable dependency/rights gates remain. This
document neither announces publication nor creates a new consent requirement.

No private-runtime, actual process-lifetime, recovery, live-model, real-device,
full-platform, hosted-CI, or broader supported-platform acceptance was attempted.
The simulation child timeout is ordinary process handling, not a hardware
interlock or hard-real-time guarantee. No comprehensive transitive-license,
vulnerability, supply-chain, privacy, or sandbox certification is claimed.
