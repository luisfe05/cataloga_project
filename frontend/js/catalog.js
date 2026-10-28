/**
 * catalog.js
 *
 * Catalog view (Screen 1).
 * Renders the document table and handles the tabs, search box, filters,
 * Edit Mode, and the Download Worksheet button. The table refreshes every
 * few seconds, so files dropped into the Drop Zone show up once the folder
 * watcher has processed them.
 */

// Seconds between automatic refreshes of the table.
const REFRESH_SECONDS = 10;

// What the user picked on the tabs. "" means All Files.
let currentStatus = "";

// True while the Edit Mode switch is on.
let editMode = false;

// The row the user clicked last. The space bar previews its file.
let selectedDocumentId = null;

// Columns the user can edit in Edit Mode. The filenames are locked and
// media_type is left out because changing it would not move the file.
const EDITABLE_TEXT_FIELDS = ["source", "document_date", "summary"];
const STATUSES = ["Classified", "Manual Review"];

// Longest summary the backend accepts (MAX_SUMMARY_LENGTH in Python).
const MAX_SUMMARY_LENGTH = 100;

/**
 * Collect the current tab, search text, and filters for GET /documents.
 * Empty values are left out so the backend ignores them.
 * @returns {Object}
 */
function readFilters() {
    const filters = {
        status: currentStatus,
        search: document.getElementById("search-input").value.trim(),
        media_type: document.getElementById("filter-media-type").value,
        source: document.getElementById("filter-source").value,
    };
    Object.keys(filters).forEach((key) => {
        if (!filters[key]) {
            delete filters[key];
        }
    });
    return filters;
}

/**
 * Build one table cell. textContent (not innerHTML) is used so text from
 * files or the AI is always shown as plain text, never run as HTML.
 * @param {string|null} text
 * @param {string} [className]
 * @returns {HTMLTableCellElement}
 */
function makeCell(text, className) {
    const cell = document.createElement("td");
    cell.textContent = text || "";
    if (className) {
        cell.className = className;
    }
    return cell;
}

// Timer that clears the toast. A new message restarts it, so the new
// message is not cleared early by the timer of the old one.
let toolbarMessageTimer = null;

/**
 * Show a short message as a toast. It clears itself after 4 seconds.
 * @param {string} text - Empty string clears it.
 * @param {boolean} isError
 */
function showToolbarMessage(text, isError) {
    const message = document.getElementById("toolbar-message");
    message.textContent = text;
    message.classList.toggle("error", Boolean(isError));
    clearTimeout(toolbarMessageTimer);
    toolbarMessageTimer = setTimeout(() => {
        message.textContent = "";
    }, 4000);
}

/**
 * Save one edited field with PATCH /documents/<id>.
 * An empty value is saved as null, so the field counts as missing.
 * Editing the source or date also makes the backend rewrite the summary
 * with the AI, which can take a few seconds.
 * @param {number} id
 * @param {string} field
 * @param {string} value
 * @returns {Promise<Object|null>} The updated document, or null on error.
 */
async function saveField(id, field, value) {
    const fields = {};
    fields[field] = value.trim() === "" ? null : value.trim();
    // Check the summary length here too, so the user gets a clear
    // message instead of a generic error from the backend.
    if (field === "summary" && fields.summary
            && fields.summary.length > MAX_SUMMARY_LENGTH) {
        showToolbarMessage(t("catalog.summary_limit"), true);
        return null;
    }
    const updatesSummary = field === "source" || field === "document_date";
    showToolbarMessage(updatesSummary
        ? t("catalog.saving_summary") : t("catalog.saving"), false);
    try {
        const updated = await updateDocument(id, fields);
        showToolbarMessage(t("catalog.saved"), false);
        return updated;
    } catch (error) {
        showToolbarMessage(errorText(error), true);
        return null;
    }
}

/**
 * Build a text cell the user can type in while Edit Mode is on.
 * The change is saved when the user leaves the cell or presses Enter.
 * @param {Object} doc
 * @param {string} field - One of EDITABLE_TEXT_FIELDS.
 * @returns {HTMLTableCellElement}
 */
