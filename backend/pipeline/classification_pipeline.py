"""ClassificationPipeline."""

import json
import os
from datetime import datetime

from pypdf import PdfReader

from backend.models.document import Document
from backend.pipeline import (archive_rules, file_metadata, file_readers,
                              folder_tree, naming)

# Sorted by extension alone, without asking the AI.
EXTENSION_MEDIA_TYPES = {
    ".jpg": "Photos",
    ".jpeg": "Photos",
    ".png": "Photos",
    ".gif": "Photos",
    ".tif": "Photos",
    ".tiff": "Photos",
    ".heic": "Photos",
    ".mp3": "Audio",
    ".wav": "Audio",
    ".m4a": "Audio",
    ".aac": "Audio",
    ".mp4": "Video",
    ".mov": "Video",
    ".avi": "Video",
    ".mkv": "Video",
    ".wmv": "Video",
    ".mxf": "Video",
}

READABLE_EXTENSIONS = (".pdf", ".txt") + file_readers.OFFICE_EXTENSIONS

# Used when a file can't be read or classified.
FALLBACK_MEDIA_TYPE = "Documents"

# Needed to count as Classified: a summary means the file was read. A
# missing source or date never sends a file to Manual Review by itself.
REQUIRED_FIELDS = ("summary",)

# How sure the AI was of the folder. Low sends the file to Manual Review.
CONFIDENCE_LEVELS = ("high", "medium", "low")

# How many files of the same folder the AI sees as context.
MAX_NEIGHBORS = 10

# One request per file: the card below, plus the folder part.
FILE_PROMPT = """You are the archivist of a research project. You read one
file at a time and fill its catalog card.

Rules:
- A meaningful file name (an event, a year, a contract name, a title) is
  strong evidence for the topic, the date and the folder. Names that a
  camera, a scanner or a phone gave (DSC_0042, IMG_4471, PXL_2026...,
  scan_0118, Screenshot...) say nothing: ignore them.
- If the name and the content disagree, follow the content and say so
  in name_hint_conflict.
- A missing date never changes the folder and never makes the file
  incomplete.
- Use null for anything the file does not say. Do not guess.

Find:
- media_type: Press (a newspaper or magazine article, press clipping or
  press release) or Documents (any other written document). When the
  file says its media type is fixed, keep it.
- summary: one factual sentence under 100 characters, in the file's
  language: what it is, who or what it is about, key dates or places.
- source: who published or created the file (a newspaper, magazine,
  organization, or person).
- document_date: the date written on the file itself, as YYYY-MM-DD,
  YYYY-MM, or YYYY, with the precision the file gives.
- topic: the main subject in 2 to 4 words, in the file's language. It
  is used in the file name.
- keywords: 3 to 5 short keywords for searching, each under 40
  characters, in the file's language.
- counterparty: the other person or organization the file is with or
  addressed to (the other side of a contract or letter).
- confidence: high, medium, or low. Low when two places fit equally or
  the content is unclear.
- name_hint_conflict: one short line when the name and the content
  disagree, else null.

Respond with ONLY a JSON object in this exact format:
{"media_type": "...", "summary": "...", "source": "...",
 "document_date": "...", "topic": "...", "keywords": ["...", "..."],
 "counterparty": "...", "confidence": "...", "name_hint_conflict": null"""

# Closes FILE_PROMPT when the project has no categories and no tree.
NO_PLACE_PROMPT = """}"""

# Added to FILE_PROMPT when the project has a category list.
CATEGORY_PROMPT = """,
 "category": "...", "subcategory": "...", "folder_reason": "..."}}

Also choose where the file belongs in this list of categories:
{categories}
"category" is one category name exactly as written, "subcategory" one
of its subcategories (null if it has none). If nothing in the list fits,
use null for both. "folder_reason" is one line on why."""

# Added to FILE_PROMPT in projects with their own folder tree.
FOLDER_PROMPT = """,
 "folder": "<a path from the list>", "folder_reason": "...",
 "suggested_folder": null}}

This project is about: {description}
These are the folders a file can go into, as paths from the project:
{folders}
Choose the folder where an archivist would file this document, by what
it is about, not by its file type. Add "folder" with one path exactly
as written. Never force a document into a folder made for something
else. "folder_reason" is one line on why this folder. If no folder
fits, use null and always add "suggested_folder": {{"parent": "<an
existing folder path, or null for a new top folder>", "name": "<new
folder name, 1 to 3 words>"}}.
Answer with one JSON object only."""

