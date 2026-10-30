/** folders.js: the project's folder tree in Settings. Two levels, edited without dragging. */

// Same limits and rules as folder_tree.py; the backend checks again.
const MAX_TOP_FOLDERS = 20;
const MAX_SUBFOLDERS = 10;
const MAX_FOLDER_NAME_LENGTH = 60;
const FOLDER_FORBIDDEN = '/\\:*?"<>|';
const RESERVED_FOLDER_NAMES = ["con", "prn", "aux", "nul",
    "com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8", "com9",
    "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9"];

// The old five folders, for "Start from file types".
const FILE_TYPE_FOLDERS = ["Press", "Documents", "Photos", "Audio", "Video"];

// "media" for old projects sorted by type, "tree" for projects with their own folders.
let projectFolderMode = "media";

// One entry per folder: { key, name, parent (a key or null), saved, count }.
let folderRows = [];
let nextFolderKey = 1;

/** Lowercase and without accents, like fold() in Python, to compare names. */
function foldName(text) {
    return text.normalize("NFKD").replace(/[̀-ͯ]/g, "")
        .toLowerCase().trim();
}

/** Why a typed name is not allowed, as a message key, or "". */
function folderNameProblem(name) {
    const text = name.trim();
    if (!text) {
        return "folders.err_empty";
    }
    if (text.length > MAX_FOLDER_NAME_LENGTH) {
        return "folders.err_long";
    }
    if ([...text].some((char) => FOLDER_FORBIDDEN.includes(char))) {
        return "folders.err_chars";
    }
    const stem = text.split(".")[0].trim().toLowerCase();
    if (text.startsWith(".") || text.endsWith(".")
            || RESERVED_FOLDER_NAMES.includes(stem)
            || ["drop zone", ".cataloga"].includes(text.toLowerCase())) {
        return "folders.err_reserved";
    }
    return "";
}

function addFolderRow(name, parent, saved, count) {
    const row = { key: nextFolderKey, name: name, parent: parent,
        saved: saved, count: count || 0 };
    nextFolderKey += 1;
    folderRows.push(row);
    return row;
}

function childrenOf(key) {
    return folderRows.filter((row) => row.parent === key);
}

function topRows() {
    return folderRows.filter((row) => row.parent === null);
}

/** Load a tree into the editor. Saved folders are locked: no rename, no move. */
function showFolderTree(tree, counts, saved) {
    folderRows = [];
    tree.forEach((top) => {
        const parent = addFolderRow(top.name, null, saved,
            counts[top.name]);
        top.subcategories.forEach((sub) => {
            addFolderRow(sub, parent.key, saved,
                counts[`${top.name}/${sub}`]);
        });
    });
    renderFolderRows();
}

/** The "Inside" dropdown: top level, or one of the top folders. */
function makeParentSelect(row) {
    const select = document.createElement("select");
    select.className = "folder-parent";
    select.setAttribute("aria-label", t("folders.inside"));
    const top = document.createElement("option");
    top.value = "";
    top.textContent = t("folders.top_level");
    select.appendChild(top);
    topRows().filter((other) => other.key !== row.key).forEach((other) => {
        const option = document.createElement("option");
        option.value = String(other.key);
        option.textContent = other.name || t("folders.unnamed");
        select.appendChild(option);
    });
    select.value = row.parent === null ? "" : String(row.parent);
    // Only two levels: a folder with subfolders stays on top.
    select.disabled = row.saved || childrenOf(row.key).length > 0;
    select.addEventListener("change", () => {
        row.parent = select.value ? Number(select.value) : null;
        renderFolderRows();
    });
    return select;
}

/** Remove a folder. Its subfolders go too, after a question. */
function removeFolder(row) {
    const children = childrenOf(row.key);
    if (children.length
            && !window.confirm(t("folders.remove_with_subs",
                { name: row.name }))) {
        return;
    }
    const gone = [row.key, ...children.map((child) => child.key)];
    folderRows = folderRows.filter((item) => !gone.includes(item.key));
    renderFolderRows();
}

