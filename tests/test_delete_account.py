"""Delete account: the password first; project folders are never touched."""

import json
import os

import pytest

from backend.app import create_app
from backend.config import ai_settings
from backend.config.terms import TERMS_VERSION
from backend.pipeline.ai_providers import base
from tests.conftest import make_project


@pytest.fixture
def client(tmp_path, data_folder):
    """A logged-out client on an app with no accounts yet."""
    app = create_app(data_folder=data_folder,
                     old_db_path=str(tmp_path / "no_old.db"))
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def api_keys(monkeypatch):
    """API keys go to a dict, never to the real Keychain."""
    saved = {}
    monkeypatch.setattr(base.keyring, "get_password",
                        lambda service, name: saved.get((service, name)))
    monkeypatch.setattr(base.keyring, "set_password",
                        lambda service, name, value: saved.__setitem__(
                            (service, name), value))
    monkeypatch.setattr(base.keyring, "delete_password",
                        lambda service, name: saved.pop((service, name), None))
    return saved


def register(client, username):
    """Create an account; the client then sends its token."""
    answer = client.post("/auth/register", json={
        "username": username, "password": username + "-password-1",
        "accepted_terms": TERMS_VERSION})
    assert answer.status_code == 201
    client.environ_base["HTTP_AUTHORIZATION"] = \
        "Bearer " + answer.get_json()["token"]
    return answer.get_json()


def log_in(client, username):
    """Log in with the password register() gave."""
    answer = client.post("/auth/login", json={
        "username": username, "password": username + "-password-1"})
    if answer.status_code == 200:
        client.environ_base["HTTP_AUTHORIZATION"] = \
            "Bearer " + answer.get_json()["token"]
    return answer


def files_of(folder):
    """Every file under a folder, by relative path."""
    found = []
    for current, dirs, names in os.walk(str(folder)):
        for name in names:
            found.append(os.path.relpath(os.path.join(current, name),
                                         str(folder)))
    return sorted(found)


@pytest.fixture
def two_accounts(client, tmp_path, api_keys, fake_keychain):
    """Marta and Beto, each with a project; Marta also has a Claude key.

    Both use Ollama Cloud (the default), each with a key of their own.
    """
    register(client, "beto")
    store = client.application.config["ACCOUNTS"]
    make_project(store.projects_path("beto"), tmp_path / "Beto Files",
                 name="Beto Files")
    client.post("/auth/logout")
    register(client, "marta")
    folder = tmp_path / "Harbor Swimmers"
    make_project(store.projects_path("marta"), folder,
                 name="Harbor Swimmers")
    (folder / "Documents" / "notes.txt").write_text("Dawn swim notes.")
    api_keys[("Cataloga/marta/ollama", "ollama")] = "ollama-test-key-000"
    api_keys[("Cataloga/marta/claude", "claude")] = "fake-claude-key-000"
    api_keys[("Cataloga/beto/ollama", "ollama")] = "ollama-test-key-111"
    ai_settings.set_role(store.projects_path("marta"), "fallback", "claude",
                         "claude-sonnet-5-5")
    return {"client": client, "store": store, "folder": folder,
            "before": files_of(folder), "beto": tmp_path / "Beto Files"}


def test_a_wrong_password_deletes_nothing(two_accounts, api_keys,
                                          fake_keychain):
    """400 wrong_password; the account, its folder and its keys stay."""
    client = two_accounts["client"]
    answer = client.post("/auth/delete-account",
                         json={"password": "not-the-password"})
    assert answer.status_code == 400
    assert answer.get_json()["error"]["code"] == "wrong_password"
    store = two_accounts["store"]
    assert store.find("marta") is not None
    assert os.path.isfile(store.projects_path("marta"))
    assert "marta" in fake_keychain
    assert ("Cataloga/marta/claude", "claude") in api_keys
    # Still logged in: the session was not cut.
    assert client.get("/settings").status_code == 200


def test_a_missing_password_deletes_nothing(two_accounts):
    """No password at all: 400 missing_field."""
    client = two_accounts["client"]
    assert client.post("/auth/delete-account", json={}).status_code == 400
    assert two_accounts["store"].find("marta") is not None


