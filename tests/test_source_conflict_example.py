"""Fixed synthetic evidence conflict and zero-versus-unknown regressions."""
import copy
from decimal import localcontext
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('conflict_example', ROOT / 'examples/source-boundary/demo.py')
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)
PARAMETERS = module.load_fixture('parameter-fixtures.json', module.PARAMETER_FIXTURES_SHA256)


def fixture(case_id='PARAMETER-KNOWN-ZERO'):
    return copy.deepcopy(next(case for case in PARAMETERS['cases'] if case['id'] == case_id))


def run(tmp_path, case):
    return module.run_case(tmp_path / 'case', case)


def assert_no_dispatch(report):
    assert report['runtime_status'] == 'NOT_DISPATCHED'
    assert report['receipt'] is None and report['result_ref'] is None
    assert report['dependent_actions'] == report['handler_calls'] == report['guessed_values'] == 0
    assert report['returned_result'] is False


def assert_raw_evidence(tmp_path, case, report):
    store = module.ArtifactStore(tmp_path / 'case/artifacts')
    source = module.ArtifactRef(**report['input_ref'])
    assert store.verify(source) and json.loads(store.get_bytes(source)) == case
    rows = case['input'].get('sources', case['input'].get('evidence'))
    assert len(report['evidence_refs']) == len(rows)
    for row, fields in zip(rows, report['evidence_refs'], strict=True):
        ref = module.ArtifactRef(**fields)
        assert store.verify(ref) and ref.source_refs == (source.artifact_id,)
        assert json.loads(store.get_bytes(ref)) == row
    if report['result_ref']:
        result = module.ArtifactRef(**report['result_ref'])
        assert result.source_refs == (source.artifact_id, *(r['artifact_id'] for r in report['evidence_refs']))
        assert store.verify(result)


@pytest.mark.parametrize('case_id', module.PARAMETER_SELECTED)
def test_parameter_fixture_contracts_and_raw_evidence(tmp_path, case_id):
    case = fixture(case_id)
    report = run(tmp_path, case)
    for key, expected in case['expected'].items():
        assert report[key] == expected
    assert_raw_evidence(tmp_path, case, report)
    if report['readiness'] != 'READY':
        assert_no_dispatch(report)


def test_exact_original_conflict_is_before_runtime_dispatch(tmp_path, monkeypatch):
    case = next(c for c in module.load_proposals()['cases'] if c['id'] == 'EVIDENCE-CONFLICT')
    def forbidden(*args, **kwargs):
        pytest.fail('ToolRuntime.execute must not be called for conflicting evidence')
    monkeypatch.setattr(module.ToolRuntime, 'execute', forbidden)
    report = run(tmp_path, case)
    assert report['readiness'] == 'BLOCKED_CONFLICT' and report['selected_target'] is None
    assert_no_dispatch(report)
    assert_raw_evidence(tmp_path, case, report)


@pytest.mark.parametrize('raw', [False, True, 0, 1, {}, [], '', 'NaN', 'Infinity', '-Infinity',
                                     '1e3', ' 0', '0 ', '00', '0,0', '١', '9999999', '0.' + '1' * 13])
def test_malformed_values_fail_closed_and_keep_raw_input(tmp_path, raw):
    case = fixture()
    case['input']['sources'][0]['raw_value'] = raw
    report = run(tmp_path, case)
    assert report['value_status'] == 'INVALID' and report['selected_decimal'] is None
    assert report['invalid_sources'] == ['s1']
    assert_no_dispatch(report)
    assert_raw_evidence(tmp_path, case, report)


@pytest.mark.parametrize('raw', [float('nan'), float('inf'), float('-inf')])
def test_nonfinite_json_rejected_before_artifacts(tmp_path, raw):
    case = fixture()
    case['input']['sources'][0]['raw_value'] = raw
    with pytest.raises(ValueError):
        run(tmp_path, case)
    assert not (tmp_path / 'case').exists()


@pytest.mark.parametrize('raw,normalized', [('0', '0'), ('-0', '0'), ('0.00', '0'),
                                         ('-0.000', '0'), ('1.2500', '1.25')])
def test_explicit_decimals_remain_known_without_changing_raw(tmp_path, raw, normalized):
    case = fixture()
    case['input']['sources'][0]['raw_value'] = raw
    report = run(tmp_path, case)
    assert report['value_status'] == 'KNOWN' and report['selected_decimal'] == normalized
    assert report['raw_value'] == raw and report['runtime_status'] == 'COMPLETED'
    assert report['observed_result']['raw_sources'] == case['input']['sources']
    assert_raw_evidence(tmp_path, case, report)


