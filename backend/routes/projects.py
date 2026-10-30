"""Project routes."""

import os

from flask import Blueprint, jsonify, request

from backend.config import projects
from backend.db.catalog_repository import CatalogRepository
from backend.db.schema import init_db
from backend.pipeline import folder_tree, naming
from backend.pipeline.ai_providers import (DEFAULT_MODEL, DEFAULT_PROVIDER,
                                           create_client)
from backend.pipeline.file_organizer import FileOrganizer
from backend.routes import error_response, project_status, projects_path

projects_bp = Blueprint("projects", __name__)


def project_list_response():
    """Build the JSON for GET /projects."""
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
    """Return every project and the active one."""
    return jsonify(project_list_response()), 200


@projects_bp.route("/projects", methods=["POST"])
def create_project():
    """Create a project in a folder and make it the active one."""
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
    template = body.get("naming_template", naming.NEW_PROJECT_TEMPLATE)

    description = body.get("description") or ""
    if not isinstance(description, str) or \
            len(description.strip()) > folder_tree.MAX_DESCRIPTION_LENGTH:
        return error_response(
            "invalid_description",
            "description must be text of {} characters or less".format(
                folder_tree.MAX_DESCRIPTION_LENGTH), 400)
    description = description.strip()

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

    # A folder that already has a catalog is opened as it is.
    if os.path.isfile(db_path):
        init_db(db_path)
        config = CatalogRepository(db_path).get_app_config() or {}
        name = config.get("research_name") or name
        organizer.migrate_old_inbox()
        organizer.ensure_archive_structure(
            CatalogRepository(db_path).get_folder_tree())
        projects.add_project(projects_path(), name, folder)
        return jsonify({"name": name, "folder": folder,
                        "opened_existing": True}), 201

    catalog_only = body.get("catalog_only") is True
    tree = []
    if not catalog_only:
        # Every new project files documents in its own folder tree.
        try:
            tree = folder_tree.check_tree(body.get("folders"))
        except ValueError as error:
            return error_response("invalid_folders", str(error), 400)

    # Catalog only reads the folder as it is: its files are expected.
    existing = 0 if catalog_only else organizer.count_existing_items(tree)
    if existing and body.get("confirm_folder") is not True:
        return error_response(
            "folder_not_empty",
            "This folder already has {} items. Cataloga will not move them: "
            "only files you drop into its Drop Zone folder are cataloged. "
            "Click Save anyway to use this folder.".format(existing), 409,
            extra={"count": existing})

    if not catalog_only:
        organizer.ensure_archive_structure(tree)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    init_db(db_path)
    new_repo = CatalogRepository(db_path)
    new_repo.save_app_config(name, folder)
    if catalog_only:
        # Nothing moves, nothing is renamed, and there is no Drop Zone yet:
        # reading the folder in place comes with the in-place scanner.
        new_repo.save_naming_template(naming.KEEP_NAMES)
        new_repo.save_config_value("folder_mode", folder_tree.CATALOG_MODE)
        new_repo.save_config_value("project_description", description)
    else:
        new_repo.save_naming_template(template)
        new_repo.save_folder_tree(description, tree)
    # Ollama Cloud works without typing a key.
    new_repo.set_active_provider(DEFAULT_PROVIDER, DEFAULT_MODEL)
    projects.add_project(projects_path(), name, folder)
    return jsonify({"name": name, "folder": folder,
                    "opened_existing": False}), 201


@projects_bp.route("/projects/folders/suggest", methods=["POST"])
def suggest_folders():
    """Ask Ollama Cloud for a folder tree for a project. Saves nothing."""
    body = request.get_json(silent=True)
    description = body.get("description") if isinstance(body, dict) \
        else None
    if not isinstance(description, str) or not description.strip():
        return error_response("missing_field",
                              "description is required.", 400)
    # The project does not exist yet, so the default provider is used.
    client = create_client(DEFAULT_PROVIDER, DEFAULT_MODEL)
    if not client.api_key:
        return error_response(
            "no_api_key", "Ollama Cloud has no API key yet. Add one in "
            "Advanced settings, or build the folders by hand.", 400)
    tree = folder_tree.parse_tree_answer(client.send_folders_request(
        description.strip()[:folder_tree.MAX_DESCRIPTION_LENGTH]))
    if not tree:
        return error_response(
            "suggest_folders_failed",
            "The AI provider did not suggest any folders.", 502)
    return jsonify({"folders": tree}), 200


@projects_bp.route("/projects", methods=["DELETE"])
def remove_project():
    """Take a project out of the project list."""
    body = request.get_json(silent=True)
    folder = body.get("folder") if isinstance(body, dict) else None
    if not isinstance(folder, str) or not folder.strip():
        return error_response("missing_field", "folder is required.", 400)
    folder = projects.normalize_folder(folder)
    try:
        projects.remove_project(projects_path(), folder)
    except KeyError:
        return error_response("not_found",
                              "This folder is not in the project list.",
                              404)
    return jsonify(project_list_response()), 200


@projects_bp.route("/projects/active", methods=["PUT"])
def switch_project():
    """Make another project in the list the active one."""
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
        # Add any column an older catalog is missing.
        init_db(projects.catalog_path(folder))
    return jsonify(project_list_response()), 200
