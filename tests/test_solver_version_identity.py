"""Synthetic declared-version contracts only; never execute a native solver."""
import itertools
import json
import math
import shutil

import pytest

from opendot_engineering.executors import geometry, gmsh_mesh
from opendot_engineering.executors import thermal_conduction as thermal
from opendot_engineering.executors import structural_beam as structural
from opendot_engineering.executors import thermal_source
from test_gmsh_mesh import cad_pack  # Reuse the existing synthetic CAD fixture.


def test_shared_gate_rejects_contradictory_versions():
    log = ('CalculiX Version 2.23, synthetic fixture\n'
           'Job finished\n'
           'CalculiX Version 2.24, contradictory fixture\n')
    with pytest.raises(ValueError, match='version'):
        thermal._check_solver_log(log)


HEADER = 'CalculiX Version 2.23, synthetic fixture'
INVALID_HEADERS = [
    pytest.param('', id='absent'),
    pytest.param('CalculiX Version 2.24, synthetic fixture', id='wrong'),
    pytest.param(HEADER + '\nCalculiX Version 2.24, fixture', id='mixed-after'),
    pytest.param('CalculiX Version 2.24, fixture\n' + HEADER, id='mixed-before'),
    pytest.param(HEADER + '\n' + HEADER, id='repeated'),
    pytest.param(HEADER + ' CalculiX Version 2.24, fixture', id='same-line-mixed'),
    pytest.param('prefix ' + HEADER, id='embedded'),
    pytest.param('CalculiX Version 2.23', id='missing-comma'),
    pytest.param('CalculiX Version 2.230, fixture', id='extended-version'),
    pytest.param('CalculiX Version 2.23.1, fixture', id='patch-version'),
    pytest.param('CalculiX Version 2.23-dev, fixture', id='suffix-version'),
    pytest.param('CalculiX Version DEVELOPMENT, fixture', id='development-version'),
    pytest.param('CalculiX Version 2.23 i8, fixture', id='variant-version'),
    pytest.param(HEADER + '\nCalculiX Version DEVELOPMENT, fixture', id='mixed-development'),
    pytest.param(HEADER + '\nCalculiX Version 2.23 i8, fixture', id='mixed-variant'),
    pytest.param('CalculiX Version , fixture', id='missing-version'),
    pytest.param('CalculiX Version\n2.23, fixture', id='split-version'),
    pytest.param('CalculiX\nVersion 2.23, fixture', id='split-marker'),
    pytest.param('calculix version 2.23, fixture', id='wrong-case'),
    pytest.param(HEADER + '\ncalculix version 2.24, fixture', id='mixed-case'),
    pytest.param(HEADER + '\nCalculiX\tVersion 2.24, fixture', id='mixed-spacing'),
    pytest.param(HEADER + '\nCalculiX Version2.24, fixture', id='mixed-malformed'),
    pytest.param(HEADER + '\nCalculiX Version', id='mixed-incomplete'),
]


@pytest.mark.parametrize('header', INVALID_HEADERS)
def test_shared_gate_rejects_invalid_declarations(header):
    with pytest.raises(ValueError, match='version'):
        thermal._check_solver_log(header + '\nJob finished\n')


@pytest.mark.parametrize('header', [HEADER, '  ' + HEADER, '\t' + HEADER,
                                     HEADER + '\r', 'CalculiX Version 2.23,',
                                     'CalculiX Version 2.23, Copyright(C) 1998-2025 Guido Dhondt'])
def test_shared_gate_accepts_single_supported_header(header):
    thermal._check_solver_log(header + '\nJob finished\n')


@pytest.mark.parametrize('ending', ['', 'Job unfinished\n',
    'Job finished\nJob finished\n', 'Job finished\nwarning: fixture\n',
    'Job finished\nERROR: fixture\n'])
def test_shared_completion_and_diagnostic_gates_remain(ending):
    with pytest.raises(ValueError):
        thermal._check_solver_log(HEADER + '\n' + ending)


# Build complete, deliberately synthetic packs. Acceptance helpers are not
# patched: these tests reach the shared log gate through both public verifiers.
def _write(path, value):
    path.write_bytes(geometry.canonical_bytes(value))


def _reseal(root, module):
    receipt = json.loads((root/'receipt.json').read_bytes())
    receipt['hashes'] = {name: geometry.sha256((root/name).read_bytes())
                         for name in module.FILES - {'receipt.json'}}
    _write(root/'receipt.json', receipt)
    _write(root/'manifest.json', {'schema_version': '1', 'hash_algorithm': 'sha256',
        'artifacts': {name: {'sha256': geometry.sha256((root/name).read_bytes()),
                            'bytes': (root/name).stat().st_size}
                      for name in module.FILES}})


