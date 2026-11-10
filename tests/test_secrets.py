"""Keys, tokens and passwords inside a file never reach an AI provider."""

import json
import logging
import os

import pytest

from backend.db.catalog_repository import CatalogRepository
from backend.db.schema import init_db
from backend.pipeline import ai_providers, secrets
from backend.pipeline.ai_providers import base
from backend.pipeline.ai_providers.base import AIProviderClient
from backend.pipeline.classification_pipeline import ClassificationPipeline
from backend.pipeline.file_organizer import FileOrganizer
from tests.conftest import card_answer

# Every key here is invented. The shapes are what matters.
FAKE_SECRETS = [
    "sk-test-000000000000000000000000",
    "sk-ant-test-0000000000000000000000000",
    "AIzaTEST000000000000000000000000000000",
    "ghp_TEST000000000000000000000000000000000",
    "github_pat_TEST00000000000000000000000",
    "xoxb-000000000000-TEST0000",
    "AKIATEST0000TEST0000",
    "gsk_TEST00000000000000000",
    "xai-TEST00000000000000000",
    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0In0.c2lnbmF0dXJlVEVTVDAwMA",
]

LABELED_LINES = [
    "password: hunter-test-2",
    "passwd = hunter-test-2",
    "contraseña: hunter-test-2",
    "Contrasena=hunter-test-2",
    "secret: hunter-test-2",
    "token: hunter-test-2",
    "api_key = hunter-test-2",
    "apikey: hunter-test-2",
    'API Key: "hunter-test-2"',
    '"password": "hunter-test-2",',
]

PRIVATE_KEY = ("-----BEGIN RSA PRIVATE KEY-----\n"
               "MIIEtestLINEONE\nMIIEtestLINETWO\n"
               "-----END RSA PRIVATE KEY-----")

PLAIN_TEXTS = [
    "Meeting on 2026-07-15 at 10:30 with the club.",
    "Call 787-555-0100 or (787) 555-0199 before noon.",
    "Files: 0001_coast-erosion.txt, dawn-swim_harbor-gazette_1998.pdf",
    "The secretary read the token of appreciation aloud.",
    "Password policy: see the handbook.",
    "Version v2 of the budget, final draft 3.",
    "https://example.com/path/to/page?id=42",
]


@pytest.mark.parametrize("secret", FAKE_SECRETS)
def test_every_key_shape_is_hidden(secret):
    """The key goes; the words around it stay."""
    text, count = secrets.redact_secrets("see " + secret + " here")
    assert text == "see [REDACTED] here"
    assert count == 1


@pytest.mark.parametrize("line", LABELED_LINES)
def test_a_labeled_value_is_hidden_but_the_label_stays(line):
    """Only the value after = or : is replaced."""
    text, count = secrets.redact_secrets(line)
    assert "hunter-test-2" not in text
    assert "[REDACTED]" in text
    assert count == 1
    assert text.split("[REDACTED]")[0].strip()


def test_a_private_key_block_is_hidden_whole():
    """The whole block, from BEGIN to END, becomes one marker."""
    text, count = secrets.redact_secrets("before\n" + PRIVATE_KEY +
                                         "\nafter")
    assert text == "before\n[REDACTED]\nafter"
    assert count == 1
    # A block that never ends takes the rest of the text with it.
    cut = PRIVATE_KEY.split("-----END")[0]
    assert secrets.redact_secrets(cut)[0] == "[REDACTED]"


def test_a_url_with_a_user_and_a_password_is_hidden():
    """user:pass goes; the host and the path stay."""
    text, count = secrets.redact_secrets(
        "see https://ana:hunter-test-2@example.com/files")
    assert text == "see https://[REDACTED]@example.com/files"
    assert count == 1


def test_a_bearer_header_is_hidden():
    """A pasted Authorization header loses its token."""
    text, count = secrets.redact_secrets(
        "Authorization: Bearer abcdefghijklmnopqrstuvwxyz0123")
    assert text == "Authorization: Bearer [REDACTED]"
    assert count == 1


@pytest.mark.parametrize("text", PLAIN_TEXTS)
def test_normal_text_does_not_change(text):
    """Dates, phone numbers, file names and prose pass untouched."""
    assert secrets.redact_secrets(text) == (text, 0)


def test_hiding_twice_counts_once():
    """ask() hides again what the pipeline hid: nothing new is counted."""
    once, count = secrets.redact_secrets("password: hunter-test-2")
    assert count == 1
    assert secrets.redact_secrets(once) == (once, 0)


def test_empty_and_odd_values():
    """None and '' come back as they are."""
    assert secrets.redact_secrets(None) == (None, 0)
    assert secrets.redact_secrets("") == ("", 0)


# --- The one exit point: nothing with a secret leaves the app ---

class SpyAI(AIProviderClient):
    """A fake provider that keeps everything it is sent."""

    def __init__(self, answer):
        super().__init__(provider_name="fake", model="fake-model")
        self.api_key = "fake-provider-key"
        self.retry_delay = 0
        self.answer = answer
        self.sent = []

    def send_prompt(self, system_prompt, text):
        self.sent.append(system_prompt + "\n" + text)
        return self.answer


