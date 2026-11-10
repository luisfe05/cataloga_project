"""The calm frame: flat sidebar and page, two moving gradients, one way in."""

import os
import re

FRONTEND = os.path.join(os.path.dirname(__file__), "..", "frontend")


def read(*parts):
    """Return the text of a frontend file."""
    with open(os.path.join(FRONTEND, *parts), encoding="utf-8") as file:
        return file.read()


def rules(css):
    """(selectors, body) of every plain rule, without comments."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = re.sub(r"@keyframes[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", "", css)
    css = re.sub(r"@media[^{]*\{", "", css)
    return re.findall(r"([^{}]+)\{([^{}]*)\}", css)


def test_only_the_login_and_needs_manual_review_drift():
    """The drifting animations are used by these two places only."""
    allowed = (".review-card::before", ".glow-a", ".glow-b")
    for name in ("main.css", "home.css"):
        for selectors, body in rules(read("css", name)):
            if re.search(r"animation\s*:[^;]*(gradient|glow)-drift", body):
                for selector in selectors.split(","):
                    assert selector.strip() in allowed, selector


def test_no_glass_and_no_moving_page_in_the_frame():
    """The page and the sidebar are flat; only the chat and login blur."""
    css = read("css", "main.css") + read("css", "home.css")
    assert "body::before" not in css
    assert "sidebar::before" not in css
    blurred = [selectors.strip() for selectors, body in rules(css)
               if re.search(r"backdrop-filter\s*:\s*blur", body)]
    assert blurred and all(s in (".chat-panel", ".auth-form")
                           for s in blurred)
    sidebar = re.search(r"\.sidebar \{([^}]*)\}", css).group(1)
    assert "var(--color-deep-space)" in sidebar


def test_home_without_a_project_has_one_way_to_start():
    """The logomark, the title, the line and Choose folder."""
    html = read("index.html")
    start = html[html.index('id="home-start"'):]
    start = start[:start.index("</section>")]
    assert "logomark" in start and 'data-i18n="start.title"' in start
    assert 'data-i18n="start.lead"' in start and "data-start-folder" in start
    home = read("js", "home.js")
    assert "showHomeStart(noProject)" in home


def test_the_dashboard_without_a_project_is_not_an_error():
    """A plain line and Choose folder; an error only for a real failure."""
    html = read("index.html")
    start = html[html.index('id="dash-start"'):]
    start = start[:start.index("</section>")]
    assert 'data-i18n="dash.no_project"' in start
    assert "data-start-folder" in start
    dashboard = read("js", "dashboard.js")
    assert 'error.code === "no_project"' in dashboard
    assert 'noProject ? "" : t("dash.load_failed"' in dashboard
    # Nothing to review: no number, no Go Review.
    assert '.toggle("hidden", count === 0)' in dashboard


def test_new_project_is_its_own_screen():
    """New Project has a view; the form moves there and back."""
    html = read("index.html")
    assert 'id="view-new"' in html and 'id="new-project-slot"' in html
    settings = read("js", "settings.js")
    assert 'getElementById("new-project-slot").appendChild(panel)' in settings
    assert 'showView("new")' in settings
    # One way to finish: no counter left.
    assert "settings-progress" not in html + settings
    app = read("js", "app.js")
    assert "openNewProject();" in app
