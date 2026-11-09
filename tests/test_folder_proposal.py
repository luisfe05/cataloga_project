"""Tests for folders proposed from what a connected folder already holds."""

import json
import os

import pytest

from backend.pipeline import ai_providers, folder_proposal
from backend.pipeline.ai_providers import base
from backend.pipeline.ai_providers.base import AIProviderClient


class FolderAI(AIProviderClient):
    """Answers the folder prompts with a fixed list and keeps what it saw."""

    def __init__(self, answer):
        super().__init__(provider_name="fake", model="fake-model")
        self.retry_delay = 0
        self.answer = answer
        self.asked = []

    def send_prompt(self, system_prompt, text):
        self.asked.append((system_prompt, text))
        return json.dumps(self.answer)


@pytest.fixture(autouse=True)
def test_key(monkeypatch):
    """A key, so the fake client answers."""
    monkeypatch.setattr(base.keyring, "get_password",
                        lambda service, name: "test-key")


def research_folder(root):
    """Only research: press clippings, interview notes and a photo."""
    root.mkdir()
    (root / "gazette_1998_race.txt").write_text(
        "Harbor Gazette, 1998. The dawn swim drew forty swimmers.")
    (root / "coast_weekly_pier.txt").write_text("Coast Weekly on the pier.")
    (root / "interview_coach.txt").write_text("Notes from the coach talk.")
    (root / "IMG_0001.jpg").write_bytes(b"jpg")
    return root


def names(tree):
    """Top folder names of a tree."""
    return [node["name"] for node in tree]


def test_only_folders_with_files_are_kept(tmp_path):
    """A film-production folder with no files in the list is dropped."""
    ai = FolderAI([
        {"name": "Press", "files": ["gazette_1998_race.txt",
                                    "coast_weekly_pier.txt"]},
        {"name": "Interviews", "files": ["interview_coach.txt"]},
        {"name": "Photos", "files": ["IMG_0001.jpg"]},
        {"name": "Editing", "files": []},
        {"name": "Music rights", "files": ["score_final.wav"]},
        {"name": "Production", "files": [],
         "subfolders": [{"name": "Call sheets", "files": []}]}])
    result = folder_proposal.propose(ai, str(research_folder(
        tmp_path / "Research")), "Research for a documentary")
    assert names(result["folder_tree"]) == ["Press", "Interviews", "Photos"]
    assert result["organized"] is False


def test_a_subfolder_stays_only_with_its_files(tmp_path):
    """Subfolders follow the same rule as top folders."""
    ai = FolderAI([{"name": "Press", "files": [], "subfolders": [
        {"name": "Gazette", "files": ["gazette_1998_race.txt"]},
        {"name": "Radio", "files": ["bay_radio.mp3"]}]}])
    tree = folder_proposal.propose(ai, str(research_folder(
        tmp_path / "Research")))["folder_tree"]
    assert names(tree) == ["Press"]
    assert names(tree[0]["children"]) == ["Gazette"]


def test_the_ai_reads_the_files_and_the_description_as_context(tmp_path):
    """Names, kinds and extracts go out; the description is only context."""
    ai = FolderAI([])
    folder_proposal.propose(ai, str(research_folder(tmp_path / "Research")),
                            "Research for a documentary")
    prompt, text = ai.asked[0]
    assert prompt == folder_proposal.FROM_FILES_PROMPT
    assert "not a list of" in prompt and "at least one" in prompt
    assert "context only): Research for a documentary" in text
    assert "gazette_1998_race.txt" in text and "IMG_0001.jpg" in text
    assert "3 .txt" in text and "1 .jpg" in text
    assert "The dawn swim drew forty swimmers." in text


