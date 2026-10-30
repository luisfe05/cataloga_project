"""Folder tree of a project: folders inside folders, chosen by the user."""

import json
import re
import unicodedata

from backend.pipeline import archive_rules

# Saved in app_config.folder_mode. Old projects have no value: 'media'.
TREE_MODE = "tree"
MEDIA_MODE = "media"
# A tree project without a Drop Zone: the folder is read in place and
# the moves and names are proposed, not done.
PLACE_MODE = "place"
# Files are read and cataloged where they are; nothing moves or renames.
CATALOG_MODE = "catalog"

MAX_TOP_FOLDERS = 20
MAX_SUBFOLDERS = 10
MAX_DEPTH = 6
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

# Why a file went to the catch-all folder (Why this folder, not a note).
CATCH_ALL_REASON = "No folder fits this file, so it went to the catch-all"

# Joins the folders of a path; "/" can never be part of a name.
SEPARATOR = "/"

# Marks a folder can carry. events: holds Event_Year folders (PR 11).
# fallback: the catch-all for what fits nowhere. auto_apply: new files
# in it move without asking (PR 13).
FLAGS = ("events", "fallback", "auto_apply")

# Folders that are a catch-all by their name, when none is marked.
CATCH_ALL_NAMES = ("sin tema", "sin_tema", "sin-tema", "otros", "otro",
                   "varios", "misc", "miscellaneous", "other", "others",
                   "uncategorized", "no topic", "no_topic", "unsorted")

# "01_" at the start of a numbered folder.
NUMBER_PREFIX = re.compile(r"^\d{2}_")


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


def make_node(name, children=None, flags=None):
    """Build one folder of the tree, with its children and marks."""
    node = {"name": name, "children": list(children or [])}
    for flag in FLAGS:
        node[flag] = bool((flags or {}).get(flag))
    # The names of the children, kept for code that reads two levels.
    node["subcategories"] = [child["name"] for child in node["children"]]
    return node


def sent_children(item):
    """Return the children a request or an old list sent for one folder."""
    for key in ("children", "subfolders", "subcategories"):
        if item.get(key):
            return item[key]
    return []


def check_tree(value, depth=1):
    """Check a tree the user built. Return it clean or raise ValueError."""
    if depth == 1 and (not isinstance(value, list) or not value):
        raise ValueError("the project needs at least one folder")
    if not isinstance(value, list):
        raise ValueError("subfolders must be a list")
    limit = MAX_TOP_FOLDERS if depth == 1 else MAX_SUBFOLDERS
    if len(value) > limit:
        raise ValueError("a folder can have {} subfolders at most"
                         .format(limit) if depth > 1 else
                         "a project can have {} top folders at most"
                         .format(limit))
    if depth > MAX_DEPTH:
        raise ValueError("folders can go {} levels deep at most"
                         .format(MAX_DEPTH))
    tree = []
    for item in value:
        # Below the top level, a plain name is a folder with nothing inside.
        if isinstance(item, str) and depth > 1:
            item = {"name": item}
        if not isinstance(item, dict):
            raise ValueError("each folder needs a name")
        name = check_name(item.get("name"), [top["name"] for top in tree])
        children = check_tree(sent_children(item), depth + 1) \
            if sent_children(item) else []
        tree.append(make_node(name, children, item))
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


def clean_ai_tree(value, depth=1):
    """Keep what is usable from a tree the AI sent. Never raises."""
    if not isinstance(value, list) or depth > MAX_DEPTH:
        return []
    limit = MAX_TOP_FOLDERS if depth == 1 else MAX_SUBFOLDERS
    tree = []
    for item in value[:limit]:
        # Below the top level, a plain name is a folder with nothing inside.
        if isinstance(item, str) and depth > 1:
            item = {"name": item}
        if not isinstance(item, dict):
            continue
        name = safe_folder_name(item.get("name"))
        folded = [archive_rules.fold(top["name"]) for top in tree]
        if not name or archive_rules.fold(name) in folded:
            continue
        tree.append(make_node(name, clean_ai_tree(sent_children(item),
                                                  depth + 1)))
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


def tree_from_text(text):
    """Read a saved tree (JSON) and return it as nodes, or []."""
    if not text:
        return []
    try:
        return check_tree(json.loads(text))
    except ValueError:
        return []


def to_categories(tree):
    """Return the first two levels as the old category list."""
    return [{"name": top["name"],
             "subcategories": [child["name"] for child in children_of(top)]}
            for top in tree]


def folder_text(folder, subfolder=None):
    """Return 'Folder/Subfolder', or 'Folder' when there is no subfolder."""
    if subfolder:
        return folder + SEPARATOR + subfolder
    return folder


def split_path(text):
    """Turn 'A/B/C' into ['A', 'B', 'C'], without empty parts."""
    if not isinstance(text, str):
        return []
    return [part.strip() for part in text.split(SEPARATOR) if part.strip()]


def join_path(parts):
    """Turn ['A', 'B'] into 'A/B'."""
    return SEPARATOR.join(parts)


def first_two(path):
    """Return the (category, subcategory) of a path, for the old columns."""
    parts = split_path(path)
    if not parts:
        return None, None
    return parts[0], (parts[1] if len(parts) > 1 else None)


