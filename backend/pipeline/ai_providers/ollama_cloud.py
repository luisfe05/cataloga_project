"""Ollama Cloud provider, the default for new projects.

Ollama Cloud runs open models (like Gemma) and has an OpenAI-compatible
API, so this client uses the openai package pointed at Ollama's base
URL, like the xAI client.

Where the API key comes from, in this order:
1. The OS keyring, like every other provider.
2. Only when running from the code (not the packaged app): the
   OLLAMA_API_KEY environment variable, or the same line in the
   cataloga/.env file. This is for development. Git ignores .env and
   build.sh never puts it inside the app.
"""

import os
import sys

from openai import OpenAI

from backend.pipeline.ai_providers.base import AIProviderClient

# Where Ollama Cloud's OpenAI-compatible API lives.
OLLAMA_BASE_URL = "https://ollama.com/v1"

# Name of the environment variable (and .env line) for development.
ENV_KEY_NAME = "OLLAMA_API_KEY"

# The cataloga folder, four levels up from this file.
CODE_FOLDER = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
ENV_PATH = os.path.join(CODE_FOLDER, ".env")


def read_env_file(path):
    """Return the OLLAMA_API_KEY value written in a .env file.

    Each line of a .env file looks like NAME=value. Blank lines and
    lines starting with # are ignored.

    Args:
        path (str): Path to the .env file.

    Returns:
        str or None: The value, or None if the file or line is missing.
    """
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
    """Return the Ollama key from the environment or .env, or None.

    The packaged app never reads it: PyInstaller sets sys.frozen there.

    Returns:
        str or None: The key, or None if there is none.
    """
    if getattr(sys, "frozen", False):
        return None
    return os.environ.get(ENV_KEY_NAME) or read_env_file(ENV_PATH)


class OllamaCloudClient(AIProviderClient):
    """Ollama Cloud implementation using the OpenAI-compatible API."""

    def __init__(self, model="gemma4:31b"):
        """Initialize with the Ollama provider name and chosen model.

        The key from the keyring wins. The development key is only used
        when the keyring has none.

        Args:
            model (str): Ollama model to use. Defaults to gemma4:31b.
        """
        super().__init__(provider_name="ollama", model=model)
        if not self.api_key:
            self.api_key = read_development_key()

    def send_prompt(self, system_prompt, text):
        """Send one request to Ollama Cloud and return its answer.

        Args:
            system_prompt (str): The instructions for the AI.
            text (str): The content the instructions apply to.

        Returns:
            str: The model's answer as plain text.
        """
        client = OpenAI(api_key=self.api_key, base_url=OLLAMA_BASE_URL)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
        )
        return response.choices[0].message.content or ""
