"""Folder Names in every project: nothing moves without To Approve."""

import json
import os

import pytest

from backend.config import ai_settings, projects
from backend.db.catalog_repository import CatalogRepository
from backend.models.document import Document
from backend.pipeline import ai_providers, folder_tree, learn_folder, refile
from backend.pipeline.ai_providers.base import AIProviderClient
from backend.pipeline.file_organizer import FileOrganizer
from tests.conftest import make_project

FRONTEND = os.path.join(os.path.dirname(__file__), "..", "frontend")

NEW_TREE = [{"name": "Press", "children": []},
            {"name": "Notes", "children": []},
            {"name": "Photos", "children": []}]


def read(*parts):
    """Return the text of a frontend file."""
    with open(os.path.join(FRONTEND, *parts), encoding="utf-8") as file:
        return file.read()


class RefileAI(AIProviderClient):
    """A fake provider that files every document into one folder."""

    def __init__(self, folder="Notes"):
        super().__init__(provider_name="fake", model="fake-model")
        self.api_key = "fake-provider-key"
        self.retry_delay = 0
        self.folder = folder
        self.sent = []

    def send_prompt(self, system_prompt, text):
        self.sent.append(text)
        ids = [int(n) for n in
               __import__("re").findall(r'"id": (\d+)', text)]
        return json.dumps({"files": [{"id": i, "folder": self.folder}
                                     for i in ids]})


@pytest.fixture
def fake_ai(monkeypatch, projects_path):
    """Every provider the routes build is the fake one."""
    ai = RefileAI()
    monkeypatch.setattr(ai_providers, "create_client",
                        lambda name, model, base_url=None: ai)
    return ai


def repo_of(app):
    """The catalog of the app fixture's project."""
    return CatalogRepository(
        projects.catalog_path(app.config["PROJECT_FOLDER"]))


