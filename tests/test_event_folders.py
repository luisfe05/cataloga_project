"""Tests for event folders and the Event_Year_N naming method."""

import os

from backend import scanner
from backend.db.catalog_repository import CatalogRepository
from backend.db.schema import init_db
from backend.pipeline import folder_tree, naming
from backend.pipeline.file_organizer import FileOrganizer
# The fixtures come along with the helpers.
from tests.test_project_folders import drop, old_project, tree_project  # noqa

PHOTOS = [{"name": "INVESTIGACION", "children": [
    {"name": "FOTOS", "children": [
        {"name": "EVENTOS_DEPORTIVOS", "events": True, "children": [
            {"name": "Juegos-Nacionales_1997"},
            {"name": "Trialo-Isla-Verde_1998"}]},
        {"name": "ESCUELA"},
        {"name": "SIN_TEMA", "fallback": True}]}]}]

EVENTS = "INVESTIGACION/FOTOS/EVENTOS_DEPORTIVOS"


def photo_project(tree_project, template=naming.EVENT_TEMPLATE):
    """Turn the fixture into the photo archive with 13 photos of 1997."""
    repo = tree_project["repo"]
    repo.save_folder_tree("Archivo de fotos", PHOTOS)
    repo.save_naming_template(template)
    repo.save_config_value("naming_style", "title")
    organizer = FileOrganizer(str(tree_project["folder"]))
    organizer.ensure_archive_structure(repo.get_folder_tree())
    juegos = tree_project["folder"] / "INVESTIGACION" / "FOTOS" / \
        "EVENTOS_DEPORTIVOS" / "Juegos-Nacionales_1997"
    for i in range(1, 14):
        (juegos / "Juegos-Nacionales_1997_{}.tif".format(i)).write_bytes(b"x")
    tree_project["juegos"] = juegos
    return tree_project


# --- The tree helpers ---

def test_event_helpers():
    """Events folders, their parent, the event of a place, and its year."""
    tree = folder_tree.check_tree(PHOTOS)
    assert folder_tree.event_places(tree) == [EVENTS]
    assert folder_tree.event_parent(tree, EVENTS + "/Regata_2003") == EVENTS
    assert folder_tree.event_parent(tree, "INVESTIGACION/FOTOS/x") is None
    assert folder_tree.event_of(tree, EVENTS + "/Trialo-Isla-Verde_1998") == \
        "Trialo-Isla-Verde_1998"
    assert folder_tree.event_of(tree, "INVESTIGACION/FOTOS/ESCUELA") is None
    assert folder_tree.event_year("Trialo-Isla-Verde_1998") == "1998"
    assert folder_tree.event_year("Boda 2003") == "2003"
    assert folder_tree.event_year("ESCUELA") is None


def test_next_event_number_counts_the_disk(tmp_path):
    """Thirteen photos on the disk, whoever named them, give 14."""
    folder = tmp_path / "Juegos_1997"
    folder.mkdir()
    for i in (1, 2, 13, 7):
        (folder / "Juegos_1997_{}.tif".format(i)).write_bytes(b"x")
    (folder / "Juegos_1997_3-edit.tif").write_bytes(b"x")
    (folder / "notas.txt").write_bytes(b"x")
    assert naming.next_event_number(str(folder), "Juegos_1997") == 14
    assert naming.next_event_number(str(tmp_path / "none"), "x") == 1


def test_event_template_is_valid_and_renders():
    """{event}_{n} is a template; the event name is kept as it is."""
    assert naming.validate_template(naming.EVENT_TEMPLATE) is None
    parts = naming.build_parts("IMG_0042.jpg", 5, event="Trialo-Isla_1998",
                               event_number=14)
    assert naming.make_filename(naming.EVENT_TEMPLATE, parts, ".JPG") == \
        "Trialo-Isla_1998_14.jpg"


# --- The pipeline ---

