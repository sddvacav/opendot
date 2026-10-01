"""Analytic output-only fixtures; no native solver, build, or installation."""
from decimal import Decimal, localcontext
import math

import pytest

from opendot_engineering.executors import structural_beam as s
from test_solver_version_identity import cad_pack, synthetic_pack, _reseal


# Independent decimal material/analytic oracles, fixed before native-pack reads.
D=Decimal
with localcontext() as ctx:
    ctx.prec=60
    E=D('210000000000');NU=D('.3')
    MU=E/(2*(1+NU));LAM=E*NU/((1+NU)*(1-2*NU))
CORNERS=((-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),
         (-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1))


def box():
    nodes={n:tuple((v+1)*length/2 for v,length in zip(p,(.02,.01,.004)))
           for n,p in enumerate(CORNERS,1)}
    return nodes,{1:list(range(1,9))},D('0.0000008')


def fixture_data(strain,energy,elements=(1,)):
    # Print according to the source contract; precision budgets use the API's
    # token extractor, while expected physical energies are independent above.
    strain_tokens=[format(float(v),'.6E') for v in strain]
    energy_token=format(float(energy),'.6E')
    data={'strain':{(e,ip):tuple(map(float,strain_tokens)) for e in elements for ip in range(1,9)},
          'energy':{e:(float(energy_token),) for e in elements}}
    budgets={'strain':{key:tuple(s._elastic_print_quantum(v) for v in strain_tokens) for key in data['strain']},
             'energy':{e:(s._elastic_print_quantum(energy_token),) for e in elements}}
    return data,budgets


@pytest.mark.parametrize('strain,density',[
    ((0,0,0,0,0,0),D(0)),
    ((1e-6,0,0,0,0,0),(LAM/2+MU)*D('1e-12')),
    ((1e-6,-.3e-6,-.3e-6,0,0,0),E/2*D('1e-12')),
    ((1e-6,1e-6,1e-6,0,0,0),(9*LAM/2+3*MU)*D('1e-12')),
    ((0,0,0,1e-6,0,0),2*MU*D('1e-12')),
    ((1e-6,-2e-6,3e-6,4e-6,-5e-6,6e-6),(2*LAM+168*MU)*D('1e-12')),
],ids=['zero','uniaxial-strain','uniaxial-stress','hydrostatic','pure-shear','mixed'])
def test_analytic_fields(strain,density):
    nodes,cells,volume=box();data,budgets=fixture_data(strain,density*volume)
    report=s._elastic_energy_report(nodes,cells,data,budgets)
    row=report['per_element'][0]
    assert row['strain_energy_J']==pytest.approx(float(density*volume),rel=2e-15,abs=0.)
    assert row['absolute_residual_J']<=row['acceptance_bound_J']
    assert row['jacobian_determinants_m3']==pytest.approx([1e-7]*8,rel=2e-15,abs=0.)
    assert report['scientific_accepted'] is False
    assert report['print_profile']['no_subnormal_or_underflow']=='ASSUMED_NOT_VERIFIED'
    assert report['arithmetic_policy']['absolute_floor_J']==0.
    if not density:
        assert row['printed_error_bound_J']==row['arithmetic_allowance_J']==0.


@pytest.mark.parametrize('component',[3,4,5])
@pytest.mark.parametrize('wrong_factor',[.5,1.,4.])
def test_wrong_tensor_shear_factor_refused(component,wrong_factor):
    nodes,cells,volume=box();strain=[0]*6;strain[component]=1e-6
    data,budgets=fixture_data(strain,D(str(wrong_factor))*MU*D('1e-12')*volume)
    with pytest.raises(ValueError,match='mismatch for element 1'):
        s._elastic_energy_report(nodes,cells,data,budgets)


@pytest.mark.parametrize('token,quantum',[
    ('1.234567E-06',1e-12),('-9.123456E+02',1e-4),('+1.000000E-99',1e-105),
    ('9.999999E+99',1e93),('0.000000E+00',0.),('-0.000000E+00',0.),('+0.000000E+00',0.)])
def test_source_precision_quantum(token,quantum):
    assert s._elastic_print_quantum(token)==quantum


@pytest.mark.parametrize('token',['0','0.0','1e-6','1.00000E-06','1.0000000E-06',
    '0.100000E-05','0.000000E-06','1.000000D-06','1.000000e-06','1.000000E-006',
    '1.000000-100','1.000000E-100','1.000000E+100','nan','inf','*************'])
