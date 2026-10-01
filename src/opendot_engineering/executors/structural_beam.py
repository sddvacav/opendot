"""Bounded synthetic cantilever using external CalculiX; not a solver owner."""
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import shutil
import time

from . import geometry, gmsh_mesh, thermal_conduction as shared, thermal_source

RECIPE = 'structural.synthetic_cantilever.c3d8i.v1'
SPEC = {'young_modulus_Pa':210e9, 'poisson_ratio':.3, 'force_z_N':-.1,
        'length_unit':'m', 'force_unit':'N', 'energy_unit':'J',
        'element':'C3D8I', 'procedure':'LINEAR STATIC',
        'clamp':'X_MIN U1=U2=U3=0', 'load':'X_MAX uniform traction via consistent QUAD4 CLOADs',
        'other_faces':'traction free', 'configured_threads':1}
DIMS = [.2,.02,.003]
TOLERANCES = {'beam_reference_relative':.02, 'refinement_tip_relative':.01,
              'force_absolute_N':1e-5, 'moment_absolute_Nm':2e-6,
              'free_node_force_absolute_N':1e-7, 'clamp_displacement_absolute_m':1e-12,
              'energy_work_relative':1e-4, 'max_displacement_over_length':.01,
              'max_absolute_strain_component':.001}
LIMITATIONS = ['Synthetic linear-elastic numerical verification only; no physical/material/strength qualification',
               'Euler-Bernoulli is an approximate slender-beam reference, not the exact clamped-face 3D elasticity solution',
               'Two-grid displacement sensitivity is not proof of mesh independence or convergence order',
               'No stress-singularity or maximum-clamp-stress strength claim',
               'Historical v1 mesh native identity is NOT_VERIFIED; v2 native claims apply only to their recorded mesh execution',
               'Local hashes are not authentication against rewriting all evidence',
               'Solver binary hash is not complete native dependency identity, reproducible build or licensing clearance',
               'Configured thread count is not measured CPU use; CPU/GPU cost not measured',
               'Unix process limits are not a hostile-code security sandbox']
RAW = {'structural.inp','structural.dat','structural.sta','structural.cvg','structural.frd','structural.12d','spooles.out','solver.log'}
DERIVED = {'recipe.json','oracle.json','displacements.csv','reactions.csv','energy.csv','deflection.svg'}
FILES = RAW | DERIVED | {'receipt.json'} | {'mesh/'+n for n in gmsh_mesh.FILES|{'manifest.json'}}


def loads(nodes,cells,ends):
    """Integrate constant traction on each verified rectangular end quad."""
    areas=thermal_source.end_node_tributary_areas(nodes,cells,ends,DIMS)['X_MAX']
    return {n:(0.,0.,SPEC['force_z_N']*area/(DIMS[1]*DIMS[2])) for n,area in areas.items()}


def deck(nodes,cells,ends,*,element='C3D8I'):
    if element not in ('C3D8I','C3D8'): raise ValueError('Unsupported structural element')
    lines=['*HEADING','OpenDot synthetic SI cantilever; linear elastic; no physical strength claim','*NODE,NSET=ALL']
    lines += [','.join([str(n)]+[format(x,'.17g') for x in xyz]) for n,xyz in sorted(nodes.items())]
    lines += ['*ELEMENT,TYPE='+element+',ELSET=BODY']
    lines += [','.join(map(str,[e]+c)) for e,c in sorted(cells.items())]
    for name,ns in sorted(ends.items()):
        ids=sorted(ns);lines+=['*NSET,NSET='+name]
        lines += [','.join(map(str,ids[k:k+12])) for k in range(0,len(ids),12)]
    lines += ['*MATERIAL,NAME=SYNTHETIC','*ELASTIC','210000000000.,0.3',
              '*SOLID SECTION,ELSET=BODY,MATERIAL=SYNTHETIC','*BOUNDARY','X_MIN,1,3,0.',
              '*STEP','*STATIC','*CLOAD']
    lines += [f'{n},3,{v[2]:.17g}' for n,v in sorted(loads(nodes,cells,ends).items())]
    lines += ['*NODE PRINT,NSET=ALL','U,RF','*EL PRINT,ELSET=BODY','E,ELSE','*END STEP']
    return ('\n'.join(lines)+'\n').encode('ascii')


