"""Archive conventions by industry: the folders, names and rules each uses."""

import os

# From the research of October 2026 (Getty, ATLA, ISO 19650, legal and
# film guides). The folders and the naming are starting points the AI
# and the user adjust; the rules are what the app turns on by default.
CONVENTIONS = {
    "documentary and research": {
        "folders": ["Press", "Interviews", "Documents", "Photos",
                    "Production", "Research"],
        "naming": "{topic}_{source}_{date}",
        "rules": {},
    },
    "legal": {
        "folders": ["01_Pleadings", "02_Discovery", "03_Correspondence",
                    "04_Client_Docs", "05_Research", "06_Billing_Admin"],
        "naming": "{date}_{topic}_{source}",
        "rules": {"date_first": True, "numbered_folders": True,
                  "versions": True},
    },
    "construction": {
        "folders": ["Architecture", "Structure", "Mechanical",
                    "Electrical", "Site", "Contracts"],
        "naming": "{original}",
        "rules": {"keep_names": True},
    },
    "web and code": {
        "folders": [],
        "naming": "{original}",
        "rules": {"keep_names": True, "catalog_only": True},
    },
    "film and video": {
        "folders": ["Camera originals", "Selects", "Masters",
                    "Interviews", "B-roll", "Audio", "Graphics"],
        "naming": "{original}",
        "rules": {"keep_names": True, "catalog_only": True},
    },
    "photo archive": {
        "folders": ["Events", "Training", "School", "Family",
                    "No topic"],
        "naming": "{event}_{n}",
        "rules": {"event_folders": True},
    },
    "library and digitization": {
        "folders": ["Collections", "Finding aids", "Scans"],
        "naming": "{topic}_{date}",
        "rules": {"lowercase": True, "no_accents": True},
    },
    "general": {
        "folders": [],
        "naming": "{topic}_{source}_{date}",
        "rules": {},
    },
}

# Files and folders that say "other programs depend on these paths":
# moving or renaming them breaks the site, the code, or the edit.
LINKED_MARKERS = {
    "web and code": ("index.html", "package.json", "package-lock.json",
                     ".git", "css", "js", "node_modules", "pyproject.toml",
                     "requirements.txt", "Makefile", ".gitignore"),
    "film and video": (".prproj", ".aep", ".fcpbundle", ".drp"),
    "design": (".indd", ".idml", ".sketch", ".fig", ".xd"),
}

# How deep the marker search goes: the root and one level down.
MARKER_DEPTH = 2


def industries():
    """Return the industry names, the general one last."""
    return tuple(CONVENTIONS)


def conventions_for(industry):
    """Return the conventions of an industry, or the general ones."""
    return CONVENTIONS.get((industry or "").strip().lower(),
                           CONVENTIONS["general"])


def typical_folders(industry):
    """Return the folders an archive in this field usually has."""
    return list(conventions_for(industry)["folders"])


def folder_hints(industry):
    """Return the text added to the tree request, or '' with no hints."""
    folders = typical_folders(industry)
    if not folders:
        return ""
    return ("\n\nFolders an archive in the field \"{}\" usually has: {}. "
            "Include the ones that apply, in the language of the "
            "description, and add folders for the project's own "
            "subject.").format(industry, ", ".join(folders))


def find_markers(folder):
    """Return the linked-project markers found in a folder's top levels."""
    found = []
    root_depth = folder.rstrip(os.sep).count(os.sep)
    for current, dirs, files in os.walk(folder):
        depth = current.count(os.sep) - root_depth
        for name in sorted(dirs) + sorted(files):
            extension = os.path.splitext(name)[1].lower()
            for markers in LINKED_MARKERS.values():
                if name in markers or (extension and extension in markers):
                    found.append(name)
        if depth + 1 >= MARKER_DEPTH:
            dirs[:] = []
    return sorted(set(found))


def linked_kind(markers):
    """Say which kind of linked project the markers point to, or ''."""
    for kind, names in LINKED_MARKERS.items():
        for marker in markers:
            extension = os.path.splitext(marker)[1].lower()
            if marker in names or (extension and extension in names):
                return kind
    return ""


def inspect_folder(folder):
    """Say what a folder looks like before it becomes a project."""
    markers = find_markers(folder)
    kind = linked_kind(markers)
    industry = kind if kind in CONVENTIONS else ""
    return {"markers": markers, "linked_kind": kind,
            "catalog_only_recommended": bool(kind),
            "industry": industry}
