"""Tests for the Media Mix colors and the contrast of the Dashboard."""

import os
import re

FRONTEND = os.path.join(os.path.dirname(__file__), "..", "frontend")
MEDIA_TYPES = {"Documents", "Audio", "Video", "Press", "Photos"}


def read(*parts):
    """Return the text of a frontend file."""
    with open(os.path.join(FRONTEND, *parts), encoding="utf-8") as file:
        return file.read()


def tokens():
    """Return {token name: #rrggbb} from the :root block of main.css."""
    root = re.search(r":root \{(.*?)\n\}", read("css", "main.css"), re.S)
    return dict(re.findall(r"--([a-z-]+): (#[0-9a-f]{6});", root.group(1)))


def mix_colors():
    """Return {media type: #rrggbb} from MIX_COLORS in dashboard.js."""
    table = re.search(r"MIX_COLORS = \{(.*?)\};", read("js", "dashboard.js"),
                      re.S).group(1)
    colors = tokens()
    return {name: colors[token] for name, token in
            re.findall(r'(\w+): "var\(--([a-z-]+)\)"', table)}


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


def test_every_media_type_has_one_brand_color():
    """Five types, five different colors, all tokens of main.css."""
    colors = mix_colors()
    assert set(colors) == MEDIA_TYPES
    assert len(set(colors.values())) == 5


def test_the_colors_also_differ_by_lightness():
    """Each step is clearly lighter than the last, not only another hue."""
    steps = sorted(luminance(color) for color in mix_colors().values())
    for darker, lighter in zip(steps, steps[1:]):
        assert (lighter + 0.05) / (darker + 0.05) >= 1.3


def test_text_on_the_review_gradient_keeps_its_contrast():
    """White and Ice (Paper) on Violet and on Midnight: 4.5:1 or more."""
    colors = tokens()
    for background in (colors["color-violet"], colors["color-midnight"]):
        for text in ("#ffffff", colors["color-paper"]):
            assert contrast(text, background) >= 4.5


def test_go_review_keeps_its_contrast():
    """Violet text on the Ice pill."""
    colors = tokens()
    assert contrast(colors["color-violet"], colors["color-paper"]) >= 4.5


def test_every_gradient_drifts_with_one_animation():
    """One gradient-drift keyframes, and reduced motion stops it."""
    css = read("css", "main.css")
    assert css.count("@keyframes gradient-drift") == 1
    assert "auth-drift" not in css
    reduced = css[css.rindex("@media (prefers-reduced-motion: reduce)"):]
    # Since Nov 9 only Needs Manual Review drifts; the login has its glows.
    for selector in (".review-card", ".glow-a", ".glow-b", ".card-drop"):
        assert selector in reduced


def test_every_segment_stands_out_from_the_rail():
    """Each Media Mix color keeps 3:1 against the Paper rail of the bar."""
    paper = tokens()["color-paper"]
    for name, color in mix_colors().items():
        assert contrast(color, paper) >= 3, name


def test_the_chip_icons_are_dusk_and_the_color_is_a_dot():
    """The icon is Dusk; the type's color shows only in its dot."""
    css = read("css", "main.css")
    icon = re.search(r"\.mix-chip::before\s*\{([^}]*)\}", css).group(1)
    assert "background-color: var(--color-dusk)" in icon
    assert "var(--chip-color)" in re.search(
        r"\.mix-dot\s*\{([^}]*)\}", css).group(1)
