"""Tests for opening, revealing, and previewing a document's file."""

import os

import pytest

from backend.config import projects
from backend.db.catalog_repository import CatalogRepository
from backend.models.document import Document
from backend.pipeline import file_organizer

# Each endpoint and the command it must start, with {path} for the file.
ACTIONS = [
    ("open", ["open", "{path}"]),
    ("reveal", ["open", "-R", "{path}"]),
    ("preview", ["qlmanage", "-p", "{path}"]),
]


@pytest.fixture
def repo(app):
    """Return a CatalogRepository on the same database as the app."""
    return CatalogRepository(
        projects.catalog_path(app.config["PROJECT_FOLDER"]))


@pytest.fixture
def started(monkeypatch):
    """Replace subprocess.Popen and return the list of calls it got."""
    calls = []

    def fake_popen(arguments, **options):
        calls.append({"arguments": arguments, "options": options})

    monkeypatch.setattr(file_organizer.subprocess, "Popen", fake_popen)
    return calls


def add_doc(repo, path):
    """Save one document whose file_path is path."""
    return repo.add_document(Document(
        original_filename="scan.pdf",
        filename=os.path.basename(path),
        media_type="Press",
        file_path=path,
        date_added="2026-10-21T10:00:00",
    ))


@pytest.fixture
def real_doc(app, repo):
    """A document whose file exists inside the project, with a space."""
    path = os.path.join(app.config["PROJECT_FOLDER"], "Press",
                        "oceanman malta.pdf")
    with open(path, "w") as handle:
        handle.write("content")
    return add_doc(repo, path)


@pytest.mark.parametrize("action, command", ACTIONS)
def test_action_starts_the_command(flask_client, started, real_doc,
                                   action, command):
    """The right command starts with the path as one list item."""
    response = flask_client.post(
        "/documents/{}/{}".format(real_doc.id, action))

    assert response.status_code == 200
    assert response.get_json() == {"ok": True}
    expected = [part.replace("{path}", real_doc.file_path)
                for part in command]
    assert started[0]["arguments"] == expected
    # A list and no shell: the file name can never run anything else.
    assert "shell" not in started[0]["options"]


@pytest.mark.parametrize("action, command", ACTIONS)
def test_action_unknown_id(flask_client, started, action, command):
    """A missing id gives 404 and starts nothing."""
    response = flask_client.post("/documents/99/{}".format(action))
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "not_found"
    assert started == []


@pytest.mark.parametrize("action, command", ACTIONS)
def test_action_missing_file(flask_client, started, real_doc, action,
                             command):
    """A file that is gone gives 409 file_missing."""
    os.remove(real_doc.file_path)
    response = flask_client.post(
        "/documents/{}/{}".format(real_doc.id, action))
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "file_missing"
    assert started == []


@pytest.mark.parametrize("action, command", ACTIONS)
def test_action_file_outside_project(flask_client, started, repo,
                                     tmp_path, action, command):
    """A file that exists but is outside the project gives 409."""
    outside = tmp_path / "elsewhere.pdf"
    outside.write_text("content")
    doc = add_doc(repo, str(outside))
    response = flask_client.post("/documents/{}/{}".format(doc.id, action))
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "file_missing"
    assert started == []


@pytest.mark.parametrize("action, command", ACTIONS)
def test_action_path_escaping_with_dots(flask_client, started, repo, app,
                                        tmp_path, action, command):
    """A path that leaves the project with .. is outside it too."""
    outside = tmp_path / "secret.pdf"
    outside.write_text("content")
    sneaky = os.path.join(app.config["PROJECT_FOLDER"], "Press", "..",
                          "..", "secret.pdf")
    doc = add_doc(repo, sneaky)
    response = flask_client.post("/documents/{}/{}".format(doc.id, action))
    assert response.status_code == 409
    assert started == []


@pytest.mark.parametrize("action, command", ACTIONS)
def test_action_needs_the_token(app, started, real_doc, action, command):
    """Without the session token, every action answers 401."""
    response = app.test_client().post(
        "/documents/{}/{}".format(real_doc.id, action))
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "unauthorized"
    assert started == []
