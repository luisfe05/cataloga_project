"""Tests for learning the tree and the naming from an organized folder."""

import os

from backend.pipeline import folder_tree, learn_folder, naming


def harbor_root(root):
    """Luis's photo archive: five levels, event folders, a catch-all."""
    events = root / "HARBOR_SWIMMERS" / "FOTOS" / "EVENTOS_DEPORTIVOS"
    dawn_swim = events / "Dawn-Swim-Harbor-Club-PR_1997"
    trialo = events / "Harbor-Race_1998"
    fotos = root / "HARBOR_SWIMMERS" / "FOTOS"
    for folder in (dawn_swim, trialo, fotos / "ESCUELA", fotos / "SIN_TEMA",
                   root / "HARBOR_SWIMMERS" / "PRENSA", root / ".git"):
        folder.mkdir(parents=True)
    for i in range(1, 14):
        (dawn_swim / "Dawn-Swim-Harbor-Club-PR_1997_{}.tif"
         .format(i)).write_bytes(b"x")
    for i in range(1, 10):
        (trialo / "Harbor-Race_1998_{}.tif".format(i)).write_bytes(b"x")
    (root / "HARBOR_SWIMMERS" / "PRENSA" / "Articulo.pdf").write_bytes(b"x")
    (root / ".DS_Store").write_bytes(b"")
    (root / ".git" / "config").write_text("x")
    return root


def test_the_tree_is_read_as_it_is(tmp_path):
    """Five levels, in order, without hidden or tool folders."""
    result = learn_folder.learn(str(harbor_root(tmp_path / "HARBOR SWIMMERS")))
    tree = result["folder_tree"]
    assert folder_tree.all_paths(tree) == [
        "HARBOR_SWIMMERS", "HARBOR_SWIMMERS/FOTOS",
        "HARBOR_SWIMMERS/FOTOS/ESCUELA",
        "HARBOR_SWIMMERS/FOTOS/EVENTOS_DEPORTIVOS",
        "HARBOR_SWIMMERS/FOTOS/EVENTOS_DEPORTIVOS/"
        "Dawn-Swim-Harbor-Club-PR_1997",
        "HARBOR_SWIMMERS/FOTOS/EVENTOS_DEPORTIVOS/Harbor-Race_1998",
        "HARBOR_SWIMMERS/FOTOS/SIN_TEMA", "HARBOR_SWIMMERS/PRENSA"]
    assert result["folders"] == 8
    assert result["files"] == 23


def test_events_and_catch_all_are_marked(tmp_path):
    """EVENTOS_DEPORTIVOS holds Event_Year folders; SIN_TEMA catches all."""
    tree = learn_folder.learn(str(harbor_root(tmp_path / "p")))["folder_tree"]
    events = folder_tree.node_at(tree,
                                 "HARBOR_SWIMMERS/FOTOS/EVENTOS_DEPORTIVOS")
    assert events["events"] is True
    assert folder_tree.node_at(tree, "HARBOR_SWIMMERS/FOTOS/SIN_TEMA")[
        "fallback"] is True
    assert folder_tree.node_at(
        tree, "HARBOR_SWIMMERS/FOTOS")["events"] is False
    assert folder_tree.fallback_place(tree) == "HARBOR_SWIMMERS/FOTOS/SIN_TEMA"


def test_the_naming_of_the_photo_archive(tmp_path):
    """Title-Case words, _ between parts, event name, year and a number."""
    result = learn_folder.learn(str(harbor_root(tmp_path / "p")))
    assert result["naming_style"] == "title"
    assert "keep_accents" not in result
    assert result["event_numbering"] is True
    assert result["naming_template"] == naming.EVENT_TEMPLATE
    assert "event folder and a number" in result["description"]
    assert "Title-Case" in result["description"]
    assert len(result["examples"]) == 3
    assert result["examples"][0].endswith("_1997_1.tif")


