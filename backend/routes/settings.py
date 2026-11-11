"""Settings routes."""

import os
import threading
import time

from flask import Blueprint, current_app, jsonify, request
from keyring.errors import KeyringError

from backend.config import ai_settings, api_keys, projects
from backend.config.app_config import LANGUAGES, AppConfig
from backend.db.schema import init_db
from backend.folder_watcher import old_inbox_has_files
from backend.pipeline.ai_providers import (MEDIA_PROVIDER, PROVIDERS, ROLES,
                                           account_client, create_client,
                                           text_client)
from backend.pipeline.ai_providers.base import (save_api_key,
                                                use_account_key)
from backend.pipeline import (archive_rules, assistant_guard, folder_tree,
                              naming, project_sheet, refile, time_budget)
from backend.pipeline.file_organizer import MEDIA_TYPES, FileOrganizer
from backend.routes import (error_response, get_active_repo,
                            project_status, projects_path, session_user)

settings_bp = Blueprint("settings", __name__)

# The connection check of GET /settings/ai-status: a short call, kept for
# a few minutes so the page never asks the provider on every visit.
STATUS_TIMEOUT_SECONDS = 8
STATUS_CACHE_SECONDS = 300
status_cache = {}

# The fields PATCH /settings saves one at a time (the General tab).
PATCH_FIELDS = ("language", "server_url")


def read_text_fields(body, names):
    """Return the stripped text of each field, or None if one is missing."""
    if not isinstance(body, dict):
        return None
    values = {}
    for name in names:
        value = body.get(name)
        if not isinstance(value, str) or not value.strip():
            return None
        values[name] = value.strip()
    return values


@settings_bp.route("/settings", methods=["GET"])
def get_settings():
    """Return the settings of the active project and the app language."""
    return jsonify(settings_view()), 200


def settings_view():
    """The settings of the active project and the account, as a dict."""
    data = projects.load_projects(projects_path())
    folder = data["active_folder"]
    status = project_status(folder)
    settings = {
        "research_name": "",
        "target_directory": folder,
        "naming_template": naming.DEFAULT_TEMPLATE,
        "stamp_date_order": archive_rules.DEFAULT_STAMP_ORDER,
        "naming_style": naming.DEFAULT_STYLE,
        "industry": "",
        "categories": [],
        "folder_mode": folder_tree.MEDIA_MODE,
        "project_description": "",
        "folder_tree": [],
        "numbered_folders": False,
        "project_sheet": "",
        "folder_counts": {},
        # How many files the catalog holds: Folder Names behaves as a new
        # project's until the first file is read.
        "files_read": 0,
    }
    if status == "ok":
        repo, error = get_active_repo()
        settings.update(AppConfig(repo).get_settings())
        settings["files_read"] = len(repo.get_all_documents())
        if repo.is_catalog_project():
            settings["folder_mode"] = folder_tree.CATALOG_MODE
            settings["project_description"] = \
                repo.get_project_description()
            # Kept for the day Catalog only is turned off.
            settings["folder_tree"] = repo.saved_tree()
            settings["folder_counts"] = counts_by_path(repo, folder)
        settings["project_sheet"] = repo.get_project_sheet()
        if repo.is_tree_project():
            # 'tree' with a Drop Zone, or 'place' when read where it is.
            settings["folder_mode"] = repo.folder_mode()
            settings["project_description"] = \
                repo.get_project_description()
            settings["folder_tree"] = repo.get_folder_tree()
            settings["numbered_folders"] = repo.numbered_folders()
            settings["folder_counts"] = folder_counts(repo)
        elif not repo.is_catalog_project() and settings["files_read"]:
            # Sorted by type and already read: those folders are the tree
            # Folder Names starts from.
            settings["folder_tree"] = type_folder_tree(folder)
            settings["folder_counts"] = counts_by_path(repo, folder)
        # The list is the source of truth for where the project is.
        settings["target_directory"] = folder
    thread = current_app.config.get("REFILE_THREAD")
    settings["refiling"] = bool(thread is not None and thread.is_alive())
    # One AI provider for every project of the account (General).
    settings.update(provider_view(ai_settings.load(projects_path())))
    settings["language"] = data["language"]
    settings["project_status"] = status
    settings["old_inbox_has_files"] = (
        status == "ok" and old_inbox_has_files(FileOrganizer(folder)))
    settings["providers_with_key"] = providers_with_key()
    # Old keys saved before each account had its own: "Is it yours?"
    settings["legacy_keys"] = api_keys.pending_legacy(projects_path(),
                                                      list(PROVIDERS))
    settings["username"] = session_user()
    return settings


