"""Portable synthetic checks for the callable-only execution profile."""
from __future__ import annotations

import ast
import concurrent.futures
import contextvars
import dataclasses
import hashlib
import json
from pathlib import Path
import threading
import time
import uuid

import pytest

from opendot_engineering import tool_runtime as module
from opendot_engineering.tool_runtime import BreakerState, ToolRisk, ToolRuntime, ToolSpec

REAL_EXECUTOR = concurrent.futures.ThreadPoolExecutor


@pytest.fixture(autouse=True)
def joined_workers(monkeypatch):
    """All real executor workers are joined, including timed-out/lost-handle work."""
    pools = []

    class JoinedExecutor(REAL_EXECUTOR):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            pools.append(self)

    monkeypatch.setattr(module.concurrent.futures, 'ThreadPoolExecutor', JoinedExecutor)
    yield pools
    for pool in pools:
        pool.shutdown(wait=True, cancel_futures=True)
        assert all(not thread.is_alive() for thread in pool._threads)


def spec(**changes):
    return dataclasses.replace(ToolSpec('echo', '1', 'input/v1', 'output/v1', ToolRisk.READ_ONLY), **changes)


def opened(runtime):
    with runtime._lock:
        row = runtime._health['echo']
        row.breaker_state = BreakerState.OPEN
        row.opened_at = time.monotonic() - 10
        row.consecutive_failures = runtime.failure_threshold




def test_no_private_owner_imports_or_dispatch_protocol():
    source = Path(module.__file__).read_text()
    tree = ast.parse(source)
    assert not any(isinstance(node, ast.ImportFrom) and node.level for node in ast.walk(tree))
    for forbidden in ['CommandBackend', 'CommandCancellation', 'CommandOutcomeUnknown', 'JobContext', 'JobRuntime',
                      'provider_adapters', '_dispatch_binding', 'tool-dispatch', 'begin_tool_execution',
                      'end_tool_execution', 'unresolved_tool_execution', 'dispatch_checkpoint', 'run_bound']:
        assert forbidden not in source


@pytest.mark.parametrize('changes', [
    {'timeout_s': True}, {'timeout_s': 0}, {'timeout_s': -1}, {'timeout_s': float('nan')},
    {'timeout_s': float('inf')}, {'timeout_s': '1'}, {'max_retries': True}, {'max_retries': -1},
    {'max_retries': 1.0}, {'permissions': iter(['read'])}, {'permissions': ['']},
    {'permissions': [1]}, {'idempotent': 1}, {'risk': ToolRisk.IRREVERSIBLE_WRITE},
])
def test_source_spec_validation(changes):
    with pytest.raises(ValueError):
        spec(**changes).validate()


@pytest.mark.parametrize('changes', [
    {'failure_threshold': True}, {'failure_threshold': 1.0}, {'failure_threshold': 0},
    {'recovery_timeout_s': float('nan')}, {'recovery_timeout_s': float('inf')},
    {'recovery_timeout_s': True}, {'ewma_alpha': float('nan')}, {'ewma_alpha': 0},
])
def test_runtime_policy_is_finite(changes):
    with pytest.raises(ValueError):
        ToolRuntime(**changes)


def test_backend_registration_is_explicitly_unsupported():
    runtime = ToolRuntime()
    with pytest.raises(NotImplementedError, match='Unsupported'):
        runtime.register_backend(spec(), lambda payload: payload)
    assert runtime._specs == runtime._handlers == runtime._health == {}
    with pytest.raises(TypeError):
        runtime.register(spec(), object())


def test_registration_snapshots_permissions_and_signature():
    permissions = {'read'}
    runtime = ToolRuntime()
    runtime.register(spec(permissions=permissions), lambda payload: payload)
    signature = runtime.registration_signature('echo')
    permissions.add('write')
    assert runtime.registration_signature('echo') == signature
    output, receipt = runtime.execute('echo', {'x': [1]}, granted_permissions=frozenset({'read'}))
    assert output == {'x': [1]}
    assert receipt.status == 'COMPLETED'
    assert receipt.execution_observation.registration_sha256 == signature
    assert receipt.execution_observation.input_sha256 == receipt.input_hash
    assert runtime.replay_safety_signature('echo') == signature
    assert runtime.health('echo').calls == 1
    assert runtime.health('echo').reliability > 0
    assert runtime.registration_signature('missing') is None
    with pytest.raises(ValueError):
        runtime.register(spec(), lambda payload: payload)
    with pytest.raises(LookupError):
        runtime.execute('missing', {})


def test_permissions_and_irreversible_approval():
    runtime = ToolRuntime()
    runtime.register(spec(permissions={'read'}), lambda payload: payload)
    _, receipt = runtime.execute('echo', {})
    assert (receipt.status, receipt.error_type) == ('BLOCKED', 'PermissionDenied')
    assert runtime.health('echo').calls == 0
    runtime = ToolRuntime()
    runtime.register(spec(risk=ToolRisk.IRREVERSIBLE_WRITE, idempotent=False), lambda payload: 1)
    _, receipt = runtime.execute('echo', {})
    assert (receipt.status, receipt.error_type) == ('BLOCKED', 'ApprovalRequired')
    output, receipt = runtime.execute('echo', {}, approval_token='synthetic-approval')
    assert output == 1 and receipt.status == 'COMPLETED'
    assert runtime.replay_safety_signature('echo') is None


