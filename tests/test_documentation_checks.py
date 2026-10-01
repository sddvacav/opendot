"""Finite offline fixtures for documentation checks; no linked commands are run."""
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("documentation_checks", ROOT / "ci" / "check_docs.py")
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)


@pytest.fixture
def repository(tmp_path):
    root = tmp_path / "repo"
    (root / "docs").mkdir(parents=True)
    (root / "README.md").write_text("# Welcome\n\n[Guide](docs/guide.md#hello-world)\n", encoding="utf-8")
    (root / "docs/guide.md").write_text("# Hello World\n", encoding="utf-8")
    for path in checks.QUICKSTARTS:
        (root / path).write_bytes(b"# Guide\n\n" + b"```sh\nprintf 'only text, never run'\n```\n" * 8)
    return root


def replace_readme(root, text):
    (root / "README.md").write_text(text, encoding="utf-8")


def failure_codes(receipt):
    assert receipt["accepted"] is False
    assert receipt["counts"]["failures"] == len(receipt["failures"])
    return {row["code"] for row in receipt["failures"]}


def test_current_documentation_passes_with_eight_exact_blocks():
    receipt = checks.check_documentation(ROOT)
    assert receipt["accepted"] is True, receipt
    assert receipt["counts"]["sh_blocks_en"] == receipt["counts"]["sh_blocks_zh"] == 8
    assert receipt["counts"]["local_links"] > 400
    assert receipt["counts"]["heading_fragments"] > 80


def test_small_fixture_counts_and_cli_output_are_stable(repository, capsys):
    receipt = checks.check_documentation(repository)
    assert receipt == checks.check_documentation(repository)
    assert receipt["counts"] == dict(markdown_files=4, local_links=1, remote_links_skipped=0,
                                      heading_fragments=1, sh_blocks_en=8, sh_blocks_zh=8, failures=0)
    assert checks.main(["--root", str(repository)]) == 0
    output = capsys.readouterr()
    assert json.loads(output.out) == receipt
    assert output.err == ""
    assert str(repository) not in output.out


@pytest.mark.parametrize(("destination", "code"), [
    ("missing.md", "LOCAL_INPUT_UNAVAILABLE_OR_UNSAFE"),
    ("docs/guide.md#missing", "HEADING_NOT_FOUND"),
    ("../outside.md", "PATH_ESCAPE"),
    ("docs/../../outside.md", "PATH_ESCAPE"),
    ("%2e%2e/outside.md", "PATH_ESCAPE"),
    ("docs/%2e%2e/%2e%2e/outside.md", "PATH_ESCAPE"),
    ("%252e%252e/outside.md", "NESTED_PERCENT_ESCAPE"),
    ("/outside.md", "INVALID_LOCAL_PATH"),
    ("%2foutside.md", "INVALID_LOCAL_PATH"),
    ("docs%5cguide.md", "INVALID_LOCAL_PATH"),
    ("file:///outside.md", "INVALID_LOCAL_PATH"),
    ("docs/guide.md?query=yes", "LOCAL_QUERY_UNSUPPORTED"),
    ("bad%XX.md", "INVALID_PERCENT_ESCAPE"),
    ("bad%FF.md", "INVALID_PERCENT_ESCAPE"),
    ("bad%00.md", "INVALID_LOCAL_PATH"),
    (".git/private.md", "EXCLUDED_TARGET"),
    ("docs", "LOCAL_INPUT_UNAVAILABLE_OR_UNSAFE"),
    ("docs/guide.md title", "LINK_SYNTAX_UNSUPPORTED"),
    ("docs/(guide).md", "LINK_SYNTAX_UNSUPPORTED"),
])
def test_broken_or_unsafe_local_target_fails(repository, destination, code):
    replace_readme(repository, f"[Link]({destination})\n")
    assert code in failure_codes(checks.check_documentation(repository))


def test_valid_local_paths_images_titles_and_percent_decoding(repository):
    (repository / "docs/with space.md").write_text("# 中文 标题\n", encoding="utf-8")
    (repository / "image.svg").write_text("<svg/>\n", encoding="utf-8")
    replace_readme(repository, '# Home\n[one](docs/./guide.md#hello-world)\n'
                   '[two](docs/../docs/with%20space.md#%E4%B8%AD%E6%96%87-%E6%A0%87%E9%A2%98)\n'
                   '[three](<docs/with space.md> "optional title")\n'
                   '![image](image.svg)\n[home](#home)\n[top](#)\n')
    (repository / "docs/guide.md").write_text('# Hello World\n[Parent](../README.md#home)\n', encoding="utf-8")
    receipt = checks.check_documentation(repository)
    assert receipt["accepted"] is True, receipt
    assert receipt["counts"]["local_links"] == 7
    assert receipt["counts"]["heading_fragments"] == 4


