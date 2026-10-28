/**
 * chat.js
 *
 * The chat panel on the right. Sends each message to POST /chat and
 * draws the answer. The backend answers with ONE action from a fixed
 * list, and this file has one draw function per action (see
 * ACTION_RENDERERS). Nothing here changes a file, except the Confirm
 * button of a proposed rename, which calls POST /documents/<id>/rename.
 *
 * The conversation lives only in memory. The last messages go with
 * each request, and clearChat() empties it when the project changes.
 */

// How many earlier messages go to the backend with each message.
const CHAT_HISTORY_SIZE = 6;

// The conversation so far: [{role: "user" or "assistant", text}].
let chatHistory = [];

// True while waiting for an answer, so a second message waits.
let chatBusy = false;

/**
 * Create an element with a class and, optionally, its text.
 * Text from files or the AI always goes in as plain text, never HTML.
 * @param {string} tag
 * @param {string} className
 * @param {string} [text]
 * @returns {HTMLElement}
 */
function chatElement(tag, className, text) {
    const element = document.createElement(tag);
    element.className = className;
    if (text !== undefined && text !== null) {
        element.textContent = text;
    }
    return element;
}

/**
 * Open or close the panel.
 * @param {boolean} open
 */
function toggleChat(open) {
    document.getElementById("chat-panel").classList.toggle("hidden", !open);
    document.body.classList.toggle("chat-open", open);
    document.getElementById("chat-toggle")
        .setAttribute("aria-expanded", String(open));
    if (open) {
        document.getElementById("chat-input").focus();
    }
}

/**
 * Empty the conversation. Called when the active project changes, so
 * answers about one project never mix with another.
 */
function clearChat() {
    chatHistory = [];
    const messages = document.getElementById("chat-messages");
    forgetSummaries(messages);
    messages.querySelectorAll(".chat-message").forEach((item) => {
        item.remove();
    });
    document.getElementById("chat-empty").classList.remove("hidden");
}

/**
 * Remember one message for the next requests.
 * @param {string} role - "user" or "assistant".
 * @param {string} text
 */
function rememberMessage(role, text) {
    if (!text) {
        return;
    }
    chatHistory.push({ role: role, text: text });
    chatHistory = chatHistory.slice(-CHAT_HISTORY_SIZE);
}

/**
 * Add a message to the panel and scroll down to it.
 * @param {HTMLElement} item
 */
function appendMessage(item) {
    const messages = document.getElementById("chat-messages");
    document.getElementById("chat-empty").classList.add("hidden");
    messages.appendChild(item);
    messages.scrollTop = messages.scrollHeight;
}

/**
 * Draw what the user wrote.
 * @param {string} text
 */
function addUserMessage(text) {
    const item = chatElement("div", "chat-message chat-user");
    item.appendChild(chatElement("p", "chat-bubble", text));
    appendMessage(item);
}

/**
 * Draw an empty answer from the assistant, with its avatar.
 * @returns {{item: HTMLElement, body: HTMLElement}}
 */
function addAssistantMessage() {
    const item = chatElement("div", "chat-message chat-assistant");
    const avatar = chatElement("span", "chat-avatar");
    const image = document.createElement("img");
    image.src = "assets/logomark-midnight.svg";
    image.alt = "";
    avatar.appendChild(image);
    const body = chatElement("div", "chat-body");
    item.append(avatar, body);
    appendMessage(item);
    return { item: item, body: body };
}

/**
 * Open a document in Catalog: switch view, then scroll to its row and
 * highlight it (highlightDocument() is in catalog.js).
 * @param {number} id
 */
function openDocument(id) {
    showView("catalog");
    highlightDocument(id);
}

/**
 * Build the card for one document. The name opens the file, the icons
 * preview it or show it in Finder (files.js), and "Show in Catalog"
 * highlights its row. A card is a div, because buttons cannot go
 * inside another button.
 * @param {Object} doc - {id, filename, media_type, document_date,
 *     summary}
 * @returns {HTMLDivElement}
 */
