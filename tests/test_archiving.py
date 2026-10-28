"""Tests for the Digital Archiving Guideline (archiving-a)."""

import json
import os
import sqlite3

import pytest

from backend import folder_watcher
from backend.config import account
from backend.db.catalog_repository import CatalogRepository
from backend.db.schema import init_db
from backend.models.document import Document
from backend.pipeline import archive_rules, chat_assistant, naming
from backend.pipeline.ai_providers import base
from backend.pipeline.ai_providers.base import AIProviderClient
from backend.pipeline.classification_pipeline import (
    ClassificationPipeline, remove_gone_duplicates)
from backend.pipeline.file_organizer import FileOrganizer
from backend.routes import settings as settings_routes
from tests.conftest import make_project

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


# --- Naming method 4 ---

def test_method_4_name():
    """Method 4: topic, source, date, and the topic's own number."""
    parts = naming.build_parts("scan.pdf", 7, document_date="2026-07-15",
                               source="El Nuevo Día",
                               topic="Oceanman Malta", topic_number=1)
    assert naming.make_filename(naming.NEW_PROJECT_TEMPLATE, parts,
                                ".pdf") == \
        "oceanman-malta_el-nuevo-dia_2026-07-15_001.pdf"


def test_method_4_without_source_or_date():
    """No source leaves that part out; no date gives 'undated'."""
    parts = naming.build_parts("scan.pdf", 7, topic="Oceanman Malta",
                               topic_number=12)
    assert naming.make_filename(naming.NEW_PROJECT_TEMPLATE, parts,
                                ".pdf") == "oceanman-malta_undated_012.pdf"


def test_topic_number_goes_to_4_digits():
    """After 999 the topic number simply has 4 digits."""
    parts = naming.build_parts("a.pdf", 1, topic="x", topic_number=1000)
    assert parts["topic_number"] == "1000"


def test_next_topic_number_counts_the_same_topic():
    """Topics that give the same slug count together."""
    saved = ["Oceanman Malta", "oceanman málta", "Other"]
    assert naming.next_topic_number("Oceanman Malta", saved) == 3
    assert naming.next_topic_number("New topic", saved) == 1


def test_topic_number_token_in_custom_template():
    """{topic_number} is valid in a custom template; {number} too."""
    assert naming.validate_template("{number}_{topic_number}") is None


def test_old_projects_keep_method_1_as_fallback():
    """Only new projects get method 4; the fallback stays method 1."""
    assert naming.DEFAULT_TEMPLATE == "{date}_{topic}"
    assert naming.NEW_PROJECT_TEMPLATE == \
        "{topic}_{source}_{date}_{topic_number}"


# --- Pipeline ---

FULL_METADATA = json.dumps({
    "source": "El Nuevo Día", "document_date": "2026-07-15",
    "topic": "Oceanman Malta",
    "keywords": ["swimming", "Malta", "malta", "x" * 60, "", "a", "b"],
    "counterparty": "Jurutungo Films",
    "category": "contracts", "subcategory": "rights"})


class RecordingAI(AIProviderClient):
    """Fake AI that answers each kind of request and keeps the prompts."""

    def __init__(self, metadata=FULL_METADATA):
        super().__init__(provider_name="fake", model="fake-model")
        self.retry_delay = 0
        self.metadata = metadata
        self.prompts = []

    def send_prompt(self, system_prompt, text):
        self.prompts.append(system_prompt)
        if system_prompt == base.CLASSIFICATION_PROMPT:
            return "Press"
        if system_prompt == base.SUMMARY_PROMPT:
            return "A news story."
        return self.metadata


