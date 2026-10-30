"""Groq provider."""

from groq import Groq

from backend.pipeline.ai_providers.base import AIProviderClient


class GroqClient(AIProviderClient):
    """Groq-specific implementation of AIProviderClient."""

    def __init__(self, model="llama-3.1-8b-instant", base_url=None):
        """Initialize with the Groq provider name and chosen model."""
        super().__init__(provider_name="groq", model=model,
                         base_url=base_url)

    def send_prompt(self, system_prompt, text):
        """Send one request to the Groq API and return its answer."""
        client = Groq(api_key=self.api_key, base_url=self.base_url)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
        )
        return response.choices[0].message.content or ""
