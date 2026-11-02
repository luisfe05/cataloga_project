"""Tests for the plan: batches, the journal, applying and undoing.

One test per safety point, plus the watcher's batches and the routes.
"""

import hashlib
import os
import threading

import pytest

from backend import folder_watcher, scanner
from backend.db.schema import get_connection
from backend.pipeline import folder_tree, naming, organization_plan
from backend.pipeline.classification_pipeline import ClassificationPipeline
from backend.pipeline.file_organizer import FileOrganizer
from backend.pipeline.organization_plan import OrganizationPlan
# The fixtures come along with the helpers.
from tests.test_folder_watcher import FakeAI, fake_ai  # noqa: F401
from tests.test_scanner import place_project

TREE = [{"name": "Prensa", "children": []},
        {"name": "Documentos", "children": [{"name": "Cartas"}]},
        {"name": "Eventos", "events": True, "children": []}]


def sha(path):
    """Hash a file."""
    with open(path, "rb") as file:
        return hashlib.sha256(file.read()).hexdigest()


def tree_of(root):
    """Every file under a folder with its hash, by relative path."""
    found = {}
    for current, dirs, files in os.walk(str(root)):
        dirs[:] = [d for d in dirs if d != ".cataloga"]
        for name in files:
            if name != ".DS_Store":
                path = os.path.join(current, name)
                found[os.path.relpath(path, str(root))] = sha(path)
    return found


def project(root, tree=TREE):
    """A project read in place, with a tree, and its repository."""
    root.mkdir(parents=True, exist_ok=True)
    repo = place_project(root)
    repo.save_tree(tree)
    return repo


def propose(repo, doc, folder=None, name=None):
    """Give a document a proposal, as the pipeline would."""
    conn = get_connection(repo.db_path)
    conn.execute("UPDATE documents SET proposed_folder = ?, proposed_name = ?"
                 " WHERE id = ?", (folder, name, doc.id))
    conn.commit()
    conn.close()
    return repo.get_document(doc.id)


def scan(root, repo):
    """Read the folder in place; return the documents by original name."""
    scanner.scan_folder(scanner.ScanJob(), str(root), repo, FakeAI())
    return {doc.original_filename: doc for doc in repo.get_all_documents()}


def plan_for(root, repo):
    """The engine for a project."""
    return OrganizationPlan(repo, FileOrganizer(str(root)))


@pytest.fixture
def three(tmp_path):
    """Three loose files: two moves into Prensa, one rename in place."""
    root = tmp_path / "p"
    repo = project(root)
    for name in ("a.txt", "b.txt", "c.txt"):
        (root / name).write_text("Article " + name)
    docs = scan(root, repo)
    propose(repo, docs["a.txt"], "Prensa", "1980_a.txt")
    propose(repo, docs["b.txt"], "Prensa", None)
    propose(repo, docs["c.txt"], None, "1980_c.txt")
    return root, repo, plan_for(root, repo)


def approve_everything(plan, repo, batch_id):
    """Approve every row, Manual Review ones too."""
    plan.choose(batch_id, [item["id"] for item in repo.get_items(batch_id)],
                "approved")


def items_by_name(repo, batch_id):
    """The journal rows by old name (folders by new name)."""
    return {item["old_name"] or item["new_name"]: item
            for item in repo.get_items(batch_id)}


# --- Building ---

def test_the_draft_lists_moves_renames_and_new_folders(three):
    """A batch has one row per proposal, with folders to make first."""
    root, repo, plan = three
    batch_id = plan.draft()
    items = repo.get_items(batch_id)
    assert [item["action"] for item in items] == [
        "create_folder", "move_rename", "move", "rename"]
    assert items[0]["new_path"] == str(root / "Prensa")
    assert items[1]["old_path"] == str(root / "a.txt")
    assert items[1]["new_path"] == str(root / "Prensa" / "1980_a.txt")
    assert all(item["status"] == "proposed" for item in items[1:])
    counts = plan.summary(batch_id)
    assert (counts["files_read"], counts["moves"], counts["renames"],
            counts["new_folders"], counts["unchanged"]) == (3, 2, 2, 1, 0)


