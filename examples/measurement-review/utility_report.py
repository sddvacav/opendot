"""Finite read-only O3 fixture report. No execution, acquisition or real utility claim."""
from __future__ import annotations

import argparse
from fractions import Fraction
import json
import math
import os
from pathlib import Path
import sys

from opendot_engineering.adapters import source_audit as audit

ROOT = Path(__file__).resolve().parents[2]
MAX_BYTES, MAX_TEXT_BYTES = 65536, 8192
ARMS, TASKS = ('baseline', 'candidate'), ('task-1', 'task-2')
EFFORTS = ('setup', 'execution_rework', 'review', 'elapsed')
DISPOSITIONS = ('COMPLETED', 'FAILED', 'BLOCKED', 'CANCELLED', 'TIMED_OUT', 'UNRESOLVED')
DECISIONS = ('ACCEPTED', 'REJECTED', 'UNREVIEWED', 'DECISION_PENDING')
SOURCE_PINS = {
    'src/opendot_engineering/adapters/source_audit.py': 'c94737305b1e5a80453541ce890bde4fcb700a0074e32344fe839b237374bfa7',
    'docs/research/delta-20261002/source-needs-delta.json': 'fcccb1cbec6d74e7bb40cd8a191dc69dd37a5b100569075895f9183d07bdfed7',
    'docs/research/oss-workflows/frozen-oracle/expected-summary.json': '4df81c0c33cd274af97197d6d9eb2d3e05c63579e026eb41b2ef8718d41d63e5',
    'examples/measurement-review/batch.csv': '12fa76e2cb8defb752ce08a2fdd386b0f943579d1438e3022cb2e345bdcae0d9',
}
HISTORY, ORACLE, INPUT = tuple(SOURCE_PINS)[1:]
FLAGS = dict(evidence_role='synthetic', measured_effort_status='UNKNOWN',
             real_comparison_status='NOT_RUN', real_world_benefit_established=False,
             scientific_accepted=False, device_control_authorized=False,
             independent_review='NOT_EVALUATED')


def require(condition, code='INVALID'):
    if not condition:
        raise ValueError(code)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def sha(raw):
    return audit._sha256(raw)


def read_local(path):
    path = Path(path).absolute()
    fd = audit._root_fd(path.parent)
    try:
        return audit._read(fd, path.name, MAX_BYTES)
    finally:
        os.close(fd)


def decode(raw):
    require(type(raw) is bytes and len(raw) <= MAX_BYTES, 'INPUT_TOO_LARGE')
    try:
        value = audit._decode(raw)
        encoded(value)  # Reject JSON exponents overflowing the default float parser.
        return value
    except (ValueError, RecursionError):
        raise ValueError('INVALID_JSON') from None


def keys(row, names):
    require(type(row) is dict and set(row) == set(names))


def text(value):
    require(type(value) is str and 0 < len(value) <= 128
            and all(ord(c) >= 32 for c in value))


def number(value):
    require(type(value) in (int, float))
    try:
        require(math.isfinite(value) and value >= 0)
    except OverflowError:
        raise ValueError('INVALID') from None
    return Fraction(str(value))


def exact(value):
    if value is None:
        return None
    return value.numerator if value.denominator == 1 else dict(
        numerator=value.numerator, denominator=value.denominator)


def source_inputs():
    require(Path(audit.__file__).resolve() == ROOT / 'src/opendot_engineering/adapters/source_audit.py',
            'SOURCE_PIN_MISMATCH')
    result = {}
    for path, pin in SOURCE_PINS.items():
        raw = read_local(ROOT / path)
        require(sha(raw) == pin, 'SOURCE_PIN_MISMATCH')
        result[path] = raw
    return result


