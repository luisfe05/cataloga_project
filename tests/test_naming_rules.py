"""Tests for the naming rules: styles, accents, versions, path length."""

import os

import pytest

from backend.pipeline import archive_rules, naming
# The fixture comes along with the helper.
from tests.test_classification_pipeline import (  # noqa: F401
    fake_keyring, make_text_file, setup)


@pytest.mark.parametrize("text, style, accents, expected", [
    ("Juegos Nacionales PR", "lower", False, "juegos-nacionales-pr"),
    ("Juegos Nacionales PR", "title", False, "Juegos-Nacionales-PR"),
    ("El Nuevo Día", "lower", False, "el-nuevo-dia"),
    ("El Nuevo Día", "lower", True, "el-nuevo-día"),
    ("El Nuevo Día", "title", True, "El-Nuevo-Día"),
    ("año de la niña", "title", True, "Año-De-La-Niña"),
    ("  --Hello___World--  ", "title", False, "Hello-World"),
])
def test_slugify_styles_and_accents(text, style, accents, expected):
    """lowercase or Title-Case, with or without accents."""
    assert naming.slugify(text, style=style, keep_accents=accents) == \
        expected


def test_method_four_has_no_number_and_examples_are_generic():
    """The number only appears when a name repeats."""
    assert naming.METHOD_TEMPLATES[3] == "{topic}_{source}_{date}"
    assert "{topic_number}" not in naming.NEW_PROJECT_TEMPLATE
    # The old token still works in a saved custom template.
    assert naming.validate_template("{topic}_{topic_number}") is None


@pytest.mark.parametrize("original, version", [
    ("informe_v02.docx", "v02"), ("Plan draft-3.pdf", "draft-3"),
    ("Contrato V1.pdf", "v1"), ("borrador_2.txt", "borrador_2"),
    ("video2024.mp4", ""), ("a.pdf", ""),
])
def test_version_of(original, version):
    """v01, draft-3 and borrador_2 are versions; a plain year is not."""
    assert naming.version_of(original) == version


def test_version_stays_at_the_end_of_the_new_name():
    """informe_v02.docx keeps v02, so v01 and v02 never collide."""
    parts = naming.build_parts("informe_v02.docx", 1,
                               document_date="2026-07-15", topic="Informe",
                               source="Claridad")
    assert naming.make_filename("{topic}_{source}_{date}", parts, ".docx") \
        == "informe_claridad_2026-07-15_v02.docx"
    # With {original} the version is already there.
    assert naming.make_filename("{original}", parts, ".docx") == \
        "informe-v02.docx"


def test_fit_path_shortens_the_topic_then_the_source():
    """A long topic is cut a word at a time until the path fits."""
    # Only lengths matter here, so the folder does not need to exist.
    folder = "/" + "x" * 180
    parts = naming.build_parts("a.pdf", 1, document_date="2026-07-15",
                               topic="one two three four five six seven",
                               source="some long source name")
    name = naming.fit_path(folder, "{topic}_{source}_{date}", parts, ".pdf")
    assert name == "one-two-three-four_some-long-source-name_2026-07-15.pdf"
    assert len(os.path.join(folder, name)) <= naming.MAX_PATH_LENGTH
    # When the topic is gone, the source goes next.
    name = naming.fit_path("/" + "x" * 205, "{topic}_{source}_{date}",
                           parts, ".pdf")
    assert name == "some-long-source_2026-07-15.pdf"
    assert naming.fit_path("/" + "x" * 250, "{topic}", parts, ".pdf") is None


# --- In the pipeline ---

def test_pipeline_uses_the_project_style_and_accents(setup):
    """Title-Case with accents: Malta-Olímpica_El-Nuevo-Día_1964-10-12."""
    setup["repo"].save_config_value("naming_style", "title")
    setup["repo"].save_config_value("keep_accents", 1)
    setup["repo"].save_naming_template(naming.NEW_PROJECT_TEMPLATE)
    pipeline, ai = setup["build"]()
    doc = pipeline.classify_document(
        make_text_file(setup["drop_zone"], "clipping.txt"))
    assert doc.filename == "Malta-Olímpica_El-Nuevo-Día_1964-10-12.txt"


def test_pipeline_never_writes_undated(setup):
    """With only the disk date, the name has no date at all."""
    replies = {"classify": "Documents", "summary": "A letter.",
               "metadata": '{"source": null, "document_date": null, '
                           '"topic": "Carta"}'}
    pipeline, ai = setup["build"](replies)
    setup["repo"].save_naming_template(naming.NEW_PROJECT_TEMPLATE)
    doc = pipeline.classify_document(
        make_text_file(setup["drop_zone"], "x.txt"))
    assert doc.filename == "carta.txt"
    assert doc.date_source == "file"


def test_second_file_with_the_same_name_gets_2(setup):
    """Same topic, source and date: the second is _2, the first stays."""
    pipeline, ai = setup["build"]()
    setup["repo"].save_naming_template(naming.NEW_PROJECT_TEMPLATE)
    first = pipeline.classify_document(
        make_text_file(setup["drop_zone"], "a.txt"))
    second = pipeline.classify_document(
        make_text_file(setup["drop_zone"], "b.txt"))
    assert first.filename == "malta-olimpica_el-nuevo-dia_1964-10-12.txt"
    assert second.filename == "malta-olimpica_el-nuevo-dia_1964-10-12_2.txt"
    assert os.path.isfile(first.file_path)


def test_path_too_long_goes_to_manual_review(setup, tmp_path):
    """A path that cannot fit stays where it is, with a note."""
    pipeline, ai = setup["build"]()
    deep = setup["drop_zone"].parent / "archive" / ("d" * 230)
    pipeline.file_organizer.target_directory = str(deep)
    pipeline.file_organizer.ensure_archive_structure()
    path = make_text_file(setup["drop_zone"], "clipping.txt")
    doc = pipeline.classify_document(path)
    assert doc.status == "Manual Review"
    assert doc.review_note == archive_rules.TOO_LONG_NOTE
    assert doc.file_path == path
    assert doc.suggested_folder == "Press"
