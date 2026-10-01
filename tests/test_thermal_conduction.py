"""Contract tests use explicit fixtures; only opt-in integration runs a real solver."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from opendot_engineering.executors import geometry
from opendot_engineering.executors import thermal_conduction as t


def write(path,value):
    path.write_bytes(geometry.canonical_bytes(value))


def reseal(root):
    """Attacker can fix hashes; semantic checks must still reject contradictions."""
    receipt=json.loads((root/'receipt.json').read_text())
    receipt['hashes']={n:geometry.sha256((root/n).read_bytes()) for n in t.FILES-{'receipt.json'}}
    write(root/'receipt.json',receipt)
    write(root/'manifest.json',{'schema_version':'1','hash_algorithm':'sha256','artifacts':{
        n:{'sha256':geometry.sha256((root/n).read_bytes()),'bytes':(root/n).stat().st_size} for n in t.FILES}})


@pytest.mark.parametrize('value',[None,True,0,301,float('nan'),'60'])
def test_timeout_contract(tmp_path,value):
    with pytest.raises(ValueError,match='Timeout'):
        t.run_thermal('missing',tmp_path/'out',solver_executable='missing',timeout_s=value)
    assert not (tmp_path/'out').exists()


def test_optional_missing_solver(tmp_path):
    with pytest.raises(ValueError,match='unavailable'):
        t.run_thermal('missing',tmp_path/'out',solver_executable='/nonexistent/ccx')


@pytest.fixture
def dat_text():
    return (' S T E P       1\n INCREMENT     1\n'
            ' temperatures for set ALL and time 1.0\n 1 300.0\n'
            ' heat generation for set ALL and time 1.0\n 1 -0.3\n'
            ' heat flux (elem, integ.pnt.,qx,qy,qz) for set BODY and time 1.0\n 4 1 -5000.0 0.0 0.0\n')


def test_parser_fixture(tmp_path,dat_text):
    p=tmp_path/'fixture.dat';p.write_text(dat_text)
    d=t.parse_dat(p)
    assert d['temperature']=={1:(300.,)}
    assert d['flux']=={(4,1):(-5000.,0.,0.)}


@pytest.mark.parametrize('mutate',[
    lambda s:s.replace('1 300.0','1 nan'),
    lambda s:s.replace('time 1.0','time 0.5'),
    lambda s:s.replace('1 300.0','1 300.0\n1 300.0'),
    lambda s:s[:s.index(' heat generation')],
    lambda s:s.replace('4 1 -5000.0 0.0 0.0','4 1 -5000.0'),
    lambda s:s.replace('set ALL','set OTHER'),
    lambda s:s+s,
])
def test_parser_rejects_incomplete_nonfinite_duplicate(tmp_path,dat_text,mutate):
    p=tmp_path/'fixture.dat';p.write_text(mutate(dat_text))
    with pytest.raises(ValueError):t.parse_dat(p)


def test_empty_manifest_rejected(tmp_path):
    write(tmp_path/'manifest.json',{})
    with pytest.raises(ValueError,match='Incomplete'):t.verify_thermal_artifacts(tmp_path)


@pytest.fixture(scope='module')
def real_config():
    mesh=os.environ.get('OPENDOT_TEST_MESH_PACK');solver=os.environ.get('OPENDOT_TEST_CCX')
    if not mesh or not solver:pytest.skip('Opt-in real verified mesh pack and installed CalculiX required')
    return mesh,solver


@pytest.fixture(scope='module')
def real_pack(tmp_path_factory,real_config):
    root=tmp_path_factory.mktemp('real-thermal')/'run'
    mesh,solver=real_config
    t.run_thermal(mesh,root,solver_executable=solver)
    return root


def test_real_solver_analytical_acceptance(real_pack):
    r=t.verify_thermal_artifacts(real_pack)
    o=json.loads((real_pack/'oracle.json').read_text())
    assert r['status']=='THERMAL_BENCHMARK_PASS'
    assert all(o['checks'].values())
    assert o['integration_points']==8*o['elements']
    assert o['end_reactions_W']['X_MIN']==pytest.approx(-.3,abs=1e-7)
    assert o['end_reactions_W']['X_MAX']==pytest.approx(.3,abs=1e-7)


@pytest.mark.parametrize('name',['thermal.dat','thermal.inp','mesh/beam.msh','temperature.svg','solver.log'])
def test_integrity_tampering(tmp_path,real_pack,name):
    root=tmp_path/'copy';shutil.copytree(real_pack,root)
    with (root/name).open('ab') as f:f.write(b'corrupt')
    with pytest.raises(ValueError):t.verify_thermal_artifacts(root)


@pytest.mark.parametrize('name,old,new',[
    ('thermal.inp','X_MAX,11,11,400.','X_MAX,11,11,410.'),
    ('thermal.dat','3.000000E+02','3.100000E+02'),
    ('thermal.dat','-5.000000E+03','-4.000000E+03'),
    ('solver.log','Job finished','Job unfinished'),
    ('solver.log','Job finished','Job finished\nWARNING: unexpected diagnostic'),
    ('solver.log','Job finished','Job finished\nERROR: unexpected diagnostic'),
    ('thermal.sta','0.100000E+01','0.500000E+00'),
    ('temperature.svg','Blue:','False:'),
    ('solver.log','\n convergence\n','\n no convergence\n'),
])
def test_resealed_semantic_tampering(tmp_path,real_pack,name,old,new):
    root=tmp_path/'copy';shutil.copytree(real_pack,root)
    p=root/name; text=p.read_text();assert old in text;p.write_text(text.replace(old,new))
    reseal(root)
    with pytest.raises(ValueError):t.verify_thermal_artifacts(root)


@pytest.mark.parametrize('field,value',[
    ('status','PASS'),('physical_validation','PERFORMED'),('mesh_independence','ESTABLISHED'),
    ('compute',{'subprocess_wall_time_s':-1,'configured_threads':1}),
    ('compute',{'subprocess_wall_time_s':1e9,'configured_threads':1,'cpu_time_s':'NOT_MEASURED','gpu_usage':'NOT_MEASURED','cost':'NOT_MEASURED'}),
    ('solver',{'version':'2.24','binary_sha256':'0'*64,'command':['/fake','-i','thermal']}),
])
def test_false_metadata_resealed(tmp_path,real_pack,field,value):
    root=tmp_path/'copy';shutil.copytree(real_pack,root)
    r=json.loads((root/'receipt.json').read_text());r[field]=value;write(root/'receipt.json',r);reseal(root)
    with pytest.raises(ValueError):t.verify_thermal_artifacts(root)


@pytest.mark.parametrize('failure',['exit0_no_results','nonzero','timeout'])
def test_failed_execution_never_publishes(tmp_path,real_config,monkeypatch,failure):
    mesh,solver=real_config;out=tmp_path/'failed'
    def execute(*args):
        if failure=='timeout':raise subprocess.TimeoutExpired('fixture',1)
        if failure=='nonzero':raise subprocess.CalledProcessError(2,'fixture')
    monkeypatch.setattr(t,'_execute',execute)
    with pytest.raises((ValueError,subprocess.TimeoutExpired,subprocess.CalledProcessError)):
        t.run_thermal(mesh,out,solver_executable=solver)
    assert (out/'failure.json').is_file()
    assert not (out/'receipt.json').exists() and not (out/'manifest.json').exists()


def test_actual_process_timeout_killed(tmp_path):
    # A test-owned executable intentionally sleeps; it is never solver evidence.
    p=tmp_path/'sleep-fixture';p.write_text('#!/bin/sh\nsleep 20\n');p.chmod(0o700)
    with pytest.raises(subprocess.TimeoutExpired):t._execute(str(p),tmp_path,.05)


def test_incomplete_publication(tmp_path,real_config,monkeypatch):
    mesh,solver=real_config;out=tmp_path/'interrupted';original=Path.replace
    def replace(path,target):
        if path.name=='receipt.pending':raise OSError('injected publication failure')
        return original(path,target)
    monkeypatch.setattr(Path,'replace',replace)
    with pytest.raises(OSError,match='publication'):
        t.run_thermal(mesh,out,solver_executable=solver)
    assert not (out/'receipt.json').exists() and not (out/'manifest.json').exists()
    with pytest.raises(ValueError):t.verify_thermal_artifacts(out)


def test_existing_output_refused(real_pack,real_config):
    mesh,solver=real_config
    with pytest.raises((ValueError,FileExistsError)):
        t.run_thermal(mesh,real_pack,solver_executable=solver)


@pytest.mark.parametrize('mode',['empty','large_correction'])
def test_false_convergence_history(tmp_path,real_pack,mode):
    root=tmp_path/'copy';shutil.copytree(real_pack,root)
    p=root/'thermal.cvg'
    if mode=='empty':p.write_text('')
    else:
        lines=p.read_text().splitlines();fields=lines[-1].split();fields[-1]='0.9999E+03'
        lines[-1]=' '.join(fields);p.write_text('\n'.join(lines)+'\n')
    reseal(root)
    with pytest.raises(ValueError):t.verify_thermal_artifacts(root)


def test_completed_process_over_wall_budget_fails(tmp_path,real_config,monkeypatch):
    mesh,solver=real_config;out=tmp_path/'wall-budget'
    monkeypatch.setattr(t,'_execute',lambda *args,**kwargs:None)
    readings=iter((0.,61.))
    monkeypatch.setattr(t.time,'monotonic',lambda:next(readings))
    with pytest.raises(ValueError,match='wall-time budget'):
        t.run_thermal(mesh,out,solver_executable=solver,timeout_s=60)
    assert not (out/'receipt.json').exists() and not (out/'manifest.json').exists()
    assert json.loads((out/'failure.json').read_text())['subprocess_wall_time_s']==61.


@pytest.mark.parametrize('wall,timeout',[(-1,60),(float('nan'),60),(float('inf'),60),(True,60),(1,True),(1,float('nan')),(1,0),(61,60)])
def test_shared_elapsed_evidence_contract(wall,timeout):
    with pytest.raises(ValueError,match='wall-time budget'):t._check_elapsed(wall,timeout)


def test_shared_elapsed_exact_bound_accepted():
    t._check_elapsed(0.,60);t._check_elapsed(60.,60)
