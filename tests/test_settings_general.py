"""Tests for the General tab: AI status, one field at a time, new projects."""

import pytest

from backend import scanner
from backend.config import projects
from backend.db.catalog_repository import CatalogRepository
from backend.pipeline.ai_providers import base
from backend.routes import settings as settings_routes
from tests.test_routes import add_doc

# Invented; only used to check that it never comes back.
FAKE_KEY = "test-key-harbor-0000"


@pytest.fixture(autouse=True)
def empty_status_cache():
    """Each test starts with no connection result kept."""
    settings_routes.status_cache.clear()
    yield
    settings_routes.status_cache.clear()


@pytest.fixture
def key_saved(monkeypatch):
    """Every provider has the invented key in the keyring."""
    monkeypatch.setattr(base.keyring, "get_password",
                        lambda service, name: FAKE_KEY)


@pytest.fixture
def calls(monkeypatch):
    """Count the connection tests; each one passes."""
    made = []

    def fake_test(self):
        made.append(self.provider_name)
        return True
    monkeypatch.setattr(base.AIProviderClient, "test_connection", fake_test)
    return made


def repo_of(app):
    """The active project's catalog."""
    return CatalogRepository(
        projects.catalog_path(app.config["PROJECT_FOLDER"]))


# --- GET /settings/ai-status ---

def test_status_without_a_key_does_not_call_the_provider(flask_client,
                                                         calls):
    """No key saved: no_key, and no call at all."""
    response = flask_client.get("/settings/ai-status")
    assert response.status_code == 200
    assert response.get_json() == {"provider": "ollama",
                                   "model": "gemma4:31b",
                                   "has_key": False, "status": "no_key"}
    assert calls == []


def test_status_with_a_key_is_connected_and_never_returns_it(
        flask_client, key_saved, calls):
    """The answer says yes or no about the key, never the key."""
    response = flask_client.get("/settings/ai-status")
    body = response.get_json()
    assert body["has_key"] is True
    assert body["status"] == "connected"
    assert FAKE_KEY not in response.get_data(as_text=True)
    assert set(body) == {"provider", "model", "has_key", "status"}


def test_status_is_kept_a_few_minutes(flask_client, key_saved, calls):
    """Two visits make one call; saving a provider asks again."""
    flask_client.get("/settings/ai-status")
    flask_client.get("/settings/ai-status")
    assert len(calls) == 1
    flask_client.put("/settings/ai-provider",
                     json={"provider_name": "ollama", "model": "gemma4:31b"})
    flask_client.get("/settings/ai-status")
    assert len(calls) == 2


def test_status_says_error_when_the_call_fails(flask_client, key_saved,
                                               monkeypatch):
    """A failing provider is error, with no message from the provider."""
    def fail(self):
        raise RuntimeError("401 bad key " + FAKE_KEY)
    monkeypatch.setattr(base.AIProviderClient, "test_connection", fail)
    response = flask_client.get("/settings/ai-status")
    assert response.get_json()["status"] == "error"
    assert FAKE_KEY not in response.get_data(as_text=True)


def test_status_follows_the_account_provider(flask_client, key_saved,
                                             calls):
    """The provider and model saved for the text role are shown."""
    flask_client.put("/settings/ai-provider", json={
        "provider_name": "gemini", "model": "gemini-2.5-flash"})
    body = flask_client.get("/settings/ai-status").get_json()
    assert body["provider"] == "gemini"
    assert body["model"] == "gemini-2.5-flash"


def test_status_with_no_project_uses_the_default(empty_client, calls):
    """Before the first project: Ollama Cloud, and no key yet."""
    body = empty_client.get("/settings/ai-status").get_json()
    assert body["provider"] == "ollama"
    assert body["status"] == "no_key"


def test_the_short_limit_is_lifted_after_the_check(flask_client, key_saved,
                                                   monkeypatch):
    """The 8 second budget only lives during the call."""
    seen = []

    def fake_test(self):
        seen.append(settings_routes.time_budget.call_seconds())
        return True
    monkeypatch.setattr(base.AIProviderClient, "test_connection", fake_test)
    flask_client.get("/settings/ai-status")
    assert 0 < seen[0] <= settings_routes.STATUS_TIMEOUT_SECONDS
    assert settings_routes.time_budget.current() is None


