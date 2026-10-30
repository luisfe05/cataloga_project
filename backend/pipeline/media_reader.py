"""Listening to audio and watching video with the media provider.

Only the first two minutes are sent. Files up to 100 MB go as they are;
bigger ones are cut to a short clip when ffmpeg is installed on the Mac.
"""

import logging
import mimetypes
import os
import shutil
import subprocess
import tempfile

from backend.pipeline import archive_rules

logger = logging.getLogger(__name__)

# What goes to the provider: whole files up to this size, else a clip.
MAX_SEND_BYTES = 100 * 1024 * 1024
# How much of a recording is listened to or watched.
CLIP_SECONDS = 120
# ffmpeg may take a while on a long video.
FFMPEG_TIMEOUT = 300

MIME_TYPES = {
    ".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4",
    ".aac": "audio/aac", ".flac": "audio/flac", ".ogg": "audio/ogg",
    ".aiff": "audio/aiff", ".aif": "audio/aiff", ".wma": "audio/x-ms-wma",
    ".mp4": "video/mp4", ".mov": "video/quicktime", ".m4v": "video/mp4",
    ".webm": "video/webm", ".mkv": "video/x-matroska",
    ".avi": "video/x-msvideo", ".mpg": "video/mpeg", ".mpeg": "video/mpeg",
    ".wmv": "video/x-ms-wmv", ".3gp": "video/3gpp",
}

PROMPTS = {
    "Audio": (
        "Listen to this recording. Write down what is said, in the "
        "language spoken, as plain text. Then add one line that starts "
        "with 'Heard:' saying who seems to speak, the language, and any "
        "music or setting. No markdown."),
    "Video": (
        "Watch this video. Describe what it shows, in order, with any text "
        "on screen, and write down what is said, in the language spoken. "
        "Plain text, no markdown."),
}


def mime_of(file_path):
    """Return the MIME type of an audio or video file."""
    extension = os.path.splitext(file_path)[1].lower()
    if extension in MIME_TYPES:
        return MIME_TYPES[extension]
    guessed = mimetypes.guess_type(file_path)[0]
    return guessed or "application/octet-stream"


def ffmpeg_path():
    """Return the ffmpeg on this Mac, or None. It is never bundled."""
    return shutil.which("ffmpeg")


def length_seconds(length):
    """Turn a length like '1:05' into seconds, or None."""
    if not length:
        return None
    try:
        minutes, seconds = length.split(":")
        return int(minutes) * 60 + int(seconds)
    except ValueError:
        return None


def cut_clip(file_path, kind, ffmpeg=None):
    """Write the first two minutes to a small temporary file, or None."""
    ffmpeg = ffmpeg or ffmpeg_path()
    if not ffmpeg:
        return None
    suffix = ".mp3" if kind == "Audio" else ".mp4"
    handle, clip = tempfile.mkstemp(prefix="cataloga-clip-", suffix=suffix)
    os.close(handle)
    command = [ffmpeg, "-y", "-loglevel", "error", "-i", file_path,
               "-t", str(CLIP_SECONDS), "-map_metadata", "-1"]
    if kind == "Audio":
        command += ["-vn", "-ac", "1", "-b:a", "64k"]
    else:
        # Small picture and sound: enough to understand, cheap to send.
        command += ["-vf", "scale=-2:480", "-c:v", "libx264", "-preset",
                    "veryfast", "-crf", "30", "-c:a", "aac", "-b:a", "64k"]
    command.append(clip)
    try:
        subprocess.run(command, check=True, capture_output=True,
                       timeout=FFMPEG_TIMEOUT)
    except (OSError, subprocess.SubprocessError) as error:
        logger.warning("ffmpeg could not cut %s: %s", file_path, error)
        remove_clip(clip)
        return None
    if not os.path.getsize(clip):
        remove_clip(clip)
        return None
    return clip


def remove_clip(clip):
    """Delete a temporary clip; a missing one is fine."""
    try:
        os.remove(clip)
    except OSError:
        pass


def read_media(client, file_path, kind, length=None):
    """Return (what was heard or seen, Manual Review note).

    The text is '' when the file could not be read; the note says why.
    """
    size = os.path.getsize(file_path)
    seconds = length_seconds(length)
    clip = None
    # A clip is cut when the file is too big to send, or just long and
    # ffmpeg is there to make the send cheaper.
    if size > MAX_SEND_BYTES or (seconds and seconds > CLIP_SECONDS and
                                 ffmpeg_path()):
        clip = cut_clip(file_path, kind)
        if clip is None and size > MAX_SEND_BYTES:
            return "", archive_rules.MEDIA_BIG_NOTE
    try:
        text = client.send_media(PROMPTS[kind], clip or file_path,
                                 mime_of(clip or file_path),
                                 seconds=CLIP_SECONDS)
    except Exception as error:
        logger.warning("could not read %s: %s", file_path, error)
        return "", archive_rules.MEDIA_FAILED_NOTE
    finally:
        if clip:
            remove_clip(clip)
    text = (text or "").strip()
    if not text:
        return "", archive_rules.MEDIA_FAILED_NOTE
    label = "Transcript" if kind == "Audio" else "What the video shows"
    return "{} (first {} minutes at most):\n{}".format(
        label, CLIP_SECONDS // 60, text), None
