import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('ci_summary', Path(__file__).parents[1] / 'ci' / 'summarize_tests.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_counts_actual_cases_without_double_counting_nested_suites(tmp_path):
    receipt = tmp_path / 'tests.xml'
    receipt.write_text('<testsuites><testsuite tests="99"><testsuite><testcase/>'
                       '<testcase><skipped/></testcase><testcase><failure/></testcase>'
                       '<testcase><error/></testcase></testsuite></testsuite></testsuites>')
    result = module.summarize(receipt)
    assert '1 passed, 1 failed, 1 errors, 1 skipped' in result
    assert 'Skipped checks do not verify' in result


def test_missing_receipt_is_not_success(tmp_path):
    assert 'NOT VERIFIED' in module.summarize(tmp_path / 'absent.xml')
