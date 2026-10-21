"""Flask application factory.

Creates and configures the Flask app, registers all route blueprints,
and initializes the database on first run.
"""

from flask import Flask
from flask_cors import CORS
from backend.routes.documents import documents_bp
from backend.routes.dashboard import dashboard_bp
from backend.routes.settings import settings_bp
from backend.db.schema import init_db, DB_PATH


def create_app(db_path=DB_PATH):
    """Create and configure the Flask application.

    Args:
        db_path (str): Path to the database file. Defaults to
                       database/catalog.db. Tests pass a temporary file.

    Returns:
        Flask: The configured app instance.
    """
    app = Flask(__name__)

    # Allow the pywebview frontend (loaded from the filesystem) to call
    # Flask routes on localhost without being blocked by CORS.
    CORS(app)

    # Register the three route blueprints.
    app.register_blueprint(documents_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(settings_bp)

    # Save the database path so routes can find it later.
    app.config["DB_PATH"] = db_path

    # Create database tables if they don't exist yet.
    init_db(db_path)

    return app
