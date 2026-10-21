"""Tests for the folder watcher.

The watcher runs with a real database and real folders in a temporary
location. The AI client is replaced with a fake so no API is called.
"""

import os

import pytest

from backend import folder_watcher
from backend.db.catalog_repository import CatalogRepository
from backend.db.schema import init_db
from backend.folder_watcher import find_new_files, scan_once
from backend.pipeline.ai_providers import base
from backend.pipeline.ai_providers.base import AIProviderClient


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
    inbox = project["folder"] / "Inbox"
    inbox.mkdir()
    (inbox / "a.txt").write_text("Some text")
    assert scan_once(project["db_path"]) == []
    assert (inbox / "a.txt").exists()


def test_scan_processes_inbox_files_once(project):
    """Inbox files are cataloged and moved; a second scan finds nothing."""
    configure(project)
    inbox = project["folder"] / "Inbox"
    inbox.mkdir()
    (inbox / "clip.txt").write_text("Newspaper text")

    first = scan_once(project["db_path"])
    second = scan_once(project["db_path"])

    assert [doc.filename for doc in first] == ["PR_001.txt"]
    assert second == []
    assert (project["folder"] / "Press" / "PR_001.txt").is_file()
    assert not (inbox / "clip.txt").exists()


def test_scan_never_moves_files_outside_inbox(project):
    """Files the user already had in the project folder stay untouched."""
    configure(project)
    existing = project["folder"] / "my_poster.pdf"
    existing.write_text("The user's own work")

    assert scan_once(project["db_path"]) == []
    assert existing.is_file()
