"""Entry point for Cataloga.

Starts the Flask backend and the folder watcher in background threads,
then opens the pywebview desktop window pointing at the frontend HTML
file. The frontend communicates with Flask over localhost only.
"""

import os
import socket
import threading
import time

import webview

from backend.app import create_app
from backend.folder_watcher import start_watcher

PORT = 5000

# Absolute path to the frontend, so the app works no matter which folder
# it is started from.
FRONTEND_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "frontend", "index.html")


def start_flask(app):
    """Run the Flask development server in a background thread.

    Args:
        app: The Flask application instance.
    """
    # debug=False is required when running inside a thread.
    app.run(port=PORT, debug=False, use_reloader=False)


def wait_for_server(port, timeout=10):
    """Wait until something is listening on the port, up to timeout seconds.

    Without this, the window could open and ask Flask for data before
    Flask is ready, and the catalog would show an error.

    Args:
        port (int): The port Flask runs on.
        timeout (int): Seconds to wait before giving up.
    """
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return
        except OSError:
            time.sleep(0.2)


def main():
    """Bootstrap the app: start Flask and the watcher, open the window."""
    app = create_app()

    flask_thread = threading.Thread(
        target=start_flask, args=(app,), daemon=True
    )
    flask_thread.start()
    start_watcher(app.config["DB_PATH"])
    wait_for_server(PORT)

    # Open the frontend HTML file directly in a native desktop window.
    webview.create_window(
        "Cataloga",
        FRONTEND_PATH,
        width=1280,
        height=720,
    )
    webview.start()


if __name__ == "__main__":
    main()