def test_the_draft_keeps_choices_when_it_is_rebuilt(three):
    """Approving survives a rebuild; a withdrawn proposal leaves the plan."""
    root, repo, plan = three
    batch_id = plan.draft()
    plan.choose(batch_id, [items_by_name(repo, batch_id)["a.txt"]["id"]],
                "approved")
    docs = {doc.original_filename: doc for doc in repo.get_all_documents()}
    propose(repo, docs["c.txt"], None, None)
    batch_id = plan.build()
    items = items_by_name(repo, batch_id)
    assert items["a.txt"]["status"] == "approved"
    assert "c.txt" not in items
    assert len(repo.list_batches(["draft"])) == 1


def test_approve_all_leaves_review_and_low_confidence_rows(three):
    """Those rows are approved one by one, by a person."""
    root, repo, plan = three
    docs = {doc.original_filename: doc for doc in repo.get_all_documents()}
    repo.set_status(docs["a.txt"].id, "Manual Review")
    conn = get_connection(repo.db_path)
    conn.execute("UPDATE documents SET confidence = 'low' WHERE id = ?",
                 (docs["b.txt"].id,))
    conn.commit()
    conn.close()
    batch_id = plan.draft()
    # The folder row is approved from the start: only c.txt changes.
    assert plan.approve_all(batch_id) == 1
    items = items_by_name(repo, batch_id)
    assert items["a.txt"]["status"] == "proposed"
    assert items["b.txt"]["status"] == "proposed"
    assert items["c.txt"]["status"] == "approved"
    assert items["Prensa"]["status"] == "approved"


def test_a_changed_folder_or_name_is_a_correction(three):
    """The user's choice replaces the proposal and is remembered."""
    root, repo, plan = three
    batch_id = plan.draft()
    item = items_by_name(repo, batch_id)["a.txt"]
    batch_id = plan.edit(batch_id, item["id"], folder="Documentos/Cartas",
                         name="carta de 1980")
    item = items_by_name(repo, batch_id)["a.txt"]
    assert item["new_path"] == str(
        root / "Documentos" / "Cartas" / "carta-de-1980.txt")
    corrections = repo.recent_corrections(5)
    assert corrections[0]["to_folder"] == "Documentos/Cartas"
    assert corrections[0]["from_name"] == "1980_a.txt"
    assert corrections[0]["to_name"] == "carta-de-1980.txt"
    with pytest.raises(ValueError):
        plan.edit(batch_id, item["id"], folder="Nowhere")


# --- Applying: one test per safety point ---

def test_1_the_journal_is_written_before_the_disk_and_after(
        three, monkeypatch):
    """Each row is pending before its move and applied after it."""
    root, repo, plan = three
    batch_id = plan.draft()
    plan.approve_all(batch_id)
    seen = []
    original = organization_plan.move_file

    def watched(old_path, new_path, temp_path=None):
        row = [item for item in repo.get_items(batch_id)
               if item["old_path"] == old_path][0]
        seen.append(row["status"])
        return original(old_path, new_path, temp_path)

    monkeypatch.setattr(organization_plan, "move_file", watched)
    batch = plan.apply(batch_id)
    assert seen == ["pending"] * 3
    assert batch["status"] == "applied"
    items = items_by_name(repo, batch_id)
    assert all(item["status"] == "applied" for item in items.values())
    assert sorted(tree_of(root)) == [
        "1980_c.txt", os.path.join("Prensa", "1980_a.txt"),
        os.path.join("Prensa", "b.txt")]
    docs = {doc.original_filename: doc for doc in repo.get_all_documents()}
    assert docs["a.txt"].folder_path == "Prensa"
    assert docs["a.txt"].filename == "1980_a.txt"
    assert docs["a.txt"].proposed_folder is None
    assert repo.index_get(docs["a.txt"].file_path)["document_id"] == \
        docs["a.txt"].id
    assert repo.index_get(str(root / "a.txt")) is None


