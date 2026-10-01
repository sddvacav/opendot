"""Standard-library contract tests and opt-in installed Gmsh integration."""
import ast
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from opendot_engineering.executors import gmsh_mesh as m
from opendot_engineering.executors import geometry as g


def test_documented_mesh_example_matches_current_recipe():
    example = json.loads((Path(__file__).resolve().parents[1]/'examples/cad_cae/mesh-beam.json').read_text())
    assert example['recipe'] == m.RECIPE
    assert example['recipe'] != m.LEGACY_RECIPE
    # Read the declared recipe statically; never invoke mesh_beam or a native backend.
    module = ast.parse(Path(m.__file__).read_text())
    builder = next(node for node in module.body
                   if isinstance(node, ast.FunctionDef) and node.name == 'mesh_beam')
    recipe = next(node.value for node in builder.body
                  if isinstance(node, ast.Assign) and any(
                      isinstance(target, ast.Name) and target.id == 'recipe'
                      for target in node.targets))
    fields = {'gmsh_version', 'step_unit', 'mesh_unit', 'element_family', 'element_order'}
    declared = {key.value: ast.literal_eval(value)
                for key, value in zip(recipe.keys, recipe.values)
                if isinstance(key, ast.Constant) and key.value in fields}
    assert set(declared) == fields
    for field, value in declared.items():
        assert example[field] == value, field


@pytest.mark.parametrize('v', [(0,2,3), (101,1,1), (100,100,100), (True,2,3), (1.,2,3), (1,2), '123',None])
def test_invalid_divisions(v):
    with pytest.raises(ValueError):
        m.mesh_beam('missing','unused',divisions=v)


@pytest.mark.parametrize('v',[0,301,True,float('nan'),float('inf'),'10'])
def test_invalid_timeout(v):
    with pytest.raises(ValueError):
        m.mesh_beam('missing','unused',timeout_s=v)


def test_import_is_lightweight():
    subprocess.run([sys.executable,'-c',"import sys; import opendot_engineering.executors.gmsh_mesh; assert not any(x in sys.modules for x in ('gmsh','numpy','OCP','build123d'))"],check=True,timeout=10)


@pytest.fixture
def cell(tmp_path):
    path=tmp_path/'cell.msh'
    # Standard Gmsh HEX8 ordering, one axis-aligned SI cell.
    xyz=[(0,0,0),(.2,0,0),(.2,.02,0),(0,.02,0),(0,0,.003),(.2,0,.003),(.2,.02,.003),(0,.02,.003)]
    faces=[(2,[1,4,8,5]),(3,[2,3,7,6]),(4,[1,2,6,5]),(5,[4,3,7,8]),(6,[1,2,3,4]),(7,[5,6,7,8])]
    text='$MeshFormat\n2.2 0 8\n$EndMeshFormat\n$PhysicalNames\n7\n'
    text+='\n'.join(f'{d} {t} "{n}"' for n,(d,t) in m.REGIONS.items())+'\n$EndPhysicalNames\n$Nodes\n8\n'
    text+='\n'.join(f'{i} '+' '.join(map(str,v)) for i,v in enumerate(xyz,1))+'\n$EndNodes\n$Elements\n7\n'
    text+='\n'.join(f'{i} 3 2 {group} {group} '+' '.join(map(str,conn)) for i,(group,conn) in enumerate(faces,1))
    text+='\n7 5 2 1 1 1 2 3 4 5 6 7 8\n$EndElements\n'
    path.write_text(text)
    return path


def test_mesh_readback(cell):
    r=m._inspect_mesh(cell,[.2,.02,.003],[1,1,1])
    assert r['nodes']==8 and r['volume_elements']==1 and r['boundary_elements']==6
    assert r['volume_m3']==pytest.approx(1.2e-5)


@pytest.mark.parametrize('old,new',[
    ('0.2','200.0'),('7 5 2 1 1 1 2 3 4 5 6 7 8','7 5 2 1 1 2 1 4 3 6 5 8 7'),
    ('1 3 2 2 2 1 4 8 5','1 3 2 3 2 1 4 8 5'),
    ('1 3 2 2 2 1 4 8 5','1 3 2 2 2 1 8 4 5'),
    ('$EndElements',''),('0.003','nan'),('X_MIN','UNKNOWN'),
])
def test_bad_saved_mesh_rejected(cell,old,new):
    cell.write_text(cell.read_text().replace(old,new))
    with pytest.raises(ValueError):
        m._inspect_mesh(cell,[.2,.02,.003],[1,1,1])


