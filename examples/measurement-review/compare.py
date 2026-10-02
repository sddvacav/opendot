"""Three fixed local callable roles: tolerance, descriptive comparison, arithmetic check."""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
from decimal import Decimal, localcontext
from fractions import Fraction
import io
import json
import math
import os
from pathlib import Path
import re
import sys
import types

from opendot_engineering.adapters import source_audit as audit
from opendot_engineering.core import ArtifactRef, ArtifactStore
from opendot_engineering.core.artifacts import ArtifactIntegrityError
from opendot_engineering.tool_runtime import ToolRisk, ToolRuntime, ToolSpec

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = 'opendot.measurement-comparison.v1'
MAX_BYTES = 65536
MAX_TEXT_BYTES = 8192
DECIMAL_PATTERN = r'-?(?:0|[1-9][0-9]{0,6})(?:\.[0-9]{1,12})?'
PARAMETER_PATTERN = r'-?(?:0|[1-9][0-9]{0,5})(?:\.[0-9]{1,12})?'
SOURCE_PINS = {
    'src/opendot_engineering/tool_runtime.py': '7c5011e02b2cf07e5f15ad7854905ce0738271e167b873bad9256a8ed169199c',
    'src/opendot_engineering/core/artifacts.py': '4606b7b11a81044267b30fee332d9b6fd6540d862726a9579655ee27c7d9a883',
    'src/opendot_engineering/core/contracts.py': '9462415baf84668825ad2c8cfc3f4f3df68332f65d1f1f4b301fbf01cf8537ca',
    'src/opendot_engineering/adapters/source_audit.py': 'c94737305b1e5a80453541ce890bde4fcb700a0074e32344fe839b237374bfa7',
    'examples/measurement-review/demo.py': '8a363374fc05cf9fd93314c8814729e29653d0a997a22c74f652842e37904624',
    'examples/source-boundary/demo.py': 'fe70a4cfacbba3a69dd8f340057d5bb4a1486f3c2a470b853250008151601be1',
    'examples/measurement-review/comparison-fixtures.json': 'dd72773f56886888be00c7f5a2c8ec461eb3f9e0eb984043bf20fdd5191cb1cd',
    'examples/measurement-review/batch.csv': '12fa76e2cb8defb752ce08a2fdd386b0f943579d1438e3022cb2e345bdcae0d9',
}
ROLE_IDS = {'parameter': 'comparison-parameter', 'analysis': 'comparison-analysis',
            'verifier': 'comparison-verifier'}
PERMISSIONS = {role: frozenset({f'comparison:{role}'}) for role in ROLE_IDS}
FLAGS = {'scientific_accepted': False, 'device_control_authorized': False,
         'independent_review': 'NOT_EVALUATED'}
ERROR_CODES = frozenset({
    'INVALID_ARGUMENTS', 'INPUT_UNAVAILABLE', 'INPUT_TOO_LARGE', 'INVALID_CSV',
    'INVALID_DECIMAL', 'INVALID_PARAMETERS', 'INVALID_JSON', 'SOURCE_PIN_MISMATCH',
    'INVALID_EVIDENCE_ROLE', 'DEMO_INPUT_MISMATCH', 'OUTPUT_EXISTS', 'OUTPUT_IN_SOURCE',
    'OUTPUT_UNAVAILABLE', 'OUTPUT_IO_ERROR', 'REPORT_TOO_LARGE', 'INVALID_PIN',
    'REPORT_PIN_MISMATCH', 'INPUT_PIN_MISMATCH', 'PROFILE_PIN_MISMATCH',
    'INVALID_REPORT', 'INVALID_ARTIFACT', 'ARTIFACT_INTEGRITY_FAILED',
    'BINDING_MISMATCH', 'NUMERIC_MISMATCH', 'PARAMETER_MISMATCH',
    'BLOCKED_UNKNOWN', 'BLOCKED_CONFLICT', 'BLOCKED_INVALID', 'NEGATIVE_TOLERANCE',
    'PERMISSION_DENIED', 'EXECUTION_UNRESOLVED', 'EXECUTION_FAILED',
    'VERIFICATION_FAILED', 'UNACCEPTED_REPORT',
})


class ComparisonRejected(ValueError):
    """Allowlisted diagnostic only; no raw input, paths or exception messages."""
    def __init__(self, code):
        self.code = code if code in ERROR_CODES else 'INVALID_REPORT'
        super().__init__(self.code)


def require(condition, code):
    if not condition:
        raise ComparisonRejected(code)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def sha(data):
    return audit._sha256(data)


def same(left, right):
    # JSON equality without bool/int or int/float coercion.
    return encoded(left) == encoded(right)


def read_local(path, limit=MAX_BYTES):
    path = Path(path).absolute()
    try:
        fd = audit._root_fd(path.parent)
        try:
            return audit._read(fd, path.name, limit)
        finally:
            os.close(fd)
    except audit.AuditRejected as exc:
        raise ComparisonRejected('INPUT_TOO_LARGE' if exc.code == 'INPUT_TOO_LARGE'
                                 else 'INPUT_UNAVAILABLE') from None


