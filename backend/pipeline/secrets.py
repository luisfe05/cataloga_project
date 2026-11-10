"""Hide keys, tokens and passwords in text before it goes to a provider.

Every text that leaves the app passes through redact_secrets() once, in
AIProviderClient.ask(). The pipeline also calls it on a file's text to
count what was hidden; the catalog keeps that number, never the secret.
"""

import re

REDACTED = "[REDACTED]"

# A value already hidden must not count again when the text is checked twice.
NOT_REDACTED = r"(?!\[REDACTED\])"

# Keys with a known shape. The first part names the service, the rest is
# the random part, long enough that a normal word never matches.
KEY_PATTERNS = [
    r"\bsk-ant-[A-Za-z0-9_-]{20,}",          # Anthropic
    r"\bsk-[A-Za-z0-9_-]{16,}",              # OpenAI and others
    r"\bAIza[0-9A-Za-z_-]{30,}",             # Google
    r"\bgh[pousr]_[A-Za-z0-9]{30,}",         # GitHub tokens
    r"\bgithub_pat_[A-Za-z0-9_]{20,}",       # GitHub fine-grained tokens
    r"\bxox[abposr]-[A-Za-z0-9-]{10,}",      # Slack
    r"\bAKIA[0-9A-Z]{16}\b",                 # AWS access key id
    r"\bgsk_[A-Za-z0-9]{16,}",               # Groq
    r"\bxai-[A-Za-z0-9]{16,}",               # xAI
    r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}",  # JWT
    r"(?<=Bearer\s)[A-Za-z0-9._-]{20,}",     # a pasted Authorization header
]

# A private key block, with or without its END line.
PRIVATE_KEY_BLOCK = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"(?:.*?-----END [A-Z ]*PRIVATE KEY-----|.*)", re.S)

# scheme://user:password@host. The user and the password both go.
URL_CREDENTIALS = re.compile(
    r"(?<=://)[^/\s:@]+:[^/\s@]+(?=@)")

# "password: hunter2", "API_KEY=abc", "contraseña: ...": only the value is
# hidden, so the line still says what it was. Words in English and Spanish.
LABELS = (r"password|passwd|pwd|contrase[ñn]a|clave|secret|token|"
          r"api[ _-]?key|apikey|access[ _-]?key|secret[ _-]?key|"
          r"client[ _-]?secret|private[ _-]?key|auth[ _-]?token")
LABELED_VALUE = re.compile(
    r"(?i)(\b(?:" + LABELS + r")\b[\"']?\s*[:=]\s*[\"']?)" + NOT_REDACTED +
    r"([^\s\"',;]+)")

KEYS = [re.compile(pattern) for pattern in KEY_PATTERNS]


def redact_secrets(text):
    """Return (text with every secret replaced, how many were replaced)."""
    if not isinstance(text, str) or not text:
        return text, 0
    count = 0
    # The whole block first, so its lines never match the shorter patterns.
    text, found = PRIVATE_KEY_BLOCK.subn(REDACTED, text)
    count += found
    text, found = URL_CREDENTIALS.subn(REDACTED, text)
    count += found
    for pattern in KEYS:
        text, found = pattern.subn(REDACTED, text)
        count += found
    text, found = LABELED_VALUE.subn(r"\g<1>" + REDACTED, text)
    count += found
    return text, count


def redact(text):
    """Return only the redacted text, for callers that keep no count."""
    return redact_secrets(text)[0]
