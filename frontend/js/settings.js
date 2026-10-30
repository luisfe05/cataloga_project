/** settings.js: Settings. Save tests the AI first, so a wrong API key is never saved. */

// The key is the backend's name. The first model is the default: free or cheapest.
const AI_PROVIDERS = {
    ollama: {
        label: "Ollama Cloud",
        models: ["gemma4:31b", "nemotron-3-nano:30b"],
    },
    gemini: {
        label: "Google Gemini",
        models: ["gemini-3.5-flash-lite", "gemini-2.5-flash",
            "gemini-2.5-flash-lite"],
    },
    groq: {
        label: "Groq",
        models: ["llama-3.1-8b-instant", "llama-3.3-70b-versatile",
            "openai/gpt-oss-20b"],
    },
    claude: {
        label: "Anthropic Claude",
        models: ["claude-sonnet-5-5", "claude-opus-5-5", "claude-haiku-5-5"],
    },
    xai: {
        label: "xAI Grok",
        models: ["grok-4.7"],
    },
    openai: {
        label: "OpenAI",
        models: ["gpt-5.4-nano", "gpt-5.4-mini"],
    },
};

// One row of the AI Provider section per role; the backend saves them by role.
const PROVIDER_ROWS = {
    text: { provider: "ai-provider", model: "ai-model", key: "api-key" },
    fallback: { provider: "fallback-provider", model: "fallback-model",
        key: "fallback-key" },
    media: { provider: "media-provider", model: "media-model",
        key: "media-key" },
};

// What each row can choose. "" is "None"; only Gemini reads audio and video.
const ROW_PROVIDERS = {
    text: Object.keys(AI_PROVIDERS),
    fallback: ["", ...Object.keys(AI_PROVIDERS)],
    media: ["", "gemini"],
};

const NAMING_METHODS = {
    m1: "{date}_{topic}",
    m2: "{source}_{date}_{topic}",
    m3: "{number}_{topic}",
    m4: "{topic}_{source}_{date}_{topic_number}",
};

// Parts a template can use, and characters a file name cannot have.
const NAMING_TOKENS = ["date", "source", "topic", "number", "original",
    "topic_number"];
const FORBIDDEN_CHARACTERS = '/\\:*?"<>|';

// Custom name parts, in the order of the buttons. "Number" is the 3-digit number per topic.
const NAMING_BLOCKS = ["topic", "source", "date", "topic_number", "original"];
const BLOCK_LABELS = {
    topic: "naming.block_topic",
    source: "naming.block_source",
    date: "naming.block_date",
    topic_number: "naming.block_number",
    original: "naming.block_original",
};

// The Custom parts chosen, in order, and the character between them.
let customBlocks = [];
let customSeparator = "_";

// A saved custom template that is not made of parts, like "archivo-{date}".
let legacyTemplate = "";

// Example values for the live preview.
const PREVIEW_PARTS = {
    date: "2026-07-15",
    source: "el-nuevo-dia",
    topic: "oceanman-malta",
    number: "0001",
    original: "scan-0042",
    topic_number: "001",
};

// True after the folder warning, so the next click confirms it.
let folderWarningShown = false;

// "edit" for the active project, "new" while creating a project.
let projectMode = "edit";

// False before the first project: nothing to go back to, so Cancel is hidden.
let hasProjects = false;

// True once pywebview's folder picker can be used.
let pywebviewReady = Boolean(window.pywebview && window.pywebview.api);

// For the Remove project dialog.
let savedProjectName = "";

// Providers with an API key ready. The backend never sends the key itself.
let providersWithKey = [];

function updateSaveButton() {
    let text = t("settings.save");
    if (folderWarningShown) {
        text = t("settings.save_anyway");
    } else if (projectMode === "new") {
        text = t("project.create");
    }
    document.getElementById("save-button").textContent = text;
}

function updateBrowseButton() {
    document.getElementById("browse-button").classList.toggle(
        "hidden", !(pywebviewReady && projectMode === "new"));
}

