"""Tests for the time limits: a file that hangs never stops a scan."""

import logging
import os
import threading
import time

import pytest

from backend import scanner
from backend.config import app_log, projects
from backend.db.catalog_repository import CatalogRepository
from backend.pipeline import (archive_rules, classification_pipeline,
                              file_readers, time_budget)
from backend.pipeline.ai_providers import base, ollama_cloud
from backend.pipeline.classification_pipeline import ClassificationPipeline
from backend.pipeline.file_organizer import FileOrganizer
# The fixtures come along with the helpers.
from tests.test_folder_watcher import FakeAI, card_answer  # noqa: F401
from tests.test_folder_watcher import fake_ai  # noqa: F401
from tests.test_scanner import TREE, place_project


# Released at the end of each test, so no stuck thread stays behind.
@pytest.fixture
def release():
    event = threading.Event()
    yield event
    event.set()


class HangingAI(FakeAI):
    """Hangs on a file whose text has the word HANG; answers the others."""

    def __init__(self, release):
        super().__init__()
        self.release = release

    def send_prompt(self, system_prompt, text):
        if "HANG" in text:
            self.release.wait(30)
        return super().send_prompt(system_prompt, text)


class ImageAI(FakeAI):
    """Answers about images with the answers it was given, in order."""

    supports_images = True

    def __init__(self, answers):
        super().__init__()
        self.answers = list(answers)
        self.prompts = []

    def send_images(self, prompt, image_uris):
        self.prompts.append(prompt)
        return self.answers.pop(0)


def three_files(root):
    """A good file, one that hangs, and another good one, in that order."""
    root.mkdir(exist_ok=True)
    (root / "a.txt").write_text("A letter")
    (root / "b.txt").write_text("HANG on this one")
    (root / "c.txt").write_text("Another letter")
    return root


def rows_by_name(repo):
    """Return the catalog's documents by original name."""
    return {doc.original_filename: doc for doc in repo.get_all_documents()}


def pipeline_for(root, repo, ai):
    """Build a pipeline that reads a folder in place."""
    return ClassificationPipeline(ai, repo, FileOrganizer(str(root)),
                                  in_place=True)


# --- A file that hangs ---

def test_a_hanging_ai_skips_the_file_and_the_scan_goes_on(
        tmp_path, monkeypatch, release):
    """The hung file is in Manual Review; the next file is cataloged."""
    monkeypatch.setattr(time_budget, "FILE_SECONDS", 0.5)
    root = three_files(tmp_path / "p")
    repo = place_project(root)
    job = scanner.ScanJob()
    scanner.scan_folder(job, str(root), repo, HangingAI(release))
    rows = rows_by_name(repo)
    assert job.status == "done" and job.done == 3
    assert rows["b.txt"].status == "Manual Review"
    assert rows["b.txt"].review_note == "Timed out while reading"
    assert rows["c.txt"].summary and rows["a.txt"].summary


def test_work_left_behind_writes_nothing(tmp_path, monkeypatch, release):
    """When the stuck AI finally answers, there is still only one row."""
    monkeypatch.setattr(time_budget, "FILE_SECONDS", 0.3)
    root = three_files(tmp_path / "p")
    repo = place_project(root)
    job = scanner.ScanJob()
    scanner.scan_folder(job, str(root), repo, HangingAI(release))
    before = threading.active_count()
    release.set()
    # The stuck thread wakes up, sees it was abandoned, and ends.
    for _ in range(100):
        if threading.active_count() < before:
            break
        time.sleep(0.02)
    assert threading.active_count() < before
    names = [doc.original_filename for doc in repo.get_all_documents()]
    assert sorted(names) == ["a.txt", "b.txt", "c.txt"]
    assert rows_by_name(repo)["b.txt"].summary is None


