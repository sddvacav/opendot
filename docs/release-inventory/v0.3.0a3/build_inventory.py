#!/usr/bin/env python3
"""Read-only archive/metadata inventory builder. Never imports inventoried packages."""
import argparse
import base64
import csv
import email.parser
import hashlib
import importlib.metadata
import io
import json
import pathlib
import platform
import re
import stat
import sys
import tarfile
import tomllib
import zipfile

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

VERSION = '0.3.0a3'
COMMIT = '30610de43da81801e7b88517459fbdf0f667ca2d'
TREE = '95ca23d9d36558680c809f2382bef188c6fc2ae4'
SOURCE_MANIFEST = '552e9900512a4d1578ef63bac8dfaca6e6e2cd5b95449362354575ff396fc17f'
BASE_URL = 'https://github.com/sddvacav/opendot'
EXPECTED = {
    'opendot_engineering-0.3.0a3-py3-none-any.whl': 'd5e08c8ee38b94b35707ac25f0e8b04fbd4cf46a539542e1e6ab95d19d51ea59',
    'opendot_engineering-0.3.0a3.tar.gz': '3df5024d5878682f678049913ea8c3b4236fefdb1c63cf5f2bea089a9451d73b',
    'opendot-engineering-0.3.0a3-source.tar.gz': 'e651190162830d9fe15e388496e1231dce8966bfd5a6807207278e0d23053fa1',
    'RELEASE-NOTES.md': 'ae545f92caadf97186fde4fff7fff70d8ea6d13695301bdb69857c45a76492b7',
}
LOCKS = {
    'ci/build-toolchain-requirements.txt': 'build-backend',
    'ci/requirements.txt': 'ci-test',
    'ci/temporal-sdk-requirements.txt': 'temporal-ci',
}
MARKERS = {
    'implementation_name': 'cpython', 'implementation_version': '3.12.14',
    'os_name': 'posix', 'platform_machine': 'x86_64', 'platform_python_implementation': 'CPython',
    'platform_release': '', 'platform_system': 'Linux', 'platform_version': '',
    'python_full_version': '3.12.14', 'python_version': '3.12', 'sys_platform': 'linux', 'extra': '',
}


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(data):
    return json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False).encode() + b'\n'


def git_object(kind, data):
    return hashlib.sha1(kind.encode() + b' ' + str(len(data)).encode() + b'\0' + data).digest()


def git_tree(root):
    entries = []
    for path in root.iterdir():
        require(not path.is_symlink(), 'Source symlink refused')
        if path.is_dir():
            entries.append((path.name + '/', b'40000 ' + path.name.encode() + b'\0' + git_tree(path)))
        else:
            require(path.is_file(), 'Nonregular source member refused')
            mode = b'100755' if path.stat().st_mode & 0o111 else b'100644'
            entries.append((path.name, mode + b' ' + path.name.encode() + b'\0' + git_object('blob', path.read_bytes())))
    return git_object('tree', b''.join(value for _, value in sorted(entries)))


def safe_name(name, is_directory=False):
    # Check raw spelling before PurePath can normalize dot/empty components.
    require(isinstance(name, str) and name, 'Empty archive name refused')
    require('\\' not in name and not name.startswith('/'), 'Unsafe archive name')
    require(not pathlib.PureWindowsPath(name).drive, 'Drive-qualified archive name refused')
    require(not any(ord(c) < 32 or ord(c) == 127 for c in name), 'Control character in archive name')
    canonical = name[:-1] if is_directory and name.endswith('/') else name
    require(canonical and all(part not in ('', '.', '..') for part in canonical.split('/')), 'Noncanonical archive name refused')


def validate_zip_members(items):
    require(len({item.filename for item in items}) == len(items), 'Duplicate ZIP member')
    for item in items:
        directory = item.is_dir()
        safe_name(item.filename, is_directory=directory)
        if item.create_system == 3:
            kind = stat.S_IFMT(item.external_attr >> 16)
            require(kind in (0, stat.S_IFREG, stat.S_IFDIR), 'Nonregular/nondirectory ZIP member refused')
            require(kind != stat.S_IFDIR or directory, 'ZIP directory type/name mismatch')
            require(kind != stat.S_IFREG or not directory, 'ZIP regular-file type/name mismatch')


