"""The organization plan: moves and renames applied in batches.

Every change is written to a journal before the disk is touched and
again after. A batch can be resumed after a crash and undone later.
Nothing is ever overwritten, and nothing leaves the project folder.
"""

import errno
import hashlib
import logging
import os
import shutil
import threading

from backend.pipeline import archive_rules, folder_tree, naming
from backend.pipeline.file_organizer import CATALOG_FOLDER

logger = logging.getLogger(__name__)

ORIGINS = ("plan", "watch")
BATCH_STATUSES = ("draft", "applying", "paused", "applied", "undoing",
                  "undone")
ITEM_STATUSES = ("proposed", "approved", "skipped", "pending", "applied",
                 "failed", "undo_pending", "undone")
ACTIONS = ("move", "rename", "move_rename", "create_folder")

# A copy to another disk is written here first, then named.
PART_SUFFIX = ".cataloga-part"
# A name that only changes its capitals passes through this name.
TEMP_SUFFIX = ".cataloga-tmp"
CHUNK = 1024 * 1024

MISSING_REASON = "File changed or missing since the plan was made"
MOVED_SINCE_REASON = "File moved or changed since it was applied"
TOO_LONG_REASON = archive_rules.TOO_LONG_NOTE
NOT_EMPTY_REASON = "Folder is not empty"
DISK_MISSING_NOTE = "The project folder is not available"
INTERRUPTED_NOTE = "The app closed while this batch was being applied"

# Held while a batch is applied or undone: the scan, the watcher, Move and
# Rename wait.
BUSY = threading.Lock()


def is_busy():
    """Say whether a batch is being applied or undone right now."""
    if BUSY.acquire(blocking=False):
        BUSY.release()
        return False
    return True


def path_length_ok(path):
    """Say whether a full path still fits Windows."""
    return len(path) <= naming.MAX_PATH_LENGTH


def excluded(name):
    """Names the plan never touches: protected, secrets, hidden, ._ files."""
    name = os.path.basename(name or "")
    return (not name or name.startswith(".") or
            naming.is_protected(name) or archive_rules.is_secret(name))


def file_stamp(path):
    """Return (size, mtime) of a file."""
    info = os.stat(path)
    return info.st_size, int(info.st_mtime)


def sha256_of(path):
    """Hash a file by chunks."""
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def same_file(first, second):
    """Say whether two paths are the same file on disk."""
    try:
        return os.path.samefile(first, second)
    except OSError:
        return False


def case_only_change(old_path, new_path):
    """Say whether only the capitals differ: Foto.JPG to foto.jpg."""
    return (old_path != new_path and
            os.path.dirname(old_path) == os.path.dirname(new_path) and
            os.path.basename(old_path).lower() ==
            os.path.basename(new_path).lower())


def free_name(folder, name, old_path=None):
    """Return a name not taken in a folder: name, name_2, name_3..."""
    base, extension = os.path.splitext(name)
    candidate = name
    number = 2
    while True:
        path = os.path.join(folder, candidate)
        # The file itself, when only its capitals change, is not a clash.
        if not os.path.exists(path) or (old_path and
                                        case_only_change(old_path, path)):
            return candidate
        candidate = "{}_{}{}".format(base, number, extension)
        number += 1


def link_or_rename(old_path, new_path):
    """Move within one disk without ever replacing a file at new_path.

    A hard link fails if new_path exists, so nothing is overwritten even
    if a file appeared a moment ago. Disks without links (exFAT) rename
    after a check.
    """
    try:
        os.link(old_path, new_path)
    except FileExistsError:
        raise
    except OSError as error:
        if error.errno not in (errno.EPERM, errno.ENOTSUP, errno.EXDEV,
                               errno.EOPNOTSUPP, errno.EACCES, errno.EMLINK):
            raise
        if os.path.exists(new_path):
            raise FileExistsError(new_path)
        os.rename(old_path, new_path)
        return
    os.unlink(old_path)


def copy_across(old_path, new_path):
    """Copy to another disk, check the hash, then remove the original."""
    part = new_path + PART_SUFFIX
    try:
        shutil.copy2(old_path, part)
        if sha256_of(part) != sha256_of(old_path):
            raise OSError("the copy does not match the original")
        link_or_rename(part, new_path)
    except BaseException:
        if os.path.exists(part):
            os.remove(part)
        raise
    os.unlink(old_path)


