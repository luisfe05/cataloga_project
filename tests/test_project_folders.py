"""Tests for the per-project folder tree."""

import json
import os

import pytest

from backend.db.catalog_repository import CatalogRepository
from backend.db.schema import init_db
from backend.pipeline import archive_rules, naming
from backend.pipeline.ai_providers import base
from backend.pipeline.ai_providers.base import AIProviderClient
from backend.pipeline.classification_pipeline import ClassificationPipeline
from backend.pipeline.file_organizer import MEDIA_TYPES, FileOrganizer

METADATA = {"source": "El Nuevo Día", "document_date": "2026-07-15",
            "topic": "Oceanman Malta", "keywords": ["swimming"]}


class FolderAI(AIProviderClient):
    """Fake AI that answers each kind of request and keeps the prompts."""

    def __init__(self, metadata):
        super().__init__(provider_name="fake", model="fake-model")
        self.retry_delay = 0
        self.metadata = metadata
        self.prompts = []

    def send_prompt(self, system_prompt, text):
        self.prompts.append(system_prompt)
        if system_prompt == base.CLASSIFICATION_PROMPT:
            return "Press"
        if system_prompt == base.SUMMARY_PROMPT:
            return "A news story."
        return json.dumps(self.metadata)


@pytest.fixture
def old_project(tmp_path, monkeypatch):
    """A project made before folder trees: no folder_mode saved."""
    monkeypatch.setattr(base.keyring, "get_password",
                        lambda service, name: "test-key")
    folder = tmp_path / "archive"
    db_path = str(tmp_path / "catalog.db")
    init_db(db_path)
    repo = CatalogRepository(db_path)
    repo.save_app_config("Old", str(folder))
    repo.save_naming_template(naming.NEW_PROJECT_TEMPLATE)
    organizer = FileOrganizer(str(folder))
    organizer.ensure_archive_structure()
    ai = FolderAI(dict(METADATA))
    pipeline = ClassificationPipeline(ai, repo, organizer)
    return {"repo": repo, "ai": ai, "pipeline": pipeline,
            "folder": folder, "drop_zone": folder / "Drop Zone"}


def drop(project, name, text):
    """Put a text file in the Drop Zone and return its path."""
    path = project["drop_zone"] / name
    path.write_text(text)
    return str(path)


# --- Old projects do not change ---

def test_old_project_keeps_the_five_media_folders(old_project):
    """An old project still gets Drop Zone and the five media folders."""
    names = sorted(os.listdir(str(old_project["folder"])))
    assert names == sorted(list(MEDIA_TYPES) + ["Drop Zone"])


def test_old_project_files_go_to_their_media_folder(old_project):
    """In an old project the media type still picks the folder."""
    doc = old_project["pipeline"].classify_document(
        drop(old_project, "a.txt", "Article"))
    assert doc.media_type == "Press"
    assert doc.file_path == os.path.join(
        str(old_project["folder"]), "Press",
        "oceanman-malta_el-nuevo-dia_2026-07-15_001.txt")
    assert doc.status == "Classified"


def test_old_project_categories_never_pick_a_folder(old_project):
    """Categories stay data in an old project; the folder is the type."""
    old_project["repo"].save_categories(
        [{"name": "Contracts", "subcategories": []}])
    old_project["ai"].metadata["category"] = "Contracts"
    doc = old_project["pipeline"].classify_document(
        drop(old_project, "a.txt", "Contract"))
    assert doc.category == "Contracts"
    assert os.path.dirname(doc.file_path) == os.path.join(
        str(old_project["folder"]), "Press")
    assert not os.path.exists(str(old_project["folder"] / "Contracts"))


def test_old_project_no_category_fit_still_moves_by_type(old_project):
    """No category fit is Manual Review, but the file still moves."""
    old_project["repo"].save_categories(
        [{"name": "Contracts", "subcategories": []}])
    old_project["ai"].metadata["category"] = "Recipes"
    doc = old_project["pipeline"].classify_document(
        drop(old_project, "a.txt", "Recipe"))
    assert doc.status == "Manual Review"
    assert doc.review_note == archive_rules.NO_CATEGORY_NOTE
    assert os.path.dirname(doc.file_path) == os.path.join(
        str(old_project["folder"]), "Press")


def test_old_project_unreadable_file_goes_to_documents(old_project):
    """A file without text still lands in Documents, as before."""
    path = old_project["drop_zone"] / "notes.xyz"
    path.write_bytes(b"\x00\x01")
    doc = old_project["pipeline"].classify_document(str(path))
    assert doc.status == "Manual Review"
    assert os.path.dirname(doc.file_path) == os.path.join(
        str(old_project["folder"]), "Documents")
