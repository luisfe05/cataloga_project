"""OpenAI provider."""

from backend.pipeline.ai_providers.base import AIProviderClient


class OpenAIClient(AIProviderClient):
    """OpenAI-specific implementation of AIProviderClient."""

    def __init__(self, model):
        """Initialize with the OpenAI provider name and chosen model.

        Args:
            model (str): OpenAI model to use (e.g. 'gpt-4o-mini').
        """
        super().__init__(provider_name="openai", model=model)

    def send_classification_request(self, text):
        """Classify document text using OpenAI."""
        pass

    def send_summary_request(self, text):
        """Summarize document text using OpenAI."""
        pass

    def test_connection(self):
        """Test that the OpenAI API key is valid."""
        pass