@pytest.fixture
def cad_pack(tmp_path):
    # Contract fixture only: real integration below requires an actual verified STEP.
    root=tmp_path/'cad'; root.mkdir()
    spec=g.BeamGeometry()
    measurement={'valid':True,'solids':1,'faces':6,'edges':12,'vertices':8,
                 'volume_mm3':12000.,'bbox_min_mm':[0.,0.,0.],'bbox_max_mm':[200.,20.,3.]}
    (root/'beam.step').write_text('LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI.,.METRE.);')
    (root/'parameters.json').write_bytes(g.canonical_bytes({'schema_version':'1','recipe':g.RECIPE,'parameters':{'length_m':.2,'width_m':.02,'thickness_m':.003},'units':g.UNITS}))
    (root/'environment.json').write_bytes(g.canonical_bytes({'packages':{'build123d':g.TESTED_BUILD123D,'cadquery-ocp':g.TESTED_OCP}}))
    r={'schema_version':'1','recipe':g.RECIPE,'status':'GEOMETRY_BENCHMARK_PASS','units':g.UNITS,
       'before_export':measurement,'after_import':measurement,'source':{'adapter_sha256':'a'*64},
       'scientific_acceptance':'NOT_EVALUATED','physical_validation':'NOT_PERFORMED'}
    for f,n in [('step_sha256','beam.step'),('parameter_sha256','parameters.json'),('environment_sha256','environment.json')]:r[f]=g.sha256((root/n).read_bytes())
    (root/'receipt.json').write_bytes(g.canonical_bytes(r))
    seal(root,g.REQUIRED_ARTIFACTS)
    return root


def seal(root,names):
    (root/'manifest.json').write_bytes(g.canonical_bytes({'schema_version':'1','hash_algorithm':'sha256','artifacts':{n:{'sha256':g.sha256((root/n).read_bytes()),'bytes':(root/n).stat().st_size} for n in names}}))


def test_existing_output_refused(cad_pack,tmp_path):
    out=tmp_path/'out';out.mkdir()
    with pytest.raises(ValueError,match='must not exist'):m.mesh_beam(cad_pack,out)


def test_tampered_input_refused(cad_pack,tmp_path):
    (cad_pack/'beam.step').write_text('corrupt')
    with pytest.raises(ValueError):m.mesh_beam(cad_pack,tmp_path/'out')
    assert not (tmp_path/'out').exists()


@pytest.mark.parametrize('error',[subprocess.CalledProcessError(1,['python']),subprocess.TimeoutExpired(['python'],1)])
def test_failed_process_never_publishes(cad_pack,tmp_path,monkeypatch,error):
    def fail(*args,**kwargs):raise error
    # Avoid patching geometry source collection, which itself uses git subprocess.
    monkeypatch.setattr(m,'_source',lambda:{'adapter_sha256':'a'*64,'worker_sha256':'b'*64})
    monkeypatch.setattr(m.subprocess,'run',fail)
    out=tmp_path/'out'
    with pytest.raises(type(error)):m.mesh_beam(cad_pack,out)
    assert (out/'failure.json').exists()
    assert json.loads((out/'failure.json').read_text())['compute']['subprocess_wall_time_s']>=0
    assert not (out/'receipt.json').exists() and not (out/'manifest.json').exists()


def test_missing_process_output_never_passes(cad_pack,tmp_path,monkeypatch):
    monkeypatch.setattr(m,'_source',lambda:{'adapter_sha256':'a'*64,'worker_sha256':'b'*64})
    monkeypatch.setattr(m.subprocess,'run',lambda *a,**k:None)
    out=tmp_path/'out'
    with pytest.raises(ValueError):m.mesh_beam(cad_pack,out)
    assert not (out/'receipt.json').exists()


@pytest.fixture
def real_pack():
    path=os.environ.get('OPENDOT_TEST_CAD_PACK')
    if not path:pytest.skip('Set OPENDOT_TEST_CAD_PACK to verified build123d beam; installed Gmsh 4.15.2 required')
    return Path(path)


