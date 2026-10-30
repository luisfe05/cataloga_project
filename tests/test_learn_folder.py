"""Tests for learning the tree and the naming from an organized folder."""

import os

from backend.pipeline import folder_tree, learn_folder, naming


def delfin(root):
    """Luis's photo archive: five levels, event folders, a catch-all."""
    events = root / "INVESTIGACION" / "FOTOS" / "EVENTOS_DEPORTIVOS"
    juegos = events / "Juegos-Nacionales-Olimpiadas-Especiales-PR_1997"
    trialo = events / "Trialo-Isla-Verde_1998"
    fotos = root / "INVESTIGACION" / "FOTOS"
    for folder in (juegos, trialo, fotos / "ESCUELA", fotos / "SIN_TEMA",
                   root / "INVESTIGACION" / "PRENSA", root / ".git"):
        folder.mkdir(parents=True)
    for i in range(1, 14):
        (juegos / "Juegos-Nacionales-Olimpiadas-Especiales-PR_1997_{}.tif"
         .format(i)).write_bytes(b"x")
    for i in range(1, 10):
        (trialo / "Trialo-Isla-Verde_1998_{}.tif".format(i)).write_bytes(b"x")
    (root / "INVESTIGACION" / "PRENSA" / "Articulo.pdf").write_bytes(b"x")
    (root / ".DS_Store").write_bytes(b"")
    (root / ".git" / "config").write_text("x")
    return root


def test_the_tree_is_read_as_it_is(tmp_path):
    """Five levels, in order, without hidden or tool folders."""
    result = learn_folder.learn(str(delfin(tmp_path / "EL DELFIN")))
    tree = result["folder_tree"]
    assert folder_tree.all_paths(tree) == [
        "INVESTIGACION", "INVESTIGACION/FOTOS",
        "INVESTIGACION/FOTOS/ESCUELA",
        "INVESTIGACION/FOTOS/EVENTOS_DEPORTIVOS",
        "INVESTIGACION/FOTOS/EVENTOS_DEPORTIVOS/"
        "Juegos-Nacionales-Olimpiadas-Especiales-PR_1997",
        "INVESTIGACION/FOTOS/EVENTOS_DEPORTIVOS/Trialo-Isla-Verde_1998",
        "INVESTIGACION/FOTOS/SIN_TEMA", "INVESTIGACION/PRENSA"]
    assert result["folders"] == 8
    assert result["files"] == 23


def test_events_and_catch_all_are_marked(tmp_path):
    """EVENTOS_DEPORTIVOS holds Event_Year folders; SIN_TEMA catches all."""
    tree = learn_folder.learn(str(delfin(tmp_path / "p")))["folder_tree"]
    events = folder_tree.node_at(tree,
                                 "INVESTIGACION/FOTOS/EVENTOS_DEPORTIVOS")
    assert events["events"] is True
    assert folder_tree.node_at(tree, "INVESTIGACION/FOTOS/SIN_TEMA")[
        "fallback"] is True
    assert folder_tree.node_at(tree, "INVESTIGACION/FOTOS")["events"] is False
    assert folder_tree.fallback_place(tree) == "INVESTIGACION/FOTOS/SIN_TEMA"


def test_the_naming_of_the_photo_archive(tmp_path):
    """Title-Case words, _ between parts, event name, year and a number."""
    result = learn_folder.learn(str(delfin(tmp_path / "p")))
    assert result["naming_style"] == "title"
    assert result["keep_accents"] is False
    assert result["event_numbering"] is True
    assert result["naming_template"] == naming.KEEP_NAMES
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
    """notas-del-día.txt: lowercase, accents kept."""
    root = tmp_path / "web"
    (root / "notas").mkdir(parents=True)
    for name in ("notas-del-día.txt", "guión-rodaje.txt", "año-uno.txt"):
        (root / "notas" / name).write_text("x")
    result = learn_folder.learn(str(root))
    assert result["naming_style"] == "lower"
    assert result["keep_accents"] is True


def test_nothing_on_disk_changes(tmp_path):
    """Learning only reads."""
    root = delfin(tmp_path / "p")
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
    root = delfin(tmp_path / "p")
    response = empty_client.post("/projects/folders/learn",
                                 json={"folder": str(root)})
    assert response.status_code == 200
    data = response.get_json()
    assert data["folder_tree"][0]["name"] == "INVESTIGACION"
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
    root = delfin(tmp_path / "p")
    learned = empty_client.post("/projects/folders/learn",
                                json={"folder": str(root)}).get_json()
    response = empty_client.post("/projects", json={
        "name": "Delfin", "folder": str(root), "folder_mode": "place",
        "folders": learned["folder_tree"],
        "naming_template": learned["naming_template"],
        "naming_style": learned["naming_style"],
        "keep_accents": learned["keep_accents"]})
    assert response.status_code == 201
    settings = empty_client.get("/settings").get_json()
    assert folder_tree.node_at(settings["folder_tree"],
                               "INVESTIGACION/FOTOS/EVENTOS_DEPORTIVOS")[
        "events"] is True
    assert settings["naming_template"] == "keep"
    assert settings["naming_style"] == "title"
    visible = sorted(n for n in os.listdir(str(root)) if not n.startswith("."))
    assert visible == ["INVESTIGACION"]
    assert (root / ".cataloga").is_dir()
