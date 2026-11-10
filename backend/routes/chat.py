"""Chat route."""

from flask import Blueprint, jsonify, request

from backend.config import ai_settings
from backend.pipeline.ai_providers import text_client
from backend.pipeline.chat_assistant import run_chat
from backend.routes import error_response, get_active_repo, projects_path

chat_bp = Blueprint("chat", __name__)


@chat_bp.route("/chat", methods=["POST"])
def chat():
    """Answer one message from the chat panel."""
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return error_response("invalid_body",
                              "The request body must be a JSON object.", 400)
    message = body.get("message")
    if not isinstance(message, str) or not message.strip():
        return error_response("missing_field", "message is required.", 400)

    repo, error = get_active_repo()
    if error:
        return error
    client = text_client(ai_settings.load(projects_path()))
    return jsonify(run_chat(repo, client, message.strip(),
                            body.get("history"))), 200