def test_retry_payload_is_detached_and_execution_ids_are_distinct(monkeypatch):
    runtime = ToolRuntime()
    seen = []
    execution_ids = []

    def handler(payload):
        seen.append(list(payload['items']))
        payload['items'].append('handler mutation')
        if len(seen) < 3:
            raise ValueError('synthetic failure')
        return 'ok'

    runtime.register(spec(), handler)
    dispatch = runtime._dispatch

    def record_dispatch(*args, **kwargs):
        execution_ids.append(kwargs['execution_id'])
        return dispatch(*args, **kwargs)

    monkeypatch.setattr(runtime, '_dispatch', record_dispatch)
    original = {'items': ['original']}
    output, receipt = runtime.execute('echo', original)
    assert output == 'ok' and receipt.attempts == 3
    assert original == {'items': ['original']}
    assert seen == [['original']] * 3
    assert len(set(execution_ids)) == 3
    assert all(uuid.UUID(value).hex == value for value in execution_ids)
    assert len(receipt.call_id) == 24 and receipt.call_id not in execution_ids
    assert receipt.input_hash == runtime._hash_json(original)
    assert receipt.output_hash == runtime._hash_json('ok')


def test_nonidempotent_is_not_retried():
    runtime = ToolRuntime()
    calls = []

    def fail(payload):
        calls.append(payload)
        raise ValueError('synthetic failure')

    runtime.register(spec(idempotent=False), fail)
    _, receipt = runtime.execute('echo', {})
    assert receipt.attempts == len(calls) == 1
    assert not runtime.can_retry('echo', receipt)


def test_semantic_failure_is_retried_and_counted():
    runtime = ToolRuntime()
    runtime.register(spec(semantic_validator=lambda output: False), lambda payload: 'invalid')
    _, receipt = runtime.execute('echo', {})
    assert receipt.status == 'FAILED' and receipt.attempts == 3
    assert runtime.health('echo').calls == 3
    assert runtime.can_retry('echo', receipt)


class ControlError(RuntimeError):
    pass


class ControlChild(ControlError):
    pass


def guarded(resolver, **kwargs):
    return ToolRuntime(guarded_embedding=True, current_context_resolver=resolver, control_error=ControlError, **kwargs)


@pytest.mark.parametrize('value', [False, 0, '', {}, [], object()])
def test_any_nonnull_context_denies_before_payload_and_health(value):
    runtime = guarded(lambda: value, recovery_timeout_s=0)
    runtime.register(spec(), lambda payload: pytest.fail('handler must not run'))
    opened(runtime)
    before = runtime.health('echo')

    class Poison(dict):
        def __deepcopy__(self, memo):
            pytest.fail('denied entry must not copy payload')

    with pytest.raises(ControlError):
        runtime.execute('echo', Poison())
    assert runtime.health('echo') == before
    assert not runtime._probe_owners


@pytest.mark.parametrize('kwargs', [
    {'guarded_embedding': True},
    {'guarded_embedding': True, 'current_context_resolver': lambda: None},
    {'guarded_embedding': True, 'current_context_resolver': 1, 'control_error': ControlError},
    {'guarded_embedding': True, 'current_context_resolver': lambda: None, 'control_error': 'ControlError'},
    {'guarded_embedding': True, 'current_context_resolver': lambda: None, 'control_error': Exception},
    {'current_context_resolver': lambda: None, 'control_error': ControlError},
    {'guarded_embedding': 1},
])
def test_guard_never_silently_falls_back(kwargs):
    with pytest.raises(ValueError):
        ToolRuntime(**kwargs)


def test_guard_binding_is_captured_and_immutable():
    class Owner:
        def current(self):
            return None

    owner = Owner()
    runtime = guarded(owner.current)
    owner.current = lambda: object()
    runtime.register(spec(), lambda payload: 1)
    assert runtime.execute('echo', {})[0] == 1
    with pytest.raises(AttributeError):
        runtime._guard_binding = None
    with pytest.raises(AttributeError):
        del runtime._guard_binding
    with pytest.raises(dataclasses.FrozenInstanceError):
        runtime._guard_binding.current_context = lambda: None


def test_resolver_failure_is_terminal_and_preserves_cause():
    failure = ValueError('resolver unavailable')

    def resolver():
        raise failure

    runtime = guarded(resolver)
    runtime.register(spec(), lambda payload: pytest.fail('handler must not run'))
    with pytest.raises(ControlError) as info:
        runtime.execute('echo', {})
    assert info.value.__cause__ is failure
    assert runtime.health('echo').calls == 0