function documentCard(doc) {
    const card = chatElement("div", "chat-card");
    const top = chatElement("div", "chat-card-top");
    const link = makeFileLink(doc);
    link.classList.add("chat-card-name");
    top.append(link, makeFileActions(doc.id));
    card.appendChild(top);
    const meta = [valueLabel(doc.media_type), doc.document_date]
        .filter(Boolean).join(" · ");
    card.appendChild(chatElement("span", "chat-card-meta", meta));
    if (doc.summary) {
        const summary = makeSummary(doc.summary, doc.id);
        summary.classList.add("chat-card-summary");
        card.appendChild(summary);
    }
    const show = chatElement("button", "chat-link",
        t("files.show_in_catalog"));
    show.type = "button";
    show.addEventListener("click", () => openDocument(doc.id));
    card.appendChild(show);
    return card;
}

/**
 * Draw the sources as numbered citations under the answer.
 * @param {HTMLElement} body
 * @param {Array<Object>} sources - Document cards.
 */
function drawSources(body, sources) {
    if (!sources.length) {
        return;
    }
    const row = chatElement("div", "chat-sources");
    row.appendChild(chatElement("span", "chat-sources-label",
        t("chat.sources")));
    sources.forEach((doc, index) => {
        // Number, name (opens the file), then the eye and folder icons.
        const chip = chatElement("span", "chat-source", `${index + 1}. `);
        chip.append(makeFileLink(doc), makeFileActions(doc.id));
        row.appendChild(chip);
    });
    body.appendChild(row);
}

/**
 * show_documents: one card per document.
 * @param {HTMLElement} body
 * @param {Object} answer
 */
function drawDocuments(body, answer) {
    const list = chatElement("div", "chat-cards");
    answer.documents.forEach((doc) => list.appendChild(documentCard(doc)));
    body.appendChild(list);
}

/**
 * filter_catalog: apply the filters in Catalog right away and list
 * them, with a button to go back to Catalog later.
 * @param {HTMLElement} body
 * @param {Object} answer
 */
function drawFilters(body, answer) {
    const filters = answer.filters;
    showView("catalog");
    applyCatalogFilters(filters);

    const box = chatElement("div", "chat-filters");
    box.appendChild(chatElement("span", "chat-sources-label",
        t("chat.filters_applied")));
    const values = [
        filters.media_type && valueLabel(filters.media_type),
        filters.status && valueLabel(filters.status),
        filters.source,
        filters.text && `“${filters.text}”`,
    ].filter(Boolean);
    values.forEach((value) => {
        box.appendChild(chatElement("span", "chat-chip", value));
    });
    const again = chatElement("button", "chat-link", t("chat.open_catalog"));
    again.type = "button";
    again.addEventListener("click", () => {
        showView("catalog");
        applyCatalogFilters(filters);
    });
    box.appendChild(again);
    body.appendChild(box);
}

/**
 * summarize_project: the numbers from the catalog, next to the text.
 * @param {HTMLElement} body
 * @param {Object} answer
 */
function drawProjectSummary(body, answer) {
    const project = answer.project;
    const stats = chatElement("div", "chat-stats");
    const addStat = (label, value) => {
        const stat = chatElement("div", "chat-stat");
        stat.appendChild(chatElement("span", "chat-stat-value", value));
        stat.appendChild(chatElement("span", "chat-stat-label", label));
        stats.appendChild(stat);
    };
    addStat(t("chat.summary_total"), String(project.total));
    addStat(valueLabel("Manual Review"), String(project.manual_review));
    body.appendChild(stats);
    if (project.first_date) {
        body.appendChild(chatElement("p", "chat-note",
            `${t("chat.summary_dates")}: ${project.first_date} – `
            + project.last_date));
    }
    if (project.top_sources.length) {
        const sources = project.top_sources
            .map((item) => `${item.source} (${item.count})`).join(", ");
        body.appendChild(chatElement("p", "chat-note",
            `${t("chat.summary_sources")}: ${sources}`));
    }
}

/**
 * propose_rename: a card "current → new" with Confirm and Cancel.
 * Only Confirm renames, through POST /documents/<id>/rename.
 * @param {HTMLElement} body
 * @param {Object} answer
 */
