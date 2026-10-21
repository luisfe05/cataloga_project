"""Tests for FileOrganizer.

Each test works inside its own temporary folder, so no real files are
ever moved.
"""

import os

import pytest

from backend.pipeline.file_organizer import FileOrganizer


@pytest.fixture
def organizer(tmp_path):
    """Return a FileOrganizer whose archive is a temporary folder."""
    return FileOrganizer(str(tmp_path / "archive"))


def make_file(folder, name, content="test"):
    """Create a small text file and return its path."""
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name)
    with open(path, "w") as file:
        file.write(content)
    return path


def test_ensure_archive_structure_creates_inbox_and_five_folders(
        organizer):
    """Inbox and all five media-type folders exist after the call."""
    organizer.ensure_archive_structure()
    folders = sorted(os.listdir(organizer.target_directory))
    assert folders == ["Audio", "Documents", "Inbox", "Photos", "Press",
                       "Video"]


def test_count_existing_items_ignores_cataloga_folders(organizer):
    """Only the user's own visible files and folders are counted."""
    organizer.ensure_archive_structure()
    folder = organizer.target_directory
    make_file(folder, "poster.png")
    make_file(folder, ".DS_Store")
    os.makedirs(os.path.join(folder, "REFERENCIA"))
    assert organizer.count_existing_items() == 2


def test_count_existing_items_empty_folder(organizer):
    """A new, empty project folder has nothing to warn about."""
    organizer.ensure_archive_structure()
    assert organizer.count_existing_items() == 0


def test_ensure_archive_structure_keeps_existing_files(organizer):
    """Running it again does not delete what is already there."""
    organizer.ensure_archive_structure()
    path = make_file(organizer.folder_for("Press"), "PR_001.pdf")
    organizer.ensure_archive_structure()
    assert os.path.isfile(path)


def test_first_serial_filename(organizer):
    """An empty folder starts at 001."""
    name = organizer.generate_serial_filename("Documents", ".pdf")
    assert name == "D_001.pdf"


def test_serial_uses_highest_number(organizer):
    """The next number follows the highest one, even with a gap."""
    folder = organizer.folder_for("Documents")
    make_file(folder, "D_001.pdf")
    make_file(folder, "D_003.txt")
    name = organizer.generate_serial_filename("Documents", ".pdf")
    assert name == "D_004.pdf"


def test_serial_ignores_other_files(organizer):
    """Files that don't follow the serial pattern are not counted."""
    folder = organizer.folder_for("Photos")
    make_file(folder, "notes.txt")
    make_file(folder, "PR_009.pdf")
    name = organizer.generate_serial_filename("Photos", ".jpg")
    assert name == "P_001.jpg"


def test_serial_extension_is_lowercase(organizer):
    """'.PDF' is saved as '.pdf'."""
    name = organizer.generate_serial_filename("Press", ".PDF")
    assert name == "PR_001.pdf"


def test_unknown_media_type_raises_value_error(organizer):
    """Only the five valid media types are accepted."""
    with pytest.raises(ValueError):
        organizer.generate_serial_filename("NewsPaper", ".pdf")


def test_move_and_rename_file(organizer, tmp_path):
    """The file ends up in its folder with its serial name."""
    original = make_file(str(tmp_path / "inbox"), "scan.pdf", "hello")
    new_path = organizer.move_and_rename_file(original, "Press")

    assert new_path == os.path.join(organizer.target_directory, "Press",
                                    "PR_001.pdf")
    assert os.path.isfile(new_path)
    assert not os.path.exists(original)
    with open(new_path) as file:
        assert file.read() == "hello"


def test_move_two_files_get_different_names(organizer, tmp_path):
    """Two files of the same type never share a serial name."""
    first = make_file(str(tmp_path / "inbox"), "a.pdf")
    second = make_file(str(tmp_path / "inbox"), "b.pdf")
    path_one = organizer.move_and_rename_file(first, "Documents")
    path_two = organizer.move_and_rename_file(second, "Documents")
    assert os.path.basename(path_one) == "D_001.pdf"
    assert os.path.basename(path_two) == "D_002.pdf"


def test_move_missing_file_raises(organizer, tmp_path):
    """Moving a file that does not exist raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        organizer.move_and_rename_file(str(tmp_path / "nope.pdf"), "Press")
