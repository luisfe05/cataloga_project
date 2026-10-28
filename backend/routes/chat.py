"""Chat route.

Endpoint:
    POST /chat    Answer one chat message with one action from a fixed
                  list. Never changes the catalog or any file.

Works on the active project's catalog. With no project, or when its
folder is not available, it answers 409 like the other routes.
"""

from flask import Blueprint, jsonify, request

from backend.pipeline.ai_providers import create_client
from backend.pipeline.chat_assistant import run_chat
from backend.routes import error_response, get_active_repo

chat_bp = Blueprint("chat", __name__)


@chat_bp.route("/chat", methods=["POST"])
def chat():
    """Answer one message from the chat panel.

    Request body (JSON):
        message (str): What the user wrote.
        history (list, optional): The last messages of the conversation,
            each {"role": "user" or "assistant", "text": str}. The
            backend keeps no history of its own.

    Returns:
        200: JSON with action, reply, notice, sources, documents,
             filters, rename, and project (see chat_assistant.py).
        400: If the body is not a JSON object or message is missing.
        409: If there is no usable project.
    """
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
    provider = repo.get_active_provider()
    client = None
    if provider:
        client = create_client(provider["provider_name"], provider["model"])
    return jsonify(run_chat(repo, client, message.strip(),
                            body.get("history"))), 200
