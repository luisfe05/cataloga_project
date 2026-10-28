"""Flask application factory.

Creates and configures the Flask app, registers all route blueprints,
asks for a session token on every route except the public login ones,
and gets the project list ready: the old single database is turned
into the first project if needed, and the active project's catalog is
brought up to date.
"""

import os

from flask import Flask
from flask_cors import CORS

from backend.config import account, projects
from backend.db.schema import DB_PATH, init_db
from backend.routes.auth import auth_bp, require_login
from backend.routes.chat import chat_bp
from backend.routes.dashboard import dashboard_bp
from backend.routes.documents import documents_bp
from backend.routes.projects import projects_bp
from backend.routes.settings import settings_bp


def create_app(projects_path=projects.PROJECTS_PATH, old_db_path=DB_PATH,
               account_path=None):
    """Create and configure the Flask application.

    Args:
        projects_path (str): Path to projects.json. Tests pass a
            temporary file.
        old_db_path (str): Path to the single database used before
            projects existed. It is only read, to create the first
            project. Tests pass a temporary file.
        account_path (str, optional): Path to account.json. By default
            it is next to projects.json.

    Returns:
        Flask: The configured app instance.
    """
    app = Flask(__name__)

    # Allow the pywebview frontend (loaded from the filesystem) to call
    # Flask routes on localhost without being blocked by CORS.
    CORS(app)

    # Every request goes through require_login() first. Without a valid
    # session token, only the public login routes answer.
    app.before_request(require_login)

    app.register_blueprint(auth_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(chat_bp)

    # Save the project list's path so routes can find it later.
    app.config["PROJECTS_PATH"] = projects_path
    # The account file, and the session, which only lives in memory.
    app.config["ACCOUNT_PATH"] = (account_path or
                                  account.account_path_for(projects_path))
    app.config["SESSION_TOKEN"] = None
    app.config["FAILED_ATTEMPTS"] = 0
    app.config["LOCKED_UNTIL"] = 0

    projects.migrate_old_database(projects_path, old_db_path)

    # Add any column a catalog made by an older version is missing.
    folder = projects.active_folder(projects_path)
    if folder and os.path.isfile(projects.catalog_path(folder)):
        init_db(projects.catalog_path(folder))

    return app
