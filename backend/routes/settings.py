"""Settings routes.

Endpoints:
    GET  /settings                      Return current app config.
    PUT  /settings                      Update research_name,
                                        target_directory, and language.
    PUT  /settings/ai-provider          Update provider and model,
                                        write API key to keyring.
    POST /settings/ai-provider/test     Test whether the provider
                                        config connects.
"""

import os

from flask import Blueprint, jsonify, request

from backend.config.app_config import LANGUAGES, AppConfig
from backend.folder_watcher import old_inbox_has_files
from backend.pipeline.ai_providers import PROVIDERS, create_client
from backend.pipeline.ai_providers.base import save_api_key
from backend.pipeline.file_organizer import FileOrganizer
from backend.routes import error_response, get_repo

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
    """Return current research and AI provider settings.

    Returns:
        200: JSON with research_name, target_directory, active provider,
             model, and old_inbox_has_files (True when an old Inbox
             folder still has files next to Drop Zone). API key is never
             returned.
    """
    settings = AppConfig(get_repo()).get_settings()
    settings["old_inbox_has_files"] = False
    if settings["target_directory"]:
        organizer = FileOrganizer(settings["target_directory"])
        settings["old_inbox_has_files"] = old_inbox_has_files(organizer)
    return jsonify(settings), 200


def save_language_only(body):
    """Save the language when it is the only field in the request.

    Settings saves the language as soon as the user picks it, even
    before a project folder exists.

    Args:
        body (dict): The parsed JSON body, with only 'language'.

    Returns:
        tuple: A Flask response and status code.
    """
    config = AppConfig(get_repo())
    try:
        config.update_language(body["language"])
    except ValueError as error:
        return error_response("invalid_language", str(error), 400)
    return jsonify(config.get_settings()), 200


@settings_bp.route("/settings", methods=["PUT"])
def update_settings():
    """Update research_name, target_directory, and language.

    The folder must already exist (for example, an external drive must
    be connected). Drop Zone and the five media-type folders are created
    inside it. When the same folder is saved again, an old Inbox folder
    is first renamed to Drop Zone.

    If the user picks a new folder that already has their own files, the
    first request is answered with 409 and a warning. The frontend sends
    the same request again with confirm_folder set to true once the user
    agrees. Existing files are never moved either way: only Drop Zone
    is processed.

    A body with only 'language' saves just the language.

    Request body (JSON): research_name, target_directory, and optional
                         confirm_folder (bool) and language ('en' or
                         'es').

    Returns:
        200: JSON of updated settings.
        400: If a field is missing, the folder does not exist, or the
             language is not supported.
        409: If a new folder has content and was not confirmed yet. The
             error includes 'count', the number of items found.
    """
    body = request.get_json(silent=True)
    if isinstance(body, dict) and list(body) == ["language"]:
        return save_language_only(body)

    values = read_text_fields(body, ("research_name", "target_directory"))
    if values is None:
        return error_response(
            "missing_field",
            "research_name and target_directory are required.", 400)
    # Checked before any folder is created, so a bad request changes
    # nothing.
    if "language" in body and body["language"] not in LANGUAGES:
        return error_response(
            "invalid_language",
            "language must be one of: " + ", ".join(LANGUAGES), 400)

    # expanduser turns "~/Documents" into "/Users/<name>/Documents".
    values["target_directory"] = os.path.expanduser(
        values["target_directory"])
    if not os.path.isdir(values["target_directory"]):
        return error_response(
            "invalid_directory",
            "The folder does not exist: " + values["target_directory"], 400)

    config = AppConfig(get_repo())
    organizer = FileOrganizer(values["target_directory"])
    is_new_folder = (values["target_directory"] !=
                     config.get_settings()["target_directory"])
    existing = organizer.count_existing_items()
    if is_new_folder and existing and body.get("confirm_folder") is not True:
        return error_response(
            "folder_not_empty",
            "This folder already has {} items. Cataloga will not move them: "
            "only files you drop into its Drop Zone folder are cataloged. "
            "Click Save anyway to use this folder.".format(existing), 409,
            extra={"count": existing})

    # The migration must run before ensure_archive_structure(), which
    # would otherwise create an empty Drop Zone next to the old Inbox.
    if not is_new_folder:
        organizer.migrate_old_inbox()
    organizer.ensure_archive_structure()
    if "language" in body:
        config.update_language(body["language"])
    config.update_settings(values["research_name"],
                           values["target_directory"])
    return jsonify(config.get_settings()), 200


@settings_bp.route("/settings/ai-provider", methods=["PUT"])
def update_ai_provider():
    """Update the active AI provider, model, and API key.

    The API key is written to the OS keyring and never stored in the
    database or returned in any response. If api_key is empty, the key
    already saved for that provider is kept.

    Request body (JSON): provider_name, model, api_key.

    Returns:
        200: The active provider and model (no key echoed back).
        400: If a field is missing or the provider is not supported.
    """
    body = request.get_json(silent=True)
    values = read_text_fields(body, ("provider_name", "model"))
    if values is None:
        return error_response("missing_field",
                              "provider_name and model are required.", 400)
    if values["provider_name"] not in PROVIDERS:
        return error_response(
            "unsupported_provider",
            "Unsupported AI provider: " + values["provider_name"], 400)

    api_key = body.get("api_key")
    if isinstance(api_key, str) and api_key.strip():
        save_api_key(values["provider_name"], api_key.strip())

    AppConfig(get_repo()).set_active_provider(values["provider_name"],
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
