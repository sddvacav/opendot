"""Pure acquisition tests: fake HTTP bytes and synthetic archives; no CLI runs."""
from __future__ import annotations

import ast
import errno
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import ssl
import sys
import tarfile
from types import SimpleNamespace
import urllib.request
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("temporal_cli_acquisition_under_test", ROOT / "ci/acquire_temporal_cli.py")
assert SPEC is not None and SPEC.loader is not None
acquirer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = acquirer
SPEC.loader.exec_module(acquirer)

BINARY = b"FAKE TEMPORAL BYTES: NEVER EXECUTE\n"
LICENSE = b"MIT License\nCopyright (c) synthetic test fixture\n"


def sha256(value):
    return hashlib.sha256(value).hexdigest()


def member(name, body=b"fixture", *, kind=tarfile.REGTYPE, linkname="", size=None, mode=0o644):
    information = tarfile.TarInfo(name)
    information.type = kind
    information.linkname = linkname
    information.mode = mode
    information.size = len(body) if size is None else size
    # Explicit physical headers let tests cover PAX/GNU pseudo-members too.
    header = information.tobuf(format=tarfile.USTAR_FORMAT)
    return header + body + bytes((-len(body)) % tarfile.BLOCKSIZE)


def archive(entries=None, *, trailer=None):
    if entries is None:
        entries = [member("temporal", BINARY), member("LICENSE", LICENSE)]
    if trailer is None:
        trailer = bytes(2 * tarfile.BLOCKSIZE)
    return gzip.compress(b"".join(entries) + trailer, mtime=0)


class FakeResponse:
    def __init__(self, body, url, *, status=200, headers=None, chunk_bytes=13):
        self.body = io.BytesIO(body)
        self.url = url
        self.status = status
        self.headers = headers if headers is not None else {"Content-Length": str(len(body))}
        self.chunk_bytes = chunk_bytes
        self.read_sizes = []
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *arguments):
        self.closed = True

    def geturl(self):
        return self.url

    def read1(self, size):
        assert 0 < size <= acquirer.CHUNK_BYTES
        self.read_sizes.append(size)
        return self.body.read(min(size, self.chunk_bytes))


class FakeOpener:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []
        self.handlers = []

    def open(self, request, timeout):
        assert 0 < timeout <= acquirer.SOCKET_TIMEOUT_SECONDS
        assert request.get_header("Accept-encoding") == "identity"
        self.calls.append(request.full_url)
        return self.responses[request.full_url]


@pytest.fixture(autouse=True)
def no_live_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Live network access is forbidden in pure tests")
    monkeypatch.setattr(acquirer, "build_opener", forbidden)
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", forbidden)
    monkeypatch.setattr(acquirer, "_proxy_environment", lambda: {})
    monkeypatch.setattr(acquirer, "getproxies", lambda: {})
    monkeypatch.setattr(acquirer.platform, "system", lambda: "Linux")
    monkeypatch.setattr(acquirer.platform, "machine", lambda: "x86_64")


@pytest.fixture
def fake_downloads(monkeypatch):
    def configure(archive_body=None, manifest_body=None):
        body = archive() if archive_body is None else archive_body
        archive_pin = acquirer.Asset(acquirer.ARCHIVE.name, len(body), sha256(body))
        manifest = ((archive_pin.sha256 + "  " + archive_pin.name + "\n").encode()
                    if manifest_body is None else manifest_body)
        checksum_pin = acquirer.Asset("checksums.txt", len(manifest), sha256(manifest))
        monkeypatch.setattr(acquirer, "ARCHIVE", archive_pin)
        monkeypatch.setattr(acquirer, "CHECKSUMS", checksum_pin)
        opener = FakeOpener({
            archive_pin.url: FakeResponse(body, archive_pin.url),
            checksum_pin.url: FakeResponse(manifest, checksum_pin.url),
        })
        monkeypatch.setattr(acquirer, "build_opener", lambda *handlers: opener)
        return opener
    return configure


def test_exact_official_release_pins():
    assert acquirer.CLI_VERSION == "1.9.1"
    assert acquirer.PLATFORM == "linux-x86_64"
    assert acquirer.ARCHIVE.size_bytes == 45_298_806
    assert acquirer.ARCHIVE.sha256 == "09a0326a51db84d02735e53542b9ebd8c4758daf47482a9ab0abce15844e60d5"
    assert acquirer.CHECKSUMS.size_bytes == 836
    assert acquirer.CHECKSUMS.sha256 == "cc22cb0df0a9bab358500dce212616e8622b0649df68317d9858867d7dc69bd2"
    assert acquirer.ARCHIVE.url == "https://github.com/temporalio/cli/releases/download/v1.9.1/temporal_cli_1.9.1_linux_amd64.tar.gz"
    assert acquirer.CHECKSUMS.url == "https://github.com/temporalio/cli/releases/download/v1.9.1/checksums.txt"


