# Pinned build backend

The build declaration selects setuptools 84.0.0. The optional controlled
[backend requirements](../ci/build-toolchain-requirements.txt) additionally pin
the official wheel SHA-256:
`51a52592b3b99e102b609654876bd65f19f999935166d1352678931132b0c670`.

[Official PyPI metadata](https://pypi.org/project/setuptools/84.0.0/) was checked
on 1 October 2026: release date 8 August 2026, MIT license, Python >=3.10.
This is a build dependency; it is not bundled into the OpenDot runtime wheel.
The ordinary PEP 517 declaration pins a version, not the acquisition origin or
wheel bytes; use the hash-pinned requirements and an independently reviewed
wheel for controlled offline builds. Never bypass certificate or access errors.

## Recorded predecessor experiment

For source commit `a59419b18a0cf6bd6fd38fb9696dd6e0be5b4289` (0.2.0a3),
two separate initially empty environments and source directories each received
only the hash-verified setuptools wheel, then built offline. Both produced
the exact accepted 88,727-byte wheel with SHA-256
`cc0bcf7a471a56c31bb3db12d175914221b56e4f62500afc4e14640e892b1d11`.
All 342 original installed backend payloads matched the verified wheel.
A corrupted wheel was refused before backend import or installation.

The tested profile used CPython 3.12.14, bootstrap pip 26.2.1, Linux x86_64,
zlib 1.3.2 and `SOURCE_DATE_EPOCH=1790834400`. The delivery profile records
exact interpreter/bootstrap hashes and commands. Its archive SHA-256 is
`5ec2f0abe9715cc5c90cda4ef8401901e91c5f9223f5275b6568a5b79efab61b`;
that historical evidence archive is delivered separately, not bundled here.

This is same-host repeatability in two clean build environments. It is not a
cross-platform result, complete hermetic runtime specification, full SBOM,
vulnerability audit or automatic acceptance of a later source version.
New candidate archives and wheels require fresh identity and build evidence.
