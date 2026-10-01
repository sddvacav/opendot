"""Synthetic worked workflow; no native solver, model, or physical measurement."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / 'examples/measurement-review/demo.py'
SPEC = importlib.util.spec_from_file_location('measurement_review_example', DEMO)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)
DATA = (DEMO.parent / 'batch.csv').read_bytes()


def run(tmp_path, **kwargs):
    out = tmp_path / 'case'
    result = module.run_case(out, DATA, **kwargs)
    return out, result


def verify(out, result):
    return module.replay(out, **{k: result[k] for k in ('bundle_sha256', 'input_sha256', 'oracle_sha256')})


def test_independent_expected_fixture():
    assert module.sha(DATA) == '12fa76e2cb8defb752ce08a2fdd386b0f943579d1438e3022cb2e345bdcae0d9'
    actual = module.summarize(DATA)
    assert actual['conditions'] == {'A': {'count': 3, 'sum': 6, 'mean': 2},
                                    'B': {'count': 3, 'sum': 12, 'mean': 4}}
    assert actual['rows'] == 6 and actual['unit'] == 'au'


def test_valid_roundtrip(tmp_path):
    out, receipt = run(tmp_path)
    assert receipt['status'] == 'COMPLETED'
    assert verify(out, receipt)['verification_replay_passed'] is True
    assert verify(out, receipt)['execution_restarted'] is False
    assert verify(out, receipt)['scientific_accepted'] is False


def test_wrong_mean_retains_unaccepted_bytes(tmp_path):
    out, receipt = run(tmp_path, wrong_mean=True)
    bundle = json.loads((out / 'bundle.json').read_bytes())
    assert receipt['status'] == 'FAILED' and receipt['semantic_valid'] is False
    assert bundle['retained_unaccepted_result'] is True
    assert bundle['returned_result'] is False and bundle['handler_calls'] == 1
    store = module.ArtifactStore(out / 'artifacts')
    assert store.verify_id(bundle['result_ref']['artifact_id'])
    with pytest.raises(ValueError, match='UNACCEPTED_TOOL_RESULT'):
        verify(out, receipt)


def test_denied_dispatch(tmp_path):
    out, receipt = run(tmp_path, grant=False)
    bundle = json.loads((out / 'bundle.json').read_bytes())
    assert receipt['status'] == 'BLOCKED'
    assert bundle['receipt']['error_type'] == 'PermissionDenied'
    assert bundle['handler_calls'] == 0 and bundle['result_ref'] is None
    assert not any(p.is_file() for p in (out / 'artifacts/objects').rglob('*'))
    with pytest.raises(ValueError, match='UNACCEPTED_TOOL_RESULT'):
        verify(out, receipt)


@pytest.mark.parametrize('field', ['bundle_sha256', 'input_sha256', 'oracle_sha256'])
def test_expected_pin_mismatch(tmp_path, field):
    out, receipt = run(tmp_path)
    receipt[field] = '0' * 64
    with pytest.raises(ValueError):
        verify(out, receipt)


@pytest.mark.parametrize('target', ['source_ref', 'result_ref'])
def test_cas_corruption(tmp_path, target):
    out, receipt = run(tmp_path)
    bundle = json.loads((out / 'bundle.json').read_bytes())
    digest = bundle[target]['sha256']
    path = out / 'artifacts/objects' / digest[:2] / digest[2:]
    path.chmod(0o600)
    path.write_bytes(b'changed')
    with pytest.raises(ValueError, match='ARTIFACT_INTEGRITY_FAILED'):
        verify(out, receipt)


@pytest.mark.parametrize('field,value', [
    ('oracle_id', 'measurement-review/v2'), ('oracle_sha256', 'f' * 64),
    ('input_sha256', 'f' * 64), ('scientific_accepted', True),
    ('evidence_role', 'measured'), ('schema', 'different'),
    ('returned_result', False), ('retained_unaccepted_result', True), ('handler_calls', 2)])
def test_resealed_bundle_mutation(tmp_path, field, value):
    out, receipt = run(tmp_path)
    bundle = json.loads((out / 'bundle.json').read_bytes())
    bundle[field] = value
    raw = module.encoded(bundle)
    (out / 'bundle.json').write_bytes(raw)
    receipt['bundle_sha256'] = module.sha(raw)  # Other trusted pins/oracle remain unchanged.
    with pytest.raises(ValueError):
        verify(out, receipt)


@pytest.mark.parametrize('data', [
    DATA.replace(b'A,1,1,au', b'A,1,nan,au'), DATA.replace(b'A,1,1,au', b'A,1,Infinity,au'),
    DATA.replace(b'A,1,1,au', b'A,1,1000001,au'),
    DATA.replace(b'A,1,1,au', b'A,1,1e999999999,au'), DATA.replace(b'A,1,1,au', b'A,1,no,au'),
    DATA.replace(b'A,1,1,au', b'A,1,1,MPa'), DATA.replace(b'A,1,1,au', b'X,1,1,au'),
    DATA.replace(b'A,1,1,au', b'A,2,1,au'), DATA.replace(b'A,1,1,au\n', b''),
    DATA.replace(b'value,unit', b'unit,value'), DATA.replace(b'A,1,1,au', b'A,1,1'),
    DATA.replace(b'A,1,1,au', b'A,1,1,au,extra'), b'\xff', b'x' * 65537])
def test_invalid_input_before_effects(tmp_path, data):
    out = tmp_path / 'case'
    with pytest.raises((ValueError, UnicodeError)):
        module.run_case(out, data)
    assert not out.exists()


def test_existing_output_is_untouched(tmp_path):
    out = tmp_path / 'case'
    out.mkdir()
    marker = out / 'sentinel'
    marker.write_text('preserve')
    with pytest.raises(FileExistsError):
        module.run_case(out, DATA)
    assert marker.read_text() == 'preserve' and list(out.iterdir()) == [marker]


def test_fresh_process_replay(tmp_path):
    out, receipt = run(tmp_path)
    command = [sys.executable, '-B', str(DEMO), 'replay', '--output', str(out)]
    for field in ('bundle_sha256', 'input_sha256', 'oracle_sha256'):
        command.extend(['--' + field.replace('_', '-'), receipt[field]])
    result = subprocess.run(command, capture_output=True, text=True, timeout=10,
                            env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    assert result.returncode == 0, result.stderr + result.stdout
    assert json.loads(result.stdout)['verification_replay_passed'] is True


def test_failed_cli_does_not_echo_private_paths(tmp_path):
    result = subprocess.run([sys.executable, '-B', str(DEMO), 'run', '--input',
                             str(tmp_path / 'not-public-name'), '--output', str(tmp_path / 'out')],
                            capture_output=True, text=True, timeout=10,
                            env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    assert result.returncode == 1
    assert str(tmp_path) not in result.stdout and 'not-public-name' not in result.stdout
