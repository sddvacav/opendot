# Callable-only public-candidate verification

Date: 2026-10-01. Version: **0.2.0a0, unreleased**. Local implementation-worker
verification on Python 3.12.14 with pytest 9.1.1. This is not an independent review
of the new public candidate, hosted-CI success, or a full-platform acceptance.

## Exact test selection

- Earlier callable candidate: **97 of 98** cases retained as portable behavior
  checks. The one source-dependent, six-class AST comparison is excluded
- Separately authored regressions: **40 of 42** cases retained. Two checks that
  require nonpublic source/blob identity and an entire source manifest are excluded
- New public contract tests: **6** cases verify the six retained types' fields,
  defaults, enum values, mutability, validation, and representative behavior
- Callable selection: **143 passed**. The exact node IDs are in
  [ci/callable-nodes.txt](../ci/callable-nodes.txt)
- Unchanged earlier public adapter selection: **502 passed**, using
  [ci/portable-nodes.txt](../ci/portable-nodes.txt)
- Combined audited selection: **645 passed**, zero failures, errors, or skips.
  The audit observed no execution or imports from frozen nonpublic inputs, and
  only the original main thread remained after testing

The original three source-dependent checks are not counted as public passes.
Source-preservation evidence was checked separately outside the public tree:
all six complete contract ASTs match their fixed source, and every byte after the
module docstring matches the already-reviewed callable implementation. No
nonpublic reference, manifest, path, identity pin, or generated receipt is needed
to run the public tests.

Portability edits remove those three checks and their private fixture constants;
one remaining module-source inspection reads the actual imported module path.
A forbidden-protocol string assertion was generalized to remove a nonpublic
project prefix. The cleanup and repaired-edge suites were copied without
behavioral changes. New contract tests specify public behavior; they do not
pretend to prove the unavailable source's identity.

An initial audit-wrapper run omitted the source import environment for five
child-process checks; those checks failed to import the package. Correcting the
runner environment produced the 645-case pass without implementation changes.

## Installed artifact checks

The wheel was built outside the source tree and installed offline, without
dependencies or bytecode, into a fresh virtual environment. An isolated `-I -B`
process verified that the environment contained exactly one distribution,
`opendot-engineering==0.2.0a0`, and imported `tool_runtime` from its installed
location. It then executed the actual [demo](../examples/callable-execution/demo.py):

- One successful addition returned `5`
- A missing permission produced `BLOCKED` with zero handler calls
- One observed ordinary failure followed by success returned `8` on attempt two
- A non-idempotent failure dispatched once and was not retry-eligible
- The explicit non-`None` guard propagated its configured exception without dispatch

Every demo worker was joined. No optional backend or test dependency was loaded
in the installed environment. The wheel's source payload, Apache-2.0 metadata,
LICENSE/NOTICE contents, and complete RECORD hashes were checked. No second
namespace-owning distribution was installed.

## Reproduce the public tests

Install the repository's test tooling in a chosen environment. From the source
root, use Bash and an external output directory:

```sh
mapfile -t callable_nodes < ci/callable-nodes.txt
mapfile -t adapter_nodes < ci/portable-nodes.txt
CHECK_OUTPUT=$(mktemp -d /tmp/opendot-callable-check.XXXXXX)
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src \
  python -B -m pytest -q -ra -p no:cacheprovider \
  "${adapter_nodes[@]}" "${callable_nodes[@]}" \
  --basetemp="$CHECK_OUTPUT/pytest" --junitxml="$CHECK_OUTPUT/results.xml"
PYTHONPATH=src python -B examples/callable-execution/demo.py
```

The tests use finite synthetic callables, context variables, and controlled
executor faults. They exercise result-wait interruption with both synthetic
proxies and real standard-library Futures, cleanup exception precedence, timeout
observation failure, no-retry reconciliation, permission snapshots, detached
payloads, and stale-probe exclusion. No source owner was reimplemented for tests.

## Not evaluated or claimed

No private product consumer has switched owners. No model, native backend,
physical device, cancellation backend, lifetime owner, recovery-event protocol,
remote write, publication, full legacy-runtime compatibility, supported-platform
matrix, scientific validity, or OS sandbox guarantee is established. All earlier
native or simulated-lab execution records retain their original revision scope;
those optional executions were not rerun for this addition.