def test_acquires_only_two_files_and_private_actual_hash_receipt(tmp_path, fake_downloads):
    opener = fake_downloads()
    output = tmp_path / "fresh"
    receipt = acquirer.acquire(output)
    assert opener.calls == [acquirer.CHECKSUMS.url, acquirer.ARCHIVE.url]
    assert set(path.name for path in output.iterdir()) == {"temporal", "LICENSE", acquirer.RECEIPT_NAME}
    assert (output / "temporal").read_bytes() == BINARY
    assert (output / "LICENSE").read_bytes() == LICENSE
    assert receipt == json.loads((output / acquirer.RECEIPT_NAME).read_text())
    assert set(receipt) == {"schema_version", "cli_version", "platform", "archive", "checksums", "files"}
    assert receipt["schema_version"] == "opendot.temporal.cli-acquisition.v1"
    assert receipt["files"] == {
        "temporal": {"size_bytes": len(BINARY), "sha256": sha256(BINARY)},
        "LICENSE": {"size_bytes": len(LICENSE), "sha256": sha256(LICENSE)},
    }
    for name in ("archive", "checksums"):
        assert set(receipt[name]) == {"name", "url", "size_bytes", "sha256"}
        pin = acquirer.ARCHIVE if name == "archive" else acquirer.CHECKSUMS
        assert receipt[name]["sha256"] == pin.sha256
        assert receipt[name]["size_bytes"] == pin.size_bytes
    assert stat.S_IMODE(output.stat().st_mode) == 0o700
    assert stat.S_IMODE((output / "temporal").stat().st_mode) == 0o700
    assert stat.S_IMODE((output / "LICENSE").stat().st_mode) == 0o600
    assert stat.S_IMODE((output / acquirer.RECEIPT_NAME).stat().st_mode) == 0o600
    assert str(tmp_path) not in json.dumps(receipt)
    assert all(response.closed for response in opener.responses.values())


@pytest.mark.parametrize("existing", ["directory", "file", "symlink", "broken_symlink"])
def test_existing_destination_never_reused_or_removed(tmp_path, fake_downloads, existing):
    opener = fake_downloads()
    output = tmp_path / "exists"
    sentinel = tmp_path / "sentinel"
    sentinel.write_bytes(b"preserve")
    if existing == "directory":
        output.mkdir()
        (output / "keep").write_bytes(b"preserve")
    elif existing == "file":
        output.write_bytes(b"preserve")
    else:
        output.symlink_to(sentinel if existing == "symlink" else tmp_path / "missing")
    with pytest.raises(acquirer.AcquisitionError, match="^OUTPUT_NOT_FRESH$"):
        acquirer.acquire(output)
    assert os.path.lexists(output)
    assert sentinel.read_bytes() == b"preserve"
    assert not opener.calls


@pytest.mark.parametrize("system,machine", [("Darwin", "x86_64"), ("Linux", "aarch64"), ("Windows", "AMD64")])
def test_non_matching_platform_fails_before_writes(tmp_path, fake_downloads, monkeypatch, system, machine):
    opener = fake_downloads()
    monkeypatch.setattr(acquirer.platform, "system", lambda: system)
    monkeypatch.setattr(acquirer.platform, "machine", lambda: machine)
    with pytest.raises(acquirer.AcquisitionError, match="^UNSUPPORTED_PLATFORM$"):
        acquirer.acquire(tmp_path / "fresh")
    assert not opener.calls
    assert not (tmp_path / "fresh").exists()


@pytest.mark.parametrize("which", ["archive", "checksums"])
def test_corrupt_download_is_rejected_before_extraction(tmp_path, fake_downloads, which):
    opener = fake_downloads()
    pin = acquirer.ARCHIVE if which == "archive" else acquirer.CHECKSUMS
    response = opener.responses[pin.url]
    contents = response.body.getvalue()
    response.body = io.BytesIO(bytes([contents[0] ^ 1]) + contents[1:])
    with pytest.raises(acquirer.AcquisitionError, match="^DOWNLOAD_HASH_MISMATCH$"):
        acquirer.acquire(tmp_path / "fresh")
    assert not (tmp_path / "fresh").exists()
    if which == "checksums":
        assert opener.calls == [acquirer.CHECKSUMS.url]


@pytest.mark.parametrize("delta", [-1, 1, 50_000])
def test_streamed_download_requires_exact_size_without_content_length(tmp_path, fake_downloads, delta):
    opener = fake_downloads()
    response = opener.responses[acquirer.ARCHIVE.url]
    body = response.body.getvalue()
    response.body = io.BytesIO(body[:delta] if delta < 0 else body + b"X" * delta)
    response.headers = {}
    with pytest.raises(acquirer.AcquisitionError, match="^DOWNLOAD_SIZE_MISMATCH$"):
        acquirer.acquire(tmp_path / "fresh")
    assert not (tmp_path / "fresh").exists()


