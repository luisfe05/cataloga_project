"""Database schema and initialization."""

import os
import sqlite3
import sys

APP_NAME = "Cataloga"


def app_data_folder():
    """Return the folder where the packaged app keeps its data."""
    home = os.path.expanduser("~")
    if sys.platform == "darwin":
        return os.path.join(home, "Library", "Application Support",
                            APP_NAME)
    if os.name == "nt":
        # Windows keeps app data in the folder named by APPDATA.
        return os.path.join(os.environ.get("APPDATA", home), APP_NAME)
    return os.path.join(home, ".local", "share", APP_NAME)


def default_db_path():
    """Return the path of the database file for the way the app runs."""
    if getattr(sys, "frozen", False):
        folder = app_data_folder()
        os.makedirs(folder, exist_ok=True)
        return os.path.join(folder, "catalog.db")
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    return os.path.join(project_root, "database", "catalog.db")


DB_PATH = default_db_path()

CREATE_DOCUMENTS = """
CREATE TABLE IF NOT EXISTS documents (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    original_filename TEXT    NOT NULL,
    filename          TEXT    NOT NULL,
    media_type        TEXT    NOT NULL CHECK(
                          media_type IN (
                              'Press', 'Audio', 'Video',
                              'Photos', 'Documents'
                          )
                      ),
    source            TEXT,
    document_date     TEXT,
    summary           TEXT,
    status            TEXT    NOT NULL DEFAULT 'Classified' CHECK(
                          status IN ('Classified', 'Manual Review')
                      ),
    file_path         TEXT    NOT NULL,
    date_added        TEXT    NOT NULL,
    date_classified   TEXT,
    topic             TEXT,
    keywords          TEXT,
    sha256            TEXT,
    duplicate_of      TEXT,
    review_note       TEXT,
    counterparty      TEXT,
    confidentiality   TEXT,
    owner             TEXT,
    effective_start   TEXT,
    effective_end     TEXT,
    category          TEXT,
    subcategory       TEXT,
    date_source       TEXT,
    suggested_folder  TEXT,
    folder_reason     TEXT,
    confidence        TEXT,
    original_path     TEXT,
    folder_path       TEXT
);
"""

# Added for the archiving guideline. keywords is a JSON list of text.
ADDED_DOCUMENTS_COLUMNS = {
    "topic": "topic TEXT",
    "keywords": "keywords TEXT",
    "sha256": "sha256 TEXT",
    "duplicate_of": "duplicate_of TEXT",
    "review_note": "review_note TEXT",
    "counterparty": "counterparty TEXT",
    "confidentiality": "confidentiality TEXT",
    "owner": "owner TEXT",
    "effective_start": "effective_start TEXT",
    "effective_end": "effective_end TEXT",
    "category": "category TEXT",
    "subcategory": "subcategory TEXT",
    # Where document_date came from: photo, content, metadata, or file.
    "date_source": "date_source TEXT",
    # A folder the AI would create, as 'Folder/Subfolder'.
    "suggested_folder": "suggested_folder TEXT",
    # One line from the AI on why the file went to its folder.
    "folder_reason": "folder_reason TEXT",
    # high, medium or low; low sends the file to Manual Review.
    "confidence": "confidence TEXT",
    # Where the file was first seen, relative to the project folder.
    "original_path": "original_path TEXT",
    # The file's folder in the tree, as 'A/B/C'. category and subcategory
    # keep its first two levels.
    "folder_path": "folder_path TEXT",
}

CREATE_ACTIVITY_LOG = """
CREATE TABLE IF NOT EXISTS activity_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id),
    action      TEXT    NOT NULL,
    timestamp   TEXT    NOT NULL,
    details     TEXT
);
"""

# Added after the first release. details holds text like 'a.pdf → b.pdf'.
ADDED_ACTIVITY_LOG_COLUMNS = {
    "details": "details TEXT",
}

