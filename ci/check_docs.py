"""Bounded offline documentation consistency checks; see docs/documentation-checks.md."""
from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import unicodedata
from urllib.parse import unquote

from opendot_engineering.adapters import source_audit as audit


SCHEMA = "opendot.documentation-checks.v1"
QUICKSTARTS = ("docs/installed-quickstart.md", "docs/installed-quickstart.zh-CN.md")
EXPECTED_SH_BLOCKS = 8
EXCLUDED_DIRECTORIES = frozenset({".git", ".hg", ".svn", ".venv", "venv",
                                  "__pycache__", ".pytest_cache", "build", "dist"})
MAX_ENTRIES = 4096
MAX_DOCUMENTS = 256
MAX_DEPTH = 16
MAX_LINKS = 4096
MAX_TOTAL_BYTES = 16 * 1024 * 1024
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})([^\r\n]*)\r?\n?$")
HEADING = re.compile(r"^ {0,3}#{1,6}[ \t]+(.+?)\s*$")
LINK = re.compile(r"(?<!\\)\[([^\[\]\n]*)\]\(([^)\n]*)\)")
DESTINATION = re.compile(r'''(?:<([^<>]+)>|([^\s<>]+))(?:[ \t]+(?:"[^"\n]*"|'[^'\n]*'))?''')
SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def _failure(failures, code, path, line=0, **details):
    failures.append({"code": code, "path": path, "line": line, **details})


def _markdown_paths(root_fd):
    """List only within the already opened root; never follow directory symlinks."""
    paths = []
    entries = 0

    def visit(fd, prefix, depth):
        nonlocal entries
        audit._require(depth <= MAX_DEPTH, "TREE_TOO_DEEP")
        # scandir is consumed with a hard cap before sorting: no unbounded listdir.
        names = []
        with os.scandir(fd) as directory:
            for entry in directory:
                entries += 1
                audit._require(entries <= MAX_ENTRIES, "TOO_MANY_ENTRIES")
                names.append(entry.name)
        for name in sorted(names):
            if name in EXCLUDED_DIRECTORIES:
                continue
            relative = f"{prefix}/{name}" if prefix else name
            audit._relative(relative)
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            audit._require(not stat.S_ISLNK(info.st_mode), "SYMLINK_IN_TREE")
            if stat.S_ISDIR(info.st_mode):
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                try:
                    visit(child, relative, depth + 1)
                finally:
                    os.close(child)
            elif name.endswith(".md"):
                audit._require(stat.S_ISREG(info.st_mode), "NOT_REGULAR_FILE")
                paths.append(relative)
                audit._require(len(paths) <= MAX_DOCUMENTS, "TOO_MANY_DOCUMENTS")

    visit(root_fd, "", 0)
    return sorted(paths)


def _without_inline_code(line):
    """Mask matched backtick runs, retaining offsets and all other characters."""
    result = list(line)
    runs = list(re.finditer(r"`+", line))
    index = 0
    while index < len(runs):
        start = runs[index]
        end_index = next((i for i in range(index + 1, len(runs))
                          if runs[i].group() == start.group()), None)
        if end_index is None:
            index += 1
            continue
        end = runs[end_index]
        result[start.start():end.end()] = " " * (end.end() - start.start())
        index = end_index + 1
    return "".join(result)


def _slug(heading):
    # A deliberately small, specified heading convention, not a Markdown renderer.
    heading = re.sub(r"[ \t]+#+[ \t]*$", "", heading).strip().lower()
    return "".join("-" if char in " \t" else char for char in heading
                   if char in "-_ \t" or unicodedata.category(char)[0] in "LNM")


