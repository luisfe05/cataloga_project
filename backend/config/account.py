"""Password rules and hashing, and the old one-account file."""

import json
import os

import bcrypt

# The file of the versions with one account per computer. See accounts.py.
ACCOUNT_FILE = "account.json"

# bcrypt reads only 72 bytes, so longer passwords are refused, not cut.
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_BYTES = 72

# bcrypt cost: each +1 doubles the time. Tests lower it.
BCRYPT_ROUNDS = 12


def account_path_for(projects_path):
    """Return the path of the old account.json next to a projects.json."""
    return os.path.join(os.path.dirname(projects_path), ACCOUNT_FILE)


def load_account(path):
    """Read the old one-account file."""
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


def save_account(path, username, password):
    """Write an old-style account file. Only tests use it now."""
    data = {"username": username, "password_hash": hash_password(password)}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary_path = path + ".tmp"
    with open(temporary_path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)
    os.replace(temporary_path, path)


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


def password_matches(password, password_hash):
    """Say whether a password matches a saved hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"),
                              password_hash.encode("utf-8"))
    except ValueError:
        # A password over 72 bytes, or a damaged hash.
        return False
