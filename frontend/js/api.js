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
 *
 * Every request carries the session token from the login in the header
 * "Authorization: Bearer <token>". The token is only kept in this
 * variable (never in localStorage), so it is gone when the app closes.
 */

const BASE_URL = "http://127.0.0.1:5050";

// Session token from POST /auth/setup or /auth/login. "" = logged out.
let sessionToken = "";

/**
 * Remember the session token, or forget it with "".
 * @param {string} token
 */
function setSessionToken(token) {
    sessionToken = token;
}

/**
 * fetch() with the session token added to the headers.
 * @param {string} url
 * @param {Object} [options] - The same options fetch() takes.
 * @returns {Promise<Response>}
 */
function apiFetch(url, options = {}) {
    const headers = Object.assign({}, options.headers);
    if (sessionToken) {
        headers.Authorization = `Bearer ${sessionToken}`;
    }
    return fetch(url, Object.assign({}, options, { headers: headers }));
}

/**
 * Handle a fetch Response: parse JSON, reject on non-2xx status.
 * A missing or old session token sends the app back to the login
 * screen (showLoginScreen() is in auth.js).
 * @param {Response} response
 * @returns {Promise<any>}
 */
async function handleResponse(response) {
    const data = await response.json();
    if (response.status === 401 && data.error
            && data.error.code === "unauthorized") {
        showLoginScreen();
    }
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
    const response = await apiFetch(url);
    return handleResponse(response);
}

/** GET /documents/:id
 * @param {number} id
 * @returns {Promise<Object>}
 */
async function getDocument(id) {
    const response = await apiFetch(`${BASE_URL}/documents/${id}`);
    return handleResponse(response);
}

/** PATCH /documents/:id - update editable fields.
 * @param {number} id
 * @param {Object} fields - { source, document_date, summary, media_type, status }
 * @returns {Promise<Object>}
 */
async function updateDocument(id, fields) {
    const response = await apiFetch(`${BASE_URL}/documents/${id}`, {
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
        return window.pywebview.api.save_worksheet(params, sessionToken);
    }
    const url = params
        ? `${BASE_URL}/documents/export?${params}`
        : `${BASE_URL}/documents/export`;
    // A plain link cannot send the token, so the file is fetched first
    // and then handed to the browser as a download.
    const response = await apiFetch(url);
    if (!response.ok) {
        return handleResponse(response);
    }
    const link = document.createElement("a");
    link.href = URL.createObjectURL(await response.blob());
    link.download = "cataloga_worksheet.csv";
    link.click();
    URL.revokeObjectURL(link.href);
    return "";
}

// --- Dashboard ---

/** GET /dashboard/stats
 * @returns {Promise<Object>}
 */
async function getDashboardStats() {
    const response = await apiFetch(`${BASE_URL}/dashboard/stats`);
    return handleResponse(response);
}

// --- Settings ---

/** GET /settings
 * @returns {Promise<Object>}
 */
async function getSettings() {
    const response = await apiFetch(`${BASE_URL}/settings`);
    return handleResponse(response);
}

/** PUT /settings - the active project's name and naming template, and
 * the app language. A body with only { language } saves just that.
 * @param {Object} data - { research_name, naming_template, language }
 * @returns {Promise<Object>}
 */
async function updateSettings(data) {
    const response = await apiFetch(`${BASE_URL}/settings`, {
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
    const response = await apiFetch(`${BASE_URL}/settings/ai-provider`, {
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
    const response = await apiFetch(`${BASE_URL}/settings/ai-provider/test`, {
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
    const response = await apiFetch(`${BASE_URL}/projects`);
    return handleResponse(response);
}

/** POST /projects - create a project (or open a folder that already
 * has a Cataloga catalog) and make it active.
 * @param {Object} data - { name, folder, naming_template, confirm_folder }
 * @returns {Promise<{name: string, folder: string,
 *     opened_existing: boolean}>}
 */
async function createProject(data) {
    const response = await apiFetch(`${BASE_URL}/projects`, {
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
    const response = await apiFetch(`${BASE_URL}/projects/active`, {
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
    const response = await apiFetch(`${BASE_URL}/projects`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ folder: folder }),
    });
    return handleResponse(response);
}

// --- Account and session ---

/** GET /auth/status - does the account exist, and the saved language.
 * Works without a token.
 * @returns {Promise<Object>} { account_exists, language }
 */
async function getAuthStatus() {
    const response = await apiFetch(`${BASE_URL}/auth/status`);
    return handleResponse(response);
}

/** POST /auth/setup - create the account, then remember the token.
 * @param {string} username
 * @param {string} password
 * @returns {Promise<Object>} { token, username }
 */
async function setupAccount(username, password) {
    const response = await apiFetch(`${BASE_URL}/auth/setup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: username, password: password }),
    });
    const data = await handleResponse(response);
    setSessionToken(data.token);
    return data;
}

/** POST /auth/login - check the account, then remember the token.
 * @param {string} username
 * @param {string} password
 * @returns {Promise<Object>} { token, username }
 */
async function logIn(username, password) {
    const response = await apiFetch(`${BASE_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: username, password: password }),
    });
    const data = await handleResponse(response);
    setSessionToken(data.token);
    return data;
}

/** POST /auth/logout - end the session and forget the token.
 * @returns {Promise<Object>}
 */
async function logOut() {
    const response = await apiFetch(`${BASE_URL}/auth/logout`,
        { method: "POST" });
    setSessionToken("");
    return handleResponse(response);
}

/** POST /auth/password - change the password. The session stays open.
 * @param {string} currentPassword
 * @param {string} newPassword
 * @returns {Promise<Object>}
 */
async function changePassword(currentPassword, newPassword) {
    const response = await apiFetch(`${BASE_URL}/auth/password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            current_password: currentPassword,
            new_password: newPassword,
        }),
    });
    return handleResponse(response);
}

// --- Chat ---

/** POST /chat - send one message. The answer is one action from a
 * fixed list; the backend never changes anything here.
 * @param {string} message
 * @param {Array<Object>} history - Last messages: [{role, text}].
 * @returns {Promise<Object>} { action, reply, notice, sources,
 *     documents, filters, rename, project }
 */
async function sendChatMessage(message, history) {
    const response = await apiFetch(`${BASE_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: message, history: history }),
    });
    return handleResponse(response);
}

/** POST /documents/:id/rename - rename after the user clicked Confirm.
 * @param {number} id
 * @param {string} newName
 * @returns {Promise<Object>} The updated document.
 */
async function renameDocument(id, newName) {
    const response = await apiFetch(`${BASE_URL}/documents/${id}/rename`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ new_name: newName }),
    });
    return handleResponse(response);
}
