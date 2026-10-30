"""Tests for the archive conventions by industry and the folder check."""

import pytest

from backend.pipeline import conventions
from backend.pipeline.ai_providers import base
from backend.routes import projects as project_routes
from tests.test_project_folders import SuggestAI


def test_every_industry_is_complete():
    """Each industry has folders, a naming template, and rules."""
    for name, entry in conventions.CONVENTIONS.items():
        assert set(entry) == {"folders", "naming", "rules"}, name
        assert isinstance(entry["folders"], list)
        assert "{" in entry["naming"]
    assert conventions.industries()[-1] == "general"
    assert conventions.conventions_for("LEGAL ")["rules"]["date_first"]
    assert conventions.conventions_for("space mining") == \
        conventions.CONVENTIONS["general"]


def test_folder_hints_name_the_usual_folders():
    """The tree request gets the field's folders; general gets nothing."""
    hints = conventions.folder_hints("legal")
    assert "01_Pleadings" in hints and "06_Billing_Admin" in hints
    assert conventions.folder_hints("general") == ""
    assert conventions.folder_hints("") == ""


def make_site(root):
    """A small website: index.html, css and js folders, and a .git."""
    (root / "css").mkdir(parents=True)
    (root / "js").mkdir()
    (root / ".git").mkdir()
    (root / "index.html").write_text("<html></html>")
    (root / "css" / "site.css").write_text("body {}")
    return root


def test_markers_find_a_website_and_not_a_pdf_folder(tmp_path):
    """index.html, css and js mark a site; a folder of PDFs is clean."""
    site = make_site(tmp_path / "site")
    result = conventions.inspect_folder(str(site))
    assert result["markers"] == [".git", "css", "index.html", "js"]
    assert result["linked_kind"] == "web and code"
    assert result["catalog_only_recommended"] is True
    assert result["industry"] == "web and code"

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.pdf").write_bytes(b"%PDF")
    result = conventions.inspect_folder(str(docs))
    assert result == {"markers": [], "linked_kind": "",
                      "catalog_only_recommended": False, "industry": ""}


def test_markers_find_edit_and_design_projects_one_level_down(tmp_path):
    """A Premiere project in a subfolder counts; three levels down not."""
    root = tmp_path / "film"
    (root / "Edit").mkdir(parents=True)
    (root / "Edit" / "cut.prproj").write_bytes(b"x")
    result = conventions.inspect_folder(str(root))
    assert result["linked_kind"] == "film and video"
    assert result["industry"] == "film and video"

    deep = tmp_path / "deep" / "a" / "b"
    deep.mkdir(parents=True)
    (deep / "book.indd").write_bytes(b"x")
    assert conventions.inspect_folder(str(tmp_path / "deep"))["markers"] == []


# --- Routes ---

def test_inspect_route(empty_client, tmp_path):
    """The route checks the folder and answers what it looks like."""
    site = make_site(tmp_path / "site")
    response = empty_client.post("/projects/folders/inspect",
                                 json={"folder": str(site)})
    assert response.status_code == 200
    assert response.get_json()["catalog_only_recommended"] is True
    response = empty_client.post("/projects/folders/inspect",
                                 json={"folder": "/nowhere/at/all"})
    assert response.get_json()["error"]["code"] == "invalid_directory"
    response = empty_client.post("/projects/folders/inspect", json={})
    assert response.get_json()["error"]["code"] == "missing_field"


@pytest.mark.parametrize("industry, expected", [
    ("legal", "01_Pleadings"), ("", "Respond with ONLY"),
])
def test_suggest_folders_adds_the_industry_folders(empty_client, monkeypatch,
                                                   industry, expected):
    """With an industry, the tree request lists its usual folders."""
    ai = SuggestAI('[{"name": "Caso 1", "subfolders": []}]')
    monkeypatch.setattr(project_routes, "create_client",
                        lambda name, model: ai)
    response = empty_client.post("/projects/folders/suggest", json={
        "description": "Archivo legal", "industry": industry})
    assert response.status_code == 200
    assert expected in ai.prompts[0]
    assert ai.prompts[0].startswith(base.FOLDERS_PROMPT)
    assert ("01_Pleadings" in ai.prompts[0]) == (industry == "legal")
