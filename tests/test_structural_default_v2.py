"""Default v2 composition and explicit historical compatibility; no native runs."""
import json
import math
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

from opendot_engineering.executors import structural_beam as s
import test_solver_version_identity as fixtures
from test_structural_elastic_energy import optional_pack, synthetic_pack, cad_pack, refresh

structural_only=pytest.mark.parametrize('synthetic_pack',['structural'],indirect=True)


def snapshot(root):
    return {str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}


def rewrite(root,mutation):
    """Deliberately false/unsupported copies of public analytic fixture bytes."""
    path=root/'structural.dat';data=s.parse_dat(path);ids=sorted(data['energy'])[:2]
    shift=min(data['energy'][e][0] for e in ids)/4
    nodes,cells,_=s._mesh(root/'mesh');shear={}
    if mutation=='wrong-shear-factor':
        # This deliberately uses coefficient mu instead of tensor-shear 2*mu.
        mu=210000000000/(2*1.3)
        for e,cell in cells.items():
            volume=math.prod(max(nodes[n][k] for n in cell)-min(nodes[n][k] for n in cell) for k in range(3))
            shear[e]=math.sqrt(data['energy'][e][0]/(mu*volume))
    out=[];section=None
    for line in path.read_text().splitlines():
        if line.startswith('strains ('):section='strain'
        elif line.startswith('internal energy ('):section='energy'
        if line and line[0].isdigit() and section:
            fields=line.split()
            if section=='strain':
                if mutation=='missing-ip' and fields[:2]==[str(ids[0]),'1']:continue
                if mutation=='zero-strain':fields[2:]=['0.000000E+00']*6
                if mutation=='half-strain':fields[2:]=[format(float(v)*.5,'.6E') for v in fields[2:]]
                if mutation=='wrong-shear-factor':fields[2:]=['0.000000E+00']*3+[format(shear[int(fields[0])],'.6E')]+['0.000000E+00']*2
                if mutation=='precision':fields[2:]=[format(float(v),'.5E') for v in fields[2:]]
                if mutation=='D-notation':fields[2:]=[v.replace('E','D') for v in fields[2:]]
                if mutation=='zero-exponent':fields[2:]=[v.replace('0.000000E+00','0.000000E-06') for v in fields[2:]]
            elif mutation=='cancel-elements' and int(fields[0]) in ids:
                fields[1]=format(float(fields[1])+(shift if int(fields[0])==ids[0] else -shift),'.6E')
            line=' '.join(fields)
        out.append(line)
    path.write_text('\n'.join(out)+'\n')
    if mutation=='missing-ip':fixtures._reseal(root,s)
    else:refresh(root)


@pytest.mark.parametrize('profile',[None,True,False,0,1,[],{},('artifact_v1',),b'artifact_v1','',
                                      'legacy','conditional_elastic_v1','artifact_v2'])
@pytest.mark.parametrize('api',['verify','compare'])
def test_invalid_profile_refuses_before_path_or_read(monkeypatch,profile,api):
    class Unreadable:
        def __fspath__(self):pytest.fail('Profile must fail before path conversion')
    monkeypatch.setattr(s.shared,'_read',lambda *a:pytest.fail('Profile must fail before read'))
    with pytest.raises(ValueError,match='profile'):
        if api=='verify':s.verify_structural_artifacts(Unreadable(),profile=profile)
        else:s.compare_refinement(Unreadable(),Unreadable(),profile=profile)


def test_default_requires_admission_before_energy(monkeypatch):
    def reject(directory):raise ValueError('strict admission first')
    monkeypatch.setattr(s,'_verify_structural_artifacts_v1',reject)
    monkeypatch.setattr(s,'_checked_elastic_energy',lambda *a:pytest.fail('Must not reach energy'))
    with pytest.raises(ValueError,match='strict admission first'):s.verify_structural_artifacts('unused')


@structural_only
def test_default_envelope_and_historical_receipt_are_distinct(optional_pack):
    root=optional_pack;before=snapshot(root)
    legacy=s.verify_structural_artifacts(root,profile='artifact_v1')
    energy=s.verify_elastic_energy(root)
    result=s.verify_structural_artifacts(root)
    assert legacy==json.loads((root/'receipt.json').read_text())
    assert result['schema_version']=='2' and result['artifact_schema_version']=='1'
    assert result['verification_profile']=='conditional_elastic_v2'
    assert result['status']=='CONDITIONAL_STRUCTURAL_CONSISTENCY_PASS'
    assert result['artifact_receipt']==legacy and result['elastic_energy']==energy
    assert result['scientific_accepted'] is False
    assert result['physical_validation']=='NOT_PERFORMED'
    assert result['independent_review']=='NOT_EVALUATED'
    assert result['mesh_independence']=='NOT_ESTABLISHED'
    assert result['conditional_assumptions']['no_subnormal_or_underflow']=='ASSUMED_NOT_VERIFIED'
    assert result['conditional_assumptions']['formal_arithmetic_error_bound']=='NOT_PROVED'
    assert snapshot(root)==before