def test_unsupported_print_precision(token):
    with pytest.raises(ValueError,match='precision or exponent'):s._elastic_print_quantum(token)


def test_predeclared_componentwise_error_bound():
    nodes,cells,volume=box()
    strain=(D('1.234567e-6'),D('-2.345678e-6'),D('3.456789e-6'),D('-4.567890e-6'),D('5.678901e-6'),D('-6.789012e-6'))
    def density(e):
        return LAM/2*sum(e[:3])**2+MU*sum(D(c)*v*v for c,v in zip((1,1,1,2,2,2),e))
    data,budgets=fixture_data(strain,density(strain)*volume)
    report=s._elastic_energy_report(nodes,cells,data,budgets);row=report['per_element'][0]
    ds=[D(str(v)) for v in budgets['strain'][1,1]]
    trace=sum(strain[:3]);dt=sum(ds[:3])
    expected=(LAM/2*(2*abs(trace)*dt+dt*dt)+MU*sum(
        D(c)*(2*abs(v)*d+d*d) for c,v,d in zip((1,1,1,2,2,2),strain,ds)))*volume
    expected+=D(str(budgets['energy'][1][0]))
    assert row['printed_error_bound_J']==pytest.approx(float(expected),rel=2e-15,abs=0.)
    assert row['arithmetic_allowance_J']==1e-10*max(row['strain_energy_J'],row['native_ELSE_J'])


def test_signed_element_errors_cannot_cancel():
    nodes,cells,volume=box();cells[2]=cells[1]
    physical=(LAM/2+MU)*D('1e-12')*volume
    data,budgets=fixture_data((1e-6,0,0,0,0,0),physical,(1,2))
    original=data['energy'][1][0]
    data['energy'][1]=(original*.8,);data['energy'][2]=(original*1.2,)
    assert math.fsum(v[0] for v in data['energy'].values())==pytest.approx(2*original,rel=2e-15,abs=0.)
    with pytest.raises(ValueError,match='mismatch for element 1'):
        s._elastic_energy_report(nodes,cells,data,budgets)


def test_zero_strain_positive_else_has_no_absolute_floor():
    nodes,cells,_=box();data,budgets=fixture_data((0,0,0,0,0,0),D('1e-90'))
    with pytest.raises(ValueError,match='mismatch'):s._elastic_energy_report(nodes,cells,data,budgets)


@pytest.mark.parametrize('missing',['strain','energy','precision-strain','precision-energy'])
def test_incomplete_identity_refused(missing):
    nodes,cells,_=box();data,budgets=fixture_data((0,0,0,0,0,0),0)
    owner=budgets if missing.startswith('precision') else data
    kind=missing.split('-')[-1];del owner[kind][next(iter(owner[kind]))]
    with pytest.raises(ValueError,match='identity'):s._elastic_energy_report(nodes,cells,data,budgets)


def test_inverted_geometry_refused():
    nodes,cells,_=box();nodes={n:(-p[0],p[1],p[2]) for n,p in nodes.items()}
    with pytest.raises(ValueError,match='Jacobian'):s._elastic_jacobians(nodes,cells[1])


def test_nonaffine_actual_jacobians_and_distinct_ip_order():
    # Mapping X=xi, Y=(1+xi/4)*eta, Z=zeta gives detJ=1+xi/4.
    # This distinguishes x-fast IP order from the corner-node order at 3/4.
    nodes={n:(x,y*(1+x/4),z) for n,(x,y,z) in enumerate(CORNERS,1)}
    a=.577350269189626;expected=[1-a/4,1+a/4]*4
    weights=s._elastic_jacobians(nodes,list(range(1,9)))
    assert weights==pytest.approx(expected,rel=2e-15,abs=0.)
    assert len(set(round(x,12) for x in weights))==2
    data,budgets=fixture_data((1e-6,0,0,0,0,0),0)
    for ip in range(1,9):
        data['strain'][1,ip]=(ip*1e-6,0,0,0,0,0)
        budgets['strain'][1,ip]=(1e-12,0,0,0,0,0)
    energy=float((LAM/2+MU)*D('1e-12'))*sum(w*ip*ip for ip,w in enumerate(expected,1))
    token=format(energy,'.6E');data['energy'][1]=(float(token),);budgets['energy'][1]=(s._elastic_print_quantum(token),)
    report=s._elastic_energy_report(nodes,{1:list(range(1,9))},data,budgets)
    assert report['strain_energy_sum_J']==pytest.approx(energy,rel=2e-15,abs=0.)
    data['strain'][1,3],data['strain'][1,4]=data['strain'][1,4],data['strain'][1,3]
    with pytest.raises(ValueError,match='mismatch'):s._elastic_energy_report(nodes,{1:list(range(1,9))},data,budgets)


