"""Non-mutating reads in trusted synthetic trees; no sandbox/race proof."""
from contextlib import contextmanager
from dataclasses import replace
import builtins
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from opendot_engineering.core import ArtifactIntegrityError, ArtifactStore


def snapshot(root):
    # Reads may update atime. Membership, content, mode, mtime and ctime must not change.
    result = {}
    for path in (root, *sorted(root.rglob('*'))):
        info = path.lstat()
        data = os.readlink(path) if path.is_symlink() else path.read_bytes() if path.is_file() else None
        result[str(path.relative_to(root))] = (info.st_mode, info.st_mtime_ns, info.st_ctime_ns, data)
    return result


@contextmanager
def no_mutation(root, monkeypatch):
    before = snapshot(root)

    def forbidden(*args, **kwargs):
        pytest.fail('verification attempted a filesystem mutation')

    with monkeypatch.context() as patch:
        for name in ('mkdir', 'chmod', 'fchmod', 'remove', 'unlink', 'rename',
                     'replace', 'rmdir', 'link', 'symlink', 'truncate', 'utime'):
            if hasattr(os, name):
                patch.setattr(os, name, forbidden)
        for owner in (builtins, io):
            original = owner.open

            def read_open(file, mode='r', *args, _open=original, **kwargs):
                if any(flag in mode for flag in 'wax+'):
                    forbidden()
                return _open(file, mode, *args, **kwargs)

            patch.setattr(owner, 'open', read_open)
        original_os_open = os.open

        def read_os_open(path, flags, *args, **kwargs):
            if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
                forbidden()
            return original_os_open(path, flags, *args, **kwargs)

        patch.setattr(os, 'open', read_os_open)
        yield
    assert snapshot(root) == before


@pytest.mark.parametrize('kind', ['missing', 'empty', 'file'])
def test_readonly_construction_never_initializes(tmp_path, monkeypatch, kind):
    root = tmp_path / 'cas'
    if kind == 'empty':
        root.mkdir()
    elif kind == 'file':
        root.write_bytes(b'not a directory')
    with no_mutation(tmp_path, monkeypatch):
        store = ArtifactStore(root, read_only=True)
        assert not store.verify_id('sha256:' + '0' * 64)
        with pytest.raises(OSError):
            store.get_bytes('0' * 64)


@pytest.mark.parametrize('read_only', [None, 0, 1, 'true'])
def test_readonly_flag_requires_bool_before_effects(tmp_path, monkeypatch, read_only):
    with no_mutation(tmp_path, monkeypatch):
        with pytest.raises(TypeError, match='read_only must be bool'):
            ArtifactStore(tmp_path / 'missing', read_only=read_only)


@pytest.mark.parametrize('method,value', [
    ('put_bytes', b'bytes'), ('put_bytes', None),
    ('put_text', 'text'), ('put_text', None),
    ('put_json', {'valid': True}), ('put_json', object()),
    ('put_file', 'missing-input'), ('put_file', None),
])
def test_readonly_puts_refuse_before_processing(tmp_path, monkeypatch, method, value):
    store = ArtifactStore(tmp_path / 'missing', read_only=True)
    with no_mutation(tmp_path, monkeypatch):
        with pytest.raises(PermissionError, match='artifact store is read-only'):
            getattr(store, method)(value)


def test_readonly_put_file_does_not_read_source(tmp_path, monkeypatch):
    source = tmp_path / 'source'
    source.write_bytes(b'do not read')
    store = ArtifactStore(tmp_path / 'missing', read_only=True)
    with no_mutation(tmp_path, monkeypatch):
        with monkeypatch.context() as patch:
            patch.setattr(Path, 'read_bytes', lambda *a: pytest.fail('put_file read source'))
            with pytest.raises(PermissionError):
                store.put_file(source)


@pytest.mark.parametrize('state', ['valid', 'missing-object', 'corrupt-object', 'missing-metadata', 'corrupt-metadata'])
def test_readonly_retrieval_preserves_existing_contract(tmp_path, monkeypatch, state):
    writer = ArtifactStore(tmp_path / 'cas')
    ref = writer.put_bytes(b'fixed public bytes')
    obj = writer.objects / ref.sha256[:2] / ref.sha256[2:]
    metadata = writer.meta / (ref.sha256 + '.json')
    if state == 'missing-object':
        obj.chmod(0o600)
        obj.unlink()
    elif state == 'corrupt-object':
        obj.chmod(0o600)
        obj.write_bytes(b'changed')
    elif state == 'missing-metadata':
        metadata.chmod(0o600)
        metadata.unlink()
    elif state == 'corrupt-metadata':
        metadata.chmod(0o600)
        metadata.write_bytes(b'not json')
    # A mutating constructor would change these POSIX modes, even when reads succeed.
    for path in (writer.root, writer.objects, writer.meta):
        path.chmod(0o755)
    with no_mutation(tmp_path, monkeypatch):
        reader = ArtifactStore(writer.root, read_only=True)
        expected = state not in ('missing-object', 'corrupt-object')
        assert reader.verify(ref) is expected
        assert reader.verify_id(ref.artifact_id) is expected
        if expected:
            assert reader.get_bytes(ref) == b'fixed public bytes'
        else:
            with pytest.raises((OSError, ArtifactIntegrityError)):
                reader.get_bytes(ref)
        assert not reader.verify(replace(ref, size_bytes=999))
        assert not reader.verify_id('sha256:../escape')
        with pytest.raises(ArtifactIntegrityError, match='invalid artifact digest'):
            reader.get_bytes('../escape')