def profile():
    source_inputs()
    common = dict(protocol_id='o3-fixed-fixture-v1', environment_id='fixture-local',
        budget_kind='all-attempts', budget_limit=3, budget_unit='attempts',
        cutoff_rule='retain-up-to-three-no-rerun', attempt_definition='one-task-trial',
        acceptance_unit='eligible-task-once', utility_rule_id='strict-more-no-extra-effort-v1',
        effort_unit='person_minutes', setup_allocation_rule='all-setup-to-two-admitted-tasks',
        acceptance_owner_id='fixture-reviewer')
    return dict(schema='o3.offline-profile.v1', task_ids=list(TASKS),
        counter_semantics='retained-output-only-and-separate-all-attempt-status-v2',
        input_sha256=SOURCE_PINS[INPUT], oracle_sha256=SOURCE_PINS[ORACLE],
        source_pins=SOURCE_PINS,
        consumer_sha256=sha(read_local(Path(__file__))),
        bindings={arm: dict(common, version=('manual-script-fixture-v1' if arm=='baseline'
                                           else 'opendot-fixture-v1')) for arm in ARMS},
        max_attempts_per_arm=3, max_effort_rows_per_arm=8, max_charge_rows_per_arm=8,
        max_bytes=MAX_BYTES, max_summary_bytes=MAX_TEXT_BYTES,
        money_boundary='setup-and-all-incremental-compute-tool-storage-idle-excludes-human-labor',
        completeness_boundary='independently-pinned-synthetic-inventory-consistency-only')


def historical_report():
    inputs = source_inputs()
    oracle = decode(inputs[HISTORY])['oracles'][2]
    require(oracle['oracle_id'] == 'O3-INCREMENTAL-UTILITY', 'SOURCE_PIN_MISMATCH')
    results = []
    for case in oracle['cases']:
        fixture = case['fixture']
        result = dict(case_id=case['case_id'], original_status=case['status'],
                      measured_effort_status='UNKNOWN', real_world_benefit_established=False)
        if 'baseline' not in fixture:
            result.update(utility_verdict='INDETERMINATE', utility_improvement=False,
                          fixture_effort_units=None)
        else:
            b, c = fixture['baseline'], fixture['candidate']
            positive = c['accepted'] > b['accepted'] and c['total_effort'] <= b['total_effort']
            result.update(fixture_effort_units=dict(baseline=b['total_effort'],candidate=c['total_effort']),
                utility_improvement=positive, fixture_utility_improvement=positive,
                utility_verdict='FIXTURE_IMPROVEMENT' if positive else 'NO_FIXTURE_IMPROVEMENT')
            if 'attempts' in c:
                result['candidate_attempt_denominator'] = c['attempts']
        results.append(result)
    return dict(schema='o3.offline-report.v1', **FLAGS, historical_cases=results,
                history_sha256=SOURCE_PINS[HISTORY], source_pins=SOURCE_PINS)


def unique(rows, field, limit):
    require(type(rows) is list and len(rows) <= limit)
    ids = []
    for row in rows:
        require(type(row) is dict and field in row)
        text(row[field]); ids.append(row[field])
    require(len(set(ids)) == len(ids))
    return dict(zip(ids, rows))


def semantics(raw, expected):
    """Arm-neutral fixed output contract, from the existing independently frozen file."""
    try:
        actual = decode(raw)
        keys(actual, expected)
        for field in ('schema_version','validator_id','unit'):
            require(actual[field] == expected[field])
        require(type(actual['rows']) is int and actual['rows'] == expected['rows'])
        keys(actual['conditions'], ('A','B'))
        for condition in ('A','B'):
            row, wanted = actual['conditions'][condition], expected['conditions'][condition]
            keys(row, ('count','sum','mean'))
            require(type(row['count']) is int and row['count'] == wanted['count'])
            for field in ('sum','mean'):
                require(number(row[field]) == number(wanted[field]))
        return True
    except ValueError:
        return False


