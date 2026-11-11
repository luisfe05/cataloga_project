"""API keys in the OS keyring, one set per account.

Each key is saved under the service Cataloga/<account>/<provider>, so an
account only reads its own keys. Before Nov 10 every key was saved under
the service "cataloga" with the provider as the name, shared by every
account of the Mac. Those old keys are moved here, never copied twice.
"""

import os

import keyring
from keyring.errors import KeyringError

from backend.config import projects

SERVICE_PREFIX = "Cataloga"

# The service every key used before each account had its own.
LEGACY_SERVICE = "cataloga"

# Old keys an account said are not its own, in its projects.json.
DECLINED_KEY = "legacy_keys_declined"


def account_of(projects_path):
    """The account folder name in users/<account>/projects.json."""
    return os.path.basename(os.path.dirname(projects_path or ""))


def service_name(account, provider):
    """Return the keyring service of one account's key for a provider."""
    # No account gives a name no account ever writes: no key.
    return "{}/{}/{}".format(SERVICE_PREFIX, account or "", provider)


def read_key(account, provider):
    """Return this account's key for a provider, or None."""
    try:
        return keyring.get_password(service_name(account, provider),
                                    provider)
    except KeyringError:
        # A locked or missing keychain reads as no key.
        return None


def save_key(account, provider, key):
    """Save this account's key for a provider. KeyringError goes up."""
    keyring.set_password(service_name(account, provider), provider, key)


def forget_key(account, provider):
    """Remove this account's key for a provider. No entry is not an error."""
    try:
        keyring.delete_password(service_name(account, provider), provider)
    except KeyringError:
        pass


def legacy_key(provider):
    """Return the old shared key of a provider, or None."""
    try:
        return keyring.get_password(LEGACY_SERVICE, provider)
    except KeyringError:
        return None


def forget_legacy_key(provider):
    """Remove the old shared key of a provider, if it is there."""
    try:
        keyring.delete_password(LEGACY_SERVICE, provider)
    except KeyringError:
        pass


def move_legacy_key(account, provider):
    """Give the old shared key to this account. Returns True when moved.

    The account's own key, if it has one, is never replaced. The old key
    is removed only after the new entry is saved.
    """
    key = legacy_key(provider)
    if not key:
        return False
    if not read_key(account, provider):
        try:
            save_key(account, provider, key)
        except KeyringError:
            # Nothing is lost: the old key stays for the next try.
            return False
    forget_legacy_key(provider)
    return True


def move_all_legacy(account, providers):
    """Known owner (the only account of the Mac): move every old key."""
    return [name for name in providers if move_legacy_key(account, name)]


def declined(projects_path):
    """Return the providers whose old key this account said is not its own."""
    saved = projects.load_projects(projects_path).get(DECLINED_KEY)
    return set(saved) if isinstance(saved, list) else set()


def decline(projects_path, provider):
    """Remember that this account will add its own key for a provider."""
    data = projects.load_projects(projects_path)
    names = declined(projects_path) | {provider}
    data[DECLINED_KEY] = sorted(names)
    projects.save_projects(projects_path, data)


def pending_legacy(projects_path, providers):
    """Providers with an old key this account has to answer about.

    Only when the account has no key of its own for that provider and has
    not said "Add my own key" before.
    """
    account = account_of(projects_path)
    skipped = declined(projects_path)
    return [name for name in providers
            if name not in skipped and not read_key(account, name)
            and legacy_key(name)]


def forget_account(account, providers):
    """Delete every key of an account (used when the account is deleted)."""
    for name in providers:
        forget_key(account, name)
