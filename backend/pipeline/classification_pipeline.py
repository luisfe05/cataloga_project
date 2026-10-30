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

# Needed to count as Classified.
REQUIRED_FIELDS = ("source", "document_date", "summary")

# A photo rarely shows its source or date, so only the summary is needed.
PHOTO_REQUIRED_FIELDS = ("summary",)

METADATA_PROMPT = """You are helping a researcher catalog an archive.
From the document text, find:
- source: who published or created the document (a newspaper, magazine,
  organization, or person).
- document_date: the date written on the document itself, as YYYY-MM-DD.
  If only the year and month are known use YYYY-MM, if only the year is
  known use YYYY.
- topic: the main subject of the document in 2 to 4 words, in the
  document's language. It is used in the file name.
- keywords: 3 to 5 short keywords for searching, each under 40
  characters, in the document's language.
- counterparty: the other person or organization the document is with
  or addressed to (for example the other side of a contract or letter).

Use null for anything the text does not say. Do not guess.

Respond with ONLY a JSON object in this exact format:
{"source": "...", "document_date": "...", "topic": "...",
 "keywords": ["...", "...", "..."], "counterparty": "..."}"""

# Added to METADATA_PROMPT when the project has a category list.
CATEGORY_PROMPT = """

Also choose where the document belongs in this list of categories:
{categories}
Add "category" with one category name exactly as written, and
"subcategory" with one of its subcategories (null if it has none).
If nothing in the list fits, use null for both."""

# Added to METADATA_PROMPT in projects with their own folder tree.
FOLDER_PROMPT = """

This project is about: {description}
These are its folders, at most two levels:
{folders}
Choose the folder where an archivist would file this document, by what
it is about, not by its file type. Add "folder" with one top folder name
exactly as written, and "subfolder" with one of its subfolders exactly
as written (null if that folder has none). Never force a document into
a folder made for something else. If no folder fits, use null for both
and always add "suggested_folder": {{"parent": "<a top folder name, or
null for a new top folder>", "name": "<new folder name, 1 to 3 words>"}}.
Answer with one JSON object only."""

METADATA_FIELDS = ("source", "document_date", "topic")

# How many of the user's moves the AI reads before filing a document.
MAX_CORRECTIONS = 10

# Added after FOLDER_PROMPT when the user has moved files by hand.
CORRECTIONS_PROMPT = """

The researcher moved these files by hand, newest first. Learn from them
where this kind of file belongs:
{corrections}"""


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


def missing_note(document, required=REQUIRED_FIELDS):
    """Return the note that lists the empty required fields."""
    missing = [field for field in required if not getattr(document, field)]
    return archive_rules.MISSING_NOTE.format(", ".join(missing))


def required_fields(document):
    """Return the fields a document needs to count as Classified."""
    if document.media_type == "Photos":
        return PHOTO_REQUIRED_FIELDS
    return REQUIRED_FIELDS


def needs_nothing(document):
    """Say whether a document has every field and no open review note."""
    if document.review_note or document.duplicate_of:
        return False
    return all(getattr(document, field)
               for field in required_fields(document))


def with_metadata(text, meta):
    """Put the useful file metadata in front of the text for the AI."""
    lines = file_metadata.metadata_text(meta)
    if not lines:
        return text
    return ("File metadata (saved by whoever made the file; if it disagrees "
            "with the document text, the text is right):\n" + lines +
            "\n\nDocument text:\n" + text)