def inspect_arm(arm, data, inventory, frozen, expected, issues):
    def missing(path): issues['missing_fields'].append(f'{arm}.{path}')
    def mismatch(path): issues['noncomparable'].append(f'{arm}.{path}')
    keys(data, ('binding','tasks','attempts','efforts','charges'))
    keys(inventory, ('task_ids','attempts','effort_ids','charge_ids'))
    require(type(inventory['task_ids']) is list and len(inventory['task_ids']) <= 2)
    require(len(set(inventory['task_ids'])) == len(inventory['task_ids']))
    if inventory['task_ids'] != list(TASKS): mismatch('inventory.task_ids')
    require(type(data['binding']) is dict and set(data['binding']) <= set(frozen['bindings'][arm]))
    for key,value in frozen['bindings'][arm].items():
        if data['binding'].get(key) is None: missing('binding.'+key)
        elif encoded(data['binding'][key]) != encoded(value): mismatch('binding.'+key)
    tasks = unique(data['tasks'],'task_id',2)
    if set(tasks) != set(TASKS): mismatch('tasks')
    eligible, admitted = set(), set()
    for tid, row in tasks.items():
        keys(row, ('task_id','input_sha256','required_output_contract_sha256','condition','unit','eligible','admitted'))
        for key,value in dict(input_sha256=frozen['input_sha256'],
                required_output_contract_sha256=frozen['oracle_sha256'], condition='bench-A',unit='au',
                eligible=True,admitted=True).items():
            if row[key] is None: missing(f'tasks.{tid}.{key}')
            elif encoded(row[key]) != encoded(value): mismatch(f'tasks.{tid}.{key}')
        if row['eligible'] is True: eligible.add(tid)
        if row['admitted'] is True: admitted.add(tid)
    retained = unique(inventory['attempts'],'attempt_id',3)
    for index, row in enumerate(retained.values(),1):
        keys(row, ('attempt_id','task_id','attempt_index','disposition','review'))
        require(type(row['attempt_index']) is int and row['attempt_index']==index)
        require(row['task_id'] in TASKS and row['disposition'] in DISPOSITIONS)
        if row['review'] is not None:
            review = row['review']
            keys(review, ('reviewer_id','task_id','output_sha256','decision',
                          'required_output_contract_sha256','source_ref','evidence_role'))
            require(review['evidence_role']=='synthetic' and review['decision'] in DECISIONS)
            for key in ('reviewer_id','source_ref'): text(review[key])
            if review['output_sha256'] is not None: audit._hash(review['output_sha256'],64)
            else: require(review['decision']=='REJECTED')
            require(review['task_id']==row['task_id'])
            if review['required_output_contract_sha256'] != frozen['oracle_sha256']:
                mismatch(f'inventory.{row["attempt_id"]}.oracle')
    attempts = unique(data['attempts'],'attempt_id',3)
    require(set(attempts) <= set(retained))
    for absent in sorted(set(retained)-set(attempts)): missing('attempts.'+absent)
    attempt_counts = {key:0 for key in ('accepted','rejected','unreviewed','pending')}
    counts = dict(candidate=0, inspected=0, **attempt_counts)
    dispositions = {key:0 for key in DISPOSITIONS}
    accepted_tasks, outputs = set(), []
    for aid,row in attempts.items():
        keys(row, ('attempt_id','task_id','attempt_index','disposition','runtime_receipt_ref',
            'runtime_attempts','handler_calls','output_json','output_sha256','acceptance_status'))
        original = retained[aid]
        for key in ('task_id','attempt_index','disposition'):
            require(encoded(row[key])==encoded(original[key]))
        for key in ('runtime_attempts','handler_calls'):
            require(row[key] is None or (type(row[key]) is int and 0 <= row[key] <= 1000000))
        if row['runtime_receipt_ref'] is not None: text(row['runtime_receipt_ref'])
        require(row['acceptance_status'] in DECISIONS)
        dispositions[row['disposition']] += 1
        integrity, semantic, decision = 'NO_OUTPUT', 'NOT_EVALUATED', row['acceptance_status']
        review = original['review']
        if row['disposition']=='UNRESOLVED': missing('attempts.'+aid+'.disposition')
        if row['output_json'] is None:
            require(row['output_sha256'] is None)
            if decision != 'REJECTED': missing('attempts.'+aid+'.output')
        else:
            require(type(row['output_json']) is str)
            audit._hash(row['output_sha256'],64)
            raw = row['output_json'].encode('utf-8')
            require(len(raw) <= MAX_BYTES)
            counts['candidate'] += 1
            integrity = 'PASS' if sha(raw)==row['output_sha256'] else 'FAIL'
            semantic = 'PASS' if semantics(raw,expected) else 'FAIL'
        if review is None:
            if row['output_json'] is not None or decision != 'REJECTED':
                missing('attempts.'+aid+'.review')
                decision='UNREVIEWED'
        else:
            require(review['decision']==row['acceptance_status'])
            if review['reviewer_id'] != 'fixture-reviewer': missing('attempts.'+aid+'.reviewer')
            if row['output_json'] is not None:
                require(review['output_sha256']==row['output_sha256'])
            if row['output_json'] is not None and decision in ('ACCEPTED','REJECTED'):
                counts['inspected'] += 1
        if decision in ('UNREVIEWED','DECISION_PENDING'):
            missing('attempts.'+aid+'.decision')
            status = 'unreviewed' if decision=='UNREVIEWED' else 'pending'
        elif (decision=='ACCEPTED' and integrity=='PASS' and semantic=='PASS'
              and row['disposition']=='COMPLETED' and review['reviewer_id']=='fixture-reviewer'
              and review['required_output_contract_sha256']==frozen['oracle_sha256']):
            status='accepted'
            if row['task_id'] in eligible & admitted: accepted_tasks.add(row['task_id'])
        else: status='rejected'
        attempt_counts[status] += 1
        if row['output_json'] is not None:
            counts[status] += 1
        outputs.append(dict(row, integrity_status=integrity, semantic_status=semantic,
                            derived_acceptance_status=status.upper(), acceptance_record=review))
    require(inventory['effort_ids'] == list(EFFORTS))
    efforts = unique(data['efforts'],'effort_id',8)
    require(set(efforts) <= set(EFFORTS))
    values, intervals = {}, []
    for field in EFFORTS:
        if field not in efforts:
            missing('efforts.'+field);values[field]=None;continue
        row = efforts[field]
        keys(row, ('effort_id','value_state','value','unit','evidence_role','source_ref',
                   'method_id','reason','start','end','person_id','covers_attempt_ids'))
        require(row['evidence_role']=='synthetic' and row['method_id']=='synthetic-interval/v1')
        require(row['unit']==('seconds' if field=='elapsed' else 'person_minutes'))
        require(row['person_id']==(None if field=='elapsed' else 'fixture-person'))
        require(row['covers_attempt_ids']==([] if field=='setup' else list(retained)))
        require(row['value_state'] in ('known','unknown','censored'))
        if row['value_state']!='known':
            require(row['value'] is row['start'] is row['end'] is None)
            text(row['reason']);missing('efforts.'+field);values[field]=None
        else:
            text(row['source_ref']);require(row['reason'] is None)
            value,start,end=number(row['value']),number(row['start']),number(row['end'])
            require(end>=start and value==end-start);values[field]=value
            if field!='elapsed': intervals.append((start,end))
    intervals.sort()
    require(all(a[1]<=b[0] for a,b in zip(intervals,intervals[1:])))
    if 'elapsed' in efforts and values['elapsed'] is not None:
        for start,end in intervals:
            require(start*60 >= number(efforts['elapsed']['start'])
                    and end*60 <= number(efforts['elapsed']['end']))
    required_charges=['setup',*retained]
    require(inventory['charge_ids']==required_charges)
    charges=unique(data['charges'],'charge_id',8)
    require(set(charges)<=set(required_charges))
    for absent in sorted(set(required_charges)-set(charges)):missing('charges.'+absent)
    money={}
    for cid,row in charges.items():
        keys(row, ('charge_id','task_id','attempt_id','category','amount','currency','value_state',
                  'source_ref','usage_ref','price_date','reason','evidence_role'))
        require(row['evidence_role']=='synthetic')
        require(row['task_id']==(None if cid=='setup' else retained[cid]['task_id'])
                and row['attempt_id']==(None if cid=='setup' else cid)
                and row['category']==('setup' if cid=='setup' else 'all-incremental'))
        require(type(row['currency']) is str and len(row['currency'])==3 and row['currency'].isalpha())
        if row['currency']!='USD': mismatch('charges.'+cid+'.currency')
        totals=money.setdefault(row['currency'],dict(setup=Fraction(0),incremental=Fraction(0)))
        category='setup' if cid=='setup' else 'incremental'
        require(row['value_state'] in ('known','unknown','censored'))
        if row['value_state']!='known':
            require(row['amount'] is None);text(row['reason'])
            missing('charges.'+cid);totals[category]=None
        else:
            amount=number(row['amount']);require(row['reason'] is None)
            for key in ('source_ref','usage_ref','price_date'):text(row[key])
            if totals[category] is not None: totals[category]+=amount
    accepted=len(accepted_tasks)
    if set(charges)!=set(required_charges):
        # Missing records have unknown currency/category; no complete totals can be inferred.
        for totals in money.values():totals['setup']=totals['incremental']=None
    for totals in money.values():
        total=None if None in totals.values() else sum(totals.values())
        totals.update(total=total,cost_per_accepted_task=None if not accepted or total is None else total/accepted)
        for key,value in totals.items():totals[key]=exact(value)
    person=None if any(values[x] is None for x in EFFORTS[:3]) else sum(values[x] for x in EFFORTS[:3])
    return dict(eligible_task_count=len(eligible), admitted_task_count=len(admitted),
        accepted_task_count=accepted, attempt_count=len(attempts), retained_attempt_count=len(retained),
        accepted_per_admitted=None if not admitted else dict(numerator=accepted,denominator=len(admitted)),
        accepted_per_attempt=None if not attempts else dict(numerator=accepted,denominator=len(attempts)),
        execution_dispositions=dispositions, output_counts=counts,
        attempt_acceptance_counts=attempt_counts, accepted_task_ids=sorted(accepted_tasks),
        tasks=data['tasks'],attempts=outputs,efforts=data['efforts'],charges=data['charges'],
        effort_component_sums={key:exact(value) for key,value in values.items()},
        total_person_minutes=exact(person),elapsed_seconds=exact(values['elapsed']),money_by_currency=money),person


