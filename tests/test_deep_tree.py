"""Tests for folder trees of any depth, the catch-all, and numbered folders."""

import os

import pytest

from backend.db.catalog_repository import CatalogRepository
from backend.db.schema import get_connection, init_db
from backend.pipeline import folder_tree
from backend.pipeline.file_organizer import FileOrganizer
from tests.test_project_folders import (  # noqa: F401
    add_file_doc, create_tree_project, drop, old_project, tree_project)

# Luis's photo archive: five levels, an events folder, a catch-all.
DEEP = [{"name": "INVESTIGACION", "children": [
    {"name": "FOTOS", "children": [
        {"name": "EVENTOS_DEPORTIVOS", "events": True, "children": [
            {"name": "Trialo-Isla-Verde_1998"},
            {"name": "Juegos-Nacionales_1997"}]},
        {"name": "ESCUELA"},
        {"name": "SIN_TEMA", "fallback": True}]},
    {"name": "PRENSA"}]},
    {"name": "Contratos"}]


# --- The tree itself ---

def test_check_tree_keeps_every_level_and_mark():
    """Five levels, the marks, and the old two-level names survive."""
    tree = folder_tree.check_tree(DEEP)
    assert folder_tree.depth_of(tree) == 4
    assert tree[0]["children"][0]["children"][0]["events"] is True
    assert tree[0]["subcategories"] == ["FOTOS", "PRENSA"]
    assert folder_tree.all_places(tree) == [
        "INVESTIGACION/FOTOS/EVENTOS_DEPORTIVOS/Trialo-Isla-Verde_1998",
        "INVESTIGACION/FOTOS/EVENTOS_DEPORTIVOS/Juegos-Nacionales_1997",
        "INVESTIGACION/FOTOS/ESCUELA", "INVESTIGACION/FOTOS/SIN_TEMA",
        "INVESTIGACION/PRENSA", "Contratos"]
    assert folder_tree.to_categories(tree) == [
        {"name": "INVESTIGACION", "subcategories": ["FOTOS", "PRENSA"]},
        {"name": "Contratos", "subcategories": []}]


def test_old_two_level_lists_still_work():
    """A list with subcategories as names is the same tree as before."""
    tree = folder_tree.check_tree([{"name": "A", "subcategories": ["B"]}])
    assert tree[0]["children"][0]["name"] == "B"
    assert folder_tree.all_places(tree) == ["A/B"]
    assert folder_tree.find_place(tree, "a/b") == "A/B"
    assert folder_tree.find_place(tree, "A") is None


def test_tree_limits():
    """Seven levels, 11 subfolders, or twins at one level are refused."""
    seven = {"name": "L1"}
    node = seven
    for level in range(2, 8):
        node["children"] = [{"name": "L{}".format(level)}]
        node = node["children"][0]
    with pytest.raises(ValueError, match="levels"):
        folder_tree.check_tree([seven])
    with pytest.raises(ValueError, match="subfolders"):
        folder_tree.check_tree([{"name": "A", "children": [
            {"name": "s{}".format(i)} for i in range(11)]}])
    with pytest.raises(ValueError, match="same name"):
        folder_tree.check_tree([{"name": "A", "children": [
            {"name": "x"}, {"name": "X"}]}])


def test_find_place_and_paths():
    """Paths match ignoring case; only folders without subfolders count."""
    tree = folder_tree.check_tree(DEEP)
    assert folder_tree.find_place(
        tree, "investigacion/fotos/eventos_deportivos/trialo-isla-verde_1998"
    ) == "INVESTIGACION/FOTOS/EVENTOS_DEPORTIVOS/Trialo-Isla-Verde_1998"
    assert folder_tree.find_place(tree, "INVESTIGACION/FOTOS") is None
    assert folder_tree.find_place(tree, "Nada") is None
    assert folder_tree.first_two("A/B/C/D") == ("A", "B")
    assert folder_tree.first_two("A") == ("A", None)
    assert folder_tree.node_at(tree, "INVESTIGACION/FOTOS/SIN_TEMA")[
        "fallback"] is True


def test_catch_all_by_mark_or_by_name():
    """The marked folder is the catch-all; else a name like Otros is."""
    assert folder_tree.fallback_place(folder_tree.check_tree(DEEP)) == \
        "INVESTIGACION/FOTOS/SIN_TEMA"
    by_name = folder_tree.check_tree([{"name": "Prensa"},
                                      {"name": "Otros"}])
    assert folder_tree.fallback_place(by_name) == "Otros"
    none = folder_tree.check_tree([{"name": "Prensa"}])
    assert folder_tree.fallback_place(none) is None


def test_add_place_creates_every_missing_level():
    """Create folder and move can add a nested path at once."""
    tree = folder_tree.check_tree(DEEP)
    tree = folder_tree.add_place(tree,
                                 "INVESTIGACION/FOTOS/FAMILIA/Boda_2003")
    assert "INVESTIGACION/FOTOS/FAMILIA/Boda_2003" in \
        folder_tree.all_places(tree)
    with pytest.raises(ValueError):
        folder_tree.add_place(tree, "Contratos")


