/**
 * catalog.js
 *
 * Catalog view (Screen 1).
 * Renders the document table and handles the tabs, search box, and
 * filters. The table refreshes every few seconds, so files dropped into
 * the project folder show up once the folder watcher has processed them.
 */

// Seconds between automatic refreshes of the table.
const REFRESH_SECONDS = 10;

// What the user picked on the tabs. "" means All Files.
let currentStatus = "";

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
 * Fill the table body with one row per document.
 * @param {Array<Object>} documents
 */
function renderTable(documents) {
    const body = document.getElementById("catalog-body");
    body.innerHTML = "";
    documents.forEach((doc) => {
        const row = document.createElement("tr");
        row.appendChild(makeCell(doc.original_filename));
        row.appendChild(makeCell(doc.filename));
        row.appendChild(makeCell(doc.media_type));
        row.appendChild(makeCell(doc.source));
        row.appendChild(makeCell(doc.document_date, "nowrap"));
        if (doc.summary) {
            row.appendChild(makeCell(doc.summary, "summary"));
        } else {
            // Same placeholder as the wireframe for missing summaries.
            row.appendChild(makeCell("Manual Summary", "placeholder"));
        }
        const statusClass =
            doc.status === "Manual Review"
                ? "nowrap status-review" : "nowrap";
        row.appendChild(makeCell(doc.status, statusClass));
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

loadCatalog();
setInterval(loadCatalog, REFRESH_SECONDS * 1000);