def report(ledger_raw, inventory_raw, *, ledger_sha256, inventory_sha256, profile_sha256):
    frozen=profile()
    for raw,pin in ((ledger_raw,ledger_sha256),(inventory_raw,inventory_sha256),(encoded(frozen),profile_sha256)):
        audit._hash(pin,64);require(sha(raw)==pin,'PIN_MISMATCH')
    ledger,inventory=decode(ledger_raw),decode(inventory_raw)
    result=historical_report()
    result.update(profile=frozen,profile_sha256=profile_sha256,ledger_sha256=ledger_sha256,
                  inventory_sha256=inventory_sha256,arms={},missing_fields=[],reason_codes=[])
    issues=dict(missing_fields=[],noncomparable=[])
    try:
        for value,schema in ((ledger,'o3.synthetic-ledger.v1'),(inventory,'o3.synthetic-inventory.v1')):
            keys(value,('schema','evidence_role','arms'))
            require(value['schema']==schema and value['evidence_role']=='synthetic')
            keys(value['arms'],ARMS)
        effort={}
        expected=decode(source_inputs()[ORACLE])
        for arm in ARMS:
            result['arms'][arm],effort[arm]=inspect_arm(arm,ledger['arms'][arm],inventory['arms'][arm],frozen,expected,issues)
        result['missing_fields']=sorted(set(issues['missing_fields']))
        result['matched_task_count']=sum(all(any(
            row['task_id']==tid and row['input_sha256']==frozen['input_sha256']
            and row['required_output_contract_sha256']==frozen['oracle_sha256']
            and row['condition']=='bench-A' and row['unit']=='au'
            and row['eligible'] is True and row['admitted'] is True
            for row in ledger['arms'][arm]['tasks']) for arm in ARMS) for tid in TASKS)
        if issues['noncomparable']:
            verdict='NOT_COMPARABLE';result['reason_codes']=['MISMATCHED_FROZEN_CONTRACT']
        elif issues['missing_fields']:
            verdict='INDETERMINATE';result['reason_codes']=['MISSING_OR_UNRESOLVED_SYNTHETIC_EVIDENCE']
        else:
            positive=(result['arms']['candidate']['accepted_task_count']>result['arms']['baseline']['accepted_task_count']
                      and effort['candidate']<=effort['baseline'])
            verdict='FIXTURE_IMPROVEMENT' if positive else 'NO_FIXTURE_IMPROVEMENT'
        result['noncomparable_fields']=sorted(set(issues['noncomparable']))
    except (ValueError,TypeError,KeyError,OverflowError,RecursionError):
        verdict='INVALID';result['reason_codes']=['MALFORMED_OR_CONTRADICTORY_SYNTHETIC_RECORD']
    result.update(utility_verdict=verdict,fixture_utility_improvement=verdict=='FIXTURE_IMPROVEMENT',
                  comparability_status='NOT_COMPARABLE' if verdict=='NOT_COMPARABLE' else
                  'INVALID' if verdict=='INVALID' else 'INDETERMINATE' if verdict=='INDETERMINATE' else 'MATCHED')
    require(len(encoded(result)) <= MAX_BYTES,'REPORT_TOO_LARGE')
    return result


