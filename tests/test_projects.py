"""Tests for multi-project support."""

import os
import sqlite3

import pytest

from backend.app import create_app
from backend.config import account, projects
from backend.db.catalog_repository import CatalogRepository
from backend.db.schema import init_db
from backend.models.document import Document
from tests.conftest import logged_in_client, make_project

# Every new project needs at least one folder.
FOLDERS = [{"name": "Press", "subcategories": []}]


def assert_error(response, status, code):
    """Check the shared error shape: status code and error code."""
    assert response.status_code == status
    assert response.get_json()["error"]["code"] == code


# --- The project list file ---

def test_load_projects_without_a_file(tmp_path):
    """No file yet means an empty list with English."""
    data = projects.load_projects(str(tmp_path / "projects.json"))
    assert data == {"active_folder": "", "language": "en", "projects": []}


def test_add_and_switch_projects(tmp_path):
    """Adding makes a project active; switching updates last_opened."""
    path = str(tmp_path / "projects.json")
    projects.add_project(path, "A", "/a")
    projects.add_project(path, "B", "/b")
    assert projects.active_folder(path) == "/b"

    projects.set_active_project(path, "/a")
    data = projects.load_projects(path)
    assert data["active_folder"] == "/a"
    assert [p["name"] for p in data["projects"]] == ["A", "B"]
    with pytest.raises(KeyError):
        projects.set_active_project(path, "/not/listed")


def test_normalize_folder_removes_differences():
    """'~/x/' and the full path become the same text."""
    home = os.path.expanduser("~")
    assert projects.normalize_folder("~/Research/") == \
        os.path.join(home, "Research")


# --- GET /projects ---

def test_get_projects(flask_client, app):
    """The list shows the active project and whether it is available."""
    data = flask_client.get("/projects").get_json()
    assert data["active_folder"] == app.config["PROJECT_FOLDER"]
    assert len(data["projects"]) == 1
    assert data["projects"][0]["name"] == "Research"
    assert data["projects"][0]["available"] is True


# --- POST /projects ---

def test_create_project(flask_client, app, tmp_path):
    """A new project gets its catalog, folders, and becomes active."""
    folder = tmp_path / "Second"
    folder.mkdir()
    response = flask_client.post("/projects", json={
        "name": "Second", "folder": str(folder), "folders": FOLDERS,
        "naming_template": "{number}_{topic}"})

    assert response.status_code == 201
    assert response.get_json() == {"name": "Second", "folder": str(folder),
                                   "opened_existing": False}
    assert (folder / ".cataloga" / "catalog.db").is_file()
    assert (folder / "Drop Zone").is_dir()
    assert (folder / "Press").is_dir()
    settings = flask_client.get("/settings").get_json()
    assert settings["research_name"] == "Second"
    assert settings["target_directory"] == str(folder)
    assert settings["naming_template"] == "{number}_{topic}"


def test_create_project_starts_with_ollama_cloud(flask_client, app,
                                                 tmp_path):
    """A new project always starts with Ollama Cloud."""
    repo = CatalogRepository(
        projects.catalog_path(app.config["PROJECT_FOLDER"]))
    repo.set_active_provider("groq", "llama-3.1-8b-instant")
    folder = tmp_path / "Second"
    folder.mkdir()
    flask_client.post("/projects", json={"name": "Second",
                                         "folder": str(folder),
                                         "folders": FOLDERS})
    settings = flask_client.get("/settings").get_json()
    assert settings["active_provider"] == "ollama"
    assert settings["active_model"] == "gemma4:31b"


def test_projects_keep_separate_catalogs(flask_client, app, tmp_path):
    """Documents of one project never show in another."""
    first_repo = CatalogRepository(
        projects.catalog_path(app.config["PROJECT_FOLDER"]))
    first_repo.add_document(Document(
        original_filename="a.pdf", filename="a.pdf",
        media_type="Documents", file_path="/x/a.pdf",
        date_added="2026-10-26T10:00:00"))
    folder = tmp_path / "Second"
    folder.mkdir()
    flask_client.post("/projects", json={"name": "Second",
                                         "folder": str(folder),
                                         "folders": FOLDERS})
    assert flask_client.get("/documents").get_json() == []

    flask_client.put("/projects/active",
                     json={"folder": app.config["PROJECT_FOLDER"]})
    assert len(flask_client.get("/documents").get_json()) == 1


