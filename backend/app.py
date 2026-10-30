"""Flask application factory."""

import os

from flask import Flask
from flask_cors import CORS

from backend.config import account, projects
from backend.config.accounts import AccountStore
from backend.db.schema import DB_PATH, init_db
from backend.routes.auth import auth_bp, require_login
from backend.routes.chat import chat_bp
from backend.routes.dashboard import dashboard_bp
from backend.routes.documents import documents_bp
from backend.routes.projects import projects_bp
from backend.routes.scan import scan_bp
from backend.routes.settings import settings_bp


def create_app(data_folder=projects.DATA_FOLDER, old_db_path=DB_PATH):
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

    store = AccountStore(data_folder)
    app.config["ACCOUNTS"] = store
    # The session lives only in memory: one token, one username.
    app.config["SESSION_TOKEN"] = None
    app.config["SESSION_USER"] = None
    # Wrong passwords are counted per username.
    app.config["FAILED_ATTEMPTS"] = {}
    app.config["LOCKED_UNTIL"] = {}

    # Older installs: first the single database, then the single account.
    old_projects_path = os.path.join(data_folder, projects.PROJECTS_FILE)
    projects.migrate_old_database(old_projects_path, old_db_path)
    store.migrate_single_account(account.account_path_for(old_projects_path),
                                 old_projects_path)

    # Add any column an older catalog is missing.
    for username in store.usernames():
        folder = projects.active_folder(store.projects_path(username))
        if folder and os.path.isfile(projects.catalog_path(folder)):
            init_db(projects.catalog_path(folder))

    return app
