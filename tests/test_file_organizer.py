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


def test_ensure_archive_structure_creates_drop_zone_and_five_folders(
        organizer):
    """Drop Zone and all five media-type folders exist after the call."""
    organizer.ensure_archive_structure()
    folders = sorted(os.listdir(organizer.target_directory))
    assert folders == ["Audio", "Documents", "Drop Zone", "Photos", "Press",
                       "Video"]


def test_count_existing_items_ignores_cataloga_folders(organizer):
    """Only the user's own visible files and folders are counted."""
    organizer.ensure_archive_structure()
    folder = organizer.target_directory
    make_file(folder, "poster.png")
    make_file(folder, ".DS_Store")
    os.makedirs(os.path.join(folder, "REFERENCIA"))
    assert organizer.count_existing_items() == 2


def test_count_existing_items_ignores_the_catalog_folder(organizer):
    """The project's own .cataloga folder is never the user's content."""
    organizer.ensure_archive_structure()
    os.makedirs(os.path.join(organizer.target_directory, ".cataloga"))
    assert organizer.count_existing_items() == 0


def test_count_existing_items_empty_folder(organizer):
    """A new, empty project folder has nothing to warn about."""
    organizer.ensure_archive_structure()
    assert organizer.count_existing_items() == 0


def test_count_existing_items_counts_an_inbox_in_a_new_folder(organizer):
    """In a folder Cataloga never used, Inbox is the user's own folder."""
    os.makedirs(organizer.old_inbox_folder())
    assert organizer.count_existing_items() == 1


def test_migrate_old_inbox_renames_it_and_keeps_files(organizer):
    """Inbox becomes Drop Zone and the files inside stay the same."""
    make_file(organizer.old_inbox_folder(), "clip.pdf", "hello")
    assert organizer.migrate_old_inbox() is True
    assert not os.path.exists(organizer.old_inbox_folder())
    path = os.path.join(organizer.drop_zone_folder(), "clip.pdf")
    with open(path) as file:
        assert file.read() == "hello"


def test_migrate_old_inbox_with_both_folders_does_nothing(organizer):
    """If Drop Zone already exists, Inbox is left alone."""
    inbox_file = make_file(organizer.old_inbox_folder(), "a.pdf")
    os.makedirs(organizer.drop_zone_folder())
    assert organizer.migrate_old_inbox() is False
    assert os.path.isfile(inbox_file)
    assert os.listdir(organizer.drop_zone_folder()) == []


def test_migrate_old_inbox_without_inbox_does_nothing(organizer):
    """A project with no Inbox has nothing to migrate."""
    organizer.ensure_archive_structure()
    assert organizer.migrate_old_inbox() is False
    assert os.path.isdir(organizer.drop_zone_folder())


def test_ensure_archive_structure_keeps_existing_files(organizer):
    """Running it again does not delete what is already there."""
    organizer.ensure_archive_structure()
    path = make_file(organizer.folder_for("Press"), "PR_001.pdf")
    organizer.ensure_archive_structure()
    assert os.path.isfile(path)


def test_unique_filename_free_name_is_kept(organizer):
    """A name that is not taken comes back unchanged."""
    folder = organizer.folder_for("Press")
    assert organizer.unique_filename(folder, "2026-07-15_malta.pdf") == \
        "2026-07-15_malta.pdf"


def test_unique_filename_adds_2_then_3(organizer):
    """Taken names get -2, then -3, before the extension."""
    folder = organizer.folder_for("Press")
    make_file(folder, "2026-07-15_malta.pdf")
    assert organizer.unique_filename(folder, "2026-07-15_malta.pdf") == \
        "2026-07-15_malta-2.pdf"
    make_file(folder, "2026-07-15_malta-2.pdf")
    assert organizer.unique_filename(folder, "2026-07-15_malta.pdf") == \
        "2026-07-15_malta-3.pdf"


def test_unknown_media_type_raises_value_error(organizer):
    """Only the five valid media types are accepted."""
    with pytest.raises(ValueError):
        organizer.folder_for("NewsPaper")


def test_move_and_rename_file(organizer, tmp_path):
    """The file ends up in its folder with its new name."""
    original = make_file(str(tmp_path / "drop_zone"), "scan.pdf", "hello")
    new_path = organizer.move_and_rename_file(
        original, "Press", "2026-07-15_malta.pdf")

    assert new_path == os.path.join(organizer.target_directory, "Press",
                                    "2026-07-15_malta.pdf")
    assert os.path.isfile(new_path)
    assert not os.path.exists(original)
    with open(new_path) as file:
        assert file.read() == "hello"


def test_move_two_files_with_the_same_name(organizer, tmp_path):
    """Two files that get the same name never overwrite each other."""
    first = make_file(str(tmp_path / "drop_zone"), "a.pdf", "first")
    second = make_file(str(tmp_path / "drop_zone"), "b.pdf", "second")
    path_one = organizer.move_and_rename_file(first, "Documents", "x.pdf")
    path_two = organizer.move_and_rename_file(second, "Documents", "x.pdf")
    assert os.path.basename(path_one) == "x.pdf"
    assert os.path.basename(path_two) == "x-2.pdf"
    with open(path_one) as file:
        assert file.read() == "first"


def test_existing_cataloged_files_keep_their_names(organizer, tmp_path):
    """Old serial names (PR_001) are never renamed by a new file."""
    old = make_file(organizer.folder_for("Press"), "PR_001.pdf", "old")
    new = make_file(str(tmp_path / "drop_zone"), "c.pdf")
    organizer.move_and_rename_file(new, "Press", "2026-07-15_malta.pdf")
    assert os.path.isfile(old)


def test_move_missing_file_raises(organizer, tmp_path):
    """Moving a file that does not exist raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        organizer.move_and_rename_file(str(tmp_path / "nope.pdf"), "Press",
                                       "x.pdf")
