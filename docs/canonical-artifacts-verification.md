# Canonical artifact candidate verification

Date: 2026-10-01 UTC. Version: `0.2.0a0`, unreleased migration candidate.
This record covers the added storage closure, not a runtime or consumer rollout.

## Executed local source checks

- 43 focused public synthetic storage cases passed on Python 3.12/Linux
- The explicit portable manifest was rerun: 545 passed, 0 failed, 0 skipped
  (502 existing regression nodes plus those same 43 cases; not 588 unique cases)
- The extracted store's executable AST matches the reviewed existing owner after
  excluding the deliberately clarified class docstring. The sole reference
  contract's AST is unchanged. Extraction/license comments do not alter behavior
- Existing adapter and executor implementation bytes remain unchanged

This is newly executed source regression evidence for this candidate. Earlier
`0.1.0a1` receipts remain historical and are not relabeled as `0.2.0a0` acceptance.
The selected checks do not install optional dependencies or execute native
backends, fake-lab plans, live models, devices, or another runtime.

## Reproduce bounded source checks

Use the repository's [test tooling and portable selection](../ci/README.md).
For only the new storage cases, from the source root:

```sh
CHECK_OUTPUT=$(mktemp -d /tmp/opendot-artifact-check.XXXXXX)
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src \
  python -B -m pytest -q -ra -p no:cacheprovider tests/test_canonical_artifacts.py \
  --basetemp="$CHECK_OUTPUT/pytest" --junitxml="$CHECK_OUTPUT/results.xml"
```

The [public example](../examples/canonical-artifacts/README.md) is a separate real CAS
invocation using synthetic bytes. It checks the successful object and a distinct
deliberately corrupted one, while retaining false science/device authority and
`NOT_EVALUATED` consumer-migration/recovery status.

## Exact installed-artifact evidence

Version text and a successful import cannot identify or validate a wheel. Keep
the exact source commit/tree, archive and wheel SHA-256, wheel member/RECORD
checks, installation metadata, interpreter identity, invocation, and result
outside the repository. Build from an exported committed tree into an external
directory, install the resulting wheel without dependencies in a new environment,
and invoke the public example using `python -I -B` from outside the source tree.
Verify the imported modules resolve to that environment, their installed bytes
match the wheel, and the resulting CAS objects were actually read and hashed.

The source tests above are not an independent release decision. Exact outgoing
source/wheel review, any broader supported-platform matrix, and real consumer
migration remain open. This addition establishes no filesystem sandbox,
cross-process concurrency, object/metadata transaction, power-loss recovery,
native lifetime, runtime recovery, scientific validity, or publication result.
