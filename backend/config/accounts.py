"""AccountStore: the accounts of this computer, each with its own projects."""

import json
import os
import re
import shutil
from datetime import datetime

from backend.config import account

ACCOUNTS_FILE = "accounts.json"

# One folder per account, with its projects.json inside.
USERS_FOLDER = "users"
PROJECTS_FILE = "projects.json"

# Letters, digits, dots, underscores and hyphens; 3 to 30 characters.
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{3,30}$")


def now_timestamp():
    """Return the current time as an ISO string, e.g. 2026-10-29T10:00:00."""
    return datetime.now().isoformat(timespec="seconds")


def username_problem(username):
    """Return why a new username is not allowed, or None."""
    if not USERNAME_PATTERN.match(username or ""):
        return "invalid_username"
    return None


def folder_name(username):
    """Turn a username into a safe folder name: 'Luis G' becomes 'luis_g'."""
    return re.sub(r"[^a-z0-9._-]", "_", username.lower())


class AccountStore:
    """The accounts file and the per-account folders in the data folder.

    A later version can keep the accounts on a server with these same
    methods; the screens and the routes would not change.
    """

    def __init__(self, data_folder):
        """Use the app data folder: accounts.json and users/ live there."""
        self.data_folder = data_folder
        self.path = os.path.join(data_folder, ACCOUNTS_FILE)

    def load(self):
        """Read the accounts file."""
        data = {"accounts": [], "last_username": ""}
        if not os.path.isfile(self.path):
            return data
        try:
            with open(self.path, encoding="utf-8") as file:
                saved = json.load(file)
        except (OSError, ValueError):
            return data
        if isinstance(saved, dict):
            data.update(saved)
        return data

    def save(self, data):
        """Write the accounts file (a temporary file, then replace)."""
        os.makedirs(self.data_folder, exist_ok=True)
        temporary_path = self.path + ".tmp"
        with open(temporary_path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
        os.replace(temporary_path, self.path)

    def usernames(self):
        """Return every username, in the order the accounts were made."""
        return [entry["username"] for entry in self.load()["accounts"]]

    def find(self, username):
        """Return the account with this username (any case), or None."""
        wanted = (username or "").strip().lower()
        for entry in self.load()["accounts"]:
            if entry["username"].lower() == wanted:
                return entry
        return None

    def projects_path(self, username):
        """Return the path of this account's project list."""
        return os.path.join(self.data_folder, USERS_FOLDER,
                            folder_name(username), PROJECTS_FILE)

    def create(self, username, password):
        """Add an account. Raises ValueError with the problem's code."""
        username = username.strip()
        if username_problem(username):
            raise ValueError("invalid_username")
        if self.find(username):
            raise ValueError("username_taken")
        data = self.load()
        data["accounts"].append({
            "username": username,
            "password_hash": account.hash_password(password),
            "created": now_timestamp(),
        })
        data["last_username"] = username
        self.save(data)
        return username

    def check_password(self, username, password):
        """Say whether the password matches this account's hash."""
        entry = self.find(username)
        if entry is None:
            return False
        return account.password_matches(password, entry["password_hash"])

    def change_password(self, username, new_password):
        """Replace the saved hash of this account."""
        data = self.load()
        for entry in data["accounts"]:
            if entry["username"].lower() == username.lower():
                entry["password_hash"] = account.hash_password(new_password)
        self.save(data)

    def remember_last(self, username):
        """Save who logged in last; the login screen uses their language."""
        data = self.load()
        data["last_username"] = username
        self.save(data)

    def last_username(self):
        """Return the account that logged in last, or ''."""
        return self.load()["last_username"] or ""

    def migrate_single_account(self, old_account_path, old_projects_path):
        """Turn the old one-account files into the first account. Once."""
        if os.path.isfile(self.path):
            return False
        old = account.load_account(old_account_path)
        if old is None:
            return False
        username = old["username"]
        new_projects_path = self.projects_path(username)
        if os.path.isfile(old_projects_path) and \
                not os.path.exists(new_projects_path):
            os.makedirs(os.path.dirname(new_projects_path), exist_ok=True)
            # The project list keeps its projects and its language.
            shutil.move(old_projects_path, new_projects_path)
        self.save({
            "accounts": [{"username": username,
                          "password_hash": old["password_hash"],
                          "created": now_timestamp()}],
            "last_username": username,
        })
        # Kept as a backup; the app never reads it again.
        os.replace(old_account_path, old_account_path + ".migrated")
        return True
