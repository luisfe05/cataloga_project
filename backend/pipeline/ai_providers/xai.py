"""xAI (Grok) provider.

xAI uses an OpenAI-compatible API, so this client uses the openai package
pointed at xAI's base URL.
"""

from backend.pipeline.ai_providers.base import AIProviderClient


class XAIClient(AIProviderClient):
    """xAI Grok implementation using the OpenAI-compatible API."""

    def __init__(self, model):
        """Initialize with the xAI provider name and chosen model.

        Args:
            model (str): xAI model to use (e.g. 'grok-3-mini').
        """
        super().__init__(provider_name="xai", model=model)

    def send_classification_request(self, text):
        """Classify document text using xAI."""
        pass

    def send_summary_request(self, text):
        """Summarize document text using xAI."""
        pass

    def test_connection(self):
        """Test that the xAI API key is valid."""
        pass
