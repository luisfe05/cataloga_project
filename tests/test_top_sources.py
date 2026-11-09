"""Tests for Top sources in the chat summary and the newest-first order."""

import os

import pytest

from backend.config import projects
from backend.db.catalog_repository import CatalogRepository
from backend.db.schema import init_db
from backend.models.document import Document

CHAT_JS = os.path.join(os.path.dirname(__file__), "..", "frontend", "js",
                       "chat.js")
CATALOG_JS = os.path.join(os.path.dirname(__file__), "..", "frontend", "js",
                          "catalog.js")


def add(repo, number, source, date=None):
    """Add one document with a source and a date."""
    name = "doc_{}.pdf".format(number)
    return repo.add_document(Document(
        original_filename=name, filename=name, media_type="Press",
        file_path="/project/" + name, date_added="2026-11-09T10:00:00",
        source=source, document_date=date, summary="A clipping.",
        status="Classified"))


@pytest.fixture
def repo(tmp_path):
    """A new, empty catalog."""
    db_path = str(tmp_path / "catalog.db")
    init_db(db_path)
    return CatalogRepository(db_path)


def top(repo):
    """The (source, count) pairs of the summary, in order."""
    return [(item["source"], item["count"])
            for item in repo.get_project_summary()["top_sources"]]


def test_top_sources_go_from_most_to_fewest(repo):
    """The source with more documents comes first."""
    add(repo, 1, "Coast Weekly", "2020-01-01")
    for number in (2, 3, 4):
        add(repo, number, "Harbor Gazette", "2019-01-01")
    add(repo, 5, "Bay Radio", "2018-01-01")
    add(repo, 6, "Bay Radio", "2018-02-01")
    assert top(repo) == [("Harbor Gazette", 3), ("Bay Radio", 2),
                         ("Coast Weekly", 1)]


def test_only_three_sources_are_listed(repo):
    """Five sources, but the summary keeps the three biggest."""
    number = 0
    for source, count in (("A Paper", 5), ("B Radio", 4), ("C Weekly", 3),
                          ("D Digital", 2), ("E News", 1)):
        for _ in range(count):
            number += 1
            add(repo, number, source, "2020-01-01")
    names = [source for source, _ in top(repo)]
    assert names == ["A Paper", "B Radio", "C Weekly"]


def test_a_tie_goes_to_the_source_with_the_newest_document(repo):
    """Same count: the newest document date wins, not the name."""
    add(repo, 1, "Alpha Gazette", "2001-05-01")
    add(repo, 2, "Zeta Radio", "2024-03-15")
    add(repo, 3, "Mid Weekly", "2010-07-07")
    names = [source for source, _ in top(repo)]
    assert names == ["Zeta Radio", "Mid Weekly", "Alpha Gazette"]


def test_a_tie_without_dates_goes_to_the_one_added_last(repo):
    """No dates at all: the source of the newest row comes first."""
    add(repo, 1, "First Paper")
    add(repo, 2, "Second Paper")
    names = [source for source, _ in top(repo)]
    assert names == ["Second Paper", "First Paper"]


def test_a_dated_source_beats_an_undated_one_on_a_tie(repo):
    """A document with a date counts as newer than one without."""
    add(repo, 1, "Dated Paper", "1990-01-01")
    add(repo, 2, "Undated Paper")
    assert [source for source, _ in top(repo)][0] == "Dated Paper"


def test_newest_first_puts_empty_dates_last(repo):
    """sort=newest: newest date first, documents with no date at the end."""
    add(repo, 1, "Harbor Gazette", "2001-01-01")
    add(repo, 2, "Harbor Gazette")
    add(repo, 3, "Harbor Gazette", "2024-06-30")
    add(repo, 4, "Harbor Gazette", "2012-03-03")
    docs = repo.get_all_documents({"source": "Harbor Gazette",
                                   "sort": "newest"})
    assert [doc.document_date for doc in docs] == [
        "2024-06-30", "2012-03-03", "2001-01-01", None]


def test_route_filters_by_source_and_sorts_newest_first(app, flask_client):
    """GET /documents?source=X&sort=newest: only X, newest first."""
    repo = CatalogRepository(projects.catalog_path(
        app.config["PROJECT_FOLDER"]))
    add(repo, 1, "Harbor Gazette", "1998-04-01")
    add(repo, 2, "Coast Weekly", "2025-01-01")
    add(repo, 3, "Harbor Gazette", "2003-09-09")
    answer = flask_client.get(
        "/documents?source=Harbor%20Gazette&sort=newest").get_json()
    assert [doc["source"] for doc in answer] == ["Harbor Gazette"] * 2
    assert [doc["document_date"] for doc in answer] == ["2003-09-09",
                                                        "1998-04-01"]


def test_route_ignores_an_unknown_order(app, flask_client):
    """Any other sort value keeps the normal order (by id)."""
    repo = CatalogRepository(projects.catalog_path(
        app.config["PROJECT_FOLDER"]))
    add(repo, 1, "Harbor Gazette", "1998-04-01")
    add(repo, 2, "Harbor Gazette", "2003-09-09")
    answer = flask_client.get("/documents?sort=random").get_json()
    assert [doc["document_date"] for doc in answer] == ["1998-04-01",
                                                        "2003-09-09"]


def test_source_link_applies_that_source_newest_first():
    """The chat link opens Catalog with the source filter and newest first."""
    with open(CHAT_JS, encoding="utf-8") as file:
        chat = file.read()
    assert 'applyCatalogFilters({ source: source, sort: "newest" })' in chat
    assert 't("chat.show_source", { source: source })' in chat
    assert 'chatElement("button", "chat-link chat-source-link"' in chat


def test_catalog_sends_the_order_and_drops_it_on_a_manual_change():
    """Catalog passes sort to GET /documents; filters, tabs, search reset."""
    with open(CATALOG_JS, encoding="utf-8") as file:
        catalog = file.read()
    assert "sort: catalogSort," in catalog
    for control in ("filter-media-type", "filter-source", "filter-category",
                    "filter-subcategory", "sort-chip-clear"):
        assert '"{}")\n    .addEventListener("{}", reloadInNormalOrder)' \
            .format(control, "click" if control == "sort-chip-clear"
                    else "change") in catalog
    assert "searchTimer = setTimeout(reloadInNormalOrder, 300);" in catalog
