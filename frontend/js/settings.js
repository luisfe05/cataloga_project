/**
 * settings.js
 *
 * Settings view (Screen 2).
 * Lets the user set the research name, the project folder, and the AI
 * provider, model, and API key.
 *
 * When Save is clicked:
 * 1. The research name and folder are saved (PUT /settings).
 * 2. The AI connection is tested (POST /settings/ai-provider/test).
 * 3. Only if the test passes, the provider is saved
 *    (PUT /settings/ai-provider), which writes the key to the keyring.
 * This way a wrong API key is never saved.
 *
 * If the chosen folder already has the user's own files, the backend
 * answers step 1 with a "folder_not_empty" warning. The button then
 * changes to "Save anyway", and the next click confirms the folder.
 *
 * The Language dropdown works on its own: a new choice is applied and
 * saved right away (PUT /settings with only the language).
 */

// Providers and models offered in the form. The key is the name the
// backend uses. The first model of each provider is the default, chosen
// for a free tier or the lowest cost.
const AI_PROVIDERS = {
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

// True after the user has seen the folder warning and may confirm it.
let folderWarningShown = false;

// True when an API key is already saved, to pick the key field's hint.
let hasSavedKey = false;

/**
 * Show "Save" or "Save anyway" on the button, in the current language.
 */
function updateSaveButton() {
    document.getElementById("save-button").textContent = folderWarningShown
        ? t("settings.save_anyway") : t("settings.save");
}

/**
 * Show the API key field's hint, in the current language.
 */
function updateKeyPlaceholder() {
    document.getElementById("api-key").placeholder = hasSavedKey
        ? t("settings.api_key_saved") : t("settings.api_key_placeholder");
}

/**
 * Put the Save button back to normal and forget any folder warning.
 */
function resetFolderWarning() {
    folderWarningShown = false;
    updateSaveButton();
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
        document.getElementById("research-name").value =
            settings.research_name;
        document.getElementById("target-directory").value =
            settings.target_directory;

        if (settings.active_provider in AI_PROVIDERS) {
            document.getElementById("ai-provider").value =
                settings.active_provider;
        }
        fillModels(settings.active_model);
        document.getElementById("language-select").value =
            settings.language;

        document.getElementById("api-key").value = "";
        hasSavedKey = Boolean(settings.active_provider);
        updateKeyPlaceholder();
        updateSaveButton();
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
    const providerData = {
        provider_name: document.getElementById("ai-provider").value,
        model: document.getElementById("ai-model").value,
        api_key: document.getElementById("api-key").value.trim(),
    };

    saveButton.disabled = true;
    showSettingsMessage(t("settings.saving"), "");
    try {
        await updateSettings({
            research_name: document.getElementById("research-name").value,
            target_directory:
                document.getElementById("target-directory").value,
            confirm_folder: folderWarningShown,
        });
        resetFolderWarning();
        await testAIProvider(providerData);
        await updateAIProvider(providerData);
        showSettingsMessage(t("settings.saved"), "success");
        await loadSettings();
        // Refresh the catalog so the project name and folder update.
        loadCatalog();
    } catch (error) {
        if (error.code === "folder_not_empty") {
            folderWarningShown = true;
            updateSaveButton();
        }
        showSettingsMessage(errorText(error), "error");
    } finally {
        saveButton.disabled = false;
    }
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
    showSettingsMessage("", "");
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
    document.getElementById("browse-button").classList.remove("hidden");
});

// Hide Browse until pywebview is ready, unless it already is.
if (!(window.pywebview && window.pywebview.api)) {
    document.getElementById("browse-button").classList.add("hidden");
}
document.getElementById("browse-button")
    .addEventListener("click", browseFolder);
document.getElementById("ai-provider")
    .addEventListener("change", () => fillModels(""));
// A different folder needs its own warning, so start over when it changes.
document.getElementById("target-directory")
    .addEventListener("input", resetFolderWarning);
document.getElementById("settings-form")
    .addEventListener("submit", saveSettings);
document.getElementById("language-select")
    .addEventListener("change", changeLanguage);

// fillProviders() and loadSettings() are first called by startApp() in
// app.js, after the saved language is known.
