"""Explicit portable public-synthetic contract tests; no native/service discovery."""
import copy
from fractions import Fraction
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from opendot_engineering.core import ArtifactRef, ArtifactStore
from opendot_engineering.tool_runtime import ToolCallReceipt, ToolRuntime

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'examples/measurement-review/compare.py'
SPEC = importlib.util.spec_from_file_location('measurement_comparison_example', SCRIPT)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)
FIXTURES = json.loads((SCRIPT.parent / 'comparison-fixtures.json').read_bytes())
DATA = (SCRIPT.parent / 'batch.csv').read_bytes()
PARAMETERS = m.encoded(FIXTURES['demo_parameters'])
PINS = ('report_sha256', 'input_sha256', 'parameters_sha256', 'profile_sha256')


def params(tolerance='2'):
    value = copy.deepcopy(FIXTURES['demo_parameters'])
    for row in value['sources']:
        row['raw_value'] = tolerance
    return m.encoded(value)


def csv_bytes(case):
    return ('condition,replicate,value,unit\n' + ''.join(
        f'{c},{index},{value},au\n' for c in ('A', 'B') for index, value in enumerate(case[c], 1))).encode()


def run(tmp_path, data=DATA, parameters=PARAMETERS, **kwargs):
    output = tmp_path / 'case'
    receipt = m.run_comparison(output, data, parameters, **kwargs)
    return output, receipt, json.loads((output / 'report.json').read_bytes())


def verify(output, receipt):
    return m.verify(output, **{key: receipt[key] for key in PINS})


def snapshot(path):
    return {str(p.relative_to(path)): (p.stat().st_mode, p.read_bytes() if p.is_file() else None)
            for p in [path, *sorted(path.rglob('*'))]}


def reseal(output, receipt, report):
    raw = m.encoded(report)
    (output / 'report.json').write_bytes(raw)
    (output / 'summary.txt').write_text(m.summary_text(report))
    return {**receipt, 'report_sha256': m.sha(raw)}


@pytest.mark.parametrize('case', FIXTURES['cases'], ids=lambda case: case['id'])
def test_frozen_fraction_oracles(tmp_path, case):
    output, receipt, report = run(tmp_path, csv_bytes(case), params(case['tolerance']))
    assert receipt['status'] == 'CHECKED' and receipt['exit_code'] == 0
    assert report['comparison']['absolute_mean_difference'] == case['difference']
    assert report['comparison']['within_tolerance'] is case['within_tolerance']
    for condition in ('A', 'B'):
        for field, expected in (('sum', case['sums'][condition]), ('mean', case['means'][condition])):
            exact = Fraction(expected['numerator'], expected['denominator'])
            observed = report['summary']['conditions'][condition][field]
            assert type(observed) is float
            assert abs(Fraction.from_float(observed) - exact) <= max(Fraction(1, 10**12), abs(exact) / 10**15)
    assert verify(output, receipt)['verification_passed'] is True
    assert all(row['attempts'] == row['handler_calls'] == 1 for row in report['roles'].values())


def test_demo_and_supplied_mode_are_distinct(tmp_path):
    demo = tmp_path / 'demo'
    supplied = tmp_path / 'supplied'
    receipt = m.run_comparison(demo, DATA, PARAMETERS, evidence_role='synthetic')
    other = m.run_comparison(supplied, DATA, PARAMETERS)
    assert receipt['profile_sha256'] != other['profile_sha256']
    assert json.loads((demo / 'report.json').read_bytes())['evidence_role'] == 'synthetic'
    assert json.loads((supplied / 'report.json').read_bytes())['evidence_role'] == 'user_supplied_unvalidated'
    assert verify(demo, receipt)['absolute_mean_difference'] == {'numerator': 2, 'denominator': 1}
    with pytest.raises(m.ComparisonRejected, match='DEMO_INPUT_MISMATCH'):
        m.run_comparison(tmp_path / 'false-demo', DATA, params('1.999'), evidence_role='synthetic')
    assert not (tmp_path / 'false-demo').exists()


