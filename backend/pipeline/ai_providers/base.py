"""AIProviderClient base class, and the client that falls back to another."""

import logging
import time

import keyring

from backend.models.document import MEDIA_TYPES

KEYRING_SERVICE = "cataloga"

logger = logging.getLogger(__name__)

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

PHOTO_PROMPT = """You are helping a researcher catalog an archive of photos.
The first image is a photo, maybe an old scanned print. The images after
it are its four corners, enlarged, so small writing can be read.
Find:
- rotation: 0 if the photo is upright; else the degrees to turn it
  clockwise so it is upright: 90, 180, or 270.
- printed_date: a date stamped on the photo by the camera, often orange
  digits in a corner like 11 13 '97, exactly as it reads, else null.
- handwritten_date: a date written by hand on the photo, exactly as it
  reads, else null.
- text: any other text you can read, exactly as written, else null.
- description: one sentence about what the photo shows: the people, the
  place, the event, the era.

Do not invent anything.

Respond with ONLY a JSON object in this exact format:
{"rotation": 0, "printed_date": null, "handwritten_date": null,
 "text": null, "description": "..."}"""

CATEGORIES_PROMPT = """You are helping a researcher set up a research archive.
For the industry or field the user gives, propose 6 to 10 categories to
sort its documents, each with 0 to 6 subcategories. Use short names
(1 to 3 words) in the same language as the user's text.

Respond with ONLY a JSON list in this exact format:
[{"name": "...", "subcategories": ["...", "..."]}]"""


FOLDERS_PROMPT = """You are an archivist setting up the folders of a new
research project. The user describes the project in one or two sentences.
Propose the folder tree an archivist would use for this kind of project:
4 to 10 top folders, each with 0 to 6 subfolders, never deeper.
First decide the industry or field of the project (a documentary, a legal
case, a book, a scientific study). Include the folders an archive in that
field always has, and add folders for the project's own subject.
Use the project's own names (an event, a case number, an episode) when
the description gives them.
Sort by what the files are about, not only by file type.
Short readable names (1 to 4 words) in the same language as the
description, with no dates unless they are part of a name.

Respond with ONLY a JSON list in this exact format:
[{"name": "...", "subfolders": ["...", "..."]}]"""


def save_api_key(provider_name, api_key):
    """Save a provider's API key in the OS keyring."""
    keyring.set_password(KEYRING_SERVICE, provider_name, api_key)


class AIProviderClient:
    """Base class for AI provider integrations."""

    # Only providers and models that accept images set this to True.
    supports_images = False

    def __init__(self, provider_name, model, base_url=None):
        """Store provider identity; fetch the API key from the OS keyring."""
        self.provider_name = provider_name
        self.model = model
        # A relay server, when the user has one; None means the provider.
        self.base_url = base_url or None
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

    def ask_about_images(self, image_uris, prompt=IMAGE_PROMPT):
        """Ask the AI to read and describe images. None if it cannot."""
        if not self.api_key or not self.supports_images or not image_uris:
            return None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                answer = self.send_images(prompt, image_uris)
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

    def send_folders_request(self, description, hints=""):
        """Ask the AI for a folder tree for a project. Saves nothing."""
        return self.ask(FOLDERS_PROMPT + hints, description)

    def test_connection(self):
        """Check that the API key and model work with a small test call."""
        if not self.api_key:
            raise ValueError("No API key saved for " + self.provider_name)
        self.send_prompt(CONNECTION_TEST_PROMPT, "ping")
        return True


class ClientWithFallback(AIProviderClient):
    """A client that asks the main provider, then the fallback if it fails.

    The pipeline uses it like any other client. Requests go to the main
    provider; when it has no key, fails after its retries, or cannot look
    at images, the fallback answers instead.
    """

    def __init__(self, main, fallback=None):
        """Wrap the main client and an optional fallback client."""
        self.main = main
        self.fallback = fallback
        # Read with defaults: test doubles do not always set them.
        self.provider_name = getattr(main, "provider_name", "")
        self.model = getattr(main, "model", "")
        self.base_url = getattr(main, "base_url", None)
        self.retry_delay = getattr(main, "retry_delay", 5)

    @property
    def api_key(self):
        """Ready when either client has a key."""
        return self.main.api_key or (self.fallback and self.fallback.api_key)

    @property
    def supports_images(self):
        """Images can go to whichever client accepts them."""
        return bool(self.image_client())

    def image_client(self):
        """Return the client that will look at images, or None."""
        for client in (self.main, self.fallback):
            if client and client.api_key and client.supports_images:
                return client
        return None

    def ask(self, system_prompt, text):
        """Ask the main provider; on no key or failure, ask the fallback."""
        answer = self.main.ask(system_prompt, text)
        if answer is not None or self.fallback is None:
            return answer
        logger.warning("%s did not answer; using %s", self.main.provider_name,
                       self.fallback.provider_name)
        return self.fallback.ask(system_prompt, text)

    def ask_about_images(self, image_uris, prompt=IMAGE_PROMPT):
        """Send images and their prompt to the first client that reads them."""
        client = self.image_client()
        if client is None:
            return None
        answer = client.ask_about_images(image_uris, prompt)
        if answer is None and client is self.main and self.fallback and \
                self.fallback.api_key and self.fallback.supports_images:
            logger.warning("%s did not read the images; using %s",
                           self.main.provider_name,
                           self.fallback.provider_name)
            return self.fallback.ask_about_images(image_uris, prompt)
        return answer

    def test_connection(self):
        """Test the main provider only; the fallback is tested on its own."""
        return self.main.test_connection()
