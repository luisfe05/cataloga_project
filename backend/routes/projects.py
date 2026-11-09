"""Project routes."""

import os

from flask import Blueprint, current_app, jsonify, request

from backend import scanner
from backend.config import projects
from backend.db.catalog_repository import CatalogRepository
from backend.db.schema import init_db
from backend.pipeline import (archive_rules, conventions, folder_proposal,
                              folder_tree, naming, project_sheet)
from backend.pipeline import learn_folder as learn_folder_module
from backend.pipeline.ai_providers import (DEFAULT_MODEL, DEFAULT_PROVIDER,
                                           create_client)
from backend.pipeline.file_organizer import FileOrganizer
from backend.routes import (error_response, project_status, projects_path,
                            session_user)
from backend.routes.settings import clean_server_url

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
        # Opening never makes a folder: only creating a project or Save do.
        if not CatalogRepository(db_path).reads_in_place():
            organizer.migrate_old_inbox()
        projects.add_project(projects_path(), name, folder)
        return jsonify({"name": name, "folder": folder,
                        "opened_existing": True}), 201

    catalog_only = body.get("catalog_only") is True
    # Archive Later: the folder is only listed. Its tree can come with Learn
    # from my folder, or from the AI when the reading starts.
    later = body.get("defer_scan") is True
    # A folder read in place can start without a tree: reading proposes it.
    reads_files = later or body.get("folder_mode") == folder_tree.PLACE_MODE
    tree = []
    if not catalog_only and not (reads_files and not body.get("folders")):
        # Every new project files documents in its own folder tree.
        try:
            tree = folder_tree.check_tree(body.get("folders"))
        except ValueError as error:
            return error_response("invalid_folders", str(error), 400)
    numbered = body.get("numbered_folders") is True
    if numbered:
        tree = folder_tree.number_new(tree, [])

    # Read in place or Catalog only: the folder's files are expected, and
    # nothing is made.
    in_place = reads_files
    existing = 0 if (in_place or catalog_only) \
        else organizer.count_existing_items(tree)
    if existing and body.get("confirm_folder") is not True:
        return error_response(
            "folder_not_empty",
            "This folder already has {} items. Cataloga will not move them: "
            "only files you drop into its Drop Zone folder are cataloged. "
            "Click Save anyway to use this folder.".format(existing), 409,
            extra={"count": existing})

    if not (in_place or catalog_only):
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
        if body.get("naming_style") in naming.STYLES:
            new_repo.save_config_value("naming_style", body["naming_style"])
        if tree:
            new_repo.save_folder_tree(description, tree)
        else:
            new_repo.save_config_value("project_description", description)
        if in_place:
            new_repo.save_config_value("folder_mode", folder_tree.PLACE_MODE)
        if numbered:
            new_repo.save_config_value("numbered_folders", 1)
    # Archive Later leaves About this project and the AI provider off, so
    # nothing from them is saved; Settings can fill them in before reading.
    sheet = "" if later else project_sheet.clean_sheet(
        body.get("project_sheet"))
    if sheet:
        new_repo.save_config_value("project_sheet", sheet)
    if body.get("stamp_date_order") in archive_rules.STAMP_ORDERS:
        new_repo.save_config_value("stamp_date_order",
                                   body["stamp_date_order"])
    # Ollama Cloud works without typing a key.
    new_repo.set_active_provider(DEFAULT_PROVIDER, DEFAULT_MODEL)
    server_url = "" if later else clean_server_url(body.get("server_url"))
    if server_url:
        new_repo.save_config_value("server_url", server_url)
    projects.add_project(projects_path(), name, folder)
    if (in_place or catalog_only) and not later:
        # Reading starts now; the Catalog shows how far it is.
        scanner.start_scan(current_app._get_current_object(),
                           projects_path(), session_user() or None)
    return jsonify({"name": name, "folder": folder,
                    "opened_existing": False}), 201


