"""ClassificationPipeline."""

import json
import os
from datetime import datetime

from pypdf import PdfReader

from backend.models.document import Document
from backend.pipeline import archive_rules, naming

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

READABLE_EXTENSIONS = (".pdf", ".txt")

# Used when a file can't be read or classified.
FALLBACK_MEDIA_TYPE = "Documents"

# Needed to count as Classified.
REQUIRED_FIELDS = ("source", "document_date", "summary")

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

METADATA_FIELDS = ("source", "document_date", "topic")


def now_timestamp():
    """Return the current time as an ISO string, e.g. 2026-10-21T16:55:00."""
    return datetime.now().isoformat(timespec="seconds")


def extract_text(file_path):
    """Return the text inside a PDF or .txt file."""
    extension = os.path.splitext(file_path)[1].lower()
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
    """Turn the AI's JSON answer into a dict."""
    if not answer:
        return {}
    text = answer.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        return {}
    if not isinstance(result, dict):
        return {}
    return result


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

        if extension in EXTENSION_MEDIA_TYPES:
            media_type = EXTENSION_MEDIA_TYPES[extension]
        elif extension in READABLE_EXTENSIONS:
            text = extract_text(file_path)
            if text:
                has_text = True
                media_type = self.ai_client.send_classification_request(text)
                summary = self.generate_summary(text)
                metadata = self.extract_metadata(text)

        # Empty fields send the document to Manual Review below.
        if media_type is None:
            media_type = FALLBACK_MEDIA_TYPE

        new_filename = self.build_filename(file_path, has_text, metadata)
        new_path = self.file_organizer.move_and_rename_file(
            file_path, media_type, new_filename)

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
            review_note=metadata["review_note"],
            sha256=sha256,
            confidentiality=archive_rules.DEFAULT_CONFIDENTIALITY,
            owner=self.owner,
        )
        self.validate_completeness(document)
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

    def build_filename(self, file_path, has_text, metadata):
        """Build the new file name with the project's naming method."""
        original_filename = os.path.basename(file_path)
        extension = os.path.splitext(file_path)[1]
        number = self.db.next_number()
        if has_text:
            template = self.db.get_naming_template()
            topic_number = naming.next_topic_number(
                metadata["topic"] or original_filename, self.db.get_topics())
            parts = naming.build_parts(
                original_filename, number,
                document_date=metadata["document_date"],
                source=metadata["source"],
                topic=metadata["topic"],
                topic_number=topic_number)
        else:
            template = naming.NO_TEXT_TEMPLATE
            parts = naming.build_parts(
                original_filename, number,
                document_date=naming.file_date(file_path))
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
                "subcategory": None, "review_note": None}

    def extract_metadata(self, text):
        """Ask the AI for the metadata, then check every field it sent."""
        categories = self.db.get_categories()
        prompt = METADATA_PROMPT
        if categories:
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
        if metadata["topic"]:
            metadata["topic"] = metadata["topic"][
                :archive_rules.MAX_TOPIC_LENGTH]
        metadata["keywords"] = archive_rules.clean_keywords(
            result.get("keywords"))
        metadata["counterparty"] = archive_rules.clean_text(
            result.get("counterparty"), archive_rules.MAX_COUNTERPARTY_LENGTH)
        category, subcategory, note = archive_rules.match_category(
            categories,
            archive_rules.clean_text(result.get("category"), 200),
            archive_rules.clean_text(result.get("subcategory"), 200))
        metadata.update({"category": category, "subcategory": subcategory,
                         "review_note": note})
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
