"""AIProviderClient base class.

Defines the interface that every provider module must implement.
The ClassificationPipeline always talks to an AIProviderClient, so
swapping providers only means changing which subclass is instantiated.

The prompts, the reading of the AI's answers, and the retries all live
here, so they are written once. Each provider subclass only implements
send_prompt(), which sends text to its own API and returns the answer.

API keys are fetched from the OS keyring at runtime using the keyring
library. They are never written to the database, a file, or a log.
"""

import time

import keyring

from backend.models.document import MEDIA_TYPES

# keyring service name used across all providers.
KEYRING_SERVICE = "cataloga"

# Longest summary allowed, per the Stage 3 report.
MAX_SUMMARY_LENGTH = 500

# Only the start of a long document is sent, to stay inside free API
# limits. The first pages are usually enough to classify and summarize.
MAX_INPUT_CHARS = 20000

# How many times to try a request before giving up.
MAX_ATTEMPTS = 3

CLASSIFICATION_PROMPT = """You are organizing files in a research archive.
Classify the document into exactly one of these media types:

Press: a newspaper or magazine article, press clipping, or press release.
Documents: any other written document, such as a letter, report, record,
book chapter, transcript, or proclamation.
Photos: a photograph or still image.
Audio: a sound recording.
Video: video footage.

Respond with ONLY the media type name, nothing else."""

SUMMARY_PROMPT = """You are helping a researcher catalog an archive.
Write a factual summary of the document in your own words: what it is,
who or what it is about, and any key dates, places, or results.
Write the summary in the same language as the document.
Keep it under 500 characters. Do not invent information that is not in
the text.

Respond with ONLY the summary text, with no labels or quotation marks."""

CONNECTION_TEST_PROMPT = "Reply with the single word OK."


class AIProviderClient:
    """Base class for AI provider integrations."""

    def __init__(self, provider_name, model):
        """Store provider identity; fetch the API key from the OS keyring.

        Args:
            provider_name (str): Name used as the keyring username
                (e.g. 'gemini').
            model (str): The model to use for requests
                (e.g. 'gemini-2.5-flash').
        """
        self.provider_name = provider_name
        self.model = model
        # Key is fetched here so it is available for the session, but never
        # written to disk or logged. None means no key was saved yet.
        self.api_key = keyring.get_password(KEYRING_SERVICE, provider_name)
        # Seconds to wait between retries. Tests set this to 0.
        self.retry_delay = 5

    def send_prompt(self, system_prompt, text):
        """Send one request to the provider's API and return its answer.

        Every provider subclass must implement this method.

        Args:
            system_prompt (str): The instructions for the AI.
            text (str): The content the instructions apply to.

        Returns:
            str: The AI's answer as plain text.
        """
        raise NotImplementedError

    def ask(self, system_prompt, text):
        """Call send_prompt(), trying again if the request fails.

        Free API tiers often reject a request for a few seconds when too
        many are sent. Waiting a little longer each time and trying again
        usually fixes it.

        Args:
            system_prompt (str): The instructions for the AI.
            text (str): The content the instructions apply to.

        Returns:
            str or None: The answer, or None if every attempt failed.
        """
        if not self.api_key:
            return None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                answer = self.send_prompt(system_prompt,
                                          text[:MAX_INPUT_CHARS])
                return (answer or "").strip()
            except Exception:
                # Wait 5 s, then 10 s, before the next attempt.
                if attempt < MAX_ATTEMPTS:
                    time.sleep(self.retry_delay * attempt)
        return None

    def send_classification_request(self, text):
        """Send document text to the AI and return the media type label.

        Args:
            text (str): Extracted text from the document.

        Returns:
            str or None: One of Press / Audio / Video / Photos / Documents,
                or None if the AI failed or gave an answer that is not a
                valid media type.
        """
        answer = self.ask(CLASSIFICATION_PROMPT, text)
        if not answer:
            return None
        # Accept small differences like 'press', 'Press.' or '"Press"'.
        cleaned = answer.strip(" .\"'\n").lower()
        for media_type in MEDIA_TYPES:
            if cleaned == media_type.lower():
                return media_type
        return None

    def send_summary_request(self, text):
        """Send document text to the AI and return a summary.

        Args:
            text (str): Extracted text from the document.

        Returns:
            str: Summary, up to 500 characters. Empty string on failure.
        """
        answer = self.ask(SUMMARY_PROMPT, text)
        if not answer:
            return ""
        if len(answer) > MAX_SUMMARY_LENGTH:
            # Cut at the last full word that fits, then add '...'.
            answer = answer[:MAX_SUMMARY_LENGTH - 3].rsplit(" ", 1)[0] + "..."
        return answer

    def test_connection(self):
        """Check that the API key and model work with a small test call.

        Unlike the other methods, this one does not retry, so the user
        sees the real error message right away in the settings screen.

        Returns:
            bool: True if the connection succeeds.

        Raises:
            ValueError: If no API key is saved for this provider.
            Exception: The provider's own error if the call fails.
        """
        if not self.api_key:
            raise ValueError("No API key saved for " + self.provider_name)
        self.send_prompt(CONNECTION_TEST_PROMPT, "ping")
        return True
