"""Plan routes: what the pipeline proposed, applied in batches, undone."""

import threading

from flask import Blueprint, current_app, jsonify, request

from backend.config import projects as project_list
from backend.pipeline import folder_tree, organization_plan
from backend.pipeline.file_organizer import FileOrganizer
from backend.routes import error_response, get_active_repo, projects_path

plan_bp = Blueprint("plan", __name__)

WATCH_LABEL = "Filed without asking"


def plan_for(repo):
    """Build the engine for the active project."""
    folder = project_list.active_folder(projects_path())
    return organization_plan.OrganizationPlan(repo, FileOrganizer(folder))


def ready_repo():
    """Return (repo, plan, error): the project and whether it has a plan."""
    repo, error = get_active_repo()
    if error:
        return None, None, error
    if repo.is_catalog_project():
        return None, None, error_response(
            "catalog_only", "Catalog only: no plan", 409)
    if not repo.is_tree_project():
        return None, None, error_response(
            "not_tree_project",
            "This project sorts files by type, so it has no plan.", 409)
    return repo, plan_for(repo), None


def row_of(repo, item, docs):
    """One row of the Plan tab: the journal row plus its document."""
    row = dict(item)
    doc = docs.get(item["document_id"]) if item["document_id"] else None
    if doc is not None:
        row.update({"filename": doc.filename, "summary": doc.summary,
                    "why": doc.folder_reason, "confidence": doc.confidence,
                    "review": doc.status == "Manual Review",
                    "review_note": doc.review_note})
    return row


def unchanged_rows(docs, items):
    """Documents the plan leaves alone, so the filter can show them."""
    changed = {item["document_id"] for item in items if item["document_id"]}
    return [{"id": None, "document_id": doc.id, "action": "none",
             "status": "unchanged", "filename": doc.filename,
             "old_folder": doc.folder_path or "", "new_folder": "",
             "old_name": doc.filename, "new_name": "", "summary": doc.summary,
             "why": doc.folder_reason, "confidence": doc.confidence,
             "review": doc.status == "Manual Review",
             "review_note": doc.review_note, "reason": None}
            for doc in docs.values() if doc.id not in changed]


def batch_view(repo, plan, batch_id):
    """The batch, its rows and its counts."""
    batch = repo.get_batch(batch_id)
    items = repo.get_items(batch_id)
    docs = {doc.id: doc for doc in repo.get_all_documents()}
    return {"batch": batch, "summary": plan.summary(batch_id),
            "rows": [row_of(repo, item, docs) for item in items],
            "unchanged": unchanged_rows(docs, items),
            "folders": folder_tree.all_places(repo.get_folder_tree() or [])}


def batch_list(repo, plan):
    """Every batch but the draft, newest first, with its counts."""
    batches = []
    for batch in repo.list_batches():
        if batch["status"] == "draft":
            continue
        batch = dict(batch)
        batch["summary"] = plan.summary(batch["id"])
        batch["label"] = WATCH_LABEL if batch["origin"] == "watch" else ""
        batches.append(batch)
    return batches


@plan_bp.route("/plan", methods=["GET"])
def get_plan():
    """The draft plan, the batches, and whether one is being applied."""
    repo, error = get_active_repo()
    if error:
        return error
    if repo.is_catalog_project():
        return jsonify({"mode": folder_tree.CATALOG_MODE,
                        "message": "Catalog only: no plan"}), 200
    if not repo.is_tree_project():
        return jsonify({"mode": repo.folder_mode(),
                        "message": "This project has no plan."}), 200
    plan = plan_for(repo)
    # A batch cut short by a crash is settled before anything else.
    if not organization_plan.is_busy():
        plan.recover()
    view = batch_view(repo, plan, plan.draft())
    view.update({"mode": repo.folder_mode(),
                 "busy": organization_plan.is_busy(),
                 "batches": batch_list(repo, plan)})
    return jsonify(view), 200


@plan_bp.route("/plan/items", methods=["PUT"])
def choose_items():
    """Approve or skip rows: {"status": "approved", "ids": [...]} or all."""
    repo, plan, error = ready_repo()
    if error:
        return error
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or body.get("status") not in (
            "approved", "skipped"):
        return error_response("missing_field",
                              "status must be approved or skipped.", 400)
    batch_id = plan.draft()
    if body.get("all") is True and body["status"] == "approved":
        count = plan.approve_all(batch_id)
    else:
        ids = body.get("ids")
        if not isinstance(ids, list) or \
                not all(isinstance(item, int) for item in ids):
            return error_response("missing_field",
                                  "ids must be a list of numbers.", 400)
        count = plan.choose(batch_id, ids, body["status"])
    view = batch_view(repo, plan, batch_id)
    view["changed"] = count
    return jsonify(view), 200


