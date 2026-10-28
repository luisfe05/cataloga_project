"""Tests for the app's account, the login, and the session token."""

import json

import pytest

from backend.app import create_app
from backend.config import account
from backend.routes import auth
from tests.conftest import make_project

USERNAME = "luis"
PASSWORD = "first-password"


def assert_error(response, status, code):
    """Check the shared error shape: status code and error code."""
    assert response.status_code == status
    assert response.get_json()["error"]["code"] == code


@pytest.fixture
def auth_app(tmp_path, projects_path):
    """An app with one project, no account, and a logged-out client."""
    make_project(projects_path, tmp_path / "Research")
    app = create_app(projects_path=projects_path,
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


def create_account(client):
    """Create the test account and return the session token."""
    response = client.post("/auth/setup", json={"username": USERNAME,
                                                "password": PASSWORD})
    assert response.status_code == 201
    return response.get_json()["token"]


def login(client, password=PASSWORD, username=USERNAME):
    """Send a login request and return the response."""
    return client.post("/auth/login", json={"username": username,
                                            "password": password})


def bearer(token):
    """Return the header that carries a session token."""
    return {"Authorization": "Bearer " + token}


# --- Creating the account ---

def test_status_before_and_after_setup(client):
    """/auth/status works without a token and never sends the username."""
    response = client.get("/auth/status")
    assert response.status_code == 200
    assert response.get_json() == {"account_exists": False,
                                   "language": "en"}
    create_account(client)
    response = client.get("/auth/status")
    assert response.get_json()["account_exists"] is True
    assert USERNAME.encode() not in response.data


def test_setup_saves_only_a_bcrypt_hash(client, auth_app):
    """The account file keeps the username and a hash, never the password."""
    token = create_account(client)
    assert token
    path = auth_app.config["ACCOUNT_PATH"]
    assert path.endswith("app_data/account.json")
    with open(path) as file:
        text = file.read()
    assert PASSWORD not in text
    saved = json.loads(text)
    assert saved["username"] == USERNAME
    assert saved["password_hash"].startswith("$2b$")


def test_setup_logs_the_user_in(client):
    """The token from setup opens the other routes right away."""
    token = create_account(client)
    assert client.get("/settings", headers=bearer(token)).status_code == 200


def test_setup_only_once(client):
    """A second account cannot be created."""
    create_account(client)
    response = client.post("/auth/setup", json={"username": "other",
                                                "password": "other-pass"})
    assert_error(response, 409, "account_exists")


@pytest.mark.parametrize("body, code", [
    ({"username": "", "password": PASSWORD}, "missing_field"),
    ({"username": USERNAME}, "missing_field"),
    ({"username": USERNAME, "password": "short"}, "password_too_short"),
    ({"username": USERNAME, "password": "a" * 73}, "password_too_long"),
    # 37 letters with an accent are 74 bytes: too long for bcrypt.
    ({"username": USERNAME, "password": "á" * 37}, "password_too_long"),
])
def test_setup_checks_the_rules(client, body, code):
    """Missing fields and passwords outside the rules are refused."""
    assert_error(client.post("/auth/setup", json=body), 400, code)
    assert client.get("/auth/status").get_json()["account_exists"] is False


# --- Logging in ---

def test_login_with_the_right_password(client):
    """The right username and password give a working token."""
    create_account(client)
    response = login(client)
    assert response.status_code == 200
    token = response.get_json()["token"]
    assert client.get("/documents", headers=bearer(token)).status_code == 200


@pytest.mark.parametrize("username, password", [
    (USERNAME, "wrong-password"),
    ("someone", PASSWORD),
])
def test_login_with_a_wrong_password_or_username(client, username,
                                                 password):
    """A wrong username or password gives the same error."""
    create_account(client)
    assert_error(login(client, password, username), 401, "wrong_login")


def test_login_before_setup(client):
    """There is nothing to log in to before the account exists."""
    assert_error(login(client), 409, "no_account")


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
    """Before setup there is no session, so no token can match."""
    response = client.get("/settings", headers=bearer(""))
    assert_error(response, 401, "unauthorized")


def test_cors_preflight_needs_no_token(client):
    """The browser's OPTIONS check is never blocked."""
    response = client.options("/settings")
    assert response.status_code == 200


# --- The wait after 5 wrong passwords ---

def test_five_wrong_passwords_start_a_wait(client, clock):
    """Five wrong passwords start a wait that blocks every login."""
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
    """The new password follows the same rules as at setup."""
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


def test_account_file_is_not_in_a_project_folder(auth_app, tmp_path):
    """The account lives with the app data, not with the projects."""
    path = auth_app.config["ACCOUNT_PATH"]
    assert path == account.account_path_for(auth_app.config["PROJECTS_PATH"])
    assert not path.startswith(str(tmp_path / "Research"))
