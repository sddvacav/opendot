"""Frozen O3 offline fixture contract, fixed before utility_report.py exists.

Protocol: two repeated task slots task-1/task-2 use the same existing batch.csv
and frozen expected-summary.json; no new measurement/task oracle is authored.
Two arms baseline/candidate, <=3 retained attempts each, one output per attempt,
<=8 effort and <=8 monetary rows per arm; every input/report <=65536 bytes and
summary <=8192 bytes. Inputs and output are public synthetic records only.

The independently pinned inventory retains admitted tasks, every attempt identity,
index, task and execution disposition, expected effort/charge IDs, and named
fixture-reviewer records binding output hash, task, decision and contract hash.
It is a synthetic retained observation source, not measured completeness proof.
A separate caller-supplied profile pin fixes rules/source; a ledger pin fixes raw
ledger bytes. Replacing/resealing report bytes never changes those trusted pins.

Both arms have two eligible/admitted rows. Matching binds task ID, input hash,
output contract hash, condition bench-A, unit au, environment fixture-local,
budget all-attempts/3/attempts, fixed cutoff and attempt/acceptance definitions,
arm version and named synthetic acceptance owner. Unknown/missing bindings are
indeterminate; nonmatching known bindings/tasks are NOT_COMPARABLE.

Attempts retain disposition COMPLETED/FAILED/BLOCKED/CANCELLED/TIMED_OUT/UNRESOLVED,
nullable diagnostic runtime_attempts/handler_calls/receipt (not trial or cost),
nullable output_json/output_sha256 and reported acceptance status. Integrity and
arm-neutral semantics are rederived against the existing frozen summary, then a
matching independent named reviewer record is required. No boolean or COMPLETED
status can accept an output. No OpenDot role receipts are required of either arm.
Each eligible task counts at most once; all attempt rows and output identities
remain retained, including duplicate output bytes and unsuccessful work.

Exactly four effort IDs: setup, execution_rework, review, elapsed. Each observation
has value_state/value/unit/evidence_role/source_ref/method_id/reason plus start,
end, person_id, covers_attempt_ids. Known finite nonnegative numeric values equal
end-start. Three human intervals are disjoint for fixture-person in person_minutes;
elapsed is a separate envelope in seconds. Setup covers all admitted tasks by the
fixed allocation rule; execution/rework and review cover every inventory attempt,
including failures/retries. Unknown/censored value/start/end remain null with a
reason. Missing rows/fields remain missing, never zero. These intervals are invented.

Charges: one setup row (no task/attempt), one all-incremental row per retained
attempt, covers declared compute/tool/storage/idle together, excluding monetized
human labor. Charge IDs/bindings must match inventory. Known amounts finite >=0,
unknown/censored null plus reason; source_ref, usage_ref, price_date required when
known. USD is fixed; other/mixed currencies are NOT_COMPARABLE, never summed across
currencies. Costs include failed/cancelled/retry attempts; zero accepted -> null
cost_per_accepted_task. This is a toy synthetic accounting boundary, not total cost.

Verdict precedence INVALID > NOT_COMPARABLE > INDETERMINATE > known strict rule:
more accepted tasks, no increased person effort, no missing required evidence.
Required charge/elapsed/reviewer uncertainty also blocks a fixture-positive claim.
Negative outcomes keep observed counters and missing paths. Malformed JSON/schema,
duplicate IDs, bool-as-number, nonfinite/negative values and interval overlap refuse.
The protocol checks only this bounded retained ledger, never general real ledgers.

All reports preserve real_comparison_status=NOT_RUN, measured_effort_status=UNKNOWN,
real_world_benefit_established=false, scientific_accepted=false,
device_control_authorized=false, independent_review=NOT_EVALUATED.
"""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'examples/measurement-review/utility_report.py'
HISTORY = ROOT / 'docs/research/delta-20261002/source-needs-delta.json'
ORACLE = ROOT / 'docs/research/oss-workflows/frozen-oracle/expected-summary.json'

