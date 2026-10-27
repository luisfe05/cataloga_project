/**
 * api.js
 *
 * Thin wrappers around fetch() for every Cataloga API endpoint.
 * All requests go to the Flask backend on 127.0.0.1:5050.
 * 127.0.0.1 is used instead of "localhost" because on a Mac
 * "localhost" can point to a different address (IPv6) than the one
 * Flask listens on.
 * Every function returns a Promise that resolves to parsed JSON,
 * or rejects with an error object shaped like {code, message}.
 */

const BASE_URL = "http://127.0.0.1:5050";

/**
 * Handle a fetch Response: parse JSON, reject on non-2xx status.
 * @param {Response} response
 * @returns {Promise<any>}
 */
async function handleResponse(response) {
    const data = await response.json();
    if (!response.ok) {
        return Promise.reject(data.error
            || { code: "generic", message: "Unknown error" });
    }
    return data;
}

// --- Documents ---

/** GET /documents - list all documents with optional filters.
 * @param {Object} filters - { media_type, source, status, search } all optional.
 * @returns {Promise<Array>}
 */
async function getDocuments(filters = {}) {
    const params = new URLSearchParams(filters).toString();
    const url = params ? `${BASE_URL}/documents?${params}` : `${BASE_URL}/documents`;
    const response = await fetch(url);
    return handleResponse(response);
}

/** GET /documents/:id
 * @param {number} id
 * @returns {Promise<Object>}
 */
async function getDocument(id) {
    const response = await fetch(`${BASE_URL}/documents/${id}`);
    return handleResponse(response);
}

/** PATCH /documents/:id - update editable fields.
 * @param {number} id
 * @param {Object} fields - { source, document_date, summary, media_type, status }
 * @returns {Promise<Object>}
 */
async function updateDocument(id, fields) {
    const response = await fetch(`${BASE_URL}/documents/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(fields),
    });
    return handleResponse(response);
}

/** GET /documents/export - save the catalog as a CSV file.
 * Inside the desktop window, Python shows a "Save as" dialog and writes
 * the file (see save_worksheet in main.py). In a normal browser, the
 * browser downloads it instead.
 * @param {Object} filters - same as getDocuments.
 * @returns {Promise<string>} Where the file was saved ("" if cancelled
 *     or unknown).
 */
async function exportDocuments(filters = {}) {
    const params = new URLSearchParams(filters).toString();
    if (window.pywebview && window.pywebview.api) {
        return window.pywebview.api.save_worksheet(params);
    }
    const url = params
        ? `${BASE_URL}/documents/export?${params}`
        : `${BASE_URL}/documents/export`;
    window.location.href = url;
    return "";
}

// --- Dashboard ---

/** GET /dashboard/stats
 * @returns {Promise<Object>}
 */
async function getDashboardStats() {
    const response = await fetch(`${BASE_URL}/dashboard/stats`);
    return handleResponse(response);
}

// --- Settings ---

/** GET /settings
 * @returns {Promise<Object>}
 */
async function getSettings() {
    const response = await fetch(`${BASE_URL}/settings`);
    return handleResponse(response);
}

/** PUT /settings - the active project's name and naming template, and
 * the app language. A body with only { language } saves just that.
 * @param {Object} data - { research_name, naming_template, language }
 * @returns {Promise<Object>}
 */
async function updateSettings(data) {
    const response = await fetch(`${BASE_URL}/settings`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    });
    return handleResponse(response);
}

/** PUT /settings/ai-provider
 * @param {Object} data - { provider_name, model, api_key }
 * @returns {Promise<Object>}
 */
async function updateAIProvider(data) {
    const response = await fetch(`${BASE_URL}/settings/ai-provider`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    });
    return handleResponse(response);
}

/** POST /settings/ai-provider/test
 * @param {Object} data - { provider_name, model, api_key }
 * @returns {Promise<{connected: boolean}>}
 */
async function testAIProvider(data) {
    const response = await fetch(`${BASE_URL}/settings/ai-provider/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    });
    return handleResponse(response);
}

// --- Projects ---

/** GET /projects - every project and the active one.
 * @returns {Promise<{active_folder: string, projects: Array}>}
 */
async function getProjects() {
    const response = await fetch(`${BASE_URL}/projects`);
    return handleResponse(response);
}

/** POST /projects - create a project (or open a folder that already
 * has a Cataloga catalog) and make it active.
 * @param {Object} data - { name, folder, naming_template, confirm_folder }
 * @returns {Promise<{name: string, folder: string,
 *     opened_existing: boolean}>}
 */
async function createProject(data) {
    const response = await fetch(`${BASE_URL}/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    });
    return handleResponse(response);
}

/** PUT /projects/active - switch to another project.
 * @param {string} folder
 * @returns {Promise<Object>} The project list, like getProjects().
 */
async function setActiveProject(folder) {
    const response = await fetch(`${BASE_URL}/projects/active`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ folder: folder }),
    });
    return handleResponse(response);
}

/** DELETE /projects - take a project out of the list. Its folder and
 * catalog are never deleted.
 * @param {string} folder
 * @returns {Promise<Object>} The project list, like getProjects().
 */
async function removeProject(folder) {
    const response = await fetch(`${BASE_URL}/projects`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ folder: folder }),
    });
    return handleResponse(response);
}