@pytest.mark.parametrize("length", ["1", "-1", "banana", "99999999999999999999999999999999999"])
def test_declared_download_size_must_match(tmp_path, fake_downloads, length):
    opener = fake_downloads()
    opener.responses[acquirer.CHECKSUMS.url].headers["Content-Length"] = length
    with pytest.raises(acquirer.AcquisitionError, match="^DOWNLOAD_SIZE_MISMATCH$"):
        acquirer.acquire(tmp_path / "fresh")
    assert not (tmp_path / "fresh").exists()


@pytest.mark.parametrize("encoding", ["gzip", "br", "deflate"])
def test_transport_content_encoding_is_not_silently_decoded(tmp_path, fake_downloads, encoding):
    opener = fake_downloads()
    opener.responses[acquirer.CHECKSUMS.url].headers["Content-Encoding"] = encoding
    with pytest.raises(acquirer.AcquisitionError, match="^UNEXPECTED_CONTENT_ENCODING$"):
        acquirer.acquire(tmp_path / "fresh")


@pytest.mark.parametrize("url", [
    "http://github.com/temporalio/cli/releases/download/v1.9.1/checksums.txt",
    "https://github.com/temporalio/cli/releases/download/latest/checksums.txt",
    "https://github.com.evil.example/checksums.txt",
    "https://user:secret@release-assets.githubusercontent.com/asset",
    "https://release-assets.githubusercontent.com:444/asset",
    "https://release-assets.githubusercontent.com/asset#fragment",
    "https://release-assets.githubusercontent.com/asset\n",
    "https://release-assets.githubusercontent.com./asset",
    "https://evil.example/asset", "file:///etc/passwd",
])
def test_unapproved_redirects_refused(url):
    assert not acquirer._official_url(url)
    handler = acquirer._OfficialRedirects()
    with pytest.raises(acquirer.AcquisitionError, match="^UNAPPROVED_DOWNLOAD_REDIRECT$"):
        handler.redirect_request(Request(acquirer.CHECKSUMS.url), None, 302, "Found", {}, url)


def test_official_release_asset_redirect_permitted_without_auth():
    url = "https://release-assets.githubusercontent.com/github-production-release-asset/123/abc?sig=opaque"
    handler = acquirer._OfficialRedirects()
    request = handler.redirect_request(Request(acquirer.CHECKSUMS.url), None, 302, "Found", {}, url)
    assert request.full_url == url
    assert not request.has_header("Authorization")
    assert handler.max_redirections == 3


@pytest.mark.parametrize("name", [
    "HTTP_PROXY", "http_proxy", "HtTp_PrOxY", "HTTPS_PROXY", "https_proxy",
    "hTtPs_pRoXy", "ALL_PROXY", "all_proxy", "AlL_pRoXy", "NO_PROXY",
    "no_proxy", "No_PrOxY", "FTP_PROXY", "custom_PrOxY",
])
@pytest.mark.parametrize("value", ["http://user:secret@untrusted.invalid:8080", "*", " "])
def test_nonempty_proxy_environment_refused_before_opener_and_network(
        tmp_path, monkeypatch, capsys, name, value):
    environment = {name: value}
    monkeypatch.setattr(acquirer, "_proxy_environment", lambda: environment)
    # The autouse forbidden constructor would fail if admission is bypassed.
    assert acquirer.main(["--output", str(tmp_path / "fresh")]) == 1
    captured = capsys.readouterr()
    assert captured.out == "PROXY_CONFIGURATION_REFUSED\n"
    assert captured.err == ""
    assert environment == {name: value}
    assert not (tmp_path / "fresh").exists()


@pytest.mark.parametrize("environment", [
    {"HTTP_PROXY": "http://user:secret@untrusted.invalid", "REQUEST_METHOD": "GET"},
    {"HTTP_PROXY": "http://user:secret@untrusted.invalid", "http_proxy": ""},
    {"HTTPS_PROXY": "http://user:secret@untrusted.invalid", "https_proxy": ""},
    {"NO_PROXY": "*", "no_proxy": ""},
    {"NO_PROXY": "github.com,release-assets.githubusercontent.com"},
    {"http_proxy": "malformed proxy configuration"},
])
def test_effective_empty_does_not_hide_cgi_case_overrides_or_bypass_rules(monkeypatch, environment):
    before = dict(environment)
    monkeypatch.setattr(acquirer, "_proxy_environment", lambda: environment)
    monkeypatch.setattr(acquirer, "getproxies", lambda: {})
    with pytest.raises(acquirer.AcquisitionError, match="^PROXY_CONFIGURATION_REFUSED$"):
        acquirer._build_opener()
    assert environment == before


