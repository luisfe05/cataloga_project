"""Tests: one row per path, copied project folders, and no surprise folders."""

import os
import shutil
import sqlite3

import pytest

from backend import folder_watcher, scanner
from backend.config import projects
from backend.config.terms import TERMS_VERSION
from backend.db.catalog_repository import CatalogRepository
from backend.db.schema import get_connection, init_db
from backend.models.document import Document
# The fixtures come along with the helpers.
from tests.test_folder_watcher import FakeAI, fake_ai  # noqa: F401
from tests.test_scanner import place_project


def scanned(root):
    """A project with three files, read."""
    root.mkdir(parents=True, exist_ok=True)
    for name in ("a.txt", "b.txt", "c.txt"):
        (root / name).write_text("Letter " + name)
    repo = place_project(root)
    scanner.scan_folder(scanner.ScanJob(), str(root), repo, FakeAI())
    return repo


def rows_of(db_path):
    """Every row of a catalog, by path."""
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT file_path, id, duplicate_of, status "
                        "FROM documents").fetchall()
    conn.close()
    return rows


def insert_raw(db_path, path, note=None, duplicate_of=None):
    """Put a row in as an old catalog could have it, past the rule."""
    conn = sqlite3.connect(db_path)
    cursor = conn.execute(
        "INSERT INTO documents (original_filename, filename, media_type, "
        "file_path, date_added, status, review_note, duplicate_of) "
        "VALUES ('x', 'x', 'Documents', ?, 'now', 'Manual Review', ?, ?)",
        (path, note, duplicate_of))
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return row_id


def drop_rule(db_path):
    """A catalog from before the rule."""
    conn = sqlite3.connect(db_path)
    conn.execute("DROP INDEX IF EXISTS one_row_per_path")
    conn.commit()
    conn.close()


# --- The rule ---

def test_the_database_refuses_a_second_row_for_a_path(tmp_path):
    """The rule lives in the catalog, not only in the code."""
    repo = scanned(tmp_path / "p")
    path = repo.get_all_documents()[0].file_path
    with pytest.raises(sqlite3.IntegrityError):
        repo.add_document(Document("x", "x", "Documents", path, "now"))


def test_a_lost_index_entry_does_not_make_a_second_row(tmp_path):
    """The row is found by its path and kept, with no AI call."""
    root = tmp_path / "p"
    repo = scanned(root)
    before = {doc.file_path: doc.id for doc in repo.get_all_documents()}
    conn = get_connection(repo.db_path)
    conn.execute("DELETE FROM scan_index")
    conn.commit()
    conn.close()

    class NoCalls(FakeAI):
        def send_prompt(self, system_prompt, text):
            raise AssertionError("the file was read again")

    scanner.scan_folder(scanner.ScanJob(), str(root), repo, NoCalls())
    assert {doc.file_path: doc.id
            for doc in repo.get_all_documents()} == before
    assert repo.index_count() == 3


def test_a_new_date_on_the_same_content_keeps_the_row(tmp_path):
    """Copies change dates; edits must survive that."""
    root = tmp_path / "p"
    repo = scanned(root)
    doc = repo.get_all_documents()[0]
    repo.update_document(doc.id, {"summary": "Written by hand."})
    os.utime(doc.file_path, (1000000, 1000000))
    scanner.scan_folder(scanner.ScanJob(), str(root), repo, FakeAI())
    assert repo.get_document(doc.id).summary == "Written by hand."
    assert len(repo.get_all_documents()) == 3


def test_changed_content_replaces_the_row(tmp_path):
    """Still one row, with what the file says now."""
    root = tmp_path / "p"
    repo = scanned(root)
    (root / "a.txt").write_text("Something much longer than it was before")
    scanner.scan_folder(scanner.ScanJob(), str(root), repo, FakeAI())
    paths = [doc.file_path for doc in repo.get_all_documents()]
    assert len(paths) == 3 and len(set(paths)) == 3


# --- Cleaning at open ---

def test_opening_keeps_the_edited_row_of_a_repeated_path(tmp_path):
    """Edits win, even over a newer row."""
    repo = scanned(tmp_path / "p")
    doc = repo.get_all_documents()[0]
    repo.update_document(doc.id, {"summary": "Written by hand."})
    drop_rule(repo.db_path)
    insert_raw(repo.db_path, doc.file_path)
    init_db(repo.db_path)
    rows = [row for row in rows_of(repo.db_path)
            if row[0] == doc.file_path]
    assert [row[1] for row in rows] == [doc.id]
    assert repo.get_document(doc.id).summary == "Written by hand."


def test_opening_keeps_the_newest_row_with_no_edits(tmp_path):
    """No edits anywhere: the newest stays, and the index follows it."""
    repo = scanned(tmp_path / "p")
    doc = repo.get_all_documents()[0]
    drop_rule(repo.db_path)
    newest = insert_raw(repo.db_path, doc.file_path, note="newer")
    init_db(repo.db_path)
    rows = [row for row in rows_of(repo.db_path)
            if row[0] == doc.file_path]
    assert [row[1] for row in rows] == [newest]
    assert repo.index_get(doc.file_path)["document_id"] == newest


