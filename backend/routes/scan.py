"""Scan routes: reading a project folder in place."""

from flask import Blueprint, current_app, jsonify

from backend import scanner
from backend.config import projects as project_list
from backend.routes import (error_response, get_active_repo, projects_path,
                            session_user)

scan_bp = Blueprint("scan", __name__)


def current_job():
    """Return the app's scan job, making an idle one the first time."""
    return current_app.config.setdefault("SCAN", scanner.ScanJob())


@scan_bp.route("/scan", methods=["GET"])
def scan_status():
    """Say how far the scan is, and how many files Retry would read."""
    repo, error = get_active_repo()
    if error:
        return jsonify(dict(current_job().to_dict(), retryable=0)), 200
    folder = project_list.active_folder(projects_path())
    state = scanner.scan_view(current_job(), repo, folder)
    state["retryable"] = len(scanner.retryable_documents(repo))
    return jsonify(state), 200


@scan_bp.route("/scan/start", methods=["POST"])
def scan_start():
    """Read the active project's folder in place, with its subfolders."""
    repo, error = get_active_repo()
    if error:
        return error
    if not repo.reads_in_place():
        return error_response(
            "has_drop_zone",
            "This project reads its Drop Zone; nothing to scan.", 409)
    # One scan at a time: another project may be the one being read.
    if current_job().is_running() and current_job().folder != \
            project_list.active_folder(projects_path()):
        return error_response("scan_running",
                              "Another folder is being read.", 409)
    job = scanner.start_scan(current_app._get_current_object(),
                             projects_path(), session_user() or None)
    if job.error == "no_provider":
        return error_response("no_provider",
                              "Choose an AI provider first.", 400)
    return jsonify(job.to_dict()), 202


@scan_bp.route("/scan/retry", methods=["POST"])
def scan_retry():
    """Read again only the files that timed out or could not be read."""
    repo, error = get_active_repo()
    if error:
        return error
    if not repo.reads_in_place():
        return error_response(
            "has_drop_zone",
            "This project reads its Drop Zone; nothing to scan.", 409)
    if current_job().is_running():
        return error_response("scan_running",
                              "The folder is being read already.", 409)
    if repo.get_active_provider() is None:
        return error_response("no_provider",
                              "Choose an AI provider first.", 400)
    count = scanner.forget_retryable(repo)
    job = scanner.start_scan(current_app._get_current_object(),
                             projects_path(), session_user() or None)
    return jsonify(dict(job.to_dict(), retried=count)), 202


@scan_bp.route("/scan/pause", methods=["POST"])
def scan_pause():
    """Hold the scan before its next file."""
    job = current_job()
    job.pause()
    return jsonify(job.to_dict()), 200


@scan_bp.route("/scan/resume", methods=["POST"])
def scan_resume():
    """Let a paused scan go on."""
    job = current_job()
    job.resume()
    return jsonify(job.to_dict()), 200
