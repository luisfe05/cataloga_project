"""AI provider modules."""

from backend.pipeline.ai_providers.claude import ClaudeClient
from backend.pipeline.ai_providers.gemini import GeminiClient
from backend.pipeline.ai_providers.groq_provider import GroqClient
from backend.pipeline.ai_providers.ollama_cloud import OllamaCloudClient
from backend.pipeline.ai_providers.openai_provider import OpenAIClient
from backend.pipeline.ai_providers.xai import XAIClient

PROVIDERS = {
    "ollama": OllamaCloudClient,
    "gemini": GeminiClient,
    "groq": GroqClient,
    "claude": ClaudeClient,
    "xai": XAIClient,
    "openai": OpenAIClient,
}

# New projects start here. See ollama_cloud.py for the key.
DEFAULT_PROVIDER = "ollama"
DEFAULT_MODEL = "gemma4:31b"


def create_client(provider_name, model):
    """Build the client for a provider by its name."""
    if provider_name not in PROVIDERS:
        raise ValueError("Unsupported AI provider: " + str(provider_name))
    return PROVIDERS[provider_name](model=model)