def test_create_first_project(empty_client, tmp_path):
    """The first project works on a fresh install."""
    folder = tmp_path / "First"
    folder.mkdir()
    response = empty_client.post("/projects", json={
        "name": "First", "folder": str(folder), "folders": FOLDERS})
    assert response.status_code == 201
    assert empty_client.get("/documents").get_json() == []
    # New projects start with method 4.
    assert empty_client.get("/settings").get_json()["naming_template"] \
        == "{topic}_{source}_{date}_{topic_number}"


def test_create_project_missing_fields(flask_client):
    """Name and folder are both required."""
    response = flask_client.post("/projects", json={"name": "X"})
    assert_error(response, 400, "missing_field")


def test_create_project_folder_must_exist(flask_client, tmp_path):
    """A folder that does not exist is rejected."""
    response = flask_client.post("/projects", json={
        "name": "X", "folder": str(tmp_path / "nope")})
    assert_error(response, 400, "invalid_directory")


def test_create_project_bad_template(flask_client, tmp_path):
    """The template is checked like in Settings, before anything is made."""
    folder = tmp_path / "Second"
    folder.mkdir()
    response = flask_client.post("/projects", json={
        "name": "X", "folder": str(folder), "naming_template": "{titulo}"})
    assert_error(response, 400, "invalid_template")
    assert response.get_json()["error"]["token"] == "{titulo}"
    assert not (folder / ".cataloga").exists()


def test_create_project_twice(flask_client, app):
    """A folder that is already a project is not added again."""
    response = flask_client.post("/projects", json={
        "name": "Again", "folder": app.config["PROJECT_FOLDER"] + "/"})
    assert_error(response, 409, "project_exists")


def test_create_project_warns_about_user_files(flask_client, tmp_path):
    """A folder with user files needs confirmation; files never move."""
    folder = tmp_path / "PEDRO_NAVAJA"
    folder.mkdir()
    (folder / "poster.png").write_text("x")
    (folder / "notes.txt").write_text("x")
    body = {"name": "X", "folder": str(folder), "folders": FOLDERS}

    first = flask_client.post("/projects", json=body)
    assert_error(first, 409, "folder_not_empty")
    assert first.get_json()["error"]["count"] == 2
    assert not (folder / ".cataloga").exists()

    body["confirm_folder"] = True
    assert flask_client.post("/projects", json=body).status_code == 201
    assert (folder / "poster.png").is_file()


def test_create_project_in_a_new_folder_never_renames_its_inbox(
        flask_client, tmp_path):
    """A user's own Inbox in a new folder is never renamed or moved."""
    folder = tmp_path / "Other"
    (folder / "Inbox").mkdir(parents=True)
    (folder / "Inbox" / "mail.eml").write_text("x")
    flask_client.post("/projects", json={
        "name": "A", "folder": str(folder), "folders": FOLDERS,
        "confirm_folder": True})
    assert (folder / "Inbox" / "mail.eml").is_file()
    assert (folder / "Drop Zone").is_dir()


def test_open_a_folder_that_already_has_a_catalog(flask_client, tmp_path):
    """A folder with a catalog opens with its data and name."""
    folder = tmp_path / "From another Mac"
    other_list = str(tmp_path / "other_projects.json")
    repo = make_project(other_list, folder, name="Old Research")
    repo.add_document(Document(
        original_filename="a.pdf", filename="a.pdf",
        media_type="Press", file_path=str(folder / "Press" / "a.pdf"),
        date_added="2026-10-26T10:00:00"))

    response = flask_client.post("/projects", json={
        "name": "Whatever", "folder": str(folder)})

    assert response.status_code == 201
    assert response.get_json()["opened_existing"] is True
    assert response.get_json()["name"] == "Old Research"
    assert len(flask_client.get("/documents").get_json()) == 1


# --- PUT /projects/active ---

def test_switch_to_unknown_folder(flask_client, tmp_path):
    """Only folders in the list can be chosen."""
    response = flask_client.put("/projects/active",
                                json={"folder": str(tmp_path / "x")})
    assert_error(response, 404, "not_found")


def test_switch_needs_a_folder(flask_client):
    """The folder is required."""
    assert_error(flask_client.put("/projects/active", json={}), 400,
                 "missing_field")


# --- DELETE /projects ---

def set_last_opened(projects_path, times):
    """Write a last_opened time for each folder in the project list."""
    data = projects.load_projects(projects_path)
    for project in data["projects"]:
        project["last_opened"] = times[project["folder"]]
    projects.save_projects(projects_path, data)