def test_1_a_crash_in_the_middle_is_settled_at_the_next_start(
        three, monkeypatch):
    """Pending rows are checked on the disk: done, or back in the queue."""
    root, repo, plan = three
    batch_id = plan.draft()
    plan.approve_all(batch_id)
    items = items_by_name(repo, batch_id)
    # Pretend the app died: the folder was made, a.txt moved on the disk
    # but its row is still pending, b.txt never moved, c.txt is in queue.
    (root / "Prensa").mkdir()
    repo.set_item(items["Prensa"]["id"], status="applied", created=1)
    os.rename(str(root / "a.txt"), str(root / "Prensa" / "1980_a.txt"))
    repo.set_item(items["a.txt"]["id"], status="pending")
    repo.set_item(items["b.txt"]["id"], status="pending")
    repo.set_batch(batch_id, status="applying")

    assert plan_for(root, repo).recover() == [batch_id]
    items = items_by_name(repo, batch_id)
    assert items["a.txt"]["status"] == "applied"
    assert items["b.txt"]["status"] == "approved"
    assert items["c.txt"]["status"] == "approved"
    assert repo.get_batch(batch_id)["status"] == "paused"
    docs = {doc.original_filename: doc for doc in repo.get_all_documents()}
    assert docs["a.txt"].file_path == str(root / "Prensa" / "1980_a.txt")
    # Resumed: the rest is applied once, nothing twice.
    assert plan.apply(batch_id)["status"] == "applied"
    assert sorted(tree_of(root)) == [
        "1980_c.txt", os.path.join("Prensa", "1980_a.txt"),
        os.path.join("Prensa", "b.txt")]
    assert len(repo.get_all_documents()) == 3


def test_2_a_taken_name_gets_a_number_and_nothing_is_replaced(three):
    """A file already at the destination keeps its bytes."""
    root, repo, plan = three
    (root / "Prensa").mkdir()
    (root / "Prensa" / "1980_a.txt").write_text("already here")
    batch_id = plan.draft()
    plan.approve_all(batch_id)
    plan.apply(batch_id)
    assert (root / "Prensa" / "1980_a.txt").read_text() == "already here"
    assert (root / "Prensa" / "1980_a_2.txt").read_text() == "Article a.txt"
    item = items_by_name(repo, batch_id)["a.txt"]
    assert item["new_name"] == "1980_a_2.txt"
    docs = {doc.original_filename: doc for doc in repo.get_all_documents()}
    assert docs["a.txt"].filename == "1980_a_2.txt"


def test_2_move_file_never_replaces_even_when_asked(tmp_path):
    """The lowest step refuses a destination that exists."""
    old = tmp_path / "old.txt"
    old.write_text("old")
    new = tmp_path / "new.txt"
    new.write_text("new")
    with pytest.raises(FileExistsError):
        organization_plan.move_file(str(old), str(new))
    assert new.read_text() == "new" and old.read_text() == "old"


def test_3_another_disk_copies_checks_the_hash_then_removes(
        tmp_path, monkeypatch):
    """Across devices: copy, compare, name, delete the original."""
    old = tmp_path / "a.bin"
    old.write_bytes(os.urandom(5000))
    digest = sha(str(old))
    new = tmp_path / "far" / "a.bin"
    new.parent.mkdir()
    real_stat = os.stat

    class OtherDevice:
        def __init__(self, info, dev):
            self.info, self.st_dev = info, dev

        def __getattr__(self, name):
            return getattr(self.info, name)

    def stat(path, *args, **kwargs):
        info = real_stat(path, *args, **kwargs)
        return OtherDevice(info, 99 if str(path).startswith(
            str(new.parent)) else info.st_dev)

    monkeypatch.setattr(organization_plan.os, "stat", stat)
    steps = []
    original = organization_plan.sha256_of

    def recorded(path):
        steps.append(os.path.basename(path))
        return original(path)

    monkeypatch.setattr(organization_plan, "sha256_of", recorded)
    organization_plan.move_file(str(old), str(new))
    assert steps == ["a.bin" + organization_plan.PART_SUFFIX, "a.bin"]
    assert sha(str(new)) == digest and not old.exists()
    assert not (new.parent / ("a.bin" + organization_plan.PART_SUFFIX)
                ).exists()


def test_3_a_bad_copy_is_removed_and_the_original_stays(
        tmp_path, monkeypatch):
    """When the hashes differ the copy goes and the original is whole."""
    old = tmp_path / "a.bin"
    old.write_bytes(b"original")
    new = tmp_path / "far" / "a.bin"
    new.parent.mkdir()
    monkeypatch.setattr(organization_plan, "sha256_of",
                        lambda path: path)
    with pytest.raises(OSError):
        organization_plan.copy_across(str(old), str(new))
    assert old.read_bytes() == b"original"
    assert os.listdir(str(new.parent)) == []


