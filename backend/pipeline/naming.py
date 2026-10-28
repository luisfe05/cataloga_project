"""File naming methods."""

import os
import re
import unicodedata
from datetime import datetime

METHOD_TEMPLATES = (
    "{date}_{topic}",            # Method 1: 2026-07-15_oceanman-malta
    "{source}_{date}_{topic}",   # Method 2: el-nuevo-dia_2026-07-15_...
    "{number}_{topic}",          # Method 3: 0001_oceanman-malta
)

DEFAULT_TEMPLATE = METHOD_TEMPLATES[0]

# Files without text always use this: 2026-07-15_0001.jpg
NO_TEXT_TEMPLATE = "{date}_{number}"

TOKENS = ("date", "source", "topic", "number", "original")

# Not allowed in file names on macOS or Windows.
FORBIDDEN_CHARACTERS = '/\\:*?"<>|'

UNDATED = "undated"

# Longest slug for the topic, the original name, and the source.
MAX_TOPIC_LENGTH = 40
MAX_SOURCE_LENGTH = 30

# Far below the 255-character limit of most file systems.
MAX_NAME_LENGTH = 150

# YYYY, YYYY-MM, or YYYY-MM-DD.
DATE_PATTERN = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")

TOKEN_PATTERN = re.compile(r"\{([^{}]*)\}")


def slugify(text, max_length=MAX_TOPIC_LENGTH):
    """Turn text into a short slug: lowercase, hyphens, no accents."""
    if not text:
        return ""
    # NFKD splits 'í' into 'i' + accent; encode drops the accent.
    text = unicodedata.normalize("NFKD", str(text))
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    # Every run of other characters becomes one hyphen.
    slug = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    if len(slug) > max_length:
        slug = slug[:max_length]
        if "-" in slug:
            slug = slug.rsplit("-", 1)[0]
    return slug


def clean_date(document_date):
    """Return the date if it looks like YYYY, YYYY-MM or YYYY-MM-DD."""
    if document_date and DATE_PATTERN.match(document_date.strip()):
        return document_date.strip()
    return UNDATED


def file_date(path):
    """Return a file's last modified date as YYYY-MM-DD."""
    return datetime.fromtimestamp(os.path.getmtime(path)).strftime(
        "%Y-%m-%d")


def build_parts(original_filename, number, document_date=None,
                source=None, topic=None):
    """Prepare the value of every template part."""
    original = slugify(os.path.splitext(original_filename)[0])
    return {
        "date": clean_date(document_date),
        "source": slugify(source, MAX_SOURCE_LENGTH),
        "topic": slugify(topic) or original or "untitled",
        "number": "{:04d}".format(number),
        "original": original or "untitled",
    }


def validate_template(template):
    """Check a template before it is saved."""
    if not isinstance(template, str) or not template.strip():
        return {"reason": "empty", "token": ""}
    for found in TOKEN_PATTERN.findall(template):
        if found not in TOKENS:
            return {"reason": "unknown", "token": "{" + found + "}"}
    if not TOKEN_PATTERN.findall(template):
        return {"reason": "no_token", "token": ""}
    # The braces are allowed, so remove them first.
    text = TOKEN_PATTERN.sub("", template)
    if any(char in FORBIDDEN_CHARACTERS for char in text):
        return {"reason": "chars", "token": ""}
    return None


def render_template(template, parts):
    """Fill a template with the parts and tidy the result."""
    name = template
    for token in TOKENS:
        name = name.replace("{" + token + "}", parts.get(token, ""))
    name = re.sub(r"_{2,}", "_", name)
    name = re.sub(r"-{2,}", "-", name)
    name = name.strip("_-. ")
    return name[:MAX_NAME_LENGTH].rstrip("_-. ")


def make_filename(template, parts, extension):
    """Build the full file name, extension included."""
    name = render_template(template, parts) or parts["number"]
    return name + extension.lower()


def clean_new_name(new_name, extension):
    """Clean a name the user asked for in the chat, and add the extension."""
    base, typed_extension = os.path.splitext(str(new_name or "").strip())
    # Any other "extension" is part of the name, like 'v1.2'.
    if typed_extension.lower() != extension.lower():
        base += typed_extension
    parts = [slugify(part, MAX_NAME_LENGTH) for part in base.split("_")]
    name = "_".join(part for part in parts if part)
    name = name[:MAX_NAME_LENGTH].rstrip("_-")
    if not name:
        return ""
    return name + extension.lower()