@pytest.mark.parametrize('mutation,expected', [
    ('missing', 'BLOCKED_UNKNOWN'), ('null', 'BLOCKED_UNKNOWN'),
    ('conflicting', 'BLOCKED_CONFLICT'), ('unknown_applicability', 'BLOCKED_UNKNOWN'),
    ('inapplicable', 'BLOCKED_UNKNOWN'), ('negative', 'NEGATIVE_TOLERANCE'),
    ('invalid', 'BLOCKED_INVALID'),
])
def test_tolerance_blocks_dependents(tmp_path, mutation, expected):
    value = copy.deepcopy(FIXTURES['demo_parameters'])
    if mutation == 'missing':
        value['sources'] = []
    elif mutation == 'null':
        value['sources'][0]['raw_value'] = None
    elif mutation == 'conflicting':
        value['sources'][0]['raw_value'] = '3'
    elif mutation == 'unknown_applicability':
        value['sources'][0]['scenario'] = None
    elif mutation == 'inapplicable':
        for row in value['sources']:
            row['scenario'] = 'other-bench'
    elif mutation == 'negative':
        for row in value['sources']:
            row['raw_value'] = '-0.1'
    else:
        value['sources'][0]['raw_value'] = '1e3'
    output, receipt, report = run(tmp_path, parameters=m.encoded(value))
    assert receipt['status'] == 'BLOCKED' and receipt['exit_code'] == 2
    assert receipt['error_code'] == expected
    assert report['roles']['parameter']['handler_calls'] == 1
    for role in ('analysis', 'verifier'):
        assert report['roles'][role] == m.empty_role()
    with pytest.raises(m.ComparisonRejected, match='UNACCEPTED_REPORT'):
        verify(output, receipt)


def test_known_zero_and_exact_boundary(tmp_path):
    same = DATA.replace(b'B,1,2,au', b'B,1,1,au').replace(b'B,2,4,au', b'B,2,2,au').replace(b'B,3,6,au', b'B,3,3,au')
    _, receipt, report = run(tmp_path, same, params('0.000000000000'))
    assert receipt['checked'] is True and report['comparison']['within_tolerance'] is True
    assert report['comparison']['tolerance'] == {'numerator': 0, 'denominator': 1}


def test_invalid_csvs_refuse_before_any_output(tmp_path):
    variants = [
        DATA.replace(b',au', b',mm'), DATA.replace(b'A,1,1,au\n', b''),
        DATA.replace(b'A,1,1,au', b'A,2,1,au'), DATA + b'A,1,1,au\n',
        DATA.replace(b'value,unit', b'value,unit,extra'), DATA.replace(b'A,1,1,au', b'A,1,1,au,private-name'),
        DATA.replace(b'A,1,1,au', b'private-name,1,1,au'), DATA + b'\n', b'\xff', b'x' * 65537,
    ]
    for text in ('1e0', 'NaN', 'Infinity', '1000000.000000000001', '0.0000000000001', '0' * 33):
        variants.append(DATA.replace(b'A,1,1,au', f'A,1,{text},au'.encode()))
    for index, data in enumerate(variants):
        output = tmp_path / str(index)
        with pytest.raises(m.ComparisonRejected):
            m.run_comparison(output, data, PARAMETERS)
        assert not output.exists()


def test_invalid_parameter_shapes_refuse_before_output(tmp_path):
    values = [b'[]', b'{"task":{},"task":{},"sources":[]}', b'{"task":1e999,"sources":[]}', b'x' * 65537]
    for change in ('unknown_field', 'too_many', 'duplicate', 'wrong_task'):
        value = copy.deepcopy(FIXTURES['demo_parameters'])
        if change == 'unknown_field':
            value['sources'][0]['private-key'] = 'untrusted'
        elif change == 'too_many':
            value['sources'] = [{**value['sources'][0], 'source': f's{i}'} for i in range(9)]
        elif change == 'duplicate':
            value['sources'][1]['source'] = value['sources'][0]['source']
        else:
            value['task']['unit'] = 'mm'
        values.append(m.encoded(value))
    for index, data in enumerate(values):
        output = tmp_path / str(index)
        with pytest.raises(m.ComparisonRejected):
            m.run_comparison(output, DATA, data)
        assert not output.exists()


