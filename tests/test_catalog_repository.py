"""Tests for CatalogRepository.

Every test gets its own empty database in a temporary folder, so tests
never touch database/catalog.db and never affect each other.
"""

import pytest

from backend.db.catalog_repository import CatalogRepository
from backend.db.schema import init_db
from backend.models.document import Document


@pytest.fixture
def repo(tmp_path):
    """Return a CatalogRepository backed by a new temporary database."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    return CatalogRepository(db_path)


def make_doc(filename="D_001.pdf", media_type="Documents", source=None,
             summary=None, status="Classified"):
    """Build a Document with sensible defaults for testing."""
    return Document(
        original_filename="original_" + filename,
        filename=filename,
        media_type=media_type,
        file_path="/archive/" + media_type + "/" + filename,
        date_added="2026-10-21T10:00:00",
        source=source,
        summary=summary,
        status=status,
    )


def test_add_document_sets_id(repo):
    """add_document() must give the document the id of its new row."""
    doc = repo.add_document(make_doc())
    assert doc.id == 1


def test_get_document_returns_saved_fields(repo):
    """A saved document comes back with the same values."""
    repo.add_document(make_doc(source="El Nuevo Dia", summary="A report."))
    doc = repo.get_document(1)
    assert doc.filename == "D_001.pdf"
    assert doc.source == "El Nuevo Dia"
    assert doc.summary == "A report."


def test_get_document_missing_id_returns_none(repo):
    """An id that does not exist returns None instead of crashing."""
    assert repo.get_document(99) is None


def test_get_all_documents_without_filters(repo):
    """With no filters, every document is returned."""
    repo.add_document(make_doc("D_001.pdf"))
    repo.add_document(make_doc("PR_001.pdf", media_type="Press"))
    assert len(repo.get_all_documents()) == 2


def test_get_all_documents_filter_by_media_type(repo):
    """The media_type filter only returns documents of that type."""
    repo.add_document(make_doc("D_001.pdf"))
    repo.add_document(make_doc("PR_001.pdf", media_type="Press"))
    results = repo.get_all_documents({"media_type": "Press"})
    assert [doc.filename for doc in results] == ["PR_001.pdf"]


def test_get_all_documents_search_matches_summary(repo):
    """search finds text inside the summary, ignoring upper/lower case."""
    repo.add_document(make_doc("D_001.pdf", summary="Interview about swim"))
    repo.add_document(make_doc("D_002.pdf", summary="Budget report"))
    results = repo.get_all_documents({"search": "SWIM"})
    assert [doc.filename for doc in results] == ["D_001.pdf"]


def test_get_all_documents_combines_filters(repo):
    """Several filters together must all match."""
    repo.add_document(make_doc("D_001.pdf", source="Archive A"))
    repo.add_document(make_doc("D_002.pdf", source="Archive A",
                               status="Manual Review"))
    results = repo.get_all_documents({"source": "Archive A",
                                      "status": "Manual Review"})
    assert [doc.filename for doc in results] == ["D_002.pdf"]


def test_get_by_status(repo):
    """get_by_status() returns only documents with that status."""
    repo.add_document(make_doc("D_001.pdf"))
    repo.add_document(make_doc("D_002.pdf", status="Manual Review"))
    results = repo.get_by_status("Manual Review")
    assert [doc.filename for doc in results] == ["D_002.pdf"]


def test_update_document_changes_editable_field(repo):
    """An editable field is saved and the updated document is returned."""
    repo.add_document(make_doc())
    doc = repo.update_document(1, {"source": "Primera Hora"})
    assert doc.source == "Primera Hora"
    assert repo.get_document(1).source == "Primera Hora"


@pytest.mark.parametrize("field", ["original_filename", "filename"])
def test_update_document_rejects_locked_fields(repo, field):
    """Locked fields raise ValueError and the row is not changed."""
    repo.add_document(make_doc())
    with pytest.raises(ValueError):
        repo.update_document(1, {field: "hacked.pdf"})
    assert repo.get_document(1).filename == "D_001.pdf"


def test_update_document_rejects_unknown_field(repo):
    """A field that is not a documents column raises ValueError."""
    repo.add_document(make_doc())
    with pytest.raises(ValueError):
        repo.update_document(1, {"color": "blue"})


def test_update_document_rejects_invalid_media_type(repo):
    """media_type must be one of the five valid types."""
    repo.add_document(make_doc())
    with pytest.raises(ValueError):
        repo.update_document(1, {"media_type": "NewsPaper"})


def test_update_document_rejects_long_summary(repo):
    """A summary over 100 characters raises ValueError."""
    repo.add_document(make_doc())
    with pytest.raises(ValueError, match="100 characters or less"):
        repo.update_document(1, {"summary": "x" * 101})


def test_update_document_accepts_100_character_summary(repo):
    """A summary right at the limit is saved."""
    repo.add_document(make_doc())
    updated = repo.update_document(1, {"summary": "x" * 100})
    assert updated.summary == "x" * 100


def test_update_document_missing_id_raises_key_error(repo):
    """Updating an id that does not exist raises KeyError."""
    with pytest.raises(KeyError):
        repo.update_document(99, {"source": "Anything"})


def test_dashboard_stats(repo):
    """The dashboard numbers match what was saved."""
    repo.add_document(make_doc("D_001.pdf", source="Archive A"))
    repo.add_document(make_doc("PR_001.pdf", media_type="Press",
                               source="Archive B"))
    repo.add_document(make_doc("D_002.pdf", source="Archive A",
                               status="Manual Review"))
    repo.update_document(1, {"summary": "Edited summary"})

    stats = repo.get_dashboard_stats()

    assert stats["documents_classified"] == 2
    assert stats["needs_manual_review"] == 1
    assert stats["sources_tracked"] == 2
    assert stats["media_type_breakdown"] == {
        "Press": 1, "Audio": 0, "Video": 0, "Photos": 0, "Documents": 2,
    }
    # Newest activity first: the edit, then the three additions.
    assert stats["recent_activity"][0]["action"] == "Edited"
    assert stats["recent_activity"][0]["filename"] == "D_001.pdf"
    assert len(stats["recent_activity"]) == 4


def test_has_file_path(repo):
    """has_file_path() is True only for a path that was saved."""
    doc = repo.add_document(make_doc())
    assert repo.has_file_path(doc.file_path) is True
    assert repo.has_file_path("/somewhere/else.pdf") is False
