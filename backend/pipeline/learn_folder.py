"""Learn from a folder the user already organized: its tree and its names."""

import os
import re
import unicodedata

from backend.pipeline import folder_tree, naming
from backend.scanner import SKIPPED_FILES, SKIPPED_FOLDERS

# How much of a folder is read: enough for any archive, cheap for a disk.
MAX_ENTRIES = 2000
MAX_EXAMPLES = 3

# A folder named like an event: Trialo-Isla-Verde_1998, Boda 2003.
EVENT_FOLDER = re.compile(r"^(.+?)[\s_-]((?:18|19|20)\d{2})$")

# A file named after its event folder plus a number: ..._1997_13.tif.
EVENT_FILE = re.compile(r"^(.+?[\s_-](?:18|19|20)\d{2})[\s_-](\d{1,4})$")

# A name that starts with a date: 2026.07.15_..., 2026-07-15_...
DATE_FIRST = re.compile(r"^(?:18|19|20)\d{2}[-._]\d{2}[-._]\d{2}")


def read_structure(folder):
    """Return the tree of a folder as nodes, and the file names it holds."""
    folder = os.path.realpath(folder)
    tree = []
    names = []
    entries = 0
    for current, dirs, files in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and
                         d not in SKIPPED_FOLDERS and
                         not os.path.islink(os.path.join(current, d)))
        relative = os.path.relpath(current, folder)
        depth = 0 if relative == "." else relative.count(os.sep) + 1
        if depth >= folder_tree.MAX_DEPTH:
            dirs[:] = []
        nodes = tree if relative == "." else node_children(tree, relative)
        for name in dirs:
            if entries >= MAX_ENTRIES:
                break
            nodes.append(folder_tree.make_node(
                folder_tree.safe_folder_name(name) or name))
            entries += 1
        for name in sorted(files):
            if entries >= MAX_ENTRIES:
                break
            if name.startswith(".") or name.startswith("~$") or \
                    name in SKIPPED_FILES:
                continue
            names.append((relative if relative != "." else "", name))
            entries += 1
    return tree, names


def node_children(tree, relative):
    """Return the children list of the node at a relative disk path."""
    nodes = tree
    for part in relative.split(os.sep):
        found = folder_tree.find_node(nodes, part)
        if found is None:
            return nodes
        nodes = found["children"]
    return nodes


def mark_tree(tree):
    """Mark the folders that hold events, and the catch-all by its name."""
    for node in tree:
        children = node["children"]
        events = [c for c in children if EVENT_FOLDER.match(c["name"])]
        if len(events) >= 2 and len(events) * 10 >= len(children) * 6:
            node["events"] = True
        if node["name"].lower() in folder_tree.CATCH_ALL_NAMES and \
                not children:
            node["fallback"] = True
        mark_tree(children)
    return tree


def has_accents(text):
    """Say whether a name carries accented letters."""
    return unicodedata.normalize("NFKD", text) != text


def detect_naming(names):
    """Say how the files are named: style, accents, separator, pattern."""
    stems = [os.path.splitext(name)[0] for folder, name in names
             if not folder_tree.safe_folder_name(name) == ""]
    stems = [s for s in stems if len(s) > 3]
    if not stems:
        return {"naming_style": naming.DEFAULT_STYLE, "keep_accents": False,
                "naming_template": naming.NEW_PROJECT_TEMPLATE,
                "event_numbering": False, "examples": [],
                "description": "No files to learn from."}
    words = [w for s in stems for w in re.split(r"[-_\s]+", s)
             if w and w[0].isalpha()]
    title = bool(words) and \
        sum(1 for w in words if w[0].isupper()) * 2 > len(words)
    accents = sum(1 for s in stems if has_accents(s)) * 2 > len(stems)
    event_numbered = sum(1 for s in stems if EVENT_FILE.match(s))
    date_first = sum(1 for s in stems if DATE_FIRST.match(s))
    examples = [name for folder, name in names][:MAX_EXAMPLES]
    if event_numbered * 2 > len(stems):
        # The event folder's name and a running number: kept as it is
        # until the event-and-number method exists.
        template = naming.KEEP_NAMES
        description = ("Each file is named after its event folder and a "
                       "number: Event_Year_N.")
    elif date_first * 2 > len(stems):
        template = naming.METHOD_TEMPLATES[0]
        description = "Each file starts with its date, then its topic."
    else:
        template = naming.KEEP_NAMES
        description = "Names that are kept as they are."
    style = "title" if title else "lower"
    description += " Words in {}{}.".format(
        "Title-Case" if title else "lowercase",
        " with accents" if accents else "")
    return {"naming_style": style, "keep_accents": accents,
            "naming_template": template,
            "event_numbering": event_numbered * 2 > len(stems),
            "examples": examples, "description": description}


def learn(folder):
    """Read an organized folder and say how it is organized. Saves nothing."""
    tree, names = read_structure(folder)
    result = detect_naming(names)
    result["folder_tree"] = mark_tree(tree)
    result["folders"] = len(folder_tree.all_paths(tree))
    result["files"] = len(names)
    return result
