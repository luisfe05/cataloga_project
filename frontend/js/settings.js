/** settings.js: Settings. Project: this project's cards. General: fields that save on their own. */

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
    keep: "keep",
    m1: "{date}_{topic}",
    m2: "{source}_{date}_{topic}",
    m3: "{number}_{topic}",
    m4: "{topic}_{source}_{date}",
    m5: "{event}_{n}",
};

// Parts a template can use, and characters a file name cannot have.
const NAMING_TOKENS = ["date", "source", "topic", "number", "original",
    "topic_number", "event", "n"];
const FORBIDDEN_CHARACTERS = '/\\:*?"<>|';

// Custom name parts, in the order of the buttons. A number is added only when a name repeats.
const NAMING_BLOCKS = ["topic", "source", "date", "original"];
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

// The four sections of the Project tab, in order.
const PROJECT_CARDS = ["project-section", "sheet-section", "naming-section",
    "folders-section"];

// The dotted place each card keeps in a new project until a folder is chosen.
const CARD_PLACEHOLDERS = {
    "sheet-section": "sheet-placeholder",
    "naming-section": "naming-placeholder",
    "folders-section": "folders-placeholder",
};

// Write it for me types its answer at this pace, in milliseconds per character.
const TYPE_MS = 20;

// How long "Saved" stays next to a General field.
const SAVED_NOTE_MS = 2000;

// Same as the card-leaving transition in main.css, plus a little.
const LEAVE_MS = 260;

// Generic values for the live preview, not real data.
const PREVIEW_PARTS = {
    date: "date",
    source: "source-name",
    topic: "topic-name",
    number: "0001",
    original: "original-name",
    topic_number: "001",
    event: "Event-Name_1998",
    n: "1",
};

function readNamingStyle() {
    const picked = document.querySelector('input[name="naming-style"]:checked');
    return picked ? picked.value : "lower";
}

/** "topic-name" as the chosen style writes it: "Topic-Name" for Title-Case. */
function styledPart(text) {
    if (readNamingStyle() !== "title") {
        return text;
    }
    return text.split("-")
        .map((word) => word.charAt(0).toUpperCase() + word.slice(1)).join("-");
}

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

// New project: the user typed a name or picked a naming method, so neither is filled for them.
let nameTouched = false;
let namingTouched = false;

// Write it for me: running now, and the folder it already ran for once on its own.
let sheetWriting = false;
let sheetWrittenFor = "";

// The chosen folder's numbers, so a new language can write them again.
let folderFacts = null;

// What General shows as saved, so a failed save puts it back.
let savedRows = {};
let savedServerUrl = "";

// ---- Cards: drop, fold, hide ----

function settingsVisible() {
    return ["view-settings", "view-new"].some((id) =>
        !document.getElementById(id).classList.contains("hidden"));
}

/** The Project form lives in New Project or in Settings > Project; it moves, it is not copied. */
function placeProjectPanel(isNew) {
    const panel = document.getElementById("settings-project");
    if (isNew) {
        document.getElementById("new-project-slot").appendChild(panel);
        panel.classList.remove("hidden");
    } else {
        // Back after the Project / General tabs.
        document.getElementById("settings-general").before(panel);
    }
    // With no project yet, Settings shows only General.
    document.getElementById("settings-tab-project").classList
        .toggle("hidden", !hasProjects);
}

// The full drop plays the first time Settings opens in this app session,
// and for every new project. Kept in memory only: a new session starts over.
let fullDropDone = false;
let fullDropNext = false;

/** The cards drop into place (card-drop), or just come in quickly (card-quick). */
function dropCards(cards, quick = false) {
    if (!settingsVisible() || prefersReducedMotion()) {
        return;
    }
    const name = quick ? "card-quick" : "card-drop";
    cards.forEach((card, index) => {
        card.classList.remove("card-drop", "card-quick");
        // Quick entrances all come at once; the full drop goes one by one.
        card.style.setProperty("--drop-index", quick ? 0 : index);
        // Reading the size restarts the animation on a card that just played it.
        card.getBoundingClientRect();
        card.classList.add(name);
    });
}

/** The visible cards and dotted places of the open tab, top to bottom. */
function openTabCards() {
    const view = document.getElementById("view-new").classList
        .contains("hidden") ? "#view-settings" : "#view-new";
    const panel = document.querySelector(
        `${view} .settings-panel:not(.hidden)`);
    if (!panel) {
        return [];
    }
    return [...panel.querySelectorAll(
        ".settings-card, .card-placeholder, .card-wait-line, .card-pair")]
        .filter((card) => !card.classList.contains("hidden")
            && !card.querySelector(".settings-card"));
}

/** The cards of the open tab come in: the full drop once, then quickly. */
function dropSettingsCards() {
    const quick = fullDropDone && !fullDropNext;
    fullDropDone = true;
    fullDropNext = false;
    dropCards(openTabCards(), quick);
}

/** Show a hidden card; only that card drops. */
function showCard(card) {
    clearTimeout(card.leaveTimer);
    card.classList.remove("card-leaving");
    card.style.height = "";
    if (!card.classList.contains("hidden")) {
        return;
    }
    card.classList.remove("hidden");
    dropCards([card]);
}

