"""Google Gemini provider."""

import base64

from google import genai
from google.genai import types

from backend.pipeline.ai_providers.base import AIProviderClient


class GeminiClient(AIProviderClient):
    """Gemini-specific implementation of AIProviderClient."""

    # Every Gemini model looks at images.
    supports_images = True

    def __init__(self, model="gemini-3.5-flash-lite", base_url=None):
        """Initialize with the Gemini provider name and chosen model."""
        super().__init__(provider_name="gemini", model=model,
                         base_url=base_url)

    def sdk_client(self):
        """Build the SDK client, aimed at the relay server if there is one."""
        if self.base_url:
            return genai.Client(api_key=self.api_key,
                                http_options={"base_url": self.base_url})
        return genai.Client(api_key=self.api_key)

    def send_prompt(self, system_prompt, text):
        """Send one request to the Gemini API and return its answer."""
        response = self.sdk_client().models.generate_content(
            model=self.model,
            contents=text,
            config={"system_instruction": system_prompt},
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
        response = self.sdk_client().models.generate_content(
            model=self.model, contents=parts)
        return response.text or ""
