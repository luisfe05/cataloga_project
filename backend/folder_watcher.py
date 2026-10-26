"""Folder watcher.

Step 1 of the Stage 3 sequence diagram: "Detect new file in target
directory". The user drops files into the Drop Zone folder inside the
active project's folder. Every few seconds the watcher reads which
project is active (so a switch takes effect on the next check), looks
for files in that project's Drop Zone, and sends them through the
ClassificationPipeline with that project's own catalog. Other projects
and the hidden .cataloga folder are never touched.

Only Drop Zone is watched, so files the user already had in the project
folder are never moved. Because processed files leave Drop Zone, the
next check only finds files added since. Nothing is processed twice.

Projects made before Drop Zone existed have an Inbox folder. The
watcher renames it to Drop Zone once. If both folders exist and Inbox
still has files, the watcher writes a warning in the log. It never
moves those files: the user decides what to do with them.
"""

import logging
import os
import threading
import time

from backend.config import projects
from backend.db.catalog_repository import CatalogRepository
from backend.pipeline.ai_providers import create_client
from backend.pipeline.classification_pipeline import ClassificationPipeline
from backend.pipeline.file_organizer import FileOrganizer

# Seconds between checks of the project folder.
CHECK_INTERVAL = 10

# Written in the log when the old Inbox folder still has files next to
# Drop Zone. The Catalog screen shows the same text (see catalog.js).
OLD_INBOX_WARNING = ("Your old Inbox folder still has files. "
                     "Move them to Drop Zone to catalog them.")

# Project folders already warned about, so the log gets the warning
# once instead of every CHECK_INTERVAL seconds.
warned_folders = set()

logger = logging.getLogger(__name__)


# Endings of temporary files made by browsers and apps. These are
# skipped because the real file is not finished or not the user's.
TEMPORARY_ENDINGS = (".part", ".download", ".crdownload", ".tmp", "~lock~")


def find_new_files(folder):
    """Return the files sitting directly in a folder.

    Subfolders are not opened. Hidden files such as .DS_Store, Office
    temporary files (names starting with '~$'), and temporary files from
    downloads or apps (see TEMPORARY_ENDINGS) are skipped.

    Args:
        folder (str): The folder to look in (the Drop Zone).

    Returns:
        list[str]: Absolute paths, sorted by name.
    """
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
    """Check if an old Inbox folder still has files next to Drop Zone.

    This only reads the folders. It never moves anything.

    Args:
        organizer (FileOrganizer): Organizer for the project folder.

    Returns:
        bool: True if Drop Zone exists and Inbox has at least one file
            the watcher would process (hidden and temporary files do not
            count).
    """
    if not os.path.isdir(organizer.drop_zone_folder()):
        return False
    return len(find_new_files(organizer.old_inbox_folder())) > 0


def log_old_inbox_warning(organizer):
    """Write OLD_INBOX_WARNING in the log, once per project folder.

    When the old Inbox is empty again, the folder is forgotten, so a
    later problem is logged again.

    Args:
        organizer (FileOrganizer): Organizer for the project folder.
    """
    folder = organizer.target_directory
    if not old_inbox_has_files(organizer):
        warned_folders.discard(folder)
        return
    if folder not in warned_folders:
        logger.warning("%s (%s)", OLD_INBOX_WARNING, folder)
        warned_folders.add(folder)


def scan_once(projects_path):
    """Check the active project's Drop Zone one time.

    Nothing is processed until there is an active project whose folder
    is available and which has an AI provider. As soon as there is a
    project, an old Inbox is renamed to Drop Zone (see
    FileOrganizer.migrate_old_inbox).

    Args:
        projects_path (str): Path to the project list (projects.json).

    Returns:
        list[Document]: The documents processed in this check.
    """
    folder = projects.active_folder(projects_path)
    # No project, or its folder (or catalog) is missing, for example an
    # external drive that is not connected.
    if not folder or not os.path.isfile(projects.catalog_path(folder)):
        return []
    repo = CatalogRepository(projects.catalog_path(folder))

    # Only a project's own folder is migrated: there, Inbox was made by
    # Cataloga, not by the user.
    organizer = FileOrganizer(folder)
    organizer.migrate_old_inbox()
    log_old_inbox_warning(organizer)

    provider = repo.get_active_provider()
    if not provider:
        return []

    files = find_new_files(organizer.drop_zone_folder())
    if not files:
        return []

    pipeline = ClassificationPipeline(
        create_client(provider["provider_name"], provider["model"]),
        repo,
        organizer,
    )
    return pipeline.process_batch(files)


def watch_forever(projects_path):
    """Run scan_once() every CHECK_INTERVAL seconds, forever.

    An error in one check (for example, the external drive was
    unplugged) is ignored so the watcher keeps running and tries again
    on the next check.

    Args:
        projects_path (str): Path to the project list (projects.json).
    """
    while True:
        try:
            scan_once(projects_path)
        except Exception:
            pass
        time.sleep(CHECK_INTERVAL)


def start_watcher(projects_path):
    """Start the watcher in a background thread.

    daemon=True means the thread stops when the app window is closed.

    Args:
        projects_path (str): Path to the project list (projects.json).

    Returns:
        threading.Thread: The running thread.
    """
    thread = threading.Thread(target=watch_forever, args=(projects_path,),
                              daemon=True)
    thread.start()
    return thread
