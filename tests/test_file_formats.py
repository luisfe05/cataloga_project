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
from backend.pipeline import archive_rules, file_metadata, file_readers
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


# --- Metadata inside files, and where the date came from ---

def pdf_with_metadata(path, text_page=True):
    """A one-page PDF with a title, an author and a creation date."""
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.add_metadata({"/Title": "Pier 9 lease", "/Author": "Ana Ruiz",
                         "/Subject": "Warehouse lease",
                         "/Keywords": "lease, pier",
                         "/CreationDate": "D:20260301090000",
                         "/Producer": "Canon iR-ADV scanner"})
    with open(path, "wb") as file:
        writer.write(file)
    return str(path)


def test_pdf_metadata_is_read(tmp_path):
    """Title, author, subject, keywords and date come from the PDF."""
    meta = file_metadata.pdf_metadata(pdf_with_metadata(tmp_path / "a.pdf"))
    assert meta["title"] == "Pier 9 lease"
    assert meta["author"] == "Ana Ruiz"
    assert meta["subject"] == "Warehouse lease"
    assert meta["keywords"] == "lease, pier"
    assert meta["created"] == "2026-03-01"


def test_pdf_metadata_goes_to_the_ai_and_gives_the_date(setup):
    """The AI sees the metadata; with no date in the text it is used."""
    ai = FakeAI(image_answer=json.dumps({"text": "Lease text", "description":
                                         None}))
    ai_metadata = json.dumps({"source": "Harbor Law Group", "topic": "Lease",
                              "document_date": None})
    seen = []

    def send(system_prompt, text):
        seen.append(text)
        if system_prompt == base.SUMMARY_PROMPT:
            return "A lease."
        if system_prompt == base.CLASSIFICATION_PROMPT:
            return "Documents"
        return ai_metadata
    ai.send_prompt = send
    doc = setup["build"](ai).classify_document(
        pdf_with_metadata(setup["drop"] / "scan.pdf"))
    assert "Title: Pier 9 lease" in seen[0]
    assert "Author: Ana Ruiz" in seen[0]
    assert doc.document_date == "2026-03-01"
    assert doc.date_source == "metadata"


def test_generic_docx_author_is_ignored(tmp_path):
    """"Microsoft Office User" and "Document1" say nothing, so they go."""
    path = office_file(tmp_path / "a.docx", {"docProps/core.xml": (
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/'
        'package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:dcterms="http://purl.org/dc/terms/"><dc:title>Document1'
        '</dc:title><dc:creator>Microsoft Office User</dc:creator>'
        '<dcterms:created>2026-02-14T10:00:00Z</dcterms:created>'
        '</cp:coreProperties>')})
    meta = file_metadata.office_metadata(path)
    assert meta["author"] is None
    assert meta["title"] is None
    assert meta["created"] == "2026-02-14"


@pytest.mark.parametrize("value", ["Admin", "Untitled 3", "Canon scanner",
                                   "scan_0047.pdf", "0001"])
def test_useless_values(value):
    """Program, scanner, file name and placeholder values are dropped."""
    assert file_metadata.useful(value, name_like=True) is None


def mp3(path, tags=None):
    """Write a tiny MP3 (silent frames), with ID3 tags if given."""
    # One MPEG-1 Layer III frame header (128 kbps, 44.1 kHz) and padding.
    frame = b"\xff\xfb\x90\x00" + b"\0" * 413
    path.write_bytes(frame * 40)
    if tags:
        from mutagen.easyid3 import EasyID3
        audio = EasyID3()
        for key, value in tags.items():
            audio[key] = value
        audio.save(str(path))
    return str(path)


def test_tagged_mp3_gets_a_name_and_a_source(setup):
    """A title and a date are enough to name an audio file."""
    ai = FakeAI()
    path = mp3(setup["drop"] / "audio 12.mp3",
               {"title": "Interview with a ferry captain",
                "artist": "Northside Podcast", "album": "Season 3",
                "date": "2026-08-01"})
    doc = setup["build"](ai).classify_document(path)
    assert doc.media_type == "Audio"
    assert doc.document_date == "2026-08-01"
    assert doc.date_source == "metadata"
    assert doc.summary == "A short summary."
    assert ai.image_calls == []
    assert "tower-top" in doc.filename


def test_mp3_without_tags_goes_to_manual_review(setup):
    """No useful metadata: Manual Review, with the file date."""
    ai = FakeAI()
    doc = setup["build"](ai).classify_document(
        mp3(setup["drop"] / "audio 13.mp3"))
    assert doc.status == "Manual Review"
    assert doc.review_note.startswith(archive_rules.MEDIA_NOTE)
    assert doc.date_source == "file"
    assert ai.text_calls == 0


def test_photo_date_comes_first(setup):
    """For photos, the EXIF date wins over a date in the content."""
    path = str(setup["drop"] / "p.jpg")
    exif = Image.Exif()
    exif[306] = "2025:12:24 18:00:00"
    Image.new("RGB", (20, 20), (255, 255, 255)).save(path, exif=exif)
    doc = setup["build"](FakeAI()).classify_document(path)
    assert doc.document_date == "2025-12-24"
    assert doc.date_source == "photo"


def test_content_date_wins_for_documents(setup):
    """A date written in the document beats the metadata date."""
    doc = setup["build"](FakeAI(images=False)).classify_document(
        docx(setup["drop"] / "a.docx"))
    assert doc.document_date == "2026-06-11"
    assert doc.date_source == "content"
