"""Database schema and initialization.

Defines the four tables (documents, activity_log, app_config,
ai_provider_config) and provides the init_db() function that creates
them on first run.

Where the database file lives depends on how the app is started:
- From the code (python main.py): database/catalog.db in the project.
- From the packaged app (PyInstaller): the system's folder for app data,
  because files inside the packaged app can't be changed and are
  replaced on every update.
"""

import os
import sqlite3
import sys

APP_NAME = "Cataloga"


def app_data_folder():
    """Return the folder where the packaged app keeps its data.

    Returns:
        str: For example ~/Library/Application Support/Cataloga on macOS.
    """
    home = os.path.expanduser("~")
    if sys.platform == "darwin":
        return os.path.join(home, "Library", "Application Support",
                            APP_NAME)
    if os.name == "nt":
        # Windows keeps app data in the folder named by APPDATA.
        return os.path.join(os.environ.get("APPDATA", home), APP_NAME)
    return os.path.join(home, ".local", "share", APP_NAME)


def default_db_path():
    """Return the path of the database file for the way the app runs.

    PyInstaller sets sys.frozen to True inside the packaged app.

    Returns:
        str: Absolute path to catalog.db.
    """
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


def get_connection(db_path=DB_PATH):
    """Open and return a connection to the SQLite database.

    Args:
        db_path (str): Path to the database file. Defaults to
                       database/catalog.db. Tests pass a temporary file.

    Returns:
        sqlite3.Connection: Connection with row_factory set so rows behave
                            like dicts.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path=DB_PATH):
    """Create all tables if they don't already exist.

    Args:
        db_path (str): Path to the database file. Defaults to
                       database/catalog.db.
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(CREATE_DOCUMENTS)
    cursor.execute(CREATE_ACTIVITY_LOG)
    cursor.execute(CREATE_APP_CONFIG)
    cursor.execute(CREATE_AI_PROVIDER_CONFIG)
    conn.commit()
    conn.close()
