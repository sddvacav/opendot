"""Public synthetic CAS demonstration; creates a new, disposable output tree."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from opendot_engineering import __version__
from opendot_engineering.core import ArtifactIntegrityError, ArtifactStore


def demonstrate(output: Path) -> dict:
    # Refuse reuse so the deliberately damaged sample cannot affect an old store.
    # This is ordinary trusted local filesystem work, not symlink-safe admission.
    output.mkdir(parents=False, exist_ok=False, mode=0o700)
    store = ArtifactStore(output / "cas")
    payload = b'{"kind":"synthetic","value":7}\n'
    ref = store.put_bytes(
        payload,
        mime_type="application/json",
        producer="public-synthetic-example",
        task_id="artifact-roundtrip",
        source_refs=("synthetic:public-example",),
    )
    retrieved = store.get_bytes(ref)
    checks = {
        "roundtrip_matches": retrieved == payload,
        "independent_sha256_matches": ref.sha256 == hashlib.sha256(payload).hexdigest(),
        "reference_verified": store.verify(ref),
        "identifier_verified": store.verify_id(ref.artifact_id),
        "repeat_put_same_id": store.put_bytes(payload).artifact_id == ref.artifact_id,
    }

    # Damage a separate disposable synthetic object, never the successful result.
    damaged = store.put_bytes(b"synthetic corruption target")
    damaged_path = store.objects / damaged.sha256[:2] / damaged.sha256[2:]
    damaged_path.chmod(0o600)
    damaged_path.write_bytes(b"deliberately different synthetic bytes")
    try:
        store.get_bytes(damaged)
    except ArtifactIntegrityError:
        checks["corrupt_read_rejected"] = True
    else:
        checks["corrupt_read_rejected"] = False
    checks["corrupt_reference_not_verified"] = not store.verify(damaged)
    checks["corrupt_identifier_not_verified"] = not store.verify_id(damaged.artifact_id)
    try:
        store.put_bytes(b"synthetic corruption target")
    except ArtifactIntegrityError:
        checks["corrupt_reuse_rejected"] = True
    else:
        checks["corrupt_reuse_rejected"] = False

    return {
        "package_version": __version__,
        "scenario": "PUBLIC_SYNTHETIC_LOCAL_CAS",
        "passed": all(checks.values()),
        "checks": checks,
        "artifact": asdict(ref),
        "scientific_accepted": False,
        "device_control_authorized": False,
        "consumer_migration_status": "NOT_EVALUATED",
        "durable_recovery_status": "NOT_EVALUATED",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True,
                        help="new directory under a trusted existing parent; must not exist")
    args = parser.parse_args()
    # Check before effects; later storage failures must retain their own errors.
    if args.output.exists() or args.output.is_symlink():
        parser.error(f"--output already exists: {args.output}; choose a fresh path")
    report = demonstrate(args.output)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
