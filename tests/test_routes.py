"""Integration tests for Flask routes using the test client."""

import os
import shutil

import pytest
from keyring.errors import KeyringError

from backend.config import projects
from backend.db.catalog_repository import CatalogRepository
from backend.models.document import Document
from backend.pipeline.ai_providers import base
from backend.pipeline.ai_providers.gemini import GeminiClient


@pytest.fixture
def repo(app):
    """Return a CatalogRepository on the same database as the app."""
    return CatalogRepository(
        projects.catalog_path(app.config["PROJECT_FOLDER"]))


@pytest.fixture
def fake_keyring(monkeypatch):
    """Replace the OS keyring with a dict, and return that dict."""
    saved = {}
    monkeypatch.setattr(base.keyring, "set_password",
                        lambda service, name, key: saved.update({name: key}))
    monkeypatch.setattr(base.keyring, "get_password",
                        lambda service, name: saved.get(name))
    return saved


def add_doc(repo, filename, media_type="Documents", source=None,
            status="Classified"):
    """Save one document directly through the repository."""
    return repo.add_document(Document(
        original_filename="orig_" + filename,
        filename=filename,
        media_type=media_type,
        file_path="/archive/" + media_type + "/" + filename,
        date_added="2026-10-21T10:00:00",
        source=source,
        summary="Summary of " + filename,
        status=status,
    ))


def assert_error(response, status, code):
    """Check the shared error shape: {"error": {"code", "message"}}."""
    assert response.status_code == status
    body = response.get_json()
    assert body["error"]["code"] == code
    assert body["error"]["message"]


# --- /documents ---

def test_list_documents_empty(flask_client):
    """With no documents the list is empty, not an error."""
    response = flask_client.get("/documents")
    assert response.status_code == 200
    assert response.get_json() == []


def test_list_documents_with_filter(flask_client, repo):
    """Query params filter the list."""
    add_doc(repo, "D_001.pdf")
    add_doc(repo, "PR_001.pdf", media_type="Press")
    response = flask_client.get("/documents?media_type=Press")
    assert response.status_code == 200
    assert [doc["filename"] for doc in response.get_json()] == ["PR_001.pdf"]


def test_get_document(flask_client, repo):
    """One document comes back as a JSON object."""
    add_doc(repo, "D_001.pdf")
    response = flask_client.get("/documents/1")
    assert response.status_code == 200
    assert response.get_json()["filename"] == "D_001.pdf"


def test_get_document_not_found(flask_client):
    """A missing id gives 404 in the shared error shape."""
    assert_error(flask_client.get("/documents/99"), 404, "not_found")


def test_patch_document(flask_client, repo):
    """An editable field is updated and the new document returned."""
    add_doc(repo, "D_001.pdf")
    response = flask_client.patch("/documents/1",
                                  json={"source": "Claridad"})
    assert response.status_code == 200
    assert response.get_json()["source"] == "Claridad"


def test_patch_locked_field(flask_client, repo):
    """Changing a locked field gives 400."""
    add_doc(repo, "D_001.pdf")
    response = flask_client.patch("/documents/1", json={"filename": "x.pdf"})
    assert_error(response, 400, "invalid_field")


def test_patch_not_found(flask_client):
    """Patching a missing id gives 404."""
    response = flask_client.patch("/documents/99", json={"source": "A"})
    assert_error(response, 404, "not_found")


def test_patch_invalid_body(flask_client, repo):
    """A body that is not a JSON object gives 400."""
    add_doc(repo, "D_001.pdf")
    response = flask_client.patch("/documents/1", data="not json",
                                  content_type="application/json")
    assert_error(response, 400, "invalid_body")


def test_export_csv(flask_client, repo):
    """The export is a CSV file download with a header row."""
    add_doc(repo, "D_001.pdf", source="Archive A")
    response = flask_client.get("/documents/export")
    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert "attachment" in response.headers["Content-Disposition"]
    lines = response.get_data(as_text=True).strip().splitlines()
    assert lines[0] == ("Original Filename,Filename,Media Type,Source,"
                        "Date,Date Source,Summary,Status,Topic,Keywords,"
                        "Category,"
                        "Subcategory,Counterparty,Confidentiality,Owner,"
                        "Effective Start,Effective End,Duplicate Of,"
                        "Review Note,Suggested Folder,SHA-256")
    assert "D_001.pdf" in lines[1]


def test_export_uses_filters(flask_client, repo):
    """The export only includes documents that match the filters."""
    add_doc(repo, "D_001.pdf")
    add_doc(repo, "D_002.pdf", status="Manual Review")
    response = flask_client.get("/documents/export?status=Manual%20Review")
    text = response.get_data(as_text=True)
    assert "D_002.pdf" in text
    assert "D_001.pdf" not in text