def test_a_hanging_read_of_the_file_is_skipped_too(
        tmp_path, monkeypatch, release):
    """A stuck read on the disk, before any AI call, has the same limit."""
    monkeypatch.setattr(time_budget, "FILE_SECONDS", 0.3)
    original = classification_pipeline.extract_text

    def stuck(path):
        if path.endswith("stuck.pdf"):
            release.wait(30)
        return original(path)

    monkeypatch.setattr(classification_pipeline, "extract_text", stuck)
    root = tmp_path / "p"
    root.mkdir()
    (root / "stuck.pdf").write_bytes(b"%PDF-1.4 nothing")
    (root / "z.txt").write_text("A letter")
    repo = place_project(root)
    job = scanner.ScanJob()
    scanner.scan_folder(job, str(root), repo, FakeAI())
    rows = rows_by_name(repo)
    assert rows["stuck.pdf"].review_note == archive_rules.TIMEOUT_NOTE
    assert rows["z.txt"].summary


def test_a_second_scan_does_not_read_a_timed_out_file_again(
        tmp_path, monkeypatch, release):
    """The index knows it: only Retry reads it again."""
    monkeypatch.setattr(time_budget, "FILE_SECONDS", 0.3)
    root = three_files(tmp_path / "p")
    repo = place_project(root)
    ai = HangingAI(release)
    scanner.scan_folder(scanner.ScanJob(), str(root), repo, ai)
    calls = []
    monkeypatch.setattr(ai, "send_prompt",
                        lambda system, text: calls.append(text))
    scanner.scan_folder(scanner.ScanJob(), str(root), repo, ai)
    assert calls == []


def test_process_batch_has_the_limit_too(tmp_path, monkeypatch, release):
    """Files of a Drop Zone go through the same limit."""
    monkeypatch.setattr(time_budget, "FILE_SECONDS", 0.3)
    root = three_files(tmp_path / "p")
    repo = place_project(root)
    docs = pipeline_for(root, repo, HangingAI(release)).process_batch(
        [str(root / "b.txt"), str(root / "c.txt")])
    assert docs[0].review_note == archive_rules.TIMEOUT_NOTE
    assert docs[1].summary


# --- The budget ---

def test_the_budget_stops_retries_with_little_time_left():
    """A failed call with under 10 s left is not tried again."""
    calls = []

    class Failing(FakeAI):
        def send_prompt(self, system_prompt, text):
            calls.append(text)
            raise RuntimeError("busy")

    with pytest.raises(time_budget.TimedOut):
        time_budget.run_limited(lambda: Failing().ask("p", "t"), seconds=5)
    assert len(calls) == 1


def test_each_call_gets_only_the_time_that_is_left(monkeypatch):
    """Late in a file, the call's timeout shrinks with the budget."""
    created = {}
    answer = type("Answer", (), {"choices": [type("Choice", (), {
        "message": type("Message", (), {"content": "ok"})})]})

    class FakeSDK:
        def __init__(self, **options):
            created.update(options)
            self.chat = self
            self.completions = self

        def create(self, **options):
            created.update(options)
            return answer

    monkeypatch.setattr(ollama_cloud, "OpenAI", FakeSDK)
    client = ollama_cloud.OllamaCloudClient()
    time_budget.run_limited(lambda: client.send_prompt("p", "t"), seconds=30)
    assert 0 < created["timeout"] <= 30
    assert created["max_retries"] == 1
    # Inside a file the answer is a short card.
    assert created["max_tokens"] == base.CARD_TOKENS
    client.send_images(base.IMAGE_PROMPT, ["data:image/jpeg;base64,QUJD"])
    assert created["max_tokens"] == base.IMAGE_TOKENS
    assert created["timeout"] == time_budget.CALL_SECONDS
    client.send_images(base.DESCRIPTION_PROMPT,
                       ["data:image/jpeg;base64,QUJD"])
    assert created["max_tokens"] == base.DESCRIPTION_TOKENS


# --- An answer cut off by its limit ---

