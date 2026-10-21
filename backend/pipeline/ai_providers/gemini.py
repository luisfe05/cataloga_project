"""Google Gemini provider."""

from backend.pipeline.ai_providers.base import AIProviderClient


class GeminiClient(AIProviderClient):
    """Gemini-specific implementation of AIProviderClient."""

    def __init__(self, model="gemini-2.5-flash"):
        """Initialize with the Gemini provider name and chosen model.

        Args:
            model (str): Gemini model to use. Defaults to gemini-2.5-flash.
        """
        super().__init__(provider_name="gemini", model=model)

    def send_classification_request(self, text):
        """Classify document text using Gemini."""
        pass

    def send_summary_request(self, text):
        """Summarize document text using Gemini."""
        pass

    def test_connection(self):
        """Test that the Gemini API key is valid."""
        pass
