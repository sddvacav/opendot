"""Bounded external CalculiX conduction benchmark; no solver implementation.

Only verified axis-aligned structured HEX8 beam meshes are supported. The
analytical oracle checks raw DAT values, independently of deck generation.
"""
from datetime import datetime, timezone
import csv
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

from . import geometry, gmsh_mesh
from . import thermal_source

RECIPE = 'thermal.synthetic_bar.dc3d8.v1'
SPEC = {'conductivity_W_mK':10.0, 'temperature_x_min_K':300.0,
        'temperature_x_max_K':400.0, 'length_unit':'m', 'temperature_unit':'K',
        'flux_unit':'W/m2', 'reaction_unit':'W', 'other_faces':'adiabatic',
        'volumetric_heat_source_W_m3':0.0, 'element':'DC3D8',
        'procedure':'STEADY STATE', 'configured_threads':1}
TOLERANCES = {'temperature_absolute_K':0.0001, 'flux_absolute_W_m2':0.001,
              'reaction_absolute_W':1e-7, 'energy_balance_absolute_W':1e-7,
              'final_cvg_flux_and_temperature_percent':1e-5}
LIMITATIONS = ['Synthetic numerical verification only; no physical experiment or material-performance claim',
               'Linear temperature is exactly representable by HEX8; no mesh-independence or general accuracy claim',
               'One prescribed SI case; no transient, nonlinear-material, contact or radiation validation',
               'Local integrity hashes are not authentication against a party rewriting all evidence',
               'Configured thread count is not measured CPU use; CPU/GPU cost not measured',
               'Unix process limits are not a hostile-code security sandbox; no native SBOM or licensing clearance']
RAW = {'thermal.inp','thermal.dat','thermal.sta','thermal.cvg','thermal.frd','thermal.12d','spooles.out','solver.log'}
DERIVED = {'recipe.json','oracle.json','temperatures.csv','flux.csv','temperature.svg','flux.svg'}
FILES = RAW | DERIVED | {'receipt.json'} | {'mesh/'+n for n in gmsh_mesh.FILES|{'manifest.json'}}


def _read(p):
    return gmsh_mesh._read(p)


def _json(p):
    return gmsh_mesh._json(p)


def _write(p, value):
    p.write_bytes(geometry.canonical_bytes(value))


def mesh_data(path):
    """Extract preserved IDs/order only after the existing mesh verifier passed."""
    lines=_read(path).decode('ascii').splitlines()
    nodes={int(v[0]):tuple(map(float,v[1:])) for v in (s.split() for s in lines[lines.index('$Nodes')+2:lines.index('$EndNodes')])}
    cells={}; ends={'X_MIN':set(),'X_MAX':set()}
    for line in lines[lines.index('$Elements')+2:lines.index('$EndElements')]:
        v=list(map(int,line.split()))
        if v[1]==5:
            cells[v[0]]=v[5:]
        elif v[3] in (2,3):
            ends[('X_MIN','X_MAX')[v[3]-2]].update(v[5:])
    return nodes,cells,ends


def _profile(benchmark):
    if benchmark=='linear': return RECIPE,SPEC,TOLERANCES,LIMITATIONS
    if benchmark in ('uniform_source','uniform_source_v1'):
        recipe=thermal_source.RECIPE if benchmark=='uniform_source' else thermal_source.LEGACY_RECIPE
        return recipe,thermal_source.SPEC,thermal_source.TOLERANCES,thermal_source.LIMITATIONS
    raise ValueError('Unsupported thermal benchmark')


def _is_source(benchmark):
    return benchmark in ('uniform_source','uniform_source_v1')


