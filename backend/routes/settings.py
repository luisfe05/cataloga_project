"""Settings routes."""

import os

from flask import Blueprint, current_app, jsonify, request
from keyring.errors import KeyringError

from backend.config import projects
from backend.config.app_config import LANGUAGES, AppConfig
from backend.folder_watcher import old_inbox_has_files
from backend.pipeline.ai_providers import (MEDIA_PROVIDER, PROVIDERS, ROLES,
                                           create_client, project_client)
from backend.pipeline.ai_providers.base import save_api_key
from backend.pipeline import archive_rules, folder_tree, naming, project_sheet
from backend.pipeline.ai_providers import DEFAULT_MODEL, DEFAULT_PROVIDER
from backend.pipeline.file_organizer import FileOrganizer
from backend.routes import (error_response, get_active_repo,
                            project_status, projects_path, session_user)

settings_bp = Blueprint("settings", __name__)


def read_text_fields(body, names):
    """Return the stripped text of each field, or None if one is missing."""
    if not isinstance(body, dict):
        return None
    values = {}
    for name in names:
        value = body.get(name)
        if not isinstance(value, str) or not value.strip():
            return None
        values[name] = value.strip()
    return values


@settings_bp.route("/settings", methods=["GET"])
def get_settings():
    """Return the settings of the active project and the app language."""
    data = projects.load_projects(projects_path())
    folder = data["active_folder"]
    status = project_status(folder)
    settings = {
        "research_name": "",
        "target_directory": folder,
        "naming_template": naming.DEFAULT_TEMPLATE,
        "naming_style": naming.DEFAULT_STYLE,
        "keep_accents": False,
        "industry": "",
        "categories": [],
        "folder_mode": folder_tree.MEDIA_MODE,
        "project_description": "",
        "folder_tree": [],
        "numbered_folders": False,
        "project_sheet": "",
        "folder_counts": {},
        "active_provider": None,
        "active_model": None,
    }
    if status == "ok":
        repo, error = get_active_repo()
        settings.update(AppConfig(repo).get_settings())
        settings["project_sheet"] = repo.get_project_sheet()
        if repo.is_tree_project():
            settings["folder_mode"] = folder_tree.TREE_MODE
            settings["project_description"] = \
                repo.get_project_description()
            settings["folder_tree"] = repo.get_folder_tree()
            settings["numbered_folders"] = repo.numbered_folders()
            settings["folder_counts"] = folder_counts(repo)
        # The list is the source of truth for where the project is.
        settings["target_directory"] = folder
    settings["language"] = data["language"]
    settings["project_status"] = status
    settings["old_inbox_has_files"] = (
        status == "ok" and old_inbox_has_files(FileOrganizer(folder)))
    settings["providers_with_key"] = providers_with_key()
    settings["username"] = session_user()
    return jsonify(settings), 200


def folder_counts(repo):
    """Count the documents in every folder of the tree, at any depth."""
    return {path: repo.count_in_path(path)
            for path in folder_tree.all_paths(repo.get_folder_tree() or [])}


def providers_with_key():
    """Return the names of the providers that have an API key ready."""
    names = []
    for name, client_class in PROVIDERS.items():
        if client_class().api_key:
            names.append(name)
    return names