@projects_bp.route("/projects/folders/suggest", methods=["POST"])
def suggest_folders():
    """Ask Ollama Cloud for a folder tree for a project. Saves nothing."""
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        body = {}
    description = body.get("description")
    if not isinstance(description, str):
        description = ""
    folder = body.get("folder")
    folder = projects.normalize_folder(folder) \
        if isinstance(folder, str) and folder.strip() else ""
    if folder and not os.path.isdir(folder):
        return error_response("invalid_directory",
                              "The folder does not exist: " + folder, 400)
    if not folder and not description.strip():
        return error_response("missing_field",
                              "description is required.", 400)
    # The project does not exist yet, so the default provider is used.
    client = create_client(DEFAULT_PROVIDER, DEFAULT_MODEL)
    if not client.api_key:
        return error_response(
            "no_api_key", "Ollama Cloud has no API key yet. Add one in "
            "Advanced settings, or build the folders by hand.", 400)
    if folder:
        # A folder with files: only what is there, and the description is
        # context. An organized folder keeps its own tree.
        result = folder_proposal.propose(
            client, folder,
            description.strip()[:folder_tree.MAX_DESCRIPTION_LENGTH])
        if not result["folder_tree"]:
            return error_response(
                "suggest_folders_failed",
                "The AI provider did not suggest any folders.", 502)
        learned = result["learned"]
        return jsonify({"folders": result["folder_tree"],
                        "organized": result["organized"],
                        "naming_style": learned["naming_style"],
                        "naming_template": learned["naming_template"]}), 200
    # The industry, when known, brings the folders that field always has.
    industry = body.get("industry") if isinstance(body.get("industry"),
                                                  str) else ""
    tree = folder_tree.parse_tree_answer(client.send_folders_request(
        description.strip()[:folder_tree.MAX_DESCRIPTION_LENGTH],
        conventions.folder_hints(industry)))
    if not tree:
        return error_response(
            "suggest_folders_failed",
            "The AI provider did not suggest any folders.", 502)
    return jsonify({"folders": tree}), 200


@projects_bp.route("/projects/folders/learn", methods=["POST"])
def learn_folder():
    """Read a folder the user organized and return its tree and naming."""
    body = request.get_json(silent=True)
    folder = body.get("folder") if isinstance(body, dict) else None
    if not isinstance(folder, str) or not folder.strip():
        return error_response("missing_field", "folder is required.", 400)
    folder = projects.normalize_folder(folder)
    if not os.path.isdir(folder):
        return error_response("invalid_directory",
                              "The folder does not exist: " + folder, 400)
    result = learn_folder_module.learn(folder)
    if not result["folder_tree"]:
        return error_response("nothing_to_learn",
                              "This folder has no subfolders to learn from.",
                              400)
    return jsonify(result), 200


@projects_bp.route("/projects/folders/list", methods=["POST"])
def list_folder():
    """Count what a folder holds. No AI, and nothing is written."""
    body = request.get_json(silent=True)
    folder = body.get("folder") if isinstance(body, dict) else None
    if not isinstance(folder, str) or not folder.strip():
        return error_response("missing_field", "folder is required.", 400)
    folder = projects.normalize_folder(folder)
    if not os.path.isdir(folder):
        return error_response("invalid_directory",
                              "The folder does not exist: " + folder, 400)
    return jsonify(dict(scanner.folder_facts(folder),
                        has_catalog=os.path.isfile(
                            projects.catalog_path(folder)))), 200


@projects_bp.route("/projects/active/learn", methods=["POST"])
def learn_active_project():
    """Use the tree and the names of the active project's own folder."""
    folder = projects.active_folder(projects_path())
    if project_status(folder) != "ok":
        return error_response("no_project", "There is no open project.", 409)
    repo = CatalogRepository(projects.catalog_path(folder))
    if repo.is_catalog_project():
        return error_response("catalog_only",
                              "This project keeps its files as they are.",
                              409)
    result = learn_folder_module.learn(folder)
    if not result["folder_tree"]:
        return error_response("nothing_to_learn",
                              "This folder has no subfolders to learn from.",
                              400)
    repo.save_tree(result["folder_tree"])
    repo.save_naming_template(result["naming_template"])
    repo.save_config_value("naming_style", result["naming_style"])
    return jsonify({"description": result["description"],
                    "folders": result["folders"],
                    "files": result["files"]}), 200


@projects_bp.route("/projects/folders/inspect", methods=["POST"])
def inspect_folder():
    """Say whether a folder looks like a website or a linked project."""
    body = request.get_json(silent=True)
    folder = body.get("folder") if isinstance(body, dict) else None
    if not isinstance(folder, str) or not folder.strip():
        return error_response("missing_field", "folder is required.", 400)
    folder = projects.normalize_folder(folder)
    if not os.path.isdir(folder):
        return error_response("invalid_directory",
                              "The folder does not exist: " + folder, 400)
    return jsonify(conventions.inspect_folder(folder)), 200


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