function setProjectMode(mode) {
    projectMode = mode;
    const isNew = mode === "new";
    document.getElementById("project-form-title").textContent =
        t(isNew ? "project.new_title" : "project.edit_title");
    document.getElementById("target-directory").readOnly = !isNew;
    document.getElementById("folder-locked")
        .classList.toggle("hidden", isNew);
    document.getElementById("cancel-new-project")
        .classList.toggle("hidden", !(isNew && hasProjects));
    document.getElementById("remove-project-section")
        .classList.toggle("hidden", isNew);
    // New projects get a folder tree; old projects keep their categories.
    const treeMode = isNew || projectFolderMode === "tree";
    document.getElementById("categories-section")
        .classList.toggle("hidden", treeMode);
    document.getElementById("folders-section")
        .classList.toggle("hidden", !treeMode);
    updateBrowseButton();
    resetFolderWarning();
}

/** Empty the form for a new project, which starts with Ollama Cloud. */
function startNewProject() {
    setProjectMode("new");
    showFolderSection({}, true);
    document.getElementById("research-name").value = "";
    document.getElementById("target-directory").value = "";
    document.getElementById("folder-advice").classList.add("hidden");
    document.getElementById("project-sheet").value = "";
    showSheetMessage("", "");
    // New projects start with method 4.
    showSavedTemplate(NAMING_METHODS.m4);
    showCategories("", []);
    showProvider("text", "ollama", "");
    showProvider("fallback", "", "");
    showProvider("media", "", "");
    document.getElementById("server-url").value = "";
    showSettingsMessage("", "");
}

function rowField(role, name) {
    return document.getElementById(PROVIDER_ROWS[role][name]);
}

function rowProvider(role) {
    return rowField(role, "provider").value;
}

function providerHasKey(provider) {
    return providersWithKey.includes(provider);
}

function updateKeyPlaceholder(role) {
    const provider = rowProvider(role);
    const field = rowField(role, "key");
    field.disabled = !provider;
    field.placeholder = providerHasKey(provider)
        ? t("settings.api_key_saved") : t("settings.api_key_placeholder");
}

/** The line under the title: the main provider, and the fallback if any. */
function updateAIStatus() {
    const provider = rowProvider("text");
    const vars = { provider: AI_PROVIDERS[provider].label,
        model: rowField("text", "model").value };
    let text = providerHasKey(provider)
        ? t("settings.ai_using", vars) : t("settings.ai_needs_key", vars);
    const fallback = rowProvider("fallback");
    if (fallback) {
        text += " " + t("settings.ai_using_fallback", {
            provider: AI_PROVIDERS[fallback].label,
            model: rowField("fallback", "model").value });
    }
    document.getElementById("ai-status").textContent = text;
}

/** Show a row's provider. Advanced settings opens only if the main one needs a key. */
function showProvider(role, provider, model) {
    rowField(role, "provider").value = provider;
    rowField(role, "key").value = "";
    fillModels(role, model);
    if (role === "text") {
        document.getElementById("ai-advanced").open =
            provider !== "ollama" || !providerHasKey(provider);
    }
    updateKeyPlaceholder(role);
    updateAIStatus();
}

/** Read the three rows. A row with no provider chosen is null. */
function readProviderRows() {
    const rows = {};
    Object.keys(PROVIDER_ROWS).forEach((role) => {
        const provider = rowProvider(role);
        rows[role] = provider ? {
            role: role,
            provider_name: provider,
            model: rowField(role, "model").value,
            api_key: rowField(role, "key").value.trim(),
        } : null;
    });
    return rows;
}

function readServerUrl() {
    return document.getElementById("server-url").value.trim();
}

/** Test and save each row. An empty optional row is cleared in the backend. */
async function saveProviderRows(rows) {
    const serverUrl = readServerUrl();
    for (const role of Object.keys(PROVIDER_ROWS)) {
        const data = rows[role];
        if (!data) {
            if (role !== "text") {
                await deleteAIProvider(role);
            }
            continue;
        }
        await testAIProvider({ ...data, server_url: serverUrl });
        await updateAIProvider(data);
    }
}

function resetFolderWarning() {
    folderWarningShown = false;
    updateSaveButton();
}

