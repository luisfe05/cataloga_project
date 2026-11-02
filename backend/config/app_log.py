"""The app's log file, with rotation, in the app data folder."""

import logging
import os
from logging.handlers import RotatingFileHandler

LOG_FOLDER = "logs"
LOG_FILE = "cataloga.log"
MAX_BYTES = 2 * 1024 * 1024
BACKUPS = 5


def setup_log(data_folder):
    """Send the backend's messages to logs/cataloga.log; return its path."""
    folder = os.path.join(data_folder, LOG_FOLDER)
    path = os.path.join(folder, LOG_FILE)
    try:
        os.makedirs(folder, exist_ok=True)
        handler = RotatingFileHandler(path, maxBytes=MAX_BYTES,
                                      backupCount=BACKUPS, encoding="utf-8")
    except OSError:
        # The app works the same without its log.
        return None
    handler.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)-7s  %(module)s  %(message)s"))
    logger = logging.getLogger("backend")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    return path