def scanned_pdf(root, monkeypatch):
    """A PDF with no text, whose first page is one image for the AI."""
    root.mkdir()
    path = root / "scan.pdf"
    path.write_bytes(b"%PDF-1.4 nothing")
    monkeypatch.setattr(file_readers, "pdf_page_data_uris",
                        lambda p: ["data:image/jpeg;base64,QUJD"])
    return path


def test_a_cut_off_answer_asks_for_a_description(tmp_path, monkeypatch):
    """The second, short request gives enough to make the card."""
    path = scanned_pdf(tmp_path / "p", monkeypatch)
    repo = place_project(tmp_path / "p")
    ai = ImageAI(['{"text": "Me dejé llevar por los nervios. Me dejé',
                  '{"text": null, "description": "A 2006 newspaper page."}'])
    doc = pipeline_for(tmp_path / "p", repo, ai).classify_document(str(path))
    assert ai.prompts == [base.IMAGE_PROMPT, base.DESCRIPTION_PROMPT]
    assert doc.status == "Classified" and doc.summary


def test_the_short_answer_names_the_publication_and_the_date(
        tmp_path, monkeypatch):
    """What the card prompt reads says the publication and printed date."""
    path = scanned_pdf(tmp_path / "p", monkeypatch)
    repo = place_project(tmp_path / "p")
    ai = ImageAI(['{"text": "cut', '{"text": null, "description": "A page '
                  'on a swim meet.", "source": "El Nuevo Dia", '
                  '"printed_date": "19 de julio de 2006"}'])
    seen = []
    original = ai.send_prompt

    def record(system_prompt, text):
        seen.append(text)
        return original(system_prompt, text)

    ai.send_prompt = record
    doc = pipeline_for(tmp_path / "p", repo, ai).classify_document(str(path))
    assert "Publication printed on the page: El Nuevo Dia." in seen[0]
    assert "Date printed on the page: 19 de julio de 2006." in seen[0]
    # Whatever the card says, the page decides the source and the date.
    assert doc.source == "El Nuevo Dia"
    assert doc.document_date == "2006-07-19"
    assert "folio line" in base.DESCRIPTION_PROMPT
    assert "not\n  the publication" in base.DESCRIPTION_PROMPT


def test_a_capitalized_publication_is_title_cased(tmp_path, monkeypatch):
    """EL NUEVO DIA in the folio line is saved as El Nuevo Dia."""
    path = scanned_pdf(tmp_path / "p", monkeypatch)
    repo = place_project(tmp_path / "p")
    ai = ImageAI(['{"text": "cut', '{"text": null, "description": "A page.",'
                  ' "source": "EL NUEVO DIA", "printed_date": null}'])
    doc = pipeline_for(tmp_path / "p", repo, ai).classify_document(str(path))
    assert doc.source == "El Nuevo Dia"


@pytest.mark.parametrize("text, expected", [
    ("MIÉRCOLES, 19 DE JULIO DE 2006", "2006-07-19"),
    ("JUEVES, 03 DE AGOSTO DE 2006", "2006-08-03"),
    ("July 19, 2006", "2006-07-19"),
    ("Nov 13 1997", "1997-11-13"),
    ("13 nov 97", "1997-11-13"),
    ("noviembre de 1997", "1997-11"),
])
def test_printed_dates_with_the_day_before_the_month(text, expected):
    """Spanish folio lines and English dates with a comma."""
    assert archive_rules.stamp_date(text) == expected


def test_recordings_get_a_longer_limit(tmp_path, monkeypatch):
    """Audio and video have 300 s; documents and photos 120 s."""
    given = []

    def fake_run(work, seconds=None):
        given.append(seconds)
        return work()

    monkeypatch.setattr(time_budget, "run_limited", fake_run)
    root = tmp_path / "p"
    root.mkdir()
    (root / "a.txt").write_text("A letter")
    (root / "b.mp3").write_bytes(b"not really audio")
    repo = place_project(root)
    pipeline = pipeline_for(root, repo, FakeAI())
    pipeline.classify_within_limit(str(root / "a.txt"))
    pipeline.classify_within_limit(str(root / "b.mp3"))
    assert given == [120, 300]
    assert time_budget.MEDIA_SECONDS == 300


