"""CatalogRepository.

The single place in the codebase that reads from and writes to the database.
All other modules call methods here instead of running SQL directly.
"""

from datetime import datetime

from backend.db.schema import get_connection, DB_PATH
from backend.models.document import Document, LOCKED_FIELDS, MEDIA_TYPES

# Fields the user is allowed to change through update_document().
EDITABLE_FIELDS = ("source", "document_date", "summary", "media_type",
                   "status")

# Valid values for the status column.
STATUSES = ("Classified", "Manual Review")

# Longest summary allowed (scope change of Oct 25, was 500).
MAX_SUMMARY_LENGTH = 100

# How many entries the dashboard's recent activity list shows.
RECENT_ACTIVITY_LIMIT = 10


def now_timestamp():
    """Return the current time as an ISO string, e.g. 2026-10-21T16:55:00.

    Returns:
        str: The current local time, without microseconds.
    """
    return datetime.now().isoformat(timespec="seconds")


def row_to_document(row):
    """Turn one row from the documents table into a Document object.

    Args:
        row (sqlite3.Row): A row that includes every documents column.

    Returns:
        Document: The matching Document object.
    """
    return Document(
        doc_id=row["id"],
        original_filename=row["original_filename"],
        filename=row["filename"],
        media_type=row["media_type"],
        source=row["source"],
        document_date=row["document_date"],
        summary=row["summary"],
        status=row["status"],
        file_path=row["file_path"],
        date_added=row["date_added"],
        date_classified=row["date_classified"],
    )