@pytest.mark.parametrize("environment,expected", [
    ({"HTTP_PROXY": "http://user:secret@synthetic.invalid", "http_proxy": ""}, {}),
    ({"HTTPS_PROXY": "http://user:secret@synthetic.invalid", "https_proxy": ""}, {}),
    ({"ALL_PROXY": "socks5://user:secret@synthetic.invalid", "all_proxy": ""}, {}),
    ({"NO_PROXY": "*", "no_proxy": ""}, {}),
    ({"HTTP_PROXY": "http://user:secret@synthetic.invalid", "REQUEST_METHOD": "GET"}, {}),
    ({"HTTP_PROXY": "", "REQUEST_METHOD": "GET", "http_proxy": "http://synthetic.invalid"},
     {"http": "http://synthetic.invalid"}),
])
def test_stdlib_cgi_and_lowercase_empty_override_semantics_still_refuse_raw_configuration(
        monkeypatch, environment, expected):
    # Swap only urllib's module reference for a synthetic object. Never change
    # os.environ, its contents, the process environment or platform settings.
    monkeypatch.setattr(urllib.request, "os", SimpleNamespace(environ=environment))
    effective = urllib.request.getproxies_environment()
    assert effective == expected
    monkeypatch.setattr(acquirer, "_proxy_environment", lambda: environment)
    monkeypatch.setattr(acquirer, "getproxies", lambda: effective)
    with pytest.raises(acquirer.AcquisitionError, match="^PROXY_CONFIGURATION_REFUSED$"):
        acquirer._build_opener()


@pytest.mark.parametrize("bypass", ["*", "github.com,release-assets.githubusercontent.com"])
def test_bypass_rules_do_not_admit_a_configured_effective_proxy(monkeypatch, bypass):
    effective = {"https": "http://user:secret@synthetic.invalid", "no": bypass}
    monkeypatch.setattr(acquirer, "_proxy_environment", lambda: {"NO_PROXY": bypass})
    monkeypatch.setattr(acquirer, "getproxies", lambda: effective)
    with pytest.raises(acquirer.AcquisitionError, match="^PROXY_CONFIGURATION_REFUSED$"):
        acquirer._build_opener()


@pytest.mark.parametrize("effective", [
    {"https": "http://user:secret@platform.invalid:8080"},
    {"http": "http://platform.invalid:8080"},
    {"all": "socks5://user:secret@platform.invalid:1080"},
    {"no": "*"}, {"no": "github.com"}, {"custom": "opaque"},
    {"https": ""}, {"https": None}, None, [], "PRIVATE PROXY DATA",
])
def test_platform_or_effective_proxy_configuration_refused_without_value_disclosure(
        tmp_path, monkeypatch, capsys, effective):
    # Empty environment values alone do not establish empty effective routing.
    monkeypatch.setattr(acquirer, "_proxy_environment", lambda: {"HTTPS_PROXY": "", "NO_PROXY": ""})
    monkeypatch.setattr(acquirer, "getproxies", lambda: effective)
    assert acquirer.main(["--output", str(tmp_path / "fresh")]) == 1
    captured = capsys.readouterr()
    assert captured.out == "PROXY_CONFIGURATION_REFUSED\n"
    assert captured.err == ""
    assert not (tmp_path / "fresh").exists()


@pytest.mark.parametrize("environment", [None, [], "PRIVATE DATA", {b"HTTPS_PROXY": ""}, {"HTTPS_PROXY": None}])
def test_malformed_environment_refused_safely(monkeypatch, environment):
    monkeypatch.setattr(acquirer, "_proxy_environment", lambda: environment)
    with pytest.raises(acquirer.AcquisitionError, match="^PROXY_CONFIGURATION_REFUSED$"):
        acquirer._build_opener()


@pytest.mark.parametrize("source", ["environment", "effective"])
def test_unreadable_routing_configuration_refused_before_construction(tmp_path, monkeypatch, capsys, source):
    def unreadable():
        raise OSError("PRIVATE http://user:secret@proxy.invalid /private/configuration")
    monkeypatch.setattr(acquirer, "_proxy_environment" if source == "environment" else "getproxies", unreadable)
    assert acquirer.main(["--output", str(tmp_path / "fresh")]) == 1
    captured = capsys.readouterr()
    assert captured.out == "PROXY_CONFIGURATION_REFUSED\n"
    assert captured.err == ""
    assert not (tmp_path / "fresh").exists()


def test_environment_iteration_failure_is_refused_safely(monkeypatch):
    class UnreadableEnvironment(dict):
        def items(self):
            yield "PATH", "/synthetic/path"
            raise OSError("PRIVATE ENVIRONMENT DATA")
    monkeypatch.setattr(acquirer, "_proxy_environment", UnreadableEnvironment)
    with pytest.raises(acquirer.AcquisitionError, match="^PROXY_CONFIGURATION_REFUSED$"):
        acquirer._build_opener()


