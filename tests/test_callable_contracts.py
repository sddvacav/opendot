"""Public, behavior-based contracts; no private source or provenance fixtures."""
from __future__ import annotations

import dataclasses

import pytest

from opendot_engineering import tool_runtime as m


def fields(cls):
    return tuple(f.name for f in dataclasses.fields(cls))


def test_tool_risk_contract():
    assert [(item.name, item.value) for item in m.ToolRisk] == [
        ('READ_ONLY', 'read_only'), ('REVERSIBLE_WRITE', 'reversible_write'),
        ('IRREVERSIBLE_WRITE', 'irreversible_write'),
    ]


def test_breaker_state_contract():
    assert [(item.name, item.value) for item in m.BreakerState] == [
        ('CLOSED', 'closed'), ('OPEN', 'open'), ('HALF_OPEN', 'half_open'),
    ]


def test_tool_spec_fields_defaults_and_validation_contract():
    assert fields(m.ToolSpec) == ('tool_id', 'version', 'input_schema', 'output_schema',
        'risk', 'timeout_s', 'max_retries', 'idempotent', 'permissions', 'semantic_validator')
    spec = m.ToolSpec('sum', '1', 'input/v1', 'output/v1', m.ToolRisk.READ_ONLY)
    assert (spec.timeout_s, spec.max_retries, spec.idempotent, spec.permissions,
            spec.semantic_validator) == (60.0, 2, True, frozenset(), None)
    spec.validate()
    assert dataclasses.replace(spec, semantic_validator=lambda value: False) == spec
    assert 'semantic_validator' not in repr(spec)
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.tool_id = 'other'
    with pytest.raises(ValueError):
        dataclasses.replace(spec, tool_id='').validate()


def test_execution_observation_fields_and_frozen_contract():
    assert fields(m._ObservedToolExecution) == ('execution_id', 'execution_kind',
        'worker_pid', 'dispatcher_pid', 'input_sha256', 'review_target_sha256',
        'read_only_declared', 'registration_sha256')
    item = m._ObservedToolExecution('synthetic', 'in_process', 1, 1, 'a'*64, None, True)
    assert item.registration_sha256 is None
    with pytest.raises(dataclasses.FrozenInstanceError):
        item.execution_id = 'changed'


def test_receipt_fields_defaults_and_validation_contract():
    assert fields(m.ToolCallReceipt) == ('call_id', 'tool_id', 'tool_version', 'status',
        'attempts', 'latency_s', 'input_hash', 'output_hash', 'semantic_valid',
        'error_type', 'breaker_state', 'execution_observation', 'execution_liveness')
    item = m.ToolCallReceipt('call', 'sum', '1', 'COMPLETED', 1, 0.0, 'a'*64, 'b'*64, True)
    item.validate()
    assert (item.error_type, item.breaker_state, item.execution_observation,
            item.execution_liveness) == (None, m.BreakerState.CLOSED, None, {})
    other = dataclasses.replace(item)
    assert other.execution_liveness is item.execution_liveness  # dataclass replace is shallow
    fresh = m.ToolCallReceipt('call', 'sum', '1', 'COMPLETED', 1, 0.0, 'a'*64, 'b'*64, True)
    assert fresh.execution_liveness is not item.execution_liveness
    assert dataclasses.replace(item, execution_observation=object()) == item
    assert 'execution_observation' not in repr(item)
    with pytest.raises(dataclasses.FrozenInstanceError):
        item.status = 'FAILED'
    for changes in ({'attempts': 0}, {'status': 'unknown'}, {'input_hash': 'short'}):
        with pytest.raises(ValueError):
            dataclasses.replace(item, **changes).validate()


def test_health_fields_defaults_and_reliability_contract():
    assert fields(m.ToolHealth) == ('success_ewma', 'semantic_ewma', 'latency_ewma',
        'calls', 'consecutive_failures', 'breaker_state', 'opened_at', 'half_open_probe_in_flight')
    health = m.ToolHealth()
    assert dataclasses.asdict(health) == dict(success_ewma=1.0, semantic_ewma=1.0,
        latency_ewma=0.0, calls=0, consecutive_failures=0, breaker_state=m.BreakerState.CLOSED,
        opened_at=None, half_open_probe_in_flight=False)
    assert health.reliability == 1.0
    health.latency_ewma = 60.0
    assert health.reliability == pytest.approx(0.5**(1.0/3.0))
    health.success_ewma = 0.0
    assert health.reliability == 0.0