def parse_dat(path):
    headers={
        'displacements (vx,vy,vz) for set ALL and time':'displacement',
        'forces (fx,fy,fz) for set ALL and time':'external_force',
        'strains (elem, integ.pnt.,exx,eyy,ezz,exy,exz,eyz) for set BODY and time':'strain',
        'internal energy (element, energy) for set BODY and time':'energy'}
    result={};section=None;preamble=[]
    for raw in shared._read(path).decode('ascii').splitlines():
        line=raw.strip()
        if not line:continue
        matches=[(prefix,name) for prefix,name in headers.items() if line.startswith(prefix)]
        if matches:
            prefix,name=matches[0]
            if name in result or float(line[len(prefix):])!=1.:
                raise ValueError('Duplicate block or unfinished structural time')
            result[name]={};section=name;continue
        if section is None:
            preamble.append(line);continue
        fields=line.split();count={'displacement':4,'external_force':4,'strain':8,'energy':2}[section]
        if len(fields)!=count:raise ValueError('Malformed structural DAT row')
        key=(int(fields[0]),int(fields[1])) if section=='strain' else int(fields[0])
        values=tuple(float(v.replace('D','E')) for v in fields[2 if section=='strain' else 1:])
        if key in result[section] or not all(math.isfinite(v) for v in values):
            raise ValueError('Duplicate or nonfinite structural result')
        result[section][key]=values
    if preamble!=['S T E P       1','INCREMENT     1'] or set(result)!=set(headers.values()) or any(not v for v in result.values()):
        raise ValueError('Missing actual structural outputs or unexpected preamble')
    return result


def _execution_checks(root):
    log=shared._read(root/'solver.log').decode('ascii')
    shared._check_solver_log(log)
    if re.findall(r'^\s*STEP\s+(\d+)\s*$',log,re.M)!=['1'] or log.count('Static analysis was selected')!=1:
        raise ValueError('Unexpected structural procedure or step')
    if 'Factoring the system of equations using the symmetric spooles solver' not in log:
        raise ValueError('Expected linear-static direct-solver diagnostic')
    threads=re.findall(r'Using (?:up to )?(\d+) cpu',log)
    if not threads or any(int(v)!=1 for v in threads):raise ValueError('Solver CPU diagnostics disagree')
    rows=[s.split() for s in shared._read(root/'structural.sta').decode('ascii').splitlines() if re.match(r'^\s*\d',s)]
    if len(rows)!=1 or len(rows[0])!=7 or rows[0][:4]!=['1','1','1','1'] or any(float(v)!=1. for v in rows[0][4:]):
        raise ValueError('Incomplete or unexpected structural step')
    # Linear static uses prespooles, not nonlinear iterations. It writes a header-only CVG.
    expected=['SUMMARY OF C0NVERGENCE INFORMATION',
              'STEP INC ATT ITER CONT. RESID. CORR. RESID. CORR.',
              'EL. FORCE DISP FLUX TEMP.', '(#) (%) (%) (%) (%)']
    actual=[' '.join(v.split()) for v in shared._read(root/'structural.cvg').decode('ascii').splitlines() if v.strip()]
    if actual!=expected:raise ValueError('Unexpected linear-static convergence history')


def _cross(a,b):
    return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])


