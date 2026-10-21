"""Groq provider."""

from backend.pipeline.ai_providers.base import AIProviderClient


class GroqClient(AIProviderClient):
    """Groq-specific implementation of AIProviderClient."""

    def __init__(self, model):
        """Initialize with the Groq provider name and chosen model.

        Args:
            model (str): Groq model to use (e.g. 'llama-3.3-70b-versatile').
        """
        super().__init__(provider_name="groq", model=model)

    def send_classification_request(self, text):
        """Classify document text using Groq."""
        pass

    def send_summary_request(self, text):
        """Summarize document text using Groq."""
        pass

    def test_connection(self):
        """Test that the Groq API key is valid."""
        pass
