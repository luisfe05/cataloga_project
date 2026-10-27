"""Project routes.

Endpoints:
    GET  /projects            List the projects and say which one is
                              active.
    POST /projects            Create a project (or open a folder that
                              already has a Cataloga catalog) and make
                              it active.
    PUT  /projects/active     Switch to another project in the list.

Added in the scope change of Oct 25 (multi-project). Each project keeps
its own catalog in <folder>/.cataloga/catalog.db.
"""

import os

from flask import Blueprint, jsonify, request

from backend.config import projects
from backend.db.catalog_repository import CatalogRepository
from backend.db.schema import init_db
from backend.pipeline import naming
from backend.pipeline.ai_providers import DEFAULT_MODEL, DEFAULT_PROVIDER
from backend.pipeline.file_organizer import FileOrganizer
from backend.routes import error_response, project_status, projects_path

projects_bp = Blueprint("projects", __name__)


def project_list_response():
    """Build the JSON for GET /projects.

    Returns:
        dict: {'active_folder': str, 'projects': [{'name', 'folder',
            'last_opened', 'available'}]}, the most recently opened
            project first.
    """
    data = projects.load_projects(projects_path())
    items = []
    for project in data["projects"]:
        item = dict(project)
        item["available"] = project_status(project["folder"]) == "ok"
        items.append(item)
    items.sort(key=lambda item: item["last_opened"], reverse=True)
    return {"active_folder": data["active_folder"], "projects": items}


@projects_bp.route("/projects", methods=["GET"])
def list_projects():
    """Return every project and the active one.

    Returns:
        200: JSON from project_list_response().
    """
    return jsonify(project_list_response()), 200


@projects_bp.route("/projects", methods=["POST"])
def create_project():
    """Create a project in a folder and make it the active one.

    If the folder already has a Cataloga catalog (.cataloga/catalog.db),
    that catalog is opened with all its data instead of making a new
    one, and its saved name is kept.

    Request body (JSON): name, folder, and optional naming_template
                         (default: method 1) and confirm_folder (bool).

    Returns:
        201: {'name', 'folder', 'opened_existing'}.
        400: If a field is missing, the folder does not exist, or the
             naming template is not valid ('invalid_template' with
             'reason' and 'token').
        409: 'project_exists' if the folder is already in the list, or
             'folder_not_empty' (with 'count') if the folder has the
             user's own files and confirm_folder is not true.
    """
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        body = {}
    name = body.get("name")
    folder = body.get("folder")
    if not isinstance(name, str) or not name.strip() or \
            not isinstance(folder, str) or not folder.strip():
        return error_response("missing_field",
                              "name and folder are required.", 400)
    name = name.strip()
    folder = projects.normalize_folder(folder)
    template = body.get("naming_template", naming.DEFAULT_TEMPLATE)

    if not os.path.isdir(folder):
        return error_response("invalid_directory",
                              "The folder does not exist: " + folder, 400)
    problem = naming.validate_template(template)
    if problem:
        return error_response(
            "invalid_template",
            "The naming template is not valid: " + problem["reason"],
            400, extra=problem)
    data = projects.load_projects(projects_path())
    if projects.find_project(data, folder):
        return error_response("project_exists",
                              "This folder is already a project.", 409)

    db_path = projects.catalog_path(folder)
    organizer = FileOrganizer(folder)

    # A folder that already has a catalog (for example, an external
    # drive used on another computer) is opened as it is.
    if os.path.isfile(db_path):
        init_db(db_path)
        config = CatalogRepository(db_path).get_app_config() or {}
        name = config.get("research_name") or name
        organizer.migrate_old_inbox()
        organizer.ensure_archive_structure()
        projects.add_project(projects_path(), name, folder)
        return jsonify({"name": name, "folder": folder,
                        "opened_existing": True}), 201

    existing = organizer.count_existing_items()
    if existing and body.get("confirm_folder") is not True:
        return error_response(
            "folder_not_empty",
            "This folder already has {} items. Cataloga will not move them: "
            "only files you drop into its Drop Zone folder are cataloged. "
            "Click Save anyway to use this folder.".format(existing), 409,
            extra={"count": existing})

    organizer.ensure_archive_structure()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    init_db(db_path)
    new_repo = CatalogRepository(db_path)
    new_repo.save_app_config(name, folder)
    new_repo.save_naming_template(template)
    # Every new project starts with Ollama Cloud, so it works without
    # typing a key. The user can change it in Advanced settings.
    new_repo.set_active_provider(DEFAULT_PROVIDER, DEFAULT_MODEL)
    projects.add_project(projects_path(), name, folder)
    return jsonify({"name": name, "folder": folder,
                    "opened_existing": False}), 201


@projects_bp.route("/projects/active", methods=["PUT"])
def switch_project():
    """Make another project in the list the active one.

    A project whose folder is not available can still be chosen: the
    Catalog then says the folder is missing.

    Request body (JSON): folder.

    Returns:
        200: JSON from project_list_response().
        400: If folder is missing.
        404: If the folder is not in the project list.
    """
    body = request.get_json(silent=True)
    folder = body.get("folder") if isinstance(body, dict) else None
    if not isinstance(folder, str) or not folder.strip():
        return error_response("missing_field", "folder is required.", 400)
    folder = projects.normalize_folder(folder)
    try:
        projects.set_active_project(projects_path(), folder)
    except KeyError:
        return error_response("not_found",
                              "This folder is not in the project list.",
                              404)
    if project_status(folder) == "ok":
        # Add any column a catalog made by an older version is missing.
        init_db(projects.catalog_path(folder))
    return jsonify(project_list_response()), 200
