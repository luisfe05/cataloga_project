"""A new account never sees anything of the account that logged out."""

import os

import pytest

from backend.app import create_app
from backend.config.terms import TERMS_VERSION
from backend.models.document import Document
from backend.routes import settings as settings_routes
from tests.conftest import make_project

FRONTEND = os.path.join(os.path.dirname(__file__), "..", "frontend")


@pytest.fixture
def client(tmp_path, data_folder):
    """A logged-out client on an app with no accounts yet."""
    app = create_app(data_folder=data_folder,
                     old_db_path=str(tmp_path / "no_old.db"))
    app.config["TESTING"] = True
    return app.test_client()


def register(client, username):
    """Create an account; the client then sends its token."""
    answer = client.post("/auth/register", json={
        "username": username, "password": username + "-password",
        "accepted_terms": TERMS_VERSION})
    assert answer.status_code == 201
    client.environ_base["HTTP_AUTHORIZATION"] = \
        "Bearer " + answer.get_json()["token"]
    return answer.get_json()


@pytest.fixture
def ana_then_beto(client, tmp_path):
    """Ana catalogs a file of Harbor Swimmers, logs out, Beto registers."""
    register(client, "ana")
    store = client.application.config["ACCOUNTS"]
    folder = tmp_path / "Harbor Swimmers"
    repo = make_project(store.projects_path("ana"), folder,
                        name="Harbor Swimmers")
    path = str(folder / "dawn_swim.txt")
    with open(path, "w") as file:
        file.write("The dawn swim of 1998.")
    repo.add_document(Document(
        "dawn_swim.txt", "dawn_swim.txt", "Documents", path,
        "2026-11-09T10:00:00", source="Harbor Gazette",
        summary="The dawn swim.", status="Manual Review"))
    # Ana sees her file before she leaves.
    assert client.get("/documents").get_json()
    client.post("/auth/logout")
    register(client, "beto")
    return client


@pytest.mark.parametrize("path", ["/documents", "/plan", "/dashboard/stats",
                                  "/browse", "/scan"])
def test_beto_gets_nothing_of_ana(ana_then_beto, path):
    """Catalog, To Approve, Dashboard, Home and the scan: no project."""
    answer = ana_then_beto.get(path)
    text = answer.get_data(as_text=True)
    assert "dawn_swim" not in text and "Harbor" not in text


def test_beto_chat_knows_nothing_of_ana(ana_then_beto):
    """The chat has no project to answer about."""
    answer = ana_then_beto.post("/chat", json={"message": "dawn swim",
                                               "history": []})
    assert "dawn_swim" not in answer.get_data(as_text=True)


def test_logout_forgets_the_ai_status(client):
    """The AI status kept for one account is not shown to the next."""
    register(client, "ana")
    settings_routes.status_cache[("ollama", "m", None)] = (0, "connected")
    client.post("/auth/logout")
    assert settings_routes.status_cache == {}


def test_the_screen_forgets_everything_on_logout():
    """Log out reloads the page: every view's memory starts empty."""
    with open(os.path.join(FRONTEND, "js", "auth.js"),
              encoding="utf-8") as file:
        auth_js = file.read()
    body = auth_js[auth_js.index("async function submitLogout"):]
    body = body[:body.index("\n}\n")]
    assert "leaveApp()" in body
    leave = auth_js[auth_js.index("function leaveApp"):]
    assert "location.reload()" in leave[:leave.index("\n}\n")]
