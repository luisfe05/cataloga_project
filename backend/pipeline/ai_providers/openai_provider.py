"""OpenAI provider."""

from openai import OpenAI

from backend.pipeline.ai_providers.base import AIProviderClient


class OpenAIClient(AIProviderClient):
    """OpenAI-specific implementation of AIProviderClient."""

    def __init__(self, model="gpt-5.4-nano", base_url=None):
        """Initialize with the OpenAI provider name and chosen model."""
        super().__init__(provider_name="openai", model=model,
                         base_url=base_url)

    def send_prompt(self, system_prompt, text):
        """Send one request to the OpenAI API and return its answer."""
        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
        )
        return response.choices[0].message.content or ""
