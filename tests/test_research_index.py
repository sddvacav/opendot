"""Offline consistency checks for the curated research index, not a runtime schema.

Passing checks bind recorded mappings to local bytes. They establish neither
source truth, fresh web access, endorsement, nor implemented/accepted features.
"""
from copy import deepcopy
from datetime import date
import ipaddress
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

import pytest

from opendot_engineering.adapters import source_audit as audit


ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = "docs/research/source-needs-index.json"
NEED_FIELDS = (
    "need_id source_ids document_locator paraphrased_need inference inference_scope "
    "proposed_feature acceptance_evidence priority priority_origin "
    "implementation_status implementation_evidence limitations"
).split()


def _fields(record, names):
    assert isinstance(record, dict), "expected an object"
    missing = set(names) - record.keys()
    assert not missing, f"missing required fields: {sorted(missing)}"


def _text(value):
    assert isinstance(value, str) and value.strip(), "expected nonempty text"


def _texts(values, *, nonempty=False):
    assert isinstance(values, list), "expected a text list"
    assert not nonempty or values, "expected a nonempty text list"
    for value in values:
        _text(value)


def _date(value, *, nullable=False):
    if nullable and value is None:
        return
    assert isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value), "invalid date"
    try:
        date.fromisoformat(value)
    except ValueError:
        raise AssertionError(f"invalid calendar date: {value}") from None


def _public_https(value):
    """Check public-link syntax only; no DNS lookup or availability assertion."""
    _text(value)
    assert not any(c.isspace() or ord(c) < 32 for c in value), "invalid HTTPS link"
    url = urlsplit(value)
    assert url.scheme == "https" and url.hostname, "expected public HTTPS link"
    assert url.username is None and url.password is None, "credentials in link"
    assert url.port in (None, 443), "unexpected HTTPS port"
    host = url.hostname.rstrip(".").lower()
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        assert "." in host and not host.endswith(
            (".localhost", ".local", ".internal", ".invalid", ".test")
        ), "nonpublic hostname"
        assert all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", label)
                   for label in host.split(".")), "invalid hostname"
    else:
        assert address.is_global, "nonpublic IP address"


def _by_id(records, key):
    assert isinstance(records, list) and records, f"empty {key} collection"
    result = {}
    for record in records:
        _fields(record, [key])
        identifier = record[key]
        audit._identifier(identifier)
        assert identifier not in result, f"duplicate {key}: {identifier}"
        result[identifier] = record
    return result


def _locator(locator, documents):
    _fields(locator, ["document_id", "line", "text_anchor"])
    assert locator["document_id"] in documents, "dangling document reference"
    text = documents[locator["document_id"]]
    line = locator["line"]
    assert type(line) is int and 1 <= line <= len(text.splitlines()), "invalid document line"
    _text(locator["text_anchor"])
    # Recorded lines are hints: integration added navigation before README's anchor.
    assert locator["text_anchor"] in text, "missing document text anchor"