/** Same rules as validate_template() in naming.py; the backend checks again. */
function validateTemplate(template) {
    if (!template.trim()) {
        return { reason: "empty", token: "" };
    }
    const found = [...template.matchAll(/\{([^{}]*)\}/g)]
        .map((match) => match[1]);
    const unknown = found.find((name) => !NAMING_TOKENS.includes(name));
    if (unknown !== undefined) {
        return { reason: "unknown", token: `{${unknown}}` };
    }
    if (found.length === 0) {
        return { reason: "no_token", token: "" };
    }
    // The braces are allowed, so remove them first.
    const text = template.replace(/\{[^{}]*\}/g, "");
    if ([...text].some((char) => FORBIDDEN_CHARACTERS.includes(char))) {
        return { reason: "chars", token: "" };
    }
    return null;
}

/** Fill a template with example values, like render_template() in naming.py. */
function previewFilename(template) {
    let name = template;
    NAMING_TOKENS.forEach((token) => {
        name = name.split(`{${token}}`).join(PREVIEW_PARTS[token]);
    });
    name = name.replace(/_{2,}/g, "_").replace(/-{2,}/g, "-")
        .replace(/^[_\-. ]+|[_\-. ]+$/g, "");
    return (name || PREVIEW_PARTS.number) + ".pdf";
}

/** The Custom template: the parts in braces, joined by the separator. */
function customTemplate() {
    if (!customBlocks.length) {
        return legacyTemplate;
    }
    return customBlocks.map((block) => `{${block}}`).join(customSeparator);
}

/** Read a saved template as parts and a separator, or null if it is not made of parts. */
function parseBlocks(template) {
    for (const separator of ["_", "-"]) {
        const parts = template.split(separator);
        const blocks = parts.map((part) => {
            const match = part.match(/^\{([a-z_]+)\}$/);
            return match ? match[1] : "";
        });
        const allBlocks = blocks.every((block) => NAMING_BLOCKS.includes(block));
        if (allBlocks && new Set(blocks).size === blocks.length) {
            return { blocks: blocks, separator: separator };
        }
    }
    return null;
}

/** One chosen part: its name, ← and → to reorder, and × to remove it. */
function makeChosenBlock(block, index) {
    const chip = document.createElement("span");
    chip.className = "naming-chip";
    const label = document.createElement("span");
    label.textContent = t(BLOCK_LABELS[block]);
    const buttons = [
        ["←", "naming.move_left", index > 0, () => {
            customBlocks.splice(index - 1, 0, customBlocks.splice(index, 1)[0]);
        }],
        ["→", "naming.move_right", index < customBlocks.length - 1, () => {
            customBlocks.splice(index + 1, 0, customBlocks.splice(index, 1)[0]);
        }],
        ["×", "naming.remove_block", true, () => {
            customBlocks.splice(index, 1);
        }],
    ];
    chip.appendChild(label);
    buttons.forEach(([text, labelKey, enabled, action]) => {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = text;
        button.disabled = !enabled;
        button.setAttribute("aria-label", t(labelKey));
        button.addEventListener("click", () => {
            action();
            renderNamingBlocks();
        });
        chip.appendChild(button);
    });
    return chip;
}

/** Draw the part buttons and the chosen parts, then update the preview. */
function renderNamingBlocks() {
    const buttons = document.getElementById("naming-blocks");
    buttons.innerHTML = "";
    NAMING_BLOCKS.forEach((block) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "pill-button";
        button.textContent = "+ " + t(BLOCK_LABELS[block]);
        // Each part is used once.
        button.disabled = customBlocks.includes(block);
        button.addEventListener("click", () => {
            customBlocks.push(block);
            // Picking a part replaces an old typed template.
            legacyTemplate = "";
            renderNamingBlocks();
        });
        buttons.appendChild(button);
    });
    const chosen = document.getElementById("naming-chosen");
    chosen.innerHTML = "";
    customBlocks.forEach((block, index) => {
        chosen.appendChild(makeChosenBlock(block, index));
    });
    if (!customBlocks.length) {
        const empty = document.createElement("span");
        empty.className = "hint";
        empty.textContent = t("naming.chosen_empty");
        chosen.appendChild(empty);
    }
    const legacy = document.getElementById("naming-legacy");
    legacy.textContent = legacyTemplate
        ? t("naming.legacy", { template: legacyTemplate }) : "";
    legacy.classList.toggle("hidden", !legacyTemplate);
    updateNamingPreview();
}