@pytest.fixture
def pipe(tmp_path, monkeypatch, repo):
    """A pipeline with a fake AI, an archive folder, and a Drop Zone."""
    monkeypatch.setattr(base.keyring, "get_password",
                        lambda service, name: "test-key")
    drop_zone = tmp_path / "archive" / "Drop Zone"
    drop_zone.mkdir(parents=True)
    ai = RecordingAI()
    pipeline = ClassificationPipeline(
        ai, repo, FileOrganizer(str(tmp_path / "archive")), owner="luis")
    repo.save_naming_template(naming.NEW_PROJECT_TEMPLATE)
    return {"pipeline": pipeline, "ai": ai, "repo": repo,
            "drop_zone": drop_zone}


def drop(pipe, name, text):
    """Put a text file in the Drop Zone and return its path."""
    path = pipe["drop_zone"] / name
    path.write_text(text)
    return str(path)


def test_new_file_gets_all_archive_fields(pipe):
    """One metadata call fills topic, keywords, counterparty, category."""
    pipe["repo"].save_categories(CATEGORIES)
    doc = pipe["pipeline"].classify_document(
        drop(pipe, "a.txt", "Contract text"))
    assert doc.filename == "oceanman-malta_el-nuevo-dia_2026-07-15_001.txt"
    assert doc.keywords == ["swimming", "Malta", "x" * 40, "a", "b"]
    assert doc.counterparty == "Jurutungo Films"
    assert (doc.category, doc.subcategory) == ("Contracts", "Rights")
    assert doc.confidentiality == "Internal"
    assert doc.owner == "luis"
    assert len(doc.sha256) == 64
    assert doc.status == "Classified"
    # Classification, summary, metadata: no extra AI call.
    assert len(pipe["ai"].prompts) == 3
    assert "Contracts" in pipe["ai"].prompts[2]


def test_second_file_of_a_topic_gets_002(pipe):
    """The topic number counts files with the same topic."""
    pipe["pipeline"].classify_document(drop(pipe, "a.txt", "One"))
    second = pipe["pipeline"].classify_document(drop(pipe, "b.txt", "Two"))
    assert second.filename.endswith("_002.txt")


def test_no_categories_leaves_category_empty(pipe):
    """Without a project list, no category and no Manual Review."""
    doc = pipe["pipeline"].classify_document(drop(pipe, "a.txt", "Text"))
    assert doc.category is None
    assert doc.review_note is None
    assert doc.status == "Classified"
    assert "categories" not in pipe["ai"].prompts[2]


def test_category_not_in_list_goes_to_manual_review(pipe):
    """A category outside the project list needs a person."""
    pipe["repo"].save_categories([{"name": "Press", "subcategories": []}])
    doc = pipe["pipeline"].classify_document(drop(pipe, "a.txt", "Text"))
    assert doc.category is None
    assert doc.status == "Manual Review"
    assert doc.review_note == archive_rules.NO_CATEGORY_NOTE


def test_bad_ai_values_are_dropped(pipe):
    """Wrong types from the AI never reach the database."""
    pipe["ai"].metadata = json.dumps({
        "source": "S", "document_date": "2026", "topic": "T",
        "keywords": "not a list", "counterparty": ["x"]})
    doc = pipe["pipeline"].classify_document(drop(pipe, "a.txt", "Text"))
    assert doc.keywords == []
    assert doc.counterparty is None


def test_duplicate_skips_the_ai_and_stays_in_drop_zone(pipe):
    """Same bytes: no AI, no rename, no move, a Manual Review row."""
    first = pipe["pipeline"].classify_document(drop(pipe, "a.txt", "Same"))
    calls = len(pipe["ai"].prompts)
    copy = drop(pipe, "copy.txt", "Same")
    doc = pipe["pipeline"].classify_document(copy)

    assert len(pipe["ai"].prompts) == calls
    assert os.path.isfile(copy)
    assert doc.file_path == copy
    assert doc.filename == "copy.txt"
    assert doc.status == "Manual Review"
    assert doc.duplicate_of == first.filename
    assert doc.review_note == "Duplicate of " + first.filename
    assert doc.media_type == "Documents"


