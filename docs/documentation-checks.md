# Offline documentation consistency checks

The source-only [checker](../ci/check_docs.py) finds broken local inline links,
missing heading fragments, and command drift between the English and Chinese
installed quickstarts. It reads public checkout bytes and returns JSON; it does
not open websites, execute links or code blocks, start a runtime, or call models,
providers, native backends, or devices. It adds no package dependency or runtime
owner. A passing result is bounded consistency evidence, not execution of the
quickstart, source truth, scientific acceptance, or a hosted-CI success claim.

## Run against a trusted source checkout

Use Python 3.12+ from the reviewed checkout root, with its public source admitted
explicitly. The existing source-audit helpers supply bounded regular-file reads
and descriptor-relative no-follow path handling; they are reused unchanged.

```sh
PYTHONPATH=src python -B ci/check_docs.py --root .
```

The root defaults to the current directory. Exit status is 0 for acceptance and
1 for check failure. Invalid CLI arguments use argparse's ordinary status 2.
Stdout is one JSON object with schema `opendot.documentation-checks.v1`, boolean
`accepted`, `counts`, and a `failures` array. No receipt file is created; redirect
stdout outside the source tree when retaining evidence.

Counts are `markdown_files` successfully read, `local_links` considered,
`remote_links_skipped`, `heading_fragments` checked after an available local
target, `sh_blocks_en`, `sh_blocks_zh`, and `failures`. Counts on rejection may be
partial and are never an acceptance claim. Each failure has a stable `code`, a
root-relative source `path`, and `line` (1-based, or 0 for a file/tree error).
Command mismatches also give the 1-based `block` number. Failures are sorted by
path, line, and code. Targets, command contents, external paths, and raw OS error
messages are not echoed. Tree-wide errors use `.` as the path.

## Deliberately supported Markdown subset

- Scan UTF-8 files ending in `.md`, recursively within the supplied root. Ignore
  `.git`, `.hg`, `.svn`, `.venv`, `venv`, `__pycache__`, `.pytest_cache`, `build`,
  and `dist` directory names; links into those names are refused as well
- Check same-line inline links and images with flat labels: `[label](path)` and
  `![label](path)`. Destinations can be bare (no whitespace or parentheses) or
  angle-bracketed, including spaces. An optional single- or double-quoted title
  is accepted. Paths use `/`, relative to the source document's directory;
  `.` and `..` are normalized without ever allowing traversal above the root
- Check `#fragment` in the same document or `other.md#fragment`. An empty
  fragment means the top of the document. Nonempty fragments on other file
  types fail. Local query strings, `file:` URLs, absolute paths, backslashes,
  malformed percent escapes, control characters, and nested percent escapes
  fail. Decode UTF-8 percent escapes once before checking paths and fragments
- For ATX headings with one to six `#` markers and following whitespace, trim
  optional closing hashes, lowercase, retain Unicode letters/marks/numbers and
  hyphens/underscores, discard other punctuation, and replace each space or tab
  with `-`. Thus `# Hello world!` gives `hello-world`; backticks around inline
  code disappear. Repeated IDs get the next unused `-1`, `-2`, etc. suffix
- Also recognize explicit HTML `id` attributes and legacy `name` attributes on
  `a` elements, using the standard library's `HTMLParser`. Declarations must be
  complete same-line start tags. Attribute values are case-sensitive, nonempty,
  at most 1,024 characters, and contain no whitespace/control characters;
  duplicate attributes are not accepted as declarations. HTML character
  references in attribute values are decoded. HTML is never rendered or
  executed. Comment contents, escaped HTML text, script/style contents, and
  the code examples excluded below do not create explicit anchors. Explicit
  IDs do not alter the numbering of duplicate Markdown heading IDs. Unsupported
  HTML declarations rejected by the parser yield `HTML_SYNTAX_UNSUPPORTED`
- Ignore fenced code using at least three backticks or tildes, with up to three
  leading spaces. Closing fences must use the same character and at least the
  opening length, without other text. An unclosed fence fails. Ignore matched
  same-line backtick code spans, four-space/tab-indented example lines, and
  escaped opening brackets. Link examples in code do not become real links;
  headings inside code do not become fragment targets
- Skip protocol-relative `//host/path` destinations and scheme-prefixed URLs
  other than `file:` without DNS or network requests. This does not validate
  their safety, syntax, availability, redirects, or remote fragments

This is not a complete CommonMark or GitHub renderer. Reference-style links,
autolinks, raw HTML links, multiline HTML anchor declarations, multiline or
nested link syntax, setext headings, heading HTML entities, and complex heading
markup are outside the supported subset. Unsupported recognizable inline destinations fail rather than being
treated as checked. Use the supported subset for navigation that CI must check.

## Exact bilingual command parity

Compare every ordered, closed fenced block whose info string is exactly `sh` in
[English](installed-quickstart.md) and [简体中文](installed-quickstart.zh-CN.md).
The reviewed current-guide profile requires exactly eight blocks in each
language. The check rejects missing or whitespace-only blocks, compares counts,
and compares literal body text including whitespace, newlines, and ordering.
It does not normalize commands or execute them. Fence markers and surrounding
translated prose are not compared. Example `sh` fences nested inside a larger
fenced Markdown example are ignored. Joint deletion of the same step in both
languages fails the eight-block profile. A future journey change requires a
reviewed update to `EXPECTED_SH_BLOCKS` and its regression fixtures, as well as
the guides. This is a deliberate contract for these two guides, not a generic
guide parser. Semantic correctness still requires review and a separate
execution check; the helper cannot detect identical wrong commands or missing
prose.

## Filesystem and resource limits

The root and its ancestors must be trusted and caller-controlled. Symlinks in
the root path or scanned tree are refused, including dangling and directory
symlinks. Source-audit no-follow reads reject linked symlinks, nonregular files,
unavailable inputs, and files over 2 MiB. No outside-root content is read through
links. The same limit applies to local non-Markdown targets, which are read only
to establish bounded regular-file availability, never executed or imported.

Limits are 4,096 visited entries, 256 Markdown documents, 16 directory levels,
4,096 considered links, and 16 MiB total input bytes. Any limit violation fails;
there is no successful truncation. This helper uses the existing POSIX
descriptor/no-follow requirements and fails on unsupported hosts. Linux checks
do not establish broader platform support. It makes no hostile-concurrent-
mutation, OS sandbox, or atomic-snapshot claim. Keep generated outputs outside
the checkout and run with `-B` to avoid source bytecode caches.

The [finite regression fixtures](../tests/test_documentation_checks.py) include
missing files/headings, traversal and encoded traversal, symlinks, command
drift/missing/empty blocks, literal example handling, resource caps, deterministic
JSON, and the current docs. They are source checks; installed-wheel checks and
the wider portable/native selections remain separate.