def test_real_mesh_and_refinement(real_pack,tmp_path):
    a=m.mesh_beam(real_pack,tmp_path/'coarse',divisions=(10,2,1))
    b=m.mesh_beam(real_pack,tmp_path/'fine',divisions=(20,4,2))
    assert a['compute']['subprocess_wall_time_s']>0
    assert a['compute']['cpu_core_hours']=='NOT_MEASURED'
    assert a['measurements']['volume_elements']==20
    assert b['measurements']['volume_elements']==160
    assert a['measurements']['volume_m3']==pytest.approx(b['measurements']['volume_m3'])
    assert m.verify_mesh_artifacts(tmp_path/'fine')==b


def test_real_resealed_geometry_mismatch(real_pack,tmp_path):
    root=tmp_path/'changed';shutil.copytree(real_pack,root)
    p=json.loads((root/'parameters.json').read_text());p['parameters']['length_m']=.3
    (root/'parameters.json').write_bytes(g.canonical_bytes(p))
    r=json.loads((root/'receipt.json').read_text());r['parameter_sha256']=g.sha256((root/'parameters.json').read_bytes())
    for key in ('before_export','after_import'):
        r[key]['bbox_max_mm'][0]=300.;r[key]['volume_mm3']=18000.;r[key]['volume_m3']=1.8e-5
    (root/'receipt.json').write_bytes(g.canonical_bytes(r));seal(root,g.REQUIRED_ARTIFACTS)
    g.verify_artifacts(root) # Deliberately coherent recorded claims; actual STEP differs.
    out=tmp_path/'out'
    with pytest.raises(subprocess.CalledProcessError):m.mesh_beam(root,out)
    assert not (out/'receipt.json').exists()


def test_real_resealed_quality_mismatch(real_pack,tmp_path):
    out=tmp_path/'out';m.mesh_beam(real_pack,out,divisions=(4,2,1))
    w=json.loads((out/'worker.json').read_text());w['quality']['minSICN']['min']*=.9
    (out/'worker.json').write_bytes(g.canonical_bytes(w))
    r=json.loads((out/'receipt.json').read_text());r['worker']=w;r['hashes']['worker.json']=g.sha256((out/'worker.json').read_bytes())
    (out/'receipt.json').write_bytes(g.canonical_bytes(r));seal(out,m.FILES)
    with pytest.raises(ValueError,match='quality mismatch'):m.verify_mesh_artifacts(out)


def test_incomplete_publication(real_pack,tmp_path,monkeypatch):
    original=Path.replace
    def fail_receipt(self,target):
        if self.name=='receipt.pending':raise OSError('injected publication failure')
        return original(self,target)
    monkeypatch.setattr(Path,'replace',fail_receipt)
    out=tmp_path/'out'
    with pytest.raises(OSError):m.mesh_beam(real_pack,out,divisions=(4,2,1))
    assert not (out/'receipt.json').exists() and not (out/'manifest.json').exists()


@pytest.fixture
def runtime_identity():
    # Deliberately synthetic contract evidence; not an installed library claim.
    return {'schema_version':'1','status':'VERIFIED_AT_EXECUTION',
            'method':'linux.proc-self-maps.symbol-address+device-inode',
            'wrapper':{'version':'4.15.2','path':'/synthetic/gmsh.py','sha256':'1'*64,'bytes':123},
            'native':{'version':'4.15.2','path':'/synthetic/libgmsh.so','sha256':'2'*64,'bytes':456}}


@pytest.fixture
def contract_pack(cad_pack, cell, tmp_path, monkeypatch, runtime_identity):
    def run(command, **kwargs):
        out = Path(command[-1])
        shutil.copyfile(cell, out/'beam.msh')
        measured = m._inspect_mesh(out/'beam.msh',[.2,.02,.003],[1,1,1])
        worker = {'gmsh_version':'4.15.2','gmsh_runtime':runtime_identity,
                  'imported_volume_m3':1.2e-5,'imported_bbox_m':[0.,0.,0.,.2,.02,.003],
                  'quality':measured['independent_quality'],'nodes':8,'volume_elements':1,
                  'regions':{name:{'dimension':dim,'physical_tag':tag,
                              'entity_tags':measured['region_entity_tags'][name]}
                             for name,(dim,tag) in m.REGIONS.items()}}
        (out/'worker.json').write_bytes(g.canonical_bytes(worker))
        recipe = json.loads((out/'recipe.json').read_bytes())
        recipe['gmsh_runtime'] = runtime_identity
        (out/'recipe.json').write_bytes(g.canonical_bytes(recipe))
    monkeypatch.setattr(m,'_source',lambda:{'adapter_sha256':'a'*64,'worker_sha256':'b'*64})
    monkeypatch.setattr(m.subprocess,'run',run)
    out = tmp_path/'contract'
    m.mesh_beam(cad_pack,out,divisions=(1,1,1))
    return out


