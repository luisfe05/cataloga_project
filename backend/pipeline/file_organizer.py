"""FileOrganizer."""

import os
import shutil
import subprocess

from backend.pipeline import folder_tree

MEDIA_TYPES = ("Press", "Audio", "Video", "Photos", "Documents")

DROP_ZONE_FOLDER = "Drop Zone"

# The same folder in projects made before Drop Zone existed.
OLD_INBOX_FOLDER = "Inbox"

# Each project's catalog. Never processed or counted as user files.
CATALOG_FOLDER = ".cataloga"


class FileOrganizer:
    """Manages the archive folder structure and file renaming."""

    def __init__(self, target_directory):
        """Set up the organizer for a specific archive folder."""
        self.target_directory = target_directory

    def folder_for(self, media_type):
        """Return the path of the subfolder for a media type."""
        if media_type not in MEDIA_TYPES:
            raise ValueError("Unknown media type: " + str(media_type))
        return os.path.join(self.target_directory, media_type)

    def drop_zone_folder(self):
        """Return the path of the Drop Zone folder."""
        return os.path.join(self.target_directory, DROP_ZONE_FOLDER)

    def old_inbox_folder(self):
        """Return the path of the old Inbox folder."""
        return os.path.join(self.target_directory, OLD_INBOX_FOLDER)

    def migrate_old_inbox(self):
        """Rename the old Inbox folder to Drop Zone, one time only."""
        if not os.path.isdir(self.old_inbox_folder()):
            return False
        if os.path.exists(self.drop_zone_folder()):
            return False
        os.rename(self.old_inbox_folder(), self.drop_zone_folder())
        return True

    def tree_folder(self, place, subfolder=None):
        """Return the disk path of a folder of the tree ('A/B/C')."""
        parts = [part for part in str(place).split("/") if part]
        if subfolder:
            parts.append(subfolder)
        return os.path.join(self.target_directory, *parts)

    def ensure_archive_structure(self, tree=None):
        """Create Drop Zone and the tree, or the five media-type folders."""
        os.makedirs(self.drop_zone_folder(), exist_ok=True)
        # Old projects have no tree and keep their media-type folders.
        if tree is None:
            for media_type in MEDIA_TYPES:
                os.makedirs(self.folder_for(media_type), exist_ok=True)
            return
        self.make_tree_folders(tree, "")

    def make_tree_folders(self, nodes, parent):
        """Create every folder of the tree, at any depth."""
        for node in nodes:
            place = parent + "/" + node["name"] if parent else node["name"]
            os.makedirs(self.tree_folder(place), exist_ok=True)
            self.make_tree_folders(folder_tree.children_of(node), place)

    def count_existing_items(self, tree=None):
        """Count the user's own files and folders in the project folder."""
        if not os.path.isdir(self.target_directory):
            return 0
        own_folders = {DROP_ZONE_FOLDER, CATALOG_FOLDER}
        if tree is None:
            own_folders |= set(MEDIA_TYPES)
        else:
            own_folders |= {top["name"] for top in tree}
        count = 0
        for name in os.listdir(self.target_directory):
            if name.startswith(".") or name in own_folders:
                continue
            count += 1
        return count

    def unique_filename(self, folder, filename):
        """Return a name that is not taken yet in a folder."""
        base, extension = os.path.splitext(filename)
        candidate = filename
        number = 2
        while os.path.exists(os.path.join(folder, candidate)):
            candidate = "{}_{}{}".format(base, number, extension)
            number += 1
        return candidate

    def move_and_rename_file(self, original_path, media_type, new_filename):
        """Move a file into its media-type folder with its new name."""
        return self.move_to_folder(original_path, self.folder_for(media_type),
                                   new_filename)

    def move_to_folder(self, original_path, folder, new_filename):
        """Move a file into a folder of the project with a new name."""
        if not os.path.isfile(original_path):
            raise FileNotFoundError(original_path)
        # A file never leaves the project folder.
        if not self.is_inside_project(folder):
            raise ValueError("The folder is outside the project.")
        os.makedirs(folder, exist_ok=True)

        new_path = os.path.join(folder,
                                self.unique_filename(folder, new_filename))

        # shutil.move works across drives, where a rename would fail.
        shutil.move(original_path, new_path)
        return new_path

    def place_of(self, folder):
        """Return a folder of the project as 'A/B', or '' for the root."""
        relative = os.path.relpath(folder, self.target_directory)
        return "" if relative == "." else relative.replace(os.sep, "/")

    def is_inside_project(self, path):
        """Return True if a path is inside the project folder."""
        folder = os.path.realpath(self.target_directory)
        real_path = os.path.realpath(path)
        return os.path.commonpath([folder, real_path]) == folder

    def rename_file(self, file_path, new_filename):
        """Give a cataloged file a new name, in the same folder."""
        if not self.is_inside_project(file_path):
            raise ValueError("The file is outside the project folder.")
        if not os.path.isfile(file_path):
            raise FileNotFoundError(file_path)

        folder = os.path.dirname(file_path)
        if new_filename == os.path.basename(file_path):
            return file_path
        new_path = os.path.join(folder, new_filename)
        # Same file when only the case changes on a case-blind disk (macOS).
        if os.path.exists(new_path) and \
                not os.path.samefile(new_path, file_path):
            new_path = os.path.join(
                folder, self.unique_filename(folder, new_filename))
        os.rename(file_path, new_path)
        return new_path

    def run_command(self, arguments):
        """Start a macOS command for a file and do not wait for it."""
        subprocess.Popen(arguments, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)

    def open_file(self, file_path):
        """Open a file with its default app, like a double click."""
        self.run_command(["open", file_path])

    def reveal_file(self, file_path):
        """Show a file in Finder, selected."""
        self.run_command(["open", "-R", file_path])

    def preview_file(self, file_path):
        """Show a Quick Look preview, like the space bar in Finder."""
        self.run_command(["qlmanage", "-p", file_path])
