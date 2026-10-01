"""Composition checks only; canonical execution and storage owners are imported."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from opendot_engineering.core import ArtifactRef, ArtifactStore
from opendot_engineering.core import artifacts, contracts

EXAMPLE = Path(__file__).resolve().parents[1] / 'examples/callable-artifacts/demo.py'
spec = importlib.util.spec_from_file_location('public_callable_artifacts', EXAMPLE)
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


def test_success_returns_canonical_reference_and_verified_bytes(tmp_path):
    row = demo.run_case(tmp_path / 'cas', text='synthetic success', grant=True, semantic_pass=True)
    assert row['receipt']['status'] == 'COMPLETED'
    assert row['receipt']['semantic_valid'] is True
    assert row['receipt']['attempts'] == row['handler_calls'] == 1
    assert row['receipt']['output_hash'] is not None
    ref = ArtifactRef(**row['returned_ref'])
    assert ArtifactStore(tmp_path / 'cas').get_bytes(ref) == b'synthetic success'
    assert row['cas_verify'] is row['independent_sha256_matches'] is row['stored_bytes_match'] is True
    assert row['retained_unaccepted_ref'] is None


def test_semantic_refusal_retains_integrity_without_returning_result(tmp_path):
    row = demo.run_case(tmp_path / 'cas', text='synthetic rejected value', grant=True, semantic_pass=False)
    assert row['receipt'] == {'status': 'FAILED', 'semantic_valid': False,
                              'attempts': 1, 'error_type': 'ValueError', 'output_hash': None}
    assert row['returned_ref'] is None
    assert row['handler_calls'] == row['stored_object_count'] == 1
    assert row['cas_verify'] is row['independent_sha256_matches'] is row['stored_bytes_match'] is True
    ref = ArtifactRef(**row['retained_unaccepted_ref'])
    assert ArtifactStore(tmp_path / 'cas').get_bytes(ref) == b'synthetic rejected value'


def test_missing_permission_never_invokes_handler_or_writes_object(tmp_path):
    row = demo.run_case(tmp_path / 'cas', text='must not be written', grant=False, semantic_pass=True)
    assert row['receipt'] == {'status': 'BLOCKED', 'semantic_valid': False,
                              'attempts': 1, 'error_type': 'PermissionDenied', 'output_hash': None}
    assert row['handler_calls'] == row['stored_object_count'] == 0
    assert row['returned_ref'] is row['retained_unaccepted_ref'] is row['cas_verify'] is None
    assert list((tmp_path / 'cas/meta').iterdir()) == []


def test_composition_imports_the_unique_canonical_contract_and_store():
    assert demo.ArtifactRef is ArtifactRef is artifacts.ArtifactRef is contracts.ArtifactRef
    assert demo.ArtifactStore is ArtifactStore is artifacts.ArtifactStore


def test_demo_separates_successful_and_unaccepted_artifacts(tmp_path):
    result = demo.demonstrate(tmp_path / 'output')
    assert result['synthetic_software_assertions_passed'] is True
    assert result['scope'] == 'SYNTHETIC_SOFTWARE_EXAMPLE_ONLY'
    assert result['success']['returned_ref']['sha256'] != result['semantic_refusal']['retained_unaccepted_ref']['sha256']
    assert 'accepted' not in result and 'scientific_accepted' not in result


def test_demo_refuses_existing_output_without_changes(tmp_path):
    output = tmp_path / 'existing'
    output.mkdir()
    marker = output / 'keep.txt'
    marker.write_text('existing content')
    with pytest.raises(FileExistsError):
        demo.demonstrate(output)
    assert list(output.iterdir()) == [marker]
    assert marker.read_text() == 'existing content'


def test_example_main_reports_bounded_software_assertions(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', [str(EXAMPLE), '--output', str(tmp_path / 'output')])
    assert demo.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result['synthetic_software_assertions_passed'] is True
    assert result['semantic_refusal']['receipt']['status'] == 'FAILED'
    assert result['semantic_refusal']['cas_verify'] is True
