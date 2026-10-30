/** catalog.js: the table, tabs, search, filters, Edit Mode, and Download Worksheet. */

const REFRESH_SECONDS = 10;

// "" means All Files.
let currentStatus = "";

let editMode = false;

// The row clicked last. The space bar previews its file.
let selectedDocumentId = null;

// Filenames are locked; media_type is left out because changing it would not move the file.
const EDITABLE_TEXT_FIELDS = ["source", "document_date", "summary"];
const STATUSES = ["Classified", "Manual Review"];

// Same as MAX_SUMMARY_LENGTH in Python.
const MAX_SUMMARY_LENGTH = 100;

// Same limits as archive_rules.py, checked here for a clear message.
const MAX_KEYWORDS = 5;
const MAX_KEYWORD_LENGTH = 40;
const MAX_COUNTERPARTY_LENGTH = 100;
const CONFIDENTIALITY_LEVELS = ["Public", "Internal", "Confidential", "Restricted"];
const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

// Shown only with the More columns switch.
const MORE_COLUMNS = ["counterparty", "confidentiality", "owner",
    "effective_start", "effective_end"];

// The active project's category list, from GET /settings.
let projectCategories = [];

// True when the project files documents in its own folder tree.
let catalogTreeMode = false;

/** Current tab, search, and filters for GET /documents. Empty values are left out. */
function readFilters() {
    const filters = {
        status: currentStatus,
        search: document.getElementById("search-input").value.trim(),
        media_type: document.getElementById("filter-media-type").value,
        source: document.getElementById("filter-source").value,
        category: document.getElementById("filter-category").value,
        subcategory: document.getElementById("filter-subcategory").value,
    };
    Object.keys(filters).forEach((key) => {
        if (!filters[key]) {
            delete filters[key];
        }
    });
    return filters;
}

/** One table cell. textContent, so text from files or the AI is never run as HTML. */
function makeCell(text, className) {
    const cell = document.createElement("td");
    cell.textContent = text || "";
    if (className) {
        cell.className = className;
    }
    return cell;
}

// A new message restarts the timer, so the old timer cannot clear it early.
let toolbarMessageTimer = null;

/** Show a short message as a toast. It clears itself after 4 seconds. */
function showToolbarMessage(text, isError) {
    const message = document.getElementById("toolbar-message");
    message.textContent = text;
    message.classList.toggle("error", Boolean(isError));
    clearTimeout(toolbarMessageTimer);
    toolbarMessageTimer = setTimeout(() => {
        message.textContent = "";
    }, 4000);
}

/** Check an archiving field before saving. Returns the message key of the problem, or "". */
function archiveFieldProblem(field, value) {
    if (field === "keywords" && value) {
        const keywords = value.split(",").map((word) => word.trim())
            .filter(Boolean);
        if (keywords.length > MAX_KEYWORDS
                || keywords.some((word) => word.length > MAX_KEYWORD_LENGTH)) {
            return "catalog.keywords_limit";
        }
    }
    if (field === "counterparty" && value
            && value.length > MAX_COUNTERPARTY_LENGTH) {
        return "catalog.counterparty_limit";
    }
    if ((field === "effective_start" || field === "effective_end") && value
            && !DATE_PATTERN.test(value)) {
        return "catalog.date_format";
    }
    return "";
}

