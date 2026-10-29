"""Document routes."""

import csv
import io
import os

from flask import Blueprint, Response, jsonify, request

from backend.pipeline.ai_providers import create_client
from backend.pipeline.classification_pipeline import ClassificationPipeline
from backend.config import projects as project_list
from backend.pipeline import folder_tree
from backend.pipeline.file_organizer import FileOrganizer
from backend.pipeline.naming import clean_new_name
from backend.routes import error_response, get_active_repo, projects_path

documents_bp = Blueprint("documents", __name__)

# Same order as the catalog table: (header, Document attribute).
EXPORT_COLUMNS = (
    ("Original Filename", "original_filename"),
    ("Filename", "filename"),
    ("Media Type", "media_type"),
    ("Source", "source"),
    ("Date", "document_date"),
    ("Date Source", "date_source"),
    ("Summary", "summary"),
    ("Status", "status"),
    ("Topic", "topic"),
    ("Keywords", "keywords"),
    ("Category", "category"),
    ("Subcategory", "subcategory"),
    ("Counterparty", "counterparty"),
    ("Confidentiality", "confidentiality"),
    ("Owner", "owner"),
    ("Effective Start", "effective_start"),
    ("Effective End", "effective_end"),
    ("Duplicate Of", "duplicate_of"),
    ("Review Note", "review_note"),
    ("Suggested Folder", "suggested_folder"),
    ("SHA-256", "sha256"),
)


def summary_should_update(fields):
    """Decide if a PATCH should regenerate the AI summary."""
    changed_facts = "source" in fields or "document_date" in fields
    return changed_facts and "summary" not in fields


def regenerate_summary(repo, doc):
    """Ask the active AI provider for a new summary of one document."""
    config = repo.get_app_config()
    provider = repo.get_active_provider()
    if not config or not provider:
        return doc
    pipeline = ClassificationPipeline(
        create_client(provider["provider_name"], provider["model"]),
        repo,
        FileOrganizer(config["target_directory"]),
    )
    return pipeline.regenerate_summary(doc)


def read_filters():
    """Collect the optional filter query params from the request."""
    filters = {}
    for name in ("media_type", "source", "status", "search", "category",
                 "subcategory"):
        value = request.args.get(name)
        if value:
            filters[name] = value
    return filters


@documents_bp.route("/documents", methods=["GET"])
def list_documents():
    """Return all documents, filtered by optional query params."""
    repo, error = get_active_repo()
    if error:
        return error
    documents = repo.get_all_documents(read_filters())
    return jsonify([doc.to_dict() for doc in documents]), 200


@documents_bp.route("/documents/export", methods=["GET"])
def export_documents():
    """Export the catalog as a downloadable file."""
    file_format = request.args.get("format", "csv").lower()
    if file_format != "csv":
        return error_response("unsupported_format",
                              "Only csv export is supported.", 400)

    repo, error = get_active_repo()
    if error:
        return error
    documents = repo.get_all_documents(read_filters())

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([header for header, attribute in EXPORT_COLUMNS])
    for doc in documents:
        row = [getattr(doc, attribute) or ""
               for header, attribute in EXPORT_COLUMNS]
        # Keywords are a list; one cell keeps them as "a; b; c".
        row[EXPORT_COLUMNS.index(("Keywords", "keywords"))] = \
            "; ".join(doc.keywords)
        writer.writerow(row)

    # Content-Disposition tells the browser to save it as a file.
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition":
                 "attachment; filename=cataloga_worksheet.csv"},
    )


@documents_bp.route("/documents/<int:doc_id>", methods=["GET"])
def get_document(doc_id):
    """Return a single document by id."""
    repo, error = get_active_repo()
    if error:
        return error
    doc = repo.get_document(doc_id)
    if doc is None:
        return error_response("not_found",
                              "Document {} does not exist.".format(doc_id),
                              404)
    return jsonify(doc.to_dict()), 200


@documents_bp.route("/documents/<int:doc_id>", methods=["PATCH"])
def update_document(doc_id):
    """Update editable fields on a document."""
    # silent=True returns None instead of raising on a bad body.
    fields = request.get_json(silent=True)
    if not isinstance(fields, dict):
        return error_response("invalid_body",
                              "The request body must be a JSON object.", 400)
    repo, error = get_active_repo()
    if error:
        return error
    # In a tree project the folder is the file's place: Move changes it.
    if repo.is_tree_project() and \
            ("category" in fields or "subcategory" in fields):
        return error_response(
            "use_move", "Use Move to change a document's folder.", 400)
    try:
        doc = repo.update_document(doc_id, fields)
    except ValueError as error:
        return error_response("invalid_field", str(error), 400)
    except KeyError:
        return error_response("not_found",
                              "Document {} does not exist.".format(doc_id),
                              404)
    if summary_should_update(fields):
        try:
            doc = regenerate_summary(repo, doc)
        except Exception:
            # The user's edit is already saved; keep the old summary.
            pass
    return jsonify(doc.to_dict()), 200


