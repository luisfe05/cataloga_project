"""Anthropic Claude provider."""

import anthropic

from backend.pipeline.ai_providers.base import AIProviderClient

# Cataloga's answers are short: a label, a summary, or small JSON.
MAX_ANSWER_TOKENS = 1024


class ClaudeClient(AIProviderClient):
    """Claude-specific implementation of AIProviderClient."""

    def __init__(self, model="claude-haiku-5-5"):
        """Initialize with the Claude provider name and chosen model."""
        super().__init__(provider_name="claude", model=model)

    def send_prompt(self, system_prompt, text):
        """Send one request to the Claude API and return its answer."""
        client = anthropic.Anthropic(api_key=self.api_key)
        response = client.messages.create(
            model=self.model,
            max_tokens=MAX_ANSWER_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": text}],
        )
        # The answer is a list of blocks; join the text ones.
        return "".join(block.text for block in response.content
                       if block.type == "text")
