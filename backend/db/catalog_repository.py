"""CatalogRepository."""

import json
import os
from datetime import datetime

from backend.db.schema import get_connection, DB_PATH
from backend.models.document import (ARCHIVE_FIELDS, Document, LOCKED_FIELDS,
                                     MEDIA_TYPES)
from backend.pipeline import archive_rules, folder_tree
from backend.pipeline.file_organizer import DROP_ZONE_FOLDER

EDITABLE_FIELDS = ("source", "document_date", "summary", "media_type",
                   "status", "keywords", "counterparty", "confidentiality",
                   "owner", "effective_start", "effective_end", "category",
                   "subcategory")

# Every column add_document() writes, in order.
INSERT_COLUMNS = ("original_filename", "filename", "media_type", "source",
                  "document_date", "summary", "status", "file_path",
                  "date_added", "date_classified") + ARCHIVE_FIELDS

STATUSES = ("Classified", "Manual Review")

# Scope change of Oct 25 (was 500).
MAX_SUMMARY_LENGTH = 100

SINGLE_CONFIG_COLUMNS = ("language", "naming_template", "industry",
                         "categories", "folder_mode", "project_description")

# Method 1. Same as naming.DEFAULT_TEMPLATE and schema.py.
DEFAULT_NAMING_TEMPLATE = "{date}_{topic}"

RECENT_ACTIVITY_LIMIT = 10


def now_timestamp():
    """Return the current time as an ISO string, e.g. 2026-10-21T16:55:00."""
    return datetime.now().isoformat(timespec="seconds")


