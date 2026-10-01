"""Separately authored synthetic boundary regressions, made source-portable."""
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
from opendot_engineering import tool_runtime as m

REAL_EXECUTOR=concurrent.futures.ThreadPoolExecutor

@pytest.fixture(autouse=True)
def all_threads_joined(monkeypatch):
    initial={t.ident for t in threading.enumerate()}
    pools=[]
    class RecordingExecutor(REAL_EXECUTOR):
        def __init__(self,*a,**kw):
            super().__init__(*a,**kw)
            pools.append(self)
    monkeypatch.setattr(m.concurrent.futures,'ThreadPoolExecutor',RecordingExecutor)
    yield pools
    for p in pools:
        p.shutdown(wait=True,cancel_futures=True)
        assert not any(t.is_alive() for t in p._threads)
    assert {t.ident for t in threading.enumerate()} <= initial

def spec(**kw):
    return dataclasses.replace(m.ToolSpec('t','v','input','output',m.ToolRisk.READ_ONLY,timeout_s=1,max_retries=2),**kw)

class StopControl(RuntimeError): pass
class StopChild(StopControl): pass

def runtime(resolver=lambda:None,**kw):
    return m.ToolRuntime(guarded_embedding=True,current_context_resolver=resolver,control_error=StopControl,**kw)

def open_breaker(r):
    with r._lock:
        h=r._health['t']
        h.breaker_state=m.BreakerState.OPEN
        h.consecutive_failures=r.failure_threshold
        h.opened_at=time.monotonic()-10

def launch(r,payload):
    results=[]
    errors=[]
    def run():
        try: results.append(r.execute('t',payload))
        except BaseException as e: errors.append(e)
    thread=threading.Thread(target=run)
    thread.start()
    return thread,results,errors