def verify_report(raw, ledger_raw, inventory_raw, *, report_sha256, **pins):
    audit._hash(report_sha256,64);require(sha(raw)==report_sha256,'PIN_MISMATCH')
    observed=decode(raw)
    expected=report(ledger_raw,inventory_raw,**pins)
    require(encoded(observed)==encoded(expected),'REPORT_MISMATCH')
    return dict(verification_passed=True,report_sha256=report_sha256,**FLAGS)


def summary_text(result):
    value=('O3 offline fixture protocol only\nVerdict: '+result.get('utility_verdict','HISTORICAL_CLASSIFICATION')+
        '\nReal O3 comparison: NOT_RUN; measured effort: UNKNOWN\n'
        'Synthetic retained-record consistency is not empirical completeness or reviewer authentication.\n'
        'Scientific acceptance: false; device control: false; independent review: NOT_EVALUATED\n')
    require(len(value.encode())<=MAX_TEXT_BYTES,'SUMMARY_TOO_LARGE')
    return value


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('history','profile','ledger','verify'))
    for name in ('ledger','inventory','profile-sha256','ledger-sha256','inventory-sha256','report','report-sha256'):
        parser.add_argument('--'+name)
    args=parser.parse_args(argv)
    try:
        if args.mode=='profile': result=profile()
        elif args.mode=='history': result=historical_report()
        else:
            require(all((args.ledger,args.inventory,args.profile_sha256,args.ledger_sha256,args.inventory_sha256)), 'MISSING_PIN_OR_INPUT')
            raw,observed=read_local(args.ledger),read_local(args.inventory)
            pins=dict(profile_sha256=args.profile_sha256,ledger_sha256=args.ledger_sha256,inventory_sha256=args.inventory_sha256)
            if args.mode=='ledger':result=report(raw,observed,**pins)
            else:
                require(args.report and args.report_sha256,'MISSING_PIN_OR_INPUT')
                result=verify_report(read_local(args.report),raw,observed,report_sha256=args.report_sha256,**pins)
        payload=encoded(result);require(len(payload)<=MAX_BYTES,'REPORT_TOO_LARGE')
        sys.stdout.buffer.write(payload)
        if args.mode!='profile':sys.stderr.write(summary_text(result))
        return 0
    except (ValueError,OSError,TypeError,RecursionError):
        sys.stdout.write('{"status":"REFUSED","real_comparison_status":"NOT_RUN"}\n')
        return 2


if __name__=='__main__':
    raise SystemExit(main())
