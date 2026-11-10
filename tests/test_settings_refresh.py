"""Folder Names counts the files read after Settings first loaded."""

import os
import re

from backend.config import projects
from backend.db.catalog_repository import CatalogRepository
from backend.models.document import Document
from backend.pipeline import folder_tree

FRONTEND = os.path.join(os.path.dirname(__file__), "..", "frontend")

TREE = [{"name": "Photos", "children": []},
        {"name": "from Mike", "children": []}]


def read(*parts):
    """Return the text of a frontend file."""
    with open(os.path.join(FRONTEND, *parts), encoding="utf-8") as file:
        return file.read()


def function_body(text, name):
    """The source of one JavaScript function, up to its closing brace."""
    start = text.index("function " + name + "(")
    return text[start:text.index("\n}\n", start)]


def test_counts_change_after_a_reading(flask_client, app):
    """The case of the bug: Settings loads with 0, then files are read.

    The second GET /settings, the one refreshFolderCounts() makes, gives
    the folder its files, so removing it asks where they go.
    """
    folder = app.config["PROJECT_FOLDER"]
    repo = CatalogRepository(projects.catalog_path(folder))
    repo.save_config_value("folder_mode", folder_tree.PLACE_MODE)
    repo.save_tree(TREE)
    first = flask_client.get("/settings").get_json()
    assert first["folder_counts"] == {"Photos": 0, "from Mike": 0}
    # The reading catalogs two files in "from Mike".
    for name in ("a.jpg", "b.jpg"):
        path = os.path.join(folder, "from Mike", name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").close()
        repo.add_document(Document(name, name, "Photos", path,
                                   "2026-11-10T10:00:00", summary="x",
                                   folder_path="from Mike"))
    second = flask_client.get("/settings").get_json()
    assert second["folder_counts"]["from Mike"] == 2
    assert second["files_read"] == 2


def test_opening_settings_refreshes_the_counts():
    """showView('settings') asks again for an existing project."""
    body = function_body(read("js", "app.js"), "showView")
    settings = body[body.index('if (name === "settings")'):]
    settings = settings[:settings.index("dropSettingsCards();")]
    assert "refreshFolderCounts();" in settings
    # Only for an existing project: a new one keeps its own form.
    assert settings.index("} else {") < settings.index(
        "refreshFolderCounts();")


def test_the_end_of_a_reading_refreshes_the_counts():
    """renderScan() notices running → done and asks again."""
    body = function_body(read("js", "catalog.js"), "renderScan")
    end = body.index("refreshFolderCounts();")
    assert body.index('["running", "paused"].includes(scanStatus)') < end
    # It compares with the status before this one is saved.
    assert end < body.index("scanStatus = scan.status;")


def test_refresh_keeps_what_the_user_is_editing():
    """Untouched folders reload whole; edited ones only get new counts."""
    body = function_body(read("js", "folders.js"), "refreshFolderCounts")
    assert "await getSettings()" in body
    assert "if (!foldersTouched)" in body
    assert "showFolderSection(settings, false)" in body
    assert re.search(r"if \(row\.saved\) \{\s*row\.count = counts\[pathOf"
                     r"\(row\)\] \|\| 0;", body)
    assert 'projectMode === "new"' in body


def test_a_folder_with_files_asks_where_they_go():
    """The question depends on the count the refresh brings."""
    body = function_body(read("js", "folders.js"), "removeFolder")
    assert 'row.count > 0 && projectFolderMode !== "catalog"' in body
    assert "openFolderRemoveDialog(row)" in body
