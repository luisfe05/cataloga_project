"""Tests for POST /chat and the confirmed rename."""

import json
import os
import sqlite3

import pytest

from backend.config import projects
from backend.db.catalog_repository import CatalogRepository
from backend.db.schema import init_db
from backend.models.document import Document
from backend.pipeline import chat_assistant
from backend.pipeline.naming import clean_new_name
from backend.routes import chat as chat_route


class FakeClient:
    """Stands in for an AIProviderClient and returns a fixed answer."""

    def __init__(self, answer):
        """Remember the answer and record every prompt sent."""
        self.answer = answer
        self.prompts = []

    def ask(self, system_prompt, text):
        """Return the fixed answer, like AIProviderClient.ask()."""
        self.prompts.append(text)
        return self.answer


@pytest.fixture
def repo(app):
    """Return a CatalogRepository on the same database as the app."""
    return CatalogRepository(
        projects.catalog_path(app.config["PROJECT_FOLDER"]))


@pytest.fixture
def fake_ai(monkeypatch, repo):
    """Make /chat use a FakeClient. Returns a function to set its answer."""
    repo.set_active_provider("gemini", "gemini-2.5-flash")
    client = FakeClient(None)
    monkeypatch.setattr(chat_route, "create_client",
                        lambda name, model: client)

    def set_answer(answer):
        client.answer = json.dumps(answer) if isinstance(answer, dict) \
            else answer
        return client
    return set_answer


def add_file_doc(repo, folder, filename, media_type="Press", source=None,
                 summary=None, status="Classified", document_date=None):
    """Create a real file in the project and save its document."""
    path = os.path.join(folder, media_type, filename)
    with open(path, "w") as handle:
        handle.write("content")
    return repo.add_document(Document(
        original_filename="scan_" + filename,
        filename=filename,
        media_type=media_type,
        file_path=path,
        date_added="2026-10-21T10:00:00",
        source=source,
        document_date=document_date,
        summary=summary or "Summary of " + filename,
        status=status,
    ))


def snapshot(app):
    """Return every row of the catalog and every file of the project."""
    folder = app.config["PROJECT_FOLDER"]
    conn = sqlite3.connect(projects.catalog_path(folder))
    try:
        rows = {table: conn.execute("SELECT * FROM " + table).fetchall()
                for table in ("documents", "activity_log")}
    finally:
        conn.close()
    files = sorted(os.path.relpath(os.path.join(root, name), folder)
                   for root, dirs, names in os.walk(folder)
                   for name in names if ".cataloga" not in root)
    return rows, files


@pytest.fixture
def project(app, repo):
    """A project with three real files. Returns (folder, documents)."""
    folder = app.config["PROJECT_FOLDER"]
    docs = [
        add_file_doc(repo, folder, "2026-07-15_malta.pdf",
                     source="El Nuevo Dia", document_date="2026-07-15",
                     summary="Oceanman Malta open water race results."),
        add_file_doc(repo, folder, "2026-05-02_letter.pdf",
                     media_type="Documents", source="Coach",
                     document_date="2026-05-02",
                     summary="Letter about the spring training camp."),
        add_file_doc(repo, folder, "2026-07-15_0001.jpg",
                     media_type="Photos", status="Manual Review"),
    ]
    return folder, docs


def activity(app):
    """Return (action, details) of every activity_log row."""
    conn = sqlite3.connect(
        projects.catalog_path(app.config["PROJECT_FOLDER"]))
    try:
        return conn.execute(
            "SELECT action, details FROM activity_log ORDER BY id"
        ).fetchall()
    finally:
        conn.close()


# --- POST /documents/<id>/rename ---

def test_rename_confirmed(flask_client, app, project):
    """The file and the catalog get the new name; the log keeps both."""
    folder, docs = project
    response = flask_client.post(
        "/documents/{}/rename".format(docs[0].id),
        json={"new_name": "oceanman-malta-results"})

    assert response.status_code == 200
    body = response.get_json()
    assert body["filename"] == "oceanman-malta-results.pdf"
    assert body["original_filename"] == "scan_2026-07-15_malta.pdf"
    assert os.path.isfile(os.path.join(folder, "Press",
                                       "oceanman-malta-results.pdf"))
    assert not os.path.exists(docs[0].file_path)
    assert activity(app)[-1] == (
        "Renamed", "2026-07-15_malta.pdf → oceanman-malta-results.pdf")