function makeEditableCell(doc, field) {
    const original = doc[field] || "";
    // Dates stay on one line, like in the normal table.
    const className =
        field === "document_date" ? "editable nowrap" : "editable";
    const cell = makeCell(original, className);
    // data-field lets other code find this cell, e.g. the summary.
    cell.dataset.field = field;
    // contentEditable lets the user type straight into the cell.
    cell.contentEditable = "true";

    cell.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            cell.blur();
        }
    });
    cell.addEventListener("blur", async () => {
        const value = cell.textContent;
        if (value.trim() === original.trim()) {
            return;
        }
        const updated = await saveField(doc.id, field, value);
        cell.classList.toggle("edit-error", !updated);
        if (!updated) {
            return;
        }
        // If the AI wrote a new summary, show it in the same row.
        if (updated.summary !== doc.summary) {
            const summaryCell = cell.parentElement
                .querySelector('[data-field="summary"]');
            summaryCell.textContent = updated.summary || "";
            showToolbarMessage(t("catalog.saved_summary"), false);
        }
        Object.assign(doc, updated);
    });
    return cell;
}

/**
 * Build the Status cell: a dropdown in Edit Mode, plain text otherwise.
 * @param {Object} doc
 * @returns {HTMLTableCellElement}
 */
function makeStatusCell(doc) {
    const statusClass =
        doc.status === "Manual Review" ? "nowrap status-review" : "nowrap";
    if (!editMode) {
        const statusCell = makeCell("", statusClass);
        // The text goes in a span so the CSS can draw it as a badge.
        statusCell.appendChild(document.createElement("span"))
            .textContent = valueLabel(doc.status);
        return statusCell;
    }
    const cell = makeCell("", "nowrap");
    const select = document.createElement("select");
    select.className = "status-select";
    STATUSES.forEach((status) => {
        const option = document.createElement("option");
        // The value stays in English: it is what the database stores.
        option.value = status;
        option.textContent = valueLabel(status);
        select.appendChild(option);
    });
    select.value = doc.status;
    select.addEventListener("change", async () => {
        const updated = await saveField(doc.id, "status", select.value);
        if (updated) {
            doc.status = updated.status;
        } else {
            select.value = doc.status;
        }
    });
    cell.appendChild(select);
    return cell;
}

/**
 * Build the Filename cell: the name opens the file, and the eye and
 * folder icons preview it or show it in Finder (files.js). In Edit
 * Mode the name is plain text, because it is locked; the icons stay.
 * @param {Object} doc
 * @returns {HTMLTableCellElement}
 */
function makeFilenameCell(doc) {
    const cell = makeCell("", "filename-cell");
    if (editMode) {
        cell.appendChild(document.createTextNode(doc.filename));
    } else {
        cell.appendChild(makeFileLink(doc));
    }
    cell.appendChild(makeFileActions(doc.id));
    return cell;
}

/**
 * Mark one row as selected, so the space bar knows which file to
 * preview. The id is kept, because the table is redrawn every few
 * seconds.
 * @param {number|null} id
 */
function selectRow(id) {
    selectedDocumentId = id;
    document.querySelectorAll("#catalog-body tr").forEach((row) => {
        const isSelected = Number(row.dataset.id) === id;
        row.classList.toggle("row-selected", isSelected);
        row.setAttribute("aria-selected", String(isSelected));
    });
}

/**
 * Fill the table body with one row per document.
 * @param {Array<Object>} documents
 */
function renderTable(documents) {
    const body = document.getElementById("catalog-body");
    body.innerHTML = "";
    documents.forEach((doc) => {
        const row = document.createElement("tr");
        // The chat finds a row by its id to highlight it.
        row.dataset.id = doc.id;
        row.addEventListener("click", () => selectRow(doc.id));
        // The two filename columns are locked, even in Edit Mode.
        row.appendChild(makeCell(doc.original_filename));
        row.appendChild(makeFilenameCell(doc));
        const typeCell = makeCell(valueLabel(doc.media_type), "media-type");
        // The stored value ("Press", "Audio"...) picks the icon in the
        // CSS, so it works in English and Spanish.
        typeCell.dataset.type = doc.media_type;
        row.appendChild(typeCell);

        if (editMode) {
            EDITABLE_TEXT_FIELDS.forEach((field) => {
                row.appendChild(makeEditableCell(doc, field));
            });
        } else {
            row.appendChild(makeCell(doc.source));
            row.appendChild(makeCell(doc.document_date, "nowrap"));
            if (doc.summary) {
                row.appendChild(makeCell(doc.summary, "summary"));
            } else {
                // Same placeholder as the wireframe for missing summaries.
                row.appendChild(makeCell(t("catalog.summary_placeholder"),
                    "placeholder"));
            }
        }
        row.appendChild(makeStatusCell(doc));
        body.appendChild(row);
    });
    // Keep the selection after the table is redrawn.
    selectRow(selectedDocumentId);
}

