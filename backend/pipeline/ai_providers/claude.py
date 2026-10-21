"""Anthropic Claude provider."""

from backend.pipeline.ai_providers.base import AIProviderClient


class ClaudeClient(AIProviderClient):
    """Claude-specific implementation of AIProviderClient."""

    def __init__(self, model):
        """Initialize with the Claude provider name and chosen model.

        Args:
            model (str): Claude model to use
                (e.g. 'claude-haiku-4-5-20251001').
        """
        super().__init__(provider_name="claude", model=model)

    def send_classification_request(self, text):
        """Classify document text using Claude."""
        pass

    def send_summary_request(self, text):
        """Summarize document text using Claude."""
        pass

    def test_connection(self):
        """Test that the Claude API key is valid."""
        pass