def test_export_unsupported_format(flask_client):
    """Only csv is supported for now."""
    response = flask_client.get("/documents/export?format=pdf")
    assert_error(response, 400, "unsupported_format")


# --- /dashboard/stats ---

def test_dashboard_stats(flask_client, repo):
    """The stats endpoint returns the counts from the repository."""
    add_doc(repo, "D_001.pdf", source="Archive A")
    add_doc(repo, "D_002.pdf", status="Manual Review")
    response = flask_client.get("/dashboard/stats")
    assert response.status_code == 200
    stats = response.get_json()
    assert stats["documents_classified"] == 1
    assert stats["needs_manual_review"] == 1
    assert stats["media_type_breakdown"]["Documents"] == 2
    assert len(stats["recent_activity"]) == 2


# --- /settings ---

def test_get_settings_of_the_active_project(flask_client, app):
    """Settings come from the active project's catalog."""
    response = flask_client.get("/settings")
    assert response.status_code == 200
    assert response.get_json() == {
        "research_name": "Research",
        "target_directory": app.config["PROJECT_FOLDER"],
        "language": "en", "naming_template": "{date}_{topic}",
        "active_provider": None, "active_model": None,
        "old_inbox_has_files": False, "project_status": "ok",
        "providers_with_key": [], "username": "test",
        "industry": "", "categories": [],
        "folder_mode": "media", "project_description": "",
        "folder_counts": {},
    }


def test_get_settings_with_no_project(empty_client):
    """Before the first project, the project fields are empty."""
    settings = empty_client.get("/settings").get_json()
    assert settings["project_status"] == "none"
    assert settings["research_name"] == ""
    assert settings["target_directory"] == ""
    assert settings["language"] == "en"


def test_put_settings_renames_the_project(flask_client, app):
    """The name changes in the catalog and in the project list."""
    response = flask_client.put("/settings", json={
        "research_name": "El Delfin"})
    assert response.status_code == 200
    assert response.get_json()["research_name"] == "El Delfin"
    names = [p["name"] for p in
             flask_client.get("/projects").get_json()["projects"]]
    assert names == ["El Delfin"]


def test_put_settings_never_changes_the_folder(flask_client, app, tmp_path):
    """A target_directory in the body is ignored: the folder is fixed."""
    other = tmp_path / "Other"
    other.mkdir()
    flask_client.put("/settings", json={
        "research_name": "A", "target_directory": str(other)})
    assert flask_client.get("/settings").get_json()["target_directory"] \
        == app.config["PROJECT_FOLDER"]


def test_put_settings_missing_name(flask_client):
    """The project name is required."""
    response = flask_client.put("/settings", json={"naming_template": "x"})
    assert_error(response, 400, "missing_field")


def test_put_settings_with_no_project(empty_client):
    """Project settings need a project."""
    response = empty_client.put("/settings", json={"research_name": "A"})
    assert_error(response, 409, "no_project")


def test_language_is_global(empty_client, tmp_path):
    """The language is saved before any project and kept after."""
    response = empty_client.put("/settings", json={"language": "es"})
    assert response.status_code == 200
    folder = tmp_path / "New"
    folder.mkdir()
    empty_client.post("/projects", json={"name": "New",
                                         "folder": str(folder)})
    assert empty_client.get("/settings").get_json()["language"] == "es"


def test_put_settings_language_only_rejects_unknown(flask_client):
    """Only 'en' and 'es' are accepted."""
    response = flask_client.put("/settings", json={"language": "fr"})
    assert_error(response, 400, "invalid_language")
    assert flask_client.get("/settings").get_json()["language"] == "en"


def test_put_settings_saves_name_template_and_language(flask_client):
    """All three can be saved together."""
    response = flask_client.put("/settings", json={
        "research_name": "A", "naming_template": "{source}_{date}_{topic}",
        "language": "es"})
    assert response.status_code == 200
    settings = response.get_json()
    assert settings["naming_template"] == "{source}_{date}_{topic}"
    assert settings["language"] == "es"
    assert settings["research_name"] == "A"


@pytest.mark.parametrize("template, reason, token", [
    ("", "empty", ""),
    ("my-files", "no_token", ""),
    ("{date}_{titulo}", "unknown", "{titulo}"),
    ("{date}/{topic}", "chars", ""),
])
def test_put_settings_rejects_bad_template(flask_client, template, reason,
                                           token):
    """A bad template is rejected before anything is saved."""
    response = flask_client.put("/settings", json={
        "research_name": "Changed", "naming_template": template})
    assert_error(response, 400, "invalid_template")
    error = response.get_json()["error"]
    assert error["reason"] == reason
    assert error["token"] == token
    settings = flask_client.get("/settings").get_json()
    assert settings["naming_template"] == "{date}_{topic}"
    assert settings["research_name"] == "Research"