def _check_curated_index(index, root_fd):
    """Assertions for this repository's proposal-only index; no external effects."""
    _fields(index, ("schema_version index_id composed_date research_as_of scope date_policy "
                    "provenance_policy priority_definitions global_limitations documents sources needs").split())
    assert index["schema_version"] == "1.0"
    audit._identifier(index["index_id"])
    for field in ("composed_date", "research_as_of"):
        _date(index[field])
    for field in ("scope", "provenance_policy"):
        _text(index[field])
    _fields(index["date_policy"], ["publication_date", "composition_date", "access_date"])
    for value in index["date_policy"].values():
        _text(value)
    assert set(index["priority_definitions"]) == {"P0", "P1", "P2"}
    for value in index["priority_definitions"].values():
        _text(value)
    _texts(index["global_limitations"], nonempty=True)

    documents = _by_id(index["documents"], "document_id")
    sources = _by_id(index["sources"], "source_id")
    needs = _by_id(index["needs"], "need_id")
    document_texts, paths = {}, set()
    for identifier, document in documents.items():
        _fields(document, ("file_name logical_location sha256 declared_research_as_of "
                           "publication_date composition_date index_read_date composition_date_note").split())
        parts = audit._relative(document["logical_location"])
        assert parts[:2] == ["docs", "research"], "document outside curated research directory"
        assert parts[-1] == document["file_name"], "document filename mismatch"
        assert document["logical_location"] not in paths, "duplicate document path"
        paths.add(document["logical_location"])
        raw = audit._read(root_fd, document["logical_location"], audit.MAX_SOURCE_BYTES)
        audit._hash(document["sha256"], 64)
        assert audit._sha256(raw) == document["sha256"], f"document hash mismatch: {identifier}"
        document_texts[identifier] = raw.decode("utf-8")
        for field in ("declared_research_as_of", "index_read_date"):
            _date(document[field])
        for field in ("publication_date", "composition_date"):
            _date(document[field], nullable=True)
        _text(document["composition_date_note"])

    for source in sources.values():
        _fields(source, ("family title original_url source_type publication_date composition_date "
                         "access_date date_precision publication_timezone verification_provenance "
                         "limitations endorsement_or_procurement_evidence").split())
        for field in ("family", "title", "source_type"):
            _text(source[field])
        _public_https(source["original_url"])
        if "supporting_urls" in source:
            _texts(source["supporting_urls"], nonempty=True)
            for url in source["supporting_urls"]:
                _public_https(url)
        # The recorded policy permits unknown publication dates for dynamic homepages.
        _date(source["publication_date"], nullable=source["source_type"] == "INSTITUTIONAL_WEBSITE")
        _date(source["composition_date"], nullable=True)
        _date(source["access_date"])
        for field in ("event_date", "first_publication_date"):
            if field in source:
                _date(source[field])
        assert source["date_precision"] == "day"
        if source["publication_timezone"] is not None:
            _text(source["publication_timezone"])
        _texts(source["limitations"], nonempty=True)
        assert source["endorsement_or_procurement_evidence"] is False
        provenance = source["verification_provenance"]
        _fields(provenance, ["mode", "reviewed_document_locator", "recorded_verification_date",
                             "reopened_for_this_index"])
        assert provenance["mode"] in {"INHERITED_DOCUMENT_VERIFICATION",
                                      "DIRECT_WEB_TEXT_VERIFIED_THIS_RESEARCH_ROUND"}
        _locator(provenance["reviewed_document_locator"], document_texts)
        _date(provenance["recorded_verification_date"])
        assert provenance["reopened_for_this_index"] is False

    for need in needs.values():
        _fields(need, NEED_FIELDS)
        _texts(need["source_ids"], nonempty=True)
        assert len(set(need["source_ids"])) == len(need["source_ids"]), "duplicate source reference"
        assert set(need["source_ids"]) <= sources.keys(), "dangling source reference"
        _locator(need["document_locator"], document_texts)
        for field in ("paraphrased_need", "inference_scope", "proposed_feature"):
            _text(need[field])
        assert need["inference"] is True
        assert need["priority"] in index["priority_definitions"], "invalid priority"
        assert need["priority_origin"] == "RESEARCH_RECOMMENDATION"
        assert need["implementation_status"] == "PROPOSED"
        assert need["implementation_evidence"] == []
        _texts(need["limitations"])
        acceptance = need["acceptance_evidence"]
        _fields(acceptance, ["oracle", "expected_artifacts", "execution_status"])
        _text(acceptance["oracle"])
        _texts(acceptance["expected_artifacts"], nonempty=True)
        assert acceptance["execution_status"] == "NOT_RUN"


@pytest.fixture
def curated_index():
    root_fd = audit._root_fd(ROOT)
    try:
        index = audit._decode(audit._read(root_fd, INDEX_PATH, audit.MAX_MANIFEST_BYTES))
        yield index, root_fd
    finally:
        os.close(root_fd)


def test_curated_research_index_is_structurally_consistent(curated_index):
    _check_curated_index(*curated_index)


@pytest.mark.parametrize("field", NEED_FIELDS)
def test_curated_index_rejects_missing_mapping_field(curated_index, field):
    index, root_fd = curated_index
    broken = deepcopy(index)
    del broken["needs"][0][field]
    with pytest.raises(AssertionError, match="missing required fields"):
        _check_curated_index(broken, root_fd)


def test_curated_index_rejects_dangling_source_reference(curated_index):
    index, root_fd = curated_index
    broken = deepcopy(index)
    broken["needs"][0]["source_ids"] = ["missing-source-for-negative-test"]
    with pytest.raises(AssertionError, match="dangling source reference"):
        _check_curated_index(broken, root_fd)


