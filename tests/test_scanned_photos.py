"""Tests for scanned photos: corners, rotation, stamp dates, EXIF rules."""

import base64
import io
import json

import pytest
from PIL import Image, ImageDraw

from backend.pipeline import archive_rules, file_readers
from backend.pipeline.ai_providers import base
# The fixtures come along with the helpers.
from tests.test_file_formats import FakeAI, setup, test_key  # noqa: F401


@pytest.mark.parametrize("text, order, expected", [
    ("11 13 '97", "month", "1997-11-13"),
    ("11 13 '97", "day", "1997-11-13"),
    ("03 04 '97", "month", "1997-03-04"),
    ("03 04 '97", "day", "1997-04-03"),
    ("13/11/1997", "month", "1997-11-13"),
    ("1997-11-13", "day", "1997-11-13"),
    ("Nov 13 1997", "month", "1997-11-13"),
    ("13 nov 97", "day", "1997-11-13"),
    ("noviembre de 1997", "month", "1997-11"),
    ("11/97", "month", "1997-11"),
    ("verano de 1997", "month", "1997"),
    ("no date here", "month", None),
    (None, "month", None),
])
def test_stamp_date(text, order, expected):
    """Camera stamps and handwritten dates, with the precision they have."""
    assert archive_rules.stamp_date(text, order) == expected


@pytest.mark.parametrize("path, year", [
    ("/a/EVENTOS/Trialo-Isla-Verde_1998/IMG_0001.jpg", "1998"),
    ("/a/Juegos_1997_3.tif", "1997"),
    ("/a/b/IMG_0001.jpg", None),
    ("/a/2026-07-15_scan.pdf", "2026"),
])
def test_year_in_path(path, year):
    """A year in the file name or its folders is found."""
    assert archive_rules.year_in_path(path) == year


def stamped_photo(path, rotation=0, size=(2400, 1600)):
    """A photo with 11 13 '97 drawn in a corner, maybe lying on its side."""
    image = Image.new("RGB", size, (200, 180, 150))
    draw = ImageDraw.Draw(image)
    draw.text((size[0] - 110, size[1] - 30), "11 13 '97", fill=(255, 120, 0))
    if rotation:
        image = image.rotate(rotation, expand=True)
    image.save(path)
    return str(path)


def sent_image(uri):
    """Open a data URI as a Pillow image."""
    return Image.open(io.BytesIO(base64.b64decode(uri.split(",", 1)[1])))


def test_photo_views_are_the_photo_and_four_corners(tmp_path):
    """Five images: the whole photo at 1600 px and each corner enlarged."""
    views = file_readers.photo_views(stamped_photo(tmp_path / "p.jpg"))
    assert len(views) == 5
    assert max(sent_image(views[0]).size) == 1600
    corner = sent_image(views[1])
    assert max(corner.size) == file_readers.CORNER_SIDE
    # The bottom-right corner holds the stamp; it is enlarged, not shrunk.
    assert sent_image(views[4]).size == corner.size


def test_photo_views_can_be_turned(tmp_path):
    """A rotation turns the copy that is sent, never the file."""
    path = stamped_photo(tmp_path / "p.jpg", rotation=90)
    before = open(path, "rb").read()
    upright = sent_image(file_readers.photo_views(path, 270)[0])
    assert upright.width > upright.height
    assert open(path, "rb").read() == before


def test_big_scan_is_opened_and_shrunk(tmp_path, monkeypatch):
    """A 1200 dpi scan over 50 MB is sent at 1600 px, not refused."""
    path = str(tmp_path / "scan.tif")
    Image.new("RGB", (4000, 3000)).save(path)
    monkeypatch.setattr(file_readers, "MAX_READ_BYTES", 1000)
    views = file_readers.photo_views(path)
    assert max(sent_image(views[0]).size) == 1600


def exif_photo(path, make=None, software=None, taken="1999:05:06 10:00:00"):
    """A photo with EXIF: a camera's, or a scanner's."""
    exif = Image.Exif()
    if make:
        exif[271] = make
    if software:
        exif[305] = software
    exif[306] = "2026:07:15 10:30:00"
    exif.get_ifd(0x8769)[36867] = taken
    Image.new("RGB", (10, 10)).save(path, exif=exif)
    return str(path)