def deck(nodes,cells,ends,*,benchmark='linear'):
    _profile(benchmark)
    lines=['*HEADING','OpenDot synthetic SI steady conduction; 300 K to 400 K; k=10 W/m/K','*NODE,NSET=ALL']
    lines += [','.join([str(n)]+[format(x,'.17g') for x in xyz]) for n,xyz in sorted(nodes.items())]
    # HEX8 Gmsh and DC3D8 use the same 1-4 bottom / 5-8 top order.
    lines += ['*ELEMENT,TYPE=DC3D8,ELSET=BODY']
    lines += [','.join(map(str,[e]+c)) for e,c in sorted(cells.items())]
    for name,ns in sorted(ends.items()):
        ids=sorted(ns); lines+=['*NSET,NSET='+name]
        lines += [','.join(map(str,ids[k:k+12])) for k in range(0,len(ids),12)]
    lines += ['*MATERIAL,NAME=SYNTHETIC','*CONDUCTIVITY','10.',
              '*SOLID SECTION,ELSET=BODY,MATERIAL=SYNTHETIC',
              '*INITIAL CONDITIONS,TYPE=TEMPERATURE','ALL,300.',
              '*BOUNDARY','X_MIN,11,11,300.','X_MAX,11,11,400.',
              '*STEP,INC=10','*HEAT TRANSFER,STEADY STATE','1.,1.',
              '*NODE PRINT,NSET=ALL,FREQUENCY=1000000','NT,RFL',
              '*EL PRINT,ELSET=BODY,FREQUENCY=1000000','HFL','*END STEP']
    if _is_source(benchmark):
        lines[1]='OpenDot synthetic uniform source; equal 300 K ends; Q=50000 W/m3; k=10 W/m/K'
        lines[lines.index('X_MAX,11,11,400.')]='X_MAX,11,11,300.'
        index=lines.index('*NODE PRINT,NSET=ALL,FREQUENCY=1000000')
        lines[index:index]=['*DFLUX','BODY,BF,50000.']
        lines[lines.index('HFL')]='HFL,COORD'
    return ('\n'.join(lines)+'\n').encode('ascii')


def parse_dat(path,*,include_coordinates=False):
    headers={
        'temperatures for set ALL and time':'temperature',
        'heat generation for set ALL and time':'reaction',
        'heat flux (elem, integ.pnt.,qx,qy,qz) for set BODY and time':'flux'}
    if include_coordinates:
        headers['global coordinates (elem, integ.pnt.,x,y,z) for set BODY and time']='coordinates'
    result={}; section=None
    for raw in _read(path).decode('ascii').splitlines():
        line=raw.strip()
        if not line: continue
        found=False
        for prefix,name in headers.items():
            if line.startswith(prefix):
                if name in result or float(line[len(prefix):])!=1.0:
                    raise ValueError('Duplicate block or unfinished result time')
                section=name; result[name]={}; found=True; break
        if found: continue
        if section is None:
            if line not in ('S T E P       1','INCREMENT     1'):
                raise ValueError('Unexpected DAT preamble')
            continue
        fields=line.split(); n=5 if section in ('flux','coordinates') else 2
        if len(fields)!=n: raise ValueError('Malformed result row')
        key=(int(fields[0]),int(fields[1])) if section in ('flux','coordinates') else int(fields[0])
        values=tuple(float(v.replace('D','E')) for v in fields[2 if section in ('flux','coordinates') else 1:])
        if key in result[section] or not all(math.isfinite(v) for v in values):
            raise ValueError('Duplicate or nonfinite solver result')
        result[section][key]=values
    if set(result)!=set(headers.values()) or any(not x for x in result.values()):
        raise ValueError('Missing actual thermal outputs')
    return result


