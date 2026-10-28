"""Tests for the interface language files."""

import os
import re

LANG_FOLDER = os.path.join(os.path.dirname(__file__), "..", "frontend",
                           "js", "lang")

# Matches a key at the start of a line, like:     "nav.catalog": ...
KEY_PATTERN = re.compile(r'^\s*"([^"]+)":', re.MULTILINE)


def read_entries(file_name):
    """Return {key: text} from a language file."""
    with open(os.path.join(LANG_FOLDER, file_name), encoding="utf-8") as f:
        content = f.read()
    matches = list(KEY_PATTERN.finditer(content))
    entries = {}
    for index, match in enumerate(matches):
        end = (matches[index + 1].start() if index + 1 < len(matches)
               else len(content))
        entries[match.group(1)] = content[match.end():end]
    return entries


def test_both_languages_have_the_same_keys():
    """No key is missing from either file."""
    assert set(read_entries("en.js")) == set(read_entries("es.js"))


def test_both_languages_use_the_same_variables():
    """{n}, {path} and the rest appear in both versions of a text."""
    english = read_entries("en.js")
    spanish = read_entries("es.js")
    for key in english:
        en_vars = set(re.findall(r"\{\w+\}", english[key]))
        es_vars = set(re.findall(r"\{\w+\}", spanish[key]))
        assert en_vars == es_vars, key


def test_old_inbox_warning_text():
    """The warning text matches the approved wording."""
    assert "Your old Inbox folder still has files." in \
        read_entries("en.js")["catalog.old_inbox_warning"]
    assert "Tu carpeta Inbox vieja todavía tiene" in \
        read_entries("es.js")["catalog.old_inbox_warning"]
