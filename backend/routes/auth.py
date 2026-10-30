"""Account and session routes."""

import math
import secrets
import time

from flask import Blueprint, current_app, jsonify, request

from backend.config import account, projects
from backend.config.accounts import username_problem
from backend.routes import error_response, session_user

auth_bp = Blueprint("auth", __name__)

# The app needs these before login.
PUBLIC_PATHS = ("/auth/status", "/auth/register", "/auth/login")

MAX_FAILED_ATTEMPTS = 5
LOCK_SECONDS = 30


def now():
    """Return the current time in seconds. Tests replace it."""
    return time.time()


def store():
    """Return the AccountStore saved by create_app()."""
    return current_app.config["ACCOUNTS"]


def start_session(username):
    """Start the only session, replacing any older token."""
    token = secrets.token_urlsafe(32)
    current_app.config["SESSION_TOKEN"] = token
    current_app.config["SESSION_USER"] = username
    store().remember_last(username)
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


def attempt_key(username):
    """Wrong passwords are counted per username, whatever its case."""
    return (username or "").strip().lower()


def seconds_locked(username):
    """Return how many seconds are left before this username may try."""
    until = current_app.config["LOCKED_UNTIL"].get(attempt_key(username), 0)
    return max(0, math.ceil(until - now()))


def locked_response(username):
    """Build the 429 answer for a try during the wait."""
    wait = seconds_locked(username)
    return error_response(
        "too_many_attempts",
        "Too many wrong passwords. Try again in {} seconds.".format(wait),
        429, extra={"retry_after": wait})


def record_failure(username):
    """Count one wrong password. The 5th in a row starts the wait."""
    key = attempt_key(username)
    failures = current_app.config["FAILED_ATTEMPTS"].get(key, 0) + 1
    if failures >= MAX_FAILED_ATTEMPTS:
        current_app.config["LOCKED_UNTIL"][key] = now() + LOCK_SECONDS
        failures = 0
    current_app.config["FAILED_ATTEMPTS"][key] = failures
    return failures == 0


def clear_failures(username):
    """A right password starts the count again."""
    current_app.config["FAILED_ATTEMPTS"].pop(attempt_key(username), None)


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
    """Say whether any account exists, and the last account's language."""
    last = store().last_username()
    language = projects.DEFAULT_LANGUAGE
    if last:
        language = projects.load_projects(
            store().projects_path(last))["language"]
    return jsonify({
        "account_exists": bool(store().usernames()),
        "language": language,
    }), 200


@auth_bp.route("/auth/register", methods=["POST"])
def register_account():
    """Create an account on this computer and log it in."""
    username, password = read_credentials(request.get_json(silent=True))
    if not username or not password:
        return error_response("missing_field",
                              "username and password are required.", 400)
    if username_problem(username):
        return error_response(
            "invalid_username",
            "Use 3 to 30 letters, digits, dots, underscores or hyphens.", 400)
    problem = account.password_problem(password)
    if problem:
        return error_response(problem, "The password does not follow "
                              "the rules.", 400)
    try:
        store().create(username, password)
    except ValueError:
        return error_response("username_taken",
                              "That username is taken.", 409)
    return jsonify({"token": start_session(username),
                    "username": username}), 201


@auth_bp.route("/auth/login", methods=["POST"])
def login():
    """Check the username and password and start a session."""
    username, password = read_credentials(request.get_json(silent=True))
    if seconds_locked(username):
        return locked_response(username)
    if not username or not password:
        return error_response("missing_field",
                              "username and password are required.", 400)
    # An unknown username gets the same answer as a wrong password.
    if not store().check_password(username, password):
        if record_failure(username):
            return locked_response(username)
        return error_response("wrong_login",
                              "The username or password is wrong.", 401)
    clear_failures(username)
    # The session uses the username as it was written when it was created.
    saved = store().find(username)["username"]
    return jsonify({"token": start_session(saved), "username": saved}), 200


@auth_bp.route("/auth/logout", methods=["POST"])
def logout():
    """End the session. The old token stops working."""
    current_app.config["SESSION_TOKEN"] = None
    current_app.config["SESSION_USER"] = None
    return jsonify({"logged_out": True}), 200


@auth_bp.route("/auth/password", methods=["POST"])
def update_password():
    """Change the password. The current session stays open."""
    username = session_user()
    if seconds_locked(username):
        return locked_response(username)
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
    if not store().check_password(username, current):
        if record_failure(username):
            return locked_response(username)
        # 400, not 401: a 401 would send the screen back to the login.
        return error_response("wrong_password",
                              "The current password is wrong.", 400)
    clear_failures(username)
    problem = account.password_problem(new)
    if problem:
        return error_response(problem, "The new password does not "
                              "follow the rules.", 400)
    store().change_password(username, new)
    return jsonify({"changed": True}), 200
