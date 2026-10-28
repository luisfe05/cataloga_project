"""Dashboard routes."""

from flask import Blueprint, jsonify

from backend.routes import get_active_repo

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard/stats", methods=["GET"])
def get_stats():
    """Return dashboard summary data for the active project."""
    repo, error = get_active_repo()
    if error:
        return error
    return jsonify(repo.get_dashboard_stats()), 200
