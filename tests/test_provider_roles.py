"""Tests for the provider roles: text, fallback, and media."""

import pytest

from backend.db.catalog_repository import CatalogRepository
from backend.db.schema import get_connection, init_db
from backend.pipeline import ai_providers
from backend.pipeline.ai_providers import base
from backend.pipeline.ai_providers.base import (AIProviderClient,
                                                ClientWithFallback)
from backend.pipeline.ai_providers.ollama_cloud import OllamaCloudClient
from backend.routes import settings as settings_routes


class FakeClient(AIProviderClient):
    """A client whose answers (or failures) are decided in advance."""

    supports_images = False

    def __init__(self, name, answers=None, key="key", images=False):
        self.provider_name = name
        self.model = name + "-model"
        self.base_url = None
        self.api_key = key
        self.retry_delay = 0
        self.answers = list(answers or [])
        self.supports_images = images
        self.calls = 0

    def send_prompt(self, system_prompt, text):
        self.calls += 1
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    def send_images(self, prompt, image_uris):
        self.last_prompt = prompt
        return self.send_prompt(prompt, "")


@pytest.fixture
def fake_keyring(monkeypatch):
    """Replace the OS keyring with a dict, and return that dict."""
    saved = {}
    monkeypatch.setattr(base.keyring, "set_password",
                        lambda service, name, key: saved.update({name: key}))
    monkeypatch.setattr(base.keyring, "get_password",
                        lambda service, name: saved.get(name))
    return saved


# --- Repository ---

def test_roles_are_saved_apart(tmp_path):
    """Each role keeps one provider; the text role is the old active one."""
    db = str(tmp_path / "c.db")
    init_db(db)
    repo = CatalogRepository(db)
    repo.set_active_provider("ollama", "gemma4:31b")
    repo.set_provider("fallback", "claude", "claude-sonnet-5-5")
    repo.set_provider("media", "gemini", "gemini-3.5-flash-lite")
    assert repo.get_active_provider() == {"provider_name": "ollama",
                                          "model": "gemma4:31b"}
    assert repo.get_provider("fallback")["provider_name"] == "claude"
    assert repo.get_provider("media")["model"] == "gemini-3.5-flash-lite"
    repo.set_provider("fallback", "groq", "llama")
    assert repo.get_provider("fallback")["provider_name"] == "groq"
    repo.clear_provider("fallback")
    assert repo.get_provider("fallback") is None
    assert repo.get_active_provider()["provider_name"] == "ollama"


def test_old_active_row_becomes_the_text_provider(tmp_path):
    """A catalog made before the roles keeps its provider."""
    db = str(tmp_path / "old.db")
    conn = get_connection(db)
    conn.execute("CREATE TABLE ai_provider_config (id INTEGER PRIMARY KEY, "
                 "provider_name TEXT, model TEXT, is_active INTEGER)")
    conn.execute("INSERT INTO ai_provider_config (provider_name, model, "
                 "is_active) VALUES ('gemini', 'gemini-2.5-flash', 1)")
    conn.commit()
    conn.close()
    init_db(db)
    repo = CatalogRepository(db)
    assert repo.get_active_provider() == {"provider_name": "gemini",
                                          "model": "gemini-2.5-flash"}
    assert repo.get_provider("fallback") is None
    assert repo.get_server_url() is None


# --- The client with a fallback ---

def test_fallback_answers_when_the_main_one_fails():
    """Three failures in a row, then the fallback answers."""
    main = FakeClient("ollama", [RuntimeError("down")] * 3)
    fallback = FakeClient("claude", ["Press"])
    client = ClientWithFallback(main, fallback)
    assert client.send_classification_request("text") == "Press"
    assert main.calls == 3 and fallback.calls == 1


def test_fallback_answers_when_the_main_one_has_no_key():
    """Without a key the main client never sends anything."""
    main = FakeClient("ollama", ["Press"], key=None)
    fallback = FakeClient("claude", ["Documents"])
    assert ClientWithFallback(main, fallback).ask("p", "t") == "Documents"
    assert main.calls == 0


def test_main_answer_is_used_when_it_works():
    """The fallback stays quiet while the main provider answers."""
    main = FakeClient("ollama", ["Press"])
    fallback = FakeClient("claude", ["Documents"])
    client = ClientWithFallback(main, fallback)
    assert client.ask("p", "t") == "Press"
    assert fallback.calls == 0
    assert client.provider_name == "ollama"


def test_no_fallback_gives_none_like_before():
    """Without a fallback, a failure still gives None."""
    main = FakeClient("ollama", [RuntimeError("down")] * 3)
    assert ClientWithFallback(main, None).ask("p", "t") is None


def test_images_go_to_the_client_that_reads_them():
    """A text-only main provider hands images to the fallback."""
    main = FakeClient("ollama", ["unused"], images=False)
    fallback = FakeClient("claude", ['{"text": "hi"}'], images=True)
    client = ClientWithFallback(main, fallback)
    assert client.supports_images is True
    assert client.ask_about_images(["data:image/jpeg;base64,QUJD"]) == \
        '{"text": "hi"}'
    assert main.calls == 0
    assert ClientWithFallback(main, None).supports_images is False


def test_photo_prompt_reaches_the_client_that_reads_images():
    """The photo prompt (corners, rotation, stamps) passes the wrapper."""
    main = FakeClient("ollama", ['{"rotation": 0}', '{"rotation": 0}'],
                      images=True)
    client = ClientWithFallback(main, None)
    client.ask_about_images(["data:image/jpeg;base64,QUJD"],
                            base.PHOTO_PROMPT)
    assert main.last_prompt == base.PHOTO_PROMPT
    client.ask_about_images(["data:image/jpeg;base64,QUJD"])
    assert main.last_prompt == base.IMAGE_PROMPT