@settings_bp.route("/settings", methods=["PUT"])
def update_settings():
    """Save the project name, naming template, and app language."""
    body = request.get_json(silent=True)
    if isinstance(body, dict) and "language" in body and \
            body["language"] not in LANGUAGES:
        return error_response(
            "invalid_language",
            "language must be one of: " + ", ".join(LANGUAGES), 400)
    if isinstance(body, dict) and list(body) == ["language"]:
        projects.set_language(projects_path(), body["language"])
        return get_settings()

    values = read_text_fields(body, ("research_name",))
    if values is None:
        return error_response("missing_field",
                              "research_name is required.", 400)
    if "naming_style" in body and body["naming_style"] not in naming.STYLES:
        return error_response("invalid_style",
                              "naming_style must be lower or title.", 400)
    if "project_sheet" in body:
        body["project_sheet"] = project_sheet.clean_sheet(
            body["project_sheet"])
        if body["project_sheet"] is None:
            return error_response(
                "invalid_sheet", "project_sheet must be text of {} "
                "characters or less".format(project_sheet.MAX_SHEET_LENGTH),
                400)
    if "server_url" in body:
        body["server_url"] = clean_server_url(body["server_url"])
        if body["server_url"] is None:
            return error_response(
                "invalid_server_url",
                "server_url must start with http:// or https://.", 400)
    if "naming_template" in body:
        problem = naming.validate_template(body["naming_template"])
        if problem:
            return error_response(
                "invalid_template",
                "The naming template is not valid: " + problem["reason"],
                400, extra=problem)

    repo, error = get_active_repo()
    if error:
        return error
    tree_mode = repo.is_tree_project()
    if tree_mode:
        archive = read_folder_tree(body, repo)
    else:
        archive = read_archive_settings(body)
    if isinstance(archive, tuple):
        return error_response(archive[0], archive[1], archive[2])
    if isinstance(archive, str):
        return error_response("invalid_categories", archive, 400)

    folder = projects.active_folder(projects_path())
    config = AppConfig(repo)

    # Must run before ensure_archive_structure(), or Drop Zone is doubled.
    organizer = FileOrganizer(folder)
    organizer.migrate_old_inbox()
    if tree_mode and "numbered_folders" in body:
        repo.save_config_value("numbered_folders",
                               1 if body["numbered_folders"] else 0)
    if tree_mode and archive is not None:
        # New folders are created now; removed ones stay on the disk.
        repo.save_tree(archive["categories"])
    organizer.ensure_archive_structure(repo.get_folder_tree())

    config.update_settings(values["research_name"], folder)
    projects.rename_project(projects_path(), folder,
                            values["research_name"])
    if "naming_template" in body:
        config.update_naming_template(body["naming_template"])
    if "naming_style" in body:
        repo.save_config_value("naming_style", body["naming_style"])
    if "keep_accents" in body:
        repo.save_config_value("keep_accents",
                               1 if body["keep_accents"] else 0)
    if "project_sheet" in body:
        repo.save_config_value("project_sheet", body["project_sheet"])
    if "server_url" in body:
        repo.save_config_value("server_url", body["server_url"])
    if archive is not None and not tree_mode:
        config.update_categories(archive["industry"], archive["categories"])
    if "language" in body:
        projects.set_language(projects_path(), body["language"])
    return get_settings()


def read_archive_settings(body):
    """Return the checked industry and categories, or an error text."""
    if "industry" not in body and "categories" not in body:
        return None
    industry = body.get("industry") or ""
    if not isinstance(industry, str) or \
            len(industry.strip()) > archive_rules.MAX_INDUSTRY_LENGTH:
        return "industry must be text of {} characters or less".format(
            archive_rules.MAX_INDUSTRY_LENGTH)
    try:
        categories = archive_rules.clean_categories(body.get("categories"))
    except ValueError as error:
        return str(error)
    return {"industry": industry.strip(), "categories": categories}


def read_folder_tree(body, repo):
    """Return the checked tree, or (code, message, status) if it is wrong."""
    sent = body.get("folder_tree", body.get("categories"))
    if sent is None:
        return None
    try:
        tree = folder_tree.check_tree(sent)
    except ValueError as error:
        return ("invalid_folders", str(error), 400)
    # A folder that holds documents can never leave the tree.
    paths = folder_tree.all_paths(tree)
    for place in folder_tree.all_paths(repo.get_folder_tree() or []):
        if not folder_in(place, paths) and repo.count_in_path(place):
            return ("folder_not_empty",
                    "This folder has documents: " + place, 409)
    if body.get("numbered_folders") if "numbered_folders" in body \
            else repo.numbered_folders():
        tree = folder_tree.number_new(
            tree, folder_tree.all_paths(repo.get_folder_tree() or []))
    return {"categories": tree}


def folder_in(place, places):
    """Say whether a folder is in a list, ignoring case and accents."""
    return archive_rules.fold(place) in [archive_rules.fold(p)
                                         for p in places]


@settings_bp.route("/settings/categories/suggest", methods=["POST"])
def suggest_categories():
    """Ask the active AI for categories for an industry. Saves nothing."""
    body = request.get_json(silent=True)
    values = read_text_fields(body, ("industry",))
    if values is None:
        return error_response("missing_field", "industry is required.", 400)
    repo, error = get_active_repo()
    if error:
        return error
    client = project_client(repo)
    if client is None:
        return error_response("no_provider",
                              "Choose an AI provider first.", 400)
    industry = values["industry"][:archive_rules.MAX_INDUSTRY_LENGTH]
    categories = archive_rules.parse_category_answer(
        client.send_categories_request(industry))
    if not categories:
        return error_response(
            "suggest_failed",
            "The AI provider did not suggest any categories.", 502)
    return jsonify({"categories": categories}), 200


