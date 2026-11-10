"""Account and session routes."""

import math
import os
import re
import secrets
import time
from datetime import date

from flask import Blueprint, current_app, jsonify, request

from backend.config import account, ai_settings, projects, recovery
from backend.config.accounts import username_problem
from backend.config.terms import TERMS_VERSION
from backend.routes import error_response, session_user
from backend.routes.settings import status_cache

auth_bp = Blueprint("auth", __name__)

# The app needs these before login.
PUBLIC_PATHS = ("/auth/status", "/auth/register", "/auth/login",
                "/auth/recovery/reset")

# Recordings and small pictures: a player or an <img> cannot send headers,
# so these routes alone take the token in their URL.
MEDIA_PATH = re.compile(r"/documents/\d+/media|/browse/(media|thumb)")

MAX_FAILED_ATTEMPTS = 5
LOCK_SECONDS = 30
# A wrong recovery key waits longer: the key is the last way in.
RESET_LOCK_SECONDS = 300

# A key just shown may be saved to a file without the password, for a while.
SAVE_TICKET_SECONDS = 600


def now():
    """Return the current time in seconds. Tests replace it."""
    return time.time()


def store():
    """Return the AccountStore saved by create_app()."""
    return current_app.config["ACCOUNTS"]


def forget_account_state():
    """Drop what the server keeps in memory for the account that leaves."""
    # The AI status of one account must not show for the next one.
    status_cache.clear()
    current_app.config["SAVE_TICKETS"] = {}
    # A scan reads one account's project: it stops with that account. It
    # can be resumed later; a running batch of the plan is not cut.
    job = current_app.config.get("SCAN")
    if job is not None and job.is_running():
        job.stop()


def start_session(username):
    """Start the only session, replacing any older token."""
    forget_account_state()
    token = secrets.token_urlsafe(32)
    current_app.config["SESSION_TOKEN"] = token
    current_app.config["SESSION_USER"] = username
    store().remember_last(username)
    # Once per account: the AI provider moves out of the projects.
    ai_settings.migrate(store().projects_path(username))
    return token


def has_valid_token():
    """Say whether the request has the current session token."""
    saved = current_app.config.get("SESSION_TOKEN")
    header = request.headers.get("Authorization", "")
    if not saved or not header.startswith("Bearer "):
        return False
    # compare_digest takes the same time either way, so timing reveals nothing.
    return secrets.compare_digest(header[len("Bearer "):], saved)


def has_valid_media_token():
    """A player cannot send headers: recordings take the token in the URL."""
    token = current_app.config.get("SESSION_TOKEN")
    return bool(token and MEDIA_PATH.fullmatch(request.path) and
                secrets.compare_digest(request.args.get("token", ""), token))


def require_login():
    """Refuse any non-public request without a valid token."""
    # The browser sends OPTIONS first to check CORS, without headers.
    if request.method == "OPTIONS" or request.path in PUBLIC_PATHS:
        return None
    if has_valid_token() or has_valid_media_token():
        return None
    return error_response("unauthorized", "Log in to use Cataloga.", 401)


def attempt_key(username):
    """Wrong passwords are counted per username, whatever its case."""
    return (username or "").strip().lower()


def reset_key(username):
    """Wrong recovery keys are counted apart from wrong passwords."""
    return "reset:" + attempt_key(username)


def seconds_locked(username, key=None):
    """Return how many seconds are left before this username may try."""
    key = key or attempt_key(username)
    until = current_app.config["LOCKED_UNTIL"].get(key, 0)
    return max(0, math.ceil(until - now()))


def locked_response(username, key=None):
    """Build the 429 answer for a try during the wait."""
    wait = seconds_locked(username, key)
    return error_response(
        "too_many_attempts",
        "Too many wrong tries. Try again in {} seconds.".format(wait),
        429, extra={"retry_after": wait})


def record_failure(username, key=None, lock_seconds=LOCK_SECONDS):
    """Count one wrong try. The 5th in a row starts the wait."""
    key = key or attempt_key(username)
    failures = current_app.config["FAILED_ATTEMPTS"].get(key, 0) + 1
    if failures >= MAX_FAILED_ATTEMPTS:
        current_app.config["LOCKED_UNTIL"][key] = now() + lock_seconds
        failures = 0
    current_app.config["FAILED_ATTEMPTS"][key] = failures
    return failures == 0


def clear_failures(username, key=None):
    """A right try starts the count again."""
    key = key or attempt_key(username)
    current_app.config["FAILED_ATTEMPTS"].pop(key, None)


def give_new_key(username):
    """Make a new recovery key: hash in the account, key in the Keychain.

    Returns the key and a ticket that lets the screen save it to a file
    once, without asking for the password again.
    """
    key = recovery.new_key()
    recovery.keep_in_keychain(username, key)
    store().set_recovery_key(username, key)
    return key, save_ticket(username)


def save_ticket(username):
    """A one-time ticket to save this account's key to a file."""
    ticket = secrets.token_urlsafe(16)
    tickets = current_app.config.setdefault("SAVE_TICKETS", {})
    tickets[ticket] = (username, now() + SAVE_TICKET_SECONDS)
    return ticket


