"""Removing a folder never deletes a file; the moves wait in To Approve."""

import json
import os
import re

import pytest

from backend.config import projects
from backend.db.catalog_repository import CatalogRepository
from backend.models.document import Document
from backend.pipeline import ai_providers, folder_tree
from backend.pipeline.ai_providers.base import AIProviderClient

FRONTEND = os.path.join(os.path.dirname(__file__), "..", "frontend")

TREE = [{"name": "Press", "children": []},
        {"name": "Notes", "children": []},
        {"name": "Old", "children": [{"name": "Letters", "children": []}]}]


def read(*parts):
    """Return the text of a frontend file."""
    with open(os.path.join(FRONTEND, *parts), encoding="utf-8") as file:
        return file.read()


def files_of(folder):
    """Every file and folder under a project, without its catalog."""
    found = []
    for current, dirs, names in os.walk(str(folder)):
        dirs[:] = [d for d in dirs if d != ".cataloga"]
        relative = os.path.relpath(current, str(folder))
        found += [os.path.join(relative, d) + "/" for d in dirs]
        found += [os.path.join(relative, n) for n in names]
    return sorted(found)


def add_doc(repo, folder, place, name):
    """A real file in a folder of the project, with its catalog row."""
    path = os.path.join(folder, place, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as handle:
        handle.write("content of " + name)
    return repo.add_document(Document(
        name, name, "Documents", path, "2026-11-10T10:00:00",
        summary="About the swim.", status="Classified", topic="swim",
        folder_path=place))


@pytest.fixture
def place(flask_client, app):
    """A project read in place with a tree, two files in Old/Letters."""
    folder = app.config["PROJECT_FOLDER"]
    repo = CatalogRepository(projects.catalog_path(folder))
    repo.save_config_value("folder_mode", folder_tree.PLACE_MODE)
    repo.save_tree(TREE)
    docs = [add_doc(repo, folder, "Old/Letters", "a.txt"),
            add_doc(repo, folder, "Old/Letters", "b.txt"),
            add_doc(repo, folder, "Press", "c.txt")]
    return {"client": flask_client, "app": app, "repo": repo,
            "folder": folder, "docs": docs, "before": files_of(folder)}


def without_old():
    """The tree with Old (and Letters) taken out."""
    return TREE[:2]


def save(place, moves, tree=None):
    """Save Folder Names with the removed folders and where their files go."""
    return place["client"].put("/settings", json={
        "research_name": "Research", "folder_tree": tree or without_old(),
        "folder_moves": moves})


def plan(place):
    """The draft plan."""
    return place["client"].get("/plan").get_json()


def apply_and_wait(place):
    """Approve every row, apply, and wait for the batch thread."""
    client = place["client"]
    client.put("/plan/items", json={"status": "approved", "all": True})
    assert client.post("/plan/apply").status_code == 202
    place["app"].config["PLAN_THREAD"].join(10)


def undo_and_wait(place):
    """Undo the newest batch and wait."""
    assert place["client"].post("/plan/undo").status_code == 202
    place["app"].config["PLAN_THREAD"].join(10)


# --- Saving never touches the disk ---

def test_removing_a_folder_with_files_deletes_nothing(place):
    """The tree changes; every file and folder on the disk stays."""
    answer = save(place, {"Old": "Notes"})
    assert answer.status_code == 200
    assert answer.get_json()["folder_moves"] == 2
    assert files_of(place["folder"]) == place["before"]
    assert folder_tree.all_paths(place["repo"].get_folder_tree()) == \
        ["Press", "Notes"]


def test_the_moves_appear_in_to_approve(place):
    """Both files get the chosen folder; the old one waits to be removed."""
    save(place, {"Old": "Notes"})
    view = plan(place)
    moves = [row for row in view["rows"] if row["action"] == "move"]
    assert sorted(row["old_name"] for row in moves) == ["a.txt", "b.txt"]
    assert all(row["new_folder"] == "Notes" for row in moves)
    assert all(row["status"] == "proposed" for row in moves)
    removals = [row["old_folder"] for row in view["rows"]
                if row["action"] == "remove_folder"]
    # Deepest first: Letters empties before Old.
    assert removals == ["Old/Letters", "Old"]
    assert files_of(place["folder"]) == place["before"]


def test_leave_them_where_they_are_moves_nothing(place):
    """No proposal, no removal row; applying the plan changes nothing."""
    save(place, {"Old": ""})
    view = plan(place)
    assert view["rows"] == []
    names = sorted(row["filename"] for row in view["unchanged"])
    assert names == ["a.txt", "b.txt", "c.txt"]
    assert place["repo"].removed_folders() == []
    assert files_of(place["folder"]) == place["before"]


def test_a_removed_folder_leaves_the_disk_only_after_apply_and_undo_restores(
        place):
    """Apply moves the files, then removes the empty folders; Undo all back."""
    save(place, {"Old": "Notes"})
    apply_and_wait(place)
    folder = place["folder"]
    assert os.path.isfile(os.path.join(folder, "Notes", "a.txt"))
    assert os.path.isfile(os.path.join(folder, "Notes", "b.txt"))
    assert not os.path.exists(os.path.join(folder, "Old"))
    assert place["repo"].removed_folders() == []
    undo_and_wait(place)
    assert files_of(folder) == place["before"]
    for doc in place["docs"]:
        again = place["repo"].get_document(doc.id)
        assert os.path.isfile(again.file_path)
        assert again.file_path == doc.file_path
    # Undone, the removal is waiting again for the next plan.
    assert place["repo"].removed_folders() == ["Old/Letters", "Old"]


def test_a_folder_that_still_holds_files_is_never_removed(place):
    """A skipped file keeps its folder on the disk; the row says why."""
    save(place, {"Old": "Notes"})
    client = place["client"]
    view = plan(place)
    first = [row for row in view["rows"] if row["old_name"] == "a.txt"][0]
    client.put("/plan/items", json={"status": "approved",
                                    "ids": [first["id"]]})
    assert client.post("/plan/apply").status_code == 202
    place["app"].config["PLAN_THREAD"].join(10)
    folder = place["folder"]
    assert os.path.isfile(os.path.join(folder, "Old", "Letters", "b.txt"))
    assert os.path.isdir(os.path.join(folder, "Old", "Letters"))
    batch = place["repo"].list_batches(["applied"])[0]
    reasons = [item["reason"] for item in place["repo"].get_items(
        batch["id"]) if item["action"] == "remove_folder"]
    assert reasons == ["Folder is not empty", "Folder is not empty"]


def test_a_folder_put_back_in_the_tree_is_not_removed(place):
    """Taken out, then back: the plan offers no removal."""
    save(place, {"Old": "Notes"})
    place["client"].put("/settings", json={
        "research_name": "Research", "folder_tree": TREE})
    removals = [row for row in plan(place)["rows"]
                if row["action"] == "remove_folder"]
    assert removals == []


@pytest.mark.parametrize("moves", [
    {"Press": "Notes"},          # Press is still in the tree.
    {"Nowhere": "Notes"},        # Never a folder of this project.
    {"Old": "Elsewhere"},        # The target is not in the tree.
    {"Old": "../Notes"},         # Outside the project.
    {"Old": 3},
    ["Old"],
])
def test_bad_folder_moves_are_refused_before_anything_is_saved(place,
                                                               moves):
    """400 invalid_folder_moves; the tree and the plan stay as they were."""
    answer = save(place, moves)
    assert answer.status_code == 400
    assert answer.get_json()["error"]["code"] == "invalid_folder_moves"
    assert folder_tree.all_paths(place["repo"].get_folder_tree()) == \
        folder_tree.all_paths(folder_tree.check_tree(TREE))
    assert plan(place)["rows"] == []


def test_the_chosen_folders_are_not_asked_to_the_ai(place, monkeypatch,
                                                    projects_path):
    """With a provider, the AI gets only the files nobody chose for."""
    from backend.config import ai_settings

    class SpyAI(AIProviderClient):
        """Records the ids it is asked about."""

        def __init__(self):
            super().__init__(provider_name="fake", model="fake-model")
            self.api_key = "fake-provider-key"
            self.retry_delay = 0
            self.ids = []

        def send_prompt(self, system_prompt, text):
            found = [int(n) for n in re.findall(r'"id": (\d+)', text)]
            self.ids += found
            return json.dumps({"files": [{"id": i, "folder": "Press"}
                                         for i in found]})
    spy = SpyAI()
    ai_settings.set_role(projects_path, "text", "gemini", "gemini-2.5-flash")
    monkeypatch.setattr(ai_providers, "create_client",
                        lambda name, model, base_url=None: spy)
    answer = save(place, {"Old": "Notes"})
    assert answer.get_json()["refile_started"] is True
    place["app"].config["REFILE_THREAD"].join(5)
    assert place["docs"][0].id not in spy.ids
    assert place["docs"][1].id not in spy.ids
    assert place["repo"].get_document(place["docs"][0].id) \
        .proposed_folder == "Notes"


# --- B2: no provider ---

def test_without_a_provider_the_answer_says_so(place):
    """The tree is saved, nothing is proposed, needs_provider is true."""
    answer = place["client"].put("/settings", json={
        "research_name": "Research", "folder_tree": TREE[:2] +
        [{"name": "Old", "children": [{"name": "Letters", "children": []},
                                      {"name": "Cards", "children": []}]}]})
    data = answer.get_json()
    assert answer.status_code == 200
    assert data["refile_started"] is False
    assert data["needs_provider"] is True
    assert all(place["repo"].get_document(d.id).proposed_folder is None
               for d in place["docs"])


def test_an_unchanged_tree_needs_no_provider(place):
    """Saving the same tree is not a change: no note."""
    answer = place["client"].put("/settings", json={
        "research_name": "Research", "folder_tree": TREE})
    assert answer.get_json()["needs_provider"] is False


def test_the_card_has_the_provider_note_and_its_link():
    """The note, its two languages and the link to AI Provider."""
    html = read("index.html")
    card = html[html.index('id="folders-section"'):]
    card = card[:card.index("</section>")]
    assert 'id="folders-provider-note"' in card
    assert 'data-i18n="folders.no_provider"' in card
    assert 'id="open-ai-provider"' in card
    assert "Connect an AI provider to get move proposals, or move files " \
        "yourself with Move to…" in read("js", "lang", "en.js").replace(
            '"\n        + "', "")
    assert "Conecta un proveedor de AI para recibir propuestas de " \
        "movimiento, o mueve los archivos tú con Mover a…" in read(
            "js", "lang", "es.js").replace('"\n        + "', "")
    settings = read("js", "settings.js")
    assert "saved.needs_provider" in settings
    assert "showProviderNote(true)" in settings
    assert 'showSettingsTab("general")' in read("js", "folders.js")


# --- B3 screen and B1 ---

def test_the_remove_dialog_asks_where_the_files_go():
    """A folder with files opens the dialog; Leave them is the last choice."""
    html = read("index.html")
    dialog = html[html.index('id="folder-remove-dialog"'):]
    dialog = dialog[:dialog.index("</dialog>")]
    assert 'id="folder-remove-target"' in dialog
    assert 'data-i18n="folders.remove_note"' in dialog
    js = read("js", "folders.js")
    assert "openFolderRemoveDialog(row)" in js
    assert 't("folders.remove_leave")' in js
    assert "folder_moves: readFolderMoves()" in read("js", "settings.js")


def test_the_folder_marks_are_not_in_spaced_capitals():
    """The four marks use the card's normal text, not the field label."""
    css = read("css", "main.css")
    rule = re.search(r"\.settings-form \.folder-flags label,[^{]*\{([^}]*)\}",
                     css).group(1)
    assert "text-transform: none" in rule
    assert "letter-spacing: 0" in rule
    assert "font-size: 15px" in rule
    assert "font-family: var(--font-body)" in rule
    en = read("js", "lang", "en.js")
    for text in ('"folders.flag_events": "Events"',
                 '"folders.flag_fallback": "Catch-all"',
                 '"folders.flag_auto": "No asking"',
                 '"folders.flag_leave": "Leave as is"'):
        assert text in en


# --- An empty folder leaves the disk through To Approve too ---

def test_an_empty_folder_is_removed_only_at_apply_and_undo_restores(place):
    """Saving keeps it on the disk; Apply removes it; Undo makes it again."""
    empty = os.path.join(place["folder"], "Empty")
    os.makedirs(empty)
    place["repo"].save_tree(TREE + [{"name": "Empty", "children": []}])
    answer = place["client"].put("/settings", json={
        "research_name": "Research", "folder_tree": TREE,
        "folder_moves": {"Empty": ""}})
    assert answer.status_code == 200
    assert os.path.isdir(empty)
    rows = plan(place)["rows"]
    assert [row["old_folder"] for row in rows
            if row["action"] == "remove_folder"] == ["Empty"]
    # Only a removal waits: it can be applied on its own.
    assert place["client"].post("/plan/apply").status_code == 202
    place["app"].config["PLAN_THREAD"].join(10)
    assert not os.path.exists(empty)
    undo_and_wait(place)
    assert os.path.isdir(empty)
    assert files_of(place["folder"]) == sorted(place["before"] + ["./Empty/"])


def test_an_empty_folder_with_a_drop_zone_goes_through_to_approve(
        flask_client, app):
    """With a Drop Zone the removal waits in To Approve as well."""
    folder = app.config["PROJECT_FOLDER"]
    repo = CatalogRepository(projects.catalog_path(folder))
    repo.save_folder_tree("Research", TREE)
    os.makedirs(os.path.join(folder, "Notes"), exist_ok=True)
    answer = flask_client.put("/settings", json={
        "research_name": "Research",
        "folder_tree": [TREE[0], TREE[2]], "folder_moves": {"Notes": ""}})
    assert answer.status_code == 200
    assert os.path.isdir(os.path.join(folder, "Notes"))
    rows = flask_client.get("/plan").get_json()["rows"]
    assert [row["old_folder"] for row in rows
            if row["action"] == "remove_folder"] == ["Notes"]


def test_a_folder_with_files_left_in_place_is_not_removed(place):
    """Leave them where they are: the folder keeps its files and stays."""
    save(place, {"Old": ""})
    assert [row for row in plan(place)["rows"]
            if row["action"] == "remove_folder"] == []
    assert os.path.isdir(os.path.join(place["folder"], "Old", "Letters"))


def test_an_empty_saved_folder_is_sent_for_removal():
    """removeFolder records an empty folder on the disk, not a new one."""
    js = read("js", "folders.js")
    body = js[js.index("function removeFolder(row)"):]
    body = body[:body.index("\n}\n")]
    assert 'row.saved && projectFolderMode !== "catalog"' in body
    assert 'folderMoves[pathOf(row)] = "";' in body
    plan_js = read("js", "plan.js")
    assert "removalRows().length" in plan_js


def test_the_name_style_and_photo_date_radios_use_normal_text():
    """Same 15 px as the folder marks, not the 12 px field label."""
    css = read("css", "main.css")
    rule = re.search(r"\.settings-form \.folder-flags label,\s*"
                     r"\.settings-form \.naming-style label,\s*"
                     r"\.settings-form \.stamp-order label \{([^}]*)\}",
                     css).group(1)
    assert "font-size: 15px" in rule
    assert "text-transform: none" in rule
