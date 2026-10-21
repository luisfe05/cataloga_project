"""Database schema and initialization.

Defines the four tables (documents, activity_log, app_config, ai_provider_config)
and provides the init_db() function that creates them on first run.
The database file lives at database/catalog.db relative to the project root.
"""

import sqlite3
import os

DB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "database", "catalog.db"
)

CREATE_DOCUMENTS = """
CREATE TABLE IF NOT EXISTS documents (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    original_filename TEXT    NOT NULL,
    filename          TEXT    NOT NULL,
    media_type        TEXT    NOT NULL CHECK(
                          media_type IN ('Press', 'Audio', 'Video', 'Photos', 'Documents')
                      ),
    source            TEXT,
    document_date     TEXT,
    summary           TEXT,
    status            TEXT    NOT NULL DEFAULT 'Classified' CHECK(
                          status IN ('Classified', 'Manual Review')
                      ),
    file_path         TEXT    NOT NULL,
    date_added        TEXT    NOT NULL,
    date_classified   TEXT
);
"""

CREATE_ACTIVITY_LOG = """
CREATE TABLE IF NOT EXISTS activity_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id),
    action      TEXT    NOT NULL,
    timestamp   TEXT    NOT NULL
);
"""

CREATE_APP_CONFIG = """
CREATE TABLE IF NOT EXISTS app_config (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    research_name           TEXT    NOT NULL,
    target_directory        TEXT    NOT NULL,
    app_lock_password_hash  TEXT
);
"""

CREATE_AI_PROVIDER_CONFIG = """
CREATE TABLE IF NOT EXISTS ai_provider_config (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_name TEXT    NOT NULL,
    model         TEXT    NOT NULL,
    is_active     INTEGER NOT NULL DEFAULT 0
);
"""


def get_connection():
    """Open and return a connection to catalog.db.

    Returns:
        sqlite3.Connection: Connection with row_factory set so rows behave
                            like dicts.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create all tables if they don't already exist."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(CREATE_DOCUMENTS)
    cursor.execute(CREATE_ACTIVITY_LOG)
    cursor.execute(CREATE_APP_CONFIG)
    cursor.execute(CREATE_AI_PROVIDER_CONFIG)
    conn.commit()
    conn.close()
