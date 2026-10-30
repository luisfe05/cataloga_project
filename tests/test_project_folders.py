"""Tests for the per-project folder tree."""

import json
import os
import sqlite3

import pytest

from backend.config import projects
from backend.db.catalog_repository import CatalogRepository
from backend.db.schema import init_db
from backend.models.document import Document
from backend.pipeline import archive_rules, chat_assistant, folder_tree, naming
from backend.pipeline.ai_providers import base
from backend.pipeline.ai_providers.base import AIProviderClient
from backend.pipeline.classification_pipeline import ClassificationPipeline
from backend.pipeline.file_organizer import MEDIA_TYPES, FileOrganizer
from backend.routes import projects as project_routes
from tests.conftest import make_project

METADATA = {"source": "El Nuevo Día", "document_date": "2026-07-15",
            "topic": "Oceanman Malta", "keywords": ["swimming"]}


class FolderAI(AIProviderClient):
    """Fake AI that answers each kind of request and keeps the prompts."""

    def __init__(self, metadata):
        super().__init__(provider_name="fake", model="fake-model")
        self.retry_delay = 0
        self.metadata = metadata
        self.prompts = []

    def send_prompt(self, system_prompt, text):
        self.prompts.append(system_prompt)
        if system_prompt == base.CLASSIFICATION_PROMPT:
            return "Press"
        if system_prompt == base.SUMMARY_PROMPT:
            return "A news story."
        return json.dumps(self.metadata)


@pytest.fixture
def old_project(tmp_path, monkeypatch):
    """A project made before folder trees: no folder_mode saved."""
    monkeypatch.setattr(base.keyring, "get_password",
                        lambda service, name: "test-key")
    folder = tmp_path / "archive"
    db_path = str(tmp_path / "catalog.db")
    init_db(db_path)
    repo = CatalogRepository(db_path)
    repo.save_app_config("Old", str(folder))
    repo.save_naming_template(naming.NEW_PROJECT_TEMPLATE)
    organizer = FileOrganizer(str(folder))
    organizer.ensure_archive_structure()
    ai = FolderAI(dict(METADATA))
    pipeline = ClassificationPipeline(ai, repo, organizer)
    return {"repo": repo, "ai": ai, "pipeline": pipeline,
            "folder": folder, "drop_zone": folder / "Drop Zone"}


def drop(project, name, text):
    """Put a text file in the Drop Zone and return its path."""
    path = project["drop_zone"] / name
    path.write_text(text)
    return str(path)


# --- Old projects do not change ---

def test_old_project_keeps_the_five_media_folders(old_project):
    """An old project still gets Drop Zone and the five media folders."""
    names = sorted(os.listdir(str(old_project["folder"])))
    assert names == sorted(list(MEDIA_TYPES) + ["Drop Zone"])


def test_old_project_files_go_to_their_media_folder(old_project):
    """In an old project the media type still picks the folder."""
    doc = old_project["pipeline"].classify_document(
        drop(old_project, "a.txt", "Article"))
    assert doc.media_type == "Press"
    assert doc.file_path == os.path.join(
        str(old_project["folder"]), "Press",
        "oceanman-malta_el-nuevo-dia_2026-07-15_001.txt")
    assert doc.status == "Classified"


def test_old_project_categories_never_pick_a_folder(old_project):
    """Categories stay data in an old project; the folder is the type."""
    old_project["repo"].save_categories(
        [{"name": "Contracts", "subcategories": []}])
    old_project["ai"].metadata["category"] = "Contracts"
    doc = old_project["pipeline"].classify_document(
        drop(old_project, "a.txt", "Contract"))
    assert doc.category == "Contracts"
    assert os.path.dirname(doc.file_path) == os.path.join(
        str(old_project["folder"]), "Press")
    assert not os.path.exists(str(old_project["folder"] / "Contracts"))


def test_old_project_no_category_fit_still_moves_by_type(old_project):
    """No category fit is Manual Review, but the file still moves."""
    old_project["repo"].save_categories(
        [{"name": "Contracts", "subcategories": []}])
    old_project["ai"].metadata["category"] = "Recipes"
    doc = old_project["pipeline"].classify_document(
        drop(old_project, "a.txt", "Recipe"))
    assert doc.status == "Manual Review"
    assert doc.review_note == archive_rules.NO_CATEGORY_NOTE
    assert os.path.dirname(doc.file_path) == os.path.join(
        str(old_project["folder"]), "Press")


