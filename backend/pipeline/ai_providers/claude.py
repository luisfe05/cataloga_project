"""Anthropic Claude provider."""

import anthropic

from backend.pipeline.ai_providers.base import AIProviderClient

# Cataloga's answers are short: a label, a summary, or small JSON. The
# model also thinks a little before answering, and that counts here.
MAX_ANSWER_TOKENS = 4096

# Short answers need little thinking.
EFFORT = "low"


def image_block(data_uri):
    """Turn a JPEG data URI into the image block the API expects."""
    header, data = data_uri.split(",", 1)
    media_type = header[len("data:"):].split(";")[0]
    return {"type": "image",
            "source": {"type": "base64", "media_type": media_type,
                       "data": data}}


class ClaudeClient(AIProviderClient):
    """Claude-specific implementation of AIProviderClient."""

    # Every current Claude model looks at images.
    supports_images = True

    def __init__(self, model="claude-sonnet-5-5", base_url=None):
        """Initialize with the Claude provider name and chosen model."""
        super().__init__(provider_name="claude", model=model,
                         base_url=base_url)

    def sdk_client(self):
        """Build the SDK client, aimed at the relay server if there is one."""
        if self.base_url:
            return anthropic.Anthropic(api_key=self.api_key,
                                       base_url=self.base_url)
        return anthropic.Anthropic(api_key=self.api_key)

    def send(self, system_prompt, content):
        """Send one request and return the text of the answer."""
        response = self.sdk_client().messages.create(
            model=self.model,
            max_tokens=MAX_ANSWER_TOKENS,
            # The system prompt repeats for every file, so it is cached.
            system=[{"type": "text", "text": system_prompt,
                     "cache_control": {"type": "ephemeral"}}],
            output_config={"effort": EFFORT},
            messages=[{"role": "user", "content": content}],
        )
        # The answer is a list of blocks; join the text ones.
        return "".join(block.text for block in response.content
                       if block.type == "text")

    def send_prompt(self, system_prompt, text):
        """Send one request to the Claude API and return its answer."""
        return self.send(system_prompt, text)

    def send_images(self, prompt, image_uris):
        """Send a prompt and images (JPEG data URIs) to the Claude API."""
        content = [image_block(uri) for uri in image_uris]
        content.append({"type": "text", "text": prompt})
        return self.send(prompt, content)
