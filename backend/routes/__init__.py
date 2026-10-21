"""Route blueprints for the Cataloga internal API.

Also holds the small helpers every route file shares.
"""

from flask import current_app, jsonify

from backend.db.catalog_repository import CatalogRepository


def error_response(code, message, status):
    """Build an error response in the shape every endpoint uses.

    Args:
        code (str): Short machine-readable name, e.g. 'not_found'.
        message (str): Explanation for the user.
        status (int): HTTP status code, e.g. 404.

    Returns:
        tuple: (JSON response, status), ready to return from a route.
    """
    return jsonify({"error": {"code": code, "message": message}}), status


def get_repo():
    """Return a CatalogRepository for the database this app uses.

    create_app() saves the database path in app.config, so the real app
    and the tests each get the right database.

    Returns:
        CatalogRepository
    """
    return CatalogRepository(current_app.config["DB_PATH"])
