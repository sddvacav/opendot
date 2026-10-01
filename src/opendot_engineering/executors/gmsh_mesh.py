"""Bounded mesh-only adapter. Gmsh runs exclusively in an external process.

The strict MSH reader below verifies this rectangular structured grid only; it is
not a general mesh format owner, mesher, solver or runtime.
"""
from datetime import datetime, timezone
import itertools
import json
import math
from pathlib import Path
import shutil
import re
import subprocess
import sys
import time

from . import geometry

LEGACY_RECIPE = 'mesh.synthetic_beam.hex8.v1'
RECIPE = 'mesh.synthetic_beam.hex8.v2'
MAX_BYTES = 32 * 1024 * 1024
FILES = {'beam.step', 'cad-receipt.json', 'cad-manifest.json', 'cad-parameters.json',
         'recipe.json', 'worker.json', 'beam.msh', 'process.log', 'receipt.json'}
REGIONS = {'BODY':(3,1), **{a+s:(2,2+2*i+j) for i,a in enumerate('XYZ')
                          for j,s in enumerate(('_MIN','_MAX'))}}
LIMITATIONS = ['Mesh-only synthetic rectangular HEX8 benchmark',
               'No solver execution, convergence, mesh independence or physical acceptance',
               'No cryptographic authenticity or hostile concurrent-writer protection',
               'External process separation is not licensing clearance or a security sandbox',
               'No complete native/transitive SBOM or clean-environment recreation']


