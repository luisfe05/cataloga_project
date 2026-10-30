/** api.js: fetch() for every endpoint. 127.0.0.1, because localhost can be IPv6 on a Mac. */

const BASE_URL = "http://127.0.0.1:5050";

// Session token, only in memory (never localStorage). "" = logged out.
let sessionToken = "";

function setSessionToken(token) {
    sessionToken = token;
}

/** fetch() with the session token added to the headers. */
function apiFetch(url, options = {}) {
    const headers = Object.assign({}, options.headers);
    if (sessionToken) {
        headers.Authorization = `Bearer ${sessionToken}`;
    }
    return fetch(url, Object.assign({}, options, { headers: headers }));
}

/** Parse JSON and reject on non-2xx. A 401 goes back to the login screen. */
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

/** GET /documents - list all documents with optional filters. */
async function getDocuments(filters = {}) {
    const params = new URLSearchParams(filters).toString();
    const url = params ? `${BASE_URL}/documents?${params}` : `${BASE_URL}/documents`;
    const response = await apiFetch(url);
    return handleResponse(response);
}

/** GET /documents/:id */
async function getDocument(id) {
    const response = await apiFetch(`${BASE_URL}/documents/${id}`);
    return handleResponse(response);
}

/** PATCH /documents/:id - update editable fields. */
async function updateDocument(id, fields) {
    const response = await apiFetch(`${BASE_URL}/documents/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(fields),
    });
    return handleResponse(response);
}

/** GET /documents/export. In the window, Python shows Save as (main.py); a browser downloads. */
async function exportDocuments(filters = {}) {
    const params = new URLSearchParams(filters).toString();
    if (window.pywebview && window.pywebview.api) {
        return window.pywebview.api.save_worksheet(params, sessionToken);
    }
    const url = params
        ? `${BASE_URL}/documents/export?${params}`
        : `${BASE_URL}/documents/export`;
    // A plain link cannot send the token, so fetch the file first.
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

/** GET /dashboard/stats */
async function getDashboardStats() {
    const response = await apiFetch(`${BASE_URL}/dashboard/stats`);
    return handleResponse(response);
}

// --- Settings ---

/** GET /settings */
async function getSettings() {
    const response = await apiFetch(`${BASE_URL}/settings`);
    return handleResponse(response);
}

/** PUT /settings: name, naming template, categories, and language. { language } alone saves just that. */
async function updateSettings(data) {
    const response = await apiFetch(`${BASE_URL}/settings`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    });
    return handleResponse(response);
}

/** POST /settings/categories/suggest: categories for an industry. Saves nothing. */
async function suggestCategories(industry) {
    const response = await apiFetch(`${BASE_URL}/settings/categories/suggest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ industry: industry }),
    });
    return handleResponse(response);
}

/** PUT /settings/ai-provider */
async function updateAIProvider(data) {
    const response = await apiFetch(`${BASE_URL}/settings/ai-provider`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    });
    return handleResponse(response);
}

/** POST /settings/ai-provider/test */
async function testAIProvider(data) {
    const response = await apiFetch(`${BASE_URL}/settings/ai-provider/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    });
    return handleResponse(response);
}

// --- Projects ---

/** GET /projects - every project and the active one. */
async function getProjects() {
    const response = await apiFetch(`${BASE_URL}/projects`);
    return handleResponse(response);
}

/** POST /projects: create a project, or open a folder that has a catalog, and make it active. */
async function createProject(data) {
    const response = await apiFetch(`${BASE_URL}/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    });
    return handleResponse(response);
}

/** POST /projects/folders/suggest: a folder tree from Ollama Cloud. Saves nothing. */
async function suggestFolders(description, industry) {
    const response = await apiFetch(`${BASE_URL}/projects/folders/suggest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ description: description,
            industry: industry || "" }),
    });
    return handleResponse(response);
}

/** POST /projects/folders/inspect: does the folder look like a website or a linked project? */
async function inspectFolder(folder) {
    const response = await apiFetch(`${BASE_URL}/projects/folders/inspect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ folder: folder }),
    });
    return handleResponse(response);
}

/** PUT /projects/active - switch to another project. */
async function setActiveProject(folder) {
    const response = await apiFetch(`${BASE_URL}/projects/active`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ folder: folder }),
    });
    return handleResponse(response);
}

/** DELETE /projects: take a project off the list. Its folder is never deleted. */
async function removeProject(folder) {
    const response = await apiFetch(`${BASE_URL}/projects`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ folder: folder }),
    });
    return handleResponse(response);
}

// --- Account and session ---

/** GET /auth/status: does the account exist, and the language. No token needed. */
async function getAuthStatus() {
    const response = await apiFetch(`${BASE_URL}/auth/status`);
    return handleResponse(response);
}

/** POST /auth/setup - create the account, then remember the token. */
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

/** POST /auth/login - check the account, then remember the token. */
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

/** POST /auth/logout - end the session and forget the token. */
async function logOut() {
    const response = await apiFetch(`${BASE_URL}/auth/logout`,
        { method: "POST" });
    setSessionToken("");
    return handleResponse(response);
}

/** POST /auth/password - change the password. The session stays open. */
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

/** POST /chat: one message; the answer is one action from a fixed list and changes nothing. */
async function sendChatMessage(message, history) {
    const response = await apiFetch(`${BASE_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: message, history: history }),
    });
    return handleResponse(response);
}

/** POST /documents/:id/rename - rename after the user clicked Confirm. */
async function renameDocument(id, newName) {
    const response = await apiFetch(`${BASE_URL}/documents/${id}/rename`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ new_name: newName }),
    });
    return handleResponse(response);
}

/** POST /documents/:id/move: move one document to a folder of the tree. */
async function moveDocument(id, folder, createFolder) {
    const response = await apiFetch(`${BASE_URL}/documents/${id}/move`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ folder: folder,
            create_folder: Boolean(createFolder) }),
    });
    return handleResponse(response);
}

// --- File links: only the id is sent, never a path ---

/** POST /documents/:id/<action> - open, reveal, or preview a file. */
async function runDocumentFileAction(id, action) {
    const response = await apiFetch(
        `${BASE_URL}/documents/${id}/${action}`, { method: "POST" });
    return handleResponse(response);
}
