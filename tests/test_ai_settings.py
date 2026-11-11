"""Tests for the account's AI provider: one for every project, migrated."""

import json
import os

import pytest

from backend import scanner
from backend.config import ai_settings, projects
from backend.db.catalog_repository import CatalogRepository
from backend.pipeline import ai_providers
from backend.pipeline.ai_providers import base
from tests.conftest import make_project

# Invented; only used to check that it never comes back.
FAKE_KEY = "test-key-harbor-1111"


def saved_ai(projects_path):
    """The "ai" block written in the account's project list."""
    with open(projects_path, encoding="utf-8") as file:
        return json.load(file).get("ai")


# --- Migration ---

def test_migration_copies_the_most_recent_project(tmp_path):
    """The newest opened project's provider, fallback, media and server."""
    path = str(tmp_path / "projects.json")
    old = make_project(path, tmp_path / "Beach Research", "Beach Research")
    old.set_provider("text", "groq", "llama-3.1-8b-instant")
    new = make_project(path, tmp_path / "Harbor Swimmers", "Harbor Swimmers")
    new.set_provider("text", "gemini", "gemini-2.5-flash")
    new.set_provider("media", "gemini", "gemini-3.5-flash-lite")
    new.save_config_value("server_url", "https://relay.example.org")
    # Harbor Swimmers was opened last.
    data = projects.load_projects(path)
    data["projects"][0]["last_opened"] = "2026-11-01T09:00:00"
    data["projects"][1]["last_opened"] = "2026-11-09T09:00:00"
    projects.save_projects(path, data)

    assert ai_settings.migrate(path) is True
    ai = saved_ai(path)
    assert ai["text"] == {"provider_name": "gemini",
                          "model": "gemini-2.5-flash"}
    assert ai["media"]["model"] == "gemini-3.5-flash-lite"
    assert ai["fallback"] is None
    assert ai["server_url"] == "https://relay.example.org"


def test_migration_runs_once(tmp_path):
    """A second run changes nothing, even if a project changes later."""
    path = str(tmp_path / "projects.json")
    repo = make_project(path, tmp_path / "Harbor Swimmers")
    repo.set_provider("text", "groq", "llama-3.1-8b-instant")
    assert ai_settings.migrate(path) is True
    first = saved_ai(path)
    repo.set_provider("text", "gemini", "gemini-2.5-flash")
    assert ai_settings.migrate(path) is False
    assert saved_ai(path) == first


def test_migration_with_no_projects_uses_the_default(tmp_path):
    """Ollama Cloud with gemma4:31b, and nothing else."""
    path = str(tmp_path / "projects.json")
    loaded = ai_settings.load(path)
    # The account comes from the folder; it is never saved in the file.
    assert loaded.pop("account") == os.path.basename(str(tmp_path))
    assert loaded.pop("language") == "en"
    assert loaded == ai_settings.default_ai()
    assert "account" not in saved_ai(path)
    assert saved_ai(path)["text"] == {"provider_name": "ollama",
                                      "model": "gemma4:31b"}


def test_migration_skips_a_project_with_no_provider(tmp_path):
    """A newest project without a provider row: the next one is used."""
    path = str(tmp_path / "projects.json")
    old = make_project(path, tmp_path / "Beach Research")
    old.set_provider("text", "groq", "llama-3.1-8b-instant")
    make_project(path, tmp_path / "Coast Erosion")
    assert ai_settings.load(path)["text"]["provider_name"] == "groq"


def test_the_language_and_the_list_stay_as_they_were(tmp_path):
    """The migration only adds the "ai" block."""
    path = str(tmp_path / "projects.json")
    make_project(path, tmp_path / "Harbor Swimmers")
    projects.set_language(path, "es")
    before = projects.load_projects(path)
    ai_settings.migrate(path)
    after = projects.load_projects(path)
    after.pop("ai")
    assert after == before


# --- One provider for every project ---

def test_two_projects_use_the_same_provider(flask_client, app, tmp_path,
                                            monkeypatch):
    """The provider chosen in General is the one each project gets."""
    flask_client.put("/settings/ai-provider", json={
        "provider_name": "gemini", "model": "gemini-2.5-flash"})
    folder = tmp_path / "Beach Research"
    folder.mkdir()
    monkeypatch.setattr(scanner, "start_scan",
                        lambda app, path, owner=None: None)
    flask_client.post("/projects", json={
        "name": "Beach Research", "folder": str(folder),
        "folder_mode": "place", "defer_scan": True})
    second = flask_client.get("/settings").get_json()
    flask_client.put("/projects/active",
                     json={"folder": app.config["PROJECT_FOLDER"]})
    first = flask_client.get("/settings").get_json()
    assert first["research_name"] != second["research_name"]
    for settings in (first, second):
        assert settings["active_provider"] == "gemini"
        assert settings["active_model"] == "gemini-2.5-flash"
    # Nothing about the provider is written in the new project.
    repo = CatalogRepository(projects.catalog_path(str(folder)))
    assert repo.get_provider("text") is None


