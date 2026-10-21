"""Entry point for Cataloga.

Starts the Flask backend in a background thread, then opens the
pywebview desktop window pointing at the frontend HTML file.
The frontend communicates with Flask over localhost only.
"""

import threading
import webview
from backend.app import create_app


def start_flask(app):
    """Run the Flask development server in a background thread.

    Args:
        app: The Flask application instance.
    """
    # debug=False is required when running inside a thread.
    app.run(port=5000, debug=False, use_reloader=False)


def main():
    """Bootstrap the app: start Flask, open the pywebview window."""
    app = create_app()

    flask_thread = threading.Thread(target=start_flask, args=(app,), daemon=True)
    flask_thread.start()

    # Open the frontend HTML file directly in a native desktop window.
    webview.create_window(
        "Cataloga",
        "frontend/index.html",
        width=1280,
        height=720,
    )
    webview.start()


if __name__ == "__main__":
    main()