def provider_view(ai):
    """The account's provider rows as GET /settings has always sent them."""
    view = {"server_url": ai.get("server_url") or ""}
    for role, prefix in (("text", "active"), ("fallback", "fallback"),
                         ("media", "media")):
        saved = ai.get(role) or {}
        view[prefix + "_provider"] = saved.get("provider_name")
        view[prefix + "_model"] = saved.get("model")
    return view


def folder_counts(repo):
    """Count the documents in every folder of the tree, at any depth."""
    return {path: repo.count_in_path(path)
            for path in folder_tree.all_paths(repo.get_folder_tree() or [])}


def counts_by_path(repo, folder):
    """Count the documents by the folder their file is in, at every level."""
    organizer = FileOrganizer(folder)
    counts = {}
    for doc in repo.get_all_documents():
        parts = folder_tree.split_path(refile.current_place(organizer, doc))
        if parts and parts[0] == "..":
            continue
        for depth in range(1, len(parts) + 1):
            path = folder_tree.join_path(parts[:depth])
            counts[path] = counts.get(path, 0) + 1
    return counts


def type_folder_tree(folder):
    """The media-type folders a project sorted by type has on disk."""
    return [folder_tree.make_node(name) for name in MEDIA_TYPES
            if os.path.isdir(os.path.join(folder, name))]


def start_refile(app, folder, repo, tree, skip=()):
    """Propose a folder of the new tree for every read file, in a thread.

    skip holds the documents the user already chose for. Returns False
    when no provider can answer; then nothing is proposed.
    """
    client = text_client(ai_settings.load(projects_path()))
    if client is None or not client.api_key:
        return False
    thread = threading.Thread(
        target=refile.refile,
        args=(repo, FileOrganizer(folder), client, tree, skip), daemon=True)
    app.config["REFILE_THREAD"] = thread
    thread.start()
    return True


def account_name():
    """Whose keys this session reads and saves."""
    return api_keys.account_of(projects_path())


def providers_with_key():
    """Return the providers this account has an API key ready for."""
    names = []
    for name, client_class in PROVIDERS.items():
        if use_account_key(client_class(), account_name()).api_key:
            names.append(name)
    return names


