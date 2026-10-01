"""Analytical fixtures are not solver evidence; archived integration packs are opt-in."""
import copy
import itertools
import json
import math
import os
from pathlib import Path
import shutil

import pytest

from opendot_engineering.executors import thermal_conduction as t
from opendot_engineering.executors import thermal_source as s
from opendot_engineering.executors import geometry


def fixture(nx=4):
    nodes={}; index={}; cells={}; n=0
    for k,j,i in itertools.product(range(2),range(2),range(nx+1)):
        n+=1; index[i,j,k]=n;nodes[n]=(.2*i/nx,.02*j,.003*k)
    for i in range(nx):
        cells[i+1]=[index[a,b,c] for a,b,c in ((i,0,0),(i+1,0,0),(i+1,1,0),(i,1,0),(i,0,1),(i+1,0,1),(i+1,1,1),(i,1,1))]
    ends={name:{n for n,p in nodes.items() if p[0]==x} for name,x in [('X_MIN',0),('X_MAX',.2)]}
    # Independent one-dimensional load/reaction and exact quadratic solution.
    h=.2/nx; q=50000.; k=10.; area=.02*.003
    data={'temperature':{},'reaction':{},'flux':{},'coordinates':{}}
    for n,(x,y,z) in nodes.items():
        data['temperature'][n]=(300+q*x*(.2-x)/(2*k),)
        source=q*area*h/(8 if x in (0,.2) else 4)
        reaction=-q*area*.2/8 if x in (0,.2) else 0
        data['reaction'][n]=(source+reaction,)
    for e in cells:
        xc=(e-.5)*h
        for p,(z,y,x) in enumerate(itertools.product((-1,1),repeat=3),1):
            data['coordinates'][e,p]=(xc+x*h/(2*math.sqrt(3)),.01+y*.02/(2*math.sqrt(3)),.0015+z*.003/(2*math.sqrt(3)))
            data['flux'][e,p]=(q*(xc-.1),0.,0.)
    return nodes,cells,ends,[.2,.02,.003],data


def report(f):return s.analytical_report(*f)


def test_exact_nodes_still_have_nonzero_field_error_and_rates():
    a=report(fixture(20));b=report(fixture(40))
    assert a['max_temperature_error_K']<1e-12
    assert a['temperature_volume_rms_error_K']==pytest.approx(.04564354645876384,abs=1e-12)
    assert a['flux_volume_rms_error_W_m2']==pytest.approx(144.337567297406,abs=1e-9)
    assert a['raw_end_RFL_W']['X_MIN']==pytest.approx(-.285)
    assert b['raw_end_RFL_W']['X_MIN']==pytest.approx(-.2925)
    assert a['end_reactions_W']==pytest.approx({'X_MIN':-.3,'X_MAX':-.3})
    assert s.refinement_report(a,b)['observed_orders']==pytest.approx({'temperature':2,'flux':1})


@pytest.mark.parametrize('mode',['missing_source','negative_source','wrong_units','wrong_distribution','wrong_bc','wrong_flux_sign','raw_as_reaction','centroid_ips','shuffled_ips'])
def test_physics_mutations_rejected(mode):
    f=fixture();nodes,cells,ends,dims,d=f
    if mode in ('missing_source','negative_source','wrong_units'):
        scale={'missing_source':0,'negative_source':-1,'wrong_units':1e-9}[mode]
        d['temperature']={n:(300+(v[0]-300)*scale,) for n,v in d['temperature'].items()}
        d['flux']={p:tuple(a*scale for a in v) for p,v in d['flux'].items()}
    elif mode=='wrong_distribution':
        free=[n for n in nodes if n not in ends['X_MIN']|ends['X_MAX']]
        for n,delta in zip(free,(.001,-.001)):
            d['reaction'][n]=(d['reaction'][n][0]+delta,)
    elif mode=='wrong_bc':
        n=next(iter(ends['X_MAX']));d['temperature'][n]=(301.,)
    elif mode=='wrong_flux_sign':d['flux']={p:tuple(-a for a in v) for p,v in d['flux'].items()}
    elif mode=='raw_as_reaction':
        b=s.source_vector(nodes,cells);d['reaction']={n:(v[0]-b[n],) for n,v in d['reaction'].items()}
    elif mode=='centroid_ips':
        d['coordinates']={p:((p[0]-.5)*.05,.01,.0015) for p in d['coordinates']}
    else:d['coordinates'][1,1],d['coordinates'][1,2]=d['coordinates'][1,2],d['coordinates'][1,1]
    with pytest.raises(ValueError):report(f)


