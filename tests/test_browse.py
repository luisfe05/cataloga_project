"""Tests for the Home screen's routes: listing, small pictures, preview."""

import os

import pytest
from PIL import Image

from backend import scanner
from backend.config import projects
from backend.db.catalog_repository import CatalogRepository
from backend.models.document import Document
from backend.pipeline import file_readers, thumbnails
from tests.conftest import TEST_TOKEN


@pytest.fixture
def project(app):
    """A folder with subfolders, a photo, hidden files and a row."""
    root = os.path.realpath(app.config["PROJECT_FOLDER"])
    os.makedirs(os.path.join(root, "Fotos", "1997"))
    os.makedirs(os.path.join(root, "Vacia"))
    os.makedirs(os.path.join(root, ".git"))
    Image.new("RGB", (800, 600), "white").save(
        os.path.join(root, "Fotos", "1997", "a.jpg"))
    with open(os.path.join(root, "nota.txt"), "w") as file:
        file.write("Una nota")
    for hidden in (".DS_Store", "._a.jpg", "b.tmp"):
        with open(os.path.join(root, hidden), "w") as file:
            file.write("x")
    repo = CatalogRepository(projects.catalog_path(root))
    doc = repo.add_document(Document(
        "nota.txt", "nota.txt", "Documents", os.path.join(root, "nota.txt"),
        "2026-11-01T10:00:00", source="Archivo", summary="Una nota.",
        document_date="2026-11-01", date_source="content",
        folder_reason="Es una nota."))
    return root, repo, doc


def test_listing_the_top_folder(flask_client, project):
    """Folders with their counts, files with the catalog's data, no hidden."""
    root, repo, doc = project
    listed = flask_client.get("/browse").get_json()
    found = {f["name"]: f["files"] for f in listed["folders"]}
    assert found["Fotos"] == 1 and found["Vacia"] == 0
    assert ".git" not in found and ".cataloga" not in found
    assert [f["name"] for f in listed["files"]] == ["nota.txt"]
    note = listed["files"][0]
    assert note["document"]["id"] == doc.id
    assert note["document"]["source"] == "Archivo"
    assert note["document"]["why"] == "Es una nota."
    assert note["size"] == 8 and note["extension"] == "txt"
    assert listed["totals"]["files"] == 2
    assert listed["totals"]["cataloged"] == 1


def test_listing_a_subfolder_and_a_file_not_cataloged(flask_client, project):
    """Works with no row: nothing here needs the AI."""
    listed = flask_client.get("/browse?path=Fotos/1997").get_json()
    assert listed["path"] == "Fotos/1997"
    photo = listed["files"][0]
    assert photo["name"] == "a.jpg" and photo["photo"] is True
    assert photo["document"] is None


@pytest.mark.parametrize("path", ["..", "../..", "Fotos/../..", "/etc",
                                  "No-existe", ".cataloga"])
def test_a_path_outside_or_unknown_is_refused(flask_client, project, path):
    """Nothing outside the project, and never the catalog's own folder."""
    response = flask_client.get("/browse", query_string={"path": path})
    assert response.status_code == 404


def test_a_small_picture_is_kept_in_cataloga_only(app, flask_client, project):
    """Made once, in .cataloga/thumbs; the user's folders do not change."""
    root, repo, doc = project
    before = sorted(os.listdir(os.path.join(root, "Fotos", "1997")))
    url = "/browse/thumb?path=Fotos/1997/a.jpg&token=" + TEST_TOKEN
    answer = app.test_client().get(url)
    assert answer.status_code == 200
    assert answer.mimetype == "image/jpeg"
    made = os.listdir(os.path.join(root, ".cataloga", "thumbs"))
    assert len(made) == 1
    assert sorted(os.listdir(os.path.join(root, "Fotos", "1997"))) == before
    with Image.open(os.path.join(root, ".cataloga", "thumbs", made[0])) as pic:
        assert max(pic.size) <= thumbnails.THUMB_SIDE


def test_a_small_picture_is_not_made_twice(project, monkeypatch):
    """The second time it comes from .cataloga, with no photo opened."""
    root, repo, doc = project
    path = os.path.join(root, "Fotos", "1997", "a.jpg")
    first = thumbnails.thumbnail_for(root, path)

    def must_not_open(*args):
        raise AssertionError("the photo was opened again")

    monkeypatch.setattr(file_readers, "open_photo", must_not_open)
    assert thumbnails.thumbnail_for(root, path) == first


def test_a_changed_photo_gets_a_new_picture(project):
    """The name comes from the size and date."""
    root, repo, doc = project
    path = os.path.join(root, "Fotos", "1997", "a.jpg")
    first = thumbnails.thumb_path(root, path)
    os.utime(path, (1000000, 1000000))
    assert thumbnails.thumb_path(root, path) != first


def test_no_picture_for_a_document_or_a_file_only_in_icloud(
        flask_client, project, monkeypatch):
    """A file only in iCloud is never opened."""
    root, repo, doc = project
    assert flask_client.get("/browse/thumb?path=nota.txt").status_code == 404
    monkeypatch.setattr(file_readers, "in_cloud_only", lambda path: True)
    assert flask_client.get(
        "/browse/thumb?path=Fotos/1997/a.jpg").status_code == 404


def test_the_scan_never_reads_the_small_pictures(flask_client, project):
    """They live in .cataloga, which is never walked."""
    root, repo, doc = project
    flask_client.get("/browse/thumb?path=Fotos/1997/a.jpg")
    assert not any(".cataloga" in path for path in scanner.find_files(root))


def test_preview_and_reveal_work_by_path(flask_client, project, monkeypatch):
    """With no row too."""
    root, repo, doc = project
    answer = flask_client.get("/browse/preview?path=Fotos/1997/a.jpg")
    assert answer.get_json()["kind"] == "image"
    assert answer.get_json()["filename"] == "a.jpg"
    assert flask_client.get("/browse/preview?path=../x").status_code == 409
    started = []
    from backend.pipeline import file_organizer
    monkeypatch.setattr(file_organizer.subprocess, "Popen",
                        lambda args, **kwargs: started.append(args))
    assert flask_client.post("/browse/reveal",
                             json={"path": "nota.txt"}).status_code == 200
    assert started == [["open", "-R", os.path.join(root, "nota.txt")]]
    assert flask_client.post("/browse/reveal",
                             json={"path": "../x"}).status_code == 409


def test_the_token_in_an_address_opens_only_pictures_and_recordings(
        app, flask_client, project):
    """Not the listing, the preview, or the rest."""
    bare = app.test_client()
    for path in ("/browse", "/browse/preview?path=nota.txt"):
        joined = path + ("&" if "?" in path else "?") + "token=" + TEST_TOKEN
        assert bare.get(joined).status_code == 401
    assert bare.get("/browse/thumb?path=Fotos/1997/a.jpg").status_code == 401
