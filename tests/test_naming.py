"""Tests for the file naming methods in naming.py."""

import pytest

from backend.db.catalog_repository import DEFAULT_NAMING_TEMPLATE
from backend.pipeline import naming


@pytest.mark.parametrize("text, expected", [
    ("Oceanman Malta", "oceanman-malta"),
    ("Malta Olímpica, 1964!", "malta-olimpica-1964"),
    ("El Nuevo Día", "el-nuevo-dia"),
    ("Año de la niña", "ano-de-la-nina"),
    ("  --Hello___World--  ", "hello-world"),
    ("¿?¡!", ""),
    ("", ""),
    (None, ""),
])
def test_slugify(text, expected):
    """Lowercase, hyphens, and no accents."""
    assert naming.slugify(text) == expected


def test_slugify_cuts_at_a_hyphen():
    """A long slug is cut without splitting a word in half."""
    slug = naming.slugify("one two three four five six seven eight nine",
                          max_length=20)
    assert slug == "one-two-three-four"
    assert len(slug) <= 20


def test_default_template_matches_the_database_default():
    """naming.py and the repository agree on method 1."""
    assert naming.DEFAULT_TEMPLATE == DEFAULT_NAMING_TEMPLATE == \
        "{date}_{topic}"


def full_parts():
    """Parts for the approved example document."""
    return naming.build_parts("scan.pdf", 1, document_date="2026-07-15",
                              source="El Nuevo Día", topic="Oceanman Malta")


@pytest.mark.parametrize("template, expected", [
    ("{date}_{topic}", "2026-07-15_oceanman-malta.pdf"),
    ("{source}_{date}_{topic}",
     "el-nuevo-dia_2026-07-15_oceanman-malta.pdf"),
    ("{number}_{topic}", "0001_oceanman-malta.pdf"),
])
def test_the_three_methods(template, expected):
    """The approved examples come out exactly."""
    assert naming.make_filename(template, full_parts(), ".PDF") == expected


def test_no_text_template():
    """Files without text use the file date and the number."""
    parts = naming.build_parts("IMG_1234.JPG", 1, document_date="2026-07-15")
    assert naming.make_filename(naming.NO_TEXT_TEMPLATE, parts, ".JPG") == \
        "2026-07-15_0001.jpg"


def test_missing_date_is_undated():
    """No date (or something that is not a date) gives 'undated'."""
    assert naming.build_parts("a.pdf", 1)["date"] == "undated"
    assert naming.build_parts("a.pdf", 1,
                              document_date="sometime")["date"] == "undated"
    assert naming.build_parts("a.pdf", 1,
                              document_date="1964-10")["date"] == "1964-10"


def test_missing_source_is_left_out():
    """Method 2 without a source has no leading underscore."""
    parts = naming.build_parts("scan.pdf", 1, document_date="2026-07-15",
                               topic="Oceanman Malta")
    assert naming.make_filename("{source}_{date}_{topic}", parts, ".pdf") \
        == "2026-07-15_oceanman-malta.pdf"


def test_missing_topic_uses_the_original_name():
    """No topic from the AI: the original name, as a slug."""
    parts = naming.build_parts("Carta de Ramón.pdf", 1,
                               document_date="1970")
    assert naming.make_filename("{date}_{topic}", parts, ".pdf") == \
        "1970_carta-de-ramon.pdf"


def test_custom_template_with_every_token():
    """A custom template can use all five parts and its own separators."""
    parts = naming.build_parts("My Scan.pdf", 42, document_date="2026-07-15",
                               source="Claridad", topic="Malta")
    template = "{number}-{source}-{date}-{topic}-{original}"
    assert naming.make_filename(template, parts, ".pdf") == \
        "0042-claridad-2026-07-15-malta-my-scan.pdf"


def test_empty_result_falls_back_to_the_number():
    """A template whose parts are all empty still gives a name."""
    parts = naming.build_parts("a.pdf", 7)
    assert naming.make_filename("{source}", parts, ".pdf") == "0007.pdf"


@pytest.mark.parametrize("template, reason, token", [
    ("", "empty", ""),
    ("   ", "empty", ""),
    (None, "empty", ""),
    ("plain-name", "no_token", ""),
    ("{date}_{titulo}", "unknown", "{titulo}"),
    ("{}_{date}", "unknown", "{}"),
    ("{date}/{topic}", "chars", ""),
    ("{date}:{topic}", "chars", ""),
    ('{date}"{topic}', "chars", ""),
])
def test_validate_template_errors(template, reason, token):
    """Each kind of mistake is reported with its reason."""
    assert naming.validate_template(template) == \
        {"reason": reason, "token": token}


@pytest.mark.parametrize("template", list(naming.METHOD_TEMPLATES) + [
    "{date}-{original}", "Malta {number}", "{topic}.{date}"])
def test_validate_template_accepts_good_ones(template):
    """The three methods and normal custom templates are valid."""
    assert naming.validate_template(template) is None