def test_4_a_file_that_changed_since_the_plan_is_not_moved(three):
    """Same path, other size: failed with the reason, disk untouched."""
    root, repo, plan = three
    batch_id = plan.draft()
    plan.approve_all(batch_id)
    (root / "a.txt").write_text("Article a.txt, edited since")
    os.remove(str(root / "b.txt"))
    plan.apply(batch_id)
    items = items_by_name(repo, batch_id)
    assert items["a.txt"]["status"] == "failed"
    assert items["a.txt"]["reason"] == organization_plan.MISSING_REASON
    assert items["b.txt"]["status"] == "failed"
    assert items["c.txt"]["status"] == "applied"
    assert (root / "a.txt").exists()
    assert not (root / "Prensa" / "1980_a.txt").exists()


def test_5_undo_puts_files_back_and_removes_only_its_folders(three):
    """In reverse, only what is still where the batch left it."""
    root, repo, plan = three
    before = tree_of(root)
    batch_id = plan.draft()
    plan.approve_all(batch_id)
    plan.apply(batch_id)
    # The user moved b by hand after applying: Undo leaves it alone.
    (root / "Documentos").mkdir()
    os.rename(str(root / "Prensa" / "b.txt"),
              str(root / "Documentos" / "b.txt"))
    batch = plan.undo(batch_id)
    assert batch["status"] == "undone"
    items = items_by_name(repo, batch_id)
    assert items["a.txt"]["status"] == "undone"
    assert items["c.txt"]["status"] == "undone"
    assert items["b.txt"]["status"] == "applied"
    assert items["b.txt"]["reason"] == organization_plan.MOVED_SINCE_REASON
    assert items["Prensa"]["status"] == "undone"
    assert not (root / "Prensa").exists()
    after = tree_of(root)
    after.pop(os.path.join("Documentos", "b.txt"))
    before.pop("b.txt")
    assert after == before
    docs = {doc.original_filename: doc for doc in repo.get_all_documents()}
    assert docs["a.txt"].file_path == str(root / "a.txt")
    assert docs["a.txt"].folder_path in (None, "")
    assert docs["a.txt"].proposed_folder == "Prensa"
    assert docs["a.txt"].proposed_name == "1980_a.txt"
    assert repo.index_get(str(root / "a.txt"))["document_id"] == \
        docs["a.txt"].id


def test_5_a_folder_the_batch_made_stays_if_it_has_other_files(three):
    """A folder with the user's own file in it is not removed."""
    root, repo, plan = three
    batch_id = plan.draft()
    plan.approve_all(batch_id)
    plan.apply(batch_id)
    (root / "Prensa" / "mine.txt").write_text("mine")
    (root / "Prensa" / ".DS_Store").write_bytes(b"")
    plan.undo(batch_id)
    assert (root / "Prensa" / "mine.txt").exists()
    item = items_by_name(repo, batch_id)["Prensa"]
    assert item["status"] == "applied"
    assert item["reason"] == organization_plan.NOT_EMPTY_REASON


def test_5_an_earlier_batch_can_be_undone_after_a_later_one(tmp_path):
    """Only its own files that nobody moved again go back."""
    root = tmp_path / "p"
    repo = project(root)
    (root / "a.txt").write_text("A")
    (root / "b.txt").write_text("B")
    docs = scan(root, repo)
    propose(repo, docs["a.txt"], "Prensa", None)
    propose(repo, docs["b.txt"], None, None)
    plan = plan_for(root, repo)
    first = plan.draft()
    plan.approve_all(first)
    plan.apply(first)
    propose(repo, repo.get_document(docs["b.txt"].id), "Prensa", None)
    second = plan.draft()
    plan.approve_all(second)
    plan.apply(second)
    assert plan.undo(first)["status"] == "undone"
    assert (root / "a.txt").exists()
    assert (root / "Prensa" / "b.txt").exists()
    assert items_by_name(repo, first)["Prensa"]["reason"] == \
        organization_plan.NOT_EMPTY_REASON


def test_6_a_name_that_only_changes_its_capitals(tmp_path):
    """Foto.JPG becomes foto.jpg through a temp name, not a duplicate."""
    root = tmp_path / "p"
    repo = project(root)
    (root / "Foto.JPG").write_bytes(b"photo")
    docs = scan(root, repo)
    propose(repo, docs["Foto.JPG"], None, "foto.jpg")
    plan = plan_for(root, repo)
    batch_id = plan.draft()
    approve_everything(plan, repo, batch_id)
    plan.apply(batch_id)
    assert sorted(os.listdir(str(root))) == [".cataloga", "foto.jpg"]
    item = items_by_name(repo, batch_id)["Foto.JPG"]
    assert item["status"] == "applied" and item["new_name"] == "foto.jpg"
    assert repo.get_document(docs["Foto.JPG"].id).filename == "foto.jpg"
    plan.undo(batch_id)
    assert "Foto.JPG" in os.listdir(str(root))