/** Hide a card: it fades out, and the cards under it move up. */
function hideCard(card) {
    if (card.classList.contains("hidden")
            || card.classList.contains("card-leaving")) {
        return;
    }
    if (!settingsVisible() || prefersReducedMotion()) {
        card.classList.add("hidden");
        return;
    }
    // A fixed height first, so the change to 0 can be animated.
    card.style.height = `${card.offsetHeight}px`;
    card.getBoundingClientRect();
    card.classList.add("card-leaving");
    card.leaveTimer = setTimeout(() => {
        card.classList.add("hidden");
        card.classList.remove("card-leaving");
        card.style.height = "";
        // The progress counts only the cards that stay.
        refreshCards();
    }, LEAVE_MS);
}

function setCardShown(card, shown) {
    if (shown) {
        showCard(card);
    } else {
        hideCard(card);
    }
}

/** Fold a card into its one-line summary, or open it again. */
function setCardDone(card, done) {
    if (card.classList.contains("is-done") === done) {
        return;
    }
    // While it moves, nothing sticks out of the card.
    card.classList.add("is-moving");
    card.classList.toggle("is-done", done);
    clearTimeout(card.foldTimer);
    card.foldTimer = setTimeout(() => {
        card.classList.remove("is-moving");
    }, prefersReducedMotion() ? 0 : LEAVE_MS);
}

/** Which cards show in the Project tab: a new project waits for its folder. */
function updateCardVisibility() {
    const isNew = projectMode === "new";
    const waiting = isNew
        && !document.getElementById("target-directory").value.trim();
    const catalogOnly = document.getElementById("catalog-only").checked;
    // Folder Names is part of every project: making the folders is the
    // archivist's work, whatever the mode. Only a new project waits.
    const wanted = {
        "sheet-section": true,
        "naming-section": true,
        "folders-section": true,
    };
    const revealed = [];
    // One line above the dotted places says when they appear.
    document.getElementById("cards-wait-line").classList
        .toggle("hidden", !waiting);
    // When to read it, and the two boxes: after the folder is chosen. An
    // existing project shows it only to say it is Catalog only.
    setCardShown(document.getElementById("read-section"),
        isNew ? !waiting : catalogOnly);
    Object.keys(CARD_PLACEHOLDERS).forEach((id) => {
        const card = document.getElementById(id);
        document.getElementById(CARD_PLACEHOLDERS[id]).classList
            .toggle("hidden", !(waiting && wanted[id]));
        if (wanted[id] && !waiting) {
            if (card.classList.contains("hidden")) {
                revealed.push(card);
            }
            showCard(card);
        } else if (waiting) {
            // Its dotted place takes its spot at once.
            card.classList.add("hidden");
        } else {
            hideCard(card);
        }
    });
    // About first, then File names, then Folder names.
    dropCards(revealed);
    const treeMode = isNew || ["tree", "place"].includes(projectFolderMode);
    setCardShown(document.getElementById("categories-section"), !treeMode);
    setCardShown(document.getElementById("remove-project-section"), !isNew);
    refreshCards();
}

/** Is a section complete? File names and Folder names have a default. */
function cardReady(id) {
    if (id === "project-section") {
        return Boolean(document.getElementById("target-directory").value
            .trim() && document.getElementById("research-name").value.trim());
    }
    if (id === "sheet-section") {
        return Boolean(document.getElementById("project-sheet").value.trim())
            && !sheetWriting;
    }
    if (id === "naming-section") {
        const picked = document.querySelector(
            'input[name="naming-method"]:checked');
        const template = chosenTemplate();
        return Boolean(picked) && Boolean(template.trim())
            && validateTemplate(template) === null;
    }
    // Folder names: a proposal, or left empty on purpose.
    return !foldersBusy;
}

/** The method's name and its preview, as the folded row shows it. */
function namingSummary() {
    const picked = document.querySelector(
        'input[name="naming-method"]:checked');
    if (!picked) {
        return "";
    }
    const label = picked.closest(".naming-option")
        .querySelector("span").textContent.trim();
    const preview = document.getElementById("naming-preview").textContent;
    return preview ? `${label} · ${preview}` : label;
}

/** "Harbor Swimmers · /Volumes/Demo/Harbor · Later" for the folded New Project row. */
function projectSummary() {
    const parts = [document.getElementById("research-name").value.trim(),
        document.getElementById("target-directory").value.trim()];
    if (projectMode === "new") {
        if (document.getElementById("catalog-only").checked) {
            parts.push(t("project.catalog_only"));
        } else if (document.getElementById("use-drop-zone").checked) {
            parts.push(t("project.mode_tree"));
        }
        if (archiveChoice()) {
            parts.push(t(`project.archive_${archiveChoice()}`));
        }
    }
    return parts.filter(Boolean).join(" · ");
}

function foldersSummary() {
    const count = readFolderTree().length;
    if (!count) {
        return t("folders.none_yet");
    }
    return count === 1 ? t("folders.count_one")
        : t("folders.count", { n: count });
}

