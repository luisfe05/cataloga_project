/** preview.js: the preview overlay. The file on the left, its facts and actions on the right. */

// The element that had the focus, to give it back on closing.
let previewReturnFocus = null;
// The files the arrows walk through, and the one on screen. Each is
// { id } for a cataloged document, or { path, item } for a file in Home.
let previewList = [];
let previewIndex = 0;

/** Stop any recording and empty the overlay. */
function clearPreview() {
    const content = document.getElementById("preview-content");
    content.querySelectorAll("audio, video").forEach((player) => {
        player.pause();
        player.removeAttribute("src");
        player.load();
    });
    content.innerHTML = "";
}

function previewOpen() {
    return !document.getElementById("preview-overlay").classList
        .contains("hidden");
}

function closePreview() {
    clearPreview();
    document.getElementById("preview-overlay").classList.add("hidden");
    if (previewReturnFocus) {
        previewReturnFocus.focus();
    }
}

/** Say that this file cannot be shown here. */
function showPreviewMessage(text) {
    const message = document.createElement("p");
    message.textContent = text;
    const content = document.getElementById("preview-content");
    content.innerHTML = "";
    content.appendChild(message);
}

/** A player for a recording, with its controls. */
function makePreviewPlayer(tag, mediaUrl) {
    const player = document.createElement(tag);
    player.controls = true;
    player.src = mediaUrl;
    // A format the player cannot read (.avi, .mkv) says so instead of failing.
    player.addEventListener("error", () => {
        if (player.getAttribute("src")) {
            showPreviewMessage(t("preview.unavailable"));
        }
    });
    return player;
}

/** Fill the left side with what the backend says this file shows. */
function fillPreview(mediaUrl, preview) {
    const content = document.getElementById("preview-content");
    content.innerHTML = "";
    if (preview.kind === "image") {
        const image = document.createElement("img");
        image.alt = preview.filename;
        image.src = preview.image;
        content.appendChild(image);
    } else if (preview.kind === "text") {
        const text = document.createElement("pre");
        text.textContent = preview.text;
        content.appendChild(text);
    } else if (preview.kind === "audio" || preview.kind === "video") {
        content.appendChild(makePreviewPlayer(preview.kind, mediaUrl));
    } else {
        showPreviewMessage(t("preview.unavailable"));
    }
}

/** One fact of the right side: a label and its value. */
function addPreviewFact(list, labelKey, value) {
    if (!value) {
        return;
    }
    const label = document.createElement("dt");
    label.textContent = t(labelKey);
    const text = document.createElement("dd");
    text.textContent = value;
    list.append(label, text);
}

/** The right side: kind and size, summary, source, date, status, new name, place. */
function fillPreviewInfo(info) {
    document.getElementById("preview-title").textContent = info.filename;
    document.getElementById("preview-kind").textContent =
        [info.mediaType ? valueLabel(info.mediaType) : "",
            info.size ? humanSize(info.size) : ""].filter(Boolean).join(" · ");
    document.getElementById("preview-summary").textContent =
        info.summary || "";
    const facts = document.getElementById("preview-facts");
    facts.innerHTML = "";
    addPreviewFact(facts, "catalog.col_source", info.source);
    addPreviewFact(facts, "catalog.col_date", info.date);
    addPreviewFact(facts, "catalog.col_status",
        info.status ? valueLabel(info.status) : "");
    const proposed = info.proposedName && info.proposedName !== info.filename;
    document.getElementById("preview-new").classList
        .toggle("hidden", !proposed);
    document.getElementById("preview-new-name").textContent =
        proposed ? info.proposedName : "";
    document.getElementById("preview-where").textContent = info.where;
}

/** What the right side shows of a cataloged document. */
async function documentInfo(id, preview) {
    const doc = await getDocument(id);
    const folder = doc.folder_path || "";
    return { filename: doc.filename, mediaType: doc.media_type,
        size: preview.size, summary: doc.summary, source: doc.source,
        date: doc.document_date, status: doc.status,
        proposedName: doc.proposed_name,
        where: [activeProjectName(), ...folder.split("/")]
            .filter(Boolean).join(" › ") };
}

/** What the right side shows of a file in Home (its row, if cataloged). */
function pathInfo(entry, preview) {
    const doc = (entry.item && entry.item.document) || {};
    const folders = entry.path.split("/").slice(0, -1);
    return { filename: preview.filename, mediaType: doc.media_type,
        size: entry.item ? entry.item.size : 0, summary: doc.summary,
        source: doc.source, date: doc.date, status: doc.status,
        proposedName: "",
        where: [activeProjectName(), ...folders].filter(Boolean)
            .join(" › ") };
}