METADATA_FIELDS = ("source", "document_date", "topic")

# Goes before the metadata prompt when the project has a sheet.
SHEET_PREFIX = "Project sheet (what this work is):\n"


def now_timestamp():
    """Return the current time as an ISO string, e.g. 2026-10-21T16:55:00."""
    return datetime.now().isoformat(timespec="seconds")


def extract_text(file_path):
    """Return the text inside a PDF, .txt, or Office file."""
    extension = os.path.splitext(file_path)[1].lower()
    if extension in file_readers.OFFICE_EXTENSIONS:
        return file_readers.office_text(file_path)
    try:
        if extension == ".pdf":
            reader = PdfReader(file_path)
            pages = [page.extract_text() or "" for page in reader.pages]
            return "\n".join(pages).strip()
        if extension == ".txt":
            # errors="replace" keeps going if the file has odd characters.
            with open(file_path, encoding="utf-8", errors="replace") as file:
                return file.read().strip()
    except Exception:
        # A damaged file is treated like an unreadable one.
        return ""
    return ""


def parse_json_answer(answer):
    """Turn the AI's JSON answer into a dict.

    Some models send text, markdown fences, or more than one JSON block.
    The first block that is a valid JSON object is used.
    """
    if not answer:
        return {}
    decoder = json.JSONDecoder()
    start = answer.find("{")
    while start != -1:
        try:
            # raw_decode reads one JSON value and ignores what comes after.
            result = decoder.raw_decode(answer, start)[0]
        except json.JSONDecodeError:
            result = None
        if isinstance(result, dict):
            return result
        start = answer.find("{", start + 1)
    return {}


def missing_note(document):
    """Return the note that lists the empty required fields."""
    missing = [field for field in REQUIRED_FIELDS
               if not getattr(document, field)]
    return archive_rules.MISSING_NOTE.format(", ".join(missing))


def needs_nothing(document):
    """Say whether a document has every field and no open review note."""
    if document.review_note or document.duplicate_of:
        return False
    return all(getattr(document, field) for field in REQUIRED_FIELDS)


def cut_summary(text):
    """Keep a summary under the limit, cut at a whole word."""
    text = archive_rules.clean_text(text, 1000) or ""
    if len(text) > archive_rules.MAX_SUMMARY_LENGTH:
        text = text[:archive_rules.MAX_SUMMARY_LENGTH - 3].rsplit(
            " ", 1)[0] + "..."
    return text


def neighbors_of(file_path):
    """Return the names of the other visible files in the same folder."""
    folder = os.path.dirname(file_path)
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return []
    names = [n for n in names if not n.startswith(".") and
             n != os.path.basename(file_path) and
             os.path.isfile(os.path.join(folder, n))]
    return names[:MAX_NEIGHBORS]


def file_context(file_path, project_folder, media_type, meta, content):
    """Write everything the AI gets about one file, content last."""
    name = os.path.basename(file_path)
    folder = os.path.relpath(os.path.dirname(file_path), project_folder) \
        if project_folder else os.path.basename(os.path.dirname(file_path))
    lines = ["File name: " + name,
             "Type: " + (os.path.splitext(name)[1].lower() or "(none)"),
             "Folder: " + folder]
    if media_type:
        lines.append("Media type: {} (fixed)".format(media_type))
    else:
        lines.append("Media type: decide between Press and Documents")
    hints = archive_rules.name_hints(name)
    if hints["generic"]:
        lines.append("The file name is a camera, scanner or phone name.")
    else:
        found = ["words: " + hints["words"]]
        if hints["year"]:
            found.append("year " + hints["year"])
        if hints["version"]:
            found.append("version " + hints["version"])
        lines.append("Name hints: " + "; ".join(found))
    neighbors = neighbors_of(file_path)
    if neighbors:
        lines.append("Other files in that folder: " + ", ".join(neighbors))
    metadata = file_metadata.metadata_text(meta) if meta else ""
    if metadata:
        lines.append("File metadata:\n" + metadata)
    lines.append("Content:\n" + (content or "(nothing could be read)"))
    return "\n".join(lines)