def test_worker_guard_runs_inside_actual_copied_context_and_releases_probe():
    ambient = contextvars.ContextVar('synthetic_context', default=None)
    calls = []

    def resolver():
        calls.append((threading.get_ident(), ambient.get()))
        return ambient.get()

    runtime = guarded(resolver, recovery_timeout_s=0)
    runtime.register(spec(), lambda payload: pytest.fail('worker fence must deny'))
    opened(runtime)

    class SetAmbient(dict):
        def __deepcopy__(self, memo):
            ambient.set(False)
            return {}

    token = ambient.set(None)
    try:
        with pytest.raises(ControlError):
            runtime.execute('echo', SetAmbient())
    finally:
        ambient.reset(token)
    assert len(calls) == 2
    assert calls[0] == (threading.get_ident(), None)
    assert calls[1][0] != threading.get_ident() and calls[1][1] is False
    assert runtime.health('echo').calls == 0
    assert runtime.health('echo').breaker_state == BreakerState.HALF_OPEN
    assert not runtime.health('echo').half_open_probe_in_flight
    assert not runtime._probe_owners


def test_standalone_preserves_unknown_context_without_claiming_detection():
    ambient = contextvars.ContextVar('unknown_to_runtime', default=None)
    token = ambient.set('synthetic marker')
    runtime = ToolRuntime()
    runtime.register(spec(), lambda payload: ambient.get())
    try:
        assert runtime.execute('echo', {})[0] == 'synthetic marker'
    finally:
        ambient.reset(token)


def test_exact_control_error_family_propagates_identity_without_retry():
    failure = ControlChild('stop')
    calls = []

    def handler(payload):
        calls.append(1)
        raise failure

    runtime = guarded(lambda: None, recovery_timeout_s=0)
    runtime.register(spec(), handler)
    opened(runtime)
    with pytest.raises(ControlChild) as info:
        runtime.execute('echo', {})
    assert info.value is failure and calls == [1]
    assert runtime.health('echo').calls == 0
    assert not runtime.health('echo').half_open_probe_in_flight
    assert not runtime._probe_owners


def test_matching_error_name_is_not_authority():
    Impostor = type('ControlError', (RuntimeError,), {})
    runtime = guarded(lambda: None)

    def handler(payload):
        raise Impostor('ordinary tool failure')

    runtime.register(spec(), handler)
    _, receipt = runtime.execute('echo', {})
    assert receipt.status == 'FAILED' and receipt.attempts == 3


def test_control_timeout_subclass_is_not_translated_to_timeout_receipt():
    class ControlTimeout(TimeoutError):
        pass

    failure = ControlTimeout('control deadline')
    runtime = ToolRuntime(guarded_embedding=True, current_context_resolver=lambda: None, control_error=ControlTimeout)

    def handler(payload):
        raise failure

    runtime.register(spec(), handler)
    with pytest.raises(ControlTimeout) as info:
        runtime.execute('echo', {})
    assert info.value is failure and runtime.health('echo').calls == 0


@pytest.mark.parametrize('value', [True, False, 0, -1, 1.0, 1.5, '1', float('inf'), float('nan'), object()])
def test_invalid_attempt_limit_cannot_strand_or_admit_probe(value):
    runtime = ToolRuntime(recovery_timeout_s=0)
    runtime.register(spec(), lambda payload: pytest.fail('handler must not run'))
    opened(runtime)
    before = runtime.health('echo')
    with pytest.raises(ValueError):
        runtime.execute('echo', {}, attempt_limit=value)
    assert runtime.health('echo') == before and not runtime._probe_owners


def test_int_subclass_attempt_limit_is_rejected():
    class IntSubclass(int):
        pass

    runtime = ToolRuntime()
    runtime.register(spec(), lambda payload: 1)
    with pytest.raises(ValueError):
        runtime.execute('echo', {}, attempt_limit=IntSubclass(1))


def test_computed_attempt_count_is_validated_before_admission():
    class WeirdRetry(int):
        def __radd__(self, value):
            return 1.5

    runtime = ToolRuntime(recovery_timeout_s=0)
    runtime.register(spec(max_retries=WeirdRetry(1)), lambda payload: pytest.fail('handler must not run'))
    opened(runtime)
    before = runtime.health('echo')
    with pytest.raises(ValueError, match='computed attempt count'):
        runtime.execute('echo', {})
    assert runtime.health('echo') == before and not runtime._probe_owners


@pytest.mark.parametrize('value', [float('inf'), float('nan'), -1, True, '1'])
def test_invalid_backoff_is_rejected_before_admission(value):
    runtime = ToolRuntime(recovery_timeout_s=0)
    runtime.register(spec(), lambda payload: 1)
    opened(runtime)
    before = runtime.health('echo')
    with pytest.raises(ValueError):
        runtime.execute('echo', {}, backoff_base_s=value)
    assert runtime.health('echo') == before