function drawRename(body, answer) {
    const rename = answer.rename;
    const card = chatElement("div", "chat-rename");
    card.appendChild(chatElement("span", "chat-sources-label",
        t("chat.rename_title")));
    card.appendChild(chatElement("p", "chat-rename-old",
        rename.current_name));
    card.appendChild(chatElement("p", "chat-rename-arrow", "↓"));
    card.appendChild(chatElement("p", "chat-rename-new", rename.new_name));

    const buttons = chatElement("div", "form-buttons");
    const confirm = chatElement("button", "primary-button",
        t("chat.confirm"));
    confirm.type = "button";
    const cancel = chatElement("button", "secondary-button",
        t("chat.cancel"));
    cancel.type = "button";
    buttons.append(confirm, cancel);
    card.appendChild(buttons);
    const result = chatElement("p", "chat-rename-result");
    card.appendChild(result);

    const finish = (text) => {
        buttons.remove();
        result.textContent = text;
    };
    confirm.addEventListener("click", async () => {
        confirm.disabled = true;
        cancel.disabled = true;
        try {
            const doc = await renameDocument(rename.document_id,
                rename.new_name);
            // The backend may add -2 if the name was taken, so show
            // the name it really used.
            finish(t("chat.renamed", { name: doc.filename }));
            rememberMessage("assistant",
                t("chat.renamed", { name: doc.filename }));
            loadCatalog();
            if (!document.getElementById("view-dashboard")
                    .classList.contains("hidden")) {
                loadDashboard();
            }
        } catch (error) {
            confirm.disabled = false;
            cancel.disabled = false;
            result.textContent = errorText(error);
        }
    });
    cancel.addEventListener("click", () => {
        finish(t("chat.rename_cancelled"));
    });
    body.appendChild(card);
}

// One draw function per action, after the reply text. "answer" only
// has the text. A new action needs one more entry here.
const ACTION_RENDERERS = {
    show_documents: drawDocuments,
    filter_catalog: drawFilters,
    summarize_project: drawProjectSummary,
    propose_rename: drawRename,
};

/**
 * Draw one answer from POST /chat.
 * @param {HTMLElement} body
 * @param {Object} answer
 */
function drawAnswer(body, answer) {
    body.innerHTML = "";
    // A notice is a friendly message in the app's language, used when
    // the AI failed or answered with something invalid.
    const text = answer.notice
        ? t(`chat.notice_${answer.notice}`) : answer.reply;
    if (text) {
        body.appendChild(chatElement("p", "chat-bubble", text));
    }
    const draw = ACTION_RENDERERS[answer.action];
    if (draw) {
        draw(body, answer);
    }
    drawSources(body, answer.sources || []);
    rememberMessage("assistant", text);
}

/**
 * Send one message and draw the answer.
 * @param {string} text
 */
async function sendChat(text) {
    const message = text.trim();
    if (!message || chatBusy) {
        return;
    }
    chatBusy = true;
    const input = document.getElementById("chat-input");
    const send = document.getElementById("chat-send");
    input.value = "";
    send.disabled = true;

    addUserMessage(message);
    // The history sent is the conversation before this message.
    const history = chatHistory.slice();
    rememberMessage("user", message);
    const reply = addAssistantMessage();
    reply.body.appendChild(chatElement("p", "chat-bubble chat-thinking",
        t("chat.thinking")));

    try {
        drawAnswer(reply.body, await sendChatMessage(message, history));
    } catch (error) {
        reply.body.innerHTML = "";
        reply.body.appendChild(chatElement("p", "chat-bubble chat-error",
            errorText(error)));
    }
    const messages = document.getElementById("chat-messages");
    messages.scrollTop = messages.scrollHeight;
    chatBusy = false;
    send.disabled = false;
    input.focus();
}

document.getElementById("chat-toggle").addEventListener("click", () => {
    const panel = document.getElementById("chat-panel");
    toggleChat(panel.classList.contains("hidden"));
});

document.getElementById("chat-close")
    .addEventListener("click", () => toggleChat(false));

document.getElementById("chat-form").addEventListener("submit", (event) => {
    event.preventDefault();
    sendChat(document.getElementById("chat-input").value);
});

// Enter sends; Shift+Enter starts a new line.
document.getElementById("chat-input").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendChat(event.target.value);
    }
});

// Example buttons: send their text, or only start the sentence.
document.querySelectorAll(".chat-example").forEach((button) => {
    button.addEventListener("click", () => {
        const text = t(button.dataset.prompt);
        if (button.dataset.fillOnly) {
            const input = document.getElementById("chat-input");
            input.value = text;
            input.focus();
            return;
        }
        sendChat(text);
    });
});
