"""Tests for the accounts, the login, and the session token."""

import json
import os

import pytest

from backend.app import create_app
from backend.config import account, projects
from backend.routes import auth
from tests.conftest import make_project

USERNAME = "luis"
PASSWORD = "first-password"


def assert_error(response, status, code):
    """Check the shared error shape: status code and error code."""
    assert response.status_code == status
    assert response.get_json()["error"]["code"] == code


@pytest.fixture
def auth_app(tmp_path, data_folder):
    """An app with no accounts yet and a logged-out client."""
    app = create_app(data_folder=data_folder,
                     old_db_path=str(tmp_path / "no_old.db"))
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(auth_app):
    """A test client with no session token."""
    return auth_app.test_client()


@pytest.fixture
def clock(monkeypatch):
    """A fake clock for the wait after 5 wrong passwords."""
    fake = {"now": 1000.0}
    monkeypatch.setattr(auth, "now", lambda: fake["now"])
    return fake


def create_account(client, username=USERNAME, password=PASSWORD):
    """Create an account and return the session token."""
    response = client.post("/auth/register", json={"username": username,
                                                   "password": password})
    assert response.status_code == 201
    return response.get_json()["token"]


def login(client, password=PASSWORD, username=USERNAME):
    """Send a login request and return the response."""
    return client.post("/auth/login", json={"username": username,
                                            "password": password})


def bearer(token):
    """Return the header that carries a session token."""
    return {"Authorization": "Bearer " + token}


# --- Creating an account ---

def test_status_before_and_after_register(client):
    """/auth/status works without a token and never sends the username."""
    response = client.get("/auth/status")
    assert response.status_code == 200
    assert response.get_json() == {"account_exists": False,
                                   "language": "en"}
    create_account(client)
    response = client.get("/auth/status")
    assert response.get_json()["account_exists"] is True
    assert USERNAME.encode() not in response.data


def test_register_saves_only_a_bcrypt_hash(client, auth_app):
    """The accounts file keeps the username and a hash, never the password."""
    token = create_account(client)
    assert token
    path = auth_app.config["ACCOUNTS"].path
    assert path.endswith("app_data/accounts.json")
    with open(path) as file:
        text = file.read()
    assert PASSWORD not in text
    saved = json.loads(text)["accounts"][0]
    assert saved["username"] == USERNAME
    assert saved["password_hash"].startswith("$2b$")


def test_register_logs_the_user_in(client):
    """The token from register opens the other routes right away."""
    token = create_account(client)
    assert client.get("/settings", headers=bearer(token)).status_code == 200


@pytest.mark.parametrize("taken", [USERNAME, "LUIS", " luis "])
def test_username_taken(client, taken):
    """The same username, in any case, cannot be created twice."""
    create_account(client)
    response = client.post("/auth/register", json={"username": taken,
                                                   "password": "other-pass"})
    assert_error(response, 409, "username_taken")


@pytest.mark.parametrize("body, code", [
    ({"username": "", "password": PASSWORD}, "missing_field"),
    ({"username": USERNAME}, "missing_field"),
    ({"username": "ab", "password": PASSWORD}, "invalid_username"),
    ({"username": "luis gonzalez", "password": PASSWORD},
     "invalid_username"),
    ({"username": "a" * 31, "password": PASSWORD}, "invalid_username"),
    ({"username": USERNAME, "password": "short"}, "password_too_short"),
    ({"username": USERNAME, "password": "a" * 73}, "password_too_long"),
    # 37 letters with an accent are 74 bytes: too long for bcrypt.
    ({"username": USERNAME, "password": "á" * 37}, "password_too_long"),
])
def test_register_checks_the_rules(client, body, code):
    """Missing fields, bad usernames and bad passwords are refused."""
    assert_error(client.post("/auth/register", json=body), 400, code)
    assert client.get("/auth/status").get_json()["account_exists"] is False


# --- Several accounts on one computer ---

def test_each_account_sees_only_its_projects(client, auth_app, tmp_path):
    """Two accounts, two project lists, and the catalogs stay in place."""
    store = auth_app.config["ACCOUNTS"]
    token_a = create_account(client, "ana", "ana-password")
    make_project(store.projects_path("ana"), tmp_path / "Ana Research",
                 name="Ana Research")
    token_b = create_account(client, "beto", "beto-password")
    make_project(store.projects_path("beto"), tmp_path / "Beto Research",
                 name="Beto Research")

    # Registering beto replaced ana's token: ana logs in again.
    assert_error(client.get("/projects", headers=bearer(token_a)), 401,
                 "unauthorized")
    token_a = login(client, "ana-password", "ana").get_json()["token"]
    names = [p["name"] for p in client.get(
        "/projects", headers=bearer(token_a)).get_json()["projects"]]
    assert names == ["Ana Research"]
    token_b = login(client, "beto-password", "beto").get_json()["token"]
    names = [p["name"] for p in client.get(
        "/projects", headers=bearer(token_b)).get_json()["projects"]]
    assert names == ["Beto Research"]
    assert os.path.isfile(str(tmp_path / "Ana Research" / ".cataloga" /
                              "catalog.db"))
    assert client.get("/settings", headers=bearer(token_b)).get_json()[
        "username"] == "beto"


