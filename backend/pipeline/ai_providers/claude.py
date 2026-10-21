"""Anthropic Claude provider."""

import anthropic

from backend.pipeline.ai_providers.base import AIProviderClient

# Longest answer to ask for. Cataloga's answers are short (a label, a
# summary under 500 characters, or a small JSON object).
MAX_ANSWER_TOKENS = 1024


class ClaudeClient(AIProviderClient):
    """Claude-specific implementation of AIProviderClient."""

    def __init__(self, model="claude-haiku-5-5"):
        """Initialize with the Claude provider name and chosen model.

        Args:
            model (str): Claude model to use. Defaults to
                claude-haiku-5-5, the lowest-cost option.
        """
        super().__init__(provider_name="claude", model=model)

    def send_prompt(self, system_prompt, text):
        """Send one request to the Claude API and return its answer.

        Args:
            system_prompt (str): The instructions for the AI.
            text (str): The content the instructions apply to.

        Returns:
            str: Claude's answer as plain text.
        """
        client = anthropic.Anthropic(api_key=self.api_key)
        response = client.messages.create(
            model=self.model,
            max_tokens=MAX_ANSWER_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": text}],
        )
        # The answer comes as a list of blocks; join the text ones.
        return "".join(block.text for block in response.content
                       if block.type == "text")
