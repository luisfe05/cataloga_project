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
        // Inside the app, the views still hold this account's data.
        if (!document.getElementById("app-main").classList.contains("hidden")) {
            leaveApp();
        } else {
            showLoginScreen();
        }
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

/** PATCH /settings: save one General field, { key, value }. The server checks it. */
async function patchSetting(key, value) {
    const response = await apiFetch(`${BASE_URL}/settings`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key: key, value: value }),
    });
    return handleResponse(response);
}

/** GET /settings/ai-status: provider, model, and whether it connects. Never the key. */
async function getAIStatus() {
    const response = await apiFetch(`${BASE_URL}/settings/ai-status`);
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

/** GET /scan: how far the reading of the project folder is. */
async function getScan() {
    const response = await apiFetch(`${BASE_URL}/scan`);
    return handleResponse(response);
}

/** POST /scan/start, /scan/pause, /scan/resume, /scan/retry */
async function controlScan(action) {
    const response = await apiFetch(`${BASE_URL}/scan/${action}`,
        { method: "POST" });
    return handleResponse(response);
}

// --- Plan ---

/** GET /plan: the draft, its rows and the batches. */
async function getPlan() {
    const response = await apiFetch(`${BASE_URL}/plan`);
    return handleResponse(response);
}

/** PUT /plan/items: approve or skip rows ({status, ids} or {status, all}). */
async function choosePlanItems(data) {
    const response = await apiFetch(`${BASE_URL}/plan/items`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    });
    return handleResponse(response);
}

/** PATCH /plan/items/:id: change a row's folder or name before applying. */
async function editPlanItem(id, data) {
    const response = await apiFetch(`${BASE_URL}/plan/items/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    });
    return handleResponse(response);
}

/** POST /plan/apply, /plan/resume, /plan/undo, with an optional batch id. */
async function runPlan(action, batchId) {
    const response = await apiFetch(`${BASE_URL}/plan/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(batchId ? { batch_id: batchId } : {}),
    });
    return handleResponse(response);
}

/** GET /plan/count: how many proposals wait for a look. */
async function getPlanCount() {
    const response = await apiFetch(`${BASE_URL}/plan/count`);
    return handleResponse(response);
}

/** PUT /plan/leave: mark a folder Leave as is, or unmark it. */
async function setLeaveAlone(folder, leave) {
    const response = await apiFetch(`${BASE_URL}/plan/leave`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ folder: folder, leave: leave }),
    });
    return handleResponse(response);
}

/** GET /plan/progress: how far the running batch is. */
async function getPlanProgress() {
    const response = await apiFetch(`${BASE_URL}/plan/progress`);
    return handleResponse(response);
}

/** POST /projects/folders/list: what a folder holds. No AI, nothing written. */
async function listNewFolder(folder) {
    const response = await apiFetch(`${BASE_URL}/projects/folders/list`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ folder: folder }),
    });
    return handleResponse(response);
}

/** POST /projects/active/learn: use the tree of the project's own folder. */
async function learnActiveProject() {
    const response = await apiFetch(`${BASE_URL}/projects/active/learn`,
        { method: "POST" });
    return handleResponse(response);
}

/** POST /settings/sheet/suggest: the AI writes the sheet from a sample. Saves nothing. */
async function suggestSheet(folder) {
    const response = await apiFetch(`${BASE_URL}/settings/sheet/suggest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ folder: folder }),
    });
    return handleResponse(response);
}

/** DELETE /settings/ai-provider/<role>: take the fallback or media provider away. */
async function deleteAIProvider(role) {
    const response = await apiFetch(`${BASE_URL}/settings/ai-provider/${role}`,
        { method: "DELETE" });
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

/** POST /projects/folders/suggest: a folder tree from the AI. Saves nothing.
 *  With a folder, only for the files already in it; About this project is context. */
async function suggestFolders(projectSheet, industry, folder) {
    const response = await apiFetch(`${BASE_URL}/projects/folders/suggest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_sheet: projectSheet,
            industry: industry || "", folder: folder || "" }),
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

