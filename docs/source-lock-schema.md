# Source-lock manifest v1

The document is UTF-8 JSON and must contain exactly these fields:

- `schema`: exactly `opendot.source-lock.v1`
- `modules`: a nonempty ordered array, maximum 32 entries
- `exports`: a nonempty object, maximum 64 named bindings

Each module object contains exactly `name`, `path`, and `sha256`.

- `name` is a single ASCII Python identifier, beginning with a letter, at most
  80 characters, with letters, numbers and underscores only; keywords fail
- `path` is a POSIX relative path within the approved root; no absolute path,
  empty segment, dot segment, parent segment, backslash, colon, C0/DEL/C1 control
  character or Unicode surrogate code point
- The path ends in `.py` and its basename cannot be `__init__.py`
- `sha256` is exactly 64 lowercase hexadecimal characters
- Names and paths cannot repeat, even if their contents have the same digest

Each export name obeys the same identifier rule. Its value contains exactly:

- `module`: one of the explicitly listed module names
- `attribute`: a single identifier present in that module's own dictionary

The attribute is returned unchanged. There are no inferred roles, type guesses,
behavioral checks, dotted lookups or synthesized wrappers. A module-level dynamic
`__getattr__` cannot fabricate a missing export. Alias names do not demonstrate
compatibility with any consuming application.

Limits are 64 KiB for the manifest, 1 MiB for each module, 8 MiB for total module
bytes, 2,048 JSON nodes, depth 8 and 1,024 characters for each JSON string. JSON
object keys count as nodes. Duplicate keys anywhere, nonfinite constants, and
float literals overflowing to infinity fail. Numeric fields are not part of this
schema. Wrong types, unknown fields and unknown schema values fail closed.

The approved root must also be Unicode-scalar text without C0/DEL/C1 controls;
POSIX surrogateescape root names are explicitly unsupported and rejected during
configuration validation. Ordinary non-ASCII Unicode scalar paths are supported.
The manifest path is relative to the same approved root. There is no embedded
root, default repository, default source revision, or built-in source pin. The
operator supplies the exact manifest SHA-256 separately. The document makes no
claim that hashes imply membership in a source-control commit.

## Import semantics

List dependencies before consumers. Within listed code, `from .helper import
value` works when `helper` was loaded earlier. A later function can import an
already loaded listed sibling. Forward imports during initialization fail;
subpackages and package resource discovery are unsupported. The source's original
package name is never registered, and its initializer is never run by this adapter.
Absolute imports are not isolated. Import hooks and namespace mutation by loaded
code are outside the trusted, cooperative execution model.

Every module is precompiled from its captured bytes with `dont_inherit=True`, so
compiler flags from the adapter are not implicitly applied. Python syntax and
execution errors propagate unchanged; they are not safe public error receipts.
Errors from admission validation use bounded codes via `SourceAdmissionError`,
which is an alias of the existing source-audit owner's exception type.

## Related contracts

See [the source-admission API](source-admission.md) for configuration, namespace
cleanup, retry limits, and the trust boundary. [Attribution](PROVENANCE.md) records
the retained Apache integration and shared helper ownership.
