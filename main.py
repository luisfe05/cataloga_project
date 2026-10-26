"""Entry point for Cataloga.

Starts the Flask backend and the folder watcher in background threads,
then opens the pywebview desktop window pointing at the frontend HTML
file. The frontend communicates with Flask over localhost only.
"""

import logging
import os
import socket
import sys
import threading
import time
import urllib.request

import webview

from backend.app import create_app
from backend.folder_watcher import start_watcher

# Port 5000 is avoided on purpose: on macOS the AirPlay Receiver
# already listens on it and answers requests meant for Flask.
PORT = 5050

# Folder that holds the frontend. Inside the packaged app, PyInstaller
# unpacks the bundled files into sys._MEIPASS; when running from the
# code, it is the folder of this file. An absolute path means the app
# works no matter which folder it is started from.
BASE_FOLDER = getattr(sys, "_MEIPASS",
                      os.path.dirname(os.path.abspath(__file__)))
FRONTEND_PATH = os.path.join(BASE_FOLDER, "frontend", "index.html")


class DesktopApi:
    """Python functions the frontend can call through pywebview.

    pywebview makes each method available in JavaScript as
    window.pywebview.api.<method name>().
    """

    def choose_folder(self):
        """Open the system folder picker and return the chosen path.

        Returns:
            str: The chosen folder, or an empty string if cancelled.
        """
        window = webview.windows[0]
        result = window.create_file_dialog(webview.FileDialog.FOLDER)
        if not result:
            return ""
        return result[0]

    def save_worksheet(self, query):
        """Ask where to save the worksheet, then save the CSV there.

        The desktop window can't download files like a browser, so Python
        asks Flask for the CSV and writes it to the chosen file.

        Args:
            query (str): The current filters as a URL query string,
                for example 'status=Manual+Review'. Can be empty.

        Returns:
            str: The path the file was saved to, or an empty string if
                the user cancelled.
        """
        window = webview.windows[0]
        result = window.create_file_dialog(
            webview.FileDialog.SAVE,
            save_filename="cataloga_worksheet.csv",
        )
        if not result:
            return ""
        # Depending on the system, the dialog returns a path or a list.
        path = result if isinstance(result, str) else result[0]

        url = "http://127.0.0.1:{}/documents/export".format(PORT)
        if query:
            url += "?" + query
        with urllib.request.urlopen(url) as response:
            content = response.read()
        with open(path, "wb") as file:
            file.write(content)
        return path


def start_flask(app):
    """Run the Flask development server in a background thread.

    Args:
        app: The Flask application instance.
    """
    # Flask's server (werkzeug) prints one line per request. The catalog
    # asks for data every 10 seconds, so only errors are shown.
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    # debug=False is required when running inside a thread.
    app.run(host="127.0.0.1", port=PORT, debug=False,
            use_reloader=False)


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
    start_watcher(app.config["PROJECTS_PATH"])
    wait_for_server(PORT)
    # The startup lines from Flask are hidden too, so print our own.
    print("Cataloga is running on http://127.0.0.1:{}. "
          "Close the window to quit.".format(PORT))

    # Open the frontend HTML file directly in a native desktop window.
    webview.create_window(
        "Cataloga",
        FRONTEND_PATH,
        width=1280,
        height=720,
        js_api=DesktopApi(),
    )
    webview.start()


if __name__ == "__main__":
    main()
