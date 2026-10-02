#!/usr/bin/env python3
"""Deterministic structural/refusal controls; no product or optional backend imports."""
import base64
import copy
import csv
import hashlib
import importlib.util
import io
import json
import pathlib
import stat
import tempfile
import unittest
import warnings
import zipfile

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('inventory_builder', HERE / 'build_inventory.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
DOC = json.loads((HERE / 'component-inventory.json').read_text())


class InventoryTests(unittest.TestCase):
    def test_valid_document(self):
        builder.validate(DOC)

    def test_no_fictitious_standard_claim(self):
        doc = copy.deepcopy(DOC)
        doc['conformance']['spdx'] = True
        with self.assertRaises(ValueError):
            builder.validate(doc)

    def test_dangling_relationship_refused(self):
        doc = copy.deepcopy(DOC)
        doc['relationships'][0]['to'] = 'absent'
        with self.assertRaises(ValueError):
            builder.validate(doc)

    def test_duplicate_component_refused(self):
        doc = copy.deepcopy(DOC)
        doc['components'].append(doc['components'][0])
        with self.assertRaises(ValueError):
            builder.validate(doc)

    def test_external_shipped_claim_refused(self):
        doc = copy.deepcopy(DOC)
        doc['components'][1]['bundled_in_release'] = True
        with self.assertRaises(ValueError):
            builder.validate(doc)

    def test_legal_conclusion_refused(self):
        doc = copy.deepcopy(DOC)
        doc['components'][0]['license_concluded'] = 'Apache-2.0'
        with self.assertRaises(ValueError):
            builder.validate(doc)

    def test_invalid_file_hash_refused(self):
        doc = copy.deepcopy(DOC)
        doc['source']['files'][0]['sha256'] = 'bad'
        with self.assertRaises(ValueError):
            builder.validate(doc)

    def test_changed_source_count_refused(self):
        doc = copy.deepcopy(DOC)
        doc['source']['files'].pop()
        with self.assertRaises(ValueError):
            builder.validate(doc)

    def test_source_manifest_recomputed_independently(self):
        mapping = {f['path']: f['sha256'] for f in DOC['source']['files']}
        digest = hashlib.sha256(json.dumps(mapping, separators=(',', ':'), sort_keys=True).encode()).hexdigest()
        self.assertEqual(digest, '552e9900512a4d1578ef63bac8dfaca6e6e2cd5b95449362354575ff396fc17f')

    def test_archive_member_mappings_are_consistent(self):
        source = {f['path']: f for f in DOC['source']['files']}
        for a in DOC['artifacts']:
            for member in a.get('members', []):
                if 'identical_source_path' in member:
                    expected = source[member['identical_source_path']]
                    self.assertEqual((member['sha256'], member['bytes']), (expected['sha256'], expected['bytes']))
        wheel = next(a for a in DOC['artifacts'] if a['kind'] == 'wheel')
        self.assertEqual(sum(m['path'].endswith('.py') for m in wheel['members']), 21)
        self.assertEqual(sum(len(a.get('members', [])) for a in DOC['artifacts']), 350)

    def test_default_profile_empty_optional_profiles_bounded(self):
        default = next(p for p in DOC['dependency_profiles'] if p['id'] == 'default-runtime')
        self.assertEqual(default['components'], [])
        self.assertEqual(len([c for c in DOC['components'] if 'wheel' in c]), 11)
        self.assertEqual(len([c for c in DOC['components'] if c['role'] == 'observed-vendored-distribution-metadata']), 12)
        self.assertTrue(all(not p.get('complete_system_or_native_sbom', False) for p in DOC['dependency_profiles']))

    def test_rust_projection_not_a_shipped_license_claim(self):
        rust = json.loads((HERE / 'temporal-rust-lock-inventory.json').read_text())
        self.assertEqual(len(rust['packages']), 369)
        self.assertFalse(rust['binary_inclusion_proven'])
        self.assertFalse(rust['licenses_audited'])
        self.assertTrue(all(p['license'] is None for p in rust['packages']))

    def test_wheel_record_valid_control_and_refusals(self):
        def make(path, mutation=None):
            name = 'synthetic-1.dist-info/METADATA'
            record_name = 'synthetic-1.dist-info/RECORD'
            content = b'Name: synthetic\nVersion: 1\n'
            digest = 'sha256=' + base64.urlsafe_b64encode(hashlib.sha256(content).digest()).decode().rstrip('=')
            rows = [[name, digest, str(len(content))], [record_name, '', '']]
            payloads = {name: content}
            if mutation == 'wrong-hash':
                rows[0][1] = 'sha256=' + 'x' * 43
            elif mutation == 'wrong-size':
                rows[0][2] = '0'
            elif mutation == 'duplicate-record-row':
                rows.append(rows[0])
            elif mutation == 'unrecorded-member':
                payloads['extra.py'] = b'x'
            elif mutation == 'hashed-self-entry':
                rows[-1][1] = digest
            elif mutation == 'weak-hash':
                rows[0][1] = 'md5=0'
            elif mutation == 'path-traversal':
                payloads['../extra'] = b'x'
            elif mutation == 'absolute-path':
                payloads['/extra'] = b'x'
            elif mutation == 'backslash-path':
                payloads['a\\extra'] = b'x'
            sio = io.StringIO()
            csv.writer(sio, lineterminator='\n').writerows(rows)
            payloads[record_name] = sio.getvalue().encode()
            with zipfile.ZipFile(path, 'w') as z:
                for n, v in payloads.items():
                    z.writestr(n, v)
                if mutation == 'symlink':
                    info = zipfile.ZipInfo('link')
                    info.external_attr = (stat.S_IFLNK | 0o777) << 16
                    z.writestr(info, 'target')
        with tempfile.TemporaryDirectory() as folder:
            p = pathlib.Path(folder) / 'synthetic.whl'
            make(p)
            _, _, result = builder.wheel_read(p)
            self.assertEqual(result['record_hashed_member_count'], 1)
            for mutation in ('wrong-hash', 'wrong-size', 'duplicate-record-row', 'unrecorded-member', 'hashed-self-entry', 'weak-hash', 'path-traversal', 'absolute-path', 'backslash-path', 'symlink'):
                with self.subTest(mutation=mutation):
                    make(p, mutation)
                    with self.assertRaises(ValueError):
                        builder.wheel_read(p)

    def test_reviewed_directory_name_and_type_refusals(self):
        # Every regular member has a valid RECORD row so name/type refusal is
        # tested independently of missing-member/hash checks.
        def tiny(path, mutation=None):
            meta = 'check-1.dist-info/METADATA'
            record_name = 'check-1.dist-info/RECORD'
            files = {meta: b'Name: check\nVersion: 1\n'}
            directories = ['valid/'] if mutation is None else []
            names = {'dot-alias': 'a/./b', 'double-separator': 'a//b', 'drive-qualified': 'C:/bad'}
            if mutation in names:
                files[names[mutation]] = b'harmless control'
            if mutation == 'unsafe-directory':
                directories = ['../bad/']
            if mutation == 'duplicate-directory':
                directories = ['a/', 'a/']
            if mutation == 'fifo':
                files['special'] = b'harmless control'
            rows = [[n, 'sha256=' + base64.urlsafe_b64encode(hashlib.sha256(v).digest()).decode().rstrip('='), str(len(v))] for n, v in files.items()]
            rows.append([record_name, '', ''])
            sio = io.StringIO()
            csv.writer(sio, lineterminator='\n').writerows(rows)
            files[record_name] = sio.getvalue().encode()
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                with zipfile.ZipFile(path, 'w') as z:
                    for name, content in files.items():
                        if name == 'special':
                            info = zipfile.ZipInfo(name)
                            info.create_system = 3
                            info.external_attr = (stat.S_IFIFO | 0o644) << 16
                            z.writestr(info, content)
                        else:
                            z.writestr(name, content)
                    for name in directories:
                        z.writestr(name, b'')
        with tempfile.TemporaryDirectory() as folder:
            p = pathlib.Path(folder) / 'synthetic.whl'
            tiny(p)
            _, _, result = builder.wheel_read(p)
            self.assertEqual(result['record_hashed_member_count'], 1)
            for mutation in ('unsafe-directory', 'duplicate-directory', 'dot-alias', 'double-separator', 'drive-qualified', 'fifo'):
                with self.subTest(mutation=mutation):
                    tiny(p, mutation)
                    with self.assertRaises(ValueError):
                        builder.wheel_read(p)

    def test_raw_name_and_unix_type_boundaries(self):
        for name, directory in [('a/b', False), ('a/b/', True), ('a', True)]:
            builder.safe_name(name, is_directory=directory)
        for name in ('', '.', './a', 'a/.', 'a//b', 'a/../b', 'a/', 'C:bad', 'C:/bad', '/bad', 'a\\b', 'a\x00b'):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    builder.safe_name(name)
        for kind in (stat.S_IFLNK, stat.S_IFIFO, stat.S_IFSOCK, stat.S_IFCHR, stat.S_IFBLK):
            info = zipfile.ZipInfo('member')
            info.create_system = 3
            info.external_attr = (kind | 0o644) << 16
            with self.subTest(kind=kind):
                with self.assertRaises(ValueError):
                    builder.validate_zip_members([info])
        for name, kind in [('directory', stat.S_IFDIR), ('regular/', stat.S_IFREG)]:
            info = zipfile.ZipInfo(name)
            info.create_system = 3
            info.external_attr = (kind | 0o644) << 16
            with self.subTest(type_name_mismatch=name):
                with self.assertRaises(ValueError):
                    builder.validate_zip_members([info])


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(InventoryTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({'status': 'PASS' if result.wasSuccessful() else 'FAIL', 'test_methods': result.testsRun, 'wheel_refusal_subcases': 16, 'raw_name_refusal_subcases': 12, 'unix_type_refusal_subcases': 7, 'failures': len(result.failures), 'errors': len(result.errors), 'skips': len(result.skipped)}, sort_keys=True))
    raise SystemExit(not result.wasSuccessful())
