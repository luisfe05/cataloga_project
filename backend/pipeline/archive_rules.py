"""Rules of the Digital Archiving Guideline: checks for every new field."""

import hashlib
import json
import os
import re
import unicodedata
from datetime import datetime

CONFIDENTIALITY_LEVELS = ("Public", "Internal", "Confidential", "Restricted")
DEFAULT_CONFIDENTIALITY = "Internal"

MIN_KEYWORDS = 3
MAX_KEYWORDS = 5
MAX_KEYWORD_LENGTH = 40
MAX_COUNTERPARTY_LENGTH = 100
MAX_TOPIC_LENGTH = 60
MAX_OWNER_LENGTH = 100
MAX_INDUSTRY_LENGTH = 100

MIN_SUGGESTED_CATEGORIES = 6
MAX_CATEGORIES = 10
MAX_SUBCATEGORIES = 10
MAX_CATEGORY_LENGTH = 60

# A folder tree is saved as categories and can have 20 top folders.
MAX_SAVED_CATEGORIES = 20

DUPLICATE_NOTE = "Duplicate of {}"
NO_CATEGORY_NOTE = "Category not in the project list"
MEDIA_NOTE = "Audio and video reading is coming soon"
IMAGE_NOTE = "Could not read the image"
SCAN_NOTE = "Could not read the scanned pages"
TOO_BIG_NOTE = "File is larger than 50 MB, so it was not read"
TOPIC_NOTE = "No topic could be found in the photo"
SECRET_NOTE = "Possible secret, not read"

# Files that may hold keys or passwords: never read, never sent anywhere.
SECRET_NAMES = (".env", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519")
SECRET_PREFIXES = (".env.", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
                   "credentials")
SECRET_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".keychain",
                   ".keychain-db", ".jks", ".kdbx")
# Fields are listed by their column name: "Missing: source, document_date".
MISSING_NOTE = "Missing: {}"

# Names that cameras, scanners and phones give files: DSC_0042, IMG_4471,
# PXL_20260715_103000, scan_0118, Screenshot 2026-07-15 at 10.30.00...
GENERIC_NAME = re.compile(
    r"^(dscn?|dscf|img|pxl|mvimg|vid|video|scan|scanned|screenshot|"
    r"screen shot|captura de pantalla|photo|image|picture|pict|gopr|dji|"
    r"cimg|wp|sam|p|document|doc|file|untitled|new)[\s_.-]*[\d\s_.:-]*"
    r"(at[\s\d_.:-]*)?(am|pm)?[\s\d()_.-]*$", re.IGNORECASE)

# Read the file in 1 MB pieces, so big videos never fill the memory.
HASH_CHUNK_SIZE = 1024 * 1024


def is_secret(filename):
    """Say whether a file looks like it holds keys or passwords."""
    name = os.path.basename(str(filename or "")).lower()
    return (name in SECRET_NAMES or name.startswith(SECRET_PREFIXES)
            or name.endswith(SECRET_SUFFIXES))


def is_generic_name(text):
    """Say whether a name or topic is only a camera, scanner or phone name."""
    if not text:
        return True
    stem = os.path.splitext(str(text).strip())[0]
    return bool(GENERIC_NAME.match(stem))