def test_cut_off_twice_says_so(tmp_path, monkeypatch):
    """Without any answer the file says why it needs a person."""
    path = scanned_pdf(tmp_path / "p", monkeypatch)
    repo = place_project(tmp_path / "p")
    ai = ImageAI(['{"text": "cut', '{"text": null, "desc'])
    doc = pipeline_for(tmp_path / "p", repo, ai).classify_document(str(path))
    assert doc.status == "Manual Review"
    assert doc.review_note == "AI answer was cut off"


# --- iCloud ---

def test_a_file_only_in_icloud_is_cataloged_by_name_without_opening(
        tmp_path, monkeypatch):
    """No hash and no AI: opening it would download it."""
    root = tmp_path / "p"
    root.mkdir()
    (root / "far.pdf").write_bytes(b"x")
    repo = place_project(root)
    ai = FakeAI()
    monkeypatch.setattr(file_readers, "in_cloud_only", lambda path: True)

    def must_not_open(path):
        raise AssertionError("the file was opened")

    monkeypatch.setattr(archive_rules, "sha256_of", must_not_open)
    doc = pipeline_for(root, repo, ai).classify_document(
        str(root / "far.pdf"))
    assert doc.status == "Manual Review"
    assert doc.review_note == "In iCloud, not downloaded"
    assert doc.filename == "far.pdf" and doc.sha256 is None


def test_in_cloud_only_reads_the_flag_of_the_file(tmp_path, monkeypatch):
    """The answer comes from os.stat, and a normal file says no."""
    path = tmp_path / "a.txt"
    path.write_text("x")
    assert file_readers.in_cloud_only(str(path)) is False
    fake = type("Stat", (), {"st_flags": file_readers.DATALESS_FLAG})
    monkeypatch.setattr(file_readers.os, "stat", lambda p: fake)
    assert file_readers.in_cloud_only(str(path)) is True


# --- No progress ---

def test_no_progress_in_five_minutes_pauses_the_scan():
    """With a clock in the test: running, then paused with the reason."""
    job = scanner.ScanJob()
    now = [1000.0]
    job.clock = lambda: now[0]
    job.note_progress()
    job.status = "running"
    job.current = "stuck.pdf"
    now[0] += scanner.STALL_SECONDS - 1
    assert job.to_dict()["status"] == "running"
    now[0] += 2
    state = job.to_dict()
    assert state["status"] == "paused" and state["error"] == "stalled"
    assert state["current"] == "stuck.pdf"
    assert not job.resume_event.is_set()
    job.resume()
    assert job.to_dict()["status"] == "running"
    assert job.to_dict()["error"] == ""


def test_timed_out_files_are_not_progress(tmp_path, monkeypatch, release):
    """An AI that never answers pauses the scan instead of using hours."""
    monkeypatch.setattr(time_budget, "FILE_SECONDS", 0.05)
    monkeypatch.setattr(scanner, "STALL_SECONDS", 0.1)
    root = tmp_path / "p"
    root.mkdir()
    for index in range(5):
        (root / "{}.txt".format(index)).write_text("HANG " + str(index))
    repo = place_project(root)
    job = scanner.ScanJob()
    thread = threading.Thread(target=scanner.scan_folder, args=(
        job, str(root), repo, HangingAI(release)), daemon=True)
    thread.start()
    for _ in range(100):
        if job.status == "paused":
            break
        time.sleep(0.02)
    assert job.status == "paused" and job.error == "stalled"
    assert job.done < 5
    job.stop()
    thread.join(5)


# --- Retry ---

@pytest.fixture
def timed_out(tmp_path, monkeypatch, release):
    """A scan with one timed-out file, and the app pointing at the project."""
    monkeypatch.setattr(time_budget, "FILE_SECONDS", 0.3)
    root = three_files(tmp_path / "p")
    repo = place_project(root)
    scanner.scan_folder(scanner.ScanJob(), str(root), repo,
                        HangingAI(release))
    monkeypatch.setattr(time_budget, "FILE_SECONDS", 120)
    return root, repo