def analytical_report(nodes,cells,ends,data):
    if set(data['displacement'])!=set(nodes) or set(data['external_force'])!=set(nodes) or set(data['energy'])!=set(cells) or set(data['strain'])!={(e,i) for e in cells for i in range(1,9)}:
        raise ValueError('Missing or wrong structural node/cell/integration-point identity')
    applied=loads(nodes,cells,ends);u=data['displacement'];rf=data['external_force']
    L,b,h=DIMS;F=SPEC['force_z_N'];E=SPEC['young_modulus_Pa'];I=b*h**3/12
    reference=F*L**3/(3*E*I);reference_energy=.5*F*reference
    work=.5*math.fsum(f[k]*u[n][k] for n,f in applied.items() for k in range(3))
    weighted_tip=2*work/F;energy=math.fsum(v[0] for v in data['energy'].values())
    support=[math.fsum(rf[n][k] for n in ends['X_MIN']) for k in range(3)]
    applied_resultant=[math.fsum(f[k] for f in applied.values()) for k in range(3)]
    origin=(0.,b/2,h/2)
    def moments(forces):
        values=[_cross(tuple(nodes[n][k]-origin[k] for k in range(3)),f) for n,f in forces.items()]
        return [math.fsum(v[k] for v in values) for k in range(3)]
    support_moment=moments({n:rf[n] for n in ends['X_MIN']});applied_moment=moments(applied)
    force_residual=[support[k]+applied_resultant[k] for k in range(3)]
    moment_residual=[support_moment[k]+applied_moment[k] for k in range(3)]
    free_error=max(abs(rf[n][k]-applied.get(n,(0.,0.,0.))[k]) for n in nodes if n not in ends['X_MIN'] for k in range(3))
    clamp_error=max(abs(v) for n in ends['X_MIN'] for v in u[n])
    max_displacement=max(math.sqrt(math.fsum(v*v for v in xyz)) for xyz in u.values())
    max_strain=max(abs(v) for row in data['strain'].values() for v in row)
    tip_error=abs(weighted_tip-reference)/abs(reference)
    energy_error=abs(energy-reference_energy)/reference_energy
    work_error=abs(energy-work)/abs(work) if work else None
    checks={'tip_displacement':weighted_tip<0 and tip_error<=TOLERANCES['beam_reference_relative'],
            'clamp_displacement':clamp_error<=TOLERANCES['clamp_displacement_absolute_m'],
            'force_balance':max(map(abs,force_residual))<=TOLERANCES['force_absolute_N'],
            'moment_balance':max(map(abs,moment_residual))<=TOLERANCES['moment_absolute_Nm'],
            'free_node_external_forces':free_error<=TOLERANCES['free_node_force_absolute_N'],
            'energy_work':energy>0 and work>0 and work_error<=TOLERANCES['energy_work_relative'] and all(v[0]>=0 for v in data['energy'].values()),
            'beam_reference_energy':energy_error<=TOLERANCES['beam_reference_relative'],
            'small_displacement':max_displacement/L<=TOLERANCES['max_displacement_over_length'],
            'small_strain':max_strain<=TOLERANCES['max_absolute_strain_component']}
    return {'checks':checks,'tolerances':TOLERANCES,'nodes':len(nodes),'elements':len(cells),
            'strain_integration_points':len(data['strain']),'weighted_tip_displacement_m':weighted_tip,
            'beam_reference_tip_m':reference,'tip_relative_error':tip_error,
            'internal_energy_J':energy,'external_work_J':work,'beam_reference_energy_J':reference_energy,
            'energy_work_relative_error':work_error,'beam_energy_relative_error':energy_error,
            'support_resultant_N':support,'applied_resultant_N':applied_resultant,
            'support_moment_Nm':support_moment,'applied_moment_Nm':applied_moment,
            'force_residual_N':force_residual,'moment_residual_Nm':moment_residual,
            'max_free_node_force_error_N':free_error,'max_clamp_displacement_m':clamp_error,
            'max_displacement_m':max_displacement,'max_absolute_strain_component':max_strain,
            'RF_interpretation':'Total external force: reaction at unloaded clamp; applied CLOAD at loaded free nodes; zero at unloaded free nodes',
            'energy_interpretation':'Sum of native whole-element ELSE, compared with 0.5 sum applied nodal force dot displacement'}


def oracle(root,nodes,cells,ends):
    _execution_checks(root);data=parse_dat(root/'structural.dat')
    return analytical_report(nodes,cells,ends,data),data


def figures(nodes,cells,ends,data):
    applied=loads(nodes,cells,ends);L,b,h=DIMS;E=SPEC['young_modulus_Pa'];F=SPEC['force_z_N'];I=b*h**3/12
    reference=lambda x:F*x*x*(3*L-x)/(6*E*I)
    rows=[['node','x_m','y_m','z_m','ux_m','uy_m','uz_m','beam_reference_uz_m']]
    reactions=[['node','x_m','y_m','z_m','RFx_N','RFy_N','RFz_N','applied_Fz_N','is_clamped']]
    for n,xyz in sorted(nodes.items()):
        rows.append([n,*xyz,*data['displacement'][n],reference(xyz[0])])
        reactions.append([n,*xyz,*data['external_force'][n],applied.get(n,(0.,0.,0.))[2],n in ends['X_MIN']])
    energies=[['element','native_ELSE_J']]+[[e,v[0]] for e,v in sorted(data['energy'].items())]
    scale=abs(reference(L))*1.05
    dots=''.join(f'<circle cx="{80+640*xyz[0]/L:.6f}" cy="{75-280*data["displacement"][n][2]/scale:.6f}" r="2" fill="#2563eb" fill-opacity=".3"/>' for n,xyz in sorted(nodes.items()))
    curve=' '.join(f'{80+640*j/100:.6f},{75-280*reference(L*j/100)/scale:.6f}' for j in range(101))
    ticks=''
    for j in range(5):
        x=80+640*j/4;y=75+280*j/4
        ticks+=f'<text x="{x}" y="385" text-anchor="middle">{L*j/4:g}</text><text x="72" y="{y+4}" text-anchor="end">{-scale*j/4*1e6:.2f}</text>'
    svg=(f'<svg xmlns="http://www.w3.org/2000/svg" width="820" height="470" viewBox="0 0 820 470"><rect width="820" height="470" fill="white"/>'
         '<g font-family="sans-serif" font-size="14" fill="#172554"><text x="35" y="27">Synthetic linear-elastic cantilever: parsed nodal deflection</text>'
         '<text x="35" y="52">Uz (micrometers)</text><path d="M80 65 V360 H735" stroke="#475569" fill="none"/>'
         f'{ticks}<polyline points="{curve}" stroke="#e11d48" stroke-width="2" stroke-dasharray="7 5" fill="none"/>{dots}'
         '<text x="365" y="410">x (m)</text><text x="35" y="438">Blue: CalculiX U; dashed red: approximate Euler-Bernoulli reference</text>'
         '<text x="35" y="460">Fz=-0.1 N; C3D8I; small strain; no physical or strength qualification</text></g></svg>').encode()
    return {'displacements.csv':shared._csv(rows),'reactions.csv':shared._csv(reactions),
            'energy.csv':shared._csv(energies),'deflection.svg':svg}