def oracle(root,nodes,cells,ends,dims,*,benchmark='linear'):
    _profile(benchmark)
    log=_read(root/'solver.log').decode('ascii')
    _check_solver_log(log)
    sta=_read(root/'thermal.sta').decode('ascii').splitlines()
    rows=[s.split() for s in sta if re.match(r'^\s*\d',s)]
    if len(rows)!=1 or len(rows[0])!=7 or rows[0][:3]!=['1','1','1'] or int(rows[0][3])<1 or any(float(v)!=1. for v in rows[0][4:]):
        raise ValueError('Incomplete or unexpected converged step')
    cvg=[line.split() for line in _read(root/'thermal.cvg').decode('ascii').splitlines() if re.match(r'^\s*\d',line)]
    iterations=int(rows[0][3])
    if len(cvg)!=iterations:
        raise ValueError('Missing or contradictory convergence history')
    for i,row in enumerate(cvg,1):
        if len(row)!=9 or row[:5]!=['1','1','1',str(i),'0'] or not all(math.isfinite(float(x)) and float(x)>=0 for x in row[5:]):
            raise ValueError('Invalid convergence iteration')
    if any(float(x)>1e-5 for x in cvg[-1][7:9]):
        raise ValueError('Final flux/temperature correction not converged')
    markers=re.findall(r'^\s*(no convergence|convergence)\s*$',log,re.M)
    if markers!=['no convergence']*(iterations-1)+['convergence']:
        raise ValueError('Contradictory final convergence log')
    observed_threads=re.findall(r'Using (?:up to )?(\d+) cpu',log)
    if not observed_threads or any(int(x)!=1 for x in observed_threads):
        raise ValueError('Solver thread diagnostics disagree with configuration')
    data=parse_dat(root/'thermal.dat',include_coordinates=_is_source(benchmark))
    if _is_source(benchmark):
        return thermal_source.analytical_report(nodes,cells,ends,dims,data,check_nodal=benchmark=='uniform_source'),data
    if set(data['temperature'])!=set(nodes) or set(data['reaction'])!=set(nodes) or set(data['flux'])!={(e,i) for e in cells for i in range(1,9)}:
        raise ValueError('Missing or wrong node/element/integration-point identity')
    length,width,height=dims; q=-10.*100./length; power=-q*width*height
    t_error=max(abs(data['temperature'][n][0]-(300.+100.*xyz[0]/length)) for n,xyz in nodes.items())
    bc_error=max(abs(data['temperature'][n][0]-t) for side,t in [('X_MIN',300.),('X_MAX',400.)] for n in ends[side])
    q_error=max(abs(v-target) for values in data['flux'].values() for v,target in zip(values,(q,0.,0.)))
    reactions={name:math.fsum(data['reaction'][n][0] for n in ids) for name,ids in ends.items()}
    interior=max((abs(v[0]) for n,v in data['reaction'].items() if n not in ends['X_MIN']|ends['X_MAX']),default=0.)
    balance=abs(math.fsum(v[0] for v in data['reaction'].values()))
    reaction_error=max(abs(reactions['X_MIN']+power),abs(reactions['X_MAX']-power),interior)
    checks={'temperature':t_error<=1e-4,'boundary_temperature':bc_error<=1e-4,
            'integration_point_flux':q_error<=1e-3,'end_reactions_and_free_nodes':reaction_error<=1e-7,
            'energy_balance':balance<=1e-7}
    if not all(checks.values()): raise ValueError('Analytical verification failed: '+str(checks))
    report={'checks':checks,'tolerances':TOLERANCES,'max_temperature_error_K':t_error,
            'max_boundary_temperature_error_K':bc_error,'max_flux_error_W_m2':q_error,
            'max_reaction_error_W':reaction_error,'energy_imbalance_W':balance,
            'end_reactions_W':reactions,'analytical_flux_W_m2':[q,0.,0.],
            'analytical_end_power_W':{'X_MIN':-power,'X_MAX':power},
            'nodes':len(nodes),'elements':len(cells),'integration_points':len(data['flux']),
            'analytical_temperature':'300 + 100*x/length (K)',
            'RFL_interpretation':'External heat sources; no applied source loads, therefore boundary reactions. Positive means heat supplied.'}
    return report,data


def _csv(rows):
    out=io.StringIO(newline=''); writer=csv.writer(out,lineterminator='\n'); writer.writerows(rows)
    return out.getvalue().encode()


