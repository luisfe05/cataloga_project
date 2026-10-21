"""AI provider modules.

Each provider module contains a class that extends AIProviderClient and
implements send_classification_request(), send_summary_request(), and
test_connection() for that specific provider's API.

Supported providers: Gemini, Groq, Claude, xAI, OpenAI.
API keys are read from the OS keyring at runtime, never from a file.
"""
