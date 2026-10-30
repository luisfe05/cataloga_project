"""Readers for Office files, images, scanned PDF pages, and media length."""

import base64
import io
import os
import re
import wave
import zipfile
from xml.etree import ElementTree

import pypdfium2
from PIL import Image, ImageOps

try:
    # HEIC photos from iPhones need this extra opener.
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIC_READY = True
except ImportError:
    HEIC_READY = False

OFFICE_EXTENSIONS = (".docx", ".xlsx", ".pptx")

# Photos the AI can look at.
VISION_EXTENSIONS = (".jpg", ".jpeg", ".png", ".heic", ".tif", ".tiff",
                     ".gif", ".bmp", ".webp")

# Longest side of an image sent to the AI, to save time and quota.
MAX_IMAGE_SIDE = 1600
JPEG_QUALITY = 85

# The corners of a photo, enlarged, so a small printed date can be read.
CORNER_FRACTION = 0.25
CORNER_SIDE = 800

# A 1200 dpi scan has over 30 million pixels; Pillow's default refuses
# anything past 89 million as a bomb. Scans of a page at 1200 dpi fit.
Image.MAX_IMAGE_PIXELS = 200 * 1000 * 1000

# EXIF software of scanners: their dates are the day of the scan.
SCANNER_WORDS = ("scan", "epson", "canon", "hp ", "brother", "fujitsu",
                 "vuescan", "silverfast", "image capture", "adobe",
                 "photoshop", "lightroom", "gimp")

# Only the first pages of a scanned PDF are read.
MAX_SCANNED_PAGES = 3

# Files bigger than this are not opened (Office parts, images, PDFs).
MAX_READ_BYTES = 50 * 1024 * 1024

WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
SHEET = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
DRAWING = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def read_zip_xml(archive, name):
    """Return the parsed XML of one part of an Office file, or None."""
    try:
        info = archive.getinfo(name)
    except KeyError:
        return None
    # A tiny file that unpacks into something huge is refused.
    if info.file_size > MAX_READ_BYTES:
        return None
    return ElementTree.fromstring(archive.read(name))


def numbered_parts(archive, pattern):
    """Return the part names that match pattern, in their number order."""
    names = [n for n in archive.namelist() if re.fullmatch(pattern, n)]
    return sorted(names, key=lambda n: int(re.findall(r"\d+", n)[-1]))


def docx_text(archive):
    """Return the paragraphs of a Word document."""
    root = read_zip_xml(archive, "word/document.xml")
    if root is None:
        return ""
    lines = []
    for paragraph in root.iter(WORD + "p"):
        line = "".join(t.text or "" for t in paragraph.iter(WORD + "t"))
        if line.strip():
            lines.append(line)
    return "\n".join(lines)


def pptx_text(archive):
    """Return the text of every slide of a PowerPoint file, in order."""
    lines = []
    for name in numbered_parts(archive, r"ppt/slides/slide\d+\.xml"):
        root = read_zip_xml(archive, name)
        if root is None:
            continue
        for paragraph in root.iter(DRAWING + "p"):
            line = "".join(t.text or "" for t in paragraph.iter(DRAWING + "t"))
            if line.strip():
                lines.append(line)
    return "\n".join(lines)


def xlsx_text(archive):
    """Return every sheet of an Excel file as lines of cells."""
    shared = []
    root = read_zip_xml(archive, "xl/sharedStrings.xml")
    if root is not None:
        for item in root.iter(SHEET + "si"):
            parts = [t.text or "" for t in item.iter(SHEET + "t")]
            shared.append("".join(parts))
    lines = []
    for name in numbered_parts(archive, r"xl/worksheets/sheet\d+\.xml"):
        root = read_zip_xml(archive, name)
        if root is None:
            continue
        for row in root.iter(SHEET + "row"):
            cells = [cell_text(cell, shared) for cell in row.iter(SHEET + "c")]
            cells = [c for c in cells if c]
            if cells:
                lines.append(" | ".join(cells))
    return "\n".join(lines)


def cell_text(cell, shared):
    """Return the text of one Excel cell."""
    kind = cell.get("t")
    if kind == "inlineStr":
        return "".join(t.text or "" for t in cell.iter(SHEET + "t"))
    value = cell.find(SHEET + "v")
    if value is None or value.text is None:
        return ""
    if kind == "s":
        index = int(value.text)
        return shared[index] if index < len(shared) else ""
    return value.text


def office_text(file_path):
    """Return the text of a .docx, .xlsx or .pptx file, or '' if unreadable."""
    readers = {".docx": docx_text, ".xlsx": xlsx_text, ".pptx": pptx_text}
    extension = os.path.splitext(file_path)[1].lower()
    try:
        with zipfile.ZipFile(file_path) as archive:
            return readers[extension](archive).strip()
    except (zipfile.BadZipFile, ElementTree.ParseError, KeyError, OSError,
            ValueError):
        return ""


def image_data_uri(image):
    """Shrink a Pillow image, put it on white, and return a JPEG data URI."""
    image = ImageOps.exif_transpose(image)
    image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
    # Transparent parts become white; the AI saw them as black.
    rgba = image.convert("RGBA")
    page = Image.new("RGB", rgba.size, (255, 255, 255))
    page.paste(rgba, mask=rgba.getchannel("A"))
    buffer = io.BytesIO()
    page.save(buffer, format="JPEG", quality=JPEG_QUALITY)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return "data:image/jpeg;base64," + encoded


