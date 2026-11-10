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


def fallback_for(ai, main_name):
    """Return the fallback client of the account's settings, or None."""
    saved = ai.get("fallback")
    if saved is None:
        # Claude steps in on its own when its key is in the keychain.
        if main_name == FALLBACK_PROVIDER:
            return None
        saved = {"provider_name": FALLBACK_PROVIDER, "model": FALLBACK_MODEL}
    client = create_client(saved["provider_name"], saved["model"],
                           ai.get("server_url") or None)
    # A fallback without a key would never answer.
    return client if getattr(client, "api_key", None) else None


def text_client(ai):
    """Build the text and image client, with its fallback.

    ai is the account's settings (ai_settings.load): one for every project.
    """
    main = ai.get("text")
    if not main:
        return None
    client = create_client(main["provider_name"], main["model"],
                           ai.get("server_url") or None)
    return ClientWithFallback(client,
                              fallback_for(ai, main["provider_name"]))


def media_client(ai):
    """Build the audio and video client, or None."""
    saved = ai.get("media")
    if not saved:
        return None
    return create_client(saved["provider_name"], saved["model"],
                         ai.get("server_url") or None)


def ready_media_client(ai):
    """Return the media client when it has a key, else None."""
    client = media_client(ai)
    if client is None or not getattr(client, "api_key", None):
        return None
    return client
