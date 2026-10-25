"""FileOrganizer.

Handles the archive's folder structure and moves each cataloged file
into its media-type folder under its new name. Creates the five
media-type subdirectories if they don't exist. The new name itself is
built in naming.py; FileOrganizer only makes sure it is not taken,
adding -2, -3, and so on when it is.

New files are dropped into the Drop Zone folder. Only Drop Zone is
processed, so anything else the user already had in the project folder
is never moved. Projects made before Drop Zone existed used a folder
called Inbox: migrate_old_inbox() renames it to Drop Zone.

FileOrganizer only works with folders and files. It never touches the
database: CatalogRepository owns all database reads and writes.
"""

import os
import shutil

# The five media-type folders.
MEDIA_TYPES = ("Press", "Audio", "Video", "Photos", "Documents")

# Subfolder where the user drops new files to be cataloged.
DROP_ZONE_FOLDER = "Drop Zone"

# Name of the same folder in projects made before Drop Zone existed.
OLD_INBOX_FOLDER = "Inbox"


class FileOrganizer:
    """Manages the archive folder structure and file renaming."""

    def __init__(self, target_directory):
        """Set up the organizer for a specific archive folder.

        Args:
            target_directory (str): Absolute path to the root archive folder.
        """
        self.target_directory = target_directory

    def folder_for(self, media_type):
        """Return the path of the subfolder for a media type.

        Args:
            media_type (str): One of the five valid media types.

        Returns:
            str: For example /archive/Press for 'Press'.

        Raises:
            ValueError: If media_type is not one of the five valid types.
        """
        if media_type not in MEDIA_TYPES:
            raise ValueError("Unknown media type: " + str(media_type))
        return os.path.join(self.target_directory, media_type)

    def drop_zone_folder(self):
        """Return the path of the Drop Zone folder.

        Returns:
            str: For example /archive/Drop Zone.
        """
        return os.path.join(self.target_directory, DROP_ZONE_FOLDER)

    def old_inbox_folder(self):
        """Return the path of the old Inbox folder.

        Returns:
            str: For example /archive/Inbox.
        """
        return os.path.join(self.target_directory, OLD_INBOX_FOLDER)

    def migrate_old_inbox(self):
        """Rename the old Inbox folder to Drop Zone, one time only.

        Only call this for the project folder already saved in Settings.
        In that folder, Inbox was created by Cataloga, so renaming it is
        safe. Renaming the folder keeps every file inside it, so nothing
        is moved or renamed.

        If Drop Zone already exists, nothing happens: Inbox is then
        treated as one of the user's own folders.

        Returns:
            bool: True if Inbox was renamed, False if nothing changed.
        """
        if not os.path.isdir(self.old_inbox_folder()):
            return False
        if os.path.exists(self.drop_zone_folder()):
            return False
        os.rename(self.old_inbox_folder(), self.drop_zone_folder())
        return True

    def ensure_archive_structure(self):
        """Create Drop Zone and the five media-type folders if missing.

        Creates: Drop Zone/, Press/, Audio/, Video/, Photos/, Documents/
        inside target_directory. Folders that already exist are left
        alone.
        """
        # exist_ok=True means no error if the folder is already there.
        os.makedirs(self.drop_zone_folder(), exist_ok=True)
        for media_type in MEDIA_TYPES:
            os.makedirs(self.folder_for(media_type), exist_ok=True)

    def count_existing_items(self):
        """Count the user's own files and folders in the project folder.

        Cataloga's folders (Drop Zone and the five media types) and hidden
        files like .DS_Store are not counted. Settings uses this number to
        warn the user before using a folder that already has content.

        Returns:
            int: How many of the user's items are in the folder.
        """
        if not os.path.isdir(self.target_directory):
            return 0
        own_folders = set(MEDIA_TYPES) | {DROP_ZONE_FOLDER}
        count = 0
        for name in os.listdir(self.target_directory):
            if name.startswith(".") or name in own_folders:
                continue
            count += 1
        return count

    def unique_filename(self, folder, filename):
        """Return a name that is not taken yet in a folder.

        Example: if 2026-07-15_malta.pdf exists, the result is
        2026-07-15_malta-2.pdf, then -3, and so on.

        Args:
            folder (str): The folder the file will go into.
            filename (str): The name the file should get.

        Returns:
            str: filename itself, or filename with -2, -3... added
                before the extension.
        """
        base, extension = os.path.splitext(filename)
        candidate = filename
        number = 2
        while os.path.exists(os.path.join(folder, candidate)):
            candidate = "{}-{}{}".format(base, number, extension)
            number += 1
        return candidate

    def move_and_rename_file(self, original_path, media_type, new_filename):
        """Move a file into its media-type folder with its new name.

        Args:
            original_path (str): Absolute path to the file before
                classification.
            media_type (str): Determines which subdirectory to move it into.
            new_filename (str): The name built by naming.make_filename().
                If it is taken, -2, -3... is added.

        Returns:
            str: The absolute path to the file in its new location. The new
                filename is os.path.basename() of this path.

        Raises:
            FileNotFoundError: If original_path does not exist.
            ValueError: If media_type is not one of the five valid types.
        """
        if not os.path.isfile(original_path):
            raise FileNotFoundError(original_path)

        folder = self.folder_for(media_type)
        os.makedirs(folder, exist_ok=True)

        new_path = os.path.join(folder,
                                self.unique_filename(folder, new_filename))

        # shutil.move also works when the archive is on an external drive,
        # where a plain rename between drives would fail.
        shutil.move(original_path, new_path)
        return new_path
