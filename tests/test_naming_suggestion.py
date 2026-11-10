"""Tests for suggest_naming_style: the naming method a folder already uses."""

from backend import scanner
from backend.pipeline import naming


def test_date_first_names_suggest_method_1():
    """1998-05-02_dawn-swim: the date, then the topic."""
    names = ["1998-05-02_dawn-swim.pdf", "1998-06_harbor-race.jpg",
             "1999_club-meeting.docx"]
    assert naming.suggest_naming_style(names) == "{date}_{topic}"


def test_source_date_topic_names_suggest_method_2():
    """harbor-gazette_1998-05-02_dawn-swim: source, date, topic."""
    names = ["harbor-gazette_1998-05-02_dawn-swim.pdf",
             "coast-weekly_1999_pier-cleanup.pdf"]
    assert naming.suggest_naming_style(names) == "{source}_{date}_{topic}"


def test_numbered_names_suggest_method_3():
    """0001_dawn-swim: a number first."""
    names = ["0001_dawn-swim.pdf", "0002_harbor-race.pdf",
             "0003_club-meeting.pdf"]
    assert naming.suggest_naming_style(names) == "{number}_{topic}"


def test_topic_source_date_names_suggest_method_4():
    """dawn-swim_harbor-gazette_1998: topic, source, date."""
    names = ["dawn-swim_harbor-gazette_1998.pdf",
             "Harbor-Race_Coast-Weekly_1999-07.pdf"]
    assert naming.suggest_naming_style(names) == "{topic}_{source}_{date}"


def test_event_names_suggest_method_5():
    """Swim-Meet_1998_3: the event folder, its year and a number."""
    names = ["Swim-Meet_1998_1.jpg", "Swim-Meet_1998_2.jpg",
             "Pier-Day_2001_14.jpg"]
    assert naming.suggest_naming_style(names) == "{event}_{n}"


def test_a_version_mark_does_not_break_the_shape():
    """0001_dawn-swim_v02 is still a numbered name."""
    names = ["0001_dawn-swim_v02.pdf", "0002_harbor-race-draft-3.pdf"]
    assert naming.suggest_naming_style(names) == "{number}_{topic}"


def test_camera_and_loose_names_suggest_nothing():
    """IMG_0001, 20250312_141502 and free names follow no method."""
    names = ["IMG_2231.jpg", "DSC_0042.jpg", "20250312_141502.jpg",
             "NOTES!!.txt", "budget v2 FINAL.docx", "scan_0048.pdf"]
    assert naming.suggest_naming_style(names) is None


def test_a_shape_needs_half_of_the_names():
    """Two dated names among six loose ones are not enough."""
    names = ["1998-05-02_dawn-swim.pdf", "1999_club-meeting.pdf",
             "todo.txt", "ideas (1).txt", "photo-1.jpg", "untitled.mov"]
    assert naming.suggest_naming_style(names) is None


def test_one_name_or_none_suggests_nothing():
    """A single file, or an empty folder, is no pattern."""
    assert naming.suggest_naming_style(["0001_dawn-swim.pdf"]) is None
    assert naming.suggest_naming_style([]) is None


def test_full_paths_and_hidden_files():
    """Only the file name counts; hidden files are left out."""
    names = ["/Volumes/Demo/Harbor/0001_dawn-swim.pdf",
             "/Volumes/Demo/Harbor/Press/0002_harbor-race.pdf",
             "/Volumes/Demo/Harbor/.DS_Store"]
    assert naming.suggest_naming_style(names) == "{number}_{topic}"


def test_folder_facts_include_the_suggestion(tmp_path):
    """POST /projects/folders/list gets it from the folder's names."""
    for name in ("0001_dawn-swim.txt", "0002_harbor-race.txt"):
        (tmp_path / name).write_text("Invented notes.")
    facts = scanner.folder_facts(str(tmp_path))
    assert facts["files"] == 2
    assert facts["naming_suggestion"] == "{number}_{topic}"


def test_folder_list_route_returns_the_suggestion(empty_client, tmp_path):
    """The route answers with the suggestion, None when nothing fits."""
    folder = tmp_path / "Harbor Swimmers"
    folder.mkdir()
    (folder / "IMG_0001.jpg").write_bytes(b"jpg")
    response = empty_client.post("/projects/folders/list",
                                 json={"folder": str(folder)})
    assert response.status_code == 200
    assert response.get_json()["naming_suggestion"] is None