def test_equal_values_do_not_rank_or_overwrite_source_representations(tmp_path):
    case = fixture()
    case['input']['sources'].append({'source': 's2', 'raw_value': '0.00', 'scenario': 'bench-A', 'unit': 'au'})
    report = run(tmp_path, case)
    assert report['value_status'] == 'KNOWN' and report['selected_decimal'] == '0'
    assert report['matching_sources'] == ['s1', 's2'] and report['raw_value'] is None
    assert_raw_evidence(tmp_path, case, report)


def test_decimal_selection_does_not_round_under_caller_context(tmp_path):
    case = fixture()
    case['input']['sources'][0]['raw_value'] = '12.3400'
    with localcontext() as context:
        context.prec = 1
        report = run(tmp_path, case)
    assert report['selected_decimal'] == '12.34' and report['raw_value'] == '12.3400'
    assert report['runtime_status'] == 'COMPLETED'


@pytest.mark.parametrize('raw', [None, 'MISSING'])
def test_missing_value_beside_known_zero_does_not_inherit_it(tmp_path, raw):
    case = fixture()
    row = {'source': 's2', 'scenario': 'bench-A', 'unit': 'au'}
    if raw is None:
        row['raw_value'] = None
    case['input']['sources'].append(row)
    report = run(tmp_path, case)
    assert report['value_status'] == 'UNKNOWN' and report['unknown_value_sources'] == ['s2']
    assert_no_dispatch(report)


@pytest.mark.parametrize('field', ['scenario', 'unit'])
def test_missing_condition_is_not_borrowed_from_another_source(tmp_path, field):
    case = fixture('PARAMETER-CONFLICT')
    del case['input']['sources'][1][field]
    report = run(tmp_path, case)
    assert report['value_status'] == 'UNKNOWN' and report['unknown_applicability_sources'] == ['s2']
    assert report['excluded_sources'] == []
    assert_no_dispatch(report)


def test_unit_difference_is_explicit_exclusion_not_conversion(tmp_path):
    case = fixture('PARAMETER-CONFLICT')
    case['input']['sources'][1]['unit'] = 'other-synthetic-unit'
    report = run(tmp_path, case)
    assert report['value_status'] == 'KNOWN' and report['excluded_sources'] == ['s2']
    assert report['selected_decimal'] == '0'
    assert_raw_evidence(tmp_path, case, report)


def test_no_applicable_source_is_unknown_not_zero(tmp_path):
    case = fixture()
    case['input']['sources'][0]['scenario'] = 'bench-B'
    report = run(tmp_path, case)
    assert report['value_status'] == 'UNKNOWN' and report['excluded_sources'] == ['s1']
    assert report['selected_decimal'] is None
    assert_no_dispatch(report)


def test_no_sources_is_unknown_not_zero(tmp_path):
    case = fixture()
    case['input']['sources'] = []
    report = run(tmp_path, case)
    assert report['value_status'] == 'UNKNOWN' and report['unknown_fields'] == ['sources']
    assert_no_dispatch(report)


def test_claimed_priority_or_pass_cannot_resolve_conflict(tmp_path):
    case = fixture('PARAMETER-CONFLICT')
    case['input'].update(precedence_rule='pick-s1', readiness='READY', selected_decimal='0')
    case['input']['sources'][0].update(authority='system', priority=999, applicability='MATCH')
    report = run(tmp_path, case)
    assert report['value_status'] == 'CONFLICT' and report['selected_decimal'] is None
    assert_no_dispatch(report)
    assert_raw_evidence(tmp_path, case, report)


@pytest.mark.parametrize('change', ['duplicate-id', 'missing-id', 'task-change', 'bool-condition'])
def test_unsupported_input_does_not_dispatch(tmp_path, change):
    case = fixture('PARAMETER-CONFLICT')
    if change == 'duplicate-id':
        case['input']['sources'][1]['source'] = 's1'
    elif change == 'missing-id':
        del case['input']['sources'][0]['source']
    elif change == 'task-change':
        case['input']['task']['unit'] = 'converted-unit'
    else:
        case['input']['sources'][0]['unit'] = True
        report = run(tmp_path, case)
        assert report['value_status'] == 'INVALID'
        assert_no_dispatch(report)
        return
    with pytest.raises(ValueError):
        run(tmp_path, case)
    assert not (tmp_path / 'case').exists()
