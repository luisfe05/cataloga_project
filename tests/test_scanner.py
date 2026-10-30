"""Tests for reading a project folder in place: the scanner and its routes."""

import os
import threading
import time

import pytest

from backend import scanner
from backend.config import projects
from backend.db.catalog_repository import CatalogRepository
from backend.db.schema import init_db
from backend.pipeline import folder_tree
from backend.pipeline.ai_providers import base
# The fixtures come along with the helpers.
from tests.test_folder_watcher import FakeAI, fake_ai  # noqa: F401

TREE = [{"name": "Prensa", "subcategories": []},
        {"name": "Documentos", "subcategories": ["Cartas"]}]


def make_folder(root):
    """Files at three levels, hidden things, and a tool folder."""
    (root / "Cartas" / "1997").mkdir(parents=True)
    (root / ".git").mkdir()
    (root / "node_modules" / "x").mkdir(parents=True)
    (root / "a.txt").write_text("Article about a swim meet")
    (root / "Cartas" / "b.txt").write_text("A letter")
    (root / "Cartas" / "1997" / "c.txt").write_text("Another letter")
    (root / ".DS_Store").write_bytes(b"")
    (root / "d.txt.download").write_text("x")
    (root / ".git" / "config").write_text("x")
    (root / "node_modules" / "x" / "index.js").write_text("x")
    return root


def place_project(root):
    """Make a folder a project read in place and return its repository."""
    db_path = projects.catalog_path(str(root))
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    init_db(db_path)
    repo = CatalogRepository(db_path)
    repo.save_app_config("Place", str(root))
    repo.save_folder_tree("Research", TREE)
    repo.save_config_value("folder_mode", folder_tree.PLACE_MODE)
    repo.set_active_provider("ollama", "gemma4:31b")
    return repo


def run_scan(root, repo):
    """Scan a folder in this thread and return the job."""
    job = scanner.ScanJob()
    scanner.scan_folder(job, str(root), repo, FakeAI(), owner="luis")
    return job


# --- Finding files ---

def test_find_files_walks_subfolders_and_skips_the_rest(tmp_path):
    """Three levels are read; hidden, temporary and tool files are not."""
    root = make_folder(tmp_path / "p")
    found = [os.path.relpath(f, str(root)) for f in scanner.find_files(root)]
    assert found == ["a.txt", os.path.join("Cartas", "b.txt"),
                     os.path.join("Cartas", "1997", "c.txt")]


def test_find_files_never_follows_links(tmp_path):
    """A link to a folder or a file outside the project is ignored."""
    root = tmp_path / "p"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("x")
    os.symlink(str(outside), str(root / "link"))
    os.symlink(str(outside / "secret.txt"), str(root / "secret.txt"))
    (root / "own.txt").write_text("x")
    assert [os.path.basename(f) for f in scanner.find_files(root)] == \
        ["own.txt"]


# --- Reading in place ---

def test_scan_catalogs_in_place_without_moving(tmp_path):
    """Every file gets a row where it is; the folder does not change."""
    root = make_folder(tmp_path / "p")
    repo = place_project(root)
    before = sorted(scanner.find_files(root))
    job = run_scan(root, repo)
    assert job.status == "done"
    assert (job.done, job.total) == (3, 3)
    assert sorted(scanner.find_files(root)) == before
    docs = repo.get_all_documents()
    assert sorted(doc.original_filename for doc in docs) == \
        ["a.txt", "b.txt", "c.txt"]
    for doc in docs:
        assert doc.file_path.startswith(str(root))
        assert doc.filename == doc.original_filename
        assert doc.summary == "A summary."
        assert doc.status == "Classified"
    assert repo.index_count() == 3


def test_scan_keeps_proposals_for_the_plan(tmp_path):
    """What the pipeline would do is saved: the folder and the name."""
    root = make_folder(tmp_path / "p")
    repo = place_project(root)
    run_scan(root, repo)
    doc = [d for d in repo.get_all_documents()
           if d.original_filename == "a.txt"][0]
    # The fake AI puts everything in Press with no folder: Drop-Zone-like.
    assert doc.proposed_name is not None
    assert doc.proposed_name != "a.txt"
    assert doc.proposed_name.endswith(".txt")
    letter = [d for d in repo.get_all_documents()
              if d.original_filename == "c.txt"][0]
    assert letter.proposed_folder is None or "/" in letter.proposed_folder \
        or letter.proposed_folder == ""


