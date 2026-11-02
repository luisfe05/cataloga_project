"""Browse routes: the folders and files of a project, as on the disk.

They work before a folder is cataloged: nothing here calls the AI.
"""

import os

from flask import Blueprint, jsonify, request, send_file

from backend import scanner
from backend.config import projects as project_list
from backend.pipeline import file_readers, previews, thumbnails
from backend.pipeline.file_organizer import FileOrganizer
from backend.routes import error_response, get_active_repo, projects_path

browse_bp = Blueprint("browse", __name__)


def project_root():
    """Return the active project's folder, as the scan writes its paths."""
    return os.path.realpath(project_list.active_folder(projects_path()))


def full_path(root, relative):
    """Turn a path from the screen into one on the disk, or None if outside."""
    if not isinstance(relative, str):
        return None
    path = os.path.realpath(os.path.join(root, relative.replace("/", os.sep)))
    if path != root and not FileOrganizer(root).is_inside_project(path):
        return None
    return path


def document_fields(doc):
    """What the information panel shows of a cataloged file."""
    return {"id": doc.id, "status": doc.status,
            "filename": doc.filename, "date": doc.document_date,
            "date_source": doc.date_source, "source": doc.source,
            "summary": doc.summary, "why": doc.folder_reason,
            "media_type": doc.media_type, "review_note": doc.review_note}


def file_entry(root, path, docs):
    """One file of a listing."""
    name = os.path.basename(path)
    extension = os.path.splitext(name)[1].lower()
    doc = docs.get(path)
    return {"name": name, "path": os.path.relpath(path, root).replace(
                os.sep, "/"),
            "size": os.path.getsize(path), "extension": extension.lstrip("."),
            "photo": extension in file_readers.VISION_EXTENSIONS,
            "document": document_fields(doc) if doc else None}


def tree_of(root):
    """Return every folder, with its subfolders, and every file by folder."""
    children = {"": []}
    files = {"": []}
    for current, dirs, names in os.walk(root):
        dirs[:] = sorted(
            d for d in dirs if not d.startswith(".") and
            d not in scanner.SKIPPED_FOLDERS and
            not os.path.islink(os.path.join(current, d)))
        place = os.path.relpath(current, root)
        place = "" if place == "." else place.replace(os.sep, "/")
        children.setdefault(place, [])
        files.setdefault(place, [])
        for name in dirs:
            child = (place + "/" + name) if place else name
            children[place].append(child)
        files[place] = [
            os.path.join(current, name) for name in sorted(names)
            if scanner.is_listed_file(current, name)]
    return children, files


def count_inside(place, children, files):
    """Count the files in a folder and everything below it."""
    return len(files.get(place, [])) + sum(
        count_inside(child, children, files)
        for child in children.get(place, []))


@browse_bp.route("/browse", methods=["GET"])
def browse():
    """List one folder of the active project: its folders and files."""
    repo, error = get_active_repo()
    if error:
        return error
    root = project_root()
    place = request.args.get("path", "").strip("/")
    path = full_path(root, place)
    if path is None or not os.path.isdir(path):
        return error_response("not_found", "This folder does not exist.", 404)
    children, files = tree_of(root)
    if place not in children:
        return error_response("not_found", "This folder does not exist.", 404)
    docs = {doc.file_path: doc for doc in repo.get_all_documents()}
    every_file = [item for group in files.values() for item in group]
    listed = {
        "path": place,
        "folders": [{"name": child.rsplit("/", 1)[-1], "path": child,
                     "files": count_inside(child, children, files)}
                    for child in children[place]],
        "files": [file_entry(root, item, docs) for item in files[place]],
        "contains": count_inside(place, children, files),
        "totals": {
            "files": len(every_file), "folders": len(children) - 1,
            "size": sum(os.path.getsize(item) for item in every_file),
            "classified": sum(1 for item in every_file if item in docs and
                              docs[item].status == "Classified"),
            "review": sum(1 for item in every_file if item in docs and
                          docs[item].status == "Manual Review"),
            "cataloged": sum(1 for item in every_file if item in docs)},
    }
    return jsonify(listed), 200


def listed_file_or_error():
    """Return (root, path) of a file from the query, or (None, error)."""
    repo, error = get_active_repo()
    if error:
        return None, error
    root = project_root()
    path = full_path(root, request.args.get("path", ""))
    if path is None or not os.path.isfile(path):
        return None, error_response(
            "file_missing",
            "The file is missing or outside the project folder.", 409)
    return root, path


@browse_bp.route("/browse/thumb", methods=["GET"])
def thumb():
    """Send a photo's small picture, made once and kept in .cataloga."""
    root, path = listed_file_or_error()
    if root is None:
        return path
    picture = thumbnails.thumbnail_for(root, path)
    if picture is None:
        return error_response("not_found", "This file has no picture.", 404)
    return send_file(picture, mimetype="image/jpeg", conditional=True)


@browse_bp.route("/browse/preview", methods=["GET"])
def preview():
    """Return what the preview overlay shows, cataloged or not."""
    root, path = listed_file_or_error()
    if root is None:
        return path
    return jsonify(dict(previews.build_preview(path),
                        filename=os.path.basename(path))), 200


@browse_bp.route("/browse/media", methods=["GET"])
def media():
    """Stream a recording; conditional answers let the player seek."""
    root, path = listed_file_or_error()
    if root is None:
        return path
    if previews.preview_kind(path) not in ("audio", "video"):
        return error_response("not_found", "This file is not a recording.",
                              404)
    return send_file(path, conditional=True)


@browse_bp.route("/browse/reveal", methods=["POST"])
def reveal():
    """Show a file or a folder in Finder."""
    repo, error = get_active_repo()
    if error:
        return error
    root = project_root()
    body = request.get_json(silent=True)
    path = full_path(root, body.get("path")) if isinstance(body, dict) \
        else None
    if path is None or not os.path.exists(path):
        return error_response(
            "file_missing",
            "The file is missing or outside the project folder.", 409)
    FileOrganizer(root).reveal_file(path)
    return jsonify({"ok": True}), 200
