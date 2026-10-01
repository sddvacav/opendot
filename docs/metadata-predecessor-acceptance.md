# Accepted metadata predecessor

Historical artifact: 0.2.0a2; source commit
`65b6a53e6fc75410a61b31262b42627cf9c6641b`. Review date: 1 October 2026 UTC.

- Source archive SHA-256: `77fcb5b717511f8aed358c65ffbee9208893fe58854416f5036c9619fbed7b7b`
- Wheel SHA-256: `999f4d5db890c0cd1eab23a17c4c08d4a48732a52067c9889e9aa16089ba9aaa`
- Independent metadata suite: 410 predeclared cases passed on source and the same
  410 on the isolated installed wheel. This is not 820 unique cases
- Author checks: 805 selected source cases; 32 repeated installed metadata cases;
  seven isolated installed examples. The independent metadata review does not
  claim to have rerun all 805 author cases
- 145 source files, 18 Python payloads, 24 wheel members and 23 hashed RECORD
  entries matched the exact source/archive/package identities

The metadata review checks explicit declaration validation, field/default/export
identity and passive behavior. It does not add runtime budget, permission or
memory enforcement. The existing ArtifactRef body and other implementation owners
were preserved. Acceptance is bounded to this metadata candidate.

## Exact-predecessor-wheel fake-only replay

The same exact 0.2.0a2 wheel separately passed 108 fake-only checks, zero failures
or skips, using pinned Bluesky 1.15.1, ophyd 1.11.2 and event-model 1.24.0.
Seventeen cases overlap the portable selection; 91 are other fake-only nodes.
Fourteen additional malformed/tamper probes were refused. Normal execution emitted
19 documents/16 events; fake failure and abort each emitted two documents/no events.

Outputs remain SIMULATED_ONLY with false scientific/device authority. Existing
inputs and historical evidence stayed unchanged. Python-level instrumentation
observed no network or forbidden backend imports; it is not an OS sandbox.
This is repeat validation, not new unique coverage, a score increase, physical
qualification or acceptance of a later software version.