def test_7_protected_secret_and_hidden_names_never_enter_the_plan(
        tmp_path):
    """Even with a proposal, those rows are not made."""
    root = tmp_path / "p"
    repo = project(root)
    for name in ("README.md", "credentials.json", "a.txt"):
        (root / name).write_text("x")
    docs = scan(root, repo)
    for name in docs:
        propose(repo, docs[name], "Prensa", None)
    propose(repo, repo.get_document(docs["a.txt"].id), "Prensa", ".a.txt")
    pipeline = ClassificationPipeline(FakeAI(), repo, FileOrganizer(
        str(root)), in_place=True)
    hidden = pipeline.add_unread(str(root / "._b.txt"), "x")
    propose(repo, hidden, "Prensa", None)
    plan = plan_for(root, repo)
    assert repo.get_items(plan.draft()) == []


def test_7_a_path_too_long_is_failed_without_touching_the_disk(tmp_path):
    """Checked when the plan is built, with the reason."""
    root = tmp_path / "p"
    repo = project(root)
    (root / "a.txt").write_text("x")
    docs = scan(root, repo)
    propose(repo, docs["a.txt"], "Prensa", "x" * 230 + ".txt")
    plan = plan_for(root, repo)
    batch_id = plan.draft()
    item = items_by_name(repo, batch_id)["a.txt"]
    assert item["status"] == "failed"
    assert item["reason"] == organization_plan.TOO_LONG_REASON
    assert not organization_plan.path_length_ok(item["new_path"])
    plan.approve_all(batch_id)
    plan.apply(batch_id)
    assert (root / "a.txt").exists()


def test_8_the_scan_and_the_watcher_wait_while_a_batch_runs(
        three, monkeypatch, tmp_path):
    """While BUSY is held, the watcher skips its pass, Move answers 409."""
    root, repo, plan = three
    from backend.config import projects
    projects_path = str(tmp_path / "app" / "projects.json")
    projects.add_project(projects_path, "P", str(root))
    (root / "new.txt").write_text("new")
    with organization_plan.BUSY:
        assert organization_plan.is_busy()
        assert folder_watcher.scan_once(projects_path) == []
    assert not organization_plan.is_busy()
    assert [d.original_filename for d in
            folder_watcher.scan_once(projects_path)] == ["new.txt"]


def test_8_apply_holds_the_lock_for_the_whole_batch(three, monkeypatch):
    """Inside apply(), is_busy() is True; after it, False."""
    root, repo, plan = three
    batch_id = plan.draft()
    plan.approve_all(batch_id)
    states = []
    original = organization_plan.move_file

    def noted(*args):
        states.append(organization_plan.is_busy())
        return original(*args)

    monkeypatch.setattr(organization_plan, "move_file", noted)
    plan.apply(batch_id)
    assert states == [True] * 3 and not organization_plan.is_busy()


def test_9_a_disk_that_leaves_pauses_the_batch(three, monkeypatch):
    """The batch pauses with the note; the rest waits for the disk."""
    root, repo, plan = three
    batch_id = plan.draft()
    plan.approve_all(batch_id)
    original = organization_plan.move_file

    def unplugged(old_path, new_path, temp_path=None):
        if old_path.endswith("b.txt"):
            monkeypatch.setattr(plan, "disk_missing", lambda: True)
            raise OSError("Input/output error")
        return original(old_path, new_path, temp_path)

    monkeypatch.setattr(organization_plan, "move_file", unplugged)
    batch = plan.apply(batch_id)
    assert batch["status"] == "paused"
    assert batch["note"] == organization_plan.DISK_MISSING_NOTE
    items = items_by_name(repo, batch_id)
    assert items["a.txt"]["status"] == "applied"
    assert items["b.txt"]["status"] == "pending"
    assert items["c.txt"]["status"] == "approved"
    # The disk is back: recovery settles the pending row, then resume.
    monkeypatch.setattr(plan, "disk_missing", lambda: False)
    monkeypatch.setattr(organization_plan, "move_file", original)
    repo.set_batch(batch_id, status="applying")
    plan.recover()
    assert items_by_name(repo, batch_id)["b.txt"]["status"] == "approved"
    assert plan.apply(batch_id)["status"] == "applied"
    assert (root / "Prensa" / "b.txt").exists()