def figures(nodes,cells,data,dims,*,benchmark='linear'):
    """Deterministic SVGs and CSVs from parsed values; never substitute the oracle."""
    _profile(benchmark)
    if _is_source(benchmark): return thermal_source.figures(nodes,cells,data,dims)
    length=dims[0]; q=-1000./length
    temperatures=[['node','x_m','y_m','z_m','computed_K','analytical_K','error_K']]
    points=[]
    for n,xyz in sorted(nodes.items()):
        t=data['temperature'][n][0]; ref=300.+100.*xyz[0]/length
        temperatures.append([n,*xyz,t,ref,t-ref]); points.append((xyz[0]/length,(t-300.)/100.))
    flux=[['element','integration_point','element_centroid_x_m','computed_qx_W_m2','computed_qy_W_m2','computed_qz_W_m2','analytical_qx_W_m2']]
    qpoints=[]
    for (e,i),v in sorted(data['flux'].items()):
        x=sum(nodes[n][0] for n in cells[e])/8
        flux.append([e,i,x,*v,q]); qpoints.append((x/length,(v[0]/abs(q)+1.1)/.2))
    def svg(title,pts,reference,axis_label,ymin,ymax,note=''):
        dots=''.join(f'<circle cx="{95+625*x:.8f}" cy="{350-270*y:.8f}" r="2" fill="#2563eb" fill-opacity="0.35"/>' for x,y in pts)
        x1,y1,x2,y2=reference
        ticks=''
        for fraction in (0,.25,.5,.75,1):
            x=95+625*fraction; y=350-270*fraction
            ticks+=(f'<path d="M{x} 350 v5 M90 {y} h5" stroke="#475569"/>'
                    f'<text x="{x}" y="375" text-anchor="middle">{fraction:g}</text>'
                    f'<text x="85" y="{y+5}" text-anchor="end">{ymin+(ymax-ymin)*fraction:g}</text>')
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="800" height="450" viewBox="0 0 800 450"><rect width="800" height="450" fill="white"/>'
                f'<g font-family="sans-serif" font-size="14" fill="#172554"><text x="40" y="25">{title}</text><text x="95" y="52">{axis_label}</text>'
                f'<text x="380" y="52">{note}</text>'
                '<path d="M95 75 V350 H740" fill="none" stroke="#475569"/>'
                f'{ticks}<path d="M{95+625*x1} {350-270*y1} L{95+625*x2} {350-270*y2}" stroke="#e11d48" stroke-width="2" stroke-dasharray="7 5" fill="none"/>{dots}'
                '<text x="340" y="397">x / length</text>'
                '<text x="40" y="424">Blue: parsed CalculiX values; dashed red: analytical reference</text></g></svg>').encode()
    return {'temperatures.csv':_csv(temperatures),'flux.csv':_csv(flux),
            'temperature.svg':svg('Synthetic steady conduction: all nodal temperatures',points,(0,0,1,1),'Temperature (K)',300.,400.),
            'flux.svg':svg('Synthetic steady conduction: all integration-point qx',qpoints,(0,.5,1,.5),'qx (W/m²)',q*1.1,q*.9,'IP position shown at element centroid')}



def _check_solver_log(log):
    """Declared-version/completion gate; not authentication or binary identity."""
    if re.search(r'\b(?:ERROR|WARNING)\b',log,re.I) or log.count('Job finished')!=1:
        raise ValueError('Solver error, warning, incomplete execution or wrong version')
    # Count broad markers before validating the single complete header line.
    # Contradictory, repeated, embedded and malformed declarations fail closed.
    markers=re.findall(r'\bCalculiX\s+Version',log,re.I)
    if len(markers)!=1 or not any(re.fullmatch(r'[ \t]*CalculiX Version 2\.23,[^\r\n]*',line)
                                 for line in log.splitlines()):
        raise ValueError('Missing, malformed, repeated or unsupported CalculiX version declaration')


