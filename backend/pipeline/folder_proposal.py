"""Folders proposed from what a folder already holds, never for empty ones."""

import json
import os

from backend.pipeline import (archive_rules, folder_tree, learn_folder,
                              project_sheet)

# File names sent to the AI, at most, so a big disk stays cheap.
MAX_FILES = 80

# A folder with no subfolders: the AI sorts the files that are there.
FROM_FILES_PROMPT = """You are an archivist. A researcher connected a folder
that already holds files. Propose folders to organize ONLY the files listed
below. The project description is context about the work, not a list of
folders to create.

Rules:
- Every folder must hold at least one of the listed files. Never propose a
  folder for a kind of material that is not in the list.
- 2 to 10 top folders, each with 0 to 6 subfolders, never deeper.
- Sort by what the files are about, using their names and the extracts.
- Short readable names (1 to 4 words) in the language of the description,
  or of the files when there is no description.
- In "files", list the exact names of the listed files each folder holds.

Respond with ONLY a JSON list in this exact format:
[{"name": "...", "files": ["..."],
  "subfolders": [{"name": "...", "files": ["..."]}]}]"""

# A folder already organized: its folders stay, only loose files need a place.
LOOSE_FILES_PROMPT = """You are an archivist. A researcher connected a folder
that is already organized. Its folders are listed below and stay as they
are. Some files are loose at the top of the folder.
For each loose file, think of the existing folder where it belongs. Only
when no existing folder fits, propose a new top folder for it. The project
description is context, not a list of folders to create.

Respond with ONLY a JSON list of the NEW folders, with the exact names of
the loose files each one would hold:
[{"name": "...", "files": ["..."]}]
Answer [] when every loose file fits an existing folder."""


def file_kinds(names):
    """Count the files by extension: {".pdf": 12, ".jpg": 30}."""
    kinds = {}
    for name in names:
        extension = os.path.splitext(name)[1].lower() or "(none)"
        kinds[extension] = kinds.get(extension, 0) + 1
    return kinds


def sample_text(description, names, extracts, existing=None):
    """Write what the AI reads: context, folders, files, kinds, extracts."""
    lines = ["Project description (context only): " +
             (description or "(none)")]
    if existing:
        lines.append("Existing folders:")
        lines += ["  " + path for path in existing]
    lines.append("Files:")
    lines += ["  " + name for name in names[:MAX_FILES]]
    kinds = file_kinds(names)
    lines.append("File types: " + ", ".join(
        "{} {}".format(count, extension)
        for extension, count in sorted(kinds.items())))
    for name, text in extracts:
        lines.append("Extract of {}:\n{}".format(name, text))
    return "\n".join(lines)


def read_list(answer):
    """The JSON list in an AI answer, or []."""
    if not answer:
        return []
    start = answer.find("[")
    end = answer.rfind("]")
    if start == -1 or end < start:
        return []
    try:
        value = json.loads(answer[start:end + 1])
    except ValueError:
        return []
    return value if isinstance(value, list) else []


def keep_folders_with_files(items, known_names):
    """Drop every proposed folder that holds none of the real files."""
    known = {archive_rules.fold(os.path.basename(name))
             for name in known_names}
    kept = []
    for item in items:
        if not isinstance(item, dict):
            continue
        files = item.get("files") if isinstance(item.get("files"),
                                                list) else []
        has_files = any(isinstance(name, str) and archive_rules.fold(
            os.path.basename(name)) in known for name in files)
        children = keep_folders_with_files(
            item.get("subfolders") or [], known_names)
        if has_files or children:
            kept.append({"name": item.get("name"), "subfolders": children})
    return kept


def propose(client, folder, description=""):
    """Folders for what this folder holds. Saves nothing."""
    # An organized folder keeps its tree (Learn from my folder); only the
    # loose files at its top can bring a new folder.
    learned = learn_folder.learn(folder)
    paths = folder_tree.all_paths(learned["folder_tree"])
    names, loose = [], []
    for relative, name in learn_folder.read_structure(folder)[1]:
        names.append(os.path.join(relative, name) if relative else name)
        if not relative:
            loose.append(name)
    extracts = project_sheet.project_sample(folder)["extracts"]
    if paths:
        tree = list(learned["folder_tree"])
        if loose:
            # Only the loose files' extracts: the filed ones need no place.
            loose_extracts = [(name, text) for name, text in extracts
                              if name in loose]
            answer = client.ask(LOOSE_FILES_PROMPT, sample_text(
                description, loose, loose_extracts, existing=paths))
            taken = {archive_rules.fold(node["name"]) for node in tree}
            for node in folder_tree.clean_ai_tree(keep_folders_with_files(
                    read_list(answer), loose)):
                if archive_rules.fold(node["name"]) not in taken and \
                        len(tree) < folder_tree.MAX_TOP_FOLDERS:
                    tree.append(node)
                    taken.add(archive_rules.fold(node["name"]))
        return {"folder_tree": tree, "organized": True, "learned": learned}
    answer = client.ask(FROM_FILES_PROMPT, sample_text(
        description, names, extracts))
    tree = folder_tree.clean_ai_tree(keep_folders_with_files(
        read_list(answer), names))
    return {"folder_tree": tree, "organized": False, "learned": learned}
