"""External Gmsh process helper. Never imported by the core adapter."""
import json
import ctypes
import hashlib
import math
import os
from pathlib import Path
import stat
import sys


def _file_identity(path, *, mapped_device_inode=None):
    """Hash a regular file, checking the opened inode and ordinary replacement."""
    path = Path(path).resolve(strict=True)
    with path.open('rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size <= 0:
            raise ValueError('Gmsh identity requires a nonempty regular file')
        if mapped_device_inode is not None and (before.st_dev, before.st_ino) != mapped_device_inode:
            raise ValueError('Loaded Gmsh native mapping no longer matches its file')
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        after = os.fstat(stream.fileno())
    signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    if signature(before) != signature(after) or signature(after) != signature(path.stat()):
        raise ValueError('Gmsh identity file changed while hashing')
    return {'path': str(path), 'sha256': digest, 'bytes': before.st_size}


def _mapped_native_file(address, maps):
    """Resolve the actual mapped symbol, never the wrapper's requested soname."""
    for line in maps.splitlines():
        fields = line.split(maxsplit=5)
        start, end = (int(v, 16) for v in fields[0].split('-'))
        if not start <= address < end:
            continue
        if len(fields) != 6 or 'x' not in fields[1] or not fields[5].startswith('/') or fields[5].endswith(' (deleted)') or '\\' in fields[5]:
            raise ValueError('Cannot identify the loaded Gmsh native file')
        major, minor = (int(v, 16) for v in fields[3].split(':'))
        return Path(fields[5]), (os.makedev(major, minor), int(fields[4]))
    raise ValueError('Gmsh native symbol has no identifiable file mapping')


def _runtime_identity(gmsh):
    """Fail closed before geometry work; supported execution is Linux only."""
    wrapper_version = gmsh.__version__
    native_version = gmsh.option.getString('General.Version')
    if wrapper_version != '4.15.2' or native_version != wrapper_version:
        raise ValueError(f'Gmsh wrapper/native version mismatch: wrapper={wrapper_version}, native={native_version}; both must be 4.15.2')
    if sys.platform != 'linux':
        raise ValueError('Verified Gmsh native identity currently requires Linux /proc/self/maps')
    maps = Path('/proc/self/maps').read_text()
    mappings = [_mapped_native_file(ctypes.cast(getattr(gmsh.lib, symbol), ctypes.c_void_p).value, maps)
                for symbol in ('gmshInitialize', 'gmshOptionGetString')]
    if mappings[0] != mappings[1]:
        raise ValueError('Gmsh native API symbols resolve to different files')
    path, mapped_device_inode = mappings[0]
    return {'schema_version': '1', 'status': 'VERIFIED_AT_EXECUTION',
            'method': 'linux.proc-self-maps.symbol-address+device-inode',
            'wrapper': {'version': wrapper_version, **_file_identity(gmsh.__file__)},
            'native': {'version': native_version, **_file_identity(path, mapped_device_inode=mapped_device_inode)}}


def main():
    import resource
    resource.setrlimit(resource.RLIMIT_FSIZE, (32*1024*1024, 32*1024*1024))
    resource.setrlimit(resource.RLIMIT_CPU, (300,300))
    import gmsh  # GPL tool loaded only in this explicitly selected subprocess
    out = Path(sys.argv[1])
    recipe = json.loads((out / 'recipe.json').read_text())
    dims = recipe['dimensions_m']
    divisions = recipe['divisions']
    if recipe.get('schema_version') != '2' or recipe.get('recipe') != 'mesh.synthetic_beam.hex8.v2':
        raise ValueError('Worker requires the native-identity v2 recipe')
    gmsh.initialize([], readConfigFiles=False)
    try:
        runtime = _runtime_identity(gmsh)
        recipe['gmsh_runtime'] = runtime
        (out / 'recipe.json').write_text(json.dumps(recipe, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n')
        gmsh.option.setNumber('General.NumThreads', 1)
        gmsh.option.setNumber('Mesh.MaxNumThreads1D', 1)
        gmsh.option.setNumber('Mesh.MaxNumThreads2D', 1)
        gmsh.option.setNumber('Mesh.MaxNumThreads3D', 1)
        gmsh.option.setString('Geometry.OCCTargetUnit', 'M')
        gmsh.model.occ.importShapes(str(out / 'beam.step'))
        gmsh.model.occ.synchronize()
        volumes = gmsh.model.getEntities(3)
        if len(volumes) != 1 or len(gmsh.model.getEntities(2)) != 6 or len(gmsh.model.getEntities(1)) != 12:
            raise ValueError('Unsupported imported topology')
        mass = gmsh.model.occ.getMass(*volumes[0])
        bbox = gmsh.model.getBoundingBox(*volumes[0])
        if not math.isclose(mass, math.prod(dims), rel_tol=1e-8):
            raise ValueError('Imported STEP volume is not SI')
        if any(abs(a-b) > 2e-7 for a,b in zip(bbox, [0,0,0,*dims])):
            raise ValueError('Imported STEP bounds are not SI')
        for _, tag in gmsh.model.getEntities(1):
            b = gmsh.model.getBoundingBox(1, tag)
            axis = max(range(3), key=lambda i: b[i+3]-b[i])
            gmsh.model.mesh.setTransfiniteCurve(tag, divisions[axis]+1)
        regions = {}
        for _, tag in gmsh.model.getEntities(2):
            gmsh.model.mesh.setTransfiniteSurface(tag)
            gmsh.model.mesh.setRecombine(2, tag)
            c = gmsh.model.occ.getCenterOfMass(2, tag)
            matches = [(i,s) for i in range(3) for s in range(2) if abs(c[i]-s*dims[i]) < 1e-9]
            if len(matches) != 1:
                raise ValueError('Ambiguous semantic face')
            i,s = matches[0]
            name = ('X','Y','Z')[i] + ('_MIN','_MAX')[s]
            if name in regions:
                raise ValueError('Duplicate semantic face')
            physical = 2 + 2*i+s
            gmsh.model.addPhysicalGroup(2, [tag], physical)
            gmsh.model.setPhysicalName(2, physical, name)
            regions[name] = {'dimension':2, 'physical_tag':physical, 'entity_tags':[tag]}
        gmsh.model.mesh.setTransfiniteVolume(volumes[0][1])
        gmsh.model.addPhysicalGroup(3, [volumes[0][1]], 1)
        gmsh.model.setPhysicalName(3, 1, 'BODY')
        regions['BODY'] = {'dimension':3, 'physical_tag':1, 'entity_tags':[volumes[0][1]]}
        gmsh.option.setNumber('Mesh.ElementOrder', 1)
        gmsh.option.setNumber('Mesh.MshFileVersion', 2.2)
        gmsh.option.setNumber('Mesh.Binary', 0)
        gmsh.model.mesh.generate(3)
        types, tags, _ = gmsh.model.mesh.getElements(3)
        if list(types) != [5]:
            raise ValueError('Expected only first-order eight-node hexahedra')
        quality = {}
        for name in ('minDetJac', 'minSICN', 'volume'):
            values = list(map(float, gmsh.model.mesh.getElementQualities(tags[0], name)))
            if not values or not all(math.isfinite(v) and v > 0 for v in values):
                raise ValueError('Nonpositive or nonfinite mesh quality')
            quality[name] = {'min':min(values), 'max':max(values), 'sum':sum(values)}
        gmsh.write(str(out / 'beam.msh'))
        if _runtime_identity(gmsh) != runtime:
            raise ValueError('Gmsh wrapper/native identity changed during meshing')
        report = {'gmsh_version':gmsh.__version__, 'gmsh_runtime':runtime, 'imported_volume_m3':mass,
                  'imported_bbox_m':list(bbox), 'quality':quality, 'regions':regions,
                  'volume_elements':len(tags[0]), 'nodes':len(gmsh.model.mesh.getNodes()[0])}
        (out / 'worker.json').write_text(json.dumps(report, sort_keys=True, allow_nan=False)+'\n')
    finally:
        gmsh.finalize()


if __name__ == '__main__':
    main()
