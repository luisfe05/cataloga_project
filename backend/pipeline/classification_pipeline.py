"""ClassificationPipeline.

Orchestrates the full classification flow for a single file or a batch:
1. Extract the text from the file (PDF and plain text files only).
2. Ask the AI provider for the media type, a summary, and (in one
   request) the source, the document date, and a short topic.
3. Validate completeness: flag as Manual Review if any field is missing.
4. Build the new name from the project's naming template (naming.py) and
   move the file to the right subdirectory.
5. Hand the finished Document object to CatalogRepository for storage.

Photos, audio, and video are sorted into their folder by file extension.
Their content is never sent to the AI (that is out of scope for the MVP),
so they always end up in Manual Review for a manual summary. Files
without text are named with the file date and a number.

The template and the number come from this pipeline's own
CatalogRepository, so each catalog keeps its own naming method.
"""

import json
import os
from datetime import datetime

from pypdf import PdfReader

from backend.models.document import Document
from backend.pipeline import naming

# File types sorted by extension alone, without asking the AI.
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

# File types whose text the pipeline can read and send to the AI.
READABLE_EXTENSIONS = (".pdf", ".txt")

# Folder used when a file can't be read or the AI can't classify it.
FALLBACK_MEDIA_TYPE = "Documents"

# Fields that must be filled in for a document to count as Classified.
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

# Fields read from the AI's metadata answer.
METADATA_FIELDS = ("source", "document_date", "topic")


def now_timestamp():
    """Return the current time as an ISO string, e.g. 2026-10-21T16:55:00.

    Returns:
        str: The current local time, without microseconds.
    """
    return datetime.now().isoformat(timespec="seconds")


def extract_text(file_path):
    """Return the text inside a PDF or .txt file.

    Args:
        file_path (str): Path to the file.

    Returns:
        str: The text, or an empty string if the file can't be read. A
            scanned PDF with no text layer also gives an empty string.
    """
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
    """Turn the AI's JSON answer into a dict.

    Models sometimes wrap JSON in markdown fences like ```json ... ```,
    so those are removed first.

    Args:
        answer (str or None): The AI's raw answer.

    Returns:
        dict: The parsed object, or an empty dict if it isn't valid JSON.
    """
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
        """Set up the pipeline with its three dependencies.

        Args:
            ai_client: An AIProviderClient instance for making AI calls.
            catalog_repo: A CatalogRepository instance for database writes.
            file_organizer: A FileOrganizer instance for renaming and
                moving files.
        """
        self.ai_client = ai_client
        self.db = catalog_repo
        self.file_organizer = file_organizer

    def classify_document(self, file_path):
        """Run the full pipeline on a single file.

        Args:
            file_path (str): Absolute path to the file to process.

        Returns:
            Document: The finished Document object, already saved to
                the database.
        """
        original_filename = os.path.basename(file_path)
        date_added = now_timestamp()
        extension = os.path.splitext(file_path)[1].lower()

        media_type = None
        summary = None
        metadata = {"source": None, "document_date": None, "topic": None}
        has_text = False

        if extension in EXTENSION_MEDIA_TYPES:
            # Photos, audio, video: the extension decides the folder.
            media_type = EXTENSION_MEDIA_TYPES[extension]
        elif extension in READABLE_EXTENSIONS:
            text = extract_text(file_path)
            if text:
                has_text = True
                media_type = self.ai_client.send_classification_request(text)
                summary = self.generate_summary(text)
                metadata = self.extract_metadata(text)

        # If nothing decided the type, use the fallback folder. The empty
        # fields will send the document to Manual Review below.
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
        """Build the new file name with the project's naming method.

        Files with text use the template saved in this catalog. Files
        without text (photos, audio, video, scans) always use the file
        date and a number, whatever the method.

        Args:
            file_path (str): The file, still in the Drop Zone.
            has_text (bool): True if text was read from the file.
            metadata (dict): source, document_date, and topic from the AI.

        Returns:
            str: The new name, e.g. '2026-07-15_oceanman-malta.pdf'. The
                FileOrganizer adds -2, -3... if it is taken.
        """
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
        """Request a content summary from the AI provider.

        Args:
            text (str): Extracted text content of the document.

        Returns:
            str: Summary, capped at 100 characters. Empty string if the
                AI fails.
        """
        return self.ai_client.send_summary_request(text)

    def regenerate_summary(self, document):
        """Write a new summary that uses the source and date the user typed.

        Called after the user edits source or document_date in Edit Mode.
        Only works for files with readable text. If there is no text or
        the AI fails, the document is returned unchanged.

        Args:
            document (Document): The document after the user's edit.

        Returns:
            Document: The document, with the new summary saved if one was
                generated.
        """
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
        """Ask the AI to pull source, document date, and topic from the text.

        The topic comes in the same request as the source and date, so
        naming files does not add another call to the AI.

        Args:
            text (str): Extracted text content of the document.

        Returns:
            dict: {'source', 'document_date', 'topic'}, each a str or None.
        """
        answer = self.ai_client.ask(METADATA_PROMPT, text)
        result = parse_json_answer(answer)

        metadata = {}
        for field in METADATA_FIELDS:
            value = result.get(field)
            # Keep only real text. null, '', and 'null' all become None.
            if isinstance(value, str) and value.strip() and \
                    value.strip().lower() != "null":
                metadata[field] = value.strip()
            else:
                metadata[field] = None
        return metadata

    def validate_completeness(self, document):
        """Check whether all expected fields were filled in.

        If any field is empty, calls document.mark_needs_review() with a
        list of the missing field names, which sets status to
        'Manual Review'.

        Args:
            document (Document): The document to validate.

        Returns:
            Document: The same document, possibly with status updated.
        """
        missing = [field for field in REQUIRED_FIELDS
                   if not getattr(document, field)]
        if missing:
            document.mark_needs_review(missing)
        return document

    def process_batch(self, file_list):
        """Run classify_document on every new file in a list.

        Files that are already in the catalog are skipped, so running the
        same folder twice only processes the files added since. A file
        that fails (for example, it was deleted meanwhile) is skipped so
        the rest of the batch still runs.

        Args:
            file_list (list[str]): Absolute paths to the files to process.

        Returns:
            list[Document]: One Document per file processed.
        """
        documents = []
        for file_path in file_list:
            if self.db.has_file_path(file_path):
                continue
            try:
                documents.append(self.classify_document(file_path))
            except (OSError, ValueError):
                continue
        return documents