def test_remove_an_inactive_project(flask_client, app, projects_path,
                                    tmp_path):
    """Removing another project keeps the active one."""
    other = tmp_path / "Other"
    make_project(projects_path, other, name="Other")
    projects.set_active_project(projects_path, app.config["PROJECT_FOLDER"])

    response = flask_client.delete("/projects", json={"folder": str(other)})

    assert response.status_code == 200
    body = response.get_json()
    assert body["active_folder"] == app.config["PROJECT_FOLDER"]
    assert [p["name"] for p in body["projects"]] == ["Research"]


def test_remove_the_active_project(flask_client, app, projects_path,
                                   tmp_path):
    """The most recently opened of the others becomes active."""
    older = tmp_path / "Older"
    newer = tmp_path / "Newer"
    active = tmp_path / "Active"
    make_project(projects_path, older, name="Older")
    make_project(projects_path, newer, name="Newer")
    make_project(projects_path, active, name="Active")
    set_last_opened(projects_path, {
        app.config["PROJECT_FOLDER"]: "2026-10-01T09:00:00",
        str(older): "2026-10-10T09:00:00",
        str(newer): "2026-10-20T09:00:00",
        str(active): "2026-10-27T09:00:00",
    })

    response = flask_client.delete("/projects", json={"folder": str(active)})

    assert response.status_code == 200
    assert response.get_json()["active_folder"] == str(newer)
    assert flask_client.get("/settings").get_json()[
        "research_name"] == "Newer"


def test_remove_the_last_project(flask_client, app, projects_path):
    """Removing the last project keeps the list file."""
    response = flask_client.delete(
        "/projects", json={"folder": app.config["PROJECT_FOLDER"]})

    assert response.status_code == 200
    assert response.get_json() == {"active_folder": "", "projects": []}
    assert flask_client.get("/settings").get_json()[
        "project_status"] == "none"
    assert os.path.isfile(projects_path)


def test_remove_never_deletes_files(flask_client, app):
    """The folder, Drop Zone, .cataloga, and the user's files stay."""
    folder = app.config["PROJECT_FOLDER"]
    user_file = os.path.join(folder, "my notes.txt")
    with open(user_file, "w") as file:
        file.write("keep me")

    flask_client.delete("/projects", json={"folder": folder})

    assert os.path.isdir(folder)
    assert os.path.isdir(os.path.join(folder, "Drop Zone"))
    assert os.path.isfile(projects.catalog_path(folder))
    with open(user_file) as file:
        assert file.read() == "keep me"


def test_add_a_removed_folder_again(flask_client, app):
    """Adding the same folder again opens its catalog with its data."""
    folder = app.config["PROJECT_FOLDER"]
    CatalogRepository(projects.catalog_path(folder)).add_document(Document(
        original_filename="a.pdf", filename="a.pdf",
        media_type="Press", file_path=folder + "/Drop Zone/Press/a.pdf",
        date_added="2026-10-27T10:00:00"))
    flask_client.delete("/projects", json={"folder": folder})

    response = flask_client.post("/projects", json={"name": "Typed name",
                                                    "folder": folder})

    assert response.status_code == 201
    assert response.get_json()["opened_existing"] is True
    # The saved name wins over the one typed in the form.
    assert response.get_json()["name"] == "Research"
    documents = flask_client.get("/documents").get_json()
    assert [d["filename"] for d in documents] == ["a.pdf"]


def test_remove_unknown_folder(flask_client, tmp_path):
    """Only folders in the list can be removed."""
    response = flask_client.delete("/projects",
                                   json={"folder": str(tmp_path / "x")})
    assert_error(response, 404, "not_found")


def test_remove_needs_a_folder(flask_client):
    """The folder is required."""
    assert_error(flask_client.delete("/projects", json={}), 400,
                 "missing_field")


# --- Turning the old single database into the first project ---

def make_old_database(path, folder, with_language=True):
    """Build a database like the one used before projects existed."""
    init_db(path)
    repo = CatalogRepository(path)
    repo.save_app_config("El Delfin", str(folder))
    if with_language:
        repo.save_language("es")
    repo.set_active_provider("gemini", "gemini-2.5-flash")
    repo.add_document(Document(
        original_filename="clip.pdf", filename="PR_001.pdf",
        media_type="Press", file_path=str(folder / "Press" / "PR_001.pdf"),
        date_added="2026-10-20T10:00:00", source="Claridad",
        summary="A swim meet.", status="Classified"))


