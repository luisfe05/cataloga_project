"""Tests for the Document model."""

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
    }
    assert expected_keys == set(result.keys())