function chosenTemplate() {
    const picked = document.querySelector(
        'input[name="naming-method"]:checked');
    const method = picked ? picked.value : "m1";
    if (method === "custom") {
        return customTemplate();
    }
    return NAMING_METHODS[method];
}

/** Show Custom's box, check the template, and update the preview. */
function updateNamingPreview() {
    const picked = document.querySelector(
        'input[name="naming-method"]:checked');
    const isCustom = Boolean(picked) && picked.value === "custom";
    document.getElementById("naming-custom")
        .classList.toggle("hidden", !isCustom);

    const template = chosenTemplate();
    const problem = isCustom && !template.trim()
        ? { reason: "no_blocks", token: "" } : validateTemplate(template);
    document.getElementById("naming-error").textContent = problem
        ? t(`naming.err_${problem.reason}`, { token: problem.token }) : "";
    document.getElementById("naming-preview").textContent = problem
        ? "" : previewFilename(template);
    return !problem;
}

/** Select the method for a saved template; anything else is Custom. */
function showSavedTemplate(template) {
    let method = "custom";
    Object.keys(NAMING_METHODS).forEach((key) => {
        if (NAMING_METHODS[key] === template) {
            method = key;
        }
    });
    document.querySelector(
        `input[name="naming-method"][value="${method}"]`).checked = true;
    customBlocks = [];
    customSeparator = "_";
    legacyTemplate = "";
    if (method === "custom") {
        const parsed = parseBlocks(template);
        if (parsed) {
            customBlocks = parsed.blocks;
            customSeparator = parsed.separator;
        } else {
            legacyTemplate = template;
        }
    }
    document.querySelector(
        `input[name="naming-separator"][value="${customSeparator}"]`)
        .checked = true;
    renderNamingBlocks();
}

/** After a folder is chosen for a new project, say what it looks like. */
async function adviseOnFolder() {
    const advice = document.getElementById("folder-advice");
    const folder = document.getElementById("target-directory").value.trim();
    advice.classList.add("hidden");
    if (projectMode !== "new" || !folder) {
        return;
    }
    try {
        const result = await inspectFolder(folder);
        if (result.catalog_only_recommended) {
            advice.textContent = t("project.linked_advice",
                { markers: result.markers.slice(0, 4).join(", ") });
            advice.className = "form-message";
            advice.classList.remove("hidden");
        }
    } catch (error) {
        // A folder that does not exist yet gets no advice.
    }
}

function showSheetMessage(text, kind) {
    const message = document.getElementById("sheet-message");
    message.textContent = text;
    message.className = "form-message " + kind;
}

/** Ask the AI for the sheet of the chosen folder; the user edits it before Save. */
async function suggestProjectSheet() {
    const folder = document.getElementById("target-directory").value.trim();
    if (!folder) {
        showSheetMessage(t("sheet.need_folder"), "error");
        return;
    }
    const button = document.getElementById("suggest-sheet");
    button.disabled = true;
    showSheetMessage(t("sheet.suggesting"), "");
    try {
        const result = await suggestSheet(folder);
        document.getElementById("project-sheet").value = result.sheet;
        showSheetMessage(t("sheet.suggested"), "success");
    } catch (error) {
        showSheetMessage(errorText(error), "error");
    } finally {
        button.disabled = false;
    }
}

function showSettingsMessage(text, kind) {
    const message = document.getElementById("settings-message");
    message.textContent = text;
    message.className = "form-message " + kind;
}

function fillModels(role, chosenModel) {
    const provider = rowProvider(role);
    const select = rowField(role, "model");
    select.innerHTML = "";
    select.disabled = !provider;
    const models = provider ? AI_PROVIDERS[provider].models : [];
    models.forEach((model) => {
        const option = document.createElement("option");
        option.value = model;
        option.textContent = model;
        select.appendChild(option);
    });
    if (models.includes(chosenModel)) {
        select.value = chosenModel;
    }
}

function fillProviders() {
    Object.keys(PROVIDER_ROWS).forEach((role) => {
        const select = rowField(role, "provider");
        select.innerHTML = "";
        ROW_PROVIDERS[role].forEach((name) => {
            const option = document.createElement("option");
            option.value = name;
            option.textContent = name ? AI_PROVIDERS[name].label
                : t("settings.ai_none");
            select.appendChild(option);
        });
    });
}

