"""Project list."""

import json
import os
import shutil
import sqlite3
from datetime import datetime

from backend.db.catalog_repository import CatalogRepository
from backend.db.schema import DB_PATH, init_db
from backend.pipeline.file_organizer import CATALOG_FOLDER

# The project list sits next to the old single database.
PROJECTS_PATH = os.path.join(os.path.dirname(DB_PATH), "projects.json")

CATALOG_FILE = "catalog.db"

DEFAULT_LANGUAGE = "en"


def now_timestamp():
    """Return the current time as an ISO string, e.g. 2026-10-26T10:00:00."""
    return datetime.now().isoformat(timespec="seconds")


def normalize_folder(folder):
    """Turn a folder path into one standard form."""
    return os.path.abspath(os.path.expanduser(folder.strip()))


def catalog_path(folder):
    """Return where a project keeps its catalog."""
    return os.path.join(folder, CATALOG_FOLDER, CATALOG_FILE)


def empty_project_list():
    """Return the contents of a project list with no projects yet."""
    return {"active_folder": "", "language": DEFAULT_LANGUAGE,
            "projects": []}


def load_projects(path):
    """Read the project list."""
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
    """Write the project list."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary_path = path + ".tmp"
    with open(temporary_path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)
    os.replace(temporary_path, path)


def find_project(data, folder):
    """Return the project for a folder, or None."""
    for project in data["projects"]:
        if project["folder"] == folder:
            return project
    return None


def active_folder(path):
    """Return the folder of the active project, or '' if there is none."""
    return load_projects(path)["active_folder"]


def add_project(path, name, folder):
    """Add a project to the list and make it the active one."""
    data = load_projects(path)
    data["projects"].append({"name": name, "folder": folder,
                             "last_opened": now_timestamp()})
    data["active_folder"] = folder
    save_projects(path, data)


def set_active_project(path, folder):
    """Make a project in the list the active one."""
    data = load_projects(path)
    project = find_project(data, folder)
    if project is None:
        raise KeyError(folder)
    project["last_opened"] = now_timestamp()
    data["active_folder"] = folder
    save_projects(path, data)


def remove_project(path, folder):
    """Take a project out of the list. Nothing is deleted from disk."""
    data = load_projects(path)
    project = find_project(data, folder)
    if project is None:
        raise KeyError(folder)
    data["projects"].remove(project)
    if data["active_folder"] == folder:
        data["active_folder"] = ""
        if data["projects"]:
            # ISO timestamps sort in time order, so max() is the newest.
            newest = max(data["projects"],
                         key=lambda item: item["last_opened"])
            data["active_folder"] = newest["folder"]
    save_projects(path, data)


def rename_project(path, folder, name):
    """Change the name shown for a project in the list."""
    data = load_projects(path)
    project = find_project(data, folder)
    if project is not None:
        project["name"] = name
        save_projects(path, data)


def set_language(path, language):
    """Save the interface language, which is the same for every project."""
    data = load_projects(path)
    data["language"] = language
    save_projects(path, data)


def read_old_settings(old_db_path):
    """Read the app_config row of the old single database."""
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
    """Turn the old single database into the first project."""
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
    # The name comes from the catalog that stays in the folder.
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
