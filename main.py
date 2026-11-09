"""Entry point for Cataloga."""

import logging
import os
import socket
import sys
import threading
import time
import urllib.request

import webview

from backend.app import create_app
from backend.config.app_log import setup_log
from backend.config.projects import DATA_FOLDER
from backend.folder_watcher import start_watcher

# Not 5000: the macOS AirPlay Receiver already listens on it.
PORT = 5050

# Inside the packaged app, PyInstaller unpacks files into sys._MEIPASS.
BASE_FOLDER = getattr(sys, "_MEIPASS",
                      os.path.dirname(os.path.abspath(__file__)))
FRONTEND_PATH = os.path.join(BASE_FOLDER, "frontend", "index.html")


ALREADY_OPEN_PAGE = ("<p style='font:15px sans-serif;margin:32px'>Cataloga is "
                     "already open, maybe in another version. Close it and "
                     "open this one again.</p>")


class DesktopApi:
    """Python functions the frontend can call through pywebview."""

    def choose_folder(self):
        """Open the system folder picker and return the chosen path."""
        window = webview.windows[0]
        result = window.create_file_dialog(webview.FileDialog.FOLDER)
        if not result:
            return ""
        return result[0]

    def save_worksheet(self, query, token):
        """Ask where to save the worksheet, then save the CSV there."""
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
        export_request = urllib.request.Request(
            url, headers={"Authorization": "Bearer " + token})
        with urllib.request.urlopen(export_request) as response:
            content = response.read()
        with open(path, "wb") as file:
            file.write(content)
        return path


def start_flask(app):
    """Run the Flask development server in a background thread."""
    # The catalog polls every 10 seconds, so log only errors.
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    # debug=False is required when running inside a thread.
    app.run(host="127.0.0.1", port=PORT, debug=False,
            use_reloader=False)


def wait_for_server(port, timeout=10):
    """Wait until something is listening on the port, up to timeout seconds."""
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return
        except OSError:
            time.sleep(0.2)


def port_in_use(port):
    """Say whether something already listens on the port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        return probe.connect_ex(("127.0.0.1", port)) == 0


def main():
    """Bootstrap the app: start Flask and the watcher, open the window."""
    setup_log(DATA_FOLDER)
    # Another copy on the port would answer this window with its own data.
    if port_in_use(PORT):
        webview.create_window("Cataloga", html=ALREADY_OPEN_PAGE,
                              width=520, height=240)
        webview.start()
        return
    app = create_app()

    flask_thread = threading.Thread(
        target=start_flask, args=(app,), daemon=True
    )
    flask_thread.start()
    start_watcher(app)
    wait_for_server(PORT)
    # Flask's startup lines are hidden, so print our own.
    print("Cataloga is running on http://127.0.0.1:{}. "
          "Close the window to quit.".format(PORT))

    # min_size keeps room for the sidebar, the toolbar, and the table.
    # text_select lets any text be copied with Cmd+C; pywebview's default
    # Edit menu already gives Copy, Paste and Select All.
    webview.create_window(
        "Cataloga",
        FRONTEND_PATH,
        width=1280,
        height=720,
        min_size=(1100, 680),
        js_api=DesktopApi(),
        text_select=True,
    )
    webview.start()


if __name__ == "__main__":
    main()
