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
    leave: "folders.flag_leave",
};

// The old five folders, for "Start from file types".
const FILE_TYPE_FOLDERS = ["Press", "Documents", "Photos", "Audio", "Video"];

// "media" for old projects sorted by type, "tree" for projects with their own folders.
let projectFolderMode = "media";

// True while the AI proposes folders, so Folder names is not ready yet.
let foldersBusy = false;

// True once the user changed the folders: a project sorted by type, or
// Catalog only, sends its tree only then.
let foldersTouched = false;

// How many files the active project has read (GET /settings files_read).
let filesRead = 0;

// Folders taken out of the tree that hold files: path -> where those files
// go ("" leaves them where they are). Sent with Save as folder_moves.
let folderMoves = {};

// The folder the remove dialog asks about.
let folderToRemove = null;

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
        auto_apply: Boolean(flags && flags.auto_apply),
        leave: Boolean(flags && flags.leave) };
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
        foldersTouched = true;
        renderFolderRows();
    });
    return select;
}

/** The four marks of a folder, as small checkboxes. */
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
            foldersTouched = true;
        });
        label.append(input, document.createTextNode(t(FOLDER_FLAGS[flag])));
        label.title = t(FOLDER_FLAGS[flag] + "_hint");
        box.appendChild(label);
    });
    return box;
}

/** Remove a folder. Its subfolders go too, after a question.

A folder that holds files asks where they go first: nothing is deleted,
and the moves wait in To Approve. An empty folder goes too, as a removal
in To Approve. Catalog only moves nothing, so it does not ask.
 */
function removeFolder(row) {
    if (row.count > 0 && projectFolderMode !== "catalog") {
        openFolderRemoveDialog(row);
        return;
    }
    const children = descendantsOf(row.key);
    if (children.length
            && !window.confirm(t("folders.remove_with_subs",
                { name: row.name }))) {
        return;
    }
    // A folder on the disk with no files: the plan removes it at Apply,
    // and Undo makes it again. Catalog only moves nothing.
    if (row.saved && projectFolderMode !== "catalog") {
        folderMoves[pathOf(row)] = "";
    }
    dropFolderRows(row);
}

/** Take a folder and its subfolders out of the editor. */
function dropFolderRows(row) {
    const children = descendantsOf(row.key);
    const gone = [row.key, ...children.map((child) => child.key)];
    folderRows = folderRows.filter((item) => !gone.includes(item.key));
    foldersTouched = true;
    renderFolderRows();
}

/** Folders a file can go into once this one is gone: named leaves of the rest. */
function otherPlaces(row) {
    const gone = [row.key, ...descendantsOf(row.key).map((r) => r.key)];
    return folderRows.filter((other) => !gone.includes(other.key)
        && other.name.trim() && !childrenOf(other.key).length)
        .map(pathOf).sort();
}

/** Ask where the files of a folder go: another folder, or where they are. */
function openFolderRemoveDialog(row) {
    folderToRemove = row;
    document.getElementById("folder-remove-title").textContent =
        t("folders.remove_title", { name: row.name });
    document.getElementById("folder-remove-lead").textContent =
        row.count === 1 ? t("folders.remove_lead_one")
            : t("folders.remove_lead", { n: row.count });
    const select = document.getElementById("folder-remove-target");
    select.innerHTML = "";
    otherPlaces(row).forEach((place) => {
        const option = document.createElement("option");
        option.value = place;
        option.textContent = place;
        select.appendChild(option);
    });
    const leave = document.createElement("option");
    leave.value = "";
    leave.textContent = t("folders.remove_leave");
    select.appendChild(leave);
    select.value = select.options[0].value;
    document.getElementById("folder-remove-dialog").showModal();
    select.focus();
}

/** Remove the folder from the tree and remember where its files go. */
function confirmFolderRemove(event) {
    event.preventDefault();
    const row = folderToRemove;
    if (!row) {
        return;
    }
    folderMoves[pathOf(row)] =
        document.getElementById("folder-remove-target").value;
    folderToRemove = null;
    document.getElementById("folder-remove-dialog").close();
    dropFolderRows(row);
    showFoldersMessage(t("folders.remove_saved_later"), "");
}