def add_doc(repo, folder, place, name, summary="About the swim."):
    """A real file in a folder of the project, with its catalog row."""
    path = os.path.join(folder, place, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as handle:
        handle.write("content of " + name)
    return repo.add_document(Document(
        name, name, "Documents", path, "2026-11-10T10:00:00",
        summary=summary, status="Classified", topic="swim"))


def files_of(folder):
    """Every file under a folder, by relative path."""
    found = []
    for current, dirs, names in os.walk(str(folder)):
        dirs[:] = [d for d in dirs if d != ".cataloga"]
        found += [os.path.relpath(os.path.join(current, n), str(folder))
                  for n in names]
    return sorted(found)


def finish_refile(app):
    """Wait for the background proposals."""
    thread = app.config.get("REFILE_THREAD")
    if thread is not None:
        thread.join(5)


# --- The card is there in every case ---

def test_the_card_is_always_wanted_and_comes_after_file_names():
    """settings.js never hides it by mode; the HTML keeps the order."""
    js = read("js", "settings.js")
    wanted = js[js.index("const wanted = {"):]
    wanted = wanted[:wanted.index("};")]
    assert '"folders-section": true' in wanted
    assert "showFolderSection(settings, false)" in js
    html = read("index.html")
    order = [html.index('id="project-section"'),
             html.index('id="sheet-section"'),
             html.index('id="naming-section"'),
             html.index('id="folders-section"'),
             html.index('id="save-button"'),
             html.index('id="remove-project-section"')]
    assert order == sorted(order)
    card = html[html.index('id="folders-section"'):]
    card = card[:card.index("</section>")]
    for button in ("suggest-folders", "file-type-folders", "learn-folders",
                   "add-folder", "turn-off-catalog"):
        assert 'id="{}"'.format(button) in card
    assert 'data-i18n="folders.plan_note"' in card
    assert 'data-i18n="folders.catalog_note"' in card
    assert "folders-new-only" not in card.split('id="folder-buttons"')[1]


def test_settings_give_a_tree_in_every_mode(flask_client, app, tmp_path):
    """Old unread: empty. Old read: its type folders with counts."""
    settings = flask_client.get("/settings").get_json()
    assert settings["folder_mode"] == "media"
    assert settings["folder_tree"] == [] and settings["files_read"] == 0
    repo = repo_of(app)
    folder = app.config["PROJECT_FOLDER"]
    add_doc(repo, folder, "Documents", "a.txt")
    add_doc(repo, folder, "Press", "b.txt")
    settings = flask_client.get("/settings").get_json()
    assert settings["files_read"] == 2
    assert [node["name"] for node in settings["folder_tree"]] == \
        ["Press", "Audio", "Video", "Photos", "Documents"]
    assert settings["folder_counts"] == {"Documents": 1, "Press": 1}


def test_settings_give_the_kept_tree_of_a_catalog_only_project(
        empty_client, tmp_path):
    """Catalog only keeps the folders it was given, with nothing on disk."""
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text("<html></html>")
    answer = empty_client.post("/projects", json={
        "name": "Site", "folder": str(site), "catalog_only": True,
        "folders": NEW_TREE})
    assert answer.status_code == 201
    settings = empty_client.get("/settings").get_json()
    assert settings["folder_mode"] == "catalog"
    assert [n["name"] for n in settings["folder_tree"]] == \
        ["Press", "Notes", "Photos"]
    assert sorted(os.listdir(str(site))) == [".cataloga", "index.html"]


# --- Old project, unread: becomes a project with its own folders ---

def test_an_unread_old_project_switches_mode_and_moves_nothing(
        flask_client, app, fake_ai):
    """Saving a tree makes it read in place; no proposal, no batch row."""
    folder = app.config["PROJECT_FOLDER"]
    before = files_of(folder)
    answer = flask_client.put("/settings", json={
        "research_name": "Research", "folder_tree": NEW_TREE})
    assert answer.status_code == 200
    assert answer.get_json()["folder_mode"] == "place"
    assert answer.get_json()["refile_started"] is False
    repo = repo_of(app)
    assert repo.folder_mode() == "place"
    assert folder_tree.all_paths(repo.get_folder_tree()) == \
        ["Press", "Notes", "Photos"]
    assert files_of(folder) == before
    assert not os.path.isdir(os.path.join(folder, "Notes"))
    plan = flask_client.get("/plan").get_json()
    assert plan["rows"] == [] and fake_ai.sent == []


def test_saving_without_touching_the_folders_keeps_the_old_mode(
        flask_client, app):
    """No folder_tree in the body: a type project stays as it was."""
    flask_client.put("/settings", json={"research_name": "Research",
                                        "categories": []})
    assert repo_of(app).folder_mode() == "media"


# --- Old project, already read: the moves wait in To Approve ---

def test_a_read_old_project_gets_its_moves_in_to_approve(
        flask_client, app, fake_ai):
    """Changing the folders proposes a move per file and moves nothing."""
    repo = repo_of(app)
    folder = app.config["PROJECT_FOLDER"]
    first = add_doc(repo, folder, "Documents", "a.txt")
    second = add_doc(repo, folder, "Press", "b.txt")
    before = files_of(folder)
    tree = NEW_TREE + [{"name": "Documents", "children": []}]
    answer = flask_client.put("/settings", json={
        "research_name": "Research", "folder_tree": tree})
    assert answer.status_code == 200
    assert answer.get_json()["refile_started"] is True
    finish_refile(app)
    assert repo.get_document(first.id).proposed_folder == "Notes"
    assert repo.get_document(second.id).proposed_folder == "Notes"
    # The AI got the cards, never the files, and the folders as data.
    assert "Folders:\nPress\nNotes\nPhotos\nDocuments" in fake_ai.sent[0]
    assert "<<FILE_DATA" in fake_ai.sent[0]
    plan = flask_client.get("/plan").get_json()
    moves = [row for row in plan["rows"] if row["action"] == "move"]
    assert sorted(row["old_name"] for row in moves) == ["a.txt", "b.txt"]
    assert all(row["new_folder"] == "Notes" for row in moves)
    assert all(row["status"] == "proposed" for row in moves)
    # Nothing moved: the files and the folders are as they were.
    assert files_of(folder) == before
    assert not os.path.isdir(os.path.join(folder, "Notes"))
    assert flask_client.get("/plan/count").get_json() == {"waiting": 2}


def test_a_file_whose_folder_is_still_right_gets_no_proposal(
        flask_client, app, fake_ai):
    """The AI says "" or the same folder: the row stays unchanged."""
    repo = repo_of(app)
    folder = app.config["PROJECT_FOLDER"]
    doc = add_doc(repo, folder, "Documents", "a.txt")
    fake_ai.folder = "Documents"
    flask_client.put("/settings", json={
        "research_name": "Research",
        "folder_tree": NEW_TREE + [{"name": "Documents", "children": []}]})
    finish_refile(app)
    assert repo.get_document(doc.id).proposed_folder is None
    plan = flask_client.get("/plan").get_json()
    assert plan["rows"] == []
    assert [row["filename"] for row in plan["unchanged"]] == ["a.txt"]


def test_without_a_provider_the_tree_is_saved_and_nothing_is_proposed(
        flask_client, app):
    """No key: the folders change, the files keep their rows as they are."""
    repo = repo_of(app)
    doc = add_doc(repo, app.config["PROJECT_FOLDER"], "Documents", "a.txt")
    answer = flask_client.put("/settings", json={
        "research_name": "Research", "folder_tree": NEW_TREE})
    assert answer.get_json()["refile_started"] is False
    assert repo.folder_mode() == "place"
    assert repo.get_document(doc.id).proposed_folder is None


# --- Catalog only: the folders are kept, nothing moves ---

@pytest.fixture
def catalog_project(flask_client, app):
    """The app fixture's project as Catalog only, with two files read."""
    repo = repo_of(app)
    folder = app.config["PROJECT_FOLDER"]
    repo.save_config_value("folder_mode", folder_tree.CATALOG_MODE)
    repo.save_naming_template("keep")
    docs = [add_doc(repo, folder, "Documents", "a.txt"),
            add_doc(repo, folder, "Press", "b.txt")]
    return {"repo": repo, "folder": folder, "docs": docs,
            "before": files_of(folder)}


def test_catalog_only_keeps_the_folders_and_moves_nothing(
        flask_client, app, catalog_project, fake_ai):
    """The tree is saved for later; no proposal, no folder on disk."""
    answer = flask_client.put("/settings", json={
        "research_name": "Research", "folder_tree": NEW_TREE})
    assert answer.status_code == 200
    assert answer.get_json()["folder_mode"] == "catalog"
    assert answer.get_json()["refile_started"] is False
    repo = catalog_project["repo"]
    assert repo.is_catalog_project()
    assert folder_tree.all_paths(repo.saved_tree()) == \
        ["Press", "Notes", "Photos"]
    assert repo.get_folder_tree() is None
    assert files_of(catalog_project["folder"]) == catalog_project["before"]
    assert all(repo.get_document(d.id).proposed_folder is None
               for d in catalog_project["docs"])
    assert fake_ai.sent == []
    assert flask_client.get("/plan").get_json()["mode"] == "catalog"


def test_turning_off_catalog_only_sends_the_moves_to_to_approve(
        flask_client, app, catalog_project, fake_ai):
    """The project is then read in place; the saved tree gets its moves."""
    flask_client.put("/settings", json={"research_name": "Research",
                                        "folder_tree": NEW_TREE})
    answer = flask_client.put("/settings", json={
        "research_name": "Research", "catalog_only": False})
    assert answer.status_code == 200
    assert answer.get_json()["folder_mode"] == "place"
    assert answer.get_json()["refile_started"] is True
    finish_refile(app)
    repo = catalog_project["repo"]
    assert repo.folder_mode() == "place"
    assert folder_tree.all_paths(repo.get_folder_tree()) == \
        ["Press", "Notes", "Photos"]
    plan = flask_client.get("/plan").get_json()
    assert sorted(row["old_name"] for row in plan["rows"]
                  if row["action"] == "move") == ["a.txt", "b.txt"]
    assert files_of(catalog_project["folder"]) == catalog_project["before"]
    # Names are kept: Catalog only left "keep" as the method.
    assert repo.get_naming_template() == "keep"


def test_catalog_only_cannot_be_turned_on_from_settings(flask_client,
                                                        app):
    """Only off: on is a choice of a new project."""
    answer = flask_client.put("/settings", json={
        "research_name": "Research", "catalog_only": True})
    assert answer.status_code == 400
    assert answer.get_json()["error"]["code"] == "invalid_field"


# --- Every proposed folder passes the path checks ---

@pytest.mark.parametrize("text, place", [
    ("Notes", "Notes"),
    ("notes", "Notes"),
    ("/Notes", None),
    ("", None),
    (None, None),
    ("../Notes", None),
    ("/etc/Notes", None),
    ("Elsewhere", None),
    ("Notes/../Press", None),
])
def test_chosen_place_keeps_only_safe_folders_of_the_tree(text, place):
    """Outside the tree, absolute or with '..': no proposal."""
    tree = folder_tree.check_tree(NEW_TREE)
    assert refile.chosen_place(tree, text) == place


def test_refile_ignores_bad_answers_and_drops_stale_proposals(tmp_path):
    """Unknown ids and folders do nothing; a stale proposal is dropped."""
    folder = tmp_path / "p"
    repo = make_project(str(tmp_path / "list.json"), folder)
    first = add_doc(repo, str(folder), "Documents", "a.txt")
    second = add_doc(repo, str(folder), "Documents", "b.txt")
    repo.set_proposal(second.id, "Gone", None)
    tree = folder_tree.check_tree(NEW_TREE)

    class OddAI:
        """Answers with an unknown id and a folder outside the tree."""

        def ask(self, system_prompt, text):
            return json.dumps({"files": [{"id": 999, "folder": "Notes"},
                                         {"id": first.id,
                                          "folder": "../Notes"},
                                         {"id": second.id, "folder": ""}]})
    assert refile.refile(repo, FileOrganizer(str(folder)), OddAI(),
                         tree) == 0
    assert repo.get_document(first.id).proposed_folder is None
    assert repo.get_document(second.id).proposed_folder is None


def test_settings_refuse_a_tree_with_a_bad_path(flask_client, app):
    """The same checks as the plan, before anything is saved."""
    answer = flask_client.put("/settings", json={
        "research_name": "Research",
        "folder_tree": [{"name": "con", "children": []}]})
    assert answer.status_code == 400
    assert answer.get_json()["error"]["code"] == "invalid_folders"
    assert repo_of(app).folder_mode() == "media"


def test_learn_from_my_folder_skips_the_drop_zone(tmp_path):
    """Cataloga's own folder is never learned as one of the archive's."""
    root = tmp_path / "r"
    (root / "Drop Zone").mkdir(parents=True)
    (root / "Press").mkdir()
    (root / "Press" / "a.txt").write_text("x")
    assert [n["name"] for n in learn_folder.read_structure(str(root))[0]] \
        == ["Press"]