@documents_bp.route("/documents/<int:doc_id>/rename", methods=["POST"])
def rename_document(doc_id):
    """Rename one document after the user clicked Confirm in the chat."""
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return error_response("invalid_body",
                              "The request body must be a JSON object.", 400)
    if not isinstance(body.get("new_name"), str):
        return error_response("missing_field", "new_name is required.", 400)

    repo, error = get_active_repo()
    if error:
        return error
    doc = repo.get_document(doc_id)
    if doc is None:
        return error_response("not_found",
                              "Document {} does not exist.".format(doc_id),
                              404)

    extension = os.path.splitext(doc.filename)[1]
    new_filename = clean_new_name(body["new_name"], extension)
    if not new_filename:
        return error_response("invalid_name",
                              "The new name has no valid characters.", 400)
    if new_filename == doc.filename:
        return jsonify(doc.to_dict()), 200

    folder = project_list.active_folder(projects_path())
    try:
        new_path = FileOrganizer(folder).rename_file(doc.file_path,
                                                     new_filename)
    except (ValueError, FileNotFoundError):
        return error_response(
            "file_missing",
            "The file is missing or outside the project folder.", 409)

    try:
        doc = repo.rename_document(doc_id, os.path.basename(new_path),
                                   new_path)
    except Exception:
        # Keep the disk and the catalog in step: put the old name back.
        os.rename(new_path, doc.file_path)
        raise
    return jsonify(doc.to_dict()), 200


@documents_bp.route("/documents/<int:doc_id>/move", methods=["POST"])
def move_document(doc_id):
    """Move one document to another folder of the project's tree."""
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not isinstance(body.get("folder"), str):
        return error_response("missing_field", "folder is required.", 400)
    repo, error = get_active_repo()
    if error:
        return error
    tree = repo.get_folder_tree()
    if tree is None:
        return error_response(
            "not_tree_project",
            "This project sorts files by type, so files are not moved.", 409)
    doc = repo.get_document(doc_id)
    if doc is None:
        return error_response("not_found",
                              "Document {} does not exist.".format(doc_id),
                              404)
    folder = project_list.active_folder(projects_path())
    organizer = FileOrganizer(folder)
    if not os.path.isfile(doc.file_path) or \
            not organizer.is_inside_project(doc.file_path):
        return error_response(
            "file_missing",
            "The file is missing or outside the project folder.", 409)

    place = folder_tree.find_place(tree, body["folder"])
    if place is None and body.get("create_folder") is True:
        # Only a click on "Create folder and move" adds a folder.
        try:
            tree = folder_tree.add_place(tree, body["folder"])
        except ValueError as error:
            return error_response("invalid_folders", str(error), 400)
        repo.save_categories(tree)
        organizer.ensure_archive_structure(tree)
        place = folder_tree.find_place(tree, body["folder"])
    if place is None:
        return error_response("unknown_folder",
                              "This folder is not in the project.", 400)
    if (doc.category, doc.subcategory) == place:
        return jsonify(doc.to_dict()), 200

    new_path = organizer.move_to_folder(
        doc.file_path, organizer.tree_folder(*place), doc.filename)
    try:
        doc = repo.move_document(doc_id, new_path, *place)
    except Exception:
        # Keep the disk and the catalog in step: put the file back.
        os.rename(new_path, doc.file_path)
        raise
    return jsonify(doc.to_dict()), 200


def run_file_action(doc_id, action):
    """Check a document's file, then open, reveal, or preview it."""
    repo, error = get_active_repo()
    if error:
        return error
    doc = repo.get_document(doc_id)
    if doc is None:
        return error_response("not_found",
                              "Document {} does not exist.".format(doc_id),
                              404)
    organizer = FileOrganizer(project_list.active_folder(projects_path()))
    if not organizer.is_inside_project(doc.file_path) or \
            not os.path.isfile(doc.file_path):
        return error_response(
            "file_missing",
            "The file is missing or outside the project folder.", 409)

    # Each action is a FileOrganizer method with the same name.
    actions = {
        "open": organizer.open_file,
        "reveal": organizer.reveal_file,
        "preview": organizer.preview_file,
    }
    actions[action](doc.file_path)
    return jsonify({"ok": True}), 200


@documents_bp.route("/documents/<int:doc_id>/open", methods=["POST"])
def open_document(doc_id):
    """Open a document's file with its default app."""
    return run_file_action(doc_id, "open")


@documents_bp.route("/documents/<int:doc_id>/reveal", methods=["POST"])
def reveal_document(doc_id):
    """Show a document's file in Finder, selected."""
    return run_file_action(doc_id, "reveal")


@documents_bp.route("/documents/<int:doc_id>/preview", methods=["POST"])
def preview_document(doc_id):
    """Show a Quick Look preview of a document's file."""
    return run_file_action(doc_id, "preview")
