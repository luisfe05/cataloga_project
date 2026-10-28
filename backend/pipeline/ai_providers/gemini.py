"""Google Gemini provider."""

from google import genai

from backend.pipeline.ai_providers.base import AIProviderClient


class GeminiClient(AIProviderClient):
    """Gemini-specific implementation of AIProviderClient."""

    def __init__(self, model="gemini-2.5-flash"):
        """Initialize with the Gemini provider name and chosen model."""
        super().__init__(provider_name="gemini", model=model)

    def send_prompt(self, system_prompt, text):
        """Send one request to the Gemini API and return its answer."""
        client = genai.Client(api_key=self.api_key)
        response = client.models.generate_content(
            model=self.model,
            contents=text,
            config={"system_instruction": system_prompt},
        )
        # response.text can be None.
        return response.text or ""
