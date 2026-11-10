"""An account is made only after the Terms and Privacy are accepted."""

import os
import re

import pytest

from backend.app import create_app
from backend.config import terms
from backend.config.terms import TERMS_VERSION


@pytest.fixture
def client(tmp_path, data_folder):
    """A logged-out client on an app with no accounts yet."""
    app = create_app(data_folder=data_folder,
                     old_db_path=str(tmp_path / "no_old.db"))
    app.config["TESTING"] = True
    return app.test_client()


BODY = {"username": "marta", "password": "harbor-pass-1"}
FRONTEND = os.path.join(os.path.dirname(__file__), "..", "frontend")


def read(*parts):
    """Return the text of a frontend file."""
    with open(os.path.join(FRONTEND, *parts), encoding="utf-8") as file:
        return file.read()


@pytest.mark.parametrize("accepted", [None, False, "", "2020-01-01"])
def test_no_account_without_the_terms(client, accepted):
    """Missing, false or an old version: refused, nothing is saved."""
    body = dict(BODY)
    if accepted is not None:
        body["accepted_terms"] = accepted
    answer = client.post("/auth/register", json=body)
    assert answer.status_code == 400
    assert answer.get_json()["error"]["code"] == "terms_not_accepted"
    assert client.get("/auth/status").get_json()["account_exists"] is False


def test_the_version_and_date_are_kept(client):
    """The account keeps the version it accepted and when."""
    body = dict(BODY, accepted_terms=TERMS_VERSION)
    assert client.post("/auth/register", json=body).status_code == 201
    entry = client.application.config["ACCOUNTS"].find("marta")
    assert entry["terms"]["version"] == TERMS_VERSION
    assert entry["terms"]["accepted"][:4].isdigit()


def test_a_new_version_asks_again_at_login(client, monkeypatch):
    """After the terms change, the login says so until they are accepted."""
    client.post("/auth/register", json=dict(BODY,
                                            accepted_terms=TERMS_VERSION))
    login = {"username": "marta", "password": "harbor-pass-1"}
    assert client.post("/auth/login", json=login).get_json()["terms_ok"]
    monkeypatch.setattr(terms, "TERMS_VERSION", "2027-01-01")
    monkeypatch.setattr("backend.routes.auth.TERMS_VERSION", "2027-01-01")
    answer = client.post("/auth/login", json=login).get_json()
    assert answer["terms_ok"] is False
    headers = {"Authorization": "Bearer " + answer["token"]}
    client.post("/auth/terms", json={"version": "2027-01-01"},
                headers=headers)
    assert client.post("/auth/login", json=login).get_json()["terms_ok"]


def test_the_final_version_replaces_the_temporary_one():
    """2026-11-09 was the temporary text; the final one asks again."""
    assert TERMS_VERSION == "2026-11-09.1"


def test_an_account_on_the_temporary_text_is_asked_again(client):
    """An account that accepted "2026-11-09" sees the overlay at login."""
    client.post("/auth/register", json=dict(BODY,
                                            accepted_terms=TERMS_VERSION))
    client.application.config["ACCOUNTS"].accept_terms("marta", "2026-11-09")
    login = {"username": "marta", "password": "harbor-pass-1"}
    assert client.post("/auth/login", json=login).get_json()["terms_ok"] \
        is False


@pytest.mark.parametrize("name, title", [
    ("terms.html", "Terms and Conditions"),
    ("privacy.html", "Privacy Policy"),
])
def test_the_legal_pages_carry_the_final_text(name, title):
    """Final text, effective date, no temporary notice, no [...] markers."""
    page = read("legal", name)
    assert "<h1>{}</h1>".format(title) in page
    assert "Effective date: November 9, 2026" in page
    assert "not published yet" not in page
    assert "Temporary" not in page
    # No [...] placeholder; "[REDACTED]" is the one mark the text names.
    assert not re.search(r"\[(?!REDACTED\])[^\]]*\]", page)
    # Self-contained: the app's own stylesheet, no scripts, no internet.
    assert 'href="../css/main.css"' in page
    assert "<script" not in page and "http" not in page.split("<body")[1]


def test_the_terms_match_the_new_limits():
    """Section 6 says what the assistant does and does not do."""
    page = read("legal", "terms.html")
    assert "does not search the internet" in page
    assert "refuse, block or pause" in page
    privacy = read("legal", "privacy.html")
    assert "the kind of block and the project name" in privacy
    assert "never read or sent" in privacy


def test_the_overlay_and_settings_link_the_pages_inside_the_app():
    """Login, the Terms overlay and Settings open the pages in a dialog."""
    html = read("index.html")
    assert html.count('href="legal/terms.html" class="legal-link"') == 3
    assert html.count('href="legal/privacy.html" class="legal-link"') == 3
    # No link leaves the app: pywebview would send it to the browser.
    assert 'target="_blank"' not in html
    assert 'id="legal-dialog"' in html and 'id="legal-frame"' in html
    assert 'closest("a.legal-link")' in read("js", "auth.js")


def test_the_overlay_points_say_what_the_terms_say():
    """Four points, each backed by the final text."""
    html = read("index.html")
    assert html.count('data-i18n="terms.point_') == 4
    en = read("js", "lang", "en.js")
    assert "their content is sent to the AI" in en
    assert "The developer is not liable" in en
    assert "↗" not in en


LANDING = os.path.join(os.path.dirname(__file__), "..", "..", "Design",
                       "cataloga-landing")


def test_the_privacy_policy_says_what_happens_to_secrets_and_accounts():
    """Hidden secrets, their limit and Delete account, in both copies."""
    for folder in (os.path.join(FRONTEND, "legal"), LANDING):
        with open(os.path.join(folder, "privacy.html"),
                  encoding="utf-8") as file:
            privacy = file.read()
        assert "never read or sent" in privacy
        assert "replaces each one with &quot;[REDACTED]&quot;" in privacy
        assert "keeps only how many were hidden, never the secret" in privacy
        assert "cannot recognize every password written in free text" \
            in privacy
        assert "Delete your account in Settings › Account" in privacy
        assert "project folders stay exactly where they are" in privacy
        assert "Effective date: November 9, 2026" in privacy
        with open(os.path.join(folder, "terms.html"),
                  encoding="utf-8") as file:
            page = file.read()
        assert "delete your account at any time in Settings › Account" \
            in page
        assert "never touches your project folders" in page
        assert "Effective date: November 9, 2026" in page