/** What Save sends as folder_moves: only folders still out of the tree. */
function readFolderMoves() {
    const paths = folderRows.map(pathOf);
    const moves = {};
    Object.keys(folderMoves).forEach((path) => {
        if (!paths.includes(path)) {
            moves[path] = folderMoves[path];
        }
    });
    return moves;
}

/** B2: saved, but no provider can propose the moves. */
function showProviderNote(shown) {
    document.getElementById("folders-provider-note").classList
        .toggle("hidden", !shown);
}

/** Settings > General > AI Provider, opened. */
function openAIProvider() {
    showView("settings");
    showSettingsTab("general");
    const section = document.getElementById("ai-section");
    document.getElementById("ai-advanced").open = true;
    section.scrollIntoView({ block: "start" });
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
    // The whole name on hover, for one longer than the field.
    name.title = row.name;
    // Folders on disk are never renamed.
    name.readOnly = row.saved;
    name.addEventListener("input", () => {
        row.name = name.value;
        foldersTouched = true;
        name.title = name.value;
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
    // With a Drop Zone, a folder with documents stays in the tree. Read in
    // place it can go: its files get a new folder in To Approve.
    const keeps = row.count > 0 && projectFolderMode === "tree";
    remove.disabled = keeps;
    remove.title = t("folders.remove");
    if (keeps) {
        remove.title = t("folders.has_documents", { n: row.count });
    } else if (row.count > 0) {
        remove.title = t("folders.has_documents_plan", { n: row.count });
    }
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
    // The folded Folder names row counts the folders.
    refreshCards();
}

/** The tree as the backend saves it: [{ name, children, events, fallback, auto_apply, leave }]. */
function readFolderTree() {
    const read = (rows) => rows.map((row) => ({
        name: row.name.trim().normalize("NFC"),
        children: read(childrenOf(row.key)),
        events: row.events,
        fallback: row.fallback,
        auto_apply: row.auto_apply,
        leave: row.leave,
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

/** Fill the section for a new project, or for the active project.

Every project gets the same card and buttons. Folders on the disk are
locked (no rename, no move); a Catalog only project's folders are not on
the disk yet, so they stay editable.
 */
function showFolderSection(settings, isNew) {
    document.querySelectorAll(".folders-new-only").forEach((element) => {
        element.classList.toggle("hidden", !isNew);
    });
    document.getElementById("drop-zone-row").classList.toggle("hidden",
        !isNew);
    document.getElementById("numbered-folders").checked =
        Boolean(!isNew && settings.numbered_folders);
    filesRead = isNew ? 0 : (settings.files_read || 0);
    const locked = !isNew && settings.folder_mode !== "catalog";
    showFolderTree(isNew ? [] : (settings.folder_tree || []),
        isNew ? {} : (settings.folder_counts || {}), locked);
    foldersTouched = false;
    folderMoves = {};
    showFoldersMessage("", "");
    showProviderNote(false);
    updateFolderNotes();
}

/** The one line under the title: To Approve, or Catalog only with its link. */
function updateFolderNotes() {
    const isNew = projectMode === "new";
    const catalogOnly = document.getElementById("catalog-only").checked;
    document.getElementById("folders-catalog-note").classList
        .toggle("hidden", !catalogOnly);
    document.getElementById("folders-plan-note").classList
        .toggle("hidden", isNew || catalogOnly || !filesRead);
}

/** Turn off Catalog only: the project is then read in place with these folders. */
async function turnOffCatalogOnly() {
    const box = document.getElementById("catalog-only");
    if (projectMode === "new") {
        // Not saved yet: the box is enough.
        box.checked = false;
        applyCatalogOnly();
        return;
    }
    if (!window.confirm(t("folders.turn_off_confirm"))) {
        return;
    }
    const problem = readFolderTree().length ? folderTreeProblem() : "";
    if (problem) {
        showFoldersMessage(problem, "error");
        return;
    }
    try {
        await updateSettings({
            research_name: document.getElementById("research-name").value,
            catalog_only: false,
            folder_tree: readFolderTree(),
            numbered_folders: readNumberedFolders(),
        });
    } catch (error) {
        showFoldersMessage(errorText(error), "error");
        return;
    }
    await refreshAfterProjectChange();
    showSettingsMessage(t("folders.turned_off"), "success");
}

/** The industry named in the project sheet, as "Industry: legal", or "". */
function sheetIndustry() {
    const sheet = document.getElementById("project-sheet").value;
    const found = sheet.match(/^\s*Industry:\s*(.+)$/im);
    return found ? found[1].trim().toLowerCase() : "";
}

/** Ask the AI for a tree. It replaces the editor; nothing is saved yet. */
async function suggestProjectFolders() {
    // The one text about the project: About this project.
    const sheet = document.getElementById("project-sheet").value.trim();
    // Archive Now, or an existing project: the tree comes from the files
    // already in the folder.
    const folder = archiveChoice() === "now" || projectMode !== "new"
        ? document.getElementById("target-directory").value.trim() : "";
    const button = document.getElementById("suggest-folders");
    if (!sheet && !folder) {
        showFoldersMessage(t("folders.need_description"), "error");
        return;
    }
    button.disabled = true;
    foldersBusy = true;
    refreshCards();
    showFoldersMessage(t(folder ? "folders.reading" : "folders.suggesting"),
        "");
    try {
        const result = await suggestFolders(sheet, sheetIndustry(), folder);
        showFolderTree(result.folders, {}, false);
        foldersTouched = true;
        if (result.organized) {
            // An organized folder also keeps how its files are named.
            document.querySelector(`input[name="naming-style"][value="${
                result.naming_style}"]`).checked = true;
            showSavedTemplate(result.naming_template);
            updateNamingPreview();
        }
        let key = "folders.suggested";
        if (folder) {
            key = result.organized ? "folders.from_organized"
                : "folders.from_files";
        }
        showFoldersMessage(t(key), "success");
    } catch (error) {
        showFoldersMessage(errorText(error), "error");
    } finally {
        button.disabled = false;
        foldersBusy = false;
        refreshCards();
    }
}

document.getElementById("suggest-folders")
    .addEventListener("click", suggestProjectFolders);

/** Learn from my folder: the folders already on the disk, and how the files are named. */
async function learnProjectFolders() {
    const folder = document.getElementById("target-directory").value.trim();
    const button = document.getElementById("learn-folders");
    if (!folder) {
        showFoldersMessage(t("folders.need_folder"), "error");
        return;
    }
    button.disabled = true;
    foldersBusy = true;
    refreshCards();
    showFoldersMessage(t("folders.learning"), "");
    try {
        const result = await learnFolder(folder);
        showFolderTree(result.folder_tree, {}, false);
        foldersTouched = true;
        document.querySelector(`input[name="naming-style"][value="${
            result.naming_style}"]`).checked = true;
        showSavedTemplate(result.naming_template);
        updateNamingPreview();
        showFoldersMessage(t("folders.learned", { n: result.folders }),
            "success");
    } catch (error) {
        showFoldersMessage(errorText(error), "error");
    } finally {
        button.disabled = false;
        foldersBusy = false;
        refreshCards();
    }
}

document.getElementById("learn-folders")
    .addEventListener("click", learnProjectFolders);
document.getElementById("folder-remove-form")
    .addEventListener("submit", confirmFolderRemove);
document.getElementById("folder-remove-cancel").addEventListener("click", () => {
    folderToRemove = null;
    document.getElementById("folder-remove-dialog").close();
});
document.getElementById("open-ai-provider")
    .addEventListener("click", openAIProvider);
document.getElementById("turn-off-catalog")
    .addEventListener("click", turnOffCatalogOnly);

document.getElementById("file-type-folders").addEventListener("click", () => {
    showFolderTree(FILE_TYPE_FOLDERS
        .map((name) => ({ name: name, children: [] })), {}, false);
    foldersTouched = true;
    showFoldersMessage("", "");
});

document.getElementById("add-folder").addEventListener("click", () => {
    const row = addFolderRow("", null, false, 0);
    foldersTouched = true;
    renderFolderRows();
    document.querySelector(`.tree-row[data-key="${row.key}"] .folder-name`)
        .focus();
});
