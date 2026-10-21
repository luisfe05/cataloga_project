"""Tests for ClassificationPipeline.

The pipeline runs with a real CatalogRepository (temporary database) and
a real FileOrganizer (temporary folder). Only the AI is fake, so tests
never hit a real API.
"""

import os

import pytest
from pypdf import PdfWriter

from backend.db.catalog_repository import CatalogRepository
from backend.db.schema import init_db
from backend.pipeline import classification_pipeline
from backend.pipeline.ai_providers import base
from backend.pipeline.ai_providers.base import AIProviderClient
from backend.pipeline.classification_pipeline import (
    ClassificationPipeline, parse_json_answer)
from backend.pipeline.file_organizer import FileOrganizer

GOOD_METADATA = '{"source": "El Nuevo Dia", "document_date": "1964-10-12"}'


class FakeAI(AIProviderClient):
    """Answers each kind of request with a prepared reply.

    replies maps 'classify', 'summary', and 'metadata' to the text the
    fake AI returns for that kind of request.
    """

    def __init__(self, replies):
        super().__init__(provider_name="fake", model="fake-model")
        self.replies = replies
        self.retry_delay = 0
        self.calls = 0

    def send_prompt(self, system_prompt, text):
        self.calls += 1
        if system_prompt == base.CLASSIFICATION_PROMPT:
            return self.replies["classify"]
        if system_prompt == base.SUMMARY_PROMPT:
            return self.replies["summary"]
        return self.replies["metadata"]


@pytest.fixture(autouse=True)
def fake_keyring(monkeypatch):
    """Make keyring return a test key so the fake AI is allowed to run."""
    monkeypatch.setattr(base.keyring, "get_password",
                        lambda service, name: "test-key")


