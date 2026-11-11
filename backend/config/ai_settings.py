"""The AI provider of an account: one for every project, like the language.

It lives in users/<username>/projects.json under "ai", next to "language".
API keys are in the keyring, one set per account (backend/config/api_keys).
"""

import os
import sqlite3

from backend.config import api_keys, projects
from backend.db.catalog_repository import CatalogRepository
from backend.pipeline.ai_providers import (DEFAULT_MODEL, DEFAULT_PROVIDER,
                                           ROLES)

AI_KEY = "ai"


def default_ai():
    """Ollama Cloud with gemma4:31b, no fallback, no media, no server."""
    return {"text": {"provider_name": DEFAULT_PROVIDER,
                     "model": DEFAULT_MODEL},
            "fallback": None, "media": None, "server_url": ""}


def from_project(folder):
    """Read what a project saved in its own catalog, or None."""
    db_path = projects.catalog_path(folder)
    if not os.path.isfile(db_path):
        return None
    repo = CatalogRepository(db_path)
    try:
        text = repo.get_provider("text")
        if not text:
            return None
        return {"text": text, "fallback": repo.get_provider("fallback"),
                "media": repo.get_provider("media"),
                "server_url": repo.get_server_url() or ""}
    except sqlite3.Error:
        # A broken or very old catalog is skipped.
        return None


def migrate(path):
    """Once per account: copy the newest project's provider, or the default.

    Returns True when it wrote the settings, False when they existed.
    """
    data = projects.load_projects(path)
    if isinstance(data.get(AI_KEY), dict):
        return False
    ai = None
    # Most recently opened first; the first one with a provider is used.
    for project in sorted(data["projects"],
                          key=lambda item: item.get("last_opened", ""),
                          reverse=True):
        ai = from_project(project["folder"])
        if ai:
            break
    data[AI_KEY] = ai or default_ai()
    projects.save_projects(path, data)
    return True


def load(path):
    """Return the account's AI settings; the first read migrates them."""
    migrate(path)
    data = projects.load_projects(path)
    ai = default_ai()
    ai.update(data[AI_KEY])
    # Whose keys the clients read, and the language the AI writes the
    # catalog in (Settings). Never saved under "ai".
    ai["account"] = api_keys.account_of(path)
    ai["language"] = data.get("language")
    return ai


def save(path, ai):
    """Write the account's AI settings back to its project list."""
    data = projects.load_projects(path)
    data[AI_KEY] = {name: value for name, value in ai.items()
                    if name not in ("account", "language")}
    projects.save_projects(path, data)


def set_role(path, role, provider_name, model):
    """Give a role (text, fallback, media) one provider and model."""
    if role not in ROLES:
        raise ValueError("Unknown role: " + str(role))
    ai = load(path)
    ai[role] = {"provider_name": provider_name, "model": model}
    save(path, ai)


def clear_role(path, role):
    """Take the fallback or media provider away; text always has one."""
    ai = load(path)
    ai[role] = None
    save(path, ai)


def providers_used(path):
    """Return the provider names an account's roles point to. Reads only."""
    saved = projects.load_projects(path).get(AI_KEY)
    if not isinstance(saved, dict):
        # Never migrated: the default provider.
        saved = default_ai()
    names = set()
    for role in ("text", "fallback", "media"):
        chosen = saved.get(role)
        if isinstance(chosen, dict) and chosen.get("provider_name"):
            names.add(chosen["provider_name"])
    return names


def set_server_url(path, server_url):
    """Save the relay server URL, '' for none."""
    ai = load(path)
    ai["server_url"] = server_url
    save(path, ai)