def test_second_scan_reads_only_changed_files(tmp_path):
    """Same size and date: not read again. A changed file is read anew."""
    root = make_folder(tmp_path / "p")
    repo = place_project(root)
    run_scan(root, repo)
    first_ids = {d.original_filename: d.id for d in repo.get_all_documents()}
    (root / "Cartas" / "b.txt").write_text("A letter, now longer than it was")
    (root / "new.txt").write_text("New file")
    job = run_scan(root, repo)
    assert job.total == 4
    docs = {d.original_filename: d for d in repo.get_all_documents()}
    assert docs["a.txt"].id == first_ids["a.txt"]
    assert docs["b.txt"].id != first_ids["b.txt"]
    assert "new.txt" in docs
    assert len(docs) == 4


def test_scan_pauses_and_resumes(tmp_path):
    """Pause holds the thread before its next file; resume lets it go."""
    root = tmp_path / "p"
    root.mkdir()
    for i in range(6):
        (root / "f{}.txt".format(i)).write_text("text " + str(i))
    repo = place_project(root)
    job = scanner.ScanJob()
    job.resume_event.clear()
    job.status = "paused"
    thread = threading.Thread(target=scanner.scan_folder,
                              args=(job, str(root), repo, FakeAI()),
                              daemon=True)
    thread.start()
    time.sleep(0.2)
    assert job.done == 0
    job.resume()
    thread.join(timeout=10)
    assert job.status == "done"
    assert job.done == 6


def test_scan_stops_when_asked(tmp_path):
    """Stop ends the scan after the current file."""
    root = tmp_path / "p"
    root.mkdir()
    (root / "f.txt").write_text("text")
    repo = place_project(root)
    job = scanner.ScanJob()
    job.stop()
    scanner.scan_folder(job, str(root), repo, FakeAI())
    assert job.status == "stopped"
    assert job.done == 0


def test_bad_file_never_stops_the_scan(tmp_path, monkeypatch):
    """A file the pipeline cannot read is skipped and the rest go on."""
    root = tmp_path / "p"
    root.mkdir()
    (root / "a.txt").write_text("a")
    (root / "b.txt").write_text("b")
    repo = place_project(root)
    from backend.pipeline import classification_pipeline

    original = classification_pipeline.ClassificationPipeline.classify_document

    def explode(self, path):
        if path.endswith("a.txt"):
            raise RuntimeError("boom")
        return original(self, path)
    monkeypatch.setattr(classification_pipeline.ClassificationPipeline,
                        "classify_document", explode)
    job = run_scan(root, repo)
    assert job.status == "done"
    assert [d.original_filename for d in repo.get_all_documents()] == \
        ["b.txt"]


# --- Routes and project creation ---

def test_new_place_project_creates_nothing_and_starts_reading(
        empty_client, tmp_path, monkeypatch):
    """No Drop Zone, no tree folders: the files stay, the scan starts."""
    root = make_folder(tmp_path / "p")
    before = sorted(os.listdir(str(root)))
    started = []
    monkeypatch.setattr(scanner, "start_scan",
                        lambda app, path, owner=None: started.append(path))
    response = empty_client.post("/projects", json={
        "name": "Place", "folder": str(root), "folders": TREE,
        "folder_mode": "place", "description": "Research"})
    assert response.status_code == 201
    assert sorted(os.listdir(str(root))) == sorted(before + [".cataloga"])
    assert len(started) == 1
    settings = empty_client.get("/settings").get_json()
    assert settings["folder_mode"] == "place"
    assert settings["categories"] == TREE


def test_scan_routes(empty_client, tmp_path, monkeypatch):
    """GET /scan reports the job; start refuses Drop Zone projects."""
    assert empty_client.get("/scan").get_json()["status"] == "idle"
    root = make_folder(tmp_path / "p")
    monkeypatch.setattr(scanner, "start_scan",
                        lambda app, path, owner=None: app.config.setdefault(
                            "SCAN", scanner.ScanJob()))
    empty_client.post("/projects", json={
        "name": "Place", "folder": str(root), "folders": TREE,
        "folder_mode": "place"})
    response = empty_client.post("/scan/start")
    assert response.status_code == 202
    job = empty_client.application.config["SCAN"]
    job.status = "running"
    assert empty_client.post("/scan/pause").get_json()["status"] == "paused"
    assert empty_client.post("/scan/resume").get_json()["status"] == \
        "running"


def test_drop_zone_project_cannot_be_scanned(flask_client):
    """A classic project has a Drop Zone; scanning it makes no sense."""
    response = flask_client.post("/scan/start")
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "has_drop_zone"
