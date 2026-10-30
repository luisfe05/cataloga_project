"""Flask application factory."""

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
from backend.routes.scan import scan_bp
from backend.routes.settings import settings_bp


def create_app(projects_path=projects.PROJECTS_PATH, old_db_path=DB_PATH,
               account_path=None):
    """Create and configure the Flask application."""
    app = Flask(__name__)

    # CORS lets the pywebview page, loaded from a file, call localhost.
    CORS(app)

    # Without a valid session token, only the public login routes answer.
    app.before_request(require_login)

    app.register_blueprint(auth_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(scan_bp)

    app.config["PROJECTS_PATH"] = projects_path
    # The session lives only in memory.
    app.config["ACCOUNT_PATH"] = (account_path or
                                  account.account_path_for(projects_path))
    app.config["SESSION_TOKEN"] = None
    app.config["FAILED_ATTEMPTS"] = 0
    app.config["LOCKED_UNTIL"] = 0

    projects.migrate_old_database(projects_path, old_db_path)

    # Add any column an older catalog is missing.
    folder = projects.active_folder(projects_path)
    if folder and os.path.isfile(projects.catalog_path(folder)):
        init_db(projects.catalog_path(folder))

    return app