def test_rename_duplicate_name_gets_a_number(flask_client, project):
    """A name another file already has gets -2."""
    folder, docs = project
    open(os.path.join(folder, "Press", "results.pdf"), "w").close()
    response = flask_client.post(
        "/documents/{}/rename".format(docs[0].id),
        json={"new_name": "results"})
    assert response.get_json()["filename"] == "results-2.pdf"


def test_rename_cleans_symbols_and_keeps_extension(flask_client, project):
    """Accents and symbols are cleaned; the file keeps its extension."""
    folder, docs = project
    response = flask_client.post(
        "/documents/{}/rename".format(docs[0].id),
        json={"new_name": "Ñandú: Résumé/2026?!.docx"})
    assert response.get_json()["filename"] == "nandu-resume-2026-docx.pdf"


def test_rename_cannot_leave_the_folder(flask_client, project):
    """A name like ../../x stays a plain name in the same folder."""
    folder, docs = project
    response = flask_client.post(
        "/documents/{}/rename".format(docs[0].id),
        json={"new_name": "../../outside"})
    assert response.status_code == 200
    assert os.path.isfile(os.path.join(folder, "Press", "outside.pdf"))


def test_rename_unknown_id(flask_client):
    """A missing id gives 404."""
    response = flask_client.post("/documents/99/rename",
                                 json={"new_name": "x"})
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "not_found"


@pytest.mark.parametrize("body, status, code", [
    ({"new_name": "!!!"}, 400, "invalid_name"),
    ({}, 400, "missing_field"),
    ({"new_name": 5}, 400, "missing_field"),
])
def test_rename_bad_names(flask_client, project, body, status, code):
    """Empty after cleaning, missing, or not text: 400."""
    folder, docs = project
    response = flask_client.post(
        "/documents/{}/rename".format(docs[0].id), json=body)
    assert response.status_code == status
    assert response.get_json()["error"]["code"] == code


def test_rename_same_name_changes_nothing(flask_client, app, project):
    """The same clean name answers 200 and logs nothing."""
    folder, docs = project
    before = activity(app)
    response = flask_client.post(
        "/documents/{}/rename".format(docs[0].id),
        json={"new_name": "2026-07-15_malta.pdf"})
    assert response.status_code == 200
    assert activity(app) == before


def test_rename_file_outside_project(flask_client, repo):
    """A document whose file is outside the project folder gives 409."""
    doc = repo.add_document(Document(
        original_filename="a.pdf", filename="a.pdf", media_type="Press",
        file_path="/somewhere/else/a.pdf",
        date_added="2026-10-21T10:00:00"))
    response = flask_client.post("/documents/{}/rename".format(doc.id),
                                 json={"new_name": "b"})
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "file_missing"


def test_rename_missing_file(flask_client, project):
    """A file that is gone from the disk gives 409."""
    folder, docs = project
    os.remove(docs[0].file_path)
    response = flask_client.post(
        "/documents/{}/rename".format(docs[0].id), json={"new_name": "b"})
    assert response.status_code == 409


def test_patch_still_rejects_filename(flask_client, project):
    """PATCH never accepts filename, even with the rename route."""
    folder, docs = project
    response = flask_client.patch("/documents/{}".format(docs[0].id),
                                  json={"filename": "x.pdf"})
    assert response.status_code == 400


@pytest.mark.parametrize("path, body", [
    ("/chat", {"message": "hi"}),
    ("/documents/1/rename", {"new_name": "x"}),
])
def test_new_routes_need_the_token(app, path, body):
    """Without the session token, both new routes answer 401."""
    response = app.test_client().post(path, json=body)
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "unauthorized"


# --- clean_new_name ---

@pytest.mark.parametrize("name, expected", [
    ("Oceanman Malta Results", "oceanman-malta-results.pdf"),
    ("2026-07-15_Oceanman Malta", "2026-07-15_oceanman-malta.pdf"),
    ("malta.PDF", "malta.pdf"),
    ("report v1.2", "report-v1-2.pdf"),
    ("???", ""),
    (None, ""),
])
def test_clean_new_name(name, expected):
    """Same rules as the naming methods; the extension is the file's."""
    assert clean_new_name(name, ".pdf") == expected


# --- POST /chat: one test per action, valid and invalid ---