def _source():
    source=geometry._source_provenance(__file__)
    source['shared_helpers_sha256']=geometry.sha256(Path(shared.__file__).read_bytes())
    source['mesh_verifier_sha256']=geometry.sha256(Path(gmsh_mesh.__file__).read_bytes())
    source['geometry_helpers_sha256']=geometry.sha256(Path(geometry.__file__).read_bytes())
    source['tributary_area_helper_sha256']=geometry.sha256(Path(thermal_source.__file__).read_bytes())
    return source


def _mesh(root):
    gmsh_mesh.verify_mesh_artifacts(root)
    recipe=shared._json(root/'recipe.json')
    if recipe['dimensions_m']!=DIMS or recipe['divisions'] not in ([20,4,2],[40,8,4]):
        raise ValueError('Structural case requires fixed SI dimensions and frozen coarse/refined grids')
    nodes,cells,ends=shared.mesh_data(root/'beam.msh')
    if len(cells)>10000:raise ValueError('Structural case bounded to 10000 elements')
    return nodes,cells,ends


def run_structural(mesh_dir,output_dir,*,solver_executable,timeout_s=60,element='C3D8I'):
    """Run one frozen case; C3D8 is an intentional diagnostic, never accepted."""
    if type(timeout_s) not in (int,float) or not math.isfinite(timeout_s) or not 1<=timeout_s<=60:
        raise ValueError('Timeout must be 1..60 seconds')
    if element not in ('C3D8I','C3D8'):raise ValueError('Unsupported structural element')
    executable=shutil.which(str(solver_executable))
    if not executable:raise ValueError('Configured installed CalculiX executable unavailable')
    executable=str(Path(executable).resolve());binary_hash=geometry.sha256(Path(executable).read_bytes())
    _,snapshot=shared._snapshot_mesh(mesh_dir)
    _mesh(Path(mesh_dir))
    out=geometry._new_output_directory(output_dir);wall=None
    try:
        (out/'mesh').mkdir()
        for n,b in snapshot.items():(out/'mesh'/n).write_bytes(b)
        nodes,cells,ends=_mesh(out/'mesh');source=_source()
        mesh_runtime=shared._json(out/'mesh/receipt.json').get('gmsh_runtime')
        recipe={'recipe':RECIPE,'spec':SPEC,'dimensions_m':DIMS,'tolerances':TOLERANCES,
                'actual_element':element,'source':source,'protocol_freeze_commit':'5da9e2e4973ed6a6ef4122c01d879f770b44c22b'}
        shared._write(out/'recipe.json',recipe)
        (out/'structural.inp').write_bytes(deck(nodes,cells,ends,element=element))
        started=time.monotonic()
        try:shared._execute(executable,out,timeout_s,job_name='structural')
        finally:wall=time.monotonic()-started
        shared._check_elapsed(wall,timeout_s)
        if geometry.sha256(Path(executable).read_bytes())!=binary_hash:raise ValueError('Solver executable changed during run')
        report,data=oracle(out,nodes,cells,ends);shared._write(out/'oracle.json',report)
        if not all(report['checks'].values()):raise ValueError('Structural acceptance failed: '+str(report['checks']))
        if element!='C3D8I':raise ValueError('Full-integration diagnostic is not eligible for acceptance')
        for n,b in figures(nodes,cells,ends,data).items():(out/n).write_bytes(b)
        receipt={'schema_version':'1','recipe':RECIPE,'status':'STRUCTURAL_BENCHMARK_PASS','source':source,
                 'execution_time_utc':datetime.now(timezone.utc).isoformat(),
                 'solver':{'version':'2.23','binary_sha256':binary_hash,'command':[executable,'-i','structural']},
                 'timeout_s':timeout_s,'compute':{'subprocess_wall_time_s':wall,'configured_threads':1,
                    'cpu_time_s':'NOT_MEASURED','gpu_usage':'NOT_MEASURED','cost':'NOT_MEASURED'},
                 'physical_validation':'NOT_PERFORMED','mesh_independence':'NOT_ESTABLISHED',
                 'refinement_check':'NOT_EVALUATED_SINGLE_PACK',
                 'mesh_native_identity':mesh_runtime['status'] if mesh_runtime else 'NOT_VERIFIED',
                 'mesh_runtime':mesh_runtime,
                 'limitations':LIMITATIONS,'hashes':{n:geometry.sha256(shared._read(out/n)) for n in FILES-{'receipt.json'}}}
        shared._publish_pack(out,receipt,FILES)
        return verify_structural_artifacts(out)
    except BaseException as exc:
        for n in ('receipt.json','manifest.json','receipt.pending','manifest.pending'):(out/n).unlink(missing_ok=True)
        hashes={}
        for n in sorted(FILES-{'receipt.json'}):
            p=out/n
            if p.is_file() and not p.is_symlink() and p.stat().st_size<=gmsh_mesh.MAX_BYTES:
                hashes[n]=geometry.sha256(shared._read(p))
        shared._write(out/'failure.json',{'status':'STRUCTURAL_FAILED','subprocess_wall_time_s':wall,
                      'error_type':type(exc).__name__,'error':str(exc),'available_artifact_hashes':hashes,
                      'solver_binary_sha256':binary_hash,'actual_element':element})
        raise