def row_to_document(row):
    """Turn one row from the documents table into a Document object."""
    archive_fields = {name: row[name] for name in ARCHIVE_FIELDS}
    archive_fields["keywords"] = archive_rules.keywords_from_text(
        row["keywords"])
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
        **archive_fields
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
            values = [getattr(doc, name) for name in INSERT_COLUMNS]
            values[INSERT_COLUMNS.index("keywords")] = \
                archive_rules.keywords_to_text(doc.keywords)
            cursor = conn.execute(
                "INSERT INTO documents (" + ", ".join(INSERT_COLUMNS) +
                ") VALUES (" + ", ".join("?" * len(INSERT_COLUMNS)) + ")",
                values,
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
        for field in ("media_type", "source", "status", "category",
                      "subcategory"):
            if filters.get(field):
                conditions.append(field + " = ?")
                values.append(filters[field])

        if filters.get("search"):
            conditions.append(
                "(original_filename LIKE ? OR filename LIKE ? "
                "OR source LIKE ? OR summary LIKE ? OR keywords LIKE ? "
                "OR counterparty LIKE ?)"
            )
            pattern = "%" + filters["search"] + "%"
            values.extend([pattern] * 6)

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

    def find_by_sha256(self, sha256):
        """Return the first cataloged document with this hash, or None."""
        conn = get_connection(self.db_path)
        try:
            row = conn.execute(
                "SELECT * FROM documents WHERE sha256 = ? "
                "AND duplicate_of IS NULL ORDER BY id LIMIT 1", (sha256,)
            ).fetchone()
        finally:
            conn.close()
        return row_to_document(row) if row else None

    def get_duplicates(self):
        """Return the rows of duplicate files left in the Drop Zone."""
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM documents WHERE duplicate_of IS NOT NULL "
                "ORDER BY id").fetchall()
        finally:
            conn.close()
        return [row_to_document(row) for row in rows]

    def delete_document(self, doc_id):
        """Remove one row and its activity. Never touches a file."""
        conn = get_connection(self.db_path)
        try:
            conn.execute("DELETE FROM activity_log WHERE document_id = ?",
                         (doc_id,))
            conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            conn.commit()
        finally:
            conn.close()

    def move_document(self, doc_id, new_path, folder, subfolder):
        """Save a document's new folder after a move the user asked for."""
        doc = self.get_document(doc_id)
        if doc is None:
            raise KeyError(doc_id)
        old_place = folder_tree.folder_text(doc.category, doc.subcategory) \
            if doc.category else DROP_ZONE_FOLDER
        details = "{} → {}".format(
            old_place, folder_tree.folder_text(folder, subfolder))

        conn = get_connection(self.db_path)
        try:
            # A file in a folder no longer needs its folder suggestion.
            conn.execute(
                "UPDATE documents SET file_path = ?, filename = ?, "
                "category = ?, subcategory = ?, suggested_folder = NULL, "
                "review_note = CASE WHEN review_note = ? THEN NULL "
                "ELSE review_note END WHERE id = ?",
                (new_path, os.path.basename(new_path), folder, subfolder,
                 folder_tree.NO_FOLDER_NOTE, doc_id),
            )
            self.log_activity(conn, doc_id, "Moved", details)
            conn.commit()
        finally:
            conn.close()
        return self.get_document(doc_id)

    def set_status(self, doc_id, status):
        """Change only the status, as part of an action already logged."""
        conn = get_connection(self.db_path)
        try:
            conn.execute("UPDATE documents SET status = ? WHERE id = ?",
                         (status, doc_id))
            conn.commit()
        finally:
            conn.close()
        return self.get_document(doc_id)

    def set_review_note(self, doc_id, note):
        """Change only the review note, as part of an action already logged."""
        conn = get_connection(self.db_path)
        try:
            conn.execute("UPDATE documents SET review_note = ? WHERE id = ?",
                         (note, doc_id))
            conn.commit()
        finally:
            conn.close()
        return self.get_document(doc_id)

    def count_in_folder(self, folder):
        """Count the documents in a tree folder or any of its subfolders."""
        conn = get_connection(self.db_path)
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM documents WHERE category = ?",
                (folder,)).fetchone()
        finally:
            conn.close()
        return row[0]

    def count_in_subfolder(self, folder, subfolder):
        """Count the documents in one subfolder of the tree."""
        conn = get_connection(self.db_path)
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM documents WHERE category = ? "
                "AND subcategory = ?", (folder, subfolder)).fetchone()
        finally:
            conn.close()
        return row[0]

    def get_topics(self):
        """Return the topic of every cataloged document that has one."""
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(
                "SELECT topic FROM documents WHERE topic IS NOT NULL "
                "AND duplicate_of IS NULL").fetchall()
        finally:
            conn.close()
        return [row["topic"] for row in rows]

    def get_by_status(self, status):
        """Return all documents with the given status."""
        return self.get_all_documents({"status": status})

    def check_fields(self, fields, current=None):
        """Return the update with clean values, or raise ValueError."""
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
        return self.check_archive_fields(dict(fields), current)

    def check_archive_fields(self, fields, current):
        """Check and clean the archiving fields of an update."""
        rules = archive_rules
        if "keywords" in fields:
            fields["keywords"] = rules.keywords_to_text(
                rules.check_keywords(fields["keywords"]))
        if "counterparty" in fields:
            fields["counterparty"] = rules.check_limited_text(
                fields["counterparty"], "counterparty",
                rules.MAX_COUNTERPARTY_LENGTH)
        if "owner" in fields:
            fields["owner"] = rules.check_limited_text(
                fields["owner"], "owner", rules.MAX_OWNER_LENGTH)
        if "confidentiality" in fields:
            rules.check_confidentiality(fields["confidentiality"])
        for name in ("effective_start", "effective_end"):
            if name in fields:
                fields[name] = rules.check_date(fields[name], name)
        start = fields.get("effective_start",
                           getattr(current, "effective_start", None))
        end = fields.get("effective_end",
                         getattr(current, "effective_end", None))
        # YYYY-MM-DD text sorts like the dates themselves.
        if start and end and start > end:
            raise ValueError("effective_start must be before effective_end")
        self.check_category(fields, current)
        return fields

    def check_category(self, fields, current):
        """Allow a category from the project list, the current one, or none."""
        categories = self.get_categories()
        if "category" in fields:
            name = fields["category"] or None
            fields["category"] = name
            if name and name != getattr(current, "category", None) and \
                    archive_rules.find_category(categories, name) is None:
                raise ValueError("category is not in the project list")
        if "subcategory" in fields:
            sub = fields["subcategory"] or None
            fields["subcategory"] = sub
            category = fields.get("category",
                                  getattr(current, "category", None))
            found = archive_rules.find_category(categories, category or "")
            allowed = found["subcategories"] if found else []
            if sub and sub != getattr(current, "subcategory", None) and \
                    sub not in allowed:
                raise ValueError("subcategory is not in the project list")

    def update_document(self, doc_id, fields):
        """Update editable fields on a document."""
        # Check everything before touching the database.
        current = self.get_document(doc_id)
        fields = self.check_fields(fields, current)
        if current is None:
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
                "app_lock_password_hash, language, naming_template, "
                "industry, categories, folder_mode, project_description "
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

    def save_industry(self, industry):
        """Save the project's industry, used to suggest categories."""
        self.save_config_value("industry", industry)

    def save_categories(self, categories):
        """Save the project's category list as JSON text."""
        self.save_config_value("categories",
                               json.dumps(categories, ensure_ascii=False))

    def get_categories(self):
        """Return the project's category list, or [] if it has none."""
        config = self.get_app_config() or {}
        return archive_rules.categories_from_text(config.get("categories"))

    def is_tree_project(self):
        """Say whether the project files documents in its own folder tree."""
        config = self.get_app_config() or {}
        return config.get("folder_mode") == folder_tree.TREE_MODE

    def get_folder_tree(self):
        """Return the folder tree, or None in a project sorted by type."""
        if not self.is_tree_project():
            return None
        return self.get_categories()

    def save_folder_tree(self, description, tree):
        """Make this a tree project with its description and folders."""
        self.save_config_value("folder_mode", folder_tree.TREE_MODE)
        self.save_config_value("project_description", description)
        self.save_categories(tree)

    def get_project_description(self):
        """Return what the project is about, or ''."""
        config = self.get_app_config() or {}
        return config.get("project_description") or ""

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