def chat(flask_client, message="hello", history=None):
    """Send one chat message and return the JSON answer."""
    response = flask_client.post("/chat", json={"message": message,
                                                "history": history or []})
    assert response.status_code == 200
    return response.get_json()


def test_answer_valid(flask_client, fake_ai, project):
    """A plain answer comes back with its sources as cards."""
    folder, docs = project
    fake_ai({"action": "answer", "reply": "There is one race result.",
             "sources": [docs[0].id, 999]})
    body = chat(flask_client)
    assert body["action"] == "answer"
    assert body["reply"] == "There is one race result."
    # 999 is not a document of the project, so it is dropped.
    assert [card["id"] for card in body["sources"]] == [docs[0].id]


def test_answer_without_text(flask_client, fake_ai, project):
    """An answer with no reply becomes a friendly notice."""
    fake_ai({"action": "answer", "reply": ""})
    body = chat(flask_client)
    assert body["action"] == "answer"
    assert body["notice"] == "invalid_reply"


def test_show_documents_valid(flask_client, fake_ai, project):
    """Only ids of the project become cards."""
    folder, docs = project
    fake_ai({"action": "show_documents", "reply": "Here they are.",
             "document_ids": [docs[1].id, "abc", 999, docs[1].id, True]})
    body = chat(flask_client)
    assert body["action"] == "show_documents"
    assert [card["id"] for card in body["documents"]] == [docs[1].id]
    assert body["documents"][0]["filename"] == "2026-05-02_letter.pdf"


def test_show_documents_with_no_valid_id(flask_client, fake_ai, project):
    """With no valid id left, the answer says nothing was found."""
    fake_ai({"action": "show_documents", "document_ids": [999]})
    body = chat(flask_client)
    assert body["action"] == "answer"
    assert body["notice"] == "no_documents"


def test_filter_catalog_valid(flask_client, fake_ai, project):
    """Valid filters are kept in their stored spelling; others dropped."""
    fake_ai({"action": "filter_catalog", "reply": "Press from El Nuevo Dia.",
             "filters": {"media_type": "press", "source": "el nuevo dia",
                         "status": "manual review", "text": " malta ",
                         "date_from": "2026-01-01"}})
    body = chat(flask_client)
    assert body["action"] == "filter_catalog"
    assert body["filters"] == {"media_type": "Press",
                               "source": "El Nuevo Dia",
                               "status": "Manual Review", "text": "malta"}


def test_filter_catalog_invalid(flask_client, fake_ai, project):
    """Unknown values and sources leave no filter: a notice instead."""
    fake_ai({"action": "filter_catalog",
             "filters": {"media_type": "Newspaper", "source": "Unknown",
                         "status": "Deleted"}})
    body = chat(flask_client)
    assert body["action"] == "answer"
    assert body["notice"] == "no_filters"


def test_summarize_project_valid(flask_client, fake_ai, project):
    """The numbers come from the catalog, not from the model."""
    fake_ai({"action": "summarize_project",
             "reply": "Three documents, mostly from July."})
    body = chat(flask_client)
    assert body["action"] == "summarize_project"
    assert body["project"]["total"] == 3
    assert body["project"]["manual_review"] == 1
    assert body["project"]["by_type"]["Press"] == 1
    assert body["project"]["first_date"] == "2026-05-02"


def test_summarize_project_without_text(flask_client, fake_ai, project):
    """A summary with no text becomes a notice."""
    fake_ai({"action": "summarize_project"})
    assert chat(flask_client)["notice"] == "invalid_reply"


def test_propose_rename_valid(flask_client, fake_ai, project):
    """The proposal has a clean name; nothing is renamed yet."""
    folder, docs = project
    fake_ai({"action": "propose_rename", "reply": "How about this?",
             "document_id": docs[0].id,
             "new_name": "Oceanman Malta Results"})
    body = chat(flask_client)
    assert body["action"] == "propose_rename"
    assert body["rename"] == {"document_id": docs[0].id,
                              "current_name": "2026-07-15_malta.pdf",
                              "new_name": "oceanman-malta-results.pdf"}
    assert os.path.isfile(docs[0].file_path)