def test_remote_links_are_skipped_without_network(repository, monkeypatch):
    import socket
    import urllib.request

    def forbidden(*args, **kwargs):
        raise AssertionError("network calls are forbidden")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    replace_readme(repository, "[web](https://invalid.example/missing#anchor)\n"
                   "[mail](mailto:example@example.invalid)\n[relative](//invalid.example/x)\n")
    receipt = checks.check_documentation(repository)
    assert receipt["accepted"] is True, receipt
    assert receipt["counts"]["remote_links_skipped"] == 3
    assert receipt["counts"]["local_links"] == 0


def test_duplicate_unicode_and_inline_code_heading_convention(repository):
    replace_readme(repository, "# Hello `world`!\n# Hello world\n# Hello world-1\n"
                   "# 中文 标题\n# Punctuation: (A/B) ###\n"
                   "[a](#hello-world) [b](#hello-world-1) [c](#hello-world-1-1)\n"
                   "[d](#中文-标题) [e](#punctuation-ab)\n")
    assert checks.check_documentation(repository)["accepted"] is True


def test_fenced_and_inline_examples_do_not_create_links_or_headings(repository):
    replace_readme(repository, "# Home\n```markdown\n[bad](absent.md)\n# Hidden\n```\n"
                   "~~~~markdown\n```sh\n[bad](absent2.md)\n```\n~~~~\n"
                   "`[inline](absent3.md)` and ``[inline `code`](absent4.md)``\n"
                   "    [indented](absent5.md)\n\\[escaped](absent6.md)\n[home](#home)\n")
    receipt = checks.check_documentation(repository)
    assert receipt["accepted"] is True, receipt
    assert receipt["counts"]["local_links"] == 1
    with (repository / "README.md").open("a", encoding="utf-8") as stream:
        stream.write("[hidden](#hidden)\n")
    assert "HEADING_NOT_FOUND" in failure_codes(checks.check_documentation(repository))


def test_unclosed_fence_fails_instead_of_hiding_links(repository):
    replace_readme(repository, "```markdown\n[broken](missing.md)\n")
    assert "UNCLOSED_FENCE" in failure_codes(checks.check_documentation(repository))


@pytest.mark.parametrize("mutation", ["command", "space", "newline", "reorder", "missing", "both_missing", "both_empty", "both_short"])
def test_quickstart_drift_missing_or_empty_blocks_fail(repository, mutation):
    english, chinese = (repository / path for path in checks.QUICKSTARTS)
    first = b"```sh\none\n```\n"
    second = b"```sh\ntwo\n```\n"
    remaining = b"```sh\nremaining\n```\n" * 6
    english.write_bytes(first + second + remaining)
    chinese.write_bytes(first + second + remaining)
    if mutation == "command":
        chinese.write_bytes(first.replace(b"one", b"changed") + second + remaining)
    elif mutation == "space":
        chinese.write_bytes(first.replace(b"one", b"one ") + second + remaining)
    elif mutation == "newline":
        chinese.write_bytes((first + second + remaining).replace(b"\n", b"\r\n"))
    elif mutation == "reorder":
        chinese.write_bytes(second + first + remaining)
    elif mutation == "missing":
        chinese.write_bytes(first + remaining)
    elif mutation == "both_missing":
        english.write_bytes(b"# Empty\n")
        chinese.write_bytes(b"# Empty\n")
    elif mutation == "both_empty":
        english.write_bytes(b"```sh\n  \n```\n" + second + remaining)
        chinese.write_bytes(b"```sh\n  \n```\n" + second + remaining)
    else:
        english.write_bytes(first + remaining)
        chinese.write_bytes(first + remaining)
    codes = failure_codes(checks.check_documentation(repository))
    expected = {"missing": "SH_BLOCK_COUNT_MISMATCH", "both_missing": "SH_BLOCKS_MISSING",
                "both_empty": "EMPTY_SH_BLOCK", "both_short": "SH_BLOCK_PROFILE_COUNT"}.get(mutation, "SH_BLOCK_MISMATCH")
    assert expected in codes


