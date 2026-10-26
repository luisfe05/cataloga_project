"""Project list.

Cataloga can hold several research projects. Each project folder keeps
its own catalog in <folder>/.cataloga/catalog.db, with the four tables
of the ERD. The app itself only remembers, in a small JSON file:

    {"active_folder": "/Users/luis/El Delfin",
     "language": "en",
     "projects": [{"name": "El Delfin",
                   "folder": "/Users/luis/El Delfin",
                   "last_opened": "2026-10-26T10:00:00"}]}

The file lives next to the app's data (Application Support in the
packaged app, the database/ folder when running from the code). The
language is here because it is the same for every project.

Everything is a plain function that gets the file's path, so tests can
use a temporary file.
"""

import json
import os
import shutil
import sqlite3
from datetime import datetime

from backend.db.catalog_repository import CatalogRepository
from backend.db.schema import DB_PATH, init_db
from backend.pipeline.file_organizer import CATALOG_FOLDER

# The project list sits in the same folder as the old single database.
PROJECTS_PATH = os.path.join(os.path.dirname(DB_PATH), "projects.json")

# Name of each project's catalog inside its .cataloga folder.
CATALOG_FILE = "catalog.db"

DEFAULT_LANGUAGE = "en"


def now_timestamp():
    """Return the current time as an ISO string, e.g. 2026-10-26T10:00:00.

    Returns:
        str: The current local time, without microseconds.
    """
    return datetime.now().isoformat(timespec="seconds")


def normalize_folder(folder):
    """Turn a folder path into one standard form.

    '~/Research/' and '/Users/luis/Research' become the same text, so
    the same folder is never listed twice.

    Args:
        folder (str): A folder path as the user typed or picked it.

    Returns:
        str: Absolute path without a trailing slash.
    """
    return os.path.abspath(os.path.expanduser(folder.strip()))


def catalog_path(folder):
    """Return where a project keeps its catalog.

    Args:
        folder (str): The project folder.

    Returns:
        str: For example /Users/luis/Research/.cataloga/catalog.db.
    """
    return os.path.join(folder, CATALOG_FOLDER, CATALOG_FILE)


def empty_project_list():
    """Return the contents of a project list with no projects yet.

    Returns:
        dict: {'active_folder': '', 'language': 'en', 'projects': []}
    """
    return {"active_folder": "", "language": DEFAULT_LANGUAGE,
            "projects": []}


def load_projects(path):
    """Read the project list.

    Args:
        path (str): Path to projects.json.

    Returns:
        dict: The list. If the file does not exist yet (or cannot be
            read), an empty list is returned.
    """
    data = empty_project_list()
    if not os.path.isfile(path):
        return data
    try:
        with open(path, encoding="utf-8") as file:
            saved = json.load(file)
    except (OSError, ValueError):
        return data
    if isinstance(saved, dict):
        data.update(saved)
    return data


def save_projects(path, data):
    """Write the project list.

    The text is written to a temporary file first and then put in
    place with os.replace(), so a crash in the middle of writing never
    leaves a half-written list.

    Args:
        path (str): Path to projects.json.
        data (dict): The whole list.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary_path = path + ".tmp"
    with open(temporary_path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)
    os.replace(temporary_path, path)


def find_project(data, folder):
    """Return the project for a folder, or None.

    Args:
        data (dict): The project list.
        folder (str): A normalized folder path.

    Returns:
        dict or None: {'name', 'folder', 'last_opened'}
    """
    for project in data["projects"]:
        if project["folder"] == folder:
            return project
    return None


def active_folder(path):
    """Return the folder of the active project, or '' if there is none.

    Args:
        path (str): Path to projects.json.

    Returns:
        str
    """
    return load_projects(path)["active_folder"]


def add_project(path, name, folder):
    """Add a project to the list and make it the active one.

    Args:
        path (str): Path to projects.json.
        name (str): The project's name.
        folder (str): A normalized folder path.
    """
    data = load_projects(path)
    data["projects"].append({"name": name, "folder": folder,
                             "last_opened": now_timestamp()})
    data["active_folder"] = folder
    save_projects(path, data)


def set_active_project(path, folder):
    """Make a project in the list the active one.

    Args:
        path (str): Path to projects.json.
        folder (str): A normalized folder path.

    Raises:
        KeyError: If the folder is not in the list.
    """
    data = load_projects(path)
    project = find_project(data, folder)
    if project is None:
        raise KeyError(folder)
    project["last_opened"] = now_timestamp()
    data["active_folder"] = folder
    save_projects(path, data)


def rename_project(path, folder, name):
    """Change the name shown for a project in the list.

    Args:
        path (str): Path to projects.json.
        folder (str): A normalized folder path.
        name (str): The new name.
    """
    data = load_projects(path)
    project = find_project(data, folder)
    if project is not None:
        project["name"] = name
        save_projects(path, data)


def set_language(path, language):
    """Save the interface language, which is the same for every project.

    Args:
        path (str): Path to projects.json.
        language (str): 'en' or 'es', already checked by the caller.
    """
    data = load_projects(path)
    data["language"] = language
    save_projects(path, data)


def read_old_settings(old_db_path):
    """Read the app_config row of the old single database.

    The file is only read: nothing is written to it, so it stays as a
    backup. Columns that an older version did not have are simply
    missing from the result.

    Args:
        old_db_path (str): Path to the old catalog.db.

    Returns:
        dict or None: The row, or None if there is no row.
    """
    conn = sqlite3.connect(old_db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM app_config ORDER BY id LIMIT 1").fetchone()
    except sqlite3.Error:
        row = None
    finally:
        conn.close()
    return dict(row) if row else None


def migrate_old_database(path, old_db_path):
    """Turn the old single database into the first project.

    Runs at start, only while projects.json does not exist yet:
    1. The old database is copied (not moved) into the project folder
       it was using, as <folder>/.cataloga/catalog.db. If a catalog is
       already there, it is kept as it is.
    2. init_db() adds any column the copy is missing.
    3. The project is added to the list and made active, and the old
       language is kept.
    The old database is never changed, so it stays as a backup. The
    files in the project folder are not moved, so every saved
    file_path still points to the right file.

    If the project folder is not there (for example, an external drive
    that is not connected), nothing is written and the next start tries
    again.

    Args:
        path (str): Path to projects.json.
        old_db_path (str): Path to the old catalog.db.

    Returns:
        bool: True if a project was created from the old database.
    """
    if os.path.exists(path) or not os.path.isfile(old_db_path):
        return False
    old = read_old_settings(old_db_path)
    if not old or not old.get("target_directory"):
        return False
    folder = normalize_folder(old["target_directory"])
    if not os.path.isdir(folder):
        return False

    new_db_path = catalog_path(folder)
    if not os.path.exists(new_db_path):
        os.makedirs(os.path.dirname(new_db_path), exist_ok=True)
        # copy2 also keeps the file's dates.
        shutil.copy2(old_db_path, new_db_path)
    init_db(new_db_path)
    # The name comes from the catalog that stays in the folder, which is
    # the old one unless a catalog was already there.
    kept = CatalogRepository(new_db_path).get_app_config() or {}

    data = empty_project_list()
    data["language"] = old.get("language") or DEFAULT_LANGUAGE
    data["projects"].append({
        "name": kept.get("research_name") or os.path.basename(folder),
        "folder": folder,
        "last_opened": now_timestamp(),
    })
    data["active_folder"] = folder
    # Written last, so a failure above leaves nothing half done.
    save_projects(path, data)
    return True
