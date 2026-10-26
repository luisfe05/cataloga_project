"""Dashboard routes.

Endpoints:
    GET /dashboard/stats    Return summary counts and recent activity.
"""

from flask import Blueprint, jsonify

from backend.routes import get_active_repo

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard/stats", methods=["GET"])
def get_stats():
    """Return dashboard summary data for the active project.

    Returns:
        200: JSON with documents_classified, needs_manual_review,
             sources_tracked, media_type_breakdown (dict),
             recent_activity (list).
        409: If there is no usable project ('no_project' or
             'project_unavailable').
    """
    repo, error = get_active_repo()
    if error:
        return error
    return jsonify(repo.get_dashboard_stats()), 200