def _verify_structural_artifacts_v1(directory):
    root=Path(directory)
    if any(p.is_symlink() for p in [root,*root.parents]):raise ValueError('Symlinked artifact directory')
    manifest=shared._verify_manifest(root,FILES,label='structural')
    nodes,cells,ends=_mesh(root/'mesh');r=shared._json(root/'receipt.json');recipe=shared._json(root/'recipe.json')
    if recipe!={'recipe':RECIPE,'spec':SPEC,'dimensions_m':DIMS,'tolerances':TOLERANCES,
                'actual_element':'C3D8I','source':r.get('source'),'protocol_freeze_commit':'5da9e2e4973ed6a6ef4122c01d879f770b44c22b'}:
        raise ValueError('False structural recipe, element, units or tolerances')
    if shared._read(root/'structural.inp')!=deck(nodes,cells,ends):raise ValueError('Structural input/mesh/BC/load identity mismatch')
    mesh_runtime=shared._json(root/'mesh/receipt.json').get('gmsh_runtime')
    claims={'schema_version':'1','recipe':RECIPE,'status':'STRUCTURAL_BENCHMARK_PASS',
            'physical_validation':'NOT_PERFORMED','mesh_independence':'NOT_ESTABLISHED',
            'refinement_check':'NOT_EVALUATED_SINGLE_PACK',
                 'mesh_native_identity':mesh_runtime['status'] if mesh_runtime else 'NOT_VERIFIED',
                 'mesh_runtime':mesh_runtime,'limitations':LIMITATIONS}
    if any(r.get(k)!=v for k,v in claims.items()):raise ValueError('Unsupported structural receipt claims')
    source=r.get('source',{})
    for key in ('adapter_sha256','shared_helpers_sha256','mesh_verifier_sha256','geometry_helpers_sha256','tributary_area_helper_sha256'):
        if not re.fullmatch('[a-f0-9]{64}',str(source.get(key,''))):raise ValueError('Missing structural source/helper binding')
    solver=r.get('solver',{});command=solver.get('command',[])
    if solver.get('version')!='2.23' or not re.fullmatch('[a-f0-9]{64}',str(solver.get('binary_sha256',''))) or len(command)!=3 or not Path(command[0]).is_absolute() or command[1:]!=['-i','structural']:
        raise ValueError('Invalid solver provenance')
    c=r.get('compute',{});wall=c.get('subprocess_wall_time_s');timeout=r.get('timeout_s')
    shared._check_elapsed(wall,timeout)
    if not 1<=timeout<=60 or c.get('configured_threads')!=1 or any(c.get(k)!='NOT_MEASURED' for k in ('cpu_time_s','gpu_usage','cost')):
        raise ValueError('Invalid structural compute claims')
    if r.get('hashes')!={n:manifest['artifacts'][n]['sha256'] for n in FILES-{'receipt.json'}}:raise ValueError('Receipt hash bindings failed')
    report,data=oracle(root,nodes,cells,ends)
    if not all(report['checks'].values()) or shared._json(root/'oracle.json')!=report:raise ValueError('False or failed structural analytical results')
    for n,b in figures(nodes,cells,ends,data).items():
        if shared._read(root/n)!=b:raise ValueError('Structural plot/backing data mismatch')
    return r


def _structural_verification_profile(profile):
    if type(profile) is not str or profile not in ('conditional_elastic_v2','artifact_v1'):
        raise ValueError('Unsupported structural verification profile')
    return profile