def test_language_is_per_account(client, auth_app):
    """Each account keeps its own language, and the login screen uses
    the language of whoever logged in last."""
    token_a = create_account(client, "ana", "ana-password")
    client.put("/settings", headers=bearer(token_a),
               json={"language": "es"})
    assert client.get("/auth/status").get_json()["language"] == "es"
    create_account(client, "beto", "beto-password")
    assert client.get("/auth/status").get_json()["language"] == "en"
    login(client, "ana-password", "ana")
    assert client.get("/auth/status").get_json()["language"] == "es"


def test_login_ignores_the_case_of_the_username(client):
    """'Luis' and 'luis' are the same account; the saved spelling wins."""
    create_account(client)
    response = login(client, username="LUIS")
    assert response.status_code == 200
    assert response.get_json()["username"] == USERNAME


# --- The old one-account install ---

def test_old_account_and_projects_are_migrated(tmp_path, data_folder):
    """The account keeps its password and sees its projects of always."""
    old_projects = os.path.join(data_folder, "projects.json")
    make_project(old_projects, tmp_path / "El Delfin", name="El Delfin")
    projects.set_language(old_projects, "es")
    account.save_account(os.path.join(data_folder, "account.json"),
                         "Luis G", PASSWORD)

    app = create_app(data_folder=data_folder,
                     old_db_path=str(tmp_path / "no_old.db"))
    client = app.test_client()
    assert client.get("/auth/status").get_json() == {
        "account_exists": True, "language": "es"}
    response = login(client, username="Luis G")
    assert response.status_code == 200
    token = response.get_json()["token"]
    names = [p["name"] for p in client.get(
        "/projects", headers=bearer(token)).get_json()["projects"]]
    assert names == ["El Delfin"]
    assert client.get("/settings", headers=bearer(token)).get_json()[
        "username"] == "Luis G"
    # The old files are kept as backups, not read again.
    assert not os.path.exists(old_projects)
    assert os.path.isfile(os.path.join(data_folder, "account.json.migrated"))
    assert os.path.isfile(os.path.join(data_folder, "users", "luis_g",
                                       "projects.json"))
    # A second start changes nothing.
    create_app(data_folder=data_folder,
               old_db_path=str(tmp_path / "no_old.db"))
    assert app.config["ACCOUNTS"].usernames() == ["Luis G"]


# --- Logging in ---

def test_login_with_the_right_password(client):
    """The right username and password give a working token."""
    create_account(client)
    response = login(client)
    assert response.status_code == 200
    token = response.get_json()["token"]
    assert client.get("/settings", headers=bearer(token)).status_code == 200


@pytest.mark.parametrize("username, password", [
    (USERNAME, "wrong-password"),
    ("someone", PASSWORD),
])
def test_login_with_a_wrong_password_or_username(client, username,
                                                 password):
    """A wrong username or password gives the same error."""
    create_account(client)
    assert_error(login(client, password, username), 401, "wrong_login")


def test_login_before_any_account(client):
    """With no accounts, a login fails like a wrong password."""
    assert_error(login(client), 401, "wrong_login")


def test_new_login_replaces_the_old_token(client):
    """Only one session at a time: the old token stops working."""
    first = create_account(client)
    second = login(client).get_json()["token"]
    assert_error(client.get("/settings", headers=bearer(first)), 401,
                 "unauthorized")
    assert client.get("/settings", headers=bearer(second)).status_code == 200


# --- The 401 without a token ---

@pytest.mark.parametrize("method, path", [
    ("get", "/documents"),
    ("get", "/documents/export"),
    ("get", "/settings"),
    ("put", "/settings"),
    ("get", "/dashboard/stats"),
    ("get", "/projects"),
    ("delete", "/projects"),
    ("post", "/auth/logout"),
    ("post", "/auth/password"),
])
def test_routes_need_a_token(client, method, path):
    """Without a token, every non-public route answers 401."""
    create_account(client)
    response = getattr(client, method)(path)
    assert_error(response, 401, "unauthorized")


def test_wrong_token_gives_401(client):
    """A made-up token does not work."""
    create_account(client)
    response = client.get("/settings", headers=bearer("made-up"))
    assert_error(response, 401, "unauthorized")


