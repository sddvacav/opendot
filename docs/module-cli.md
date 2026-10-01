# Package help and version

With a reviewed `opendot-engineering` package installed in your Python 3.12+
interpreter, run:

```sh
python -I -B -m opendot_engineering
python -I -B -m opendot_engineering --help
python -I -B -m opendot_engineering --version
```

No arguments, `--help`, and `-h` print the same usage and exit zero. `--version`
prints `opendot-engineering` followed by the imported package's `__version__`,
then exits zero. It does not query distribution metadata, a registry, or a network
service. Unknown arguments, abbreviated long options, and combining help with
version exit 2 with a usage error on stderr. There are no root subcommands or
registered `opendot` / `odot` console commands.

The help lists the actual Python API paths for local artifact storage,
descriptive agent metadata, callable-only execution, controlled Git workspaces,
and explicit source admission. It also points to the existing, separately
invoked adapter and CAD/CAE module entrypoints. To inspect one module's own
options, for example:

```sh
python -I -B -m opendot_engineering.adapters.source_audit --help
```

The package-root entrypoint is static guidance only. It does not import those
APIs or optional backends, inspect user files, print environment or installation
paths, create output directories, dispatch tools, start a runtime, or call a
model or network service. Python still loads its interpreter and package files;
`-B` prevents bytecode cache writes. Actual adapter execution retains its own
input, dependency, trust, and scientific-acceptance boundaries. See the
[architecture](architecture.md) and [installed quickstart](installed-quickstart.md).

## Source checkout and focused checks

From the reviewed source root, the equivalent developer-only invocation is:

```sh
PYTHONPATH=src python -B -m opendot_engineering --help
```

That is a source import, not an installed-wheel check. For the focused source
tests, explicitly admit the public source directory to the isolated children:

```sh
CLI_TEST_PARENT=$(mktemp -d /tmp/opendot-cli-tests.XXXXXX)
OPENDOT_TEST_SOURCE_ROOT="$PWD/src" PYTHONPATH=src python -B -m pytest \
  -p no:cacheprovider tests/test_module_cli.py --basetemp "$CLI_TEST_PARENT/session"
```

Choose a fresh temporary test directory outside the checkout. For installed
checks, copy `tests/test_module_cli.py` outside the source tree, leave
`OPENDOT_TEST_SOURCE_ROOT` unset, and use the wheel's interpreter with separately
prepared pytest tooling. Without explicit source admission the subprocesses use
`python -I -B -m opendot_engineering`; they do not fall back to a checkout. Source
and installed checks are separate evidence and neither establishes release
acceptance, a sandbox, or autonomous agent orchestration.
