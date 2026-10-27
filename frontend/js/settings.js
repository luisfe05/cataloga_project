/**
 * settings.js
 *
 * Settings view (Screen 2). It has two modes:
 * - "edit": the active project. The name, file names, and AI provider
 *   can change; the folder cannot, because the catalog is inside it.
 * - "new": a new project, with its name, folder, file names, and AI
 *   provider. Used for the first project and from the header's
 *   "New project" option.
 *
 * When Save (or Create project) is clicked:
 * 1. The project is saved (PUT /settings) or created (POST /projects).
 * 2. The AI connection is tested (POST /settings/ai-provider/test).
 * 3. Only if the test passes, the provider is saved
 *    (PUT /settings/ai-provider), which writes the key to the keyring.
 * This way a wrong API key is never saved. The key is kept per
 * provider, so a new project can use it without typing it again.
 *
 * Every new project starts with Ollama Cloud. The provider fields are
 * inside "Advanced settings", which is closed unless the chosen
 * provider still needs a key or the project uses another provider.
 * The backend only says which providers have a key, never the key.
 *
 * If the chosen folder already has the user's own files, the backend
 * answers step 1 with a "folder_not_empty" warning. The button then
 * changes to "Save anyway", and the next click confirms the folder.
 *
 * Remove project (only for the active project) asks first in a dialog
 * inside the app, then calls DELETE /projects. It only takes the
 * project out of the list: the folder and its catalog stay.
 *
 * The Language dropdown works on its own: a new choice is applied and
 * saved right away (PUT /settings with only the language).
 *
 * The File names section is saved with the Save button. Its template is
 * checked here while the user types, with the same rules as
 * backend/pipeline/naming.py, and the backend checks it again.
 */

