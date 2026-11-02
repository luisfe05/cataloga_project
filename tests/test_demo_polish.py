"""Tests for the scan state per project, the preview overlay and the port."""

import os
import socket
import threading

from PIL import Image
from pypdf import PdfWriter

import main
from backend import folder_watcher, scanner
from backend.config import projects
from backend.models.document import Document
from backend.pipeline import file_readers, previews
from tests.conftest import TEST_TOKEN
# The fixtures come along with the helpers.
from tests.test_folder_watcher import FakeAI, fake_ai  # noqa: F401
from tests.test_scanner import place_project


def some_files(root, count=3):
    """A project folder with a few text files."""
    root.mkdir(exist_ok=True)
    for index in range(count):
        (root / "{}.txt".format(index)).write_text("Letter {}".format(index))
    return root


# --- The scan, per project ---

def test_a_folder_never_read_says_so(tmp_path):
    """No file read yet: the screen offers Catalog files."""
    root = some_files(tmp_path / "p")
    state = scanner.scan_view(scanner.ScanJob(), place_project(root),
                              str(root))
    assert (state["status"], state["done"], state["total"]) == ("unread", 0, 3)


def test_a_scan_cut_short_says_where_it_stopped(tmp_path):
    """The app closed in the middle: read 1 of 3, Resume goes on."""
    root = some_files(tmp_path / "p")
    repo = place_project(root)
    job = scanner.ScanJob()
    scanner.scan_folder(job, str(root), repo, FakeAI())
    repo.delete_document(repo.get_all_documents()[0].id)
    repo.delete_document(repo.get_all_documents()[0].id)
    repo.save_config_value("scan_state", scanner.SCAN_RUNNING)
    state = scanner.scan_view(scanner.ScanJob(), repo, str(root))
    assert state["status"] == "stopped"
    assert (state["done"], state["total"]) == (1, 3)


def test_a_job_whose_thread_died_does_not_look_alive(tmp_path):
    """Status running with no thread behind it is a stopped scan."""
    root = some_files(tmp_path / "p")
    repo = place_project(root)
    job = scanner.ScanJob()
    job.status, job.folder, job.done, job.total = "running", str(root), 1, 3
    job.current = "stuck.pdf"
    state = scanner.scan_view(job, repo, str(root))
    assert state["status"] == "unread" and state["current"] == ""


def test_the_job_of_another_project_is_not_shown(tmp_path):
    """One job per app: a running scan of A says nothing about B."""
    first = some_files(tmp_path / "a")
    second = some_files(tmp_path / "b", 2)
    place_project(first)
    release = threading.Event()
    job = scanner.ScanJob()
    job.status, job.folder = "running", str(first)
    job.thread = threading.Thread(target=release.wait, daemon=True)
    job.thread.start()
    state = scanner.scan_view(job, place_project(second), str(second))
    release.set()
    assert state["status"] == "unread" and state["total"] == 2
    assert state["folder"] == str(second)


def test_a_finished_scan_shows_nothing_to_do(tmp_path):
    """Done is saved in the catalog, so a new start knows it."""
    root = some_files(tmp_path / "p")
    repo = place_project(root)
    scanner.scan_folder(scanner.ScanJob(), str(root), repo, FakeAI())
    assert repo.scan_state() == scanner.SCAN_DONE
    assert scanner.scan_view(scanner.ScanJob(), repo,
                             str(root))["status"] == "idle"


def test_the_watcher_waits_for_a_scan_that_never_finished(tmp_path):
    """Files stay unread until Resume or Catalog files; then it watches."""
    root = some_files(tmp_path / "p")
    repo = place_project(root)
    projects_path = str(tmp_path / "app" / "projects.json")
    projects.add_project(projects_path, "P", str(root))
    assert folder_watcher.scan_once(projects_path) == []
    assert repo.get_all_documents() == []
    scanner.scan_folder(scanner.ScanJob(), str(root), repo, FakeAI())
    (root / "new.txt").write_text("A new letter")
    found = folder_watcher.scan_once(projects_path)
    assert [doc.original_filename for doc in found] == ["new.txt"]


def test_an_old_catalog_with_everything_read_counts_as_finished(tmp_path):
    """No saved state and nothing unread: done, and it is saved."""
    root = some_files(tmp_path / "p")
    repo = place_project(root)
    scanner.scan_folder(scanner.ScanJob(), str(root), repo, FakeAI())
    repo.save_config_value("scan_state", None)
    assert scanner.needs_scan(repo, str(root)) is False
    assert repo.scan_state() == scanner.SCAN_DONE


def test_scan_route_for_an_unread_project(flask_client, app):
    """GET /scan and GET /plan both tell about the unread files."""
    root = app.config["PROJECT_FOLDER"]
    from backend.db.catalog_repository import CatalogRepository
    repo = CatalogRepository(projects.catalog_path(root))
    repo.save_folder_tree("Research", [{"name": "Prensa"}])
    repo.save_config_value("folder_mode", "place")
    with open(os.path.join(root, "a.txt"), "w") as file:
        file.write("A letter")
    state = flask_client.get("/scan").get_json()
    assert state["status"] == "unread" and state["total"] == 1
    assert flask_client.get("/plan").get_json()["unread"] == 1


