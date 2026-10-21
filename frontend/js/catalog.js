/**
 * catalog.js
 *
 * Catalog view (Screen 1).
 * Renders the document table and handles the tabs, search box, filters,
 * Edit Mode, and the Download Worksheet button. The table refreshes every
 * few seconds, so files dropped into the Inbox show up once the folder
 * watcher has processed them.
 */

// Seconds between automatic refreshes of the table.
const REFRESH_SECONDS = 10;

// What the user picked on the tabs. "" means All Files.
let currentStatus = "";

// True while the Edit Mode switch is on.
let editMode = false;

// Columns the user can edit in Edit Mode. The filenames are locked and
// media_type is left out because changing it would not move the file.
const EDITABLE_TEXT_FIELDS = ["source", "document_date", "summary"];
const STATUSES = ["Classified", "Manual Review"];

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

/**
 * Show a short message under the toolbar.
 * @param {string} text - Empty string clears it.
 * @param {boolean} isError
 */
function showToolbarMessage(text, isError) {
    const message = document.getElementById("toolbar-message");
    message.textContent = text;
    message.classList.toggle("error", Boolean(isError));
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
    const updatesSummary = field === "source" || field === "document_date";
    showToolbarMessage(updatesSummary
        ? "Saving and updating the summary with your edit..."
        : "Saving...", false);
    try {
        const updated = await updateDocument(id, fields);
        showToolbarMessage("Saved.", false);
        return updated;
    } catch (error) {
        showToolbarMessage(error.message || "Could not save.", true);
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
            showToolbarMessage("Saved. The summary was updated using "
                + "your edit.", false);
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
        return makeCell(doc.status, statusClass);
    }
    const cell = makeCell("", "nowrap");
    const select = document.createElement("select");
    select.className = "status-select";
    STATUSES.forEach((status) => {
        const option = document.createElement("option");
        option.value = status;
        option.textContent = status;
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
 * Fill the table body with one row per document.
 * @param {Array<Object>} documents
 */
function renderTable(documents) {
    const body = document.getElementById("catalog-body");
    body.innerHTML = "";
    documents.forEach((doc) => {
        const row = document.createElement("tr");
        // The two filename columns are locked, even in Edit Mode.
        row.appendChild(makeCell(doc.original_filename));
        row.appendChild(makeCell(doc.filename));
        row.appendChild(makeCell(doc.media_type));

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
                row.appendChild(makeCell("Manual Summary", "placeholder"));
            }
        }
        row.appendChild(makeStatusCell(doc));
        body.appendChild(row);
    });
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

    select.innerHTML = '<option value="">Source: All</option>';
    sources.forEach((source) => {
        const option = document.createElement("option");
        option.value = source;
        option.textContent = source;
        select.appendChild(option);
    });
    select.value = sources.includes(chosen) ? chosen : "";
}

/**
 * Show the project name from Settings in the header.
 * @param {Object} settings
 */
function renderProjectHeader(settings) {
    const name = settings.research_name || "No project yet";
    document.getElementById("project-name").textContent = name;
    // The circle shows the first letter of the project name.
    document.getElementById("project-badge").textContent =
        name.charAt(0).toUpperCase();
}

/**
 * Load everything the catalog needs and draw it.
 */
async function loadCatalog() {
    try {
        const settings = await getSettings();
        renderProjectHeader(settings);

        if (!settings.target_directory) {
            showMessage("Go to Settings to choose the project folder "
                + "and the AI provider.");
            return;
        }

        // All documents (no filters) feed the Source list and the
        // Manual Review counter, so they stay complete while filtering.
        const allDocuments = await getDocuments();
        updateSourceFilter(allDocuments);
        const reviewCount = allDocuments
            .filter((doc) => doc.status === "Manual Review").length;
        document.getElementById("tab-review").textContent =
            `Manual Review (${reviewCount})`;

        if (allDocuments.length === 0) {
            showMessage("Drop files into the Inbox folder inside "
                + settings.target_directory
                + " and they will appear here once they are classified.");
            return;
        }

        const documents = await getDocuments(readFilters());
        showMessage(documents.length ? "" : "No files match your search.");
        renderTable(documents);
    } catch (error) {
        showMessage("Could not load the catalog: "
            + (error.message || "the app's backend is not responding."));
    }
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
    showToolbarMessage(editMode
        ? "Edit Mode is on. Click a cell to edit it. Automatic refresh "
            + "is paused."
        : "", false);
    loadCatalog();
});

// Download Worksheet: save what is on screen (same tab, search, filters).
document.getElementById("download-button")
    .addEventListener("click", async () => {
        try {
            const path = await exportDocuments(readFilters());
            if (path) {
                showToolbarMessage("Worksheet saved to " + path, false);
            }
        } catch (error) {
            showToolbarMessage("Could not save the worksheet.", true);
        }
    });

loadCatalog();
// Refresh on a timer, except in Edit Mode, where a refresh would redraw
// the table and erase what the user is typing.
setInterval(() => {
    if (!editMode) {
        loadCatalog();
    }
}, REFRESH_SECONDS * 1000);
