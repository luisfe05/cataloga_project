"""Ollama Cloud provider, the default for new projects."""

import os
import sys

from openai import OpenAI

from backend.pipeline.ai_providers.base import AIProviderClient

OLLAMA_BASE_URL = "https://ollama.com/v1"

# Models that accept images. nemotron-3-nano:30b does not.
VISION_MODELS = ("gemma4:31b",)

# Environment variable (and .env line) for development.
ENV_KEY_NAME = "OLLAMA_API_KEY"

# The cataloga folder, four levels up from this file.
CODE_FOLDER = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
ENV_PATH = os.path.join(CODE_FOLDER, ".env")


def read_env_file(path):
    """Return the OLLAMA_API_KEY value written in a .env file."""
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            if name.strip() == ENV_KEY_NAME:
                # Remove quotes, as in OLLAMA_API_KEY="abc".
                return value.strip().strip("\"'") or None
    return None


def read_development_key():
    """Return the Ollama key from the environment or .env, or None."""
    if getattr(sys, "frozen", False):
        return None
    return os.environ.get(ENV_KEY_NAME) or read_env_file(ENV_PATH)


class OllamaCloudClient(AIProviderClient):
    """Ollama Cloud implementation using the OpenAI-compatible API."""

    def __init__(self, model="gemma4:31b", base_url=None):
        """Initialize with the Ollama provider name and chosen model."""
        super().__init__(provider_name="ollama", model=model,
                         base_url=base_url or OLLAMA_BASE_URL)
        if not self.api_key:
            self.api_key = read_development_key()

    def send_prompt(self, system_prompt, text):
        """Send one request to Ollama Cloud and return its answer."""
        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
        )
        return response.choices[0].message.content or ""

    @property
    def supports_images(self):
        """Say whether the chosen model can look at images."""
        return self.model in VISION_MODELS

    def send_images(self, prompt, image_uris):
        """Send a prompt and images (JPEG data URIs) to Ollama Cloud."""
        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        content = [{"type": "text", "text": prompt}]
        for uri in image_uris:
            content.append({"type": "image_url", "image_url": {"url": uri}})
        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": content}],
        )
        return response.choices[0].message.content or ""