def test_start_refuses_while_another_project_is_read(flask_client, app):
    """The one job is busy with a different folder."""
    from backend.db.catalog_repository import CatalogRepository
    root = app.config["PROJECT_FOLDER"]
    repo = CatalogRepository(projects.catalog_path(root))
    repo.save_folder_tree("Research", [{"name": "Prensa"}])
    repo.save_config_value("folder_mode", "place")
    job = scanner.ScanJob()
    job.folder = "/somewhere/else"
    job.is_running = lambda: True
    app.config["SCAN"] = job
    response = flask_client.post("/scan/start")
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "scan_running"


# --- The preview ---

def add_file(app, name, content=b"x"):
    """Save a file in the project with its row; return (path, id)."""
    from backend.db.catalog_repository import CatalogRepository
    root = app.config["PROJECT_FOLDER"]
    path = os.path.join(root, name)
    with open(path, "wb") as file:
        file.write(content)
    repo = CatalogRepository(projects.catalog_path(root))
    doc = repo.add_document(Document(name, name, "Documents", path,
                                     "2026-11-01T10:00:00"))
    return path, doc.id


def test_preview_kinds(tmp_path, monkeypatch):
    """Each family has its kind; secrets and iCloud files show nothing."""
    (tmp_path / "a.txt").write_text("Text")
    (tmp_path / "b.bin").write_bytes(b"\x00\x01\x02" * 50)
    (tmp_path / "credentials.json").write_text("{}")
    for name in ("a.jpg", "a.tiff", "a.pdf", "a.mp3", "a.mov", "a.docx"):
        (tmp_path / name).write_bytes(b"x")
    kinds = {name: previews.preview_kind(str(tmp_path / name))
             for name in os.listdir(str(tmp_path))}
    assert kinds == {"a.txt": "text", "b.bin": "none",
                     "credentials.json": "none", "a.jpg": "image",
                     "a.tiff": "image", "a.pdf": "pdf", "a.mp3": "audio",
                     "a.mov": "video", "a.docx": "office"}
    monkeypatch.setattr(file_readers, "in_cloud_only", lambda path: True)
    assert previews.preview_kind(str(tmp_path / "a.txt")) == "none"


def test_preview_of_a_photo_a_pdf_and_text(flask_client, app, tmp_path):
    """A TIFF and a PDF's first page come as JPEG; text comes as text."""
    picture = tmp_path / "p.tif"
    Image.new("RGB", (40, 30), "white").save(str(picture))
    doc_id = add_file(app, "p.tif", picture.read_bytes())[1]
    answer = flask_client.get("/documents/{}/preview".format(doc_id)
                              ).get_json()
    assert answer["kind"] == "image" and answer["filename"] == "p.tif"
    assert answer["image"].startswith("data:image/jpeg;base64,")

    writer = PdfWriter()
    writer.add_blank_page(100, 100)
    writer.add_blank_page(100, 100)
    pdf = tmp_path / "d.pdf"
    with open(str(pdf), "wb") as file:
        writer.write(file)
    doc_id = add_file(app, "d.pdf", pdf.read_bytes())[1]
    answer = flask_client.get("/documents/{}/preview".format(doc_id)
                              ).get_json()
    assert answer["kind"] == "image"

    doc_id = add_file(app, "n.txt", b"Hello there")[1]
    answer = flask_client.get("/documents/{}/preview".format(doc_id)
                              ).get_json()
    assert answer == {"kind": "text", "text": "Hello there",
                      "filename": "n.txt"}


def test_preview_of_a_missing_file(flask_client, app):
    """The file left: 409, like the other file actions."""
    path, doc_id = add_file(app, "gone.txt")
    os.remove(path)
    response = flask_client.get("/documents/{}/preview".format(doc_id))
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "file_missing"


def test_a_recording_takes_the_token_in_its_address(app, flask_client):
    """A player sends no headers; it can seek; only this route allows it."""
    doc_id = add_file(app, "a.mp3", b"0123456789")[1]
    url = "/documents/{}/media".format(doc_id)
    bare = app.test_client()
    assert bare.get(url).status_code == 401
    assert bare.get(url + "?token=wrong").status_code == 401
    answer = bare.get(url + "?token=" + TEST_TOKEN)
    assert answer.status_code == 200 and answer.data == b"0123456789"
    part = bare.get(url + "?token=" + TEST_TOKEN,
                    headers={"Range": "bytes=2-4"})
    assert part.status_code == 206 and part.data == b"234"
    # The token in an address opens nothing else.
    assert bare.get("/documents?token=" + TEST_TOKEN).status_code == 401
    other = "/documents/{}/preview?token={}".format(doc_id, TEST_TOKEN)
    assert bare.get(other).status_code == 401


def test_media_route_only_serves_recordings(flask_client, app):
    """A document is not streamed by this route."""
    doc_id = add_file(app, "a.txt", b"text")[1]
    response = flask_client.get("/documents/{}/media".format(doc_id))
    assert response.status_code == 404


# --- The port ---

def test_port_in_use():
    """True while something listens, so a second app can say so."""
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        port = server.getsockname()[1]
        assert main.port_in_use(port) is True
    assert main.port_in_use(port) is False


# --- Opening a folder that already has a catalog ---

def test_opening_an_in_place_project_makes_no_folders(empty_client, tmp_path):
    """A second account adds the folder: nothing appears on the disk."""
    root = some_files(tmp_path / "p")
    place_project(root).save_tree([{"name": "Prensa"}])
    before = sorted(os.listdir(str(root)))
    response = empty_client.post("/projects", json={
        "name": "Otra", "folder": str(root)})
    assert response.status_code == 201
    assert response.get_json()["opened_existing"] is True
    assert sorted(os.listdir(str(root))) == before
    assert empty_client.get("/scan").get_json()["status"] == "unread"