function makeFolderRow(row) {
    const line = document.createElement("div");
    line.className = row.parent === null ? "tree-row" : "tree-row sub";

    const name = document.createElement("input");
    name.type = "text";
    name.className = "folder-name";
    name.value = row.name;
    name.maxLength = MAX_FOLDER_NAME_LENGTH;
    name.placeholder = t("folders.name_placeholder");
    name.setAttribute("aria-label", t("folders.name_placeholder"));
    // Folders on disk are never renamed.
    name.readOnly = row.saved;
    name.addEventListener("input", () => {
        row.name = name.value;
        name.classList.remove("input-error");
        document.getElementById("folders-message").textContent = "";
    });
    // The parent names in the dropdowns change with this one.
    name.addEventListener("change", renderFolderRows);

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "category-remove";
    remove.textContent = "×";
    remove.setAttribute("aria-label", t("folders.remove"));
    // A folder with documents stays in the tree.
    remove.disabled = row.count > 0;
    remove.title = row.count > 0
        ? t("folders.has_documents", { n: row.count }) : t("folders.remove");
    remove.addEventListener("click", () => removeFolder(row));

    line.append(name, makeParentSelect(row), remove);
    line.dataset.key = row.key;
    return line;
}

/** Draw the rows: each top folder, then its subfolders. */
function renderFolderRows() {
    const list = document.getElementById("folder-list");
    list.innerHTML = "";
    topRows().forEach((top) => {
        list.appendChild(makeFolderRow(top));
        childrenOf(top.key).forEach((child) => {
            list.appendChild(makeFolderRow(child));
        });
    });
    document.getElementById("add-folder").disabled =
        topRows().length >= MAX_TOP_FOLDERS;
}

/** The tree as the backend saves it: [{ name, subcategories }]. */
function readFolderTree() {
    return topRows().map((top) => ({
        name: top.name.trim().normalize("NFC"),
        subcategories: childrenOf(top.key)
            .map((child) => child.name.trim().normalize("NFC")),
    }));
}

/** Check the whole tree. Marks the wrong names and returns a message, or "". */
function folderTreeProblem() {
    if (!folderRows.length) {
        return t("folders.err_none");
    }
    let message = "";
    const groups = [topRows(), ...topRows().map((top) => childrenOf(top.key))];
    groups.forEach((rows) => {
        const seen = [];
        rows.forEach((row) => {
            let problem = folderNameProblem(row.name);
            if (!problem && seen.includes(foldName(row.name))) {
                problem = "folders.err_twin";
            }
            seen.push(foldName(row.name));
            if (problem) {
                const input = document.querySelector(
                    `.tree-row[data-key="${row.key}"] .folder-name`);
                input.classList.add("input-error");
                message = message || t(problem, { name: row.name.trim() });
            }
        });
    });
    if (!message && topRows().some(
        (top) => childrenOf(top.key).length > MAX_SUBFOLDERS)) {
        message = t("folders.err_subs");
    }
    return message;
}

function showFoldersMessage(text, kind) {
    const message = document.getElementById("folders-message");
    message.textContent = text;
    message.className = "form-message " + kind;
}

/** Fill the section for a new project, or for the active project. */
function showFolderSection(settings, isNew) {
    const description = document.getElementById("project-description");
    description.value = isNew ? "" : settings.project_description;
    description.readOnly = !isNew;
    document.querySelectorAll(".folders-new-only").forEach((element) => {
        element.classList.toggle("hidden", !isNew);
    });
    showFolderTree(isNew ? [] : settings.categories,
        isNew ? {} : settings.folder_counts, !isNew);
    showFoldersMessage("", "");
}

/** Ask Ollama Cloud for a tree. It replaces the editor; nothing is saved yet. */
async function suggestProjectFolders() {
    const description = document.getElementById("project-description")
        .value.trim();
    const button = document.getElementById("suggest-folders");
    if (!description) {
        showFoldersMessage(t("folders.need_description"), "error");
        return;
    }
    button.disabled = true;
    showFoldersMessage(t("folders.suggesting"), "");
    try {
        const result = await suggestFolders(description);
        showFolderTree(result.folders, {}, false);
        showFoldersMessage(t("folders.suggested"), "success");
    } catch (error) {
        showFoldersMessage(errorText(error), "error");
    } finally {
        button.disabled = false;
    }
}

document.getElementById("suggest-folders")
    .addEventListener("click", suggestProjectFolders);

document.getElementById("file-type-folders").addEventListener("click", () => {
    showFolderTree(FILE_TYPE_FOLDERS
        .map((name) => ({ name: name, subcategories: [] })), {}, false);
    showFoldersMessage("", "");
});

document.getElementById("add-folder").addEventListener("click", () => {
    const row = addFolderRow("", null, false, 0);
    renderFolderRows();
    document.querySelector(`.tree-row[data-key="${row.key}"] .folder-name`)
        .focus();
});
