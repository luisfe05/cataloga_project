"""Scanner: reads a project folder in place, with its subfolders.

Files are cataloged where they are; nothing moves and nothing is renamed.
What the pipeline would have done is saved as a proposal for the plan.
"""

import logging
import os
import threading

from backend.config import projects
from backend.db.catalog_repository import CatalogRepository
from backend.pipeline import folder_tree
from backend.pipeline.ai_providers import (create_client,
                                           ready_media_client)
from backend.pipeline.classification_pipeline import ClassificationPipeline
from backend.pipeline.file_organizer import CATALOG_FOLDER, FileOrganizer

logger = logging.getLogger(__name__)

# Folders that are never entered: tools, caches, and the catalog itself.
SKIPPED_FOLDERS = {CATALOG_FOLDER, ".git", "node_modules", "__pycache__",
                   ".venv", "venv", "$RECYCLE.BIN",
                   "System Volume Information"}

# Files that are never read.
SKIPPED_FILES = {".DS_Store", "Thumbs.db", "desktop.ini"}
TEMPORARY_ENDINGS = (".part", ".download", ".crdownload", ".tmp", "~lock~")

STATUSES = ("idle", "running", "paused", "done", "stopped")


def find_files(folder):
    """List the files of a folder and its subfolders, in a steady order."""
    found = []
    root = os.path.realpath(folder)
    for current, dirs, files in os.walk(root):
        # Prune in place: hidden and tool folders are never entered.
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and
                         d not in SKIPPED_FOLDERS and
                         not os.path.islink(os.path.join(current, d)))
        for name in sorted(files):
            path = os.path.join(current, name)
            if name.startswith(".") or name.startswith("~$") or \
                    name in SKIPPED_FILES or name.endswith(TEMPORARY_ENDINGS):
                continue
            # A link could point outside the project: never followed.
            if os.path.islink(path) or not os.path.isfile(path):
                continue
            found.append(path)
    return found


def file_stamp(path):
    """Return (size, mtime): what says a file changed since it was read."""
    info = os.stat(path)
    return info.st_size, int(info.st_mtime)


class ScanJob:
    """The state of one scan, read by GET /scan and driven by a thread."""

    def __init__(self):
        self.status = "idle"
        self.folder = ""
        self.total = 0
        self.done = 0
        self.current = ""
        self.error = ""
        self.resume_event = threading.Event()
        self.resume_event.set()
        self.stop_requested = False
        self.thread = None

    def to_dict(self):
        """What the screen shows."""
        return {"status": self.status, "folder": self.folder,
                "total": self.total, "done": self.done,
                "current": self.current, "error": self.error}

    def is_running(self):
        """Say whether a thread is still working on this job."""
        return self.thread is not None and self.thread.is_alive()

    def pause(self):
        """Hold the thread before its next file."""
        if self.status == "running":
            self.resume_event.clear()
            self.status = "paused"

    def resume(self):
        """Let a paused thread go on."""
        if self.status == "paused":
            self.status = "running"
            self.resume_event.set()

    def stop(self):
        """Ask the thread to end after its current file."""
        self.stop_requested = True
        self.resume_event.set()


def scan_folder(job, folder, repo, client, owner=None):
    """Read every new or changed file of a folder in place, one by one."""
    files = find_files(folder)
    job.folder = folder
    job.total = len(files)
    job.done = 0
    # A job that starts paused waits for Resume before its first file.
    if job.status != "paused":
        job.status = "running"
    pipeline = ClassificationPipeline(client, repo, FileOrganizer(folder),
                                      owner=owner, in_place=True,
                                      media_client=ready_media_client(repo))
    for path in files:
        # Pause holds here; stop ends here.
        job.resume_event.wait()
        if job.stop_requested:
            job.status = "stopped"
            return
        job.current = os.path.relpath(path, folder)
        try:
            stamp = file_stamp(path)
            known = repo.index_get(path)
            # The same size and date: the file was read already.
            if known and (known["size"], known["mtime"]) == stamp:
                job.done += 1
                continue
            if known:
                repo.delete_document(known["document_id"])
            document = pipeline.classify_document(path)
            repo.index_put(path, stamp[0], stamp[1], document.id)
        except Exception as error:
            # One bad file never stops the scan.
            logger.warning("could not read %s: %s", path, error)
        job.done += 1
    job.current = ""
    job.status = "done"


