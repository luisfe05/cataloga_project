"""Summaries and names come in the app's language, not the file's."""

import json

import pytest

from backend.config import ai_settings, projects
from backend.db.catalog_repository import CatalogRepository
from backend.db.schema import init_db
from backend.pipeline import archive_rules, chat_assistant, language_check
from backend.pipeline.ai_providers import base
from backend.pipeline.ai_providers.base import AIProviderClient
from backend.pipeline.classification_pipeline import ClassificationPipeline
from backend.pipeline.file_organizer import FileOrganizer

# An invented answer in Cyrillic, like the one seen in the demo take.
CYRILLIC_CARD = {"media_type": "Documents",
                 "summary": "Фотографія полиці з офісними папками",
                 "topic": "офісні папки", "keywords": ["папки", "office"],
                 "confidence": "high"}
ENGLISH_CARD = {"media_type": "Documents",
                "summary": "Photo of a shelf with office folders",
                "topic": "office folders", "keywords": ["folders", "shelf"],
                "confidence": "high"}
SPANISH_CARD = {"media_type": "Documents",
                "summary": "Foto de un estante con carpetas de la oficina",
                "topic": "carpetas de oficina", "keywords": ["carpetas"],
                "confidence": "high"}


class CardAI(AIProviderClient):
    """Answers each request with the next prepared card; keeps the prompts."""

    def __init__(self, cards):
        """Prepared answers, one per request."""
        super().__init__(provider_name="fake", model="fake-model")
        self.api_key = "fake-key"
        self.retry_delay = 0
        self.cards = list(cards)
        self.prompts = []

    def send_prompt(self, system_prompt, text):
        """Return the next card as JSON text."""
        self.prompts.append(system_prompt)
        card = self.cards.pop(0) if self.cards else ENGLISH_CARD
        return card if isinstance(card, str) else json.dumps(card)


@pytest.fixture
def make_pipeline(tmp_path):
    """Build a pipeline with a Drop Zone project and a fake AI."""
    db_path = str(tmp_path / "catalog.db")
    init_db(db_path)
    repo = CatalogRepository(db_path)
    organizer = FileOrganizer(str(tmp_path / "Harbor Clinic"))
    organizer.ensure_archive_structure()

    def build(cards, language="en"):
        ai = CardAI(cards)
        return ClassificationPipeline(ai, repo, organizer,
                                      language=language), ai, organizer
    return build


def drop(organizer, name="shelf-notes.txt"):
    """Put an invented text file in the Drop Zone and return its path."""
    path = organizer.drop_zone_folder() + "/" + name
    with open(path, "w", encoding="utf-8") as file:
        file.write("Shelf labels: Institute of the City, 2013.")
    return path


def test_the_card_prompt_names_english(make_pipeline):
    """Settings in English: the prompt says English, never the file's."""
    pipeline, ai, organizer = make_pipeline([ENGLISH_CARD], "en")
    pipeline.classify_document(drop(organizer))
    assert "in English, whatever the language of the file" in ai.prompts[0]
    assert "file's language" not in ai.prompts[0]


def test_the_card_prompt_names_spanish(make_pipeline):
    """Settings in Spanish: the same prompt says Spanish."""
    pipeline, ai, organizer = make_pipeline([SPANISH_CARD], "es")
    doc = pipeline.classify_document(drop(organizer))
    assert "in Spanish, whatever the language of the file" in ai.prompts[0]
    assert "in English" not in ai.prompts[0]
    assert doc.summary == SPANISH_CARD["summary"]
    assert len(ai.prompts) == 1


def test_a_cyrillic_answer_is_asked_again_once(make_pipeline):
    """The second answer, in English, is the one saved."""
    pipeline, ai, organizer = make_pipeline([CYRILLIC_CARD, ENGLISH_CARD])
    doc = pipeline.classify_document(drop(organizer))
    assert len(ai.prompts) == 2
    assert "Your last answer was not in English" in ai.prompts[1]
    assert doc.summary == ENGLISH_CARD["summary"]
    assert doc.topic == "office folders"
    assert doc.status == "Classified"


