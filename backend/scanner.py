"""Scanner: reads a project folder in place, with its subfolders.

Files are cataloged where they are; nothing moves and nothing is renamed.
What the pipeline would have done is saved as a proposal for the plan.
"""

import logging
import os
import threading
import time

from backend.config import projects
from backend.db.catalog_repository import CatalogRepository
from backend.pipeline import (archive_rules, file_readers, folder_tree,
                              organization_plan)
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

STATUSES = ("idle", "running", "paused", "done", "stopped", "unread")

# app_config.scan_state, saved per project.
SCAN_RUNNING = "running"
SCAN_DONE = "done"

# How many file names the AI sees to suggest the folders of a new project.
MAX_NAMES_FOR_TREE = 60

# With no file finished in this time, the scan pauses and says so. A file
# that timed out does not count: an AI that is down stops the scan here.
STALL_SECONDS = 5 * 60

# What Retry reads again. Everything else in Manual Review was understood.
RETRY_NOTES = (archive_rules.TIMEOUT_NOTE, archive_rules.CUT_OFF_NOTE,
               archive_rules.SCAN_NOTE, archive_rules.ICLOUD_NOTE)


def is_listed_file(folder, name):
    """Say whether a file counts: not hidden, temporary, or a link."""
    path = os.path.join(folder, name)
    if name.startswith(".") or name.startswith("~$") or \
            name in SKIPPED_FILES or name.endswith(TEMPORARY_ENDINGS):
        return False
    # A link could point outside the project: never followed.
    return not os.path.islink(path) and os.path.isfile(path)


def find_files(folder):
    """List the files of a folder and its subfolders, in a steady order."""
    found = []
    root = os.path.realpath(folder)
    for current, dirs, files in os.walk(root):
        # Prune in place: hidden and tool folders are never entered.
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and
                         d not in SKIPPED_FOLDERS and
                         not os.path.islink(os.path.join(current, d)))
        found += [os.path.join(current, name) for name in sorted(files)
                  if is_listed_file(current, name)]
    return found


def file_stamp(path):
    """Return (size, mtime): what says a file changed since it was read."""
    info = os.stat(path)
    return info.st_size, int(info.st_mtime)


def already_read(repo, path, stamp):
    """Say whether a file's row is good; if not, clear the way for a new one.

    A catalog never has two rows for one path. A row whose index entry was
    lost, or whose date changed with a copy, stays if the content is the same.
    """
    known = repo.index_get(path)
    if known and (known["size"], known["mtime"]) == stamp:
        return True
    doc = repo.document_at(path)
    if doc is not None and doc.sha256 and \
            archive_rules.sha256_of(path) == doc.sha256:
        repo.index_put(path, stamp[0], stamp[1], doc.id)
        return True
    if doc is not None:
        repo.delete_document(doc.id)
    if known:
        repo.delete_document(known["document_id"])
    return False


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
        # Tests replace the clock.
        self.clock = time.monotonic
        self.last_progress = self.clock()
        # When the file being read now was started, or None.
        self.file_started = None

    def note_progress(self):
        """Remember that a file was finished just now."""
        self.last_progress = self.clock()

    def check_stalled(self):
        """Pause with a warning when no file has finished for too long."""
        if self.status == "running" and \
                self.clock() - self.last_progress > STALL_SECONDS:
            logger.warning("no progress in %d s, pausing on %s",
                           STALL_SECONDS, self.current)
            self.error = "stalled"
            self.pause()

    def to_dict(self):
        """What the screen shows."""
        self.check_stalled()
        seconds = 0 if self.file_started is None else \
            int(self.clock() - self.file_started)
        return {"status": self.status, "folder": self.folder,
                "total": self.total, "done": self.done,
                "current": self.current, "error": self.error,
                "current_seconds": seconds}

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
            self.error = ""
            self.note_progress()
            self.resume_event.set()

    def stop(self):
        """Ask the thread to end after its current file."""
        self.stop_requested = True
        self.resume_event.set()


def folder_facts(folder):
    """Count a folder's files and subfolders, and how much they weigh."""
    files = find_files(folder)
    folders = 0
    for current, dirs, names in os.walk(os.path.realpath(folder)):
        dirs[:] = [d for d in dirs if not d.startswith(".") and
                   d not in SKIPPED_FOLDERS and
                   not os.path.islink(os.path.join(current, d))]
        folders += len(dirs)
    return {"files": len(files), "folders": folders,
            "size": sum(os.path.getsize(path) for path in files)}


def suggest_tree_if_empty(repo, folder, files, client):
    """A project made with Later may have no folders yet: ask the AI once."""
    if not repo.is_tree_project() or repo.get_folder_tree():
        return
    config = repo.get_app_config() or {}
    names = [os.path.basename(path) for path in files[:MAX_NAMES_FOR_TREE]]
    description = "{}. {} Some files: {}".format(
        config.get("research_name") or os.path.basename(folder),
        config.get("project_description") or "", ", ".join(names))
    try:
        tree = folder_tree.parse_tree_answer(
            client.send_folders_request(description))
        if tree:
            repo.save_tree(tree)
    except (ValueError, OSError) as error:
        logger.warning("could not suggest folders: %s", error)