def decode(raw):
    require(type(raw) is bytes and len(raw) <= MAX_BYTES, 'INPUT_TOO_LARGE')
    try:
        value = audit._decode(raw)
        encoded(value)  # Also refuse finite-JSON syntax whose exponent overflows a float.
        return value
    except (audit.AuditRejected, ValueError, RecursionError):
        raise ComparisonRejected('INVALID_JSON') from None


def profile(evidence_role):
    require(evidence_role in ('synthetic', 'user_supplied_unvalidated'), 'INVALID_EVIDENCE_ROLE')
    for module_name, relative in (
        ('opendot_engineering.tool_runtime', 'src/opendot_engineering/tool_runtime.py'),
        ('opendot_engineering.core.artifacts', 'src/opendot_engineering/core/artifacts.py'),
        ('opendot_engineering.core.contracts', 'src/opendot_engineering/core/contracts.py'),
        ('opendot_engineering.adapters.source_audit', 'src/opendot_engineering/adapters/source_audit.py'),
    ):
        require(Path(sys.modules[module_name].__file__).resolve() == (ROOT / relative).resolve(),
                'SOURCE_PIN_MISMATCH')
    for path, expected in SOURCE_PINS.items():
        require(sha(read_local(ROOT / path)) == expected, 'SOURCE_PIN_MISMATCH')
    return {
        'id': 'measurement-comparison/bench-A-au/v1', 'evidence_role': evidence_role,
        'source_sha256': dict(SOURCE_PINS),
        'consumer_sha256': sha(read_local(ROOT / 'examples/measurement-review/compare.py')),
        'scenario': 'bench-A', 'unit': 'au', 'conditions': ['A', 'B'],
        'replicates': ['1', '2', '3'], 'max_input_bytes': MAX_BYTES,
        'max_result_bytes': MAX_BYTES, 'max_report_bytes': MAX_BYTES,
        'max_summary_bytes': MAX_TEXT_BYTES, 'max_sources': 8,
        'value_max_abs': '1000000', 'tolerance_max_abs': '999999.999999999999',
        'max_numeric_characters': 32, 'max_fractional_places': 12,
        'decimal_precision': 50, 'float_absolute_allowance': '0.000000000001',
        'float_relative_allowance': '0.000000000000001',
        'decision_rule': 'abs(sum_B*n_A-sum_A*n_B)<=tolerance*n_A*n_B',
        'attempt_limit': 1, 'timeout_seconds': 5, 'scripted_roles': list(ROLE_IDS),
    }


def load_producers():
    # Fixed repository paths and hash-checked captured bytes; no caller-selected
    # modules, exports, discovery, source admission or new execution owner.
    loaded = []
    for path, name in (('examples/source-boundary/demo.py', 'comparison_parameter_source'),
                       ('examples/measurement-review/demo.py', 'comparison_measurement_source')):
        raw = read_local(ROOT / path)
        require(sha(raw) == SOURCE_PINS[path], 'SOURCE_PIN_MISMATCH')
        module = types.ModuleType(name)
        module.__file__ = str(ROOT / path)
        exec(compile(raw, path, 'exec'), module.__dict__)
        loaded.append(module)
    return loaded[0].parameter_readiness, loaded[1].summarize


def demo_inputs():
    profile('synthetic')
    fixtures = decode(read_local(ROOT / 'examples/measurement-review/comparison-fixtures.json'))
    return read_local(ROOT / 'examples/measurement-review/batch.csv'), encoded(fixtures['demo_parameters'])


def parse_csv_decimal(raw):
    require(type(raw) is bytes and len(raw) <= MAX_BYTES, 'INPUT_TOO_LARGE')
    try:
        rows = list(csv.reader(io.StringIO(raw.decode('utf-8'), newline=''), strict=True))
    except (UnicodeError, csv.Error):
        raise ComparisonRejected('INVALID_CSV') from None
    require(len(rows) == 7 and rows[0] == ['condition', 'replicate', 'value', 'unit'], 'INVALID_CSV')
    groups, seen = {'A': [], 'B': []}, set()
    for row in rows[1:]:
        require(len(row) == 4, 'INVALID_CSV')
        condition, replicate, value, unit = row
        require(condition in groups and replicate in ('1', '2', '3') and unit == 'au'
                and (condition, replicate) not in seen, 'INVALID_CSV')
        require(len(value) <= 32 and re.fullmatch(DECIMAL_PATTERN, value) is not None,
                'INVALID_DECIMAL')
        number = Decimal(value)
        require(abs(number) <= 1000000, 'INVALID_DECIMAL')
        groups[condition].append(number)
        seen.add((condition, replicate))
    require(seen == {(c, r) for c in ('A', 'B') for r in ('1', '2', '3')}, 'INVALID_CSV')
    return groups


