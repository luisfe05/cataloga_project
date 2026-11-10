"""Recovery keys: made with the account, saved by the user, used to reset."""

import json
import logging
import os
import re

import pytest

from backend.app import create_app
from backend.config import recovery
from backend.config.terms import TERMS_VERSION
from backend.routes import auth
from tests.conftest import make_project

KEY_SHAPE = re.compile(r"^[A-HJ-NP-Z2-9]{4}(-[A-HJ-NP-Z2-9]{4}){3}$")


@pytest.fixture
def client(tmp_path, data_folder):
    """A logged-out client on an app with no accounts yet."""
    app = create_app(data_folder=data_folder,
                     old_db_path=str(tmp_path / "no_old.db"))
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def clock(monkeypatch):
    """A fake clock for the wait after 5 wrong keys."""
    fake = {"now": 1000.0}
    monkeypatch.setattr(auth, "now", lambda: fake["now"])
    return fake


def register(client, username="marta", password="harbor-pass-1"):
    """Create an account, keep its token on the client, return the answer."""
    answer = client.post("/auth/register", json={
        "username": username, "password": password,
        "accepted_terms": TERMS_VERSION})
    assert answer.status_code == 201
    client.environ_base["HTTP_AUTHORIZATION"] = \
        "Bearer " + answer.get_json()["token"]
    return answer.get_json()


def reset(client, key, username="marta", new="new-harbor-pass"):
    """Ask for a new password with a recovery key."""
    return client.post("/auth/recovery/reset", json={
        "username": username, "recovery_key": key, "new_password": new})


def test_a_new_account_gets_a_key(client, fake_keychain):
    """The key has the shape, its hash is in the account, the key in the
    Keychain, and it is not saved to a file yet."""
    answer = register(client)
    key = answer["recovery_key"]
    assert KEY_SHAPE.match(key)
    assert not set(key) & set("01OI")
    assert fake_keychain["marta"] == key
    entry = client.application.config["ACCOUNTS"].find("marta")
    assert entry["recovery_hash"].startswith("$2b$")
    assert key not in json.dumps(entry)
    assert client.get("/auth/recovery").get_json() == {"saved": ""}


def test_a_typed_key_can_have_any_case_and_spacing():
    """'abcd efgh …' reads as 'ABCD-EFGH-…'."""
    assert recovery.clean_key("hbrs 7k2q-m9xp4twd") == "HBRS-7K2Q-M9XP-4TWD"
    assert recovery.clean_key("too-short") == ""


def test_reset_with_the_right_key_changes_the_password(client,
                                                       fake_keychain):
    """The new password works, the old one does not, the key rotates."""
    old_key = register(client)["recovery_key"]
    client.post("/auth/logout")
    answer = reset(client, old_key.lower())
    assert answer.status_code == 200
    new_key = answer.get_json()["recovery_key"]
    assert new_key != old_key and fake_keychain["marta"] == new_key
    logins = [client.post("/auth/login", json={
        "username": "marta", "password": p}).status_code
        for p in ("harbor-pass-1", "new-harbor-pass")]
    assert logins == [401, 200]
    # The old key stops working.
    client.post("/auth/logout")
    assert reset(client, old_key).get_json()["error"]["code"] == \
        "wrong_recovery"


def test_a_wrong_username_or_key_get_the_same_answer(client):
    """Never says which of the two is wrong."""
    key = register(client)["recovery_key"]
    client.post("/auth/logout")
    wrong_key = reset(client, "AAAA-BBBB-CCCC-DDDD").get_json()["error"]
    wrong_user = reset(client, key, username="nobody").get_json()["error"]
    assert wrong_key == wrong_user
    assert wrong_key["message"] == "Username or recovery key is wrong."


def test_five_wrong_keys_wait_five_minutes(client, clock):
    """The 5th wrong key locks the reset; it opens again after 300 s."""
    key = register(client)["recovery_key"]
    client.post("/auth/logout")
    for _ in range(4):
        assert reset(client, "AAAA-BBBB-CCCC-DDDD").status_code == 400
    assert reset(client, "AAAA-BBBB-CCCC-DDDD").status_code == 429
    # Even the right key waits.
    assert reset(client, key).status_code == 429
    clock["now"] += 299
    assert reset(client, key).status_code == 429
    clock["now"] += 2
    assert reset(client, key).status_code == 200


def test_showing_or_renewing_the_key_needs_the_password(client,
                                                        fake_keychain):
    """Save current key and Get a new key both ask for the password."""
    key = register(client)["recovery_key"]
    for body in ({}, {"password": "wrong-pass"}, {"new": True}):
        answer = client.post("/auth/recovery/key", json=body)
        assert answer.status_code == 400
        assert "recovery_key" not in answer.get_json()
    same = client.post("/auth/recovery/key",
                       json={"password": "harbor-pass-1"}).get_json()
    assert same["recovery_key"] == key
    new = client.post("/auth/recovery/key", json={
        "password": "harbor-pass-1", "new": True}).get_json()
    assert new["recovery_key"] != key
    assert fake_keychain["marta"] == new["recovery_key"]
    # The old key no longer resets the password.
    client.post("/auth/logout")
    assert reset(client, key).status_code == 400


def test_the_key_is_saved_to_the_chosen_file(client, tmp_path):
    """The file has the username, the key, the date and the steps."""
    answer = register(client)
    path = str(tmp_path / "Documents" / "Cataloga Recovery Key - marta.txt")
    os.makedirs(os.path.dirname(path))
    saved = client.post("/auth/recovery/save", json={
        "path": path, "ticket": answer["save_ticket"]})
    assert saved.status_code == 200
    with open(path, encoding="utf-8") as file:
        text = file.read()
    assert "marta" in text and answer["recovery_key"] in text
    assert saved.get_json()["saved"] in text and "Forgot your password" in text
    assert client.get("/auth/recovery").get_json()["saved"] == \
        saved.get_json()["saved"]
    # A ticket is used once: saving again needs the password.
    again = client.post("/auth/recovery/save", json={
        "path": path, "ticket": answer["save_ticket"]})
    assert again.status_code == 403


def test_the_key_file_cannot_go_into_a_project(client, tmp_path):
    """Inside a project folder, or below it, the save is refused."""
    answer = register(client)
    store = client.application.config["ACCOUNTS"]
    folder = tmp_path / "Harbor Swimmers"
    make_project(store.projects_path("marta"), folder)
    os.makedirs(folder / "Press", exist_ok=True)
    for path in (folder / "key.txt", folder / "Press" / "key.txt"):
        refused = client.post("/auth/recovery/save", json={
            "path": str(path), "ticket": answer["save_ticket"]})
        assert refused.get_json()["error"]["code"] == "inside_project"
        assert not os.path.exists(path)


def test_the_key_never_reaches_the_log(client, caplog):
    """Creating, showing and resetting log nothing of the key."""
    caplog.set_level(logging.DEBUG)
    key = register(client)["recovery_key"]
    client.post("/auth/recovery/key", json={"password": "harbor-pass-1"})
    client.post("/auth/logout")
    new_key = reset(client, key).get_json()["recovery_key"]
    assert key not in caplog.text and new_key not in caplog.text