def test_old_project_unreadable_file_goes_to_documents(old_project):
    """A file without text still lands in Documents, as before."""
    path = old_project["drop_zone"] / "notes.xyz"
    path.write_bytes(b"\x00\x01")
    doc = old_project["pipeline"].classify_document(str(path))
    assert doc.status == "Manual Review"
    assert os.path.dirname(doc.file_path) == os.path.join(
        str(old_project["folder"]), "Documents")


# --- Folder names ---

@pytest.mark.parametrize("text, expected", [
    ("Fotos del evento", "Fotos del evento"),
    ("  Caso   1142 ", "Caso 1142"),
    ("Notas: ¿qué? <final>", "Notas ¿qué final"),
    ("a/b\\c|d*e", "abcde"),
    ("Planos.", "Planos"),
    (".hidden", "hidden"),
    ("CON", ""),
    ("aux.txt", ""),
    ("com1", ""),
    ("Drop Zone", ""),
    (".cataloga", "cataloga"),
    ("x" * 80, "x" * folder_tree.MAX_FOLDER_NAME_LENGTH),
    (None, ""),
])
def test_safe_folder_name(text, expected):
    """Names keep spaces and capitals but never break Mac or Windows."""
    assert folder_tree.safe_folder_name(text) == expected


def test_safe_folder_name_uses_one_form_for_accents():
    """'í' typed as i + accent and as one character is the same name."""
    assert folder_tree.safe_folder_name("María") == "María"


@pytest.mark.parametrize("name, problem", [
    ("", "empty"),
    ("Notas: final", "chars"),
    ("CON", "reserved"),
    ("Planos.", "reserved"),
    ("x" * 61, "long"),
    ("Entrevistas", None),
])
def test_name_problem(name, problem):
    """A typed name is refused with the reason the screen shows."""
    assert folder_tree.name_problem(name) == problem


def test_check_tree_refuses_twins_and_bad_names():
    """Siblings that differ only in case or accents are one folder."""
    with pytest.raises(ValueError):
        folder_tree.check_tree([{"name": "Prensa"}, {"name": "prensa"}])
    with pytest.raises(ValueError):
        folder_tree.check_tree([{"name": "A", "subcategories": ["Fotos",
                                                                "FOTOS"]}])
    with pytest.raises(ValueError):
        folder_tree.check_tree([{"name": "Notas?"}])
    with pytest.raises(ValueError):
        folder_tree.check_tree([])


def test_check_tree_limits():
    """20 top folders and 10 subfolders at most."""
    folder_tree.check_tree([{"name": str(n)} for n in range(20)])
    with pytest.raises(ValueError):
        folder_tree.check_tree([{"name": str(n)} for n in range(21)])
    with pytest.raises(ValueError):
        folder_tree.check_tree([{"name": "A", "subcategories": [
            str(n) for n in range(11)]}])


def test_parse_tree_answer_cleans_the_ai_tree():
    """Bad names and twins from the AI are dropped; nesting is kept."""
    answer = "```json\n" + json.dumps([
        {"name": "Oceanman Malta", "subfolders": [
            "Prensa", {"name": "Deep", "subfolders": ["Deeper"]}, "prensa",
            "CON"]},
        {"name": "aux"}, {"name": "Oceanman malta"}, "text"]) + "\n```"
    tree = folder_tree.parse_tree_answer(answer)
    assert folder_tree.to_categories(tree) == [
        {"name": "Oceanman Malta", "subcategories": ["Prensa", "Deep"]}]
    assert folder_tree.all_places(tree) == ["Oceanman Malta/Prensa",
                                            "Oceanman Malta/Deep/Deeper"]
    assert folder_tree.parse_tree_answer("I cannot help.") == []


def test_find_place():
    """Only a saved folder or subfolder is a place for a file."""
    assert folder_tree.find_place(TREE, "oceanman malta/PRENSA") == \
        "Oceanman Malta/Prensa"
    assert folder_tree.find_place(TREE, "Contratos") == "Contratos"
    # A folder with subfolders only holds files in its subfolders.
    assert folder_tree.find_place(TREE, "Oceanman Malta") is None
    assert folder_tree.find_place(TREE, "../Oceanman Malta/Prensa") is None
    assert folder_tree.find_place(TREE, "Contratos/Extra") is None


