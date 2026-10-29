"""Tests for Office files, photos, scanned PDFs, and audio and video."""

import base64
import io
import json
import wave
import zipfile

import pytest
from PIL import Image
from pypdf import PdfWriter

from backend.db.catalog_repository import CatalogRepository
from backend.db.schema import init_db
from backend.pipeline import archive_rules, file_readers
from backend.pipeline.ai_providers import base
from backend.pipeline.ai_providers.base import AIProviderClient
from backend.pipeline.ai_providers.ollama_cloud import OllamaCloudClient
from backend.pipeline.classification_pipeline import ClassificationPipeline
from backend.pipeline.file_organizer import FileOrganizer

METADATA = json.dumps({"source": "Harbor Business Journal",
                       "document_date": "2026-06-11", "topic": "Tower top",
                       "keywords": ["tower", "harbor"]})
IMAGE_ANSWER = json.dumps({"text": "Tower reaches its top floor",
                           "description": "A newspaper page."})


class FakeAI(AIProviderClient):
    """Fake AI that answers text and, if allowed, image requests."""

    def __init__(self, images=True, image_answer=IMAGE_ANSWER):
        super().__init__(provider_name="fake", model="fake-model")
        self.retry_delay = 0
        self.images = images
        self.image_answer = image_answer
        self.text_calls = 0
        self.image_calls = []

    @property
    def supports_images(self):
        return self.images

    def send_prompt(self, system_prompt, text):
        self.text_calls += 1
        if system_prompt == base.CLASSIFICATION_PROMPT:
            return "Documents"
        if system_prompt == base.SUMMARY_PROMPT:
            return "A short summary."
        return METADATA

    def send_images(self, prompt, image_uris):
        self.image_calls.append(image_uris)
        if self.image_answer is None:
            raise RuntimeError("the model is down")
        return self.image_answer


@pytest.fixture(autouse=True)
def test_key(monkeypatch):
    """Give the fake AI a key so it is allowed to answer."""
    monkeypatch.setattr(base.keyring, "get_password",
                        lambda service, name: "test-key")


@pytest.fixture
def setup(tmp_path):
    """A pipeline builder with a temp catalog, archive, and Drop Zone."""
    db_path = str(tmp_path / "catalog.db")
    init_db(db_path)
    repo = CatalogRepository(db_path)
    organizer = FileOrganizer(str(tmp_path / "archive"))
    drop_zone = tmp_path / "drop"
    drop_zone.mkdir()

    def build(ai):
        return ClassificationPipeline(ai, repo, organizer, owner="luis")

    return {"build": build, "drop": drop_zone}


def office_file(path, parts):
    """Write a small Office file (a zip of XML parts)."""
    with zipfile.ZipFile(path, "w") as archive:
        for name, xml in parts.items():
            archive.writestr(name, xml)
    return str(path)


W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
S = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
A = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'


def docx(path):
    """A Word file with two paragraphs."""
    return office_file(path, {"word/document.xml": (
        '<w:document ' + W + '><w:body><w:p><w:r><w:t>Lease </w:t></w:r>'
        '<w:r><w:t>agreement</w:t></w:r></w:p><w:p><w:r><w:t>Pier 9'
        '</w:t></w:r></w:p></w:body></w:document>')})


# --- Office files ---

def test_docx_text(tmp_path):
    """Word paragraphs come out one per line."""
    assert file_readers.office_text(docx(tmp_path / "a.docx")) == \
        "Lease agreement\nPier 9"


def test_xlsx_text(tmp_path):
    """Excel cells come out row by row, with shared and inline text."""
    path = office_file(tmp_path / "a.xlsx", {
        "xl/sharedStrings.xml": '<sst ' + S + '><si><t>Budget</t></si></sst>',
        "xl/worksheets/sheet1.xml": (
            '<worksheet ' + S + '><sheetData><row><c t="s"><v>0</v></c>'
            '<c><v>2026</v></c></row><row><c t="inlineStr"><is><t>Total</t>'
            '</is></c></row></sheetData></worksheet>')})
    assert file_readers.office_text(path) == "Budget | 2026\nTotal"


def test_pptx_text_in_slide_order(tmp_path):
    """Slides are read by their number, so slide10 comes after slide2."""
    def slide(text):
        return '<p:sld ' + A + ' xmlns:p="p"><a:p><a:t>' + text + \
            '</a:t></a:p></p:sld>'
    path = office_file(tmp_path / "a.pptx", {
        "ppt/slides/slide10.xml": slide("Ten"),
        "ppt/slides/slide2.xml": slide("Two")})
    assert file_readers.office_text(path) == "Two\nTen"


def test_broken_office_file_gives_no_text(tmp_path):
    """A damaged file is treated as unreadable."""
    path = tmp_path / "bad.docx"
    path.write_text("not a zip")
    assert file_readers.office_text(str(path)) == ""


def test_docx_is_cataloged_like_a_pdf(setup):
    """A Word file is classified, summarized and renamed from its text."""
    ai = FakeAI(images=False)
    doc = setup["build"](ai).classify_document(docx(setup["drop"] / "a.docx"))
    assert doc.status == "Classified"
    assert doc.summary == "A short summary."
    assert doc.filename.endswith(".docx")
    assert ai.text_calls == 3


# --- Photos ---

def png(path, size=(3000, 1000), transparent=True):
    """Write a PNG; transparent ones have no background."""
    color = (0, 0, 0, 0) if transparent else (200, 30, 30, 255)
    Image.new("RGBA", size, color).save(path)
    return str(path)


