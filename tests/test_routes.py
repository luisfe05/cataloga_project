"""Integration tests for Flask routes using the test client.

Uses the app and flask_client fixtures from conftest.py.
Tests confirm correct HTTP status codes and response shapes,
not business logic (that belongs in the unit test files).
"""

import pytest

from backend.db.catalog_repository import CatalogRepository
from backend.models.document import Document
from backend.pipeline.ai_providers import base
from backend.pipeline.ai_providers.gemini import GeminiClient


@pytest.fixture
def repo(app):
    """Return a CatalogRepository on the same database as the app."""
    return CatalogRepository(app.config["DB_PATH"])


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
                        "Date,Summary,Status")
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

def test_get_settings_before_setup(flask_client):
    """Before setup, settings are empty strings and no provider."""
    response = flask_client.get("/settings")
    assert response.status_code == 200
    assert response.get_json() == {
        "research_name": "", "target_directory": "",
        "active_provider": None, "active_model": None,
    }


def test_put_settings_creates_archive_folders(flask_client, tmp_path):
    """Saving settings stores them and creates the five folders."""
    archive = tmp_path / "my_archive"
    archive.mkdir()
    response = flask_client.put("/settings", json={
        "research_name": "El Delfin", "target_directory": str(archive)})
    assert response.status_code == 200
    assert response.get_json()["research_name"] == "El Delfin"
    assert (archive / "Press").is_dir()
    assert flask_client.get("/settings").get_json()["target_directory"] \
        == str(archive)


def test_put_settings_missing_field(flask_client):
    """Both fields are required."""
    response = flask_client.put("/settings", json={"research_name": "X"})
    assert_error(response, 400, "missing_field")


def test_put_settings_folder_must_exist(flask_client, tmp_path):
    """A folder that does not exist (e.g. unplugged drive) gives 400."""
    response = flask_client.put("/settings", json={
        "research_name": "X", "target_directory": str(tmp_path / "nope")})
    assert_error(response, 400, "invalid_directory")


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
