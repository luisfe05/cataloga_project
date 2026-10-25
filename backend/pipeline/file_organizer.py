"""FileOrganizer.

Handles the archive's folder structure and the serial renaming of files
after classification. Creates the five media-type subdirectories if they
don't exist, generates the next serial filename for a given type, and
moves the original file into the correct subdirectory.

New files are dropped into the Drop Zone folder. Only Drop Zone is
processed, so anything else the user already had in the project folder
is never moved. Projects made before Drop Zone existed used a folder
called Inbox: migrate_old_inbox() renames it to Drop Zone.

FileOrganizer only works with folders and files. It never touches the
database: CatalogRepository owns all database reads and writes.
"""

import os
import re
import shutil

# Maps each media type to its serial filename prefix.
MEDIA_TYPE_PREFIXES = {
    "Press": "PR",
    "Audio": "A",
    "Video": "V",
    "Photos": "P",
    "Documents": "D",
}

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
        self.media_type_prefixes = MEDIA_TYPE_PREFIXES

    def folder_for(self, media_type):
        """Return the path of the subfolder for a media type.

        Args:
            media_type (str): One of the five valid media types.

        Returns:
            str: For example /archive/Press for 'Press'.

        Raises:
            ValueError: If media_type is not one of the five valid types.
        """
        if media_type not in self.media_type_prefixes:
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
        for media_type in self.media_type_prefixes:
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
        own_folders = set(self.media_type_prefixes) | {DROP_ZONE_FOLDER}
        count = 0
        for name in os.listdir(self.target_directory):
            if name.startswith(".") or name in own_folders:
                continue
            count += 1
        return count

    def generate_serial_filename(self, media_type, extension):
        """Build the next available serial filename for a media type.

        Looks at the files already in the media type's folder, finds the
        highest serial number in use, and returns the next one. Using the
        highest number (not a count of files) means a deleted file never
        causes a repeated name.

        Example: Documents/ has D_001.pdf and D_003.txt -> 'D_004.pdf'

        Args:
            media_type (str): One of the five valid media types.
            extension (str): File extension including the dot
                (e.g. '.pdf'). Saved in lowercase.

        Returns:
            str: The new filename (e.g. 'D_004.pdf').
        """
        folder = self.folder_for(media_type)
        prefix = self.media_type_prefixes[media_type]

        # Matches names like D_001.pdf and captures the number part.
        pattern = re.compile("^" + prefix + r"_(\d+)\.")

        highest = 0
        if os.path.isdir(folder):
            for name in os.listdir(folder):
                match = pattern.match(name)
                if match:
                    highest = max(highest, int(match.group(1)))

        # :03d pads the number with zeros to 3 digits: 4 -> 004.
        return "{}_{:03d}{}".format(prefix, highest + 1, extension.lower())

    def move_and_rename_file(self, original_path, media_type):
        """Move a file into its media-type folder with its serial name.

        Args:
            original_path (str): Absolute path to the file before
                classification.
            media_type (str): Determines which subdirectory to move it into.

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

        # splitext splits 'scan.PDF' into ('scan', '.PDF').
        extension = os.path.splitext(original_path)[1]
        new_filename = self.generate_serial_filename(media_type, extension)
        new_path = os.path.join(folder, new_filename)

        # shutil.move also works when the archive is on an external drive,
        # where a plain rename between drives would fail.
        shutil.move(original_path, new_path)
        return new_path