def test_existing_strict_verifier_runs_first(tmp_path,monkeypatch):
    def reject(directory):raise ValueError('baseline gate reached')
    monkeypatch.setattr(s,'verify_structural_artifacts',reject)
    monkeypatch.setattr(s,'_mesh',lambda *a:pytest.fail('must not inspect mesh after failed admission'))
    with pytest.raises(ValueError,match='baseline gate reached'):s.verify_elastic_energy(tmp_path)


@pytest.fixture
def optional_pack(synthetic_pack):
    root,module,_=synthetic_pack
    if module is not s:pytest.skip('Structural-only API fixture')
    # Existing shared analytic beam fixture supplies all strict admission fields.
    # Only raw E/ELSE lexical precision changes; rebuild its existing derivations.
    p=root/'structural.dat';lines=[];target=False
    for line in p.read_text().splitlines():
        if line.startswith(('strains (','internal energy (')):target=True
        if target and line and line[0].isdigit():
            fields=line.split();offset=2 if len(fields)==8 else 1
            line=' '.join(fields[:offset]+[format(float(v),'.6E') for v in fields[offset:]])
        lines.append(line)
    p.write_text('\n'.join(lines)+'\n');refresh(root)
    return root


def refresh(root):
    nodes,cells,ends=s._mesh(root/'mesh');report,data=s.oracle(root,nodes,cells,ends)
    (root/'oracle.json').write_bytes(s.geometry.canonical_bytes(report))
    for name,content in s.figures(nodes,cells,ends,data).items():(root/name).write_bytes(content)
    _reseal(root,s)


@pytest.mark.parametrize('synthetic_pack',['structural'],indirect=True)
def test_optin_api_and_unchanged_default_receipt(optional_pack):
    root=optional_pack;before={p.relative_to(root):p.read_bytes() for p in root.rglob('*') if p.is_file()}
    receipt=s.verify_structural_artifacts(root);report=s.verify_elastic_energy(root)
    assert report['status']=='CONDITIONAL_ELASTIC_ENERGY_CONSISTENCY_PASS' and report['elements']==160
    assert receipt==s.verify_structural_artifacts(root)
    assert before=={p.relative_to(root):p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.mark.parametrize('synthetic_pack',['structural'],indirect=True)
@pytest.mark.parametrize('change',['zero-strain','strain-scale','signed-energy-cancellation','precision','missing-ip'])
def test_resealed_synthetic_pack_counterexamples(optional_pack,change):
    root=optional_pack;p=root/'structural.dat';lines=p.read_text().splitlines();out=[];target=None
    for line in lines:
        if line.startswith('strains ('):target='strain'
        elif line.startswith('internal energy ('):target='energy'
        if line and line[0].isdigit() and target:
            fields=line.split()
            if target=='strain':
                if change=='missing-ip' and fields[:2]==['1','1']:continue
                if change=='zero-strain':fields[2:]=['0.000000E+00']*6
                if change=='strain-scale':fields[2:]=[format(float(x)*.5,'.6E') for x in fields[2:]]
                if change=='precision':fields[2:]=[format(float(x),'.5E') for x in fields[2:]]
            elif change=='signed-energy-cancellation' and fields[0] in ('1','2'):
                fields[1]=format(float(fields[1])+(1e-9 if fields[0]=='1' else -1e-9),'.6E')
            line=' '.join(fields)
        out.append(line)
    p.write_text('\n'.join(out)+'\n')
    if change=='missing-ip':
        _reseal(root,s)
        with pytest.raises(ValueError,match='identity'):s.verify_elastic_energy(root)
    else:
        refresh(root)
        assert s.verify_structural_artifacts(root)['status']=='STRUCTURAL_BENCHMARK_PASS'
        with pytest.raises(ValueError,match='mismatch|precision'):s.verify_elastic_energy(root)
