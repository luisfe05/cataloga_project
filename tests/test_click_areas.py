"""Click areas: 44 px for the main controls, 24 px for everything else.

The real sizes are measured in the app with the test harness; this test
keeps the CSS that makes them from being lost.
"""

import os
import re

FRONTEND = os.path.join(os.path.dirname(__file__), "..", "frontend")

# The controls whose clicks reach 44 x 44 px through an invisible ::after.
MAIN = [".primary-button", ".secondary-button", ".pill-button", ".tab",
        ".review-go", ".mix-chip", ".help-button", ".link-button",
        ".read-more", ".file-link", ".file-action"]


def read(*parts):
    """Return the text of a frontend file."""
    with open(os.path.join(FRONTEND, *parts), encoding="utf-8") as file:
        return file.read()


def test_the_main_controls_take_clicks_in_44_px():
    """One ::after rule, 44 px at least, for every main control."""
    css = read("css", "main.css")
    # The selector list before the rule that sets the 44 px size.
    rule = re.search(r"([^{}]+)\{([^}]*max\(100%, 44px\)[^}]*)\}", css)
    selectors = re.findall(r"(\.[a-z-]+)::after", rule.group(1))
    for name in MAIN:
        assert name in selectors, name
    assert "width: max(100%, 44px)" in rule.group(2)
    assert "height: max(100%, 44px)" in rule.group(2)


def test_the_plan_checkboxes_sit_in_a_44_px_label():
    """The whole square around each box of To Approve is clickable."""
    css = read("css", "main.css")
    hit = re.search(r"\.check-hit\s*\{([^}]*)\}", css).group(1)
    assert "width: 44px" in hit and "height: 44px" in hit
    assert 'check.className = "check-hit"' in read("js", "plan.js")


def test_small_text_controls_are_at_least_24_px():
    """Advanced settings and the photo date choices."""
    css = read("css", "main.css")
    for selector in (r"\.advanced-settings summary",
                     r"\.settings-form \.naming-separator label"):
        body = re.search(selector + r"\s*\{([^}]*)\}", css).group(1)
        assert "min-height: 24px" in body
