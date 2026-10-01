"""Fixed synthetic uniform-source oracle; not a solver or material validation.

See docs/thermal-source.md for the independently derived continuum and discrete
references. All numerical field checks use preserved mesh/output values.
"""
import csv
import io
import itertools
import math

LEGACY_RECIPE = 'thermal.synthetic_uniform_source.dc3d8.v1'
RECIPE = 'thermal.synthetic_uniform_source.dc3d8.v2'
SPEC = {'conductivity_W_mK': 10.0, 'temperature_x_min_K': 300.0,
        'temperature_x_max_K': 300.0, 'length_unit': 'm', 'temperature_unit': 'K',
        'flux_unit': 'W/m2', 'reaction_unit': 'W', 'other_faces': 'adiabatic',
        'volumetric_heat_source_W_m3': 50000.0, 'element': 'DC3D8',
        'procedure': 'STEADY STATE', 'configured_threads': 1}
TOLERANCES = {'temperature_absolute_K': 0.0001, 'flux_absolute_W_m2': 0.001,
              'reaction_absolute_W': 1e-7, 'energy_balance_absolute_W': 1e-7,
              'coordinate_absolute_m': 1e-7, 'temperature_rms_absolute_K': 0.0001,
              'flux_rms_absolute_W_m2': 0.002,
              'final_cvg_flux_and_temperature_percent': 1e-5}
LIMITATIONS = [
    'Synthetic numerical verification only; no physical experiment or material-performance claim',
    'Uniform-source quadratic field on affine structured HEX8 only; no general mesh-independence claim',
    'Nodal temperatures can be exact; off-node and true integration-point errors are required',
    'One prescribed SI case; no transient, nonlinear-material, contact or radiation validation',
    'Local integrity hashes are not authentication against a party rewriting all evidence',
    'Configured thread count is not measured CPU use; CPU/GPU cost not measured',
    'Unix process limits are not a hostile-code security sandbox; no native SBOM or licensing clearance']
K, Q, T0, L = 10.0, 50000.0, 300.0, 0.2
SIGNS = ((-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),
         (-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1))
# Official CalculiX 2.23 gauss.f: x changes fastest, then y, then z.
G2 = tuple((x/math.sqrt(3),y/math.sqrt(3),z/math.sqrt(3))
           for z in (-1,1) for y in (-1,1) for x in (-1,1))
G3 = ((-math.sqrt(3/5),5/9),(0.,8/9),(math.sqrt(3/5),5/9))


def exact_temperature(x):
    return T0 + Q*x*(L-x)/(2*K)


def exact_flux(x):
    return Q*(x-L/2)


def shape(local):
    return [math.prod(1+s*x for s,x in zip(sign,local))/8 for sign in SIGNS]


def interpolate(values, local):
    return math.fsum(w*v for w,v in zip(shape(local),values))


def geometry(points):
    bounds=[(min(p[a] for p in points),max(p[a] for p in points)) for a in range(3)]
    lengths=[hi-lo for lo,hi in bounds]
    return math.prod(lengths), lengths[0], math.fsum(p[0] for p in points)/8


def source_vector(nodes, cells):
    """Consistent BF load: integral N_i Q dV = Q V_e/8 on affine HEX8."""
    contributions={n:[] for n in nodes}
    for cell in cells.values():
        volume,_,_=geometry([nodes[n] for n in cell])
        for n in cell:
            contributions[n].append(Q*volume/8)
    return {n:math.fsum(values) for n,values in contributions.items()}


