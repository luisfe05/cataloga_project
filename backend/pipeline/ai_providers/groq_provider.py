"""Groq provider.

Groq runs open models (like Llama) very fast and has a free tier, which
fits Cataloga's goal of working within free or low-cost API limits.
"""

from groq import Groq

from backend.pipeline.ai_providers.base import AIProviderClient


class GroqClient(AIProviderClient):
    """Groq-specific implementation of AIProviderClient."""

    def __init__(self, model="llama-3.1-8b-instant"):
        """Initialize with the Groq provider name and chosen model.

        Args:
            model (str): Groq model to use. Defaults to
                llama-3.1-8b-instant, which has the highest free daily
                limit.
        """
        super().__init__(provider_name="groq", model=model)

    def send_prompt(self, system_prompt, text):
        """Send one request to the Groq API and return its answer.

        Args:
            system_prompt (str): The instructions for the AI.
            text (str): The content the instructions apply to.

        Returns:
            str: The model's answer as plain text.
        """
        client = Groq(api_key=self.api_key)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
        )
        return response.choices[0].message.content or ""
