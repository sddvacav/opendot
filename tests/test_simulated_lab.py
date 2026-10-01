"""Bounded pure-Python simulation; no hardware or remote services."""
import builtins
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from opendot_engineering.adapters import simulated_lab as lab
from opendot_engineering.adapters import source_audit as audit


@pytest.fixture
def simulation_deps():
    try:
        if any(version(name) != pin for name, pin in lab.TESTED_VERSIONS.items()):
            pytest.skip("exact optional simulated-lab dependencies are not installed")
    except PackageNotFoundError:
        pytest.skip("optional simulated-lab dependencies are not installed")


def test_optional_imports_remain_lazy(monkeypatch):
    real_import = builtins.__import__
    def guarded(name, *args, **kwargs):
        assert name.split('.')[0] not in {'bluesky', 'ophyd'}
        return real_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', guarded)
    import importlib
    importlib.reload(lab)
    assert lab._request([0], 'normal')['setpoints'] == [0.0]


@pytest.mark.parametrize('points', [[], [0] * 17, [True], ['0'], [None], [float('nan')],
                                    [float('inf')], [1.01], [-1.01], [10**1000], object(), iter([0])])
def test_reject_before_dependencies_execution_or_output(tmp_path, monkeypatch, points):
    def forbidden(*args, **kwargs):
        pytest.fail('validation must precede execution and dependency lookup')
    monkeypatch.setattr(lab, '_versions', forbidden)
    monkeypatch.setattr(subprocess, 'run', forbidden)
    with pytest.raises(audit.AuditRejected):
        lab.run_simulation(tmp_path, setpoints=points)
    assert list(tmp_path.iterdir()) == []


def test_no_generic_plan_or_device_injection(tmp_path, monkeypatch):
    with pytest.raises(TypeError):
        lab.run_simulation(tmp_path, device=object())
    with pytest.raises(TypeError):
        lab.run_simulation(tmp_path, plan=lambda: None)
    with pytest.raises(audit.AuditRejected, match='INVALID_SCENARIO'):
        lab.run_simulation(tmp_path, scenario='resume')
    assert list(tmp_path.iterdir()) == []