def test_candidate_import_surface_and_no_protocol_binding():
    tree=ast.parse(Path(m.__file__).read_text())
    imports=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.Import): imports.extend(a.name for a in node.names)
        if isinstance(node,ast.ImportFrom):
            assert node.level==0
            imports.append(node.module)
    assert set(imports)=={'__future__','concurrent.futures','copy','hashlib','json','math','os','threading','time','uuid','contextvars','dataclasses','enum','typing'}
    for node in ast.walk(tree):
        if isinstance(node,ast.Constant) and isinstance(node.value,str):
            assert 'tool-dispatch' not in node.value
        if isinstance(node,ast.Attribute): assert node.attr not in {'Popen','system','fork','spawn','run_bound','dispatch_checkpoint','begin_tool_execution','end_tool_execution','unresolved_tool_execution'}
    owner=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='ToolRuntime')
    assert '_dispatch_binding' not in {n.name for n in owner.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    execute=next(n for n in owner.body if isinstance(n,ast.FunctionDef) and n.name=='execute')
    assert {a.arg for a in execute.args.kwonlyargs}=={'granted_permissions','approval_token','backoff_base_s','attempt_limit'}

@pytest.mark.parametrize('value',[False,0,'',{},[],(),object()])
def test_early_guard_preempts_all_untrusted_conversion(value):
    hooks=[]
    class Poison(dict):
        def __deepcopy__(self,memo): hooks.append('copy'); raise AssertionError('copied')
    class Permissions:
        def __rsub__(self,other): hooks.append('permissions'); raise AssertionError('converted')
    r=runtime(lambda:value,recovery_timeout_s=0)
    r.register(spec(permissions={'r'}),lambda p:pytest.fail('dispatched'))
    open_breaker(r)
    h=r.health('t')
    with pytest.raises(StopControl): r.execute('t',Poison(),granted_permissions=Permissions())
    assert hooks==[] and r.health('t')==h and not r._probe_owners

@pytest.mark.parametrize('stage',['entry','worker','handler','validation','output_hash'])
def test_control_family_object_identity_for_every_catch_boundary(stage):
    error=StopChild(stage)
    checks=0
    calls=[]
    def resolver():
        nonlocal checks
        checks+=1
        if (stage=='entry' and checks==1) or (stage=='worker' and checks==2): raise error
        return None
    def validate(value):
        if stage=='validation': raise error
        return True
    class Output:
        def __str__(self): raise error
    def handler(p):
        calls.append(1)
        if stage=='handler': raise error
        return Output() if stage=='output_hash' else 1
    r=runtime(resolver,recovery_timeout_s=0)
    r.register(spec(semantic_validator=validate),handler)
    open_breaker(r)
    with pytest.raises(StopChild) as caught: r.execute('t',{})
    assert caught.value is error
    assert r.health('t').calls==0
    assert len(calls)==(0 if stage in {'entry','worker'} else 1)
    assert not r._probe_owners and not r.health('t').half_open_probe_in_flight

def test_context_guard_after_second_payload_copy():
    context=contextvars.ContextVar('independent',default=None)
    reads=[]
    copies=[]
    def resolver():
        reads.append((threading.get_ident(),context.get()))
        return context.get()
    class ChangeOnAttempt(dict):
        def __deepcopy__(self,memo):
            copies.append(1)
            if len(copies)==2: context.set('bound-during-per-attempt-copy')
            return self.__class__()
    r=runtime(resolver,recovery_timeout_s=0)
    r.register(spec(),lambda p:pytest.fail('worker dispatch not fenced'))
    open_breaker(r)
    reset=context.set(None)
    try:
        with pytest.raises(StopControl): r.execute('t',ChangeOnAttempt())
    finally: context.reset(reset)
    assert len(copies)==2 and len(reads)==2
    assert reads[0]==(threading.get_ident(),None)
    assert reads[1][0]!=threading.get_ident() and reads[1][1]=='bound-during-per-attempt-copy'
    assert r.health('t').calls==0 and not r._probe_owners

@pytest.mark.parametrize('kind',['mutable-list','mutable-set'])
def test_permission_contract_binding_and_detached_health(kind):
    permissions=['read'] if kind=='mutable-list' else {'read'}
    r=m.ToolRuntime()
    r.register(spec(permissions=permissions),lambda p:p)
    first=r.registration_signature('t')
    if isinstance(permissions,list): permissions.append('write')
    else: permissions.add('write')
    out,receipt=r.execute('t',{'nested':{'x':[1]}},granted_permissions=frozenset({'read'}))
    assert receipt.execution_observation.registration_sha256==first==r.registration_signature('t')
    assert receipt.input_hash==receipt.execution_observation.input_sha256
    external=r.health('t'); external.calls=900
    assert r.health('t').calls==1

def test_hash_baseline_per_attempt_ids_and_mutations(monkeypatch):
    seen=[]; ids=[]
    r=m.ToolRuntime()
    original={'x':{'a':[1]}}
    def handler(p):
        seen.append(list(p['x']['a']))
        p['x']['a'].append(2)
        if len(seen)<2: raise ValueError('first fails')
        return p
    r.register(spec(),handler)
    dispatch=r._dispatch
    def traced(*a,**kw):
        ids.append(kw['execution_id'])
        return dispatch(*a,**kw)
    monkeypatch.setattr(r,'_dispatch',traced)
    out,receipt=r.execute('t',original)
    canonical=json.dumps(original,sort_keys=True,separators=(',',':')).encode()
    assert receipt.input_hash==hashlib.sha256(canonical).hexdigest()
    assert seen==[[1],[1]] and original=={'x':{'a':[1]}}
    assert len(set(ids))==2 and all(uuid.UUID(i).hex==i for i in ids)
    assert receipt.execution_observation.execution_id==ids[-1] and receipt.call_id not in ids
    assert out=={'x':{'a':[1,2]}} and receipt.attempts==2

def test_timeout_receipt_remains_conservative_after_actual_completion(monkeypatch):
    entered=threading.Event(); release=threading.Event(); captures=[]; calls=[]
    Base=m.concurrent.futures.ThreadPoolExecutor
    class Capture(Base):
        def submit(self,fn,wrapped):
            values=dict(zip(wrapped.__code__.co_freevars,[c.cell_contents for c in wrapped.__closure__]))
            captures.append(values['completion'])
            return super().submit(fn,wrapped)
    monkeypatch.setattr(m.concurrent.futures,'ThreadPoolExecutor',Capture)
    def handler(p):
        calls.append(1); entered.set(); assert release.wait(2); return 7
    r=m.ToolRuntime(); r.register(spec(timeout_s=.03),handler)
    try:
        _,receipt=r.execute('t',{})
        assert entered.is_set() and not captures[0].done()
        assert receipt.attempts==1 and not r.can_retry('t',receipt)
        before=dict(receipt.execution_liveness)
        assert before['reconciliation_required'] and not before['termination_observed']
        assert not before['descendant_termination_observed']
    finally: release.set()
    assert captures[0].result(timeout=2)[0]==7
    assert receipt.execution_liveness==before and calls==[1]

def test_lost_submit_handle_after_completed_worker_is_still_unknown(monkeypatch):
    calls=[]; captured=[]
    Base=m.concurrent.futures.ThreadPoolExecutor
    class Lost(Base):
        def submit(self,fn,wrapper):
            values=dict(zip(wrapper.__code__.co_freevars,[c.cell_contents for c in wrapper.__closure__]))
            captured.append(values['completion'])
            f=super().submit(fn,wrapper)
            f.result(timeout=2)
            raise RuntimeError('completed but submit return lost')
    monkeypatch.setattr(m.concurrent.futures,'ThreadPoolExecutor',Lost)
    r=m.ToolRuntime();r.register(spec(),lambda p:calls.append(1) or 7)
    _,receipt=r.execute('t',{})
    assert calls==[1] and receipt.attempts==1
    assert receipt.execution_liveness['reconciliation_required']
    assert not receipt.execution_liveness['return_handle_observed']
    assert captured[0].done() and captured[0].result(timeout=2)[0]==7

def test_interrupted_wait_after_worker_completion_cannot_automatically_retry(monkeypatch):
    """Result delivery failure racing worker completion remains an unknown attempt."""
    calls=[]
    Base=m.concurrent.futures.ThreadPoolExecutor
    class InterruptedHandle:
        def __init__(self,f): self.f=f
        def result(self,timeout):
            self.f.result(timeout=timeout)
            raise RuntimeError('synthetic result-wait interruption after worker completion')
        def done(self): return self.f.done()
    class Interrupted(Base):
        def submit(self,*a,**kw): return InterruptedHandle(super().submit(*a,**kw))
    monkeypatch.setattr(m.concurrent.futures,'ThreadPoolExecutor',Interrupted)
    r=m.ToolRuntime(); r.register(spec(),lambda p:calls.append(1) or 7)
    _,receipt=r.execute('t',{})
    assert calls==[1], f'Unknown result-delivery outcome retried actual callable {len(calls)} times; receipt={receipt!r}'
    assert receipt.attempts==1 and receipt.execution_liveness['reconciliation_required']
    assert not r.can_retry('t',receipt)

@pytest.mark.parametrize('old_success',[False,True])
@pytest.mark.parametrize('new_success',[False,True])
def test_real_old_ordinary_completion_cannot_override_new_settled_probe(old_success,new_success):
    old_entered=threading.Event(); release=threading.Event()
    def handler(p):
        if p['role']=='old':
            old_entered.set(); assert release.wait(2)
            if not old_success: raise ValueError('old failure')
            return 'old success'
        if p['role']=='opening' or not new_success: raise ValueError('new failure')
        return 'new success'
    r=m.ToolRuntime(failure_threshold=1,recovery_timeout_s=0)
    r.register(spec(max_retries=0),handler)
    t,results,errors=launch(r,{'role':'old'})
    try:
        assert old_entered.wait(2)
        assert r.execute('t',{'role':'opening'})[1].status=='FAILED'
        new=r.execute('t',{'role':'new'})[1]
        settled=r.health('t')
        assert new.status==('COMPLETED' if new_success else 'FAILED')
        release.set(); t.join(3); assert not t.is_alive()
        final=r.health('t')
        assert not errors and len(results)==1
        assert final.breaker_state==settled.breaker_state
        assert final.consecutive_failures==settled.consecutive_failures
        assert final.calls==settled.calls+1 and not r._probe_owners
    finally:
        release.set();t.join(3);assert not t.is_alive()

@pytest.mark.parametrize('new_success',[False,True])
def test_retry_from_retired_probe_cannot_override_new_settled_probe(monkeypatch,new_success):
    old_retry_entered=threading.Event(); release=threading.Event(); counts={}
    def handler(p):
        key=p['role']; counts[key]=counts.get(key,0)+1
        if key=='old':
            if counts[key]==1: raise ValueError('first old attempt')
            old_retry_entered.set(); assert release.wait(2); return 'old retry result'
        if not new_success: raise ValueError('new failure')
        return 'new success'
    r=m.ToolRuntime(failure_threshold=1,recovery_timeout_s=0)
    r.register(spec(max_retries=1),handler);open_breaker(r)
    t,results,errors=launch(r,{'role':'old'})
    try:
        assert old_retry_entered.wait(2)
        new=r.execute('t',{'role':'new'},attempt_limit=1)[1]
        settled=r.health('t')
        assert new.status==('COMPLETED' if new_success else 'FAILED')
        release.set();t.join(3);assert not t.is_alive()
        final=r.health('t')
        assert not errors and results[0][1].status=='COMPLETED'
        assert final.breaker_state==settled.breaker_state
        assert final.consecutive_failures==settled.consecutive_failures
        assert final.calls==settled.calls+1 and not r._probe_owners
    finally: release.set();t.join(3);assert not t.is_alive()

def test_real_future_condition_interrupt_after_completion_cannot_retry(monkeypatch):
    """Use the stdlib Future and unmodified Future.result; inject only a wait interruption."""
    calls=[]; observed=[]; gates=[]
    Base=m.concurrent.futures.ThreadPoolExecutor
    class RealFutureExecutor(Base):
        def submit(self,fn,*args,**kwargs):
            gate=threading.Event();gates.append(gate)
            def gated_dispatch():
                assert gate.wait(2)
                return fn(*args,**kwargs)
            future=super().submit(gated_dispatch)
            assert type(future) is concurrent.futures.Future
            normal_wait=future._condition.wait
            def interrupted_wait(timeout=None):
                gate.set()
                normal_wait(timeout)
                observed.append((future.done(),future.exception(timeout=0)))
                raise RuntimeError('synthetic condition-wait interruption after completion notification')
            future._condition.wait=interrupted_wait
            return future
    monkeypatch.setattr(m.concurrent.futures,'ThreadPoolExecutor',RealFutureExecutor)
    r=m.ToolRuntime();r.register(spec(),lambda p:calls.append(1) or 7)
    try:
        _,receipt=r.execute('t',{})
        assert observed and all(done and error is None for done,error in observed)
        assert calls==[1], f'real Future wait interruption retried {len(calls)} successful dispatches; liveness={receipt.execution_liveness}, can_retry={r.can_retry("t",receipt)}'
        assert receipt.attempts==1 and receipt.execution_liveness['reconciliation_required']
        assert not r.can_retry('t',receipt)
    finally:
        for gate in gates: gate.set()