def test_clean_suggestion():
    """A suggestion is a new, safe folder, inside a saved one or on top."""
    assert folder_tree.clean_suggestion(
        {"parent": "Oceanman Malta", "name": "Entrevistas"}, TREE) == \
        "Oceanman Malta/Entrevistas"
    assert folder_tree.clean_suggestion(
        {"parent": None, "name": "Recibos?"}, TREE) == "Recibos"
    assert folder_tree.clean_suggestion(
        {"parent": "Oceanman Malta", "name": "prensa"}, TREE) is None
    assert folder_tree.clean_suggestion({"name": "CON"}, TREE) is None
    assert folder_tree.clean_suggestion("Entrevistas", TREE) is None


# --- Tree projects ---

TREE = [{"name": "Oceanman Malta",
         "subcategories": ["Prensa", "Fotos del evento"]},
        {"name": "Contratos", "subcategories": []}]


@pytest.fixture
def tree_project(old_project):
    """A new project with its own folder tree."""
    old_project["repo"].save_folder_tree(
        "Documental sobre un nadador en Malta", TREE)
    return old_project


def test_tree_structure_has_no_media_folders(tmp_path):
    """A tree project gets Drop Zone and its folders, nothing else."""
    organizer = FileOrganizer(str(tmp_path / "doc"))
    organizer.ensure_archive_structure(TREE)
    assert sorted(os.listdir(str(tmp_path / "doc"))) == \
        ["Contratos", "Drop Zone", "Oceanman Malta"]
    assert sorted(os.listdir(str(tmp_path / "doc" / "Oceanman Malta"))) == \
        ["Fotos del evento", "Prensa"]


def test_file_goes_to_the_folder_the_ai_picks(tree_project):
    """The folder comes from the content; the media type stays a column."""
    tree_project["ai"].metadata.update(
        {"folder": "oceanman malta", "subfolder": "prensa"})
    doc = tree_project["pipeline"].classify_document(
        drop(tree_project, "a.txt", "Article"))
    assert doc.file_path == os.path.join(
        str(tree_project["folder"]), "Oceanman Malta", "Prensa",
        "oceanman-malta_el-nuevo-dia_2026-07-15_001.txt")
    assert (doc.category, doc.subcategory) == ("Oceanman Malta", "Prensa")
    assert doc.media_type == "Press"
    assert doc.status == "Classified"
    prompt = tree_project["ai"].prompts[-1]
    assert "Documental sobre un nadador" in prompt
    assert "Fotos del evento" in prompt


def test_no_fit_stays_in_drop_zone_with_a_suggestion(tree_project):
    """No folder fits: Manual Review in the Drop Zone, nothing created."""
    tree_project["ai"].metadata.update({
        "folder": None, "subfolder": None,
        "suggested_folder": {"parent": "Oceanman Malta",
                             "name": "Entrevistas"}})
    doc = tree_project["pipeline"].classify_document(
        drop(tree_project, "a.txt", "Interview"))
    assert os.path.dirname(doc.file_path) == str(tree_project["drop_zone"])
    assert os.path.isfile(doc.file_path)
    assert doc.status == "Manual Review"
    assert doc.review_note == folder_tree.NO_FOLDER_NOTE
    assert doc.suggested_folder == "Oceanman Malta/Entrevistas"
    assert not os.path.exists(str(
        tree_project["folder"] / "Oceanman Malta" / "Entrevistas"))


@pytest.mark.parametrize("folder, subfolder", [
    ("Recetas", None),
    ("../..", None),
    ("Oceanman Malta", None),
    ("Oceanman Malta", "Entrevistas"),
])
def test_ai_cannot_pick_a_folder_outside_the_tree(tree_project, folder,
                                                  subfolder):
    """An invented or unsafe folder never moves the file."""
    tree_project["ai"].metadata.update(
        {"folder": folder, "subfolder": subfolder})
    doc = tree_project["pipeline"].classify_document(
        drop(tree_project, "a.txt", "Text"))
    assert os.path.dirname(doc.file_path) == str(tree_project["drop_zone"])
    assert doc.category is None
    assert doc.status == "Manual Review"


