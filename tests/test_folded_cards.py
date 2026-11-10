"""A folded card shows its summary on one line, with "…" when it is long."""

import os
import re

FRONTEND = os.path.join(os.path.dirname(__file__), "..", "frontend")

# An About text of more than 200 characters, with line breaks.
LONG_ABOUT = ("Work: A documentary about the Harbor Swimmers, a club that "
              "swims across the harbor of Port Alder at dawn.\n"
              "Industry: documentary and research\n"
              "Parts: interviews, press clippings from the Harbor Gazette, "
              "photos of the pier cleanup and recordings.")


def read(*parts):
    """Return the text of a frontend file."""
    with open(os.path.join(FRONTEND, *parts), encoding="utf-8") as file:
        return file.read()


def rule(css, selector):
    """The body of the first CSS rule for exactly this selector."""
    found = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert found, selector
    return found.group(1)


def one_line(text):
    """What oneLine() in settings.js does, for the test."""
    return re.sub(r"\s+", " ", text).strip()


def test_the_summary_is_one_line_cut_with_an_ellipsis():
    """nowrap, hidden overflow, ellipsis, and min-width 0 in the flex row."""
    css = read("css", "main.css")
    text = rule(css, ".card-row-text")
    for line in ("white-space: nowrap", "overflow: hidden",
                 "text-overflow: ellipsis", "min-width: 0", "flex: 1"):
        assert line in text
    assert "min-width: 0" in rule(css, ".card-row")


def test_change_is_never_pushed_or_covered():
    """Change and the title keep their size; only the summary shrinks."""
    css = read("css", "main.css")
    change = rule(css, ".card-row .card-change")
    assert "flex: none" in change and "margin-left: auto" in change
    assert "flex: none" in rule(css, ".card-row-title")
    html = read("index.html")
    # Settings and New Project use the same cards: each row ends in Change.
    for card in ("project-section", "sheet-section", "naming-section",
                 "folders-section"):
        section = html[html.index('id="{}"'.format(card)):]
        row = section[:section.index("</div>")]
        assert row.index('class="card-row-text"') < row.index("card-change")


def test_line_breaks_show_as_spaces_in_the_folded_about():
    """The whole About text, on one line; the saved text does not change."""
    js = read("js", "settings.js")
    assert 'oneLine(sheet)' in js
    assert 'sheet.split("\\n")[0]' not in js
    assert re.search(r'function oneLine\(text\) \{\s*return String\(text '
                     r'\|\| ""\)\.replace\(/\\s\+/g, " "\)\.trim\(\);', js)
    shown = one_line(LONG_ABOUT)
    assert len(LONG_ABOUT) > 200 and "\n" in LONG_ABOUT
    assert "\n" not in shown
    assert shown.startswith("Work: A documentary") and \
        shown.endswith("recordings.")
    # Only the folded row changes: the field keeps the text as saved.
    assert 'document.getElementById("project-sheet").value =' in js