def scan_folder(job, folder, repo, client, owner=None):
    """Read every new or changed file of a folder in place, one by one."""
    files = find_files(folder)
    job.folder = folder
    job.total = len(files)
    job.done = 0
    # Saved in the catalog: a closed app leaves it as "running".
    repo.save_config_value("scan_state", SCAN_RUNNING)
    suggest_tree_if_empty(repo, folder, files, client)
    # A job that starts paused waits for Resume before its first file.
    if job.status != "paused":
        job.status = "running"
    pipeline = ClassificationPipeline(client, repo, FileOrganizer(folder),
                                      owner=owner, in_place=True,
                                      media_client=ready_media_client(repo))
    for number, path in enumerate(files, start=1):
        # Pause holds here; stop ends here.
        job.check_stalled()
        job.resume_event.wait()
        if job.stop_requested:
            job.status = "stopped"
            return
        job.current = os.path.relpath(path, folder)
        try:
            stamp = file_stamp(path)
            if already_read(repo, path, stamp):
                job.done += 1
                job.note_progress()
                continue
            logger.info("reading %d/%d %s", number, job.total, job.current)
            job.file_started = job.clock()
            document = pipeline.classify_within_limit(path)
            repo.index_put(path, stamp[0], stamp[1], document.id)
            if document.review_note != archive_rules.TIMEOUT_NOTE:
                job.note_progress()
        except Exception as error:
            # One bad file never stops the scan.
            logger.warning("could not read %s: %s", path, error)
            job.note_progress()
        job.file_started = None
        job.done += 1
    job.current = ""
    job.status = "done"
    repo.save_config_value("scan_state", SCAN_DONE)


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
            if already_read(repo, path, stamp):
                continue
            logger.info("reading %s", os.path.relpath(path, folder))
            document = pipeline.classify_within_limit(path)
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


def apply_proposals(repo, organizer, docs):
    """File documents as proposed, as one watch batch Undo can reverse.

    The batch is written first and the disk touched after, like the plan.
    Returns the documents, fresh from the catalog.
    """
    plan = organization_plan.OrganizationPlan(repo, organizer)
    batch = plan.apply_watch(docs)
    if batch is not None:
        logger.info("watch batch %s: %s", batch["id"], batch["status"])
    return [repo.get_document(doc.id) for doc in docs]


def apply_proposal(repo, organizer, doc):
    """File one document as proposed. Returns it, fresh from the catalog."""
    return apply_proposals(repo, organizer, [doc])[0]


def watch_once(folder, repo, client, owner=None):
    """Read what is new in an in-place project and apply the marked moves."""
    documents = read_new_files(folder, repo, client, owner)
    if repo.is_catalog_project():
        return documents
    marked = [doc for doc in documents if auto_apply_place(repo, doc)]
    if not marked:
        return documents
    try:
        filed = {doc.id: doc for doc in apply_proposals(
            repo, FileOrganizer(folder), marked)}
    except Exception as error:
        logger.warning("could not file the new files: %s", error)
        return documents
    return [filed.get(doc.id, doc) for doc in documents]


def scan_counts(repo, folder):
    """Return (files already read, files in the folder)."""
    files = find_files(folder)
    known = repo.index_paths()
    return sum(1 for path in files if path in known), len(files)


def needs_scan(repo, folder):
    """Say whether a scan was never finished and files still wait for it."""
    if repo.scan_state() == SCAN_DONE:
        return False
    read, total = scan_counts(repo, folder)
    if read == total:
        repo.save_config_value("scan_state", SCAN_DONE)
        return False
    return True


def scan_view(job, repo, folder):
    """What the screen shows for a project, whichever project the job read.

    The job lives in memory and there is one per app: it says nothing
    about another project, or about a scan from before the app started.
    """
    state = job.to_dict()
    if job.folder == folder and (job.is_running() or job.status == "done"):
        return state
    state.update({"status": "idle", "folder": folder, "current": "",
                  "error": "", "done": 0, "total": 0, "current_seconds": 0})
    if not repo.reads_in_place():
        return state
    state["done"], state["total"] = scan_counts(repo, folder)
    if needs_scan(repo, folder):
        state["status"] = "stopped" if state["done"] else "unread"
    return state


def retryable_documents(repo):
    """Return the rows Retry would read again, never one edited by hand."""
    rows = []
    for row in repo.untouched_with_notes(RETRY_NOTES):
        if not os.path.isfile(row["file_path"]):
            continue
        # Still only in iCloud: reading it again would change nothing.
        if row["review_note"] == archive_rules.ICLOUD_NOTE and \
                file_readers.in_cloud_only(row["file_path"]):
            continue
        rows.append(row)
    return rows


def forget_retryable(repo):
    """Forget those rows so the next scan reads only them; return how many."""
    rows = retryable_documents(repo)
    for row in rows:
        # delete_document also removes its row in the scan index.
        repo.delete_document(row["id"])
    return len(rows)


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
