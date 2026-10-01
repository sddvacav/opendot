"""Finite synthetic callable/CAS composition; writes only beneath a new output."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from opendot_engineering import __version__
from opendot_engineering.core import ArtifactRef, ArtifactStore
from opendot_engineering.tool_runtime import ToolRisk, ToolRuntime, ToolSpec


def run_case(root: Path, *, text: str, grant: bool, semantic_pass: bool) -> dict:
    store = ArtifactStore(root)
    written: list[ArtifactRef] = []
    calls = []

    def write_artifact(payload):
        calls.append(1)
        ref = store.put_text(payload['text'], producer='synthetic-callable-example',
                             task_id='local-composition')
        written.append(ref)  # Local observation of an effect, not task acceptance.
        return ref

    runtime = ToolRuntime()
    runtime.register(ToolSpec(
        'write-artifact', '1', 'synthetic-text/v1', 'artifact-ref/v1',
        ToolRisk.REVERSIBLE_WRITE, timeout_s=5.0, max_retries=0,
        idempotent=False, permissions=frozenset({'artifact:write'}),
        semantic_validator=lambda ref: isinstance(ref, ArtifactRef) and semantic_pass,
    ), write_artifact)
    output, receipt = runtime.execute(
        'write-artifact', {'text': text},
        granted_permissions=frozenset({'artifact:write'}) if grant else frozenset(),
    )
    # Inspect effects separately, even when execute returns no result after refusal.
    ref = written[0] if written else None
    stored = store.get_bytes(ref) if ref is not None else None
    return {
        'receipt': {'status': receipt.status, 'semantic_valid': receipt.semantic_valid,
                    'attempts': receipt.attempts, 'error_type': receipt.error_type,
                    'output_hash': receipt.output_hash},
        'handler_calls': len(calls),
        'returned_ref': asdict(output) if output is not None else None,
        'retained_unaccepted_ref': asdict(ref) if ref is not None and output is None else None,
        'cas_verify': store.verify(ref) if ref is not None else None,
        'independent_sha256_matches': (
            hashlib.sha256(stored).hexdigest() == ref.sha256 if ref is not None else None),
        'stored_bytes_match': stored == text.encode('utf-8') if ref is not None else None,
        'stored_object_count': sum(path.is_file() for path in store.objects.rglob('*')),
    }


def demonstrate(output: Path) -> dict:
    # Parent/root must be trusted. This is not symlink-safe admission or a sandbox.
    output.mkdir(parents=False, exist_ok=False, mode=0o700)
    success = run_case(output / 'success', text='synthetic successful output\n',
                       grant=True, semantic_pass=True)
    refused = run_case(output / 'semantic-refusal', text='synthetic unaccepted output\n',
                       grant=True, semantic_pass=False)
    denied = run_case(output / 'permission-refusal', text='must not be written\n',
                      grant=False, semantic_pass=True)
    checks = [
        success['receipt']['status'] == 'COMPLETED', success['receipt']['semantic_valid'],
        success['handler_calls'] == 1, success['returned_ref'] is not None,
        success['cas_verify'], success['independent_sha256_matches'], success['stored_bytes_match'],
        refused['receipt']['status'] == 'FAILED', not refused['receipt']['semantic_valid'],
        refused['handler_calls'] == 1, refused['returned_ref'] is None,
        refused['retained_unaccepted_ref'] is not None, refused['cas_verify'],
        refused['independent_sha256_matches'], refused['stored_bytes_match'],
        denied['receipt']['status'] == 'BLOCKED', denied['receipt']['error_type'] == 'PermissionDenied',
        denied['handler_calls'] == 0, denied['stored_object_count'] == 0,
    ]
    return {'package_version': __version__, 'scope': 'SYNTHETIC_SOFTWARE_EXAMPLE_ONLY',
            'synthetic_software_assertions_passed': all(checks),
            'success': success, 'semantic_refusal': refused, 'permission_refusal': denied,
            'boundary': 'Byte integrity is not task or scientific acceptance; failure does not roll back effects.'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path,
                        help='new directory beneath a trusted existing parent')
    args = parser.parse_args()
    # Check before effects; later storage failures must retain their own errors.
    if args.output.exists() or args.output.is_symlink():
        parser.error(f'--output already exists: {args.output}; choose a fresh path')
    result = demonstrate(args.output)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result['synthetic_software_assertions_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