def test_probe_retirement_and_stale_settlement_preserve_new_owner():
    runtime = ToolRuntime(failure_threshold=1, recovery_timeout_s=0)
    runtime.register(spec(), lambda payload: 1)
    opened(runtime)
    old, new = object(), object()
    with runtime._lock:
        assert runtime._allow_call('echo', old)
        assert not runtime._allow_call('echo', object())
        runtime._update_health('echo', success=False, semantic_valid=False, latency_s=0, probe_token=old, generation=1)
        assert 'echo' not in runtime._probe_owners
        assert runtime._allow_call('echo', new)
        runtime._release_probe('echo', old)
        runtime._update_health('echo', success=True, semantic_valid=True, latency_s=0, probe_token=old, generation=1)
        runtime._update_health('echo', success=True, semantic_valid=True, latency_s=0, probe_token=None, generation=0)
        assert runtime._probe_owners['echo'] is new
        assert runtime._health['echo'].half_open_probe_in_flight
        assert runtime._health['echo'].breaker_state == BreakerState.HALF_OPEN
        runtime._update_health('echo', success=True, semantic_valid=True, latency_s=0, probe_token=new, generation=2)
    assert runtime.health('echo').breaker_state == BreakerState.CLOSED
    assert not runtime.health('echo').half_open_probe_in_flight and not runtime._probe_owners


def test_old_exceptional_cleanup_cannot_clear_concurrent_new_probe(monkeypatch):
    runtime = ToolRuntime(failure_threshold=1, recovery_timeout_s=0)
    old_at_receipt, release_old, new_running, release_new = [threading.Event() for _ in range(4)]
    count = 0
    count_lock = threading.Lock()
    results, errors = [], []

    def handler(payload):
        nonlocal count
        with count_lock:
            count += 1
            number = count
        if number == 1:
            raise ValueError('first probe failed')
        new_running.set()
        assert release_new.wait(2)
        return 1

    original_validate = module.ToolCallReceipt.validate

    def validate(receipt):
        if receipt.status == 'FAILED':
            old_at_receipt.set()
            assert release_old.wait(2)
            raise RuntimeError('synthetic receipt unwind after probe retirement')
        return original_validate(receipt)

    monkeypatch.setattr(module.ToolCallReceipt, 'validate', validate)
    runtime.register(spec(max_retries=0), handler)
    opened(runtime)

    def run():
        try:
            results.append(runtime.execute('echo', {}))
        except BaseException as exc:
            errors.append(exc)

    old = threading.Thread(target=run)
    new = threading.Thread(target=run)
    old.start()
    try:
        assert old_at_receipt.wait(2)
        new.start()
        assert new_running.wait(2)
        release_old.set()
        old.join(2)
        assert not old.is_alive()
        assert runtime.health('echo').half_open_probe_in_flight
        assert runtime.health('echo').breaker_state == BreakerState.HALF_OPEN
    finally:
        release_old.set()
        release_new.set()
        old.join(3)
        if new.ident is not None:
            new.join(3)
    assert not old.is_alive() and not new.is_alive()
    assert len(errors) == 1 and isinstance(errors[0], RuntimeError)
    assert len(results) == 1 and results[0][1].status == 'COMPLETED'
    assert not runtime._probe_owners


def test_baseexception_unwind_releases_own_probe():
    class Stop(BaseException):
        pass

    runtime = ToolRuntime(recovery_timeout_s=0)

    def handler(payload):
        raise Stop()

    runtime.register(spec(), handler)
    opened(runtime)
    with pytest.raises(Stop):
        runtime.execute('echo', {})
    assert runtime.health('echo').calls == 0
    assert not runtime.health('echo').half_open_probe_in_flight and not runtime._probe_owners


def test_timeout_preserves_unknown_liveness_and_does_not_retry():
    entered, release = threading.Event(), threading.Event()
    calls = []

    def handler(payload):
        calls.append(1)
        entered.set()
        assert release.wait(2)
        return 'late result'

    runtime = ToolRuntime()
    runtime.register(spec(timeout_s=0.05), handler)
    try:
        _, receipt = runtime.execute('echo', {})
        assert entered.is_set() and calls == [1]
        assert receipt.status == 'FAILED' and receipt.error_type == 'TimeoutError'
        assert receipt.attempts == 1 and not runtime.can_retry('echo', receipt)
        assert receipt.execution_liveness['reconciliation_required'] is True
        assert receipt.execution_liveness['termination_observed'] is False
        assert receipt.execution_liveness['termination_scope'] == 'in_process_handler'
        assert receipt.execution_liveness['descendant_termination_observed'] is False
        assert uuid.UUID(receipt.execution_liveness['execution_id'])
    finally:
        release.set()


def test_handler_timeout_is_conservatively_not_retried():
    runtime = ToolRuntime()

    def handler(payload):
        raise TimeoutError('synthetic handler timeout')

    runtime.register(spec(), handler)
    _, receipt = runtime.execute('echo', {})
    assert receipt.attempts == 1 and receipt.error_type == 'TimeoutError'
    assert receipt.execution_liveness['reconciliation_required'] is True
    assert receipt.execution_liveness['descendant_termination_observed'] is False


