"""What the preview overlay shows for a file, without leaving the app."""

import os

from backend.pipeline import archive_rules, file_readers

AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}


def preview_kind(file_path):
    """Return image, pdf, design, office, text, audio, video, or none."""
    name = os.path.basename(file_path)
    extension = os.path.splitext(name)[1].lower()
    # A secret is never shown; a file only in iCloud is never opened.
    if archive_rules.is_secret(name) or \
            file_readers.in_cloud_only(file_path):
        return "none"
    if extension in AUDIO_EXTENSIONS:
        return "audio"
    if extension in VIDEO_EXTENSIONS:
        return "video"
    if extension in file_readers.VISION_EXTENSIONS:
        return "image"
    if extension == ".pdf":
        return "pdf"
    if extension in file_readers.DESIGN_EXTENSIONS:
        return "design"
    if extension in file_readers.OFFICE_EXTENSIONS:
        return "office"
    return "text" if file_readers.is_text_file(file_path) else "none"


def first_picture(pictures):
    """Return the first picture that could be made, or None."""
    return next((uri for uri in pictures or [] if uri), None)


def build_preview(file_path):
    """Return {"kind", "image" or "text"}; kind none when nothing can show."""
    kind = preview_kind(file_path)
    if kind in ("audio", "video"):
        return {"kind": kind}
    image = text = None
    if kind == "image":
        image = file_readers.photo_data_uri(file_path)
    elif kind == "pdf":
        image = first_picture(file_readers.pdf_page_data_uris(file_path, 1))
    elif kind == "design":
        image = first_picture(file_readers.design_views(file_path))
    elif kind == "office":
        text = file_readers.office_text(file_path)
    elif kind == "text":
        text = file_readers.text_extract(file_path)
    if image:
        return {"kind": "image", "image": image}
    if text:
        return {"kind": "text", "text": text}
    return {"kind": "none"}