/**
 * Show a message instead of the table, or hide it when there is data.
 * @param {string} text - Empty string hides the message.
 */
function showMessage(text) {
    const message = document.getElementById("catalog-message");
    message.textContent = text;
    message.classList.toggle("hidden", !text);
    document.getElementById("catalog-table")
        .classList.toggle("hidden", Boolean(text));
}

/**
 * Rebuild the Source dropdown from the sources in the catalog, keeping
 * the current choice selected.
 * @param {Array<Object>} allDocuments
 */
function updateSourceFilter(allDocuments) {
    const select = document.getElementById("filter-source");
    const chosen = select.value;
    const sources = [...new Set(
        allDocuments.map((doc) => doc.source).filter(Boolean)
    )].sort();

    select.innerHTML = "";
    const allOption = document.createElement("option");
    allOption.value = "";
    allOption.textContent = t("catalog.filter_source_all");
    select.appendChild(allOption);
    sources.forEach((source) => {
        const option = document.createElement("option");
        option.value = source;
        option.textContent = source;
        select.appendChild(option);
    });
    select.value = sources.includes(chosen) ? chosen : "";
}

/**
 * Show or hide the warning about files left in the old Inbox folder.
 * It only informs: nothing is moved.
 * @param {Object} settings - Includes old_inbox_has_files (boolean).
 */
function renderOldInboxWarning(settings) {
    const warning = document.getElementById("catalog-warning");
    warning.textContent = settings.old_inbox_has_files
        ? t("catalog.old_inbox_warning") : "";
    warning.classList.toggle("hidden", !settings.old_inbox_has_files);
}

/**
 * Fill the progress bar in the header: Classified vs. Manual Review.
 * @param {number} classified
 * @param {number} review
 */
function renderProgress(classified, review) {
    const total = classified + review;
    // Avoid dividing by zero when the catalog is empty.
    const percent = total ? Math.round((classified / total) * 100) : 0;
    countUp(document.getElementById("progress-classified"), classified);
    countUp(document.getElementById("progress-review"), review);
    document.getElementById("progress-percent").textContent = total
        ? t("catalog.progress_percent", { n: percent })
        : t("dash.no_documents");
    const fill = document.getElementById("progress-fill");
    growBar(fill, "--share", fill.style.getPropertyValue("--share") || "0%",
        `${percent}%`);
}

/**
 * Load everything the catalog needs and draw it.
 */
async function loadCatalog() {
    try {
        const settings = await getSettings();
        renderOldInboxWarning(settings);

        // Only the active project is shown. With no project, or when its
        // folder is missing, say so instead of showing an empty table.
        if (settings.project_status !== "ok") {
            document.getElementById("tab-review").textContent =
                t("catalog.tab_review", { n: 0 });
            renderProgress(0, 0);
            showMessage(settings.project_status === "none"
                ? t("catalog.no_project")
                : t("error.project_unavailable",
                    { path: settings.target_directory }));
            return;
        }

        // All documents (no filters) feed the Source list and the
        // Manual Review counter, so they stay complete while filtering.
        const allDocuments = await getDocuments();
        updateSourceFilter(allDocuments);
        const reviewCount = allDocuments
            .filter((doc) => doc.status === "Manual Review").length;
        document.getElementById("tab-review").textContent =
            t("catalog.tab_review", { n: reviewCount });
        const classifiedCount = allDocuments
            .filter((doc) => doc.status === "Classified").length;
        renderProgress(classifiedCount, reviewCount);

        if (allDocuments.length === 0) {
            // Without an AI provider, nothing can be classified yet.
            showMessage(settings.active_provider
                ? t("catalog.empty", { path: settings.target_directory })
                : t("catalog.no_folder"));
            return;
        }

        const documents = await getDocuments(readFilters());
        showMessage(documents.length ? "" : t("catalog.no_match"));
        renderTable(documents);
    } catch (error) {
        showMessage(t("catalog.load_failed",
            { message: errorText(error) }));
    }
}

