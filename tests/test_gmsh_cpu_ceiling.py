"""Fake-resource AST tests only: no worker, Gmsh, solver, or kernel-limit run.

Only main's prefix before its Gmsh import is compiled. A restricted import hook
supplies fake resource and a sentinel records reaching the unexecuted boundary.
"""
import ast
from pathlib import Path
import unittest


SOURCE = (Path(__file__).resolve().parents[1] / 'src' / 'opendot_engineering'
          / 'executors' / '_gmsh_worker.py')
SOLVER_SOURCE = SOURCE.with_name('thermal_conduction.py')
MAX_BYTES = 32 * 1024 * 1024


class FakeResource:
    RLIMIT_FSIZE = 'file-size'
    RLIMIT_CPU = 'cpu'

    def __init__(self, inherited, *, infinity=-1, fail_at=None, error=None,
                 inherited_fsize=None):
        self.inherited = inherited
        self.RLIM_INFINITY = infinity
        self.fail_at = fail_at
        self.error = error
        self.inherited_fsize = inherited_fsize
        self.calls = []

    def getrlimit(self, which):
        self.calls.append(('get', which))
        if which != self.RLIMIT_CPU:
            raise AssertionError('Only CPU limits are queried')
        if self.fail_at == 'get':
            raise self.error
        return self.inherited

    def setrlimit(self, which, limits):
        self.calls.append(('set', which, limits))
        if self.fail_at == which:
            raise self.error
        if which == self.RLIMIT_CPU:
            for value in limits:
                for inherited in self.inherited:
                    if inherited != self.RLIM_INFINITY and value > inherited:
                        raise AssertionError('Attempted to raise an inherited CPU cap')
        elif which == self.RLIMIT_FSIZE:
            if self.inherited_fsize is not None and max(limits) > self.inherited_fsize:
                raise ValueError('Existing FSIZE set exceeds fake inherited hard cap')
        else:
            raise AssertionError('Unexpected resource operation')


def worker_prefix():
    module = ast.parse(SOURCE.read_text(), filename=str(SOURCE))
    main, = (node for node in module.body
             if isinstance(node, ast.FunctionDef) and node.name == 'main')
    index, = (i for i, node in enumerate(main.body)
              if isinstance(node, ast.Import)
              and any(alias.name == 'gmsh' for alias in node.names))
    return main.body[:index]


class GmshCpuCeilingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prefix = worker_prefix()
        sentinel = ast.Expr(value=ast.Call(func=ast.Name(id='boundary', ctx=ast.Load()),
                                          args=[], keywords=[]))
        cls.prefix_code = compile(ast.fix_missing_locations(
            ast.Module(body=[*prefix, sentinel], type_ignores=[])), str(SOURCE), 'exec')

    def invoke(self, resource, *, import_error=None):
        imports = []

        def fake_import(name, *args, **kwargs):
            imports.append(name)
            if name != 'resource':
                raise AssertionError('Only fake resource may be imported')
            if import_error is not None:
                raise import_error
            return resource

        namespace = {'__builtins__': {'__import__': fake_import, 'min': min},
                     'boundary': lambda: resource.calls.append(('before-gmsh',))}
        try:
            exec(self.prefix_code, namespace)
        finally:
            self.assertEqual(imports, ['resource'])

    def check_limits(self, inherited, expected, *, infinity=-1):
        resource = FakeResource(inherited, infinity=infinity)
        self.invoke(resource)
        self.assertEqual(resource.calls, [
            ('set', resource.RLIMIT_FSIZE, (MAX_BYTES, MAX_BYTES)),
            ('get', resource.RLIMIT_CPU),
            ('set', resource.RLIMIT_CPU, (expected, expected)),
            ('before-gmsh',),
        ])

    def test_both_unlimited_use_existing_300_second_cap(self):
        self.check_limits((-1, -1), 300)

    def test_lower_hard_cap_is_never_raised(self):
        self.check_limits((30, 30), 30)

    def test_lower_soft_cap_is_never_raised(self):
        self.check_limits((10, 30), 10)

    def test_unlimited_soft_does_not_hide_finite_hard(self):
        # Defensive synthetic pair; not a claimed valid kernel configuration.
        self.check_limits((-1, 30), 30)

    def test_unlimited_hard_does_not_hide_finite_soft(self):
        self.check_limits((10, -1), 10)

    def test_zero_soft_remains_numerically_zero(self):
        self.check_limits((0, 30), 0)

    def test_zero_hard_remains_numerically_zero(self):
        # Synthetic input; no zero-duration kernel guarantee is implied.
        self.check_limits((-1, 0), 0)

    def test_both_zero_remain_numerically_zero(self):
        self.check_limits((0, 0), 0)

    def test_larger_inherited_caps_keep_existing_300_second_cap(self):
        self.check_limits((600, 900), 300)

    def test_equal_300_second_caps_are_preserved(self):
        self.check_limits((300, 300), 300)

    def test_large_finite_values_are_not_assumed_unlimited(self):
        self.check_limits((2**63 - 2, 2**63 - 1), 300)

    def test_unlimited_is_compared_to_the_resource_constant(self):
        for infinity in (-1, 2**64 - 1):
            for inherited, expected in [
                ((infinity, infinity), 300), ((infinity, 30), 30),
                ((10, infinity), 10), ((0, infinity), 0),
            ]:
                with self.subTest(infinity=infinity, inherited=inherited):
                    self.check_limits(inherited, expected, infinity=infinity)

    def test_neither_cap_can_increase_across_finite_boundary_matrix(self):
        for soft in (0, 1, 10, 30, 299, 300, 301, 1000):
            for hard in (0, 1, 10, 30, 299, 300, 301, 1000):
                if soft > hard:
                    continue
                with self.subTest(soft=soft, hard=hard):
                    self.check_limits((soft, hard), min(300, soft, hard))

    def test_resource_import_failure_propagates_before_any_limit_call(self):
        resource = FakeResource((10, 30))
        error = ImportError('injected resource import failure')
        with self.assertRaises(ImportError) as caught:
            self.invoke(resource, import_error=error)
        self.assertIs(caught.exception, error)
        self.assertEqual(resource.calls, [])

    def test_get_failure_propagates_without_cpu_set_or_gmsh_boundary(self):
        error = OSError('injected CPU get failure')
        resource = FakeResource((10, 30), fail_at='get', error=error)
        with self.assertRaises(OSError) as caught:
            self.invoke(resource)
        self.assertIs(caught.exception, error)
        self.assertEqual(resource.calls, [
            ('set', resource.RLIMIT_FSIZE, (MAX_BYTES, MAX_BYTES)),
            ('get', resource.RLIMIT_CPU),
        ])

    def test_cpu_set_failure_propagates_without_retry_or_gmsh_boundary(self):
        error = ValueError('injected CPU set failure')
        resource = FakeResource((10, 30), fail_at='cpu', error=error)
        with self.assertRaises(ValueError) as caught:
            self.invoke(resource)
        self.assertIs(caught.exception, error)
        self.assertEqual(resource.calls, [
            ('set', resource.RLIMIT_FSIZE, (MAX_BYTES, MAX_BYTES)),
            ('get', resource.RLIMIT_CPU),
            ('set', resource.RLIMIT_CPU, (10, 10)),
        ])

    def test_existing_file_size_failure_propagates_before_cpu_work(self):
        error = OSError('injected file-size set failure')
        resource = FakeResource((10, 30), fail_at='file-size', error=error)
        with self.assertRaises(OSError) as caught:
            self.invoke(resource)
        self.assertIs(caught.exception, error)
        self.assertEqual(resource.calls, [
            ('set', resource.RLIMIT_FSIZE, (MAX_BYTES, MAX_BYTES)),
        ])

    def test_lower_file_size_hard_cap_remains_an_unchanged_limitation(self):
        resource = FakeResource((-1, -1), inherited_fsize=MAX_BYTES-1)
        with self.assertRaisesRegex(ValueError, 'FSIZE set exceeds'):
            self.invoke(resource)
        self.assertEqual(resource.calls, [
            ('set', resource.RLIMIT_FSIZE, (MAX_BYTES, MAX_BYTES)),
        ])

    def test_cpu_policy_is_the_accepted_solver_policy_ast(self):
        module = ast.parse(SOLVER_SOURCE.read_text(), filename=str(SOLVER_SOURCE))
        execute, = (node for node in module.body
                    if isinstance(node, ast.FunctionDef) and node.name == '_execute')
        limits, = (node for node in execute.body
                   if isinstance(node, ast.FunctionDef) and node.name == 'limits')
        prefix = worker_prefix()
        self.assertEqual(len(prefix), 5)
        self.assertEqual(ast.dump(prefix[0]), ast.dump(ast.parse('import resource').body[0]))
        self.assertEqual([ast.dump(node) for node in prefix[2:]],
                         [ast.dump(node) for node in limits.body[1:]])


if __name__ == '__main__':
    unittest.main()
