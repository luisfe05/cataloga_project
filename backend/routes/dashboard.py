"""Dashboard routes.

Endpoints:
    GET /dashboard/stats    Return summary counts and recent activity.
"""

from flask import Blueprint, jsonify

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard/stats", methods=["GET"])
def get_stats():
    """Return dashboard summary data.

    Returns:
        200: JSON with documents_classified, needs_manual_review,
             sources_tracked, media_type_breakdown (dict), recent_activity (list).
    """
    pass
