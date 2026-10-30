"""The project sheet: what the work is, written from a sample of its files."""

import json
import os

from backend.pipeline import archive_rules, file_readers
from backend.pipeline.file_organizer import CATALOG_FOLDER

# The sheet the user keeps is plain text, at most this long.
MAX_SHEET_LENGTH = 1500

# Limits of the sample sent to the AI, so a huge folder stays cheap.
MAX_FOLDERS = 60
MAX_DEPTH = 3
MAX_NAMES = 40
MAX_EXTRACTS = 5
EXTRACT_LENGTH = 1500

# Folders that say nothing about the work.
SKIPPED_FOLDERS = {CATALOG_FOLDER, "node_modules", "__pycache__", ".git",
                   ".venv", "venv"}

# Fields of the AI's answer, in the order the sheet shows them.
SHEET_FIELDS = (("work", "Work"), ("industry", "Industry"),
                ("parts", "Parts"), ("file_types", "File types"),
                ("naming_style", "Naming style"), ("notes", "Notes"))

# The AI picks one of these. conventions.py (PR 4) will own the list.
INDUSTRIES = ("documentary and research", "legal", "construction",
              "web and code", "film and video", "photo archive",
              "library and digitization", "general")

SHEET_PROMPT = """You are an archivist looking at a sample of a folder:
its structure, some file names, and short extracts of a few files.
Write a short sheet of the project the folder holds. Plain language.

Find:
- work: what this work is, in one or two sentences.
- industry: one of {industries}.
- parts: the parts or stages of the work you can see, as a short list.
- file_types: the kinds of files it holds (contracts, photos, scans...).
- naming_style: how the files are named, in one line.
- notes: anything else an archivist should know, or null.

Respond with ONLY a JSON object in this exact format:
{{"work": "...", "industry": "...", "parts": ["...", "..."],
 "file_types": ["...", "..."], "naming_style": "...", "notes": null}}"""


def readable(name):
    """Say whether an extract can be read from a file with this name."""
    extension = os.path.splitext(name)[1].lower()
    return extension in (".pdf", ".txt") + file_readers.OFFICE_EXTENSIONS


def project_sample(folder):
    """Walk a folder and return a small sample: folders, names, extracts."""
    folders = []
    names = []
    extracts = []
    root_depth = folder.rstrip(os.sep).count(os.sep)
    for current, dirs, files in os.walk(folder):
        depth = current.count(os.sep) - root_depth
        # Prune in place: hidden and tool folders are never entered.
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and
                         d not in SKIPPED_FOLDERS)
        if depth >= MAX_DEPTH:
            dirs[:] = []
        relative = os.path.relpath(current, folder)
        if relative != "." and len(folders) < MAX_FOLDERS:
            folders.append(relative)
        for name in sorted(files):
            if name.startswith(".") or name.startswith("~$"):
                continue
            if len(names) < MAX_NAMES:
                names.append(name if relative == "." else
                             os.path.join(relative, name))
            if len(extracts) < MAX_EXTRACTS and readable(name):
                text = read_extract(os.path.join(current, name))
                if text:
                    extracts.append((name, text))
    return {"folders": folders, "names": names, "extracts": extracts}


def read_extract(path):
    """Return the start of a readable file's text, or ''."""
    # Imported here: classification_pipeline imports this module.
    from backend.pipeline.classification_pipeline import extract_text
    try:
        return archive_rules.clean_text(extract_text(path), EXTRACT_LENGTH)
    except Exception:
        return ""


def sample_text(sample):
    """Write the sample as the text the AI reads."""
    lines = ["Folders:"]
    lines += ["  " + f for f in sample["folders"]] or ["  (none)"]
    lines.append("File names:")
    lines += ["  " + n for n in sample["names"]] or ["  (none)"]
    for name, text in sample["extracts"]:
        lines.append("Extract of {}:\n{}".format(name, text))
    return "\n".join(lines)


def parse_sheet_answer(answer):
    """Turn the AI's JSON into the sheet text, or '' if unusable."""
    from backend.pipeline.classification_pipeline import parse_json_answer
    result = parse_json_answer(answer)
    lines = []
    for key, label in SHEET_FIELDS:
        value = result.get(key)
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value if str(v).strip())
        value = archive_rules.clean_text(value, 400)
        if key == "industry" and value:
            value = value.lower()
            if value not in INDUSTRIES:
                value = "general"
        if value:
            lines.append("{}: {}".format(label, value))
    if not any(line.startswith("Work:") for line in lines):
        return ""
    return clean_sheet("\n".join(lines))


def clean_sheet(value):
    """Return the sheet text ready to save, '' for none, None if bad."""
    if value is None:
        return ""
    if not isinstance(value, str):
        return None
    value = "\n".join(line.rstrip() for line in value.strip().splitlines())
    if len(value) > MAX_SHEET_LENGTH:
        return None
    return value


def sheet_industry(sheet):
    """Return the industry named in a sheet, or ''."""
    for line in (sheet or "").splitlines():
        if line.lower().startswith("industry:"):
            return line.split(":", 1)[1].strip().lower()
    return ""
