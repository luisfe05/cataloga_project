"""Account and session routes."""

import math
import secrets
import time

from flask import Blueprint, current_app, jsonify, request

from backend.config import account
from backend.config import projects
from backend.routes import error_response, projects_path

auth_bp = Blueprint("auth", __name__)

# The app needs these before login.
PUBLIC_PATHS = ("/auth/status", "/auth/setup", "/auth/login")

MAX_FAILED_ATTEMPTS = 5
LOCK_SECONDS = 30


def now():
    """Return the current time in seconds. Tests replace it."""
    return time.time()


def account_path():
    """Return the path of account.json, saved by create_app()."""
    return current_app.config["ACCOUNT_PATH"]


def start_session():
    """Start the only session, replacing any older token."""
    token = secrets.token_urlsafe(32)
    current_app.config["SESSION_TOKEN"] = token
    return token


def has_valid_token():
    """Say whether the request has the current session token."""
    saved = current_app.config.get("SESSION_TOKEN")
    header = request.headers.get("Authorization", "")
    if not saved or not header.startswith("Bearer "):
        return False
    # compare_digest takes the same time either way, so timing reveals nothing.
    return secrets.compare_digest(header[len("Bearer "):], saved)


def require_login():
    """Refuse any non-public request without a valid token."""
    # The browser sends OPTIONS first to check CORS, without headers.
    if request.method == "OPTIONS" or request.path in PUBLIC_PATHS:
        return None
    if has_valid_token():
        return None
    return error_response("unauthorized", "Log in to use Cataloga.", 401)


def seconds_locked():
    """Return how many seconds are left before a new try is allowed."""
    left = current_app.config.get("LOCKED_UNTIL", 0) - now()
    return max(0, math.ceil(left))


def locked_response():
    """Build the 429 answer for a try during the wait."""
    wait = seconds_locked()
    return error_response(
        "too_many_attempts",
        "Too many wrong passwords. Try again in {} seconds.".format(wait),
        429, extra={"retry_after": wait})


def record_failure():
    """Count one wrong password. The 5th in a row starts the wait."""
    failures = current_app.config.get("FAILED_ATTEMPTS", 0) + 1
    if failures >= MAX_FAILED_ATTEMPTS:
        current_app.config["LOCKED_UNTIL"] = now() + LOCK_SECONDS
        failures = 0
    current_app.config["FAILED_ATTEMPTS"] = failures
    return failures == 0


def read_credentials(body):
    """Return the stripped username and the password from a body."""
    if not isinstance(body, dict):
        return "", ""
    username = body.get("username")
    password = body.get("password")
    username = username.strip() if isinstance(username, str) else ""
    password = password if isinstance(password, str) else ""
    return username, password


@auth_bp.route("/auth/status", methods=["GET"])
def auth_status():
    """Say which screen to show first, and in which language."""
    return jsonify({
        "account_exists": account.account_exists(account_path()),
        "language": projects.load_projects(projects_path())["language"],
    }), 200


@auth_bp.route("/auth/setup", methods=["POST"])
def setup_account():
    """Create the app's account. Only works while there is none."""
    if account.account_exists(account_path()):
        return error_response("account_exists",
                              "The account already exists.", 409)
    username, password = read_credentials(request.get_json(silent=True))
    if not username or not password:
        return error_response("missing_field",
                              "username and password are required.", 400)
    problem = account.password_problem(password)
    if problem:
        return error_response(problem, "The password does not follow "
                              "the rules.", 400)
    account.save_account(account_path(), username, password)
    return jsonify({"token": start_session(), "username": username}), 201


@auth_bp.route("/auth/login", methods=["POST"])
def login():
    """Check the username and password and start a session."""
    if seconds_locked():
        return locked_response()
    if not account.account_exists(account_path()):
        return error_response("no_account",
                              "Create the account first.", 409)
    username, password = read_credentials(request.get_json(silent=True))
    if not username or not password:
        return error_response("missing_field",
                              "username and password are required.", 400)
    if not account.check_login(account_path(), username, password):
        if record_failure():
            return locked_response()
        return error_response("wrong_login",
                              "The username or password is wrong.", 401)
    current_app.config["FAILED_ATTEMPTS"] = 0
    return jsonify({"token": start_session(), "username": username}), 200


@auth_bp.route("/auth/logout", methods=["POST"])
def logout():
    """End the session. The old token stops working."""
    current_app.config["SESSION_TOKEN"] = None
    return jsonify({"logged_out": True}), 200


@auth_bp.route("/auth/password", methods=["POST"])
def update_password():
    """Change the password. The current session stays open."""
    if seconds_locked():
        return locked_response()
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        body = {}
    current = body.get("current_password")
    new = body.get("new_password")
    if not isinstance(current, str) or not current or \
            not isinstance(new, str) or not new:
        return error_response(
            "missing_field",
            "current_password and new_password are required.", 400)
    if not account.check_password(account_path(), current):
        if record_failure():
            return locked_response()
        # 400, not 401: a 401 would send the screen back to the login.
        return error_response("wrong_password",
                              "The current password is wrong.", 400)
    current_app.config["FAILED_ATTEMPTS"] = 0
    problem = account.password_problem(new)
    if problem:
        return error_response(problem, "The new password does not "
                              "follow the rules.", 400)
    account.change_password(account_path(), new)
    return jsonify({"changed": True}), 200
