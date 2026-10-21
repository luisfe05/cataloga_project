"""Settings routes.

Endpoints:
    GET  /settings                      Return current app config.
    PUT  /settings                      Update research_name and
                                        target_directory.
    PUT  /settings/ai-provider          Update provider and model,
                                        write API key to keyring.
    POST /settings/ai-provider/test     Test whether the provider
                                        config connects.
"""

import os

from flask import Blueprint, jsonify, request

from backend.config.app_config import AppConfig
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
             model. API key is never returned.
    """
    return jsonify(AppConfig(get_repo()).get_settings()), 200


@settings_bp.route("/settings", methods=["PUT"])
def update_settings():
    """Update research_name and target_directory.

    The folder must already exist (for example, an external drive must
    be connected). The five media-type folders are created inside it.

    Request body (JSON): research_name, target_directory.

    Returns:
        200: JSON of updated settings.
        400: If a field is missing or the folder does not exist.
    """
    values = read_text_fields(request.get_json(silent=True),
                              ("research_name", "target_directory"))
    if values is None:
        return error_response(
            "missing_field",
            "research_name and target_directory are required.", 400)

    # expanduser turns "~/Documents" into "/Users/<name>/Documents".
    values["target_directory"] = os.path.expanduser(
        values["target_directory"])
    if not os.path.isdir(values["target_directory"]):
        return error_response(
            "invalid_directory",
            "The folder does not exist: " + values["target_directory"], 400)

    FileOrganizer(values["target_directory"]).ensure_archive_structure()
    config = AppConfig(get_repo())
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