def _check_elapsed(wall,timeout):
    """Conservative successful-call evidence bound, not an OS hard-timeout proof.

    The caller measures process creation plus wait/cleanup. There is no invented
    cleanup grace: even exit zero is not accepted if that full call exceeds the
    selected bound. Failed calls retain their actual elapsed diagnostic instead.
    """
    if type(wall) not in (int,float) or not math.isfinite(wall) or wall<0 or type(timeout) not in (int,float) or not math.isfinite(timeout) or timeout<=0 or wall>timeout:
        raise ValueError('Invalid elapsed evidence or exceeded wall-time budget')


def _publish_pack(out,receipt,files):
    """Existing receipt-last publication, with caller-owned fixed artifact names."""
    _write(out/'receipt.pending',receipt)
    artifacts={n:{'sha256':geometry.sha256(_read(out/n)),'bytes':len(_read(out/n))} for n in files-{'receipt.json'}}
    data=_read(out/'receipt.pending'); artifacts['receipt.json']={'sha256':geometry.sha256(data),'bytes':len(data)}
    _write(out/'manifest.pending',{'schema_version':'1','hash_algorithm':'sha256','artifacts':artifacts})
    (out/'manifest.pending').replace(out/'manifest.json'); (out/'receipt.pending').replace(out/'receipt.json')


def _verify_manifest(root,files,*,label):
    manifest=_json(root/'manifest.json')
    if manifest.get('schema_version')!='1' or manifest.get('hash_algorithm')!='sha256' or set(manifest.get('artifacts',{}))!=files:
        raise ValueError('Incomplete '+label+' manifest')
    for n,entry in manifest['artifacts'].items():
        b=_read(root/n)
        if entry!={'sha256':geometry.sha256(b),'bytes':len(b)}: raise ValueError('Artifact integrity failed: '+n)
    return manifest


def _snapshot_mesh(mesh_dir):
    """Capture the existing verified mesh pack and recheck those exact bytes."""
    mesh_dir=Path(mesh_dir); mesh_receipt=gmsh_mesh.verify_mesh_artifacts(mesh_dir)
    snapshot={n:_read(mesh_dir/n) for n in gmsh_mesh.FILES|{'manifest.json'}}
    manifest=json.loads(snapshot['manifest.json'])
    if json.loads(snapshot['receipt.json'])!=mesh_receipt or any(geometry.sha256(snapshot[n])!=manifest['artifacts'][n]['sha256'] for n in gmsh_mesh.FILES):
        raise ValueError('Mesh changed during snapshot')
    return mesh_receipt,snapshot


def _execute(executable,out,timeout,*,job_name='thermal'):
    if not isinstance(job_name,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,31}',job_name):
        raise ValueError('Invalid solver job basename')
    # Unix only. No shell; trusted installed executable. Each output <=32 MiB.
    import resource
    def limits():
        resource.setrlimit(resource.RLIMIT_FSIZE,(gmsh_mesh.MAX_BYTES,gmsh_mesh.MAX_BYTES))
        resource.setrlimit(resource.RLIMIT_CPU,(300,300))
    env={k:v for k,v in os.environ.items() if k in ('PATH','LD_LIBRARY_PATH','HOME','LANG')}
    env.update({k:'1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','CCX_NPROC_RESULTS','CCX_NPROC_EQUATION_SOLVER')})
    env['LC_ALL']='C'
    with (out/'solver.log').open('wb') as log:
        process=subprocess.Popen([executable,'-i',job_name],cwd=out,env=env,stdin=subprocess.DEVNULL,
                                 stdout=log,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=limits)
        try:
            code=process.wait(timeout=timeout)
            if code: raise subprocess.CalledProcessError(code,[executable,'-i',job_name])
        except BaseException:
            if process.poll() is None:
                os.killpg(process.pid,signal.SIGKILL); process.wait()
            raise