@pytest.fixture
def setup(tmp_path):
    """Build a pipeline with a temp database, archive, and inbox folder."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    repo = CatalogRepository(db_path)
    organizer = FileOrganizer(str(tmp_path / "archive"))
    inbox = tmp_path / "inbox"
    inbox.mkdir()

    def build(replies=None):
        if replies is None:
            replies = {"classify": "Press", "summary": "A news story.",
                       "metadata": GOOD_METADATA}
        ai = FakeAI(replies)
        return ClassificationPipeline(ai, repo, organizer), ai

    return {"build": build, "repo": repo, "inbox": inbox}


def make_text_file(folder, name, text="Article text about a swim meet."):
    """Write a .txt file and return its path as a string."""
    path = folder / name
    path.write_text(text)
    return str(path)


def make_blank_pdf(folder, name):
    """Write a one-page PDF with no text layer, like a scanned page."""
    path = folder / name
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    with open(path, "wb") as file:
        writer.write(file)
    return str(path)


def test_readable_file_is_fully_classified(setup):
    """A text file gets type, summary, source, date, and Classified."""
    pipeline, ai = setup["build"]()
    path = make_text_file(setup["inbox"], "clipping.txt")

    doc = pipeline.classify_document(path)

    assert doc.id == 1
    assert doc.original_filename == "clipping.txt"
    assert doc.filename == "PR_001.txt"
    assert doc.media_type == "Press"
    assert doc.summary == "A news story."
    assert doc.source == "El Nuevo Dia"
    assert doc.document_date == "1964-10-12"
    assert doc.status == "Classified"
    assert os.path.isfile(doc.file_path)
    assert not os.path.exists(path)
    assert ai.calls == 3


def test_missing_metadata_sends_to_manual_review(setup):
    """If the AI finds no source, the document goes to Manual Review."""
    replies = {"classify": "Documents", "summary": "A letter.",
               "metadata": '{"source": null, "document_date": "1970"}'}
    pipeline, ai = setup["build"](replies)
    doc = pipeline.classify_document(make_text_file(setup["inbox"], "a.txt"))
    assert doc.source is None
    assert doc.document_date == "1970"
    assert doc.status == "Manual Review"


def test_invalid_classification_uses_fallback_folder(setup):
    """An answer that is not a media type goes to Documents for review."""
    replies = {"classify": "Newspaper", "summary": "Something.",
               "metadata": GOOD_METADATA}
    pipeline, ai = setup["build"](replies)
    doc = pipeline.classify_document(make_text_file(setup["inbox"], "a.txt"))
    assert doc.media_type == "Documents"
    assert doc.filename == "D_001.txt"


def test_photo_is_sorted_without_ai(setup):
    """A photo goes to Photos by extension, with no AI call."""
    pipeline, ai = setup["build"]()
    path = str(setup["inbox"] / "team.JPG")
    with open(path, "wb") as file:
        file.write(b"fake image bytes")

    doc = pipeline.classify_document(path)

    assert doc.media_type == "Photos"
    assert doc.filename == "P_001.jpg"
    assert doc.status == "Manual Review"
    assert ai.calls == 0


def test_scanned_pdf_is_flagged_for_manual_summary(setup):
    """A PDF with no text is moved and flagged, not skipped."""
    pipeline, ai = setup["build"]()
    doc = pipeline.classify_document(
        make_blank_pdf(setup["inbox"], "scan.pdf"))
    assert doc.media_type == "Documents"
    assert doc.filename == "D_001.pdf"
    assert doc.summary is None
    assert doc.status == "Manual Review"
    assert ai.calls == 0


def test_unsupported_format_is_flagged(setup):
    """A .docx is not read in the MVP: Documents folder, Manual Review."""
    pipeline, ai = setup["build"]()
    path = str(setup["inbox"] / "notes.docx")
    with open(path, "wb") as file:
        file.write(b"not really a docx")
    doc = pipeline.classify_document(path)
    assert doc.media_type == "Documents"
    assert doc.status == "Manual Review"
    assert ai.calls == 0


def test_process_batch_handles_every_file(setup):
    """Every file in the list becomes one saved document."""
    pipeline, ai = setup["build"]()
    paths = [make_text_file(setup["inbox"], name)
             for name in ("a.txt", "b.txt", "c.txt")]
    documents = pipeline.process_batch(paths)
    assert [doc.filename for doc in documents] == [
        "PR_001.txt", "PR_002.txt", "PR_003.txt"]
    assert len(setup["repo"].get_all_documents()) == 3


def test_process_batch_skips_files_already_cataloged(setup):
    """Files already in the catalog are not sent to the AI again."""
    pipeline, ai = setup["build"]()
    first = pipeline.process_batch([make_text_file(setup["inbox"], "a.txt")])
    calls_after_first_run = ai.calls

    # Run again with the cataloged file plus one new file.
    new_file = make_text_file(setup["inbox"], "b.txt")
    second = pipeline.process_batch([first[0].file_path, new_file])

    assert [doc.original_filename for doc in second] == ["b.txt"]
    assert ai.calls == calls_after_first_run + 3


def test_process_batch_continues_after_a_missing_file(setup):
    """A file that no longer exists is skipped, the rest still run."""
    pipeline, ai = setup["build"]()
    good = make_text_file(setup["inbox"], "good.txt")
    missing = str(setup["inbox"] / "deleted.txt")
    documents = pipeline.process_batch([missing, good])
    assert [doc.original_filename for doc in documents] == ["good.txt"]


@pytest.mark.parametrize("answer, expected", [
    ('{"source": "Claridad"}', {"source": "Claridad"}),
    ('```json\n{"source": "Claridad"}\n```', {"source": "Claridad"}),
    ("not json at all", {}),
    ('["a list"]', {}),
    (None, {}),
])
def test_parse_json_answer(answer, expected):
    """JSON is read even inside markdown fences; bad answers give {}."""
    assert parse_json_answer(answer) == expected


def test_extract_text_reads_txt(tmp_path):
    """extract_text() returns the content of a .txt file."""
    path = make_text_file(tmp_path, "a.txt", "  Hello archive  ")
    assert classification_pipeline.extract_text(path) == "Hello archive"


def test_regenerate_summary_uses_the_users_facts(setup):
    """After an edit, the new summary is saved for a readable file."""
    replies = {"classify": "Documents", "summary": "First summary.",
               "metadata": '{"source": null, "document_date": null}'}
    pipeline, ai = setup["build"](replies)
    doc = pipeline.classify_document(
        make_text_file(setup["inbox"], "letter.txt"))

    # The user types the source by hand, then the summary is rewritten.
    ai.replies["summary"] = "Letter from Claridad."
    doc = setup["repo"].update_document(doc.id, {"source": "Claridad"})
    doc = pipeline.regenerate_summary(doc)

    assert doc.summary == "Letter from Claridad."
    assert setup["repo"].get_document(doc.id).summary == \
        "Letter from Claridad."


def test_regenerate_summary_skips_files_without_text(setup):
    """A photo has no text, so its summary is left as it was."""
    pipeline, ai = setup["build"]()
    path = str(setup["inbox"] / "team.jpg")
    with open(path, "wb") as file:
        file.write(b"fake image bytes")
    doc = pipeline.classify_document(path)

    doc = pipeline.regenerate_summary(doc)

    assert doc.summary is None
    assert ai.calls == 0