def test_get_settings_reports_old_inbox_files(flask_client, app):
    """GET /settings tells Catalog when the old Inbox still has files."""
    folder = app.config["PROJECT_FOLDER"]
    assert flask_client.get("/settings").get_json()[
        "old_inbox_has_files"] is False
    os.makedirs(os.path.join(folder, "Inbox"))
    with open(os.path.join(folder, "Inbox", "left.pdf"), "w") as file:
        file.write("x")
    assert flask_client.get("/settings").get_json()[
        "old_inbox_has_files"] is True


def test_put_settings_migrates_old_inbox(flask_client, app):
    """Saving the project renames an old Inbox to Drop Zone."""
    folder = app.config["PROJECT_FOLDER"]
    # Simulate a project made with the old version.
    os.rename(os.path.join(folder, "Drop Zone"),
              os.path.join(folder, "Inbox"))
    with open(os.path.join(folder, "Inbox", "clip.pdf"), "w") as file:
        file.write("x")
    response = flask_client.put("/settings", json={"research_name": "A"})
    assert response.status_code == 200
    assert not os.path.exists(os.path.join(folder, "Inbox"))
    assert os.path.isfile(os.path.join(folder, "Drop Zone", "clip.pdf"))


def test_documents_need_a_project(empty_client):
    """With no project, the document and dashboard routes say so."""
    assert_error(empty_client.get("/documents"), 409, "no_project")
    assert_error(empty_client.get("/dashboard/stats"), 409, "no_project")


def test_missing_project_folder_is_unavailable(flask_client, app):
    """A disconnected drive gives project_unavailable with the path."""
    shutil.rmtree(app.config["PROJECT_FOLDER"])
    response = flask_client.get("/documents")
    assert_error(response, 409, "project_unavailable")
    assert response.get_json()["error"]["path"] == \
        app.config["PROJECT_FOLDER"]
    assert flask_client.get("/settings").get_json()["project_status"] == \
        "unavailable"


# --- /settings/ai-provider ---

def test_put_ai_provider_saves_key_in_keyring(flask_client, fake_keyring):
    """The key goes to the keyring and is never sent back."""
    response = flask_client.put("/settings/ai-provider", json={
        "provider_name": "gemini", "model": "gemini-2.5-flash",
        "api_key": "secret-key"})
    assert response.status_code == 200
    assert "secret-key" not in response.get_data(as_text=True)
    assert fake_keyring == {"gemini": "secret-key"}

    settings = flask_client.get("/settings").get_json()
    assert settings["active_provider"] == "gemini"
    assert settings["active_model"] == "gemini-2.5-flash"
    assert "secret-key" not in str(settings)


def test_put_ai_provider_keyring_failure(flask_client, monkeypatch):
    """A keychain error gives a clear 400 and keeps the provider."""
    def refuse(service, name, key):
        raise KeyringError("Can't store password on keychain: (-25244)")
    monkeypatch.setattr(base.keyring, "set_password", refuse)
    response = flask_client.put("/settings/ai-provider", json={
        "provider_name": "groq", "model": "llama-3.1-8b-instant",
        "api_key": "secret-key"})
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "keyring_failed"
    assert flask_client.get("/settings").get_json()[
        "active_provider"] is None


def test_get_settings_lists_providers_with_key(flask_client, fake_keyring):
    """Only provider names are sent, never the keys themselves."""
    fake_keyring["groq"] = "secret-key"
    response = flask_client.get("/settings")
    assert response.get_json()["providers_with_key"] == ["groq"]
    assert b"secret-key" not in response.data


def test_get_settings_counts_ollama_development_key(flask_client,
                                                    monkeypatch):
    """The .env key makes Ollama Cloud ready and is never sent."""
    monkeypatch.setenv("OLLAMA_API_KEY", "dev-key")
    response = flask_client.get("/settings")
    assert response.get_json()["providers_with_key"] == ["ollama"]
    assert b"dev-key" not in response.data


def test_put_ai_provider_needs_a_project(empty_client, fake_keyring):
    """The provider is saved per project, so it needs one."""
    response = empty_client.put("/settings/ai-provider", json={
        "provider_name": "gemini", "model": "gemini-2.5-flash",
        "api_key": "k"})
    assert_error(response, 409, "no_project")


