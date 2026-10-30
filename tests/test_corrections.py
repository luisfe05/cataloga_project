"""Tests for learning from the user's moves (corrections)."""

import os

from backend.db.catalog_repository import CatalogRepository
from backend.pipeline import classification_pipeline, folder_tree
# The fixtures come along with the helpers.
from tests.test_project_folders import (  # noqa: F401
    add_file_doc, create_tree_project, drop, old_project, tree_project,
    tree_repo)


def test_move_by_hand_is_remembered(flask_client, tmp_path):
    """A Move writes a correction: the file, what it is, from and to."""
    folder, repo = tree_repo(flask_client, tmp_path)
    doc = add_file_doc(repo, str(folder / "Drop Zone" / "receta.txt"),
                       summary="Una receta de arroz.",
                       review_note=folder_tree.NO_FOLDER_NOTE,
                       status="Manual Review")
    response = flask_client.post("/documents/{}/move".format(doc.id),
                                 json={"folder": "Contratos"})
    assert response.status_code == 200
    moves = repo.recent_corrections()
    assert moves == [{"original_filename": "receta.txt",
                      "summary": "Una receta de arroz.",
                      "from_folder": "Drop Zone", "to_folder": "Contratos"}]
    # A second move of the same file records where it came from now.
    flask_client.post("/documents/{}/move".format(doc.id),
                      json={"folder": "Oceanman Malta/Prensa"})
    assert repo.recent_corrections()[0]["from_folder"] == "Contratos"
    assert repo.recent_corrections()[0]["to_folder"] == \
        "Oceanman Malta/Prensa"


def test_latest_moves_go_into_the_prompt(tree_project):
    """The AI reads the user's moves, newest first, ten at most."""
    repo = tree_project["repo"]
    for i in range(12):
        doc = add_file_doc(repo, str(tree_project["drop_zone"] /
                                     "f{}.txt".format(i)),
                           summary="File {}".format(i))
        repo.add_correction(doc, "Contratos")
    tree_project["pipeline"].classify_document(
        drop(tree_project, "new.txt", "Text"))
    prompt = tree_project["ai"].prompts[-1]
    assert "moved these files by hand" in prompt
    assert '"f11.txt" (about: File 11) went from Drop Zone to Contratos' \
        in prompt
    assert prompt.index('"f11.txt"') < prompt.index('"f2.txt"')
    assert '"f1.txt"' not in prompt and '"f0.txt"' not in prompt
    assert prompt.count("went from") == classification_pipeline.MAX_CORRECTIONS


def test_without_moves_the_prompt_is_unchanged(tree_project):
    """No corrections yet: no extra section."""
    tree_project["pipeline"].classify_document(
        drop(tree_project, "a.txt", "Text"))
    assert "moved these files" not in tree_project["ai"].prompts[-1]


def test_corrections_stay_in_their_project(flask_client, tmp_path):
    """Each catalog keeps its own corrections."""
    folder, repo = tree_repo(flask_client, tmp_path)
    doc = add_file_doc(repo, str(folder / "Drop Zone" / "a.txt"))
    flask_client.post("/documents/{}/move".format(doc.id),
                      json={"folder": "Contratos"})
    other = tmp_path / "Other"
    other.mkdir()
    db_path = os.path.join(str(other), ".cataloga", "catalog.db")
    os.makedirs(os.path.dirname(db_path))
    from backend.db.schema import init_db
    init_db(db_path)
    assert CatalogRepository(db_path).recent_corrections() == []
    assert len(repo.recent_corrections()) == 1
