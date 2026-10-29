"""AIProviderClient base class."""

import time

import keyring

from backend.models.document import MEDIA_TYPES

KEYRING_SERVICE = "cataloga"

# Scope change of Oct 25 (was 500).
MAX_SUMMARY_LENGTH = 100

# Only the start of a document is sent, to stay inside free API limits.
MAX_INPUT_CHARS = 20000

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
Write one short sentence, under 100 characters. Do not invent
information that is not in the text.

Respond with ONLY the summary text, with no labels or quotation marks."""

CONNECTION_TEST_PROMPT = "Reply with the single word OK."

IMAGE_PROMPT = """You are helping a researcher catalog an archive.
Look at the image or images (a photo, or the pages of a scanned document).
Find:
- text: all the text you can read, exactly as written, in reading order.
- description: one sentence about what the image shows.

Use null for text if there is no text. Do not invent anything.

Respond with ONLY a JSON object in this exact format:
{"text": "...", "description": "..."}"""

CATEGORIES_PROMPT = """You are helping a researcher set up a research archive.
For the industry or field the user gives, propose 6 to 10 categories to
sort its documents, each with 0 to 6 subcategories. Use short names
(1 to 3 words) in the same language as the user's text.

Respond with ONLY a JSON list in this exact format:
[{"name": "...", "subcategories": ["...", "..."]}]"""


FOLDERS_PROMPT = """You are an archivist setting up the folders of a new
research project. The user describes the project in one or two sentences.
Propose the folder tree an archivist would use for this kind of project:
3 to 8 top folders, each with 0 to 6 subfolders, never deeper.
Use the project's own names (an event, a case number, an episode) when
the description gives them. Sort by what the files are about, not only
by file type. Short readable names (1 to 4 words) in the same language as
the description, with no dates unless they are part of a name.

Respond with ONLY a JSON list in this exact format:
[{"name": "...", "subfolders": ["...", "..."]}]"""


def save_api_key(provider_name, api_key):
    """Save a provider's API key in the OS keyring."""
    keyring.set_password(KEYRING_SERVICE, provider_name, api_key)


class AIProviderClient:
    """Base class for AI provider integrations."""

    # Only providers and models that accept images set this to True.
    supports_images = False

    def __init__(self, provider_name, model):
        """Store provider identity; fetch the API key from the OS keyring."""
        self.provider_name = provider_name
        self.model = model
        # The key stays in memory: never written to disk or logged.
        self.api_key = keyring.get_password(KEYRING_SERVICE, provider_name)
        # Seconds between retries. Tests set this to 0.
        self.retry_delay = 5

    def send_prompt(self, system_prompt, text):
        """Send one request to the provider's API and return its answer."""
        raise NotImplementedError

    def ask(self, system_prompt, text):
        """Call send_prompt(), trying again if the request fails."""
        if not self.api_key:
            return None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                answer = self.send_prompt(system_prompt,
                                          text[:MAX_INPUT_CHARS])
                return (answer or "").strip()
            except Exception:
                # Wait 5 s, then 10 s.
                if attempt < MAX_ATTEMPTS:
                    time.sleep(self.retry_delay * attempt)
        return None

    def send_images(self, prompt, image_uris):
        """Send a prompt with images to the provider's API."""
        raise NotImplementedError

    def ask_about_images(self, image_uris):
        """Ask the AI to read and describe images. None if it cannot."""
        if not self.api_key or not self.supports_images or not image_uris:
            return None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                answer = self.send_images(IMAGE_PROMPT, image_uris)
                return (answer or "").strip()
            except Exception:
                # Wait 5 s, then 10 s, like text requests.
                if attempt < MAX_ATTEMPTS:
                    time.sleep(self.retry_delay * attempt)
        return None

    def send_classification_request(self, text):
        """Send document text to the AI and return the media type label."""
        answer = self.ask(CLASSIFICATION_PROMPT, text)
        if not answer:
            return None
        # Accept small differences like 'press', 'Press.' or '"Press"'.
        cleaned = answer.strip(" .\"'\n").lower()
        for media_type in MEDIA_TYPES:
            if cleaned == media_type.lower():
                return media_type
        return None

    def send_summary_request(self, text, facts=None):
        """Send document text to the AI and return a summary."""
        if facts:
            lines = ["Facts confirmed by the researcher (use them):"]
            for name, value in facts.items():
                if value:
                    lines.append("- {}: {}".format(name, value))
            text = "\n".join(lines) + "\n\nDocument text:\n" + text
        answer = self.ask(SUMMARY_PROMPT, text)
        if not answer:
            return ""
        if len(answer) > MAX_SUMMARY_LENGTH:
            # Cut at the last full word that fits, then add '...'.
            answer = answer[:MAX_SUMMARY_LENGTH - 3].rsplit(" ", 1)[0] + "..."
        return answer

    def send_categories_request(self, industry):
        """Ask the AI for a category list for an industry. Saves nothing."""
        return self.ask(CATEGORIES_PROMPT, industry)

    def send_folders_request(self, description):
        """Ask the AI for a folder tree for a project. Saves nothing."""
        return self.ask(FOLDERS_PROMPT, description)

    def test_connection(self):
        """Check that the API key and model work with a small test call."""
        if not self.api_key:
            raise ValueError("No API key saved for " + self.provider_name)
        self.send_prompt(CONNECTION_TEST_PROMPT, "ping")
        return True