def reseal_mesh(root):
    receipt = json.loads((root/'receipt.json').read_bytes())
    receipt['hashes'] = {n:g.sha256((root/n).read_bytes()) for n in m.FILES-{'receipt.json'}}
    (root/'receipt.json').write_bytes(g.canonical_bytes(receipt))
    seal(root,m.FILES)


def test_new_receipt_binds_native_identity(contract_pack, runtime_identity):
    receipt = m.verify_mesh_artifacts(contract_pack,require_native_identity=True)
    assert receipt['schema_version']=='2' and receipt['recipe']==m.RECIPE
    assert m.native_provenance(receipt)==runtime_identity
    assert receipt['gmsh_runtime']==receipt['worker']['gmsh_runtime']
    assert json.loads((contract_pack/'recipe.json').read_bytes())['gmsh_runtime']==runtime_identity


@pytest.mark.parametrize('filename,field,value',[
    ('recipe.json','sha256','3'*64),('worker.json','sha256','3'*64),
    ('receipt.json','sha256','3'*64),('recipe.json','version','4.13.1'),
    ('receipt.json','bytes',False),('receipt.json','path','relative/libgmsh.so'),
])
def test_resealed_native_identity_disagreement_rejected(contract_pack, filename, field, value):
    record = json.loads((contract_pack/filename).read_bytes())
    record['gmsh_runtime']['native'][field] = value
    (contract_pack/filename).write_bytes(g.canonical_bytes(record))
    reseal_mesh(contract_pack)
    with pytest.raises(ValueError,match='identity|binding mismatch'):
        m.verify_mesh_artifacts(contract_pack)


def test_resealed_matching_wrong_native_version_rejected(contract_pack):
    for name in ('recipe.json','worker.json','receipt.json'):
        record = json.loads((contract_pack/name).read_bytes())
        record['gmsh_runtime']['native']['version']='4.13.1'
        if name=='receipt.json':record['worker']['gmsh_runtime']['native']['version']='4.13.1'
        (contract_pack/name).write_bytes(g.canonical_bytes(record))
    reseal_mesh(contract_pack)
    with pytest.raises(ValueError,match='identity'):
        m.verify_mesh_artifacts(contract_pack)


def make_legacy(root):
    for name in ('recipe.json','worker.json','receipt.json'):
        record = json.loads((root/name).read_bytes())
        record.pop('gmsh_runtime')
        if name!='worker.json':record.update(schema_version='1',recipe=m.LEGACY_RECIPE)
        if name=='receipt.json':record['worker'].pop('gmsh_runtime')
        (root/name).write_bytes(g.canonical_bytes(record))
    reseal_mesh(root)


def test_legacy_is_read_only_not_native_verified(contract_pack):
    make_legacy(contract_pack)
    before = {n:(contract_pack/n).read_bytes() for n in m.FILES|{'manifest.json'}}
    receipt = m.verify_mesh_artifacts(contract_pack)
    assert receipt==json.loads(before['receipt.json'])
    assert m.native_provenance(receipt)['status']=='NOT_VERIFIED'
    with pytest.raises(ValueError,match='NOT_VERIFIED'):
        m.verify_mesh_artifacts(contract_pack,require_native_identity=True)
    assert {n:(contract_pack/n).read_bytes() for n in before}==before


@pytest.mark.parametrize('target',['recipe.json','receipt.json','worker.json'])
def test_legacy_cannot_silently_upgrade_native_claim(contract_pack,runtime_identity,target):
    make_legacy(contract_pack)
    record = json.loads((contract_pack/target).read_bytes())
    record['gmsh_runtime']=runtime_identity
    (contract_pack/target).write_bytes(g.canonical_bytes(record))
    reseal_mesh(contract_pack)
    with pytest.raises(ValueError):m.verify_mesh_artifacts(contract_pack)


def test_worker_checks_native_version_before_file_identity(monkeypatch):
    from types import SimpleNamespace
    from opendot_engineering.executors import _gmsh_worker as w
    gmsh = SimpleNamespace(__version__='4.15.2',option=SimpleNamespace(getString=lambda name:'4.13.1'))
    with pytest.raises(ValueError,match='wrapper=4.15.2, native=4.13.1'):
        w._runtime_identity(gmsh)