def read_new_files(folder, repo, client, owner=None):
    """Read the new or changed files of a folder in place, without a job.

    The watcher calls this every few seconds; the index makes it cheap.
    """
    pipeline = ClassificationPipeline(client, repo, FileOrganizer(folder),
                                      owner=owner, in_place=True,
                                      media_client=ready_media_client(repo))
    documents = []
    for path in find_files(folder):
        try:
            stamp = file_stamp(path)
            known = repo.index_get(path)
            if known and (known["size"], known["mtime"]) == stamp:
                continue
            if known:
                repo.delete_document(known["document_id"])
            document = pipeline.classify_document(path)
            repo.index_put(path, stamp[0], stamp[1], document.id)
            documents.append(document)
        except Exception as error:
            logger.warning("could not read %s: %s", path, error)
    return documents


def events_folder_of(tree, path):
    """Return the Events folder a path sits in, or None."""
    parts = folder_tree.split_path(path)
    if len(parts) < 2:
        return None
    parent = folder_tree.join_path(parts[:-1])
    node = folder_tree.node_at(tree, parent)
    if node is not None and node.get("events"):
        return parent
    return None


def auto_apply_place(repo, doc):
    """Return the proposed folder if the user marked it No asking, or None."""
    if not doc.proposed_folder or not repo.is_tree_project():
        return None
    tree = repo.get_folder_tree() or []
    # The folder itself, or an Events folder it is proposed inside of.
    for path in (doc.proposed_folder,
                 events_folder_of(tree, doc.proposed_folder)):
        node = folder_tree.node_at(tree, path) if path else None
        if node is not None and node.get("auto_apply"):
            return doc.proposed_folder
    return None


def apply_proposal(repo, organizer, doc):
    """Move and rename a file as proposed; the folder is created if needed."""
    place = doc.proposed_folder or folder_tree.join_path(
        folder_tree.split_path(doc.folder_path or ""))
    tree = repo.get_folder_tree() or []
    if doc.proposed_folder and folder_tree.find_place(
            tree, doc.proposed_folder) is None:
        # A new event folder: the tree gains it, then the disk.
        tree = folder_tree.add_place(tree, doc.proposed_folder)
        repo.save_tree(tree)
    target = organizer.tree_folder(place) if place else \
        os.path.dirname(doc.file_path)
    name = doc.proposed_name or doc.filename
    old_path = doc.file_path
    new_path = organizer.move_to_folder(old_path, target, name)
    stamp = file_stamp(new_path)
    repo.clear_proposals(doc.id)
    repo.index_replace(old_path, new_path, stamp[0], stamp[1], doc.id)
    logger.info("Moved %s to %s", doc.filename, new_path)
    return repo.move_document(doc.id, new_path,
                              folder_tree.canonical_path(tree, place)
                              if place else (doc.folder_path or ""))


def watch_once(folder, repo, client, owner=None):
    """Read what is new in an in-place project and apply the marked moves."""
    documents = read_new_files(folder, repo, client, owner)
    if repo.is_catalog_project():
        return documents
    organizer = FileOrganizer(folder)
    applied = []
    for doc in documents:
        if auto_apply_place(repo, doc):
            try:
                applied.append(apply_proposal(repo, organizer, doc))
            except Exception as error:
                logger.warning("could not file %s: %s", doc.filename, error)
        else:
            applied.append(doc)
    return applied


def start_scan(app, projects_path, owner=None):
    """Start reading the active project's folder in a thread, once."""
    job = app.config.setdefault("SCAN", ScanJob())
    if job.is_running():
        return job
    folder = projects.active_folder(projects_path)
    if not folder or not os.path.isfile(projects.catalog_path(folder)):
        job.status = "idle"
        return job
    repo = CatalogRepository(projects.catalog_path(folder))
    provider = repo.get_active_provider()
    if not provider:
        job.status = "idle"
        job.error = "no_provider"
        return job
    client = create_client(provider["provider_name"], provider["model"])
    job.__init__()
    job.thread = threading.Thread(
        target=scan_folder, args=(job, folder, repo, client, owner),
        daemon=True)
    job.status = "running"
    job.thread.start()
    return job