/** Load the saved settings. The backend never sends the API key. */
async function loadSettings() {
    try {
        const settings = await getSettings();
        hasProjects = settings.project_status !== "none";
        document.getElementById("research-name").value =
            settings.research_name;
        savedProjectName = settings.research_name;
        document.getElementById("account-username").value =
            settings.username;
        document.getElementById("topbar-user").textContent =
            settings.username;
        document.getElementById("target-directory").value =
            settings.target_directory;

        document.getElementById("project-sheet").value =
            settings.project_sheet || "";
        showSheetMessage("", "");
        document.getElementById("language-select").value =
            settings.language;
        showSavedTemplate(settings.naming_template);
        projectFolderMode = settings.folder_mode;
        showCategories(settings.industry, settings.categories);
        if (projectFolderMode === "tree") {
            showFolderSection(settings, false);
        }

        providersWithKey = settings.providers_with_key;
        // A project with no provider saved yet gets Ollama Cloud.
        const provider = settings.active_provider in AI_PROVIDERS
            ? settings.active_provider : "ollama";
        showProvider("text", provider, settings.active_model);
        showProvider("fallback", settings.fallback_provider || "",
            settings.fallback_model);
        showProvider("media", settings.media_provider || "",
            settings.media_model);
        document.getElementById("server-url").value =
            settings.server_url || "";

        // With no project yet, the form starts as "New project".
        if (hasProjects) {
            setProjectMode("edit");
        } else {
            startNewProject();
        }
        if (settings.project_status === "unavailable") {
            showSettingsMessage(t("error.project_unavailable",
                { path: settings.target_directory }), "error");
        }
    } catch (error) {
        showSettingsMessage(t("settings.load_failed",
            { message: errorText(error) }), "error");
    }
}

/** Save: project, then AI test, then provider (only if the test passed). */
async function saveSettings(event) {
    event.preventDefault();

    const saveButton = document.getElementById("save-button");
    // A wrong template shows its error and nothing is sent.
    if (!updateNamingPreview()) {
        showSettingsMessage(
            document.getElementById("naming-error").textContent, "error");
        return;
    }
    const isTree = projectMode === "new" || projectFolderMode === "tree";
    const treeProblem = isTree ? folderTreeProblem() : "";
    if (treeProblem) {
        showFoldersMessage(treeProblem, "error");
        showSettingsMessage(treeProblem, "error");
        return;
    }
    const providerRows = readProviderRows();

    const isNew = projectMode === "new";
    // True once a new project exists, even if the AI test fails later.
    let projectCreated = false;
    let doneMessage = t("settings.saved");

    saveButton.disabled = true;
    showSettingsMessage(t(isNew ? "project.creating" : "settings.saving"),
        "");
    try {
        if (isNew) {
            const created = await createProject({
                name: document.getElementById("research-name").value,
                folder: document.getElementById("target-directory").value,
                naming_template: chosenTemplate(),
                description: document.getElementById("project-description")
                    .value.trim(),
                project_sheet: document.getElementById("project-sheet")
                    .value.trim(),
                folders: readFolderTree(),
                confirm_folder: folderWarningShown,
                server_url: readServerUrl(),
            });
            projectCreated = true;
            doneMessage = t(created.opened_existing
                ? "project.opened_existing" : "project.created");
        } else {
            await updateSettings({
                research_name:
                    document.getElementById("research-name").value,
                naming_template: chosenTemplate(),
                project_sheet: document.getElementById("project-sheet")
                    .value.trim(),
                industry: document.getElementById("industry").value,
                // In a tree project the categories are the folders.
                categories: isTree ? readFolderTree() : readCategories(),
                server_url: readServerUrl(),
            });
        }
        resetFolderWarning();
        await saveProviderRows(providerRows);
        await refreshAfterProjectChange();
        showSettingsMessage(doneMessage, "success");
    } catch (error) {
        if (projectCreated) {
            // The project exists now: show it, then explain the error.
            await refreshAfterProjectChange();
        }
        if (error.code === "folder_not_empty") {
            folderWarningShown = true;
            updateSaveButton();
        }
        // The backend checks the template too and says why it failed.
        const message = error.code === "invalid_template"
            ? t(`naming.err_${error.reason}`, { token: error.token })
            : errorText(error);
        showSettingsMessage(message, "error");
    } finally {
        saveButton.disabled = false;
    }
}