def photo_data_uri(file_path):
    """Return a photo ready for the AI, or None if it cannot be opened."""
    try:
        with Image.open(file_path) as image:
            return image_data_uri(image)
    except (OSError, ValueError, Image.DecompressionBombError):
        return None


def open_photo(file_path, rotation=0):
    """Open a photo as RGB, turned by rotation degrees clockwise, or None."""
    try:
        with Image.open(file_path) as image:
            image = ImageOps.exif_transpose(image)
            image.load()
    except (OSError, ValueError, Image.DecompressionBombError):
        return None
    if rotation in (90, 180, 270):
        # Pillow turns counterclockwise, so the angle is reversed.
        image = image.rotate(-rotation, expand=True)
    return image


def corner_crops(image):
    """Return the four corners of a photo, enlarged, as JPEG data URIs."""
    width, height = image.size
    w = max(1, int(width * CORNER_FRACTION))
    h = max(1, int(height * CORNER_FRACTION))
    boxes = [(0, 0, w, h), (width - w, 0, width, h),
             (0, height - h, w, height), (width - w, height - h, width,
                                          height)]
    uris = []
    for box in boxes:
        corner = image.crop(box)
        # Enlarge a small corner; a huge one is shrunk by image_data_uri.
        if max(corner.size) < CORNER_SIDE:
            scale = CORNER_SIDE / max(corner.size)
            corner = corner.resize((max(1, int(corner.width * scale)),
                                    max(1, int(corner.height * scale))))
        uris.append(image_data_uri(corner))
    return uris


def photo_views(file_path, rotation=0):
    """Return the photo and its four corners for the AI, or []."""
    image = open_photo(file_path, rotation)
    if image is None:
        return []
    return [image_data_uri(image)] + corner_crops(image)


def photo_date(file_path):
    """Return the date a camera wrote in a photo's EXIF, or None.

    A scanner also writes EXIF dates, but those are the day of the scan,
    so they only count when a camera make or model is there too.
    """
    try:
        with Image.open(file_path) as image:
            exif = image.getexif()
            make = str(exif.get(271) or "") + " " + str(exif.get(272) or "")
            software = str(exif.get(305) or "").lower()
            # 36867 is DateTimeOriginal, in the Exif block.
            taken = exif.get_ifd(0x8769).get(36867)
    except (OSError, ValueError, Image.DecompressionBombError):
        return None
    if not taken or not make.strip():
        return None
    if any(word in software for word in SCANNER_WORDS):
        return None
    # EXIF writes dates as 2026:07:15 10:30:00.
    match = re.match(r"(\d{4}):(\d{2}):(\d{2})", str(taken))
    if not match:
        return None
    return "-".join(match.groups())


def pdf_page_data_uris(file_path):
    """Return the first pages of a PDF as images on white, for the AI."""
    uris = []
    try:
        pdf = pypdfium2.PdfDocument(file_path)
    except (pypdfium2.PdfiumError, OSError):
        return []
    try:
        for index in range(min(MAX_SCANNED_PAGES, len(pdf))):
            # Scale 2 is about 144 dpi; the image is shrunk to 1600 px after.
            bitmap = pdf[index].render(scale=2,
                                       fill_color=(255, 255, 255, 255))
            uris.append(image_data_uri(bitmap.to_pil()))
    finally:
        pdf.close()
    return uris


def wav_seconds(file_path):
    """Return the length of a .wav file in seconds."""
    with wave.open(file_path, "rb") as audio:
        return audio.getnframes() / float(audio.getframerate())


def mp4_seconds(file_path):
    """Return the length of an .mp4, .mov or .m4a file from its mvhd box."""
    size = os.path.getsize(file_path)
    with open(file_path, "rb") as file:
        # The movie header is near the start or near the end of the file.
        data = file.read(4 * 1024 * 1024)
        if size > len(data):
            file.seek(max(0, size - 4 * 1024 * 1024))
            data += file.read()
    at = data.find(b"mvhd")
    if at == -1:
        return None
    header = data[at + 4:at + 40]
    if header[0] == 1:
        # Version 1 uses 8-byte dates and an 8-byte duration.
        scale = int.from_bytes(header[20:24], "big")
        length = int.from_bytes(header[24:32], "big")
    else:
        scale = int.from_bytes(header[12:16], "big")
        length = int.from_bytes(header[16:20], "big")
    return length / scale if scale else None


def media_length(file_path):
    """Return an audio or video length like '1:05', or None if unknown."""
    extension = os.path.splitext(file_path)[1].lower()
    try:
        if extension == ".wav":
            seconds = wav_seconds(file_path)
        elif extension in (".mp4", ".mov", ".m4a"):
            seconds = mp4_seconds(file_path)
        else:
            return None
    except (OSError, ValueError, EOFError, wave.Error, IndexError):
        return None
    if seconds is None or seconds <= 0:
        return None
    # int(x + 0.5) rounds 30.5 up; round() would give 30.
    seconds = int(seconds + 0.5)
    return "{}:{:02d}".format(seconds // 60, seconds % 60)