@pytest.mark.parametrize("environment", [
    {}, {"PATH": "/synthetic/path", "REQUEST_METHOD": "GET"},
    {"HTTP_PROXY": "", "http_proxy": "", "hTtPs_PrOxY": "", "ALL_PROXY": "", "NO_PROXY": ""},
])
def test_empty_configuration_uses_normal_opener_and_verified_tls(monkeypatch, environment):
    before = dict(environment)
    monkeypatch.setattr(acquirer, "_proxy_environment", lambda: environment)
    # Only synthetic discovery and a never-opened stdlib opener are used. No
    # environment variable, platform setting, handler or TLS setting is changed.
    monkeypatch.setattr(urllib.request, "getproxies", lambda: {})
    calls = []
    def normal_constructor(*handlers, **kwargs):
        calls.append((handlers, kwargs))
        return urllib.request.build_opener(*handlers, **kwargs)
    monkeypatch.setattr(acquirer, "build_opener", normal_constructor)
    opener = acquirer._build_opener()
    assert len(calls) == 1
    handlers, kwargs = calls[0]
    assert len(handlers) == 1 and type(handlers[0]) is acquirer._OfficialRedirects
    assert kwargs == {}
    https = [handler for handler in opener.handlers if isinstance(handler, urllib.request.HTTPSHandler)]
    assert len(https) == 1
    context = https[0]._context
    if context is None:
        context = ssl._create_default_https_context()
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    assert environment == before


@pytest.mark.parametrize("proxies", [
    {"https": "http://user:secret@appeared.invalid:8080"}, {"no": "*"},
    {"https": ""}, None, "PRIVATE DATA",
])
def test_proxy_configuration_appearing_during_construction_is_refused_before_network(
        tmp_path, monkeypatch, capsys, proxies):
    # Construct an uninitialized synthetic handler: never parse credentials or
    # invoke real discovery. Only the post-construction mapping is exercised.
    handler = object.__new__(acquirer.ProxyHandler)
    handler.proxies = proxies
    opener = FakeOpener({})
    opener.handlers = [handler]
    monkeypatch.setattr(acquirer, "build_opener", lambda *handlers: opener)
    assert acquirer.main(["--output", str(tmp_path / "fresh")]) == 1
    captured = capsys.readouterr()
    assert captured.out == "PROXY_CONFIGURATION_REFUSED\n"
    assert captured.err == ""
    assert opener.calls == []
    assert not (tmp_path / "fresh").exists()


def test_unreadable_constructed_proxy_mapping_is_refused(monkeypatch):
    class UnreadableProxy(acquirer.ProxyHandler):
        @property
        def proxies(self):
            raise OSError("PRIVATE PROXY DATA")
    opener = FakeOpener({})
    opener.handlers = [object.__new__(UnreadableProxy)]
    monkeypatch.setattr(acquirer, "build_opener", lambda *handlers: opener)
    with pytest.raises(acquirer.AcquisitionError, match="^PROXY_CONFIGURATION_REFUSED$"):
        acquirer._build_opener()
    assert opener.calls == []


def test_source_never_overrides_proxy_routing_or_tls():
    tree = ast.parse((ROOT / "ci/acquire_temporal_cli.py").read_text())
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                   and node.func.id == "ProxyHandler" for node in ast.walk(tree))
    assert not any(isinstance(node, ast.Attribute) and node.attr in {
        "_create_unverified_context", "CERT_NONE", "setdefault", "putenv", "unsetenv",
    } for node in ast.walk(tree))


@pytest.mark.parametrize("status,url", [(206, None), (500, None), (200, "https://evil.example/leak")])
def test_final_response_status_and_origin_checked(tmp_path, fake_downloads, status, url):
    opener = fake_downloads()
    response = opener.responses[acquirer.CHECKSUMS.url]
    response.status = status
    if url is not None:
        response.url = url
    with pytest.raises(acquirer.AcquisitionError, match="^UNAPPROVED_DOWNLOAD_RESPONSE$"):
        acquirer.acquire(tmp_path / "fresh")


@pytest.mark.parametrize("manifest,code", [
    (b"garbage\n", "INVALID_CHECKSUM_MANIFEST"),
    (b"\xff\n", "INVALID_CHECKSUM_MANIFEST"),
    (("0" * 64 + "  temporal_cli_1.9.1_linux_amd64.tar.gz\n").encode(), "CHECKSUM_ARCHIVE_MISMATCH"),
    (("0" * 64 + "  other.tar.gz\n").encode(), "CHECKSUM_ARCHIVE_MISSING"),
    (("0" * 64 + "  other.tar.gz\n").encode() * 2, "INVALID_CHECKSUM_MANIFEST"),
    (("0" * 64 + "  ../archive.tar.gz\n").encode(), "INVALID_CHECKSUM_MANIFEST"),
])
def test_manifest_must_bind_archive_once_before_archive_download(tmp_path, fake_downloads, manifest, code):
    opener = fake_downloads(manifest_body=manifest)
    with pytest.raises(acquirer.AcquisitionError, match="^" + code + "$"):
        acquirer.acquire(tmp_path / "fresh")
    assert opener.calls == [acquirer.CHECKSUMS.url]
    assert not (tmp_path / "fresh").exists()