def _read(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError('Missing, symlinked or oversized artifact: '+str(path))
    return path.read_bytes()


def _json(path):
    return json.loads(_read(path), parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def _divisions(value):
    if not isinstance(value, (tuple,list)) or len(value) != 3 or any(type(v) is not int or not 1 <= v <= 100 for v in value) or math.prod(value) > 100000:
        raise ValueError('Three integer divisions in [1,100], product <=100000 required')
    return list(value)


def _inspect_mesh(path, dims, divisions):
    """Check every node, cell, orientation and boundary of the expected SI grid."""
    lines = _read(path).decode('ascii').splitlines()
    sections = {}
    while lines:
        marker = lines.pop(0)
        if not marker.startswith('$') or marker.startswith('$End') or marker in sections:
            raise ValueError('Malformed MSH section')
        end = '$End'+marker[1:]
        try:
            n = lines.index(end)
        except ValueError as exc:
            raise ValueError('Truncated MSH') from exc
        sections[marker] = lines[:n]
        del lines[:n+1]
    if set(sections) != {'$MeshFormat','$PhysicalNames','$Nodes','$Elements'} or sections['$MeshFormat'] != ['2.2 0 8']:
        raise ValueError('Only ASCII MSH2.2 with named regions is supported')
    def records(name):
        rows = sections[name]
        if int(rows[0]) != len(rows)-1:
            raise ValueError('Truncated/count-mismatched section')
        return rows[1:]
    physical = {}
    for row in records('$PhysicalNames'):
        d,t,name = row.split(maxsplit=2)
        name = name.strip('"')
        if name in physical:
            raise ValueError('Duplicate region')
        physical[name] = (int(d), int(t))
    if physical != REGIONS:
        raise ValueError('Region identity mismatch')
    nodes, grid = {}, {}
    for row in records('$Nodes'):
        t,*xyz = row.split()
        t,xyz = int(t),tuple(map(float,xyz))
        if t <= 0 or t in nodes or len(xyz) != 3 or not all(math.isfinite(x) for x in xyz):
            raise ValueError('Invalid node')
        ijk = tuple(round(x/d*n) for x,d,n in zip(xyz,dims,divisions))
        if any(not 0 <= k <= n or abs(x-k*d/n)>1e-10 for x,k,d,n in zip(xyz,ijk,dims,divisions)) or ijk in grid:
            raise ValueError('Nodes do not form the expected SI grid')
        nodes[t] = ijk
        grid[ijk] = xyz
    if len(nodes) != math.prod(n+1 for n in divisions):
        raise ValueError('Missing grid nodes')
    cells,faces,element_ids = set(),set(),set()
    quality_values={k:[] for k in ('volume','minDetJac','minSICN')}
    counts = {name:0 for name in REGIONS}
    entities = {name:set() for name in REGIONS}
    # Gmsh HEX8 standard local ordering, allowing positive axis permutations.
    offsets = ((0,0,0),(1,0,0),(1,1,0),(0,1,0),(0,0,1),(1,0,1),(1,1,1),(0,1,1))
    for row in records('$Elements'):
        vals = list(map(int,row.split()))
        eid,typ,nt = vals[:3]
        if eid in element_ids or eid<=0 or nt != 2 or typ not in (3,5):
            raise ValueError('Unexpected/duplicate mesh element')
        element_ids.add(eid)
        group,entity = vals[3:5]
        if entity<=0:
            raise ValueError('Invalid elementary entity')
        conn = vals[5:]
        if len(conn) != (8 if typ==5 else 4) or len(set(conn)) != len(conn) or any(t not in nodes for t in conn):
            raise ValueError('Malformed connectivity')
        points = [nodes[t] for t in conn]
        lo = tuple(min(p[i] for p in points) for i in range(3))
        hi = tuple(max(p[i] for p in points) for i in range(3))
        if typ == 5:
            if group != 1 or lo in cells or any(b-a!=1 for a,b in zip(lo,hi)) or set(points)!=set(itertools.product(*[(a,a+1) for a in lo])):
                raise ValueError('Duplicate, missing or malformed volume cell')
            edges = [tuple(points[j][i]-points[0][i] for i in range(3)) for j in (1,3,4)]
            a,b,c=edges
            det = a[0]*(b[1]*c[2]-b[2]*c[1])-a[1]*(b[0]*c[2]-b[2]*c[0])+a[2]*(b[0]*c[1]-b[1]*c[0])
            if det != 1 or any(points[j] != tuple(points[0][i]+sum(offsets[j][k]*edges[k][i] for k in range(3)) for i in range(3)) for j in range(8)):
                raise ValueError('Invalid HEX8 orientation/order')
            actual=[grid[p] for p in points]
            vectors=[tuple(actual[j][i]-actual[0][i] for i in range(3)) for j in (1,3,4)]
            if any(abs(actual[j][i]-(actual[0][i]+sum(offsets[j][k]*vectors[k][i] for k in range(3))))>1e-12 for j in range(8) for i in range(3)) or any(abs(vectors[k][i])>1e-12 for k in range(3) for i in range(3) if edges[k][i]==0):
                raise ValueError('Saved cell is not an affine axis-aligned cuboid')
            steps=[math.sqrt(sum(x*x for x in v)) for v in vectors]
            vol=math.prod(steps)
            quality_values['volume'].append(vol)
            quality_values['minDetJac'].append(vol/8)
            quality_values['minSICN'].append(3/math.sqrt(sum(x*x for x in steps)*sum(1/(x*x) for x in steps)))
            cells.add(lo)
            counts['BODY'] += 1
            entities['BODY'].add(entity)
        else:
            if group not in range(2,8):
                raise ValueError('Unknown boundary region')
            axis,side = divmod(group-2,2)
            if lo[axis]!=hi[axis] or lo[axis]!=side*divisions[axis] or any(hi[i]-lo[i]!=1 for i in range(3) if i!=axis):
                raise ValueError('Wrong semantic boundary location')
            key=(group,lo)
            if key in faces or set(points)!=set(itertools.product(*[(lo[i],) if i==axis else (lo[i],hi[i]) for i in range(3)])):
                raise ValueError('Duplicate/malformed boundary')
            if any(sum(abs(a-b) for a,b in zip(points[j],points[(j+1)%4])) != 1 for j in range(4)):
                raise ValueError('Invalid QUAD4 ordering')
            entities['XYZ'[axis]+('_MIN','_MAX')[side]].add(entity)
            faces.add(key)
            counts['XYZ'[axis]+('_MIN','_MAX')[side]] += 1
    if len(cells)!=math.prod(divisions) or any(counts[a+s]!=math.prod(divisions[k] for k in range(3) if k!=i) for i,a in enumerate('XYZ') for s in ('_MIN','_MAX')):
        raise ValueError('Incomplete grid or boundary mesh')
    bbox = [min(v[i] for v in grid.values()) for i in range(3)]+[max(v[i] for v in grid.values()) for i in range(3)]
    volume = math.fsum(quality_values['volume'])
    if not math.isclose(volume,math.prod(dims),rel_tol=1e-8):
        raise ValueError('Actual mesh volume disagrees with CAD')
    qualities={name:{'min':min(values),'max':max(values),'sum':math.fsum(values)} for name,values in quality_values.items()}
    steps=[dims[i]/divisions[i] for i in range(3)]
    sicn=3/math.sqrt(sum(x*x for x in steps)*sum(1/(x*x) for x in steps))
    return {'independent_quality':qualities,'analytic_minSICN':sicn,'nodes':len(nodes),'volume_elements':len(cells),'boundary_elements':len(faces),
            'region_entity_tags':{k:sorted(v) for k,v in entities.items()},
            'region_element_counts':counts,'bbox_m':bbox,'volume_m3':volume,
            'element_family':'hexahedron','gmsh_element_type':5,'element_order':1,'nodes_per_element':8}


def _source():
    info = geometry._source_provenance(__file__)
    info['worker_sha256'] = geometry.sha256(Path(__file__).with_name('_gmsh_worker.py').read_bytes())
    return info


def mesh_beam(cad_dir, output_dir, *, divisions=(20,4,2), python_executable=sys.executable, timeout_s=60):
    """Mesh a verified geometry pack with a caller-selected installed Python/Gmsh.

    The Python executable is trusted local execution configuration, never read
    from the CAD pack. The inherited environment selects optional dependencies.
    """
    divisions = _divisions(divisions)
    if type(timeout_s) not in (int,float) or not math.isfinite(timeout_s) or not 1<=timeout_s<=300:
        raise ValueError('Timeout must be finite and between 1 and 300 seconds')
    root = Path(cad_dir).absolute()
    if any(p.is_symlink() for p in [root,*root.parents]):
        raise ValueError('Symlinked CAD directory is unsupported')
    for name in geometry.REQUIRED_ARTIFACTS | {'manifest.json'}:
        _read(root/name)
    cad = geometry.verify_artifacts(root)
    geometry._check_step_units(root/'beam.step')
    snapshot = {n:_read(root/n) for n in geometry.REQUIRED_ARTIFACTS | {'manifest.json'}}
    # Recheck hashes over the exact bytes passed to the worker.
    manifest=json.loads(snapshot['manifest.json'])
    if any(geometry.sha256(snapshot[n]) != manifest['artifacts'][n]['sha256'] for n in geometry.REQUIRED_ARTIFACTS):
        raise ValueError('CAD pack changed during input capture')
    if json.loads(snapshot['receipt.json']) != cad or any(cad[field] != geometry.sha256(snapshot[name]) for field,name in (('step_sha256','beam.step'),('parameter_sha256','parameters.json'),('environment_sha256','environment.json'))):
        raise ValueError('CAD verified receipt changed during capture')
    params = json.loads(snapshot['parameters.json'])['parameters']
    spec = geometry.BeamGeometry.from_parameters(params)
    dims = [spec.length_m,spec.width_m,spec.thickness_m]
    source=_source()
    recipe = {'source':source, 'schema_version':'2','recipe':RECIPE,'dimensions_m':dims,'divisions':divisions,
              'step_unit':'mm','mesh_unit':'m','conversion':'Geometry.OCCTargetUnit=M before STEP import',
              'element_family':'hexahedron','element_order':1,'gmsh_version':'4.15.2',
              'configured_gmsh_threads':1}
    executable = shutil.which(str(python_executable))
    if not executable:
        raise ValueError('Configured Python executable is unavailable')
    out = geometry._new_output_directory(output_dir)
    compute={'subprocess_wall_time_s':None,'configured_gmsh_threads':1,
             'cpu_time_s':'NOT_MEASURED','cpu_core_hours':'NOT_MEASURED',
             'gpu_usage':'NOT_MEASURED','cost':'NOT_MEASURED'}
    try:
        for dst,src in (('beam.step','beam.step'),('cad-receipt.json','receipt.json'),('cad-manifest.json','manifest.json'),('cad-parameters.json','parameters.json')):
            (out/dst).write_bytes(snapshot[src])
        (out/'recipe.json').write_bytes(geometry.canonical_bytes(recipe))
        command=[executable,str(Path(__file__).with_name('_gmsh_worker.py').resolve()),str(out)]
        # File-backed logging bounds memory; worker output is checked before publication.
        with (out/'process.log').open('wb') as log:
            started=time.monotonic()
            try:
                subprocess.run(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                               timeout=timeout_s, check=True, cwd=out)
            finally:
                compute['subprocess_wall_time_s']=time.monotonic()-started
        measured = _inspect_mesh(out/'beam.msh',dims,divisions)
        worker = _json(out/'worker.json')
        _check_worker(worker, measured, dims)
        runtime = worker.get('gmsh_runtime')
        _check_runtime_identity(runtime)
        if _json(out/'recipe.json') != {**recipe, 'gmsh_runtime':runtime}:
            raise ValueError('Worker recipe/native identity binding mismatch')
        receipt={'schema_version':'2','recipe':RECIPE,'status':'MESH_BENCHMARK_PASS',
                 'gmsh_runtime':runtime,
                 'execution_time_utc':datetime.now(timezone.utc).isoformat(),'source':source,
                 'cad_source':cad['source'],'cad_parameters':params,'measurements':measured,
                 'worker':worker,'command':command,'timeout_s':timeout_s,'compute':compute,
                 'scientific_acceptance':'NOT_EVALUATED','solver_execution':'NOT_PERFORMED',
                 'mesh_independence':'NOT_EVALUATED','limitations':LIMITATIONS,
                 'hashes':{n:geometry.sha256(_read(out/n)) for n in FILES-{'receipt.json'}}}
        (out/'receipt.pending').write_bytes(geometry.canonical_bytes(receipt))
        artifacts = {n:{'sha256':geometry.sha256(_read(out/n)),'bytes':(out/n).stat().st_size} for n in FILES-{'receipt.json'}}
        data = (out/'receipt.pending').read_bytes()
        artifacts['receipt.json']={'sha256':geometry.sha256(data),'bytes':len(data)}
        (out/'manifest.pending').write_bytes(geometry.canonical_bytes({'schema_version':'1','hash_algorithm':'sha256','artifacts':artifacts}))
        (out/'manifest.pending').replace(out/'manifest.json')
        (out/'receipt.pending').replace(out/'receipt.json')
        return verify_mesh_artifacts(out)
    except BaseException as exc:
        for name in ('receipt.json','manifest.json','receipt.pending','manifest.pending'):
            (out/name).unlink(missing_ok=True)
        (out/'failure.json').write_bytes(geometry.canonical_bytes({'status':'MESH_FAILED','compute':compute,'error_type':type(exc).__name__,'error':str(exc)}))
        raise


def _check_worker(worker, measured, dims):
    if worker.get('gmsh_version')!='4.15.2' or any(worker.get(k)!=measured[k] for k in ('nodes','volume_elements')):
        raise ValueError('Worker version/count mismatch')
    if set(worker.get('regions',{}))!=set(REGIONS):
        raise ValueError('Worker region mismatch')
    for name,(dim,tag) in REGIONS.items():
        r=worker['regions'][name]
        if r.get('dimension')!=dim or r.get('physical_tag')!=tag or r.get('entity_tags')!=measured['region_entity_tags'][name] or len(r.get('entity_tags',[]))!=1:
            raise ValueError('Invalid worker region')
    for field in ('imported_volume_m3',):
        if not math.isclose(worker[field],math.prod(dims),rel_tol=1e-8):
            raise ValueError('Imported CAD volume mismatch')
    if len(worker['imported_bbox_m'])!=6 or any(not math.isfinite(a) or abs(a-b)>2e-7 for a,b in zip(worker['imported_bbox_m'],[0,0,0,*dims])):
        raise ValueError('Imported CAD bbox mismatch')
    for name in ('minDetJac','minSICN','volume'):
        q=worker['quality'][name]
        if set(q)!={'min','max','sum'} or not all(type(v) in (int,float) and math.isfinite(v) and v>0 for v in q.values()) or q['min']>q['max']:
            raise ValueError('Invalid quality metrics')
    for name in ('volume','minDetJac','minSICN'):
        if any(not math.isclose(worker['quality'][name][k],measured['independent_quality'][name][k],rel_tol=1e-7) for k in ('min','max','sum')):
            raise ValueError('Saved-grid quality mismatch')
    if worker['quality']['minSICN']['max']>1+1e-10:
        raise ValueError('Invalid normalized quality')
    if not math.isclose(worker['quality']['volume']['sum'],measured['volume_m3'],rel_tol=1e-8):
        raise ValueError('Mesh volume mismatch')


def _check_runtime_identity(runtime):
    if not isinstance(runtime, dict) or set(runtime) != {'schema_version','status','method','wrapper','native'} or runtime.get('schema_version') != '1' or runtime.get('status') != 'VERIFIED_AT_EXECUTION' or runtime.get('method') != 'linux.proc-self-maps.symbol-address+device-inode':
        raise ValueError('Missing or unsupported Gmsh native identity')
    for name in ('wrapper','native'):
        identity = runtime[name]
        if not isinstance(identity, dict) or set(identity) != {'version','path','sha256','bytes'} or identity.get('version') != '4.15.2' or not isinstance(identity.get('path'), str) or not Path(identity['path']).is_absolute() or not re.fullmatch('[a-f0-9]{64}', str(identity.get('sha256',''))) or type(identity.get('bytes')) is not int or identity['bytes'] <= 0:
            raise ValueError('Invalid Gmsh wrapper/native file identity')


def native_provenance(receipt):
    """Assess a verified receipt without rewriting or upgrading historical claims.

    Call verify_mesh_artifacts first. Archived hashes are execution evidence,
    not current-machine revalidation, authenticated attestation or a full SBOM.
    """
    if receipt.get('recipe') == LEGACY_RECIPE and receipt.get('schema_version') == '1':
        if 'gmsh_runtime' in receipt or 'gmsh_runtime' in receipt.get('worker', {}):
            raise ValueError('Legacy mesh cannot claim verified native identity')
        return {'status':'NOT_VERIFIED', 'reason':'Legacy v1 records only the wrapper version; loaded native file identity was not captured'}
    if receipt.get('recipe') != RECIPE or receipt.get('schema_version') != '2':
        raise ValueError('Unsupported mesh provenance recipe/schema')
    runtime = receipt.get('gmsh_runtime')
    _check_runtime_identity(runtime)
    if receipt.get('worker', {}).get('gmsh_runtime') != runtime:
        raise ValueError('Receipt/worker native identity binding mismatch')
    return runtime


def verify_mesh_artifacts(directory, *, require_native_identity=False):
    """Reverify geometry/integrity; legacy receipts remain byte-equivalent.

    Use native_provenance(result) for an explicit native identity assessment, or
    require_native_identity=True to reject legacy geometry-only evidence.
    """
    root=Path(directory)
    if any(p.is_symlink() for p in [root,*root.parents]):
        raise ValueError('Symlinked artifact directory')
    manifest=_json(root/'manifest.json')
    if manifest.get('schema_version')!='1' or manifest.get('hash_algorithm')!='sha256' or set(manifest.get('artifacts',{}))!=FILES:
        raise ValueError('Incomplete mesh manifest')
    for n,entry in manifest['artifacts'].items():
        data=_read(root/n)
        if entry!={'sha256':geometry.sha256(data),'bytes':len(data)}:
            raise ValueError('Artifact integrity failed: '+n)
    r=_json(root/'receipt.json')
    recipe=_json(root/'recipe.json')
    provenance = native_provenance(r)
    if recipe.get('schema_version') != r.get('schema_version') or recipe.get('recipe') != r.get('recipe'):
        raise ValueError('Mesh recipe/schema mismatch')
    if provenance['status'] == 'NOT_VERIFIED':
        if 'gmsh_runtime' in recipe or require_native_identity:
            raise ValueError('Legacy mesh native identity is NOT_VERIFIED')
    elif recipe.get('gmsh_runtime') != provenance:
        raise ValueError('Recipe/receipt native identity binding mismatch')
    compute=r.get('compute',{})
    wall=compute.get('subprocess_wall_time_s')
    if type(wall) not in (float,int) or not math.isfinite(wall) or wall<0 or compute.get('configured_gmsh_threads')!=1 or recipe.get('configured_gmsh_threads')!=1 or any(compute.get(k)!='NOT_MEASURED' for k in ('cpu_time_s','cpu_core_hours','gpu_usage','cost')):
        raise ValueError('Invalid compute measurement or unsupported resource claim')
    source=r.get('source',{})
    if source!=recipe.get('source') or any(not re.fullmatch('[a-f0-9]{64}',str(source.get(k,''))) for k in ('adapter_sha256','worker_sha256')):
        raise ValueError('Missing or inconsistent source binding')
    cad=_json(root/'cad-receipt.json')
    params=_json(root/'cad-parameters.json')['parameters']
    cm=_json(root/'cad-manifest.json')['artifacts']
    for dst,src in (('beam.step','beam.step'),('cad-receipt.json','receipt.json'),('cad-parameters.json','parameters.json')):
        if geometry.sha256(_read(root/dst))!=cm[src]['sha256']:
            raise ValueError('CAD lineage mismatch')
    spec=geometry.BeamGeometry.from_parameters(params)
    dims=[spec.length_m,spec.width_m,spec.thickness_m]
    if r.get('status')!='MESH_BENCHMARK_PASS' or recipe.get('dimensions_m')!=dims or recipe.get('mesh_unit')!='m' or recipe.get('step_unit')!='mm' or recipe.get('element_order')!=1 or recipe.get('element_family')!='hexahedron' or recipe.get('gmsh_version')!='4.15.2' or recipe.get('conversion')!='Geometry.OCCTargetUnit=M before STEP import':
        raise ValueError('Invalid mesh receipt/units')
    if r.get('cad_source')!=cad['source'] or r.get('cad_parameters')!=params or cad.get('step_sha256')!=geometry.sha256(_read(root/'beam.step')):
        raise ValueError('CAD binding mismatch')
    geometry._check_step_units(root/'beam.step')
    if r.get('hashes')!={n:manifest['artifacts'][n]['sha256'] for n in FILES-{'receipt.json'}}:
        raise ValueError('Receipt hash bindings mismatch')
    measured=_inspect_mesh(root/'beam.msh',dims,_divisions(recipe['divisions']))
    if r.get('measurements')!=measured or r.get('worker')!=_json(root/'worker.json'):
        raise ValueError('Measurement binding mismatch')
    _check_worker(r['worker'],measured,dims)
    if r.get('solver_execution')!='NOT_PERFORMED' or r.get('scientific_acceptance')!='NOT_EVALUATED' or r.get('mesh_independence')!='NOT_EVALUATED':
        raise ValueError('Unsupported acceptance claim')
    return r


def main(argv=None):
    import argparse
    p=argparse.ArgumentParser(description='External Gmsh mesh-only synthetic beam benchmark')
    p.add_argument('cad_dir'); p.add_argument('output_dir')
    p.add_argument('--divisions',nargs=3,type=int,default=[20,4,2])
    p.add_argument('--python',default=sys.executable)
    p.add_argument('--timeout-s',type=float,default=60)
    a=p.parse_args(argv)
    r=mesh_beam(a.cad_dir,a.output_dir,divisions=a.divisions,python_executable=a.python,timeout_s=a.timeout_s)
    print(json.dumps({'status':r['status'],'measurements':r['measurements'],'native_provenance':native_provenance(r)},indent=2))


if __name__=='__main__':
    main()