def test_missing_quickstart_file_fails(repository):
    (repository / checks.QUICKSTARTS[1]).unlink()
    assert "QUICKSTART_UNAVAILABLE" in failure_codes(checks.check_documentation(repository))


def test_nested_sh_example_is_not_a_command_block(repository):
    for path in checks.QUICKSTARTS:
        (repository / path).write_text("````markdown\n```sh\nexample only\n```\n````\n", encoding="utf-8")
    assert "SH_BLOCKS_MISSING" in failure_codes(checks.check_documentation(repository))


@pytest.mark.parametrize("kind", ["file", "directory", "root", "dangling"])
def test_symlinks_fail_without_reading_external_content(repository, tmp_path, monkeypatch, kind):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.md").write_text("# External secret\n", encoding="utf-8")
    try:
        if kind == "directory":
            (repository / "escape").symlink_to(outside, target_is_directory=True)
            replace_readme(repository, "[escape](escape/secret.md)\n")
        elif kind == "root":
            linked_root = tmp_path / "linked-root"
            linked_root.symlink_to(repository, target_is_directory=True)
        else:
            (repository / "escape.md").symlink_to(outside / ("secret.md" if kind == "file" else "absent.md"))
            replace_readme(repository, "[escape](escape.md)\n")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable; not a passing symlink check")
    original_read = checks.audit._read

    def guarded_read(fd, path, limit):
        assert (repository / path).resolve().is_relative_to(repository)
        return original_read(fd, path, limit)

    monkeypatch.setattr(checks.audit, "_read", guarded_read)
    receipt = checks.check_documentation(linked_root if kind == "root" else repository)
    assert failure_codes(receipt) & {"SYMLINK_IN_TREE", "ROOT_UNAVAILABLE"}
    assert "External secret" not in json.dumps(receipt)
    assert str(tmp_path) not in json.dumps(receipt)


def test_invalid_utf8_and_non_markdown_fragment_fail(repository):
    (repository / "docs/guide.md").write_bytes(b"\xff")
    (repository / "plain.txt").write_text("# Not a Markdown anchor\n", encoding="utf-8")
    replace_readme(repository, "[plain](plain.txt#not-a-markdown-anchor)\n")
    codes = failure_codes(checks.check_documentation(repository))
    assert {"INVALID_UTF8", "FRAGMENT_ON_NON_MARKDOWN"} <= codes


@pytest.mark.parametrize(("limit", "value", "code"), [
    ("MAX_ENTRIES", 2, "TOO_MANY_ENTRIES"),
    ("MAX_DOCUMENTS", 2, "TOO_MANY_DOCUMENTS"),
    ("MAX_DEPTH", 0, "TREE_TOO_DEEP"),
    ("MAX_TOTAL_BYTES", 5, "TOTAL_INPUT_TOO_LARGE"),
    ("MAX_LINKS", 0, "TOO_MANY_LINKS"),
])
def test_limits_fail_closed(repository, monkeypatch, limit, value, code):
    monkeypatch.setattr(checks, limit, value)
    assert code in failure_codes(checks.check_documentation(repository))


def test_excluded_output_trees_are_not_scanned(repository):
    (repository / "dist").mkdir()
    (repository / "dist/ignored.md").write_text("[broken](not-real.md)\n", encoding="utf-8")
    receipt = checks.check_documentation(repository)
    assert receipt["accepted"] is True
    assert receipt["counts"]["markdown_files"] == 4


def test_failures_are_sorted_and_cli_returns_one_json_without_paths_or_commands(repository, capsys):
    replace_readme(repository, "[one](missing.md)\n[two](../outside.md)\n")
    (repository / checks.QUICKSTARTS[1]).write_text("```sh\nDO_NOT_LEAK_THIS_COMMAND\n```\n", encoding="utf-8")
    assert checks.main(["--root", str(repository)]) == 1
    output = capsys.readouterr()
    receipt = json.loads(output.out)
    failures = receipt["failures"]
    assert failures == sorted(failures, key=lambda row: (row["path"], row["line"], row["code"]))
    assert all(not Path(row["path"]).is_absolute() and ".." not in Path(row["path"]).parts for row in failures)
    assert str(repository) not in output.out
    assert "DO_NOT_LEAK_THIS_COMMAND" not in output.out
    assert output.err == ""


def test_empty_or_unavailable_root_cannot_pass(tmp_path):
    assert "NO_MARKDOWN_FILES" in failure_codes(checks.check_documentation(tmp_path))
    assert "ROOT_UNAVAILABLE" in failure_codes(checks.check_documentation(tmp_path / "absent"))