@pytest.mark.parametrize("name", ["../temporal", "/temporal", "./temporal", "folder/../temporal", "folder/temporal", "temporal.exe", "README", "C:\\temporal"])
def test_traversal_and_every_extra_name_rejected(tmp_path, fake_downloads, name):
    fake_downloads(archive([member("temporal", BINARY), member("LICENSE", LICENSE), member(name)]))
    with pytest.raises(acquirer.AcquisitionError, match="^UNEXPECTED_ARCHIVE_MEMBER$"):
        acquirer.acquire(tmp_path / "fresh")
    assert not (tmp_path / "fresh").exists()
    assert not (tmp_path / "temporal").exists()


@pytest.mark.parametrize("kind", [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.DIRTYPE, tarfile.FIFOTYPE, tarfile.CHRTYPE, tarfile.BLKTYPE, tarfile.XHDTYPE, tarfile.XGLTYPE, tarfile.GNUTYPE_LONGNAME, tarfile.GNUTYPE_LONGLINK, tarfile.GNUTYPE_SPARSE])
def test_links_special_files_and_hidden_metadata_rejected(tmp_path, fake_downloads, kind):
    fake_downloads(archive([member("temporal", b"", kind=kind, linkname="../outside"), member("LICENSE", LICENSE)]))
    with pytest.raises(acquirer.AcquisitionError, match="^UNSAFE_ARCHIVE_MEMBER$"):
        acquirer.acquire(tmp_path / "fresh")
    assert not (tmp_path / "fresh").exists()


@pytest.mark.parametrize("name", ["temporal", "LICENSE"])
def test_duplicate_archive_member_rejected(tmp_path, fake_downloads, name):
    fake_downloads(archive([member("temporal", BINARY), member("LICENSE", LICENSE), member(name)]))
    with pytest.raises(acquirer.AcquisitionError, match="^DUPLICATE_ARCHIVE_MEMBER$"):
        acquirer.acquire(tmp_path / "fresh")
    assert not (tmp_path / "fresh").exists()


@pytest.mark.parametrize("name", ["temporal", "LICENSE"])
def test_missing_required_member_rejected(tmp_path, fake_downloads, name):
    fake_downloads(archive([member(name)]))
    with pytest.raises(acquirer.AcquisitionError, match="^MISSING_ARCHIVE_MEMBER$"):
        acquirer.acquire(tmp_path / "fresh")
    assert not (tmp_path / "fresh").exists()


@pytest.mark.parametrize("name,size", [("temporal", 0), ("LICENSE", 0), ("temporal", 192 * 1024 * 1024 + 1), ("LICENSE", 64 * 1024 + 1)])
def test_zero_and_oversized_member_rejected_before_payload_read(tmp_path, fake_downloads, name, size):
    fake_downloads(archive([member(name, b"", size=size)]))
    with pytest.raises(acquirer.AcquisitionError, match="^ARCHIVE_MEMBER_SIZE$"):
        acquirer.acquire(tmp_path / "fresh")
    assert not (tmp_path / "fresh").exists()


def test_huge_metadata_bomb_rejected_before_read(tmp_path, fake_downloads):
    fake_downloads(archive([member("temporal", b"", kind=tarfile.XHDTYPE, size=4 * 1024 * 1024 * 1024)]))
    with pytest.raises(acquirer.AcquisitionError, match="^UNSAFE_ARCHIVE_MEMBER$"):
        acquirer.acquire(tmp_path / "fresh")


@pytest.mark.parametrize("mode", [0o4755, 0o2755, 0o1755])
def test_special_permission_bits_rejected(tmp_path, fake_downloads, mode):
    fake_downloads(archive([member("temporal", BINARY, mode=mode), member("LICENSE", LICENSE)]))
    with pytest.raises(acquirer.AcquisitionError, match="^UNSAFE_ARCHIVE_MODE$"):
        acquirer.acquire(tmp_path / "fresh")


def test_bad_header_checksum_rejected(tmp_path, fake_downloads):
    body = bytearray(gzip.decompress(archive()))
    body[0] ^= 1
    fake_downloads(gzip.compress(body, mtime=0))
    with pytest.raises(acquirer.AcquisitionError, match="^INVALID_ARCHIVE_HEADER$"):
        acquirer.acquire(tmp_path / "fresh")


@pytest.mark.parametrize("body", [
    b"", b"not gzip", gzip.compress(b"x" * 20, mtime=0),
    gzip.compress(member("temporal", b"", size=512), mtime=0),
], ids=["empty_input", "not_gzip", "truncated_tar_header", "truncated_tar_member_payload"])
def test_truncated_or_invalid_gzip_tar_fails_and_cleans(tmp_path, fake_downloads, body):
    fake_downloads(body)
    with pytest.raises(acquirer.AcquisitionError):
        acquirer.acquire(tmp_path / "fresh")
    assert not (tmp_path / "fresh").exists()


