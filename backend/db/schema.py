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
    folder_path       TEXT,
    proposed_folder   TEXT,
    proposed_name     TEXT,
    secrets_hidden    INTEGER
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
    # What the pipeline would do to a file read in place (the plan).
    "proposed_folder": "proposed_folder TEXT",
    "proposed_name": "proposed_name TEXT",
    # How many keys or passwords were hidden before the text was sent.
    # Only the number is kept, never the secret itself.
    "secrets_hidden": "secrets_hidden INTEGER",
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
    keep_accents            INTEGER,
    stamp_date_order        TEXT,
    removed_folders         TEXT
);
"""

# Added after the first release; add_missing_columns() adds them.
ADDED_APP_CONFIG_COLUMNS = {
    # How the folder's scan stands; a closed app leaves "running".
    "scan_state": "scan_state TEXT",
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
    # How a date stamped on a photo reads: 'month' first or 'day' first.
    "stamp_date_order": "stamp_date_order TEXT",
    # Folders taken out of the tree whose files go elsewhere (JSON list of
    # 'A/B'). The plan removes each one from the disk once it is empty.
    "removed_folders": "removed_folders TEXT",
}

# Each move the user made by hand: the AI reads the latest ones before
# it files a new document of the same project.
CREATE_CORRECTIONS = """
CREATE TABLE IF NOT EXISTS corrections (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id       INTEGER,
    original_filename TEXT    NOT NULL,
    summary           TEXT,
    from_folder       TEXT,
    to_folder         TEXT    NOT NULL,
    timestamp         TEXT    NOT NULL
);
"""

# Added with the plan: a name the user changed before applying.
ADDED_CORRECTIONS_COLUMNS = {
    "from_name": "from_name TEXT",
    "to_name": "to_name TEXT",
}

# A batch of moves and renames: the plan the user applied, or what the
# watcher filed without asking. Undo works on a batch.
CREATE_BATCHES = """
CREATE TABLE IF NOT EXISTS batches (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    origin     TEXT    NOT NULL,
    status     TEXT    NOT NULL,
    created    TEXT    NOT NULL,
    applied_at TEXT,
    undone_at  TEXT,
    note       TEXT
);
"""

# The journal: one row per file or folder, written before the disk is
# touched (pending) and again after (applied). old_* and new_* are what
# Undo needs; size and mtime say whether the file is still the same.
CREATE_BATCH_ITEMS = """
CREATE TABLE IF NOT EXISTS batch_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id    INTEGER NOT NULL REFERENCES batches(id),
    position    INTEGER NOT NULL,
    document_id INTEGER,
    action      TEXT    NOT NULL,
    status      TEXT    NOT NULL,
    old_path    TEXT,
    new_path    TEXT,
    temp_path   TEXT,
    old_folder  TEXT,
    new_folder  TEXT,
    old_name    TEXT,
    new_name    TEXT,
    size        INTEGER,
    mtime       INTEGER,
    new_size    INTEGER,
    new_mtime   INTEGER,
    reason      TEXT,
    created     INTEGER NOT NULL DEFAULT 0
);
"""

# What was read in place, and how it looked: a file with the same size
# and date is not read again.
CREATE_SCAN_INDEX = """
CREATE TABLE IF NOT EXISTS scan_index (
    path        TEXT    PRIMARY KEY,
    size        INTEGER NOT NULL,
    mtime       INTEGER NOT NULL,
    document_id INTEGER,
    seen_at     TEXT    NOT NULL
);
"""

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
             ("corrections", ADDED_CORRECTIONS_COLUMNS),
             ("ai_provider_config", ADDED_AI_PROVIDER_COLUMNS))
    for table, new_columns in added:
        # row[1] is the column name.
        columns = [row[1] for row in
                   cursor.execute("PRAGMA table_info(" + table + ")")]
        for name, definition in new_columns.items():
            if name not in columns:
                cursor.execute("ALTER TABLE " + table + " ADD COLUMN " +
                               definition)


def move_prefix(cursor, table, column, old, new):
    """Rewrite paths under one folder to the same place under another."""
    # OR REPLACE: a path that exists twice leaves one row; the rest is below.
    cursor.execute(
        "UPDATE OR REPLACE " + table + " SET " + column + " = ? || substr(" +
        column + ", ?) WHERE substr(" + column + ", 1, ?) = ?",
        (new, len(old) + 1, len(old) + 1, old + os.sep))


def follow_copied_folder(cursor, db_path):
    """A project folder that was copied or moved keeps its catalog.

    The rows still say where the files used to be, so every file looked new
    and came back as a duplicate of its own old row. They move with it.
    """
    holder = os.path.dirname(db_path)
    if os.path.basename(holder) != ".cataloga":
        return
    row = cursor.execute(
        "SELECT target_directory FROM app_config ORDER BY id LIMIT 1"
    ).fetchone()
    root = os.path.dirname(holder)
    if not row or not row[0]:
        return
    if os.path.realpath(row[0]) == os.path.realpath(root):
        return
    cursor.execute("DROP INDEX IF EXISTS one_row_per_path")
    new = os.path.realpath(root)
    for old in {row[0].rstrip(os.sep), os.path.realpath(row[0])}:
        cursor.execute("UPDATE documents SET file_path = ? || substr("
                       "file_path, ?) WHERE substr(file_path, 1, ?) = ?",
                       (new, len(old) + 1, len(old) + 1, old + os.sep))
        move_prefix(cursor, "scan_index", "path", old, new)
        for column in ("old_path", "new_path"):
            move_prefix(cursor, "batch_items", column, old, new)
    cursor.execute("UPDATE app_config SET target_directory = ?", (new,))


def remove_repeated_paths(cursor):
    """Leave one row per path: the edited one, else the newest real one.

    A row that says "duplicate of" its own copy is never the one to keep.
    """
    repeated = cursor.execute(
        "SELECT file_path FROM documents GROUP BY file_path "
        "HAVING COUNT(*) > 1").fetchall()
    for repeat in repeated:
        rows = cursor.execute(
            "SELECT d.id, EXISTS (SELECT 1 FROM activity_log a WHERE "
            "a.document_id = d.id AND a.action IN ('Edited', 'Moved', "
            "'Renamed')), d.duplicate_of IS NULL FROM documents d "
            "WHERE d.file_path = ?", (repeat[0],)).fetchall()
        keep = max(rows, key=lambda row: (row[1], row[2], row[0]))[0]
        for row in rows:
            if row[0] != keep:
                cursor.execute("DELETE FROM activity_log WHERE "
                               "document_id = ?", (row[0],))
                cursor.execute("DELETE FROM documents WHERE id = ?",
                               (row[0],))
    # The index follows the rows that stayed.
    cursor.execute(
        "UPDATE scan_index SET document_id = (SELECT d.id FROM documents d "
        "WHERE d.file_path = scan_index.path) WHERE path IN "
        "(SELECT file_path FROM documents)")
    cursor.execute("DELETE FROM scan_index WHERE path NOT IN "
                   "(SELECT file_path FROM documents)")
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS one_row_per_path "
                   "ON documents (file_path)")


def repair_in_place_folders(cursor):
    """In a project read in place, folder_path is the file's own folder.

    Rows made before the plan kept the AI's folder there. The real folder
    comes from the path; the AI's choice is already in proposed_folder.
    """
    config = cursor.execute(
        "SELECT target_directory, folder_mode FROM app_config "
        "ORDER BY id LIMIT 1").fetchone()
    if not config or config[1] != "place":
        return
    root = os.path.realpath(config[0])
    rows = cursor.execute("SELECT id, file_path FROM documents").fetchall()
    for doc_id, file_path in rows:
        folder = os.path.dirname(os.path.realpath(file_path))
        relative = os.path.relpath(folder, root)
        if relative.startswith(".."):
            continue
        place = "" if relative == "." else relative.replace(os.sep, "/")
        parts = place.split("/") if place else []
        cursor.execute(
            "UPDATE documents SET folder_path = ?, category = ?, "
            "subcategory = ? WHERE id = ? AND (folder_path IS NOT ? OR "
            "folder_path IS NULL AND ? IS NOT NULL)",
            (place or None, parts[0] if parts else None,
             parts[1] if len(parts) > 1 else None, doc_id, place or None,
             place or None))


def init_db(db_path=DB_PATH):
    """Create all tables if they don't already exist."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(CREATE_DOCUMENTS)
    cursor.execute(CREATE_ACTIVITY_LOG)
    cursor.execute(CREATE_APP_CONFIG)
    cursor.execute(CREATE_AI_PROVIDER_CONFIG)
    cursor.execute(CREATE_CORRECTIONS)
    cursor.execute(CREATE_SCAN_INDEX)
    cursor.execute(CREATE_BATCHES)
    cursor.execute(CREATE_BATCH_ITEMS)
    add_missing_columns(cursor)
    # The provider a project used before the roles is its text provider.
    cursor.execute("UPDATE ai_provider_config SET role = 'text' "
                   "WHERE is_active = 1 AND role IS NULL")
    follow_copied_folder(cursor, db_path)
    remove_repeated_paths(cursor)
    repair_in_place_folders(cursor)
    # Rows from before folder_path: the path is the two old columns.
    cursor.execute("UPDATE documents SET folder_path = CASE WHEN "
                   "subcategory IS NOT NULL THEN category || '/' || "
                   "subcategory ELSE category END WHERE folder_path IS "
                   "NULL AND category IS NOT NULL")
    conn.commit()
    conn.close()