@pytest.mark.parametrize('role', ['parameter', 'analysis', 'verifier'])
def test_deny_each_role_stops_dependents(tmp_path, role):
    grants = {**m.PERMISSIONS, role: frozenset()}
    output, receipt, report = run(tmp_path, grants=grants)
    assert receipt['status'] == 'BLOCKED' and receipt['error_code'] == 'PERMISSION_DENIED'
    row = report['roles'][role]
    assert row['status'] == 'BLOCKED' and row['handler_calls'] == 0 and row['attempts'] == 1
    assert row['result_ref'] is None
    names = list(m.ROLE_IDS)
    assert all(report['roles'][later] == m.empty_role() for later in names[names.index(role) + 1:])
    with pytest.raises(m.ComparisonRejected):
        verify(output, receipt)


@pytest.mark.parametrize('role', ['parameter', 'analysis', 'verifier'])
@pytest.mark.parametrize('outcome', ['failed', 'unresolved', 'dispatch_exception'])
def test_pure_failure_fixtures_stop_without_retries(tmp_path, monkeypatch, outcome, role):
    original = ToolRuntime.execute
    seen = []
    def execute(self, tool_id, payload, **kwargs):
        seen.append(tool_id)
        if tool_id == m.ROLE_IDS[role]:
            if outcome == 'dispatch_exception':
                raise OSError('private-path-must-not-leak')
            return None, ToolCallReceipt(call_id='fixture', tool_id=tool_id, tool_version='1',
                status='FAILED', attempts=1, latency_s=0, input_hash=self._hash_json(payload),
                output_hash=None, semantic_valid=False, error_type='TimeoutError' if outcome == 'unresolved' else 'ValueError',
                execution_liveness={'reconciliation_required': outcome == 'unresolved'})
        return original(self, tool_id, payload, **kwargs)
    monkeypatch.setattr(ToolRuntime, 'execute', execute)
    output, receipt, report = run(tmp_path)
    names = list(m.ROLE_IDS)
    assert seen == [m.ROLE_IDS[name] for name in names[:names.index(role) + 1]]
    assert receipt['status'] == 'FAILED' and receipt['exit_code'] == 1
    assert report['roles'][role]['attempts'] == 1
    assert all(report['roles'][later] == m.empty_role() for later in names[names.index(role) + 1:])
    assert 'private-path' not in (output / 'report.json').read_text()
    if outcome == 'unresolved':
        assert report['roles'][role]['status'] == 'UNRESOLVED'


@pytest.mark.parametrize('mutation', ['sum', 'mean', 'exact_delta', 'false_within'])
def test_wrong_computation_retains_rejected_bytes(tmp_path, monkeypatch, mutation):
    original_producers = m.load_producers
    original_comparison = m.produce_comparison
    if mutation in ('sum', 'mean'):
        resolver, summarizer = original_producers()
        def wrong_summary(raw):
            value = summarizer(raw)
            value['conditions']['A'][mutation] += 0.0001
            return value
        monkeypatch.setattr(m, 'load_producers', lambda: (resolver, wrong_summary))
    else:
        def wrong_comparison(raw, resolution):
            value = original_comparison(raw, resolution)
            if mutation == 'exact_delta':
                value['absolute_mean_difference']['numerator'] += 1
            else:
                value['within_tolerance'] = True
            return value
        monkeypatch.setattr(m, 'produce_comparison', wrong_comparison)
    output, receipt, report = run(tmp_path, parameters=params('1.999'))
    assert receipt['status'] == 'FAILED' and receipt['error_code'] == 'NUMERIC_MISMATCH'
    assert report['roles']['analysis']['retained_unaccepted_result'] is True
    assert report['roles']['verifier']['retained_unaccepted_result'] is True
    ref = m.as_ref(report['roles']['analysis']['result_ref'])
    raw = ArtifactStore(output / 'artifacts', read_only=True).get_bytes(ref, max_bytes=m.MAX_BYTES)
    assert json.loads(raw)['summary']['rows'] == 6
    with pytest.raises(m.ComparisonRejected):
        verify(output, receipt)


