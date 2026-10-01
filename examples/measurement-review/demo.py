"""Bounded synthetic batch review using existing callable and artifact owners."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from decimal import Decimal, InvalidOperation
import csv
import hashlib
import io
import json
from pathlib import Path

from opendot_engineering.core import ArtifactRef, ArtifactStore
from opendot_engineering.tool_runtime import ToolRisk, ToolRuntime, ToolSpec

SCHEMA = 'opendot.synthetic-measurement-review.v1'
ORACLE_ID = 'measurement-review/v1'
EXPECTED = {'schema_version': 'measurement-review-result/v1',
            'validator_id': ORACLE_ID, 'unit': 'au', 'rows': 6,
            'conditions': {'A': {'count': 3, 'sum': 6, 'mean': 2},
                           'B': {'count': 3, 'sum': 12, 'mean': 4}}}
MAX_BYTES = 65536


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def oracle_sha():
    # Describes a fixed synthetic expected result, not scientific authority.
    return sha(encoded({'id': ORACLE_ID, 'expected': EXPECTED}))


def read_small(path):
    with Path(path).open('rb') as handle:
        data = handle.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError('INPUT_TOO_LARGE')
    return data


def summarize(data):
    if not isinstance(data, bytes) or len(data) > MAX_BYTES:
        raise ValueError('INVALID_INPUT_BYTES')
    rows = csv.DictReader(io.StringIO(data.decode('utf-8'), newline=''))
    if rows.fieldnames != ['condition', 'replicate', 'value', 'unit']:
        raise ValueError('INVALID_COLUMNS')
    groups = {}
    seen = set()
    for index, row in enumerate(rows):
        if index >= 100 or set(row) != set(rows.fieldnames) or any(v is None for v in row.values()):
            raise ValueError('INVALID_ROW')
        condition, replicate, unit = row['condition'], row['replicate'], row['unit']
        if condition not in {'A', 'B'} or replicate not in {'1', '2', '3'} or unit != 'au':
            raise ValueError('INVALID_SYNTHETIC_ID_OR_UNIT')
        key = (condition, replicate)
        if key in seen:
            raise ValueError('DUPLICATE_REPLICATE')
        seen.add(key)
        try:
            value = Decimal(row['value'])
        except InvalidOperation:
            raise ValueError('INVALID_VALUE') from None
        if not value.is_finite() or value.copy_abs() > 1000000:
            raise ValueError('NONFINITE_OR_OUT_OF_RANGE_VALUE')
        groups.setdefault(condition, []).append(value)
    if seen != {(c, r) for c in ('A', 'B') for r in ('1', '2', '3')}:
        raise ValueError('INCOMPLETE_SYNTHETIC_BATCH')
    return {'schema_version': 'measurement-review-result/v1', 'validator_id': ORACLE_ID,
            'unit': 'au', 'rows': len(seen),
            'conditions': {c: {'count': len(v), 'sum': float(sum(v)),
                'mean': float(sum(v) / len(v))} for c, v in sorted(groups.items())}}


def run_case(output, data, *, grant=True, wrong_mean=False):
    # Trusted cooperative local directory only; not a sandbox or atomic workflow.
    summarize(data)  # Check before creating output or storing artifacts.
    output = Path(output)
    output.mkdir(parents=False, exist_ok=False, mode=0o700)
    store = ArtifactStore(output / 'artifacts')
    observed = []
    calls = []
    runtime = ToolRuntime()

    def handler(payload):
        calls.append(1)
        source = store.put_bytes(payload['csv'].encode(), mime_type='text/csv',
                                 producer='synthetic-measurement-example', task_id='batch-review')
        value = summarize(payload['csv'].encode())
        if wrong_mean:
            value['conditions']['A']['mean'] = 3  # Deliberate controlled counterexample.
        report = {'schema': SCHEMA, 'input_sha256': source.sha256,
                  'oracle_id': ORACLE_ID, 'oracle_sha256': oracle_sha(),
                  'summary': value, 'evidence_role': 'synthetic', 'scientific_accepted': False}
        ref = store.put_json(report, producer='synthetic-measurement-example',
                             task_id='batch-review', source_refs=(source.artifact_id,))
        observed.append((source, ref))
        return ref

    def valid(ref):
        report = json.loads(store.get_bytes(ref))
        return (report['summary'] == EXPECTED and report['input_sha256'] == sha(data)
                and report['oracle_sha256'] == oracle_sha()
                and report['scientific_accepted'] is False)

    runtime.register(ToolSpec('review-synthetic-batch', '1', 'synthetic-csv/v1', SCHEMA,
                             ToolRisk.REVERSIBLE_WRITE, timeout_s=5, max_retries=0,
                             idempotent=False, permissions=frozenset({'artifact:write'}),
                             semantic_validator=valid), handler)
    result, receipt = runtime.execute('review-synthetic-batch', {'csv': data.decode()},
        granted_permissions=frozenset({'artifact:write'}) if grant else frozenset())
    source, ref = observed[0] if observed else (None, None)
    bundle = {'schema': SCHEMA, 'input_sha256': sha(data), 'oracle_id': ORACLE_ID,
              'oracle_sha256': oracle_sha(), 'evidence_role': 'synthetic',
              'scientific_accepted': False, 'handler_calls': len(calls),
              'receipt': {'status': receipt.status, 'semantic_valid': receipt.semantic_valid,
                          'attempts': receipt.attempts, 'error_type': receipt.error_type},
              'source_ref': asdict(source) if source else None,
              'result_ref': asdict(ref) if ref else None,
              'returned_result': result is not None,
              'retained_unaccepted_result': ref is not None and result is None}
    raw = encoded(bundle)
    (output / 'bundle.json').write_bytes(raw)
    return {'bundle_sha256': sha(raw), 'input_sha256': sha(data),
            'oracle_sha256': oracle_sha(), 'status': receipt.status,
            'semantic_valid': receipt.semantic_valid, 'scientific_accepted': False}


def replay(output, *, bundle_sha256, input_sha256, oracle_sha256):
    # Caller-supplied expected hashes must come from a trusted separate channel.
    # No setup writes or puts; trusted paths/cooperative writers are still required.
    output = Path(output)
    raw = read_small(output / 'bundle.json')
    if sha(raw) != bundle_sha256:
        raise ValueError('BUNDLE_PIN_MISMATCH')
    bundle = json.loads(raw)
    if (bundle['schema'] != SCHEMA or bundle['evidence_role'] != 'synthetic'
            or bundle['scientific_accepted'] is not False
            or bundle['input_sha256'] != input_sha256
            or bundle['oracle_id'] != ORACLE_ID
            or bundle['oracle_sha256'] != oracle_sha256 or oracle_sha256 != oracle_sha()):
        raise ValueError('BINDING_OR_ORACLE_MISMATCH')
    if bundle['receipt']['status'] != 'COMPLETED' or bundle['receipt']['semantic_valid'] is not True:
        raise ValueError('UNACCEPTED_TOOL_RESULT')
    if not bundle['returned_result'] or bundle['retained_unaccepted_result'] or bundle['handler_calls'] != 1:
        raise ValueError('INVALID_EXECUTION_OBSERVATION')
    source_fields, result_fields = dict(bundle['source_ref']), dict(bundle['result_ref'])
    source_fields['source_refs'] = tuple(source_fields['source_refs'])
    result_fields['source_refs'] = tuple(result_fields['source_refs'])
    source, result = ArtifactRef(**source_fields), ArtifactRef(**result_fields)
    store = ArtifactStore(output / 'artifacts', read_only=True)
    if not store.verify(source) or not store.verify(result):
        raise ValueError('ARTIFACT_INTEGRITY_FAILED')
    data = store.get_bytes(source)
    report = json.loads(store.get_bytes(result))
    expected_report = {'schema': SCHEMA, 'input_sha256': input_sha256,
                       'oracle_id': ORACLE_ID, 'oracle_sha256': oracle_sha256,
                       'summary': EXPECTED, 'evidence_role': 'synthetic', 'scientific_accepted': False}
    if (sha(data) != input_sha256 or result.source_refs != (source.artifact_id,)
            or summarize(data) != EXPECTED or report != expected_report):
        raise ValueError('SYNTHETIC_ORACLE_FAILED')
    return {'verification_replay_passed': True, 'execution_restarted': False,
            'scientific_accepted': False, 'input_sha256': input_sha256,
            'result_sha256': result.sha256, 'oracle_sha256': oracle_sha256}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    run = commands.add_parser('run')
    run.add_argument('--output', required=True, type=Path)
    run.add_argument('--input', required=True, type=Path)
    run.add_argument('--case', choices=('valid', 'wrong-mean', 'denied'), default='valid')
    verify = commands.add_parser('replay')
    verify.add_argument('--output', required=True, type=Path)
    for name in ('bundle-sha256', 'input-sha256', 'oracle-sha256'):
        verify.add_argument('--' + name, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'run':
            value = run_case(args.output, read_small(args.input),
                             grant=args.case != 'denied', wrong_mean=args.case == 'wrong-mean')
        else:
            value = replay(args.output, bundle_sha256=args.bundle_sha256,
                           input_sha256=args.input_sha256, oracle_sha256=args.oracle_sha256)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        # Never echo file paths or arbitrary raw input to a shareable error report.
        print(json.dumps({'accepted': False, 'error_type': type(exc).__name__}))
        return 1
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
