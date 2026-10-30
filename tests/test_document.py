"""Tests for the Document model and where its database lives."""

import os
import sys

import pytest
from backend.models.document import Document


def test_is_locked_field_original_filename():
    """original_filename must always be reported as locked."""
    doc = Document(
        original_filename="scan.pdf",
        filename="D_001.pdf",
        media_type="Documents",
        file_path="/archive/Documents/D_001.pdf",
        date_added="2026-09-11T10:00:00",
    )
    assert doc.is_locked_field("original_filename") is True


def test_is_locked_field_filename():
    """filename must always be reported as locked."""
    doc = Document(
        original_filename="scan.pdf",
        filename="D_001.pdf",
        media_type="Documents",
        file_path="/archive/Documents/D_001.pdf",
        date_added="2026-09-11T10:00:00",
    )
    assert doc.is_locked_field("filename") is True


def test_is_locked_field_editable_field():
    """source is not a locked field."""
    doc = Document(
        original_filename="scan.pdf",
        filename="D_001.pdf",
        media_type="Documents",
        file_path="/archive/Documents/D_001.pdf",
        date_added="2026-09-11T10:00:00",
    )
    assert doc.is_locked_field("source") is False


def test_mark_needs_review():
    """mark_needs_review() must set status to 'Manual Review'."""
    doc = Document(
        original_filename="scan.pdf",
        filename="D_001.pdf",
        media_type="Documents",
        file_path="/archive/Documents/D_001.pdf",
        date_added="2026-09-11T10:00:00",
    )
    doc.mark_needs_review(["summary", "source"])
    assert doc.status == "Manual Review"


def test_to_dict_contains_all_keys():
    """to_dict() must include every field the API returns."""
    doc = Document(
        original_filename="scan.pdf",
        filename="D_001.pdf",
        media_type="Documents",
        file_path="/archive/Documents/D_001.pdf",
        date_added="2026-09-11T10:00:00",
    )
    result = doc.to_dict()
    expected_keys = {
        "id", "original_filename", "filename", "media_type",
        "source", "document_date", "summary", "status",
        "file_path", "date_added", "date_classified",
        "topic", "keywords", "sha256", "duplicate_of", "review_note",
        "counterparty", "confidentiality", "owner", "effective_start",
        "effective_end", "category", "subcategory", "date_source",
        "suggested_folder", "proposed_folder", "proposed_name",
    }
    assert expected_keys == set(result.keys())
    assert result["keywords"] == []


def test_unknown_document_field_is_refused():
    """A typo in a field name raises instead of being lost."""
    with pytest.raises(TypeError):
        Document(original_filename="a.pdf", filename="a.pdf",
                 media_type="Documents", file_path="/a.pdf",
                 date_added="2026-09-11T10:00:00", keyword=["x"])


# --- Where the database file lives (backend/db/schema.py) ---

def test_db_path_from_code_is_in_project_database_folder():
    """Running from the code keeps using database/catalog.db."""
    from backend.db import schema
    path = schema.default_db_path()
    assert path.endswith(os.path.join("database", "catalog.db"))


def test_db_path_in_packaged_mac_app(monkeypatch, tmp_path):
    """The packaged Mac app keeps its data in Application Support."""
    from backend.db import schema
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setenv("HOME", str(tmp_path))
    path = schema.default_db_path()
    expected_folder = tmp_path / "Library" / "Application Support" / \
        "Cataloga"
    assert path == str(expected_folder / "catalog.db")
    assert expected_folder.is_dir()
