"""Frozen physics contracts, explicit failure injection and opt-in native solves."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from opendot_engineering.executors import geometry, thermal_conduction as shared
from opendot_engineering.executors import structural_beam as s


def write(path,value):path.write_bytes(geometry.canonical_bytes(value))


def reseal(root):
    r=json.loads((root/'receipt.json').read_text())
    r['hashes']={n:geometry.sha256((root/n).read_bytes()) for n in s.FILES-{'receipt.json'}}
    write(root/'receipt.json',r)
    write(root/'manifest.json',{'schema_version':'1','hash_algorithm':'sha256','artifacts':{
        n:{'sha256':geometry.sha256((root/n).read_bytes()),'bytes':(root/n).stat().st_size} for n in s.FILES}})


@pytest.mark.parametrize('value',[None,True,0,61,float('nan'),float('inf'),'60'])
def test_timeout_contract(tmp_path,value):
    with pytest.raises(ValueError,match='Timeout'):
        s.run_structural('missing',tmp_path/'out',solver_executable='missing',timeout_s=value)
    assert not (tmp_path/'out').exists()


def test_unsupported_element_and_missing_solver(tmp_path):
    with pytest.raises(ValueError,match='element'):s.run_structural('missing',tmp_path/'out',solver_executable='missing',element='C3D20R')
    with pytest.raises(ValueError,match='unavailable'):s.run_structural('missing',tmp_path/'out',solver_executable='/nonexistent/ccx')


@pytest.mark.parametrize('name',['../evil','/tmp/evil','a/b','x;echo','-i','',None,'a'*33])
def test_shared_job_name_rejected_before_spawn(tmp_path,name):
    with pytest.raises(ValueError,match='basename'):shared._execute('/nonexistent',tmp_path,1,job_name=name)
    assert not (tmp_path/'solver.log').exists()


def test_shared_job_name_forwarded(tmp_path):
    fixture=tmp_path/'test-owned-fixture'
    fixture.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n');fixture.chmod(0o700)
    shared._execute(str(fixture),tmp_path,1,job_name='structural')
    assert (tmp_path/'solver.log').read_text()=='-i\nstructural\n'


def test_consistent_face_load_weights():
    # Two end-face quads: shared edge receives twice corner load. Independent grid fixture.
    nodes={};cells={};ids={}
    for i,x in enumerate((0.,.2)):
        for j,y in enumerate((0.,.01,.02)):
            for k,z in enumerate((0.,.003)):
                n=len(nodes)+1;nodes[n]=(x,y,z);ids[i,j,k]=n
    for j in range(2):
        cells[j+1]=[ids[i,y,z] for i,y,z in ((0,j,0),(1,j,0),(1,j+1,0),(0,j+1,0),(0,j,1),(1,j,1),(1,j+1,1),(0,j+1,1))]
    ends={'X_MIN':{n for n,v in nodes.items() if v[0]==0},'X_MAX':{n for n,v in nodes.items() if v[0]==.2}}
    f=s.loads(nodes,cells,ends)
    assert sum(v[2] for v in f.values())==pytest.approx(-.1)
    for n,v in f.items():assert v==(0.,0.,-.025 if nodes[n][1]==.01 else -.0125)
    deck=s.deck(nodes,cells,ends).decode()
    assert '*ELEMENT,TYPE=C3D8I' in deck and '*STATIC\n*CLOAD' in deck
    assert 'X_MIN,1,3,0.' in deck and 'NLGEOM' not in deck
    assert '*ELEMENT,TYPE=C3D8,ELSET' in s.deck(nodes,cells,ends,element='C3D8').decode()


@pytest.fixture
def dat_text():
    return (' S T E P       1\n INCREMENT     1\n'
            ' displacements (vx,vy,vz) for set ALL and time 1.0\n 1 0 0 -2.8D-5\n'
            ' forces (fx,fy,fz) for set ALL and time 1.0\n 1 0 0 -0.1\n'
            ' strains (elem, integ.pnt.,exx,eyy,ezz,exy,exz,eyz) for set BODY and time 1.0\n 4 1 1e-6 0 0 0 0 0\n'
            ' internal energy (element, energy) for set BODY and time 1.0\n 4 1.4e-6\n')


def test_parser_fixture(tmp_path,dat_text):
    p=tmp_path/'data';p.write_text(dat_text);d=s.parse_dat(p)
    assert d['displacement']=={1:(0.,0.,-2.8e-5)} and d['energy']=={4:(1.4e-6,)}


@pytest.mark.parametrize('mutate',[
    lambda t:t.replace('-2.8D-5','nan'),lambda t:t.replace('time 1.0','time .5'),
    lambda t:t.replace('1 0 0 -2.8D-5','1 0 0 -2.8D-5\n1 0 0 -2.8D-5'),
    lambda t:t[:t.index(' internal energy')],lambda t:t.replace('1 0 0 -0.1','1 0 -0.1'),
    lambda t:t.replace('set ALL','set OTHER'),lambda t:t+t,
    lambda t:t.replace('INCREMENT     1','INCREMENT     2'),
    lambda t:t.replace('4 1.4e-6','4 inf')])
def test_parser_rejects_bad_output(tmp_path,dat_text,mutate):
    p=tmp_path/'data';p.write_text(mutate(dat_text))
    with pytest.raises(ValueError):s.parse_dat(p)


def test_empty_manifest_rejected(tmp_path):
    write(tmp_path/'manifest.json',{})
    with pytest.raises(ValueError,match='Incomplete'):s.verify_structural_artifacts(tmp_path)


@pytest.fixture(scope='module')
def real_config():
    mesh=os.environ.get('OPENDOT_TEST_MESH_PACK');refined=os.environ.get('OPENDOT_TEST_REFINED_MESH_PACK');solver=os.environ.get('OPENDOT_TEST_CCX')
    if not mesh or not refined or not solver:pytest.skip('Opt-in verified coarse/refined mesh packs and installed CalculiX required')
    return mesh,refined,solver


@pytest.fixture(scope='module')
def real_packs(tmp_path_factory,real_config):
    root=tmp_path_factory.mktemp('real-structural');mesh,refined,solver=real_config
    for name,path in [('coarse',mesh),('refined',refined)]:s.run_structural(path,root/name,solver_executable=solver)
    return root/'coarse',root/'refined'


def test_real_solver_and_refinement(real_packs):
    for root in real_packs:
        assert s.verify_structural_artifacts(root,profile='artifact_v1')['status']=='STRUCTURAL_BENCHMARK_PASS'
        o=json.loads((root/'oracle.json').read_text())
        assert all(o['checks'].values()) and o['strain_integration_points']==8*o['elements']
        assert o['support_resultant_N'][2]==pytest.approx(.1,abs=1e-5)
        assert o['support_moment_Nm'][1]==pytest.approx(-.02,abs=2e-6)
    assert s.compare_refinement(*real_packs,profile='artifact_v1')['status']=='STRUCTURAL_REFINEMENT_PASS'
    with pytest.raises(ValueError):s.compare_refinement(real_packs[0],real_packs[0])


@pytest.mark.parametrize('name',['structural.dat','structural.inp','mesh/beam.msh','deflection.svg','solver.log'])
def test_integrity_tampering(tmp_path,real_packs,name):
    root=tmp_path/'copy';shutil.copytree(real_packs[0],root)
    with (root/name).open('ab') as f:f.write(b'corrupt')
    with pytest.raises(ValueError):s.verify_structural_artifacts(root)


@pytest.mark.parametrize('name,old,new',[
    ('structural.inp','X_MIN,1,3,0.','X_MIN,1,2,0.'),
    ('structural.inp','210000000000.,0.3','21000000000.,0.3'),
    ('structural.inp','TYPE=C3D8I','TYPE=C3D8'),
    ('structural.dat','time  0.1000000E+01','time  0.5000000E+00'),
    ('structural.dat','-2.773323E-05','-1.773323E-05'),
    ('solver.log','Job finished','Job unfinished'),
    ('solver.log','Job finished','Job finished\nWARNING: unexpected diagnostic'),
    ('solver.log','Job finished','Job finished\nERROR: unexpected diagnostic'),
    ('solver.log','CalculiX Version 2.23','CalculiX Version 2.24'),
    ('solver.log','Using 1 cpu for spooles.','Using 2 cpu for spooles.'),
    ('structural.sta','0.100000E+01','0.500000E+00'),
    ('structural.cvg','FORCE','BROKEN'),('deflection.svg','Blue:','False:')])
def test_resealed_semantic_tampering(tmp_path,real_packs,name,old,new):
    root=tmp_path/'copy';shutil.copytree(real_packs[0],root)
    p=root/name;text=p.read_text();assert old in text;p.write_text(text.replace(old,new));reseal(root)
    with pytest.raises(ValueError):s.verify_structural_artifacts(root)


@pytest.mark.parametrize('field,value',[
    ('status','PASS'),('physical_validation','PERFORMED'),('mesh_independence','ESTABLISHED'),
    ('mesh_native_identity','VERIFIED'),('timeout_s',61),
    ('compute',{'subprocess_wall_time_s':-1,'configured_threads':1}),
    ('compute',{'subprocess_wall_time_s':1e9,'configured_threads':1,'cpu_time_s':'NOT_MEASURED','gpu_usage':'NOT_MEASURED','cost':'NOT_MEASURED'}),
    ('source',{'adapter_sha256':'0'*64}),
    ('solver',{'version':'2.24','binary_sha256':'0'*64,'command':['/fake','-i','structural']})])
def test_false_metadata_resealed(tmp_path,real_packs,field,value):
    root=tmp_path/'copy';shutil.copytree(real_packs[0],root)
    r=json.loads((root/'receipt.json').read_text());r[field]=value;write(root/'receipt.json',r);reseal(root)
    with pytest.raises(ValueError):s.verify_structural_artifacts(root)


@pytest.mark.parametrize('mutation',['force','moment','loaded_rf','energy','missing_strain','clamp','large_displacement','large_strain'])
def test_raw_oracle_rejects_physics_mutations(real_packs,mutation):
    root=real_packs[0];n,c,e=s._mesh(root/'mesh');d=s.parse_dat(root/'structural.dat')
    if mutation=='force':
        node=next(iter(e['X_MIN']));v=d['external_force'][node];d['external_force'][node]=(v[0],v[1],v[2]+.001)
    if mutation=='moment':
        node=min(e['X_MIN'],key=lambda x:n[x][2]);v=d['external_force'][node];d['external_force'][node]=(v[0]+1,v[1],v[2])
    if mutation=='loaded_rf':
        for node in e['X_MAX']:d['external_force'][node]=(0.,0.,0.)
    if mutation=='energy':d['energy']={k:(v[0]*.9,) for k,v in d['energy'].items()}
    if mutation=='clamp':d['displacement'][next(iter(e['X_MIN']))]=(1e-6,0.,0.)
    if mutation=='large_displacement':d['displacement'][next(iter(e['X_MAX']))]=(1.,0.,0.)
    if mutation=='large_strain':d['strain'][next(iter(d['strain']))]=(1.,0.,0.,0.,0.,0.)
    if mutation=='missing_strain':
        del d['strain'][next(iter(d['strain']))]
        with pytest.raises(ValueError,match='identity'):s.analytical_report(n,c,e,d)
        return
    assert not all(s.analytical_report(n,c,e,d)['checks'].values())


@pytest.mark.parametrize('failure',['exit0_no_results','nonzero','timeout'])
def test_failed_execution_never_publishes(tmp_path,real_config,monkeypatch,failure):
    mesh,_,solver=real_config;out=tmp_path/'failed'
    def execute(*args,**kwargs):
        if failure=='timeout':raise subprocess.TimeoutExpired('fixture',1)
        if failure=='nonzero':raise subprocess.CalledProcessError(2,'fixture')
    monkeypatch.setattr(shared,'_execute',execute)
    with pytest.raises((ValueError,subprocess.TimeoutExpired,subprocess.CalledProcessError)):
        s.run_structural(mesh,out,solver_executable=solver)
    assert (out/'failure.json').is_file() and not (out/'receipt.json').exists() and not (out/'manifest.json').exists()


def test_incomplete_publication(tmp_path,real_config,monkeypatch):
    mesh,_,solver=real_config;out=tmp_path/'interrupted';original=Path.replace
    def replace(path,target):
        if path.name=='receipt.pending':raise OSError('injected publication failure')
        return original(path,target)
    monkeypatch.setattr(Path,'replace',replace)
    with pytest.raises(OSError,match='publication'):s.run_structural(mesh,out,solver_executable=solver)
    assert (out/'failure.json').is_file() and not (out/'receipt.json').exists() and not (out/'manifest.json').exists()


def test_full_integration_locking_is_rejected(tmp_path,real_config):
    mesh,_,solver=real_config;out=tmp_path/'locking'
    with pytest.raises(ValueError,match='acceptance failed'):s.run_structural(mesh,out,solver_executable=solver,element='C3D8')
    report=json.loads((out/'oracle.json').read_text())
    assert not report['checks']['tip_displacement'] and report['checks']['force_balance']
    assert (out/'failure.json').is_file() and not (out/'receipt.json').exists()


def test_existing_output_refused(real_packs,real_config):
    mesh,_,solver=real_config
    with pytest.raises(ValueError,match='must not exist'):s.run_structural(mesh,real_packs[0],solver_executable=solver)


def test_completed_process_over_wall_budget_fails(tmp_path,real_config,monkeypatch):
    mesh,_,solver=real_config;out=tmp_path/'wall-budget'
    monkeypatch.setattr(shared,'_execute',lambda *args,**kwargs:None)
    readings=iter((0.,61.))
    monkeypatch.setattr(s.time,'monotonic',lambda:next(readings))
    with pytest.raises(ValueError,match='wall-time budget'):
        s.run_structural(mesh,out,solver_executable=solver,timeout_s=60)
    assert not (out/'receipt.json').exists() and not (out/'manifest.json').exists()
    assert json.loads((out/'failure.json').read_text())['subprocess_wall_time_s']==61.
