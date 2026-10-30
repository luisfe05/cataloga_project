"""AI provider modules."""

from backend.pipeline.ai_providers.base import ClientWithFallback
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

# Used as the fallback when no fallback is chosen and its key exists.
FALLBACK_PROVIDER = "claude"
FALLBACK_MODEL = "claude-sonnet-5-5"

# The only provider that reads audio and video.
MEDIA_PROVIDER = "gemini"
MEDIA_MODEL = "gemini-3.5-flash-lite"

# What each role in ai_provider_config is for.
ROLES = ("text", "fallback", "media")


def create_client(provider_name, model, base_url=None):
    """Build the client for a provider by its name."""
    if provider_name not in PROVIDERS:
        raise ValueError("Unsupported AI provider: " + str(provider_name))
    return PROVIDERS[provider_name](model=model, base_url=base_url)


def fallback_for(repo, main_name):
    """Return the fallback client of a project, or None."""
    saved = repo.get_provider("fallback")
    if saved is None:
        # Claude steps in on its own when its key is in the keychain.
        if main_name == FALLBACK_PROVIDER:
            return None
        saved = {"provider_name": FALLBACK_PROVIDER, "model": FALLBACK_MODEL}
    client = create_client(saved["provider_name"], saved["model"],
                           repo.get_server_url())
    # A fallback without a key would never answer.
    return client if getattr(client, "api_key", None) else None


def project_client(repo):
    """Build the text and image client of a project, with its fallback."""
    main = repo.get_provider("text")
    if main is None:
        return None
    client = create_client(main["provider_name"], main["model"],
                           repo.get_server_url())
    return ClientWithFallback(client,
                              fallback_for(repo, main["provider_name"]))


def media_client(repo):
    """Build the audio and video client of a project, or None."""
    saved = repo.get_provider("media")
    if saved is None:
        return None
    return create_client(saved["provider_name"], saved["model"],
                         repo.get_server_url())
