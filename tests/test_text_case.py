"""English titles are in Title Case; status values read the same everywhere."""

import json
import os
import re
import subprocess

FRONTEND = os.path.join(os.path.dirname(__file__), "..", "frontend")

# Titles named by convention (*.title, *_title, *_heading), plus screen,
# tab and card titles that have other names.
TITLE_KEYS = ["nav.home", "nav.catalog", "nav.plan", "nav.dashboard",
              "nav.settings", "nav.projects", "catalog.progress",
              "dash.classified", "dash.review", "dash.sources",
              "dash.activity", "dash.media_mix", "dash.top_sources",
              "settings.tab_project", "settings.tab_general"]

# Short words that stay in lowercase inside a title.
MINOR = {"a", "an", "and", "as", "at", "but", "by", "for", "from", "in",
         "into", "of", "on", "or", "the", "to", "with"}


def language(name):
    """Read en.js or es.js with node and return its keys and texts."""
    path = os.path.join(FRONTEND, "js", "lang", name + ".js")
    script = ('const fs = require("fs");'
              'const f = new Function(fs.readFileSync(process.argv[1], '
              '"utf8") + "\\nreturn LANG_{};");'
              'process.stdout.write(JSON.stringify(f()));').format(
                  name.upper())
    answer = subprocess.run(["node", "-e", script, path],
                            capture_output=True, text=True, check=True)
    return json.loads(answer.stdout)


def title_keys(texts):
    """Every key that names a title."""
    named = [key for key in texts
             if re.search(r"(\.title|_title|_heading)$", key)]
    return sorted(set(named + TITLE_KEYS))


def not_title_case(text):
    """The words of a title that should start with a capital, but do not."""
    wrong = []
    for index, word in enumerate(text.split()):
        word = word.strip("()\"'·,:")
        if not word or word.startswith("{") or not word[0].isalpha():
            continue
        if index > 0 and word.lower() in MINOR:
            continue
        if not word[0].isupper():
            wrong.append(word)
    return wrong


def test_english_titles_are_in_title_case():
    """Screen, card and section titles; questions and sentences are not."""
    texts = language("en")
    problems = {}
    for key in title_keys(texts):
        text = texts[key]
        if text.rstrip().endswith(("?", ".")):
            continue
        wrong = not_title_case(text)
        if wrong:
            problems[key] = wrong
    assert problems == {}


def test_spanish_titles_only_start_with_a_capital():
    """Spanish keeps sentence case: no word after the first is capitalized,
    except names (Cataloga, IA, Drop Zone)."""
    names = {"Cataloga", "IA", "Drop", "Zone", "Harbor"}
    texts = language("es")
    problems = {}
    for key in title_keys(texts):
        words = texts[key].strip("¿?").split()
        wrong = [w for w in words[1:] if w[:1].isupper() and w not in names
                 and not w.startswith("{")]
        if wrong:
            problems[key] = wrong
    assert problems == {}


def test_status_values_read_the_same_in_home():
    """Home's counts use the same words as the status column."""
    texts = language("en")
    assert texts["value.Classified"] in texts["home.classified"]
    assert texts["value.Manual Review"] in texts["home.manual_review"]


def test_home_switch_uses_the_sidebar_names():
    """Home and Catalog List, the same two names as the sidebar."""
    with open(os.path.join(FRONTEND, "index.html"), encoding="utf-8") as file:
        html = file.read()
    tabs = html[html.index('class="home-tabs"'):]
    tabs = tabs[:tabs.index("</div>")]
    assert re.findall(r'data-i18n="([^"]+)"', tabs) == ["nav.home",
                                                        "nav.catalog"]