def test_number_new_folders_leaves_existing_ones():
    """New folders get 01_; folders already on disk keep their names."""
    tree = folder_tree.check_tree([{"name": "Prensa"}, {"name": "Fotos",
                                   "children": [{"name": "Eventos"}]}])
    numbered = folder_tree.number_new(tree, ["Prensa"])
    assert [n["name"] for n in numbered] == ["Prensa", "02_Fotos"]
    assert numbered[1]["children"][0]["name"] == "01_Eventos"
    again = folder_tree.number_new(numbered, ["Prensa", "02_Fotos"])
    assert [n["name"] for n in again] == ["Prensa", "02_Fotos"]


def test_ai_tree_can_be_deep():
    """The AI may answer nested subfolders; they are kept up to six."""
    tree = folder_tree.parse_tree_answer(
        '[{"name": "A", "subfolders": [{"name": "B", "subfolders": ["C"]}]}]')
    assert folder_tree.all_places(tree) == ["A/B/C"]


# --- The disk and the catalog ---

def test_structure_is_created_at_every_level(tmp_path):
    """ensure_archive_structure makes the nested folders."""
    organizer = FileOrganizer(str(tmp_path / "p"))
    organizer.ensure_archive_structure(folder_tree.check_tree(DEEP))
    assert (tmp_path / "p" / "INVESTIGACION" / "FOTOS" /
            "EVENTOS_DEPORTIVOS" / "Trialo-Isla-Verde_1998").is_dir()
    assert organizer.tree_folder("A/B/C") == str(tmp_path / "p" / "A" /
                                                 "B" / "C")
    assert organizer.tree_folder("A", "B") == str(tmp_path / "p" / "A" / "B")


def test_old_rows_get_their_folder_path(tmp_path):
    """Documents saved before folder_path get it from the two columns."""
    db = str(tmp_path / "old.db")
    init_db(db)
    conn = get_connection(db)
    conn.execute("ALTER TABLE documents DROP COLUMN folder_path")
    conn.execute("INSERT INTO documents (original_filename, filename, "
                 "media_type, file_path, date_added, category, subcategory) "
                 "VALUES ('a', 'a', 'Press', '/a', 'now', 'Prensa', 'Local')")
    conn.execute("INSERT INTO documents (original_filename, filename, "
                 "media_type, file_path, date_added, category) "
                 "VALUES ('b', 'b', 'Press', '/b', 'now', 'Contratos')")
    conn.commit()
    conn.close()
    init_db(db)
    docs = CatalogRepository(db).get_all_documents()
    assert [doc.folder_path for doc in docs] == ["Prensa/Local", "Contratos"]


def test_two_level_project_reads_as_a_tree(tree_project):
    """A project saved with categories gives the same tree, with children."""
    tree = tree_project["repo"].get_folder_tree()
    assert tree[0]["children"][0]["name"] == "Prensa"
    assert tree_project["repo"].count_in_path("Oceanman Malta") == 0


# --- The pipeline ---

def deep_project(tree_project):
    """Turn the fixture's project into the deep photo archive."""
    tree_project["repo"].save_folder_tree("Archivo de fotos", DEEP)
    FileOrganizer(str(tree_project["folder"])).ensure_archive_structure(
        tree_project["repo"].get_folder_tree())
    return tree_project


def test_file_goes_to_a_deep_folder(tree_project):
    """The AI answers a path; the file lands there, with the two columns."""
    project = deep_project(tree_project)
    project["ai"].metadata.update({
        "folder": "investigacion/fotos/eventos_deportivos/"
                  "trialo-isla-verde_1998"})
    doc = project["pipeline"].classify_document(drop(project, "a.txt", "x"))
    assert doc.folder_path == \
        "INVESTIGACION/FOTOS/EVENTOS_DEPORTIVOS/Trialo-Isla-Verde_1998"
    assert (doc.category, doc.subcategory) == ("INVESTIGACION", "FOTOS")
    assert doc.file_path.startswith(os.path.join(
        str(project["folder"]), "INVESTIGACION", "FOTOS",
        "EVENTOS_DEPORTIVOS", "Trialo-Isla-Verde_1998"))
    prompt = project["ai"].prompts[-1]
    assert "INVESTIGACION/FOTOS/SIN_TEMA" in prompt


def test_file_that_fits_nowhere_goes_to_the_catch_all(tree_project):
    """With a catch-all in the tree, no fit is not Manual Review."""
    project = deep_project(tree_project)
    project["ai"].metadata.update({"folder": None})
    doc = project["pipeline"].classify_document(drop(project, "a.txt", "x"))
    assert doc.folder_path == "INVESTIGACION/FOTOS/SIN_TEMA"
    assert doc.status == "Classified"
    assert doc.review_note is None