def test_gzip_crc_corruption_fails_even_when_archive_download_hash_matches(tmp_path, fake_downloads):
    body = bytearray(archive())
    body[-8] ^= 1
    fake_downloads(bytes(body))
    with pytest.raises(acquirer.AcquisitionError, match="^ACQUISITION_FAILED$"):
        acquirer.acquire(tmp_path / "fresh")
    assert not (tmp_path / "fresh").exists()


@pytest.mark.parametrize("trailer,code", [
    (bytes(512), "TRUNCATED_ARCHIVE"),
    (bytes(512) + b"x" * 512, "INVALID_ARCHIVE_END"),
    (bytes(1024) + member("extra"), "UNEXPECTED_ARCHIVE_TRAILER"),
    (bytes(1024 + 10 * 1024 + 1), "UNEXPECTED_ARCHIVE_TRAILER"),
])
def test_archive_end_requires_bounded_zero_padding_only(tmp_path, fake_downloads, trailer, code):
    fake_downloads(archive(trailer=trailer))
    with pytest.raises(acquirer.AcquisitionError, match="^" + code + "$"):
        acquirer.acquire(tmp_path / "fresh")
    assert not (tmp_path / "fresh").exists()


def test_member_alignment_padding_must_be_zero(tmp_path, fake_downloads):
    bad_member = bytearray(member("temporal", BINARY))
    bad_member[512 + len(BINARY)] = 1
    fake_downloads(archive([bytes(bad_member), member("LICENSE", LICENSE)]))
    with pytest.raises(acquirer.AcquisitionError, match="^INVALID_ARCHIVE_PADDING$"):
        acquirer.acquire(tmp_path / "fresh")


def test_deadline_checked_before_open_and_failure_removes_new_dir(tmp_path, fake_downloads, monkeypatch):
    opener = fake_downloads()
    clock = iter([0, acquirer.DOWNLOAD_SECONDS + 1])
    monkeypatch.setattr(acquirer.time, "monotonic", lambda: next(clock))
    with pytest.raises(acquirer.AcquisitionError, match="^ACQUISITION_DEADLINE$"):
        acquirer.acquire(tmp_path / "fresh")
    assert not opener.calls
    assert not (tmp_path / "fresh").exists()


def test_read_progress_does_not_extend_overall_deadline(tmp_path, fake_downloads, monkeypatch):
    opener = fake_downloads()
    clock = iter([0, 0, 0, acquirer.DOWNLOAD_SECONDS + 1])
    monkeypatch.setattr(acquirer.time, "monotonic", lambda: next(clock))
    with pytest.raises(acquirer.AcquisitionError, match="^ACQUISITION_DEADLINE$"):
        acquirer.acquire(tmp_path / "fresh")
    assert opener.calls == [acquirer.CHECKSUMS.url]
    assert not (tmp_path / "fresh").exists()


def test_download_exception_text_is_not_reported(tmp_path, fake_downloads, monkeypatch, capsys):
    fake_downloads()
    class FailingOpener:
        def open(self, *args, **kwargs):
            raise OSError("SECRET /private/path https://url.invalid/?token=secret")
    monkeypatch.setattr(acquirer, "_build_opener", lambda: FailingOpener())
    assert acquirer.main(["--output", str(tmp_path / "fresh")]) == 1
    assert capsys.readouterr().out == "ACQUISITION_FAILED\n"
    assert not (tmp_path / "fresh").exists()


@pytest.mark.parametrize("argument", ["--output", "--output-dir"])
def test_cli_aliases_only_report_acquisition_not_execution(tmp_path, fake_downloads, capsys, argument):
    fake_downloads()
    assert acquirer.main([argument, str(tmp_path / "fresh")]) == 0
    assert capsys.readouterr().out == "TEMPORAL_CLI_ACQUIRED_NOT_EXECUTED\n"


def test_source_contains_no_execution_or_optional_sdk_import():
    tree = ast.parse((ROOT / "ci/acquire_temporal_cli.py").read_text())
    imports = {alias.name.split(".")[0] for node in ast.walk(tree)
               if isinstance(node, ast.Import) for alias in node.names}
    imports.update((node.module or "").split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom))
    assert not imports & {"subprocess", "temporalio", "opendot_engineering", "ctypes"}
    forbidden_calls = {"system", "popen", "spawn", "fork", "execv", "execve", "execl", "extract", "extractall"}
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                   and isinstance(node.func.value, ast.Name) and node.func.value.id in {"os", "subprocess"}
                   and node.func.attr in forbidden_calls for node in ast.walk(tree))


