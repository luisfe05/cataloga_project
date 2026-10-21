"""xAI (Grok) provider.

xAI uses an OpenAI-compatible API, so this client uses the openai package
pointed at xAI's base URL.
"""

from openai import OpenAI

from backend.pipeline.ai_providers.base import AIProviderClient

# Where xAI's OpenAI-compatible API lives.
XAI_BASE_URL = "https://api.x.ai/v1"


class XAIClient(AIProviderClient):
    """xAI Grok implementation using the OpenAI-compatible API."""

    def __init__(self, model="grok-4.7"):
        """Initialize with the xAI provider name and chosen model.

        Args:
            model (str): xAI model to use. Defaults to grok-4.7.
        """
        super().__init__(provider_name="xai", model=model)

    def send_prompt(self, system_prompt, text):
        """Send one request to the xAI API and return its answer.

        Args:
            system_prompt (str): The instructions for the AI.
            text (str): The content the instructions apply to.

        Returns:
            str: Grok's answer as plain text.
        """
        client = OpenAI(api_key=self.api_key, base_url=XAI_BASE_URL)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
        )
        return response.choices[0].message.content or ""
