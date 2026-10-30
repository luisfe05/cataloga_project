"""Document model."""

# Valid values, per the Stage 3 report.
MEDIA_TYPES = ("Press", "Audio", "Video", "Photos", "Documents")

LOCKED_FIELDS = ("original_filename", "filename")

# Fields of the Digital Archiving Guideline, added after the first release.
ARCHIVE_FIELDS = ("topic", "keywords", "sha256", "duplicate_of",
                  "review_note", "counterparty", "confidentiality", "owner",
                  "effective_start", "effective_end", "category",
                  "subcategory", "date_source")


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
        **archive_fields
    ):
        """Build a Document. archive_fields are the ARCHIVE_FIELDS."""
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
        for name in archive_fields:
            if name not in ARCHIVE_FIELDS:
                raise TypeError("Unknown Document field: " + name)
        for name in ARCHIVE_FIELDS:
            setattr(self, name, archive_fields.get(name))
        # keywords is always a list, never None.
        self.keywords = self.keywords or []

    def to_dict(self):
        """Return all fields as a plain dictionary for JSON serialization."""
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
            **{name: getattr(self, name) for name in ARCHIVE_FIELDS},
        }

    def mark_needs_review(self, missing_fields):
        """Set status to 'Manual Review' and record the missing fields."""
        self.status = "Manual Review"

    def is_locked_field(self, field_name):
        """Return True if field_name must not be edited by the user."""
        return field_name in LOCKED_FIELDS
