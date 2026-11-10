"""About this project is the one text that says what a project is."""

import os
import re

from tests.test_folder_proposal import FolderAI, research_folder

FRONTEND = os.path.join(os.path.dirname(__file__), "..", "frontend")
SHEET = ("Work: A documentary about the Harbor Swimmers, a club that "
         "swims across the harbor at dawn.")


def read(*parts):
    """Return the text of a frontend file."""
    with open(os.path.join(FRONTEND, *parts), encoding="utf-8") as file:
        return file.read()


def fake_ai(monkeypatch, answer):
    """Every folder request goes to a FolderAI; return it."""
    ai = FolderAI(answer)
    ai.api_key = "test-key"
    monkeypatch.setattr("backend.routes.projects.text_client",
                        lambda settings: ai)
    return ai


def test_the_folder_proposal_reads_about_this_project(
        empty_client, tmp_path, monkeypatch):
    """With a folder, the sheet goes into the request as context."""
    ai = fake_ai(monkeypatch, [{"name": "Press",
                                "files": ["gazette_1998_race.txt"]}])
    root = research_folder(tmp_path / "Harbor Swimmers")
    answer = empty_client.post("/projects/folders/suggest", json={
        "folder": str(root), "project_sheet": SHEET})
    assert answer.status_code == 200
    assert any("Harbor Swimmers, a club" in text for _, text in ai.asked)


def test_without_a_folder_the_sheet_alone_is_enough(empty_client,
                                                    monkeypatch):
    """No folder yet: the sheet is the description of the project."""
    ai = fake_ai(monkeypatch, [{"name": "Press", "subfolders": []}])
    answer = empty_client.post("/projects/folders/suggest",
                               json={"project_sheet": SHEET})
    assert answer.status_code == 200
    assert ai.asked[0][1].startswith("Work: A documentary")


def test_without_a_sheet_the_folder_alone_still_works(
        empty_client, tmp_path, monkeypatch):
    """About left empty: the proposal works from the files, as before."""
    ai = fake_ai(monkeypatch, [{"name": "Press",
                                "files": ["gazette_1998_race.txt"]}])
    root = research_folder(tmp_path / "Harbor Swimmers")
    answer = empty_client.post("/projects/folders/suggest",
                               json={"folder": str(root)})
    assert answer.status_code == 200
    assert answer.get_json()["folders"][0]["name"] == "Press"
    assert ai.asked


def test_with_neither_there_is_nothing_to_go_on(empty_client):
    """No folder and no sheet: a clear error, no request."""
    answer = empty_client.post("/projects/folders/suggest", json={})
    assert answer.status_code == 400
    assert answer.get_json()["error"]["code"] == "missing_field"


def test_the_second_field_and_its_names_are_gone():
    """No "What is this project about?" field, no "Project sheet" label."""
    html = read("index.html")
    assert 'id="project-description"' not in html
    assert 'data-i18n="sheet.label"' not in html
    assert 'aria-labelledby="sheet-title"' in html
    for name in ("en.js", "es.js"):
        texts = read("js", "lang", name)
        for key in ("folders.description", "folders.description_placeholder",
                    "sheet.label"):
            assert '"{}":'.format(key) not in texts
    assert "project-description" not in read("js", "folders.js")
    assert re.search(r"suggestFolders\(sheet,", read("js", "folders.js"))