def split_folder_text(text):
    """Turn 'Folder/Subfolder' back into (folder, subfolder)."""
    parts = split_path(text)
    if not parts:
        return None, None
    if len(parts) == 1:
        return parts[0], None
    return parts[0], join_path(parts[1:])


def children_of(node):
    """Return a node's children, also for a raw two-level dict."""
    if "children" in node:
        return node["children"]
    return [make_node(name) if isinstance(name, str) else name
            for name in node.get("subcategories") or []]


def find_node(nodes, name):
    """Return the node with this name (any case or accents), or None."""
    return archive_rules.find_category(nodes, name or "")


def node_at(tree, path):
    """Return the node at a path, with the names as saved, or None."""
    nodes = tree
    found = None
    for part in split_path(path):
        found = find_node(nodes, part)
        if found is None:
            return None
        nodes = children_of(found)
    return found


def canonical_path(tree, path):
    """Return the path with the saved spelling of each name, or None."""
    names = []
    nodes = tree
    for part in split_path(path):
        found = find_node(nodes, part)
        if found is None:
            return None
        names.append(found["name"])
        nodes = children_of(found)
    return join_path(names) if names else None


def find_place(tree, text):
    """Return the saved path of a folder a file can go into, or None."""
    node = node_at(tree, text)
    # A folder with subfolders only holds files in its subfolders.
    if node is None or children_of(node):
        return None
    return canonical_path(tree, text)


def all_places(tree, parent=""):
    """List every folder path a file can go into."""
    places = []
    for node in tree:
        path = join_path([parent, node["name"]]) if parent else node["name"]
        if children_of(node):
            places += all_places(children_of(node), path)
        else:
            places.append(path)
    return places


def all_paths(tree, parent=""):
    """List every folder path, with subfolders or not."""
    paths = []
    for node in tree:
        path = join_path([parent, node["name"]]) if parent else node["name"]
        paths.append(path)
        paths += all_paths(children_of(node), path)
    return paths


# A folder named like an event: Trialo-Isla-Verde_1998, Boda 2003.
EVENT_NAME = re.compile(r"^(.+?)[\s_-]((?:18|19|20)\d{2})$")


def event_places(tree, parent=""):
    """List the paths of the folders marked as holding events."""
    places = []
    for node in tree:
        path = join_path([parent, node["name"]]) if parent else node["name"]
        if node.get("events"):
            places.append(path)
        places += event_places(children_of(node), path)
    return places


def event_parent(tree, text):
    """Return the saved path of an events folder a path points into."""
    parts = split_path(text)
    if len(parts) < 2:
        return None
    parent = canonical_path(tree, join_path(parts[:-1]))
    if parent is None or not node_at(tree, parent).get("events"):
        return None
    return parent


def event_of(tree, place):
    """Return the event folder name of a place inside an events folder."""
    if not place or event_parent(tree, place) is None:
        return None
    return split_path(place)[-1]


def event_year(name):
    """Return the year in an event folder name, or None."""
    found = EVENT_NAME.match(name or "")
    return found.group(2) if found else None


def fallback_place(tree, parent=""):
    """Return the catch-all folder: the one marked, or one by its name."""
    for node in tree:
        path = join_path([parent, node["name"]]) if parent else node["name"]
        if node.get("fallback") and not children_of(node):
            return path
        found = fallback_place(children_of(node), path)
        if found:
            return found
    if parent:
        return None
    for place in all_places(tree):
        if split_path(place)[-1].lower() in CATCH_ALL_NAMES:
            return place
    return None


def clean_suggestion(value, tree):
    """Turn the AI's suggested new folder into a path, or None."""
    if not isinstance(value, dict):
        return None
    name = safe_folder_name(value.get("name"))
    if not name:
        return None
    parent = canonical_path(tree, value.get("parent") or "")
    if parent is None:
        # A suggestion that already exists is not new.
        if find_node(tree, name):
            return None
        return name
    if find_node(children_of(node_at(tree, parent)), name):
        return None
    return join_path([parent, name])


def add_place(tree, text):
    """Return a copy of the tree with every folder of a path added."""
    tree = copy_tree(tree)
    nodes = tree
    added = False
    for part in split_path(text):
        found = find_node(nodes, part)
        if found is None:
            found = make_node(safe_folder_name(part) or part)
            nodes.append(found)
            added = True
        nodes = found["children"]
    if not added:
        raise ValueError("this folder already exists")
    return check_tree(tree)


def copy_tree(tree):
    """Return a copy of the tree that can be changed safely."""
    return [make_node(node["name"], copy_tree(children_of(node)), node)
            for node in tree]


def number_new(tree, existing, parent=""):
    """Give new folders a 01_ prefix; folders on disk keep their names."""
    numbered = []
    for index, node in enumerate(tree, 1):
        path = join_path([parent, node["name"]]) if parent else node["name"]
        name = node["name"]
        if path not in existing and not NUMBER_PREFIX.match(name):
            name = "{:02d}_{}".format(index, name)
        children = number_new(children_of(node), existing,
                              join_path([parent, node["name"]])
                              if parent else node["name"])
        numbered.append(make_node(name, children, node))
    return numbered


def depth_of(tree):
    """Return how many levels deep a tree goes."""
    if not tree:
        return 0
    return 1 + max(depth_of(children_of(node)) for node in tree)
