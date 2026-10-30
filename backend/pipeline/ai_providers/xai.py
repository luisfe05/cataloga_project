"""xAI (Grok) provider."""

from openai import OpenAI

from backend.pipeline.ai_providers.base import AIProviderClient

XAI_BASE_URL = "https://api.x.ai/v1"


class XAIClient(AIProviderClient):
    """xAI Grok implementation using the OpenAI-compatible API."""

    def __init__(self, model="grok-4.7", base_url=None):
        """Initialize with the xAI provider name and chosen model."""
        super().__init__(provider_name="xai", model=model,
                         base_url=base_url or XAI_BASE_URL)

    def send_prompt(self, system_prompt, text):
        """Send one request to the xAI API and return its answer."""
        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
        )
        return response.choices[0].message.content or ""
