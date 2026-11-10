"""Tests for the help balloons ("?") of Settings: five, in both languages."""

import json
import os
import re
import subprocess

import pytest

FRONTEND = os.path.join(os.path.dirname(__file__), "..", "frontend")

# The five "?" of Settings, as approved on Nov 9.
# In page order: Now / Later comes before Use a Drop Zone since Nov 9.
FIVE = ["help.archive", "help.drop_zone", "naming.help_names",
        "help.folders", "help.language"]


def settings_html():
    """The Settings view of index.html, every card included."""
    with open(os.path.join(FRONTEND, "index.html"), encoding="utf-8") as file:
        html = file.read()
    return html[html.index('id="view-settings"'):html.index("<!-- Toast")]


def language(name):
    """Read en.js or es.js with node and return its keys and texts."""
    path = os.path.join(FRONTEND, "js", "lang", name + ".js")
    variable = "LANG_" + name.upper()
    script = ('const fs = require("fs");'
              'const f = new Function(fs.readFileSync(process.argv[1], '
              '"utf8") + "\\nreturn {};");'
              'process.stdout.write(JSON.stringify(f()));').format(variable)
    answer = subprocess.run(["node", "-e", script, path],
                            capture_output=True, text=True, check=True)
    return json.loads(answer.stdout)


def test_settings_has_exactly_the_five_help_balloons():
    """Drop Zone, Now and Later, File names, Folder names, Language.

    Categories (old projects only) says its text in a gray line instead.
    """
    assert re.findall(r'data-help="([^"]+)"', settings_html()) == FIVE


@pytest.mark.parametrize("name", ["en", "es"])
def test_each_balloon_has_its_text(name):
    """Every one of the five has a text in English and in Spanish."""
    texts = language(name)
    for key in FIVE:
        assert texts[key].strip()


def test_now_and_later_explain_catalog_only_in_three_sentences():
    """Catalog only lost its own "?"; Now and Later say it instead."""
    for name, word in (("en", "Catalog only"), ("es", "Solo catalogar")):
        text = language(name)["help.archive"]
        assert word in text
        assert text.count(". ") == 2 and text.endswith(".")


def test_the_removed_texts_are_gone_or_moved():
    """No key left without use; the folder note and placeholder exist."""
    texts = language("en")
    for key in ("help.folder", "help.catalog_only", "help.sheet",
                "help.ai_provider", "help.account", "help.remove_project",
                "naming.help_style"):
        assert key not in texts
    assert texts["project.folder_locked"].startswith("The project folder")
    assert texts["sheet.placeholder"].startswith("A few lines")
    assert texts["value.Undone"] and language("es")["value.Undone"] == \
        "Deshecho"
