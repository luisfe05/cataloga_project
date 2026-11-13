"""Google Gemini provider."""

import base64
import os
import time

from google import genai
from google.genai import types

from backend.pipeline import time_budget
from backend.pipeline.ai_providers.base import AIProviderClient, OTHER_TOKENS


# Files up to this size go inside the request; bigger ones are uploaded.
INLINE_BYTES = 20 * 1024 * 1024
# How long to wait for an uploaded file to be ready, in 2-second steps.
UPLOAD_WAIT_STEPS = 90


class GeminiClient(AIProviderClient):
    """Gemini-specific implementation of AIProviderClient."""

    # Every Gemini model looks at images.
    supports_images = True

    def __init__(self, model="gemini-3.5-flash-lite", base_url=None):
        """Initialize with the Gemini provider name and chosen model."""
        super().__init__(provider_name="gemini", model=model,
                         base_url=base_url)

    def sdk_client(self, one_call=True):
        """Build the SDK client, aimed at the relay server if there is one.

        Uploading a recording is not one call: only the file's limit applies.
        """
        options = {}
        if one_call:
            # Google's library counts in milliseconds.
            options["timeout"] = int(time_budget.call_seconds() * 1000)
        if self.base_url:
            options["base_url"] = self.base_url
        if options:
            return genai.Client(api_key=self.api_key, http_options=options)
        return genai.Client(api_key=self.api_key)

    def send_prompt(self, system_prompt, text):
        """Send one request to the Gemini API and return its answer."""
        # Kept in a variable: the library closes a client nothing holds.
        client = self.sdk_client()
        response = client.models.generate_content(
            model=self.model,
            contents=text,
            config={"system_instruction": system_prompt,
                    "max_output_tokens": OTHER_TOKENS},
        )
        # response.text can be None.
        return response.text or ""

    def send_images(self, prompt, image_uris):
        """Send a prompt and images (JPEG data URIs) to the Gemini API."""
        parts = []
        for uri in image_uris:
            header, data = uri.split(",", 1)
            media_type = header[len("data:"):].split(";")[0]
            parts.append(types.Part.from_bytes(
                data=base64.b64decode(data), mime_type=media_type))
        parts.append(prompt)
        # Kept in a variable, like send_prompt.
        client = self.sdk_client()
        response = client.models.generate_content(
            model=self.model, contents=parts,
            config={"max_output_tokens": OTHER_TOKENS})
        return response.text or ""

    def send_media(self, prompt, file_path, mime_type, seconds=None):
        """Send an audio or video file with a prompt and return the text.

        A video is cut to the first seconds on Google's side. Uploads
        are deleted right after the answer.
        """
        if not self.api_key:
            raise ValueError("No Gemini key is saved.")
        client = self.sdk_client(one_call=False)
        uploaded = None
        try:
            if os.path.getsize(file_path) <= INLINE_BYTES:
                with open(file_path, "rb") as file:
                    part = types.Part.from_bytes(data=file.read(),
                                                 mime_type=mime_type)
            else:
                uploaded = client.files.upload(
                    file=file_path, config={"mime_type": mime_type})
                uploaded = self.wait_for_file(client, uploaded)
                part = types.Part.from_uri(file_uri=uploaded.uri,
                                           mime_type=mime_type)
            if seconds and mime_type.startswith("video/"):
                part.video_metadata = types.VideoMetadata(
                    end_offset="{}s".format(int(seconds)))
            response = client.models.generate_content(
                model=self.model, contents=[part, prompt])
            return response.text or ""
        finally:
            if uploaded is not None:
                try:
                    client.files.delete(name=uploaded.name)
                except Exception:
                    # A file Google will drop on its own in two days.
                    pass

    def wait_for_file(self, client, uploaded):
        """Return the uploaded file once Google has processed it."""
        for _ in range(UPLOAD_WAIT_STEPS):
            state = str(getattr(uploaded, "state", "") or "")
            if not state.endswith("PROCESSING"):
                break
            time.sleep(2)
            uploaded = client.files.get(name=uploaded.name)
        if str(getattr(uploaded, "state", "") or "").endswith("FAILED"):
            raise RuntimeError("Google could not process the file.")
        return uploaded