// Providers and models offered in the form. The key is the name the
// backend uses. The first model of each provider is the default, chosen
// for a free tier or the lowest cost.
const AI_PROVIDERS = {
    ollama: {
        label: "Ollama Cloud",
        models: ["gemma4:31b", "nemotron-3-nano:30b"],
    },
    gemini: {
        label: "Google Gemini",
        models: ["gemini-2.5-flash", "gemini-2.5-flash-lite"],
    },
    groq: {
        label: "Groq",
        models: ["llama-3.1-8b-instant", "llama-3.3-70b-versatile",
            "openai/gpt-oss-20b"],
    },
    claude: {
        label: "Anthropic Claude",
        models: ["claude-haiku-5-5", "claude-sonnet-5-5"],
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

// The three naming methods, as the templates the backend saves.
const NAMING_METHODS = {
    m1: "{date}_{topic}",
    m2: "{source}_{date}_{topic}",
    m3: "{number}_{topic}",
};

// Parts a template can use, and characters a file name cannot have.
const NAMING_TOKENS = ["date", "source", "topic", "number", "original"];
const FORBIDDEN_CHARACTERS = '/\\:*?"<>|';

// Example values for the live preview (from the approved examples).
const PREVIEW_PARTS = {
    date: "2026-07-15",
    source: "el-nuevo-dia",
    topic: "oceanman-malta",
    number: "0001",
    original: "scan-0042",
};

// True after the user has seen the folder warning and may confirm it.
let folderWarningShown = false;

// "edit" for the active project, "new" while creating a project.
let projectMode = "edit";

// False before the first project exists (then there is nothing to go
// back to, so Cancel is hidden).
let hasProjects = false;

// True once pywebview's folder picker can be used.
let pywebviewReady = Boolean(window.pywebview && window.pywebview.api);

// Saved name of the active project, for the Remove project dialog.
let savedProjectName = "";

// Names of the providers that have an API key ready, from GET /settings.
let providersWithKey = [];

/**
 * Show "Save" or "Save anyway" on the button, in the current language.
 */
function updateSaveButton() {
    let text = t("settings.save");
    if (folderWarningShown) {
        text = t("settings.save_anyway");
    } else if (projectMode === "new") {
        text = t("project.create");
    }
    document.getElementById("save-button").textContent = text;
}

/**
 * Show Browse only in the desktop window and only for a new project.
 */
function updateBrowseButton() {
    document.getElementById("browse-button").classList.toggle(
        "hidden", !(pywebviewReady && projectMode === "new"));
}

/**
 * Switch the form between the active project and a new project.
 * @param {string} mode - "edit" or "new".
 */
function setProjectMode(mode) {
    projectMode = mode;
    const isNew = mode === "new";
    document.getElementById("project-form-title").textContent =
        t(isNew ? "project.new_title" : "project.edit_title");
    // readOnly keeps the folder visible but not editable.
    document.getElementById("target-directory").readOnly = !isNew;
    document.getElementById("folder-locked")
        .classList.toggle("hidden", isNew);
    document.getElementById("cancel-new-project")
        .classList.toggle("hidden", !(isNew && hasProjects));
    document.getElementById("remove-project-section")
        .classList.toggle("hidden", isNew);
    updateBrowseButton();
    resetFolderWarning();
}

/**
 * Empty the form for a new project. The AI provider goes back to
 * Ollama Cloud, like the backend does for every new project.
 */
function startNewProject() {
    setProjectMode("new");
    document.getElementById("research-name").value = "";
    document.getElementById("target-directory").value = "";
    document.getElementById("api-key").value = "";
    showSavedTemplate(NAMING_METHODS.m1);
    showProvider("ollama", "");
    showSettingsMessage("", "");
}

/**
 * True when the provider chosen in the form has an API key ready.
 * @returns {boolean}
 */
function chosenProviderHasKey() {
    const provider = document.getElementById("ai-provider").value;
    return providersWithKey.includes(provider);
}

/**
 * Show the API key field's hint, in the current language.
 */
function updateKeyPlaceholder() {
    document.getElementById("api-key").placeholder = chosenProviderHasKey()
        ? t("settings.api_key_saved") : t("settings.api_key_placeholder");
}

/**
 * Say which provider and model are in use, or that a key is missing.
 */
function updateAIStatus() {
    const provider = document.getElementById("ai-provider").value;
    const model = document.getElementById("ai-model").value;
    const vars = { provider: AI_PROVIDERS[provider].label, model: model };
    document.getElementById("ai-status").textContent = chosenProviderHasKey()
        ? t("settings.ai_using", vars) : t("settings.ai_needs_key", vars);
}

/**
 * Put a provider and model in the form and decide if Advanced settings
 * starts open: only when the provider needs a key or is not Ollama.
 * @param {string} provider - A key of AI_PROVIDERS.
 * @param {string} model - Model to select, if it is in the list.
 */
function showProvider(provider, model) {
    document.getElementById("ai-provider").value = provider;
    fillModels(model);
    document.getElementById("ai-advanced").open =
        provider !== "ollama" || !chosenProviderHasKey();
    updateKeyPlaceholder();
    updateAIStatus();
}

/**
 * Put the Save button back to normal and forget any folder warning.
 */
function resetFolderWarning() {
    folderWarningShown = false;
    updateSaveButton();
}

/**
 * Check a naming template. Same rules as validate_template() in
 * backend/pipeline/naming.py.
 * @param {string} template
 * @returns {Object|null} null if valid, or {reason, token}.
 */
function validateTemplate(template) {
    if (!template.trim()) {
        return { reason: "empty", token: "" };
    }
    // Every {word} in the template.
    const found = [...template.matchAll(/\{([^{}]*)\}/g)]
        .map((match) => match[1]);
    const unknown = found.find((name) => !NAMING_TOKENS.includes(name));
    if (unknown !== undefined) {
        return { reason: "unknown", token: `{${unknown}}` };
    }
    if (found.length === 0) {
        return { reason: "no_token", token: "" };
    }
    // The braces are removed first, since they are allowed.
    const text = template.replace(/\{[^{}]*\}/g, "");
    if ([...text].some((char) => FORBIDDEN_CHARACTERS.includes(char))) {
        return { reason: "chars", token: "" };
    }
    return null;
}

/**
 * Fill a template with the example values, like render_template() in
 * backend/pipeline/naming.py.
 * @param {string} template
 * @returns {string} For example "2026-07-15_oceanman-malta.pdf".
 */
function previewFilename(template) {
    let name = template;
    NAMING_TOKENS.forEach((token) => {
        name = name.split(`{${token}}`).join(PREVIEW_PARTS[token]);
    });
    name = name.replace(/_{2,}/g, "_").replace(/-{2,}/g, "-")
        .replace(/^[_\-. ]+|[_\-. ]+$/g, "");
    return (name || PREVIEW_PARTS.number) + ".pdf";
}

/**
 * Return the template for the method picked in the File names section.
 * @returns {string}
 */
function chosenTemplate() {
    const picked = document.querySelector(
        'input[name="naming-method"]:checked');
    const method = picked ? picked.value : "m1";
    if (method === "custom") {
        return document.getElementById("naming-template").value;
    }
    return NAMING_METHODS[method];
}

/**
 * Show the template box for Custom, check the template, and update the
 * preview. Called on every change and key press in the section.
 * @returns {boolean} True if the template is valid.
 */
function updateNamingPreview() {
    const picked = document.querySelector(
        'input[name="naming-method"]:checked');
    const isCustom = Boolean(picked) && picked.value === "custom";
    document.getElementById("naming-custom")
        .classList.toggle("hidden", !isCustom);

    const template = chosenTemplate();
    const problem = validateTemplate(template);
    document.getElementById("naming-error").textContent = problem
        ? t(`naming.err_${problem.reason}`, { token: problem.token }) : "";
    document.getElementById("naming-preview").textContent = problem
        ? "" : previewFilename(template);
    return !problem;
}

/**
 * Select the method that matches a saved template. A template that is
 * not one of the three methods is shown as Custom.
 * @param {string} template
 */
function showSavedTemplate(template) {
    let method = "custom";
    Object.keys(NAMING_METHODS).forEach((key) => {
        if (NAMING_METHODS[key] === template) {
            method = key;
        }
    });
    document.querySelector(
        `input[name="naming-method"][value="${method}"]`).checked = true;
    document.getElementById("naming-template").value =
        method === "custom" ? template : "";
    updateNamingPreview();
}

/**
 * Show a message under the Save button.
 * @param {string} text
 * @param {string} kind - "error", "success", or "" for neutral.
 */
function showSettingsMessage(text, kind) {
    const message = document.getElementById("settings-message");
    message.textContent = text;
    message.className = "form-message " + kind;
}

/**
 * Fill the Model dropdown with the models of the chosen provider.
 * @param {string} chosenModel - Model to select, if it is in the list.
 */
function fillModels(chosenModel) {
    const provider = document.getElementById("ai-provider").value;
    const select = document.getElementById("ai-model");
    select.innerHTML = "";
    AI_PROVIDERS[provider].models.forEach((model) => {
        const option = document.createElement("option");
        option.value = model;
        option.textContent = model;
        select.appendChild(option);
    });
    if (AI_PROVIDERS[provider].models.includes(chosenModel)) {
        select.value = chosenModel;
    }
}

/**
 * Fill the AI Provider dropdown once, when the page loads.
 */
function fillProviders() {
    const select = document.getElementById("ai-provider");
    Object.keys(AI_PROVIDERS).forEach((name) => {
        const option = document.createElement("option");
        option.value = name;
        option.textContent = AI_PROVIDERS[name].label;
        select.appendChild(option);
    });
}

/**
 * Load the saved settings into the form. The API key is never sent by
 * the backend, so the key field only shows a hint when one is saved.
 */
async function loadSettings() {
    try {
        const settings = await getSettings();
        hasProjects = settings.project_status !== "none";
        document.getElementById("research-name").value =
            settings.research_name;
        savedProjectName = settings.research_name;
        document.getElementById("target-directory").value =
            settings.target_directory;

        document.getElementById("language-select").value =
            settings.language;
        showSavedTemplate(settings.naming_template);

        document.getElementById("api-key").value = "";
        providersWithKey = settings.providers_with_key;
        // A project with no provider saved yet gets Ollama Cloud.
        const provider = settings.active_provider in AI_PROVIDERS
            ? settings.active_provider : "ollama";
        showProvider(provider, settings.active_model);

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

/**
 * Save the form, following the three steps described at the top.
 * @param {Event} event
 */
async function saveSettings(event) {
    // Stop the form from reloading the page.
    event.preventDefault();

    const saveButton = document.getElementById("save-button");
    // A wrong template is shown under the File names section, and
    // nothing is sent.
    if (!updateNamingPreview()) {
        showSettingsMessage(
            document.getElementById("naming-error").textContent, "error");
        return;
    }
    const providerData = {
        provider_name: document.getElementById("ai-provider").value,
        model: document.getElementById("ai-model").value,
        api_key: document.getElementById("api-key").value.trim(),
    };

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
                confirm_folder: folderWarningShown,
            });
            projectCreated = true;
            doneMessage = t(created.opened_existing
                ? "project.opened_existing" : "project.created");
        } else {
            await updateSettings({
                research_name:
                    document.getElementById("research-name").value,
                naming_template: chosenTemplate(),
            });
        }
        resetFolderWarning();
        await testAIProvider(providerData);
        await updateAIProvider(providerData);
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

/**
 * Ask in the app's own dialog before removing the active project.
 */
function openRemoveDialog() {
    document.getElementById("remove-project-title").textContent =
        t("project.remove_title", { name: savedProjectName });
    document.getElementById("remove-project-error").textContent = "";
    document.getElementById("remove-project-confirm").disabled = false;
    document.getElementById("remove-project-dialog").showModal();
}

/**
 * Take the active project out of the list (DELETE /projects). The
 * backend makes the most recently opened project active. With none
 * left, loadSettings() shows the New project form.
 */
async function confirmRemoveProject() {
    const dialog = document.getElementById("remove-project-dialog");
    const confirmButton = document.getElementById("remove-project-confirm");
    confirmButton.disabled = true;
    try {
        await removeProject(
            document.getElementById("target-directory").value);
    } catch (error) {
        // Keep the dialog open and say what went wrong.
        document.getElementById("remove-project-error").textContent =
            errorText(error);
        confirmButton.disabled = false;
        return;
    }
    dialog.close();
    await refreshAfterProjectChange();
    showSettingsMessage(t("project.removed"), "success");
}

/**
 * Open the system folder picker. It only exists inside the desktop
 * window (pywebview), so in a normal browser the button is hidden.
 */
async function browseFolder() {
    const folder = await window.pywebview.api.choose_folder();
    if (folder) {
        document.getElementById("target-directory").value = folder;
        resetFolderWarning();
    }
}

/**
 * Apply and save the language picked in the dropdown.
 * Fixed text changes right away; the views are reloaded so the text
 * built by JavaScript (tables, messages) changes too.
 */
async function changeLanguage() {
    const language = document.getElementById("language-select").value;
    setLanguage(language);
    updateSaveButton();
    updateKeyPlaceholder();
    updateAIStatus();
    updateNamingPreview();
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
document.getElementById("ai-provider")
    .addEventListener("change", () => {
        fillModels("");
        updateKeyPlaceholder();
        updateAIStatus();
    });
document.getElementById("ai-model")
    .addEventListener("change", updateAIStatus);
// A different folder needs its own warning, so start over when it changes.
document.getElementById("target-directory")
    .addEventListener("input", resetFolderWarning);
document.getElementById("settings-form")
    .addEventListener("submit", saveSettings);
document.getElementById("language-select")
    .addEventListener("change", changeLanguage);
// The preview follows every method change and every key press.
document.getElementById("naming-options")
    .addEventListener("change", updateNamingPreview);
document.getElementById("naming-template")
    .addEventListener("input", updateNamingPreview);

// fillProviders() and loadSettings() are first called by startApp() in
// app.js, after the saved language is known.