CREATE_APP_CONFIG = """
CREATE TABLE IF NOT EXISTS app_config (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    research_name           TEXT    NOT NULL,
    target_directory        TEXT    NOT NULL,
    app_lock_password_hash  TEXT,
    language                TEXT    NOT NULL DEFAULT 'en',
    naming_template         TEXT    NOT NULL DEFAULT '{date}_{topic}',
    industry                TEXT,
    categories              TEXT,
    folder_mode             TEXT,
    project_description     TEXT,
    folder_tree             TEXT,
    numbered_folders        INTEGER,
    project_sheet           TEXT,
    server_url              TEXT,
    naming_style            TEXT,
    keep_accents            INTEGER
);
"""

# Added after the first release; add_missing_columns() adds them.
ADDED_APP_CONFIG_COLUMNS = {
    "language": "language TEXT NOT NULL DEFAULT 'en'",
    "naming_template":
        "naming_template TEXT NOT NULL DEFAULT '{date}_{topic}'",
    # categories is a JSON list of {"name": ..., "subcategories": [...]}.
    "industry": "industry TEXT",
    "categories": "categories TEXT",
    # 'tree' for projects with their own folders; empty in old projects.
    "folder_mode": "folder_mode TEXT",
    "project_description": "project_description TEXT",
    # What the work is, written by the AI from a sample and edited by hand.
    "project_sheet": "project_sheet TEXT",
    # A relay server that holds the API keys; empty means the providers.
    "server_url": "server_url TEXT",
    # The whole tree as JSON (any depth); categories keeps two levels.
    "folder_tree": "folder_tree TEXT",
    # 1 when new folders get a 01_ prefix.
    "numbered_folders": "numbered_folders INTEGER",
    # How file names look: 'lower' (topic-name) or 'title' (Topic-Name).
    "naming_style": "naming_style TEXT",
    # 1 keeps accents in file names (Día); empty or 0 drops them (Dia).
    "keep_accents": "keep_accents INTEGER",
}

CREATE_AI_PROVIDER_CONFIG = """
CREATE TABLE IF NOT EXISTS ai_provider_config (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_name TEXT    NOT NULL,
    model         TEXT    NOT NULL,
    is_active     INTEGER NOT NULL DEFAULT 0,
    role          TEXT
);
"""

# Added with the provider roles. 'text' is the main provider (the old
# is_active row), 'fallback' answers when it fails, 'media' reads audio
# and video.
ADDED_AI_PROVIDER_COLUMNS = {
    "role": "role TEXT",
}


def get_connection(db_path=DB_PATH):
    """Open and return a connection to the SQLite database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def add_missing_columns(cursor):
    """Add any column an older database lacks. Rows are kept."""
    # Safe: table and column names are fixed here, never from the user.
    added = (("app_config", ADDED_APP_CONFIG_COLUMNS),
             ("activity_log", ADDED_ACTIVITY_LOG_COLUMNS),
             ("documents", ADDED_DOCUMENTS_COLUMNS),
             ("ai_provider_config", ADDED_AI_PROVIDER_COLUMNS))
    for table, new_columns in added:
        # row[1] is the column name.
        columns = [row[1] for row in
                   cursor.execute("PRAGMA table_info(" + table + ")")]
        for name, definition in new_columns.items():
            if name not in columns:
                cursor.execute("ALTER TABLE " + table + " ADD COLUMN " +
                               definition)


def init_db(db_path=DB_PATH):
    """Create all tables if they don't already exist."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(CREATE_DOCUMENTS)
    cursor.execute(CREATE_ACTIVITY_LOG)
    cursor.execute(CREATE_APP_CONFIG)
    cursor.execute(CREATE_AI_PROVIDER_CONFIG)
    add_missing_columns(cursor)
    # The provider a project used before the roles is its text provider.
    cursor.execute("UPDATE ai_provider_config SET role = 'text' "
                   "WHERE is_active = 1 AND role IS NULL")
    # Rows from before folder_path: the path is the two old columns.
    cursor.execute("UPDATE documents SET folder_path = CASE WHEN "
                   "subcategory IS NOT NULL THEN category || '/' || "
                   "subcategory ELSE category END WHERE folder_path IS "
                   "NULL AND category IS NOT NULL")
    conn.commit()
    conn.close()
