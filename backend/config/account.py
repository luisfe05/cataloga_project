"""The app's local account: one username and password for the whole app."""

import json
import os

import bcrypt

ACCOUNT_FILE = "account.json"

# bcrypt reads only 72 bytes, so longer passwords are refused, not cut.
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_BYTES = 72

# bcrypt cost: each +1 doubles the time. Tests lower it.
BCRYPT_ROUNDS = 12


def account_path_for(projects_path):
    """Return the path of account.json next to a projects.json."""
    return os.path.join(os.path.dirname(projects_path), ACCOUNT_FILE)


def load_account(path):
    """Read the account file."""
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or "username" not in data or \
            "password_hash" not in data:
        return None
    return data


def account_exists(path):
    """Say whether the account was already created."""
    return load_account(path) is not None


def password_problem(password):
    """Check a new password against the rules."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return "password_too_short"
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        return "password_too_long"
    return None


def hash_password(password):
    """Return the bcrypt hash of a password, as text."""
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def save_account(path, username, password):
    """Write the account file with the username and the password's hash."""
    data = {"username": username, "password_hash": hash_password(password)}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Safe write: a temporary file, then replace.
    temporary_path = path + ".tmp"
    with open(temporary_path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)
    os.replace(temporary_path, path)


def check_password(path, password):
    """Say whether a password matches the saved account."""
    account = load_account(path)
    if account is None:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"),
                              account["password_hash"].encode("utf-8"))
    except ValueError:
        # A password over 72 bytes, or a damaged hash.
        return False


def check_login(path, username, password):
    """Say whether a username and password match the saved account."""
    account = load_account(path)
    if account is None or account["username"] != username:
        return False
    return check_password(path, password)


def change_password(path, new_password):
    """Replace the saved password hash, keeping the username."""
    account = load_account(path)
    save_account(path, account["username"], new_password)