def test_zero_error_from_exact_nodes_cannot_certify_field(monkeypatch):
    original=s.field_samples
    def fake(*args):
        for e,j,p,value,ref,w in original(*args):yield e,j,p,ref,ref,w
    monkeypatch.setattr(s,'field_samples',fake)
    with pytest.raises(ValueError,match='off_node_temperature_error'):report(fixture())


def test_two_point_temperature_quadrature_is_not_continuous_rms():
    a=report(fixture(20));underintegrated=50000*(.2/20)**2/(12*10)
    assert abs(a['temperature_volume_rms_error_K']-underintegrated)>.003


@pytest.mark.parametrize('mode',['same','reversed','false_exact'])
def test_false_refinement_rejected(mode):
    a=report(fixture(20));b=report(fixture(40))
    if mode=='same':b=a
    elif mode=='reversed':a,b=b,a
    else:b['temperature_volume_rms_error_K']=a['temperature_volume_rms_error_K']
    with pytest.raises(ValueError):s.refinement_report(a,b)


def test_source_deck_leaves_linear_default_unchanged():
    n,c,e,_,_=fixture()
    linear=t.deck(n,c,e);source=t.deck(n,c,e,benchmark='uniform_source')
    assert b'*DFLUX' not in linear and b'X_MAX,11,11,400.' in linear
    assert b'*DFLUX\nBODY,BF,50000.\n' in source
    assert b'HFL,COORD\n' in source and b'X_MAX,11,11,300.' in source
    with pytest.raises(ValueError):t.deck(n,c,e,benchmark='unknown')


def test_same_end_reaction_cancellation_is_rejected():
    f=fixture();nodes,cells,ends,dims,data=f
    a,b=sorted(ends['X_MIN'])[:2]
    data['reaction'][a]=(data['reaction'][a][0]+.001,)
    data['reaction'][b]=(data['reaction'][b][0]-.001,)
    # The preserved v1 scope accepts end sums; the explicitly stronger v2 must not.
    old=s.analytical_report(*f,check_nodal=False)
    assert old['checks']['corrected_reactions_and_free_nodes']
    assert 'constrained_nodal_reactions' not in old['checks']
    with pytest.raises(ValueError,match="'constrained_nodal_reactions': False"):
        report(f)