@structural_only
def test_default_and_optional_each_use_one_shared_admission_and_kernel(optional_pack,monkeypatch):
    events=[];admit=s._verify_structural_artifacts_v1;kernel=s._elastic_energy_report
    def admission(directory):events.append('admission');return admit(directory)
    def energy(*args):events.append('energy');return kernel(*args)
    monkeypatch.setattr(s,'_verify_structural_artifacts_v1',admission)
    monkeypatch.setattr(s,'_elastic_energy_report',energy)
    result=s.verify_structural_artifacts(optional_pack)
    assert events==['admission','energy'];events.clear()
    # Calling the public v2 verifier from the optional API would recurse or
    # perform the energy calculation twice; explicitly forbid that route.
    monkeypatch.setattr(s,'verify_structural_artifacts',lambda *a,**k:pytest.fail('Public verifier recursion'))
    assert s.verify_elastic_energy(optional_pack)==result['elastic_energy']
    assert events==['admission','energy']


@structural_only
def test_untrusted_archived_authority_cannot_override_v2(optional_pack):
    path=optional_pack/'receipt.json';receipt=json.loads(path.read_text())
    receipt.update(scientific_accepted=True,independent_review='PASS',verification_profile='forged')
    fixtures._write(path,receipt);fixtures._reseal(optional_pack,s)
    result=s.verify_structural_artifacts(optional_pack)
    assert result['artifact_receipt']['scientific_accepted'] is True  # Archived declaration only.
    assert result['scientific_accepted'] is False
    assert result['independent_review']=='NOT_EVALUATED'
    assert result['verification_profile']=='conditional_elastic_v2'


@structural_only
@pytest.mark.parametrize('mutation',['zero-strain','half-strain','wrong-shear-factor','cancel-elements',
                                      'precision','D-notation','zero-exponent'])
def test_new_default_refuses_preserved_legacy_false_accepts(optional_pack,mutation):
    rewrite(optional_pack,mutation);before=snapshot(optional_pack)
    assert s.verify_structural_artifacts(optional_pack,profile='artifact_v1')['status']=='STRUCTURAL_BENCHMARK_PASS'
    with pytest.raises(ValueError,match='mismatch|precision'):s.verify_structural_artifacts(optional_pack)
    with pytest.raises(ValueError,match='mismatch|precision'):s.verify_elastic_energy(optional_pack)
    assert snapshot(optional_pack)==before


@structural_only
def test_missing_ip_never_reaches_current_acceptance(optional_pack):
    rewrite(optional_pack,'missing-ip')
    for profile in ('artifact_v1','conditional_elastic_v2'):
        with pytest.raises(ValueError,match='identity'):s.verify_structural_artifacts(optional_pack,profile=profile)


@structural_only
@pytest.mark.parametrize('keyword',['*INITIAL CONDITIONS,TYPE=STRESS','*TEMPERATURE','*PLASTIC',
                                   '*STEP,NLGEOM','*ORIENTATION,NAME=OTHER'])
def test_unsupported_physics_profile_is_refused_by_exact_deck(optional_pack,keyword):
    path=optional_pack/'structural.inp';path.write_bytes(path.read_bytes()+('\n'+keyword+'\n').encode())
    fixtures._reseal(optional_pack,s)
    with pytest.raises(ValueError,match='identity mismatch'):s.verify_structural_artifacts(optional_pack)


@structural_only
def test_cli_verify_exposes_v2_without_a_legacy_switch(optional_pack,capsys):
    s.main(['verify',str(optional_pack)])
    result=json.loads(capsys.readouterr().out)
    assert result['status']=='CONDITIONAL_STRUCTURAL_CONSISTENCY_PASS'
    assert result['scientific_accepted'] is False
    with pytest.raises(SystemExit) as error:s.main(['verify',str(optional_pack),'--profile','artifact_v1'])
    assert error.value.code==2


@structural_only
def test_cli_verify_rejects_zero_strain_instead_of_printing_pass(optional_pack,capsys):
    rewrite(optional_pack,'zero-strain')
    with pytest.raises(ValueError,match='mismatch'):s.main(['verify',str(optional_pack)])
    assert capsys.readouterr().out==''


def normal_precision(root):
    path=root/'structural.dat';out=[];target=False
    for line in path.read_text().splitlines():
        if line.startswith(('strains (','internal energy (')):target=True
        if target and line and line[0].isdigit():
            fields=line.split();offset=2 if len(fields)==8 else 1
            line=' '.join(fields[:offset]+[format(float(v),'.6E') for v in fields[offset:]])
        out.append(line)
    path.write_text('\n'.join(out)+'\n');refresh(root)


