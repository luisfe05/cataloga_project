"""Tests for AIProviderClient and GeminiClient.

No test ever calls a real AI API or reads the real OS keyring. The
keyring is replaced with a fake that returns a test key, and the AI is
replaced with a fake that returns prepared answers.
"""

import pytest

from backend.pipeline.ai_providers import base
from backend.pipeline.ai_providers import gemini
from backend.pipeline.ai_providers.base import AIProviderClient
from backend.pipeline.ai_providers.gemini import GeminiClient


@pytest.fixture(autouse=True)
def fake_keyring(monkeypatch):
    """Make keyring return 'test-key' for every provider in every test."""
    monkeypatch.setattr(base.keyring, "get_password",
                        lambda service, name: "test-key")


class FakeClient(AIProviderClient):
    """A provider that returns prepared answers instead of calling an API.

    Each item in answers is either a string to return or an Exception to
    raise, used in order, one per call.
    """

    def __init__(self, answers):
        super().__init__(provider_name="fake", model="fake-model")
        self.answers = list(answers)
        self.calls = []
        self.retry_delay = 0

    def send_prompt(self, system_prompt, text):
        self.calls.append(text)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def test_api_key_comes_from_keyring():
    """The key is read from the keyring when the client is created."""
    assert FakeClient([]).api_key == "test-key"


@pytest.mark.parametrize("answer", ["Press", "press", " Press.\n", '"Press"'])
def test_classification_accepts_small_differences(answer):
    """Case, spaces, periods, and quotes around the label are ignored."""
    assert FakeClient([answer]).send_classification_request("text") == "Press"


def test_classification_invalid_answer_returns_none():
    """An answer that is not one of the five media types gives None."""
    client = FakeClient(["Newspaper article"])
    assert client.send_classification_request("text") is None


def test_classification_retries_after_error():
    """A failed request is tried again, and the next answer is used."""
    client = FakeClient([RuntimeError("busy"), "Documents"])
    assert client.send_classification_request("text") == "Documents"
    assert len(client.calls) == 2


def test_classification_gives_up_after_three_errors():
    """After three failed attempts the result is None, not a crash."""
    client = FakeClient([RuntimeError("busy")] * 3)
    assert client.send_classification_request("text") is None
    assert len(client.calls) == 3


def test_long_text_is_cut_before_sending():
    """Only the first MAX_INPUT_CHARS characters are sent to the AI."""
    client = FakeClient(["Documents"])
    client.send_classification_request("a" * (base.MAX_INPUT_CHARS + 100))
    assert len(client.calls[0]) == base.MAX_INPUT_CHARS


def test_summary_is_returned():
    """A normal summary comes back without extra spaces."""
    client = FakeClient(["  A letter from 1964.  "])
    assert client.send_summary_request("text") == "A letter from 1964."


def test_summary_is_capped_at_500_characters():
    """A summary that is too long is cut at a word and ends with '...'."""
    client = FakeClient(["word " * 200])
    summary = client.send_summary_request("text")
    assert len(summary) <= 500
    assert summary.endswith("...")


def test_summary_failure_returns_empty_string():
    """If every attempt fails, the summary is an empty string."""
    client = FakeClient([RuntimeError("down")] * 3)
    assert client.send_summary_request("text") == ""


def test_no_api_key_skips_the_request(monkeypatch):
    """Without a saved key, nothing is sent and the result is empty."""
    monkeypatch.setattr(base.keyring, "get_password",
                        lambda service, name: None)
    client = FakeClient(["Press"])
    assert client.send_classification_request("text") is None
    assert client.calls == []


def test_connection_success():
    """test_connection() returns True when the API answers."""
    assert FakeClient(["OK"]).test_connection() is True


def test_connection_without_key_raises(monkeypatch):
    """test_connection() explains that the key is missing."""
    monkeypatch.setattr(base.keyring, "get_password",
                        lambda service, name: None)
    with pytest.raises(ValueError):
        FakeClient([]).test_connection()


def test_connection_error_is_not_hidden():
    """The provider's error reaches the caller so the user can see it."""
    client = FakeClient([RuntimeError("API key not valid")])
    with pytest.raises(RuntimeError, match="API key not valid"):
        client.test_connection()


class FakeGeminiResponse:
    """Stands in for the response object the Gemini library returns."""

    def __init__(self, text):
        self.text = text


class FakeGeminiModels:
    """Records what generate_content() was called with."""

    def __init__(self):
        self.last_call = None

    def generate_content(self, model, contents, config):
        self.last_call = {"model": model, "contents": contents,
                          "config": config}
        return FakeGeminiResponse("Press")


def test_gemini_send_prompt(monkeypatch):
    """GeminiClient passes the key, model, prompt, and text to Gemini."""
    models = FakeGeminiModels()
    created_with = {}

    class FakeGenaiClient:
        def __init__(self, api_key):
            created_with["api_key"] = api_key
            self.models = models

    monkeypatch.setattr(gemini.genai, "Client", FakeGenaiClient)

    client = GeminiClient()
    answer = client.send_prompt("Classify this.", "Some article text")

    assert answer == "Press"
    assert created_with["api_key"] == "test-key"
    assert models.last_call["model"] == "gemini-2.5-flash"
    assert models.last_call["contents"] == "Some article text"
    assert models.last_call["config"] == {
        "system_instruction": "Classify this."}
