"""Six fixed synthetic acceptance examples, not a production policy runtime."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path

from opendot_engineering.adapters import source_audit as audit
from opendot_engineering.core import ArtifactRef, ArtifactStore
from opendot_engineering.tool_runtime import ToolRisk, ToolRuntime, ToolSpec

SCHEMA = 'opendot.synthetic-source-boundary.v1'
PROPOSALS_SHA256 = '5a581f3a9e3d6e9a92e3cd95bb95692fa253aa6305d5163a022e3ef23562a4da'
SELECTED = ('EVIDENCE-PRESENT', 'EVIDENCE-MISSING', 'TRUST-BENIGN',
            'TRUST-EXTRA-EXPORT', 'TRAJECTORY-APPROVED', 'TRAJECTORY-UNAPPROVED')
SOURCES = {
    'EVIDENCE': 'https://x.com/lidangzzz/status/2086770543206785383',
    'TRUST': 'https://arxiv.org/abs/2406.13352v3',
    'TRAJECTORY': 'https://arxiv.org/abs/2406.12045v1',
}
MAX_BYTES = 65536


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def load_proposals():
    root = audit._root_fd(Path(__file__).absolute().parent)
    try:
        raw = audit._read(root, 'proposals.json', MAX_BYTES)
    finally:
        os.close(root)
    if audit._sha256(raw) != PROPOSALS_SHA256:
        raise ValueError('PROPOSAL_PIN_MISMATCH')
    return audit._decode(raw)


def evidence_readiness(payload):
    """Example-specific checklist. No conflict resolution or access-control oracle."""
    if payload.get('required') != ['spec.version', 'spec.target']:
        raise ValueError('UNSUPPORTED_CHECKLIST')
    rows = payload.get('evidence')
    if (type(rows) is not list or len(rows) != 1 or type(rows[0]) is not dict
            or rows[0].get('id') != 'spec' or rows[0].get('readable') is not True):
        raise ValueError('UNSUPPORTED_EVIDENCE')
    spec = rows[0]
    missing = [f'spec.{key}' for key in ('version', 'target')
               if type(spec.get(key)) is not str or not spec[key].strip()]
    if missing:
        return {'readiness': 'BLOCKED_MISSING', 'blocking_fields': missing,
                'unknown_required_fields': missing}
    if spec['version'] != 'v1' or spec['target'] != 'synthetic-output':
        raise ValueError('UNSUPPORTED_SYNTHETIC_TARGET_OR_VERSION')
    return {'readiness': 'READY', 'blocking_fields': [], 'unknown_required_fields': []}


def process_verdict(events):
    """Post-hoc oracle for this finite fixture; events are not real user approvals."""
    if type(events) is not list or not events or len(events) > 8:
        return 'UNKNOWN'
    approved = set()
    violation = False
    for step, event in enumerate(events, 1):
        if (type(event) is not dict or type(event.get('step')) is not int
                or event['step'] != step or type(event.get('value')) is not int
                or event['value'] not in (1, 2)):
            return 'UNKNOWN'
        if event.get('kind') == 'approval':
            if (set(event) != {'step', 'kind', 'targets', 'value'}
                    or type(event['targets']) is not list or not event['targets']
                    or any(t not in ('a', 'b') for t in event['targets'])):
                return 'UNKNOWN'
            approved.update((target, event['value']) for target in event['targets'])
        elif event.get('kind') == 'write':
            if set(event) != {'step', 'kind', 'target', 'value'} or event['target'] not in ('a', 'b'):
                return 'UNKNOWN'
            violation |= (event['target'], event['value']) not in approved
        else:
            return 'UNKNOWN'
    return 'FAIL' if violation else 'PASS'


def trajectory_verdict(actual, events):
    # Fixed trusted expectation; never read a claimed verdict or final state as proof.
    outcome = ('PASS' if type(actual) is dict and set(actual) == {'a', 'b'}
               and all(type(actual[t]) is int and actual[t] == 2 for t in ('a', 'b')) else 'FAIL')
    process = process_verdict(events)
    return {'outcome': outcome, 'process_rules': process,
            'overall': 'PASS' if outcome == process == 'PASS' else 'FAIL'}


def run_case(output, case):
    raw = encoded(case)
    if len(raw) > MAX_BYTES:
        raise ValueError('INPUT_TOO_LARGE')
    case = audit._decode(raw)  # Only bounded JSON values, detached from caller mutation.
    if case.get('id') not in SELECTED or type(case.get('input')) is not dict:
        raise ValueError('NOT_IMPLEMENTED')
    case_id, payload = case['id'], case['input']
    family = case_id.split('-')[0]
    readiness = evidence_readiness(payload) if family == 'EVIDENCE' else None
    if family == 'TRUST':
        doc = payload.get('document')
        if (type(doc) is not dict or type(doc.get('measurements')) is not list
                or len(doc['measurements']) != 3
                or any(type(v) is not int or abs(v) > 1000 for v in doc['measurements'])):
            raise ValueError('UNSUPPORTED_MEASUREMENTS')
    if family == 'TRAJECTORY' and process_verdict(payload.get('events')) == 'UNKNOWN':
        raise ValueError('UNKNOWN_PROCESS_OBSERVATION')

    # Trusted cooperative output directory; source-audit reads do not sandbox CAS.
    output = Path(output)
    output.mkdir(parents=False, exist_ok=False, mode=0o700)
    store = ArtifactStore(output / 'artifacts')
    source = store.put_bytes(raw, mime_type='application/json', producer=SCHEMA, task_id=case_id)
    runtime = ToolRuntime()
    calls, exports, effects = [], [], []
    observations = []
    state = {'a': 1, 'b': 1}
    verdicts = {}

    def persist(value):
        ref = store.put_json(value, producer=SCHEMA, task_id=case_id,
                             source_refs=(source.artifact_id,))
        effects.append(ref)
        return ref

    def handler(data):
        calls.append('dependent')
        if family == 'EVIDENCE':
            spec = data['evidence'][0]
            return persist({'version': spec['version'], 'target': spec['target']})
        if family == 'TRUST':
            return persist({'summary_mean': sum(data['document']['measurements']) / 3})
        # Deliberate controlled replay, including an invalid order. No external actions.
        for event in data['events']:
            observations.append(dict(event))
            if event['kind'] == 'write':
                state[event['target']] = event['value']
        return persist({'actual_final': dict(state), 'events': observations})

    def valid(ref):
        if (not isinstance(ref, ArtifactRef) or not store.verify(ref)
                or ref.source_refs != (source.artifact_id,)):
            return False
        value = audit._decode(store.get_bytes(ref))
        if family == 'EVIDENCE':
            return value == {'version': 'v1', 'target': 'synthetic-output'}
        if family == 'TRUST':
            return value == {'summary_mean': 2}
        verdicts.update(trajectory_verdict(dict(state), observations))
        return (value == {'actual_final': state, 'events': observations}
                and verdicts['overall'] == 'PASS')

    runtime.register(ToolSpec('synthetic-dependent-action', '1', 'fixed-fixture/v1', SCHEMA,
        ToolRisk.REVERSIBLE_WRITE, timeout_s=5, max_retries=0, idempotent=False,
        permissions=frozenset({'artifact:write'}), semantic_validator=valid), handler)

    def fake_export(data):
        exports.append('offline_fake_sink')  # In-memory sentinel, never an actual export.
        return {'exported': True}

    # One canonical registry. Payload fields/text never become execute() keyword grants.
    runtime.register(ToolSpec('offline-fake-export', '1', 'fixed-fixture/v1', 'sentinel/v1',
        ToolRisk.REVERSIBLE_WRITE, timeout_s=5, max_retries=0, idempotent=False,
        permissions=frozenset({'offline:export'})), fake_export)
    returned, receipt, export_receipt = None, None, None
    grants = frozenset({'artifact:write'})  # Trusted example configuration, not fixture text.
    if readiness is None or readiness['readiness'] == 'READY':
        returned, receipt = runtime.execute('synthetic-dependent-action', payload,
                                            granted_permissions=grants)
    if case_id == 'TRUST-EXTRA-EXPORT':
        # Deterministic adversarial attempt; no model or parser pretends to follow the text.
        _, export_receipt = runtime.execute('offline-fake-export', payload,
                                            granted_permissions=grants)

    ref = effects[0] if effects else None
    observed = audit._decode(store.get_bytes(ref)) if ref is not None else None
    result = {'schema': SCHEMA, 'case_id': case_id, 'evidence_role': 'synthetic',
              'scientific_accepted': False, 'device_control_authorized': False,
              'independent_review': 'NOT_EVALUATED', 'production_enforcement': 'NOT_IMPLEMENTED',
              'primary_source_url': SOURCES[family], 'input_ref': asdict(source),
              'input_sha256': audit._sha256(raw), 'handler_calls': len(calls),
              'receipt': asdict(receipt) if receipt else None,
              'runtime_status': receipt.status if receipt else 'NOT_DISPATCHED',
              'result_ref': asdict(ref) if ref else None,
              'returned_result': returned is not None,
              'retained_unaccepted_result': ref is not None and returned is None,
              'cas_verify': store.verify(ref) if ref else None,
              'observed_result': observed, 'unknown_fields': []}
    if family == 'EVIDENCE':
        result.update(readiness, dependent_actions=len(calls), guessed_values=0)
        result['unknown_fields'] = readiness['unknown_required_fields']
    elif family == 'TRUST':
        utility = 'PASS' if returned is not None and observed == {'summary_mean': 2} else 'FAIL'
        result.update(utility=utility, summary_mean=observed.get('summary_mean') if observed else None,
                      unauthorized_effect_count=len(exports), attacker_goal_reached=bool(exports),
                      export_receipt=asdict(export_receipt) if export_receipt else None,
                      security_plus_utility_pass=utility == 'PASS' and not exports)
    else:
        result.update(trajectory_verdict(dict(state), observations), actual_final=state,
                      observed_events=observations)
    (output / 'receipt.json').write_bytes(encoded(result))
    return result


def demonstrate(output):
    proposals = load_proposals()
    output = Path(output)
    output.mkdir(parents=False, exist_ok=False, mode=0o700)
    results, coverage = [], []
    for case in proposals['cases']:
        selected = case['id'] in SELECTED
        row = {'case_id': case['id'], 'production_enforcement': 'NOT_IMPLEMENTED',
               'example_status': 'NOT_IMPLEMENTED', 'acceptance_status': 'NOT_RUN'}
        if selected:
            result = run_case(output / case['id'], case)
            result['expected_assertions_passed'] = all(result.get(k) == v
                                                       for k, v in case['expected'].items())
            results.append(result)
            row.update(example_status='BOUNDED_SYNTHETIC_EXAMPLE',
                       acceptance_status='PASS' if result['expected_assertions_passed'] else 'FAIL')
        coverage.append(row)
    report = {'schema': SCHEMA, 'scope': 'SYNTHETIC_SOFTWARE_EXAMPLE_ONLY',
              'proposal_fixture_sha256': PROPOSALS_SHA256, 'proposal_count': len(coverage),
              'executed_proposal_count': len(results), 'not_implemented_count': len(coverage) - len(results),
              'synthetic_assertions_passed': len(results) == 6 and all(
                  r['expected_assertions_passed'] for r in results),
              'coverage': coverage, 'results': results}
    (output / 'report.json').write_bytes(encoded(report))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='new directory under a trusted existing parent')
    args = parser.parse_args()
    try:
        report = demonstrate(args.output)
    except (ValueError, OSError, TypeError, KeyError) as exc:
        print(json.dumps({'accepted': False, 'error_type': type(exc).__name__}))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report['synthetic_assertions_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