def positive_permutations():
    corners=[(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]
    for axes in itertools.permutations(range(3)):
        parity=(-1)**sum(axes[i]>axes[j] for i in range(3) for j in range(i+1,3))
        for signs in itertools.product((-1,1),repeat=3):
            if parity*math.prod(signs)!=1:continue
            yield tuple(corners.index(tuple(signs[a]*p[axes[a]] for a in range(3))) for p in corners)


@pytest.mark.parametrize('permutation',list(positive_permutations()))
def test_nodal_areas_accept_all_positive_axis_permutations(permutation):
    f=fixture();nodes,cells,ends,dims,data=f
    expected=s.end_node_tributary_areas(nodes,cells,ends,dims)
    for e,cell in list(cells.items()):
        cells[e]=[cell[i] for i in permutation]
        points=[nodes[n] for n in cells[e]]
        for ip,(z,y,x) in enumerate(itertools.product((-1,1),repeat=3),1):
            local=[x/math.sqrt(3),y/math.sqrt(3),z/math.sqrt(3)]
            data['coordinates'][e,ip]=tuple(points[0][a]+sum((local[j]+1)/2*(points[v][a]-points[0][a]) for j,v in enumerate((1,3,4))) for a in range(3))
    assert s.end_node_tributary_areas(nodes,cells,ends,dims)==expected
    result=report(f)
    assert result['checks']['constrained_nodal_reactions']
    assert result['max_constrained_nodal_reaction_error_W']<1e-12


@pytest.mark.parametrize('mode',['missing_node','wrong_plane','duplicate_face','nonrectangular'])
def test_ambiguous_boundary_area_fails_closed(mode):
    nodes,cells,ends,dims,data=fixture()
    if mode=='missing_node':ends['X_MIN'].remove(min(ends['X_MIN']))
    elif mode=='wrong_plane':ends['X_MIN'].add(next(n for n,p in nodes.items() if p[0]==.05))
    elif mode=='duplicate_face':cells[999]=cells[1]
    else:
        n=max(ends['X_MIN']);x,y,z=nodes[n];nodes[n]=(x,y/2,z)
    with pytest.raises(ValueError):s.end_node_tributary_areas(nodes,cells,ends,dims)


def test_legacy_source_creation_is_refused(tmp_path):
    with pytest.raises(ValueError,match='verification-only'):
        t.run_thermal('missing',tmp_path/'out',solver_executable='missing',benchmark='uniform_source_v1')


@pytest.fixture(scope='module')
def preserved_source_pack():
    path=os.environ.get('OPENDOT_TEST_SOURCE_PACK')
    if not path:pytest.skip('Opt-in preserved real source solver pack required; no solve performed')
    return Path(path)


def reseal(root):
    r=json.loads((root/'receipt.json').read_text())
    r['hashes']={n:geometry.sha256((root/n).read_bytes()) for n in t.FILES-{'receipt.json'}}
    (root/'receipt.json').write_bytes(geometry.canonical_bytes(r))
    manifest={'schema_version':'1','hash_algorithm':'sha256','artifacts':{n:{'sha256':geometry.sha256((root/n).read_bytes()),'bytes':(root/n).stat().st_size} for n in t.FILES}}
    (root/'manifest.json').write_bytes(geometry.canonical_bytes(manifest))


def test_preserved_real_pack(preserved_source_pack):
    r=t.verify_thermal_artifacts(preserved_source_pack)
    assert r['recipe']==s.RECIPE


@pytest.mark.parametrize('old,new',[
    ('BODY,BF,50000.','BODY,BF,-50000.'),
    ('BODY,BF,50000.','BODY,BF,0.00005'),
    ('BODY,BF,50000.','BODY,S1,50000.'),
    ('BODY,BF,50000.','BODY,BF,0.'),
    ('BODY,BF,50000.','BODY,BF,50000.\nBODY,BF,50000.'),
    ('X_MAX,11,11,300.','X_MAX,11,11,301.'),
])
def test_resealed_source_deck_mutation(tmp_path,preserved_source_pack,old,new):
    out=tmp_path/'bad';shutil.copytree(preserved_source_pack,out)
    p=out/'thermal.inp';text=p.read_text();assert old in text;p.write_text(text.replace(old,new))
    reseal(out)
    with pytest.raises(ValueError,match='identity mismatch'):t.verify_thermal_artifacts(out)


def test_resealed_misleading_nodal_only_oracle(tmp_path,preserved_source_pack):
    out=tmp_path/'bad';shutil.copytree(preserved_source_pack,out)
    p=out/'oracle.json';r=json.loads(p.read_text());r['temperature_volume_rms_error_K']=0
    p.write_bytes(geometry.canonical_bytes(r));reseal(out)
    with pytest.raises(ValueError,match='False analytical'):t.verify_thermal_artifacts(out)


def test_resealed_same_end_reaction_pair(tmp_path,preserved_source_pack):
    out=tmp_path/'bad';shutil.copytree(preserved_source_pack,out)
    assert json.loads((out/'recipe.json').read_text())['recipe']==s.RECIPE
    _,_,ends=t.mesh_data(out/'mesh/beam.msh')
    a,b=sorted(ends['X_MIN'])[:2]
    changes={a:.001,b:-.001};changed=set();active=False
    p=out/'thermal.dat';lines=p.read_text().splitlines()
    for i,line in enumerate(lines):
        if line.strip().startswith('heat generation for set ALL'):active=True;continue
        if active and line.strip().startswith(('heat flux','global coordinates')):break
        if active and line.strip():
            fields=line.split();n=int(fields[0])
            if n in changes:
                lines[i]=f'{n} {float(fields[1])+changes[n]:.9E}';changed.add(n)
    assert changed==set(changes)
    p.write_text('\n'.join(lines)+'\n');reseal(out)
    with pytest.raises(ValueError,match="'constrained_nodal_reactions': False"):
        t.verify_thermal_artifacts(out)
