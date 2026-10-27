"""Tests for AIProviderClient and GeminiClient.

No test ever calls a real AI API or reads the real OS keyring. The
keyring is replaced with a fake that returns a test key, and the AI is
replaced with a fake that returns prepared answers.
"""

import pytest

from backend.pipeline.ai_providers import (
    base, claude, create_client, gemini, groq_provider, ollama_cloud,
    openai_provider, xai)
from backend.pipeline.ai_providers.base import AIProviderClient
from backend.pipeline.ai_providers.claude import ClaudeClient
from backend.pipeline.ai_providers.gemini import GeminiClient
from backend.pipeline.ai_providers.groq_provider import GroqClient
from backend.pipeline.ai_providers.ollama_cloud import OllamaCloudClient
from backend.pipeline.ai_providers.openai_provider import OpenAIClient
from backend.pipeline.ai_providers.xai import XAIClient


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


def test_summary_is_capped_at_100_characters():
    """A summary that is too long is cut at a word and ends with '...'."""
    client = FakeClient(["word " * 200])
    summary = client.send_summary_request("text")
    assert len(summary) <= 100
    assert summary.endswith("...")
    # The cut happens between words, so no word is split in half.
    assert summary[:-3].split() == ["word"] * len(summary[:-3].split())


def test_summary_of_exactly_100_characters_is_kept():
    """A summary right at the limit is returned whole, with no '...'."""
    answer = "a" * 100
    client = FakeClient([answer])
    assert client.send_summary_request("text") == answer


def test_summary_prompt_asks_for_100_characters():
    """The prompt tells the AI the same limit the app enforces."""
    assert base.MAX_SUMMARY_LENGTH == 100
    assert "under 100 characters" in base.SUMMARY_PROMPT


def test_summary_with_facts_sends_them_first():
    """Facts typed by the researcher go before the document text."""
    client = FakeClient(["A summary."])
    client.send_summary_request("The text.", {"source": "Claridad",
                                              "document_date": None})
    sent = client.calls[0]
    assert sent.startswith("Facts confirmed by the researcher")
    assert "- source: Claridad" in sent
    assert "document_date" not in sent
    assert sent.endswith("Document text:\nThe text.")


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


# --- Groq, OpenAI, and xAI (all use the chat completions format) ---

class FakeChatCompletions:
    """Stands in for client.chat.completions in the groq/openai SDKs."""

    def __init__(self, answer):
        self.answer = answer
        self.last_call = None

    def create(self, model, messages):
        self.last_call = {"model": model, "messages": messages}
        message = type("Message", (), {"content": self.answer})
        choice = type("Choice", (), {"message": message})
        return type("Response", (), {"choices": [choice]})


def make_fake_chat_sdk(answer, created_with):
    """Build a fake SDK client class that records how it was created."""
    completions = FakeChatCompletions(answer)

    class FakeSDKClient:
        def __init__(self, api_key, base_url=None):
            created_with["api_key"] = api_key
            created_with["base_url"] = base_url
            self.chat = type("Chat", (), {"completions": completions})

    return FakeSDKClient, completions


@pytest.mark.parametrize("module, sdk_name, client_class, model, base_url", [
    (groq_provider, "Groq", GroqClient, "llama-3.1-8b-instant", None),
    (openai_provider, "OpenAI", OpenAIClient, "gpt-5.4-nano", None),
    (xai, "OpenAI", XAIClient, "grok-4.7", "https://api.x.ai/v1"),
    (ollama_cloud, "OpenAI", OllamaCloudClient, "gemma4:31b",
     "https://ollama.com/v1"),
])
def test_chat_providers_send_prompt(monkeypatch, module, sdk_name,
                                    client_class, model, base_url):
    """Each chat-style client sends the key, model, and both messages."""
    created_with = {}
    fake_sdk, completions = make_fake_chat_sdk("Press", created_with)
    monkeypatch.setattr(module, sdk_name, fake_sdk)

    answer = client_class().send_prompt("Classify this.", "Article text")

    assert answer == "Press"
    assert created_with["api_key"] == "test-key"
    assert created_with["base_url"] == base_url
    assert completions.last_call["model"] == model
    assert completions.last_call["messages"] == [
        {"role": "system", "content": "Classify this."},
        {"role": "user", "content": "Article text"},
    ]