def test_file_without_text_stays_in_drop_zone(tree_project):
    """Without content there is no folder: a person chooses it."""
    path = tree_project["drop_zone"] / "clip.xyz"
    path.write_bytes(b"\x00\x01")
    doc = tree_project["pipeline"].classify_document(str(path))
    assert os.path.dirname(doc.file_path) == str(tree_project["drop_zone"])
    assert doc.review_note == folder_tree.NO_FOLDER_NOTE
    assert doc.status == "Manual Review"


def test_duplicate_in_a_tree_project_is_unchanged(tree_project):
    """A duplicate stays as it is, with its own note."""
    tree_project["ai"].metadata["folder"] = "Contratos"
    first = tree_project["pipeline"].classify_document(
        drop(tree_project, "a.txt", "Same"))
    copy = drop(tree_project, "copy.txt", "Same")
    doc = tree_project["pipeline"].classify_document(copy)
    assert doc.file_path == copy
    assert doc.duplicate_of == first.filename


def test_tree_survives_more_than_ten_folders(old_project):
    """The saved tree is read back whole, past the 10 category limit."""
    tree = [{"name": "Caso " + str(n), "subcategories": []}
            for n in range(15)]
    old_project["repo"].save_folder_tree("Oficina legal", tree)
    assert len(old_project["repo"].get_folder_tree()) == 15


# --- Routes ---

def active_repo(app):
    """Return the repository of the app fixture's active project."""
    return CatalogRepository(projects.catalog_path(
        app.config["PROJECT_FOLDER"]))


def create_tree_project(client, tmp_path, tree=None):
    """Create and open a new tree project; return its folder."""
    folder = tmp_path / "Doc"
    folder.mkdir()
    response = client.post("/projects", json={
        "name": "Doc", "folder": str(folder), "folders": tree or TREE,
        "description": "Documental sobre un nadador en Malta"})
    assert response.status_code == 201
    return folder


def test_create_project_makes_the_tree(flask_client, tmp_path):
    """A new project gets its tree on disk and in its catalog."""
    folder = create_tree_project(flask_client, tmp_path)
    assert sorted(os.listdir(str(folder))) == \
        [".cataloga", "Contratos", "Drop Zone", "Oceanman Malta"]
    settings = flask_client.get("/settings").get_json()
    assert settings["folder_mode"] == "tree"
    assert settings["project_description"].startswith("Documental")
    assert settings["categories"] == TREE
    assert settings["folder_counts"]["Oceanman Malta/Prensa"] == 0


@pytest.mark.parametrize("folders", [None, [], [{"name": "CON"}],
                                     [{"name": "A"}, {"name": "a"}]])
def test_create_project_needs_a_good_tree(flask_client, tmp_path, folders):
    """No folders or a bad name: nothing is created."""
    folder = tmp_path / "Doc"
    folder.mkdir()
    response = flask_client.post("/projects", json={
        "name": "Doc", "folder": str(folder), "folders": folders})
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_folders"
    assert os.listdir(str(folder)) == []


def test_opening_an_old_catalog_keeps_media_folders(flask_client, tmp_path):
    """A folder with an old catalog opens as it was, by type."""
    folder = tmp_path / "Old"
    make_project(str(tmp_path / "other.json"), folder, name="Old")
    response = flask_client.post("/projects", json={
        "name": "Old", "folder": str(folder)})
    assert response.get_json()["opened_existing"] is True
    assert flask_client.get("/settings").get_json()["folder_mode"] == \
        "media"
    assert (folder / "Press").is_dir()


class SuggestAI(AIProviderClient):
    """Fake Ollama Cloud that answers the folder request."""

    def __init__(self, answer):
        super().__init__(provider_name="ollama", model="gemma4:31b")
        self.api_key = "test-key"
        self.answer = answer
        self.prompts = []

    def send_prompt(self, system_prompt, text):
        self.prompts.append(system_prompt)
        return self.answer


def test_suggest_folders_uses_ollama_and_saves_nothing(empty_client,
                                                       monkeypatch):
    """The tree comes from Ollama Cloud, even before a project exists."""
    used = []
    answer = json.dumps([{"name": "Caso 1142", "subfolders": [
        "Contratos", "Evidencia"]}])

    def fake_client(name, model):
        used.append((name, model))
        return SuggestAI(answer)
    monkeypatch.setattr(project_routes, "create_client", fake_client)
    response = empty_client.post("/projects/folders/suggest", json={
        "description": "Archivo de casos de una oficina legal"})
    assert response.status_code == 200
    folders = response.get_json()["folders"]
    assert [(f["name"], f["subcategories"]) for f in folders] == [
        ("Caso 1142", ["Contratos", "Evidencia"])]
    assert used == [("ollama", "gemma4:31b")]
    assert empty_client.get("/projects").get_json()["projects"] == []