def test_display_allowance_is_exact_and_observed_values_preserved(tmp_path, monkeypatch):
    resolver, summarizer = m.load_producers()
    def allowed(raw):
        result = summarizer(raw)
        result['conditions']['A']['mean'] = 2.0 + 5e-13
        return result
    monkeypatch.setattr(m, 'load_producers', lambda: (resolver, allowed))
    output, receipt, report = run(tmp_path)
    assert receipt['checked'] is True
    assert report['summary']['conditions']['A']['mean'] == 2.0 + 5e-13
    assert verify(output, receipt)['verification_passed'] is True


def test_independent_verifier_never_calls_producers_or_dispatch(tmp_path, monkeypatch):
    output, receipt, _ = run(tmp_path)
    before = snapshot(output)
    def forbidden(*args, **kwargs):
        pytest.fail('standalone verifier called a producer, dispatcher or writer')
    monkeypatch.setattr(m, 'load_producers', forbidden)
    monkeypatch.setattr(m, 'parse_csv_decimal', forbidden)
    monkeypatch.setattr(m, 'parameter_shape', forbidden)
    monkeypatch.setattr(m, 'produce_comparison', forbidden)
    monkeypatch.setattr(ToolRuntime, 'execute', forbidden)
    monkeypatch.setattr(ArtifactStore, 'put_bytes', forbidden)
    monkeypatch.setattr(ArtifactStore, 'put_json', forbidden)
    assert verify(output, receipt)['verification_passed'] is True
    for key in PINS:
        with pytest.raises(m.ComparisonRejected):
            verify(output, {**receipt, key: '0' * 64})
    assert snapshot(output) == before


def test_all_consumer_artifact_reads_bounded(tmp_path, monkeypatch):
    original = ArtifactStore.get_bytes
    bounds = []
    def bounded(self, ref, *, max_bytes=None):
        bounds.append(max_bytes)
        assert max_bytes == m.MAX_BYTES
        return original(self, ref, max_bytes=max_bytes)
    monkeypatch.setattr(ArtifactStore, 'get_bytes', bounded)
    output, receipt, _ = run(tmp_path)
    verify(output, receipt)
    assert bounds


def test_resealed_report_forgery_refuses(tmp_path):
    output, receipt, report = run(tmp_path)
    mutations = [
        ('status', 'COMPLETED'), ('checked', 1), ('scientific_accepted', True),
        ('independent_review', 'PASS'), ('evidence_role', 'synthetic'),
        ('summary', {**report['summary'], 'rows': 7}),
    ]
    for key, value in mutations:
        altered = copy.deepcopy(report)
        altered[key] = value
        changed_receipt = reseal(output, receipt, altered)
        with pytest.raises(m.ComparisonRejected):
            verify(output, changed_receipt)
    for field, value in [('attempts', True), ('handler_calls', 2), ('input_hash', '0' * 64),
                         ('returned_result', False), ('retained_unaccepted_result', True)]:
        altered = copy.deepcopy(report)
        altered['roles']['analysis'][field] = value
        with pytest.raises(m.ComparisonRejected):
            verify(output, reseal(output, receipt, altered))


def test_artifact_corruption_and_metadata_substitution(tmp_path):
    output, receipt, report = run(tmp_path)
    altered = copy.deepcopy(report)
    altered['roles']['analysis']['result_ref']['producer'] = 'other-owner'
    with pytest.raises(m.ComparisonRejected, match='INVALID_ARTIFACT'):
        verify(output, reseal(output, receipt, altered))
    reseal(output, receipt, report)
    digest = report['roles']['analysis']['result_ref']['sha256']
    path = output / 'artifacts/objects' / digest[:2] / digest[2:]
    path.chmod(0o600)
    path.write_bytes(b'corrupted')
    with pytest.raises(m.ComparisonRejected, match='ARTIFACT_INTEGRITY_FAILED'):
        verify(output, receipt)