def end_node_tributary_areas(nodes,cells,ends,dims):
    """Geometric end-face area/4; never assume a local HEX8 face number.

    The caller has verified affine, axis-aligned cuboids. Check the boundary
    mapping again here and fail closed if the purported face is not its four
    geometric corners. Positive local-axis permutations do not change areas.
    """
    if set(ends)!={'X_MIN','X_MAX'} or ends['X_MIN'] & ends['X_MAX']:
        raise ValueError('Invalid end-region identities for tributary areas')
    result={}
    for side,x in (('X_MIN',0.),('X_MAX',dims[0])):
        contributions={n:[] for n in ends[side]}; seen=set()
        if not contributions or not set(contributions)<=set(nodes):
            raise ValueError('Missing end nodes for tributary areas')
        for cell in cells.values():
            geometric={n for n in cell if abs(nodes[n][0]-x)<=1e-10}
            selected=set(cell)&ends[side]
            if selected!=geometric:
                raise ValueError('End-region and geometric face disagree')
            if not selected:continue
            if len(selected)!=4 or tuple(sorted(selected)) in seen:
                raise ValueError('Invalid or duplicated four-node end face')
            seen.add(tuple(sorted(selected)))
            yz=[nodes[n][1:] for n in selected]
            y0,y1=min(p[0] for p in yz),max(p[0] for p in yz)
            z0,z1=min(p[1] for p in yz),max(p[1] for p in yz)
            if y1<=y0 or z1<=z0:
                raise ValueError('Degenerate end-face area')
            corners={(round((y-y0)/(y1-y0)),round((z-z0)/(z1-z0))) for y,z in yz}
            if corners!={(0,0),(1,0),(1,1),(0,1)} or any(
                    min(abs(y-y0),abs(y-y1))>1e-12 or min(abs(z-z0),abs(z-z1))>1e-12 for y,z in yz):
                raise ValueError('End face is not an affine rectangle')
            area=(y1-y0)*(z1-z0)
            for n in selected:contributions[n].append(area/4)
        if any(not values for values in contributions.values()):
            raise ValueError('End node has no incident boundary face')
        result[side]={n:math.fsum(values) for n,values in contributions.items()}
        if not math.isclose(math.fsum(result[side].values()),dims[1]*dims[2],rel_tol=1e-10,abs_tol=1e-14):
            raise ValueError('Tributary areas do not cover the full end')
    return result


def field_samples(nodes, cells, data):
    """Three-point tensor quadrature exactly integrates squared Q1/quadratic error."""
    for e,cell in sorted(cells.items()):
        points=[nodes[n] for n in cell]
        volume,_,_=geometry(points)
        ts=[data['temperature'][n][0] for n in cell]
        for j,triplet in enumerate(itertools.product(G3,repeat=3),1):
            local=[v[0] for v in triplet]
            xyz=tuple(interpolate([p[a] for p in points],local) for a in range(3))
            value=interpolate(ts,local)
            weight=volume/8*math.prod(v[1] for v in triplet)
            yield e,j,xyz,value,exact_temperature(xyz[0]),weight


