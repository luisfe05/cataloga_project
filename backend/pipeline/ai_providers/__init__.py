"""AI provider modules.

Each provider module contains a class that extends AIProviderClient and
implements send_prompt() for that specific provider's API.

Supported providers: Gemini, Groq, Claude, xAI, OpenAI.
API keys are read from the OS keyring at runtime, never from a file.
"""

from backend.pipeline.ai_providers.gemini import GeminiClient

# Maps the provider name used in settings to its client class.
# Groq, Claude, xAI, and OpenAI are added in task S2-4.
PROVIDERS = {
    "gemini": GeminiClient,
}


def create_client(provider_name, model):
    """Build the client for a provider by its name.

    Args:
        provider_name (str): A key of PROVIDERS, e.g. 'gemini'.
        model (str): The model to use.

    Returns:
        AIProviderClient: A ready-to-use client.

    Raises:
        ValueError: If the provider is not supported.
    """
    if provider_name not in PROVIDERS:
        raise ValueError("Unsupported AI provider: " + str(provider_name))
    return PROVIDERS[provider_name](model=model)
