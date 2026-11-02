"""Small pictures for the Home screen, kept in the project's .cataloga folder.

Nothing is ever written in the user's own folders.
"""

import hashlib
import os

from backend.pipeline import file_readers
from backend.pipeline.file_organizer import CATALOG_FOLDER

THUMBS_FOLDER = "thumbs"
THUMB_SIDE = 192
THUMB_QUALITY = 80


def thumb_path(root, file_path):
    """Return where a file's picture is kept; a changed file gets a new one."""
    info = os.stat(file_path)
    key = "{}|{}|{}".format(os.path.relpath(file_path, root), info.st_size,
                            int(info.st_mtime))
    name = hashlib.sha1(key.encode("utf-8")).hexdigest() + ".jpg"
    return os.path.join(root, CATALOG_FOLDER, THUMBS_FOLDER, name)


def thumbnail_for(root, file_path):
    """Return the path of a photo's small picture, or None if it has none."""
    if os.path.splitext(file_path)[1].lower() not in \
            file_readers.VISION_EXTENSIONS:
        return None
    # A file only in iCloud is never opened: that would download it.
    if file_readers.in_cloud_only(file_path):
        return None
    path = thumb_path(root, file_path)
    if os.path.isfile(path):
        return path
    image = file_readers.open_photo(file_path)
    if image is None:
        return None
    image.thumbnail((THUMB_SIDE, THUMB_SIDE))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # A half-written picture must never be served.
    temporary = path + ".tmp"
    try:
        image.convert("RGB").save(temporary, format="JPEG",
                                  quality=THUMB_QUALITY)
        os.replace(temporary, path)
    except (OSError, ValueError):
        if os.path.exists(temporary):
            os.remove(temporary)
        return None
    return path