@settings_bp.route("/settings", methods=["PUT"])
def update_settings():
    """Save the project name, naming template, and app language."""
    body = request.get_json(silent=True)
    if isinstance(body, dict) and "language" in body and \
            body["language"] not in LANGUAGES:
        return error_response(
            "invalid_language",
            "language must be one of: " + ", ".join(LANGUAGES), 400)
    if isinstance(body, dict) and list(body) == ["language"]:
        projects.set_language(projects_path(), body["language"])
        return get_settings()
    if "catalog_only" in body and body["catalog_only"] is not False:
        return error_response(
            "invalid_field",
            "catalog_only can only be turned off here.", 400)

    values = read_text_fields(body, ("research_name",))
    if values is None:
        return error_response("missing_field",
                              "research_name is required.", 400)
    if "stamp_date_order" in body and \
            body["stamp_date_order"] not in archive_rules.STAMP_ORDERS:
        return error_response("invalid_stamp_order",
                              "stamp_date_order must be month or day.", 400)
    if "naming_style" in body and body["naming_style"] not in naming.STYLES:
        return error_response("invalid_style",
                              "naming_style must be lower or title.", 400)
    if "project_sheet" in body:
        body["project_sheet"] = project_sheet.clean_sheet(
            body["project_sheet"])
        if body["project_sheet"] is None:
            return error_response(
                "invalid_sheet", "project_sheet must be text of {} "
                "characters or less".format(project_sheet.MAX_SHEET_LENGTH),
                400)
    if "server_url" in body:
        body["server_url"] = clean_server_url(body["server_url"])
        if body["server_url"] is None:
            return error_response(
                "invalid_server_url",
                "server_url must start with http:// or https://.", 400)
    if "naming_template" in body:
        problem = naming.validate_template(body["naming_template"])
        if problem:
            return error_response(
                "invalid_template",
                "The naming template is not valid: " + problem["reason"],
                400, extra=problem)

    repo, error = get_active_repo()
    if error:
        return error
    tree_mode = repo.is_tree_project()
    catalog_mode = repo.is_catalog_project()
    # Catalog only ends here: the project is then read in place, with the
    # folders it kept, and the moves wait in To Approve.
    turn_off = catalog_mode and body.get("catalog_only") is False
    # Folder Names in a project sorted by type (or one leaving Catalog
    # only): it becomes a project with its own folders, read in place.
    becomes_place = (not tree_mode and not catalog_mode and
                     "folder_tree" in body) or turn_off
    uses_tree = tree_mode or becomes_place
    # A Catalog only project keeps the tree it is given, for later.
    kept = None
    if uses_tree:
        archive = read_folder_tree(body, repo)
        if turn_off and archive is None:
            archive = {"categories": repo.saved_tree()}
    else:
        archive = read_archive_settings(body)
        if catalog_mode and "folder_tree" in body:
            kept = read_folder_tree(body, repo)
    for checked in (archive, kept):
        if isinstance(checked, tuple):
            return error_response(checked[0], checked[1], checked[2])
        if isinstance(checked, str):
            return error_response("invalid_categories", checked, 400)

    folder = projects.active_folder(projects_path())
    config = AppConfig(repo)
    # The tree Folder Names showed: the saved one, or the type folders.
    old_tree = repo.get_folder_tree()
    if old_tree is None and not catalog_mode:
        old_tree = type_folder_tree(folder)
    old_paths = set(folder_tree.all_paths(old_tree or []))
    # Where the files of each folder taken out of the tree go.
    moves = read_folder_moves(body, old_paths, archive)
    if isinstance(moves, tuple):
        return error_response(moves[0], moves[1], moves[2])

    # Must run before ensure_archive_structure(), or Drop Zone is doubled.
    organizer = FileOrganizer(folder)
    if becomes_place:
        repo.save_config_value("folder_mode", folder_tree.PLACE_MODE)
        # The rows say the folder each file is in now.
        init_db(repo.db_path)
    if (uses_tree or kept is not None) and "numbered_folders" in body:
        repo.save_config_value("numbered_folders",
                               1 if body["numbered_folders"] else 0)
    if uses_tree and archive is not None:
        # Drop Zone projects create new folders below; read in place the
        # tree is saved and nothing is made on the disk.
        repo.save_tree(archive["categories"])
    if kept is not None:
        repo.save_tree(kept["categories"])
    if not repo.is_catalog_project():
        organizer.migrate_old_inbox()
        # Read in place nothing is made: the plan makes folders when applied.
        if not repo.reads_in_place():
            organizer.ensure_archive_structure(repo.get_folder_tree())
    # The files of a removed folder go where the user said, or stay.
    chosen = {}
    if moves and repo.is_tree_project():
        chosen = apply_folder_moves(repo, organizer, old_tree or [], moves)
    # The tree changed under files already read: the AI proposes where
    # the other files go now, and the moves wait in To Approve.
    refile_started = False
    needs_provider = False
    if archive is not None and not repo.is_catalog_project() and \
            repo.get_all_documents():
        new_paths = set(folder_tree.all_paths(repo.get_folder_tree() or []))
        if becomes_place or new_paths != old_paths:
            refile_started = start_refile(current_app._get_current_object(),
                                          folder, repo, repo.get_folder_tree(),
                                          skip=set(chosen))
            # Saved, but nobody can propose the moves: the card says so.
            needs_provider = not refile_started

    config.update_settings(values["research_name"], folder)
    projects.rename_project(projects_path(), folder,
                            values["research_name"])
    if "naming_template" in body:
        config.update_naming_template(body["naming_template"])
    if "stamp_date_order" in body:
        repo.save_config_value("stamp_date_order", body["stamp_date_order"])
    if "naming_style" in body:
        repo.save_config_value("naming_style", body["naming_style"])
    if "project_sheet" in body:
        repo.save_config_value("project_sheet", body["project_sheet"])
    if "server_url" in body:
        ai_settings.set_server_url(projects_path(), body["server_url"])
        status_cache.clear()
    if archive is not None and not uses_tree:
        config.update_categories(archive["industry"], archive["categories"])
    if "language" in body:
        projects.set_language(projects_path(), body["language"])
    settings = settings_view()
    settings["refile_started"] = refile_started
    settings["needs_provider"] = needs_provider
    settings["folder_moves"] = len(chosen)
    return jsonify(settings), 200


