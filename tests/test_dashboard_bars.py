"""Tests for the gradients of the Media Type Breakdown bars."""

import os
import re

DASHBOARD_JS = os.path.join(os.path.dirname(__file__), "..", "frontend",
                            "js", "dashboard.js")

PALETTE = {"#08051c": "Deep Space", "#221854": "Midnight",
           "#342476": "Nebula", "#46417b": "Dusk", "#493bb2": "Violet",
           "#eef5fa": "Paper"}
MEDIA_TYPES = {"Documents", "Audio", "Video", "Press", "Photos"}


def read_gradients():
    """Return {media type: [colors bottom to top]} from dashboard.js."""
    with open(DASHBOARD_JS, encoding="utf-8") as file:
        content = file.read()
    table = re.search(r"BAR_GRADIENTS = \{(.*?)\};", content, re.S).group(1)
    return {name: re.findall(r"#[0-9a-f]{6}", value)
            for name, value in re.findall(r'(\w+): "([^"]+)"', table)}


def luminance(color):
    """Relative luminance of a #rrggbb color (WCAG)."""
    channels = []
    for start in (1, 3, 5):
        value = int(color[start:start + 2], 16) / 255
        channels.append(value / 12.92 if value <= 0.03928
                        else ((value + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast(first, second):
    """WCAG contrast ratio between two colors."""
    light, dark = sorted([luminance(first), luminance(second)], reverse=True)
    return (light + 0.05) / (dark + 0.05)


def test_every_media_type_has_a_gradient():
    """One gradient for each of the five bars, no more."""
    assert set(read_gradients()) == MEDIA_TYPES


def test_gradients_use_two_or_three_palette_colors():
    """Only brand colors, two or three per bar."""
    for colors in read_gradients().values():
        assert 2 <= len(colors) <= 3
        assert set(colors) <= set(PALETTE)


def test_every_bar_has_its_own_combination():
    """No two bars share the same colors in the same order."""
    combinations = [tuple(colors) for colors in read_gradients().values()]
    assert len(set(combinations)) == len(combinations)


def test_paper_is_only_a_light_accent_at_the_top():
    """Paper never starts a bar and never stands without darker colors."""
    for colors in read_gradients().values():
        if "#eef5fa" in colors:
            assert colors[-1] == "#eef5fa"
            assert len(colors) == 3


def test_text_around_the_bars_keeps_its_contrast():
    """Labels (Dusk) and counts (Midnight, Violet) stay readable."""
    for card in ("#ffffff", "#eef5fa"):
        for text in ("#46417b", "#221854", "#493bb2"):
            assert contrast(text, card) >= 4.5