@plan_bp.route("/plan/items/<int:item_id>", methods=["PATCH"])
def edit_item(item_id):
    """Change a row's folder or name before applying. A correction."""
    repo, plan, error = ready_repo()
    if error:
        return error
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not (
            isinstance(body.get("folder"), str) or
            isinstance(body.get("name"), str)):
        return error_response("missing_field",
                              "folder or name is required.", 400)
    try:
        batch_id = plan.edit(plan.draft(), item_id, body.get("folder"),
                             body.get("name"))
    except KeyError:
        return error_response("not_found", "That row does not exist.", 404)
    except ValueError as problem:
        return error_response(str(problem), "That change is not valid.",
                              400)
    return jsonify(batch_view(repo, plan, batch_id)), 200


def run_batch(app, repo, plan, batch_id, action):
    """Apply or undo in a thread; the scan is held while it runs."""
    job = app.config.get("SCAN")
    held = job is not None and job.status == "running"
    if held:
        job.pause()
    try:
        if action == "apply":
            plan.apply(batch_id)
        else:
            plan.undo(batch_id)
    finally:
        if held:
            job.resume()


def start_batch(action, batch_id=None):
    """Start applying or undoing a batch in the background."""
    repo, plan, error = ready_repo()
    if error:
        return error
    if organization_plan.is_busy():
        return error_response("plan_applying",
                              "A batch is being applied or undone.", 409)
    if batch_id is None:
        batch_id = plan.draft()
    batch = repo.get_batch(batch_id)
    wanted = ("draft", "paused") if action == "apply" else \
        ("applied", "paused")
    if batch is None or batch["status"] not in wanted:
        return error_response("batch_not_ready",
                              "This batch cannot be {} now.".format(
                                  "applied" if action == "apply"
                                  else "undone"), 409)
    approved = repo.get_items(batch_id, ["approved"])
    if action == "apply" and not any(item["document_id"]
                                     for item in approved):
        return error_response("nothing_approved",
                              "Approve at least one row first.", 409)
    app = current_app._get_current_object()
    thread = threading.Thread(target=run_batch,
                              args=(app, repo, plan, batch_id, action),
                              daemon=True)
    thread.start()
    app.config["PLAN_THREAD"] = thread
    return jsonify({"batch_id": batch_id, "status": "started"}), 202


@plan_bp.route("/plan/apply", methods=["POST"])
def apply_plan():
    """Apply the approved rows of the draft, or resume a paused batch."""
    body = request.get_json(silent=True) or {}
    return start_batch("apply", body.get("batch_id"))


@plan_bp.route("/plan/resume", methods=["POST"])
def resume_batch():
    """Go on with a batch that paused (the disk is back)."""
    body = request.get_json(silent=True) or {}
    if not isinstance(body.get("batch_id"), int):
        return error_response("missing_field", "batch_id is required.", 400)
    return start_batch("apply", body["batch_id"])


@plan_bp.route("/plan/undo", methods=["POST"])
def undo_batch():
    """Undo a batch; the newest applied one when none is named."""
    repo, plan, error = ready_repo()
    if error:
        return error
    body = request.get_json(silent=True) or {}
    batch_id = body.get("batch_id")
    if batch_id is None:
        applied = repo.list_batches(["applied"])
        if not applied:
            return error_response("batch_not_ready",
                                  "There is no batch to undo.", 409)
        batch_id = applied[0]["id"]
    return start_batch("undo", batch_id)


@plan_bp.route("/plan/progress", methods=["GET"])
def progress():
    """How far a batch is: its counts, while it is applied or undone."""
    repo, plan, error = ready_repo()
    if error:
        return error
    batch_id = request.args.get("batch_id", type=int)
    if batch_id is None:
        running = repo.list_batches(["applying", "undoing", "paused"])
        if not running:
            return jsonify({"batch": None, "busy": False}), 200
        batch_id = running[0]["id"]
    batch = repo.get_batch(batch_id)
    if batch is None:
        return error_response("not_found", "That batch does not exist.", 404)
    return jsonify({"batch": batch, "summary": plan.summary(batch_id),
                    "busy": organization_plan.is_busy(),
                    "failed": [dict(item) for item in repo.get_items(
                        batch_id, ["failed"])]}), 200


@plan_bp.route("/batches", methods=["GET"])
def list_batches():
    """Every batch applied so far, with its counts."""
    repo, plan, error = ready_repo()
    if error:
        return error
    return jsonify({"batches": batch_list(repo, plan)}), 200