def test_the_right_password_deletes_the_account_and_its_keys(
        two_accounts, api_keys, fake_keychain):
    """The account, its folder, its recovery key and its own API key go."""
    client = two_accounts["client"]
    store = two_accounts["store"]
    answer = client.post("/auth/delete-account",
                         json={"password": "marta-password-1"})
    assert answer.status_code == 200
    assert answer.get_json() == {"deleted": True, "accounts_left": 1}
    assert store.find("marta") is None
    assert not os.path.exists(os.path.dirname(store.projects_path("marta")))
    with open(store.path, encoding="utf-8") as file:
        assert "marta" not in file.read().lower()
    assert "marta" not in fake_keychain
    # Every key of Marta goes; Beto's own Ollama Cloud key stays.
    assert ("Cataloga/marta/claude", "claude") not in api_keys
    assert ("Cataloga/marta/ollama", "ollama") not in api_keys
    assert api_keys[("Cataloga/beto/ollama", "ollama")] == \
        "ollama-test-key-111"
    # The session ended.
    assert client.get("/settings").status_code == 401


def test_project_folders_and_files_stay_exactly_the_same(two_accounts):
    """Nothing in the project folder changes, the catalog included."""
    client = two_accounts["client"]
    client.post("/auth/delete-account", json={"password": "marta-password-1"})
    assert files_of(two_accounts["folder"]) == two_accounts["before"]
    assert ".cataloga/catalog.db" in two_accounts["before"]
    assert (two_accounts["folder"] / "Documents" / "notes.txt").read_text() \
        == "Dawn swim notes."


def test_the_other_account_is_not_touched(two_accounts, fake_keychain):
    """Beto keeps his account, his folder, his key and his project."""
    client = two_accounts["client"]
    store = two_accounts["store"]
    client.post("/auth/delete-account", json={"password": "marta-password-1"})
    assert store.find("beto") is not None
    assert os.path.isfile(store.projects_path("beto"))
    assert "beto" in fake_keychain
    assert log_in(client, "beto").status_code == 200
    projects = client.get("/projects").get_json()["projects"]
    assert [p["name"] for p in projects] == ["Beto Files"]
    assert os.path.isdir(str(two_accounts["beto"]))


def test_the_deleted_account_cannot_log_in(two_accounts):
    """The username and password answer like any unknown account."""
    client = two_accounts["client"]
    client.post("/auth/delete-account", json={"password": "marta-password-1"})
    answer = log_in(client, "marta")
    assert answer.status_code == 401
    assert answer.get_json()["error"]["code"] == "wrong_login"
    status = client.get("/auth/status").get_json()
    assert status["account_exists"] is True


def test_the_only_account_leaves_an_empty_login(client, api_keys,
                                                fake_keychain):
    """With no account left, the app starts again from the first screen."""
    register(client, "solo")
    answer = client.post("/auth/delete-account",
                         json={"password": "solo-password-1"})
    assert answer.get_json() == {"deleted": True, "accounts_left": 0}
    status = client.get("/auth/status").get_json()
    assert status["account_exists"] is False
    with open(client.application.config["ACCOUNTS"].path,
              encoding="utf-8") as file:
        data = json.load(file)
    assert data == {"accounts": [], "last_username": ""}


def test_the_account_folder_is_only_removed_inside_users(two_accounts,
                                                         monkeypatch):
    """A folder name that resolves outside users/ is never removed."""
    store = two_accounts["store"]
    outside = os.path.dirname(store.data_folder)
    monkeypatch.setattr(store, "user_folder", lambda username: outside)
    assert store.delete("marta") is True
    assert os.path.isdir(outside)
    assert store.find("marta") is None


def test_the_screen_has_the_button_and_the_dialog():
    """Settings > Account ends with Delete account; the dialog lists it."""
    frontend = os.path.join(os.path.dirname(__file__), "..", "frontend")
    with open(os.path.join(frontend, "index.html"), encoding="utf-8") as f:
        html = f.read()
    account = html[html.index('id="account-section"'):]
    account = account[:account.index("</section>")]
    assert account.rstrip().endswith("</div>")
    assert 'id="delete-account-open"' in account
    assert account.index('id="delete-account-open"') > \
        account.index('id="recovery-confirm"')
    dialog = html[html.index('id="delete-account-dialog"'):]
    dialog = dialog[:dialog.index("</dialog>")]
    for key in ("delete.title", "delete.goes_account", "delete.goes_recovery",
                "delete.goes_keys", "delete.goes_settings", "delete.stays",
                "delete.catalogs", "delete.password", "delete.confirm"):
        assert 'data-i18n="{}"'.format(key) in dialog
    assert 'type="password" id="delete-password"' in dialog
    assert 'id="delete-confirm" disabled' in dialog
    assert dialog.index('id="delete-cancel"') < \
        dialog.index('id="delete-confirm"')
    with open(os.path.join(frontend, "js", "auth.js"), encoding="utf-8") as f:
        auth = f.read()
    assert "deleteAccount(field.value)" in auth
    assert "leaveApp()" in auth[auth.index("submitDeleteAccount"):]
