"""An account is made only after the Terms and Privacy are accepted."""

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
