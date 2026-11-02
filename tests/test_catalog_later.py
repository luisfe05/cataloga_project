"""Tests for listing a new folder and cataloging it now or later."""

import os

from backend import scanner
from backend.config import projects
from backend.db.catalog_repository import CatalogRepository
from backend.pipeline.ai_providers import base
from tests.test_folder_watcher import FakeAI, fake_ai  # noqa: F401


def a_folder(root):
    """Two files in two levels, and things that do not count."""
    (root / "Fotos" / "1997").mkdir(parents=True)
    (root / ".git").mkdir()
    (root / "a.txt").write_text("12345")
    (root / "Fotos" / "1997" / "b.txt").write_text("123")
    (root / ".DS_Store").write_text("x")
    return root


def everything_in(root):
    """Every path under a folder."""
    found = set()
    for current, dirs, files in os.walk(str(root)):
        found.update(os.path.join(current, name) for name in dirs + files)
    return found


def test_listing_a_folder_counts_and_writes_nothing(empty_client, tmp_path):
    """No AI, no catalog: the folder stays exactly as it was."""
    root = a_folder(tmp_path / "p")
    before = everything_in(root)
    answer = empty_client.post("/projects/folders/list",
                               json={"folder": str(root)}).get_json()
    assert answer == {"files": 2, "folders": 2, "size": 8,
                      "has_catalog": False}
    assert everything_in(root) == before


def test_listing_refuses_what_is_not_a_folder(empty_client, tmp_path):
    """The form shows its usual message."""
    response = empty_client.post("/projects/folders/list",
                                 json={"folder": str(tmp_path / "no")})
    assert response.status_code == 400


def later(client, root, **extra):
    """Make a project with Later, as the question does."""
    return client.post("/projects", json=dict(
        {"name": "Nuevo", "folder": str(root), "defer_scan": True,
         "folders": []}, **extra))


def test_later_reads_nothing_and_makes_no_folder(empty_client, tmp_path,
                                                 monkeypatch):
    """Only .cataloga appears; Home says the folder is not cataloged."""
    root = a_folder(tmp_path / "p")
    calls = []
    monkeypatch.setattr(scanner, "start_scan",
                        lambda *args, **kwargs: calls.append(args))
    before = everything_in(root)
    assert later(empty_client, root).status_code == 201
    assert calls == []
    extra = {path for path in everything_in(root) - before
             if ".cataloga" not in path}
    assert extra == set()
    state = empty_client.get("/scan").get_json()
    assert (state["status"], state["total"]) == ("unread", 2)
    listed = empty_client.get("/browse").get_json()
    assert listed["totals"]["files"] == 2
    assert listed["totals"]["cataloged"] == 0


def test_the_watcher_does_not_read_a_folder_left_for_later(
        empty_client, tmp_path):
    """Nothing is read or sent until Catalog now."""
    from backend import folder_watcher
    root = a_folder(tmp_path / "p")
    later(empty_client, root)
    app = empty_client.application
    assert folder_watcher.scan_for_session(app) == []
    repo = CatalogRepository(projects.catalog_path(str(root)))
    assert repo.get_all_documents() == []


def test_catalog_now_asks_the_ai_for_folders_when_there_are_none(tmp_path):
    """A project made with Later gets its tree, once, before reading."""
    root = a_folder(tmp_path / "p")
    (root / ".cataloga").mkdir()
    from backend.db.schema import init_db
    db_path = projects.catalog_path(str(root))
    init_db(db_path)
    repo = CatalogRepository(db_path)
    repo.save_app_config("Nuevo", str(root))
    repo.save_config_value("folder_mode", "place")

    class Folders(FakeAI):
        asked = 0

        def send_folders_request(self, description, hints=""):
            Folders.asked += 1
            assert "a.txt" in description
            return '[{"name": "Prensa", "subfolders": ["Recortes"]}]'

    scanner.scan_folder(scanner.ScanJob(), str(root), repo, Folders())
    assert [node["name"] for node in repo.get_folder_tree()] == ["Prensa"]
    assert Folders.asked == 1
    assert len(repo.get_all_documents()) == 2
    scanner.scan_folder(scanner.ScanJob(), str(root), repo, Folders())
    assert Folders.asked == 1


def test_a_bad_answer_about_folders_does_not_stop_the_reading(tmp_path):
    """No tree: the files are still cataloged."""
    root = a_folder(tmp_path / "p")
    (root / ".cataloga").mkdir()
    from backend.db.schema import init_db
    db_path = projects.catalog_path(str(root))
    init_db(db_path)
    repo = CatalogRepository(db_path)
    repo.save_app_config("Nuevo", str(root))
    repo.save_config_value("folder_mode", "place")
    job = scanner.ScanJob()
    scanner.scan_folder(job, str(root), repo, FakeAI())
    assert job.status == "done" and len(repo.get_all_documents()) == 2


def test_learn_from_my_folder_fills_the_project(empty_client, tmp_path):
    """The tree of the folder itself, with no AI."""
    root = a_folder(tmp_path / "p")
    later(empty_client, root)
    answer = empty_client.post("/projects/active/learn")
    assert answer.status_code == 200 and answer.get_json()["folders"] >= 1
    settings = empty_client.get("/settings").get_json()
    assert settings["folder_tree"][0]["name"] == "Fotos"
    assert settings["folder_mode"] == "place"


def test_learn_with_no_subfolders_says_so(empty_client, tmp_path):
    """A flat folder has nothing to learn from."""
    root = tmp_path / "flat"
    root.mkdir()
    (root / "a.txt").write_text("x")
    later(empty_client, root)
    answer = empty_client.post("/projects/active/learn")
    assert answer.status_code == 400
    assert answer.get_json()["error"]["code"] == "nothing_to_learn"


def test_the_plan_of_a_project_left_for_later_says_why_it_is_empty(
        empty_client, tmp_path):
    """No rows yet, and the count of files waiting."""
    root = a_folder(tmp_path / "p")
    later(empty_client, root)
    view = empty_client.get("/plan").get_json()
    assert view["rows"] == [] and view["unread"] == 2


def test_folders_request_still_exists_for_the_ai(tmp_path):
    """The prompt the tree comes from is unchanged."""
    assert "JSON list" in base.FOLDERS_PROMPT


def test_the_job_says_how_long_the_current_file_has_taken():
    """The screen says Still reading after 30 s."""
    job = scanner.ScanJob()
    now = [100.0]
    job.clock = lambda: now[0]
    assert job.to_dict()["current_seconds"] == 0
    job.file_started = 100.0
    now[0] = 131.5
    assert job.to_dict()["current_seconds"] == 31


def test_the_seconds_go_back_to_zero_after_each_file(tmp_path):
    """Nothing is left counting when a scan ends."""
    root = a_folder(tmp_path / "p")
    (root / ".cataloga").mkdir()
    from backend.db.schema import init_db
    db_path = projects.catalog_path(str(root))
    init_db(db_path)
    repo = CatalogRepository(db_path)
    repo.save_app_config("Nuevo", str(root))
    job = scanner.ScanJob()
    scanner.scan_folder(job, str(root), repo, FakeAI())
    assert job.file_started is None
    assert job.to_dict()["current_seconds"] == 0