# Expected controls frozen before executable implementation. Parametrizations below
# are collected pytest nodes, not inflated counts of internal assertions/subtests.
CONTROLS = {
    'drop_failed': 'INDETERMINATE', 'drop_blocked': 'INDETERMINATE',
    'drop_cancelled': 'INDETERMINATE', 'drop_timed_out': 'INDETERMINATE',
    'drop_unresolved': 'INDETERMINATE', 'missing_review': 'INDETERMINATE',
    'missing_setup': 'INDETERMINATE', 'unknown_charge': 'INDETERMINATE',
    'censored_charge': 'INDETERMINATE', 'unknown_elapsed': 'INDETERMINATE',
    'pending_review': 'INDETERMINATE', 'unreviewed': 'INDETERMINATE',
    'missing_attempt_task': 'NOT_COMPARABLE', 'wrong_input': 'NOT_COMPARABLE',
    'wrong_version': 'NOT_COMPARABLE', 'wrong_unit': 'NOT_COMPARABLE',
    'weaker_oracle': 'NOT_COMPARABLE', 'wrong_budget': 'NOT_COMPARABLE',
    'mixed_currency': 'NOT_COMPARABLE', 'wrong_mean': 'NO_FIXTURE_IMPROVEMENT',
    'duplicate_task': 'INVALID', 'duplicate_attempt': 'INVALID',
    'negative_effort': 'INVALID', 'bool_effort': 'INVALID',
    'overlap': 'INVALID', 'person_wall_mix': 'INVALID',
    'role_promotion': 'INVALID', 'forged_boolean': 'INVALID',
    'duplicate_charge': 'INVALID', 'unbacked_known': 'INVALID',
}


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