def test_put_ai_provider_unsupported(flask_client, fake_keyring):
    """An unknown provider gives 400 and saves nothing."""
    response = flask_client.put("/settings/ai-provider", json={
        "provider_name": "skynet", "model": "x", "api_key": "k"})
    assert_error(response, 400, "unsupported_provider")
    assert fake_keyring == {}


def test_test_ai_provider_success(flask_client, fake_keyring, monkeypatch):
    """A working key gives {"connected": true}, and is not saved."""
    monkeypatch.setattr(GeminiClient, "send_prompt",
                        lambda self, prompt, text: "OK")
    response = flask_client.post("/settings/ai-provider/test", json={
        "provider_name": "gemini", "model": "gemini-2.5-flash",
        "api_key": "test-key"})
    assert response.status_code == 200
    assert response.get_json() == {"connected": True}
    assert fake_keyring == {}


def test_test_ai_provider_failure(flask_client, fake_keyring, monkeypatch):
    """The provider's error message reaches the user."""
    def fail(self, prompt, text):
        raise RuntimeError("API key not valid")

    monkeypatch.setattr(GeminiClient, "send_prompt", fail)
    response = flask_client.post("/settings/ai-provider/test", json={
        "provider_name": "gemini", "model": "gemini-2.5-flash",
        "api_key": "bad-key"})
    assert_error(response, 400, "connection_failed")
    assert "API key not valid" in response.get_json()["error"]["message"]


def test_test_ai_provider_without_key(flask_client, fake_keyring):
    """With no key typed and none saved, the test fails clearly."""
    response = flask_client.post("/settings/ai-provider/test", json={
        "provider_name": "gemini", "model": "gemini-2.5-flash"})
    assert_error(response, 400, "connection_failed")


def setup_project_with_text_doc(flask_client, repo, tmp_path, fake_keyring):
    """Set the AI provider and add one document that has a text file."""
    folder = tmp_path / "Research"
    flask_client.put("/settings/ai-provider", json={
        "provider_name": "gemini", "model": "gemini-2.5-flash",
        "api_key": "test-key"})
    text_file = folder / "Documents" / "D_001.txt"
    text_file.write_text("A letter about a swim meet.")
    return repo.add_document(Document(
        original_filename="letter.txt", filename="D_001.txt",
        media_type="Documents", file_path=str(text_file),
        date_added="2026-10-21T10:00:00", summary="Old summary.",
        status="Manual Review"))


def test_patch_source_regenerates_summary(flask_client, repo, tmp_path,
                                          fake_keyring, monkeypatch):
    """Editing the source rewrites the summary with the AI."""
    doc = setup_project_with_text_doc(flask_client, repo, tmp_path,
                                      fake_keyring)
    sent = []

    def fake_send(self, prompt, text):
        sent.append(text)
        return "New summary that mentions Claridad."

    monkeypatch.setattr(GeminiClient, "send_prompt", fake_send)
    response = flask_client.patch("/documents/{}".format(doc.id),
                                  json={"source": "Claridad"})

    assert response.status_code == 200
    assert response.get_json()["source"] == "Claridad"
    assert response.get_json()["summary"] == \
        "New summary that mentions Claridad."
    assert "- source: Claridad" in sent[0]


def test_patch_with_own_summary_is_not_overwritten(
        flask_client, repo, tmp_path, fake_keyring, monkeypatch):
    """If the user writes the summary too, the AI is not called."""
    doc = setup_project_with_text_doc(flask_client, repo, tmp_path,
                                      fake_keyring)
    calls = []
    monkeypatch.setattr(GeminiClient, "send_prompt",
                        lambda self, prompt, text: calls.append(1) or "AI")
    response = flask_client.patch("/documents/{}".format(doc.id), json={
        "source": "Claridad", "summary": "My own summary."})
    assert response.get_json()["summary"] == "My own summary."
    assert calls == []


def test_patch_keeps_edit_when_ai_fails(flask_client, repo, tmp_path,
                                        fake_keyring, monkeypatch):
    """If the AI fails, the edit is saved and the old summary stays."""
    doc = setup_project_with_text_doc(flask_client, repo, tmp_path,
                                      fake_keyring)

    def fail(self, prompt, text):
        raise RuntimeError("quota exceeded")

    monkeypatch.setattr(GeminiClient, "send_prompt", fail)
    # Skip the waits between retries so the test stays fast.
    monkeypatch.setattr(base.time, "sleep", lambda seconds: None)
    response = flask_client.patch("/documents/{}".format(doc.id),
                                  json={"document_date": "1980"})
    assert response.status_code == 200
    assert response.get_json()["document_date"] == "1980"
    assert response.get_json()["summary"] == "Old summary."