def read_archive_settings(body):
    """Return the checked industry and categories, or an error text."""
    if "industry" not in body and "categories" not in body:
        return None
    industry = body.get("industry") or ""
    if not isinstance(industry, str) or \
            len(industry.strip()) > archive_rules.MAX_INDUSTRY_LENGTH:
        return "industry must be text of {} characters or less".format(
            archive_rules.MAX_INDUSTRY_LENGTH)
    try:
        categories = archive_rules.clean_categories(body.get("categories"))
    except ValueError as error:
        return str(error)
    return {"industry": industry.strip(), "categories": categories}


def read_folder_tree(body, repo):
    """Return the checked tree, or (code, message, status) if it is wrong."""
    sent = body.get("folder_tree", body.get("categories"))
    if sent is None:
        return None
    try:
        tree = folder_tree.check_tree(sent)
    except ValueError as error:
        return ("invalid_folders", str(error), 400)
    paths = folder_tree.all_paths(tree)
    # The same path rules as the plan: inside the project, no "..".
    for place in paths:
        if assistant_guard.path_problem(place):
            return ("invalid_folders", "This folder path is not allowed: " +
                    place, 400)
    # With a Drop Zone, a folder that holds documents can never leave the
    # tree. Read in place it can: its files get a new folder in To Approve.
    if repo.folder_mode() == folder_tree.TREE_MODE:
        for place in folder_tree.all_paths(repo.get_folder_tree() or []):
            if not folder_in(place, paths) and repo.count_in_path(place):
                return ("folder_not_empty",
                        "This folder has documents: " + place, 409)
    if body.get("numbered_folders") if "numbered_folders" in body \
            else repo.numbered_folders():
        tree = folder_tree.number_new(
            tree, folder_tree.all_paths(repo.get_folder_tree() or []))
    return {"categories": tree}


def read_folder_moves(body, old_paths, archive):
    """Return {removed folder: target folder, or '' to leave the files}.

    A removed folder must be one Folder Names showed and that left the
    tree; a target must be a folder of the new tree that holds files.
    Returns (code, message, status) when something is wrong.
    """
    sent = body.get("folder_moves")
    if sent is None:
        return {}
    new_tree = archive["categories"] if isinstance(archive, dict) and \
        "categories" in archive else None
    if not isinstance(sent, dict) or new_tree is None:
        return ("invalid_folder_moves", "folder_moves must go with a "
                "folder_tree.", 400)
    new_paths = folder_tree.all_paths(new_tree)
    moves = {}
    for removed, target in sent.items():
        if not isinstance(removed, str) or not isinstance(target, str) or \
                removed not in old_paths or folder_in(removed, new_paths):
            return ("invalid_folder_moves", "That folder was not removed: " +
                    str(removed), 400)
        target = target.strip().strip("/")
        if target and (assistant_guard.path_problem(target) or
                       folder_tree.find_place(new_tree, target) is None):
            return ("invalid_folder_moves", "That folder is not in the "
                    "tree: " + target, 400)
        moves[removed] = folder_tree.find_place(new_tree, target) \
            if target else ""
    return moves


def apply_folder_moves(repo, organizer, old_tree, moves):
    """Give the files of each removed folder the folder the user chose.

    Nothing moves here: a target becomes the file's proposal in To
    Approve, and the emptied folder is removed only after Apply. Leave
    them where they are clears any proposal and keeps the folder. A
    folder with no files is removed at Apply too. Returns {document id:
    target}.
    """
    chosen = {}
    removed = list(repo.removed_folders())
    for place, target in moves.items():
        inside = [path for path in folder_tree.all_paths(old_tree)
                  if path == place or path.startswith(place + "/")]
        has_files = False
        for doc in repo.get_all_documents():
            here = refile.current_place(organizer, doc)
            if here == place or here.startswith(place + "/"):
                has_files = True
                if repo.reads_in_place():
                    repo.set_proposal(doc.id, target or None,
                                      doc.proposed_name)
                    chosen[doc.id] = target
        if target or not has_files:
            removed += inside
    repo.set_removed_folders(removed)
    return chosen


def folder_in(place, places):
    """Say whether a folder is in a list, ignoring case and accents."""
    return archive_rules.fold(place) in [archive_rules.fold(p)
                                         for p in places]