def verify_structural_artifacts(directory,*,profile='conditional_elastic_v2'):
    """Require conditional elastic consistency by default; never rewrite a pack.

    The explicit artifact_v1 profile preserves historical admission/receipt
    behavior. It does not establish v2 consistency or scientific acceptance.
    Unsupported cases raise ValueError; no historical fallback is automatic.
    """
    _structural_verification_profile(profile)
    receipt=_verify_structural_artifacts_v1(directory)
    if profile=='artifact_v1':return receipt
    energy=_checked_elastic_energy(directory)
    return {'schema_version':'2','verification_profile':'conditional_elastic_v2',
            'status':'CONDITIONAL_STRUCTURAL_CONSISTENCY_PASS',
            'artifact_schema_version':'1','artifact_receipt':receipt,'elastic_energy':energy,
            'scientific_accepted':False,'physical_validation':'NOT_PERFORMED',
            'independent_review':'NOT_EVALUATED','mesh_independence':'NOT_ESTABLISHED',
            'conditional_assumptions':{
                'model':'Fixed initially unstressed, no-thermal-strain, zero-history isotropic linear-static C3D8I recipe',
                'no_subnormal_or_underflow':energy['print_profile']['no_subnormal_or_underflow'],
                'formal_arithmetic_error_bound':energy['arithmetic_policy']['formal_error_bound']}}


# The numerical contract is unchanged. The default v2 profile and the optional
# API reuse this same kernel after one canonical strict-admission implementation.
# See docs/structural-elastic-energy.md for the source-frozen uncertainty scope.
_ELASTIC_CONTRACT = 'structural.elastic_energy.ccx223.e13_6.v1'
_ELASTIC_GAUSS = tuple((x*0.577350269189626,y*0.577350269189626,z*0.577350269189626)
                       for z in (-1,1) for y in (-1,1) for x in (-1,1))
_ELASTIC_ARITHMETIC_RELATIVE = 1e-10


def _elastic_print_quantum(token):
    """One last-place quantum; canonical zero is conditional on no underflow."""
    if token in ('0.000000E+00','+0.000000E+00','-0.000000E+00'):
        return 0.
    match=re.fullmatch(r'[+-]?[1-9]\.[0-9]{6}E([+-][0-9]{2})',token)
    if match is None:
        raise ValueError('Unsupported elastic energy printed precision or exponent')
    return 10.**(int(match[1])-6)


def _elastic_print_budgets(path,data):
    """Extract precision only after parse_dat has admitted all DAT semantics."""
    prefixes=(('strains (elem, integ.pnt.,exx,eyy,ezz,exy,exz,eyz) for set BODY and time','strain'),
              ('internal energy (element, energy) for set BODY and time','energy'),
              ('displacements (vx,vy,vz) for set ALL and time',None),
              ('forces (fx,fy,fz) for set ALL and time',None))
    result={'strain':{},'energy':{}};section=None
    for raw in shared._read(path).decode('ascii').splitlines():
        line=raw.strip()
        if not line:continue
        header=next(((prefix,name) for prefix,name in prefixes if line.startswith(prefix)),None)
        if header is not None:
            section=header[1];continue
        if section is None:continue
        fields=line.split();offset=2 if section=='strain' else 1
        key=(int(fields[0]),int(fields[1])) if section=='strain' else int(fields[0])
        tokens=fields[offset:]
        quanta=tuple(_elastic_print_quantum(v) for v in tokens)
        # Not a second admission parser: bind extracted tokens to the already
        # admitted identities and values, refusing a changed/repeated read.
        if key in result[section] or key not in data[section] or tuple(float(v) for v in tokens)!=data[section][key]:
            raise ValueError('Elastic energy raw/parsed output identity mismatch')
        result[section][key]=quanta
    if any(set(result[name])!=set(data[name]) for name in result):
        raise ValueError('Elastic energy raw/parsed output identity mismatch')
    return result


def _elastic_jacobians(nodes,cell):
    """Eight physical-node detJ values, in CalculiX 2.23 integration order."""
    if len(cell)!=8 or len(set(cell))!=8 or any(n not in nodes for n in cell):
        raise ValueError('Unsupported elastic energy physical-node identity')
    weights=[]
    for local in _ELASTIC_GAUSS:
        derivatives=[tuple(sign[b]*math.prod(1+sign[k]*local[k] for k in range(3) if k!=b)/8
                           for b in range(3)) for sign in thermal_source.SIGNS]
        jac=[[math.fsum(nodes[n][a]*d[b] for n,d in zip(cell,derivatives))
              for b in range(3)] for a in range(3)]
        a,b,c=jac
        determinant=math.fsum((a[0]*b[1]*c[2],a[1]*b[2]*c[0],a[2]*b[0]*c[1],
                               -a[2]*b[1]*c[0],-a[1]*b[0]*c[2],-a[0]*b[2]*c[1]))
        if not math.isfinite(determinant) or determinant<=0:
            raise ValueError('Nonpositive or nonfinite elastic energy Jacobian')
        weights.append(determinant)
    return tuple(weights)