/** Save one field. Empty is saved as null. Source or date also rewrite the summary (slow). */
async function saveField(id, field, value) {
    const fields = {};
    fields[field] = value.trim() === "" ? null : value.trim();
    // Check here too, for a clear message instead of a generic backend error.
    if (field === "summary" && fields.summary
            && fields.summary.length > MAX_SUMMARY_LENGTH) {
        showToolbarMessage(t("catalog.summary_limit"), true);
        return null;
    }
    const problem = archiveFieldProblem(field, fields[field]);
    if (problem) {
        showToolbarMessage(t(problem), true);
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

/** Text shown for a field. Keywords are a list, shown as "a, b, c". */
function fieldText(doc, field) {
    if (field === "keywords") {
        return (doc.keywords || []).join(", ");
    }
    return doc[field] || "";
}

/** A text cell for Edit Mode. Saves on Enter or when the user leaves the cell. */
function makeEditableCell(doc, field) {
    const original = fieldText(doc, field);
    const dateFields = ["document_date", "effective_start", "effective_end"];
    const className =
        dateFields.includes(field) ? "editable nowrap" : "editable";
    const cell = makeCell(original, className);
    // data-field lets other code find this cell, e.g. the summary.
    cell.dataset.field = field;
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

/** On-screen text of a review note. The backend stores it in English. */
function reviewNoteText(note) {
    const duplicatePrefix = "Duplicate of ";
    if (note.startsWith(duplicatePrefix)) {
        return t("catalog.note_duplicate",
            { name: note.slice(duplicatePrefix.length) });
    }
    if (note === "Category not in the project list") {
        return t("catalog.note_no_category");
    }
    if (note === "No folder fits this file") {
        return t("catalog.note_no_folder");
    }
    // The backend may add the length: "... coming soon. Duration 1:05".
    const mediaPrefix = "Audio and video reading is coming soon";
    if (note.startsWith(mediaPrefix)) {
        const length = note.split("Duration ")[1];
        return length ? t("catalog.note_media_length", { length: length })
            : t("catalog.note_media");
    }
    // "Low confidence: <the AI's reason>".
    const lowPrefix = "Low confidence: ";
    if (note.startsWith(lowPrefix)) {
        return t("catalog.note_low_confidence")
            + ": " + note.slice(lowPrefix.length);
    }
    // "Missing: source, document_date": each field in the user's language.
    const missingPrefix = "Missing: ";
    if (note.startsWith(missingPrefix)) {
        const labels = {
            source: "catalog.col_source",
            document_date: "catalog.col_date",
            summary: "catalog.col_summary",
        };
        const fields = note.slice(missingPrefix.length).split(", ")
            .map((field) => labels[field] ? t(labels[field]) : field);
        return t("catalog.note_missing", { fields: fields.join(", ") });
    }
    const notes = {
        "Could not read the image": "catalog.note_image",
        "No topic could be found in the photo": "catalog.note_topic",
        "Could not read the scanned pages": "catalog.note_scan",
        "File is larger than 50 MB, so it was not read": "catalog.note_too_big",
    };
    if (notes[note]) {
        return t(notes[note]);
    }
    return note;
}

/** Build the Status cell: a dropdown in Edit Mode, plain text otherwise. */
function makeStatusCell(doc) {
    const statusClass =
        doc.status === "Manual Review" ? "nowrap status-review" : "nowrap";
    if (!editMode) {
        const statusCell = makeCell("", statusClass);
        // The text goes in a span so the CSS can draw it as a badge.
        statusCell.appendChild(document.createElement("span"))
            .textContent = valueLabel(doc.status);
        if (doc.review_note) {
            const note = document.createElement("p");
            note.className = "review-note";
            note.textContent = reviewNoteText(doc.review_note);
            statusCell.appendChild(note);
        }
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

/** A dropdown cell for Edit Mode. A saved value missing from the list shows "(not in list)". */
function makeSelectCell(doc, field, values, labelOf) {
    const cell = makeCell("", "nowrap");
    const select = document.createElement("select");
    select.className = "status-select";
    const current = doc[field] || "";
    const choices = ["", ...values];
    if (current && !values.includes(current)) {
        choices.push(current);
    }
    choices.forEach((value) => {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value && !values.includes(value)
            ? t("catalog.not_in_list", { value: value }) : labelOf(value);
        select.appendChild(option);
    });
    select.value = current;
    select.addEventListener("change", async () => {
        const updated = await saveField(doc.id, field, select.value);
        if (!updated) {
            select.value = current;
            return;
        }
        Object.assign(doc, updated);
        // The subcategory list depends on the category, so redraw the row's cells.
        if (field === "category") {
            loadCatalog();
        }
    });
    cell.appendChild(select);
    return cell;
}

/** Names of the subcategories of one category in the project list. */
function subcategoriesOf(categoryName) {
    const category = projectCategories
        .find((item) => item.name === categoryName);
    return category ? category.subcategories : [];
}

/** "Folder / Subfolder" as the user reads it. */
function folderLabel(place) {
    return place.split("/").join(" / ");
}

/** Every folder a file can go into: "Folder", or "Folder/Subfolder". */
function allFolderPlaces() {
    const places = [];
    projectCategories.forEach((top) => {
        if (!top.subcategories.length) {
            places.push(top.name);
        }
        top.subcategories.forEach((sub) => places.push(`${top.name}/${sub}`));
    });
    return places;
}

/** Move a document, then show where it went. createFolder adds the folder first. */
async function moveToFolder(doc, place, createFolder) {
    showToolbarMessage(t("catalog.moving"), false);
    try {
        await moveDocument(doc.id, place, createFolder);
        showToolbarMessage(t("catalog.moved", { folder: folderLabel(place) }),
            false);
    } catch (error) {
        showToolbarMessage(errorText(error), true);
    }
    loadCatalog();
}

/** Folder cell of a tree project: where the file is, the AI's suggestion, and Move. */
function makeFolderCell(doc) {
    const cell = makeCell("", "folder-cell");
    const current = doc.category
        ? [doc.category, doc.subcategory].filter(Boolean).join("/") : "";
    cell.appendChild(document.createElement("span")).textContent = current
        ? folderLabel(current) : t("catalog.in_drop_zone");
    // A duplicate stays in the Drop Zone until the user deletes it.
    if (doc.duplicate_of) {
        return cell;
    }
    if (doc.suggested_folder) {
        const suggestion = document.createElement("p");
        suggestion.className = "review-note";
        suggestion.textContent = t("catalog.suggested_folder",
            { folder: folderLabel(doc.suggested_folder) });
        const create = document.createElement("button");
        create.type = "button";
        create.className = "pill-button folder-create";
        create.textContent = t("catalog.create_and_move");
        create.addEventListener("click", (event) => {
            event.stopPropagation();
            moveToFolder(doc, doc.suggested_folder, true);
        });
        cell.append(suggestion, create);
    }
    const select = document.createElement("select");
    select.className = "status-select folder-move";
    select.setAttribute("aria-label", t("catalog.move_to"));
    const first = document.createElement("option");
    first.value = "";
    first.textContent = t("catalog.move_to");
    select.appendChild(first);
    allFolderPlaces().filter((place) => place !== current).forEach((place) => {
        const option = document.createElement("option");
        option.value = place;
        option.textContent = folderLabel(place);
        select.appendChild(option);
    });
    select.addEventListener("click", (event) => event.stopPropagation());
    select.addEventListener("change", () => {
        if (select.value) {
            moveToFolder(doc, select.value, false);
        }
    });
    cell.appendChild(select);
    return cell;
}

/** Category, Subcategory, and Keywords: always visible. */
function addArchiveCells(row, doc) {
    if (catalogTreeMode) {
        // The folder is the file's place, so it only changes with Move.
        row.appendChild(makeFolderCell(doc));
        row.appendChild(editMode ? makeEditableCell(doc, "keywords")
            : makeCell(fieldText(doc, "keywords"), "keywords"));
    } else if (editMode) {
        row.appendChild(makeSelectCell(doc, "category",
            projectCategories.map((item) => item.name),
            (value) => value || "—"));
        row.appendChild(makeSelectCell(doc, "subcategory",
            subcategoriesOf(doc.category), (value) => value || "—"));
        row.appendChild(makeEditableCell(doc, "keywords"));
    } else {
        row.appendChild(makeCell(doc.category));
        row.appendChild(makeCell(doc.subcategory));
        row.appendChild(makeCell(fieldText(doc, "keywords"), "keywords"));
    }
    MORE_COLUMNS.forEach((field) => {
        let cell;
        if (editMode && field === "confidentiality") {
            cell = makeSelectCell(doc, field, CONFIDENTIALITY_LEVELS,
                (value) => (value ? valueLabel(value) : "—"));
        } else if (editMode) {
            cell = makeEditableCell(doc, field);
        } else {
            cell = makeCell(field === "confidentiality" && doc[field]
                ? valueLabel(doc[field]) : doc[field], "nowrap");
        }
        cell.classList.add("more-col");
        row.appendChild(cell);
    });
    // Where the date came from. Read only, even in Edit Mode.
    const dateSource = makeCell(doc.date_source
        ? t(`catalog.date_from_${doc.date_source}`) : "", "nowrap more-col");
    row.appendChild(dateSource);
    // Why the AI chose the folder, and how sure it was. Read only.
    row.appendChild(makeCell(doc.folder_reason || "", "more-col"));
    row.appendChild(makeCell(doc.confidence
        ? t(`catalog.confidence_${doc.confidence}`) : "", "nowrap more-col"));
}

/** Filename cell: the name opens the file. In Edit Mode it is plain text, but the icons stay. */
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

/** Select a row for the space bar. The id is kept because the table is redrawn. */
function selectRow(id) {
    selectedDocumentId = id;
    document.querySelectorAll("#catalog-body tr").forEach((row) => {
        const isSelected = Number(row.dataset.id) === id;
        row.classList.toggle("row-selected", isSelected);
        row.setAttribute("aria-selected", String(isSelected));
    });
}

function renderTable(documents) {
    const body = document.getElementById("catalog-body");
    forgetSummaries(body);
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
        // The stored value picks the icon in CSS, so it works in both languages.
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
                // At most 2 lines, with Read more (summary.js).
                const summaryCell = makeCell("", "summary");
                summaryCell.appendChild(makeSummary(doc.summary, doc.id));
                row.appendChild(summaryCell);
            } else {
                // Same placeholder as the wireframe for missing summaries.
                row.appendChild(makeCell(t("catalog.summary_placeholder"),
                    "placeholder"));
            }
        }
        addArchiveCells(row, doc);
        row.appendChild(makeStatusCell(doc));
        body.appendChild(row);
    });
    // Keep the selection after the table is redrawn.
    selectRow(selectedDocumentId);
}

function showMessage(text) {
    const message = document.getElementById("catalog-message");
    message.textContent = text;
    message.classList.toggle("hidden", !text);
    document.getElementById("catalog-table")
        .classList.toggle("hidden", Boolean(text));
}

/** Rebuild the Source dropdown, keeping the current choice. */
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

/** Fill one filter dropdown with values, keeping the current choice. */
function fillFilter(select, allLabel, values) {
    const chosen = select.value;
    select.innerHTML = "";
    const allOption = document.createElement("option");
    allOption.value = "";
    allOption.textContent = allLabel;
    select.appendChild(allOption);
    values.forEach((value) => {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        select.appendChild(option);
    });
    select.value = values.includes(chosen) ? chosen : "";
}

/** Category and Subcategory filters: the project list plus older values still in use. */
function updateCategoryFilters(allDocuments) {
    const categories = [...new Set([
        ...projectCategories.map((item) => item.name),
        ...allDocuments.map((doc) => doc.category).filter(Boolean),
    ])].sort();
    const categorySelect = document.getElementById("filter-category");
    fillFilter(categorySelect, t(catalogTreeMode
        ? "catalog.filter_folder_all" : "catalog.filter_category_all"),
    categories);
    // Subcategories of the chosen category, or of every category.
    const chosen = categorySelect.value;
    const subcategories = [...new Set([
        ...projectCategories.filter((item) => !chosen || item.name === chosen)
            .flatMap((item) => item.subcategories),
        ...allDocuments.filter((doc) => !chosen || doc.category === chosen)
            .map((doc) => doc.subcategory).filter(Boolean),
    ])].sort();
    fillFilter(document.getElementById("filter-subcategory"),
        t(catalogTreeMode ? "catalog.filter_subfolder_all"
            : "catalog.filter_subcategory_all"), subcategories);
}

/** A tree project shows one Folder column instead of Category and Subcategory. */
function showFolderColumns(treeMode) {
    catalogTreeMode = treeMode;
    document.getElementById("catalog-table").classList
        .toggle("tree-mode", treeMode);
    const header = document.getElementById("col-category");
    header.dataset.i18n = treeMode ? "catalog.col_folder"
        : "catalog.col_category";
    header.textContent = t(header.dataset.i18n);
}

/** Show or hide the old Inbox warning. It only informs: nothing is moved. */
function renderOldInboxWarning(settings) {
    const warning = document.getElementById("catalog-warning");
    warning.textContent = settings.old_inbox_has_files
        ? t("catalog.old_inbox_warning") : "";
    warning.classList.toggle("hidden", !settings.old_inbox_has_files);
}

/** Fill the progress bar in the header: Classified vs. Manual Review. */
function renderProgress(classified, review) {
    const total = classified + review;
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

async function loadCatalog() {
    try {
        const settings = await getSettings();
        renderOldInboxWarning(settings);

        // Only the active project is shown. With none, or a missing folder, say so.
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

        // All documents feed the Source list and counter, so they stay complete while filtering.
        const allDocuments = await getDocuments();
        projectCategories = settings.categories || [];
        showFolderColumns(settings.folder_mode === "tree");
        updateSourceFilter(allDocuments);
        updateCategoryFilters(allDocuments);
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

/** Mark the tab for a status. "Classified" has no tab. */
function selectStatus(status) {
    currentStatus = status;
    document.querySelectorAll(".tab").forEach((tab) => {
        tab.classList.toggle("active", tab.dataset.status === status);
    });
}

/** Put the chat's filters into the controls and reload. The backend already checked them. */
async function applyCatalogFilters(filters) {
    document.getElementById("search-input").value = filters.text || "";
    document.getElementById("filter-media-type").value =
        filters.media_type || "";
    const source = document.getElementById("filter-source");
    // The source list fills after the first load, so add the option if it is missing.
    if (filters.source && ![...source.options]
            .some((option) => option.value === filters.source)) {
        const option = document.createElement("option");
        option.value = filters.source;
        option.textContent = filters.source;
        source.appendChild(option);
    }
    source.value = filters.source || "";
    // The chat has no category filter, so these start from All.
    document.getElementById("filter-category").value = "";
    document.getElementById("filter-subcategory").value = "";
    selectStatus(filters.status || "");
    await loadCatalog();
}

/** Clear the filters, scroll to a document's row, and highlight it for two seconds. */
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

document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
        currentStatus = tab.dataset.status;
        document.querySelectorAll(".tab").forEach((other) => {
            other.classList.toggle("active", other === tab);
        });
        loadCatalog();
    });
});