def test_retry_reads_only_the_timed_out_file(timed_out):
    """The next scan reads that one file, and the others are not touched."""
    root, repo = timed_out
    others = {name: doc.id for name, doc in rows_by_name(repo).items()
              if name != "b.txt"}
    assert scanner.forget_retryable(repo) == 1
    seen = []

    class Recording(FakeAI):
        def send_prompt(self, system_prompt, text):
            seen.append(text)
            return super().send_prompt(system_prompt, text)

    scanner.scan_folder(scanner.ScanJob(), str(root), repo, Recording())
    rows = rows_by_name(repo)
    assert len(seen) == 1 and "HANG" in seen[0]
    assert rows["b.txt"].review_note != archive_rules.TIMEOUT_NOTE
    assert {name: rows[name].id for name in others} == others


@pytest.mark.parametrize("touch", ["edit", "rename", "move"])
def test_retry_leaves_rows_edited_by_hand(timed_out, touch):
    """Edit Mode and the chat leave a mark; those rows stay as they are."""
    root, repo = timed_out
    doc = rows_by_name(repo)["b.txt"]
    if touch == "edit":
        repo.update_document(doc.id, {"summary": "Written by hand."})
    elif touch == "rename":
        repo.rename_document(doc.id, "b.txt", doc.file_path)
    else:
        repo.move_document(doc.id, doc.file_path, "Prensa")
    assert scanner.retryable_documents(repo) == []
    assert scanner.forget_retryable(repo) == 0
    assert repo.get_document(doc.id) is not None
    assert repo.get_document(doc.id).review_note == archive_rules.TIMEOUT_NOTE
    assert repo.index_get(doc.file_path) is not None


def test_retry_skips_a_file_that_is_gone(timed_out):
    """A row whose file left the folder is not lost by Retry."""
    root, repo = timed_out
    os.remove(str(root / "b.txt"))
    assert scanner.retryable_documents(repo) == []


def test_retry_takes_icloud_files_once_they_are_downloaded(
        tmp_path, monkeypatch):
    """Still only in iCloud: no. On the Mac now: yes."""
    root = tmp_path / "p"
    root.mkdir()
    (root / "far.pdf").write_bytes(b"x")
    repo = place_project(root)
    monkeypatch.setattr(file_readers, "in_cloud_only", lambda path: True)
    scanner.scan_folder(scanner.ScanJob(), str(root), repo, FakeAI())
    assert scanner.retryable_documents(repo) == []
    monkeypatch.setattr(file_readers, "in_cloud_only", lambda path: False)
    assert len(scanner.retryable_documents(repo)) == 1


# --- The log ---

@pytest.fixture
def log_file(tmp_path):
    """The real log file, removed from the logger after the test."""
    path = app_log.setup_log(str(tmp_path / "data"))
    logger = logging.getLogger("backend")
    yield path
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    logger.setLevel(logging.NOTSET)


def test_the_log_says_what_is_read_and_how_long_each_step_took(
        tmp_path, monkeypatch, release, log_file):
    """Which file, each step's time, the end of each file, why it failed."""
    monkeypatch.setattr(time_budget, "FILE_SECONDS", 0.5)
    root = three_files(tmp_path / "p")
    repo = place_project(root)
    scanner.scan_folder(scanner.ScanJob(), str(root), repo,
                        HangingAI(release))
    with open(log_file, encoding="utf-8") as file:
        text = file.read()
    assert "reading 1/3 a.txt" in text and "reading 2/3 b.txt" in text
    assert "ai text" in text and "done in" in text
    assert "timed out after" in text and "in step ai text" in text
    assert "test-key" not in text
    assert "A letter" not in text


def test_a_log_that_cannot_be_opened_does_not_stop_the_app(tmp_path):
    """The app works the same without its log."""
    blocked = tmp_path / "data"
    blocked.write_text("a file, not a folder")
    assert app_log.setup_log(str(blocked)) is None


