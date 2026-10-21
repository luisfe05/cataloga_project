"""AIProviderClient base class.

Defines the interface that every provider module must implement.
The ClassificationPipeline always talks to an AIProviderClient, so
swapping providers only means changing which subclass is instantiated.

API keys are fetched from the OS keyring at runtime using the keyring library.
They are never passed in at construction time or stored in memory
longer than needed.
"""

import keyring

# keyring service name used across all providers.
KEYRING_SERVICE = "cataloga"


class AIProviderClient:
    """Abstract base for AI provider integrations."""

    def __init__(self, provider_name, model):
        """Store provider identity; fetch the API key from the OS keyring.

        Args:
            provider_name (str): Name used as the keyring username
                (e.g. 'gemini').
            model (str): The model to use for requests
                (e.g. 'gemini-2.5-flash').
        """
        self.provider_name = provider_name
        self.model = model
        # Key is fetched here so it is available for the session, but never
        # written to disk or logged.
        self.api_key = keyring.get_password(KEYRING_SERVICE, provider_name)

    def send_classification_request(self, text):
        """Send document text to the AI and return the media type label.

        Args:
            text (str): Extracted text from the document.

        Returns:
            str: One of Press / Audio / Video / Photos / Documents.
        """
        raise NotImplementedError

    def send_summary_request(self, text):
        """Send document text to the AI and return a summary.

        Args:
            text (str): Extracted text from the document.

        Returns:
            str: Summary, up to 500 characters. Empty string on failure.
        """
        raise NotImplementedError

    def test_connection(self):
        """Check that the API key and model work with a small test call.

        Returns:
            bool: True if the connection succeeds.

        Raises:
            Exception: With a descriptive message if the connection fails.
        """
        raise NotImplementedError