def run_thermal(mesh_dir,output_dir,*,solver_executable,timeout_s=60,benchmark='linear'):
    if benchmark not in ('linear','uniform_source'):
        raise ValueError('Unsupported thermal benchmark; v1 source packs are verification-only')
    recipe_name,spec,tolerances,limitations=_profile(benchmark)
    if type(timeout_s) not in (int,float) or not math.isfinite(timeout_s) or not 1<=timeout_s<=300:
        raise ValueError('Timeout must be 1..300 seconds')
    executable=shutil.which(str(solver_executable))
    if not executable: raise ValueError('Configured installed CalculiX executable unavailable')
    executable=str(Path(executable).resolve())
    binary_hash=geometry.sha256(Path(executable).read_bytes())
    mesh_receipt,snapshot=_snapshot_mesh(mesh_dir)
    if mesh_receipt['measurements']['volume_elements']>10000:
        raise ValueError('Thermal benchmark bounded to 10000 elements')
    out=geometry._new_output_directory(output_dir); wall=None
    try:
        (out/'mesh').mkdir()
        for n,b in snapshot.items(): (out/'mesh'/n).write_bytes(b)
        gmsh_mesh.verify_mesh_artifacts(out/'mesh')
        nodes,cells,ends=mesh_data(out/'mesh/beam.msh')
        dims=_json(out/'mesh/recipe.json')['dimensions_m']
        source=geometry._source_provenance(__file__)
        if benchmark=='uniform_source':
            if tuple(dims)!=(0.2,0.02,0.003): raise ValueError('Source benchmark requires the fixed SI bar dimensions')
            source['source_oracle_sha256']=geometry.sha256(Path(thermal_source.__file__).read_bytes())
        recipe={'recipe':recipe_name,'spec':spec,'dimensions_m':dims,'tolerances':tolerances,'source':source}
        _write(out/'recipe.json',recipe); (out/'thermal.inp').write_bytes(deck(nodes,cells,ends,benchmark=benchmark))
        started=time.monotonic()
        try: _execute(executable,out,timeout_s)
        finally: wall=time.monotonic()-started
        _check_elapsed(wall,timeout_s)
        if geometry.sha256(Path(executable).read_bytes())!=binary_hash:
            raise ValueError('Solver executable changed during run')
        report,data=oracle(out,nodes,cells,ends,dims,benchmark=benchmark)
        _write(out/'oracle.json',report)
        for n,b in figures(nodes,cells,data,dims,benchmark=benchmark).items(): (out/n).write_bytes(b)
        receipt={'schema_version':'1','recipe':recipe_name,'status':'THERMAL_BENCHMARK_PASS','source':source,
                 'figure_source_sha256':source.get('source_oracle_sha256',source['adapter_sha256']),
                 'execution_time_utc':datetime.now(timezone.utc).isoformat(),'solver':{'version':'2.23','binary_sha256':binary_hash,'command':[executable,'-i','thermal']},
                 'timeout_s':timeout_s,'compute':{'subprocess_wall_time_s':wall,'configured_threads':1,'cpu_time_s':'NOT_MEASURED','gpu_usage':'NOT_MEASURED','cost':'NOT_MEASURED'},
                 'physical_validation':'NOT_PERFORMED','mesh_independence':'NOT_EVALUATED','limitations':limitations,
                 'hashes':{n:geometry.sha256(_read(out/n)) for n in FILES-{'receipt.json'}}}
        _publish_pack(out,receipt,FILES)
        return verify_thermal_artifacts(out)
    except BaseException as exc:
        for n in ('receipt.json','manifest.json','receipt.pending','manifest.pending'): (out/n).unlink(missing_ok=True)
        _write(out/'failure.json',{'status':'THERMAL_FAILED','subprocess_wall_time_s':wall,'error_type':type(exc).__name__,'error':str(exc)})
        raise


