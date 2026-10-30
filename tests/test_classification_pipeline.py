"""Tests for ClassificationPipeline."""

import os
import time

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
from tests.conftest import card_answer

GOOD_METADATA = ('{"source": "El Nuevo Día", "document_date": "1964-10-12",'
                 ' "topic": "Malta Olímpica"}')

# 2026-07-15 at noon, local time, used as a file's modified date.
JULY_15 = time.mktime((2026, 7, 15, 12, 0, 0, 0, 0, -1))


class FakeAI(AIProviderClient):
    """Answers each kind of request with a prepared reply."""

    def __init__(self, replies):
        super().__init__(provider_name="fake", model="fake-model")
        self.replies = replies
        self.retry_delay = 0
        self.calls = 0

    def send_prompt(self, system_prompt, text):
        self.calls += 1
        self.last_text = text
        if system_prompt == base.SUMMARY_PROMPT:
            return self.replies["summary"]
        return card_answer(self.replies["metadata"], self.replies["classify"],
                           self.replies["summary"])


@pytest.fixture(autouse=True)
def fake_keyring(monkeypatch):
    """Make keyring return a test key so the fake AI is allowed to run."""
    monkeypatch.setattr(base.keyring, "get_password",
                        lambda service, name: "test-key")


@pytest.fixture
def setup(tmp_path):
    """Build a pipeline with a temp database, archive, and Drop Zone folder."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    repo = CatalogRepository(db_path)
    organizer = FileOrganizer(str(tmp_path / "archive"))
    drop_zone = tmp_path / "drop_zone"
    drop_zone.mkdir()

    def build(replies=None):
        if replies is None:
            replies = {"classify": "Press", "summary": "A news story.",
                       "metadata": GOOD_METADATA}
        ai = FakeAI(replies)
        return ClassificationPipeline(ai, repo, organizer), ai

    return {"build": build, "repo": repo, "drop_zone": drop_zone}


def make_text_file(folder, name, text=None):
    """Write a .txt file; the default text is different for each name."""
    path = folder / name
    # Same bytes would make a duplicate, so the name goes in the text.
    path.write_text(text or "Article text about a swim meet. " + name)
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
    path = make_text_file(setup["drop_zone"], "clipping.txt")

    doc = pipeline.classify_document(path)

    assert doc.id == 1
    assert doc.original_filename == "clipping.txt"
    assert doc.filename == "1964-10-12_malta-olimpica.txt"
    assert doc.media_type == "Press"
    assert doc.summary == "A news story."
    assert doc.source == "El Nuevo Día"
    assert doc.document_date == "1964-10-12"
    assert doc.status == "Classified"
    assert os.path.isfile(doc.file_path)
    assert not os.path.exists(path)
    # One request per file: the card, the folder, and how sure.
    assert ai.calls == 1


def test_missing_source_or_date_is_still_classified(setup):
    """No source and no date: the file is read, so it is Classified."""
    replies = {"classify": "Documents", "summary": "A letter.",
               "metadata": '{"source": null, "document_date": null}'}
    pipeline, ai = setup["build"](replies)
    doc = pipeline.classify_document(
        make_text_file(setup["drop_zone"], "a.txt"))
    assert doc.source is None
    assert doc.date_source == "file"
    assert doc.status == "Classified"
    assert doc.review_note is None


def test_no_summary_sends_to_manual_review(setup):
    """Without a summary the file was not really read."""
    replies = {"classify": "Documents", "summary": "",
               "metadata": '{"source": "Claridad", "document_date": "1970"}'}
    pipeline, ai = setup["build"](replies)
    doc = pipeline.classify_document(
        make_text_file(setup["drop_zone"], "a.txt"))
    assert doc.status == "Manual Review"
    assert doc.review_note == "Missing: summary"


def test_every_manual_review_file_has_a_note(setup):
    """Like plan_viaje.txt: no summary, and no other reason."""
    replies = {"classify": "Documents", "summary": "",
               "metadata": '{"source": null, "document_date": "2025-03",'
                           ' "topic": "Plan de viaje"}'}
    pipeline, ai = setup["build"](replies)
    pipeline.classify_document(
        make_text_file(setup["drop_zone"], "plan_viaje.txt"))
    # A photo the provider cannot see is read by no one.
    ai.supports_images = False
    photo = setup["drop_zone"] / "IMG_0001.jpg"
    photo.write_bytes(b"not really a photo")
    pipeline.classify_document(str(photo))
    documents = setup["repo"].get_all_documents()
    assert [doc.review_note for doc in documents] == [
        "Missing: summary", "Missing: summary"]
    assert all(doc.status == "Manual Review" for doc in documents)


def test_invalid_classification_uses_fallback_folder(setup):
    """An answer that is not a media type goes to Documents for review."""
    replies = {"classify": "Newspaper", "summary": "Something.",
               "metadata": GOOD_METADATA}
    pipeline, ai = setup["build"](replies)
    doc = pipeline.classify_document(
        make_text_file(setup["drop_zone"], "a.txt"))
    assert doc.media_type == "Documents"
    assert doc.filename == "1964-10-12_malta-olimpica.txt"


def test_photo_is_sorted_without_ai(setup):
    """A photo goes to Photos by extension, with no AI call."""
    pipeline, ai = setup["build"]()
    path = str(setup["drop_zone"] / "team.JPG")
    with open(path, "wb") as file:
        file.write(b"fake image bytes")
    os.utime(path, (JULY_15, JULY_15))

    doc = pipeline.classify_document(path)

    assert doc.media_type == "Photos"
    assert doc.filename == "undated_0001.jpg"
    assert doc.status == "Manual Review"
    assert ai.calls == 0


def test_scanned_pdf_is_flagged_for_manual_summary(setup):
    """A PDF with no text is moved and flagged, not skipped."""
    pipeline, ai = setup["build"]()
    path = make_blank_pdf(setup["drop_zone"], "scan.pdf")
    os.utime(path, (JULY_15, JULY_15))
    doc = pipeline.classify_document(path)
    assert doc.media_type == "Documents"
    assert doc.filename == "undated_0001.pdf"
    assert doc.summary is None
    assert doc.status == "Manual Review"
    assert ai.calls == 0


def test_unsupported_format_is_flagged(setup):
    """A .docx is not read in the MVP: Documents folder, Manual Review."""
    pipeline, ai = setup["build"]()
    path = str(setup["drop_zone"] / "notes.docx")
    with open(path, "wb") as file:
        file.write(b"not really a docx")
    doc = pipeline.classify_document(path)
    assert doc.media_type == "Documents"
    assert doc.status == "Manual Review"
    assert ai.calls == 0


def test_process_batch_handles_every_file(setup):
    """Every file in the list becomes one saved document."""
    pipeline, ai = setup["build"]()
    paths = [make_text_file(setup["drop_zone"], name)
             for name in ("a.txt", "b.txt", "c.txt")]
    documents = pipeline.process_batch(paths)
    # Same date and topic, so the names get -2 and -3.
    assert [doc.filename for doc in documents] == [
        "1964-10-12_malta-olimpica.txt", "1964-10-12_malta-olimpica-2.txt",
        "1964-10-12_malta-olimpica-3.txt"]
    assert len(setup["repo"].get_all_documents()) == 3


def test_process_batch_skips_files_already_cataloged(setup):
    """Files already in the catalog are not sent to the AI again."""
    pipeline, ai = setup["build"]()
    first = pipeline.process_batch(
        [make_text_file(setup["drop_zone"], "a.txt")])
    calls_after_first_run = ai.calls

    # Run again with the cataloged file plus one new file.
    new_file = make_text_file(setup["drop_zone"], "b.txt")
    second = pipeline.process_batch([first[0].file_path, new_file])

    assert [doc.original_filename for doc in second] == ["b.txt"]
    assert ai.calls == calls_after_first_run + 1


def test_process_batch_continues_after_a_missing_file(setup):
    """A file that no longer exists is skipped, the rest still run."""
    pipeline, ai = setup["build"]()
    good = make_text_file(setup["drop_zone"], "good.txt")
    missing = str(setup["drop_zone"] / "deleted.txt")
    documents = pipeline.process_batch([missing, good])
    assert [doc.original_filename for doc in documents] == ["good.txt"]


# --- File names ---

def test_each_method_names_the_file(setup):
    """Methods 2 and 3 use the source and the catalog number."""
    pipeline, ai = setup["build"]()
    setup["repo"].save_naming_template("{source}_{date}_{topic}")
    first = pipeline.classify_document(
        make_text_file(setup["drop_zone"], "a.txt"))
    setup["repo"].save_naming_template("{number}_{topic}")
    second = pipeline.classify_document(
        make_text_file(setup["drop_zone"], "b.txt"))
    assert first.filename == "el-nuevo-dia_1964-10-12_malta-olimpica.txt"
    assert second.filename == "0002_malta-olimpica.txt"


def test_missing_date_source_and_topic(setup):
    """No date in the text: the file date is saved, the name says undated."""
    replies = {"classify": "Documents", "summary": "A letter.",
               "metadata": '{"source": null, "document_date": null, '
                           '"topic": null}'}
    pipeline, ai = setup["build"](replies)
    setup["repo"].save_naming_template("{source}_{date}_{topic}")
    path = make_text_file(setup["drop_zone"], "Carta de Ramón.txt")
    os.utime(path, (JULY_15, JULY_15))
    doc = pipeline.classify_document(path)
    assert doc.filename == "undated_carta-de-ramon.txt"
    assert doc.document_date == "2026-07-15"
    assert doc.date_source == "file"


def test_custom_template_with_original(setup):
    """A custom template can use the original name as a slug."""
    pipeline, ai = setup["build"]()
    setup["repo"].save_naming_template("{date}-{original}")
    doc = pipeline.classify_document(
        make_text_file(setup["drop_zone"], "Scan Letter.TXT"))
    assert doc.filename == "1964-10-12-scan-letter.txt"


def test_photo_ignores_the_custom_template(setup):
    """Files without text always use the file date and number."""
    pipeline, ai = setup["build"]()
    setup["repo"].save_naming_template("{source}_{topic}")
    path = str(setup["drop_zone"] / "team.png")
    with open(path, "wb") as file:
        file.write(b"fake image bytes")
    os.utime(path, (JULY_15, JULY_15))
    assert pipeline.classify_document(path).filename == "undated_0001.png"


def test_topic_comes_in_the_metadata_request(setup):
    """Naming adds no AI request: still 1 call per readable file."""
    pipeline, ai = setup["build"]()
    pipeline.classify_document(make_text_file(setup["drop_zone"], "a.txt"))
    assert ai.calls == 1
    assert '"topic"' in classification_pipeline.FILE_PROMPT


@pytest.mark.parametrize("answer, expected", [
    ('{"source": "Claridad"}', {"source": "Claridad"}),
    ('```json\n{"source": "Claridad"}\n```', {"source": "Claridad"}),
    ('Here it is: {"source": "Claridad"} Done.', {"source": "Claridad"}),
    ("not json at all", {}),
    ('["a list"]', {}),
    ('{"source": broken}', {}),
    (None, {}),
])
def test_parse_json_answer(answer, expected):
    """JSON is read even inside markdown fences; bad answers give {}."""
    assert parse_json_answer(answer) == expected


@pytest.mark.parametrize("answer", [
    '{"source": "Claridad"}\n{"source": "El Mundo"}',
    '```json\n{"source": "Claridad"}\n```\n```json\n'
    '{"source": "El Mundo"}\n```',
    '{"source": broken}\n{"source": "Claridad"}\n{"source": "El Mundo"}',
])
def test_parse_json_answer_uses_the_first_valid_block(answer):
    """With several JSON blocks, the first valid one is read."""
    assert parse_json_answer(answer) == {"source": "Claridad"}


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
        make_text_file(setup["drop_zone"], "letter.txt"))

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
    path = str(setup["drop_zone"] / "team.jpg")
    with open(path, "wb") as file:
        file.write(b"fake image bytes")
    doc = pipeline.classify_document(path)

    doc = pipeline.regenerate_summary(doc)

    assert doc.summary is None
    assert ai.calls == 0


# --- One request per file: the context the AI gets and the card it fills ---

def test_context_names_the_file_its_folder_and_its_neighbors(setup):
    """The AI sees the name, the folder, the other files, and the text."""
    pipeline, ai = setup["build"]()
    make_text_file(setup["drop_zone"], "otro.txt")
    pipeline.classify_document(
        make_text_file(setup["drop_zone"], "Contrato_alquiler_v02.txt"))
    text = ai.last_text
    assert text.startswith("File name: Contrato_alquiler_v02.txt")
    assert "Type: .txt" in text
    # The test Drop Zone sits next to the archive, so the path goes up.
    assert "Folder: ../drop_zone" in text
    assert "Media type: decide between Press and Documents" in text
    assert "Name hints: words: Contrato alquiler v02; version v02" in text
    assert "Other files in that folder: otro.txt" in text
    assert text.rstrip().endswith("Contrato_alquiler_v02.txt")


def test_context_says_when_the_name_is_a_camera_name(setup):
    """DSC_0042 tells the AI nothing, and the prompt says so."""
    pipeline, ai = setup["build"]()
    pipeline.classify_document(make_text_file(setup["drop_zone"],
                                              "DSC_0042.txt"))
    assert "camera, scanner or phone name" in ai.last_text
    assert "Name hints" not in ai.last_text


def test_year_in_the_name_is_the_date_when_the_text_has_none(setup):
    """Juegos-Nacionales_1997.txt with no date inside gives 1997."""
    replies = {"classify": "Documents", "summary": "A program.",
               "metadata": '{"source": null, "document_date": null}'}
    pipeline, ai = setup["build"](replies)
    doc = pipeline.classify_document(
        make_text_file(setup["drop_zone"], "Juegos-Nacionales_1997.txt"))
    assert doc.document_date == "1997"
    assert doc.date_source == "name"
    assert doc.filename.startswith("1997_")


def test_why_and_confidence_are_saved(setup):
    """The AI's reason and confidence go to the catalog."""
    replies = {"classify": "Press", "summary": "A story.",
               "metadata": '{"source": "El Mundo", "document_date": "1964",'
                           ' "topic": "Malta", "confidence": "medium",'
                           ' "folder_reason": "A news story about a race."}'}
    pipeline, ai = setup["build"](replies)
    doc = pipeline.classify_document(
        make_text_file(setup["drop_zone"], "a.txt"))
    assert doc.status == "Classified"
    assert doc.confidence == "medium"
    assert doc.folder_reason == "A news story about a race."
    assert doc.original_path == os.path.join("..", "drop_zone", "a.txt")


