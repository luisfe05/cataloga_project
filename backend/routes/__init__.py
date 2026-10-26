"""Route blueprints for the Cataloga internal API.

Also holds the small helpers every route file shares.
"""

import os

from flask import current_app, jsonify

# Imported as project_list because backend.routes.projects (the route
# file) would replace a name "projects" in this package.
from backend.config import projects as project_list
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


def projects_path():
    """Return the path of the project list this app uses.

    create_app() saves it in app.config, so the real app and the tests
    each get their own list.

    Returns:
        str: Path to projects.json.
    """
    return current_app.config["PROJECTS_PATH"]


def project_status(folder):
    """Say whether a project folder can be used right now.

    Args:
        folder (str): The active project's folder, or ''.

    Returns:
        str: 'none' (no project), 'unavailable' (folder or catalog
            missing, for example an external drive that is not
            connected), or 'ok'.
    """
    if not folder:
        return "none"
    if not os.path.isfile(project_list.catalog_path(folder)):
        return "unavailable"
    return "ok"


def get_active_repo():
    """Open the catalog of the active project.

    Returns:
        tuple: (CatalogRepository, None) when the project can be used,
            or (None, error response) when there is no project or its
            folder is not available. Routes return that error as is.
    """
    folder = project_list.active_folder(projects_path())
    status = project_status(folder)
    if status == "none":
        return None, error_response(
            "no_project", "There is no open project.", 409)
    if status == "unavailable":
        return None, error_response(
            "project_unavailable",
            "The project folder is not available: " + folder, 409,
            extra={"path": folder})
    return CatalogRepository(project_list.catalog_path(folder)), None