class _ExplicitAnchors(HTMLParser):
    """Read complete same-line HTML anchor declarations; never render HTML."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.anchors = set()

    def feed(self, data):
        try:
            super().feed(data)
        except AssertionError:
            raise audit.AuditRejected("HTML_SYNTAX_UNSUPPORTED") from None

    def close(self):
        try:
            super().close()
        except AssertionError:
            raise audit.AuditRejected("HTML_SYNTAX_UNSUPPORTED") from None

    def handle_starttag(self, tag, attrs):
        # Avoid synthesizing a declaration across excluded code/example lines.
        if any(char in self.get_starttag_text() for char in "\r\n"):
            return
        for key in (("id", "name") if tag == "a" else ("id",)):
            values = [value for name, value in attrs if name == key]
            if len(values) != 1:
                continue
            value = values[0]
            if (value and len(value) <= 1024
                    and not any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value)):
                self.anchors.add(value)


def _parse(text, path, failures):
    links, headings, blocks = [], set(), []
    explicit = _ExplicitAnchors()
    fence, info, body, opened_at = None, "", [], 0
    for number, line in enumerate(text.splitlines(keepends=True), 1):
        match = FENCE.match(line)
        if fence is not None:
            explicit.feed("\n")
            if (match and match[1][0] == fence[0] and len(match[1]) >= len(fence)
                    and not match[2].strip()):
                if info == "sh":
                    blocks.append((opened_at, "".join(body)))
                fence = None
            else:
                body.append(line)
            continue
        if match and (match[1][0] != "`" or "`" not in match[2]):
            explicit.feed("\n")
            fence, info, body, opened_at = match[1], match[2].strip(), [], number
            continue
        # Four-space/tab indented examples are excluded along with fenced examples.
        if line.startswith(("    ", "\t")):
            explicit.feed("\n")
            continue
        if heading := HEADING.match(line):
            base = _slug(heading[1])
            anchor, suffix = base, 0
            while anchor in headings:
                suffix += 1
                anchor = f"{base}-{suffix}"
            headings.add(anchor)
        visible = _without_inline_code(line)
        explicit.feed(visible)
        for link in LINK.finditer(visible):
            links.append((number, link[2]))
            audit._require(len(links) <= MAX_LINKS, "TOO_MANY_LINKS")
    if fence is not None:
        _failure(failures, "UNCLOSED_FENCE", path, opened_at)
    explicit.close()
    return links, headings | explicit.anchors, blocks


def _decoded(value):
    audit._require(re.search(r"%(?![0-9A-Fa-f]{2})", value) is None, "INVALID_PERCENT_ESCAPE")
    try:
        decoded = unquote(value, encoding="utf-8", errors="strict")
    except UnicodeError:
        raise audit.AuditRejected("INVALID_PERCENT_ESCAPE") from None
    # A second decoding pass must never change interpretation.
    audit._require("%" not in decoded, "NESTED_PERCENT_ESCAPE")
    audit._require(not any(ord(char) < 32 or ord(char) == 127 for char in decoded),
                   "INVALID_LOCAL_PATH")
    return decoded


def _target(source, destination):
    path, separator, fragment = destination.partition("#")
    path, fragment = _decoded(path), _decoded(fragment)
    audit._require("?" not in path, "LOCAL_QUERY_UNSUPPORTED")
    audit._require(not path.startswith("/") and "\\" not in path and ":" not in path,
                   "INVALID_LOCAL_PATH")
    if not path:
        return source, fragment if separator else None
    parts = list(PurePosixPath(source).parent.parts)
    for part in path.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            audit._require(bool(parts), "PATH_ESCAPE")
            parts.pop()
        else:
            parts.append(part)
    target = "/".join(parts)
    audit._relative(target)
    audit._require(not any(part in EXCLUDED_DIRECTORIES for part in parts), "EXCLUDED_TARGET")
    return target, fragment if separator else None


def check_documentation(root):
    """Return one deterministic JSON-ready receipt. Never execute linked content."""
    counts = dict(markdown_files=0, local_links=0, remote_links_skipped=0,
                  heading_fragments=0, sh_blocks_en=0, sh_blocks_zh=0, failures=0)
    failures, documents, parsed, total_bytes = [], {}, {}, 0
    root_fd = None

    def read(relative):
        nonlocal total_bytes
        remaining = MAX_TOTAL_BYTES - total_bytes
        audit._require(remaining > 0, "TOTAL_INPUT_TOO_LARGE")
        try:
            data = audit._read(root_fd, relative, min(remaining, audit.MAX_SOURCE_BYTES))
        except audit.AuditRejected as exc:
            if exc.code == "INPUT_TOO_LARGE" and remaining < audit.MAX_SOURCE_BYTES:
                raise audit.AuditRejected("TOTAL_INPUT_TOO_LARGE") from None
            raise
        total_bytes += len(data)
        return data

    try:
        root_fd = audit._root_fd(root)
        paths = _markdown_paths(root_fd)
        audit._require(bool(paths), "NO_MARKDOWN_FILES")
        for path in paths:
            try:
                documents[path] = read(path).decode("utf-8")
                parsed[path] = _parse(documents[path], path, failures)
                counts["markdown_files"] += 1
            except (audit.AuditRejected, UnicodeError) as exc:
                _failure(failures, getattr(exc, "code", "INVALID_UTF8"), path)
        checked_files = set(documents)
        for source, (links, _, _) in parsed.items():
            for line, raw in links:
                audit._require(counts["local_links"] + counts["remote_links_skipped"] < MAX_LINKS,
                               "TOO_MANY_LINKS")
                match = DESTINATION.fullmatch(raw.strip())
                if match is None:
                    counts["local_links"] += 1
                    _failure(failures, "LINK_SYNTAX_UNSUPPORTED", source, line)
                    continue
                destination = match[1] or match[2]
                if destination.startswith("//") or (SCHEME.match(destination)
                                                        and not destination.lower().startswith("file:")):
                    counts["remote_links_skipped"] += 1
                    continue
                counts["local_links"] += 1
                try:
                    audit._require("(" not in destination, "LINK_SYNTAX_UNSUPPORTED")
                    target, fragment = _target(source, destination)
                    if target not in checked_files:
                        read(target)
                        checked_files.add(target)
                    if fragment is not None and fragment:
                        counts["heading_fragments"] += 1
                        audit._require(target.endswith(".md"), "FRAGMENT_ON_NON_MARKDOWN")
                        audit._require(target in parsed, "MARKDOWN_NOT_CHECKED")
                        audit._require(fragment in parsed[target][1], "HEADING_NOT_FOUND")
                except audit.AuditRejected as exc:
                    _failure(failures, exc.code, source, line)
        bilingual = []
        for path, key in zip(QUICKSTARTS, ("sh_blocks_en", "sh_blocks_zh")):
            if path not in parsed:
                _failure(failures, "QUICKSTART_UNAVAILABLE", path)
                bilingual.append([])
                continue
            blocks = parsed[path][2]
            counts[key] = len(blocks)
            bilingual.append(blocks)
            if not blocks:
                _failure(failures, "SH_BLOCKS_MISSING", path)
            if len(blocks) != EXPECTED_SH_BLOCKS:
                _failure(failures, "SH_BLOCK_PROFILE_COUNT", path,
                         expected=EXPECTED_SH_BLOCKS, actual=len(blocks))
            for index, (line, body) in enumerate(blocks, 1):
                if not body.strip():
                    _failure(failures, "EMPTY_SH_BLOCK", path, line, block=index)
        english, chinese = bilingual
        if len(english) != len(chinese):
            _failure(failures, "SH_BLOCK_COUNT_MISMATCH", QUICKSTARTS[1])
        for index, (left, right) in enumerate(zip(english, chinese), 1):
            if left[1] != right[1]:
                _failure(failures, "SH_BLOCK_MISMATCH", QUICKSTARTS[1], right[0], block=index)
    except (audit.AuditRejected, OSError) as exc:
        _failure(failures, getattr(exc, "code", "TREE_UNAVAILABLE_OR_UNSAFE"), ".")
    finally:
        if root_fd is not None:
            os.close(root_fd)
    failures.sort(key=lambda row: (row["path"], row["line"], row["code"]))
    counts["failures"] = len(failures)
    return {"schema": SCHEMA, "accepted": not failures, "counts": counts, "failures": failures}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."), help="trusted source checkout (default: .)")
    args = parser.parse_args(argv)
    receipt = check_documentation(args.root)
    print(json.dumps(receipt, ensure_ascii=True, sort_keys=True))
    return 0 if receipt["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