def verify_thermal_artifacts(directory):
    root=Path(directory)
    if any(p.is_symlink() for p in [root,*root.parents]): raise ValueError('Symlinked artifact directory')
    manifest=_verify_manifest(root,FILES,label='thermal')
    gmsh_mesh.verify_mesh_artifacts(root/'mesh')
    r=_json(root/'receipt.json'); recipe=_json(root/'recipe.json')
    benchmark={thermal_source.RECIPE:'uniform_source',thermal_source.LEGACY_RECIPE:'uniform_source_v1'}.get(recipe.get('recipe'),'linear')
    recipe_name,spec,tolerances,limitations=_profile(benchmark)
    dims=_json(root/'mesh/recipe.json')['dimensions_m']; nodes,cells,ends=mesh_data(root/'mesh/beam.msh')
    if recipe.get('recipe')!=recipe_name or recipe.get('spec')!=spec or recipe.get('dimensions_m')!=dims or recipe.get('tolerances')!=tolerances:
        raise ValueError('False recipe metadata or units')
    if len(cells)>10000 or _read(root/'thermal.inp')!=deck(nodes,cells,ends,benchmark=benchmark): raise ValueError('Input/mesh/BC identity mismatch')
    if r.get('schema_version')!='1' or r.get('recipe')!=recipe_name or r.get('status')!='THERMAL_BENCHMARK_PASS' or r.get('physical_validation')!='NOT_PERFORMED' or r.get('mesh_independence')!='NOT_EVALUATED' or r.get('limitations')!=limitations:
        raise ValueError('Unsupported receipt claims')
    if r.get('source')!=recipe.get('source') or not re.fullmatch('[a-f0-9]{64}',str(r.get('source',{}).get('adapter_sha256',''))): raise ValueError('Invalid source binding')
    if not re.fullmatch('[a-f0-9]{64}',str(r.get('figure_source_sha256',''))): raise ValueError('Missing figure source binding')
    if _is_source(benchmark) and not re.fullmatch('[a-f0-9]{64}',str(r.get('source',{}).get('source_oracle_sha256',''))):
        raise ValueError('Missing source oracle binding')
    solver=r.get('solver',{}); command=solver.get('command',[])
    if solver.get('version')!='2.23' or not re.fullmatch('[a-f0-9]{64}',str(solver.get('binary_sha256',''))) or len(command)!=3 or not Path(command[0]).is_absolute() or command[1:]!=['-i','thermal']:
        raise ValueError('Invalid solver provenance')
    c=r.get('compute',{}); wall=c.get('subprocess_wall_time_s'); timeout=r.get('timeout_s')
    _check_elapsed(wall,timeout)
    if not 1<=timeout<=300 or c.get('configured_threads')!=1 or any(c.get(k)!='NOT_MEASURED' for k in ('cpu_time_s','gpu_usage','cost')):
        raise ValueError('Invalid compute claims')
    if r.get('hashes')!={n:manifest['artifacts'][n]['sha256'] for n in FILES-{'receipt.json'}}: raise ValueError('Receipt hash bindings failed')
    report,data=oracle(root,nodes,cells,ends,dims,benchmark=benchmark)
    if _json(root/'oracle.json')!=report: raise ValueError('False analytical results')
    for n,b in figures(nodes,cells,data,dims,benchmark=benchmark).items():
        if _read(root/n)!=b: raise ValueError('Plot/backing data mismatch')
    return r


def main(argv=None):
    import argparse
    p=argparse.ArgumentParser(description='Real external CalculiX synthetic steady conduction')
    p.add_argument('mesh_dir'); p.add_argument('output_dir'); p.add_argument('--solver',required=True)
    p.add_argument('--timeout-s',type=float,default=60)
    p.add_argument('--benchmark',choices=('linear','uniform_source'),default='linear')
    a=p.parse_args(argv)
    r=run_thermal(a.mesh_dir,a.output_dir,solver_executable=a.solver,timeout_s=a.timeout_s,benchmark=a.benchmark)
    print(json.dumps({'status':r['status'],'compute':r['compute']},indent=2))


if __name__=='__main__': main()
