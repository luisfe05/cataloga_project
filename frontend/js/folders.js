/** folders.js: the project's folder tree in Settings. Any depth, edited without dragging. */

// Same limits and rules as folder_tree.py; the backend checks again.
const MAX_TOP_FOLDERS = 20;
const MAX_SUBFOLDERS = 10;
const MAX_TREE_DEPTH = 6;
const MAX_FOLDER_NAME_LENGTH = 60;
const FOLDER_FORBIDDEN = '/\\:*?"<>|';
const RESERVED_FOLDER_NAMES = ["con", "prn", "aux", "nul",
    "com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8", "com9",
    "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9"];

// Marks a folder can carry, with their text keys.
const FOLDER_FLAGS = {
    events: "folders.flag_events",
    fallback: "folders.flag_fallback",
    auto_apply: "folders.flag_auto",
};

// The old five folders, for "Start from file types".
const FILE_TYPE_FOLDERS = ["Press", "Documents", "Photos", "Audio", "Video"];

// "media" for old projects sorted by type, "tree" for projects with their own folders.
let projectFolderMode = "media";

// One entry per folder: { key, name, parent (a key or null), saved, count, flags }.
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

function addFolderRow(name, parent, saved, count, flags) {
    const row = { key: nextFolderKey, name: name, parent: parent,
        saved: saved, count: count || 0,
        events: Boolean(flags && flags.events),
        fallback: Boolean(flags && flags.fallback),
        auto_apply: Boolean(flags && flags.auto_apply) };
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

function rowByKey(key) {
    return folderRows.find((row) => row.key === key);
}

/** How deep a row sits: 0 for a top folder. */
function depthOf(row) {
    let depth = 0;
    let current = row;
    while (current.parent !== null) {
        current = rowByKey(current.parent);
        depth += 1;
    }
    return depth;
}

/** The path of a row, "A/B/C", as the backend keys the counts. */
function pathOf(row) {
    const names = [];
    let current = row;
    while (current) {
        names.unshift(current.name);
        current = current.parent === null ? null : rowByKey(current.parent);
    }
    return names.join("/");
}

/** Every row under a row, at any depth. */
function descendantsOf(key) {
    const found = [];
    childrenOf(key).forEach((child) => {
        found.push(child, ...descendantsOf(child.key));
    });
    return found;
}

/** How many levels a row's subtree has, the row included. */
function subtreeDepth(row) {
    const children = childrenOf(row.key);
    if (!children.length) {
        return 1;
    }
    return 1 + Math.max(...children.map(subtreeDepth));
}

/** Load a tree into the editor. Saved folders are locked: no rename, no move. */
function showFolderTree(tree, counts, saved) {
    folderRows = [];
    const addNodes = (nodes, parent, parentPath) => {
        nodes.forEach((node) => {
            // An old two-level list sends subfolders as plain names.
            const item = typeof node === "string" ? { name: node } : node;
            const path = parentPath ? `${parentPath}/${item.name}` : item.name;
            const row = addFolderRow(item.name, parent, saved, counts[path],
                item);
            const children = item.children
                || (item.subcategories || []).map((name) => ({ name: name }));
            addNodes(children, row.key, path);
        });
    };
    addNodes(tree, null, "");
    renderFolderRows();
}

/** The "Inside" dropdown: top level, or any folder that is not below this one. */
function makeParentSelect(row) {
    const select = document.createElement("select");
    select.className = "folder-parent";
    select.setAttribute("aria-label", t("folders.inside"));
    const top = document.createElement("option");
    top.value = "";
    top.textContent = t("folders.top_level");
    select.appendChild(top);
    const below = [row.key, ...descendantsOf(row.key).map((r) => r.key)];
    folderRows.filter((other) => !below.includes(other.key)).forEach((other) => {
        const option = document.createElement("option");
        option.value = String(other.key);
        option.textContent = "— ".repeat(depthOf(other))
            + (other.name || t("folders.unnamed"));
        select.appendChild(option);
    });
    select.value = row.parent === null ? "" : String(row.parent);
    // Folders on disk stay where they are.
    select.disabled = row.saved;
    select.addEventListener("change", () => {
        row.parent = select.value ? Number(select.value) : null;
        renderFolderRows();
    });
    return select;
}

/** The three marks of a folder, as small checkboxes. */
function makeFlagBox(row) {
    const box = document.createElement("div");
    box.className = "folder-flags";
    Object.keys(FOLDER_FLAGS).forEach((flag) => {
        const label = document.createElement("label");
        const input = document.createElement("input");
        input.type = "checkbox";
        input.checked = row[flag];
        input.addEventListener("change", () => {
            row[flag] = input.checked;
        });
        label.append(input, document.createTextNode(t(FOLDER_FLAGS[flag])));
        label.title = t(FOLDER_FLAGS[flag] + "_hint");
        box.appendChild(label);
    });
    return box;
}

/** Remove a folder. Its subfolders go too, after a question. */
function removeFolder(row) {
    const children = descendantsOf(row.key);
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
    const depth = depthOf(row);
    line.className = depth ? "tree-row sub" : "tree-row";
    line.style.setProperty("--depth", depth);

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

    line.append(name, makeParentSelect(row), makeFlagBox(row), remove);
    line.dataset.key = row.key;
    return line;
}

/** Draw the rows: each folder, then what is inside it, at any depth. */
function renderFolderRows() {
    const list = document.getElementById("folder-list");
    list.innerHTML = "";
    const draw = (rows) => {
        rows.forEach((row) => {
            list.appendChild(makeFolderRow(row));
            draw(childrenOf(row.key));
        });
    };
    draw(topRows());
    document.getElementById("add-folder").disabled =
        topRows().length >= MAX_TOP_FOLDERS;
}

/** The tree as the backend saves it: [{ name, children, events, fallback, auto_apply }]. */
function readFolderTree() {
    const read = (rows) => rows.map((row) => ({
        name: row.name.trim().normalize("NFC"),
        children: read(childrenOf(row.key)),
        events: row.events,
        fallback: row.fallback,
        auto_apply: row.auto_apply,
    }));
    return read(topRows());
}

function readNumberedFolders() {
    return document.getElementById("numbered-folders").checked;
}

/** Check the whole tree. Marks the wrong names and returns a message, or "". */
function folderTreeProblem() {
    if (!folderRows.length) {
        return t("folders.err_none");
    }
    let message = "";
    const groups = [topRows(), ...folderRows.map((row) => childrenOf(row.key))];
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
    if (!message && folderRows.some(
        (row) => childrenOf(row.key).length > MAX_SUBFOLDERS)) {
        message = t("folders.err_subs");
    }
    if (!message && topRows().some(
        (row) => subtreeDepth(row) > MAX_TREE_DEPTH)) {
        message = t("folders.err_depth");
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
    document.getElementById("numbered-folders").checked =
        Boolean(!isNew && settings.numbered_folders);
    showFolderTree(isNew ? [] : (settings.folder_tree || settings.categories),
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
        .map((name) => ({ name: name, children: [] })), {}, false);
    showFoldersMessage("", "");
});

document.getElementById("add-folder").addEventListener("click", () => {
    const row = addFolderRow("", null, false, 0);
    renderFolderRows();
    document.querySelector(`.tree-row[data-key="${row.key}"] .folder-name`)
        .focus();
});