def file_info(name, data):
    return {'path': name, 'bytes': len(data), 'sha256': sha(data)}


def wheel_read(path):
    with zipfile.ZipFile(path) as z:
        all_items = z.infolist()
        validate_zip_members(all_items)
        items = [item for item in all_items if not item.is_dir()]
        payloads = {x.filename: z.read(x) for x in items}
    roots = [n for n in payloads if re.fullmatch(r'[^/]+\.dist-info/METADATA', n)]
    require(len(roots) == 1, 'Expected one top-level wheel metadata file')
    root = roots[0].removesuffix('METADATA')
    record = root + 'RECORD'
    rows = list(csv.reader(io.StringIO(payloads[record].decode())))
    require(all(len(row) == 3 for row in rows), 'Malformed RECORD')
    require(len({r[0] for r in rows}) == len(rows), 'Duplicate RECORD row')
    require(set(r[0] for r in rows) == set(payloads), 'RECORD membership mismatch')
    checked = 0
    for name, digest, length in rows:
        if name == record:
            require(not digest and not length, 'RECORD self-hash must be empty')
            continue
        require(digest.startswith('sha256='), 'Expected SHA-256 RECORD digest')
        actual = base64.urlsafe_b64encode(hashlib.sha256(payloads[name]).digest()).decode().rstrip('=')
        require(digest == 'sha256=' + actual and length == str(len(payloads[name])), 'RECORD hash/size mismatch: ' + name)
        checked += 1
    return payloads, roots[0], {'member_count': len(payloads), 'record_hashed_member_count': checked, 'record_self_entry_unhashed': True, 'all_record_hashes_and_sizes_match': True}


def metadata(data):
    m = email.parser.BytesParser().parsebytes(data)
    return {
        'name': m['Name'], 'version': m['Version'], 'requires_python': m['Requires-Python'],
        'requires_dist': m.get_all('Requires-Dist', []), 'provides_extra': m.get_all('Provides-Extra', []),
        'license_expression_declared': m['License-Expression'], 'legacy_license_declared': m['License'],
        'license_classifiers_declared': [x for x in m.get_all('Classifier', []) if x.startswith('License ::')],
        'license_files_declared': m.get_all('License-File', []),
        'license_concluded': None,
    }


def notice_files(payloads, prefix=''):
    output = []
    for name, data in sorted(payloads.items()):
        base = pathlib.PurePosixPath(name).name.lower()
        if name.startswith(prefix) and (base.startswith(('license', 'copying')) or base in ('notice', 'authors')):
            if pathlib.PurePosixPath(name).suffix.lower() not in ('.py', '.pyc'):
                output.append(file_info(name, data))
    return output


def component_id(name, version):
    return 'python:' + canonicalize_name(name) + '@' + version


def declarations(source, rel, require_hash):
    output = []
    for line_number, line in enumerate((source / rel).read_text().splitlines(), 1):
        line = line.split('#', 1)[0].strip()
        if not line:
            continue
        pattern = r'([A-Za-z0-9_.-]+)==([^\s]+)' + (r' --hash=sha256:([a-f0-9]{64})' if require_hash else '')
        m = re.fullmatch(pattern, line)
        require(m is not None, 'Unsupported requirements syntax: ' + rel)
        item = {'name': m[1], 'version': m[2], 'source_path': rel, 'source_line': line_number}
        if require_hash:
            item['wheel_sha256_expected'] = m[3]
        output.append(item)
    return output