def _elastic_energy_report(nodes,cells,data,budgets):
    """Fixed-material tensor-strain quadrature, not a displacement solver."""
    expected={(e,i) for e in cells for i in range(1,9)}
    if not cells or set(data['strain'])!=expected or set(data['energy'])!=set(cells) or set(budgets['strain'])!=expected or set(budgets['energy'])!=set(cells):
        raise ValueError('Missing or wrong elastic energy element/integration-point identity')
    young=210000000000.;poisson=.3
    mu=young/(2*(1+poisson));lam=young*poisson/((1+poisson)*(1-2*poisson))
    rows=[]
    for element,cell in sorted(cells.items()):
        energies=[];errors=[];weights=_elastic_jacobians(nodes,cell)
        for ip,weight in enumerate(weights,1):
            strain=data['strain'][element,ip];delta=budgets['strain'][element,ip]
            if len(strain)!=6 or len(delta)!=6 or any(not math.isfinite(v) for v in (*strain,*delta)) or any(v<0 for v in delta):
                raise ValueError('Unsupported elastic energy strain/precision values')
            trace=math.fsum(strain[:3]);dtrace=math.fsum(delta[:3]);factors=(1,1,1,2,2,2)
            density=lam/2*trace**2+mu*math.fsum(c*v*v for c,v in zip(factors,strain))
            bound=lam/2*(2*abs(trace)*dtrace+dtrace*dtrace)+mu*math.fsum(
                c*(2*abs(v)*d+d*d) for c,v,d in zip(factors,strain,delta))
            energies.append(weight*density);errors.append(weight*bound)
        native=data['energy'][element];native_delta=budgets['energy'][element]
        if len(native)!=1 or len(native_delta)!=1 or not math.isfinite(native[0]) or native[0]<0 or not math.isfinite(native_delta[0]) or native_delta[0]<0:
            raise ValueError('Unsupported elastic energy ELSE/precision values')
        energy=math.fsum(energies);printed_bound=math.fsum((*errors,native_delta[0]))
        arithmetic_bound=_ELASTIC_ARITHMETIC_RELATIVE*max(energy,abs(native[0]))
        bound=printed_bound+arithmetic_bound;residual=abs(energy-native[0])
        if not all(math.isfinite(v) for v in (energy,printed_bound,arithmetic_bound,bound,residual)):
            raise ValueError('Nonfinite elastic energy arithmetic')
        if residual>bound:
            raise ValueError(f'Elastic energy mismatch for element {element}: residual {residual:.17g} J exceeds bound {bound:.17g} J')
        rows.append({'element':element,'strain_energy_J':energy,'native_ELSE_J':native[0],
                     'absolute_residual_J':residual,'printed_error_bound_J':printed_bound,
                     'arithmetic_allowance_J':arithmetic_bound,'acceptance_bound_J':bound,
                     'jacobian_determinants_m3':list(weights)})
    total=math.fsum(row['strain_energy_J'] for row in rows)
    native_total=math.fsum(row['native_ELSE_J'] for row in rows)
    return {'schema_version':'1','status':'CONDITIONAL_ELASTIC_ENERGY_CONSISTENCY_PASS','contract':_ELASTIC_CONTRACT,
            'recipe':RECIPE,'scope':'Optional per-element E/ELSE consistency under the fixed model and declared print/arithmetic assumptions',
            'scientific_accepted':False,'physical_validation':'NOT_PERFORMED',
            'independent_review':'NOT_EVALUATED','mesh_independence':'NOT_ESTABLISHED',
            'material':{'young_modulus_Pa':young,'poisson_ratio':poisson},
            'strain_components':['xx','yy','zz','xy','xz','yz'],'shear_convention':'TENSOR',
            'quadrature':'Eight physical-node Jacobians; CalculiX 2.23 x-fast Gauss order; unit weights',
            'print_profile':{'format':'1P E13.6','nonzero_exponent_digits':2,'rounding_bound':'ONE_LAST_PLACE_QUANTUM',
                             'zero_quantum':0.,'no_subnormal_or_underflow':'ASSUMED_NOT_VERIFIED'},
            'arithmetic_policy':{'relative_allowance':_ELASTIC_ARITHMETIC_RELATIVE,'absolute_floor_J':0.,
                                 'formal_error_bound':'NOT_PROVED'},
            'elements':len(rows),'strain_integration_points':len(expected),'per_element':rows,
            'strain_energy_sum_J':total,'native_ELSE_sum_J':native_total,
            'sum_absolute_residual_J':abs(total-native_total),
            'sum_acceptance_bound_J':math.fsum(row['acceptance_bound_J'] for row in rows),
            'maximum_element_absolute_residual_J':max(row['absolute_residual_J'] for row in rows),
            'limitations':['Restricted to the existing initially unstressed, no-thermal-strain linear-static C3D8I recipe',
                           'No general material, nonlinear/history, nodal-strain reconstruction or physical validation',
                           'No authentication against coordinated evidence rewriting; no default verifier behavior change',
                           'Normal finite output/no-underflow is a conditional profile, not a fact proven by DAT',
                           'The arithmetic allowance is a declared policy, not a formal native-binary error proof']}