def test_without_a_catch_all_no_fit_is_still_manual_review(tree_project):
    """The old behavior stays when nothing is marked or named for it."""
    tree_project["ai"].metadata.update({"folder": "Nada"})
    doc = tree_project["pipeline"].classify_document(
        drop(tree_project, "a.txt", "x"))
    assert doc.status == "Manual Review"
    assert doc.review_note == folder_tree.NO_FOLDER_NOTE


# --- Routes ---

def test_settings_shows_the_deep_tree_and_its_counts(flask_client, tmp_path):
    """GET /settings has folder_tree (any depth) and counts per path."""
    folder = create_tree_project(flask_client, tmp_path, DEEP)
    settings = flask_client.get("/settings").get_json()
    assert settings["folder_tree"][0]["children"][0]["name"] == "FOTOS"
    assert settings["categories"] == folder_tree.to_categories(
        folder_tree.check_tree(DEEP))
    assert settings["folder_counts"][
        "INVESTIGACION/FOTOS/EVENTOS_DEPORTIVOS"] == 0
    assert (folder / "INVESTIGACION" / "FOTOS" / "SIN_TEMA").is_dir()


def test_move_to_a_deep_folder_and_create_one(flask_client, tmp_path):
    """Move takes a path; Create folder and move adds the missing levels."""
    folder = create_tree_project(flask_client, tmp_path, DEEP)
    repo = CatalogRepository(os.path.join(str(folder), ".cataloga",
                                          "catalog.db"))
    doc = add_file_doc(repo, str(folder / "Drop Zone" / "a.txt"))
    place = "INVESTIGACION/FOTOS/EVENTOS_DEPORTIVOS/Trialo-Isla-Verde_1998"
    moved = flask_client.post("/documents/{}/move".format(doc.id),
                              json={"folder": place}).get_json()
    assert moved["folder_path"] == place
    assert moved["category"] == "INVESTIGACION"
    assert os.path.isfile(str(folder / "INVESTIGACION" / "FOTOS" /
                              "EVENTOS_DEPORTIVOS" /
                              "Trialo-Isla-Verde_1998" / "a.txt"))
    response = flask_client.post("/documents/{}/move".format(doc.id), json={
        "folder": "INVESTIGACION/FOTOS/FAMILIA/Boda_2003",
        "create_folder": True})
    assert response.status_code == 200
    assert (folder / "INVESTIGACION" / "FOTOS" / "FAMILIA" /
            "Boda_2003" / "a.txt").is_file()
    assert repo.count_in_path("INVESTIGACION/FOTOS") == 1
    assert repo.count_in_path("INVESTIGACION/FOTOS/FAMILIA") == 1


def test_settings_keeps_folders_with_documents_and_numbers_new_ones(
        flask_client, tmp_path):
    """A deep folder with files cannot go; new folders get 01_ if asked."""
    folder = create_tree_project(flask_client, tmp_path, DEEP)
    repo = CatalogRepository(os.path.join(str(folder), ".cataloga",
                                          "catalog.db"))
    doc = add_file_doc(repo, str(folder / "Drop Zone" / "a.txt"))
    flask_client.post("/documents/{}/move".format(doc.id),
                      json={"folder": "INVESTIGACION/PRENSA"})
    without_prensa = [{"name": "INVESTIGACION", "children": [
        {"name": "FOTOS"}]}, {"name": "Contratos"}]
    response = flask_client.put("/settings", json={
        "research_name": "Doc", "folder_tree": without_prensa})
    assert response.get_json()["error"]["code"] == "folder_not_empty"

    with_new = folder_tree.check_tree(DEEP)
    with_new.append({"name": "Entrevistas", "children": [{"name": "Radio"}]})
    response = flask_client.put("/settings", json={
        "research_name": "Doc", "folder_tree": with_new,
        "numbered_folders": True})
    assert response.status_code == 200
    names = [n["name"] for n in response.get_json()["folder_tree"]]
    assert names == ["INVESTIGACION", "Contratos", "03_Entrevistas"]
    assert response.get_json()["numbered_folders"] is True
    assert (folder / "03_Entrevistas" / "01_Radio").is_dir()


def test_new_project_can_number_its_folders(flask_client, tmp_path):
    """numbered_folders at creation prefixes every folder."""
    folder = tmp_path / "Legal"
    folder.mkdir()
    response = flask_client.post("/projects", json={
        "name": "Legal", "folder": str(folder), "numbered_folders": True,
        "folders": [{"name": "Pleadings"}, {"name": "Discovery",
                                            "children": [{"name": "Docs"}]}]})
    assert response.status_code == 201
    assert sorted(os.listdir(str(folder))) == [
        ".cataloga", "01_Pleadings", "02_Discovery", "Drop Zone"]
    assert (folder / "02_Discovery" / "01_Docs").is_dir()