@settings_bp.route("/settings/categories/suggest", methods=["POST"])
def suggest_categories():
    """Ask the active AI for categories for an industry. Saves nothing."""
    body = request.get_json(silent=True)
    values = read_text_fields(body, ("industry",))
    if values is None:
        return error_response("missing_field", "industry is required.", 400)
    client = text_client(ai_settings.load(projects_path()))
    if client is None:
        return error_response("no_provider",
                              "Choose an AI provider first.", 400)
    industry = values["industry"][:archive_rules.MAX_INDUSTRY_LENGTH]
    categories = archive_rules.parse_category_answer(
        client.send_categories_request(industry))
    if not categories:
        return error_response(
            "suggest_failed",
            "The AI provider did not suggest any categories.", 502)
    return jsonify({"categories": categories}), 200


@settings_bp.route("/settings/sheet/suggest", methods=["POST"])
def suggest_sheet():
    """Ask the AI to write the project sheet from a sample. Saves nothing."""
    body = request.get_json(silent=True)
    folder = body.get("folder") if isinstance(body, dict) else None
    if isinstance(folder, str) and folder.strip():
        folder = projects.normalize_folder(folder)
    else:
        # No folder sent: the active project's own folder.
        folder = projects.active_folder(projects_path())
    if not folder or not os.path.isdir(folder):
        return error_response("invalid_directory",
                              "The folder does not exist: " + str(folder),
                              400)
    # The account's provider, even before the first project exists.
    client = text_client(ai_settings.load(projects_path()))
    if client is None or not client.api_key:
        return error_response("no_provider",
                              "Choose an AI provider first.", 400)
    sheet = project_sheet.write_sheet(client, folder)
    if not sheet:
        # Its own code, so the message speaks of the description.
        return error_response("sheet_failed",
                              "The AI provider did not write a sheet.", 502)
    return jsonify({"sheet": sheet}), 200


def clean_server_url(value):
    """Return a server URL without spaces, '' for none, or None if bad."""
    if value is None:
        return ""
    if not isinstance(value, str):
        return None
    value = value.strip().rstrip("/")
    if not value:
        return ""
    if not value.startswith(("http://", "https://")) or len(value) > 200:
        return None
    return value


def read_role(body):
    """Return the role a provider request is about: text unless said."""
    role = body.get("role", "text") if isinstance(body, dict) else "text"
    return role if role in ROLES else None


@settings_bp.route("/settings/ai-provider", methods=["PUT"])
def update_ai_provider():
    """Update the provider, model, and API key of one role."""
    body = request.get_json(silent=True)
    values = read_text_fields(body, ("provider_name", "model"))
    if values is None:
        return error_response("missing_field",
                              "provider_name and model are required.", 400)
    role = read_role(body)
    if role is None:
        return error_response("invalid_role",
                              "role must be text, fallback, or media.", 400)
    if values["provider_name"] not in PROVIDERS:
        return error_response(
            "unsupported_provider",
            "Unsupported AI provider: " + values["provider_name"], 400)
    # Ollama Cloud and the others do not read audio or video.
    if role == "media" and values["provider_name"] != MEDIA_PROVIDER:
        return error_response(
            "unsupported_provider",
            "Only Google Gemini reads audio and video.", 400)

    api_key = body.get("api_key")
    if isinstance(api_key, str) and api_key.strip():
        try:
            save_api_key(account_name(), values["provider_name"],
                         api_key.strip())
        except KeyringError:
            # Like macOS error -25244. Nothing is saved, not even the provider.
            return error_response(
                "keyring_failed",
                "The API key could not be saved in the system keychain.",
                400)

    # One provider for every project: saved with the account.
    ai_settings.set_role(projects_path(), role, values["provider_name"],
                         values["model"])
    status_cache.clear()
    return jsonify({"role": role, "provider_name": values["provider_name"],
                    "model": values["model"]}), 200


@settings_bp.route("/settings/ai-provider/<role>", methods=["DELETE"])
def clear_ai_provider(role):
    """Take the fallback or media provider away. The key stays saved."""
    if role not in ROLES or role == "text":
        return error_response("invalid_role",
                              "Only fallback and media can be cleared.", 400)
    ai_settings.clear_role(projects_path(), role)
    status_cache.clear()
    return jsonify({"role": role, "provider_name": None}), 200


