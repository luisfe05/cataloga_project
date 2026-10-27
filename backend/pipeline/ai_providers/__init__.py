"""AI provider modules.

Each provider module contains a class that extends AIProviderClient and
implements send_prompt() for that specific provider's API.

Supported providers: Ollama Cloud (the default), Gemini, Groq, Claude,
xAI, OpenAI. API keys are read from the OS keyring at runtime. Only
Ollama Cloud can also read a development key (see ollama_cloud.py).
"""

from backend.pipeline.ai_providers.claude import ClaudeClient
from backend.pipeline.ai_providers.gemini import GeminiClient
from backend.pipeline.ai_providers.groq_provider import GroqClient
from backend.pipeline.ai_providers.ollama_cloud import OllamaCloudClient
from backend.pipeline.ai_providers.openai_provider import OpenAIClient
from backend.pipeline.ai_providers.xai import XAIClient

# Maps the provider name used in settings to its client class.
PROVIDERS = {
    "ollama": OllamaCloudClient,
    "gemini": GeminiClient,
    "groq": GroqClient,
    "claude": ClaudeClient,
    "xai": XAIClient,
    "openai": OpenAIClient,
}

# Provider and model every new project starts with. No key to type:
# see ollama_cloud.py for where the key comes from.
DEFAULT_PROVIDER = "ollama"
DEFAULT_MODEL = "gemma4:31b"


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
