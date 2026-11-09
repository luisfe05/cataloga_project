"""Tests for the Archive Now / Archive Later switch of a new project."""

import os
import re

import pytest

from backend import scanner
from backend.config import projects
from backend.db.catalog_repository import CatalogRepository

FRONTEND = os.path.join(os.path.dirname(__file__), "..", "frontend")


def read_frontend(*parts):
    """Return the text of a frontend file."""
    with open(os.path.join(FRONTEND, *parts), encoding="utf-8") as file:
        return file.read()


@pytest.fixture
def scans(monkeypatch):
    """Record the scans a request starts, without reading anything."""
    started = []
    monkeypatch.setattr(scanner, "start_scan",
                        lambda app, path, owner=None: started.append(path))
    return started


@pytest.fixture
def folder(tmp_path):
    """A folder with two files, as the user has it."""
    folder = tmp_path / "Harbor Swimmers"
    folder.mkdir()
    (folder / "notes.txt").write_text("Dawn swim, 1997.")
    (folder / "IMG_0001.jpg").write_bytes(b"jpg")
    return folder


def create(client, folder, **extra):
    """POST /projects for a folder read in place."""
    body = {"name": "Harbor Swimmers", "folder": str(folder),
            "folder_mode": "place",
            "project_sheet": "Work: a documentary about a swim club.",
            "server_url": "https://relay.example.org"}
    body.update(extra)
    return client.post("/projects", json=body)


def test_archive_later_reads_nothing_and_saves_nothing_it_turned_off(
        empty_client, folder, scans):
    """Later: no scan, no sheet, no server URL, no folders made."""
    response = create(empty_client, folder, defer_scan=True)
    assert response.status_code == 201
    assert scans == []
    config = CatalogRepository(projects.catalog_path(str(folder))) \
        .get_app_config()
    assert not config.get("project_sheet")
    assert not config.get("server_url")
    assert sorted(os.listdir(folder)) == [".cataloga", "IMG_0001.jpg",
                                          "notes.txt"]


def test_archive_now_starts_reading_with_no_folders_yet(empty_client, folder,
                                                        scans):
    """Now: the reading starts at once; the tree comes from the reading."""
    response = create(empty_client, folder)
    assert response.status_code == 201
    assert len(scans) == 1
    repo = CatalogRepository(projects.catalog_path(str(folder)))
    config = repo.get_app_config()
    assert config["project_sheet"].startswith("Work:")
    assert config["server_url"] == "https://relay.example.org"
    assert repo.get_folder_tree() == []


def test_a_drop_zone_project_still_needs_its_folders(empty_client, folder,
                                                     scans):
    """The Drop Zone mode is not read in place, so it keeps the old rule."""
    response = create(empty_client, folder, folder_mode="tree")
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_folders"


def test_the_switch_sits_right_above_catalog_only():
    """The switch comes after the folder and just before Catalog only."""
    html = read_frontend("index.html")
    switch = html.index('id="archive-switch"')
    assert html.index('id="target-directory"') < switch
    assert switch < html.index('id="catalog-only-row"')
    between = html[switch:html.index('id="catalog-only-row"')]
    assert "<section" not in between
    assert 'value="later" checked' in between


def test_the_old_now_or_later_dialog_is_gone():
    """The switch replaces the Catalog this folder now? dialog."""
    assert "ask-overlay" not in read_frontend("index.html")
    assert "ask-overlay" not in read_frontend("js", "settings.js")
    assert ".ask-" not in read_frontend("css", "home.css")


def test_later_turns_off_the_four_sections():
    """About this project, File names, Folders and AI provider."""
    settings = read_frontend("js", "settings.js")
    listed = re.search(r"ARCHIVE_SECTIONS = \[(.*?)\];", settings, re.S)
    ids = re.findall(r'"([a-z-]+)"', listed.group(1))
    assert ids == ["sheet-section", "naming-section", "folders-section",
                   "ai-section"]
    html = read_frontend("index.html")
    for section_id in ids:
        assert 'id="{}"'.format(section_id) in html


def test_archive_is_the_one_word_on_buttons():
    """No button or text still says Catalog now."""
    for name in ("en.js", "es.js"):
        text = read_frontend("js", "lang", name)
        assert "Catalog now" not in text
        assert "Catalogar ahora" not in text


def test_drop_zone_is_a_box_and_read_in_place_is_the_default():
    """No mode choice left: one Use a Drop Zone box, unticked by default."""
    html = read_frontend("index.html")
    assert 'name="folder-mode"' not in html
    box = html.index('id="use-drop-zone"')
    assert html.index('id="target-directory"') < box
    assert box < html.index('id="archive-switch"')
    assert 'data-help="help.drop_zone"' in html[box:html.index(
        'id="archive-switch"')]
    settings = read_frontend("js", "settings.js")
    assert 'checked ? "tree" : "place"' in settings
    assert 'getElementById("use-drop-zone").checked = false' in settings


def test_drop_zone_and_catalog_only_exclude_each_other():
    """Ticking one unticks the other, in both directions."""
    settings = read_frontend("js", "settings.js")
    drop_zone = settings.index('getElementById("use-drop-zone")\n'
                               '    .addEventListener')
    catalog = settings.index('getElementById("catalog-only")\n'
                             '    .addEventListener')
    assert 'getElementById("catalog-only").checked = false' in \
        settings[drop_zone:drop_zone + 400]
    assert 'getElementById("use-drop-zone").checked = false' in \
        settings[catalog:catalog + 400]
