"""Five finite synthetic callable scenarios; no external services or devices."""
from __future__ import annotations

import json

from opendot_engineering.tool_runtime import ToolRisk, ToolRuntime, ToolSpec


def contract(tool_id: str, **changes) -> ToolSpec:
    return ToolSpec(tool_id, '1', 'input/v1', 'output/v1', ToolRisk.READ_ONLY,
                    timeout_s=1.0, **changes)


def summary(runtime, tool_id, receipt):
    return {'status': receipt.status, 'attempts': receipt.attempts,
            'error_type': receipt.error_type,
            'retry_eligible': runtime.can_retry(tool_id, receipt)}


def run_demo():
    results = {'scope': 'SYNTHETIC_CALLABLES_ONLY'}
    runtime = ToolRuntime()
    runtime.register(contract('add'), lambda payload: payload['left'] + payload['right'])
    output, receipt = runtime.execute('add', {'left': 2, 'right': 3})
    assert output == 5 and receipt.status == 'COMPLETED' and receipt.attempts == 1
    results['success'] = {'output': output, **summary(runtime, 'add', receipt)}

    denied_calls = []
    runtime.register(contract('permission', permissions=frozenset({'example:read'})),
                     lambda payload: denied_calls.append(payload))
    _, receipt = runtime.execute('permission', {})
    assert not denied_calls and receipt.status == 'BLOCKED' and receipt.error_type == 'PermissionDenied'
    results['permission_refusal'] = summary(runtime, 'permission', receipt)

    retry_calls = []
    def succeeds_on_second_attempt(payload):
        retry_calls.append(1)
        if len(retry_calls) == 1:
            raise ValueError('synthetic ordinary handler failure')
        return payload['value'] * 2
    runtime.register(contract('retry', max_retries=1), succeeds_on_second_attempt)
    output, receipt = runtime.execute('retry', {'value': 4})
    assert output == 8 and receipt.attempts == len(retry_calls) == 2
    results['declared_idempotent_retry'] = {'output': output, **summary(runtime, 'retry', receipt)}

    failure_calls = []
    def fails_once(payload):
        failure_calls.append(1)
        raise ValueError('synthetic non-idempotent handler failure')
    runtime.register(contract('no_retry', idempotent=False, max_retries=5), fails_once)
    _, receipt = runtime.execute('no_retry', {})
    assert len(failure_calls) == receipt.attempts == 1 and not runtime.can_retry('no_retry', receipt)
    results['non_idempotent_failure'] = summary(runtime, 'no_retry', receipt)

    class ControlRefusal(RuntimeError):
        pass
    guarded_calls = []
    guarded = ToolRuntime(guarded_embedding=True, current_context_resolver=lambda: False,
                          control_error=ControlRefusal)
    guarded.register(contract('guarded'), lambda payload: guarded_calls.append(payload))
    try:
        guarded.execute('guarded', {})
    except ControlRefusal:
        assert not guarded_calls and guarded.health('guarded').calls == 0
        results['guard_refusal'] = {'exception': 'ControlRefusal', 'handler_calls': 0,
                                    'receipt_returned': False}
    else:
        raise AssertionError('all non-None context values must refuse dispatch')
    return results


if __name__ == '__main__':
    print(json.dumps(run_demo(), indent=2, sort_keys=True))