def test_source_pin_and_canonical_owner_identity(tmp_path, monkeypatch):
    from opendot_engineering.core.artifacts import ArtifactStore as OwnerStore
    from opendot_engineering.core.contracts import ArtifactRef as OwnerRef
    assert m.ArtifactStore is OwnerStore is ArtifactStore
    assert m.ArtifactRef is OwnerRef is ArtifactRef
    assert m.ToolRuntime is ToolRuntime
    for relative, digest in m.SOURCE_PINS.items():
        assert m.sha((ROOT / relative).read_bytes()) == digest
    original = m.read_local
    def changed(path, limit=m.MAX_BYTES):
        raw = original(path, limit)
        if str(path).endswith('source-boundary/demo.py'):
            return raw + b'\n# changed\n'
        return raw
    monkeypatch.setattr(m, 'read_local', changed)
    with pytest.raises(m.ComparisonRejected, match='SOURCE_PIN_MISMATCH'):
        m.run_comparison(tmp_path / 'out', DATA, PARAMETERS)
    assert not (tmp_path / 'out').exists()


def test_output_collision_and_source_output_refusal(tmp_path):
    output, _, _ = run(tmp_path)
    before = snapshot(output)
    with pytest.raises(m.ComparisonRejected, match='OUTPUT_EXISTS'):
        m.run_comparison(output, DATA, PARAMETERS)
    assert snapshot(output) == before
    target = ROOT / 'forbidden-output'
    with pytest.raises(m.ComparisonRejected, match='OUTPUT_IN_SOURCE'):
        m.run_comparison(target, DATA, PARAMETERS)
    assert not target.exists()


def test_fresh_process_cli_and_no_optional_imports(tmp_path):
    output = tmp_path / 'demo'
    env = {**os.environ, 'PYTHONPATH': str(ROOT / 'src'), 'PYTHONDONTWRITEBYTECODE': '1'}
    command = [sys.executable, '-B', str(SCRIPT)]
    result = subprocess.run([*command, 'run', '--demo', '--output', str(output)],
                            env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
    receipt = json.loads(result.stdout)
    assert 'Absolute mean difference: 2/1 au' in result.stderr
    before = snapshot(output)
    args = [*command, 'verify', '--output', str(output)]
    for key in PINS:
        args += ['--' + key.replace('_', '-'), receipt[key]]
    result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)['verification_passed'] is True
    assert snapshot(output) == before
    code = ('import importlib.util,sys; s=importlib.util.spec_from_file_location("comparison",sys.argv[1]); '
            'm=importlib.util.module_from_spec(s); s.loader.exec_module(m); m.demo_inputs(); '
            'print([x for x in sys.modules if x.split(".")[0] in '
            '{"temporalio","bluesky","ophyd","numpy","openai","anthropic"}])')
    check = subprocess.run([sys.executable, '-B', '-c', code, str(SCRIPT)],
                           env=env, capture_output=True, text=True, timeout=10)
    assert check.returncode == 0 and check.stdout.strip() == '[]'


def test_cli_errors_omit_paths_and_arbitrary_tokens(tmp_path):
    command = [sys.executable, '-B', str(SCRIPT)]
    env = {**os.environ, 'PYTHONPATH': str(ROOT / 'src'), 'PYTHONDONTWRITEBYTECODE': '1'}
    for args in (['run', '--demo', '--output', str(tmp_path / 'out'), '--private-secret'],
                 ['run', '--input', str(tmp_path / 'private-identity'), '--parameters', 'missing', '--output', str(tmp_path / 'out')],
                 ['private-token']):
        result = subprocess.run([*command, *args], env=env, capture_output=True, text=True, timeout=10)
        assert result.returncode == 2
        assert json.loads(result.stdout)['checked'] is False
        assert 'private-' not in result.stdout + result.stderr and str(tmp_path) not in result.stdout + result.stderr
