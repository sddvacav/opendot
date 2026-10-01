# Hash-pinned CI test tooling

The [CI test lock](../ci/requirements.txt) selects the existing five versions:
pytest 9.1.1, iniconfig 2.3.0, packaging 26.3, pluggy 1.6.0 and Pygments 2.21.0.
Each line admits one SHA-256-pinned official PyPI `py3-none-any` wheel. Versions
were not upgraded. These are test tools, not OpenDot runtime dependencies.

The reviewed dependency closure is **CPython 3.12 on Linux, with no extras**.
Under those markers, pytest requires the other four packages; those packages
have no further active dependencies. Windows colorama, Python <3.11 helpers,
development extras and other profiles are outside the lock. Universal wheel
tags do not establish that the dependency closure works on every platform.

Hashes were obtained from the official version-specific PyPI metadata for
[pytest](https://pypi.org/pypi/pytest/9.1.1/json),
[iniconfig](https://pypi.org/pypi/iniconfig/2.3.0/json),
[packaging](https://pypi.org/pypi/packaging/26.3/json),
[pluggy](https://pypi.org/pypi/pluggy/1.6.0/json) and
[Pygments](https://pypi.org/pypi/Pygments/2.21.0/json).
Version metadata, sizes, hashes, wheel METADATA/RECORD and the active dependency
graph must be checked again when deliberately updating the lock. A matching
hash proves consistency with the reviewed artifact, not trustworthy authorship,
absence of vulnerabilities, legal clearance or a complete system SBOM.

## Acquire wheels with hash checks

Run from the checkout in the selected Python 3.12/Linux environment. Keep all
generated wheels, environments and test artifacts outside the source tree. The
following uses a new trusted external temporary directory; keep its variables in
the same shell for both steps. Do not choose a directory inside the checkout.
The five selected archives total 1,794,661 bytes; the review download budget is
50 MiB. A pre-existing cached wheel can be reused only after it matches the
official filename, size and SHA-256. Do not fall back to a source distribution,
another version, an unreviewed mirror or a disabled TLS check.

```sh
CI_TOOLCHAIN_ROOT="$(mktemp -d /tmp/opendot-ci-toolchain.XXXXXX)"
CI_WHEELHOUSE="$CI_TOOLCHAIN_ROOT/wheelhouse"
CI_TEST_VENV="$CI_TOOLCHAIN_ROOT/venv"
mkdir "$CI_WHEELHOUSE"
PIP_CONFIG_FILE=/dev/null python -B -m pip --isolated download \
  --disable-pip-version-check --no-cache-dir --require-hashes \
  --only-binary=:all: --index-url https://pypi.org/simple \
  --dest "$CI_WHEELHOUSE" -r ci/requirements.txt
```

The portable workflow uses the same hash and wheel-only restrictions for its
online test-tool installation. Hash mode requires all active dependencies to be
exactly pinned and hashed. Dependency resolution remains enabled; `--no-deps`
would hide a missing dependency and must not be used to validate this closure.

## Install offline in a clean environment

The following creates a separate venv without pip or system-site-packages, then
uses the existing host pip solely as installer. Its interpreter/pip/stdlib and
host libraries are bootstrap prerequisites outside the five-wheel lock. Use a
known existing pip that supports `--python` and record its version separately.
The verification profile records the concrete bootstrap identities; it does not
install or upgrade bootstrap packages or claim hermetic completeness.

```sh
python -B -m venv --without-pip "$CI_TEST_VENV"
PIP_CONFIG_FILE=/dev/null python -B -m pip --isolated \
  --python "$CI_TEST_VENV/bin/python" install \
  --disable-pip-version-check --no-index --find-links "$CI_WHEELHOUSE" \
  --no-cache-dir --no-compile --require-hashes --only-binary=:all: \
  -r ci/requirements.txt
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  "$CI_TEST_VENV/bin/python" -B -m pytest -q -p no:cacheprovider \
  --basetemp "$CI_TOOLCHAIN_ROOT/pytest-temp" tests/test_ci_toolchain_lock.py
```

All five archives must be present and intact. In a fresh empty target, a missing
hash, wrong hash, altered wheel, unavailable dependency or missing wheel must
fail rather than use an index, source archive, already installed package or
unpinned fallback. Refusal is not an installation rollback or a sandbox claim.
Use new disposable targets for each refusal control and record exit statuses.

## Boundaries

The lock does not cover the interpreter, bootstrap pip, standard library,
GitHub-hosted runner image, action implementations, optional simulation/native
profiles or the separately pinned build backend. The source package's default
external Python dependency list remains empty. No GitHub run, native solver,
model, physical device, public release or new quality score is established by a
local locked installation. Keep local and hosted CI evidence separate.