def test_date_first_names(tmp_path):
    """A legal archive: 2026.07.15_Matter_Category_Description."""
    root = tmp_path / "legal"
    (root / "Caso 1").mkdir(parents=True)
    for i in range(5):
        (root / "Caso 1" / "2026.07.1{}_Garcia_Demanda_v01.pdf".format(i)
         ).write_bytes(b"x")
    result = learn_folder.learn(str(root))
    assert result["naming_template"] == "{date}_{topic}"
    assert result["naming_style"] == "title"
    assert "starts with its date" in result["description"]


def test_lowercase_names_with_accents(tmp_path):
    """notas-del-día.txt: lowercase; accents are not learned."""
    root = tmp_path / "web"
    (root / "notas").mkdir(parents=True)
    for name in ("notas-del-día.txt", "guión-rodaje.txt", "año-uno.txt"):
        (root / "notas" / name).write_text("x")
    result = learn_folder.learn(str(root))
    assert result["naming_style"] == "lower"
    assert "keep_accents" not in result


def test_nothing_on_disk_changes(tmp_path):
    """Learning only reads."""
    root = harbor_root(tmp_path / "p")
    before = sorted(str(p) for p in root.rglob("*"))
    learn_folder.learn(str(root))
    assert sorted(str(p) for p in root.rglob("*")) == before


def test_limits(tmp_path):
    """A huge folder gives at most 2000 entries and six levels."""
    root = tmp_path / "big"
    deep = root
    for level in range(8):
        deep = deep / "L{}".format(level)
    deep.mkdir(parents=True)
    for i in range(2100):
        (root / "f{:04d}.txt".format(i)).write_bytes(b"x")
    tree, names = learn_folder.read_structure(str(root))
    assert len(names) + len(folder_tree.all_paths(tree)) <= \
        learn_folder.MAX_ENTRIES
    assert folder_tree.depth_of(tree) <= folder_tree.MAX_DEPTH


# --- Route ---

def test_learn_route(empty_client, tmp_path):
    """The route answers the tree and naming, and saves nothing."""
    root = harbor_root(tmp_path / "p")
    response = empty_client.post("/projects/folders/learn",
                                 json={"folder": str(root)})
    assert response.status_code == 200
    data = response.get_json()
    assert data["folder_tree"][0]["name"] == "HARBOR_SWIMMERS"
    assert data["naming_style"] == "title"
    assert empty_client.get("/projects").get_json()["projects"] == []
    assert not (root / ".cataloga").exists()
    flat = tmp_path / "flat"
    flat.mkdir()
    (flat / "a.txt").write_text("x")
    response = empty_client.post("/projects/folders/learn",
                                 json={"folder": str(flat)})
    assert response.get_json()["error"]["code"] == "nothing_to_learn"
    response = empty_client.post("/projects/folders/learn",
                                 json={"folder": "/nowhere"})
    assert response.get_json()["error"]["code"] == "invalid_directory"


def test_learned_tree_creates_a_project_without_touching_folders(
        empty_client, tmp_path):
    """The learned tree can be the tree of an in-place project as it is."""
    root = harbor_root(tmp_path / "p")
    learned = empty_client.post("/projects/folders/learn",
                                json={"folder": str(root)}).get_json()
    response = empty_client.post("/projects", json={
        "name": "Harbor", "folder": str(root), "folder_mode": "place",
        "folders": learned["folder_tree"],
        "naming_template": learned["naming_template"],
        "naming_style": learned["naming_style"]})
    assert response.status_code == 201
    settings = empty_client.get("/settings").get_json()
    assert folder_tree.node_at(settings["folder_tree"],
                               "HARBOR_SWIMMERS/FOTOS/EVENTOS_DEPORTIVOS")[
        "events"] is True
    assert settings["naming_template"] == naming.EVENT_TEMPLATE
    assert settings["naming_style"] == "title"
    visible = sorted(n for n in os.listdir(str(root)) if not n.startswith("."))
    assert visible == ["HARBOR_SWIMMERS"]
    assert (root / ".cataloga").is_dir()