// Search 300 ms after the last key press, not on every key.
let searchTimer = null;
// The search is in the top bar, so typing elsewhere opens Catalog first.
document.getElementById("search-input").addEventListener("input", () => {
    if (document.getElementById("view-catalog").classList
            .contains("hidden")) {
        showView("catalog");
    }
    clearTimeout(searchTimer);
    searchTimer = setTimeout(loadCatalog, 300);
});

document.getElementById("filter-media-type")
    .addEventListener("change", loadCatalog);
document.getElementById("filter-source")
    .addEventListener("change", loadCatalog);
document.getElementById("filter-category")
    .addEventListener("change", loadCatalog);
document.getElementById("filter-subcategory")
    .addEventListener("change", loadCatalog);

// More columns: show Counterparty, Confidentiality, Owner, and the effective dates.
document.getElementById("more-columns").addEventListener("change", (event) => {
    document.getElementById("catalog-table").classList
        .toggle("show-more", event.target.checked);
});

// Edit Mode: redraw the table; the bar above it stays while Edit Mode is on.
document.getElementById("edit-mode").addEventListener("change", (event) => {
    editMode = event.target.checked;
    document.getElementById("edit-banner").classList.toggle("hidden",
        !editMode);
    showToolbarMessage("", false);
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

// startApp() in app.js makes the first loadCatalog() call, after the language is known.

// No refresh in Edit Mode (it would erase typing) or while logged out.
setInterval(() => {
    if (!editMode && sessionToken) {
        loadCatalog();
    }
}, REFRESH_SECONDS * 1000);

/** Does this element use the space bar itself? Then no preview. */
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
    // Otherwise the space bar also scrolls the page.
    event.preventDefault();
    runFileAction(selectedDocumentId, "preview");
});