def test_duplicate_photo_type_comes_from_extension(pipe):
    """A duplicate keeps the media type its extension gives."""
    photo = pipe["drop_zone"] / "p.jpg"
    photo.write_bytes(b"jpeg bytes")
    pipe["pipeline"].classify_document(str(photo))
    again = pipe["drop_zone"] / "p2.jpg"
    again.write_bytes(b"jpeg bytes")
    assert pipe["pipeline"].classify_document(str(again)).media_type == \
        "Photos"


def test_duplicate_is_not_hashed_twice(pipe, monkeypatch):
    """A duplicate row's path is skipped before the hash."""
    pipe["pipeline"].classify_document(drop(pipe, "a.txt", "Same"))
    copy = drop(pipe, "copy.txt", "Same")
    pipe["pipeline"].process_batch([copy])
    hashed = []
    monkeypatch.setattr(archive_rules, "sha256_of",
                        lambda path: hashed.append(path))
    assert pipe["pipeline"].process_batch([copy]) == []
    assert hashed == []


def test_gone_duplicate_row_is_removed(pipe):
    """When the user deletes the duplicate, only its row goes."""
    first = pipe["pipeline"].classify_document(drop(pipe, "a.txt", "Same"))
    copy = drop(pipe, "copy.txt", "Same")
    duplicate = pipe["pipeline"].classify_document(copy)

    remove_gone_duplicates(pipe["repo"])
    assert pipe["repo"].get_document(duplicate.id) is not None
    os.remove(copy)
    remove_gone_duplicates(pipe["repo"])
    assert pipe["repo"].get_document(duplicate.id) is None
    assert os.path.isfile(first.file_path)


def test_old_rows_without_hash_are_not_compared(pipe):
    """Old documents have no sha256, so a copy of them is a new file."""
    pipe["repo"].add_document(make_doc("old.txt"))
    doc = pipe["pipeline"].classify_document(drop(pipe, "a.txt", "Text"))
    assert doc.duplicate_of is None


# --- Watcher ---

def test_watcher_sets_owner_and_cleans_duplicates(tmp_path, monkeypatch):
    """The scan uses the account's username and drops gone duplicates."""
    monkeypatch.setattr(base.keyring, "get_password",
                        lambda service, name: "test-key")
    monkeypatch.setattr(folder_watcher, "create_client",
                        lambda name, model: RecordingAI())
    projects_path = str(tmp_path / "app" / "projects.json")
    repo = make_project(projects_path, tmp_path / "Research")
    repo.set_active_provider("gemini", "gemini-2.5-flash")
    account.save_account(account.account_path_for(projects_path),
                         "luis", "password123")
    drop_zone = tmp_path / "Research" / "Drop Zone"
    (drop_zone / "a.txt").write_text("Same")

    first = folder_watcher.scan_once(projects_path)
    assert first[0].owner == "luis"
    (drop_zone / "copy.txt").write_text("Same")
    duplicate = folder_watcher.scan_once(projects_path)[0]
    assert duplicate.duplicate_of == first[0].filename

    os.remove(str(drop_zone / "copy.txt"))
    assert folder_watcher.scan_once(projects_path) == []
    assert repo.get_document(duplicate.id) is None


# --- Routes ---

def active_repo(app):
    """Return the repository of the app fixture's active project."""
    return CatalogRepository(os.path.join(
        app.config["PROJECT_FOLDER"], ".cataloga", "catalog.db"))


def test_put_settings_saves_industry_and_categories(flask_client):
    """Save keeps the industry and the cleaned category list."""
    response = flask_client.put("/settings", json={
        "research_name": "Research", "industry": " Sports media ",
        "categories": [{"name": "Contracts", "subcategories": ["Rights"]},
                       {"name": "contracts"}]})
    assert response.status_code == 200
    data = flask_client.get("/settings").get_json()
    assert data["industry"] == "Sports media"
    assert data["categories"] == [{"name": "Contracts",
                                   "subcategories": ["Rights"]}]