def test_suggest_folders_errors(empty_client, monkeypatch):
    """No description, no key, or no usable answer."""
    response = empty_client.post("/projects/folders/suggest", json={})
    assert response.status_code == 400
    no_key = SuggestAI("[]")
    no_key.api_key = None
    monkeypatch.setattr(project_routes, "create_client",
                        lambda name, model: no_key)
    response = empty_client.post("/projects/folders/suggest",
                                 json={"description": "Podcast"})
    assert response.get_json()["error"]["code"] == "no_api_key"
    monkeypatch.setattr(project_routes, "create_client",
                        lambda name, model: SuggestAI("No idea."))
    response = empty_client.post("/projects/folders/suggest",
                                 json={"description": "Podcast"})
    assert response.status_code == 502


def add_file_doc(repo, path, **fields):
    """Write a file and add its document row."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as file:
        file.write("text " + path)
    return repo.add_document(Document(
        original_filename=os.path.basename(path),
        filename=os.path.basename(path), media_type="Documents",
        file_path=path, date_added="2026-10-29T10:00:00", **fields))


def tree_repo(client, tmp_path):
    """Create a tree project and return (folder, repo)."""
    folder = create_tree_project(client, tmp_path)
    return folder, CatalogRepository(projects.catalog_path(str(folder)))


def test_move_document_to_another_folder(flask_client, tmp_path):
    """Move puts the file in the new folder and logs where it went."""
    folder, repo = tree_repo(flask_client, tmp_path)
    doc = add_file_doc(repo, str(folder / "Drop Zone" / "a.txt"),
                       status="Manual Review",
                       review_note=folder_tree.NO_FOLDER_NOTE,
                       suggested_folder="Recibos")
    response = flask_client.post("/documents/{}/move".format(doc.id),
                                 json={"folder": "Oceanman Malta/Prensa"})
    assert response.status_code == 200
    moved = response.get_json()
    assert moved["file_path"] == str(
        folder / "Oceanman Malta" / "Prensa" / "a.txt")
    assert os.path.isfile(moved["file_path"])
    assert (moved["category"], moved["subcategory"]) == \
        ("Oceanman Malta", "Prensa")
    assert moved["suggested_folder"] is None
    # Without source, date, and summary it still needs a person.
    assert moved["status"] == "Manual Review"
    assert moved["review_note"] == "Missing: source, document_date, summary"
    activity = flask_client.get("/dashboard/stats").get_json()[
        "recent_activity"]
    assert activity[0]["action"] == "Moved"


def test_move_keeps_both_files_with_the_same_name(flask_client, tmp_path):
    """A name already in the folder gets -2."""
    folder, repo = tree_repo(flask_client, tmp_path)
    add_file_doc(repo, str(folder / "Contratos" / "a.txt"))
    doc = add_file_doc(repo, str(folder / "Drop Zone" / "a.txt"))
    moved = flask_client.post("/documents/{}/move".format(doc.id),
                              json={"folder": "Contratos"}).get_json()
    assert moved["filename"] == "a-2.txt"


def test_create_folder_and_move(flask_client, tmp_path):
    """Only an explicit create_folder adds a folder to the tree."""
    folder, repo = tree_repo(flask_client, tmp_path)
    doc = add_file_doc(repo, str(folder / "Drop Zone" / "a.txt"))
    url = "/documents/{}/move".format(doc.id)
    response = flask_client.post(url, json={
        "folder": "Oceanman Malta/Entrevistas"})
    assert response.get_json()["error"]["code"] == "unknown_folder"
    assert not (folder / "Oceanman Malta" / "Entrevistas").exists()

    response = flask_client.post(url, json={
        "folder": "Oceanman Malta/Entrevistas", "create_folder": True})
    assert response.status_code == 200
    assert (folder / "Oceanman Malta" / "Entrevistas" / "a.txt").is_file()
    assert "Entrevistas" in repo.get_folder_tree()[0]["subcategories"]


def test_move_classifies_a_file_that_only_needs_a_folder(
        flask_client, tmp_path):
    """After Move or Create folder and move, a complete file is Classified."""
    folder, repo = tree_repo(flask_client, tmp_path)
    complete = {"status": "Manual Review", "source": "El Nuevo Dia",
                "document_date": "2024-05-02", "summary": "Una receta.",
                "review_note": folder_tree.NO_FOLDER_NOTE}
    doc = add_file_doc(repo, str(folder / "Drop Zone" / "a.txt"), **complete)
    moved = flask_client.post("/documents/{}/move".format(doc.id), json={
        "folder": "Vida Personal", "create_folder": True}).get_json()
    assert moved["status"] == "Classified"
    activity = flask_client.get("/dashboard/stats").get_json()[
        "recent_activity"]
    assert activity[0]["action"] == "Moved"

    doc = add_file_doc(repo, str(folder / "Drop Zone" / "b.txt"), **complete)
    moved = flask_client.post("/documents/{}/move".format(doc.id),
                              json={"folder": "Contratos"}).get_json()
    assert moved["status"] == "Classified"


def test_move_keeps_other_review_reasons(flask_client, tmp_path):
    """A missing field or another note keeps the file in Manual Review."""
    folder, repo = tree_repo(flask_client, tmp_path)
    no_date = add_file_doc(repo, str(folder / "Drop Zone" / "a.txt"),
                           status="Manual Review", source="El Nuevo Dia",
                           summary="Una receta.",
                           review_note=folder_tree.NO_FOLDER_NOTE)
    other_note = add_file_doc(repo, str(folder / "Drop Zone" / "b.txt"),
                              status="Manual Review", source="El Nuevo Dia",
                              document_date="2024-05-02",
                              summary="Una receta.",
                              review_note="This file is too big to read")
    for doc in (no_date, other_note):
        moved = flask_client.post("/documents/{}/move".format(doc.id),
                                  json={"folder": "Contratos"}).get_json()
        assert moved["status"] == "Manual Review"
    # The folder note is gone, so the empty field becomes the reason.
    assert flask_client.get("/documents/{}".format(no_date.id)).get_json()[
        "review_note"] == "Missing: document_date"
    assert flask_client.get("/documents/{}".format(other_note.id)).get_json()[
        "review_note"] == "This file is too big to read"


@pytest.mark.parametrize("target", ["../Outside", "Notas?/x", "CON"])
def test_create_folder_refuses_bad_names(flask_client, tmp_path, target):
    """A new folder follows the same name rules as the tree editor."""
    folder, repo = tree_repo(flask_client, tmp_path)
    doc = add_file_doc(repo, str(folder / "Drop Zone" / "a.txt"))
    response = flask_client.post("/documents/{}/move".format(doc.id), json={
        "folder": target, "create_folder": True})
    assert response.status_code == 400
    assert os.path.isfile(str(folder / "Drop Zone" / "a.txt"))
    assert not (tmp_path / "Outside").exists()


def test_move_refuses_files_outside_the_project(flask_client, tmp_path):
    """A row pointing outside the project never moves that file."""
    folder, repo = tree_repo(flask_client, tmp_path)
    outside = str(tmp_path / "elsewhere" / "a.txt")
    doc = add_file_doc(repo, outside)
    response = flask_client.post("/documents/{}/move".format(doc.id),
                                 json={"folder": "Contratos"})
    assert response.get_json()["error"]["code"] == "file_missing"
    assert os.path.isfile(outside)


def test_move_is_not_for_old_projects(flask_client, app):
    """A project sorted by type never moves files."""
    repo = active_repo(app)
    doc = add_file_doc(repo, os.path.join(app.config["PROJECT_FOLDER"],
                                          "Press", "a.txt"))
    response = flask_client.post("/documents/{}/move".format(doc.id),
                                 json={"folder": "Documents"})
    assert response.get_json()["error"]["code"] == "not_tree_project"


def test_patch_cannot_change_the_folder(flask_client, tmp_path):
    """In a tree project the folder only changes with Move."""
    folder, repo = tree_repo(flask_client, tmp_path)
    doc = add_file_doc(repo, str(folder / "Contratos" / "a.txt"),
                       category="Contratos")
    response = flask_client.patch("/documents/{}".format(doc.id),
                                  json={"category": "Oceanman Malta"})
    assert response.get_json()["error"]["code"] == "use_move"


def test_settings_adds_folders_on_disk(flask_client, tmp_path):
    """A folder added in Settings is created at Save."""
    folder, repo = tree_repo(flask_client, tmp_path)
    tree = TREE + [{"name": "Recibos", "subcategories": []}]
    response = flask_client.put("/settings", json={
        "research_name": "Doc", "categories": tree})
    assert response.status_code == 200
    assert (folder / "Recibos").is_dir()
    assert not (folder / "Press").exists()


def test_settings_removes_only_empty_folders(flask_client, tmp_path):
    """A folder with documents stays; an empty one leaves the tree only."""
    folder, repo = tree_repo(flask_client, tmp_path)
    add_file_doc(repo, str(folder / "Contratos" / "a.txt"),
                 category="Contratos")
    response = flask_client.put("/settings", json={
        "research_name": "Doc", "categories": TREE[:1]})
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "folder_not_empty"

    smaller = [{"name": "Oceanman Malta", "subcategories": ["Prensa"]},
               TREE[1]]
    response = flask_client.put("/settings", json={
        "research_name": "Doc", "categories": smaller})
    assert response.status_code == 200
    assert folder_tree.to_categories(repo.get_folder_tree()) == smaller
    # The folder on disk is never deleted.
    assert (folder / "Oceanman Malta" / "Fotos del evento").is_dir()


def test_old_catalog_gets_the_folder_columns(tmp_path):
    """An old catalog gains the new columns and stays a media project."""
    db_path = str(tmp_path / "old.db")
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE app_config (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "research_name TEXT NOT NULL, target_directory TEXT NOT NULL, "
        "app_lock_password_hash TEXT)")
    conn.execute("INSERT INTO app_config (research_name, target_directory)"
                 " VALUES ('Old', '/old')")
    conn.commit()
    conn.close()
    init_db(db_path)
    repo = CatalogRepository(db_path)
    assert repo.is_tree_project() is False
    assert repo.get_folder_tree() is None
    assert repo.get_app_config()["research_name"] == "Old"


# --- Chat ---

class ChatAI(AIProviderClient):
    """Fake chat model with one fixed answer."""

    def __init__(self, answer):
        super().__init__(provider_name="fake", model="fake-model")
        self.api_key = "test-key"
        self.answer = answer
        self.prompts = []

    def send_prompt(self, system_prompt, text):
        self.prompts.append(system_prompt)
        return json.dumps(self.answer)


def test_chat_proposes_a_move_and_moves_nothing(tmp_path, tree_project):
    """propose_move is checked against the tree; the file stays."""
    repo = tree_project["repo"]
    doc = add_file_doc(repo, str(tree_project["drop_zone"] / "a.txt"))
    ai = ChatAI({"action": "propose_move", "reply": "Sí.",
                 "document_id": doc.id, "folder": "oceanman malta/prensa"})
    result = chat_assistant.run_chat(repo, ai, "muévelo a Prensa")
    assert result["action"] == "propose_move"
    assert result["move"]["new_folder"] == "Oceanman Malta/Prensa"
    assert result["move"]["current_folder"] == ""
    assert os.path.isfile(doc.file_path)
    assert "propose_move" in ai.prompts[0]


@pytest.mark.parametrize("folder, notice", [
    ("Recetas", "move_invalid"), ("Oceanman Malta", "move_invalid")])
def test_chat_move_must_use_the_tree(tree_project, folder, notice):
    """An invented folder is refused."""
    repo = tree_project["repo"]
    doc = add_file_doc(repo, str(tree_project["drop_zone"] / "a.txt"))
    ai = ChatAI({"action": "propose_move", "reply": "",
                 "document_id": doc.id, "folder": folder})
    assert chat_assistant.run_chat(repo, ai, "x")["notice"] == notice


def test_chat_move_is_not_offered_in_old_projects(old_project):
    """An old project never gets propose_move."""
    repo = old_project["repo"]
    doc = add_file_doc(repo, str(old_project["drop_zone"] / "a.txt"))
    ai = ChatAI({"action": "propose_move", "reply": "",
                 "document_id": doc.id, "folder": "Press"})
    result = chat_assistant.run_chat(repo, ai, "x")
    assert result["notice"] == "move_unavailable"
    assert "propose_move" not in ai.prompts[0]