def test_every_reader_builds_the_same_client(tmp_path):
    """Pipeline, chat and Write it for me all go through text_client."""
    path = str(tmp_path / "projects.json")
    ai_settings.set_role(path, "text", "groq", "llama-3.1-8b-instant")
    client = ai_providers.text_client(ai_settings.load(path))
    assert client.main.provider_name == "groq"


def test_ai_status_never_returns_the_key(flask_client, monkeypatch):
    """Only yes or no about the key, for the account's provider."""
    monkeypatch.setattr(base.keyring, "get_password",
                        lambda service, name: FAKE_KEY)
    monkeypatch.setattr(base.AIProviderClient, "test_connection",
                        lambda self: True)
    response = flask_client.get("/settings/ai-status")
    assert response.get_json()["has_key"] is True
    assert FAKE_KEY not in response.get_data(as_text=True)


# --- Later sends nothing to the AI ---

class CountingAI(base.AIProviderClient):
    """A provider that counts every request it gets."""

    calls = []

    def __init__(self, model=None, base_url=None):
        """No key needed; every request is counted."""
        super().__init__(provider_name="ollama", model=model or "m",
                         base_url=base_url)
        self.api_key = FAKE_KEY

    def send_prompt(self, system_prompt, text):
        """Count, and answer with nothing useful."""
        CountingAI.calls.append(text)
        return "{}"


@pytest.fixture
def counting_ai(monkeypatch):
    """Every provider is the counting one."""
    CountingAI.calls = []
    for name in list(ai_providers.PROVIDERS):
        monkeypatch.setitem(ai_providers.PROVIDERS, name, CountingAI)
    return CountingAI.calls


def test_later_makes_zero_ai_calls(empty_client, tmp_path, counting_ai):
    """Name, About and File names filled in, folder listed: no request."""
    folder = tmp_path / "Harbor-Swimmers-Documentary"
    folder.mkdir()
    for name in ("0001_dawn-swim.txt", "0002_harbor-race.txt"):
        (folder / name).write_text("Invented notes.")
    listed = empty_client.post("/projects/folders/list",
                               json={"folder": str(folder)}).get_json()
    assert listed["naming_suggestion"] == "{number}_{topic}"
    response = empty_client.post("/projects", json={
        "name": "Harbor Swimmers Documentary", "folder": str(folder),
        "folder_mode": "place", "defer_scan": True,
        "project_sheet": "Work: a documentary about a swim club.",
        "naming_template": listed["naming_suggestion"],
        "naming_style": "lower", "folders": []})
    assert response.status_code == 201
    assert counting_ai == []
    repo = CatalogRepository(projects.catalog_path(str(folder)))
    assert repo.get_project_sheet().startswith("Work:")
    assert repo.get_app_config()["naming_template"] == "{number}_{topic}"


def test_the_reading_writes_an_empty_sheet_but_never_replaces_one(
        tmp_path, counting_ai):
    """Later left About empty: the reading fills it; a typed one stays."""
    folder = tmp_path / "Beach Research"
    folder.mkdir()
    repo = make_project(str(tmp_path / "projects.json"), folder)

    class SheetAI(CountingAI):
        """Answers the sheet request with one line of work."""

        def send_prompt(self, system_prompt, text):
            """Count, and write the sheet."""
            CountingAI.calls.append(text)
            return '{"work": "Field notes about coast erosion."}'
    scanner.write_sheet_if_empty(repo, str(folder), SheetAI())
    assert repo.get_project_sheet() == \
        "Work: Field notes about coast erosion."
    repo.save_config_value("project_sheet", "Work: typed by hand.")
    scanner.write_sheet_if_empty(repo, str(folder), SheetAI())
    assert repo.get_project_sheet() == "Work: typed by hand."
    assert len(counting_ai) == 1


# --- Write it for me has its own error ---

def test_a_sheet_that_fails_has_its_own_code(flask_client, app, monkeypatch):
    """Not the categories message: sheet_failed, 502."""
    monkeypatch.setattr("backend.routes.settings.text_client",
                        lambda settings: CountingAI())
    response = flask_client.post("/settings/sheet/suggest", json={
        "folder": app.config["PROJECT_FOLDER"]})
    assert response.status_code == 502
    assert response.get_json()["error"]["code"] == "sheet_failed"