def test_preparation_exhaustion_is_not_started_and_not_retried():
    runtime = ToolRuntime()
    runtime.register(spec(timeout_s=0.005), lambda payload: pytest.fail('must not start'))

    class SlowCopy(dict):
        def __deepcopy__(self, memo):
            time.sleep(0.02)
            return {}

    _, receipt = runtime.execute('echo', SlowCopy())
    assert receipt.attempts == 1 and receipt.error_type == 'TimeoutError'
    assert receipt.execution_liveness['dispatch_started'] is False
    assert receipt.execution_liveness['termination_scope'] == 'not_started'
    assert receipt.execution_liveness['reconciliation_required'] is False
    assert not runtime.can_retry('echo', receipt)


def test_lost_submit_handle_keeps_completion_future_and_unknown(monkeypatch, joined_workers):
    entered, release = threading.Event(), threading.Event()
    captured_completion = []
    base = module.concurrent.futures.ThreadPoolExecutor

    class LostHandleExecutor(base):
        def submit(self, function, wrapper):
            closure = dict(zip(wrapper.__code__.co_freevars, [cell.cell_contents for cell in wrapper.__closure__]))
            captured_completion.append(closure['completion'])
            super().submit(function, wrapper)
            assert entered.wait(2)
            raise RuntimeError('synthetic lost return handle')

    monkeypatch.setattr(module.concurrent.futures, 'ThreadPoolExecutor', LostHandleExecutor)
    calls = []

    def handler(payload):
        calls.append(1)
        entered.set()
        assert release.wait(2)
        return 1

    runtime = ToolRuntime()
    runtime.register(spec(), handler)
    try:
        _, receipt = runtime.execute('echo', {})
        assert receipt.status == 'FAILED' and receipt.attempts == 1 and calls == [1]
        assert receipt.execution_liveness['submission_entered'] is True
        assert receipt.execution_liveness['return_handle_observed'] is False
        assert receipt.execution_liveness['termination_observed'] is False
        assert receipt.execution_liveness['reconciliation_required'] is True
        assert not runtime.can_retry('echo', receipt)
        assert not captured_completion[0].done()
    finally:
        release.set()
    assert captured_completion[0].result(timeout=2)[0] == 1
    assert receipt.execution_liveness['reconciliation_required'] is True


def test_submit_failure_without_observed_handle_remains_unknown(monkeypatch):
    base = module.concurrent.futures.ThreadPoolExecutor

    class NeverSubmitted(base):
        def submit(self, *args, **kwargs):
            raise RuntimeError('submission outcome unknown to caller')

    monkeypatch.setattr(module.concurrent.futures, 'ThreadPoolExecutor', NeverSubmitted)
    runtime = ToolRuntime()
    runtime.register(spec(), lambda payload: pytest.fail('not submitted'))
    _, receipt = runtime.execute('echo', {})
    assert receipt.attempts == 1
    assert receipt.execution_liveness['return_handle_observed'] is False
    assert receipt.execution_liveness['reconciliation_required'] is True


def test_interrupted_wait_is_unknown_and_not_retried(monkeypatch):
    entered, release = threading.Event(), threading.Event()
    base = module.concurrent.futures.ThreadPoolExecutor

    class InterruptedFuture:
        def __init__(self, future):
            self.future = future

        def result(self, timeout):
            assert entered.wait(2)
            raise RuntimeError('synthetic wait interruption')

        def done(self):
            return self.future.done()

    class InterruptedExecutor(base):
        def submit(self, *args, **kwargs):
            return InterruptedFuture(super().submit(*args, **kwargs))

    monkeypatch.setattr(module.concurrent.futures, 'ThreadPoolExecutor', InterruptedExecutor)

    def handler(payload):
        entered.set()
        assert release.wait(2)
        return 1

    runtime = ToolRuntime()
    runtime.register(spec(), handler)
    try:
        _, receipt = runtime.execute('echo', {})
        assert receipt.attempts == 1 and receipt.execution_liveness['reconciliation_required'] is True
        assert receipt.execution_liveness['return_handle_observed'] is True
        assert receipt.execution_liveness['termination_observed'] is False
    finally:
        release.set()


def test_half_open_retry_success_keeps_settlement_authority_until_superseded():
    runtime = ToolRuntime(failure_threshold=1, recovery_timeout_s=0)
    calls = []

    def handler(payload):
        calls.append(1)
        if len(calls) == 1:
            raise ValueError('retryable probe failure')
        return 1

    runtime.register(spec(max_retries=1), handler)
    opened(runtime)
    output, receipt = runtime.execute('echo', {})
    assert output == 1 and receipt.status == 'COMPLETED' and receipt.attempts == 2
    assert receipt.breaker_state == BreakerState.CLOSED
    assert runtime.health('echo').breaker_state == BreakerState.CLOSED
    assert not runtime._probe_owners