def build(args):
    source, dist = args.source, args.dist
    source_bytes = {}
    for p in sorted(source.rglob('*')):
        require(not p.is_symlink(), 'Source symlink refused')
        if p.is_file():
            source_bytes[p.relative_to(source).as_posix()] = p.read_bytes()
    source_hashes = {n: sha(v) for n, v in source_bytes.items()}
    actual_manifest = sha(json.dumps(source_hashes, sort_keys=True, separators=(',', ':')).encode())
    require(len(source_bytes) == 249 and actual_manifest == SOURCE_MANIFEST, 'Exact source manifest mismatch')
    require(git_tree(source).hex() == TREE, 'Exact source Git tree mismatch')
    pyproject = tomllib.loads(source_bytes['pyproject.toml'].decode())
    project = pyproject['project']
    require(project['version'] == VERSION and project['dependencies'] == [], 'Unexpected default package requirements')
    require(set(p.name for p in dist.iterdir()) == set(EXPECTED) | {'SHA256SUMS'}, 'Unexpected publication packet membership')
    checksum_lines = {}
    for line in (dist / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        require(name not in checksum_lines, 'Duplicate release checksum entry')
        checksum_lines[name] = digest
    require(checksum_lines == EXPECTED, 'Publication checksum manifest changed')
    artifacts = []
    for path in sorted(dist.iterdir()):
        data = path.read_bytes()
        if path.name in EXPECTED:
            require(sha(data) == EXPECTED[path.name], 'Release asset changed: ' + path.name)
        a = file_info(path.name, data)
        a['download_url'] = BASE_URL + '/releases/download/v' + VERSION + '/' + path.name
        if path.suffix == '.whl':
            payloads, meta_name, record = wheel_read(path)
            a['kind'] = 'wheel'
            a['verification'] = record
            a['metadata'] = metadata(payloads[meta_name])
            a['wheel_headers'] = payloads[meta_name.removesuffix('METADATA') + 'WHEEL'].decode()
            a['license_and_notice_files'] = notice_files(payloads)
            require(a['metadata']['name'] == project['name'] and a['metadata']['version'] == VERSION, 'Wheel identity mismatch')
            require(a['metadata']['license_expression_declared'] == project['license'], 'Wheel license declaration mismatch')
            require(a['metadata']['license_files_declared'] == ['LICENSE', 'NOTICE'], 'Wheel license member declarations changed')
            a['members'] = []
            modules = 0
            for name, value in sorted(payloads.items()):
                member = file_info(name, value)
                match = 'src/' + name if name.startswith('opendot_engineering/') else None
                if '/licenses/' in name:
                    match = name.rsplit('/', 1)[1]
                if match:
                    require(match in source_bytes and value == source_bytes[match], 'Wheel source payload mismatch')
                    member['identical_source_path'] = match
                    if name.endswith('.py'):
                        modules += 1
                else:
                    member['role'] = 'generated-packaging-metadata'
                a['members'].append(member)
            require(modules == 21 and len(payloads) == 27, 'Unexpected wheel module count')
            a['source_module_count'] = modules
            a['default_requires_dist'] = [r for r in a['metadata']['requires_dist'] if not Requirement(r).marker or Requirement(r).marker.evaluate(MARKERS)]
            require(a['default_requires_dist'] == [], 'Unexpected unconditional runtime dependency')
            require(not any(n.endswith(('.so', '.dll', '.dylib')) for n in payloads), 'Unexpected native payload')
        elif path.name.endswith('.tar.gz'):
            a['kind'] = 'full-source-archive' if '-source.' in path.name else 'packaging-sdist'
            a['members'] = []
            seen = set()
            with tarfile.open(path, mode='r:gz') as archive:
                for entry in archive.getmembers():
                    safe_name(entry.name, is_directory=entry.isdir())
                    require(entry.name not in seen, 'Duplicate tar member')
                    seen.add(entry.name)
                    if entry.isdir():
                        continue
                    require(entry.isfile(), 'Nonregular tar member refused')
                    rel = entry.name.split('/', 1)[1]
                    value = archive.extractfile(entry).read()
                    member = file_info(entry.name, value)
                    member['relative_to_archive_root'] = rel
                    if rel in source_bytes:
                        require(value == source_bytes[rel], 'Tar source payload mismatch: ' + rel)
                        member['identical_source_path'] = rel
                    else:
                        member['role'] = 'generated-packaging-metadata'
                    a['members'].append(member)
            a['members'].sort(key=lambda x: x['path'])
            if a['kind'] == 'full-source-archive':
                require({m['relative_to_archive_root'] for m in a['members']} == set(source_bytes), 'Source archive membership mismatch')
            else:
                require(len(a['members']) == 74, 'Unexpected sdist member count')
        else:
            a['kind'] = 'release-document' if path.name == 'RELEASE-NOTES.md' else 'release-checksum-manifest'
        artifacts.append(a)

    wheel_paths = {}
    for folder in [args.test_wheelhouse, args.build_wheelhouse]:
        for path in sorted(folder.glob('*.whl')):
            digest = sha(path.read_bytes())
            if digest in wheel_paths:
                require(wheel_paths[digest].read_bytes() == path.read_bytes(), 'Hash collision')
            wheel_paths[digest] = path
    components = [{
        'id': 'release:opendot-engineering@' + VERSION, 'name': project['name'], 'version': VERSION,
        'role': 'released-project', 'bundled_in_release': True,
        'license_expression_declared': project['license'], 'license_concluded': None,
        'license_evidence': ['LICENSE', 'NOTICE', 'docs/PROVENANCE.md', 'assets/brand/NOTICE'],
        'license_scope_note': 'Project declaration and retained notices; not a per-file rights/legal conclusion. Brand artwork is Apache-2.0 only to the extent applicable rights exist.',
    }]
    relationships = []
    profiles = []
    all_locked = {}
    for rel, role in LOCKS.items():
        pins = declarations(source, rel, True)
        profile_ids = []
        for pin in pins:
            cid = component_id(pin['name'], pin['version'])
            require(cid not in all_locked, 'Unexpected repeated locked component')
            require(pin['wheel_sha256_expected'] in wheel_paths, 'Pinned wheel unavailable: ' + cid)
            path = wheel_paths[pin['wheel_sha256_expected']]
            payloads, meta_name, record = wheel_read(path)
            md = metadata(payloads[meta_name])
            require(canonicalize_name(md['name']) == canonicalize_name(pin['name']) and md['version'] == pin['version'], 'Pinned metadata identity mismatch')
            c = {'id': cid, **md, 'role': role, 'bundled_in_release': False,
                 'declaration': pin, 'wheel': file_info(path.name, path.read_bytes()),
                 'metadata_file': file_info(meta_name, payloads[meta_name]),
                 'license_and_notice_files': notice_files(payloads), 'record_verification': record,
                 'origin_evidence': {'kind': 'existing-byte-pinned-wheel', 'declaration_source_url': BASE_URL + '/blob/' + COMMIT + '/' + rel, 'official_version_metadata_url': 'https://pypi.org/pypi/' + md['name'] + '/' + md['version'] + '/json', 'official_metadata_refetched_for_every_wheel': False},
                 'native_payloads': [file_info(n, v) for n, v in sorted(payloads.items()) if n.endswith(('.so', '.dll', '.dylib'))],
                 'license_scope_note': 'Top-level package declaration; bundled subcomponents may have additional licenses. This is not an aggregate license expression for the whole wheel.'}
            components.append(c)
            all_locked[cid] = c
            profile_ids.append(cid)
            relationships.append({'from': components[0]['id'], 'to': cid, 'relationship': role + '-uses', 'evidence': rel})
            for nested in sorted(n for n in payloads if n.endswith('.dist-info/METADATA') and n != meta_name):
                nmd = metadata(payloads[nested])
                nid = cid + ':contains:' + component_id(nmd['name'], nmd['version'])
                nested_dir = nested.removesuffix('METADATA')
                components.append({'id': nid, **nmd, 'role': 'observed-vendored-distribution-metadata', 'bundled_in_release': False,
                    'contained_in_component': cid, 'metadata_file': file_info(nested, payloads[nested]),
                    'license_and_notice_files': notice_files(payloads, nested_dir),
                    'scope_note': 'Evidence of nested distribution identity/notices only; no exhaustive file-ownership map or reconstructed vendored dependency graph.'})
                relationships.append({'from': cid, 'to': nid, 'relationship': 'contains-distribution-metadata'})
            if canonicalize_name(md['name']) == 'setuptools':
                for name, expression, evidence, files in [
                    ('validate-pyproject', 'MPL-2.0', 'setuptools/config/NOTICE', ['setuptools/config/setuptools.schema.json', 'setuptools/config/distutils.schema.json']),
                    ('validate-pyproject-generated-integration', 'MPL-2.0', 'setuptools/config/_validate_pyproject/NOTICE', ['setuptools/config/_validate_pyproject/extra_validations.py', 'setuptools/config/_validate_pyproject/formats.py', 'setuptools/config/_validate_pyproject/error_reporting.py']),
                    ('fastjsonschema-exceptions', 'BSD-3-Clause', 'setuptools/config/_validate_pyproject/NOTICE', ['setuptools/config/_validate_pyproject/fastjsonschema_exceptions.py']),
                ]:
                    nid = cid + ':notice:' + name
                    require(expression in payloads[evidence].decode(), 'Notice license text changed')
                    components.append({'id': nid, 'name': name, 'version': None, 'role': 'notice-identified-code', 'bundled_in_release': False,
                        'contained_in_component': cid, 'license_expression_declared': expression, 'license_concluded': None,
                        'notice_file': file_info(evidence, payloads[evidence]),
                        'observed_corresponding_files': [file_info(n, payloads[n]) for n in files if n in payloads],
                        'scope_note': 'Version unavailable from this notice; not inferred from unrelated package releases.'})
                    relationships.append({'from': cid, 'to': nid, 'relationship': 'contains-notice-identified-code'})
            if canonicalize_name(md['name']) == 'temporalio':
                n = 'temporalio/bridge/Cargo.lock'
                cargo = tomllib.loads(payloads[n].decode())
                c['rust_lockfile'] = {**file_info(n, payloads[n]), 'declared_package_count': len(cargo['package']), 'package_versions_and_sources_recorded_in': 'temporal-rust-lock-inventory.json', 'scope_note': 'Cargo resolution records are not proof that each crate is compiled or shipped in the bridge. Crate license closure and binary linkage have not been audited.'}
                rust_inventory = {'format': 'opendot-unreviewed-rust-lock-projection', 'format_version': 1, 'parent_component': cid, 'source_wheel_sha256': c['wheel']['sha256'], 'source_member': c['rust_lockfile']['path'], 'source_member_sha256': c['rust_lockfile']['sha256'], 'binary_inclusion_proven': False, 'licenses_audited': False, 'packages': [{'name': p['name'], 'version': p['version'], 'source': p.get('source'), 'checksum_as_declared_by_cargo': p.get('checksum'), 'license': None} for p in cargo['package']]}
        profiles.append({'id': role, 'declaration_path': rel, 'scope': 'CPython 3.12.14 / Linux x86_64 / no extras', 'components': profile_ids})

    for profile in profiles:
        allowed = {canonicalize_name(all_locked[c]['name']): all_locked[c] for c in profile['components']}
        active, inactive = [], []
        for cid in profile['components']:
            for raw in all_locked[cid]['requires_dist']:
                r = Requirement(raw)
                if r.marker and not r.marker.evaluate(MARKERS):
                    inactive.append({'component': cid, 'requirement': raw})
                    continue
                name = canonicalize_name(r.name)
                require(name in allowed, 'Missing active dependency in profile: ' + raw)
                target = allowed[name]
                require(r.specifier.contains(target['version']), 'Locked dependency version violates metadata requirement')
                edge = {'from': cid, 'to': target['id'], 'relationship': 'requires-python-distribution', 'requirement': raw, 'profile': profile['id']}
                relationships.append(edge)
                active.append(edge)
        profile['active_requirement_edges'] = active
        profile['inactive_marker_requirements'] = inactive
        profile['python_distribution_metadata_closure_verified'] = True
        profile['complete_system_or_native_sbom'] = False
    profiles.insert(0, {'id': 'default-runtime', 'components': [], 'source_declaration': 'pyproject.toml:project.dependencies', 'wheel_requires_dist_with_no_extra': [], 'python_distribution_dependency_declaration_complete': True, 'interpreter_and_os_inventoried': False})

    upstream = json.loads(args.upstream_evidence.read_text())
    evidence_by_name = {e['name']: e for e in upstream}
    for e in upstream:
        require(git_object('blob', e['license_text'].encode()).hex() == e['source_git_blob_sha1'], 'Upstream license evidence Git blob hash mismatch')
    snapshot_ids = {}
    for rel, role in [('examples/cad_cae/requirements-tested.txt', 'historical-cad-recipe'), ('examples/simulated-lab/requirements-tested.txt', 'simulated-lab-recipe')]:
        ids = []
        for pin in declarations(source, rel, False):
            cid = component_id(pin['name'], pin['version'])
            if cid not in all_locked and cid not in snapshot_ids:
                component = {'id': cid, 'name': pin['name'], 'version': pin['version'], 'role': 'recipe-only-reference', 'bundled_in_release': False,
                    'artifact_sha256': None, 'artifact_metadata_inspected': False, 'license_concluded': None,
                    'license_expression_declared': None, 'declarations': [pin]}
                if pin['name'] in evidence_by_name:
                    evidence = evidence_by_name[pin['name']]
                    require(pin['version'] == evidence['version'], 'Upstream license version mismatch')
                    component['license_expression_declared'] = evidence['declared_license']
                    component['license_evidence'] = {'source_url': evidence['source_url'], 'git_blob_sha1': evidence['source_git_blob_sha1'], 'license_text_sha256': sha(evidence['license_text'].encode()), 'scope': evidence['scope']}
                if pin['name'] in ('build123d', 'cadquery-ocp'):
                    component['license_expression_declared'] = 'Apache-2.0'
                    component['license_evidence'] = {'kind': 'existing-source-guide-declaration', 'source_path': 'docs/cad-geometry.md', 'source_sha256': source_hashes['docs/cad-geometry.md'], 'independently_verified_for_exact_distribution': False, 'scope': 'Wrapper/project declaration only; underlying OCCT and other bundled native libraries retain their own licenses.'}
                components.append(component)
                snapshot_ids[cid] = component
            elif cid in snapshot_ids:
                snapshot_ids[cid]['declarations'].append(pin)
            ids.append(cid)
            relationships.append({'from': components[0]['id'], 'to': cid, 'relationship': role + '-references', 'evidence': rel})
        profiles.append({'id': role, 'declaration_path': rel, 'components': ids, 'hash_locked': False, 'dependency_closure_verified': False, 'installed_or_executed_for_this_inventory': False, 'scope_note': 'A version recipe, not an independently reconstructed installed environment or full transitive SBOM. Pins shared with other profiles do not validate this complete recipe.'})
    for extra, requirements in project['optional-dependencies'].items():
        for raw in requirements:
            r = Requirement(raw)
            matches = [c['id'] for c in components if c['id'].startswith('python:') and ':contains:' not in c['id'] and ':notice:' not in c['id'] and canonicalize_name(c['name']) == canonicalize_name(r.name) and c['version'] and r.specifier.contains(c['version'])]
            require(len(matches) == 1, 'Optional extra inventory ambiguity')
            relationships.append({'from': components[0]['id'], 'to': matches[0], 'relationship': 'optional-extra-direct-requirement', 'extra': extra, 'requirement': raw, 'evidence': 'pyproject.toml:project.optional-dependencies', 'scope_note': 'The test extra permits a range; the linked CI version is one inspected selection, not a resolution guarantee for every install.' if extra == 'test' else 'Selected only when this extra is requested.'})

    external = [
        ('gmsh', '4.15.2', 'GNU GPL version 2 or later with an additional linking exception; commercial licensing separately available', 'docs/cad-mesh.md', 'https://gmsh.info/#Licensing'),
        ('calculix-ccx', '2.23', 'GPL; the official project links GPL version 2; exact binary/build and any later-version choice not inspected', 'docs/thermal-conduction.md', 'https://www.dhondt.de/'),
        ('git', '>=2.52.0', 'Not reverified in this inventory', 'docs/git-workspaces.md', None),
        ('opencascade-occt', None, 'Source guide reports LGPL 2.1 with an additional exception; exact installed binary/version not inspected', 'docs/cad-geometry.md', 'https://occt3d.com/open-cascade-technology/index.html'),
        ('temporal-cli', '1.9.1', 'Not reverified in this inventory', 'ci/acquire_temporal_cli.py', None),
        ('temporal-server', '1.32.0', 'Not reverified in this inventory', 'docs/temporal-qualification-evidence.md', None),
    ]
    for name, version, license_note, evidence, url in external:
        cid = 'external:' + name
        components.append({'id': cid, 'name': name, 'version_or_constraint_as_declared': version, 'role': 'excluded-external-tool-or-native-backend', 'bundled_in_release': False, 'binary_hash': None, 'binary_inspected': False, 'license_concluded': None, 'license_note': license_note, 'declaration_path': evidence, 'official_reference': url})
        relationships.append({'from': components[0]['id'], 'to': cid, 'relationship': 'optional-external-tool-reference', 'evidence': evidence})

    public_evidence = []
    for e in upstream:
        public_evidence.append({k: v for k, v in e.items() if k != 'license_text'})
    notice_paths = ['LICENSE', 'NOTICE', 'SECURITY.md', 'assets/brand/NOTICE', 'docs/PROVENANCE.md', 'docs/release-checklist.md', *LOCKS]
    gaps = [
        {'id': 'G1', 'scope': 'host-platform', 'missing': 'Interpreter/stdlib, bootstrap pip, operating system, system libraries, runner image and GitHub Action implementation inventories are absent.'},
        {'id': 'G2', 'scope': 'optional-native', 'missing': 'CAD/Gmsh/CalculiX/OpenCASCADE/Git binaries and their exact bundled or linked native libraries are not inspected. Native execution is not performed.'},
        {'id': 'G3', 'scope': 'simulation-and-cad-recipes', 'missing': 'The two unhashed recipes do not establish complete transitive graphs, resolved wheel identities or full notices. Most recipe-only licenses remain unknown rather than guessed.'},
        {'id': 'G4', 'scope': 'temporal-native-bridge', 'missing': 'The bridge binary and Cargo.lock are hashed, but Rust crate licenses, enabled features, actual compiled/linked contents and system-library closure are not reconstructed.'},
        {'id': 'G5', 'scope': 'build-vendoring', 'missing': 'Nested distribution metadata and selected explicit notices are recorded for setuptools. Complete vendored-file ownership and generated-code provenance are not reconstructed. Top-level MIT does not relabel nested LGPL/MPL/BSD material.'},
        {'id': 'G6', 'scope': 'legal-security', 'missing': 'No vulnerability scan, comprehensive copyright/rights audit, legal opinion, license compatibility finding, trademark clearance, digital signature or origin attestation is produced. Process isolation alone does not settle GPL obligations.'},
        {'id': 'G7', 'scope': 'optional-extra-expansion', 'missing': 'Upstream extras excluded by the recorded no-extras marker environment are not resolved or audited; other Python/OS/architecture profiles may have different requirements.'},
        {'id': 'G8', 'scope': 'source-metadata-and-publication', 'missing': 'Source docs retain some version-bound predecessor release statements. Artifact hashes identify this exact packet; this inventory is a new unattached supplement and does not alter or re-certify any published asset.'},
    ]
    inventory = {
        'format': 'opendot-bounded-component-inventory', 'format_version': 1,
        'inventory_date_utc': '2026-10-02',
        'conformance': {'spdx': False, 'cyclonedx': False, 'full_transitive_sbom': False, 'certification': False},
        'scope': 'Exact five-file a3 release packet and complete regular-file member hashes for its three archives; source-byte mappings; declared optional recipes; separately inspected existing hash-locked test/build/Temporal wheels and visible nested metadata/notices. Excluded components are references, never a claim that they ship inside OpenDot.',
        'generator': {'name': 'build_inventory.py', 'script_sha256': sha(pathlib.Path(__file__).read_bytes()), 'python_implementation': platform.python_implementation(), 'python_version': platform.python_version(), 'packaging_version': importlib.metadata.version('packaging'), 'inventoried_package_code_imported': False, 'dependency_installation_performed': False, 'network_access_by_generator': False},
        'source': {'repository': BASE_URL, 'release_tag': 'v' + VERSION, 'commit_as_bound_by_release_notes': COMMIT, 'computed_git_tree_sha1': TREE, 'file_count': len(source_bytes), 'source_path_sha256_mapping_digest': SOURCE_MANIFEST, 'digest_convention': 'SHA-256 of UTF-8 json.dumps(relative-path-to-sha256 mapping, sort_keys=True, separators=(comma,colon)), no newline', 'commit_signature_or_remote_ref_verified_by_this_inventory': False, 'files': [file_info(n, data) for n, data in source_bytes.items()]},
        'artifacts': artifacts, 'project_notices_and_policy_evidence': [file_info(n, source_bytes[n]) for n in notice_paths],
        'components': components, 'relationships': relationships, 'dependency_profiles': profiles,
        'python_marker_environment_for_inspected_locks': MARKERS,
        'primary_license_checks': public_evidence,
        'upstream_metadata_caveat': 'Bluesky 1.15.1 PyPI displays a conflicting Apache classifier and BSD license text. The exact upstream tag LICENSE directly declares BSD-3-Clause; recorded as root-license evidence, not as proof of all files/NOTICE obligations.',
        'known_gaps': gaps,
        'claims': {'release_members_and_source_mapping_verified': True, 'no_default_external_python_requirements_declared': True, 'wheel_package_payload_source_match': 'All 21 package modules byte-match project source; remaining six members are metadata/LICENSE/NOTICE/RECORD. This is a structural/byte observation, not independent authorship certification.', 'complete_dependency_license_clearance': False, 'production_ready': False},
    }
    validate(inventory)
    return inventory, rust_inventory


def validate(doc):
    require(doc['format'] == 'opendot-bounded-component-inventory' and doc['format_version'] == 1, 'Unsupported format')
    require(doc['conformance'] == {'spdx': False, 'cyclonedx': False, 'full_transitive_sbom': False, 'certification': False}, 'Scope assertion changed')
    ids = [c['id'] for c in doc['components']]
    require(len(ids) == len(set(ids)), 'Duplicate component ID')
    for r in doc['relationships']:
        require(r['from'] in ids and r['to'] in ids, 'Dangling component relationship')
    for p in doc['dependency_profiles']:
        require(all(x in ids for x in p['components']), 'Dangling profile component')
    for collection in [doc['source']['files'], doc['project_notices_and_policy_evidence'], doc['artifacts']]:
        for f in collection:
            require(type(f['bytes']) is int and f['bytes'] >= 0 and re.fullmatch('[a-f0-9]{64}', f['sha256']), 'Invalid file record')
    require(doc['source']['file_count'] == len(doc['source']['files']) == 249, 'Source count mismatch')
    require(all(not c.get('bundled_in_release') for c in doc['components'][1:]), 'External component marked shipped')
    require(all(c.get('license_concluded') is None for c in doc['components']), 'Unexpected legal conclusion')
    require(len(doc['artifacts']) == 5 and len(doc['known_gaps']) >= 8, 'Inventory scope incomplete')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('generate', 'verify'))
    for name in ('source', 'dist', 'test-wheelhouse', 'build-wheelhouse', 'output', 'upstream-evidence'):
        parser.add_argument('--' + name, type=pathlib.Path, required=True)
    args = parser.parse_args()
    inventory, rust = build(args)
    outputs = {'component-inventory.json': encoded(inventory), 'temporal-rust-lock-inventory.json': encoded(rust)}
    if args.action == 'generate':
        args.output.mkdir(parents=True, exist_ok=True)
        for name, value in outputs.items():
            (args.output / name).write_bytes(value)
    else:
        for name, value in outputs.items():
            require((args.output / name).read_bytes() == value, 'Generated inventory differs: ' + name)
    summary = {'status': 'PASS', 'action': args.action, 'source_files': inventory['source']['file_count'],
               'release_assets': len(inventory['artifacts']), 'archive_regular_files': {a['path']: len(a['members']) for a in inventory['artifacts'] if 'members' in a},
               'components': len(inventory['components']), 'relationships': len(inventory['relationships']),
               'inspected_external_wheels': sum('wheel' in c for c in inventory['components']),
               'record_hashed_payloads_checked': sum(c.get('record_verification', {}).get('record_hashed_member_count', 0) for c in inventory['components']) + 26,
               'rust_lock_packages_not_license_audited': len(rust['packages']),
               'output_sha256': {n: sha(v) for n, v in outputs.items()},
               'not_claimed': ['SPDX or CycloneDX conformance', 'full transitive or native SBOM', 'legal/security certification']}
    print(json.dumps(summary, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