/** Progress, summaries, Done links and the Create button, after any change. */
function refreshCards() {
    // A card still in its dotted place is not ready yet.
    const ready = PROJECT_CARDS.filter((id) => cardReady(id)
        && !document.getElementById(id).classList.contains("hidden"));
    PROJECT_CARDS.forEach((id) => {
        const card = document.getElementById(id);
        card.querySelector(".card-confirm").classList
            .toggle("hidden", !ready.includes(id));
        // A card that is no longer complete opens again; in a new project
        // the optional cards stay folded until the user opens them.
        const optional = projectMode === "new" && id !== "project-section";
        if (!ready.includes(id) && card.classList.contains("is-done")
                && !optional) {
            setCardDone(card, false);
        }
    });
    document.getElementById("project-summary").textContent =
        projectSummary();
    const sheet = document.getElementById("project-sheet").value.trim();
    document.getElementById("sheet-summary").textContent =
        sheet.split("\n")[0];
    document.getElementById("naming-summary").textContent = namingSummary();
    document.getElementById("folders-summary").textContent =
        foldersSummary();

    const isNew = projectMode === "new";
    // A project needs a folder and a name; the rest has defaults.
    const blocked = isNew && !ready.includes("project-section");
    document.getElementById("save-button").disabled = blocked;
    // An off button says what is missing.
    let missing = "";
    if (blocked) {
        missing = document.getElementById("target-directory").value.trim()
            ? t("settings.need_name") : t("settings.need_folder");
    }
    document.getElementById("save-hint").textContent = missing;
}

/** Moving on to a later card folds the complete cards above it. */
function moveOnFrom(target) {
    // A new project's cards open and fold only when the user says so.
    if (projectMode === "new") {
        return;
    }
    const card = target.closest(".settings-card");
    const index = card ? PROJECT_CARDS.indexOf(card.id) : -1;
    if (index < 1) {
        return;
    }
    PROJECT_CARDS.slice(0, index).forEach((id) => {
        const above = document.getElementById(id);
        if (!above.classList.contains("hidden") && cardReady(id)) {
            setCardDone(above, true);
        }
    });
}

// ---- Project tab ----

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
    placeProjectPanel(isNew);
    const title = t(isNew ? "project.new_title" : "project.edit_title");
    document.getElementById("project-form-title").textContent = title;
    document.getElementById("project-row-title").textContent = title;
    document.getElementById("target-directory").readOnly = !isNew;
    // An existing project says, under its folder, why it can't change.
    document.getElementById("folder-locked").classList.toggle("hidden", isNew);
    // Cancel always shows: in New Project it goes back to Home.
    document.getElementById("cancel-new-project").classList.remove("hidden");
    // Catalog only: the box is a choice for new projects, a fact after.
    const box = document.getElementById("catalog-only");
    box.disabled = !isNew;
    if (!isNew) {
        box.checked = projectFolderMode === "catalog";
    }
    applyCatalogOnly();
    updateBrowseButton();
    resetFolderWarning();
    hideArchiveSwitch();
    // An existing project shows every section folded. A new one shows its
    // folder and name open, and the optional details folded.
    PROJECT_CARDS.forEach((id) => {
        const card = document.getElementById(id);
        card.classList.remove("is-moving");
        card.classList.toggle("is-done", !isNew || id !== "project-section");
    });
    updateCardVisibility();
}

/** "now" or "later" while the switch shows, else "" (an existing project, or a Drop Zone). */
function archiveChoice() {
    if (document.getElementById("archive-switch").classList
        .contains("hidden")) {
        return "";
    }
    return document.querySelector('input[name="archive-when"]:checked').value;
}

/** Later sends nothing to the AI: its two AI buttons give way to a short note.

Everything else works the same with Now and Later. Going back to Now, the
buttons come back, each with its drop.
 */
function applyArchiveChoice() {
    const later = archiveChoice() === "later";
    const comeBack = [];
    [["sheet-buttons", "sheet-later"], ["folder-buttons", "folders-later"]]
        .forEach(([buttonsId, noteId]) => {
            const buttons = document.getElementById(buttonsId);
            if (!later && buttons.classList.contains("later-hidden")) {
                comeBack.push(...buttons.children);
            }
            buttons.classList.toggle("later-hidden", later);
            document.getElementById(noteId).classList.toggle("hidden", !later);
        });
    dropCards(comeBack);
    refreshCards();
}

/** Archive Now: read the folder and propose its tree, unless the user already has one. */
function proposeFromFolder() {
    if (archiveChoice() === "now" && !readFolderTree().length) {
        suggestProjectFolders();
    }
}

function hideArchiveSwitch() {
    document.getElementById("folder-facts").classList.add("hidden");
    document.getElementById("archive-switch").classList.add("hidden");
    applyArchiveChoice();
}

/** "tree" with Use a Drop Zone ticked; otherwise the folder is read in place. */
function chosenFolderMode() {
    return document.getElementById("use-drop-zone").checked ? "tree" : "place";
}

/** Only a new project read where it is (in place or Catalog only) can wait. */
function readsNewFolder() {
    return projectMode === "new" && (chosenFolderMode() === "place"
        || document.getElementById("catalog-only").checked);
}

/** Catalog only hides the folders and fixes the names: nothing moves. */
function applyCatalogOnly() {
    const on = document.getElementById("catalog-only").checked;
    const isNew = projectMode === "new";
    document.getElementById("drop-zone-row")
        .classList.toggle("hidden", !isNew);
    document.querySelectorAll("#naming-options input").forEach((radio) => {
        radio.disabled = on && radio.value !== "keep";
    });
    if (on) {
        document.querySelector('input[name="naming-method"][value="keep"]')
            .checked = true;
        updateNamingPreview();
    }
    updateFolderNotes();
    updateCardVisibility();
}

