"""Document model.

Represents one row in the documents table, which corresponds to one
classified file in the archive. Locked fields (original_filename, filename)
cannot be changed after the document is created.
"""

# Valid values for media_type, per the Stage 3 report.
MEDIA_TYPES = ("Press", "Audio", "Video", "Photos", "Documents")

# Fields the user is never allowed to edit.
LOCKED_FIELDS = ("original_filename", "filename")


class Document:
    """One cataloged research file."""

    def __init__(
        self,
        original_filename,
        filename,
        media_type,
        file_path,
        date_added,
        doc_id=None,
        source=None,
        document_date=None,
        summary=None,
        status="Classified",
        date_classified=None,
    ):
        """Build a Document.

        Args:
            original_filename (str): The file's name before
                classification. Locked.
            filename (str): The generated serial name (e.g. D_001.pdf). Locked.
            media_type (str): One of MEDIA_TYPES.
            file_path (str): Absolute path to the file after it was moved.
            date_added (str): ISO timestamp when the file was added to
                the archive.
            doc_id (int, optional): Primary key once the row is saved
                to the DB.
            source (str, optional): Where the document came from.
            document_date (str, optional): The date on the document itself.
            summary (str, optional): AI-generated summary, up to 100
                characters.
            status (str): 'Classified' or 'Manual Review'. Defaults to
                'Classified'.
            date_classified (str, optional): ISO timestamp of classification.
        """
        self.id = doc_id
        self.original_filename = original_filename
        self.filename = filename
        self.media_type = media_type
        self.file_path = file_path
        self.date_added = date_added
        self.source = source
        self.document_date = document_date
        self.summary = summary
        self.status = status
        self.date_classified = date_classified

    def to_dict(self):
        """Return all fields as a plain dictionary for JSON serialization.

        Returns:
            dict: All document fields.
        """
        return {
            "id": self.id,
            "original_filename": self.original_filename,
            "filename": self.filename,
            "media_type": self.media_type,
            "source": self.source,
            "document_date": self.document_date,
            "summary": self.summary,
            "status": self.status,
            "file_path": self.file_path,
            "date_added": self.date_added,
            "date_classified": self.date_classified,
        }

    def mark_needs_review(self, missing_fields):
        """Set status to 'Manual Review' and record which fields are missing.

        Called by ClassificationPipeline.validate_completeness() when any
        expected field came back empty from the AI.

        Args:
            missing_fields (list[str]): Names of fields that are empty.
        """
        self.status = "Manual Review"

    def is_locked_field(self, field_name):
        """Return True if field_name must not be edited by the user.

        Args:
            field_name (str): The field to check.

        Returns:
            bool: True if the field is locked.
        """
        return field_name in LOCKED_FIELDS
