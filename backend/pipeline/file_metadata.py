"""Metadata stored inside files: documents, audio and video."""

import os
import re
import zipfile
from datetime import datetime
from xml.etree import ElementTree

import mutagen
from pypdf import PdfReader

from backend.pipeline import file_readers

# Values that say nothing about who made the file or what it is.
GENERIC_VALUES = {
    "microsoft office user", "admin", "administrator", "user", "owner",
    "author", "unknown", "untitled", "document", "document1", "book1",
    "sheet1", "presentation", "presentation1", "default", "guest", "none",
}

# Programs and scanners that often appear as the author or the title.
PROGRAM_WORDS = re.compile(
    r"\b(microsoft|word|excel|powerpoint|office|adobe|acrobat|pdf|"
    r"libreoffice|openoffice|google docs|keynote|preview|quartz|scan|"
    r"scanner|scansnap|canon|epson|xerox|ricoh|kyocera|brother|fujitsu|"
    r"konica|lexmark|ghostscript|itext|photoshop|lightroom|iphone|android|"
    r"garageband|audacity|premiere|final cut|imovie|handbrake|ffmpeg|lavf|"
    r"quicktime)\b", re.IGNORECASE)

# A title like "scan_0047.pdf" is only a file name.
FILE_NAME = re.compile(r"\.[a-z0-9]{2,4}$", re.IGNORECASE)

DATE_PATTERN = re.compile(r"(\d{4})(?:-?(\d{2}))?(?:-?(\d{2}))?")

DC = "{http://purl.org/dc/elements/1.1/}"
CP = ("{http://schemas.openxmlformats.org/package/2006/metadata/"
      "core-properties}")
DCTERMS = "{http://purl.org/dc/terms/}"


def useful(value, name_like=False):
    """Return a cleaned value, or None if it says nothing useful."""
    if isinstance(value, (list, tuple)):
        value = value[0] if value else None
    if not isinstance(value, str):
        return None
    value = " ".join(value.split())
    lowered = value.lower()
    if not value or lowered in GENERIC_VALUES or \
            lowered.startswith("untitled"):
        return None
    # Only digits and symbols, like "0001" or "---".
    if not re.search(r"[^\W\d_]", value):
        return None
    if name_like and (PROGRAM_WORDS.search(value) or FILE_NAME.search(value)):
        return None
    return value[:200]


def clean_date(value):
    """Return a date as YYYY-MM-DD, YYYY-MM or YYYY, or None."""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, (list, tuple)):
        value = value[0] if value else None
    if not isinstance(value, str):
        return None
    match = DATE_PATTERN.search(value)
    if not match or not 1800 < int(match.group(1)) < 2200:
        return None
    return "-".join(part for part in match.groups() if part)


def pdf_metadata(file_path):
    """Return the title, author, subject, keywords and dates of a PDF."""
    try:
        info = PdfReader(file_path).metadata
    except Exception:
        # pypdf raises many kinds of errors for damaged files.
        return {}
    if not info:
        return {}
    try:
        created, modified = info.creation_date, info.modification_date
    except (ValueError, TypeError):
        created, modified = None, None
    return {
        "title": useful(info.title, name_like=True),
        "author": useful(info.author, name_like=True),
        "subject": useful(info.subject),
        "keywords": useful(info.get("/Keywords")),
        "created": clean_date(created),
        "modified": clean_date(modified),
    }


def office_metadata(file_path):
    """Return the same fields from a Word, Excel or PowerPoint file."""
    try:
        with zipfile.ZipFile(file_path) as archive:
            root = file_readers.read_zip_xml(archive, "docProps/core.xml")
    except (zipfile.BadZipFile, ElementTree.ParseError, OSError):
        return {}
    if root is None:
        return {}

    def field(tag):
        found = root.find(tag)
        return found.text if found is not None else None

    return {
        "title": useful(field(DC + "title"), name_like=True),
        "author": useful(field(DC + "creator"), name_like=True),
        "subject": useful(field(DC + "subject")),
        "keywords": useful(field(CP + "keywords")),
        "created": clean_date(field(DCTERMS + "created")),
        "modified": clean_date(field(DCTERMS + "modified")),
    }


def document_metadata(file_path):
    """Return the metadata of a PDF or Office file, or {} for others."""
    extension = os.path.splitext(file_path)[1].lower()
    if extension == ".pdf":
        return pdf_metadata(file_path)
    if extension in file_readers.OFFICE_EXTENSIONS:
        return office_metadata(file_path)
    return {}


def media_comment(file_path):
    """Return the first comment tag of an audio or video file."""
    try:
        tags = mutagen.File(file_path).tags
    except Exception:
        return None
    if not tags:
        return None
    for key in tags.keys():
        # ID3 uses COMM frames; MP4 uses ©cmt; others use "comment".
        if key.startswith("COMM") or key in ("\xa9cmt", "comment"):
            value = tags[key]
            text = getattr(value, "text", value)
            return useful(text)
    return None


# Easy names for the ID3 frames a .wav can carry.
ID3_FRAMES = {"title": "TIT2", "artist": "TPE1", "album": "TALB",
              "date": "TDRC"}


def media_metadata(file_path):
    """Return the title, artist, album, date, comment and length."""
    try:
        audio = mutagen.File(file_path, easy=True)
    except Exception:
        # mutagen raises its own errors for files it cannot parse.
        audio = None
    tags = audio.tags if audio is not None and audio.tags else {}
    # A .wav keeps raw ID3 frames even with easy=True; name them.
    if tags and "TIT2" in tags or tags and "TPE1" in tags:
        tags = {name: [str(frame)] for name, key in ID3_FRAMES.items()
                if key in tags for frame in [tags[key]]}
    length = None
    if audio is not None and getattr(audio.info, "length", 0):
        seconds = int(audio.info.length + 0.5)
        length = "{}:{:02d}".format(seconds // 60, seconds % 60)
    return {
        "title": useful(tags.get("title"), name_like=True),
        "author": useful(tags.get("artist"), name_like=True),
        "album": useful(tags.get("album")),
        "date": clean_date(tags.get("date")),
        "comment": media_comment(file_path),
        "length": length or file_readers.media_length(file_path),
    }


def metadata_text(meta):
    """Write the useful metadata as lines for the AI, or '' if none."""
    labels = (("title", "Title"), ("author", "Author"), ("subject", "Subject"),
              ("keywords", "Keywords"), ("album", "Album or program"),
              ("date", "Recording date"), ("created", "Created"),
              ("comment", "Comment"), ("length", "Length"))
    lines = ["{}: {}".format(label, meta[key]) for key, label in labels
             if meta.get(key)]
    return "\n".join(lines)