def test_two_wrong_answers_leave_the_file_in_manual_review(make_pipeline):
    """Nothing in Cyrillic is saved; the note says why; no third request."""
    pipeline, ai, organizer = make_pipeline([CYRILLIC_CARD, CYRILLIC_CARD])
    path = drop(organizer)
    doc = pipeline.classify_document(path)
    assert len(ai.prompts) == 2
    assert doc.summary is None
    assert doc.topic is None
    assert doc.keywords == ["office"]
    assert doc.status == "Manual Review"
    assert doc.review_note == "Summary not in English, not saved"
    assert doc.review_note == archive_rules.LANGUAGE_NOTE.format("English")


def test_an_english_answer_in_spanish_settings_is_asked_again(make_pipeline):
    """The other app language counts as wrong too."""
    pipeline, ai, organizer = make_pipeline([ENGLISH_CARD, ENGLISH_CARD],
                                            "es")
    doc = pipeline.classify_document(drop(organizer))
    assert len(ai.prompts) == 2
    assert doc.summary is None
    assert doc.review_note == "Summary not in Spanish, not saved"


def test_quoted_titles_and_names_keep_their_language(make_pipeline):
    """An original title in quotes is not a wrong language."""
    card = dict(ENGLISH_CARD, summary="Shelf of folders labeled "
                "'ІНСТИТУТ МІСТА', 2013")
    pipeline, ai, organizer = make_pipeline([card])
    doc = pipeline.classify_document(drop(organizer))
    assert len(ai.prompts) == 1
    assert doc.summary == card["summary"]


def test_the_check_is_simple_and_local():
    """Script and common words only; short good texts pass."""
    assert language_check.wrong_language("Фотографія полиці", "en")
    assert language_check.wrong_language("Foto de la oficina del puerto",
                                         "en")
    assert not language_check.wrong_language("Harbor race results 2019",
                                             "en")
    assert not language_check.wrong_language("Harbor race results 2019",
                                             "es")
    assert language_check.wrong_language("Photo of the harbor and boats",
                                         "es")
    assert not language_check.wrong_language("Foto del puerto", "es")
    assert not language_check.wrong_language("", "en")


def test_the_regenerated_summary_uses_the_language_and_checks_it():
    """Asked again once; two wrong answers save nothing (the old one stays)."""
    ai = CardAI(["Фотографія полиці", "Photo of a shelf of folders"])
    assert ai.send_summary_request("text", None, "en") == \
        "Photo of a shelf of folders"
    assert "Write the summary in English" in ai.prompts[0]
    ai = CardAI(["Фотографія полиці", "Фотографія полиці"])
    assert ai.send_summary_request("text", None, "es") == ""
    assert "Write the summary in Spanish" in ai.prompts[0]
    assert len(ai.prompts) == 2


def test_the_english_prompts_stay_the_known_constants():
    """English is the default: the constants are the English prompts."""
    assert base.summary_prompt("en") == base.SUMMARY_PROMPT
    assert base.summary_prompt("fr") == base.SUMMARY_PROMPT


def test_the_account_language_reaches_the_ai_settings(tmp_path):
    """ai_settings.load gives the pipeline the language of Settings."""
    path = str(tmp_path / "ana" / "projects.json")
    projects.set_language(path, "es")
    assert ai_settings.load(path)["language"] == "es"
    with open(path, encoding="utf-8") as file:
        assert json.load(file)["ai"].get("language") is None


def test_ask_cataloga_still_answers_in_the_users_language():
    """The chat prompt is not tied to Settings: the user's language rules."""
    assert "in the user's language" in chat_assistant.SYSTEM_PROMPT
    assert "whatever the language" not in chat_assistant.SYSTEM_PROMPT
    assert "in English" not in chat_assistant.SYSTEM_PROMPT
    assert "in Spanish" not in chat_assistant.SYSTEM_PROMPT
