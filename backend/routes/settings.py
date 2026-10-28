"""Settings routes."""

from flask import Blueprint, current_app, jsonify, request
from keyring.errors import KeyringError

from backend.config import account, projects
from backend.config.app_config import LANGUAGES, AppConfig
from backend.folder_watcher import old_inbox_has_files
from backend.pipeline.ai_providers import PROVIDERS, create_client
from backend.pipeline.ai_providers.base import save_api_key
from backend.pipeline import archive_rules, naming
from backend.pipeline.file_organizer import FileOrganizer
from backend.routes import (error_response, get_active_repo,
                            project_status, projects_path)

settings_bp = Blueprint("settings", __name__)


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
    data = projects.load_projects(projects_path())
    folder = data["active_folder"]
    status = project_status(folder)
    settings = {
        "research_name": "",
        "target_directory": folder,
        "naming_template": naming.DEFAULT_TEMPLATE,
        "industry": "",
        "categories": [],
        "active_provider": None,
        "active_model": None,
    }
    if status == "ok":
        repo, error = get_active_repo()
        settings.update(AppConfig(repo).get_settings())
        # The list is the source of truth for where the project is.
        settings["target_directory"] = folder
    settings["language"] = data["language"]
    settings["project_status"] = status
    settings["old_inbox_has_files"] = (
        status == "ok" and old_inbox_has_files(FileOrganizer(folder)))
    settings["providers_with_key"] = providers_with_key()
    saved_account = account.load_account(current_app.config["ACCOUNT_PATH"])
    settings["username"] = saved_account["username"] if saved_account \
        else ""
    return jsonify(settings), 200


def providers_with_key():
    """Return the names of the providers that have an API key ready."""
    names = []
    for name, client_class in PROVIDERS.items():
        if client_class().api_key:
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

    values = read_text_fields(body, ("research_name",))
    if values is None:
        return error_response("missing_field",
                              "research_name is required.", 400)
    if "naming_template" in body:
        problem = naming.validate_template(body["naming_template"])
        if problem:
            return error_response(
                "invalid_template",
                "The naming template is not valid: " + problem["reason"],
                400, extra=problem)

    archive = read_archive_settings(body)
    if isinstance(archive, str):
        return error_response("invalid_categories", archive, 400)

    repo, error = get_active_repo()
    if error:
        return error
    folder = projects.active_folder(projects_path())
    config = AppConfig(repo)

    # Must run before ensure_archive_structure(), or Drop Zone is doubled.
    organizer = FileOrganizer(folder)
    organizer.migrate_old_inbox()
    organizer.ensure_archive_structure()

    config.update_settings(values["research_name"], folder)
    projects.rename_project(projects_path(), folder,
                            values["research_name"])
    if "naming_template" in body:
        config.update_naming_template(body["naming_template"])
    if archive is not None:
        config.update_categories(archive["industry"], archive["categories"])
    if "language" in body:
        projects.set_language(projects_path(), body["language"])
    return get_settings()


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


@settings_bp.route("/settings/categories/suggest", methods=["POST"])
def suggest_categories():
    """Ask the active AI for categories for an industry. Saves nothing."""
    body = request.get_json(silent=True)
    values = read_text_fields(body, ("industry",))
    if values is None:
        return error_response("missing_field", "industry is required.", 400)
    repo, error = get_active_repo()
    if error:
        return error
    provider = repo.get_active_provider()
    if not provider:
        return error_response("no_provider",
                              "Choose an AI provider first.", 400)
    client = create_client(provider["provider_name"], provider["model"])
    industry = values["industry"][:archive_rules.MAX_INDUSTRY_LENGTH]
    categories = archive_rules.parse_category_answer(
        client.send_categories_request(industry))
    if not categories:
        return error_response(
            "suggest_failed",
            "The AI provider did not suggest any categories.", 502)
    return jsonify({"categories": categories}), 200


@settings_bp.route("/settings/ai-provider", methods=["PUT"])
def update_ai_provider():
    """Update the active AI provider, model, and API key."""
    body = request.get_json(silent=True)
    values = read_text_fields(body, ("provider_name", "model"))
    if values is None:
        return error_response("missing_field",
                              "provider_name and model are required.", 400)
    repo, error = get_active_repo()
    if error:
        return error
    if values["provider_name"] not in PROVIDERS:
        return error_response(
            "unsupported_provider",
            "Unsupported AI provider: " + values["provider_name"], 400)

    api_key = body.get("api_key")
    if isinstance(api_key, str) and api_key.strip():
        try:
            save_api_key(values["provider_name"], api_key.strip())
        except KeyringError:
            # Like macOS error -25244. Nothing is saved, not even the provider.
            return error_response(
                "keyring_failed",
                "The API key could not be saved in the system keychain.",
                400)

    AppConfig(repo).set_active_provider(values["provider_name"],
                                        values["model"])
    return jsonify({"provider_name": values["provider_name"],
                    "model": values["model"]}), 200


@settings_bp.route("/settings/ai-provider/test", methods=["POST"])
def test_ai_provider():
    """Test whether the provided AI credentials can connect."""
    body = request.get_json(silent=True)
    values = read_text_fields(body, ("provider_name", "model"))
    if values is None:
        return error_response("missing_field",
                              "provider_name and model are required.", 400)
    try:
        client = create_client(values["provider_name"], values["model"])
    except ValueError as error:
        return error_response("unsupported_provider", str(error), 400)

    api_key = body.get("api_key")
    if isinstance(api_key, str) and api_key.strip():
        client.api_key = api_key.strip()

    try:
        client.test_connection()
    except Exception as error:
        return error_response("connection_failed", str(error), 400)
    return jsonify({"connected": True}), 200