class CatalogRepository:
    """Owns all database reads and writes for documents and activity_log."""

    def __init__(self, db_path=DB_PATH):
        """Remember which database file to use.

        Args:
            db_path (str): Path to the SQLite file. Defaults to
                database/catalog.db. Tests pass a temporary file.
        """
        self.db_path = db_path

    def log_activity(self, conn, doc_id, action):
        """Add one entry to activity_log, using an already open connection.

        The caller commits, so the document change and its log entry are
        saved together.

        Args:
            conn (sqlite3.Connection): The open connection to use.
            doc_id (int): The document the action happened to.
            action (str): Short description, e.g. 'Classified' or 'Edited'.
        """
        conn.execute(
            "INSERT INTO activity_log (document_id, action, timestamp) "
            "VALUES (?, ?, ?)",
            (doc_id, action, now_timestamp()),
        )

    def add_document(self, doc):
        """Insert a new document row and log the 'Classified' event.

        Args:
            doc (Document): The document to save.

        Returns:
            Document: The same document with its id set from the new row.
        """
        conn = get_connection(self.db_path)
        try:
            cursor = conn.execute(
                "INSERT INTO documents (original_filename, filename, "
                "media_type, source, document_date, summary, status, "
                "file_path, date_added, date_classified) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (doc.original_filename, doc.filename, doc.media_type,
                 doc.source, doc.document_date, doc.summary, doc.status,
                 doc.file_path, doc.date_added, doc.date_classified),
            )
            # lastrowid is the id SQLite gave the new row.
            doc.id = cursor.lastrowid
            self.log_activity(conn, doc.id, doc.status)
            conn.commit()
        finally:
            conn.close()
        return doc

    def get_document(self, doc_id):
        """Return one document by its id.

        Args:
            doc_id (int): The document's primary key.

        Returns:
            Document or None: The document, or None if the id does not exist.
        """
        conn = get_connection(self.db_path)
        try:
            row = conn.execute(
                "SELECT * FROM documents WHERE id = ?", (doc_id,)
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return row_to_document(row)

    def get_all_documents(self, filters=None):
        """Return all documents, optionally filtered.

        Args:
            filters (dict, optional): Keys: media_type, source, status,
                search. Empty or missing keys are ignored. search looks
                for the text inside the filenames, source, and summary.

        Returns:
            list[Document]: Matching documents, oldest first.
        """
        if filters is None:
            filters = {}

        # Build the WHERE clause one condition at a time. The values go in
        # a separate list so SQLite fills the ? placeholders safely.
        conditions = []
        values = []
        for field in ("media_type", "source", "status"):
            if filters.get(field):
                conditions.append(field + " = ?")
                values.append(filters[field])

        if filters.get("search"):
            conditions.append(
                "(original_filename LIKE ? OR filename LIKE ? "
                "OR source LIKE ? OR summary LIKE ?)"
            )
            pattern = "%" + filters["search"] + "%"
            values.extend([pattern, pattern, pattern, pattern])

        query = "SELECT * FROM documents"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY id"

        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(query, values).fetchall()
        finally:
            conn.close()
        return [row_to_document(row) for row in rows]

    def has_file_path(self, file_path):
        """Return True if a document with this file_path is already saved.

        ClassificationPipeline uses this to skip files that were already
        processed, so only new files are sent to the AI.

        Args:
            file_path (str): Absolute path of the file.

        Returns:
            bool: True if the path is already in the documents table.
        """
        conn = get_connection(self.db_path)
        try:
            row = conn.execute(
                "SELECT id FROM documents WHERE file_path = ?", (file_path,)
            ).fetchone()
        finally:
            conn.close()
        return row is not None

    def get_by_status(self, status):
        """Return all documents with the given status.

        Args:
            status (str): 'Classified' or 'Manual Review'.

        Returns:
            list[Document]: Matching documents.
        """
        return self.get_all_documents({"status": status})

    def check_fields(self, fields):
        """Raise ValueError if any field in an update is not allowed.

        Args:
            fields (dict): Field names and new values from the user.

        Raises:
            ValueError: With a message that explains the problem.
        """
        for name in fields:
            if name in LOCKED_FIELDS:
                raise ValueError(name + " is locked and cannot be edited")
            if name not in EDITABLE_FIELDS:
                raise ValueError(name + " is not an editable field")

        if "media_type" in fields and fields["media_type"] not in MEDIA_TYPES:
            raise ValueError("media_type must be one of: " +
                             ", ".join(MEDIA_TYPES))
        if "status" in fields and fields["status"] not in STATUSES:
            raise ValueError("status must be one of: " + ", ".join(STATUSES))
        summary = fields.get("summary")
        if summary is not None and len(summary) > MAX_SUMMARY_LENGTH:
            raise ValueError("summary must be {} characters or less"
                             .format(MAX_SUMMARY_LENGTH))

    def update_document(self, doc_id, fields):
        """Update editable fields on a document.

        Rejects any attempt to change original_filename or filename with a
        ValueError, which the route will translate into a 400 response.

        Args:
            doc_id (int): The document's primary key.
            fields (dict): Field names and new values.

        Returns:
            Document: The updated document.

        Raises:
            ValueError: If fields has a locked, unknown, or invalid value.
            KeyError: If doc_id does not exist.
        """
        # Check everything before touching the database.
        self.check_fields(fields)
        if self.get_document(doc_id) is None:
            raise KeyError(doc_id)
        if not fields:
            return self.get_document(doc_id)

        # Column names come only from EDITABLE_FIELDS (checked above),
        # never straight from the user, so building the SET part is safe.
        set_parts = [name + " = ?" for name in fields]
        values = list(fields.values())
        values.append(doc_id)

        conn = get_connection(self.db_path)
        try:
            conn.execute(
                "UPDATE documents SET " + ", ".join(set_parts) +
                " WHERE id = ?",
                values,
            )
            self.log_activity(conn, doc_id, "Edited")
            conn.commit()
        finally:
            conn.close()
        return self.get_document(doc_id)

    def get_dashboard_stats(self):
        """Return aggregate data for the dashboard.

        Returns:
            dict: {
                'documents_classified': int,
                'needs_manual_review': int,
                'sources_tracked': int,
                'media_type_breakdown': {type: count, ...},
                'recent_activity': [{'filename': str, 'action': str,
                                     'timestamp': str}, ...]
            }
        """
        conn = get_connection(self.db_path)
        try:
            classified = conn.execute(
                "SELECT COUNT(*) FROM documents WHERE status = 'Classified'"
            ).fetchone()[0]
            manual_review = conn.execute(
                "SELECT COUNT(*) FROM documents "
                "WHERE status = 'Manual Review'"
            ).fetchone()[0]
            sources = conn.execute(
                "SELECT COUNT(DISTINCT source) FROM documents "
                "WHERE source IS NOT NULL AND source != ''"
            ).fetchone()[0]
            type_rows = conn.execute(
                "SELECT media_type, COUNT(*) AS total FROM documents "
                "GROUP BY media_type"
            ).fetchall()
            activity_rows = conn.execute(
                "SELECT documents.filename, activity_log.action, "
                "activity_log.timestamp FROM activity_log "
                "JOIN documents ON documents.id = activity_log.document_id "
                "ORDER BY activity_log.id DESC LIMIT ?",
                (RECENT_ACTIVITY_LIMIT,),
            ).fetchall()
        finally:
            conn.close()

        # Start every media type at 0 so the dashboard always shows all 5.
        breakdown = {media_type: 0 for media_type in MEDIA_TYPES}
        for row in type_rows:
            breakdown[row["media_type"]] = row["total"]

        recent = [
            {"filename": row["filename"], "action": row["action"],
             "timestamp": row["timestamp"]}
            for row in activity_rows
        ]

        return {
            "documents_classified": classified,
            "needs_manual_review": manual_review,
            "sources_tracked": sources,
            "media_type_breakdown": breakdown,
            "recent_activity": recent,
        }

    def get_app_config(self):
        """Return the single app_config row as a dict, or None if unset.

        Returns:
            dict or None: {'research_name', 'target_directory',
                'app_lock_password_hash'}, or None before first setup.
        """
        conn = get_connection(self.db_path)
        try:
            row = conn.execute(
                "SELECT research_name, target_directory, "
                "app_lock_password_hash FROM app_config ORDER BY id LIMIT 1"
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return dict(row)

    def save_app_config(self, research_name, target_directory):
        """Save research_name and target_directory.

        The app has only one app_config row: it is created the first time
        and updated after that.

        Args:
            research_name (str): Name of the current research project.
            target_directory (str): Path to the archive folder.
        """
        conn = get_connection(self.db_path)
        try:
            row = conn.execute(
                "SELECT id FROM app_config ORDER BY id LIMIT 1"
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO app_config (research_name, "
                    "target_directory) VALUES (?, ?)",
                    (research_name, target_directory),
                )
            else:
                conn.execute(
                    "UPDATE app_config SET research_name = ?, "
                    "target_directory = ? WHERE id = ?",
                    (research_name, target_directory, row["id"]),
                )
            conn.commit()
        finally:
            conn.close()

    def get_active_provider(self):
        """Return the active AI provider and model, or None if unset.

        Returns:
            dict or None: {'provider_name': str, 'model': str}
        """
        conn = get_connection(self.db_path)
        try:
            row = conn.execute(
                "SELECT provider_name, model FROM ai_provider_config "
                "WHERE is_active = 1 LIMIT 1"
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return dict(row)

    def set_active_provider(self, provider_name, model):
        """Make one provider the active one and store its model.

        Every other provider is marked inactive first, so only one is
        active at a time. The API key is never stored here.

        Args:
            provider_name (str): e.g. 'gemini'.
            model (str): e.g. 'gemini-2.5-flash'.
        """
        conn = get_connection(self.db_path)
        try:
            conn.execute("UPDATE ai_provider_config SET is_active = 0")
            row = conn.execute(
                "SELECT id FROM ai_provider_config WHERE provider_name = ?",
                (provider_name,),
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO ai_provider_config (provider_name, model, "
                    "is_active) VALUES (?, ?, 1)",
                    (provider_name, model),
                )
            else:
                conn.execute(
                    "UPDATE ai_provider_config SET model = ?, is_active = 1 "
                    "WHERE id = ?",
                    (model, row["id"]),
                )
            conn.commit()
        finally:
            conn.close()