def test_curated_index_rejects_wrong_document_hash(curated_index):
    index, root_fd = curated_index
    broken = deepcopy(index)
    broken["documents"][0]["sha256"] = "0" * 64
    with pytest.raises(AssertionError, match="document hash mismatch"):
        _check_curated_index(broken, root_fd)


@pytest.mark.parametrize("collection,key", [("documents", "document_id"),
                                            ("sources", "source_id"), ("needs", "need_id")])
def test_curated_index_rejects_duplicate_ids(curated_index, collection, key):
    index, root_fd = curated_index
    broken = deepcopy(index)
    broken[collection].append(deepcopy(broken[collection][0]))
    with pytest.raises(AssertionError, match=f"duplicate {key}"):
        _check_curated_index(broken, root_fd)


@pytest.mark.parametrize("provenance", [False, True])
def test_curated_index_rejects_dangling_document_reference(curated_index, provenance):
    index, root_fd = curated_index
    broken = deepcopy(index)
    locator = (broken["sources"][0]["verification_provenance"]["reviewed_document_locator"]
               if provenance else broken["needs"][0]["document_locator"])
    locator["document_id"] = "missing-document-for-negative-test"
    with pytest.raises(AssertionError, match="dangling document reference"):
        _check_curated_index(broken, root_fd)


@pytest.mark.parametrize("value", [None, "", "20261001", "2026-02-30", "2026-10-01T00:00:00Z"])
def test_curated_index_rejects_invalid_access_date(curated_index, value):
    index, root_fd = curated_index
    broken = deepcopy(index)
    broken["sources"][0]["access_date"] = value
    with pytest.raises(AssertionError, match="date"):
        _check_curated_index(broken, root_fd)


@pytest.mark.parametrize("url", ["http://example.com/report", "https://localhost/report",
                                  "https://127.0.0.1/report", "https://10.0.0.1/report",
                                  "https://[::1]/report", "https://notes.local/report",
                                  "https://user:password@example.com/report"])
def test_curated_index_rejects_nonpublic_links(curated_index, url):
    index, root_fd = curated_index
    broken = deepcopy(index)
    broken["sources"][0]["original_url"] = url
    with pytest.raises(AssertionError):
        _check_curated_index(broken, root_fd)



def test_curated_index_allows_document_and_dynamic_homepage_null_dates(curated_index):
    index, root_fd = curated_index
    copy = deepcopy(index)
    for document in copy["documents"]:
        document.update(publication_date=None, composition_date=None)
    copy["sources"][0].update(source_type="INSTITUTIONAL_WEBSITE",
                              publication_date=None, composition_date=None)
    _check_curated_index(copy, root_fd)


def test_curated_index_rejects_null_publication_date_for_dated_source(curated_index):
    index, root_fd = curated_index
    broken = deepcopy(index)
    broken["sources"][0].update(source_type="PUBLIC_SOCIAL_POST", publication_date=None)
    with pytest.raises(AssertionError, match="date"):
        _check_curated_index(broken, root_fd)


@pytest.mark.parametrize("field,value", [
    ("priority", "P9"), ("priority_origin", "SOURCE_REQUIREMENT"),
    ("implementation_status", "IMPLEMENTED"), ("implementation_evidence", ["claimed"]),
    ("inference", False),
])
def test_curated_index_rejects_promoted_or_invalid_mapping_status(curated_index, field, value):
    index, root_fd = curated_index
    broken = deepcopy(index)
    broken["needs"][0][field] = value
    with pytest.raises(AssertionError):
        _check_curated_index(broken, root_fd)


@pytest.mark.parametrize("field", ["oracle", "expected_artifacts", "execution_status"])
def test_curated_index_rejects_missing_acceptance_field(curated_index, field):
    index, root_fd = curated_index
    broken = deepcopy(index)
    del broken["needs"][0]["acceptance_evidence"][field]
    with pytest.raises(AssertionError, match="missing required fields"):
        _check_curated_index(broken, root_fd)


def test_curated_index_rejects_claimed_acceptance_execution(curated_index):
    index, root_fd = curated_index
    broken = deepcopy(index)
    broken["needs"][0]["acceptance_evidence"]["execution_status"] = "PASSED"
    with pytest.raises(AssertionError):
        _check_curated_index(broken, root_fd)