def _synthetic_mesh(root, cad):
    root.mkdir()
    for target, source in [('beam.step', 'beam.step'), ('cad-receipt.json', 'receipt.json'),
                           ('cad-parameters.json', 'parameters.json'),
                           ('cad-manifest.json', 'manifest.json')]:
        shutil.copyfile(cad/source, root/target)
    dims = [.2, .02, .003]
    nx, ny, nz = 20, 4, 2
    nodes, ids, cells, faces = {}, {}, {}, []
    for k, j, i in itertools.product(range(nz+1), range(ny+1), range(nx+1)):
        n = len(nodes)+1
        ids[i, j, k] = n
        nodes[n] = (.2*i/nx, .02*j/ny, .003*k/nz)
    for k, j, i in itertools.product(range(nz), range(ny), range(nx)):
        cells[len(cells)+1] = [ids[a, b, c] for a, b, c in (
            (i,j,k), (i+1,j,k), (i+1,j+1,k), (i,j+1,k),
            (i,j,k+1), (i+1,j,k+1), (i+1,j+1,k+1), (i,j+1,k+1))]
    for j, k in itertools.product(range(ny), range(nz)):
        for i, tag in [(0, 2), (nx, 3)]:
            faces.append((tag, [ids[i,j,k], ids[i,j+1,k], ids[i,j+1,k+1], ids[i,j,k+1]]))
    for i, k in itertools.product(range(nx), range(nz)):
        for j, tag in [(0, 4), (ny, 5)]:
            faces.append((tag, [ids[i,j,k], ids[i+1,j,k], ids[i+1,j,k+1], ids[i,j,k+1]]))
    for i, j in itertools.product(range(nx), range(ny)):
        for k, tag in [(0, 6), (nz, 7)]:
            faces.append((tag, [ids[i,j,k], ids[i+1,j,k], ids[i+1,j+1,k], ids[i,j+1,k]]))
    lines = ['$MeshFormat', '2.2 0 8', '$EndMeshFormat', '$PhysicalNames', '7']
    lines += [f'{d} {tag} "{name}"' for name, (d, tag) in gmsh_mesh.REGIONS.items()]
    lines += ['$EndPhysicalNames', '$Nodes', str(len(nodes))]
    lines += [str(n)+' '+' '.join(format(x, '.17g') for x in p) for n, p in nodes.items()]
    lines += ['$EndNodes', '$Elements', str(len(cells)+len(faces))]
    lines += [f'{e} 5 2 1 1 '+' '.join(map(str, ns)) for e, ns in cells.items()]
    lines += [f'{len(cells)+e} 3 2 {tag} {tag} '+' '.join(map(str, ns))
              for e, (tag, ns) in enumerate(faces, 1)]
    (root/'beam.msh').write_text('\n'.join(lines+['$EndElements', '']))
    measured = gmsh_mesh._inspect_mesh(root/'beam.msh', dims, [nx, ny, nz])
    worker = {'gmsh_version': '4.15.2', 'imported_volume_m3': 1.2e-5,
        'imported_bbox_m': [0., 0., 0., *dims], 'quality': measured['independent_quality'],
        'nodes': len(nodes), 'volume_elements': len(cells),
        'regions': {name: {'dimension': d, 'physical_tag': tag,
                          'entity_tags': measured['region_entity_tags'][name]}
                    for name, (d, tag) in gmsh_mesh.REGIONS.items()}}
    source = {'adapter_sha256': 'a'*64, 'worker_sha256': 'b'*64}
    _write(root/'recipe.json', {'source': source, 'schema_version': '1',
        'recipe': gmsh_mesh.LEGACY_RECIPE, 'dimensions_m': dims, 'divisions': [nx,ny,nz],
        'step_unit': 'mm', 'mesh_unit': 'm', 'conversion': 'Geometry.OCCTargetUnit=M before STEP import',
        'element_family': 'hexahedron', 'element_order': 1, 'gmsh_version': '4.15.2',
        'configured_gmsh_threads': 1})
    _write(root/'worker.json', worker)
    (root/'process.log').write_text('SYNTHETIC FIXTURE: NO NATIVE EXECUTION\n')
    _write(root/'receipt.json', {'schema_version': '1', 'recipe': gmsh_mesh.LEGACY_RECIPE,
        'status': 'MESH_BENCHMARK_PASS', 'source': source,
        'cad_source': json.loads((cad/'receipt.json').read_bytes())['source'],
        'cad_parameters': json.loads((cad/'parameters.json').read_bytes())['parameters'],
        'measurements': measured, 'worker': worker,
        'compute': {'subprocess_wall_time_s': 0., 'configured_gmsh_threads': 1,
                    'cpu_time_s': 'NOT_MEASURED', 'cpu_core_hours': 'NOT_MEASURED',
                    'gpu_usage': 'NOT_MEASURED', 'cost': 'NOT_MEASURED'},
        'scientific_acceptance': 'NOT_EVALUATED', 'solver_execution': 'NOT_PERFORMED',
        'mesh_independence': 'NOT_EVALUATED'})
    _reseal(root, gmsh_mesh)
    return nodes, cells, {'X_MIN': {n for n, p in nodes.items() if p[0] == 0},
                          'X_MAX': {n for n, p in nodes.items() if p[0] == .2}}