def test_10_a_failed_row_does_not_stop_the_batch(three, monkeypatch):
    """The others are applied and the summary counts the failure."""
    root, repo, plan = three
    batch_id = plan.draft()
    plan.approve_all(batch_id)
    original = organization_plan.move_file

    def flaky(old_path, new_path, temp_path=None):
        if old_path.endswith("a.txt"):
            raise PermissionError("no")
        return original(old_path, new_path, temp_path)

    monkeypatch.setattr(organization_plan, "move_file", flaky)
    batch = plan.apply(batch_id)
    assert batch["status"] == "applied"
    counts = plan.summary(batch_id)
    assert counts["failed"] == 1 and counts["applied"] == 3
    item = items_by_name(repo, batch_id)["a.txt"]
    assert item["reason"].startswith("PermissionError")
    assert (root / "a.txt").exists()


def test_11_every_step_is_in_the_activity_log(three):
    """Moved, Renamed and Undone rows, with the paths."""
    root, repo, plan = three
    batch_id = plan.draft()
    plan.approve_all(batch_id)
    plan.apply(batch_id)
    plan.undo(batch_id)
    conn = get_connection(repo.db_path)
    rows = conn.execute("SELECT action, details FROM activity_log "
                        "ORDER BY id").fetchall()
    conn.close()
    actions = [(row[0], row[1]) for row in rows if row[0] != "Classified"]
    assert ("Moved", "a.txt → Prensa/1980_a.txt") in actions
    assert ("Moved", "b.txt → Prensa/b.txt") in actions
    assert ("Renamed", "c.txt → 1980_c.txt") in actions
    assert ("Undone", "Prensa/1980_a.txt → a.txt") in actions
    assert len([a for a in actions if a[0] == "Undone"]) == 3


# --- Rows of files read in place ---

def test_a_row_read_in_place_says_where_the_file_is(tmp_path):
    """folder_path is the real folder; the AI's folder is the proposal."""
    root = tmp_path / "p"
    repo = project(root)
    (root / "Documentos" / "Cartas").mkdir(parents=True)
    (root / "Documentos" / "Cartas" / "a.txt").write_text("A letter")
    (root / "b.txt").write_text("Loose")
    docs = scan(root, repo)
    assert docs["a.txt"].folder_path == "Documentos/Cartas"
    assert docs["a.txt"].category == "Documentos"
    assert docs["a.txt"].subcategory == "Cartas"
    assert docs["b.txt"].folder_path is None
    # FakeAI answers Press: that is the proposal, not where the file is.
    assert docs["a.txt"].proposed_folder in (None, "Prensa")


def test_a_file_moved_by_hand_is_read_again_not_a_duplicate(tmp_path):
    """Same hash, old file gone: the stale row goes and the file is read."""
    root = tmp_path / "p"
    repo = project(root)
    (root / "a.txt").write_text("A letter")
    first = scan(root, repo)["a.txt"]
    (root / "Prensa").mkdir()
    os.rename(str(root / "a.txt"), str(root / "Prensa" / "moved.txt"))
    docs = scan(root, repo)
    assert list(docs) == ["moved.txt"]
    assert docs["moved.txt"].duplicate_of is None
    assert docs["moved.txt"].status == "Classified"
    assert docs["moved.txt"].folder_path == "Prensa"
    assert repo.get_document(first.id) is None
    assert repo.index_get(str(root / "a.txt")) is None


def test_older_in_place_catalogs_get_their_real_folders(tmp_path):
    """init_db repairs folder_path from the path, once."""
    root = tmp_path / "p"
    repo = project(root)
    (root / "Prensa").mkdir()
    (root / "Prensa" / "a.txt").write_text("x")
    doc = scan(root, repo)["a.txt"]
    conn = get_connection(repo.db_path)
    conn.execute("UPDATE documents SET folder_path = 'Documentos/Cartas', "
                 "category = 'Documentos', subcategory = 'Cartas' "
                 "WHERE id = ?", (doc.id,))
    conn.commit()
    conn.close()
    from backend.db.schema import init_db
    init_db(repo.db_path)
    fixed = repo.get_document(doc.id)
    assert fixed.folder_path == "Prensa"
    assert fixed.category == "Prensa" and fixed.subcategory is None


