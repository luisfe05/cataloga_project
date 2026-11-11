"""API keys per account: each account reads only its own keys."""

import pytest

from backend.app import create_app
from backend.config import ai_settings, api_keys
from backend.config.terms import TERMS_VERSION
from backend.pipeline.ai_providers import base, text_client

# Obviously fake keys, never real ones.
ANA_KEY = "fake-ollama-key-ana"
OLD_KEY = "fake-ollama-key-old"


@pytest.fixture
def keyring_dict(monkeypatch):
    """A fake keyring: a dict by (service, name), never the real Keychain."""
    saved = {}
    monkeypatch.setattr(base.keyring, "get_password",
                        lambda service, name: saved.get((service, name)))
    monkeypatch.setattr(base.keyring, "set_password",
                        lambda service, name, value: saved.__setitem__(
                            (service, name), value))
    monkeypatch.setattr(base.keyring, "delete_password",
                        lambda service, name: saved.pop((service, name), None))
    return saved


@pytest.fixture
def client(tmp_path, data_folder, keyring_dict):
    """A logged-out client on an app with no accounts yet."""
    app = create_app(data_folder=data_folder,
                     old_db_path=str(tmp_path / "no_old.db"))
    app.config["TESTING"] = True
    return app.test_client()


def register(client, username):
    """Create an account and send its token from now on."""
    answer = client.post("/auth/register", json={
        "username": username, "password": username + "-password-1",
        "accepted_terms": TERMS_VERSION})
    assert answer.status_code == 201
    client.environ_base["HTTP_AUTHORIZATION"] = \
        "Bearer " + answer.get_json()["token"]


def log_in(client, username):
    """Log in with the password register() gave."""
    answer = client.post("/auth/login", json={
        "username": username, "password": username + "-password-1"})
    assert answer.status_code == 200
    client.environ_base["HTTP_AUTHORIZATION"] = \
        "Bearer " + answer.get_json()["token"]


def projects_path_of(client, username):
    """The project list of one account."""
    return client.application.config["ACCOUNTS"].projects_path(username)


def test_a_new_key_is_saved_under_the_account(client, keyring_dict):
    """PUT /settings/ai-provider saves Cataloga/<account>/<provider>."""
    register(client, "ana")
    answer = client.put("/settings/ai-provider", json={
        "provider_name": "ollama", "model": "gemma4:31b",
        "api_key": ANA_KEY})
    assert answer.status_code == 200
    assert keyring_dict == {("Cataloga/ana/ollama", "ollama"): ANA_KEY}


def test_account_b_never_reads_the_key_of_account_a(client, keyring_dict):
    """Beto has no key: Ana's key is not his, not even for Ollama Cloud."""
    register(client, "ana")
    client.put("/settings/ai-provider", json={
        "provider_name": "ollama", "model": "gemma4:31b",
        "api_key": ANA_KEY})
    client.post("/auth/logout")
    register(client, "beto")
    settings = client.get("/settings").get_json()
    assert settings["providers_with_key"] == []
    assert client.get("/settings/ai-status").get_json()["has_key"] is False
    beto_ai = ai_settings.load(projects_path_of(client, "beto"))
    assert text_client(beto_ai).api_key is None
    ana_ai = ai_settings.load(projects_path_of(client, "ana"))
    assert text_client(ana_ai).api_key == ANA_KEY


def test_the_only_account_gets_the_old_shared_keys(client, keyring_dict):
    """Known owner: one account on the Mac, so the old key is moved to it."""
    register(client, "ana")
    client.post("/auth/logout")
    keyring_dict[(api_keys.LEGACY_SERVICE, "ollama")] = OLD_KEY
    log_in(client, "ana")
    assert keyring_dict == {("Cataloga/ana/ollama", "ollama"): OLD_KEY}
    assert client.get("/settings").get_json()["legacy_keys"] == []


def test_a_second_account_leaves_the_old_keys_with_the_first(
        client, keyring_dict):
    """Creating account two first gives the old keys to account one."""
    register(client, "ana")
    client.post("/auth/logout")
    keyring_dict[(api_keys.LEGACY_SERVICE, "groq")] = OLD_KEY
    register(client, "beto")
    assert keyring_dict == {("Cataloga/ana/groq", "groq"): OLD_KEY}
    assert client.get("/settings").get_json()["legacy_keys"] == []


