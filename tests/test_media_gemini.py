"""Tests for listening to audio and watching video with Gemini."""

import os
import wave

import pytest

from backend.db.catalog_repository import CatalogRepository
from backend.db.schema import init_db
from backend.pipeline import archive_rules, file_metadata, media_reader
from backend.pipeline.ai_providers import gemini
from backend.pipeline.ai_providers.gemini import GeminiClient
from backend.pipeline.classification_pipeline import ClassificationPipeline
from backend.pipeline.file_organizer import FileOrganizer
from tests.test_file_formats import FakeAI, mp3, test_key  # noqa: F401


@pytest.fixture
def setup(tmp_path):
    """A temp catalog, archive and Drop Zone for the media tests."""
    db_path = str(tmp_path / "catalog.db")
    init_db(db_path)
    (tmp_path / "drop").mkdir()
    return {"repo": CatalogRepository(db_path),
            "project": tmp_path / "archive",
            "drop": (tmp_path / "drop")}


class FakeMedia:
    """A media client that remembers what it was asked to listen to."""

    def __init__(self, answer="Hola, esta es la entrevista. Heard: a man."):
        self.answer = answer
        self.calls = []

    def send_media(self, prompt, file_path, mime_type, seconds=None):
        self.calls.append((prompt, file_path, mime_type, seconds))
        if self.answer is None:
            raise RuntimeError("Gemini is down")
        return self.answer


def build(setup, media):
    """A pipeline with the fake text AI and a fake media client."""
    return ClassificationPipeline(FakeAI(), setup["repo"],
                                  FileOrganizer(str(setup["project"])),
                                  owner="luis", media_client=media)


def wav(path, seconds=1):
    """A silent .wav of some seconds."""
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b"\0\0" * 8000 * seconds)
    return str(path)


# --- The pipeline ---

def test_audio_is_listened_to_and_classified(setup):
    """A short recording is sent to the media client and then cataloged."""
    media = FakeMedia()
    path = mp3(setup["drop"] / "entrevista.mp3")
    doc = build(setup, media).classify_document(path)
    assert len(media.calls) == 1
    prompt, sent, mime, seconds = media.calls[0]
    assert sent == path and mime == "audio/mpeg" and seconds == 120
    assert "Listen" in prompt
    assert doc.media_type == "Audio"
    assert doc.summary == "A short summary."
    assert doc.review_note != archive_rules.MEDIA_NOTE


def test_video_is_watched(setup):
    """A video goes to the media client with its MIME type."""
    media = FakeMedia("A regatta. People cheer.")
    path = setup["drop"] / "regata.mov"
    path.write_bytes(b"not a real video")
    doc = build(setup, media).classify_document(str(path))
    assert media.calls[0][2] == "video/quicktime"
    assert "Watch" in media.calls[0][0]
    assert doc.media_type == "Video"
    assert doc.status != "Manual Review" or \
        doc.review_note != archive_rules.MEDIA_NOTE


def test_without_a_media_client_only_the_tags_are_read(setup):
    """No Gemini key: audio keeps the old note and no media call."""
    doc = build(setup, None).classify_document(
        mp3(setup["drop"] / "audio.mp3"))
    assert doc.status == "Manual Review"
    assert doc.review_note.startswith(archive_rules.MEDIA_NOTE)


def test_big_file_without_ffmpeg_keeps_its_tags_and_a_note(
        setup, monkeypatch):
    """Over 100 MB and no ffmpeg: nothing is sent; the note says why."""
    media = FakeMedia()
    path = mp3(setup["drop"] / "largo.mp3")
    monkeypatch.setattr(media_reader, "ffmpeg_path", lambda: None)
    monkeypatch.setattr(media_reader.os.path, "getsize",
                        lambda p: 150 * 1024 * 1024)
    doc = build(setup, media).classify_document(path)
    assert media.calls == []
    assert doc.status == "Manual Review"
    assert doc.review_note == archive_rules.MEDIA_BIG_NOTE