/**
 * Mark the tab that matches a status. "Classified" has no tab of its
 * own, so then no tab is marked.
 * @param {string} status - "", "Manual Review" or "Classified".
 */
function selectStatus(status) {
    currentStatus = status;
    document.querySelectorAll(".tab").forEach((tab) => {
        tab.classList.toggle("active", tab.dataset.status === status);
    });
}

/**
 * Put filters from the chat into the catalog controls and reload.
 * The backend already checked every value.
 * @param {Object} filters - Any of media_type, source, status, text.
 */
async function applyCatalogFilters(filters) {
    document.getElementById("search-input").value = filters.text || "";
    document.getElementById("filter-media-type").value =
        filters.media_type || "";
    const source = document.getElementById("filter-source");
    // The source list is filled after the first load, so add the
    // option now if it is not there yet.
    if (filters.source && ![...source.options]
            .some((option) => option.value === filters.source)) {
        const option = document.createElement("option");
        option.value = filters.source;
        option.textContent = filters.source;
        source.appendChild(option);
    }
    source.value = filters.source || "";
    selectStatus(filters.status || "");
    await loadCatalog();
}

/**
 * Show one document in the table: clear the filters, scroll to its
 * row, and highlight it for two seconds.
 * @param {number} id
 */
async function highlightDocument(id) {
    await applyCatalogFilters({});
    const row = document.querySelector(`#catalog-body tr[data-id="${id}"]`);
    if (!row) {
        return;
    }
    row.scrollIntoView({ block: "center" });
    row.classList.add("row-highlight");
    setTimeout(() => row.classList.remove("row-highlight"), 2000);
}

// Tabs: switch between All Files and Manual Review.
document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
        currentStatus = tab.dataset.status;
        document.querySelectorAll(".tab").forEach((other) => {
            other.classList.toggle("active", other === tab);
        });
        loadCatalog();
    });
});

// Search: wait until the user stops typing for 300 ms before searching,
// so the backend is not called on every key press.
let searchTimer = null;
document.getElementById("search-input").addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(loadCatalog, 300);
});

document.getElementById("filter-media-type")
    .addEventListener("change", loadCatalog);
document.getElementById("filter-source")
    .addEventListener("change", loadCatalog);

// Edit Mode: redraw the table with editable cells, or back to plain text.
document.getElementById("edit-mode").addEventListener("change", (event) => {
    editMode = event.target.checked;
    showToolbarMessage(editMode ? t("catalog.edit_mode_on") : "", false);
    loadCatalog();
});

// Download Worksheet: save what is on screen (same tab, search, filters).
document.getElementById("download-button")
    .addEventListener("click", async () => {
        try {
            const path = await exportDocuments(readFilters());
            if (path) {
                showToolbarMessage(t("catalog.export_saved", { path: path }),
                    false);
            }
        } catch (error) {
            showToolbarMessage(t("catalog.export_failed"), true);
        }
    });

// The first loadCatalog() call is made by startApp() in app.js, after
// the saved language is known.

// Refresh on a timer, except in Edit Mode, where a refresh would redraw
// the table and erase what the user is typing.
// Nothing is asked while logged out.
setInterval(() => {
    if (!editMode && sessionToken) {
        loadCatalog();
    }
}, REFRESH_SECONDS * 1000);

/**
 * Is the user typing or on a control that uses the space bar itself?
 * Then the space bar must not open a preview.
 * @param {Element} target
 * @returns {boolean}
 */
function spaceBelongsToControl(target) {
    const tags = ["INPUT", "TEXTAREA", "SELECT", "BUTTON", "A"];
    return tags.includes(target.tagName) || target.isContentEditable;
}

// Space bar: Quick Look preview of the selected row, like in Finder.
document.addEventListener("keydown", (event) => {
    const catalogOpen = !document.getElementById("view-catalog")
        .classList.contains("hidden");
    if (event.key !== " " || !catalogOpen || selectedDocumentId === null
            || spaceBelongsToControl(event.target)) {
        return;
    }
    // Without this the space bar would also scroll the page down.
    event.preventDefault();
    runFileAction(selectedDocumentId, "preview");
});