def test_low_confidence_goes_to_manual_review_with_the_reason(setup):
    """Low confidence needs a person; the note says why."""
    replies = {"classify": "Press", "summary": "A story.",
               "metadata": '{"source": "El Mundo", "confidence": "low",'
                           ' "folder_reason": "Could be sports or politics."}'}
    pipeline, ai = setup["build"](replies)
    doc = pipeline.classify_document(
        make_text_file(setup["drop_zone"], "a.txt"))
    assert doc.status == "Manual Review"
    assert doc.review_note == "Low confidence: Could be sports or politics."
    assert doc.confidence == "low"


def test_name_and_content_conflict_is_noted(setup):
    """When the name says one thing and the text another, the card says."""
    replies = {"classify": "Documents", "summary": "A recipe.",
               "metadata": '{"source": null, "confidence": "high",'
                           ' "folder_reason": "It is a recipe.",'
                           ' "name_hint_conflict": "The name says contract."}'}
    pipeline, ai = setup["build"](replies)
    doc = pipeline.classify_document(
        make_text_file(setup["drop_zone"], "contrato.txt"))
    assert doc.status == "Classified"
    assert doc.folder_reason == ("It is a recipe. Name and content "
                                 "disagree: The name says contract.")


@pytest.mark.parametrize("value, expected", [
    ("Press", "Press"), ("documents", "Documents"), ("Newspaper", "Documents"),
    (None, "Documents"),
])
def test_media_type_from_the_card(setup, value, expected):
    """Only Press and Documents are accepted; anything else is Documents."""
    replies = {"classify": value, "summary": "x",
               "metadata": '{"source": "S"}'}
    pipeline, ai = setup["build"](replies)
    doc = pipeline.classify_document(
        make_text_file(setup["drop_zone"], "a.txt"))
    assert doc.media_type == expected


def test_unknown_confidence_counts_as_medium(setup):
    """A confidence the AI made up does not block the file."""
    replies = {"classify": "Press", "summary": "x",
               "metadata": '{"source": "S", "confidence": "very sure"}'}
    pipeline, ai = setup["build"](replies)
    doc = pipeline.classify_document(
        make_text_file(setup["drop_zone"], "a.txt"))
    assert doc.confidence == "medium"
    assert doc.status == "Classified"