/** The active project's name, as the sidebar shows it. */
function activeProjectName() {
    const active = document.querySelector(".project-link.active");
    return active ? active.textContent : "";
}

/** Show the file at previewIndex: the picture or text, then its facts. */
async function showPreviewAt() {
    const entry = previewList[previewIndex];
    clearPreview();
    showPreviewMessage(t("preview.loading"));
    const many = previewList.length > 1;
    document.getElementById("preview-count").textContent = many
        ? t("preview.count", { n: previewIndex + 1,
            total: previewList.length }) : "";
    document.getElementById("preview-prev").classList.toggle("hidden", !many);
    document.getElementById("preview-next").classList.toggle("hidden", !many);
    try {
        let preview;
        let info;
        if (entry.id) {
            preview = await getDocumentPreview(entry.id);
            info = await documentInfo(entry.id, preview);
            fillPreview(documentMediaUrl(entry.id), preview);
        } else {
            preview = await getFilePreview(entry.path);
            info = pathInfo(entry, preview);
            fillPreview(fileMediaUrl(entry.path), preview);
        }
        fillPreviewInfo(info);
    } catch (error) {
        closePreview();
        showToolbarMessage(error && error.code === "file_missing"
            ? t("files.not_found") : errorText(error), true);
    }
}

/** Open the overlay on one entry of a list (the arrows walk the list). */
function showPreview(list, index) {
    previewReturnFocus = document.activeElement;
    previewList = list;
    previewIndex = Math.max(0, index);
    document.getElementById("preview-overlay").classList.remove("hidden");
    document.getElementById("preview-close").focus();
    showPreviewAt();
}

/** Preview a cataloged document; the arrows go through the Catalog page. */
function openPreview(id) {
    const ids = catalogRows.some((doc) => doc.id === id)
        ? catalogRows.map((doc) => ({ id: doc.id })) : [{ id: id }];
    return showPreview(ids, ids.findIndex((entry) => entry.id === id));
}

/** Preview a file by its path in the project; the arrows go through its folder. */
function openPreviewAt(path, files = []) {
    const list = files.some((file) => file.path === path)
        ? files.map((file) => ({ path: file.path, item: file }))
        : [{ path: path, item: null }];
    return showPreview(list, list.findIndex((entry) => entry.path === path));
}

/** Previous or next file, going round at the ends. */
function stepPreview(step) {
    if (previewList.length < 2) {
        return;
    }
    previewIndex = (previewIndex + step + previewList.length)
        % previewList.length;
    showPreviewAt();
}

/** Show in Finder (the main action) or Open, on the file on screen. */
async function previewFileAction(action) {
    const entry = previewList[previewIndex];
    try {
        if (entry.id) {
            await runDocumentFileAction(entry.id, action);
        } else if (action === "reveal") {
            await revealFile(entry.path);
        } else {
            await openFileAt(entry.path);
        }
    } catch (error) {
        showToolbarMessage(error && error.code === "file_missing"
            ? t("files.not_found") : errorText(error), true);
    }
}

document.getElementById("preview-close")
    .addEventListener("click", closePreview);
document.getElementById("preview-prev")
    .addEventListener("click", () => stepPreview(-1));
document.getElementById("preview-next")
    .addEventListener("click", () => stepPreview(1));
document.getElementById("preview-reveal")
    .addEventListener("click", () => previewFileAction("reveal"));
document.getElementById("preview-open")
    .addEventListener("click", () => previewFileAction("open"));
document.getElementById("preview-overlay").addEventListener("click", (event) => {
    // Only the dark area around the box closes it.
    if (event.target.id === "preview-overlay") {
        closePreview();
    }
});
// Esc or the space bar close it; the arrows go to the next file.
document.addEventListener("keydown", (event) => {
    if (!previewOpen()) {
        return;
    }
    const typing = event.target.closest("input, textarea, select");
    if (event.key === "Escape" || (event.key === " " && !typing
            && !event.target.closest("button, audio, video"))) {
        event.preventDefault();
        closePreview();
    } else if (event.key === "ArrowLeft" && !typing) {
        stepPreview(-1);
    } else if (event.key === "ArrowRight" && !typing) {
        stepPreview(1);
    }
});
