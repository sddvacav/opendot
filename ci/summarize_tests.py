"""Report JUnit evidence without converting optional skips into acceptance."""
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


def summarize(path: Path) -> str:
    if not path.is_file():
        return 'No test receipt was produced. Portable checks are NOT VERIFIED.\n'
    root = ET.parse(path).getroot()
    cases = list(root.iter('testcase'))
    failed = sum(case.find('failure') is not None for case in cases)
    errors = sum(case.find('error') is not None for case in cases)
    skipped = sum(case.find('skipped') is not None for case in cases)
    passed = sum(all(case.find(tag) is None for tag in ('failure', 'error', 'skipped')) for case in cases)
    return (f'Portable checks: {passed} passed, {failed} failed, {errors} errors, {skipped} skipped.\n\n'
            'Optional licensed-source, CAD, mesh and solver checks require explicit environments. '
            'Skipped checks do not verify those capabilities. This job does not prove live-model, '
            'multi-host, physical-experiment or full-platform acceptance.\n')


if __name__ == '__main__':
    print(summarize(Path(sys.argv[1])), end='')
