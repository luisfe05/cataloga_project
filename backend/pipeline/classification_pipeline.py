"""ClassificationPipeline."""

import json
import os
from datetime import datetime

from pypdf import PdfReader

from backend.models.document import Document
from backend.pipeline import naming

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

Use null for anything the text does not say. Do not guess.

Respond with ONLY a JSON object in this exact format:
{"source": "...", "document_date": "...", "topic": "..."}"""

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


class ClassificationPipeline:
    """Runs the classify-summarize-organize-catalog flow."""

    def __init__(self, ai_client, catalog_repo, file_organizer):
        """Set up the pipeline with its three dependencies."""
        self.ai_client = ai_client
        self.db = catalog_repo
        self.file_organizer = file_organizer

    def classify_document(self, file_path):
        """Run the full pipeline on a single file."""
        original_filename = os.path.basename(file_path)
        date_added = now_timestamp()
        extension = os.path.splitext(file_path)[1].lower()

        media_type = None
        summary = None
        metadata = {"source": None, "document_date": None, "topic": None}
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
        )
        self.validate_completeness(document)
        return self.db.add_document(document)

    def build_filename(self, file_path, has_text, metadata):
        """Build the new file name with the project's naming method."""
        original_filename = os.path.basename(file_path)
        extension = os.path.splitext(file_path)[1]
        number = self.db.next_number()
        if has_text:
            template = self.db.get_naming_template()
            parts = naming.build_parts(
                original_filename, number,
                document_date=metadata["document_date"],
                source=metadata["source"],
                topic=metadata["topic"])
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

    def extract_metadata(self, text):
        """Ask the AI for the source, document date, and topic."""
        answer = self.ai_client.ask(METADATA_PROMPT, text)
        result = parse_json_answer(answer)

        metadata = {}
        for field in METADATA_FIELDS:
            value = result.get(field)
            # null, '', and 'null' all become None.
            if isinstance(value, str) and value.strip() and \
                    value.strip().lower() != "null":
                metadata[field] = value.strip()
            else:
                metadata[field] = None
        return metadata

    def validate_completeness(self, document):
        """Check whether all expected fields were filled in."""
        missing = [field for field in REQUIRED_FIELDS
                   if not getattr(document, field)]
        if missing:
            document.mark_needs_review(missing)
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