# --- PATCH /settings ---

def test_patch_saves_the_language_alone(flask_client, app):
    """One field: the language, nothing else changes."""
    response = flask_client.patch("/settings",
                                  json={"key": "language", "value": "es"})
    assert response.status_code == 200
    assert response.get_json() == {"key": "language", "value": "es"}
    settings = flask_client.get("/settings").get_json()
    assert settings["language"] == "es"
    assert settings["research_name"] == "Research"


def test_patch_saves_the_server_url_cleaned(flask_client, app):
    """Spaces and the last slash go away."""
    response = flask_client.patch(
        "/settings", json={"key": "server_url",
                           "value": " https://relay.example.org/ "})
    assert response.get_json()["value"] == "https://relay.example.org"
    settings = flask_client.get("/settings").get_json()
    assert settings["server_url"] == "https://relay.example.org"


def test_patch_clears_the_server_url(flask_client, app):
    """An empty value takes the server away."""
    flask_client.patch("/settings", json={
        "key": "server_url", "value": "https://relay.example.org"})
    flask_client.patch("/settings", json={"key": "server_url", "value": ""})
    assert flask_client.get("/settings").get_json()["server_url"] == ""


@pytest.mark.parametrize("body, code", [
    ({"key": "language", "value": "fr"}, "invalid_language"),
    ({"key": "server_url", "value": "relay.example.org"},
     "invalid_server_url"),
    ({"key": "research_name", "value": "Other"}, "invalid_key"),
    ({"key": "api_key", "value": FAKE_KEY}, "invalid_key"),
    ({"value": "es"}, "missing_field"),
    ([], "missing_field"),
])
def test_patch_rejects_wrong_fields(flask_client, app, body, code):
    """The server checks the field and its value; nothing is saved."""
    response = flask_client.patch("/settings", json=body)
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == code
    settings = flask_client.get("/settings").get_json()
    assert settings["language"] == "en"
    assert settings["server_url"] == ""


def test_patch_server_url_works_with_no_project(empty_client):
    """The server belongs to the account, like the provider."""
    response = empty_client.patch(
        "/settings", json={"key": "server_url",
                           "value": "https://relay.example.org"})
    assert response.status_code == 200
    assert empty_client.get("/settings").get_json()["server_url"] == \
        "https://relay.example.org"


# --- POST /projects without the General fields ---

def test_a_project_is_created_without_the_general_fields(empty_client,
                                                         tmp_path,
                                                         monkeypatch):
    """No language, provider or server: defaults, as before."""
    monkeypatch.setattr(scanner, "start_scan",
                        lambda app, path, owner=None: None)
    folder = tmp_path / "Beach Research"
    folder.mkdir()
    (folder / "coast-erosion.txt").write_text("Invented notes.")
    response = empty_client.post("/projects", json={
        "name": "Beach Research", "folder": str(folder),
        "folder_mode": "place", "defer_scan": True})
    assert response.status_code == 201
    settings = empty_client.get("/settings").get_json()
    assert settings["active_provider"] == "ollama"
    assert settings["server_url"] == ""
    assert settings["research_name"] == "Beach Research"
    assert settings["language"] == "en"


def test_the_dashboard_lists_the_top_sources(flask_client, app):
    """The three sources with the most documents, as the chat counts them."""
    repo = repo_of(app)
    for index, source in enumerate(["Harbor Gazette", "Harbor Gazette",
                                    "Coast Weekly", "Pier Digital",
                                    "Bay Radio", "Harbor Gazette"]):
        add_doc(repo, "D_{:03d}.pdf".format(index), source=source)
    stats = flask_client.get("/dashboard/stats").get_json()
    assert stats["top_sources"][0] == {"source": "Harbor Gazette",
                                       "count": 3}
    assert len(stats["top_sources"]) == 3
    summary = repo.get_project_summary()
    assert stats["top_sources"] == summary["top_sources"]