/** Write it for me's button: "Write it again" once it has written. */
function setSheetButton(again) {
    const button = document.getElementById("suggest-sheet");
    button.dataset.i18n = again ? "sheet.again" : "sheet.suggest";
    button.textContent = t(button.dataset.i18n);
}

/** Choose folder (Home, Dashboard, …): the picker, then New Project with that folder. */
async function chooseFolderToStart() {
    let folder = "";
    if (pywebviewReady) {
        folder = await window.pywebview.api.choose_folder();
        if (!folder) {
            // The picker was closed: stay where we are.
            return;
        }
    }
    openNewProject();
    if (folder) {
        document.getElementById("target-directory").value = folder;
        await folderChosen();
    }
}

/** New Project: an empty form, on its own screen. */
function openNewProject() {
    startNewProject();
    showView("new");
}

/** Empty the form for a new project, which starts with Ollama Cloud. */
function startNewProject() {
    // A new project always gets the full drop.
    fullDropNext = true;
    showSettingsTab("project", false);
    showFolderSection({}, true);
    document.getElementById("research-name").value = "";
    document.getElementById("target-directory").value = "";
    document.getElementById("use-drop-zone").checked = false;
    document.getElementById("folder-advice").classList.add("hidden");
    document.getElementById("project-sheet").value = "";
    showSheetMessage("", "");
    setSheetButton(false);
    nameTouched = false;
    namingTouched = false;
    sheetWrittenFor = "";
    showNamingSuggestion(null);
    document.getElementById("catalog-only").checked = false;
    // Archive Later by default: nothing is read or sent until the user says so.
    document.querySelector('input[name="archive-when"][value="later"]')
        .checked = true;
    // New projects start with method 4, lowercase, no accents, and
    // month-first photo stamps.
    showSavedTemplate(NAMING_METHODS.m4);
    document.querySelector('input[name="naming-style"][value="lower"]')
        .checked = true;
    document.querySelector('input[name="stamp-order"][value="month"]')
        .checked = true;
    showCategories("", []);
    showSettingsMessage("", "");
    setProjectMode("new");
}

function resetFolderWarning() {
    folderWarningShown = false;
    updateSaveButton();
}