def test_the_log_rotates(log_file):
    """It keeps a few files of a limited size."""
    handler = logging.getLogger("backend").handlers[-1]
    assert handler.maxBytes == 2 * 1024 * 1024
    assert handler.backupCount == 5
    assert log_file.endswith(os.path.join("logs", "cataloga.log"))


def test_a_plain_refusal_is_not_a_cut_off_answer(tmp_path, monkeypatch):
    """No JSON at all: no second request, and the usual reason."""
    path = scanned_pdf(tmp_path / "p", monkeypatch)
    repo = place_project(tmp_path / "p")
    ai = ImageAI(["I cannot read this."])
    doc = pipeline_for(tmp_path / "p", repo, ai).classify_document(str(path))
    assert len(ai.prompts) == 1
    assert doc.review_note == archive_rules.SCAN_NOTE


# --- The routes ---

def open_place_project(client, root, monkeypatch):
    """Make the folder the active project, without its first scan."""
    start_scan = scanner.start_scan
    monkeypatch.setattr(scanner, "start_scan",
                        lambda app, path, owner=None: app.config.setdefault(
                            "SCAN", scanner.ScanJob()))
    response = client.post("/projects", json={
        "name": "Place", "folder": str(root), "folders": TREE,
        "folder_mode": "place"})
    assert response.status_code == 201
    monkeypatch.setattr(scanner, "start_scan", start_scan)
    monkeypatch.setattr(scanner, "create_client",
                        lambda name, model: FakeAI())
    return CatalogRepository(projects.catalog_path(str(root)))


def test_retry_route_reads_only_what_timed_out(empty_client, tmp_path,
                                               monkeypatch):
    """GET /scan counts them; POST /scan/retry reads them; edits stay."""
    root = tmp_path / "project"
    root.mkdir()
    (root / "late.txt").write_text("A letter that took too long")
    (root / "edited.txt").write_text("A letter someone already fixed")
    (root / "good.txt").write_text("A letter")
    repo = open_place_project(empty_client, root, monkeypatch)
    pipeline = pipeline_for(root, repo, FakeAI())
    for name in ("late.txt", "edited.txt"):
        doc = pipeline.add_unread(str(root / name),
                                  archive_rules.TIMEOUT_NOTE)
        stamp = scanner.file_stamp(str(root / name))
        repo.index_put(str(root / name), stamp[0], stamp[1], doc.id)
    edited = rows_by_name(repo)["edited.txt"]
    repo.update_document(edited.id, {"summary": "Written by hand."})

    assert empty_client.get("/scan").get_json()["retryable"] == 1
    response = empty_client.post("/scan/retry")
    assert response.status_code == 202
    assert response.get_json()["retried"] == 1
    empty_client.application.config["SCAN"].thread.join(5)

    rows = rows_by_name(repo)
    assert rows["late.txt"].review_note != archive_rules.TIMEOUT_NOTE
    assert rows["late.txt"].summary
    assert rows["edited.txt"].id == edited.id
    assert rows["edited.txt"].summary == "Written by hand."
    assert rows["edited.txt"].review_note == archive_rules.TIMEOUT_NOTE
    assert empty_client.get("/scan").get_json()["retryable"] == 0


def test_retry_route_waits_for_a_running_scan(empty_client, tmp_path,
                                              monkeypatch):
    """Forgetting rows under a running scan would make duplicates."""
    root = tmp_path / "project"
    root.mkdir()
    open_place_project(empty_client, root, monkeypatch)
    job = empty_client.application.config.setdefault("SCAN",
                                                     scanner.ScanJob())
    job.is_running = lambda: True
    response = empty_client.post("/scan/retry")
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "scan_running"


def test_retry_route_is_not_for_a_drop_zone(flask_client):
    """A classic project has a Drop Zone and no scan index."""
    response = flask_client.post("/scan/retry")
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "has_drop_zone"