def test_default_and_explicit_writers_still_initialize_and_publish(tmp_path):
    for options in ({}, {'read_only': False}):
        root = tmp_path / str(len(options))
        store = ArtifactStore(root, **options)
        assert store.objects.is_dir() and store.meta.is_dir()
        ref = store.put_bytes(b'ordinary writer')
        assert store.get_bytes(ref) == b'ordinary writer'
        assert (store.meta / (ref.sha256 + '.json')).is_file()
        if os.name == 'posix':
            assert all(p.stat().st_mode & 0o777 == 0o700
                       for p in (root, store.objects, store.meta))


def test_readonly_still_follows_trusted_symlink(tmp_path, monkeypatch):
    writer = ArtifactStore(tmp_path / 'real')
    ref = writer.put_bytes(b'trusted symlink')
    alias = tmp_path / 'alias'
    try:
        alias.symlink_to(writer.root, target_is_directory=True)
    except (OSError, NotImplementedError) as error:
        pytest.skip(str(error))
    with no_mutation(tmp_path, monkeypatch):
        assert ArtifactStore(alias, read_only=True).get_bytes(ref) == b'trusted symlink'


@pytest.fixture
def measurement():
    demo = Path(__file__).resolve().parents[1] / 'examples/measurement-review/demo.py'
    spec = importlib.util.spec_from_file_location('readonly_measurement_example', demo)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, demo, (demo.parent / 'batch.csv').read_bytes()


@pytest.mark.parametrize('case', [
    'valid', 'missing-output', 'missing-bundle', 'missing-store', 'missing-source',
    'missing-result', 'mutated-source', 'mutated-result', 'mutated-bundle',
    'bundle-pin', 'input-pin', 'oracle-pin', 'wrong-mean', 'denied',
    'substituted-source', 'substituted-result',
])
def test_replay_success_and_refusals_do_not_mutate(tmp_path, monkeypatch, measurement, case):
    module, _, data = measurement
    out = tmp_path / 'case'
    receipt = module.run_case(out, data, grant=case != 'denied', wrong_mean=case == 'wrong-mean')
    pins = {key: receipt[key] for key in ('bundle_sha256', 'input_sha256', 'oracle_sha256')}
    bundle = json.loads((out / 'bundle.json').read_bytes())
    if case == 'missing-output':
        out = tmp_path / 'absent'
    elif case == 'missing-bundle':
        (out / 'bundle.json').unlink()
    elif case == 'missing-store':
        shutil.rmtree(out / 'artifacts')
    elif case.startswith(('missing-', 'mutated-')) and case.split('-')[1] in ('source', 'result'):
        digest = bundle[case.split('-')[1] + '_ref']['sha256']
        obj = out / 'artifacts/objects' / digest[:2] / digest[2:]
        obj.chmod(0o600)
        obj.unlink() if case.startswith('missing-') else obj.write_bytes(b'mutated evidence')
    elif case == 'mutated-bundle':
        (out / 'bundle.json').write_bytes(b'{}')
    elif case.endswith('-pin'):
        pins[case.split('-')[0] + '_sha256'] = '0' * 64
    elif case.startswith('substituted-'):
        # Valid new object and a resealed bundle still cannot replace the independent input/oracle pins.
        store = ArtifactStore(out / 'artifacts')
        if case == 'substituted-source':
            ref = store.put_bytes(data.replace(b'A,1,1,au', b'A,1,2,au'))
            bundle['source_ref'] = ref.__dict__
        else:
            report = {'summary': 'invented replacement'}
            ref = store.put_json(report, source_refs=(bundle['source_ref']['artifact_id'],))
            bundle['result_ref'] = ref.__dict__
        raw = module.encoded(bundle)
        (out / 'bundle.json').write_bytes(raw)
        pins['bundle_sha256'] = module.sha(raw)
    if out.exists():
        for path in (out, *(p for p in out.rglob('*') if p.is_dir())):
            path.chmod(0o755)
    monkeypatch.setattr(module, 'ToolRuntime', lambda: pytest.fail('replay started execution'))
    with no_mutation(tmp_path, monkeypatch):
        if case == 'valid':
            result = module.replay(out, **pins)
            assert result == {'verification_replay_passed': True, 'execution_restarted': False,
                              'scientific_accepted': False, 'input_sha256': pins['input_sha256'],
                              'result_sha256': bundle['result_ref']['sha256'],
                              'oracle_sha256': pins['oracle_sha256']}
        else:
            with pytest.raises((ValueError, OSError)):
                module.replay(out, **pins)


@pytest.mark.parametrize('valid', [True, False])
def test_fresh_process_replay_preserves_tree(tmp_path, measurement, valid):
    module, demo, data = measurement
    out = tmp_path / 'case'
    receipt = module.run_case(out, data)
    if not valid:
        shutil.rmtree(out / 'artifacts')
    for path in (tmp_path, *(p for p in tmp_path.rglob('*') if p.is_dir())):
        path.chmod(0o755)
    before = snapshot(tmp_path)
    command = [sys.executable, '-B', str(demo), 'replay', '--output', str(out)]
    for key in ('bundle_sha256', 'input_sha256', 'oracle_sha256'):
        command.extend(['--' + key.replace('_', '-'), receipt[key]])
    result = subprocess.run(command, capture_output=True, text=True, timeout=10,
                            env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    assert result.returncode == (0 if valid else 1), result.stderr + result.stdout
    response = json.loads(result.stdout)
    assert response.get('verification_replay_passed', False) is valid
    assert snapshot(tmp_path) == before
