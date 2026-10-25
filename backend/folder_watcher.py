"""Folder watcher.

Step 1 of the Stage 3 sequence diagram: "Detect new file in target
directory". The user drops files into the Drop Zone folder inside the
project folder (the target_directory chosen in Settings). Every few
seconds the watcher looks for files in Drop Zone and sends them through
the ClassificationPipeline, which moves each one into its media-type
folder.

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


def scan_once(db_path):
    """Check the project folder one time and process any new files.

    Nothing is processed until Settings has a project folder and an
    active AI provider. As soon as there is a project folder, an old
    Inbox is renamed to Drop Zone (see FileOrganizer.migrate_old_inbox).

    Args:
        db_path (str): Path to the SQLite database file.

    Returns:
        list[Document]: The documents processed in this check.
    """
    repo = CatalogRepository(db_path)
    config = repo.get_app_config()
    # The row can exist with an empty folder when only the language was
    # saved. An empty path would point at the app's own working folder.
    if not config or not config["target_directory"]:
        return []

    # Only the folder saved in Settings is migrated: there, Inbox was
    # made by Cataloga, not by the user.
    organizer = FileOrganizer(config["target_directory"])
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


def watch_forever(db_path):
    """Run scan_once() every CHECK_INTERVAL seconds, forever.

    An error in one check (for example, the external drive was
    unplugged) is ignored so the watcher keeps running and tries again
    on the next check.

    Args:
        db_path (str): Path to the SQLite database file.
    """
    while True:
        try:
            scan_once(db_path)
        except Exception:
            pass
        time.sleep(CHECK_INTERVAL)


def start_watcher(db_path):
    """Start the watcher in a background thread.

    daemon=True means the thread stops when the app window is closed.

    Args:
        db_path (str): Path to the SQLite database file.

    Returns:
        threading.Thread: The running thread.
    """
    thread = threading.Thread(target=watch_forever, args=(db_path,),
                              daemon=True)
    thread.start()
    return thread
