"""Show in Finder and Open: only files inside the project, checked here."""

import os

import pytest

from backend.db.schema import get_connection
from backend.pipeline import file_organizer
from tests.test_browse import project  # noqa: F401


@pytest.fixture
def started(monkeypatch):
    """Record the commands instead of running them."""
    commands = []
    monkeypatch.setattr(file_organizer.subprocess, "Popen",
                        lambda args, **kwargs: commands.append(args))
    return commands


def test_show_in_finder_and_open_a_project_file(flask_client, project,
                                                started):
    """open -R shows it; open opens it. Nothing moves or is renamed."""
    root, repo, doc = project
    before = sorted(os.listdir(root))
    for route in ("/browse/reveal", "/browse/open"):
        answer = flask_client.post(route, json={"path": "nota.txt"})
        assert answer.status_code == 200
    path = os.path.join(root, "nota.txt")
    assert started == [["open", "-R", path], ["open", path]]
    assert sorted(os.listdir(root)) == before


@pytest.mark.parametrize("path", ["../outside.txt", "Fotos/../../x.txt",
                                  "/etc/hosts", "../../../../etc/hosts"])
def test_a_path_outside_the_project_is_refused(flask_client, project,
                                               started, path):
    """.. and absolute paths: refused, and nothing runs."""
    for route in ("/browse/reveal", "/browse/open"):
        answer = flask_client.post(route, json={"path": path})
        assert answer.status_code == 400
        assert answer.get_json()["error"]["code"] == "outside_project"
    assert started == []


def test_a_missing_file_says_so(flask_client, project, started):
    """A clear error, not a crash, and nothing runs."""
    for route in ("/browse/reveal", "/browse/open"):
        answer = flask_client.post(route, json={"path": "gone.pdf"})
        assert answer.status_code == 409
        assert answer.get_json()["error"]["message"] == \
            "The file is not there anymore."
    assert started == []


def test_open_needs_a_file_not_a_folder(flask_client, project, started):
    """A folder can be shown in Finder, but Open is for files."""
    assert flask_client.post("/browse/reveal",
                             json={"path": "Fotos"}).status_code == 200
    assert flask_client.post("/browse/open",
                             json={"path": "Fotos"}).status_code == 409


def test_a_document_outside_the_project_is_refused(flask_client, project,
                                                   started, tmp_path):
    """By id too: the path in the catalog is checked before running."""
    root, repo, doc = project
    outside = tmp_path / "elsewhere.txt"
    outside.write_text("x")
    # The app never writes such a path; the test puts it there directly.
    conn = get_connection(repo.db_path)
    conn.execute("UPDATE documents SET file_path = ? WHERE id = ?",
                 (str(outside), doc.id))
    conn.commit()
    conn.close()
    for action in ("open", "reveal"):
        answer = flask_client.post(
            "/documents/{}/{}".format(doc.id, action))
        assert answer.status_code == 409
    assert started == []