def test_five_new_photos_get_the_next_numbers(tree_project):
    """Five photos of the 1997 games land in their folder as _14 to _18."""
    project = photo_project(tree_project)
    project["ai"].metadata.update(
        {"folder": EVENTS + "/Juegos-Nacionales_1997"})
    names = []
    for i in range(5):
        # Different bytes each time: the same bytes would be a duplicate.
        doc = project["pipeline"].classify_document(
            drop(project, "IMG_00{}.txt".format(i), "photo " + str(i)))
        names.append(doc.filename)
        assert doc.folder_path == EVENTS + "/Juegos-Nacionales_1997"
    assert names == ["Juegos-Nacionales_1997_{}.txt".format(n)
                     for n in range(14, 19)]
    assert sorted(os.listdir(str(project["juegos"])))[-1] == \
        "Juegos-Nacionales_1997_9.tif"
    assert len(os.listdir(str(project["juegos"]))) == 18


def test_event_year_is_the_date_when_nothing_better_is_known(tree_project):
    """A photo in Trialo-Isla-Verde_1998 with no date is from 1998."""
    project = photo_project(tree_project)
    project["ai"].metadata.update(
        {"folder": EVENTS + "/Trialo-Isla-Verde_1998", "document_date": None})
    doc = project["pipeline"].classify_document(
        drop(project, "IMG_0001.txt", "photo text"))
    assert doc.document_date == "1998"
    assert doc.date_source == "name"


def test_new_event_is_proposed_only_inside_an_events_folder(tree_project):
    """A folder that does not exist yet is proposed there, never elsewhere."""
    project = photo_project(tree_project)
    project["ai"].metadata.update({"folder": EVENTS + "/Regata-Ponce_2003"})
    doc = project["pipeline"].classify_document(
        drop(project, "a.txt", "regata"))
    assert doc.status == "Manual Review"
    assert doc.suggested_folder == EVENTS + "/Regata-Ponce_2003"
    assert not (project["folder"] / "INVESTIGACION" / "FOTOS" /
                "EVENTOS_DEPORTIVOS" / "Regata-Ponce_2003").exists()
    # Outside the events folder: the catch-all, no new folder.
    project["ai"].metadata.update({"folder": "INVESTIGACION/FOTOS/Nueva_2003"})
    doc = project["pipeline"].classify_document(
        drop(project, "b.txt", "otra"))
    assert doc.folder_path == "INVESTIGACION/FOTOS/SIN_TEMA"
    assert doc.suggested_folder is None


def test_the_prompt_names_the_event_folders(tree_project):
    """The AI is told which folders hold events and how to name a new one."""
    project = photo_project(tree_project)
    project["pipeline"].classify_document(drop(project, "a.txt", "x"))
    prompt = project["ai"].prompts[-1]
    assert "one folder per event" in prompt
    assert EVENTS in prompt
    assert "Regata-Ponce_2003" in prompt


def test_outside_an_event_folder_method_4_names_the_file(tree_project):
    """With the event method on, a file in ESCUELA gets topic_source_date."""
    project = photo_project(tree_project)
    project["ai"].metadata.update({"folder": "INVESTIGACION/FOTOS/ESCUELA"})
    doc = project["pipeline"].classify_document(
        drop(project, "a.txt", "escuela"))
    assert doc.filename == "Oceanman-Malta_El-Nuevo-Día_2026-07-15.txt" or \
        doc.filename.startswith("Oceanman-Malta_El-Nuevo-D")


def test_in_place_scan_proposes_the_event_folder(tmp_path, tree_project):
    """Read in place, a photo of a new event gets the folder as a proposal."""
    project = photo_project(tree_project)
    repo = project["repo"]
    repo.save_config_value("folder_mode", folder_tree.PLACE_MODE)
    loose = project["folder"] / "regata.txt"
    loose.write_text("regata")
    project["ai"].metadata.update({"folder": EVENTS + "/Regata-Ponce_2003"})
    doc = project["pipeline"].__class__(
        project["ai"], repo, FileOrganizer(str(project["folder"])),
        in_place=True).classify_document(str(loose))
    assert doc.file_path == str(loose)
    assert doc.proposed_folder == EVENTS + "/Regata-Ponce_2003"
    assert doc.status == "Classified"
