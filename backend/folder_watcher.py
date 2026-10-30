"""Folder watcher."""

import logging
import os
import threading
import time

from backend.config import projects
from backend.db.catalog_repository import CatalogRepository
from backend.pipeline.ai_providers import project_client
from backend.pipeline.classification_pipeline import (
    ClassificationPipeline, remove_gone_duplicates)
from backend.pipeline.file_organizer import FileOrganizer

CHECK_INTERVAL = 10

# The Catalog screen shows the same text (catalog.js).
OLD_INBOX_WARNING = ("Your old Inbox folder still has files. "
                     "Move them to Drop Zone to catalog them.")

# Warn once per folder, not every CHECK_INTERVAL seconds.
warned_folders = set()

logger = logging.getLogger(__name__)


# Unfinished downloads and app temp files are skipped.
TEMPORARY_ENDINGS = (".part", ".download", ".crdownload", ".tmp", "~lock~")


def find_new_files(folder):
    """Return the files sitting directly in a folder."""
    if not os.path.isdir(folder):
        return []
    files = []
    for name in sorted(os.listdir(folder)):
        path = os.path.join(folder, name)
        if not os.path.isfile(path):
            continue
        if name.startswith(".") or name.startswith("~$"):
            continue
        if name.endswith(TEMPORARY_ENDINGS):
            continue
        files.append(path)
    return files


def old_inbox_has_files(organizer):
    """Check if an old Inbox folder still has files next to Drop Zone."""
    if not os.path.isdir(organizer.drop_zone_folder()):
        return False
    return len(find_new_files(organizer.old_inbox_folder())) > 0


def log_old_inbox_warning(organizer):
    """Write OLD_INBOX_WARNING in the log, once per project folder."""
    folder = organizer.target_directory
    if not old_inbox_has_files(organizer):
        warned_folders.discard(folder)
        return
    if folder not in warned_folders:
        logger.warning("%s (%s)", OLD_INBOX_WARNING, folder)
        warned_folders.add(folder)


def scan_once(projects_path, owner=None):
    """Check the active project's Drop Zone one time."""
    folder = projects.active_folder(projects_path)
    # No project, or its folder is missing (like an unplugged drive).
    if not folder or not os.path.isfile(projects.catalog_path(folder)):
        return []
    repo = CatalogRepository(projects.catalog_path(folder))

    # Only a project's own Inbox is migrated: Cataloga made it.
    organizer = FileOrganizer(folder)
    organizer.migrate_old_inbox()
    log_old_inbox_warning(organizer)
    remove_gone_duplicates(repo)

    client = project_client(repo)
    if client is None:
        return []

    files = find_new_files(organizer.drop_zone_folder())
    if not files:
        return []

    pipeline = ClassificationPipeline(
        client,
        repo,
        organizer,
        owner=owner,
    )
    return pipeline.process_batch(files)


def scan_for_session(app):
    """Scan the Drop Zone of the logged-in account's active project."""
    username = app.config.get("SESSION_USER")
    # Nobody is logged in: there is no project list to read.
    if not username:
        return []
    projects_path = app.config["ACCOUNTS"].projects_path(username)
    return scan_once(projects_path, owner=username)


def watch_forever(app):
    """Run scan_for_session() every CHECK_INTERVAL seconds, forever."""
    while True:
        try:
            scan_for_session(app)
        except Exception:
            pass
        time.sleep(CHECK_INTERVAL)


def start_watcher(app):
    """Start the watcher in a background thread."""
    thread = threading.Thread(target=watch_forever, args=(app,),
                              daemon=True)
    thread.start()
    return thread
