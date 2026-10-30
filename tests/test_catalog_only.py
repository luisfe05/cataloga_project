"""Tests for kept names, protected names, secrets, and Catalog only."""

import json
import os

import pytest

from backend.db.catalog_repository import CatalogRepository
from backend.pipeline import archive_rules, naming
from backend.pipeline.file_organizer import FileOrganizer
# The fixtures come along with the helpers.
from tests.test_classification_pipeline import (  # noqa: F401
    fake_keyring, make_text_file, setup)
from tests.test_project_folders import add_file_doc


@pytest.mark.parametrize("name, protected", [
    ("index.html", True), ("INDEX.HTML", True), ("README.md", True),
    ("readme", True), ("package.json", True), (".gitignore", True),
    ("favicon.ico", True), ("vite.config.js", True), ("yarn.lock", True),
    ("Makefile", True), ("carta.pdf", False), ("index-old.html", False),
])
def test_protected_names(name, protected):
    """Files other programs look for by name are protected."""
    assert naming.is_protected(name) is protected


@pytest.mark.parametrize("name, secret", [
    (".env", True), (".env.local", True), ("server.pem", True),
    ("site.key", True), ("id_rsa", True), ("id_rsa.pub", True),
    ("credentials.json", True), ("cert.p12", True), ("login.keychain", True),
    ("keys.txt", False), ("environment.pdf", False),
])
def test_secret_names(name, secret):
    """Files that may hold keys or passwords are recognized by name."""
    assert archive_rules.is_secret(name) is secret


def test_keep_template_is_valid():
    """'keep' is a template the settings accept."""
    assert naming.validate_template(naming.KEEP_NAMES) is None


# --- The pipeline ---

def test_keep_original_names_classifies_and_moves_without_renaming(setup):
    """With Keep original names the file moves, with the same name."""
    setup["repo"].save_naming_template(naming.KEEP_NAMES)
    pipeline, ai = setup["build"]()
    doc = pipeline.classify_document(
        make_text_file(setup["drop_zone"], "Carta de Ramón.txt"))
    assert doc.filename == "Carta de Ramón.txt"
    assert doc.status == "Classified"
    assert doc.source == "El Nuevo Día"
    assert os.path.dirname(doc.file_path).endswith("Press")


def test_protected_names_are_never_renamed(setup):
    """index.html keeps its name whatever the naming method is."""
    pipeline, ai = setup["build"]()
    doc = pipeline.classify_document(
        make_text_file(setup["drop_zone"], "README.txt"))
    assert doc.filename == "README.txt"
    assert doc.status == "Classified"


def test_secret_files_are_never_read(setup):
    """.env goes to Manual Review by its name; the AI never sees it."""
    pipeline, ai = setup["build"]()
    path = make_text_file(setup["drop_zone"], ".env", "KEY=abc")
    (setup["drop_zone"] / "server.pem").write_text("-----BEGIN-----")
    doc = pipeline.classify_document(path)
    pem = pipeline.classify_document(str(setup["drop_zone"] / "server.pem"))
    assert ai.calls == 0
    for item in (doc, pem):
        assert item.status == "Manual Review"
        assert item.review_note == archive_rules.SECRET_NOTE
        assert item.summary is None
        assert os.path.isfile(item.file_path)
    assert doc.file_path == path
    assert doc.filename == ".env"
    assert "abc" not in json.dumps(doc.to_dict())


# --- Catalog only ---

def make_site(root):
    """A small website with linked files."""
    (root / "css").mkdir(parents=True)
    (root / "index.html").write_text(
        '<html><link href="css/site.css"><img src="logo.png"></html>')
    (root / "css" / "site.css").write_text("body { color: red }")
    (root / "logo.png").write_bytes(b"png")
    (root / "notas.txt").write_text("Notas sobre el sitio del documental.")
    return root


def test_create_a_catalog_only_project(empty_client, tmp_path):
    """No tree is needed; no folder, not even a Drop Zone, is created."""
    site = make_site(tmp_path / "site")
    before = sorted(os.listdir(str(site)))
    response = empty_client.post("/projects", json={
        "name": "Site", "folder": str(site), "catalog_only": True,
        "description": "La página web del documental"})
    assert response.status_code == 201
    assert sorted(os.listdir(str(site))) == sorted(before + [".cataloga"])
    settings = empty_client.get("/settings").get_json()
    assert settings["folder_mode"] == "catalog"
    assert settings["naming_template"] == "keep"
    assert settings["project_description"].startswith("La página")


def test_catalog_only_never_moves_or_renames(setup, tmp_path):
    """In a catalog project the pipeline leaves the file where it is."""
    repo = setup["repo"]
    repo.save_config_value("folder_mode", "catalog")
    repo.save_naming_template(naming.KEEP_NAMES)
    pipeline, ai = setup["build"]()
    path = make_text_file(setup["drop_zone"], "Notas del sitio.txt")
    doc = pipeline.classify_document(path)
    assert doc.file_path == path
    assert doc.filename == "Notas del sitio.txt"
    assert doc.status == "Classified"
    assert doc.summary == "A news story."
    assert sorted(os.listdir(str(setup["drop_zone"]))) == \
        ["Notas del sitio.txt"]


def test_catalog_only_refuses_move_and_rename(empty_client, tmp_path):
    """Move and Rename answer 409 catalog_only; nothing on disk changes."""
    site = make_site(tmp_path / "site")
    empty_client.post("/projects", json={
        "name": "Site", "folder": str(site), "catalog_only": True})
    repo = CatalogRepository(os.path.join(str(site), ".cataloga",
                                          "catalog.db"))
    doc = add_file_doc(repo, str(site / "notas.txt"))
    response = empty_client.post("/documents/{}/rename".format(doc.id),
                                 json={"new_name": "otro"})
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "catalog_only"
    response = empty_client.post("/documents/{}/move".format(doc.id),
                                 json={"folder": "css"})
    assert response.get_json()["error"]["code"] == "catalog_only"
    assert (site / "notas.txt").is_file()
    # Settings can still be saved without touching the folder.
    response = empty_client.put("/settings", json={"research_name": "Web"})
    assert response.status_code == 200
    assert not (site / "Drop Zone").exists()


def test_protected_file_cannot_be_renamed_by_hand(flask_client, app):
    """Rename answers 400 protected_name for index.html."""
    folder = app.config["PROJECT_FOLDER"]
    repo = CatalogRepository(os.path.join(folder, ".cataloga", "catalog.db"))
    doc = add_file_doc(repo, os.path.join(folder, "Documents", "index.html"))
    response = flask_client.post("/documents/{}/rename".format(doc.id),
                                 json={"new_name": "home"})
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "protected_name"
    assert os.path.isfile(os.path.join(folder, "Documents", "index.html"))