@settings_bp.route("/settings/sheet/suggest", methods=["POST"])
def suggest_sheet():
    """Ask the AI to write the project sheet from a sample. Saves nothing."""
    body = request.get_json(silent=True)
    folder = body.get("folder") if isinstance(body, dict) else None
    if isinstance(folder, str) and folder.strip():
        folder = projects.normalize_folder(folder)
    else:
        # No folder sent: the active project's own folder.
        folder = projects.active_folder(projects_path())
    if not folder or not os.path.isdir(folder):
        return error_response("invalid_directory",
                              "The folder does not exist: " + str(folder),
                              400)
    repo, error = get_active_repo()
    client = project_client(repo) if error is None else None
    if client is None:
        # Before the first project exists, the default provider is used.
        client = create_client(DEFAULT_PROVIDER, DEFAULT_MODEL)
    if not client.api_key:
        return error_response("no_provider",
                              "Choose an AI provider first.", 400)
    sample = project_sheet.project_sample(folder)
    sheet = project_sheet.parse_sheet_answer(client.ask(
        project_sheet.SHEET_PROMPT.format(
            industries=", ".join(project_sheet.INDUSTRIES)),
        project_sheet.sample_text(sample)))
    if not sheet:
        return error_response("suggest_failed",
                              "The AI provider did not write a sheet.", 502)
    return jsonify({"sheet": sheet}), 200


def clean_server_url(value):
    """Return a server URL without spaces, '' for none, or None if bad."""
    if value is None:
        return ""
    if not isinstance(value, str):
        return None
    value = value.strip().rstrip("/")
    if not value:
        return ""
    if not value.startswith(("http://", "https://")) or len(value) > 200:
        return None
    return value


def read_role(body):
    """Return the role a provider request is about: text unless said."""
    role = body.get("role", "text") if isinstance(body, dict) else "text"
    return role if role in ROLES else None


@settings_bp.route("/settings/ai-provider", methods=["PUT"])
def update_ai_provider():
    """Update the provider, model, and API key of one role."""
    body = request.get_json(silent=True)
    values = read_text_fields(body, ("provider_name", "model"))
    if values is None:
        return error_response("missing_field",
                              "provider_name and model are required.", 400)
    role = read_role(body)
    if role is None:
        return error_response("invalid_role",
                              "role must be text, fallback, or media.", 400)
    repo, error = get_active_repo()
    if error:
        return error
    if values["provider_name"] not in PROVIDERS:
        return error_response(
            "unsupported_provider",
            "Unsupported AI provider: " + values["provider_name"], 400)
    # Ollama Cloud and the others do not read audio or video.
    if role == "media" and values["provider_name"] != MEDIA_PROVIDER:
        return error_response(
            "unsupported_provider",
            "Only Google Gemini reads audio and video.", 400)

    api_key = body.get("api_key")
    if isinstance(api_key, str) and api_key.strip():
        try:
            save_api_key(values["provider_name"], api_key.strip())
        except KeyringError:
            # Like macOS error -25244. Nothing is saved, not even the provider.
            return error_response(
                "keyring_failed",
                "The API key could not be saved in the system keychain.",
                400)

    repo.set_provider(role, values["provider_name"], values["model"])
    return jsonify({"role": role, "provider_name": values["provider_name"],
                    "model": values["model"]}), 200


@settings_bp.route("/settings/ai-provider/<role>", methods=["DELETE"])
def clear_ai_provider(role):
    """Take the fallback or media provider away. The key stays saved."""
    if role not in ROLES or role == "text":
        return error_response("invalid_role",
                              "Only fallback and media can be cleared.", 400)
    repo, error = get_active_repo()
    if error:
        return error
    repo.clear_provider(role)
    return jsonify({"role": role, "provider_name": None}), 200


@settings_bp.route("/settings/ai-provider/test", methods=["POST"])
def test_ai_provider():
    """Test whether the provided AI credentials can connect."""
    body = request.get_json(silent=True)
    values = read_text_fields(body, ("provider_name", "model"))
    if values is None:
        return error_response("missing_field",
                              "provider_name and model are required.", 400)
    server_url = body.get("server_url")
    if not isinstance(server_url, str) or not server_url.strip():
        server_url = None
    try:
        client = create_client(values["provider_name"], values["model"],
                               server_url)
    except ValueError as error:
        return error_response("unsupported_provider", str(error), 400)

    api_key = body.get("api_key")
    if isinstance(api_key, str) and api_key.strip():
        client.api_key = api_key.strip()

    try:
        client.test_connection()
    except Exception as error:
        return error_response("connection_failed", str(error), 400)
    return jsonify({"connected": True}), 200
