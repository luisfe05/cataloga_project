"""Folder tree of a project: two levels of folders chosen by the user."""

import json
import re
import unicodedata

from backend.pipeline import archive_rules

# Saved in app_config.folder_mode. Old projects have no value: 'media'.
TREE_MODE = "tree"
MEDIA_MODE = "media"

MAX_TOP_FOLDERS = 20
MAX_SUBFOLDERS = 10
MAX_FOLDER_NAME_LENGTH = 60
MAX_DESCRIPTION_LENGTH = 300

# Not allowed in a folder name on macOS or Windows.
FORBIDDEN_CHARACTERS = '/\\:*?"<>|'

# Windows refuses these names, even with an extension (con.txt).
RESERVED_NAMES = (["con", "prn", "aux", "nul"] +
                  ["com" + str(n) for n in range(1, 10)] +
                  ["lpt" + str(n) for n in range(1, 10)])

# Cataloga's own folders.
OWN_NAMES = ("drop zone", ".cataloga")

NO_FOLDER_NOTE = "No folder fits this file"

# Joins a folder and its subfolder; "/" can never be part of a name.
SEPARATOR = "/"


def safe_folder_name(text):
    """Turn text into a folder name that works on Mac and Windows, or ''."""
    if not isinstance(text, str):
        return ""
    # NFC keeps 'í' as one character, so names compare the same way.
    name = unicodedata.normalize("NFC", text)
    name = "".join(char for char in name
                   if char not in FORBIDDEN_CHARACTERS and ord(char) >= 32)
    name = re.sub(r"\s+", " ", name).strip()
    name = name[:MAX_FOLDER_NAME_LENGTH]
    # Windows drops a dot or space at the end; a dot at the start hides it.
    name = name.rstrip(". ").lstrip(". ")
    if name.split(".")[0].strip().lower() in RESERVED_NAMES:
        return ""
    if name.lower() in OWN_NAMES:
        return ""
    return name


def name_problem(text):
    """Return why a typed folder name is not allowed, or None."""
    if not isinstance(text, str) or not text.strip():
        return "empty"
    if len(text.strip()) > MAX_FOLDER_NAME_LENGTH:
        return "long"
    if any(char in FORBIDDEN_CHARACTERS for char in text):
        return "chars"
    if safe_folder_name(text) != unicodedata.normalize("NFC", text.strip()):
        return "reserved"
    return None


def check_tree(value):
    """Check a tree the user built. Return it clean or raise ValueError."""
    if not isinstance(value, list) or not value:
        raise ValueError("the project needs at least one folder")
    if len(value) > MAX_TOP_FOLDERS:
        raise ValueError("a project can have {} top folders at most"
                         .format(MAX_TOP_FOLDERS))
    tree = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("each folder needs a name")
        name = check_name(item.get("name"), [top["name"] for top in tree])
        subfolders = []
        sent = item.get("subcategories") or []
        if not isinstance(sent, list):
            raise ValueError("subfolders must be a list")
        if len(sent) > MAX_SUBFOLDERS:
            raise ValueError("a folder can have {} subfolders at most"
                             .format(MAX_SUBFOLDERS))
        for sub in sent:
            subfolders.append(check_name(sub, subfolders))
        tree.append({"name": name, "subcategories": subfolders})
    return tree


def check_name(text, siblings):
    """Check one folder name against the rules and its siblings."""
    problem = name_problem(text)
    if problem:
        raise ValueError("folder name not allowed ({}): {}"
                         .format(problem, text))
    name = safe_folder_name(text)
    # The Mac disk ignores case, so 'Prensa' and 'prensa' are one folder.
    if archive_rules.fold(name) in [archive_rules.fold(s) for s in siblings]:
        raise ValueError("two folders have the same name: " + name)
    return name


def clean_ai_tree(value):
    """Keep what is usable from a tree the AI sent. Never raises."""
    if not isinstance(value, list):
        return []
    tree = []
    for item in value[:MAX_TOP_FOLDERS]:
        if not isinstance(item, dict):
            continue
        name = safe_folder_name(item.get("name"))
        folded = [archive_rules.fold(top["name"]) for top in tree]
        if not name or archive_rules.fold(name) in folded:
            continue
        subfolders = []
        # The prompt says "subfolders"; the saved tree says "subcategories".
        sent = item.get("subfolders") or item.get("subcategories") or []
        for sub in sent if isinstance(sent, list) else []:
            sub = safe_folder_name(sub)
            folded = [archive_rules.fold(s) for s in subfolders]
            if sub and archive_rules.fold(sub) not in folded:
                subfolders.append(sub)
        tree.append({"name": name,
                     "subcategories": subfolders[:MAX_SUBFOLDERS]})
    return tree


def parse_tree_answer(answer):
    """Read the JSON list in the AI's answer and clean it, or return []."""
    if not answer:
        return []
    start = answer.find("[")
    end = answer.rfind("]")
    if start == -1 or end < start:
        return []
    try:
        return clean_ai_tree(json.loads(answer[start:end + 1]))
    except ValueError:
        return []


def folder_text(folder, subfolder=None):
    """Return 'Folder/Subfolder', or 'Folder' when there is no subfolder."""
    if subfolder:
        return folder + SEPARATOR + subfolder
    return folder


def split_folder_text(text):
    """Turn 'Folder/Subfolder' back into (folder, subfolder)."""
    if not isinstance(text, str) or not text.strip():
        return None, None
    parts = text.split(SEPARATOR, 1)
    if len(parts) == 1:
        return parts[0].strip(), None
    return parts[0].strip(), parts[1].strip() or None


def find_place(tree, text):
    """Return the saved (folder, subfolder) for 'Folder/Sub', or None."""
    folder, subfolder = split_folder_text(text)
    if not folder:
        return None
    found = archive_rules.find_category(tree, folder)
    if found is None:
        return None
    if not found["subcategories"]:
        return (found["name"], None) if not subfolder else None
    for sub in found["subcategories"]:
        if subfolder and archive_rules.fold(sub) == \
                archive_rules.fold(subfolder):
            return found["name"], sub
    # A folder with subfolders only holds files in its subfolders.
    return None


def clean_suggestion(value, tree):
    """Turn the AI's suggested new folder into 'Parent/Name', or None."""
    if not isinstance(value, dict):
        return None
    name = safe_folder_name(value.get("name"))
    if not name:
        return None
    parent = archive_rules.find_category(tree, value.get("parent") or "")
    if parent is None:
        # A suggestion that already exists is not new.
        if archive_rules.find_category(tree, name):
            return None
        return name
    if archive_rules.fold(name) in [archive_rules.fold(sub) for sub in
                                    parent["subcategories"]]:
        return None
    return folder_text(parent["name"], name)


def add_place(tree, text):
    """Return a copy of the tree with 'Folder/Sub' added, or raise."""
    folder, subfolder = split_folder_text(text)
    tree = [{"name": top["name"],
             "subcategories": list(top["subcategories"])} for top in tree]
    found = archive_rules.find_category(tree, folder or "")
    if found is None:
        tree.append({"name": folder,
                     "subcategories": [subfolder] if subfolder else []})
    elif subfolder:
        found["subcategories"].append(subfolder)
    else:
        raise ValueError("this folder already exists")
    return check_tree(tree)


def all_places(tree):
    """List every 'Folder' and 'Folder/Sub' a file can go into."""
    places = []
    for top in tree:
        if not top["subcategories"]:
            places.append(top["name"])
        for sub in top["subcategories"]:
            places.append(folder_text(top["name"], sub))
    return places
