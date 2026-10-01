# Usability and research candidate verification

Date: 1 October 2026 UTC. Candidate version: **0.2.0a3**, unreleased.

## Local combined source result

**899 selected tests passed**, with zero failures, errors or skips on Linux,
Python 3.12.14 and Git 2.52.0. The exact six-manifest union is disjoint:
805 inherited cases plus 30 demo-output, 20 module-CLI and 44 research-index cases.
The hosted portable selection omits the 78 controlled-Git cases; its 821 selected
nodes are a workflow definition, not a hosted CI result. See [CI recipes](../ci/README.md).

An initial integration harness omitted PYTHONPATH for inherited child processes:
894 passed and five failed with missing-package imports. Correcting the harness
environment, without changing production code or tests, produced the result above.
The initial log is retained with the delivery evidence.

## What changed

- Read-only package help/version through `python -m opendot_engineering`; no
  console script, dispatch, runtime startup or optional-backend loading
- Preflight collision diagnostics in two example CLIs. Existing output paths
  are preserved. Direct-call exceptions and later failures retain their behavior;
  the preflight is non-atomic and adds no retry or cleanup
- Offline structural checks for the source-to-need index, including negative
  fixtures. They do not prove source truth, endorsement or feature completion
- Dated speaker-attributed research additions, with proposed acceptance criteria

The existing artifact, callable, metadata and Git implementation owners retain
their reviewed bytes. Only the package version and a new passive entrypoint change
production files in this candidate. Existing consumers are not migrated.

## Independent worker checks

Two implementation-blind worker reviews passed 18 demo probes and seven CLI probes;
the seven CLI probes repeated successfully on the author's intermediate wheel.
The reviewer additionally reran 80 focused demo tests and 20 CLI tests. The later
research-index review passed 44 tests and rejected ten additional invalid copies.
These counts overlap with the combined selection and must not be added to 899.

[Host-orchestrated development](host-development/README.md) records actual isolated
worktrees, CAS outputs, measured worker overlap, separate independent review and
ordinary host Git integration. It does not establish autonomous OpenDot scheduling,
multi-host execution, simultaneous model inference, durable recovery or speedup.

## Artifact and release boundary

The final commit, source archive, installed wheel, documentation and exact payload
need their own independent review. Those final identities and outcomes are recorded
in the separate delivery receipt. A source test pass is not final artifact or
release acceptance. GitHub publication and hosted CI have not been completed.

Optional fake/native/model/provider execution is not part of these 899 checks.
The [accepted predecessor record](metadata-predecessor-acceptance.md) remains bound
to its exact earlier artifacts. No scientific or physical-device qualification is
implied by software or simulated checks.