@settings_bp.route("/settings/ai-provider/legacy-key", methods=["POST"])
def answer_legacy_key():
    """Answer "Is it yours?" about an old shared key: claim or decline.

    claim moves the key to this account and removes the shared entry, so
    no other account can use it. decline only stops asking this account.
    """
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or body.get("provider_name") not in \
            PROVIDERS or body.get("answer") not in ("claim", "decline"):
        return error_response(
            "invalid_field",
            "provider_name and answer (claim or decline) are needed.", 400)
    provider = body["provider_name"]
    if body["answer"] == "decline":
        api_keys.decline(projects_path(), provider)
        return jsonify({"provider_name": provider, "claimed": False}), 200
    if not api_keys.move_legacy_key(account_name(), provider):
        # Another account took it first, or the keychain refused.
        return error_response("legacy_key_gone",
                              "That key is no longer available.", 409)
    status_cache.clear()
    return jsonify({"provider_name": provider, "claimed": True}), 200


@settings_bp.route("/settings/ai-provider/test", methods=["POST"])
def test_ai_provider():
    """Test whether the provided AI credentials can connect."""
    body = request.get_json(silent=True)
    values = read_text_fields(body, ("provider_name", "model"))
    if values is None:
        return error_response("missing_field",
                              "provider_name and model are required.", 400)
    server_url = body.get("server_url")
    if not isinstance(server_url, str) or not server_url.strip():
        server_url = None
    try:
        client = create_client(values["provider_name"], values["model"],
                               server_url)
    except ValueError as error:
        return error_response("unsupported_provider", str(error), 400)
    # Without a typed key, the test uses this account's saved key.
    use_account_key(client, account_name())

    api_key = body.get("api_key")
    if isinstance(api_key, str) and api_key.strip():
        client.api_key = api_key.strip()

    try:
        client.test_connection()
    except Exception as error:
        return error_response("connection_failed", str(error), 400)
    return jsonify({"connected": True}), 200


@settings_bp.route("/settings", methods=["PATCH"])
def patch_setting():
    """Save one General field, {key, value}, checked here first."""
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or "key" not in body or \
            "value" not in body:
        return error_response("missing_field",
                              "key and value are required.", 400)
    key = body["key"]
    value = body["value"]
    if key not in PATCH_FIELDS:
        return error_response(
            "invalid_key",
            "key must be one of: " + ", ".join(PATCH_FIELDS), 400)
    if key == "language":
        if value not in LANGUAGES:
            return error_response(
                "invalid_language",
                "language must be one of: " + ", ".join(LANGUAGES), 400)
        projects.set_language(projects_path(), value)
        return jsonify({"key": key, "value": value}), 200
    # The server belongs to the account, like the provider.
    value = clean_server_url(value)
    if value is None:
        return error_response(
            "invalid_server_url",
            "server_url must start with http:// or https://.", 400)
    ai_settings.set_server_url(projects_path(), value)
    status_cache.clear()
    return jsonify({"key": key, "value": value}), 200


def check_connection(client):
    """Return connected or error after one short call, kept for minutes."""
    # Saving a provider, a key or a server clears the cache.
    # Per account: each one has its own key.
    cache_key = (account_name(), client.provider_name, client.model,
                 getattr(client, "base_url", None))
    saved = status_cache.get(cache_key)
    if saved and time.monotonic() - saved[0] < STATUS_CACHE_SECONDS:
        return saved[1]
    # A budget on this thread makes the client's timeout short.
    time_budget.local.budget = time_budget.Budget(STATUS_TIMEOUT_SECONDS)
    try:
        client.test_connection()
        status = "connected"
    except Exception:  # noqa: BLE001
        status = "error"
    finally:
        time_budget.local.budget = None
    status_cache[cache_key] = (time.monotonic(), status)
    return status


@settings_bp.route("/settings/ai-status", methods=["GET"])
def ai_status():
    """Say which provider reads the files and whether it connects."""
    ai = ai_settings.load(projects_path())
    provider = ai["text"]["provider_name"]
    model = ai["text"]["model"]
    client = account_client(ai, provider, model)
    has_key = bool(client.api_key)
    status = check_connection(client) if has_key else "no_key"
    # Only yes or no about the key: the key itself never leaves.
    return jsonify({"provider": provider, "model": model,
                    "has_key": has_key, "status": status}), 200