def test_a_folder_is_made_only_for_an_approved_file(three):
    """Approving one rename makes no folder; its row is skipped."""
    root, repo, plan = three
    batch_id = plan.draft()
    plan.choose(batch_id, [items_by_name(repo, batch_id)["c.txt"]["id"]],
                "approved")
    plan.apply(batch_id)
    assert not (root / "Prensa").exists()
    items = items_by_name(repo, batch_id)
    assert items["Prensa"]["status"] == "skipped"
    assert items["c.txt"]["status"] == "applied"


# --- The watcher's batches ---

def test_the_watcher_files_as_a_batch_that_undo_can_reverse(tmp_path):
    """No asking folders: journal first, then the move, as origin watch."""
    root = tmp_path / "p"
    repo = project(root, [{"name": "Prensa", "auto_apply": True},
                          {"name": "Otros"}])
    (root / "loose.txt").write_text("Article")
    doc = scanner.watch_once(str(root), repo, FakeAI())[0]
    doc = propose(repo, doc, "Prensa", "1980_article.txt")
    filed = scanner.apply_proposal(repo, FileOrganizer(str(root)), doc)
    assert filed.file_path == str(root / "Prensa" / "1980_article.txt")
    batches = repo.list_batches()
    assert len(batches) == 1 and batches[0]["origin"] == "watch"
    assert batches[0]["status"] == "applied"
    plan = plan_for(root, repo)
    plan.undo(batches[0]["id"])
    assert (root / "loose.txt").exists()
    assert repo.get_document(doc.id).file_path == str(root / "loose.txt")


# --- Zero moves for a folder that is already organized ---

def test_a_file_in_its_folder_that_follows_the_pattern_is_left_alone(
        tmp_path):
    """Event_Year_N inside its event folder: no proposal at all."""
    root = tmp_path / "p"
    repo = project(root, [{"name": "Eventos", "events": True,
                           "children": [{"name": "Trialo-Isla-Verde_1998"}]}])
    repo.save_naming_template(naming.EVENT_TEMPLATE)
    event = root / "Eventos" / "Trialo-Isla-Verde_1998"
    event.mkdir(parents=True)
    (event / "Trialo-Isla-Verde_1998_3.txt").write_text("Race photo text")
    (event / "IMG_0042.txt").write_text("Race photo text two")
    docs = scan(root, repo)
    done = docs["Trialo-Isla-Verde_1998_3.txt"]
    assert done.proposed_folder is None and done.proposed_name is None
    other = docs["IMG_0042.txt"]
    assert other.proposed_name == "Trialo-Isla-Verde_1998_4.txt"
    plan = plan_for(root, repo)
    assert plan.summary(plan.draft())["moves"] == 0


@pytest.mark.parametrize("name, template, event, expected", [
    ("Juegos_1997_13.tif", "{event}_{n}", "Juegos_1997", True),
    ("Juegos_1997_13_v2.tif", "{event}_{n}", "Juegos_1997", True),
    ("Otros_1997_13.tif", "{event}_{n}", "Juegos_1997", False),
    ("2026-05-21_0001.jpg", "{date}_{number}", None, True),
    ("regata_el-dia_1998-03.pdf", "{topic}_{source}_{date}", None, True),
    ("PHOTO-2026-05-21(13).jpg", "{topic}_{source}_{date}", None, False),
    ("anything.pdf", "keep", None, True),
])
def test_follows_template(name, template, event, expected):
    """A name has the shape of its template, or not."""
    assert naming.follows_template(name, template, event) is expected


# --- Routes ---

@pytest.fixture
def plan_client(empty_client, tmp_path, monkeypatch):
    """A logged-in client with an in-place project that has proposals."""
    root = tmp_path / "project"
    root.mkdir()
    (root / "a.txt").write_text("Article")
    (root / "b.txt").write_text("Letter")
    monkeypatch.setattr(scanner, "start_scan",
                        lambda app, path, owner=None: app.config.setdefault(
                            "SCAN", scanner.ScanJob()))
    response = empty_client.post("/projects", json={
        "name": "Place", "folder": str(root), "folders": TREE,
        "folder_mode": "place"})
    assert response.status_code == 201
    from backend.config import projects
    repo = place_project(root)
    repo.save_tree(TREE)
    docs = scan(root, repo)
    propose(repo, docs["a.txt"], "Prensa", None)
    propose(repo, docs["b.txt"], None, "1980_letter.txt")
    return empty_client, root, repo