def _synthetic_data(nodes, cells, ends, kind):
    areas = thermal_source.end_node_tributary_areas(nodes, cells, ends, structural.DIMS)
    if kind == 'thermal':
        reaction = {n: (0.,) for n in nodes}
        for side, sign in [('X_MIN', -1), ('X_MAX', 1)]:
            for n, area in areas[side].items():
                reaction[n] = (sign*5000*area,)
        return {'temperature': {n: (300+500*p[0],) for n, p in nodes.items()},
                'reaction': reaction,
                'flux': {(e, ip): (-5000., 0., 0.) for e in cells for ip in range(1,9)}}
    L, b, h = structural.DIMS
    F, E, I = -.1, 210e9, b*h**3/12
    displacement = {n: (-(p[2]-h/2)*F*p[0]*(2*L-p[0])/(2*E*I), 0.,
                        F*p[0]**2*(3*L-p[0])/(6*E*I)) for n, p in nodes.items()}
    denom = math.fsum(a*(nodes[n][2]-h/2)**2 for n, a in areas['X_MIN'].items())
    forces = {n: (0., 0., 0.) for n in nodes}
    for n, area in areas['X_MIN'].items():
        forces[n] = (-.02*area*(nodes[n][2]-h/2)/denom, 0., .1*area/(b*h))
    forces.update(structural.loads(nodes, cells, ends))
    strains, energies = {}, {}
    for e, ids in cells.items():
        x0, y0, z0 = (min(nodes[n][k] for n in ids) for k in range(3))
        x1, y1, z1 = (max(nodes[n][k] for n in ids) for k in range(3))
        for ip, (xi, _, zi) in enumerate(thermal_source.G2, 1):
            x, z = (x0+x1)/2+xi*(x1-x0)/2, (z0+z1)/2+zi*(z1-z0)/2
            exx = -(z-h/2)*F*(L-x)/(E*I)
            strains[e,ip] = (exx, -.3*exx, -.3*exx, 0., 0., 0.)
        energies[e] = (F*F/(2*E*I*I)*((L-x0)**3-(L-x1)**3)/3
                       *(y1-y0)*((z1-h/2)**3-(z0-h/2)**3)/3,)
    return {'displacement': displacement, 'external_force': forces,
            'strain': strains, 'energy': energies}


def _write_raw(root, kind, data):
    headers = ([('temperature', 'temperatures for set ALL and time'),
                ('reaction', 'heat generation for set ALL and time'),
                ('flux', 'heat flux (elem, integ.pnt.,qx,qy,qz) for set BODY and time')]
               if kind == 'thermal' else [
                ('displacement', 'displacements (vx,vy,vz) for set ALL and time'),
                ('external_force', 'forces (fx,fy,fz) for set ALL and time'),
                ('strain', 'strains (elem, integ.pnt.,exx,eyy,ezz,exy,exz,eyz) for set BODY and time'),
                ('energy', 'internal energy (element, energy) for set BODY and time')])
    lines = [' S T E P       1', ' INCREMENT     1']
    for key, header in headers:
        lines.append(header+' 1.0')
        for n, values in sorted(data[key].items()):
            ids = n if isinstance(n, tuple) else (n,)
            lines.append(' '.join(map(str, ids))+' '+' '.join(format(v, '.17g') for v in values))
    (root/(kind+'.dat')).write_text('\n'.join(lines)+'\n')
    (root/(kind+'.sta')).write_text('1 1 1 1 1.0 1.0 1.0\n')
    if kind == 'thermal':
        cvg, extra = '1 1 1 1 0 0.0 0.0 0.0 0.0\n', ' convergence\n'
    else:
        cvg = ('SUMMARY OF C0NVERGENCE INFORMATION\n'
               'STEP INC ATT ITER CONT. RESID. CORR. RESID. CORR.\n'
               'EL. FORCE DISP FLUX TEMP.\n(#) (%) (%) (%) (%)\n')
        extra = ('STEP 1\nStatic analysis was selected\n'
                 'Factoring the system of equations using the symmetric spooles solver\n')
    (root/(kind+'.cvg')).write_text(cvg)
    (root/'solver.log').write_text('SYNTHETIC FIXTURE: NO SOLVER EXECUTED\n'+HEADER+
                                 '\nUsing 1 cpu for spooles.\n'+extra+'Job finished\n')
    for name in (kind+'.frd', kind+'.12d', 'spooles.out'):
        (root/name).write_text('SYNTHETIC FIXTURE: NO NATIVE EXECUTION\n')


