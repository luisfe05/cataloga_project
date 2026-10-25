"""Tests for the folder watcher.

The watcher runs with a real database and real folders in a temporary
location. The AI client is replaced with a fake so no API is called.
"""

import os

import pytest

from backend import folder_watcher
from backend.db.catalog_repository import CatalogRepository
from backend.db.schema import init_db
from backend.folder_watcher import (OLD_INBOX_WARNING, find_new_files,
                                    old_inbox_has_files, scan_once)
from backend.pipeline.ai_providers import base
from backend.pipeline.ai_providers.base import AIProviderClient
from backend.pipeline.file_organizer import FileOrganizer


class FakeAI(AIProviderClient):
    """Classifies everything as Press with full metadata."""

    def __init__(self):
        super().__init__(provider_name="fake", model="fake-model")
        self.retry_delay = 0

    def send_prompt(self, system_prompt, text):
        if system_prompt == base.CLASSIFICATION_PROMPT:
            return "Press"
        if system_prompt == base.SUMMARY_PROMPT:
            return "A summary."
        return '{"source": "Claridad", "document_date": "1980"}'


@pytest.fixture(autouse=True)
def fake_ai(monkeypatch):
    """Use FakeAI instead of a real provider, with a test key."""
    monkeypatch.setattr(base.keyring, "get_password",
                        lambda service, name: "test-key")
    monkeypatch.setattr(folder_watcher, "create_client",
                        lambda name, model: FakeAI())


@pytest.fixture
def project(tmp_path):
    """A database and an empty project folder."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    folder = tmp_path / "project"
    folder.mkdir()
    return {"db_path": db_path, "folder": folder,
            "repo": CatalogRepository(db_path)}


def configure(project):
    """Save the project folder and an active provider in settings."""
    project["repo"].save_app_config("Test", str(project["folder"]))
    project["repo"].set_active_provider("gemini", "gemini-2.5-flash")


def test_find_new_files_skips_folders_hidden_and_temporary_files(project):
    """Only regular, visible, finished files are returned."""
    folder = project["folder"]
    (folder / "Press").mkdir()
    (folder / "Press" / "PR_001.txt").write_text("old")
    (folder / ".DS_Store").write_text("x")
    (folder / "big.pdf.download").write_text("x")
    (folder / "Poster.af~lock~").write_text("x")
    (folder / "b.txt").write_text("new")
    (folder / "a.txt").write_text("new")
    names = [os.path.basename(path) for path in find_new_files(str(folder))]
    assert names == ["a.txt", "b.txt"]


def test_find_new_files_missing_folder():
    """A folder that does not exist gives an empty list, not an error."""
    assert find_new_files("/no/such/folder") == []


def test_scan_does_nothing_before_settings(project):
    """Without a project folder and provider, nothing is processed."""
    drop_zone = project["folder"] / "Drop Zone"
    drop_zone.mkdir()
    (drop_zone / "a.txt").write_text("Some text")
    assert scan_once(project["db_path"]) == []
    assert (drop_zone / "a.txt").exists()


def test_scan_processes_drop_zone_files_once(project):
    """Drop Zone files are cataloged and moved; a second scan finds none."""
    configure(project)
    drop_zone = project["folder"] / "Drop Zone"
    drop_zone.mkdir()
    (drop_zone / "clip.txt").write_text("Newspaper text")

    first = scan_once(project["db_path"])
    second = scan_once(project["db_path"])

    assert [doc.filename for doc in first] == ["PR_001.txt"]
    assert second == []
    assert (project["folder"] / "Press" / "PR_001.txt").is_file()
    assert not (drop_zone / "clip.txt").exists()


def test_scan_never_moves_files_outside_drop_zone(project):
    """Files the user already had in the project folder stay untouched."""
    configure(project)
    existing = project["folder"] / "my_poster.pdf"
    existing.write_text("The user's own work")

    assert scan_once(project["db_path"]) == []
    assert existing.is_file()


# --- Old Inbox folder from earlier versions ---

@pytest.fixture(autouse=True)
def forget_warnings():
    """Start every test with no project folder warned about yet."""
    folder_watcher.warned_folders.clear()


def make_old_inbox_with_file(project):
    """Create Drop Zone and an old Inbox that still has one file."""
    (project["folder"] / "Drop Zone").mkdir()
    inbox = project["folder"] / "Inbox"
    inbox.mkdir()
    (inbox / "left.txt").write_text("Left behind")
    return inbox


def test_scan_renames_old_inbox_and_processes_its_files(project):
    """An old project's Inbox becomes Drop Zone and its files are read."""
    configure(project)
    inbox = project["folder"] / "Inbox"
    inbox.mkdir()
    (inbox / "clip.txt").write_text("Newspaper text")

    documents = scan_once(project["db_path"])

    assert not inbox.exists()
    assert (project["folder"] / "Drop Zone").is_dir()
    assert [doc.filename for doc in documents] == ["PR_001.txt"]


def test_old_inbox_has_files_with_both_folders(project):
    """Inbox with a file next to Drop Zone is reported."""
    make_old_inbox_with_file(project)
    organizer = FileOrganizer(str(project["folder"]))
    assert old_inbox_has_files(organizer) is True


def test_old_inbox_has_files_ignores_hidden_files(project):
    """An Inbox with only .DS_Store does not count as having files."""
    (project["folder"] / "Drop Zone").mkdir()
    inbox = project["folder"] / "Inbox"
    inbox.mkdir()
    (inbox / ".DS_Store").write_text("x")
    organizer = FileOrganizer(str(project["folder"]))
    assert old_inbox_has_files(organizer) is False


def test_old_inbox_has_files_needs_drop_zone(project):
    """Without Drop Zone, Inbox is not reported (it will be migrated)."""
    inbox = project["folder"] / "Inbox"
    inbox.mkdir()
    (inbox / "a.txt").write_text("x")
    organizer = FileOrganizer(str(project["folder"]))
    assert old_inbox_has_files(organizer) is False


def test_scan_warns_once_and_never_moves_old_inbox_files(project, caplog):
    """The warning is logged once, and the Inbox file stays where it is."""
    configure(project)
    inbox = make_old_inbox_with_file(project)

    scan_once(project["db_path"])
    scan_once(project["db_path"])

    warnings = [record for record in caplog.records
                if OLD_INBOX_WARNING in record.getMessage()]
    assert len(warnings) == 1
    assert warnings[0].levelname == "WARNING"
    assert (inbox / "left.txt").is_file()