def test_old_database_becomes_the_first_project(tmp_path):
    """Nothing is lost: documents, provider, name, and language."""
    folder = tmp_path / "El Delfin"
    (folder / "Press").mkdir(parents=True)
    old_db = str(tmp_path / "database" / "catalog.db")
    os.makedirs(os.path.dirname(old_db))
    make_old_database(old_db, folder)
    old_bytes = open(old_db, "rb").read()
    data_folder = str(tmp_path / "app_data")
    # The install also had its one account next to the project list.
    account.save_account(os.path.join(data_folder, "account.json"),
                         "luis", "password123")

    app = create_app(data_folder=data_folder, old_db_path=old_db)
    client = logged_in_client(app, username="luis")

    documents = client.get("/documents").get_json()
    assert [doc["filename"] for doc in documents] == ["PR_001.pdf"]
    assert documents[0]["file_path"] == str(folder / "Press" / "PR_001.pdf")
    settings = client.get("/settings").get_json()
    assert settings["research_name"] == "El Delfin"
    assert settings["language"] == "es"
    assert settings["active_provider"] == "gemini"
    assert settings["naming_template"] == "{date}_{topic}"
    # The old database is a backup: it was not changed.
    assert open(old_db, "rb").read() == old_bytes


def test_old_database_without_new_columns(tmp_path):
    """A database older than the language column also converts."""
    folder = tmp_path / "Project"
    folder.mkdir()
    old_db = str(tmp_path / "catalog.db")
    conn = sqlite3.connect(old_db)
    conn.execute(
        "CREATE TABLE app_config (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "research_name TEXT NOT NULL, target_directory TEXT NOT NULL, "
        "app_lock_password_hash TEXT)")
    conn.execute("INSERT INTO app_config (research_name, target_directory) "
                 "VALUES ('Old', ?)", (str(folder),))
    conn.commit()
    conn.close()
    projects_path = str(tmp_path / "projects.json")

    assert projects.migrate_old_database(projects_path, old_db) is True
    data = projects.load_projects(projects_path)
    assert data["language"] == "en"
    assert data["projects"][0]["name"] == "Old"
    repo = CatalogRepository(projects.catalog_path(str(folder)))
    assert repo.get_naming_template() == "{date}_{topic}"


def test_conversion_waits_for_a_missing_folder(tmp_path):
    """If the folder is not there, nothing is written; it retries later."""
    folder = tmp_path / "External drive"
    old_db = str(tmp_path / "catalog.db")
    folder.mkdir()
    make_old_database(old_db, folder)
    folder.rmdir()
    projects_path = str(tmp_path / "projects.json")

    assert projects.migrate_old_database(projects_path, old_db) is False
    assert not os.path.exists(projects_path)

    # The drive is connected again: the next start converts it.
    folder.mkdir()
    assert projects.migrate_old_database(projects_path, old_db) is True


def test_conversion_runs_only_once(tmp_path):
    """Once projects.json exists, the old database is left alone."""
    folder = tmp_path / "Project"
    folder.mkdir()
    old_db = str(tmp_path / "catalog.db")
    make_old_database(old_db, folder)
    projects_path = str(tmp_path / "projects.json")
    projects.save_projects(projects_path, projects.empty_project_list())

    assert projects.migrate_old_database(projects_path, old_db) is False
    assert not (folder / ".cataloga").exists()


def test_conversion_keeps_an_existing_catalog(tmp_path):
    """A catalog already in the folder is never overwritten."""
    folder = tmp_path / "Project"
    other_list = str(tmp_path / "other.json")
    repo = make_project(other_list, folder, name="Newer")
    old_db = str(tmp_path / "catalog.db")
    make_old_database(old_db, folder)
    projects_path = str(tmp_path / "projects.json")

    projects.migrate_old_database(projects_path, old_db)

    assert repo.get_all_documents() == []
    assert repo.get_app_config()["research_name"] == "Newer"
    names = [p["name"] for p in
             projects.load_projects(projects_path)["projects"]]
    assert names == ["Newer"]


def test_fresh_install_has_no_projects(empty_client):
    """With no old database, the app starts with an empty list."""
    assert empty_client.get("/projects").get_json() == {
        "active_folder": "", "projects": []}