/** Same rules as validate_template() in naming.py; the backend checks again. */
function validateTemplate(template) {
    if (template === NAMING_METHODS.keep) {
        return null;
    }
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
    if (template === NAMING_METHODS.keep) {
        return t("naming.keep_example");
    }
    let name = template;
    NAMING_TOKENS.forEach((token) => {
        const part = ["topic", "source", "original"].includes(token)
            ? styledPart(PREVIEW_PARTS[token]) : PREVIEW_PARTS[token];
        name = name.split(`{${token}}`).join(part);
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

function readStampOrder() {
    const picked = document.querySelector('input[name="stamp-order"]:checked');
    return picked ? picked.value : "month";
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

/** The naming method of a template, like "m4", or "" for Custom. */
function methodOf(template) {
    return Object.keys(NAMING_METHODS)
        .find((key) => NAMING_METHODS[key] === template) || "";
}

/** Mark the method the folder's names already follow; pick it unless the user chose. */
function showNamingSuggestion(template) {
    document.querySelectorAll(".suggested-tag").forEach((tag) => tag.remove());
    const method = template ? methodOf(template) : "";
    if (!method) {
        return;
    }
    const radio = document.querySelector(
        `input[name="naming-method"][value="${method}"]`);
    // Catalog only keeps every name: nothing to suggest.
    if (radio.disabled) {
        return;
    }
    if (!namingTouched) {
        radio.checked = true;
        updateNamingPreview();
    }
    const tag = document.createElement("span");
    tag.className = "suggested-tag";
    tag.dataset.i18n = "settings.suggested";
    tag.textContent = t("settings.suggested");
    radio.closest(".naming-option").querySelector("span").after(tag);
}

/** "Harbor-Swimmers-Documentary" becomes "Harbor Swimmers Documentary". */
function readableName(folder) {
    return folder.replace(/[-_]+/g, " ").replace(/\s+/g, " ").trim()
        .split(" ")
        .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
        .join(" ");
}

/** A typed name is never replaced; an empty one takes the folder's name. */
function fillNameFromFolder() {
    const field = document.getElementById("research-name");
    if (!nameTouched || !field.value.trim()) {
        field.value = readableName(folderName());
    }
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
            // The box is ticked, not forced: the user can untick it.
            document.getElementById("catalog-only").checked = true;
            document.getElementById("use-drop-zone").checked = false;
            applyCatalogOnly();
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

/** Show a text one character at a time, or at once with reduced motion. */
function typeText(field, text) {
    if (prefersReducedMotion()) {
        field.value = text;
        return Promise.resolve();
    }
    return new Promise((resolve) => {
        let shown = 0;
        field.value = "";
        const timer = setInterval(() => {
            shown += 1;
            field.value = text.slice(0, shown);
            if (shown >= text.length) {
                clearInterval(timer);
                resolve();
            }
        }, TYPE_MS);
    });
}

/** Ask the AI for the sheet of the chosen folder; the user edits it before saving. */
async function suggestProjectSheet() {
    const folder = document.getElementById("target-directory").value.trim();
    if (!folder) {
        showSheetMessage(t("sheet.need_folder"), "error");
        return;
    }
    const button = document.getElementById("suggest-sheet");
    const field = document.getElementById("project-sheet");
    const before = field.value;
    sheetWriting = true;
    button.disabled = true;
    field.readOnly = true;
    showSheetMessage(t("sheet.writing"), "");
    refreshCards();
    try {
        const result = await suggestSheet(folder);
        await typeText(field, result.sheet);
        showSheetMessage("", "");
        setSheetButton(true);
    } catch (error) {
        // What was there before comes back: empty when it ran on its own.
        field.value = before;
        showSheetMessage(errorText(error), "error");
    } finally {
        sheetWriting = false;
        button.disabled = false;
        field.readOnly = false;
        refreshCards();
    }
}

/** Write it for me runs on its own once per folder, unless Later or the user wrote. */
function writeSheetIfEmpty() {
    const folder = document.getElementById("target-directory").value.trim();
    const later = readsNewFolder() && document.querySelector(
        'input[name="archive-when"]:checked').value === "later";
    if (projectMode !== "new" || !folder || later || sheetWriting
            || sheetWrittenFor === folder
            || document.getElementById("project-sheet").value.trim()) {
        return;
    }
    sheetWrittenFor = folder;
    suggestProjectSheet();
}

function showSettingsMessage(text, kind) {
    const message = document.getElementById("settings-message");
    message.textContent = text;
    message.className = "form-message " + kind;
}

// ---- General tab: each field saves on its own ----

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
    const saved = Boolean(provider) && providerHasKey(provider);
    field.placeholder = t(saved ? "settings.api_key_replace"
        : "settings.api_key_placeholder");
    // Whether a key is saved is said in a line of its own, not in the field.
    document.getElementById(`${PROVIDER_ROWS[role].key}-status`).classList
        .toggle("hidden", !saved);
}

/** Show a row's provider and model as saved. */
function showProvider(role, provider, model) {
    rowField(role, "provider").value = provider;
    rowField(role, "key").value = "";
    fillModels(role, model);
    updateKeyPlaceholder(role);
    savedRows[role] = { provider: provider, model: rowField(role, "model")
        .value };
}

function readServerUrl() {
    return document.getElementById("server-url").value.trim();
}

/** "Saved" next to a field for 2 seconds, or the error that undid the change. */
function showFieldNote(field, text, kind) {
    let note = field.nextElementSibling;
    if (!note || !note.classList.contains("field-note")) {
        note = document.createElement("span");
        note.setAttribute("aria-live", "polite");
        field.after(note);
    }
    note.className = "field-note " + kind;
    note.textContent = text;
    clearTimeout(note.timer);
    if (kind === "saved") {
        note.timer = setTimeout(() => {
            note.textContent = "";
        }, SAVED_NOTE_MS);
    }
}

/** The line under AI Provider: provider, model, and whether it connects. */
async function loadAIStatus() {
    const line = document.getElementById("ai-status");
    const text = document.getElementById("ai-status-text");
    const addKey = document.getElementById("ai-status-open");
    line.dataset.state = "loading";
    text.textContent = t("settings.ai_checking");
    addKey.classList.add("hidden");
    try {
        const status = await getAIStatus();
        const known = AI_PROVIDERS[status.provider];
        const parts = [known ? known.label : status.provider, status.model,
            t(`settings.ai_${status.status}`)];
        line.dataset.state = status.status;
        text.textContent = parts.join(" · ");
        addKey.classList.toggle("hidden", status.status !== "no_key");
    } catch (error) {
        line.dataset.state = "error";
        text.textContent = t("settings.ai_error");
    }
}

/** Save a row's provider and model as soon as they change; no key is sent. */
async function saveProviderRow(role, field) {
    const provider = rowProvider(role);
    try {
        if (provider) {
            await updateAIProvider({ role: role, provider_name: provider,
                model: rowField(role, "model").value });
        } else {
            await deleteAIProvider(role);
        }
        savedRows[role] = { provider: provider,
            model: rowField(role, "model").value };
        showFieldNote(field, t("settings.saved_short"), "saved");
        loadAIStatus();
    } catch (error) {
        // The saved choice comes back.
        const saved = savedRows[role] || { provider: "", model: "" };
        rowField(role, "provider").value = saved.provider;
        fillModels(role, saved.model);
        updateKeyPlaceholder(role);
        showFieldNote(field, errorText(error), "error");
    }
}

/** A key is tested first, then saved in the Keychain. A wrong key is never saved. */
async function saveProviderKey(role) {
    const field = rowField(role, "key");
    const key = field.value.trim();
    const provider = rowProvider(role);
    if (!key || !provider) {
        return;
    }
    const model = rowField(role, "model").value;
    field.disabled = true;
    try {
        await testAIProvider({ provider_name: provider, model: model,
            api_key: key, server_url: readServerUrl() });
        await updateAIProvider({ role: role, provider_name: provider,
            model: model, api_key: key });
        if (!providerHasKey(provider)) {
            providersWithKey.push(provider);
        }
        field.value = "";
        showFieldNote(field, t("settings.saved_short"), "saved");
        loadAIStatus();
    } catch (error) {
        // Keys are never shown, so the field goes back to empty.
        field.value = "";
        showFieldNote(field, errorText(error), "error");
    } finally {
        updateKeyPlaceholder(role);
    }
}

async function saveServerUrl() {
    const field = document.getElementById("server-url");
    if (readServerUrl() === savedServerUrl) {
        return;
    }
    try {
        const saved = await patchSetting("server_url", readServerUrl());
        savedServerUrl = saved.value;
        field.value = saved.value;
        showFieldNote(field, t("settings.saved_short"), "saved");
        loadAIStatus();
    } catch (error) {
        field.value = savedServerUrl;
        showFieldNote(field, errorText(error), "error");
    }
}

/** Save the language, then show it everywhere, JS-built text included. */
async function changeLanguage() {
    const select = document.getElementById("language-select");
    const language = select.value;
    const before = currentLanguage;
    try {
        await patchSetting("language", language);
    } catch (error) {
        select.value = before;
        showFieldNote(select, errorText(error), "error");
        return;
    }
    setLanguage(language);
    updateSaveButton();
    Object.keys(PROVIDER_ROWS).forEach(updateKeyPlaceholder);
    // Redraws the part names in the new language, and the preview.
    renderNamingBlocks();
    const title = t(projectMode === "new" ? "project.new_title"
        : "project.edit_title");
    document.getElementById("project-form-title").textContent = title;
    document.getElementById("project-row-title").textContent = title;
    writeFolderFacts();
    refreshCards();
    loadAIStatus();
    showSettingsMessage("", "");
    loadProjectHeader();
    loadCatalog();
    showFieldNote(select, t("settings.saved_short"), "saved");
}

// ---- Load and save ----

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
        loadRecoveryStatus();
        document.getElementById("target-directory").value =
            settings.target_directory;

        document.getElementById("project-sheet").value =
            settings.project_sheet || "";
        showSheetMessage("", "");
        setSheetButton(false);
        document.getElementById("language-select").value =
            settings.language;
        showNamingSuggestion(null);
        showSavedTemplate(settings.naming_template);
        document.querySelector(`input[name="stamp-order"][value="${
            settings.stamp_date_order || "month"}"]`).checked = true;
        document.querySelector(`input[name="naming-style"][value="${
            settings.naming_style || "lower"}"]`).checked = true;
        updateNamingPreview();
        projectFolderMode = settings.folder_mode;
        showCategories(settings.industry, settings.categories);
        // Every project: the saved tree, the type folders of an old
        // project already read, or an empty editor.
        showFolderSection(settings, false);

        providersWithKey = settings.providers_with_key;
        // A project with no provider saved yet gets Ollama Cloud.
        const provider = settings.active_provider in AI_PROVIDERS
            ? settings.active_provider : "ollama";
        showProvider("text", provider, settings.active_model);
        showProvider("fallback", settings.fallback_provider || "",
            settings.fallback_model);
        showProvider("media", settings.media_provider || "",
            settings.media_model);
        savedServerUrl = settings.server_url || "";
        document.getElementById("server-url").value = savedServerUrl;

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

/** Save the Project tab: create the project, or save the active one. */
async function saveSettings(event) {
    event.preventDefault();

    const saveButton = document.getElementById("save-button");
    // A wrong template shows its error and nothing is sent.
    if (!updateNamingPreview()) {
        showSettingsMessage(
            document.getElementById("naming-error").textContent, "error");
        return;
    }
    const catalogOnly = document.getElementById("catalog-only").checked;
    const isTree = !catalogOnly && (projectMode === "new"
        || ["tree", "place"].includes(projectFolderMode));
    // Sorted by type, or Catalog only: the folders go only once the user
    // changed them. Saved, a type project becomes one with its own folders.
    const sendTree = isTree || foldersTouched;
    const archive = archiveChoice();
    const later = archive === "later";
    // A tree typed by hand is checked; read in place it may be empty, the
    // reading proposes it. A Drop Zone (no switch) always needs one.
    const checkTree = sendTree && (readFolderTree().length > 0
        || (isTree && !archive));
    const treeProblem = checkTree ? folderTreeProblem() : "";
    if (treeProblem) {
        showFoldersMessage(treeProblem, "error");
        showSettingsMessage(treeProblem, "error");
        setCardDone(document.getElementById("folders-section"), false);
        return;
    }

    const isNew = projectMode === "new";
    // Set when the folders were saved but no provider can propose moves.
    let needsProvider = false;
    // True once a new project exists, even if something fails later.
    let projectCreated = false;
    let doneMessage = t("settings.saved");

    saveButton.disabled = true;
    showSettingsMessage(t(isNew ? "project.creating" : "settings.saving"),
        "");
    try {
        if (isNew) {
            // Language, AI provider and server live in General, not here.
            // Later reads nothing and asks no AI, but keeps what was typed.
            const created = await createProject({
                name: document.getElementById("research-name").value
                    || folderName(),
                folder: document.getElementById("target-directory").value,
                defer_scan: later,
                naming_template: chosenTemplate(),
                stamp_date_order: readStampOrder(),
                naming_style: readNamingStyle(),
                project_sheet: document.getElementById("project-sheet")
                    .value.trim(),
                folders: readFolderTree(),
                folder_mode: chosenFolderMode(),
                catalog_only: document.getElementById("catalog-only").checked,
                numbered_folders: readNumberedFolders(),
                confirm_folder: folderWarningShown,
            });
            projectCreated = true;
            let createdKey = later ? "project.created_later" : "project.created";
            if (created.opened_existing) {
                createdKey = "project.opened_existing";
            }
            doneMessage = t(createdKey);
        } else {
            const saved = await updateSettings({
                research_name:
                    document.getElementById("research-name").value,
                naming_template: chosenTemplate(),
                stamp_date_order: readStampOrder(),
                naming_style: readNamingStyle(),
                project_sheet: document.getElementById("project-sheet")
                    .value.trim(),
                industry: document.getElementById("industry").value,
                // The tree, when the project has one or the user made one.
                ...(sendTree
                    ? { folder_tree: readFolderTree(),
                        numbered_folders: readNumberedFolders(),
                        folder_moves: readFolderMoves() }
                    : {}),
                // Categories belong to projects sorted by type.
                ...(isTree ? {} : { categories: readCategories() }),
            });
            if (saved.refile_started) {
                // Files already read: the AI proposes their folders now.
                doneMessage = t("folders.refiling");
            }
            needsProvider = Boolean(saved.needs_provider);
            if (saved.folder_moves && !saved.refile_started) {
                // The folders the user chose need no AI.
                doneMessage = t("folders.moves_waiting");
            }
        }
        resetFolderWarning();
        await refreshAfterProjectChange();
        showSettingsMessage(doneMessage, "success");
        if (needsProvider) {
            // The note sits in Folder Names, so that card opens to show it.
            showProviderNote(true);
            const card = document.getElementById("folders-section");
            setCardDone(card, false);
            card.scrollIntoView({ block: "start" });
        }
        if (archive) {
            // Home shows the folder and how far the reading is, or Archive now.
            showView("home");
        }
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
        refreshCards();
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

/** The last part of the chosen folder, the name when none is typed. */
function folderName() {
    const parts = document.getElementById("target-directory").value
        .split("/").filter(Boolean);
    return parts[parts.length - 1] || "";
}

/** A folder was chosen: the name, the advice, the cards, then what it holds. */
async function folderChosen() {
    if (projectMode !== "new") {
        return;
    }
    fillNameFromFolder();
    resetFolderWarning();
    updateCardVisibility();
    await adviseOnFolder();
    await showFolderFacts();
    writeSheetIfEmpty();
}

/** Open the folder picker. Only the desktop window has it, so a browser hides Browse. */
async function browseFolder() {
    const folder = await window.pywebview.api.choose_folder();
    if (folder) {
        document.getElementById("target-directory").value = folder;
        await folderChosen();
    }
}

/** "This folder has 30 files in 3 folders (6.7 MB)." in the current language. */
function writeFolderFacts() {
    if (!folderFacts) {
        return;
    }
    document.getElementById("folder-facts").textContent = t(
        "project.folder_facts", { files: folderFacts.files,
            folders: folderFacts.folders,
            size: humanSize(folderFacts.size) });
}

/** After a folder is chosen: list it (nothing is read), then show its numbers and the switch. */
async function showFolderFacts() {
    const folder = document.getElementById("target-directory").value.trim();
    hideArchiveSwitch();
    if (!folder || projectMode !== "new") {
        return;
    }
    let facts;
    try {
        facts = await listNewFolder(folder);
    } catch (error) {
        return;
    }
    if (facts.has_catalog) {
        // Already a project: it opens as it is, with nothing to choose.
        openExistingFolder();
        return;
    }
    showNamingSuggestion(facts.naming_suggestion);
    folderFacts = facts;
    writeFolderFacts();
    document.getElementById("folder-facts").classList.remove("hidden");
    // A Drop Zone has nothing to read now or later.
    if (readsNewFolder()) {
        document.getElementById("archive-switch").classList.remove("hidden");
    }
    applyArchiveChoice();
    proposeFromFolder();
}

/** A folder that already has a catalog opens as it is, in Home. */
async function openExistingFolder() {
    try {
        await createProject({
            name: document.getElementById("research-name").value.trim()
                || folderName(),
            folder: document.getElementById("target-directory").value.trim(),
            defer_scan: true,
        });
    } catch (error) {
        showSettingsMessage(errorText(error), "error");
        return;
    }
    await refreshAfterProjectChange();
    showView("home");
}

/** Project or General. Opening a tab drops its cards. */
function showSettingsTab(name, drop = true) {
    document.querySelectorAll("[data-settings-tab]").forEach((tab) => {
        const on = tab.dataset.settingsTab === name;
        tab.classList.toggle("active", on);
        tab.setAttribute("aria-selected", String(on));
    });
    document.getElementById("settings-project").classList
        .toggle("hidden", name !== "project");
    document.getElementById("settings-general").classList
        .toggle("hidden", name !== "general");
    if (name === "general") {
        loadAIStatus();
    }
    // Changing tabs is never the full drop: the cards just come in.
    if (drop) {
        dropCards(openTabCards(), true);
    }
}

// ---- Events ----

// pywebview announces itself with this event once its API is ready.
window.addEventListener("pywebviewready", () => {
    pywebviewReady = true;
    updateBrowseButton();
});

document.querySelectorAll("[data-settings-tab]").forEach((tab) => {
    tab.addEventListener("click", () => showSettingsTab(tab.dataset
        .settingsTab));
});
// A finished drop leaves nothing behind, so the next one can play.
document.addEventListener("animationend", (event) => {
    if (["card-drop", "card-quick"].includes(event.animationName)) {
        event.target.classList.remove("card-drop", "card-quick");
    }
});

updateBrowseButton();
// Every Choose folder button, now and later (they can be drawn by JS).
document.addEventListener("click", (event) => {
    if (event.target.closest("[data-start-folder]")) {
        chooseFolderToStart();
    }
});
document.getElementById("browse-button")
    .addEventListener("click", browseFolder);
// Cancel leaves New Project for Home; Settings reloads as it is saved.
document.getElementById("cancel-new-project")
    .addEventListener("click", () => {
        showSettingsMessage("", "");
        loadSettings();
        showView("home");
    });
document.getElementById("remove-project-button")
    .addEventListener("click", openRemoveDialog);
document.getElementById("remove-project-confirm")
    .addEventListener("click", confirmRemoveProject);
document.getElementById("remove-project-cancel")
    .addEventListener("click", () => {
        document.getElementById("remove-project-dialog").close();
    });

// Folded cards: Change opens one; Done, or going on to a later card, folds it.
const settingsForm = document.getElementById("settings-form");
settingsForm.addEventListener("click", (event) => {
    const change = event.target.closest(".card-change");
    const confirm = event.target.closest(".card-confirm");
    if (change) {
        const card = change.closest(".settings-card");
        setCardDone(card, false);
        const first = card.querySelector(".card-open input:not([readonly]), "
            + ".card-open textarea, .card-open select");
        if (first) {
            first.focus({ preventScroll: true });
        }
    } else if (confirm) {
        setCardDone(confirm.closest(".settings-card"), true);
    }
});
settingsForm.addEventListener("focusin", (event) => moveOnFrom(event.target));
settingsForm.addEventListener("pointerdown",
    (event) => moveOnFrom(event.target));
settingsForm.addEventListener("input", refreshCards);
settingsForm.addEventListener("change", refreshCards);
settingsForm.addEventListener("submit", saveSettings);

document.getElementById("research-name").addEventListener("input", () => {
    nameTouched = Boolean(document.getElementById("research-name").value
        .trim());
});
// A different folder needs its own warning.
document.getElementById("target-directory")
    .addEventListener("input", resetFolderWarning);
document.getElementById("target-directory")
    .addEventListener("change", folderChosen);
// Only Archive Now reads the folder and asks the AI; Later sends nothing.
document.querySelectorAll('input[name="archive-when"]').forEach((radio) => {
    radio.addEventListener("change", () => {
        applyArchiveChoice();
        proposeFromFolder();
        writeSheetIfEmpty();
    });
});
// Drop Zone has nothing to read now or later; in place and Catalog only do.
// The two boxes exclude each other: ticking one unticks the other.
document.getElementById("use-drop-zone")
    .addEventListener("change", async () => {
        if (document.getElementById("use-drop-zone").checked) {
            document.getElementById("catalog-only").checked = false;
            applyCatalogOnly();
        }
        await showFolderFacts();
        writeSheetIfEmpty();
    });
document.getElementById("catalog-only")
    .addEventListener("change", () => {
        if (document.getElementById("catalog-only").checked) {
            document.getElementById("use-drop-zone").checked = false;
        }
        applyCatalogOnly();
        showFolderFacts();
    });
document.getElementById("suggest-sheet")
    .addEventListener("click", suggestProjectSheet);
document.getElementById("naming-options")
    .addEventListener("change", (event) => {
        // A method the user picks is never replaced by a suggestion.
        if (event.isTrusted && event.target.name === "naming-method") {
            namingTouched = true;
        }
        updateNamingPreview();
    });
document.querySelectorAll('input[name="naming-style"]').forEach((radio) => {
    radio.addEventListener("change", updateNamingPreview);
});
document.querySelectorAll('input[name="naming-separator"]')
    .forEach((radio) => {
        radio.addEventListener("change", () => {
            customSeparator = radio.value;
            updateNamingPreview();
        });
    });

// General: selects save when they change, text fields on leaving or Enter.
document.getElementById("language-select")
    .addEventListener("change", changeLanguage);
Object.keys(PROVIDER_ROWS).forEach((role) => {
    const provider = rowField(role, "provider");
    const model = rowField(role, "model");
    const key = rowField(role, "key");
    provider.addEventListener("change", () => {
        fillModels(role, "");
        updateKeyPlaceholder(role);
        saveProviderRow(role, provider);
    });
    model.addEventListener("change", () => saveProviderRow(role, model));
    key.addEventListener("change", () => saveProviderKey(role));
});
document.getElementById("server-url")
    .addEventListener("change", saveServerUrl);
document.querySelectorAll("#ai-advanced input").forEach((field) => {
    field.addEventListener("keydown", (event) => {
        // Enter saves a key or the server, as leaving the field does.
        if (event.key === "Enter") {
            event.preventDefault();
            field.blur();
        }
    });
});
document.getElementById("ai-status-open").addEventListener("click", () => {
    document.getElementById("ai-advanced").open = true;
    rowField("text", "key").focus();
});
// Change password opens the three fields; they save with their own button.
document.getElementById("open-password").addEventListener("click", () => {
    const fields = document.getElementById("password-fields");
    const open = fields.classList.contains("hidden");
    fields.classList.toggle("hidden", !open);
    document.getElementById("open-password")
        .setAttribute("aria-expanded", String(open));
    if (open) {
        document.getElementById("current-password").focus();
    }
});

// startApp() in app.js calls fillProviders() and loadSettings() after the language loads.