@pytest.fixture
def unknown_owner(client, keyring_dict):
    """Two accounts and an old shared key nobody can tell the owner of."""
    register(client, "ana")
    client.post("/auth/logout")
    register(client, "beto")
    client.post("/auth/logout")
    keyring_dict[(api_keys.LEGACY_SERVICE, "ollama")] = OLD_KEY
    log_in(client, "beto")
    return client


def test_an_unknown_owner_is_asked_not_guessed(unknown_owner, keyring_dict):
    """The key is not used and not moved until an account answers."""
    settings = unknown_owner.get("/settings").get_json()
    assert settings["legacy_keys"] == ["ollama"]
    assert settings["providers_with_key"] == []
    assert keyring_dict == {(api_keys.LEGACY_SERVICE, "ollama"): OLD_KEY}


def test_the_first_account_to_claim_it_keeps_it(unknown_owner, keyring_dict):
    """Use it for my account: moved to Beto, gone for Ana."""
    answer = unknown_owner.post("/settings/ai-provider/legacy-key", json={
        "provider_name": "ollama", "answer": "claim"})
    assert answer.status_code == 200
    assert answer.get_json()["claimed"] is True
    assert keyring_dict == {("Cataloga/beto/ollama", "ollama"): OLD_KEY}
    assert unknown_owner.get("/settings").get_json()["legacy_keys"] == []
    unknown_owner.post("/auth/logout")
    log_in(unknown_owner, "ana")
    settings = unknown_owner.get("/settings").get_json()
    assert settings["legacy_keys"] == []
    assert settings["providers_with_key"] == []
    late = unknown_owner.post("/settings/ai-provider/legacy-key", json={
        "provider_name": "ollama", "answer": "claim"})
    assert late.status_code == 409
    assert late.get_json()["error"]["code"] == "legacy_key_gone"


def test_add_my_own_key_stops_asking_only_that_account(
        unknown_owner, keyring_dict):
    """Decline: Beto is not asked again; Ana still is; the key stays."""
    answer = unknown_owner.post("/settings/ai-provider/legacy-key", json={
        "provider_name": "ollama", "answer": "decline"})
    assert answer.status_code == 200
    assert unknown_owner.get("/settings").get_json()["legacy_keys"] == []
    assert (api_keys.LEGACY_SERVICE, "ollama") in keyring_dict
    unknown_owner.post("/auth/logout")
    log_in(unknown_owner, "ana")
    assert unknown_owner.get("/settings").get_json()["legacy_keys"] == \
        ["ollama"]


def test_a_bad_answer_is_refused(unknown_owner):
    """Only claim or decline, for a known provider."""
    for body in ({"provider_name": "ollama", "answer": "maybe"},
                 {"provider_name": "nope", "answer": "claim"}, {}):
        answer = unknown_owner.post("/settings/ai-provider/legacy-key",
                                    json=body)
        assert answer.status_code == 400


def test_deleting_account_a_leaves_the_keys_of_b(client, keyring_dict):
    """Ana's keys go with her account; Beto's stay as they were."""
    register(client, "beto")
    client.put("/settings/ai-provider", json={
        "provider_name": "ollama", "model": "gemma4:31b",
        "api_key": "fake-ollama-key-beto"})
    client.post("/auth/logout")
    register(client, "ana")
    client.put("/settings/ai-provider", json={
        "provider_name": "ollama", "model": "gemma4:31b",
        "api_key": ANA_KEY})
    answer = client.post("/auth/delete-account",
                         json={"password": "ana-password-1"})
    assert answer.status_code == 200
    assert keyring_dict == {
        ("Cataloga/beto/ollama", "ollama"): "fake-ollama-key-beto"}


def test_the_account_name_is_never_saved_in_the_settings(client):
    """ai["account"] is read from the folder, never written to the file."""
    register(client, "ana")
    path = projects_path_of(client, "ana")
    ai_settings.set_role(path, "fallback", "claude", "claude-sonnet-5-5")
    with open(path, encoding="utf-8") as file:
        assert '"account"' not in file.read()
    assert ai_settings.load(path)["account"] == "ana"