def choose_date(content_date, file_path, taken=None, meta_date=None,
                name_year=None):
    """Pick the date and say where it came from, in order of trust."""
    if taken:
        return taken, "photo"
    if content_date:
        return content_date, "content"
    if meta_date:
        return meta_date, "metadata"
    if name_year:
        return name_year, "name"
    return naming.file_date(file_path), "file"


def too_big_to_read(file_path, extension):
    """Say whether a file that would be opened is over the size limit."""
    opened = READABLE_EXTENSIONS + file_readers.VISION_EXTENSIONS
    return (extension in opened and
            os.path.getsize(file_path) > file_readers.MAX_READ_BYTES)


def remove_gone_duplicates(catalog_repo):
    """Drop the rows of duplicates the user removed. Never touches a file."""
    for document in catalog_repo.get_duplicates():
        if not os.path.exists(document.file_path):
            catalog_repo.delete_document(document.id)


class ClassificationPipeline:
    """Runs the classify-summarize-organize-catalog flow."""

    def __init__(self, ai_client, catalog_repo, file_organizer, owner=None):
        """Set up the pipeline; owner is the account's username."""
        self.ai_client = ai_client
        self.db = catalog_repo
        self.file_organizer = file_organizer
        self.owner = owner or None

    def destination(self, file_path, media_type, metadata):
        """Return the folder a file goes to, and if it found its place."""
        # Catalog only: the file is already where it belongs.
        if self.db.is_catalog_project():
            return os.path.dirname(file_path), True
        if not self.db.is_tree_project():
            return self.file_organizer.folder_for(media_type), True
        if metadata["folder_path"]:
            return self.file_organizer.tree_folder(
                metadata["folder_path"]), True
        # No folder fits: the file stays in the Drop Zone for a person.
        return os.path.dirname(file_path), False

    def classify_document(self, file_path):
        """Run the full pipeline on a single file."""
        original_filename = os.path.basename(file_path)
        date_added = now_timestamp()
        extension = os.path.splitext(file_path)[1].lower()

        # A file that may hold keys is never read and never sent anywhere.
        if archive_rules.is_secret(original_filename):
            return self.add_unread(file_path, archive_rules.SECRET_NOTE)

        # Hash first: a duplicate never reaches the AI.
        sha256 = archive_rules.sha256_of(file_path)
        original = self.db.find_by_sha256(sha256)
        if original is not None:
            return self.add_duplicate(file_path, sha256, original)

        media_type = None
        metadata = self.empty_metadata()
        # What the AI reads: text, what a photo shows, or a file's tags.
        content = ""
        # Why the file needs a person, when it is known before the AI.
        reason = None
        kind = EXTENSION_MEDIA_TYPES.get(extension)
        # Metadata saved inside the file, and the date a photo was taken.
        file_meta = {}
        taken = None

        if too_big_to_read(file_path, extension):
            media_type = kind
            reason = archive_rules.TOO_BIG_NOTE
        elif kind in ("Audio", "Video"):
            media_type = kind
            file_meta = file_metadata.media_metadata(file_path)
            # Not listened to yet, but a title is enough to name it.
            if file_meta["title"]:
                content = ("This {} file was not listened to; use only its "
                           "tags above.").format(kind.lower())
        elif (extension in file_readers.VISION_EXTENSIONS and
              self.ai_client.supports_images):
            media_type = "Photos"
            taken = file_readers.photo_date(file_path)
            content = self.read_images(
                [file_readers.photo_data_uri(file_path)], "photo")
            if not content:
                reason = archive_rules.IMAGE_NOTE
        elif kind:
            media_type = kind
            if kind == "Photos":
                taken = file_readers.photo_date(file_path)
        elif extension in READABLE_EXTENSIONS:
            file_meta = file_metadata.document_metadata(file_path)
            content = extract_text(file_path)
            if (not content and extension == ".pdf" and
                    self.ai_client.supports_images):
                # A scanned PDF: its first pages go to the AI as images.
                content = self.read_images(
                    file_readers.pdf_page_data_uris(file_path), "scan")
                if not content:
                    reason = archive_rules.SCAN_NOTE

        has_text = bool(content)
        if content:
            # One request: the card, the folder and why, and how sure.
            metadata = self.read_card(file_path, media_type, file_meta,
                                      content)
            if media_type is None:
                media_type = metadata["media_type"]
            if kind in ("Audio", "Video"):
                # The date of a recording comes from its tags, below.
                metadata["document_date"] = None
            # The name of a photo must come from what the photo shows.
            if media_type == "Photos" and not metadata["topic"]:
                reason = archive_rules.TOPIC_NOTE
            if metadata["confidence"] == "low" and not reason:
                reason = archive_rules.LOW_CONFIDENCE_NOTE + ": " + (
                    metadata["folder_reason"] or metadata["summary"] or "")

        # Empty fields send the document to Manual Review below.
        if media_type is None:
            media_type = FALLBACK_MEDIA_TYPE

        date, date_source = choose_date(
            metadata["document_date"], file_path, taken,
            file_meta.get("date") or file_meta.get("created"),
            archive_rules.name_hints(original_filename)["year"])
        metadata["document_date"] = date

        folder, placed = self.destination(file_path, media_type, metadata)
        new_filename = self.build_filename(file_path, has_text, metadata,
                                           date_source, folder)
        if self.db.is_catalog_project():
            new_path = file_path
        elif new_filename is None:
            # Even a short name would not fit: a person must choose.
            reason = reason or archive_rules.TOO_LONG_NOTE
            metadata["suggested_folder"] = metadata["suggested_folder"] or \
                self.file_organizer.place_of(folder)
            metadata.update({"category": None, "subcategory": None})
            placed = False
            new_path = file_path
        else:
            new_path = self.file_organizer.move_to_folder(
                file_path, folder, new_filename)

        document = Document(
            original_filename=original_filename,
            filename=os.path.basename(new_path),
            media_type=media_type,
            file_path=new_path,
            date_added=date_added,
            source=metadata["source"],
            document_date=metadata["document_date"],
            summary=metadata["summary"] or None,
            date_classified=now_timestamp(),
            topic=metadata["topic"],
            keywords=metadata["keywords"],
            counterparty=metadata["counterparty"],
            category=metadata["category"],
            subcategory=metadata["subcategory"],
            folder_path=metadata["folder_path"],
            review_note=reason or metadata["review_note"],
            suggested_folder=metadata["suggested_folder"],
            folder_reason=metadata["folder_reason"],
            confidence=metadata["confidence"],
            original_path=self.relative_path(file_path),
            date_source=date_source,
            sha256=sha256,
            confidentiality=archive_rules.DEFAULT_CONFIDENTIALITY,
            owner=self.owner,
        )
        self.validate_completeness(document)
        # Audio or video that still needs a person says why.
        if kind in ("Audio", "Video") and not document.review_note and \
                document.status == "Manual Review":
            document.review_note = self.media_note(file_meta.get("length"))
        if not placed:
            document.review_note = document.review_note or \
                folder_tree.NO_FOLDER_NOTE
            document.mark_needs_review(["folder"])
        # Every file in Manual Review says why.
        if document.status == "Manual Review" and not document.review_note:
            document.review_note = missing_note(document)
        return self.db.add_document(document)

    def relative_path(self, file_path):
        """Return where a file was first seen, relative to the project."""
        folder = self.file_organizer.target_directory
        try:
            return os.path.relpath(file_path, folder)
        except ValueError:
            # Another drive on Windows has no relative path.
            return file_path

    def media_note(self, length):
        """Return the Manual Review reason for audio and video, with length."""
        if length:
            return "{}. Duration {}".format(archive_rules.MEDIA_NOTE, length)
        return archive_rules.MEDIA_NOTE

    def read_images(self, image_uris, kind):
        """Ask the AI to read images; return them as text, or ''."""
        image_uris = [uri for uri in image_uris if uri]
        result = parse_json_answer(self.ai_client.ask_about_images(image_uris))
        found = archive_rules.clean_text(result.get("text"), 20000)
        description = archive_rules.clean_text(result.get("description"), 500)
        if not found and not description:
            return ""
        # The summary and metadata prompts then read this like a document.
        if kind == "photo":
            # Without this, the AI often finds no topic in a photo.
            lines = ["This is a photo; its topic is what it shows.",
                     "Photo description: " + (description or "")]
            if found:
                lines.append("Text in the photo:\n" + found)
        else:
            lines = ["Text of the scanned pages:\n" + (found or "")]
            if description:
                lines.append("What the pages show: " + description)
        return "\n".join(lines)

    def add_unread(self, file_path, note):
        """Record a file by its name only, in Manual Review, where it is."""
        name = os.path.basename(file_path)
        extension = os.path.splitext(name)[1].lower()
        document = Document(
            original_filename=name,
            filename=name,
            media_type=EXTENSION_MEDIA_TYPES.get(extension,
                                                 FALLBACK_MEDIA_TYPE),
            file_path=file_path,
            date_added=now_timestamp(),
            status="Manual Review",
            review_note=note,
            confidentiality=archive_rules.DEFAULT_CONFIDENTIALITY,
            owner=self.owner,
        )
        return self.db.add_document(document)

    def add_duplicate(self, file_path, sha256, original):
        """Record a duplicate in Manual Review. It stays in the Drop Zone."""
        name = os.path.basename(file_path)
        extension = os.path.splitext(name)[1].lower()
        document = Document(
            original_filename=name,
            filename=name,
            media_type=EXTENSION_MEDIA_TYPES.get(extension,
                                                 FALLBACK_MEDIA_TYPE),
            file_path=file_path,
            date_added=now_timestamp(),
            status="Manual Review",
            sha256=sha256,
            duplicate_of=original.filename,
            review_note=archive_rules.DUPLICATE_NOTE.format(
                original.filename),
            confidentiality=archive_rules.DEFAULT_CONFIDENTIALITY,
            owner=self.owner,
        )
        return self.db.add_document(document)

    def build_filename(self, file_path, has_text, metadata, date_source,
                       folder):
        """Build the new file name, short enough for its folder, or None."""
        original_filename = os.path.basename(file_path)
        extension = os.path.splitext(file_path)[1]
        # Keep original names, and names other programs look for.
        if self.db.get_naming_template() == naming.KEEP_NAMES or \
                naming.is_protected(original_filename):
            return original_filename
        number = self.db.next_number()
        style = self.db.get_naming_style()
        keep_accents = self.db.keep_accents()
        # The disk date changes when files are copied, so it is left out.
        name_date = None if date_source == "file" else \
            metadata["document_date"]
        # Without a topic, a camera or scanner name never becomes one.
        if has_text and not metadata["topic"] and \
                archive_rules.is_generic_name(original_filename):
            has_text = False
        if has_text:
            template = self.db.get_naming_template()
            topic_number = naming.next_topic_number(
                metadata["topic"] or original_filename, self.db.get_topics())
            parts = naming.build_parts(
                original_filename, number,
                document_date=name_date,
                source=metadata["source"],
                topic=metadata["topic"],
                topic_number=topic_number,
                style=style, keep_accents=keep_accents)
        else:
            template = naming.NO_TEXT_TEMPLATE
            parts = naming.build_parts(original_filename, number,
                                       document_date=name_date,
                                       style=style, keep_accents=keep_accents)
        return naming.fit_path(folder, template, parts, extension)

    def regenerate_summary(self, document):
        """Write a new summary that uses the source and date the user typed."""
        text = extract_text(document.file_path)
        if not text:
            return document
        facts = {"source": document.source,
                 "document_date": document.document_date}
        summary = self.ai_client.send_summary_request(text, facts)
        if not summary:
            return document
        return self.db.update_document(document.id, {"summary": summary})

    def empty_metadata(self):
        """Return the card of a file the AI did not read."""
        return {"media_type": None, "summary": None, "source": None,
                "document_date": None, "topic": None, "keywords": [],
                "counterparty": None, "category": None,
                "subcategory": None, "folder_path": None,
                "review_note": None, "suggested_folder": None,
                "folder_reason": None, "confidence": None}

    def card_prompt(self):
        """Return the system prompt: the sheet, the card, and the places."""
        categories = self.db.get_folder_tree() if self.db.is_tree_project() \
            else self.db.get_categories()
        prompt = self.sheet_prompt() + FILE_PROMPT
        if self.db.is_tree_project():
            return prompt + self.folder_prompt(categories)
        if categories:
            return prompt + CATEGORY_PROMPT.format(
                categories=json.dumps(categories, ensure_ascii=False))
        return prompt + NO_PLACE_PROMPT

    def read_card(self, file_path, media_type, file_meta, content):
        """Ask the AI for the whole card in one request, then check it."""
        tree_mode = self.db.is_tree_project()
        categories = self.db.get_folder_tree() if tree_mode \
            else self.db.get_categories()
        text = file_context(file_path, self.file_organizer.target_directory,
                            media_type, file_meta, content)
        result = parse_json_answer(self.ai_client.ask(self.card_prompt(),
                                                      text))

        metadata = self.empty_metadata()
        for field in METADATA_FIELDS:
            value = result.get(field)
            # null, '', and 'null' all become None.
            if isinstance(value, str) and value.strip() and \
                    value.strip().lower() != "null":
                metadata[field] = value.strip()
        # A topic like "DSC 0042" is a camera name, not a topic.
        if archive_rules.is_generic_name(metadata["topic"]):
            metadata["topic"] = None
        if metadata["topic"]:
            metadata["topic"] = metadata["topic"][
                :archive_rules.MAX_TOPIC_LENGTH]
        metadata["summary"] = cut_summary(result.get("summary")) or None
        kind = archive_rules.clean_text(result.get("media_type"), 20) or ""
        metadata["media_type"] = kind.strip(" .\"'").title() \
            if kind.strip(" .\"'").lower() in ("press", "documents") \
            else FALLBACK_MEDIA_TYPE
        metadata["keywords"] = archive_rules.clean_keywords(
            result.get("keywords"))
        metadata["counterparty"] = archive_rules.clean_text(
            result.get("counterparty"), archive_rules.MAX_COUNTERPARTY_LENGTH)
        confidence = (archive_rules.clean_text(result.get("confidence"), 20)
                      or "").lower()
        metadata["confidence"] = confidence \
            if confidence in CONFIDENCE_LEVELS else "medium"
        reason = archive_rules.clean_text(result.get("folder_reason"), 300)
        conflict = archive_rules.clean_text(result.get("name_hint_conflict"),
                                            300)
        if conflict:
            reason = ((reason + " ") if reason else "") + \
                "Name and content disagree: " + conflict
        metadata["folder_reason"] = reason
        if tree_mode:
            return self.match_folder(metadata, result, categories)
        category, subcategory, note = archive_rules.match_category(
            categories,
            archive_rules.clean_text(result.get("category"), 200),
            archive_rules.clean_text(result.get("subcategory"), 200))
        metadata.update({"category": category, "subcategory": subcategory,
                         "folder_path": folder_tree.folder_text(
                             category, subcategory) if category else None,
                         "review_note": note})
        return metadata

    def sheet_prompt(self):
        """Return the project sheet as the first part of the prompt, or ''."""
        sheet = self.db.get_project_sheet()
        if not sheet:
            return ""
        return SHEET_PREFIX + sheet + "\n\n"

    def folder_prompt(self, tree):
        """Return the part of the prompt with the project's folder paths."""
        return FOLDER_PROMPT.format(
            description=self.db.get_project_description() or "(not given)",
            folders=json.dumps(folder_tree.all_places(tree),
                               ensure_ascii=False))

    def match_folder(self, metadata, result, tree):
        """Keep the AI's folder if it is in the tree; else the catch-all."""
        folder = archive_rules.clean_text(result.get("folder"), 400) or ""
        subfolder = archive_rules.clean_text(result.get("subfolder"), 200)
        # Older answers send the subfolder apart.
        if subfolder:
            folder = folder_tree.join_path([folder, subfolder])
        place = folder_tree.find_place(tree, folder)
        if place is None:
            place = folder_tree.fallback_place(tree)
            if place is None:
                metadata["review_note"] = folder_tree.NO_FOLDER_NOTE
                metadata["suggested_folder"] = folder_tree.clean_suggestion(
                    result.get("suggested_folder"), tree)
                return metadata
            # What fits nowhere goes to the catch-all, as a Classified file.
            metadata["review_note"] = None
            metadata["folder_reason"] = folder_tree.CATCH_ALL_REASON
        category, subcategory = folder_tree.first_two(place)
        metadata.update({"category": category, "subcategory": subcategory,
                         "folder_path": place})
        return metadata

    def validate_completeness(self, document):
        """Check whether all expected fields were filled in."""
        missing = [field for field in REQUIRED_FIELDS
                   if not getattr(document, field)]
        if missing:
            document.mark_needs_review(missing)
        # A category that is not in the project list needs a person.
        if document.review_note:
            document.mark_needs_review(["category"])
        return document

    def process_batch(self, file_list):
        """Run classify_document on every new file in a list."""
        documents = []
        for file_path in file_list:
            if self.db.has_file_path(file_path):
                continue
            try:
                documents.append(self.classify_document(file_path))
            except (OSError, ValueError):
                continue
        return documents