def analytical_report(nodes,cells,ends,dims,data,*,check_nodal=True):
    if tuple(dims)!=(0.2,0.02,0.003):
        raise ValueError('Source benchmark requires the fixed SI bar dimensions')
    keys={(e,i) for e in cells for i in range(1,9)}
    if (set(data['temperature'])!=set(nodes) or set(data['reaction'])!=set(nodes)
            or set(data['flux'])!=keys or set(data['coordinates'])!=keys):
        raise ValueError('Missing source benchmark output identities')
    b=source_vector(nodes,cells)
    reaction={n:data['reaction'][n][0]-b[n] for n in nodes}
    volume=math.prod(dims)
    total=math.fsum(b.values())
    raw_ends={s:math.fsum(data['reaction'][n][0] for n in ns) for s,ns in ends.items()}
    end_reactions={s:math.fsum(reaction[n] for n in ns) for s,ns in ends.items()}
    free=max(abs(reaction[n]) for n in nodes if n not in ends['X_MIN']|ends['X_MAX'])
    balance=abs(math.fsum(reaction.values())+Q*volume)
    t_error=max(abs(data['temperature'][n][0]-exact_temperature(p[0])) for n,p in nodes.items())
    bc=max(abs(data['temperature'][n][0]-T0) for ns in ends.values() for n in ns)
    coord_error=0.; discrete_flux_error=0.; flux_terms=[]; hs=[]
    for e,cell in cells.items():
        points=[nodes[n] for n in cell]
        ve,h,xc=geometry(points); hs.append(h)
        for i,local in enumerate(G2,1):
            xyz=tuple(interpolate([p[a] for p in points],local) for a in range(3))
            coord_error=max(coord_error,*(abs(a-b) for a,b in zip(xyz,data['coordinates'][e,i])))
            flux=data['flux'][e,i]
            # Exact discrete reference is the element's constant slope, not the continuum at its centroid.
            discrete_flux_error=max(discrete_flux_error,abs(flux[0]-exact_flux(xc)),abs(flux[1]),abs(flux[2]))
            flux_terms.append(ve/8*((flux[0]-exact_flux(xyz[0]))**2+flux[1]**2+flux[2]**2))
    h=math.fsum(hs)/len(hs)
    if max(abs(v-h) for v in hs)>1e-10:
        raise ValueError('Source convergence reference requires a uniform x grid')
    t_rms=math.sqrt(math.fsum((computed-reference)**2*w for _,_,_,computed,reference,w in field_samples(nodes,cells,data))/volume)
    q_rms=math.sqrt(math.fsum(flux_terms)/volume)
    expected_t=Q*h*h/(2*K*math.sqrt(30))
    expected_q=Q*h/math.sqrt(12)
    reaction_error=max(free,*(abs(v+Q*volume/2) for v in end_reactions.values()))
    checks={'nodal_temperature':t_error<=1e-4,'boundary_temperature':bc<=1e-4,
            'true_ip_coordinates':coord_error<=1e-7,
            'discrete_integration_point_flux':discrete_flux_error<=1e-3,
            'off_node_temperature_error':abs(t_rms-expected_t)<=1e-4 and t_rms>1e-3,
            'continuous_flux_error':abs(q_rms-expected_q)<=2e-3 and q_rms>1.,
            'consistent_source_power':abs(total-Q*volume)<=1e-12,
            'corrected_reactions_and_free_nodes':reaction_error<=1e-7,
            'source_energy_balance':balance<=1e-7}
    nodal_metrics={}
    if check_nodal:
        areas=end_node_tributary_areas(nodes,cells,ends,dims)
        nodal_error=max(abs(reaction[n]+Q*L/2*area) for by_node in areas.values() for n,area in by_node.items())
        checks['constrained_nodal_reactions']=nodal_error<=TOLERANCES['reaction_absolute_W']
        nodal_metrics={'max_constrained_nodal_reaction_error_W':nodal_error,
                       'end_tributary_area_m2':{side:math.fsum(by_node.values()) for side,by_node in areas.items()},
                       'constrained_nodal_reaction_reference':'-Q*L/2 times sum of adjacent geometric end-face areas/4; either end'}
    if not all(checks.values()):
        raise ValueError('Source analytical verification failed: '+str(checks))
    return {**nodal_metrics,'checks':checks,'tolerances':TOLERANCES,'nodes':len(nodes),'elements':len(cells),
            'integration_points':len(keys),'h_x_m':h,'source_power_W':total,
            'raw_end_RFL_W':raw_ends,'end_reactions_W':end_reactions,
            'max_free_corrected_reaction_W':free,'energy_imbalance_W':balance,
            'max_temperature_error_K':t_error,'max_boundary_temperature_error_K':bc,
            'max_ip_coordinate_error_m':coord_error,
            'max_discrete_flux_error_W_m2':discrete_flux_error,
            'temperature_volume_rms_error_K':t_rms,'expected_temperature_volume_rms_error_K':expected_t,
            'flux_volume_rms_error_W_m2':q_rms,'expected_flux_volume_rms_error_W_m2':expected_q,
            'analytical_temperature':'300 + 50000*x*(0.2-x)/(2*10) K',
            'analytical_flux':'(50000*(x-0.1),0,0) W/m2',
            'RFL_interpretation':'RFL=K*T; pure reaction=RFL minus assembled consistent BF source vector',
            'temperature_quadrature':'3x3x3 Gauss, squared Q1/quadratic error integrated exactly',
            'physical_validation':'NOT_PERFORMED','mesh_independence':'NOT_EVALUATED'}