def test_missing_optional_dependency_creates_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(lab, 'version', lambda _: (_ for _ in ()).throw(PackageNotFoundError()))
    with pytest.raises(audit.AuditRejected, match='DEPENDENCY_MISSING'):
        lab.run_simulation(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_untested_optional_version_creates_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(lab, 'version', lambda _: '0.0.0')
    with pytest.raises(audit.AuditRejected, match='VERSION_UNTESTED'):
        lab.run_simulation(tmp_path)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('scenario,status,event_count', [('normal', 'success', 16),
    ('fake_failure', 'fail', 0), ('simulated_abort', 'abort', 0)])
def test_actual_run_and_raw_terminal(tmp_path, simulation_deps, scenario, status, event_count):
    points = [-1, 1] * 8
    receipt = lab.run_simulation(tmp_path, setpoints=points, scenario=scenario)
    assert receipt['exit_status'] == status
    assert receipt['error_code'] is None
    assert 0 < receipt['elapsed_s'] < 10
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    result = lab.verify_run(tmp_path, expected_manifest_sha256=receipt['manifest_sha256'])
    assert result['audit_accepted'] is True
    assert result['exit_status'] == status and result['events'] == event_count
    assert result['documents'] <= 19
    for item in [receipt, result]:
        for key in ('scientific_accepted', 'device_authority', 'device_control_authorized', 'real_device_qualified'):
            assert item[key] is False
        for key in ('resume', 'real_interlocks', 'physical_calibration'):
            assert item[key] == 'NOT_IMPLEMENTED'
    records = [json.loads(line) for line in before['documents.jsonl'].splitlines()]
    assert records[-1]['name'] == 'stop'
    assert records[-1]['doc']['exit_status'] == status
    if scenario == 'fake_failure':
        assert records[-1]['doc']['reason'] == 'INJECTED_FAKE_DETECTOR_FAILURE'
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises(audit.AuditRejected, match='OUTPUT_DIRECTORY_NOT_EMPTY'):
        lab.run_simulation(tmp_path)
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


@pytest.fixture
def normal(tmp_path, simulation_deps):
    receipt = lab.run_simulation(tmp_path)
    return tmp_path, receipt


@pytest.mark.parametrize('filename', ['documents.jsonl', 'terminal.json', 'manifest.json'])
def test_tamper_detected(normal, filename):
    root, receipt = normal
    path = root / filename
    path.write_bytes(path.read_bytes() + b' ')
    with pytest.raises(audit.AuditRejected, match='HASH_MISMATCH'):
        lab.verify_run(root, expected_manifest_sha256=receipt['manifest_sha256'])


def _repin(root, name, value):
    raw = lab._json(value)
    (root / name).write_bytes(raw)
    manifest = json.loads((root / 'manifest.json').read_text())
    manifest['files'][name] = {'sha256': audit._sha256(raw), 'bytes': len(raw)}
    (root / 'manifest.json').write_bytes(lab._json(manifest))
    return audit._sha256((root / 'manifest.json').read_bytes())


def test_semantic_false_promotion_even_with_new_pin(normal):
    root, _ = normal
    terminal = json.loads((root / 'terminal.json').read_text())
    terminal['device_authority'] = True
    pin = _repin(root, 'terminal.json', terminal)
    with pytest.raises(audit.AuditRejected, match='FALSE_EVIDENCE_PROMOTION'):
        lab.verify_run(root, expected_manifest_sha256=pin)


def test_symlink_raw_refused(normal):
    root, receipt = normal
    original = root / 'documents.jsonl'
    data = original.read_bytes()
    original.unlink()
    other = root / 'other.jsonl'
    other.write_bytes(data)
    original.symlink_to(other)
    with pytest.raises(audit.AuditRejected, match='UNAVAILABLE_OR_UNSAFE'):
        lab.verify_run(root, expected_manifest_sha256=receipt['manifest_sha256'])


def test_timeout_preserves_partial_raw_without_inventing_stop(tmp_path, monkeypatch):
    monkeypatch.setattr(lab, '_versions', lambda: dict(lab.TESTED_VERSIONS))
    def timeout(command, **kwargs):
        fd = kwargs['pass_fds'][0]
        os.write(fd, b'{"name":"start","doc":')
        assert kwargs['timeout'] == 8
        assert kwargs['env']['OPHYD_CONTROL_LAYER'] == 'dummy'
        assert 'PYTHONPATH' not in kwargs['env']
        raise subprocess.TimeoutExpired(command, 8)
    monkeypatch.setattr(subprocess, 'run', timeout)
    receipt = lab.run_simulation(tmp_path)
    assert receipt['exit_status'] == 'incomplete'
    assert receipt['error_code'] == 'WORKER_TIMEOUT'
    assert (tmp_path / 'documents.jsonl').read_bytes() == b'{"name":"start","doc":'
    assert receipt['stop_uid'] is None
    with pytest.raises(audit.AuditRejected, match='INCOMPLETE_RUN'):
        lab.verify_run(tmp_path, expected_manifest_sha256=receipt['manifest_sha256'])


def test_no_outbound_connection_from_worker(tmp_path, simulation_deps):
    worker = Path(lab.__file__).with_name('_simulated_lab_worker.py')
    code = '''import runpy, socket, sys

def refused(*args, **kwargs):
    raise AssertionError("outbound socket operation forbidden")
socket.socket.connect = refused
socket.socket.connect_ex = refused
socket.create_connection = refused
sys.argv = [sys.argv[1], sys.argv[2]]
runpy.run_path(sys.argv[0], run_name="__main__")
'''
    with (tmp_path / 'raw.jsonl').open('xb', buffering=0) as raw:
        result = subprocess.run([sys.executable, '-I', '-B', '-c', code, str(worker), str(raw.fileno())],
            pass_fds=(raw.fileno(),), input=lab._json(lab._request([0], 'normal')),
            env={'OPHYD_CONTROL_LAYER': 'dummy', 'OTEL_SDK_DISABLED': 'true'},
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8)
    assert result.returncode == 0, result.stderr.decode()
    assert json.loads(result.stdout)['exit_status'] == 'success'


@pytest.mark.parametrize('mutation,code', [('reading', 'SIMULATED_DATA_MISMATCH'),
                                         ('status', 'TERMINAL_MISMATCH'),
                                         ('sequence_bool', 'SIMULATED_DATA_MISMATCH')])
def test_rehashed_raw_semantic_tampering_refused(normal, mutation, code):
    root, _ = normal
    records = [json.loads(line) for line in (root / 'documents.jsonl').read_bytes().splitlines()]
    if mutation == 'reading':
        records[2]['doc']['data']['sim_detector'] = 999
    elif mutation == 'status':
        records[-1]['doc']['exit_status'] = 'abort'
    else:
        records[2]['doc']['seq_num'] = True
    raw = b''.join(lab._json(record) for record in records)
    (root / 'documents.jsonl').write_bytes(raw)
    manifest = json.loads((root / 'manifest.json').read_text())
    manifest['files']['documents.jsonl'] = {'sha256': audit._sha256(raw), 'bytes': len(raw)}
    manifest_raw = lab._json(manifest)
    (root / 'manifest.json').write_bytes(manifest_raw)
    with pytest.raises(audit.AuditRejected, match=code):
        lab.verify_run(root, expected_manifest_sha256=audit._sha256(manifest_raw))


@pytest.fixture(scope='module')
def protocol_bundles(tmp_path_factory):
    try:
        lab._versions()
    except audit.AuditRejected:
        pytest.skip('exact optional simulation dependencies are not installed')
    bundles = {}
    for scenario in ('normal', 'fake_failure', 'simulated_abort'):
        root = tmp_path_factory.mktemp('profile-' + scenario)
        receipt = lab.run_simulation(root, setpoints=[-1, .125, 1], scenario=scenario)
        lab.verify_run(root, expected_manifest_sha256=receipt['manifest_sha256'])
        bundles[scenario] = {p.name: p.read_bytes() for p in root.iterdir()}
    return bundles


def _mutated_bundle(root, bundle, mutate):
    records = [json.loads(line) for line in bundle['documents.jsonl'].splitlines()]
    terminal = json.loads(bundle['terminal.json'])
    manifest = json.loads(bundle['manifest.json'])
    mutate(records, terminal)
    raw = b''.join(lab._json(record) for record in records)
    for name, data in [('documents.jsonl', raw), ('terminal.json', lab._json(terminal))]:
        (root / name).write_bytes(data)
        manifest['files'][name] = {'sha256': audit._sha256(data), 'bytes': len(data)}
    manifest_raw = lab._json(manifest)
    (root / 'manifest.json').write_bytes(manifest_raw)
    return audit._sha256(manifest_raw)


def _change(document, path, value):
    parts = path.split('/')
    for part in parts[:-1]:
        document = document[part]
    if value == '__DELETE__':
        document.pop(parts[-1])
    else:
        document[parts[-1]] = value


@pytest.mark.parametrize('role,path,value', [
    ('start', 'uid', '__DELETE__'), ('start', 'time', '__DELETE__'),
    ('start', 'uid', None), ('start', 'uid', 'not-a-uuid'),
    ('start', 'time', True), ('start', 'time', -1),
    ('start', 'versions/ophyd', '0.0.0'), ('start', 'versions/event_model', '__DELETE__'),
    ('start', 'plan_type', 'custom'), ('start', 'scan_id', True),
    ('start', 'simulation_request/setpoints', [-1, .125, 1]),
    ('descriptor', 'run_start', '__DELETE__'), ('descriptor', 'run_start', None),
    ('descriptor', 'uid', '__DELETE__'), ('descriptor', 'time', '__DELETE__'),
    ('descriptor', 'name', 'other'), ('descriptor', 'configuration', '__DELETE__'),
    ('descriptor', 'data_keys', '__DELETE__'), ('descriptor', 'object_keys', {}),
    ('descriptor', 'hints/sim_axis/fields', ['not_the_axis']),
    ('descriptor', 'data_keys/sim_axis/units', 'millimeter'),
    ('descriptor', 'data_keys/sim_detector/source', 'PV:REAL:HARDWARE'),
    ('descriptor', 'data_keys/sim_detector/source', 'SIM:other_detector'),
    ('descriptor', 'data_keys/sim_detector/dtype', 'string'),
    ('descriptor', 'data_keys/sim_detector/shape', [1]),
    ('descriptor', 'data_keys/sim_axis/precision', True),
    ('descriptor', 'configuration/sim_axis/data_keys/sim_axis_velocity/source', 'PV:VELOCITY'),
    ('descriptor', 'configuration/sim_axis/data/sim_axis_velocity', True),
    ('descriptor', 'configuration/sim_axis/timestamps/sim_axis_velocity', '__DELETE__'),
    ('descriptor', 'configuration/sim_detector/data/sim_detector', 42.0),
    ('event', 'uid', '__DELETE__'), ('event', 'uid', []),
    ('event', 'time', '__DELETE__'), ('event', 'time', 0), ('event', 'time', 'now'),
    ('event', 'descriptor', '__DELETE__'), ('event', 'descriptor', None),
    ('event', 'filled', {'sim_detector': True}),
    ('event', 'seq_num', '__DELETE__'), ('event', 'seq_num', 1.0),
    ('event', 'timestamps', '__DELETE__'), ('event', 'timestamps', {}),
    ('event', 'timestamps/sim_axis', True), ('event', 'timestamps/sim_detector', 1e99),
    ('stop', 'uid', '__DELETE__'), ('stop', 'uid', ''),
    ('stop', 'time', '__DELETE__'), ('stop', 'run_start', None),
    ('stop', 'reason', 'an unrelated physical stop'), ('stop', 'num_events/primary', 3.0),
])
def test_strict_profile_rejects_rehashed_document_mutations(tmp_path, protocol_bundles, role, path, value):
    def mutate(records, terminal):
        document = next(r['doc'] for r in records if r['name'] == role)
        _change(document, path, value)
    pin = _mutated_bundle(tmp_path, protocol_bundles['normal'], mutate)
    with pytest.raises(audit.AuditRejected):
        lab.verify_run(tmp_path, expected_manifest_sha256=pin)


@pytest.mark.parametrize('mutation', ['missing_all_identity', 'descriptor_without_schema',
    'duplicate_uid', 'missing_terminal_uid', 'float_timeout', 'bad_name_object',
    'bad_name_list', 'timestamp_after_event', 'event_before_descriptor',
    'configuration_timestamp_after_descriptor'])
def test_independent_reviewer_reproductions(tmp_path, protocol_bundles, mutation):
    def mutate(records, terminal):
        if mutation == 'missing_all_identity':
            for record in records:
                for key in ('uid', 'run_start', 'descriptor', 'time', 'timestamps'):
                    record['doc'].pop(key, None)
            terminal['stop_uid'] = None
        elif mutation == 'descriptor_without_schema':
            records[1]['doc'] = {key: records[1]['doc'][key] for key in ('uid', 'run_start')}
        elif mutation == 'duplicate_uid':
            records[2]['doc']['uid'] = records[0]['doc']['uid']
        elif mutation == 'missing_terminal_uid':
            terminal['stop_uid'] = None
        elif mutation == 'float_timeout':
            terminal['worker_timeout_s'] = 8.0
        elif mutation == 'bad_name_object':
            records[2]['name'] = {}
        elif mutation == 'bad_name_list':
            records[2]['name'] = []
        elif mutation == 'timestamp_after_event':
            records[2]['doc']['timestamps']['sim_axis'] = records[-1]['doc']['time'] + 1
        elif mutation == 'event_before_descriptor':
            records[2]['doc']['time'] = records[0]['doc']['time'] - 1
        else:
            records[1]['doc']['configuration']['sim_axis']['timestamps']['sim_axis_velocity'] = records[-1]['doc']['time'] + 1
    pin = _mutated_bundle(tmp_path, protocol_bundles['normal'], mutate)
    with pytest.raises(audit.AuditRejected):
        lab.verify_run(tmp_path, expected_manifest_sha256=pin)


@pytest.mark.parametrize('scenario', ['fake_failure', 'simulated_abort'])
@pytest.mark.parametrize('mutation', ['missing_start_uid', 'missing_stop_uid', 'missing_time',
    'broken_link', 'duplicate_uid', 'wrong_reason', 'wrong_status', 'fake_event_count', 'unexpected_descriptor'])
def test_failure_abort_profiles_fail_closed(tmp_path, protocol_bundles, scenario, mutation):
    def mutate(records, terminal):
        start, stop = records[0]['doc'], records[-1]['doc']
        if mutation == 'missing_start_uid':
            del start['uid']
        elif mutation == 'missing_stop_uid':
            del stop['uid']
            terminal['stop_uid'] = None
        elif mutation == 'missing_time':
            del stop['time']
        elif mutation == 'broken_link':
            stop['run_start'] = None
        elif mutation == 'duplicate_uid':
            stop['uid'] = start['uid']
            terminal['stop_uid'] = start['uid']
        elif mutation == 'wrong_reason':
            stop['reason'] = 'injected unrelated reason'
        elif mutation == 'wrong_status':
            stop['exit_status'] = terminal['exit_status'] = 'success'
        elif mutation == 'fake_event_count':
            stop['num_events'] = {'primary': 1}
        else:
            records.insert(1, {'name': 'descriptor', 'doc': {}})
    pin = _mutated_bundle(tmp_path, protocol_bundles[scenario], mutate)
    with pytest.raises(audit.AuditRejected):
        lab.verify_run(tmp_path, expected_manifest_sha256=pin)


def test_verifier_needs_no_optional_imports(tmp_path, protocol_bundles, monkeypatch):
    for name, raw in protocol_bundles['normal'].items():
        (tmp_path / name).write_bytes(raw)
    pin = audit._sha256(protocol_bundles['normal']['manifest.json'])
    real_import = builtins.__import__
    def guarded(name, *args, **kwargs):
        assert name.split('.')[0] not in {'bluesky', 'ophyd', 'event_model'}
        return real_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', guarded)
    assert lab.verify_run(tmp_path, expected_manifest_sha256=pin)['audit_accepted']