# --- Building the project's clients ---

def test_project_client_uses_claude_when_its_key_exists(tmp_path,
                                                        monkeypatch):
    """With no fallback chosen, a saved Claude key makes Claude step in."""
    db = str(tmp_path / "c.db")
    init_db(db)
    repo = CatalogRepository(db)
    repo.set_active_provider("ollama", "gemma4:31b")
    monkeypatch.setattr(base.keyring, "get_password",
                        lambda service, name: "k" if name == "claude"
                        else None)
    client = ai_providers.project_client(repo)
    assert isinstance(client, ClientWithFallback)
    assert client.fallback.provider_name == "claude"
    assert client.fallback.model == "claude-sonnet-5-5"

    # The chosen fallback wins over the automatic one.
    repo.set_provider("fallback", "groq", "llama-3.1-8b-instant")
    monkeypatch.setattr(base.keyring, "get_password",
                        lambda service, name: "k")
    assert ai_providers.project_client(repo).fallback.provider_name == "groq"


def test_project_client_without_keys_has_no_fallback(tmp_path):
    """No Claude key, no fallback chosen: the main client stands alone."""
    db = str(tmp_path / "c.db")
    init_db(db)
    repo = CatalogRepository(db)
    repo.set_active_provider("ollama", "gemma4:31b")
    client = ai_providers.project_client(repo)
    assert client.fallback is None
    assert ai_providers.media_client(repo) is None
    repo.set_provider("media", "gemini", "gemini-3.5-flash-lite")
    assert ai_providers.media_client(repo).provider_name == "gemini"


def test_server_url_reaches_every_client(tmp_path, monkeypatch):
    """A saved server URL replaces each provider's own address."""
    db = str(tmp_path / "c.db")
    init_db(db)
    repo = CatalogRepository(db)
    repo.save_app_config("Research", str(tmp_path))
    repo.set_active_provider("ollama", "gemma4:31b")
    repo.set_provider("media", "gemini", "gemini-3.5-flash-lite")
    repo.save_config_value("server_url", "https://relay.example")
    client = ai_providers.project_client(repo)
    assert client.main.base_url == "https://relay.example"
    assert ai_providers.media_client(repo).base_url == "https://relay.example"
    # Without a server, Ollama Cloud keeps its own address.
    assert OllamaCloudClient().base_url == "https://ollama.com/v1"


# --- Routes ---

def test_put_ai_provider_with_roles(flask_client, fake_keyring):
    """Each role is saved apart and shown in Settings."""
    response = flask_client.put("/settings/ai-provider", json={
        "role": "fallback", "provider_name": "claude",
        "model": "claude-sonnet-5-5", "api_key": "claude-key"})
    assert response.status_code == 200
    response = flask_client.put("/settings/ai-provider", json={
        "role": "media", "provider_name": "gemini",
        "model": "gemini-3.5-flash-lite", "api_key": "gemini-key"})
    assert response.status_code == 200
    assert fake_keyring == {"claude": "claude-key", "gemini": "gemini-key"}
    settings = flask_client.get("/settings").get_json()
    assert settings["active_provider"] is None
    assert settings["fallback_provider"] == "claude"
    assert settings["media_model"] == "gemini-3.5-flash-lite"
    assert "claude-key" not in str(settings)

    response = flask_client.delete("/settings/ai-provider/fallback")
    assert response.status_code == 200
    settings = flask_client.get("/settings").get_json()
    assert settings["fallback_provider"] is None
    assert settings["media_provider"] == "gemini"


@pytest.mark.parametrize("body, code", [
    ({"role": "owner", "provider_name": "ollama", "model": "m"},
     "invalid_role"),
    ({"role": "media", "provider_name": "ollama", "model": "m"},
     "unsupported_provider"),
])
def test_put_ai_provider_refuses_bad_roles(flask_client, fake_keyring,
                                           body, code):
    """Unknown roles, and media providers other than Gemini, are refused."""
    response = flask_client.put("/settings/ai-provider", json=body)
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == code
    assert flask_client.delete("/settings/ai-provider/text").status_code \
        == 400


def test_server_url_is_saved_and_checked(flask_client):
    """The server URL is saved with Settings and must be a web address."""
    response = flask_client.put("/settings", json={
        "research_name": "Research", "server_url": "https://relay.example/"})
    assert response.status_code == 200
    assert response.get_json()["server_url"] == "https://relay.example"
    response = flask_client.put("/settings", json={
        "research_name": "Research", "server_url": "relay.example"})
    assert response.get_json()["error"]["code"] == "invalid_server_url"
    response = flask_client.put("/settings", json={
        "research_name": "Research", "server_url": ""})
    assert response.get_json()["server_url"] == ""


def test_test_endpoint_uses_the_server_url(flask_client, monkeypatch):
    """The connection test goes through the server when one is typed."""
    seen = {}

    def fake_create(name, model, base_url=None):
        seen.update({"name": name, "base_url": base_url})
        return FakeClient(name, ["OK"])
    monkeypatch.setattr(settings_routes, "create_client", fake_create)
    response = flask_client.post("/settings/ai-provider/test", json={
        "provider_name": "ollama", "model": "gemma4:31b",
        "server_url": "https://relay.example"})
    assert response.status_code == 200
    assert seen == {"name": "ollama", "base_url": "https://relay.example"}