def figures(nodes,cells,data,dims):
    def csv_bytes(rows):
        f=io.StringIO(newline='');csv.writer(f,lineterminator='\n').writerows(rows);return f.getvalue().encode()
    ts=[['kind','node_or_element','quadrature_point','x_m','y_m','z_m','computed_K','analytical_K','error_K','weight_m3']]
    for n,p in sorted(nodes.items()):
        value=data['temperature'][n][0];ref=exact_temperature(p[0]);ts.append(['node',n,'',*p,value,ref,value-ref,''])
    for e,j,p,value,ref,w in field_samples(nodes,cells,data):
        ts.append(['gauss3_reconstructed',e,j,*p,value,ref,value-ref,w])
    qs=[['element','integration_point','x_m','y_m','z_m','computed_qx_W_m2','computed_qy_W_m2','computed_qz_W_m2','analytical_qx_W_m2']]
    for key,v in sorted(data['flux'].items()):
        p=data['coordinates'][key];qs.append([*key,*p,*v,exact_flux(p[0])])
    def svg(title,points,reference,label,ymin,ymax):
        def xy(x,y):return 90+630*x/L,350-270*(y-ymin)/(ymax-ymin)
        dots=''.join('<circle cx="%.6f" cy="%.6f" r="2" fill="#2563eb" fill-opacity="0.25"/>'%xy(x,y) for x,y in points)
        curve=' '.join('%.6f,%.6f'%xy(x,y) for x,y in reference)
        ticks=''.join(f'<text x="{90+630*f}" y="375" text-anchor="middle">{L*f:g}</text><text x="80" y="{355-270*f}" text-anchor="end">{ymin+(ymax-ymin)*f:g}</text>' for f in (0,.25,.5,.75,1))
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="800" height="450" viewBox="0 0 800 450"><rect width="800" height="450" fill="white"/>'
                f'<g font-family="sans-serif" font-size="14" fill="#172554"><text x="30" y="25">{title}</text><text x="90" y="52">{label}</text>'
                f'<path d="M90 75 V350 H735" fill="none" stroke="#475569"/>{ticks}<polyline points="{curve}" fill="none" stroke="#e11d48" stroke-width="2" stroke-dasharray="7 5"/>{dots}'
                '<text x="360" y="400">x (m)</text><text x="30" y="430">Blue: parsed/reconstructed FE field; red: analytical continuum</text></g></svg>').encode()
    # One centroid per x cell in this 1D field keeps the image compact; CSV retains all values.
    midpoints=[]
    for cell in cells.values():
        p=[nodes[n] for n in cell];_,_,x=geometry(p)
        midpoints.append((x,math.fsum(data['temperature'][n][0] for n in cell)/8))
    refs=[L*i/100 for i in range(101)]
    return {'temperatures.csv':csv_bytes(ts),'flux.csv':csv_bytes(qs),
            'temperature.svg':svg('Synthetic uniform-source conduction: off-node temperature',sorted(set(midpoints)),[(x,exact_temperature(x)) for x in refs],'Temperature (K); Q1 field at cell centers',300,326),
            'flux.svg':svg('Synthetic uniform-source conduction: true-IP flux',[(r[2],r[5]) for r in qs[1:]],[(x,exact_flux(x)) for x in refs],'qx (W/m²); actual printed integration-point coordinates',-5000,5000)}


def refinement_report(coarse,fine):
    h0,h1=coarse['h_x_m'],fine['h_x_m']
    if not math.isclose(h0/h1,2.,rel_tol=1e-8):
        raise ValueError('Require distinct x meshes with refinement factor two')
    orders={name:math.log(coarse[key]/fine[key])/math.log(h0/h1)
            for name,key in [('temperature','temperature_volume_rms_error_K'),('flux','flux_volume_rms_error_W_m2')]}
    if not (1.95<=orders['temperature']<=2.05 and .99<=orders['flux']<=1.01):
        raise ValueError('Source refinement rates do not match the independent oracle')
    return {'status':'SOURCE_RECIPE_REFINEMENT_PASS','observed_orders':orders,
            'scope':'Quadratic uniform-source affine HEX8 recipe only; not general mesh independence',
            'physical_validation':'NOT_PERFORMED'}