def test_a_row_that_is_a_duplicate_of_its_own_copy_never_wins(tmp_path):
    """Newest, but it only says Duplicate of: the real row stays."""
    repo = scanned(tmp_path / "p")
    doc = repo.get_all_documents()[0]
    drop_rule(repo.db_path)
    insert_raw(repo.db_path, doc.file_path, duplicate_of="a.txt")
    init_db(repo.db_path)
    rows = [row for row in rows_of(repo.db_path)
            if row[0] == doc.file_path]
    assert [row[1] for row in rows] == [doc.id]


def test_opening_twice_changes_nothing(tmp_path):
    """The repair runs on every open."""
    repo = scanned(tmp_path / "p")
    before = rows_of(repo.db_path)
    init_db(repo.db_path)
    init_db(repo.db_path)
    assert rows_of(repo.db_path) == before


# --- A project folder that was copied ---

def test_a_copied_folder_keeps_its_catalog_and_reads_nothing(tmp_path):
    """The case found in real use: every file came back as a duplicate."""
    first = tmp_path / "Desktop" / "copy"
    repo = scanned(first)
    second = tmp_path / "Disk" / "copy 2"
    second.parent.mkdir()
    shutil.copytree(str(first), str(second))
    db_path = projects.catalog_path(str(second))
    init_db(db_path)
    copied = CatalogRepository(db_path)
    assert all(doc.file_path.startswith(str(second.resolve()))
               for doc in copied.get_all_documents())
    assert copied.get_app_config()["target_directory"] == \
        str(second.resolve())

    class NoCalls(FakeAI):
        def send_prompt(self, system_prompt, text):
            raise AssertionError("the file was read again")

    scanner.scan_folder(scanner.ScanJob(), str(second), copied, NoCalls())
    assert len(copied.get_all_documents()) == 3
    # The first folder and its catalog do not change.
    assert all(doc.file_path.startswith(str(first.resolve()))
               for doc in repo.get_all_documents())


def test_a_catalog_already_doubled_by_a_copy_is_repaired(tmp_path):
    """161 + 161 rows of the real case: back to one row per file."""
    first = tmp_path / "Desktop" / "copy"
    scanned(first)
    second = tmp_path / "Disk" / "copy 2"
    second.parent.mkdir()
    shutil.copytree(str(first), str(second))
    db_path = projects.catalog_path(str(second))
    drop_rule(db_path)
    for name in ("a.txt", "b.txt", "c.txt"):
        insert_raw(db_path, str(second.resolve() / name),
                   note="Duplicate of " + name, duplicate_of=name)
    assert len(rows_of(db_path)) == 6
    init_db(db_path)
    rows = rows_of(db_path)
    assert len(rows) == 3
    assert all(row[2] is None and row[3] == "Classified" for row in rows)
    assert all(row[0].startswith(str(second.resolve())) for row in rows)
    assert CatalogRepository(db_path).index_count() == 3


# --- No folder appears unless the user asked ---

def folders_in(root):
    """Every folder under a project, but the catalog's own."""
    found = set()
    for current, dirs, files in os.walk(str(root)):
        dirs[:] = [d for d in dirs if d != ".cataloga"]
        found.update(os.path.join(current, d) for d in dirs)
    return found


@pytest.mark.parametrize("tree_name", ["Prensa", "Footage"])
def test_no_folder_on_open_on_switch_or_on_start(
        empty_client, tmp_path, data_folder, tree_name):
    """Open in another account, switch back and forth, start the app."""
    from backend.app import create_app
    root = tmp_path / "project"
    other = tmp_path / "other"
    for folder in (root, other):
        repo = scanned(folder)
        repo.save_tree([{"name": tree_name, "children": [{"name": "Sub"}]},
                        {"name": "Vacia"}])
    before = folders_in(root), folders_in(other)

    # Opening a folder that has a catalog (a second account does this).
    response = empty_client.post("/projects", json={"name": "A",
                                                    "folder": str(root)})
    assert response.get_json()["opened_existing"] is True
    empty_client.post("/projects", json={"name": "B", "folder": str(other)})
    # Switching projects, and the screens each one loads.
    for folder in (root, other, root):
        empty_client.put("/projects/active", json={"folder": str(folder)})
        for path in ("/settings", "/documents", "/scan", "/plan", "/batches",
                     "/dashboard/stats"):
            empty_client.get(path)
    # The watcher's pass.
    username = empty_client.application.config["SESSION_USER"]
    projects_path = empty_client.application.config[
        "ACCOUNTS"].projects_path(username)
    folder_watcher.scan_once(projects_path)
    # A new start of the app, and a log in with another account.
    create_app(data_folder=data_folder,
               old_db_path=str(tmp_path / "no_old.db"))
    empty_client.post("/auth/logout")
    empty_client.post("/auth/register", json={
        "username": "otra-cuenta", "password": "password-1234",
        "accepted_terms": TERMS_VERSION})
    assert (folders_in(root), folders_in(other)) == before


def test_saving_settings_makes_no_folder_in_a_project_read_in_place(
        empty_client, tmp_path):
    """Save used to make the whole tree and a Drop Zone."""
    root = tmp_path / "project"
    repo = scanned(root)
    repo.save_tree([{"name": "Prensa"}])
    empty_client.post("/projects", json={"name": "A", "folder": str(root)})
    before = folders_in(root)
    response = empty_client.put("/settings", json={
        "research_name": "A", "target_directory": str(root)})
    assert response.status_code == 200
    assert folders_in(root) == before