def everything_sent(ai):
    """All the text the fake provider ever got."""
    return "\n".join(ai.sent)


def test_ask_hides_secrets_in_the_prompt_and_the_text():
    """The exit point itself: the system prompt and the text are cleaned."""
    ai = SpyAI("ok")
    ai.ask("Sheet: api_key=sk-test-000000000000000000000000",
           "password: hunter-test-2 and " + FAKE_SECRETS[2])
    assert "sk-test" not in everything_sent(ai)
    assert "hunter-test-2" not in everything_sent(ai)
    assert "AIza" not in everything_sent(ai)
    assert everything_sent(ai).count("[REDACTED]") == 3


@pytest.fixture
def project(tmp_path):
    """A Drop Zone project with a spying AI."""
    folder = tmp_path / "archive"
    db_path = str(tmp_path / "catalog.db")
    init_db(db_path)
    repo = CatalogRepository(db_path)
    repo.save_app_config("Secrets", str(folder))
    organizer = FileOrganizer(str(folder))
    organizer.ensure_archive_structure()
    ai = SpyAI(card_answer({"topic": "Budget", "source": "Club"}))
    pipeline = ClassificationPipeline(ai, repo, organizer)
    return {"repo": repo, "ai": ai, "pipeline": pipeline,
            "drop_zone": folder / "Drop Zone"}


def test_a_key_inside_a_file_never_reaches_the_provider(project, caplog):
    """The file is read and summarized; the key is not sent, kept or logged.

    The catalog keeps only the number of secrets hidden.
    """
    path = project["drop_zone"] / "notes.txt"
    path.write_text("Budget notes for the club.\n"
                    "API_KEY=" + FAKE_SECRETS[0] + "\n"
                    "password: hunter-test-2\n")
    with caplog.at_level(logging.INFO, logger="backend"):
        doc = project["pipeline"].classify_document(str(path))
    sent = everything_sent(project["ai"])
    assert "Budget notes for the club" in sent
    assert FAKE_SECRETS[0] not in sent
    assert "hunter-test-2" not in sent
    assert doc.status == "Classified"
    assert doc.secrets_hidden == 2
    row = json.dumps(project["repo"].get_document(doc.id).to_dict())
    assert FAKE_SECRETS[0] not in row and "hunter-test-2" not in row
    assert '"secrets_hidden": 2' in row
    # The file itself is untouched.
    assert FAKE_SECRETS[0] in open(doc.file_path, encoding="utf-8").read()
    assert FAKE_SECRETS[0] not in caplog.text
    assert "hunter-test-2" not in caplog.text
    assert "2 secrets hidden" in caplog.text


def test_a_file_without_secrets_keeps_no_count(project):
    """Nothing hidden: the column stays empty."""
    path = project["drop_zone"] / "plain.txt"
    path.write_text("Notes about the dawn swim of 1998.")
    doc = project["pipeline"].classify_document(str(path))
    assert doc.secrets_hidden is None
    assert project["ai"].sent


def test_a_regenerated_summary_is_cleaned_too(project):
    """Editing the source reads the file again: the key still never leaves."""
    path = project["drop_zone"] / "letter.txt"
    path.write_text("Letter about the race.\nsecret: hunter-test-2\n")
    doc = project["pipeline"].classify_document(str(path))
    project["ai"].sent = []
    project["ai"].answer = "A letter about the race."
    project["pipeline"].regenerate_summary(doc)
    assert project["ai"].sent
    assert "hunter-test-2" not in everything_sent(project["ai"])


def test_a_chat_message_with_a_key_never_reaches_the_provider(
        flask_client, projects_path, monkeypatch):
    """The user's message and the catalog cards are cleaned before the call."""
    from backend.config import ai_settings
    ai = SpyAI(json.dumps({"in_scope": True, "category": "help",
                           "action": "answer",
                           "reply": "I cannot use a key.", "sources": []}))
    ai_settings.set_role(projects_path, "text", "gemini", "gemini-2.5-flash")
    monkeypatch.setattr(ai_providers, "create_client",
                        lambda name, model, base_url=None: ai)
    answer = flask_client.post("/chat", json={
        "message": "My key is " + FAKE_SECRETS[1] + ", does it work?"})
    assert answer.status_code == 200
    assert ai.sent
    assert FAKE_SECRETS[1] not in everything_sent(ai)
    assert "[REDACTED]" in everything_sent(ai)


def test_an_old_catalog_gets_the_secrets_column(tmp_path):
    """init_db adds secrets_hidden to a catalog made before it."""
    import sqlite3
    db_path = str(tmp_path / "old.db")
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE documents (id INTEGER PRIMARY KEY, "
                 "original_filename TEXT, filename TEXT, media_type TEXT, "
                 "file_path TEXT, date_added TEXT, status TEXT)")
    conn.commit()
    conn.close()
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    columns = [row[1] for row in conn.execute("PRAGMA table_info(documents)")]
    conn.close()
    assert "secrets_hidden" in columns
    assert os.path.isfile(db_path)
    assert base.MAX_INPUT_CHARS > 0