def test_a_failed_listen_says_so(setup):
    """When the media provider fails, the file waits for a person."""
    doc = build(setup, FakeMedia(None)).classify_document(
        mp3(setup["drop"] / "roto.mp3"))
    assert doc.status == "Manual Review"
    assert doc.review_note == archive_rules.MEDIA_FAILED_NOTE


# --- Clips with ffmpeg ---

def fake_ffmpeg(monkeypatch, calls):
    """Pretend ffmpeg is installed and writes a small clip."""
    monkeypatch.setattr(media_reader, "ffmpeg_path", lambda: "/usr/bin/ff")

    def run(command, **kwargs):
        calls.append(command)
        with open(command[-1], "wb") as clip:
            clip.write(b"clip")
    monkeypatch.setattr(media_reader.subprocess, "run", run)


def test_big_file_with_ffmpeg_sends_a_two_minute_clip(setup, monkeypatch):
    """Over 100 MB with ffmpeg: a clip of 120 seconds is sent and removed."""
    media = FakeMedia()
    calls = []
    fake_ffmpeg(monkeypatch, calls)
    path = setup["drop"] / "largo.mp4"
    path.write_bytes(b"x")
    real_size = os.path.getsize
    monkeypatch.setattr(
        media_reader.os.path, "getsize",
        lambda p: 150 * 1024 * 1024 if p == str(path) else real_size(p))
    build(setup, media).classify_document(str(path))
    assert len(calls) == 1 and calls[0][calls[0].index("-t") + 1] == "120"
    clip = media.calls[0][1]
    assert clip != str(path) and clip.endswith(".mp4")
    assert media.calls[0][2] == "video/mp4"
    assert not os.path.exists(clip)


def test_long_audio_with_ffmpeg_is_cut_first(setup, monkeypatch):
    """A three-minute .wav is cut before sending when ffmpeg is there."""
    media = FakeMedia()
    calls = []
    fake_ffmpeg(monkeypatch, calls)
    path = wav(setup["drop"] / "largo.wav", seconds=180)
    build(setup, media).classify_document(path)
    assert len(calls) == 1 and "-vn" in calls[0]
    assert media.calls[0][1].endswith(".mp3")


def test_ffmpeg_failure_still_sends_a_small_file(setup, monkeypatch):
    """When ffmpeg fails on a long but small file, the file itself goes."""
    media = FakeMedia()
    monkeypatch.setattr(media_reader, "ffmpeg_path", lambda: "/usr/bin/ff")

    def run(command, **kwargs):
        raise OSError("no ffmpeg after all")
    monkeypatch.setattr(media_reader.subprocess, "run", run)
    path = wav(setup["drop"] / "largo.wav", seconds=180)
    build(setup, media).classify_document(path)
    assert media.calls[0][1] == path


def test_mime_types_and_lengths():
    """MIME types come from a short table; lengths from m:ss."""
    assert media_reader.mime_of("a.m4a") == "audio/mp4"
    assert media_reader.mime_of("a.MOV") == "video/quicktime"
    assert media_reader.mime_of("a.weird") == "application/octet-stream"
    assert media_reader.length_seconds("1:05") == 65
    assert media_reader.length_seconds("") is None
    assert media_reader.length_seconds("x") is None


# --- The Gemini client ---

class FakeFiles:
    """The SDK's files service: upload, get, delete."""

    def __init__(self, states=("ACTIVE",)):
        self.states = list(states)
        self.deleted = []

    def upload(self, file, config=None):
        return FakeFile("files/abc", self.states.pop(0), config["mime_type"])

    def get(self, name):
        return FakeFile(name, self.states.pop(0), "video/mp4")

    def delete(self, name):
        self.deleted.append(name)


class FakeFile:
    def __init__(self, name, state, mime_type):
        self.name = name
        self.state = state
        self.uri = "https://files/" + name
        self.mime_type = mime_type