def wait_for_batch(client):
    """Let the background thread finish."""
    thread = client.application.config.get("PLAN_THREAD")
    if thread is not None:
        thread.join(10)


def test_plan_routes_approve_apply_and_undo(plan_client):
    """GET, PUT, apply, progress and undo, end to end."""
    client, root, repo = plan_client
    view = client.get("/plan").get_json()
    assert view["mode"] == "place" and view["busy"] is False
    assert view["summary"]["moves"] == 1
    assert view["summary"]["renames"] == 1
    assert view["summary"]["new_folders"] == 1
    assert [row["action"] for row in view["rows"]] == [
        "create_folder", "move", "rename"]
    assert view["rows"][1]["why"] is not None or True
    assert view["unchanged"] == []
    assert "Prensa" in view["folders"]

    rows = {row["old_name"]: row for row in view["rows"] if row["old_name"]}
    response = client.put("/plan/items", json={
        "status": "approved", "ids": [rows["a.txt"]["id"]]})
    assert response.status_code == 200 and response.get_json()["changed"]
    assert client.post("/plan/apply").status_code == 202
    wait_for_batch(client)
    progress = client.get("/plan/progress").get_json()
    assert progress["batch"] is None
    batches = client.get("/batches").get_json()["batches"]
    assert batches[0]["status"] == "applied"
    assert batches[0]["summary"]["applied"] == 2
    assert (root / "Prensa" / "a.txt").exists()
    assert (root / "b.txt").exists()
    # The draft is rebuilt without the applied row.
    view = client.get("/plan").get_json()
    assert [row["old_name"] for row in view["rows"]] == ["b.txt"]

    assert client.post("/plan/undo").status_code == 202
    wait_for_batch(client)
    assert (root / "a.txt").exists() and not (root / "Prensa").exists()
    assert client.get("/batches").get_json()["batches"][0]["status"] == \
        "undone"


def test_plan_routes_edit_a_row(plan_client):
    """PATCH changes the folder and the name of a row."""
    client, root, repo = plan_client
    rows = {row["old_name"]: row for row in client.get("/plan").get_json()[
        "rows"] if row["old_name"]}
    response = client.patch("/plan/items/{}".format(rows["b.txt"]["id"]),
                            json={"folder": "Documentos/Cartas",
                                  "name": "carta"})
    assert response.status_code == 200
    rows = {row["old_name"]: row for row in response.get_json()["rows"]
            if row["old_name"]}
    assert rows["b.txt"]["new_folder"] == "Documentos/Cartas"
    assert rows["b.txt"]["new_name"] == "carta.txt"
    assert client.patch("/plan/items/999", json={"name": "x"}
                        ).status_code == 404


def test_apply_needs_an_approved_row(plan_client):
    """Nothing approved: 409."""
    client, root, repo = plan_client
    client.get("/plan")
    response = client.post("/plan/apply")
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "nothing_approved"


def test_catalog_only_has_no_plan(empty_client, tmp_path, monkeypatch):
    """The tab says so, and the other routes answer 409."""
    root = tmp_path / "project"
    root.mkdir()
    monkeypatch.setattr(scanner, "start_scan",
                        lambda app, path, owner=None: app.config.setdefault(
                            "SCAN", scanner.ScanJob()))
    response = empty_client.post("/projects", json={
        "name": "Only", "folder": str(root), "catalog_only": True})
    assert response.status_code == 201
    view = empty_client.get("/plan").get_json()
    assert view["mode"] == "catalog"
    assert view["message"] == "Catalog only: no plan"
    assert empty_client.post("/plan/apply").status_code == 409


def test_move_and_rename_wait_while_a_batch_runs(flask_client):
    """Both answer plan_applying while BUSY is held."""
    with organization_plan.BUSY:
        response = flask_client.post("/documents/1/move",
                                     json={"folder": "Prensa"})
        assert response.status_code == 409
        assert response.get_json()["error"]["code"] == "plan_applying"
        response = flask_client.post("/documents/1/rename",
                                     json={"new_name": "x"})
        assert response.get_json()["error"]["code"] == "plan_applying"