def _checked_elastic_energy(directory):
    """Shared energy entry point; the caller must first perform strict admission."""
    root=Path(directory);nodes,cells,_=_mesh(root/'mesh')
    data=parse_dat(root/'structural.dat')
    budgets=_elastic_print_budgets(root/'structural.dat',data)
    return _elastic_energy_report(nodes,cells,data,budgets)


def verify_elastic_energy(directory):
    """Return the existing scoped energy report after canonical strict admission.

    This optional API preserves its report and numerical/error contract while
    the default structural v2 profile requires the same energy kernel. A pass
    remains conditional and does not establish scientific acceptance.
    """
    _verify_structural_artifacts_v1(directory)
    return _checked_elastic_energy(directory)


def compare_refinement(coarse_dir,refined_dir,*,profile='conditional_elastic_v2'):
    """Require v2 for both grids; artifact_v1 is explicit historical comparison."""
    _structural_verification_profile(profile)
    coarse,refined=Path(coarse_dir),Path(refined_dir)
    verified=[verify_structural_artifacts(root,profile=profile) for root in (coarse,refined)]
    divisions=[shared._json(root/'mesh/recipe.json')['divisions'] for root in (coarse,refined)]
    if divisions!=[[20,4,2],[40,8,4]]:raise ValueError('Expected distinct frozen coarse then refined grids')
    receipts=[shared._json(root/'receipt.json') for root in (coarse,refined)]
    if receipts[0]['solver']!=receipts[1]['solver'] or receipts[0]['source']!=receipts[1]['source']:
        raise ValueError('Refinement solver/source identity mismatch')
    reports=[shared._json(root/'oracle.json') for root in (coarse,refined)]
    u,v=[r['weighted_tip_displacement_m'] for r in reports];change=abs(u-v)/abs(v)
    if change>TOLERANCES['refinement_tip_relative']:raise ValueError('Refinement sensitivity criterion failed')
    result={'status':'STRUCTURAL_REFINEMENT_PASS','relative_tip_change':change,
            'tolerance':TOLERANCES['refinement_tip_relative'],'coarse_tip_m':u,'refined_tip_m':v,
            'coarse_receipt_sha256':geometry.sha256(shared._read(coarse/'receipt.json')),
            'refined_receipt_sha256':geometry.sha256(shared._read(refined/'receipt.json')),
            'mesh_independence':'NOT_ESTABLISHED','physical_validation':'NOT_PERFORMED',
            'mesh_native_identity':{name:r['mesh_native_identity'] for name,r in zip(('coarse','refined'),receipts)}}
    if profile=='conditional_elastic_v2':
        result.update(schema_version='2',verification_profile='conditional_elastic_v2',
                      status='CONDITIONAL_STRUCTURAL_REFINEMENT_PASS',scientific_accepted=False,
                      independent_review='NOT_EVALUATED',
                      conditional_assumptions=dict(verified[0]['conditional_assumptions']),
                      input_verification_status={name:r['status'] for name,r in zip(('coarse','refined'),verified)})
    return result


def main(argv=None):
    import argparse
    p=argparse.ArgumentParser(description='Bounded external CalculiX synthetic cantilever')
    sub=p.add_subparsers(dest='command',required=True)
    run=sub.add_parser('run');run.add_argument('mesh_dir');run.add_argument('output_dir')
    run.add_argument('--solver',required=True);run.add_argument('--timeout-s',type=float,default=60)
    run.add_argument('--element',choices=('C3D8I','C3D8'),default='C3D8I')
    verify=sub.add_parser('verify');verify.add_argument('directory')
    compare=sub.add_parser('compare');compare.add_argument('coarse_dir');compare.add_argument('refined_dir')
    a=p.parse_args(argv)
    if a.command=='run':result=run_structural(a.mesh_dir,a.output_dir,solver_executable=a.solver,timeout_s=a.timeout_s,element=a.element)
    elif a.command=='verify':result=verify_structural_artifacts(a.directory)
    else:result=compare_refinement(a.coarse_dir,a.refined_dir)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