def test_cleanup_failure_is_a_fixed_code_and_never_success(tmp_path, fake_downloads, monkeypatch, capsys):
    fake_downloads(manifest_body=b"invalid")
    def failed_cleanup(path, **kwargs):
        raise OSError("SECRET /private/cleanup/path")
    monkeypatch.setattr(acquirer.shutil, "rmtree", failed_cleanup)
    assert acquirer.main(["--output", str(tmp_path / "fresh")]) == 1
    assert capsys.readouterr().out == "ACQUISITION_CLEANUP_UNCONFIRMED\n"
    assert not (tmp_path / "fresh" / acquirer.RECEIPT_NAME).exists()


@pytest.mark.parametrize("error,code", [
    (HTTPError("https://private.invalid/?secret=1", 403, "PRIVATE MESSAGE", {}, io.BytesIO(b"PRIVATE BODY")), "HTTP_ERROR"),
    (ssl.SSLCertVerificationError(1, "PRIVATE CERT DETAILS"), "TLS_VERIFICATION_FAILED"),
    (ssl.SSLError(1, "PRIVATE TLS DETAILS"), "TLS_ERROR"),
    (TimeoutError("PRIVATE TIMEOUT DETAILS"), "NETWORK_TIMEOUT"),
    (OSError(errno.ENETUNREACH, "PRIVATE ROUTE DETAILS"), "NETWORK_UNREACHABLE"),
    (OSError(errno.EHOSTUNREACH, "PRIVATE HOST DETAILS"), "NETWORK_UNREACHABLE"),
    (OSError(errno.ENETDOWN, "PRIVATE NETWORK DETAILS"), "NETWORK_UNREACHABLE"),
    (OSError(errno.EACCES, "PRIVATE PERMISSION DETAILS"), "PERMISSION_DENIED"),
    (OSError(errno.EPERM, "PRIVATE POLICY DETAILS"), "PERMISSION_DENIED"),
    (OSError(errno.ECONNREFUSED, "PRIVATE REFUSED DETAILS"), "ACQUISITION_FAILED"),
    (OSError(errno.ENOENT, "PRIVATE MISSING FILE"), "ACQUISITION_FAILED"),
    (PermissionError("permission denied WITHOUT errno"), "ACQUISITION_FAILED"),
    (OSError("TLS certificate failed and timed out, network unreachable, permission denied"), "ACQUISITION_FAILED"),
    (URLError("TLS certificate failed and timed out, network unreachable, permission denied"), "ACQUISITION_FAILED"),
    (ValueError("PRIVATE UNKNOWN DETAILS"), "ACQUISITION_FAILED"),
])
@pytest.mark.parametrize("wrapped", [False, True])
def test_exception_categories_emit_only_supported_fixed_codes(tmp_path, fake_downloads, monkeypatch, capsys, error, code, wrapped):
    fake_downloads()
    caught = URLError(error) if wrapped else error
    class FailingOpener:
        def open(self, *args, **kwargs):
            raise caught
    monkeypatch.setattr(acquirer, "_build_opener", lambda: FailingOpener())
    assert acquirer.main(["--output", str(tmp_path / "fresh")]) == 1
    captured = capsys.readouterr()
    assert captured.out == code + "\n"
    assert captured.err == ""
    assert not (tmp_path / "fresh").exists()


def test_http_error_body_not_read_by_classifier():
    class ForbiddenBody:
        def read(self, *args, **kwargs):
            raise AssertionError("Response body must not be inspected")
        def close(self):
            pass
    error = HTTPError("https://private.invalid", 403, "PRIVATE", {}, ForbiddenBody())
    assert acquirer._failure_code(error) == "HTTP_ERROR"


def test_nested_exception_reason_classification_is_bounded():
    assert acquirer._failure_code(URLError(URLError(TimeoutError()))) == "NETWORK_TIMEOUT"
    error = URLError("UNKNOWN")
    error.reason = error
    assert acquirer._failure_code(error) == "ACQUISITION_FAILED"
    nested = TimeoutError()
    for _ in range(5):
        nested = URLError(nested)
    assert acquirer._failure_code(nested) == "ACQUISITION_FAILED"


def test_classifier_does_not_guess_from_arbitrary_causes_or_boolean_errno():
    error = ValueError("UNKNOWN")
    error.__cause__ = TimeoutError()
    assert acquirer._failure_code(error) == "ACQUISITION_FAILED"
    error = OSError("UNKNOWN")
    error.errno = True
    assert acquirer._failure_code(error) == "ACQUISITION_FAILED"


def test_transport_read_timeout_is_classified_without_a_second_request(tmp_path, fake_downloads, monkeypatch, capsys):
    opener = fake_downloads()
    response = opener.responses[acquirer.CHECKSUMS.url]
    def timed_out(size):
        raise TimeoutError("PRIVATE READ DETAILS")
    monkeypatch.setattr(response, "read1", timed_out)
    assert acquirer.main(["--output", str(tmp_path / "fresh")]) == 1
    assert capsys.readouterr().out == "NETWORK_TIMEOUT\n"
    assert opener.calls == [acquirer.CHECKSUMS.url]
    assert not (tmp_path / "fresh").exists()