# --- Claude (uses the Anthropic messages format) ---

def test_claude_send_prompt(monkeypatch):
    """ClaudeClient sends the system prompt separately and joins text."""
    recorded = {}

    class FakeMessages:
        def create(self, model, max_tokens, system, messages):
            recorded.update({"model": model, "system": system,
                             "messages": messages})
            text_block = type("Block", (), {"type": "text",
                                            "text": "Documents"})
            return type("Response", (), {"content": [text_block]})

    class FakeAnthropic:
        def __init__(self, api_key):
            recorded["api_key"] = api_key
            self.messages = FakeMessages()

    monkeypatch.setattr(claude.anthropic, "Anthropic", FakeAnthropic)

    answer = ClaudeClient().send_prompt("Classify this.", "A letter")

    assert answer == "Documents"
    assert recorded["api_key"] == "test-key"
    assert recorded["model"] == "claude-haiku-5-5"
    assert recorded["system"] == "Classify this."
    assert recorded["messages"] == [{"role": "user", "content": "A letter"}]


@pytest.mark.parametrize("name", ["ollama", "gemini", "groq", "claude",
                                  "xai", "openai"])
def test_create_client_supports_all_six_providers(name):
    """Every provider in the scope can be built by its settings name."""
    client = create_client(name, "some-model")
    assert client.provider_name == name
    assert client.model == "some-model"


def test_create_client_rejects_unknown_provider():
    """A name that is not one of the six gives ValueError."""
    with pytest.raises(ValueError):
        create_client("skynet", "x")


# --- Ollama Cloud: where the key comes from ---

def test_ollama_key_from_keyring_wins(monkeypatch):
    """A key saved in the keyring is used before the development key."""
    monkeypatch.setenv("OLLAMA_API_KEY", "dev-key")
    assert OllamaCloudClient().api_key == "test-key"


def test_ollama_uses_environment_key_without_keyring(monkeypatch):
    """With no key in the keyring, OLLAMA_API_KEY is used."""
    monkeypatch.setattr(base.keyring, "get_password",
                        lambda service, name: None)
    monkeypatch.setenv("OLLAMA_API_KEY", "dev-key")
    assert OllamaCloudClient().api_key == "dev-key"


def test_ollama_uses_env_file_without_keyring(monkeypatch, tmp_path):
    """With no keyring key and no variable, the .env file is read."""
    monkeypatch.setattr(base.keyring, "get_password",
                        lambda service, name: None)
    env_file = tmp_path / ".env"
    env_file.write_text('# dev settings\nOTHER=1\nOLLAMA_API_KEY="file-key"\n')
    monkeypatch.setattr(ollama_cloud, "ENV_PATH", str(env_file))
    assert OllamaCloudClient().api_key == "file-key"


def test_ollama_without_any_key(monkeypatch):
    """No keyring key, no variable, no .env: the key is None."""
    monkeypatch.setattr(base.keyring, "get_password",
                        lambda service, name: None)
    assert OllamaCloudClient().api_key is None


def test_packaged_app_never_reads_development_key(monkeypatch):
    """Inside the packaged app (sys.frozen), only the keyring counts."""
    monkeypatch.setattr(base.keyring, "get_password",
                        lambda service, name: None)
    monkeypatch.setenv("OLLAMA_API_KEY", "dev-key")
    monkeypatch.setattr(ollama_cloud.sys, "frozen", True, raising=False)
    assert OllamaCloudClient().api_key is None


def test_other_providers_never_read_the_ollama_key(monkeypatch):
    """The development key is only for Ollama Cloud."""
    monkeypatch.setattr(base.keyring, "get_password",
                        lambda service, name: None)
    monkeypatch.setenv("OLLAMA_API_KEY", "dev-key")
    assert GroqClient().api_key is None
