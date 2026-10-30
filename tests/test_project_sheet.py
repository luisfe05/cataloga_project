"""Tests for the project sheet: the sample, the AI's answer, the routes."""

import json
import os

import pytest

from backend.pipeline import project_sheet
from backend.pipeline.ai_providers import base
from backend.pipeline.ai_providers.base import AIProviderClient
from backend.routes import settings as settings_routes
# The fixtures come along with the helpers.
from tests.test_project_folders import (FolderAI, drop, old_project,  # noqa
                                        tree_project)


def make_tree(root):
    """Build a small folder with files, hidden things, and a tool folder."""
    (root / "Prensa").mkdir(parents=True)
    (root / "Fotos" / "1997").mkdir(parents=True)
    (root / ".git").mkdir()
    (root / "node_modules" / "x").mkdir(parents=True)
    (root / "Prensa" / "articulo.txt").write_text("El Nuevo Dia, 1964. " * 200)
    (root / "Fotos" / "1997" / "IMG_0001.jpg").write_bytes(b"jpg")
    (root / ".DS_Store").write_bytes(b"")
    (root / ".git" / "config").write_text("x")
    (root / "node_modules" / "x" / "index.js").write_text("x")
    (root / "notas.txt").write_text("Notas del rodaje")
    return root


# --- The sample ---

def test_sample_skips_hidden_and_tool_folders(tmp_path):
    """Hidden files, .git and node_modules never reach the AI."""
    sample = project_sheet.project_sample(str(make_tree(tmp_path / "p")))
    assert sample["folders"] == ["Fotos", os.path.join("Fotos", "1997"),
                                 "Prensa"]
    assert sample["names"] == ["notas.txt",
                               os.path.join("Fotos", "1997", "IMG_0001.jpg"),
                               os.path.join("Prensa", "articulo.txt")]
    names = [name for name, text in sample["extracts"]]
    assert names == ["notas.txt", "articulo.txt"]


def test_sample_has_limits(tmp_path):
    """A huge folder gives a small sample: 60 folders, 40 names, 5 texts."""
    root = tmp_path / "big"
    for i in range(80):
        folder = root / "f{:02d}".format(i)
        folder.mkdir(parents=True)
        (folder / "a.txt").write_text("text " + str(i))
    sample = project_sheet.project_sample(str(root))
    assert len(sample["folders"]) == project_sheet.MAX_FOLDERS
    assert len(sample["names"]) == project_sheet.MAX_NAMES
    assert len(sample["extracts"]) == project_sheet.MAX_EXTRACTS
    assert all(len(text) <= project_sheet.EXTRACT_LENGTH
               for name, text in sample["extracts"])


def test_sample_stops_at_three_levels(tmp_path):
    """Deep folders are not walked; the sample stays small and quick."""
    deep = tmp_path / "p" / "a" / "b" / "c" / "d"
    deep.mkdir(parents=True)
    (deep / "x.txt").write_text("deep")
    sample = project_sheet.project_sample(str(tmp_path / "p"))
    assert os.path.join("a", "b", "c") in sample["folders"]
    assert os.path.join("a", "b", "c", "d") not in sample["folders"]
    assert sample["names"] == []


def test_sample_text_lists_everything():
    """The text the AI reads has the folders, the names and the extracts."""
    text = project_sheet.sample_text({
        "folders": ["Prensa"], "names": ["a.txt"],
        "extracts": [("a.txt", "Hello")]})
    assert text == ("Folders:\n  Prensa\nFile names:\n  a.txt\n"
                    "Extract of a.txt:\nHello")


# --- The answer ---

def test_answer_becomes_sheet_lines():
    """The JSON becomes one line per field, lists joined with commas."""
    sheet = project_sheet.parse_sheet_answer(json.dumps({
        "work": "A documentary about a swimmer.", "industry": "Legal",
        "parts": ["Research", "Shooting"], "file_types": ["scans"],
        "naming_style": "topic_date", "notes": None}))
    assert sheet == ("Work: A documentary about a swimmer.\n"
                     "Industry: legal\nParts: Research, Shooting\n"
                     "File types: scans\nNaming style: topic_date")
    assert project_sheet.sheet_industry(sheet) == "legal"


def test_unknown_industry_becomes_general():
    """An industry outside the list is saved as general."""
    sheet = project_sheet.parse_sheet_answer(
        '{"work": "x", "industry": "space mining"}')
    assert "Industry: general" in sheet


@pytest.mark.parametrize("answer", ["No idea.", '{"industry": "legal"}', ""])
def test_answer_without_work_is_unusable(answer):
    """A sheet needs at least what the work is."""
    assert project_sheet.parse_sheet_answer(answer) == ""