/** GET /auth/status: is there any account, and the language. No token needed. */
async function getAuthStatus() {
    const response = await apiFetch(`${BASE_URL}/auth/status`);
    return handleResponse(response);
}

/** POST /auth/register - create an account (terms accepted), remember the token. */
async function registerAccount(username, password, termsVersion) {
    const response = await apiFetch(`${BASE_URL}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: username, password: password,
            accepted_terms: termsVersion }),
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

/** POST with a JSON body to an account route; returns the parsed answer. */
async function postAccount(path, body) {
    const response = await apiFetch(`${BASE_URL}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });
    return handleResponse(response);
}

/** POST /auth/terms - accept the current terms after a login that asked. */
function acceptTerms(version) {
    return postAccount("/auth/terms", { version: version });
}

/** GET /auth/recovery - the day the key was saved to a file, or "". */
async function getRecoveryStatus() {
    const response = await apiFetch(`${BASE_URL}/auth/recovery`);
    return handleResponse(response);
}

/** POST /auth/recovery/key - the same key, or a new one. Needs the password. */
function getRecoveryKey(password, makeNew) {
    return postAccount("/auth/recovery/key",
        { password: password, new: makeNew });
}

/** POST /auth/recovery/save - the server writes the key to the chosen file. */
function saveRecoveryFile(path, ticket) {
    return postAccount("/auth/recovery/save", { path: path, ticket: ticket });
}

/** POST /auth/recovery/reset - a new password with the recovery key. */
async function resetPassword(username, key, newPassword) {
    const data = await postAccount("/auth/recovery/reset", {
        username: username, recovery_key: key, new_password: newPassword });
    setSessionToken(data.token);
    return data;
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

// --- Browse ---

/** GET /browse: one folder of the project, as on the disk. */
async function browseFolderList(path) {
    const query = new URLSearchParams({ path: path }).toString();
    const response = await apiFetch(`${BASE_URL}/browse?${query}`);
    return handleResponse(response);
}

/** The address of a file's small picture. An <img> cannot send headers. */
function fileThumbUrl(path) {
    const query = new URLSearchParams({ path: path, token: sessionToken });
    return `${BASE_URL}/browse/thumb?${query.toString()}`;
}

/** GET /browse/preview: a picture or text for the overlay, by path. */
async function getFilePreview(path) {
    const query = new URLSearchParams({ path: path }).toString();
    const response = await apiFetch(`${BASE_URL}/browse/preview?${query}`);
    return handleResponse(response);
}

/** The address of a recording, by path. */
function fileMediaUrl(path) {
    const query = new URLSearchParams({ path: path, token: sessionToken });
    return `${BASE_URL}/browse/media?${query.toString()}`;
}

/** POST /browse/reveal: show a file or folder in Finder. */
async function revealFile(path) {
    const response = await apiFetch(`${BASE_URL}/browse/reveal`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: path }),
    });
    return handleResponse(response);
}

/** POST /browse/open: open a file of the project with its default app. */
async function openFileAt(path) {
    const response = await apiFetch(`${BASE_URL}/browse/open`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: path }),
    });
    return handleResponse(response);
}

/** GET /documents/:id/preview: a picture or text for the overlay. */
async function getDocumentPreview(id) {
    const response = await apiFetch(`${BASE_URL}/documents/${id}/preview`);
    return handleResponse(response);
}

/** The address of a recording. A player cannot send the token in a header. */
function documentMediaUrl(id) {
    return `${BASE_URL}/documents/${id}/media?token=${encodeURIComponent(sessionToken)}`;
}

/** POST /documents/:id/<action> - open or reveal a file. */
async function runDocumentFileAction(id, action) {
    const response = await apiFetch(
        `${BASE_URL}/documents/${id}/${action}`, { method: "POST" });
    return handleResponse(response);
}
