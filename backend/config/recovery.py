"""Recovery keys: the second way into an account when the password is lost.

The account keeps a bcrypt hash of the key, to check it. The key itself is
kept in the Keychain, so the same key can be shown again after the user
types the password. It is never written to a plain file except the one the
user chooses in the Save window.
"""

import os
import secrets
from datetime import date

import keyring
from keyring.errors import KeyringError

from backend.config import account

# No 0, O, 1 or I: they are easy to mix up when typed by hand.
KEY_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
GROUPS = 4
GROUP_LENGTH = 4

# Keychain service for the keys; the API keys use "cataloga".
KEYCHAIN_SERVICE = "cataloga-recovery"

FILE_NAME = "Cataloga Recovery Key - {}.txt"

FILE_TEXT = """Cataloga recovery key

Username: {username}
Recovery key: {key}
Saved on: {day}

How to use it:
1. On the Cataloga login screen, click "Forgot your password?".
2. Type your username and this recovery key.
3. Choose a new password.

After the reset you get a new recovery key, and this one stops working.
Keep this file somewhere safe, outside your project folders.
"""


def new_key():
    """Return a new random key like 7K2Q-M9XP-4TWD-HBRS."""
    groups = []
    for _ in range(GROUPS):
        groups.append("".join(secrets.choice(KEY_LETTERS)
                              for _ in range(GROUP_LENGTH)))
    return "-".join(groups)


def clean_key(text):
    """Read a typed key: any case, with or without dashes and spaces."""
    if not isinstance(text, str):
        return ""
    letters = "".join(c for c in text.upper() if c.isalnum())
    if len(letters) != GROUPS * GROUP_LENGTH:
        return ""
    return "-".join(letters[i:i + GROUP_LENGTH]
                    for i in range(0, len(letters), GROUP_LENGTH))


def hash_key(key):
    """Return the bcrypt hash of a key, as text."""
    return account.hash_password(clean_key(key))


def key_matches(key, key_hash):
    """Say whether a typed key matches the saved hash."""
    key = clean_key(key)
    if not key or not key_hash:
        return False
    return account.password_matches(key, key_hash)


def keychain_name(username):
    """One Keychain entry per account, whatever the case of the name."""
    return username.strip().lower()


def keep_in_keychain(username, key):
    """Save the key in the Keychain, replacing the old one."""
    keyring.set_password(KEYCHAIN_SERVICE, keychain_name(username), key)


def read_from_keychain(username):
    """Return the key saved in the Keychain, or ''."""
    return keyring.get_password(KEYCHAIN_SERVICE,
                                keychain_name(username)) or ""


def forget_keychain(username):
    """Remove the key from the Keychain. No entry is not an error."""
    try:
        keyring.delete_password(KEYCHAIN_SERVICE, keychain_name(username))
    except KeyringError:
        pass


def file_text(username, key, day=None):
    """The text of the saved file: username, key, date and the steps."""
    day = day or date.today().isoformat()
    return FILE_TEXT.format(username=username, key=key, day=day)


def inside_any(path, folders):
    """Say whether a path is inside one of these folders (or is one)."""
    target = os.path.realpath(path)
    for folder in folders:
        if not folder:
            continue
        root = os.path.realpath(folder)
        try:
            if os.path.commonpath([root, target]) == root:
                return True
        except ValueError:
            # Different drives: not inside.
            continue
    return False