@pytest.fixture
def m():
    spec = importlib.util.spec_from_file_location('offline_utility_report', SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def fixture_inputs(m):
    """Only synthetic accounting; the original summary/oracles are read, not copied."""
    profile = m.profile()
    summary = ORACLE.read_text()
    output_hash = m.sha(summary.encode())
    ledger = {'schema': 'o3.synthetic-ledger.v1', 'evidence_role': 'synthetic', 'arms': {}}
    inventory = {'schema': 'o3.synthetic-inventory.v1', 'evidence_role': 'synthetic', 'arms': {}}
    for arm in ('baseline', 'candidate'):
        tasks = [dict(task_id=t, input_sha256=profile['input_sha256'],
                      required_output_contract_sha256=profile['oracle_sha256'],
                      condition='bench-A', unit='au', eligible=True, admitted=True)
                 for t in ('task-1', 'task-2')]
        attempts = []
        retained = []
        for i, task in enumerate(('task-1',) if arm == 'baseline' else ('task-1', 'task-2'), 1):
            identity = f'{arm}-{i}'
            attempts.append(dict(attempt_id=identity, task_id=task, attempt_index=i,
                disposition='COMPLETED', runtime_receipt_ref=None, runtime_attempts=None,
                handler_calls=None, output_json=summary, output_sha256=output_hash,
                acceptance_status='ACCEPTED'))
            retained.append(dict(attempt_id=identity, task_id=task, attempt_index=i,
                disposition='COMPLETED', review=dict(reviewer_id='fixture-reviewer',
                task_id=task, output_sha256=output_hash, decision='ACCEPTED',
                required_output_contract_sha256=profile['oracle_sha256'],
                source_ref=f'review-{identity}', evidence_role='synthetic')))
        ids = [a['attempt_id'] for a in attempts]
        efforts = []
        for field, start, end in [('setup',0,2), ('execution_rework',2,8), ('review',8,10), ('elapsed',0,600)]:
            efforts.append(dict(effort_id=field, value_state='known', value=end-start,
                unit='seconds' if field=='elapsed' else 'person_minutes', evidence_role='synthetic',
                source_ref=f'{arm}-{field}', method_id='synthetic-interval/v1', reason=None,
                start=start, end=end, person_id=None if field=='elapsed' else 'fixture-person',
                covers_attempt_ids=list(ids) if field!='setup' else []))
        charges = [dict(charge_id='setup', task_id=None, attempt_id=None, category='setup',
            amount=2, currency='USD', value_state='known', source_ref=f'{arm}-setup-charge',
            usage_ref='invented-usage', price_date='2026-10-02', reason=None, evidence_role='synthetic')]
        charges += [dict(charge_id=a['attempt_id'], task_id=a['task_id'], attempt_id=a['attempt_id'],
            category='all-incremental', amount=1, currency='USD', value_state='known',
            source_ref=f"charge-{a['attempt_id']}", usage_ref='invented-usage',
            price_date='2026-10-02', reason=None, evidence_role='synthetic') for a in attempts]
        ledger['arms'][arm] = dict(binding=copy.deepcopy(profile['bindings'][arm]), tasks=tasks,
                                  attempts=attempts, efforts=efforts, charges=charges)
        inventory['arms'][arm] = dict(task_ids=['task-1','task-2'], attempts=retained,
                                     effort_ids=['setup','execution_rework','review','elapsed'],
                                     charge_ids=['setup', *ids])
    return ledger, inventory


def evaluate(m, ledger, inventory):
    raw, observed = encoded(ledger), encoded(inventory)
    return m.report(raw, observed, ledger_sha256=m.sha(raw), inventory_sha256=m.sha(observed),
                    profile_sha256=m.sha(m.encoded(m.profile())))


def unknown(row, field='value', state='unknown'):
    row.update(value_state=state, reason='synthetic missing observation')
    row[field] = None
    if field == 'value':
        row['start'] = row['end'] = None


@pytest.mark.parametrize('case', json.loads(HISTORY.read_bytes())['oracles'][2]['cases'],
                         ids=lambda c: c['case_id'])
def test_original_four_records(m, case):
    results = m.historical_report()['historical_cases']
    result = next(r for r in results if r['case_id'] == case['case_id'])
    for key, value in case['expected_not_observed'].items():
        assert result[key] == value
    assert result['original_status'] == 'NOT_RUN'
    assert result['measured_effort_status'] == 'UNKNOWN'
    if 'baseline' in case['fixture']:
        assert result['fixture_effort_units']['baseline'] == case['fixture']['baseline']['total_effort']


def test_positive_is_only_synthetic_consistency(m):
    ledger, inventory = fixture_inputs(m)
    report = evaluate(m, ledger, inventory)
    assert report['utility_verdict'] == 'FIXTURE_IMPROVEMENT'
    assert report['arms']['candidate']['accepted_task_count'] == 2
    assert report['arms']['baseline']['accepted_task_count'] == 1
    assert report['arms']['candidate']['total_person_minutes'] == 10
    assert report['arms']['candidate']['elapsed_seconds'] == 600
    assert report['arms']['candidate']['money_by_currency']['USD']['total'] == 4
    assert report['real_comparison_status'] == 'NOT_RUN'
    assert report['measured_effort_status'] == 'UNKNOWN'
    assert report['real_world_benefit_established'] is False
    assert report['scientific_accepted'] is report['device_control_authorized'] is False
    assert report['independent_review'] == 'NOT_EVALUATED'
    assert len(m.encoded(report)) <= 65536 and len(m.summary_text(report).encode()) <= 8192


@pytest.mark.parametrize('control,expected', CONTROLS.items(), ids=CONTROLS)
def test_frozen_negative_controls(m, control, expected):
    ledger, inventory = fixture_inputs(m)
    arm, retained = ledger['arms']['candidate'], inventory['arms']['candidate']
    if control.startswith('drop_'):
        disposition = control.removeprefix('drop_').upper()
        retained['attempts'][-1]['disposition'] = disposition
        arm['attempts'].pop()
    elif control in ('missing_review', 'missing_setup'):
        arm['efforts'] = [r for r in arm['efforts'] if r['effort_id'] != control.removeprefix('missing_')]
    elif control in ('unknown_charge', 'censored_charge'):
        unknown(arm['charges'][-1], 'amount', control.split('_')[0])
    elif control == 'unknown_elapsed': unknown(arm['efforts'][-1])
    elif control in ('pending_review', 'unreviewed'):
        status = 'DECISION_PENDING' if control == 'pending_review' else 'UNREVIEWED'
        arm['attempts'][-1]['acceptance_status'] = status
        retained['attempts'][-1]['review']['decision'] = status
    elif control == 'missing_attempt_task': arm['tasks'].pop()
    elif control == 'wrong_input': arm['tasks'][-1]['input_sha256'] = '0'*64
    elif control == 'wrong_version': arm['binding']['version'] = 'other-v1'
    elif control == 'wrong_unit': arm['tasks'][-1]['unit'] = 'mm'
    elif control == 'weaker_oracle': arm['tasks'][-1]['required_output_contract_sha256'] = '0'*64
    elif control == 'wrong_budget': arm['binding']['budget_limit'] = 4
    elif control == 'mixed_currency': arm['charges'][-1]['currency'] = 'EUR'
    elif control == 'wrong_mean':
        value = json.loads(arm['attempts'][-1]['output_json']);value['conditions']['A']['mean'] = 3
        arm['attempts'][-1]['output_json'] = encoded(value).decode()
        arm['attempts'][-1]['output_sha256'] = m.sha(encoded(value))
        retained['attempts'][-1]['review']['output_sha256'] = m.sha(encoded(value))
    elif control == 'duplicate_task': arm['tasks'][-1] = copy.deepcopy(arm['tasks'][0])
    elif control == 'duplicate_attempt': arm['attempts'][-1] = copy.deepcopy(arm['attempts'][0])
    elif control == 'negative_effort': arm['efforts'][0]['value'] = -1
    elif control == 'bool_effort': arm['efforts'][0]['value'] = True
    elif control == 'overlap': arm['efforts'][2].update(start=7,end=9)
    elif control == 'person_wall_mix': arm['efforts'][0]['unit'] = 'seconds'
    elif control == 'role_promotion': arm['efforts'][0]['evidence_role'] = 'measured'
    elif control == 'forged_boolean': arm['attempts'][-1]['accepted'] = True
    elif control == 'duplicate_charge': arm['charges'][-1] = copy.deepcopy(arm['charges'][0])
    elif control == 'unbacked_known': arm['efforts'][0]['value'] = None
    report = evaluate(m, ledger, inventory)
    assert report['utility_verdict'] == expected
    assert report['real_world_benefit_established'] is False


def test_three_outputs_same_task_keep_all_work(m):
    ledger, inventory = fixture_inputs(m)
    arm, retained = ledger['arms']['candidate'], inventory['arms']['candidate']
    arm['attempts'][-1]['task_id'] = retained['attempts'][-1]['task_id'] = 'task-1'
    retained['attempts'][-1]['review']['task_id'] = 'task-1'
    arm['charges'][-1]['task_id'] = 'task-1'
    third = copy.deepcopy(arm['attempts'][-1]); third.update(attempt_id='candidate-3',attempt_index=3)
    arm['attempts'].append(third)
    observed = copy.deepcopy(retained['attempts'][-1]); observed.update(attempt_id='candidate-3',attempt_index=3)
    retained['attempts'].append(observed)
    charge = copy.deepcopy(arm['charges'][-1]);charge.update(charge_id='candidate-3',attempt_id='candidate-3')
    arm['charges'].append(charge);retained['charge_ids'].append('candidate-3')
    for row in arm['efforts'][1:]: row['covers_attempt_ids'].append('candidate-3')
    result = evaluate(m, ledger, inventory)['arms']['candidate']
    assert result['attempt_count'] == 3 and result['accepted_task_count'] == 1
    assert result['accepted_per_attempt'] == {'numerator':1,'denominator':3}
    assert result['accepted_per_admitted'] == {'numerator':1,'denominator':2}
    assert len(result['attempts']) == 3 and result['money_by_currency']['USD']['total'] == 5


def test_zero_accepted_retains_cost_and_null_ratio(m):
    ledger, inventory = fixture_inputs(m)
    for arm in ('baseline','candidate'):
        for row in ledger['arms'][arm]['attempts']: row['acceptance_status'] = 'REJECTED'
        for row in inventory['arms'][arm]['attempts']: row['review']['decision'] = 'REJECTED'
    report = evaluate(m,ledger,inventory)
    assert report['utility_verdict'] == 'NO_FIXTURE_IMPROVEMENT'
    for result in report['arms'].values():
        assert result['accepted_task_count'] == 0
        assert result['money_by_currency']['USD']['total'] > 0
        assert result['money_by_currency']['USD']['cost_per_accepted_task'] is None


@pytest.mark.parametrize('raw',[b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":1e999}',b' '*65537],
                         ids=['duplicate-keys','nan','overflow','oversize'])
def test_strict_json_boundary(m, raw):
    with pytest.raises(ValueError): m.decode(raw)


def test_independent_pins_reject_resealed_inputs_or_report(m):
    ledger, inventory = fixture_inputs(m)
    raw, observed = encoded(ledger), encoded(inventory)
    pins = dict(ledger_sha256=m.sha(raw), inventory_sha256=m.sha(observed),
                profile_sha256=m.sha(m.encoded(m.profile())))
    report = m.report(raw,observed,**pins)
    ledger['arms']['candidate']['efforts'][0]['evidence_role'] = 'measured'
    with pytest.raises(ValueError): m.report(encoded(ledger),observed,**pins)
    with pytest.raises(ValueError): m.report(raw,observed,**{**pins,'profile_sha256':'0'*64})
    report['real_world_benefit_established'] = True
    resealed = m.encoded(report)
    with pytest.raises(ValueError):
        m.verify_report(resealed,raw,observed,report_sha256=m.sha(resealed),**pins)


def test_no_dispatch_writes_network_or_input_mutation(m, monkeypatch, tmp_path):
    import os
    import socket
    import subprocess
    from opendot_engineering.core import ArtifactStore
    from opendot_engineering.tool_runtime import ToolRuntime
    def trap(*args, **kwargs): raise AssertionError('forbidden entrypoint')
    for owner, name in ((ToolRuntime,'execute'),(ArtifactStore,'put_bytes'),
                        (socket,'socket'),(subprocess,'Popen'),(os,'system')):
        monkeypatch.setattr(owner,name,trap)
    ledger, inventory = fixture_inputs(m)
    paths = [tmp_path/'ledger.json',tmp_path/'inventory.json']
    for path,value in zip(paths,(ledger,inventory)):path.write_bytes(encoded(value))
    before = [(p.read_bytes(),p.stat().st_mode) for p in paths]
    result = evaluate(m,m.decode(m.read_local(paths[0])),m.decode(m.read_local(paths[1])))
    assert result['utility_verdict'] == 'FIXTURE_IMPROVEMENT'
    assert before == [(p.read_bytes(),p.stat().st_mode) for p in paths]


@pytest.mark.parametrize('disposition',['FAILED','BLOCKED','CANCELLED','TIMED_OUT'])
def test_unsuccessful_no_output_retains_trial_and_charge(m, disposition):
    ledger, inventory = fixture_inputs(m)
    arm, retained = ledger['arms']['candidate'], inventory['arms']['candidate']
    third = dict(attempt_id='candidate-3',task_id='task-2',attempt_index=3,
        disposition=disposition,runtime_receipt_ref=None,runtime_attempts=1,handler_calls=0,
        output_json=None,output_sha256=None,acceptance_status='REJECTED')
    arm['attempts'].append(third)
    retained['attempts'].append({k:third[k] for k in ('attempt_id','task_id','attempt_index','disposition')})
    retained['attempts'][-1]['review']=None
    charge=copy.deepcopy(arm['charges'][-1]);charge.update(charge_id='candidate-3',attempt_id='candidate-3')
    arm['charges'].append(charge);retained['charge_ids'].append('candidate-3')
    for row in arm['efforts'][1:]:row['covers_attempt_ids'].append('candidate-3')
    report=evaluate(m,ledger,inventory)
    result=report['arms']['candidate']
    assert report['utility_verdict']=='FIXTURE_IMPROVEMENT'
    assert result['attempt_count']==3 and result['accepted_task_count']==2
    assert result['execution_dispositions'][disposition]==1
    assert result['output_counts']['rejected']==0
    assert result['attempt_acceptance_counts']['rejected']==1
    assert result['money_by_currency']['USD']['total']==5


@pytest.mark.parametrize('field',['setup','execution_rework','review','elapsed'])
def test_censored_effort_remains_null(m, field):
    ledger,inventory=fixture_inputs(m)
    unknown(next(row for row in ledger['arms']['candidate']['efforts'] if row['effort_id']==field),state='censored')
    report=evaluate(m,ledger,inventory)
    assert report['utility_verdict']=='INDETERMINATE'
    assert report['arms']['candidate']['effort_component_sums'][field] is None
    assert 'candidate.efforts.'+field in report['missing_fields']


@pytest.mark.parametrize('kind',['tasks','attempts','efforts','charges'])
def test_fixed_row_caps_refuse(m, kind):
    ledger,inventory=fixture_inputs(m)
    rows=ledger['arms']['candidate'][kind]
    rows.extend(copy.deepcopy(rows[-1]) for _ in range(9))
    assert evaluate(m,ledger,inventory)['utility_verdict']=='INVALID'


def test_equivalent_integer_float_summary_is_arm_neutral(m):
    ledger,inventory=fixture_inputs(m)
    for arm in ('baseline','candidate'):
        for row, observed in zip(ledger['arms'][arm]['attempts'],inventory['arms'][arm]['attempts']):
            summary=json.loads(row['output_json'])
            for values in summary['conditions'].values():
                values['sum']=float(values['sum']);values['mean']=float(values['mean'])
            row['output_json']=encoded(summary).decode();row['output_sha256']=m.sha(encoded(summary))
            observed['review']['output_sha256']=row['output_sha256']
    assert evaluate(m,ledger,inventory)['utility_verdict']=='FIXTURE_IMPROVEMENT'


# V2 counter correction, frozen before executable changes: output_counts includes
# only retained output_json (candidate) and its decision status; inspected counts
# only retained outputs with ACCEPTED/REJECTED reviewer decisions. Every observed
# attempt contributes exactly once to attempt_acceptance_counts, irrespective of
# output existence. Neither bucket deduplicates repeated bytes. No-output failures
# remain in trial/disposition/effort/cost accounting. V1 mislabeled failed no-output
# attempts as rejected outputs; this is a semantic correction, not a v1 claim.
@pytest.mark.parametrize('disposition,has_output', [
    ('FAILED', False), ('BLOCKED', False), ('COMPLETED', True),
], ids=['failed-no-output','blocked-no-output','completed-rejected-output'])
def test_v2_output_and_attempt_counters_are_distinct(m, disposition, has_output):
    ledger,inventory=fixture_inputs(m)
    arm,retained=ledger['arms']['candidate'],inventory['arms']['candidate']
    third=copy.deepcopy(arm['attempts'][-1])
    third.update(attempt_id='candidate-3',attempt_index=3,disposition=disposition,
                 acceptance_status='REJECTED')
    observed=copy.deepcopy(retained['attempts'][-1])
    observed.update(attempt_id='candidate-3',attempt_index=3,disposition=disposition)
    if has_output:
        observed['review']['decision']='REJECTED'
    else:
        third.update(output_json=None,output_sha256=None,runtime_attempts=1,handler_calls=0)
        observed['review']=None
    arm['attempts'].append(third);retained['attempts'].append(observed)
    charge=copy.deepcopy(arm['charges'][-1])
    charge.update(charge_id='candidate-3',attempt_id='candidate-3')
    arm['charges'].append(charge);retained['charge_ids'].append('candidate-3')
    for row in arm['efforts'][1:]:row['covers_attempt_ids'].append('candidate-3')
    report=evaluate(m,ledger,inventory);result=report['arms']['candidate']
    assert report['utility_verdict']=='FIXTURE_IMPROVEMENT'
    assert result['attempt_count']==3 and result['accepted_task_count']==2
    assert result['money_by_currency']['USD']['total']==5
    assert result['accepted_per_attempt']=={'numerator':2,'denominator':3}
    assert result['attempt_acceptance_counts']==dict(accepted=2,rejected=1,unreviewed=0,pending=0)
    assert result['output_counts']==dict(candidate=2+int(has_output),inspected=2+int(has_output),
                                        accepted=2,rejected=int(has_output),unreviewed=0,pending=0)