def parameter_shape(raw):
    value = decode(raw)
    require(type(value) is dict and set(value) == {'task', 'sources'}
            and same(value['task'], {'scenario': 'bench-A', 'unit': 'au'}), 'INVALID_PARAMETERS')
    rows = value['sources']
    require(type(rows) is list and len(rows) <= 8, 'INVALID_PARAMETERS')
    names = set()
    for row in rows:
        require(type(row) is dict and 'source' in row
                and set(row) <= {'source', 'scenario', 'unit', 'raw_value'}, 'INVALID_PARAMETERS')
        name = row['source']
        require(type(name) is str and re.fullmatch(r'[A-Za-z0-9_-]{1,64}', name) is not None
                and name not in names, 'INVALID_PARAMETERS')
        names.add(name)
    return value


def rational(numerator, denominator=1):
    divisor = math.gcd(numerator, denominator)
    return {'numerator': numerator // divisor, 'denominator': denominator // divisor}


def decimal_ratio(value, denominator=1):
    numerator, scale = value.as_integer_ratio()
    return rational(numerator, scale * denominator)


def produce_comparison(raw, resolution):
    groups = parse_csv_decimal(raw)
    with localcontext() as context:
        context.prec = 50
        a, b = sum(groups['A']), sum(groups['B'])
        tolerance = Decimal(resolution['selected_decimal'])
        difference = abs(b * 3 - a * 3)
        return {'absolute_mean_difference': decimal_ratio(difference, 9),
                'tolerance': decimal_ratio(tolerance),
                'within_tolerance': difference <= tolerance * 9,
                'selected_decimal': resolution['selected_decimal'],
                'matching_sources': resolution['matching_sources']}


def independent_expected(csv_raw, parameters_raw):
    """Separate Fraction oracle. Never calls either producer or Decimal parser."""
    require(type(csv_raw) is bytes and len(csv_raw) <= MAX_BYTES, 'INPUT_TOO_LARGE')
    try:
        records = list(csv.DictReader(io.StringIO(csv_raw.decode('utf-8'), newline=''), strict=True))
        physical_rows = list(csv.reader(io.StringIO(csv_raw.decode('utf-8'), newline=''), strict=True))
        header = physical_rows[0] if physical_rows else None
    except (UnicodeError, csv.Error, StopIteration):
        raise ComparisonRejected('INVALID_CSV') from None
    require(header == ['condition', 'replicate', 'value', 'unit'] and len(records) == 6
            and len(physical_rows) == 7, 'INVALID_CSV')
    cells = {}
    for row in records:
        require(set(row) == {'condition', 'replicate', 'value', 'unit'}
                and all(type(v) is str for v in row.values()), 'INVALID_CSV')
        key = (row['condition'], row['replicate'])
        require(key in {(c, r) for c in ('A', 'B') for r in ('1', '2', '3')}
                and key not in cells and row['unit'] == 'au', 'INVALID_CSV')
        text = row['value']
        require(len(text) <= 32 and re.fullmatch(DECIMAL_PATTERN, text) is not None, 'INVALID_DECIMAL')
        number = Fraction(text)
        require(abs(number) <= 1000000, 'INVALID_DECIMAL')
        cells[key] = number
    require(len(cells) == 6, 'INVALID_CSV')

    payload = decode(parameters_raw)
    require(type(payload) is dict and set(payload) == {'task', 'sources'}
            and same(payload['task'], {'scenario': 'bench-A', 'unit': 'au'}), 'INVALID_PARAMETERS')
    sources = payload['sources']
    require(type(sources) is list and len(sources) <= 8, 'INVALID_PARAMETERS')
    seen, matching, excluded, unknown_conditions, unknown_values, invalid = set(), [], [], [], [], []
    values, raw_values = {}, []
    for source in sources:
        require(type(source) is dict and 'source' in source
                and set(source) <= {'source', 'scenario', 'unit', 'raw_value'}, 'INVALID_PARAMETERS')
        name = source['source']
        require(type(name) is str and re.fullmatch(r'[A-Za-z0-9_-]{1,64}', name) is not None
                and name not in seen, 'INVALID_PARAMETERS')
        seen.add(name)
        scenario, unit = source.get('scenario'), source.get('unit')
        if any(x is not None and type(x) is not str for x in (scenario, unit)):
            invalid.append(name)
        elif any(x is None or not x.strip() for x in (scenario, unit)):
            unknown_conditions.append(name)
        elif scenario != 'bench-A' or unit != 'au':
            excluded.append(name)
        else:
            matching.append(name)
        value = source.get('raw_value')
        if value is None:
            if name in matching:
                unknown_values.append(name)
        elif (type(value) is not str or len(value) > 32
              or re.fullmatch(PARAMETER_PATTERN, value) is None):
            invalid.append(name)
        elif name in matching:
            values[name] = Fraction(value)
        if name in matching and 'raw_value' in source:
            raw_values.append(source['raw_value'])
    status = ('INVALID' if invalid else 'UNKNOWN' if unknown_conditions or unknown_values or not matching
              else 'CONFLICT' if len(set(values.values())) != 1 else 'KNOWN')
    selected = None
    if status == 'KNOWN':
        first = next(source['raw_value'] for source in sources if source['source'] in matching)
        selected = first.rstrip('0').rstrip('.') if '.' in first else first
        if next(iter(values.values())) == 0:
            selected = '0'
    resolution = {
        'readiness': 'READY' if status == 'KNOWN' else f'BLOCKED_{status}',
        'value_status': status, 'selected_decimal': selected,
        'raw_value': raw_values[0] if status == 'KNOWN' and len(set(raw_values)) == 1 else None,
        'matching_sources': matching, 'excluded_sources': excluded,
        'unknown_applicability_sources': unknown_conditions, 'unknown_value_sources': unknown_values,
        'invalid_sources': sorted(set(invalid)),
        'unknown_required_fields': ((['sources'] if not sources else [])
            + [f'{name}.conditions' for name in unknown_conditions]
            + [f'{name}.raw_value' for name in unknown_values]),
    }
    require(status == 'KNOWN', f'BLOCKED_{status}')
    tolerance = next(iter(values.values()))
    require(tolerance >= 0, 'NEGATIVE_TOLERANCE')
    sums = {c: sum(cells[c, r] for r in ('1', '2', '3')) for c in ('A', 'B')}
    means = {c: sums[c] / 3 for c in sums}
    difference = abs(means['B'] - means['A'])
    comparison = {
        'absolute_mean_difference': rational(difference.numerator, difference.denominator),
        'tolerance': rational(tolerance.numerator, tolerance.denominator),
        'within_tolerance': difference <= tolerance, 'selected_decimal': selected,
        'matching_sources': matching,
    }
    return resolution, sums, means, comparison


def check_candidate(csv_raw, parameters_raw, parameter_value, analysis_value, binding):
    require(type(parameter_value) is dict and set(parameter_value) == {'binding', 'resolution'}
            and same(parameter_value['binding'], binding), 'BINDING_MISMATCH')
    require(type(analysis_value) is dict and set(analysis_value) == {'binding', 'summary', 'comparison'}
            and same(analysis_value['binding'], binding), 'BINDING_MISMATCH')
    resolution, sums, means, comparison = independent_expected(csv_raw, parameters_raw)
    require(same(parameter_value['resolution'], resolution), 'PARAMETER_MISMATCH')
    require(same(analysis_value['comparison'], comparison), 'NUMERIC_MISMATCH')
    summary = analysis_value['summary']
    require(type(summary) is dict and set(summary) == {'schema_version', 'validator_id', 'unit', 'rows', 'conditions'}
            and summary['schema_version'] == 'measurement-review-result/v1'
            and summary['validator_id'] == 'measurement-review/v1' and summary['unit'] == 'au'
            and type(summary['rows']) is int and summary['rows'] == 6
            and type(summary['conditions']) is dict and set(summary['conditions']) == {'A', 'B'}, 'NUMERIC_MISMATCH')
    for condition in ('A', 'B'):
        observed = summary['conditions'][condition]
        require(type(observed) is dict and set(observed) == {'count', 'sum', 'mean'}
                and type(observed['count']) is int and observed['count'] == 3, 'NUMERIC_MISMATCH')
        for field, exact in (('sum', sums[condition]), ('mean', means[condition])):
            value = observed[field]
            require(type(value) is float and math.isfinite(value), 'NUMERIC_MISMATCH')
            allowance = max(Fraction(1, 10**12), abs(exact) / 10**15)
            require(abs(Fraction.from_float(value) - exact) <= allowance, 'NUMERIC_MISMATCH')
    return comparison


def as_ref(fields):
    require(type(fields) is dict and set(fields) == set(ArtifactRef.__dataclass_fields__), 'INVALID_ARTIFACT')
    require(all(type(fields[k]) is str for k in ('artifact_id', 'uri', 'mime_type', 'sha256',
                                               'schema_version', 'producer', 'task_id'))
            and type(fields['size_bytes']) is int and fields['size_bytes'] >= 0
            and fields['integrity_verified'] is True and type(fields['source_refs']) is list
            and all(type(x) is str for x in fields['source_refs']), 'INVALID_ARTIFACT')
    try:
        ref = ArtifactRef(**{**fields, 'source_refs': tuple(fields['source_refs'])})
        ref.validate()
        require(ref.uri == f'artifact://sha256/{ref.sha256}', 'INVALID_ARTIFACT')
        return ref
    except (ValueError, TypeError):
        raise ComparisonRejected('INVALID_ARTIFACT') from None


def read_artifact(store, ref, *, mime, task, sources=()):
    require(isinstance(ref, ArtifactRef) and ref.mime_type == mime and ref.producer == SCHEMA
            and ref.task_id == task and ref.schema_version == '1.0.0'
            and ref.source_refs == sources and ref.integrity_verified is True, 'INVALID_ARTIFACT')
    try:
        raw = store.get_bytes(ref, max_bytes=MAX_BYTES)
    except (OSError, ValueError, ArtifactIntegrityError):
        raise ComparisonRejected('ARTIFACT_INTEGRITY_FAILED') from None
    require(len(raw) == ref.size_bytes, 'ARTIFACT_INTEGRITY_FAILED')
    return raw


def binding_for(csv_raw, parameters_raw, selected_profile):
    return {'schema': SCHEMA, 'input_sha256': sha(csv_raw), 'parameters_sha256': sha(parameters_raw),
            'profile_sha256': sha(encoded(selected_profile)),
            'evidence_role': selected_profile['evidence_role'], **FLAGS}


def role_spec(role, validator=None):
    return ToolSpec(ROLE_IDS[role], '1', f'{role}-input/v1', f'{role}-result/v1',
                    ToolRisk.REVERSIBLE_WRITE, timeout_s=5, max_retries=0, idempotent=False,
                    permissions=PERMISSIONS[role], semantic_validator=validator)


def empty_role():
    return {'status': 'NOT_DISPATCHED', 'attempts': 0, 'handler_calls': 0,
            'semantic_valid': False, 'error_code': None, 'input_hash': None, 'output_hash': None,
            'returned_result': False, 'result_ref': None, 'retained_unaccepted_result': False,
            'unresolved': False}


def observe_role(receipt, returned, refs, calls):
    unresolved = bool(receipt.execution_liveness.get('reconciliation_required', False)
                      or receipt.error_type == 'TimeoutError')
    error = (None if receipt.status == 'COMPLETED' and receipt.semantic_valid and not unresolved
             else 'EXECUTION_UNRESOLVED' if unresolved
             else 'PERMISSION_DENIED' if receipt.error_type == 'PermissionDenied'
             else 'EXECUTION_FAILED')
    return {'status': receipt.status if not unresolved else 'UNRESOLVED',
            'attempts': receipt.attempts, 'handler_calls': len(calls),
            'semantic_valid': receipt.semantic_valid, 'error_code': error,
            'input_hash': receipt.input_hash, 'output_hash': receipt.output_hash,
            'returned_result': returned is not None,
            'result_ref': asdict(refs[0]) if refs else None,
            'retained_unaccepted_result': bool(refs and (returned is None or unresolved)),
            'unresolved': unresolved}


def role_ok(row):
    return (row['status'] == 'COMPLETED' and row['semantic_valid'] is True
            and row['attempts'] == 1 and row['handler_calls'] == 1
            and row['returned_result'] is True and row['unresolved'] is False)


def summary_text(report):
    lines = [f"Measurement comparison: {report['status']}",
             f"Evidence: {report['evidence_role']} (local/private by default)"]
    if report['checked']:
        for condition in ('A', 'B'):
            row = report['summary']['conditions'][condition]
            lines.append(f"{condition}: count={row['count']}, sum={row['sum']}, mean={row['mean']} au")
        comparison = report['comparison']
        delta, tolerance = comparison['absolute_mean_difference'], comparison['tolerance']
        lines.extend([f"Absolute mean difference: {delta['numerator']}/{delta['denominator']} au",
                      f"Declared tolerance: {tolerance['numerator']}/{tolerance['denominator']} au",
                      'Within tolerance' if comparison['within_tolerance'] else 'Outside tolerance'])
    else:
        lines.append(f"Reason: {report['error_code']}")
    lines.append('Roles: ' + ', '.join(f"{role}={report['roles'][role]['status']}" for role in ROLE_IDS))
    lines.extend(['Scientific acceptance: false; device control: false; independent review: NOT_EVALUATED',
                  'Files: report.json, summary.txt, artifacts/ (retained results may be unaccepted)'])
    return '\n'.join(lines) + '\n'


def write_report(output, report):
    raw = encoded(report)
    text = summary_text(report).encode('utf-8')
    require(len(raw) <= MAX_BYTES and len(text) <= MAX_TEXT_BYTES, 'REPORT_TOO_LARGE')
    for name, data in (('report.json', raw), ('summary.txt', text)):
        fd = os.open(Path(output) / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
    return {'status': report['status'], 'checked': report['checked'], 'exit_code': report['exit_code'],
            'error_code': report['error_code'], 'report_sha256': sha(raw),
            'input_sha256': report['binding']['input_sha256'],
            'parameters_sha256': report['binding']['parameters_sha256'],
            'profile_sha256': report['binding']['profile_sha256'], **FLAGS}


def run_comparison(output, csv_raw, parameters_raw, *, evidence_role='user_supplied_unvalidated', grants=None):
    selected_profile = profile(evidence_role)
    parse_csv_decimal(csv_raw)
    parameter_shape(parameters_raw)
    if evidence_role == 'synthetic':
        demo_csv, demo_parameters = demo_inputs()
        require(csv_raw == demo_csv and parameters_raw == demo_parameters, 'DEMO_INPUT_MISMATCH')
    parameter_readiness, summarize = load_producers()
    output = Path(output)
    require(not output.resolve().is_relative_to(ROOT.resolve()), 'OUTPUT_IN_SOURCE')
    require(not output.exists() and not output.is_symlink(), 'OUTPUT_EXISTS')
    try:
        fd = audit._root_fd(output.absolute().parent)
        os.close(fd)
        output.mkdir(parents=False, exist_ok=False, mode=0o700)
    except (OSError, audit.AuditRejected):
        raise ComparisonRejected('OUTPUT_UNAVAILABLE') from None
    binding = binding_for(csv_raw, parameters_raw, selected_profile)
    report = {'schema': SCHEMA, 'status': 'FAILED', 'checked': False, 'exit_code': 1,
              'error_code': 'EXECUTION_FAILED', 'evidence_role': evidence_role, **FLAGS,
              'binding': binding, 'profile': selected_profile, 'inputs': {},
              'roles': {role: empty_role() for role in ROLE_IDS}, 'summary': None, 'comparison': None}
    store = ArtifactStore(output / 'artifacts')
    csv_ref = store.put_bytes(csv_raw, mime_type='text/csv', producer=SCHEMA, task_id='input')
    parameters_ref = store.put_bytes(parameters_raw, mime_type='application/json', producer=SCHEMA, task_id='parameters')
    report['inputs'] = {'csv': asdict(csv_ref), 'parameters': asdict(parameters_ref)}
    refs = {role: [] for role in ROLE_IDS}
    calls = {role: [] for role in ROLE_IDS}
    runtime = ToolRuntime()
    grants = PERMISSIONS if grants is None else grants

    def read_csv():
        return read_artifact(store, csv_ref, mime='text/csv', task='input')

    def read_parameters():
        return read_artifact(store, parameters_ref, mime='application/json', task='parameters')

    def parameter_sources():
        return (parameters_ref.artifact_id,)

    def analysis_sources():
        return (csv_ref.artifact_id, parameters_ref.artifact_id, refs['parameter'][0].artifact_id)

    def verifier_sources():
        return (*analysis_sources(), refs['analysis'][0].artifact_id)

    def result_value(role, sources):
        return decode(read_artifact(store, refs[role][0], mime='application/json', task=role, sources=sources))

    def persist(role, value, sources):
        require(len(encoded(value)) <= MAX_BYTES, 'REPORT_TOO_LARGE')
        ref = store.put_json(value, producer=SCHEMA, task_id=role, source_refs=sources)
        refs[role].append(ref)
        return ref

    def parameter_handler(_):
        calls['parameter'].append(1)
        resolution = parameter_readiness(decode(read_parameters()))
        return persist('parameter', {'binding': binding, 'resolution': resolution}, parameter_sources())

    def analysis_handler(_):
        calls['analysis'].append(1)
        data = read_csv()
        resolution = result_value('parameter', parameter_sources())['resolution']
        with localcontext() as context:
            context.prec = 50
            observed = summarize(data)
        return persist('analysis', {'binding': binding, 'summary': observed,
            'comparison': produce_comparison(data, resolution)}, analysis_sources())

    def verifier_handler(_):
        calls['verifier'].append(1)
        try:
            check_candidate(read_csv(), read_parameters(), result_value('parameter', parameter_sources()),
                            result_value('analysis', analysis_sources()), binding)
            accepted, code = True, None
        except ComparisonRejected as exc:
            accepted, code = False, exc.code
        return persist('verifier', {'binding': binding, 'accepted': accepted, 'error_code': code,
            'parameter_result_sha256': refs['parameter'][0].sha256,
            'analysis_result_sha256': refs['analysis'][0].sha256}, verifier_sources())

    def structural_valid(role, ref, sources):
        try:
            require(ref == refs[role][0], 'INVALID_ARTIFACT')
            value = result_value(role, sources())
            return same(value['binding'], binding) and (role != 'verifier' or
                (value['accepted'] is True and value['error_code'] is None))
        except (ComparisonRejected, KeyError, IndexError, TypeError):
            return False

    runtime.register(role_spec('parameter', lambda ref: structural_valid('parameter', ref, parameter_sources)), parameter_handler)
    runtime.register(role_spec('analysis', lambda ref: structural_valid('analysis', ref, analysis_sources)), analysis_handler)
    runtime.register(role_spec('verifier', lambda ref: structural_valid('verifier', ref, verifier_sources)), verifier_handler)
    def mark_dispatch(role):
        report['roles'][role].update(status='DISPATCH_ERROR', attempts=1, error_code='EXECUTION_FAILED')

    try:
        mark_dispatch('parameter')
        returned, receipt = runtime.execute('comparison-parameter', {'parameters_sha256': parameters_ref.sha256},
            granted_permissions=grants.get('parameter', frozenset()), attempt_limit=1)
        report['roles']['parameter'] = observe_role(receipt, returned, refs['parameter'], calls['parameter'])
        if role_ok(report['roles']['parameter']):
            resolution = result_value('parameter', parameter_sources())['resolution']
            if resolution['readiness'] != 'READY':
                require(resolution['readiness'] in ('BLOCKED_UNKNOWN', 'BLOCKED_CONFLICT', 'BLOCKED_INVALID'),
                        'PARAMETER_MISMATCH')
                report.update(status='BLOCKED', exit_code=2, error_code=resolution['readiness'])
            elif Decimal(resolution['selected_decimal']) < 0:
                report.update(status='BLOCKED', exit_code=2, error_code='NEGATIVE_TOLERANCE')
            else:
                mark_dispatch('analysis')
                returned, receipt = runtime.execute('comparison-analysis',
                    {'input_sha256': csv_ref.sha256, 'parameter_result_sha256': refs['parameter'][0].sha256},
                    granted_permissions=grants.get('analysis', frozenset()), attempt_limit=1)
                report['roles']['analysis'] = observe_role(receipt, returned, refs['analysis'], calls['analysis'])
                if role_ok(report['roles']['analysis']):
                    mark_dispatch('verifier')
                    returned, receipt = runtime.execute('comparison-verifier',
                        {'input_sha256': csv_ref.sha256, 'parameters_sha256': parameters_ref.sha256,
                         'parameter_result_sha256': refs['parameter'][0].sha256,
                         'analysis_result_sha256': refs['analysis'][0].sha256},
                        granted_permissions=grants.get('verifier', frozenset()), attempt_limit=1)
                    report['roles']['verifier'] = observe_role(receipt, returned, refs['verifier'], calls['verifier'])
                    if role_ok(report['roles']['verifier']):
                        value = result_value('analysis', analysis_sources())
                        report.update(status='CHECKED', checked=True, exit_code=0, error_code=None,
                                      summary=value['summary'], comparison=value['comparison'])
                    elif refs['verifier']:
                        verdict = result_value('verifier', verifier_sources())
                        report['error_code'] = verdict.get('error_code') or 'VERIFICATION_FAILED'
        if report['status'] == 'FAILED':
            errors = [row['error_code'] for row in report['roles'].values() if row['error_code']]
            if errors and report['error_code'] == 'EXECUTION_FAILED':
                report['error_code'] = errors[-1]
            if report['error_code'] == 'PERMISSION_DENIED':
                report.update(status='BLOCKED', exit_code=2)
    except ComparisonRejected as exc:
        report.update(status='FAILED', checked=False, exit_code=1, error_code=exc.code)
    except (OSError, ValueError, TypeError, KeyError, IndexError):
        report.update(status='FAILED', checked=False, exit_code=1, error_code='EXECUTION_FAILED')
    # Saved role observations are not proof of native termination. On uncertainty
    # stop dispatch; late effects can remain. No retries, cleanup or recovery.
    for role in ROLE_IDS:
        if report['roles'][role]['status'] == 'DISPATCH_ERROR':
            report['roles'][role].update(handler_calls=len(calls[role]),
                result_ref=asdict(refs[role][0]) if refs[role] else None,
                retained_unaccepted_result=bool(refs[role]))
    require(report['error_code'] is None or report['error_code'] in ERROR_CODES, 'INVALID_REPORT')
    if not report['checked'] and refs['analysis']:
        report['roles']['analysis']['retained_unaccepted_result'] = True
    receipt = write_report(output, report)
    return receipt


def verify(output, *, report_sha256, input_sha256, parameters_sha256, profile_sha256):
    for pin in (report_sha256, input_sha256, parameters_sha256, profile_sha256):
        require(type(pin) is str and re.fullmatch(r'[0-9a-f]{64}', pin) is not None, 'INVALID_PIN')
    raw = read_local(Path(output) / 'report.json')
    require(sha(raw) == report_sha256, 'REPORT_PIN_MISMATCH')
    report = decode(raw)
    require(type(report) is dict and set(report) == {'schema', 'status', 'checked', 'exit_code', 'error_code',
            'evidence_role', *FLAGS, 'binding', 'profile', 'inputs', 'roles', 'summary', 'comparison'}, 'INVALID_REPORT')
    selected_profile = profile(report['evidence_role'])
    require(sha(encoded(selected_profile)) == profile_sha256 and same(report['profile'], selected_profile), 'PROFILE_PIN_MISMATCH')
    require(report['schema'] == SCHEMA and report['status'] == 'CHECKED' and report['checked'] is True
            and type(report['exit_code']) is int and report['exit_code'] == 0 and report['error_code'] is None
            and same({key: report[key] for key in FLAGS}, FLAGS), 'UNACCEPTED_REPORT')
    require(type(report['inputs']) is dict and set(report['inputs']) == {'csv', 'parameters'}
            and type(report['roles']) is dict and set(report['roles']) == set(ROLE_IDS), 'INVALID_REPORT')
    store = ArtifactStore(Path(output) / 'artifacts', read_only=True)
    csv_ref, parameters_ref = (as_ref(report['inputs'][key]) for key in ('csv', 'parameters'))
    csv_raw = read_artifact(store, csv_ref, mime='text/csv', task='input')
    parameters_raw = read_artifact(store, parameters_ref, mime='application/json', task='parameters')
    require(sha(csv_raw) == input_sha256 and sha(parameters_raw) == parameters_sha256, 'INPUT_PIN_MISMATCH')
    binding = binding_for(csv_raw, parameters_raw, selected_profile)
    require(same(report['binding'], binding), 'BINDING_MISMATCH')
    if report['evidence_role'] == 'synthetic':
        expected_csv, expected_parameters = demo_inputs()
        require(csv_raw == expected_csv and parameters_raw == expected_parameters, 'DEMO_INPUT_MISMATCH')
    refs, values = {}, {}
    for role in ROLE_IDS:
        row = report['roles'][role]
        require(type(row) is dict and set(row) == set(empty_role()) and role_ok(row)
                and type(row['attempts']) is int and type(row['handler_calls']) is int
                and row['error_code'] is None and row['retained_unaccepted_result'] is False,
                'UNACCEPTED_REPORT')
        refs[role] = as_ref(row['result_ref'])
        sources = ((parameters_ref.artifact_id,) if role == 'parameter' else
                   (csv_ref.artifact_id, parameters_ref.artifact_id, refs['parameter'].artifact_id)
                   + ((refs['analysis'].artifact_id,) if role == 'verifier' else ()))
        values[role] = decode(read_artifact(store, refs[role], mime='application/json', task=role, sources=sources))
        payload = ({'parameters_sha256': parameters_sha256} if role == 'parameter' else
                   {'input_sha256': input_sha256, 'parameter_result_sha256': refs['parameter'].sha256})
        if role == 'verifier':
            payload.update(parameters_sha256=parameters_sha256, analysis_result_sha256=refs['analysis'].sha256)
        require(row['input_hash'] == ToolRuntime._hash_json(payload)
                and row['output_hash'] == ToolRuntime._hash_json(refs[role]), 'BINDING_MISMATCH')
    comparison = check_candidate(csv_raw, parameters_raw, values['parameter'], values['analysis'], binding)
    require(same(values['verifier'], {'binding': binding, 'accepted': True, 'error_code': None,
                'parameter_result_sha256': refs['parameter'].sha256,
                'analysis_result_sha256': refs['analysis'].sha256})
            and same(report['summary'], values['analysis']['summary'])
            and same(report['comparison'], comparison), 'VERIFICATION_FAILED')
    require(read_local(Path(output) / 'summary.txt', MAX_TEXT_BYTES) == summary_text(report).encode(), 'INVALID_REPORT')
    return {'verification_passed': True, 'execution_restarted': False,
            'within_tolerance': comparison['within_tolerance'], 'absolute_mean_difference': comparison['absolute_mean_difference'],
            'report_sha256': report_sha256, 'profile_sha256': profile_sha256, **FLAGS}


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's ordinary message can include caller-supplied paths/tokens.
        raise ComparisonRejected('INVALID_ARGUMENTS')


def main(argv=None):
    try:
        parser = SafeParser(description=__doc__)
        commands = parser.add_subparsers(dest='command', required=True, parser_class=SafeParser)
        run = commands.add_parser('run')
        run.add_argument('--output', required=True, type=Path)
        run.add_argument('--demo', action='store_true')
        run.add_argument('--input', type=Path)
        run.add_argument('--parameters', type=Path)
        check = commands.add_parser('verify')
        check.add_argument('--output', required=True, type=Path)
        for name in ('report-sha256', 'input-sha256', 'parameters-sha256', 'profile-sha256'):
            check.add_argument('--' + name, required=True)
        args = parser.parse_args(argv)
        if args.command == 'run':
            require((args.demo and args.input is None and args.parameters is None)
                    or (not args.demo and args.input is not None and args.parameters is not None), 'INVALID_ARGUMENTS')
            csv_raw, parameters_raw = demo_inputs() if args.demo else (read_local(args.input), read_local(args.parameters))
            result = run_comparison(args.output, csv_raw, parameters_raw,
                                    evidence_role='synthetic' if args.demo else 'user_supplied_unvalidated')
            print(read_local(args.output / 'summary.txt', MAX_TEXT_BYTES).decode(), file=sys.stderr, end='')
            exit_code = result['exit_code']
        else:
            result = verify(args.output, report_sha256=args.report_sha256, input_sha256=args.input_sha256,
                            parameters_sha256=args.parameters_sha256, profile_sha256=args.profile_sha256)
            exit_code = 0
    except ComparisonRejected as exc:
        failed = 'args' in locals() and args.command == 'verify'
        result = {'status': 'FAILED' if failed else 'REFUSED', 'checked': False,
                  'error_code': exc.code, 'exit_code': 1 if failed else 2, **FLAGS}
        exit_code = result['exit_code']
    except (OSError, ValueError, TypeError, KeyError, IndexError):
        result = {'status': 'FAILED', 'checked': False, 'error_code': 'OUTPUT_IO_ERROR', 'exit_code': 1, **FLAGS}
        exit_code = 1
    print(encoded(result).decode())
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
