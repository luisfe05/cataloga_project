"""Route blueprints for the Cataloga internal API.

Also holds the small helpers every route file shares.
"""

from flask import current_app, jsonify

from backend.db.catalog_repository import CatalogRepository


def error_response(code, message, status, extra=None):
    """Build an error response in the shape every endpoint uses.

    Args:
        code (str): Short machine-readable name, e.g. 'not_found'. The
            frontend uses it to show the error in the user's language.
        message (str): Explanation in English (for logs and tests).
        status (int): HTTP status code, e.g. 404.
        extra (dict, optional): More fields for the error, such as
            {'count': 3}, so the frontend can build its own sentence.

    Returns:
        tuple: (JSON response, status), ready to return from a route.
    """
    error = {"code": code, "message": message}
    if extra:
        error.update(extra)
    return jsonify({"error": error}), status


def get_repo():
    """Return a CatalogRepository for the database this app uses.

    create_app() saves the database path in app.config, so the real app
    and the tests each get the right database.

    Returns:
        CatalogRepository
    """
    return CatalogRepository(current_app.config["DB_PATH"])
