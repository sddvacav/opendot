# Integrated artifact/callable core verification

Date: 2026-10-01 UTC. Version: **0.2.0a0, unreleased**. This is the local
implementation-worker integration record, not an independent decision on the
combined artifact, hosted-CI success, publication, or real-consumer migration.

## Exact scope and preserved owners

The two reviewed public component candidates are combined into one
`opendot-engineering` distribution and one `opendot_engineering` import namespace.
The complete `core/artifacts.py`, `core/contracts.py`, `core/__init__.py`, and
`tool_runtime.py` bytes are retained from their respective inputs. No duplicate
store, reference, execution owner, or copied tool contract is introduced.
Existing adapter/executor and baseline test bytes remain unchanged.

The newly authored [small composition](../examples/callable-artifacts/README.md)
uses ordinary standard-library Python calls. It demonstrates three outcomes:

- A permitted callable writes synthetic text, returns the canonical reference,
  and gets a COMPLETED, semantic-valid receipt; retrieved bytes are independently
  hashed and checked against the reference
- A validator refusal yields FAILED, semantic-invalid, with no returned result;
  the prior write remains as a separately observed, intact, unaccepted artifact
- A missing permission yields BLOCKED/PermissionDenied with zero handler calls
  and zero objects; empty store directories may already exist

Byte integrity does not imply tool-result or scientific acceptance. The example
claims only that its synthetic software assertions pass. It does not implement
rollback, a Goal/DAG, JobRuntime, persistent controller, or a broader runtime.

## Local source execution

Executed on Python 3.12.14/Linux with pre-existing pytest 9.1.1. All output,
pytest temporary directories, and JUnit files were outside source, against a
separate exported copy. Bytecode/plugin autoload/cache were disabled; the aggregate
runner used `-I -B` and checked exact collected node equality.

- CAS predecessor selection: 545; callable predecessor selection: 645
- Their 502 shared baseline cases are counted once: **688 inherited unique cases**
- New composition selection: **7 cases**
- Integrated portable total: **695 passed, 0 failed, 0 errors, 0 skipped**
- Complete separately prepared fake-only simulation selection: **108 passed,
  0 failed, 0 errors, 0 skipped**; **17 overlap** with the portable selection,
  so these are not 108 additional independent cases

The inherited 43 CAS and 143 callable nodes remain intact. The three excluded
private source-identity callable tests are not counted. The aggregate ended with
only its original MainThread, with no optional backend imports, private-source
execution, or network connection attempts observed. Existing finite Python/Git
child checks retain their approved scope. The fake-only run uses the already
prepared exact optional dependency environment, never a real device or native
solver. See [manifest composition and reproduction](../ci/README.md).

## Exact final artifact checks

Keep the exact committed source/tree, source archive and wheel hashes, member
inventories, installed probe output, and source/CI/link/privacy checks in the
external integration packet. Build only from the committed exported tree, using
an external build directory. Verify every source-archive member against Git and
every wheel package-source member, LICENSE/NOTICE, RECORD digest, and size.

Install the final wheel offline without dependencies or bytecode into a newly
created environment. Use `python -I -B` from outside the source checkout to run
the composition and both component examples. Confirm all core imports originate
inside that environment, only one distribution owns the namespace, and no test
or optional backend dependency is loaded. Read and independently hash the
composition's successful and retained unaccepted objects; a successful import
alone is insufficient. The public example script remains source material.

The workflow and relative documentation links are checked locally; hosted CI is
not claimed. Scoped privacy scans and exact artifact inspection are not a general
confidentiality/security certificate or release authorization. Private provenance,
independent reports, compatibility proposals, and generated receipts stay outside
source and wheels.

## Retained limitations

CAS follows symlinks beneath trusted caller-controlled roots, uses best-effort
permissions and instance-local locking, and does not transactionally publish
object plus metadata. Callable permissions/idempotence are caller declarations;
its threads are not a sandbox, and timeout does not terminate arbitrary handlers
or establish reconciliation. Semantic rejection may follow effects and, under
other declarations, may follow the runtime's existing retry policy.

No old consumer has switched owners. No model, Codex, native lifetime, private
JobRuntime, recovery event, physical device, remote write, durable recovery,
scientific acceptance, complete autonomous/multi-host system, or published
release is established. Earlier component and `0.1.0a1` evidence retains its
original revision and scope.
