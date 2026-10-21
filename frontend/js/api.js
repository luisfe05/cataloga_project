/**
 * api.js
 *
 * Thin wrappers around fetch() for every Cataloga API endpoint.
 * All requests go to the Flask backend on localhost:5000.
 * Every function returns a Promise that resolves to parsed JSON,
 * or rejects with an error object shaped like {code, message}.
 */

const BASE_URL = "http://localhost:5000";

/**
 * Handle a fetch Response: parse JSON, reject on non-2xx status.
 * @param {Response} response
 * @returns {Promise<any>}
 */
async function handleResponse(response) {
    const data = await response.json();
    if (!response.ok) {
        return Promise.reject(data.error || { message: "Unknown error" });
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

/** GET /documents/export - download the catalog as a file.
 * @param {Object} filters - same as getDocuments, plus optional format ('csv'|'xlsx').
 */
function exportDocuments(filters = {}) {
    const params = new URLSearchParams(filters).toString();
    const url = params
        ? `${BASE_URL}/documents/export?${params}`
        : `${BASE_URL}/documents/export`;
    // Trigger a browser download by navigating to the URL.
    window.location.href = url;
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

/** PUT /settings
 * @param {Object} data - { research_name, target_directory }
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