def choose_date(content_date, file_path, taken=None, meta_date=None):
    """Pick the date and say where it came from, in order of trust."""
    if taken:
        return taken, "photo"
    if content_date:
        return content_date, "content"
    if meta_date:
        return meta_date, "metadata"
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
        if not self.db.is_tree_project():
            return self.file_organizer.folder_for(media_type), True
        if metadata["category"]:
            return self.file_organizer.tree_folder(
                metadata["category"], metadata["subcategory"]), True
        # No folder fits: the file stays in the Drop Zone for a person.
        return os.path.dirname(file_path), False

    def classify_document(self, file_path):
        """Run the full pipeline on a single file."""
        original_filename = os.path.basename(file_path)
        date_added = now_timestamp()
        extension = os.path.splitext(file_path)[1].lower()

        # Hash first: a duplicate never reaches the AI.
        sha256 = archive_rules.sha256_of(file_path)
        original = self.db.find_by_sha256(sha256)
        if original is not None:
            return self.add_duplicate(file_path, sha256, original)

        media_type = None
        summary = None
        metadata = self.empty_metadata()
        has_text = False
        # Why the file needs a person, when it is known before the AI.
        reason = None
        required = REQUIRED_FIELDS
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
                text = ("Metadata of an " if kind == "Audio" else
                        "Metadata of a ") + kind.lower() + (
                    " file. It was not listened to; use only these facts:\n"
                    + file_metadata.metadata_text(file_meta))
                has_text = True
                summary = self.generate_summary(text)
                metadata = self.extract_metadata(text)
                # The date of a recording comes from its tags, below.
                metadata["document_date"] = None
        elif (extension in file_readers.VISION_EXTENSIONS and
              self.ai_client.supports_images):
            media_type = "Photos"
            required = PHOTO_REQUIRED_FIELDS
            taken = file_readers.photo_date(file_path)
            text = self.read_images([file_readers.photo_data_uri(file_path)],
                                    "photo")
            if text:
                has_text = True
                summary = self.generate_summary(text)
                metadata = self.extract_metadata(text)
                # The name must come from what the photo shows.
                if not metadata["topic"]:
                    reason = archive_rules.TOPIC_NOTE
            else:
                reason = archive_rules.IMAGE_NOTE
        elif kind:
            media_type = kind
            if kind == "Photos":
                taken = file_readers.photo_date(file_path)
        elif extension in READABLE_EXTENSIONS:
            file_meta = file_metadata.document_metadata(file_path)
            text = extract_text(file_path)
            if (not text and extension == ".pdf" and
                    self.ai_client.supports_images):
                # A scanned PDF: its first pages go to the AI as images.
                text = self.read_images(
                    file_readers.pdf_page_data_uris(file_path), "scan")
                if not text:
                    reason = archive_rules.SCAN_NOTE
            if text:
                has_text = True
                text = with_metadata(text, file_meta)
                media_type = self.ai_client.send_classification_request(text)
                summary = self.generate_summary(text)
                metadata = self.extract_metadata(text)

        # Empty fields send the document to Manual Review below.
        if media_type is None:
            media_type = FALLBACK_MEDIA_TYPE

        date, date_source = choose_date(
            metadata["document_date"], file_path, taken,
            file_meta.get("date") or file_meta.get("created"))
        metadata["document_date"] = date

        new_filename = self.build_filename(file_path, has_text, metadata,
                                           date_source)
        folder, placed = self.destination(file_path, media_type, metadata)
        new_path = self.file_organizer.move_to_folder(file_path, folder,
                                                      new_filename)

        document = Document(
            original_filename=original_filename,
            filename=os.path.basename(new_path),
            media_type=media_type,
            file_path=new_path,
            date_added=date_added,
            source=metadata["source"],
            document_date=metadata["document_date"],
            summary=summary or None,
            date_classified=now_timestamp(),
            topic=metadata["topic"],
            keywords=metadata["keywords"],
            counterparty=metadata["counterparty"],
            category=metadata["category"],
            subcategory=metadata["subcategory"],
            review_note=reason or metadata["review_note"],
            suggested_folder=metadata["suggested_folder"],
            date_source=date_source,
            sha256=sha256,
            confidentiality=archive_rules.DEFAULT_CONFIDENTIALITY,
            owner=self.owner,
        )
        self.validate_completeness(document, required)
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
            document.review_note = missing_note(document, required)
        return self.db.add_document(document)

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

    def build_filename(self, file_path, has_text, metadata, date_source):
        """Build the new file name with the project's naming method."""
        original_filename = os.path.basename(file_path)
        extension = os.path.splitext(file_path)[1]
        number = self.db.next_number()
        # The disk date changes when files are copied, so names say undated.
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
                topic_number=topic_number)
        else:
            template = naming.NO_TEXT_TEMPLATE
            parts = naming.build_parts(original_filename, number,
                                       document_date=name_date)
        return naming.make_filename(template, parts, extension)

    def generate_summary(self, text):
        """Request a content summary from the AI provider."""
        return self.ai_client.send_summary_request(text)

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
        """Return the metadata of a file the AI did not read."""
        return {"source": None, "document_date": None, "topic": None,
                "keywords": [], "counterparty": None, "category": None,
                "subcategory": None, "review_note": None,
                "suggested_folder": None}

    def extract_metadata(self, text):
        """Ask the AI for the metadata, then check every field it sent."""
        categories = self.db.get_categories()
        tree_mode = self.db.is_tree_project()
        prompt = METADATA_PROMPT
        if tree_mode:
            prompt += self.folder_prompt(categories)
        elif categories:
            prompt += CATEGORY_PROMPT.format(categories=json.dumps(
                categories, ensure_ascii=False))
        result = parse_json_answer(self.ai_client.ask(prompt, text))

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
        metadata["keywords"] = archive_rules.clean_keywords(
            result.get("keywords"))
        metadata["counterparty"] = archive_rules.clean_text(
            result.get("counterparty"), archive_rules.MAX_COUNTERPARTY_LENGTH)
        if tree_mode:
            return self.match_folder(metadata, result, categories)
        category, subcategory, note = archive_rules.match_category(
            categories,
            archive_rules.clean_text(result.get("category"), 200),
            archive_rules.clean_text(result.get("subcategory"), 200))
        metadata.update({"category": category, "subcategory": subcategory,
                         "review_note": note})
        return metadata

    def folder_prompt(self, tree):
        """Return the part of the prompt with the project's folder tree."""
        folders = [{"folder": top["name"], "subfolders": top["subcategories"]}
                   for top in tree]
        prompt = FOLDER_PROMPT.format(
            description=self.db.get_project_description() or "(not given)",
            folders=json.dumps(folders, ensure_ascii=False))
        return prompt + self.corrections_prompt()

    def corrections_prompt(self):
        """Return the user's latest moves as lines for the AI, or ''."""
        lines = []
        for move in self.db.recent_corrections(MAX_CORRECTIONS):
            about = " (about: {})".format(move["summary"]) \
                if move["summary"] else ""
            lines.append("- \"{}\"{} went from {} to {}".format(
                move["original_filename"], about,
                move["from_folder"] or "the Drop Zone", move["to_folder"]))
        if not lines:
            return ""
        return CORRECTIONS_PROMPT.format(corrections="\n".join(lines))

    def match_folder(self, metadata, result, tree):
        """Keep the AI's folder if it is in the tree; else a suggestion."""
        folder, subfolder, note = archive_rules.match_category(
            tree,
            archive_rules.clean_text(result.get("folder"), 200),
            archive_rules.clean_text(result.get("subfolder"), 200))
        if note:
            # Half a match (a folder without its subfolder) is no match.
            metadata["review_note"] = folder_tree.NO_FOLDER_NOTE
            metadata["suggested_folder"] = folder_tree.clean_suggestion(
                result.get("suggested_folder"), tree)
            return metadata
        metadata.update({"category": folder, "subcategory": subfolder})
        return metadata

    def validate_completeness(self, document, required=REQUIRED_FIELDS):
        """Check whether all expected fields were filled in."""
        missing = [field for field in required
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