def test_document_commands_and_linked_python_are_never_executed(repository, monkeypatch):
    import os
    import subprocess

    def forbidden(*args, **kwargs):
        raise AssertionError("command execution is forbidden")

    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    (repository / "linked.py").write_text("raise AssertionError('linked code ran')\n", encoding="utf-8")
    replace_readme(repository, "[source](linked.py)\n```python\nraise AssertionError('fenced code ran')\n```\n")
    assert checks.check_documentation(repository)["accepted"] is True


def test_unsupported_filesystem_platform_fails_closed(repository, monkeypatch):
    def unsupported(root):
        raise checks.audit.AuditRejected("UNSUPPORTED_PLATFORM")

    monkeypatch.setattr(checks.audit, "_root_fd", unsupported)
    assert "UNSUPPORTED_PLATFORM" in failure_codes(checks.check_documentation(repository))


@pytest.mark.parametrize("declaration", [
    '<a id="declared-anchor"></a>',
    "<span id='declared-anchor'>Target</span>",
    "<A ID=declared-anchor></A>",
    '<a name="declared-anchor"></a>',
    '<span id="declared&#45;anchor" />',
])
def test_explicit_html_anchor_declarations_pass(repository, declaration):
    replace_readme(repository, f"{declaration}\n[Target](#declared-anchor)\n")
    assert checks.check_documentation(repository)["accepted"] is True


@pytest.mark.parametrize("example", [
    '```html\n<a id="declared-anchor"></a>\n```',
    '~~~~markdown\n```html\n<a id="declared-anchor"></a>\n```\n~~~~',
    '`<a id="declared-anchor"></a>`',
    '``<a id="declared-anchor" title="`example`"></a>``',
    '    <a id="declared-anchor"></a>',
    '<!-- <a id="declared-anchor"></a> -->',
    '<!--\n<a id="declared-anchor"></a>\n-->',
    '&lt;a id="declared-anchor"&gt;&lt;/a&gt;',
    '<script>\nconst example = \'<a id="declared-anchor"></a>\';\n</script>',
    '<style>\n/* <a id="declared-anchor"></a> */\n</style>',
    '<a title=\'id="declared-anchor"\'></a>',
    '<span name="declared-anchor"></span>',
    '<a id="DECLARED-ANCHOR"></a>',
    '<a id="declared-anchor" id="ambiguous"></a>',
    '<a\nid="declared-anchor"></a>',
])
def test_inert_or_unsupported_html_does_not_create_anchor(repository, example):
    replace_readme(repository, f"{example}\n[Target](#declared-anchor)\n")
    assert "HEADING_NOT_FOUND" in failure_codes(checks.check_documentation(repository))


def test_code_example_does_not_open_html_parser_state_or_join_an_anchor(repository):
    replace_readme(repository, '```html\n<script>\n```\n<a id="real"></a>\n[real](#real)\n'
                   '<a\n```html\nignored\n```\nid="joined"></a>\n[joined](#joined)\n')
    receipt = checks.check_documentation(repository)
    assert failure_codes(receipt) == {"HEADING_NOT_FOUND"}
    assert len(receipt["failures"]) == 1


def test_explicit_html_ids_preserve_case_unicode_and_heading_suffixes(repository):
    replace_readme(repository, '<a id="Hello-世界"></a>\n<span id="repeat"></span>\n'
                   '# Repeat\n# Repeat\n[explicit](#Hello-%E4%B8%96%E7%95%8C)\n'
                   '[first](#repeat)\n[second](#repeat-1)\n')
    assert checks.check_documentation(repository)["accepted"] is True


def test_html_parser_refusal_returns_json_failure(repository, monkeypatch, capsys):
    original_feed = checks.HTMLParser.feed

    def refuse_declaration(parser, data):
        if "<![BOGUS]>" in data:
            raise AssertionError("parser-specific unsupported declaration")
        return original_feed(parser, data)

    monkeypatch.setattr(checks.HTMLParser, "feed", refuse_declaration)
    replace_readme(repository, '<![BOGUS]>\n<a id="declared-anchor"></a>\n[Target](#declared-anchor)\n')
    assert checks.main(["--root", str(repository)]) == 1
    output = capsys.readouterr()
    assert "HTML_SYNTAX_UNSUPPORTED" in failure_codes(json.loads(output.out))
    assert output.err == ""
