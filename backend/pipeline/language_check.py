"""Is a text the AI wrote in the app's language? A simple local check.

Nothing is sent anywhere and no library is needed: the script of the
letters (Latin or not), and a few common words of English and Spanish.
Proper names, quotes and original titles may keep their own language, so
text between quotation marks is left out of the check.
"""

import re
import unicodedata

# The app's languages and the name the prompt uses for each.
LANGUAGE_NAMES = {"en": "English", "es": "Spanish"}
DEFAULT_LANGUAGE = "en"

# Short words that show the language of a sentence. Words both languages
# use ("a", "no", "me") are left out.
COMMON_WORDS = {
    "en": {"the", "of", "and", "with", "for", "from", "about", "is", "this",
           "that", "his", "her", "their", "on", "at", "by", "an", "to",
           "its", "who", "which", "photo", "letter", "report"},
    "es": {"el", "la", "los", "las", "del", "de", "y", "con", "para", "sobre",
           "es", "este", "esta", "que", "su", "sus", "una", "un", "por",
           "en", "al", "foto", "carta", "informe"},
}

# Above this share of non-Latin letters, the text is in another script.
OTHER_SCRIPT_SHARE = 0.3

# Quoted parts: '...', "...", «...», “...”, ‘...’.
QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"|«[^»]*»|“[^”]*”|‘[^’]*’")


def language_name(language):
    """Return English or Spanish for a language code (English if unknown)."""
    return LANGUAGE_NAMES.get(language, LANGUAGE_NAMES[DEFAULT_LANGUAGE])


def unquoted(text):
    """Return the text without its quoted parts (titles, quotes)."""
    return QUOTED.sub(" ", text or "")


def other_script(text):
    """Say whether most letters are not Latin (Cyrillic, Greek, Arabic...)."""
    letters = [char for char in unquoted(text) if char.isalpha()]
    if not letters:
        return False
    other = [char for char in letters
             if not unicodedata.name(char, "").startswith("LATIN")]
    return len(other) / len(letters) > OTHER_SCRIPT_SHARE


def common_word_count(text, language):
    """Count the common words of one language in a text."""
    words = re.findall(r"[^\W\d_]+", unquoted(text).lower())
    return sum(1 for word in words if word in COMMON_WORDS[language])


def other_language(text, language):
    """Say whether a Latin text reads as the other app language.

    Only a clear case counts: two or more common words of the other
    language and none of the one asked for. A short text with no common
    words passes, so a good summary is never thrown away.
    """
    others = [code for code in COMMON_WORDS if code != language]
    asked = common_word_count(text, language) if language in COMMON_WORDS \
        else 0
    return asked == 0 and any(common_word_count(text, code) >= 2
                              for code in others)


def wrong_language(text, language):
    """Say whether a text is not in the language the app asked for."""
    if not text:
        return False
    return other_script(text) or other_language(text, language)
