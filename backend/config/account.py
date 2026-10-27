"""The app's local account: one username and password for the whole app.

The account is saved in account.json, in the same folder as
projects.json (Application Support in the packaged app, database/ when
running from the code). It is never saved inside a project folder.

The file only holds the username and a bcrypt hash of the password.
The password itself is never written anywhere. bcrypt adds a random
salt to every hash and is slow on purpose, so a stolen hash is hard to
guess.

The login protects the app, not the files: it does not encrypt the
projects or their catalogs (that is phase 1).

To reset a forgotten password, close the app and delete account.json.
Projects and catalogs are not touched (see the README).
"""

import json
import os

import bcrypt

# Name of the account file, next to projects.json.
ACCOUNT_FILE = "account.json"

# Password rules. bcrypt only reads the first 72 bytes of a password,
# so a longer one is refused instead of being cut without warning.
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_BYTES = 72

# How slow bcrypt is (each +1 doubles the time). 12 is the library's
# default. Tests lower it so they run fast.
BCRYPT_ROUNDS = 12


def account_path_for(projects_path):
    """Return the path of account.json next to a projects.json.

    Args:
        projects_path (str): Path to projects.json.

    Returns:
        str: Path to account.json in the same folder.
    """
    return os.path.join(os.path.dirname(projects_path), ACCOUNT_FILE)


def load_account(path):
    """Read the account file.

    Args:
        path (str): Path to account.json.

    Returns:
        dict or None: {'username', 'password_hash'}, or None if there is
            no account yet (or the file cannot be read).
    """
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
    """Say whether the account was already created.

    Args:
        path (str): Path to account.json.

    Returns:
        bool
    """
    return load_account(path) is not None


def password_problem(password):
    """Check a new password against the rules.

    Args:
        password (str): The password the user typed.

    Returns:
        str or None: 'password_too_short', 'password_too_long', or None
            if the password is fine.
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        return "password_too_short"
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        return "password_too_long"
    return None


def hash_password(password):
    """Return the bcrypt hash of a password, as text.

    Args:
        password (str): The password.

    Returns:
        str: The hash, which includes its own salt.
    """
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def save_account(path, username, password):
    """Write the account file with the username and the password's hash.

    Args:
        path (str): Path to account.json.
        username (str): The username.
        password (str): The password, already checked with
            password_problem(). Only its hash is saved.
    """
    data = {"username": username, "password_hash": hash_password(password)}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Same safe write as projects.json: a temporary file, then replace.
    temporary_path = path + ".tmp"
    with open(temporary_path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)
    os.replace(temporary_path, path)


def check_password(path, password):
    """Say whether a password matches the saved account.

    Args:
        path (str): Path to account.json.
        password (str): The password to check.

    Returns:
        bool: True if it matches. False if not, or if there is no
            account.
    """
    account = load_account(path)
    if account is None:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"),
                              account["password_hash"].encode("utf-8"))
    except ValueError:
        # A password longer than 72 bytes, or a damaged hash.
        return False


def check_login(path, username, password):
    """Say whether a username and password match the saved account.

    Args:
        path (str): Path to account.json.
        username (str): The username typed in the login screen.
        password (str): The password typed in the login screen.

    Returns:
        bool
    """
    account = load_account(path)
    if account is None or account["username"] != username:
        return False
    return check_password(path, password)


def change_password(path, new_password):
    """Replace the saved password hash, keeping the username.

    Args:
        path (str): Path to account.json.
        new_password (str): The new password, already checked.
    """
    account = load_account(path)
    save_account(path, account["username"], new_password)
