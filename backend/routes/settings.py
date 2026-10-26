"""Settings routes.

Endpoints:
    GET  /settings                      Return the active project's
                                        settings and the app language.
    PUT  /settings                      Update the project's name and
                                        naming_template, and language.
    PUT  /settings/ai-provider          Update the active project's
                                        provider and model, write the
                                        API key to the keyring.
    POST /settings/ai-provider/test     Test whether the provider
                                        config connects.
"""

from flask import Blueprint, jsonify, request

from backend.config import projects
from backend.config.app_config import LANGUAGES, AppConfig
from backend.folder_watcher import old_inbox_has_files
from backend.pipeline.ai_providers import PROVIDERS, create_client
from backend.pipeline.ai_providers.base import save_api_key
from backend.pipeline import naming
from backend.pipeline.file_organizer import FileOrganizer
from backend.routes import (error_response, get_active_repo,
                            project_status, projects_path)

settings_bp = Blueprint("settings", __name__)


def read_text_fields(body, names):
    """Return the stripped text of each field, or None if one is missing.

    Args:
        body (dict or None): The parsed JSON body.
        names (tuple[str]): Fields that must be non-empty text.

    Returns:
        dict or None: {name: text}, or None if any field is missing.
    """
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
    """Return the settings of the active project and the app language.

    Returns:
        200: JSON with research_name, target_directory (the project
             folder), language (the same for every project),
             naming_template, active_provider, active_model,
             old_inbox_has_files, and project_status ('none',
             'unavailable', or 'ok'). With no usable project, the
             project fields are empty. The API key is never returned.
    """
    data = projects.load_projects(projects_path())
    folder = data["active_folder"]
    status = project_status(folder)
    settings = {
        "research_name": "",
        "target_directory": folder,
        "naming_template": naming.DEFAULT_TEMPLATE,
        "active_provider": None,
        "active_model": None,
    }
    if status == "ok":
        repo, error = get_active_repo()
        settings.update(AppConfig(repo).get_settings())
        # The list is the source of truth for where the project is.
        settings["target_directory"] = folder
    settings["language"] = data["language"]
    settings["project_status"] = status
    settings["old_inbox_has_files"] = (
        status == "ok" and old_inbox_has_files(FileOrganizer(folder)))
    return jsonify(settings), 200


@settings_bp.route("/settings", methods=["PUT"])
def update_settings():
    """Update the active project's name and naming template, and the
    app language.

    The project folder cannot change here: the catalog is saved inside
    it. A new folder means a new project (POST /projects).

    A body with only 'language' saves just the language, which works
    even before any project exists.

    Request body (JSON): research_name, and optional naming_template
                         (str) and language ('en' or 'es').

    Returns:
        200: JSON of the updated settings (same shape as GET).
        400: If the name is missing, the language is not supported, or
             the naming template is not valid. An 'invalid_template'
             error includes 'reason' ('empty', 'no_token', 'unknown',
             'chars') and 'token'.
        409: If there is no usable project.
    """
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
    folder = projects.active_folder(projects_path())
    config = AppConfig(repo)

    # Saving the same project again also renames an old Inbox to Drop
    # Zone. It must run before ensure_archive_structure(), which would
    # otherwise create an empty Drop Zone next to the old Inbox.
    organizer = FileOrganizer(folder)
    organizer.migrate_old_inbox()
    organizer.ensure_archive_structure()

    config.update_settings(values["research_name"], folder)
    projects.rename_project(projects_path(), folder,
                            values["research_name"])
    if "naming_template" in body:
        config.update_naming_template(body["naming_template"])
    if "language" in body:
        projects.set_language(projects_path(), body["language"])
    return get_settings()


@settings_bp.route("/settings/ai-provider", methods=["PUT"])
def update_ai_provider():
    """Update the active AI provider, model, and API key.

    The provider and model are saved in the active project's catalog.
    The API key is written to the OS keyring, one per provider, so every
    project shares it. It is never stored in the database or returned in
    any response. If api_key is empty, the key already saved for that
    provider is kept.

    Request body (JSON): provider_name, model, api_key.

    Returns:
        200: The active provider and model (no key echoed back).
        400: If a field is missing or the provider is not supported.
        409: If there is no usable project.
    """
    body = request.get_json(silent=True)
    values = read_text_fields(body, ("provider_name", "model"))
    if values is None:
        return error_response("missing_field",
                              "provider_name and model are required.", 400)
    repo, error = get_active_repo()
    if error:
        return error
    if values["provider_name"] not in PROVIDERS:
        return error_response(
            "unsupported_provider",
            "Unsupported AI provider: " + values["provider_name"], 400)

    api_key = body.get("api_key")
    if isinstance(api_key, str) and api_key.strip():
        save_api_key(values["provider_name"], api_key.strip())

    AppConfig(repo).set_active_provider(values["provider_name"],
                                        values["model"])
    return jsonify({"provider_name": values["provider_name"],
                    "model": values["model"]}), 200


@settings_bp.route("/settings/ai-provider/test", methods=["POST"])
def test_ai_provider():
    """Test whether the provided AI credentials can connect.

    The key in the body is only used for this test. It is not saved.
    If api_key is empty, the key already saved for the provider is used.

    Request body (JSON): provider_name, model, api_key.

    Returns:
        200: {"connected": true} if test_connection() succeeds.
        400: {"error": {"code": "...", "message": "..."}} on failure.
    """
    body = request.get_json(silent=True)
    values = read_text_fields(body, ("provider_name", "model"))
    if values is None:
        return error_response("missing_field",
                              "provider_name and model are required.", 400)
    try:
        client = create_client(values["provider_name"], values["model"])
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