def use_ticket(ticket, username):
    """Say whether a ticket is valid for this account, and spend it."""
    tickets = current_app.config.setdefault("SAVE_TICKETS", {})
    saved = tickets.pop(ticket, None) if isinstance(ticket, str) else None
    return bool(saved and saved[0].lower() == username.lower() and
                saved[1] > now())


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
        "terms_version": TERMS_VERSION,
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
    # The account is made only after the Terms and Privacy are accepted.
    if request.get_json(silent=True).get("accepted_terms") != TERMS_VERSION:
        return error_response("terms_not_accepted",
                              "Accept the Terms and Privacy Policy first.",
                              400)
    try:
        store().create(username, password)
    except ValueError:
        return error_response("username_taken",
                              "That username is taken.", 409)
    store().accept_terms(username, TERMS_VERSION)
    token = start_session(username)
    key, ticket = give_new_key(username)
    # The key is shown once here; later it needs the password.
    return jsonify({"token": token, "username": username,
                    "recovery_key": key, "save_ticket": ticket}), 201


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
    return jsonify({"token": start_session(saved), "username": saved,
                    "terms_ok": store().terms_version(saved) ==
                    TERMS_VERSION}), 200


@auth_bp.route("/auth/logout", methods=["POST"])
def logout():
    """End the session. The old token stops working."""
    forget_account_state()
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


@auth_bp.route("/auth/terms", methods=["POST"])
def accept_terms():
    """Accept a new version of the terms, after a login that asked for it."""
    body = request.get_json(silent=True)
    version = body.get("version") if isinstance(body, dict) else None
    if version != TERMS_VERSION:
        return error_response("terms_not_accepted",
                              "Accept the current Terms and Privacy Policy.",
                              400)
    store().accept_terms(session_user(), TERMS_VERSION)
    return jsonify({"version": TERMS_VERSION}), 200


@auth_bp.route("/auth/recovery", methods=["GET"])
def recovery_status():
    """Say whether the recovery key was saved to a file, and when."""
    return jsonify({"saved": store().recovery_saved(session_user())}), 200


def checked_password(username, body):
    """Return an error answer when the password is missing or wrong."""
    if seconds_locked(username):
        return locked_response(username)
    password = body.get("password") if isinstance(body, dict) else None
    if not isinstance(password, str) or not password:
        return error_response("missing_field", "password is required.", 400)
    if not store().check_password(username, password):
        if record_failure(username):
            return locked_response(username)
        return error_response("wrong_password",
                              "The current password is wrong.", 400)
    clear_failures(username)
    return None


@auth_bp.route("/auth/recovery/key", methods=["POST"])
def recovery_key():
    """Show the key again, or make a new one. Both need the password."""
    username = session_user()
    body = request.get_json(silent=True)
    problem = checked_password(username, body)
    if problem:
        return problem
    key = recovery.read_from_keychain(username)
    if body.get("new") is True or not key:
        # A new key: the old one stops working at once.
        key, ticket = give_new_key(username)
    else:
        ticket = save_ticket(username)
    return jsonify({"recovery_key": key, "save_ticket": ticket}), 200


@auth_bp.route("/auth/recovery/save", methods=["POST"])
def save_recovery_file():
    """Write the key to the file chosen in the Save window."""
    username = session_user()
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        body = {}
    path = body.get("path")
    if not isinstance(path, str) or not os.path.isabs(path):
        return error_response("missing_field", "path is required.", 400)
    # The key must never land inside a project: projects get shared.
    folders = [p["folder"] for p in projects.load_projects(
        store().projects_path(username))["projects"]]
    if recovery.inside_any(path, folders):
        return error_response(
            "inside_project",
            "Choose a folder outside your projects for the key.", 400)
    if not use_ticket(body.get("ticket"), username):
        return error_response("ticket_expired",
                              "Type your password to save the key.", 403)
    key = recovery.read_from_keychain(username)
    if not key:
        return error_response("no_key", "There is no recovery key.", 409)
    day = date.today().isoformat()
    with open(path, "w", encoding="utf-8") as file:
        file.write(recovery.file_text(username, key, day))
    store().mark_recovery_saved(username, day)
    return jsonify({"saved": day}), 200


@auth_bp.route("/auth/recovery/reset", methods=["POST"])
def reset_password():
    """Public. A new password with the username and the recovery key."""
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        body = {}
    username = body.get("username")
    username = username.strip() if isinstance(username, str) else ""
    key = body.get("recovery_key")
    new = body.get("new_password")
    lock = reset_key(username)
    if seconds_locked(username, lock):
        return locked_response(username, lock)
    if not username or not isinstance(key, str) or not key or \
            not isinstance(new, str) or not new:
        return error_response(
            "missing_field",
            "username, recovery_key and new_password are required.", 400)
    # One answer for both mistakes: it never says which one is wrong.
    if not store().recovery_key_matches(username, key):
        if record_failure(username, lock, RESET_LOCK_SECONDS):
            return locked_response(username, lock)
        return error_response("wrong_recovery",
                              "Username or recovery key is wrong.", 400)
    problem = account.password_problem(new)
    if problem:
        return error_response(problem, "The new password does not "
                              "follow the rules.", 400)
    clear_failures(username, lock)
    saved = store().find(username)["username"]
    store().change_password(saved, new)
    token = start_session(saved)
    new_key, ticket = give_new_key(saved)
    return jsonify({"token": token, "username": saved,
                    "recovery_key": new_key, "save_ticket": ticket,
                    "terms_ok": store().terms_version(saved) ==
                    TERMS_VERSION}), 200
