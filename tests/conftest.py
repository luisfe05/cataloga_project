"""pytest fixtures shared across all test modules."""

import os

import pytest

from backend.app import create_app
from backend.config import account, projects
from backend.db.catalog_repository import CatalogRepository
from backend.db.schema import init_db
from backend.pipeline.ai_providers import base, ollama_cloud
from backend.pipeline.file_organizer import FileOrganizer


# Session token the logged-in test clients send.
TEST_TOKEN = "test-token"


def logged_in_client(app):
    """Return a test client that sends a valid session token."""
    app.config["SESSION_TOKEN"] = TEST_TOKEN
    client = app.test_client()
    client.environ_base["HTTP_AUTHORIZATION"] = "Bearer " + TEST_TOKEN
    return client


def make_project(projects_path, folder, name="Research"):
    """Create a project folder with its catalog and add it to the list."""
    folder.mkdir(parents=True, exist_ok=True)
    db_path = projects.catalog_path(str(folder))
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    init_db(db_path)
    repo = CatalogRepository(db_path)
    repo.save_app_config(name, str(folder))
    FileOrganizer(str(folder)).ensure_archive_structure()
    projects.add_project(projects_path, name, str(folder))
    return repo


@pytest.fixture(autouse=True)
def no_real_keys(monkeypatch, tmp_path):
    """Hide the real keyring, OLLAMA_API_KEY, and cataloga/.env."""
    monkeypatch.setattr(base.keyring, "get_password",
                        lambda service, name: None)
    monkeypatch.delenv(ollama_cloud.ENV_KEY_NAME, raising=False)
    monkeypatch.setattr(ollama_cloud, "ENV_PATH",
                        str(tmp_path / "missing.env"))


@pytest.fixture(autouse=True)
def fast_bcrypt(monkeypatch):
    """Use the fewest bcrypt rounds, so password tests run fast."""
    monkeypatch.setattr(account, "BCRYPT_ROUNDS", 4)


@pytest.fixture
def projects_path(tmp_path):
    """Path of a project list in a temporary app data folder."""
    return str(tmp_path / "app_data" / "projects.json")


@pytest.fixture
def app(tmp_path, projects_path):
    """Return a Flask app with one active project, "Research"."""
    folder = tmp_path / "Research"
    make_project(projects_path, folder)
    app = create_app(projects_path=projects_path,
                     old_db_path=str(tmp_path / "no_old.db"))
    app.config["TESTING"] = True
    app.config["PROJECT_FOLDER"] = str(folder)
    return app


@pytest.fixture
def flask_client(app):
    """Return a logged-in Flask test client for the app fixture."""
    with logged_in_client(app) as client:
        yield client


@pytest.fixture
def empty_client(tmp_path, projects_path):
    """Return a logged-in test client for an app with no projects yet."""
    app = create_app(projects_path=projects_path,
                     old_db_path=str(tmp_path / "no_old.db"))
    app.config["TESTING"] = True
    with logged_in_client(app) as client:
        yield client