@pytest.fixture(params=['thermal', 'structural'])
def synthetic_pack(tmp_path, cad_pack, request):
    kind = request.param
    module = thermal if kind == 'thermal' else structural
    root = tmp_path/'pack'
    root.mkdir()
    nodes, cells, ends = _synthetic_mesh(root/'mesh', cad_pack)
    data = _synthetic_data(nodes, cells, ends, kind)
    _write_raw(root, kind, data)
    (root/(kind+'.inp')).write_bytes(module.deck(nodes, cells, ends))
    source = {key: 'a'*64 for key in ('adapter_sha256', 'shared_helpers_sha256',
        'mesh_verifier_sha256', 'geometry_helpers_sha256', 'tributary_area_helper_sha256')}
    recipe = {'recipe': module.RECIPE, 'spec': module.SPEC, 'dimensions_m': structural.DIMS,
              'tolerances': module.TOLERANCES, 'source': source}
    receipt = {'schema_version': '1', 'recipe': module.RECIPE,
        'status': kind.upper()+'_BENCHMARK_PASS', 'source': source,
        'solver': {'version': '2.23', 'binary_sha256': '0'*64,
                   'command': ['/synthetic/not-executed', '-i', kind]},
        'timeout_s': 60, 'compute': {'subprocess_wall_time_s': 0., 'configured_threads': 1,
            'cpu_time_s': 'NOT_MEASURED', 'gpu_usage': 'NOT_MEASURED', 'cost': 'NOT_MEASURED'},
        'physical_validation': 'NOT_PERFORMED', 'limitations': module.LIMITATIONS}
    if kind == 'thermal':
        receipt.update(figure_source_sha256=source['adapter_sha256'], mesh_independence='NOT_EVALUATED')
        report, parsed = thermal.oracle(root, nodes, cells, ends, structural.DIMS)
        figures = thermal.figures(nodes, cells, parsed, structural.DIMS)
        verify = thermal.verify_thermal_artifacts
    else:
        recipe.update(actual_element='C3D8I', protocol_freeze_commit='5da9e2e4973ed6a6ef4122c01d879f770b44c22b')
        receipt.update(mesh_independence='NOT_ESTABLISHED', refinement_check='NOT_EVALUATED_SINGLE_PACK',
                       mesh_native_identity='NOT_VERIFIED', mesh_runtime=None)
        report, parsed = structural.oracle(root, nodes, cells, ends)
        figures = structural.figures(nodes, cells, ends, parsed)
        verify = structural.verify_structural_artifacts
    _write(root/'recipe.json', recipe)
    _write(root/'receipt.json', receipt)
    _write(root/'oracle.json', report)
    for name, content in figures.items():
        (root/name).write_bytes(content)
    _reseal(root, module)
    assert verify(root)['status'] == kind.upper()+'_BENCHMARK_PASS'
    return root, module, verify


def test_both_verifiers_accept_synthetic_single_version(synthetic_pack):
    root, _, verify = synthetic_pack
    assert verify(root)['solver']['version'] == '2.23'


@pytest.mark.parametrize('header', INVALID_HEADERS)
def test_both_verifiers_reject_resealed_version_mutations(synthetic_pack, header):
    root, module, verify = synthetic_pack
    path = root/'solver.log'
    path.write_text(path.read_text().replace(HEADER, header))
    _reseal(root, module)
    with pytest.raises(ValueError, match='version'):
        verify(root)


@pytest.mark.parametrize('mutation', ['warning', 'error', 'completion', 'convergence', 'procedure'])
def test_both_verifiers_preserve_execution_gates(synthetic_pack, mutation):
    root, module, verify = synthetic_pack
    path = root/'solver.log'
    text = path.read_text()
    if mutation in ('warning', 'error'):
        text += mutation.upper()+': synthetic diagnostic\n'
    elif mutation == 'completion':
        text = text.replace('Job finished', 'Job unfinished')
    elif mutation == 'procedure' and module is structural:
        text = text.replace('Static analysis was selected', 'Nonlinear analysis was selected')
    elif module is thermal:
        text = text.replace(' convergence\n', ' no convergence\n')
    else:
        (root/'structural.cvg').write_text((root/'structural.cvg').read_text()+'1 1 1 1 0 0 0 0 0\n')
    path.write_text(text)
    _reseal(root, module)
    with pytest.raises(ValueError):
        verify(root)
