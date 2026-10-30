"""Tests for the formats read by content: text and code, design, zips."""

import base64
import io
import json
import zipfile

import pytest
from PIL import Image

from backend.pipeline import archive_rules, file_readers
# The fixtures come along with the helpers.
from tests.test_file_formats import (  # noqa: F401
    FakeAI, METADATA, setup, test_key)


@pytest.mark.parametrize("name, data, expected", [
    ("site.css", b"body { color: red }", True),
    ("app.py", "print('hola')\n# año\n".encode("utf-8"), True),
    ("notas", b"Notas del rodaje", True),
    ("old.txt", "Año de la niña".encode("latin-1"), True),
    ("empty.txt", b"", False),
    ("program.bin", b"\x00\x01\x02MZ", False),
    ("photo.raw", bytes(range(256)) * 4, False),
])
def test_is_text_file_looks_at_the_bytes(tmp_path, name, data, expected):
    """Text and code are known by their bytes, whatever the name says."""
    path = tmp_path / name
    path.write_bytes(data)
    assert file_readers.is_text_file(str(path)) is expected


def test_text_extract_is_cut(tmp_path):
    """Only the start of a big text file goes to the AI."""
    path = tmp_path / "big.log"
    path.write_text("x" * 100000)
    assert len(file_readers.text_extract(str(path))) == \
        file_readers.TEXT_EXTRACT_CHARS


def test_code_is_cataloged_by_content(setup):
    """A .js file is read as text and classified like any document."""
    ai = FakeAI()
    path = setup["drop"] / "main.js"
    path.write_text("function hello() { return 'world'; }")
    doc = setup["build"](ai).classify_document(str(path))
    assert doc.status == "Classified"
    assert doc.summary == "A short summary."
    assert doc.media_type == "Documents"
    # Code is a document: the summary and the metadata, no type request.
    assert ai.text_calls == 2


def test_zip_listing_never_unpacks(tmp_path):
    """The names and the total size are listed; nothing is written."""
    path = tmp_path / "fotos.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Fotos/a.jpg", b"x" * 1000)
        archive.writestr("Fotos/b.jpg", b"y" * 1000)
        archive.writestr("Fotos/.DS_Store", b"")
    listing = file_readers.zip_listing(str(path))
    assert listing.startswith("Compressed file with 2 files")
    assert "Fotos/a.jpg" in listing and ".DS_Store" not in listing
    assert sorted(p.name for p in tmp_path.iterdir()) == ["fotos.zip"]


def test_zip_listing_is_capped(tmp_path):
    """Sixty names: fifty are listed and the rest are counted."""
    path = tmp_path / "many.zip"
    with zipfile.ZipFile(path, "w") as archive:
        for i in range(60):
            archive.writestr("f{:02d}.txt".format(i), b"x")
    listing = file_readers.zip_listing(str(path))
    assert "f49.txt" in listing and "f50.txt" not in listing
    assert "... and 10 more" in listing


def test_zip_is_cataloged_from_its_listing(setup):
    """The AI reads the list of files; the zip stays packed."""
    ai = FakeAI()
    path = setup["drop"] / "entrevistas.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("entrevista_1.mp3", b"x")
    seen = []
    original = ai.send_prompt

    def send(system_prompt, text):
        seen.append(text)
        return original(system_prompt, text)
    ai.send_prompt = send
    doc = setup["build"](ai).classify_document(str(path))
    assert "entrevista_1.mp3" in seen[0]
    assert doc.status == "Classified"


def test_psd_is_read_as_a_picture(setup):
    """Photoshop's flattened picture goes to the vision model."""
    ai = FakeAI()
    path = setup["drop"] / "poster.psd"
    # Pillow reads PSD but cannot write it: a PNG under the name will do,
    # because Pillow opens files by their bytes, not their name.
    Image.new("RGB", (300, 200), (10, 200, 10)).save(str(path), format="PNG")
    doc = setup["build"](ai).classify_document(str(path))
    assert len(ai.image_calls) == 1
    assert doc.status == "Classified"


def test_sketch_preview_is_read(setup):
    """A Sketch file is a zip with a preview inside."""
    ai = FakeAI()
    path = setup["drop"] / "app.sketch"
    buffer = io.BytesIO()
    Image.new("RGB", (100, 100)).save(buffer, format="PNG")
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("previews/preview.png", buffer.getvalue())
    setup["build"](ai).classify_document(str(path))
    assert len(ai.image_calls) == 1


def test_indd_uses_its_xmp_when_there_is_no_picture(setup):
    """An InDesign file with XMP but no thumbnail: title and author."""
    ai = FakeAI()
    path = setup["drop"] / "libro.indd"
    xmp = ('<x:xmpmeta><dc:title><rdf:Alt><rdf:li xml:lang="x-default">'
           'Libro del Delfin</rdf:li></rdf:Alt></dc:title><dc:creator>'
           '<rdf:Seq><rdf:li>Luis</rdf:li></rdf:Seq></dc:creator></x:xmpmeta>')
    path.write_bytes(b"\x00\x01" + xmp.encode("utf-8") + b"\x00")
    seen = []
    original = ai.send_prompt

    def send(system_prompt, text):
        seen.append(text)
        return original(system_prompt, text)
    ai.send_prompt = send
    doc = setup["build"](ai).classify_document(str(path))
    assert ai.image_calls == []
    assert "Title: Libro del Delfin" in seen[0]
    assert "Author: Luis" in seen[0]
    assert doc.status == "Classified"


def test_xmp_thumbnail_is_decoded():
    """A base64 JPEG inside XMP becomes a picture."""
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8)).save(buffer, format="JPEG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    data = ("<xapGImg:image>" + encoded + "</xapGImg:image>").encode()
    assert file_readers.xmp_thumbnail(data).size == (8, 8)


def test_unknown_format_is_cataloged_by_its_name(setup):
    """A .xyz file: the name, folder and neighbors go to the AI."""
    ai = FakeAI()
    (setup["drop"] / "guion_v2.docx").write_bytes(b"x")
    path = setup["drop"] / "proyecto_final.xyz"
    path.write_bytes(b"\x00\x01\x02\x03" * 100)
    seen = []
    original = ai.send_prompt

    def send(system_prompt, text):
        seen.append(text)
        return original(system_prompt, text)
    ai.send_prompt = send
    doc = setup["build"](ai).classify_document(str(path))
    assert seen[0].startswith("File name: proyecto_final.xyz")
    assert "Other files in that folder: guion_v2.docx" in seen[0]
    assert doc.status == "Classified"
    assert doc.media_type == "Documents"
    assert doc.review_note is None


def test_secret_like_and_big_files_still_follow_their_rules(setup,
                                                            monkeypatch):
    """A design file over the size limit is not opened: name only."""
    ai = FakeAI()
    path = setup["drop"] / "huge.psd"
    Image.new("RGB", (50, 50)).save(str(path), format="PNG")
    monkeypatch.setattr(file_readers, "MAX_READ_BYTES", 10)
    doc = setup["build"](ai).classify_document(str(path))
    assert ai.image_calls == []
    assert doc.review_note == archive_rules.TOO_BIG_NOTE