def test_no_token_works_before_any_login(client):
    """Before any login there is no session, so no token can match."""
    response = client.get("/settings", headers=bearer(""))
    assert_error(response, 401, "unauthorized")


def test_cors_preflight_needs_no_token(client):
    """The browser's OPTIONS check is never blocked."""
    response = client.options("/settings")
    assert response.status_code == 200


# --- The wait after 5 wrong passwords ---

def test_five_wrong_passwords_start_a_wait(client, clock):
    """Five wrong passwords start a wait that blocks that account."""
    create_account(client)
    for attempt in range(4):
        assert_error(login(client, "wrong-password"), 401, "wrong_login")
    response = login(client, "wrong-password")
    assert_error(response, 429, "too_many_attempts")
    assert response.get_json()["error"]["retry_after"] == auth.LOCK_SECONDS

    clock["now"] += 10
    response = login(client)
    assert_error(response, 429, "too_many_attempts")
    assert response.get_json()["error"]["retry_after"] == 20

    clock["now"] += 20
    assert login(client).status_code == 200


def test_the_wait_is_per_account(client, clock):
    """Ana's wrong passwords never lock Beto out."""
    create_account(client, "ana", "ana-password")
    create_account(client, "beto", "beto-password")
    for attempt in range(5):
        login(client, "wrong-password", "ana")
    assert_error(login(client, "ana-password", "ana"), 429,
                 "too_many_attempts")
    assert_error(login(client, "ana-password", "ANA"), 429,
                 "too_many_attempts")
    assert login(client, "beto-password", "beto").status_code == 200


def test_right_password_resets_the_count(client, clock):
    """Wrong tries only count when they are in a row."""
    create_account(client)
    for attempt in range(4):
        login(client, "wrong-password")
    assert login(client).status_code == 200
    for attempt in range(4):
        assert_error(login(client, "wrong-password"), 401, "wrong_login")


# --- Logging out ---

def test_logout_ends_the_session(client):
    """After Log out, the old token gives 401."""
    token = create_account(client)
    response = client.post("/auth/logout", headers=bearer(token))
    assert response.status_code == 200
    assert_error(client.get("/settings", headers=bearer(token)), 401,
                 "unauthorized")


# --- Changing the password (Settings > Account) ---

def change(client, token, current, new):
    """Send a password change and return the response."""
    return client.post("/auth/password", headers=bearer(token),
                       json={"current_password": current,
                             "new_password": new})


def test_change_password(client):
    """The new password works, the old one does not, the session stays."""
    token = create_account(client)
    response = change(client, token, PASSWORD, "second-password")
    assert response.status_code == 200
    assert client.get("/settings", headers=bearer(token)).status_code == 200
    assert_error(login(client, PASSWORD), 401, "wrong_login")
    assert login(client, "second-password").status_code == 200


def test_change_password_only_touches_that_account(client):
    """Beto's new password does not change Ana's."""
    create_account(client, "ana", "ana-password")
    token = create_account(client, "beto", "beto-password")
    assert change(client, token, "beto-password",
                  "beto-second").status_code == 200
    assert login(client, "ana-password", "ana").status_code == 200
    assert login(client, "beto-second", "beto").status_code == 200


def test_change_password_with_wrong_current(client):
    """A wrong current password changes nothing."""
    token = create_account(client)
    response = change(client, token, "wrong-password", "second-password")
    assert_error(response, 400, "wrong_password")
    assert login(client, PASSWORD).status_code == 200


@pytest.mark.parametrize("new, code", [
    ("short", "password_too_short"),
    ("a" * 73, "password_too_long"),
])
def test_change_password_checks_the_rules(client, new, code):
    """The new password follows the same rules as at register."""
    token = create_account(client)
    assert_error(change(client, token, PASSWORD, new), 400, code)
    assert login(client, PASSWORD).status_code == 200


def test_change_password_counts_wrong_tries(client, clock):
    """Wrong current passwords count toward the login wait."""
    token = create_account(client)
    for attempt in range(4):
        assert_error(change(client, token, "wrong-password", "new-password"),
                     400, "wrong_password")
    assert_error(change(client, token, "wrong-password", "new-password"),
                 429, "too_many_attempts")
    assert_error(login(client), 429, "too_many_attempts")


def test_settings_shows_the_username(client):
    """Settings > Account shows the username (read only)."""
    token = create_account(client)
    settings = client.get("/settings", headers=bearer(token)).get_json()
    assert settings["username"] == USERNAME


def test_accounts_file_is_not_in_a_project_folder(auth_app, tmp_path):
    """The accounts live with the app data, not with the projects."""
    path = auth_app.config["ACCOUNTS"].path
    assert path.startswith(str(tmp_path / "app_data"))
    assert not path.startswith(str(tmp_path / "Research"))
