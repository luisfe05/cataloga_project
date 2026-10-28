"""CatalogRepository."""

from datetime import datetime

from backend.db.schema import get_connection, DB_PATH
from backend.models.document import Document, LOCKED_FIELDS, MEDIA_TYPES

EDITABLE_FIELDS = ("source", "document_date", "summary", "media_type",
                   "status")

STATUSES = ("Classified", "Manual Review")

# Scope change of Oct 25 (was 500).
MAX_SUMMARY_LENGTH = 100

SINGLE_CONFIG_COLUMNS = ("language", "naming_template")

# Method 1. Same as naming.DEFAULT_TEMPLATE and schema.py.
DEFAULT_NAMING_TEMPLATE = "{date}_{topic}"

RECENT_ACTIVITY_LIMIT = 10


def now_timestamp():
    """Return the current time as an ISO string, e.g. 2026-10-21T16:55:00."""
    return datetime.now().isoformat(timespec="seconds")


def row_to_document(row):
    """Turn one row from the documents table into a Document object."""
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
        """Remember which database file to use."""
        self.db_path = db_path

    def log_activity(self, conn, doc_id, action, details=None):
        """Add one entry to activity_log, using an already open connection."""
        conn.execute(
            "INSERT INTO activity_log (document_id, action, timestamp, "
            "details) VALUES (?, ?, ?, ?)",
            (doc_id, action, now_timestamp(), details),
        )

    def add_document(self, doc):
        """Insert a new document row and log the 'Classified' event."""
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
            doc.id = cursor.lastrowid
            self.log_activity(conn, doc.id, doc.status)
            conn.commit()
        finally:
            conn.close()
        return doc

    def get_document(self, doc_id):
        """Return one document by its id."""
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
        """Return all documents, optionally filtered."""
        if filters is None:
            filters = {}

        # Values go in a separate list so SQLite fills the ? safely.
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
        """Return True if a document with this file_path is already saved."""
        conn = get_connection(self.db_path)
        try:
            row = conn.execute(
                "SELECT id FROM documents WHERE file_path = ?", (file_path,)
            ).fetchone()
        finally:
            conn.close()
        return row is not None

    def get_by_status(self, status):
        """Return all documents with the given status."""
        return self.get_all_documents({"status": status})

    def check_fields(self, fields):
        """Raise ValueError if any field in an update is not allowed."""
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
        """Update editable fields on a document."""
        # Check everything before touching the database.
        self.check_fields(fields)
        if self.get_document(doc_id) is None:
            raise KeyError(doc_id)
        if not fields:
            return self.get_document(doc_id)

        # Safe: column names come only from EDITABLE_FIELDS, never the user.
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

    def rename_document(self, doc_id, new_filename, new_path):
        """Save a new filename after a rename the user confirmed."""
        doc = self.get_document(doc_id)
        if doc is None:
            raise KeyError(doc_id)
        details = "{} → {}".format(doc.filename, new_filename)

        conn = get_connection(self.db_path)
        try:
            conn.execute(
                "UPDATE documents SET filename = ?, file_path = ? "
                "WHERE id = ?",
                (new_filename, new_path, doc_id),
            )
            self.log_activity(conn, doc_id, "Renamed", details)
            conn.commit()
        finally:
            conn.close()
        return self.get_document(doc_id)

    def get_project_summary(self):
        """Return the numbers the chat uses to describe the project."""
        conn = get_connection(self.db_path)
        try:
            status_rows = conn.execute(
                "SELECT status, COUNT(*) AS total FROM documents "
                "GROUP BY status"
            ).fetchall()
            type_rows = conn.execute(
                "SELECT media_type, COUNT(*) AS total FROM documents "
                "GROUP BY media_type"
            ).fetchall()
            source_rows = conn.execute(
                "SELECT source, COUNT(*) AS total FROM documents "
                "WHERE source IS NOT NULL AND source != '' "
                "GROUP BY source ORDER BY total DESC, source LIMIT 5"
            ).fetchall()
            dates = conn.execute(
                "SELECT MIN(document_date), MAX(document_date) "
                "FROM documents WHERE document_date IS NOT NULL "
                "AND document_date != ''"
            ).fetchone()
        finally:
            conn.close()

        by_status = {row["status"]: row["total"] for row in status_rows}
        # Start every media type at 0, like the dashboard.
        by_type = {media_type: 0 for media_type in MEDIA_TYPES}
        for row in type_rows:
            by_type[row["media_type"]] = row["total"]
        return {
            "total": sum(by_status.values()),
            "classified": by_status.get("Classified", 0),
            "manual_review": by_status.get("Manual Review", 0),
            "by_type": by_type,
            "top_sources": [{"source": row["source"],
                             "count": row["total"]}
                            for row in source_rows],
            "first_date": dates[0],
            "last_date": dates[1],
        }

    def get_dashboard_stats(self):
        """Return aggregate data for the dashboard."""
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
        """Return the single app_config row as a dict, or None if unset."""
        conn = get_connection(self.db_path)
        try:
            row = conn.execute(
                "SELECT research_name, target_directory, "
                "app_lock_password_hash, language, naming_template "
                "FROM app_config "
                "ORDER BY id LIMIT 1"
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return dict(row)

    def save_app_config(self, research_name, target_directory):
        """Save research_name and target_directory."""
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

    def save_config_value(self, column, value):
        """Save one setting in the app_config row."""
        if column not in SINGLE_CONFIG_COLUMNS:
            raise ValueError(column + " is not a single setting")
        conn = get_connection(self.db_path)
        try:
            row = conn.execute(
                "SELECT id FROM app_config ORDER BY id LIMIT 1"
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO app_config (research_name, "
                    "target_directory, " + column + ") VALUES ('', '', ?)",
                    (value,),
                )
            else:
                conn.execute(
                    "UPDATE app_config SET " + column + " = ? WHERE id = ?",
                    (value, row["id"]),
                )
            conn.commit()
        finally:
            conn.close()

    def save_language(self, language):
        """Save the interface language ('en' or 'es')."""
        self.save_config_value("language", language)

    def save_naming_template(self, template):
        """Save the file naming template, e.g. '{date}_{topic}'."""
        self.save_config_value("naming_template", template)

    def get_naming_template(self):
        """Return the saved naming template, or the default one."""
        config = self.get_app_config()
        if config and config["naming_template"]:
            return config["naming_template"]
        return DEFAULT_NAMING_TEMPLATE

    def next_number(self):
        """Return the number for the next file added to the catalog."""
        conn = get_connection(self.db_path)
        try:
            row = conn.execute(
                "SELECT MAX(id) AS highest FROM documents").fetchone()
        finally:
            conn.close()
        return (row["highest"] or 0) + 1

    def get_active_provider(self):
        """Return the active AI provider and model, or None if unset."""
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
        """Make one provider the active one and store its model."""
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