function openRemoveDialog() {
    document.getElementById("remove-project-title").textContent =
        t("project.remove_title", { name: savedProjectName });
    document.getElementById("remove-project-error").textContent = "";
    document.getElementById("remove-project-confirm").disabled = false;
    document.getElementById("remove-project-dialog").showModal();
}

/** Remove the active project from the list. The most recently opened one becomes active. */
async function confirmRemoveProject() {
    const dialog = document.getElementById("remove-project-dialog");
    const confirmButton = document.getElementById("remove-project-confirm");
    confirmButton.disabled = true;
    try {
        await removeProject(
            document.getElementById("target-directory").value);
    } catch (error) {
        document.getElementById("remove-project-error").textContent =
            errorText(error);
        confirmButton.disabled = false;
        return;
    }
    dialog.close();
    await refreshAfterProjectChange();
    showSettingsMessage(t("project.removed"), "success");
}

/** Open the folder picker. Only the desktop window has it, so a browser hides Browse. */
async function browseFolder() {
    const folder = await window.pywebview.api.choose_folder();
    if (folder) {
        document.getElementById("target-directory").value = folder;
        adviseOnFolder();
        resetFolderWarning();
    }
}

/** Apply and save the language; reload the views so JS-built text changes too. */
async function changeLanguage() {
    const language = document.getElementById("language-select").value;
    setLanguage(language);
    updateSaveButton();
    updateKeyPlaceholder();
    updateAIStatus();
    // Redraws the part names in the new language, and the preview.
    renderNamingBlocks();
    document.getElementById("project-form-title").textContent = t(
        projectMode === "new" ? "project.new_title" : "project.edit_title");
    showSettingsMessage("", "");
    loadProjectHeader();
    loadCatalog();
    if (!document.getElementById("view-dashboard")
            .classList.contains("hidden")) {
        loadDashboard();
    }
    try {
        await updateSettings({ language: language });
    } catch (error) {
        showSettingsMessage(errorText(error), "error");
    }
}

// pywebview announces itself with this event once its API is ready.
window.addEventListener("pywebviewready", () => {
    pywebviewReady = true;
    updateBrowseButton();
});

updateBrowseButton();
document.getElementById("browse-button")
    .addEventListener("click", browseFolder);
// Cancel goes back to the active project's settings.
document.getElementById("cancel-new-project")
    .addEventListener("click", () => {
        showSettingsMessage("", "");
        loadSettings();
    });
document.getElementById("remove-project-button")
    .addEventListener("click", openRemoveDialog);
document.getElementById("remove-project-confirm")
    .addEventListener("click", confirmRemoveProject);
document.getElementById("remove-project-cancel")
    .addEventListener("click", () => {
        document.getElementById("remove-project-dialog").close();
    });
Object.keys(PROVIDER_ROWS).forEach((role) => {
    rowField(role, "provider").addEventListener("change", () => {
        fillModels(role, "");
        updateKeyPlaceholder(role);
        updateAIStatus();
    });
    rowField(role, "model").addEventListener("change", updateAIStatus);
});
// A different folder needs its own warning.
document.getElementById("target-directory")
    .addEventListener("input", resetFolderWarning);
document.getElementById("target-directory")
    .addEventListener("change", adviseOnFolder);
document.getElementById("settings-form")
    .addEventListener("submit", saveSettings);
document.getElementById("suggest-sheet")
    .addEventListener("click", suggestProjectSheet);
document.getElementById("language-select")
    .addEventListener("change", changeLanguage);
document.getElementById("naming-options")
    .addEventListener("change", updateNamingPreview);
document.querySelectorAll('input[name="naming-separator"]')
    .forEach((radio) => {
        radio.addEventListener("change", () => {
            customSeparator = radio.value;
            updateNamingPreview();
        });
    });

// startApp() in app.js calls fillProviders() and loadSettings() after the language loads.
