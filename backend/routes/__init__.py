"""Route blueprints for the Cataloga internal API."""

import os

from flask import current_app, jsonify

# Renamed: the projects route file would replace a name "projects".
from backend.config import projects as project_list
from backend.db.catalog_repository import CatalogRepository


def error_response(code, message, status, extra=None):
    """Build an error response in the shape every endpoint uses."""
    error = {"code": code, "message": message}
    if extra:
        error.update(extra)
    return jsonify({"error": error}), status


def projects_path():
    """Return the path of the project list this app uses."""
    return current_app.config["PROJECTS_PATH"]


def project_status(folder):
    """Say whether a project folder can be used right now."""
    if not folder:
        return "none"
    if not os.path.isfile(project_list.catalog_path(folder)):
        return "unavailable"
    return "ok"


def get_active_repo():
    """Open the catalog of the active project."""
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
