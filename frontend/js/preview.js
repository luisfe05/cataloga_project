/** preview.js: the preview overlay. Closes with X, Esc, or a click outside. */

// The element that had the focus, to give it back on closing.
let previewReturnFocus = null;

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

/** Fill the overlay with what the backend says this file shows. */
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

/** Open the overlay and fill it with what load() answers. */
async function showPreview(load, mediaUrl) {
    previewReturnFocus = document.activeElement;
    clearPreview();
    showPreviewMessage(t("preview.loading"));
    document.getElementById("preview-title").textContent = "";
    document.getElementById("preview-overlay").classList.remove("hidden");
    document.getElementById("preview-close").focus();
    try {
        const preview = await load();
        document.getElementById("preview-title").textContent =
            preview.filename;
        fillPreview(mediaUrl, preview);
    } catch (error) {
        closePreview();
        showToolbarMessage(error && error.code === "file_missing"
            ? t("files.not_found") : errorText(error), true);
    }
}

/** Preview a cataloged document. A missing file shows a toast. */
function openPreview(id) {
    return showPreview(() => getDocumentPreview(id), documentMediaUrl(id));
}

/** Preview a file by its path in the project, cataloged or not. */
function openPreviewAt(path) {
    return showPreview(() => getFilePreview(path), fileMediaUrl(path));
}

document.getElementById("preview-close")
    .addEventListener("click", closePreview);
document.getElementById("preview-overlay").addEventListener("click", (event) => {
    // Only the dark area around the box closes it.
    if (event.target.id === "preview-overlay") {
        closePreview();
    }
});
document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !document.getElementById("preview-overlay")
        .classList.contains("hidden")) {
        closePreview();
    }
});