def test_put_settings_refuses_bad_categories(flask_client):
    """A category list in the wrong shape is refused with 400."""
    response = flask_client.put("/settings", json={
        "research_name": "Research", "categories": "Contracts"})
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_categories"


class SuggestAI(AIProviderClient):
    """Fake AI that answers the category request."""

    def __init__(self, answer):
        super().__init__(provider_name="fake", model="fake-model")
        self.api_key = "test-key"
        self.answer = answer

    def send_prompt(self, system_prompt, text):
        return self.answer


@pytest.mark.parametrize("answer, count", [
    ('```json\n[{"name": "Contracts", "subcategories": ["Rights"]}]\n```',
     1),
    (json.dumps([{"name": str(n)} for n in range(14)]), 10),
])
def test_suggest_categories(flask_client, app, monkeypatch, answer, count):
    """Suggest returns a checked list and saves nothing."""
    monkeypatch.setattr(settings_routes, "create_client",
                        lambda name, model: SuggestAI(answer))
    active_repo(app).set_active_provider("gemini", "gemini-2.5-flash")
    response = flask_client.post("/settings/categories/suggest",
                                 json={"industry": "Sports media"})
    assert response.status_code == 200
    assert len(response.get_json()["categories"]) == count
    assert flask_client.get("/settings").get_json()["categories"] == []


def test_suggest_categories_bad_answer(flask_client, app, monkeypatch):
    """No usable list from the AI gives a clear error."""
    monkeypatch.setattr(settings_routes, "create_client",
                        lambda name, model: SuggestAI("I cannot help."))
    active_repo(app).set_active_provider("gemini", "gemini-2.5-flash")
    response = flask_client.post("/settings/categories/suggest",
                                 json={"industry": "Sports media"})
    assert response.status_code == 502
    assert response.get_json()["error"]["code"] == "suggest_failed"


def test_suggest_categories_needs_industry(flask_client):
    """The industry field is required."""
    response = flask_client.post("/settings/categories/suggest", json={})
    assert response.status_code == 400


def test_documents_route_filters_by_category(flask_client, app):
    """GET /documents accepts category and subcategory."""
    repo = active_repo(app)
    repo.add_document(make_doc("a.pdf", category="Contracts",
                               subcategory="Rights"))
    repo.add_document(make_doc("b.pdf", category="Press"))
    response = flask_client.get(
        "/documents?category=Contracts&subcategory=Rights")
    assert [d["filename"] for d in response.get_json()] == ["a.pdf"]


def test_patch_route_edits_archive_fields(flask_client, app):
    """PATCH saves the new fields and refuses bad ones with 400."""
    doc = active_repo(app).add_document(make_doc())
    response = flask_client.patch("/documents/{}".format(doc.id), json={
        "keywords": ["malta", "swim"], "confidentiality": "Public"})
    assert response.status_code == 200
    assert response.get_json()["keywords"] == ["malta", "swim"]
    response = flask_client.patch("/documents/{}".format(doc.id), json={
        "confidentiality": "Top secret"})
    assert response.status_code == 400


def test_export_has_keywords_in_one_cell(flask_client, app):
    """Keywords are exported as 'a; b'."""
    active_repo(app).add_document(make_doc(keywords=["a", "b"]))
    text = flask_client.get("/documents/export").get_data(as_text=True)
    assert "a; b" in text


# --- Chat ---

def test_chat_finds_documents_by_keyword():
    """The chat picks documents whose keywords match the message."""
    match = make_doc("a.pdf", keywords=["oceanman"])
    match.id = 1
    other = make_doc("b.pdf")
    other.id = 2
    found = chat_assistant.find_documents([other, match],
                                          "find oceanman files")
    assert found == [match]


def test_chat_card_shows_keywords_and_category():
    """The cards sent to the model carry the new fields."""
    doc = make_doc(keywords=["malta"], category="Press")
    card = chat_assistant.document_card(doc)
    assert card["keywords"] == ["malta"]
    assert card["category"] == "Press"
