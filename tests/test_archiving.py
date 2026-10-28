"""Tests for the Digital Archiving Guideline (archiving-a)."""

import sqlite3

import pytest

from backend.db.catalog_repository import CatalogRepository
from backend.db.schema import init_db
from backend.models.document import Document
from backend.pipeline import archive_rules

CATEGORIES = [
    {"name": "Contracts", "subcategories": ["Sponsorship", "Rights"]},
    {"name": "Press", "subcategories": []},
]


@pytest.fixture
def repo(tmp_path):
    """Return a CatalogRepository backed by a new temporary database."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    return CatalogRepository(db_path)


def make_doc(name="a.pdf", **fields):
    """Build a Document with only the fields a test needs."""
    return Document(original_filename=name, filename=name,
                    media_type="Documents", file_path="/archive/" + name,
                    date_added="2026-10-28T10:00:00", **fields)


# --- Migration of old catalogs ---

def make_old_catalog(path):
    """Write a catalog with the columns of the first release and one row."""
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE documents (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "original_filename TEXT NOT NULL, filename TEXT NOT NULL, "
        "media_type TEXT NOT NULL, source TEXT, document_date TEXT, "
        "summary TEXT, status TEXT NOT NULL DEFAULT 'Classified', "
        "file_path TEXT NOT NULL, date_added TEXT NOT NULL, "
        "date_classified TEXT)")
    conn.execute(
        "CREATE TABLE app_config (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "research_name TEXT NOT NULL, target_directory TEXT NOT NULL, "
        "app_lock_password_hash TEXT)")
    conn.execute(
        "INSERT INTO documents (original_filename, filename, media_type, "
        "source, file_path, date_added) VALUES ('scan.pdf', 'D_003.pdf', "
        "'Documents', 'El Mundo', '/old/D_003.pdf', '2026-09-01')")
    conn.execute("INSERT INTO app_config (research_name, target_directory)"
                 " VALUES ('Old', '/old')")
    conn.commit()
    conn.close()


def test_old_catalog_gets_new_columns_and_keeps_rows(tmp_path):
    """init_db() adds the new columns without losing the old row."""
    path = str(tmp_path / "old.db")
    make_old_catalog(path)
    init_db(path)
    repo = CatalogRepository(path)

    docs = repo.get_all_documents()
    assert len(docs) == 1
    assert docs[0].filename == "D_003.pdf"
    assert docs[0].source == "El Mundo"
    assert docs[0].keywords == []
    assert docs[0].owner is None
    assert docs[0].category is None
    config = repo.get_app_config()
    assert config["research_name"] == "Old"
    assert config["industry"] is None
    assert repo.get_categories() == []
    # A second start changes nothing.
    init_db(path)
    assert len(repo.get_all_documents()) == 1


def test_still_four_tables(tmp_path):
    """The archiving fields are columns, not new tables."""
    path = str(tmp_path / "new.db")
    init_db(path)
    conn = sqlite3.connect(path)
    names = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' "
        "AND name != 'sqlite_sequence'")}
    conn.close()
    assert names == {"documents", "activity_log", "app_config",
                     "ai_provider_config"}


# --- Saving and reading the new fields ---

def test_archive_fields_are_saved_and_read(repo):
    """Every new field comes back the same, keywords as a list."""
    doc = repo.add_document(make_doc(
        topic="Malta Olímpica", keywords=["swimming", "malta", "1964"],
        sha256="abc", counterparty="Jurutungo Films",
        confidentiality="Internal", owner="luis", category="Press"))
    saved = repo.get_document(doc.id)
    assert saved.keywords == ["swimming", "malta", "1964"]
    assert saved.topic == "Malta Olímpica"
    assert saved.counterparty == "Jurutungo Films"
    assert saved.owner == "luis"
    assert saved.to_dict()["category"] == "Press"


def test_search_finds_keywords_and_counterparty(repo):
    """Catalog search looks inside keywords and counterparty too."""
    repo.add_document(make_doc("a.pdf", keywords=["oceanman"]))
    repo.add_document(make_doc("b.pdf", counterparty="Acme Corp"))
    repo.add_document(make_doc("c.pdf"))
    assert [d.filename for d in repo.get_all_documents(
        {"search": "oceanman"})] == ["a.pdf"]
    assert [d.filename for d in repo.get_all_documents(
        {"search": "acme"})] == ["b.pdf"]


def test_filter_by_category_and_subcategory(repo):
    """GET /documents filters by category and subcategory."""
    repo.add_document(make_doc("a.pdf", category="Contracts",
                               subcategory="Rights"))
    repo.add_document(make_doc("b.pdf", category="Contracts",
                               subcategory="Sponsorship"))
    repo.add_document(make_doc("c.pdf", category="Press"))
    assert len(repo.get_all_documents({"category": "Contracts"})) == 2
    assert [d.filename for d in repo.get_all_documents(
        {"category": "Contracts", "subcategory": "Rights"})] == ["a.pdf"]


def test_find_by_sha256_skips_duplicate_rows(repo):
    """The hash points to the first real document, never to a duplicate."""
    first = repo.add_document(make_doc("a.pdf", sha256="h1"))
    repo.add_document(make_doc("b.pdf", sha256="h1", duplicate_of="a.pdf"))
    assert repo.find_by_sha256("h1").id == first.id
    assert repo.find_by_sha256("other") is None


def test_delete_document_removes_row_and_activity(repo):
    """delete_document() removes the row and its log lines."""
    doc = repo.add_document(make_doc("a.pdf", duplicate_of="b.pdf"))
    assert len(repo.get_duplicates()) == 1
    repo.delete_document(doc.id)
    assert repo.get_document(doc.id) is None
    assert repo.get_dashboard_stats()["recent_activity"] == []


def test_categories_and_industry_are_saved(repo):
    """The project keeps its industry and category list."""
    repo.save_app_config("Research", "/research")
    repo.save_industry("Sports media")
    repo.save_categories(CATEGORIES)
    assert repo.get_app_config()["industry"] == "Sports media"
    assert repo.get_categories() == CATEGORIES


# --- Edit Mode (PATCH) checks ---

def test_patch_keywords_from_list_or_text(repo):
    """Keywords can come as a list or as comma separated text."""
    doc = repo.add_document(make_doc())
    saved = repo.update_document(doc.id, {"keywords": "a, b ,c"})
    assert saved.keywords == ["a", "b", "c"]
    saved = repo.update_document(doc.id, {"keywords": []})
    assert saved.keywords == []


@pytest.mark.parametrize("fields", [
    {"keywords": ["a", "b", "c", "d", "e", "f"]},
    {"keywords": ["x" * 41]},
    {"counterparty": "x" * 101},
    {"confidentiality": "Secret"},
    {"effective_start": "15/07/2026"},
    {"effective_start": "2026-08-01", "effective_end": "2026-07-01"},
    {"category": "Invented"},
])
def test_patch_refuses_bad_archive_values(repo, fields):
    """Each new field is checked before it is saved."""
    repo.save_categories(CATEGORIES)
    doc = repo.add_document(make_doc())
    with pytest.raises(ValueError):
        repo.update_document(doc.id, fields)


def test_patch_accepts_good_archive_values(repo):
    """Valid values are saved; empty dates become None."""
    repo.save_categories(CATEGORIES)
    doc = repo.add_document(make_doc())
    saved = repo.update_document(doc.id, {
        "confidentiality": "Restricted", "owner": "ana",
        "effective_start": "2026-01-01", "effective_end": "",
        "category": "Contracts", "subcategory": "Rights",
        "counterparty": "Acme"})
    assert saved.confidentiality == "Restricted"
    assert saved.effective_start == "2026-01-01"
    assert saved.effective_end is None
    assert (saved.category, saved.subcategory) == ("Contracts", "Rights")


def test_old_category_value_is_kept_after_list_changes(repo):
    """A value that left the list stays, and can be saved again."""
    doc = repo.add_document(make_doc(category="Old category"))
    repo.save_categories(CATEGORIES)
    saved = repo.update_document(doc.id, {"category": "Old category",
                                          "summary": "Same."})
    assert saved.category == "Old category"


def test_subcategory_must_belong_to_the_category(repo):
    """A subcategory of another category is refused."""
    repo.save_categories(CATEGORIES)
    doc = repo.add_document(make_doc(category="Press"))
    with pytest.raises(ValueError):
        repo.update_document(doc.id, {"subcategory": "Rights"})


# --- archive_rules helpers ---

def test_sha256_of_matches_for_same_content(tmp_path):
    """Two files with the same bytes have the same hash."""
    one = tmp_path / "one.txt"
    two = tmp_path / "two.txt"
    one.write_text("same")
    two.write_text("same")
    assert archive_rules.sha256_of(str(one)) == \
        archive_rules.sha256_of(str(two))
    assert len(archive_rules.sha256_of(str(one))) == 64


def test_clean_keywords_from_ai():
    """AI keywords: up to 5, 40 characters, no repeats, no blanks."""
    result = archive_rules.clean_keywords(
        ["Malta", "malta", "", None, "x" * 50, "b", "c", "d", "e"])
    assert result == ["Malta", "x" * 40, "b", "c", "d"]
    assert archive_rules.clean_keywords("not a list") == []


def test_clean_categories_rules():
    """Categories: names required, no repeats, at most 10."""
    result = archive_rules.clean_categories([
        {"name": " Contracts ", "subcategories": ["A", "a", ""]},
        {"name": "contracts"},
        {"name": ""},
    ])
    assert result == [{"name": "Contracts", "subcategories": ["A"]}]
    with pytest.raises(ValueError):
        archive_rules.clean_categories(
            [{"name": str(n)} for n in range(11)])
    with pytest.raises(ValueError):
        archive_rules.clean_categories("Contracts")


@pytest.mark.parametrize("category, subcategory, expected", [
    ("contracts", "rights", ("Contracts", "Rights", None)),
    ("Press", None, ("Press", None, None)),
    ("Contracts", "Other", ("Contracts", None,
                            archive_rules.NO_CATEGORY_NOTE)),
    ("Invented", None, (None, None, archive_rules.NO_CATEGORY_NOTE)),
    (None, None, (None, None, archive_rules.NO_CATEGORY_NOTE)),
])
def test_match_category(category, subcategory, expected):
    """The AI's choice must come from the project list."""
    assert archive_rules.match_category(
        CATEGORIES, category, subcategory) == expected


def test_match_category_without_a_list():
    """A project with no categories leaves them empty, with no note."""
    assert archive_rules.match_category([], "Press", None) == \
        (None, None, None)
