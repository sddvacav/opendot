from __future__ import annotations
import concurrent.futures
import threading
import pytest
from opendot_engineering import tool_runtime as m

REAL=concurrent.futures.ThreadPoolExecutor

@pytest.fixture(autouse=True)
def finite_joined_executors(monkeypatch):
    pools=[]
    class Joinable(REAL):
        def __init__(self,*a,**kw):super().__init__(*a,**kw);pools.append(self)
    monkeypatch.setattr(m.concurrent.futures,'ThreadPoolExecutor',Joinable)
    yield
    for pool in pools:
        REAL.shutdown(pool,wait=True,cancel_futures=True)
        assert not any(t.is_alive() for t in pool._threads)

def register(r,handler,**kw):
    r.register(m.ToolSpec('t','1','i','o',m.ToolRisk.READ_ONLY,timeout_s=kw.get('timeout_s',1),max_retries=3),handler)

def test_exact_observed_ordinary_handler_failures_still_retry():
    calls=[];same_error=ValueError('same actual handler instance on each attempt')
    def handler(p):
        calls.append(1)
        if len(calls)<3:raise same_error
        return 'third'
    r=m.ToolRuntime();register(r,handler)
    out,receipt=r.execute('t',{})
    assert out=='third' and receipt.attempts==3 and receipt.status=='COMPLETED'
    assert len(calls)==3 and r.health('t').calls==3

def test_equal_type_text_wait_exception_is_not_original_handler_exception(monkeypatch):
    actual=ValueError('equal text');replacement=ValueError('equal text');calls=[]
    Base=m.concurrent.futures.ThreadPoolExecutor
    class Proxy:
        def __init__(self,f):self.f=f
        def result(self,timeout):
            try:self.f.result(timeout=timeout)
            except ValueError as caught:
                assert caught is actual
                raise replacement
        def done(self):return self.f.done()
    class ChangedResult(Base):
        def submit(self,*a,**kw):return Proxy(super().submit(*a,**kw))
    monkeypatch.setattr(m.concurrent.futures,'ThreadPoolExecutor',ChangedResult)
    def handler(p):calls.append(1);raise actual
    r=m.ToolRuntime();register(r,handler)
    _,receipt=r.execute('t',{})
    assert calls==[1] and receipt.attempts==1 and receipt.execution_liveness['reconciliation_required']
    assert not r.can_retry('t',receipt)

@pytest.mark.parametrize('observation',['cancel','done'])
def test_observation_and_cleanup_failures_keep_timeout_nonretryable(monkeypatch,observation):
    entered=threading.Event();release=threading.Event();calls=[]
    Base=m.concurrent.futures.ThreadPoolExecutor
    class Proxy:
        def __init__(self,f):self.f=f
        def result(self,timeout):return self.f.result(timeout=timeout)
        def cancel(self):
            if observation=='cancel':raise ValueError('cannot observe cancellation')
            return self.f.cancel()
        def done(self):
            if observation=='done':raise ValueError('cannot observe completion')
            return self.f.done()
    class Faulty(Base):
        def submit(self,*a,**kw):return Proxy(super().submit(*a,**kw))
        def shutdown(self,wait=True,*,cancel_futures=False):
            super().shutdown(wait=wait,cancel_futures=cancel_futures)
            if not wait:raise RuntimeError('also cleanup failed')
    monkeypatch.setattr(m.concurrent.futures,'ThreadPoolExecutor',Faulty)
    def handler(p):
        calls.append(1);entered.set();assert release.wait(2);return 3
    r=m.ToolRuntime();register(r,handler,timeout_s=.03)
    try:
        _,receipt=r.execute('t',{})
        assert entered.is_set() and calls==[1] and receipt.attempts==1
        assert receipt.error_type=='TimeoutError'
        live=receipt.execution_liveness
        assert live['timed_out'] and live['reconciliation_required']
        assert not live['termination_observed'] and not live['descendant_termination_observed']
        assert live['observation_error_type']=='ValueError' and live['cleanup_error_type']=='RuntimeError'
        assert not r.can_retry('t',receipt)
    finally:release.set()

def test_shutdown_error_makes_known_ordinary_handler_failure_nonretryable(monkeypatch):
    calls=[]
    Base=m.concurrent.futures.ThreadPoolExecutor
    class CleanupFails(Base):
        def shutdown(self,wait=True,*,cancel_futures=False):
            super().shutdown(wait=wait,cancel_futures=cancel_futures)
            if not wait:raise OSError('cleanup failed')
    monkeypatch.setattr(m.concurrent.futures,'ThreadPoolExecutor',CleanupFails)
    def handler(p):calls.append(1);raise ValueError('ordinary primary')
    r=m.ToolRuntime();register(r,handler)
    _,receipt=r.execute('t',{})
    assert calls==[1] and receipt.attempts==1 and receipt.error_type=='ValueError'
    assert receipt.execution_liveness['cleanup_error_type']=='OSError'
    assert receipt.execution_liveness['reconciliation_required'] and not r.can_retry('t',receipt)

@pytest.mark.parametrize('primary',['ordinary','control'])
def test_baseexception_cleanup_respects_primary_control_authority(monkeypatch,primary):
    class Halt(BaseException):pass
    class Control(RuntimeError):pass
    refusal=Control('original control refusal');interrupt=Halt('cleanup interruption');calls=[]
    Base=m.concurrent.futures.ThreadPoolExecutor
    class InterruptCleanup(Base):
        def shutdown(self,wait=True,*,cancel_futures=False):
            super().shutdown(wait=wait,cancel_futures=cancel_futures)
            if not wait:raise interrupt
    monkeypatch.setattr(m.concurrent.futures,'ThreadPoolExecutor',InterruptCleanup)
    def handler(p):
        calls.append(1)
        if primary=='control':raise refusal
        raise ValueError('ordinary handler failure')
    r=m.ToolRuntime(guarded_embedding=True,current_context_resolver=lambda:None,control_error=Control)
    register(r,handler)
    expected=refusal if primary=='control' else interrupt
    with pytest.raises(type(expected)) as caught:r.execute('t',{})
    assert caught.value is expected and calls==[1] and r.health('t').calls==0