def test_camera_exif_date_counts_but_a_scanners_does_not(tmp_path):
    """Only a camera's DateTimeOriginal is the day the photo was taken."""
    assert file_readers.photo_date(exif_photo(tmp_path / "c.jpg",
                                              make="Canon")) == "1999-05-06"
    assert file_readers.photo_date(exif_photo(tmp_path / "s.jpg")) is None
    assert file_readers.photo_date(exif_photo(
        tmp_path / "e.jpg", make="EPSON", software="Epson Scan 2")) is None


class StampAI(FakeAI):
    """A vision AI that reads the stamp only once the photo is upright."""

    def __init__(self, rotation=0, printed="11 13 '97", handwritten=None):
        super().__init__()
        self.rotation = rotation
        self.printed = printed
        self.handwritten = handwritten
        self.prompts = []

    def send_prompt(self, system_prompt, text):
        # No date in the metadata: the photo's own dates decide.
        self.text_calls += 1
        if system_prompt == base.SUMMARY_PROMPT:
            return "Children at a track meet."
        if system_prompt == base.CLASSIFICATION_PROMPT:
            return "Photos"
        return json.dumps({"source": None, "document_date": None,
                           "topic": "Juegos Nacionales"})

    def send_images(self, prompt, image_uris):
        self.image_calls.append(image_uris)
        self.prompts.append(prompt)
        turned = sent_image(image_uris[0]).width > sent_image(
            image_uris[0]).height
        if self.rotation and not turned:
            return json.dumps({"rotation": self.rotation,
                               "printed_date": None, "description": "?"})
        return json.dumps({"rotation": 0, "printed_date": self.printed,
                           "handwritten_date": self.handwritten,
                           "text": "MARINA",
                           "description": "Children at a track meet."})


def test_sideways_photo_is_turned_and_dated_from_its_stamp(setup):
    """Luis's 1997 photo: lying on its side, stamp 11 13 '97, no EXIF."""
    path = stamped_photo(setup["drop"] / "Juegos_1997_1.tif", rotation=90)
    ai = StampAI(rotation=270)
    doc = setup["build"](ai).classify_document(path)
    assert ai.prompts[0] == base.PHOTO_PROMPT
    assert len(ai.image_calls) == 2
    assert len(ai.image_calls[0]) == 5
    assert doc.document_date == "1997-11-13"
    assert doc.date_source == "photo stamp"
    assert doc.media_type == "Photos"
    assert doc.status == "Classified"


def test_handwritten_date_counts_when_nothing_is_printed(setup):
    """A note on the back, 'verano 1997', gives the year."""
    path = stamped_photo(setup["drop"] / "p.jpg")
    ai = StampAI(printed=None, handwritten="verano 1997")
    doc = setup["build"](ai).classify_document(path)
    assert doc.document_date == "1997"
    assert doc.date_source == "photo stamp"


def test_stamp_order_follows_the_setting(setup):
    """03 04 '97 is April 3 with Day first."""
    pipeline = setup["build"](StampAI(printed="03 04 '97"))
    pipeline.db.save_config_value("stamp_date_order", "day")
    doc = pipeline.classify_document(stamped_photo(setup["drop"] / "p.jpg"))
    assert doc.document_date == "1997-04-03"


def test_year_in_the_name_when_the_photo_has_no_stamp(setup):
    """No stamp and a scanner's EXIF: the _1997 in the name gives 1997."""
    exif = Image.Exif()
    exif[306] = "2026:07:15 10:30:00"
    path = str(setup["drop"] / "Juegos-Nacionales_1997_2.jpg")
    Image.new("RGB", (40, 40)).save(path, exif=exif)
    doc = setup["build"](StampAI(printed=None)).classify_document(path)
    assert doc.document_date == "1997"
    assert doc.date_source == "name"
    assert doc.filename.startswith("1997")


def test_stamp_wins_over_a_cameras_exif(setup):
    """A stamp on the photo beats the EXIF date."""
    path = exif_photo(setup["drop"] / "c.jpg", make="Canon")
    doc = setup["build"](StampAI()).classify_document(path)
    assert doc.document_date == "1997-11-13"
    assert doc.date_source == "photo stamp"


def test_settings_save_the_stamp_order(flask_client):
    """PUT /settings keeps the order and refuses other values."""
    response = flask_client.put("/settings", json={
        "research_name": "Research", "stamp_date_order": "day"})
    assert response.status_code == 200
    assert response.get_json()["stamp_date_order"] == "day"
    response = flask_client.put("/settings", json={
        "research_name": "Research", "stamp_date_order": "year"})
    assert response.get_json()["error"]["code"] == "invalid_stamp_order"