def sha256_of(path):
    """Return the SHA-256 hash of a file, as hex text."""
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(HASH_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fold(text):
    """Return text in lowercase and without accents, for comparing."""
    text = unicodedata.normalize("NFKD", str(text or ""))
    return text.encode("ascii", "ignore").decode("ascii").lower().strip()


def clean_text(value, max_length):
    """Return stripped text cut to max_length, or None if empty."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or value.lower() == "null":
        return None
    return value[:max_length].strip()


def clean_keywords(value):
    """Keep up to 5 different keywords from the AI, 40 characters each."""
    if not isinstance(value, list):
        return []
    keywords = []
    for item in value:
        keyword = clean_text(item, MAX_KEYWORD_LENGTH)
        if not keyword:
            continue
        if fold(keyword) not in [fold(saved) for saved in keywords]:
            keywords.append(keyword)
    return keywords[:MAX_KEYWORDS]


def check_keywords(value):
    """Check keywords the user typed. Raise ValueError if they break a rule."""
    if value is None or value == "":
        return []
    if isinstance(value, str):
        value = value.split(",")
    if not isinstance(value, list):
        raise ValueError("keywords must be a list of text")
    keywords = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError("keywords must be a list of text")
        if len(item.strip()) > MAX_KEYWORD_LENGTH:
            raise ValueError("each keyword must be {} characters or less"
                             .format(MAX_KEYWORD_LENGTH))
        if item.strip():
            keywords.append(item.strip())
    if len(keywords) > MAX_KEYWORDS:
        raise ValueError("keywords must be {} or fewer".format(MAX_KEYWORDS))
    return keywords


def keywords_to_text(keywords):
    """Save a keyword list as JSON text, or None if it is empty."""
    if not keywords:
        return None
    return json.dumps(keywords, ensure_ascii=False)


def keywords_from_text(text):
    """Read the keyword list saved by keywords_to_text()."""
    if not text:
        return []
    try:
        value = json.loads(text)
    except ValueError:
        return []
    return [item for item in value if isinstance(item, str)] \
        if isinstance(value, list) else []


def check_date(value, name):
    """Return a YYYY-MM-DD date, None if empty, or raise ValueError."""
    if value is None or value == "":
        return None
    if isinstance(value, str):
        try:
            datetime.strptime(value.strip(), "%Y-%m-%d")
            return value.strip()
        except ValueError:
            pass
    raise ValueError(name + " must be a date like 2026-07-15")


def check_limited_text(value, name, max_length):
    """Return text up to max_length, None if empty, or raise ValueError."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(name + " must be text")
    if len(value.strip()) > max_length:
        raise ValueError("{} must be {} characters or less"
                         .format(name, max_length))
    return value.strip() or None


def check_confidentiality(value):
    """Return a valid confidentiality level, or raise ValueError."""
    if value not in CONFIDENTIALITY_LEVELS:
        raise ValueError("confidentiality must be one of: " +
                         ", ".join(CONFIDENTIALITY_LEVELS))
    return value


def clean_categories(value, max_categories=MAX_CATEGORIES):
    """Return a clean category list, or raise ValueError if it is wrong."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("categories must be a list")
    categories = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("each category needs a name")
        name = clean_text(item.get("name"), MAX_CATEGORY_LENGTH)
        if not name:
            continue
        if fold(name) in [fold(saved["name"]) for saved in categories]:
            continue
        subcategories = []
        sent = item.get("subcategories") or []
        if not isinstance(sent, list):
            raise ValueError("subcategories must be a list")
        for sub in sent:
            sub = clean_text(sub, MAX_CATEGORY_LENGTH)
            if sub and fold(sub) not in [fold(s) for s in subcategories]:
                subcategories.append(sub)
        categories.append({"name": name,
                           "subcategories": subcategories[:MAX_SUBCATEGORIES]})
    if len(categories) > max_categories:
        raise ValueError("categories must be {} or fewer"
                         .format(max_categories))
    return categories


def parse_category_answer(answer):
    """Read the JSON list in the AI's answer, or return []."""
    if not answer:
        return []
    start = answer.find("[")
    end = answer.rfind("]")
    if start == -1 or end < start:
        return []
    try:
        value = json.loads(answer[start:end + 1])
    except ValueError:
        return []
    if not isinstance(value, list):
        return []
    # Extra categories are cut, so a long answer is still useful.
    try:
        return clean_categories(value[:MAX_CATEGORIES])
    except ValueError:
        return []


def categories_from_text(text):
    """Read the category list saved in app_config."""
    if not text:
        return []
    try:
        return clean_categories(json.loads(text), MAX_SAVED_CATEGORIES)
    except ValueError:
        return []


def find_category(categories, name):
    """Return the category in the list with this name, or None."""
    for category in categories:
        if fold(category["name"]) == fold(name):
            return category
    return None


def match_category(categories, category, subcategory):
    """Match the AI's choice to the list: (category, subcategory, note)."""
    if not categories:
        return None, None, None
    found = find_category(categories, category) if category else None
    if found is None:
        return None, None, NO_CATEGORY_NOTE
    if not found["subcategories"]:
        return found["name"], None, None
    for sub in found["subcategories"]:
        if subcategory and fold(sub) == fold(subcategory):
            return found["name"], sub, None
    return found["name"], None, NO_CATEGORY_NOTE
