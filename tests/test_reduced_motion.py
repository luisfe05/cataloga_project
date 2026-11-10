"""Every CSS rule that moves something is stopped with reduced motion."""

import os
import re

CSS = os.path.join(os.path.dirname(__file__), "..", "frontend", "css")
REDUCED = "@media (prefers-reduced-motion: reduce)"


def read_css(name):
    """Return a stylesheet without its comments."""
    with open(os.path.join(CSS, name), encoding="utf-8") as file:
        return re.sub(r"/\*.*?\*/", "", file.read(), flags=re.S)


def split_blocks(css):
    """Return (reduced-motion text, the rest) of a stylesheet."""
    reduced, rest = "", ""
    position = 0
    while True:
        start = css.find(REDUCED, position)
        if start < 0:
            rest += css[position:]
            return reduced, rest
        rest += css[position:start]
        depth, index = 0, css.index("{", start)
        for index in range(index, len(css)):
            if css[index] == "{":
                depth += 1
            elif css[index] == "}":
                depth -= 1
                if depth == 0:
                    break
        reduced += css[start:index + 1]
        position = index + 1


def stopped_selectors(reduced):
    """Selectors that a reduced-motion block sets to none."""
    names = set()
    for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", reduced):
        if re.search(r"(animation|transition)\s*:\s*none", body):
            names.update(s.strip() for s in selectors.split(","))
    return names


def moving_selectors(rest):
    """Selectors of rules with a transition or an animation."""
    names = set()
    # Media queries other than reduced motion only wrap ordinary rules.
    rest = re.sub(r"@media[^{]*\{", "", rest)
    rest = re.sub(r"@keyframes[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", "", rest)
    for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", rest):
        if re.search(r"(^|;|\s)(animation|transition)\s*:\s*(?!none)",
                     body):
            names.update(s.strip() for s in selectors.split(","))
    return names


def test_every_moving_rule_has_a_reduced_motion_twin():
    """main.css and home.css: no rule keeps moving with reduced motion."""
    missing = []
    for name in ("main.css", "home.css"):
        reduced, rest = split_blocks(read_css(name))
        stopped = stopped_selectors(reduced)
        missing += [name + ": " + s for s in sorted(moving_selectors(rest))
                    if s not in stopped]
    assert missing == []


def test_the_switch_moves_with_transform():
    """The switch knob slides with transform, not with left."""
    css = read_css("main.css")
    knob = re.search(r"\.switch::after\s*\{([^}]*)\}", css).group(1)
    assert "transition: transform" in knob
    checked = re.search(
        r"input:checked \+ \.switch::after\s*\{([^}]*)\}", css).group(1)
    assert "translateX" in checked and "left" not in checked
