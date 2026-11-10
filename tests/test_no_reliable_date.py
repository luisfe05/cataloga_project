"""No reliable date: an empty Date, and never a name that is only a number."""

import os
import re

import pytest

from backend.pipeline import naming
from backend.pipeline.classification_pipeline import (ClassificationPipeline,
                                                      choose_date)
from backend.pipeline.file_organizer import FileOrganizer
from tests.test_classification_pipeline import (  # noqa: F401
    FakeAI, fake_keyring, make_text_file, setup)
from tests.test_file_formats import mp3

FRONTEND = os.path.join(os.path.dirname(__file__), "..", "frontend")

# The AI read the file but found no topic, source or date.
NOTHING = '{"source": null, "document_date": null, "topic": null}'
# A topic and a source, no date.
NO_DATE = ('{"source": "Pier Digital", "document_date": null, '
           '"topic": "Pier cleanup"}')

# January 1, 2001: a disk date that must never be used.
OLD_DISK_DATE = 978307200


def read_in_place(setup, metadata, name):
    """Read one text file where it is, as a project without a Drop Zone."""
    replies = {"classify": "Documents", "summary": "A note.",
               "metadata": metadata}
    folder = setup["drop_zone"]
    pipeline = ClassificationPipeline(
        FakeAI(replies), setup["repo"], FileOrganizer(str(folder)),
        in_place=True)
    setup["repo"].save_naming_template(naming.NEW_PROJECT_TEMPLATE)
    path = make_text_file(folder, name)
    os.utime(path, (OLD_DISK_DATE, OLD_DISK_DATE))
    return pipeline.classify_document(path)


def test_the_disk_date_is_never_the_document_date(tmp_path):
    """Nothing reliable: no date and no source of a date."""
    path = tmp_path / "audio 12.mp3"
    path.write_bytes(b"x")
    assert choose_date(None, str(path)) == (None, None)
    # A date in the file's own metadata is kept.
    assert choose_date(None, str(path), meta_date="2026-08-01") == \
        ("2026-08-01", "metadata")


def test_a_file_without_a_date_has_an_empty_date(setup):
    """The Date field stays empty, whatever the disk says."""
    doc = read_in_place(setup, NOTHING, "notes.txt")
    assert doc.document_date is None and doc.date_source is None


def test_a_file_with_nothing_known_is_not_renamed(setup):
    """No topic, source or date: no rename is proposed in To Approve."""
    doc = read_in_place(setup, NOTHING, "audio 12.txt")
    assert doc.filename == "audio 12.txt"
    assert doc.proposed_name is None


def test_a_topic_without_a_date_still_gets_a_name(setup):
    """pier-cleanup_pier-digital: the name simply has no date part."""
    doc = read_in_place(setup, NO_DATE, "IMG_0007.txt")
    assert doc.proposed_name == "pier-cleanup_pier-digital.txt"
    assert doc.document_date is None


def test_a_recording_without_tags_keeps_its_name(setup, tmp_path):
    """No key for audio, no tags: no date, no 0005.mp3."""
    pipeline, ai = setup["build"]()
    path = mp3(tmp_path / "audio 12.mp3")
    os.utime(path, (OLD_DISK_DATE, OLD_DISK_DATE))
    doc = pipeline.classify_document(path)
    assert doc.filename == "audio 12.mp3"
    assert doc.document_date is None
    assert doc.status == "Manual Review" and doc.review_note


def test_a_recording_with_a_date_tag_keeps_it(setup, tmp_path):
    """The date in the file's metadata is kept, and used."""
    pipeline, ai = setup["build"]()
    path = mp3(tmp_path / "audio 14.mp3",
               {"title": "Harbor race", "date": "2026-08-01"})
    os.utime(path, (OLD_DISK_DATE, OLD_DISK_DATE))
    doc = pipeline.classify_document(path)
    assert doc.document_date == "2026-08-01"
    assert doc.date_source == "metadata"


@pytest.mark.parametrize("name, digits", [
    ("0005.mp3", True), ("0005_2.mp3", True), ("2026-07-15_0001.jpg", False),
    ("pier-cleanup.jpg", False), ("1998.pdf", True)])
def test_only_digits(name, digits):
    """A name that is only a number, with or without _2."""
    assert naming.only_digits(name) is digits


def test_no_proposed_name_is_only_digits(setup):
    """Across files with and without data, no name is a bare number."""
    names = [read_in_place(setup, NOTHING, "a.txt").filename,
             read_in_place(setup, NO_DATE, "b.txt").proposed_name]
    for name in names:
        assert not re.fullmatch(r"\d+(_\d+)?\.\w+", name or "")


def test_the_catalog_shows_a_dash_for_no_date():
    """An empty date reads "—", never a blank or the import day."""
    with open(os.path.join(FRONTEND, "js", "catalog.js"),
              encoding="utf-8") as file:
        catalog = file.read()
    assert 'makeCell(doc.document_date || "—", "nowrap")' in catalog


def test_the_chat_header_is_solid():
    """Nothing of the page shows through the header of Ask Cataloga."""
    with open(os.path.join(FRONTEND, "css", "main.css"),
              encoding="utf-8") as file:
        css = file.read()
    header = re.search(r"\.chat-header \{([^}]*)\}", css).group(1)
    assert "background: var(--color-deep-space);" in header
    panel = re.search(r"\.chat-panel \{([^}]*)\}", css).group(1)
    assert "backdrop-filter: blur" in panel
