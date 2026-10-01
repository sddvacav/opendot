"""Fake-only tests of the existing child callback; never import or launch a solver.

Only the nested ``thermal_conduction._execute.limits`` function is compiled from
the public source AST. No real resource calls, module initialization, subprocess
creation, provider calls, or kernel CPU-limit behavior are exercised here.
"""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


SOURCE = (Path(__file__).resolve().parents[1] / 'src' / 'opendot_engineering'
          / 'executors' / 'thermal_conduction.py')
MAX_BYTES = 32 * 1024 * 1024


class FakeResource:
    RLIMIT_FSIZE = 'file-size'
    RLIMIT_CPU = 'cpu'

    def __init__(self, inherited, *, infinity=-1, fail_at=None, error=None):
        self.inherited = inherited
        self.RLIM_INFINITY = infinity
        self.fail_at = fail_at
        self.error = error
        self.calls = []

    def getrlimit(self, which):
        self.calls.append(('get', which))
        if which != self.RLIMIT_CPU:
            raise AssertionError('Only inherited CPU limits may be queried')
        if self.fail_at == 'get':
            raise self.error
        return self.inherited

    def setrlimit(self, which, limits):
        self.calls.append(('set', which, limits))
        if self.fail_at == which:
            raise self.error
        if which == self.RLIMIT_CPU:
            # Independently refuse every attempted increase before recording success.
            for value in limits:
                for inherited in self.inherited:
                    if inherited != self.RLIM_INFINITY and value > inherited:
                        raise AssertionError('Attempted to raise an inherited CPU cap')


class SolverCpuCeilingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        module = ast.parse(SOURCE.read_text(), filename=str(SOURCE))
        execute, = (node for node in module.body
                    if isinstance(node, ast.FunctionDef) and node.name == '_execute')
        limits, = (node for node in execute.body
                   if isinstance(node, ast.FunctionDef) and node.name == 'limits')
        cls.callback_code = compile(ast.Module(body=[limits], type_ignores=[]),
                                    str(SOURCE), 'exec')

    def invoke(self, resource, *, timeout=60):
        namespace = {'resource': resource,
                     'gmsh_mesh': SimpleNamespace(MAX_BYTES=MAX_BYTES),
                     'timeout': timeout}
        exec(self.callback_code, namespace)
        namespace['limits']()

    def check_limits(self, inherited, expected, *, infinity=-1, timeout=60):
        resource = FakeResource(inherited, infinity=infinity)
        self.invoke(resource, timeout=timeout)
        self.assertEqual(resource.calls, [
            ('set', resource.RLIMIT_FSIZE, (MAX_BYTES, MAX_BYTES)),
            ('get', resource.RLIMIT_CPU),
            ('set', resource.RLIMIT_CPU, (expected, expected)),
        ])

    def test_both_unlimited_use_existing_300_second_cap(self):
        self.check_limits((-1, -1), 300)

    def test_lower_hard_cap_is_never_raised(self):
        self.check_limits((30, 30), 30)

    def test_lower_soft_cap_is_never_raised(self):
        self.check_limits((10, 30), 10)

    def test_unlimited_soft_does_not_hide_finite_hard(self):
        # A defensive synthetic pair, not a claimed valid kernel configuration.
        self.check_limits((-1, 30), 30)

    def test_unlimited_hard_does_not_hide_finite_soft(self):
        self.check_limits((10, -1), 10)

    def test_zero_soft_remains_numerically_zero(self):
        self.check_limits((0, 30), 0)

    def test_zero_hard_remains_numerically_zero(self):
        # Defensive synthetic input; no zero-duration kernel guarantee is implied.
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
                ((infinity, infinity), 300),
                ((infinity, 30), 30),
                ((10, infinity), 10),
                ((0, infinity), 0),
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

    def test_wall_timeout_does_not_change_cpu_budget(self):
        for timeout in (.05, 1, 30, 60, 300):
            with self.subTest(timeout=timeout):
                self.check_limits((-1, -1), 300, timeout=timeout)
                self.check_limits((10, 30), 10, timeout=timeout)

    def test_get_failure_propagates_without_cpu_set_or_fallback(self):
        error = OSError('injected CPU get failure')
        resource = FakeResource((10, 30), fail_at='get', error=error)
        with self.assertRaises(OSError) as caught:
            self.invoke(resource)
        self.assertIs(caught.exception, error)
        self.assertEqual(resource.calls, [
            ('set', resource.RLIMIT_FSIZE, (MAX_BYTES, MAX_BYTES)),
            ('get', resource.RLIMIT_CPU),
        ])

    def test_cpu_set_failure_propagates_without_retry_or_fallback(self):
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


if __name__ == '__main__':
    unittest.main()
