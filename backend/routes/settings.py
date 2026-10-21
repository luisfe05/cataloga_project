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

from flask import Blueprint, jsonify, request

settings_bp = Blueprint("settings", __name__)


@settings_bp.route("/settings", methods=["GET"])
def get_settings():
    """Return current research and AI provider settings.

    Returns:
        200: JSON with research_name, target_directory, active provider, model.
             API key is never returned.
    """
    pass


@settings_bp.route("/settings", methods=["PUT"])
def update_settings():
    """Update research_name and/or target_directory.

    Request body (JSON): research_name, target_directory.

    Returns:
        200: JSON of updated settings.
    """
    pass


@settings_bp.route("/settings/ai-provider", methods=["PUT"])
def update_ai_provider():
    """Update the active AI provider, model, and API key.

    The API key is written to the OS keyring and never stored in the database
    or returned in any response.

    Request body (JSON): provider_name, model, api_key.

    Returns:
        200: OK (no key echoed back).
    """
    pass


@settings_bp.route("/settings/ai-provider/test", methods=["POST"])
def test_ai_provider():
    """Test whether the provided AI credentials can connect.

    Request body (JSON): provider_name, model, api_key.

    Returns:
        200: {"connected": true} if test_connection() succeeds.
        400: {"error": {"code": "...", "message": "..."}} on failure.
    """
    pass
