"""File naming methods."""

import os
import re
import unicodedata
from datetime import datetime

METHOD_TEMPLATES = (
    "{date}_{topic}",            # Method 1: date_topic-name
    "{source}_{date}_{topic}",   # Method 2: source-name_date_topic-name
    "{number}_{topic}",          # Method 3: 0001_topic-name
    "{topic}_{source}_{date}",   # Method 4: topic-name_source-name_date
)

# How the words of a name look: "topic-name" or "Topic-Name".
STYLES = ("lower", "title")
DEFAULT_STYLE = "lower"

# The whole path must fit Windows (259); this leaves room for the drive.
MAX_PATH_LENGTH = 240

# A version mark in the original name: v01, v2, draft-3, borrador_2.
VERSION_PATTERN = re.compile(
    r"(?<![a-z0-9])(v\d{1,3}|draft[-_ ]?\d+|borrador[-_ ]?\d+)(?![a-z0-9])",
    re.IGNORECASE)

# Fallback for old projects that never saved a template.
DEFAULT_TEMPLATE = METHOD_TEMPLATES[0]

# Only projects created from now on start with method 4.
NEW_PROJECT_TEMPLATE = METHOD_TEMPLATES[3]

# Files without text always use this: 2026-07-15_0001.jpg, or 0001.jpg
# when no date is known.
NO_TEXT_TEMPLATE = "{date}_{number}"

TOKENS = ("date", "source", "topic", "number", "original", "topic_number")

# Not allowed in file names on macOS or Windows.
FORBIDDEN_CHARACTERS = '/\\:*?"<>|'

# Longest slug for the topic, the original name, and the source.
MAX_TOPIC_LENGTH = 40
MAX_SOURCE_LENGTH = 30

# Far below the 255-character limit of most file systems.
MAX_NAME_LENGTH = 150

# YYYY, YYYY-MM, or YYYY-MM-DD.
DATE_PATTERN = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")

TOKEN_PATTERN = re.compile(r"\{([^{}]*)\}")


def slugify(text, max_length=MAX_TOPIC_LENGTH, style=DEFAULT_STYLE,
            keep_accents=False):
    """Turn text into a short slug with hyphens: topic-name or Topic-Name."""
    if not text:
        return ""
    if keep_accents:
        # NFC keeps 'í' as one character.
        text = unicodedata.normalize("NFC", str(text))
    else:
        # NFKD splits 'í' into 'i' + accent; encode drops the accent.
        text = unicodedata.normalize("NFKD", str(text))
        text = text.encode("ascii", "ignore").decode("ascii")
    # Every run of other characters becomes one hyphen.
    words = [w for w in re.split(r"[^0-9A-Za-z\u00C0-\u024F]+", text) if w]
    if style == "title":
        # Juegos-Nacionales-PR: the first letter up, the rest as written.
        words = [w[0].upper() + w[1:] for w in words]
    else:
        words = [w.lower() for w in words]
    slug = "-".join(words)
    if len(slug) > max_length:
        slug = slug[:max_length]
        if "-" in slug:
            slug = slug.rsplit("-", 1)[0]
    return slug


def version_of(original_filename):
    """Return the version mark of a name (v02), or ''."""
    stem = os.path.splitext(os.path.basename(str(original_filename)))[0]
    found = VERSION_PATTERN.search(stem)
    return found.group(1).lower() if found else ""


def clean_date(document_date):
    """Return the date if it looks like YYYY, YYYY-MM or YYYY-MM-DD, or ''."""
    if document_date and DATE_PATTERN.match(document_date.strip()):
        return document_date.strip()
    # No date: the name has no date part, and the catalog says so.
    return ""


def file_date(path):
    """Return a file's last modified date as YYYY-MM-DD."""
    return datetime.fromtimestamp(os.path.getmtime(path)).strftime(
        "%Y-%m-%d")


def build_parts(original_filename, number, document_date=None,
                source=None, topic=None, topic_number=1,
                style=DEFAULT_STYLE, keep_accents=False):
    """Prepare the value of every template part."""
    original = slugify(os.path.splitext(original_filename)[0],
                       style=style, keep_accents=keep_accents)
    return {
        "date": clean_date(document_date),
        "source": slugify(source, MAX_SOURCE_LENGTH, style, keep_accents),
        "topic": slugify(topic, style=style, keep_accents=keep_accents)
        or original or "untitled",
        "number": "{:04d}".format(number),
        # 3 digits; the 1000th file of a topic simply gets 4.
        "topic_number": "{:03d}".format(topic_number),
        "original": original or "untitled",
        # Kept at the end of the new name, so v01 and v02 stay apart.
        "version": version_of(original_filename),
    }


def next_topic_number(topic, saved_topics):
    """Return how many saved documents share this topic, plus one."""
    slug = slugify(topic)
    if not slug:
        return 1
    return sum(1 for saved in saved_topics if slugify(saved) == slug) + 1


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
    version = parts.get("version")
    # The original name carries its own version; others get it appended.
    if version and "{original}" not in template and \
            version not in name.lower():
        name += "_" + version
    return name + extension.lower()


def fit_path(folder, template, parts, extension):
    """Return a name whose full path fits Windows, or None if it cannot."""
    parts = dict(parts)
    while True:
        name = make_filename(template, parts, extension)
        if len(os.path.join(folder, name)) <= MAX_PATH_LENGTH:
            return name
        # Shorten the topic first, then the source, a word at a time.
        for key in ("topic", "source"):
            if "-" in parts[key]:
                parts[key] = parts[key].rsplit("-", 1)[0]
                break
            if parts[key]:
                parts[key] = ""
                break
        else:
            return None


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