class FakeModels:
    def __init__(self):
        self.calls = []

    def generate_content(self, model, contents, config=None):
        self.calls.append((model, contents))

        class Response:
            text = "heard"
        return Response()


class FakeSDK:
    def __init__(self, states=("ACTIVE",)):
        self.files = FakeFiles(states)
        self.models = FakeModels()


@pytest.fixture
def client(monkeypatch):
    """A Gemini client with a key and a fake SDK."""
    sdk = FakeSDK()
    gem = GeminiClient()
    gem.api_key = "k"
    monkeypatch.setattr(gem, "sdk_client", lambda: sdk)
    monkeypatch.setattr(gemini.time, "sleep", lambda s: None)
    return gem, sdk


def test_small_video_goes_inline_with_the_time_limit(client, tmp_path):
    """A small file is sent as bytes; the video is cut at 120 seconds."""
    gem, sdk = client
    path = tmp_path / "v.mp4"
    path.write_bytes(b"video")
    assert gem.send_media("Watch", str(path), "video/mp4", 120) == "heard"
    part, prompt = sdk.models.calls[0][1]
    assert part.inline_data.data == b"video"
    assert part.video_metadata.end_offset == "120s"
    assert prompt == "Watch" and sdk.files.deleted == []


def test_audio_has_no_time_limit_part(client, tmp_path):
    gem, sdk = client
    path = tmp_path / "a.mp3"
    path.write_bytes(b"audio")
    gem.send_media("Listen", str(path), "audio/mpeg", 120)
    assert sdk.models.calls[0][1][0].video_metadata is None


def test_big_file_is_uploaded_and_deleted(client, tmp_path, monkeypatch):
    """Over 20 MB the file is uploaded, waited for, used, and deleted."""
    gem, sdk = client
    sdk.files.states = ["PROCESSING", "ACTIVE"]
    path = tmp_path / "v.mp4"
    path.write_bytes(b"video")
    monkeypatch.setattr(gemini.os.path, "getsize", lambda p: 30 * 1024 * 1024)
    assert gem.send_media("Watch", str(path), "video/mp4", 120) == "heard"
    part = sdk.models.calls[0][1][0]
    assert part.file_data.file_uri == "https://files/files/abc"
    assert sdk.files.deleted == ["files/abc"]


def test_failed_upload_raises_and_is_deleted(client, tmp_path, monkeypatch):
    gem, sdk = client
    sdk.files.states = ["FAILED"]
    path = tmp_path / "v.mp4"
    path.write_bytes(b"video")
    monkeypatch.setattr(gemini.os.path, "getsize", lambda p: 30 * 1024 * 1024)
    with pytest.raises(RuntimeError):
        gem.send_media("Watch", str(path), "video/mp4", 120)
    assert sdk.files.deleted == ["files/abc"]


def test_without_a_key_nothing_is_sent(tmp_path):
    gem = GeminiClient()
    gem.api_key = None
    with pytest.raises(ValueError):
        gem.send_media("Watch", str(tmp_path), "video/mp4")


# --- WAV tags ---

def test_wav_id3_tags_are_read(tmp_path):
    """A .wav with ID3 frames gives its title, artist and date."""
    from mutagen.id3 import TDRC, TIT2, TPE1
    from mutagen.wave import WAVE
    path = wav(tmp_path / "t.wav")
    audio = WAVE(path)
    audio.add_tags()
    audio.tags.add(TIT2(encoding=3, text="Ferry interview"))
    audio.tags.add(TPE1(encoding=3, text="Radio Isla"))
    audio.tags.add(TDRC(encoding=3, text="2001-05-02"))
    audio.save()
    meta = file_metadata.media_metadata(path)
    assert meta["title"] == "Ferry interview"
    assert meta["author"] == "Radio Isla"
    assert meta["date"] == "2001-05-02"
    assert meta["length"] == "0:01"