def test_clean_sheet_rules():
    """Spaces are trimmed, None is '', and a long sheet is refused."""
    assert project_sheet.clean_sheet("  Work: x  \n\n") == "Work: x"
    assert project_sheet.clean_sheet(None) == ""
    assert project_sheet.clean_sheet(42) is None
    assert project_sheet.clean_sheet("x" * 1501) is None


# --- The sheet in every request ---

def test_sheet_goes_into_the_metadata_prompt(tree_project):
    """With a sheet saved, the AI reads it before the file."""
    repo = tree_project["repo"]
    repo.save_config_value("project_sheet", "Work: A documentary.")
    tree_project["pipeline"].classify_document(
        drop(tree_project, "a.txt", "Text"))
    prompts = tree_project["ai"].prompts
    metadata_prompt = [p for p in prompts if "Project sheet" in p]
    assert len(metadata_prompt) == 1
    assert metadata_prompt[0].startswith(
        "Project sheet (what this work is):\nWork: A documentary.\n\n")


def test_without_a_sheet_the_prompt_is_unchanged(tree_project):
    """No sheet, no prefix."""
    tree_project["pipeline"].classify_document(
        drop(tree_project, "a.txt", "Text"))
    assert not any("Project sheet" in p for p in tree_project["ai"].prompts)


# --- Routes ---

class SheetAI(AIProviderClient):
    """Fake AI that answers the sheet request and keeps the sample."""

    def __init__(self, answer):
        super().__init__(provider_name="fake", model="fake-model")
        self.api_key = "test-key"
        self.answer = answer
        self.texts = []

    def send_prompt(self, system_prompt, text):
        self.texts.append(text)
        return self.answer


def test_suggest_sheet_reads_the_folder_and_saves_nothing(
        flask_client, app, tmp_path, monkeypatch):
    """The sample of the given folder goes to the AI; nothing is saved."""
    folder = make_tree(tmp_path / "web")
    ai = SheetAI('{"work": "A website.", "industry": "web and code"}')
    monkeypatch.setattr(settings_routes, "create_client",
                        lambda name, model: ai)
    response = flask_client.post("/settings/sheet/suggest",
                                 json={"folder": str(folder)})
    assert response.status_code == 200
    assert response.get_json()["sheet"] == ("Work: A website.\n"
                                            "Industry: web and code")
    assert "Prensa" in ai.texts[0] and "node_modules" not in ai.texts[0]
    assert flask_client.get("/settings").get_json()["project_sheet"] == ""


def test_suggest_sheet_uses_the_active_project_by_default(
        flask_client, app, monkeypatch):
    """Without a folder, the active project's folder is sampled."""
    ai = SheetAI('{"work": "Research."}')
    monkeypatch.setattr(settings_routes, "create_client",
                        lambda name, model: ai)
    (os.path.join(app.config["PROJECT_FOLDER"], "Drop Zone"))
    response = flask_client.post("/settings/sheet/suggest", json={})
    assert response.status_code == 200
    assert "Drop Zone" in ai.texts[0]


def test_suggest_sheet_errors(flask_client, monkeypatch):
    """A missing folder, no key, or a useless answer give clear errors."""
    response = flask_client.post("/settings/sheet/suggest",
                                 json={"folder": "/nowhere/at/all"})
    assert response.get_json()["error"]["code"] == "invalid_directory"
    no_key = SheetAI("x")
    no_key.api_key = None
    monkeypatch.setattr(settings_routes, "create_client",
                        lambda name, model: no_key)
    response = flask_client.post("/settings/sheet/suggest", json={})
    assert response.get_json()["error"]["code"] == "no_provider"
    monkeypatch.setattr(settings_routes, "create_client",
                        lambda name, model: SheetAI("No idea."))
    response = flask_client.post("/settings/sheet/suggest", json={})
    assert response.status_code == 502


def test_sheet_is_saved_with_settings(flask_client):
    """PUT /settings saves the sheet; a long one is refused."""
    response = flask_client.put("/settings", json={
        "research_name": "Research", "project_sheet": "Work: x\n"})
    assert response.status_code == 200
    assert response.get_json()["project_sheet"] == "Work: x"
    assert flask_client.get("/settings").get_json()["project_sheet"] == \
        "Work: x"
    response = flask_client.put("/settings", json={
        "research_name": "Research", "project_sheet": "x" * 1501})
    assert response.get_json()["error"]["code"] == "invalid_sheet"


def test_new_project_can_start_with_a_sheet(empty_client, tmp_path):
    """The sheet typed before Create project is saved with it."""
    folder = tmp_path / "New"
    folder.mkdir()
    response = empty_client.post("/projects", json={
        "name": "New", "folder": str(folder),
        "folders": [{"name": "Docs", "subcategories": []}],
        "project_sheet": "Work: a new one"})
    assert response.status_code == 201
    assert empty_client.get("/settings").get_json()["project_sheet"] == \
        "Work: a new one"
