/**
 * files.js
 *
 * The three actions every file has, shared by Catalog and the chat:
 * open it with its default app (click on the name), preview it with
 * Quick Look (eye icon or the space bar), and show it in Finder
 * (folder icon). Only the document id goes to the backend; the backend
 * finds the path and checks it is inside the project.
 */

/**
 * Ask the backend to open, reveal, or preview a file. A missing file
 * shows a toast instead of failing silently.
 * @param {number} id
 * @param {string} action - "open", "reveal", or "preview".
 */
async function runFileAction(id, action) {
    try {
        await runDocumentFileAction(id, action);
    } catch (error) {
        const text = error && error.code === "file_missing"
            ? t("files.not_found") : errorText(error);
        showToolbarMessage(text, true);
    }
}

/**
 * Make a small icon button, like the eye or the folder.
 * @param {string} iconClass - For example "icon-eye".
 * @param {string} labelKey - Text key for aria-label and the tooltip.
 * @param {Function} onClick
 * @returns {HTMLButtonElement}
 */
function makeIconButton(iconClass, labelKey, onClick) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "file-action";
    button.setAttribute("aria-label", t(labelKey));
    button.title = t(labelKey);
    const icon = document.createElement("span");
    icon.className = `icon ${iconClass}`;
    button.appendChild(icon);
    button.addEventListener("click", (event) => {
        // The click must not also select the row or the card.
        event.stopPropagation();
        onClick();
    });
    return button;
}

/**
 * The file name as a button that opens the file.
 * @param {Object} doc - {id, filename}
 * @returns {HTMLButtonElement}
 */
function makeFileLink(doc) {
    const link = document.createElement("button");
    link.type = "button";
    link.className = "file-link";
    link.textContent = doc.filename;
    link.title = `${t("files.open")}: ${doc.filename}`;
    link.addEventListener("click", (event) => {
        event.stopPropagation();
        runFileAction(doc.id, "open");
    });
    return link;
}

/**
 * The eye (preview) and folder (show in Finder) buttons.
 * @param {number} id
 * @returns {HTMLSpanElement}
 */
function makeFileActions(id) {
    const actions = document.createElement("span");
    actions.className = "file-actions";
    actions.append(
        makeIconButton("icon-eye", "files.preview",
            () => runFileAction(id, "preview")),
        makeIconButton("icon-catalog", "files.reveal",
            () => runFileAction(id, "reveal")),
    );
    return actions;
}
