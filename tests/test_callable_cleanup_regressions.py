from __future__ import annotations
import concurrent.futures
import threading
import pytest
from opendot_engineering import tool_runtime as m

REAL_EXECUTOR=concurrent.futures.ThreadPoolExecutor
class ControlError(RuntimeError): pass
class ChildControl(ControlError): pass

@pytest.fixture
def throwing_shutdown(monkeypatch):
    pools=[]
    class ThrowsAfterCleanup(REAL_EXECUTOR):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs);pools.append(self)
        def shutdown(self,wait=True,*,cancel_futures=False):
            super().shutdown(wait=wait,cancel_futures=cancel_futures)
            if not wait: raise RuntimeError('synthetic executor cleanup interruption')
    monkeypatch.setattr(m.concurrent.futures,'ThreadPoolExecutor',ThrowsAfterCleanup)
    yield
    for pool in pools:
        pool.shutdown(wait=True,cancel_futures=True)
        assert all(not t.is_alive() for t in pool._threads)

def register(r,handler):
    r.register(m.ToolSpec('t','v','in','out',m.ToolRisk.READ_ONLY,timeout_s=1,max_retries=2),handler)

def test_shutdown_failure_cannot_replace_canonical_control_exception(throwing_shutdown):
    failure=ChildControl('original canonical refusal')
    calls=[]
    def handler(payload):
        calls.append(1)
        raise failure
    r=m.ToolRuntime(guarded_embedding=True,current_context_resolver=lambda:None,control_error=ControlError)
    register(r,handler)
    with pytest.raises(ChildControl) as captured:
        r.execute('t',{})
    assert captured.value is failure and calls==[1] and r.health('t').calls==0

def test_shutdown_failure_after_success_cannot_repeat_effects(throwing_shutdown):
    calls=[]
    r=m.ToolRuntime()
    register(r,lambda p:calls.append(1) or 7)
    _,receipt=r.execute('t',{})
    assert calls==[1], f'cleanup failure repeated completed handler {len(calls)} times; receipt={receipt!r}, can_retry={r.can_retry("t",receipt)}'
    assert receipt.status=='COMPLETED' or (receipt.attempts==1 and receipt.execution_liveness.get('reconciliation_required') and not r.can_retry('t',receipt))

def test_shutdown_failure_cannot_convert_baseexception_to_retry(throwing_shutdown):
    class Interrupt(BaseException):pass
    original=Interrupt('original interruption')
    calls=[]
    def handler(payload):
        calls.append(1);raise original
    r=m.ToolRuntime();register(r,handler)
    with pytest.raises(Interrupt) as caught:r.execute('t',{})
    assert caught.value is original and calls==[1]
    assert r.health('t').calls==0

@pytest.mark.parametrize('primary',['success','ordinary_handler_error','canonical_control'])
def test_canonical_cleanup_error_propagates_with_primary_control_precedence(monkeypatch,primary):
    original=ChildControl('primary control refusal')
    cleanup=ChildControl('cleanup control refusal')
    calls=[];pools=[]
    class CanonicalCleanup(REAL_EXECUTOR):
        def __init__(self,*a,**kw):super().__init__(*a,**kw);pools.append(self)
        def shutdown(self,wait=True,*,cancel_futures=False):
            super().shutdown(wait=wait,cancel_futures=cancel_futures)
            if not wait:raise cleanup
    monkeypatch.setattr(m.concurrent.futures,'ThreadPoolExecutor',CanonicalCleanup)
    def handler(p):
        calls.append(1)
        if primary=='ordinary_handler_error':raise ValueError('ordinary error')
        if primary=='canonical_control':raise original
        return 7
    r=m.ToolRuntime(guarded_embedding=True,current_context_resolver=lambda:None,control_error=ControlError)
    register(r,handler)
    try:
        with pytest.raises(ChildControl) as caught:r.execute('t',{})
        assert caught.value is (original if primary=='canonical_control' else cleanup)
        assert calls==[1] and r.health('t').calls==0
    finally:
        for pool in pools:
            pool.shutdown(wait=True,cancel_futures=True)
            assert not any(t.is_alive() for t in pool._threads)
