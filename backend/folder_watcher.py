"""Folder watcher.

Step 1 of the Stage 3 sequence diagram: "Detect new file in target
directory". The user drops files into the project folder (the
target_directory chosen in Settings). Every few seconds the watcher looks
for files sitting directly in that folder and sends them through the
ClassificationPipeline, which moves each one into its media-type folder.

Because processed files are moved out of the main folder, the next check
only finds files added since. Nothing is processed twice.
"""

import os
import threading
import time

from backend.db.catalog_repository import CatalogRepository
from backend.pipeline.ai_providers import create_client
from backend.pipeline.classification_pipeline import ClassificationPipeline
from backend.pipeline.file_organizer import FileOrganizer

# Seconds between checks of the project folder.
CHECK_INTERVAL = 10


def find_new_files(target_directory):
    """Return the files sitting directly in the project folder.

    Subfolders (like Press/ or Documents/) are not opened, so files that
    were already organized are never picked up again. Hidden files such
    as .DS_Store, and files still being copied by the system (names
    starting with '~$' or ending in '.part' or '.download'), are skipped.

    Args:
        target_directory (str): The project folder from Settings.

    Returns:
        list[str]: Absolute paths, sorted by name.
    """
    if not os.path.isdir(target_directory):
        return []
    files = []
    for name in sorted(os.listdir(target_directory)):
        path = os.path.join(target_directory, name)
        if not os.path.isfile(path):
            continue
        if name.startswith(".") or name.startswith("~$"):
            continue
        if name.endswith(".part") or name.endswith(".download"):
            continue
        files.append(path)
    return files


def scan_once(db_path):
    """Check the project folder one time and process any new files.

    Nothing happens until Settings has a project folder and an active
    AI provider.

    Args:
        db_path (str): Path to the SQLite database file.

    Returns:
        list[Document]: The documents processed in this check.
    """
    repo = CatalogRepository(db_path)
    config = repo.get_app_config()
    provider = repo.get_active_provider()
    if not config or not provider:
        return []

    files = find_new_files(config["target_directory"])
    if not files:
        return []

    pipeline = ClassificationPipeline(
        create_client(provider["provider_name"], provider["model"]),
        repo,
        FileOrganizer(config["target_directory"]),
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