def move_file(old_path, new_path, temp_path=None):
    """Move a file, never replacing anything. Returns the path it took."""
    if same_file(old_path, new_path) and case_only_change(old_path,
                                                          new_path):
        # Same file on a case-blind disk: two steps through a temp name.
        temp_path = temp_path or old_path + TEMP_SUFFIX
        os.rename(old_path, temp_path)
        os.rename(temp_path, new_path)
        return new_path
    if os.path.exists(new_path):
        raise FileExistsError(new_path)
    os.makedirs(os.path.dirname(new_path), exist_ok=True)
    if os.stat(old_path).st_dev == os.stat(
            os.path.dirname(new_path)).st_dev:
        link_or_rename(old_path, new_path)
    else:
        copy_across(old_path, new_path)
    return new_path


def remove_if_empty(folder):
    """Remove a folder the batch made, if nothing is left in it."""
    try:
        names = os.listdir(folder)
    except OSError:
        return False
    # Finder leaves .DS_Store behind; alone, it is not content.
    if names == [".DS_Store"]:
        os.remove(os.path.join(folder, ".DS_Store"))
        names = []
    if names:
        return False
    os.rmdir(folder)
    return True


class OrganizationPlan:
    """Build, apply and undo batches of moves and renames for a project."""

    def __init__(self, repo, organizer):
        """Work on one project's catalog and folder."""
        self.repo = repo
        self.organizer = organizer
        self.root = organizer.target_directory

    # --- Building ---

    def file_item(self, doc, approved=False):
        """The journal row for one document's proposal, or None."""
        if not (doc.proposed_folder or doc.proposed_name):
            return None
        # A folder marked Leave as is: its files stay as they are.
        if folder_tree.left_alone(self.repo.get_folder_tree() or [],
                                  doc.folder_path or ""):
            return None
        old_path = doc.file_path
        new_name = doc.proposed_name or doc.filename
        folder = self.organizer.tree_folder(doc.proposed_folder) \
            if doc.proposed_folder else os.path.dirname(old_path)
        new_path = os.path.join(folder, new_name)
        if new_path == old_path:
            return None
        if excluded(doc.filename) or excluded(new_name):
            return None
        action = "move_rename" if doc.proposed_folder and \
            new_name != doc.filename else \
            "move" if doc.proposed_folder else "rename"
        item = {"document_id": doc.id, "action": action,
                "status": "approved" if approved else "proposed",
                "old_path": old_path, "new_path": new_path,
                "old_folder": doc.folder_path or "",
                "new_folder": doc.proposed_folder or doc.folder_path or "",
                "old_name": doc.filename, "new_name": new_name,
                "size": None, "mtime": None, "reason": None, "created": 0}
        try:
            item["size"], item["mtime"] = file_stamp(old_path)
        except OSError:
            item["status"], item["reason"] = "failed", MISSING_REASON
            return item
        if not path_length_ok(new_path):
            # Marked here, so the disk is never touched for it.
            item["status"], item["reason"] = "failed", TOO_LONG_REASON
        return item

    def folder_items(self, file_items):
        """One create_folder row per missing folder, parents first."""
        wanted = []
        for item in file_items:
            if item["action"] in ("move", "move_rename") and \
                    item["status"] != "failed":
                folder = os.path.dirname(item["new_path"])
                while not os.path.isdir(folder) and folder != self.root \
                        and folder not in wanted:
                    wanted.append(folder)
                    folder = os.path.dirname(folder)
        # Deepest last: a parent is made before its child.
        wanted.sort(key=lambda path: path.count(os.sep))
        return [{"document_id": None, "action": "create_folder",
                 "status": "approved", "old_path": None, "new_path": path,
                 "old_folder": None,
                 "new_folder": self.organizer.place_of(path),
                 "old_name": None, "new_name": os.path.basename(path),
                 "size": None, "mtime": None, "reason": None, "created": 0}
                for path in wanted]

    def build(self):
        """Make the draft batch from the proposals; keep earlier choices."""
        kept = {}
        for batch in self.repo.list_batches(["draft"]):
            for item in self.repo.get_items(batch["id"]):
                chosen = item["status"] in ("approved", "skipped")
                if item["document_id"] and chosen:
                    kept[item["document_id"]] = item["status"]
            self.repo.delete_batch(batch["id"])
        file_items = []
        for doc in self.repo.documents_with_proposals():
            item = self.file_item(doc)
            if item is None:
                continue
            if item["status"] == "proposed" and doc.id in kept:
                item["status"] = kept[doc.id]
            file_items.append(item)
        batch_id = self.repo.create_batch("plan")
        self.repo.add_batch_items(batch_id,
                                  self.folder_items(file_items) + file_items)
        return batch_id

    def draft(self):
        """Return the current draft batch, building it when needed."""
        drafts = self.repo.list_batches(["draft"])
        if len(drafts) == 1:
            return drafts[0]["id"]
        return self.build()

    def summary(self, batch_id):
        """Count what a batch does, and what the catalog leaves alone."""
        items = self.repo.get_items(batch_id)
        counts = {"files_read": len(self.repo.get_all_documents()),
                  "moves": 0, "renames": 0, "new_folders": 0, "approved": 0,
                  "skipped": 0, "applied": 0, "failed": 0, "undone": 0,
                  "pending": 0}
        for item in items:
            if item["action"] in ("move", "move_rename"):
                counts["moves"] += 1
            if item["action"] in ("rename", "move_rename"):
                counts["renames"] += 1
            if item["action"] == "create_folder":
                counts["new_folders"] += 1
            if item["status"] in counts:
                counts[item["status"]] += 1
        with_change = {item["document_id"] for item in items
                       if item["document_id"]}
        counts["unchanged"] = counts["files_read"] - len(with_change)
        return counts

    # --- Choosing ---

    def approve_all(self, batch_id):
        """Approve every row but the ones that need a person's eye."""
        chosen = []
        for item in self.repo.get_items(batch_id, ["proposed", "skipped"]):
            doc = self.repo.get_document(item["document_id"]) \
                if item["document_id"] else None
            if doc is None or (doc.status != "Manual Review" and
                               doc.confidence != "low"):
                chosen.append(item["id"])
        return self.repo.set_items_status(batch_id, "approved", chosen)

    def choose(self, batch_id, item_ids, status):
        """Approve or skip the chosen rows."""
        if status not in ("approved", "skipped"):
            raise ValueError(status)
        return self.repo.set_items_status(batch_id, status, item_ids)

    def edit(self, batch_id, item_id, folder=None, name=None):
        """Change a row's folder or name; the change is a correction."""
        item = self.repo.get_item(item_id)
        if item is None or item["batch_id"] != batch_id or \
                not item["document_id"]:
            raise KeyError(item_id)
        doc = self.repo.get_document(item["document_id"])
        tree = self.repo.get_folder_tree() or []
        new_folder = doc.proposed_folder
        if folder is not None:
            place = folder_tree.find_place(tree, folder) if folder else None
            if folder and place is None:
                raise ValueError("unknown_folder")
            new_folder = place if place != (doc.folder_path or "") else None
        new_name = doc.proposed_name
        if name is not None:
            cleaned = naming.clean_new_name(
                name, os.path.splitext(doc.filename)[1])
            if not cleaned:
                raise ValueError("invalid_name")
            new_name = cleaned if cleaned != doc.filename else None
        self.repo.add_correction(
            doc, new_folder or doc.folder_path or "",
            from_name=doc.proposed_name or doc.filename,
            to_name=new_name or doc.filename)
        self.repo.set_proposal(doc.id, new_folder, new_name)
        return self.build()

    # --- Applying ---

    def ensure_tree_folder(self, place):
        """Add a proposed folder to the tree when it is new (an event)."""
        tree = self.repo.get_folder_tree()
        if tree is None or not place or folder_tree.node_at(tree, place):
            return
        self.repo.save_tree(folder_tree.add_place(tree, place))

    def disk_missing(self):
        """Say whether the project folder itself is gone (a drive)."""
        return not os.path.isdir(self.root)

    def make_folder(self, item):
        """Apply a create_folder row."""
        path = item["new_path"]
        self.repo.set_item(item["id"], status="pending")
        existed = os.path.isdir(path)
        os.makedirs(path, exist_ok=True)
        self.repo.set_item(item["id"], status="applied",
                           created=0 if existed else 1)

    def document_fields(self, doc, place, new_path):
        """What a document row becomes after its file moved."""
        folder, subfolder = (folder_tree.first_two(place) if place
                             else (None, None))
        fields = {"folder_path": place or None, "proposed_folder": None,
                  "proposed_name": None}
        if place:
            fields.update({"category": folder, "subcategory": subfolder,
                           "suggested_folder": None})
            if doc.review_note == folder_tree.NO_FOLDER_NOTE:
                fields["review_note"] = None
        return fields

    def apply_file(self, item):
        """Apply one move or rename: verify, journal, disk, journal."""
        doc = self.repo.get_document(item["document_id"])
        old_path, new_path = item["old_path"], item["new_path"]
        if doc is None or not os.path.isfile(old_path) or \
                file_stamp(old_path) != (item["size"], item["mtime"]) or \
                not self.organizer.is_inside_project(new_path):
            self.repo.set_item(item["id"], status="failed",
                               reason=MISSING_REASON)
            return
        # Never replace: a taken name gets _2, _3.
        folder = os.path.dirname(new_path)
        name = free_name(folder, item["new_name"], old_path)
        new_path = os.path.join(folder, name)
        if name != item["new_name"]:
            self.repo.set_item(item["id"], new_path=new_path, new_name=name)
        temp_path = old_path + TEMP_SUFFIX if case_only_change(
            old_path, new_path) else None
        place = doc.proposed_folder if item["action"] != "rename" \
            else (doc.folder_path or "")
        self.repo.set_item(item["id"], status="pending", temp_path=temp_path)
        try:
            self.ensure_tree_folder(place)
            move_file(old_path, new_path, temp_path)
        except OSError as error:
            if self.disk_missing():
                raise
            logger.warning("could not move %s: %s", old_path, error)
            self.repo.set_item(item["id"], status="failed",
                               reason=type(error).__name__ + ": " +
                               str(error)[:200], temp_path=None)
            return
        self.finish_file(item, doc, new_path, place)

    def finish_file(self, item, doc, new_path, place):
        """Write everything a finished move changes, in one transaction."""
        size, mtime = file_stamp(new_path)
        tree = self.repo.get_folder_tree() or []
        place = folder_tree.canonical_path(tree, place) or place \
            if place else (doc.folder_path or "")
        action = "Renamed" if item["action"] == "rename" else "Moved"
        details = "{} → {}".format(
            os.path.relpath(item["old_path"], self.root),
            os.path.relpath(new_path, self.root))
        self.repo.record_file_change(
            item["id"], "applied", doc.id,
            self.document_fields(doc, place, new_path),
            item["old_path"], new_path, action, details, size, mtime)

    def apply(self, batch_id, progress=None):
        """Apply the approved rows of a batch, in order. Returns the batch."""
        batch = self.repo.get_batch(batch_id)
        if batch is None or batch["status"] not in ("draft", "paused"):
            raise ValueError("batch_not_ready")
        with BUSY:
            self.repo.set_batch(batch_id, status="applying", note=None)
            approved = self.repo.get_items(batch_id, ["approved"])
            # A folder is made only when an approved file goes into it.
            wanted = {os.path.dirname(item["new_path"]) for item in approved
                      if item["document_id"]}
            try:
                for item in approved:
                    if item["action"] == "create_folder":
                        if any(path == item["new_path"] or path.startswith(
                                item["new_path"] + os.sep)
                               for path in wanted):
                            self.make_folder(item)
                        else:
                            self.repo.set_item(item["id"], status="skipped")
                    else:
                        self.apply_file(item)
                    if progress:
                        progress()
            except OSError as error:
                # The drive left: the batch waits for it to come back.
                logger.warning("batch %s paused: %s", batch_id, error)
                self.repo.set_batch(batch_id, status="paused",
                                    note=DISK_MISSING_NOTE)
                return self.repo.get_batch(batch_id)
            self.repo.set_batch(batch_id, status="applied",
                                applied_at=now())
        return self.repo.get_batch(batch_id)

    def apply_watch(self, docs):
        """File what the watcher may move without asking, as one batch."""
        items = [item for item in (self.file_item(doc, approved=True)
                                   for doc in docs) if item]
        if not items:
            return None
        batch_id = self.repo.create_batch("watch")
        self.repo.add_batch_items(batch_id, self.folder_items(items) + items)
        return self.apply(batch_id)

    # --- Undoing ---

    def undo_file(self, item):
        """Put one file back, only if it is still where the batch left it."""
        new_path, old_path = item["new_path"], item["old_path"]
        if not os.path.isfile(new_path) or \
                os.stat(new_path).st_size != item["new_size"] or \
                (os.path.exists(old_path) and
                 not case_only_change(new_path, old_path)):
            self.repo.set_item(item["id"], reason=MOVED_SINCE_REASON)
            return
        doc = self.repo.get_document(item["document_id"])
        temp_path = new_path + TEMP_SUFFIX if case_only_change(
            new_path, old_path) else None
        self.repo.set_item(item["id"], status="undo_pending",
                           temp_path=temp_path)
        try:
            move_file(new_path, old_path, temp_path)
        except OSError as error:
            if self.disk_missing():
                raise
            logger.warning("could not put back %s: %s", new_path, error)
            self.repo.set_item(item["id"], status="applied",
                               reason=str(error)[:200], temp_path=None)
            return
        self.finish_undo(item, doc, old_path)

    def finish_undo(self, item, doc, old_path):
        """Restore the document row and the index, in one transaction."""
        size, mtime = file_stamp(old_path)
        place = item["old_folder"] or None
        folder, subfolder = folder_tree.first_two(place) if place \
            else (None, None)
        fields = {"folder_path": place, "category": folder,
                  "subcategory": subfolder,
                  "proposed_folder": item["new_folder"]
                  if item["action"] != "rename" else None,
                  "proposed_name": item["new_name"]
                  if item["action"] != "move" else None}
        details = "{} → {}".format(
            os.path.relpath(item["new_path"], self.root),
            os.path.relpath(old_path, self.root))
        self.repo.record_file_change(
            item["id"], "undone", doc.id, fields, item["new_path"],
            old_path, "Undone", details, size, mtime)

    def undo(self, batch_id):
        """Undo a batch in reverse order. Returns the batch."""
        batch = self.repo.get_batch(batch_id)
        if batch is None or batch["status"] not in ("applied", "paused"):
            raise ValueError("batch_not_ready")
        with BUSY:
            self.repo.set_batch(batch_id, status="undoing", note=None)
            try:
                for item in reversed(self.repo.get_items(batch_id,
                                                         ["applied"])):
                    if item["action"] == "create_folder":
                        if not item["created"]:
                            self.repo.set_item(item["id"], status="undone")
                        elif remove_if_empty(item["new_path"]):
                            self.repo.set_item(item["id"], status="undone")
                        else:
                            self.repo.set_item(item["id"],
                                               reason=NOT_EMPTY_REASON)
                    else:
                        self.undo_file(item)
            except OSError as error:
                logger.warning("undo of batch %s paused: %s", batch_id,
                               error)
                self.repo.set_batch(batch_id, status="paused",
                                    note=DISK_MISSING_NOTE)
                return self.repo.get_batch(batch_id)
            self.repo.set_batch(batch_id, status="undone", undone_at=now())
        return self.repo.get_batch(batch_id)

    # --- After a crash ---

    def settle_item(self, item, undoing):
        """Decide what a pending row became while the app was closed."""
        source, target = (item["new_path"], item["old_path"]) if undoing \
            else (item["old_path"], item["new_path"])
        temp = item["temp_path"]
        if temp and os.path.isfile(temp) and not os.path.exists(target):
            # Caught between the two steps of a case-only rename.
            os.rename(temp, target)
        part = target + PART_SUFFIX
        if os.path.exists(part):
            # A copy that never finished: the original is still whole.
            os.remove(part)
        at_source, at_target = os.path.isfile(source), \
            os.path.isfile(target)
        if at_source and at_target and not same_file(source, target):
            # A finished copy whose original was not removed yet.
            if sha256_of(source) == sha256_of(target):
                os.unlink(source)
                at_source = False
            else:
                self.repo.set_item(item["id"], status="failed",
                                   reason="Both paths exist and differ")
                return
        if at_target and not at_source:
            doc = self.repo.get_document(item["document_id"])
            if undoing:
                self.finish_undo(item, doc, target)
            else:
                place = doc.proposed_folder if item["action"] != "rename" \
                    else (doc.folder_path or "")
                self.finish_file(item, doc, target, place)
        elif at_source:
            # Not done: back to the queue.
            self.repo.set_item(item["id"],
                               status="applied" if undoing else "approved",
                               temp_path=None)
        else:
            self.repo.set_item(item["id"], status="failed",
                               reason="File not found after the app closed")

    def recover(self):
        """Settle batches the app was applying or undoing when it closed."""
        settled = []
        for batch in self.repo.list_batches(["applying", "undoing"]):
            undoing = batch["status"] == "undoing"
            if self.disk_missing():
                self.repo.set_batch(batch["id"], status="paused",
                                    note=DISK_MISSING_NOTE)
                continue
            for item in self.repo.get_items(
                    batch["id"], ["undo_pending" if undoing else "pending"]):
                self.settle_item(item, undoing)
            left = self.repo.get_items(
                batch["id"], ["applied" if undoing else "approved"])
            if left:
                self.repo.set_batch(batch["id"], status="paused",
                                    note=INTERRUPTED_NOTE)
            elif undoing:
                self.repo.set_batch(batch["id"], status="undone",
                                    undone_at=now())
            else:
                self.repo.set_batch(batch["id"], status="applied",
                                    applied_at=now())
            settled.append(batch["id"])
        return settled


def now():
    """Return the time as the catalog writes it."""
    from backend.db.catalog_repository import now_timestamp
    return now_timestamp()