def test_stale_closed_call_cannot_override_settled_newer_probe():
    runtime = ToolRuntime(failure_threshold=1, recovery_timeout_s=0)
    runtime.register(spec(), lambda payload: 1)
    old, probe = object(), object()
    with runtime._lock:
        assert runtime._allow_call('echo', old)
        old_generation = runtime._health_generations['echo']
        runtime._update_health('echo', success=False, semantic_valid=False, latency_s=0,
                               probe_token=None, generation=old_generation)
        assert runtime._allow_call('echo', probe)
        new_generation = runtime._health_generations['echo']
        runtime._update_health('echo', success=False, semantic_valid=False, latency_s=0,
                               probe_token=probe, generation=new_generation)
        assert 'echo' not in runtime._probe_owners
        assert runtime._health['echo'].breaker_state == BreakerState.OPEN
        runtime._update_health('echo', success=True, semantic_valid=True, latency_s=0,
                               probe_token=None, generation=old_generation)
        assert runtime._health['echo'].breaker_state == BreakerState.OPEN
        assert runtime._health['echo'].consecutive_failures == 2


def test_retry_settlement_cannot_override_newer_settled_probe():
    runtime = ToolRuntime(failure_threshold=1, recovery_timeout_s=0)
    runtime.register(spec(), lambda payload: 1)
    opened(runtime)
    old, new = object(), object()
    with runtime._lock:
        assert runtime._allow_call('echo', old)
        runtime._update_health('echo', success=False, semantic_valid=False, latency_s=0,
                               probe_token=old, generation=1)
        assert runtime._allow_call('echo', new)
        runtime._update_health('echo', success=False, semantic_valid=False, latency_s=0,
                               probe_token=new, generation=2)
        assert 'echo' not in runtime._probe_owners
        runtime._update_health('echo', success=True, semantic_valid=True, latency_s=0,
                               probe_token=old, generation=1)
        assert runtime._health['echo'].breaker_state == BreakerState.OPEN


def test_handler_and_spec_snapshot_survive_preparation_mutation():
    runtime = ToolRuntime()
    runtime.register(spec(), lambda payload: 'captured handler')
    signature = runtime.registration_signature('echo')

    class ChangeRegistry(dict):
        def __deepcopy__(self, memo):
            with runtime._lock:
                runtime._handlers['echo'] = lambda payload: 'late replacement'
                runtime._specs['echo'] = spec(version='2')
            return {}

    output, receipt = runtime.execute('echo', ChangeRegistry())
    assert output == 'captured handler'
    assert receipt.tool_version == '1'
    assert receipt.execution_observation.registration_sha256 == signature


def test_semantic_control_error_is_not_counted_or_retried():
    failure = ControlChild('semantic control stop')
    calls = []

    def validator(output):
        raise failure

    def handler(payload):
        calls.append(1)
        return 1

    runtime = guarded(lambda: None)
    runtime.register(spec(semantic_validator=validator), handler)
    with pytest.raises(ControlChild) as info:
        runtime.execute('echo', {})
    assert info.value is failure and calls == [1]
    assert runtime.health('echo').calls == 0


def test_rejected_payload_copy_leaves_breaker_unadmitted():
    runtime = ToolRuntime(recovery_timeout_s=0)
    runtime.register(spec(), lambda payload: pytest.fail('must not dispatch'))
    opened(runtime)
    before = runtime.health('echo')

    class BadCopy(dict):
        def __deepcopy__(self, memo):
            raise ValueError('synthetic copy failure')

    with pytest.raises(ValueError, match='synthetic copy failure'):
        runtime.execute('echo', BadCopy())
    assert runtime.health('echo') == before and not runtime._probe_owners


def test_result_delivery_interruption_after_success_is_unknown(monkeypatch):
    calls = []
    base = module.concurrent.futures.ThreadPoolExecutor

    class InterruptedHandle:
        def __init__(self, future):
            self.future = future

        def result(self, timeout):
            self.future.result(timeout=timeout)
            raise RuntimeError('synthetic result delivery interruption after success')

        def done(self):
            return self.future.done()

    class InterruptedExecutor(base):
        def submit(self, *args, **kwargs):
            return InterruptedHandle(super().submit(*args, **kwargs))

    monkeypatch.setattr(module.concurrent.futures, 'ThreadPoolExecutor', InterruptedExecutor)
    runtime = ToolRuntime()
    runtime.register(spec(), lambda payload: calls.append(1) or 7)
    _, receipt = runtime.execute('echo', {})
    assert calls == [1] and receipt.attempts == 1
    assert receipt.execution_liveness['reconciliation_required'] is True
    assert receipt.execution_liveness['return_handle_observed'] is True
    assert receipt.execution_liveness['descendant_termination_observed'] is False
    assert not runtime.can_retry('echo', receipt)


