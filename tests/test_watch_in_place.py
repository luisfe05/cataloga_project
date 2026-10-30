"""Tests for watching an in-place project and applying marked moves."""

import os

from backend import folder_watcher, scanner
from backend.pipeline import folder_tree
# The fixtures come along with the helpers.
from tests.test_folder_watcher import FakeAI, fake_ai  # noqa: F401
from tests.test_scanner import TREE, place_project

MARKED = [{"name": "Prensa", "auto_apply": True},
          {"name": "Documentos", "children": [{"name": "Cartas"}]},
          {"name": "Eventos", "events": True, "auto_apply": True}]


def watched(root, tree=MARKED):
    """A project read in place with some folders marked No asking."""
    root.mkdir(parents=True, exist_ok=True)
    repo = place_project(root)
    # save_tree keeps the project in place mode; save_folder_tree would not.
    repo.save_tree(tree)
    return repo


def test_watcher_reads_new_files_of_an_in_place_project(tmp_path):
    """A file added later is read in place; old ones are not read again."""
    root = tmp_path / "p"
    repo = watched(root, TREE)
    (root / "a.txt").write_text("Article one")
    first = scanner.watch_once(str(root), repo, FakeAI())
    assert [d.original_filename for d in first] == ["a.txt"]
    (root / "sub").mkdir()
    (root / "sub" / "b.txt").write_text("Article two")
    second = scanner.watch_once(str(root), repo, FakeAI())
    assert [d.original_filename for d in second] == ["b.txt"]
    assert len(repo.get_all_documents()) == 2
    assert scanner.watch_once(str(root), repo, FakeAI()) == []


def test_apply_proposal_moves_renames_and_rekeys_the_index(tmp_path):
    """Applying a proposal moves the file, renames it, and keeps the index."""
    root = tmp_path / "p"
    repo = watched(root)
    (root / "loose.txt").write_text("Article")
    doc = scanner.watch_once(str(root), repo, FakeAI())[0]
    # Pretend the AI proposed Prensa with a new name.
    from backend.db.schema import get_connection
    conn = get_connection(repo.db_path)
    conn.execute("UPDATE documents SET proposed_folder = ?, proposed_name = ? "
                 "WHERE id = ?", ("Prensa", "1980_article.txt", doc.id))
    conn.commit()
    conn.close()
    doc = repo.get_document(doc.id)
    assert scanner.auto_apply_place(repo, doc) == "Prensa"
    moved = scanner.apply_proposal(repo, scanner.FileOrganizer(str(root)),
                                   doc)
    assert moved.file_path == str(root / "Prensa" / "1980_article.txt")
    assert moved.folder_path == "Prensa"
    assert moved.proposed_folder is None and moved.proposed_name is None
    assert os.path.isfile(moved.file_path)
    assert not (root / "loose.txt").exists()
    assert repo.index_get(str(root / "loose.txt")) is None
    assert repo.index_get(moved.file_path)["document_id"] == doc.id
    # Watching again reads nothing: the moved file is known.
    assert scanner.watch_once(str(root), repo, FakeAI()) == []


def test_unmarked_folder_only_proposes(tmp_path):
    """Documentos/Cartas is not marked: the file stays with its proposal."""
    root = tmp_path / "p"
    repo = watched(root)
    (root / "carta.txt").write_text("A letter")
    doc = scanner.watch_once(str(root), repo, FakeAI())[0]
    from backend.db.schema import get_connection
    conn = get_connection(repo.db_path)
    conn.execute("UPDATE documents SET proposed_folder = ? WHERE id = ?",
                 ("Documentos/Cartas", doc.id))
    conn.commit()
    conn.close()
    assert scanner.auto_apply_place(repo, repo.get_document(doc.id)) is None
    assert (root / "carta.txt").is_file()


def test_new_event_folder_is_created_when_its_events_folder_is_marked(
        tmp_path):
    """Eventos is marked No asking: a new Event_Year folder is made."""
    root = tmp_path / "p"
    repo = watched(root)
    (root / "regata.txt").write_text("Regata")
    doc = scanner.watch_once(str(root), repo, FakeAI())[0]
    from backend.db.schema import get_connection
    conn = get_connection(repo.db_path)
    conn.execute("UPDATE documents SET proposed_folder = ? WHERE id = ?",
                 ("Eventos/Regata-Ponce_2003", doc.id))
    conn.commit()
    conn.close()
    doc = repo.get_document(doc.id)
    assert scanner.auto_apply_place(repo, doc) == "Eventos/Regata-Ponce_2003"
    moved = scanner.apply_proposal(repo, scanner.FileOrganizer(str(root)),
                                   doc)
    assert os.path.dirname(moved.file_path) == str(
        root / "Eventos" / "Regata-Ponce_2003")
    assert os.path.isfile(moved.file_path)
    assert "Eventos/Regata-Ponce_2003" in folder_tree.all_places(
        repo.get_folder_tree())
    assert moved.folder_path == "Eventos/Regata-Ponce_2003"


def test_catalog_only_never_applies(tmp_path):
    """A Catalog only project is watched but nothing ever moves."""
    root = tmp_path / "p"
    repo = watched(root)
    repo.save_config_value("folder_mode", folder_tree.CATALOG_MODE)
    (root / "a.txt").write_text("Article")
    docs = scanner.watch_once(str(root), repo, FakeAI())
    assert docs[0].file_path == str(root / "a.txt")
    assert docs[0].proposed_folder is None


def test_watcher_skips_while_the_first_scan_runs(tmp_path, monkeypatch):
    """The watcher waits for the scan job instead of reading twice."""
    root = tmp_path / "p"
    watched(root, TREE)
    (root / "a.txt").write_text("Article")
    from backend.config import projects
    projects_path = str(tmp_path / "app" / "projects.json")
    projects.add_project(projects_path, "P", str(root))
    assert folder_watcher.scan_once(projects_path, scan_busy=True) == []
    docs = folder_watcher.scan_once(projects_path, scan_busy=False)
    assert [d.original_filename for d in docs] == ["a.txt"]
