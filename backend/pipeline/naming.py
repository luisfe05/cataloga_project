"""File naming methods.

Builds the new name of a cataloged file from a template such as
'{date}_{topic}'. The user picks the template in Settings: one of the
three methods below, or a custom one.

Everything here is a plain function that gets its values as arguments,
so it never reads the database or a global setting. The pipeline passes
in the template saved in its own catalog.
"""

import os
import re
import unicodedata
from datetime import datetime

# The three approved methods, as templates.
METHOD_TEMPLATES = (
    "{date}_{topic}",            # Method 1: 2026-07-15_oceanman-malta
    "{source}_{date}_{topic}",   # Method 2: el-nuevo-dia_2026-07-15_...
    "{number}_{topic}",          # Method 3: 0001_oceanman-malta
)

# Method 1 is the default for every project.
DEFAULT_TEMPLATE = METHOD_TEMPLATES[0]

# Files without text (photos, audio, video, scans) always use this,
# whatever method the project uses: 2026-07-15_0001.jpg
NO_TEXT_TEMPLATE = "{date}_{number}"

# Parts a template can use.
TOKENS = ("date", "source", "topic", "number", "original")

# Characters a file name cannot have on macOS or Windows.
FORBIDDEN_CHARACTERS = '/\\:*?"<>|'

# Used in the name when the document has no date.
UNDATED = "undated"

# Longest slug for the topic, the original name, and the source.
MAX_TOPIC_LENGTH = 40
MAX_SOURCE_LENGTH = 30

# Longest file name without the extension, to stay far below the
# 255-character limit of most file systems.
MAX_NAME_LENGTH = 150

# A document date the AI may give: YYYY, YYYY-MM, or YYYY-MM-DD.
DATE_PATTERN = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")

# Finds every {word} in a template.
TOKEN_PATTERN = re.compile(r"\{([^{}]*)\}")


def slugify(text, max_length=MAX_TOPIC_LENGTH):
    """Turn text into a short slug: lowercase, hyphens, no accents.

    Example: 'Malta Olímpica, 1964!' -> 'malta-olimpica-1964'

    Args:
        text (str or None): Any text.
        max_length (int): Longest slug allowed. A longer one is cut at
            the last hyphen that fits, so no word is split in half.

    Returns:
        str: The slug, or '' if nothing is left.
    """
    if not text:
        return ""
    # NFKD splits 'í' into 'i' plus an accent mark; the encode step
    # drops the accent marks (and anything else that is not ASCII).
    text = unicodedata.normalize("NFKD", str(text))
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    # Every run of characters that are not letters or digits becomes
    # one hyphen, then hyphens at the ends are removed.
    slug = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    if len(slug) > max_length:
        slug = slug[:max_length]
        if "-" in slug:
            slug = slug.rsplit("-", 1)[0]
    return slug


def clean_date(document_date):
    """Return the date if it looks like YYYY, YYYY-MM or YYYY-MM-DD.

    Args:
        document_date (str or None): The date from the AI or the user.

    Returns:
        str: The date, or UNDATED if it is missing or not a date.
    """
    if document_date and DATE_PATTERN.match(document_date.strip()):
        return document_date.strip()
    return UNDATED


def file_date(path):
    """Return a file's last modified date as YYYY-MM-DD.

    The modified date is used (not the created date) because Finder
    keeps it when a file is copied.

    Args:
        path (str): Path to the file.

    Returns:
        str: For example '2026-07-15'.
    """
    return datetime.fromtimestamp(os.path.getmtime(path)).strftime(
        "%Y-%m-%d")


def build_parts(original_filename, number, document_date=None,
                source=None, topic=None):
    """Prepare the value of every template part.

    Missing values follow the approved rules: no date gives 'undated',
    no source leaves that part out, and no topic uses the original name.

    Args:
        original_filename (str): The file's name before cataloging.
        number (int): The file's number in the catalog.
        document_date (str, optional): Date on the document.
        source (str, optional): Who published or created it.
        topic (str, optional): Short topic from the AI.

    Returns:
        dict: {'date', 'source', 'topic', 'number', 'original'}, as text.
    """
    original = slugify(os.path.splitext(original_filename)[0])
    return {
        "date": clean_date(document_date),
        "source": slugify(source, MAX_SOURCE_LENGTH),
        "topic": slugify(topic) or original or "untitled",
        "number": "{:04d}".format(number),
        "original": original or "untitled",
    }


def validate_template(template):
    """Check a template before it is saved.

    Args:
        template (str): For example '{date}_{topic}'. Anything that is
            not text counts as empty.

    Returns:
        dict or None: None if the template is valid. Otherwise
            {'reason': ..., 'token': ...}, where reason is 'empty',
            'no_token', 'unknown', or 'chars', and token is the wrong
            part (only for 'unknown').
    """
    if not isinstance(template, str) or not template.strip():
        return {"reason": "empty", "token": ""}
    for found in TOKEN_PATTERN.findall(template):
        if found not in TOKENS:
            return {"reason": "unknown", "token": "{" + found + "}"}
    if not TOKEN_PATTERN.findall(template):
        return {"reason": "no_token", "token": ""}
    # The braces are removed first, since they are allowed.
    text = TOKEN_PATTERN.sub("", template)
    if any(char in FORBIDDEN_CHARACTERS for char in text):
        return {"reason": "chars", "token": ""}
    return None


def render_template(template, parts):
    """Fill a template with the parts and tidy the result.

    An empty part (for example, no source) would leave two separators
    together, like 'a__b', or one at the start, like '_b'. Those are
    cleaned up.

    Args:
        template (str): A valid template.
        parts (dict): Values from build_parts().

    Returns:
        str: The name without extension, e.g. '2026-07-15_oceanman-malta'.
    """
    name = template
    for token in TOKENS:
        name = name.replace("{" + token + "}", parts.get(token, ""))
    name = re.sub(r"_{2,}", "_", name)
    name = re.sub(r"-{2,}", "-", name)
    name = name.strip("_-. ")
    return name[:MAX_NAME_LENGTH].rstrip("_-. ")


def make_filename(template, parts, extension):
    """Build the full file name, extension included.

    Args:
        template (str): The project's template.
        parts (dict): Values from build_parts().
        extension (str): For example '.PDF'. Saved in lowercase.

    Returns:
        str: For example '2026-07-15_oceanman-malta.pdf'. If the template
            gives an empty name, the number is used instead.
    """
    name = render_template(template, parts) or parts["number"]
    return name + extension.lower()