@pytest.mark.parametrize('handler_fails', [False, True])
def test_real_future_wait_interruption_after_completion_is_unknown(monkeypatch, handler_fails):
    """Real stdlib Future/result; bounded injection only into condition.wait."""
    calls, observed, gates = [], [], []
    failure = ValueError('actual handler failure')
    base = module.concurrent.futures.ThreadPoolExecutor

    class InterruptedExecutor(base):
        def submit(self, function, *args, **kwargs):
            gate = threading.Event()
            gates.append(gate)

            def gated_dispatch():
                assert gate.wait(2)
                return function(*args, **kwargs)

            future = super().submit(gated_dispatch)
            assert type(future) is concurrent.futures.Future
            normal_wait = future._condition.wait

            def interrupted_wait(timeout=None):
                gate.set()
                normal_wait(timeout)
                observed.append((future.done(), future.exception(timeout=0)))
                raise RuntimeError('synthetic wait interruption after completion notification')

            future._condition.wait = interrupted_wait
            return future

    def handler(payload):
        calls.append(1)
        if handler_fails:
            raise failure
        return 7

    monkeypatch.setattr(module.concurrent.futures, 'ThreadPoolExecutor', InterruptedExecutor)
    runtime = ToolRuntime()
    runtime.register(spec(), handler)
    try:
        _, receipt = runtime.execute('echo', {})
        assert calls == [1] and receipt.attempts == 1
        assert observed == [(True, failure if handler_fails else None)]
        assert receipt.execution_liveness['reconciliation_required'] is True
        assert not runtime.can_retry('echo', receipt)
    finally:
        for gate in gates:
            gate.set()


def test_result_exception_type_and_text_cannot_impersonate_dispatch_exception(monkeypatch):
    calls = []
    failure = ValueError('same error text')
    base = module.concurrent.futures.ThreadPoolExecutor

    class InterruptedHandle:
        def __init__(self, future):
            self.future = future

        def result(self, timeout):
            try:
                return self.future.result(timeout=timeout)
            except ValueError:
                raise ValueError('same error text') from None

        def done(self):
            return self.future.done()

    class InterruptedExecutor(base):
        def submit(self, *args, **kwargs):
            return InterruptedHandle(super().submit(*args, **kwargs))

    def handler(payload):
        calls.append(1)
        raise failure

    monkeypatch.setattr(module.concurrent.futures, 'ThreadPoolExecutor', InterruptedExecutor)
    runtime = ToolRuntime()
    runtime.register(spec(), handler)
    _, receipt = runtime.execute('echo', {})
    assert calls == [1] and receipt.attempts == 1
    assert receipt.execution_liveness['reconciliation_required'] is True
    assert not runtime.can_retry('echo', receipt)


def test_cancelled_return_handle_without_dispatch_observation_remains_unknown(monkeypatch):
    base = module.concurrent.futures.ThreadPoolExecutor

    class CancelledExecutor(base):
        def submit(self, *args, **kwargs):
            future = concurrent.futures.Future()
            assert future.cancel()
            return future

    monkeypatch.setattr(module.concurrent.futures, 'ThreadPoolExecutor', CancelledExecutor)
    runtime = ToolRuntime()
    runtime.register(spec(), lambda payload: pytest.fail('never dispatched'))
    _, receipt = runtime.execute('echo', {})
    assert receipt.attempts == 1 and receipt.error_type == 'CancelledError'
    assert receipt.execution_liveness['reconciliation_required'] is True
    assert not runtime.can_retry('echo', receipt)


@pytest.fixture
def interrupted_shutdown(monkeypatch):
    base = module.concurrent.futures.ThreadPoolExecutor

    class InterruptedShutdown(base):
        def shutdown(self, wait=True, *, cancel_futures=False):
            super().shutdown(wait=wait, cancel_futures=cancel_futures)
            if not wait:
                raise RuntimeError('synthetic executor cleanup interruption')

    monkeypatch.setattr(module.concurrent.futures, 'ThreadPoolExecutor', InterruptedShutdown)


def test_shutdown_failure_preserves_exact_primary_control_error(interrupted_shutdown):
    failure = ControlChild('original canonical refusal')
    calls = []

    def handler(payload):
        calls.append(1)
        raise failure

    runtime = guarded(lambda: None, recovery_timeout_s=0)
    runtime.register(spec(), handler)
    opened(runtime)
    with pytest.raises(ControlChild) as info:
        runtime.execute('echo', {})
    assert info.value is failure and calls == [1]
    assert runtime.health('echo').calls == 0 and not runtime._probe_owners


@pytest.mark.parametrize('handler_fails', [False, True])
def test_shutdown_failure_never_retries_observed_dispatch(interrupted_shutdown, handler_fails):
    calls = []

    def handler(payload):
        calls.append(1)
        if handler_fails:
            raise ValueError('observed handler failure')
        return 7

    runtime = ToolRuntime()
    runtime.register(spec(), handler)
    _, receipt = runtime.execute('echo', {})
    assert calls == [1] and receipt.status == 'FAILED' and receipt.attempts == 1
    assert receipt.error_type == ('ValueError' if handler_fails else 'RuntimeError')
    assert receipt.execution_liveness['cleanup_error_type'] == 'RuntimeError'
    assert receipt.execution_liveness['reconciliation_required'] is True
    assert not runtime.can_retry('echo', receipt)