@pytest.fixture
def two_grid_packs(tmp_path,cad_pack,monkeypatch):
    packs=[];mesh=fixtures._synthetic_mesh
    for name,divisions in [('coarse',(20,4,2)),('refined',(40,8,4))]:
        parent=tmp_path/name;parent.mkdir()
        with monkeypatch.context() as patch:
            patch.setattr(fixtures,'_synthetic_mesh',lambda root,cad:mesh(root,cad,divisions=divisions))
            root,_,_=fixtures.synthetic_pack.__wrapped__(parent,cad_pack,SimpleNamespace(param='structural'))
        normal_precision(root);packs.append(root)
    return packs


def test_comparison_default_gates_both_and_explicit_legacy_preserves_numbers(two_grid_packs):
    coarse,refined=two_grid_packs;before=[snapshot(root) for root in two_grid_packs]
    historical=s.compare_refinement(coarse,refined,profile='artifact_v1')
    current=s.compare_refinement(coarse,refined)
    assert historical['status']=='STRUCTURAL_REFINEMENT_PASS'
    assert current['status']=='CONDITIONAL_STRUCTURAL_REFINEMENT_PASS'
    assert current['schema_version']=='2' and current['verification_profile']=='conditional_elastic_v2'
    assert current['scientific_accepted'] is False
    assert current['conditional_assumptions']['no_subnormal_or_underflow']=='ASSUMED_NOT_VERIFIED'
    assert current['conditional_assumptions']['formal_arithmetic_error_bound']=='NOT_PROVED'
    assert current['input_verification_status']=={'coarse':'CONDITIONAL_STRUCTURAL_CONSISTENCY_PASS','refined':'CONDITIONAL_STRUCTURAL_CONSISTENCY_PASS'}
    assert {k:current[k] for k in historical if k!='status'}=={k:v for k,v in historical.items() if k!='status'}
    assert before==[snapshot(root) for root in two_grid_packs]


@pytest.mark.parametrize('which',[0,1])
@pytest.mark.parametrize('mutation',['zero-strain','half-strain','cancel-elements'])
def test_comparison_default_refuses_each_false_accepting_grid(two_grid_packs,which,mutation):
    rewrite(two_grid_packs[which],mutation)
    assert s.compare_refinement(*two_grid_packs,profile='artifact_v1')['status']=='STRUCTURAL_REFINEMENT_PASS'
    with pytest.raises(ValueError,match='mismatch'):s.compare_refinement(*two_grid_packs)


def test_cli_compare_reports_conditional_profile(two_grid_packs,capsys):
    s.main(['compare',*map(str,two_grid_packs)])
    assert json.loads(capsys.readouterr().out)['status']=='CONDITIONAL_STRUCTURAL_REFINEMENT_PASS'


@structural_only
@pytest.mark.parametrize('failure',[False,True],ids=['supported-return','required-energy-refusal'])
@pytest.mark.parametrize('route',['api','cli'])
def test_native_run_return_and_existing_failure_cleanup_without_native_execution(optional_pack,tmp_path,monkeypatch,capsys,failure,route):
    source=optional_pack
    if failure:rewrite(source,'zero-strain')
    executable=tmp_path/'not-executed-synthetic-solver';executable.write_text('Synthetic bytes. No execution.\n');executable.chmod(0o700)
    # Only copy synthetic raw fields. No subprocess, native backend or installed
    # solver is run; the production preparation/publication path is exercised.
    def fake_execute(exe,out,timeout,job_name):
        assert job_name=='structural'
        for name in s.RAW-{'structural.inp'}:shutil.copyfile(source/name,out/name)
    monkeypatch.setattr(s.shared,'_execute',fake_execute)
    out=tmp_path/'run-result'
    def invoke():
        if route=='api':return s.run_structural(source/'mesh',out,solver_executable=str(executable))
        s.main(['run',str(source/'mesh'),str(out),'--solver',str(executable)])
        return json.loads(capsys.readouterr().out)
    if failure:
        with pytest.raises(ValueError,match='mismatch'):invoke()
        assert capsys.readouterr().out==''
        assert (out/'failure.json').is_file()
        assert not (out/'receipt.json').exists() and not (out/'manifest.json').exists()
        assert json.loads((out/'failure.json').read_text())['error_type']=='ValueError'
    else:
        result=invoke()
        assert result['status']=='CONDITIONAL_STRUCTURAL_CONSISTENCY_PASS'
        assert result['artifact_receipt']==json.loads((out/'receipt.json').read_text())
        assert result['artifact_receipt']['schema_version']=='1'
        assert result['scientific_accepted'] is False


def test_native_run_has_no_historical_profile_bypass():
    with pytest.raises(TypeError,match='profile'):
        s.run_structural('unused','unused',solver_executable='unused',profile='artifact_v1')


def test_cli_compare_cannot_report_current_pass_for_bad_second_pack(two_grid_packs,capsys):
    rewrite(two_grid_packs[1],'zero-strain')
    with pytest.raises(ValueError,match='mismatch'):s.main(['compare',*map(str,two_grid_packs)])
    assert capsys.readouterr().out==''