def sent_image(uri):
    """Open the image the pipeline sent to the AI."""
    assert uri.startswith("data:image/jpeg;base64,")
    return Image.open(io.BytesIO(base64.b64decode(uri.split(",", 1)[1])))


def test_photo_is_read_by_the_ai(setup):
    """A photo is sent once, shrunk to 1600 px, on white, as JPEG."""
    ai = FakeAI()
    doc = setup["build"](ai).classify_document(png(setup["drop"] / "p.png"))
    image = sent_image(ai.image_calls[0][0])
    assert max(image.size) == 1600
    assert image.getpixel((10, 10))[0] > 240
    assert doc.media_type == "Photos"
    assert doc.summary == "A short summary."
    # Only the summary is needed for a photo to be Classified.
    assert doc.status == "Classified"
    assert "tower-top" in doc.filename


def test_photo_failure_goes_to_manual_review(setup):
    """If the AI cannot read a photo, it waits for a person."""
    ai = FakeAI(image_answer=None)
    doc = setup["build"](ai).classify_document(png(setup["drop"] / "p.png"))
    assert doc.status == "Manual Review"
    assert doc.review_note == archive_rules.IMAGE_NOTE
    assert ai.text_calls == 0


def test_photo_without_a_vision_model_is_not_read(setup):
    """With a model that takes no images, photos are cataloged as before."""
    ai = FakeAI(images=False)
    doc = setup["build"](ai).classify_document(png(setup["drop"] / "p.png"))
    assert ai.image_calls == []
    assert doc.media_type == "Photos"
    assert doc.status == "Manual Review"


def test_photo_date_from_exif(tmp_path):
    """The date the photo was taken comes from its EXIF data."""
    path = str(tmp_path / "p.jpg")
    exif = Image.Exif()
    exif[306] = "2026:07:15 10:30:00"
    Image.new("RGB", (10, 10)).save(path, exif=exif)
    assert file_readers.photo_date(path) == "2026-07-15"


def test_only_gemma_accepts_images():
    """The text backup model does not get images."""
    assert OllamaCloudClient("gemma4:31b").supports_images
    assert not OllamaCloudClient("nemotron-3-nano:30b").supports_images


# --- Scanned PDFs ---

def blank_pdf(path, pages):
    """Write a PDF with pages but no text, like a scan."""
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    with open(path, "wb") as file:
        writer.write(file)
    return str(path)


def test_scanned_pdf_reads_at_most_3_pages(setup):
    """A PDF without text sends its first 3 pages, on white."""
    ai = FakeAI()
    doc = setup["build"](ai).classify_document(
        blank_pdf(setup["drop"] / "scan.pdf", 5))
    assert len(ai.image_calls[0]) == 3
    assert sent_image(ai.image_calls[0][0]).getpixel((5, 5))[0] > 240
    assert doc.status == "Classified"
    assert doc.media_type == "Documents"


def test_scanned_pdf_failure_goes_to_manual_review(setup):
    """No backup model for images: a failed scan waits for a person."""
    ai = FakeAI(image_answer="I cannot read this.")
    doc = setup["build"](ai).classify_document(
        blank_pdf(setup["drop"] / "scan.pdf", 1))
    assert doc.status == "Manual Review"
    assert doc.review_note == archive_rules.SCAN_NOTE


# --- Audio, video, and big files ---

def test_audio_goes_to_manual_review_with_its_length(setup):
    """Audio is not read; its length is noted when it can be found."""
    path = str(setup["drop"] / "a.wav")
    with wave.open(path, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b"\0\0" * 8000 * 65)
    ai = FakeAI()
    doc = setup["build"](ai).classify_document(path)
    assert doc.media_type == "Audio"
    assert doc.status == "Manual Review"
    assert doc.review_note == archive_rules.MEDIA_NOTE + ". Duration 1:05"
    assert ai.text_calls == 0 and ai.image_calls == []


def test_video_length_from_its_header(tmp_path):
    """The mvhd box of an .mp4 gives the length without a library."""
    # Version 0: flags, two dates, time scale 1000, duration 30500.
    box = (b"\0\0\0\0" + b"\0" * 8 + (1000).to_bytes(4, "big") +
           (30500).to_bytes(4, "big") + b"\0" * 16)
    path = tmp_path / "v.mp4"
    path.write_bytes(b"\0\0\0\x08moov" + b"\0\0\0\x40mvhd" + box)
    assert file_readers.media_length(str(path)) == "0:31"


def test_unknown_length_keeps_the_plain_reason(setup):
    """Without a readable length, the reason is the plain sentence."""
    path = setup["drop"] / "clip.mov"
    path.write_bytes(b"not a real video")
    doc = setup["build"](FakeAI()).classify_document(str(path))
    assert doc.media_type == "Video"
    assert doc.review_note == archive_rules.MEDIA_NOTE


def test_big_file_is_not_read(setup, monkeypatch):
    """A file over the size limit goes to Manual Review unread."""
    monkeypatch.setattr(file_readers, "MAX_READ_BYTES", 10)
    ai = FakeAI()
    doc = setup["build"](ai).classify_document(docx(setup["drop"] / "a.docx"))
    assert doc.review_note == archive_rules.TOO_BIG_NOTE
    assert doc.status == "Manual Review"
    assert ai.text_calls == 0