def test_shutdown_failure_cannot_replace_baseexception(interrupted_shutdown):
    class Halt(BaseException):
        pass

    failure = Halt('stop')
    runtime = ToolRuntime(recovery_timeout_s=0)

    def handler(payload):
        raise failure

    runtime.register(spec(), handler)
    opened(runtime)
    with pytest.raises(Halt) as info:
        runtime.execute('echo', {})
    assert info.value is failure
    assert runtime.health('echo').calls == 0 and not runtime._probe_owners


def test_canonical_cleanup_error_is_terminal_and_propagates_identity(monkeypatch):
    failure = ControlChild('cleanup control stop')
    base = module.concurrent.futures.ThreadPoolExecutor

    class ControlShutdown(base):
        def shutdown(self, wait=True, *, cancel_futures=False):
            super().shutdown(wait=wait, cancel_futures=cancel_futures)
            if not wait:
                raise failure

    monkeypatch.setattr(module.concurrent.futures, 'ThreadPoolExecutor', ControlShutdown)
    calls = []
    runtime = guarded(lambda: None)
    runtime.register(spec(), lambda payload: calls.append(1) or 7)
    with pytest.raises(ControlChild) as info:
        runtime.execute('echo', {})
    assert info.value is failure and calls == [1]
    assert runtime.health('echo').calls == 0


def test_timeout_liveness_survives_cleanup_failure(interrupted_shutdown):
    entered, release = threading.Event(), threading.Event()
    calls = []

    def handler(payload):
        calls.append(1)
        entered.set()
        assert release.wait(2)
        return 7

    runtime = ToolRuntime()
    runtime.register(spec(timeout_s=0.03), handler)
    try:
        _, receipt = runtime.execute('echo', {})
        assert entered.is_set() and calls == [1] and receipt.attempts == 1
        assert receipt.error_type == 'TimeoutError'
        assert receipt.execution_liveness['timed_out'] is True
        assert receipt.execution_liveness['termination_observed'] is False
        assert receipt.execution_liveness['reconciliation_required'] is True
        assert receipt.execution_liveness['cleanup_error_type'] == 'RuntimeError'
        assert not runtime.can_retry('echo', receipt)
    finally:
        release.set()


@pytest.mark.parametrize('primary_kind', ['control', 'ordinary', 'base'])
def test_cleanup_control_exception_precedence_never_produces_retry(monkeypatch, primary_kind):
    class Halt(BaseException):
        pass

    primary = {'control': ControlChild('primary control'), 'ordinary': ValueError('primary failure'),
               'base': Halt('primary halt')}[primary_kind]
    cleanup = ControlChild('cleanup control')
    base = module.concurrent.futures.ThreadPoolExecutor

    class ControlShutdown(base):
        def shutdown(self, wait=True, *, cancel_futures=False):
            super().shutdown(wait=wait, cancel_futures=cancel_futures)
            if not wait:
                raise cleanup

    monkeypatch.setattr(module.concurrent.futures, 'ThreadPoolExecutor', ControlShutdown)
    calls = []

    def handler(payload):
        calls.append(1)
        raise primary

    runtime = guarded(lambda: None)
    runtime.register(spec(), handler)
    expected = primary if primary_kind in {'control', 'base'} else cleanup
    with pytest.raises(type(expected)) as info:
        runtime.execute('echo', {})
    assert info.value is expected
    assert calls == [1] and runtime.health('echo').calls == 0


@pytest.mark.parametrize('broken_observation', ['cancel', 'done'])
def test_timeout_observation_failure_cannot_erase_no_retry_liveness(monkeypatch, broken_observation):
    entered, release = threading.Event(), threading.Event()
    calls = []
    base = module.concurrent.futures.ThreadPoolExecutor

    class BrokenObservationHandle:
        def __init__(self, future):
            self.future = future

        def result(self, timeout):
            return self.future.result(timeout=timeout)

        def cancel(self):
            if broken_observation == 'cancel':
                raise RuntimeError('synthetic cancellation observation failure')
            return self.future.cancel()

        def done(self):
            if broken_observation == 'done':
                raise RuntimeError('synthetic completion observation failure')
            return self.future.done()

    class BrokenObservationExecutor(base):
        def submit(self, *args, **kwargs):
            return BrokenObservationHandle(super().submit(*args, **kwargs))

    def handler(payload):
        calls.append(1)
        entered.set()
        assert release.wait(2)
        return 7

    monkeypatch.setattr(module.concurrent.futures, 'ThreadPoolExecutor', BrokenObservationExecutor)
    runtime = ToolRuntime()
    runtime.register(spec(timeout_s=0.03), handler)
    try:
        _, receipt = runtime.execute('echo', {})
        assert entered.is_set() and calls == [1] and receipt.attempts == 1
        assert receipt.error_type == 'TimeoutError'
        assert receipt.execution_liveness['timed_out'] is True
        assert receipt.execution_liveness['termination_observed'] is False
        assert receipt.execution_liveness['observation_error_type'] == 'RuntimeError'
        assert receipt.execution_liveness['reconciliation_required'] is True
        assert not runtime.can_retry('echo', receipt)
    finally:
        release.set()