def test_worker_mismatch_never_touches_geometry(tmp_path,monkeypatch):
    import resource
    from types import SimpleNamespace
    from opendot_engineering.executors import _gmsh_worker as w
    calls=[]
    # No model API is supplied: any premature geometry access fails this test.
    gmsh=SimpleNamespace(__version__='4.15.2',
                         option=SimpleNamespace(getString=lambda name:'4.13.1'),
                         initialize=lambda *a,**k:calls.append('initialize'),
                         finalize=lambda:calls.append('finalize'))
    (tmp_path/'recipe.json').write_bytes(g.canonical_bytes({'schema_version':'2','recipe':m.RECIPE,
                                       'dimensions_m':[.2,.02,.003],'divisions':[1,1,1]}))
    before=(tmp_path/'recipe.json').read_bytes()
    monkeypatch.setitem(sys.modules,'gmsh',gmsh)
    monkeypatch.setattr(resource,'setrlimit',lambda *a:None)
    monkeypatch.setattr(sys,'argv',['worker',str(tmp_path)])
    with pytest.raises(ValueError,match='wrapper/native version mismatch'):w.main()
    assert calls==['initialize','finalize']
    assert (tmp_path/'recipe.json').read_bytes()==before
    assert set(p.name for p in tmp_path.iterdir())=={'recipe.json'}


def test_worker_requires_linux_for_native_identity(monkeypatch):
    from types import SimpleNamespace
    from opendot_engineering.executors import _gmsh_worker as w
    gmsh = SimpleNamespace(__version__='4.15.2',option=SimpleNamespace(getString=lambda name:'4.15.2'))
    monkeypatch.setattr(w.sys,'platform','darwin')
    with pytest.raises(ValueError,match='requires Linux'):
        w._runtime_identity(gmsh)


def test_native_mapping_uses_symbol_address_and_inode(tmp_path):
    from opendot_engineering.executors import _gmsh_worker as w
    native = tmp_path/'actual native.so';native.write_bytes(b'synthetic native bytes')
    st=native.stat()
    maps=f'1000-2000 r-xp 00000000 {os.major(st.st_dev):x}:{os.minor(st.st_dev):x} {st.st_ino} {native}\n'
    path,dev_inode=w._mapped_native_file(0x1234,maps)
    assert path==native and dev_inode==(st.st_dev,st.st_ino)
    assert w._file_identity(path,mapped_device_inode=dev_inode)['sha256']==g.sha256(native.read_bytes())
    with pytest.raises(ValueError,match='no longer matches'):
        w._file_identity(path,mapped_device_inode=(st.st_dev,st.st_ino+1))
    with pytest.raises(ValueError,match='no identifiable'):
        w._mapped_native_file(0x2345,maps)
    for invalid in (maps.replace('r-xp','rw-p'), maps.replace(str(native),str(native)+' (deleted)'), maps.replace(str(native),'[anonymous]')):
        with pytest.raises(ValueError,match='Cannot identify'):
            w._mapped_native_file(0x1234,invalid)


def test_file_identity_detects_mutation_during_hash(tmp_path,monkeypatch):
    from opendot_engineering.executors import _gmsh_worker as w
    path=tmp_path/'wrapper.py';path.write_bytes(b'first')
    original=w.hashlib.file_digest
    def changed(stream,*args):
        digest=original(stream,*args)
        path.write_bytes(b'changed bytes')
        return digest
    monkeypatch.setattr(w.hashlib,'file_digest',changed)
    with pytest.raises(ValueError,match='changed while hashing'):
        w._file_identity(path)


def test_real_native_mismatch_stops_before_mesh(real_pack,tmp_path,monkeypatch):
    mismatch=os.environ.get('OPENDOT_TEST_MISMATCH_GMSH_PATH')
    if not mismatch:pytest.skip('Set OPENDOT_TEST_MISMATCH_GMSH_PATH to a known mismatched wrapper installation')
    monkeypatch.setenv('PYTHONPATH',mismatch)
    out=tmp_path/'mismatch'
    with pytest.raises(subprocess.CalledProcessError):
        m.mesh_beam(real_pack,out,divisions=(1,1,1))
    assert 'wrapper=4.15.2, native=4.13.1' in (out/'process.log').read_text()
    assert not (out/'beam.msh').exists()
    assert not (out/'worker.json').exists()
    assert 'gmsh_runtime' not in json.loads((out/'recipe.json').read_bytes())
    assert not (out/'receipt.json').exists() and not (out/'manifest.json').exists()