def test_an_organized_folder_keeps_its_tree_without_asking(tmp_path):
    """No loose files: Learn from my folder decides, with no AI call."""
    root = tmp_path / "Organized"
    (root / "Press").mkdir(parents=True)
    (root / "Photos" / "Dawn-Swim_1997").mkdir(parents=True)
    (root / "Press" / "gazette.txt").write_text("x")
    (root / "Photos" / "Dawn-Swim_1997" / "a.jpg").write_bytes(b"x")
    ai = FolderAI([{"name": "Should not appear", "files": ["gazette.txt"]}])
    result = folder_proposal.propose(ai, str(root))
    assert result["organized"] is True
    assert names(result["folder_tree"]) == ["Photos", "Press"]
    assert ai.asked == []


def test_loose_files_bring_new_folders_only_when_they_need_them(tmp_path):
    """Existing folders stay; a new one only with a loose file in it."""
    root = tmp_path / "Organized"
    (root / "Press").mkdir(parents=True)
    (root / "Press" / "gazette.txt").write_text("x")
    (root / "coach_notes.txt").write_text("Notes from the coach.")
    (root / "radio_clip.txt").write_text("A radio clip transcript.")
    ai = FolderAI([{"name": "Interviews", "files": ["coach_notes.txt"]},
                   {"name": "press", "files": ["radio_clip.txt"]},
                   {"name": "Budget", "files": ["budget.xlsx"]}])
    result = folder_proposal.propose(ai, str(root))
    assert names(result["folder_tree"]) == ["Press", "Interviews"]
    prompt, text = ai.asked[0]
    assert prompt == folder_proposal.LOOSE_FILES_PROMPT
    assert "Existing folders:\n  Press" in text
    assert "coach_notes.txt" in text and "gazette.txt" not in text


def test_route_proposes_from_the_folder_with_no_description(
        empty_client, tmp_path, monkeypatch):
    """POST /projects/folders/suggest with folder: only what is there."""
    ai = FolderAI([{"name": "Press", "files": ["gazette_1998_race.txt"]},
                   {"name": "Editing", "files": []}])
    monkeypatch.setattr("backend.routes.projects.create_client",
                        lambda name, model, base_url=None: ai)
    root = research_folder(tmp_path / "Research")
    answer = empty_client.post("/projects/folders/suggest",
                               json={"folder": str(root)})
    assert answer.status_code == 200
    body = answer.get_json()
    assert names(body["folders"]) == ["Press"]
    assert body["organized"] is False
    assert sorted(p.name for p in root.iterdir()) == sorted(
        ["gazette_1998_race.txt", "coast_weekly_pier.txt",
         "interview_coach.txt", "IMG_0001.jpg"])


def test_route_says_so_when_nothing_fits(empty_client, tmp_path,
                                         monkeypatch):
    """Every proposed folder was empty: no tree, and an error to show."""
    ai = FolderAI([{"name": "Editing", "files": []}])
    monkeypatch.setattr("backend.routes.projects.create_client",
                        lambda name, model, base_url=None: ai)
    answer = empty_client.post("/projects/folders/suggest", json={
        "folder": str(research_folder(tmp_path / "Research"))})
    assert answer.status_code == 502
    assert answer.get_json()["error"]["code"] == "suggest_folders_failed"


def test_the_old_description_request_still_works_without_a_folder():
    """An empty Drop Zone project has no files: the description decides."""
    assert ai_providers.base.FOLDERS_PROMPT.startswith(
        "You are an archivist setting up")


def read_js(name):
    """Return the text of a frontend script."""
    path = os.path.join(os.path.dirname(__file__), "..", "frontend", "js",
                        name)
    with open(path, encoding="utf-8") as file:
        return file.read()


def test_only_archive_now_reads_the_folder_from_the_form():
    """Later never asks; Now asks once, and never over the user's folders."""
    settings = read_js("settings.js")
    assert 'archiveChoice() === "now" && !readFolderTree().length' \
        in settings
    folders = read_js("folders.js")
    assert 'const folder = archiveChoice() === "now"' in folders
    request = ("suggestFolders(description, sheetIndustry(),\n"
               "            folder)")
    assert request in folders