@pytest.mark.parametrize("answer, notice", [
    ({"action": "propose_rename", "document_id": 999, "new_name": "x"},
     "rename_not_found"),
    ({"action": "propose_rename", "document_id": 1, "new_name": "!!!"},
     "rename_invalid"),
    ({"action": "propose_rename", "document_id": 1,
      "new_name": "2026-07-15_malta"}, "rename_same"),
])
def test_propose_rename_invalid(flask_client, fake_ai, project, answer,
                                notice):
    """Unknown id, empty name, or the same name: a notice, no card."""
    fake_ai(answer)
    body = chat(flask_client)
    assert body["action"] == "answer"
    assert body["notice"] == notice
    assert body["rename"] is None


@pytest.mark.parametrize("answer, notice", [
    ("not json at all", "invalid_reply"),
    ('```json\n{"action": "delete_file", "document_id": 1}\n```',
     "invalid_reply"),
    ('{"action": ["answer"]}', "invalid_reply"),
    ("[1, 2]", "invalid_reply"),
    (None, "ai_unavailable"),
])
def test_bad_model_answers(flask_client, fake_ai, project, answer, notice):
    """Broken JSON, unknown actions, or no answer: a friendly notice."""
    fake_ai(answer)
    body = chat(flask_client)
    assert body["action"] == "answer"
    assert body["notice"] == notice


def test_chat_without_provider(flask_client, project):
    """With no AI provider set, the chat answers with a notice."""
    assert chat(flask_client)["notice"] == "ai_unavailable"


def test_chat_needs_a_message(flask_client):
    """An empty message gives 400."""
    response = flask_client.post("/chat", json={"message": "  "})
    assert response.status_code == 400


@pytest.mark.parametrize("answer", [
    {"action": "answer", "reply": "Hi."},
    {"action": "show_documents", "document_ids": [1, 2]},
    {"action": "filter_catalog", "filters": {"media_type": "Press"}},
    {"action": "summarize_project", "reply": "Three files."},
    {"action": "propose_rename", "document_id": 1, "new_name": "renamed"},
    "garbage",
])
def test_chat_never_changes_anything(flask_client, app, fake_ai, project,
                                     answer):
    """No action of /chat changes the catalog or any file."""
    before = snapshot(app)
    fake_ai(answer)
    chat(flask_client, "rename the Malta article to renamed")
    assert snapshot(app) == before


# --- What the model receives ---

def test_context_has_project_documents_and_history(flask_client, fake_ai,
                                                   project):
    """The prompt has the summary, related documents, and 6 messages."""
    client = fake_ai({"action": "answer", "reply": "Ok."})
    history = [{"role": "user", "text": "message {}".format(number)}
               for number in range(10)]
    history.append({"role": "system", "text": "ignored"})
    chat(flask_client, "Oceanman results", history)

    prompt = json.loads(client.prompts[0])
    assert prompt["project"]["total"] == 3
    assert prompt["documents"][0]["filename"] == "2026-07-15_malta.pdf"
    assert [item["text"] for item in prompt["conversation"]] == \
        ["message {}".format(number) for number in range(5, 10)]


def test_find_documents_falls_back_to_newest(repo, app):
    """With no matching word, the newest documents are used."""
    folder = app.config["PROJECT_FOLDER"]
    for number in range(35):
        add_file_doc(repo, folder, "doc-{}.pdf".format(number))
    found = chat_assistant.find_documents(repo.get_all_documents(),
                                          "July 15")
    assert len(found) == 30
    assert found[0].filename == "doc-34.pdf"


# --- Migration ---

def test_old_catalog_gets_details_column(tmp_path):
    """A catalog made before details existed gets it, keeping its rows."""
    db_path = str(tmp_path / "old.db")
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE activity_log (id INTEGER PRIMARY KEY "
                 "AUTOINCREMENT, document_id INTEGER NOT NULL, action TEXT "
                 "NOT NULL, timestamp TEXT NOT NULL)")
    conn.execute("INSERT INTO activity_log (document_id, action, "
                 "timestamp) VALUES (1, 'Classified', '2026-10-01T10:00')")
    conn.commit()
    conn.close()

    init_db(db_path)

    conn = sqlite3.connect(db_path)
    columns = [row[1] for row in
               conn.execute("PRAGMA table_info(activity_log)")]
    rows = conn.execute("SELECT action, details FROM activity_log").fetchall()
    conn.close()
    assert "details" in columns
    assert rows == [("Classified", None)]
