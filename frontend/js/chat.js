/** chat.js: the chat window. Only Confirm on a proposed rename changes anything. */

const CHAT_HISTORY_SIZE = 6;

// [{role: "user" or "assistant", text}]
let chatHistory = [];

// True while waiting for an answer, so a second message waits.
let chatBusy = false;

/** An element with a class and plain text: text from files or the AI is never HTML. */
function chatElement(tag, className, text) {
    const element = document.createElement(tag);
    element.className = className;
    if (text !== undefined && text !== null) {
        element.textContent = text;
    }
    return element;
}

function toggleChat(open) {
    document.getElementById("chat-panel").classList.toggle("hidden", !open);
    const button = document.getElementById("chat-toggle");
    button.setAttribute("aria-expanded", String(open));
    // Open, the round button turns Violet with ×; it closes the panel.
    button.classList.toggle("is-open", open);
    if (open) {
        // "Harbor Swimmers · 30 files": what the answers are about.
        const parts = [activeProjectName()];
        if (catalogTotal) {
            parts.push(t("home.files", { n: catalogTotal }));
        }
        document.getElementById("chat-scope").textContent =
            parts.filter(Boolean).join(" · ");
        document.getElementById("chat-input").focus();
    }
}

/** Empty the conversation, so answers about one project never mix with another. */
function clearChat() {
    chatHistory = [];
    const messages = document.getElementById("chat-messages");
    forgetSummaries(messages);
    messages.querySelectorAll(".chat-message").forEach((item) => {
        item.remove();
    });
    document.getElementById("chat-empty").classList.remove("hidden");
}

function rememberMessage(role, text) {
    if (!text) {
        return;
    }
    chatHistory.push({ role: role, text: text });
    chatHistory = chatHistory.slice(-CHAT_HISTORY_SIZE);
}

function appendMessage(item) {
    const messages = document.getElementById("chat-messages");
    document.getElementById("chat-empty").classList.add("hidden");
    messages.appendChild(item);
    messages.scrollTop = messages.scrollHeight;
}

function addUserMessage(text) {
    const item = chatElement("div", "chat-message chat-user");
    item.appendChild(chatElement("p", "chat-bubble", text));
    appendMessage(item);
}

function addAssistantMessage() {
    const item = chatElement("div", "chat-message chat-assistant");
    const avatar = chatElement("span", "chat-avatar");
    const image = document.createElement("img");
    // All Paper, tab too, on the Violet circle: Violet on Violet is lost.
    image.src = "assets/logomark-avatar.svg";
    image.alt = "";
    avatar.appendChild(image);
    const body = chatElement("div", "chat-body");
    item.append(avatar, body);
    appendMessage(item);
    return { item: item, body: body };
}

/** Open a document's row in Catalog and highlight it. */
function openDocument(id) {
    showView("catalog");
    highlightDocument(id);
}

/** One document card. A div, because buttons cannot go inside another button. */
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

/** Draw the sources as numbered citations under the answer. */
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

/** show_documents: one card per document. */
function drawDocuments(body, answer) {
    const list = chatElement("div", "chat-cards");
    answer.documents.forEach((doc) => list.appendChild(documentCard(doc)));
    body.appendChild(list);
}

/** filter_catalog: apply the filters in Catalog now and list them. */
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

/** summarize_project: the numbers from the catalog, next to the text. */
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
        const note = chatElement("p", "chat-note",
            `${t("chat.summary_sources")}: `);
        project.top_sources.forEach((item, index) => {
            if (index > 0) {
                note.append(", ");
            }
            note.append(sourceLink(item.source), ` (${item.count})`);
        });
        body.appendChild(note);
    }
}

/** A source name that opens Catalog list with only its documents, newest first. */
function sourceLink(source) {
    const link = chatElement("button", "chat-link chat-source-link", source);
    link.type = "button";
    link.setAttribute("aria-label", t("chat.show_source", { source: source }));
    link.addEventListener("click", () => {
        showView("catalog");
        applyCatalogFilters({ source: source, sort: "newest" });
    });
    return link;
}

/** propose_rename: "current → new" with Confirm and Cancel. Only Confirm renames. */
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
            // The backend may add -2, so show the name it really used.
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

/** propose_move: "file: current folder → new folder" with Confirm and Cancel. Only Confirm moves. */
function drawMove(body, answer) {
    const move = answer.move;
    const card = chatElement("div", "chat-rename");
    card.appendChild(chatElement("span", "chat-sources-label",
        t("chat.move_title", { name: move.filename })));
    card.appendChild(chatElement("p", "chat-rename-old",
        move.current_folder ? folderLabel(move.current_folder)
            : t("catalog.in_drop_zone")));
    card.appendChild(chatElement("p", "chat-rename-arrow", "↓"));
    card.appendChild(chatElement("p", "chat-rename-new",
        folderLabel(move.new_folder)));

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
            await moveDocument(move.document_id, move.new_folder, false);
            const text = t("catalog.moved",
                { folder: folderLabel(move.new_folder) });
            finish(text);
            rememberMessage("assistant", text);
            loadCatalog();
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

// One draw function per action. A new action needs one more entry here.
const ACTION_RENDERERS = {
    show_documents: drawDocuments,
    filter_catalog: drawFilters,
    summarize_project: drawProjectSummary,
    propose_rename: drawRename,
    propose_move: drawMove,
};

function drawAnswer(body, answer) {
    body.innerHTML = "";
    // A notice is a friendly message used when the AI failed or answered badly.
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

// The message limit: the field stops there, the server checks it too.
const CHAT_MAX_CHARS = 2000;
// The counter appears when this many characters, or fewer, are left.
const CHAT_COUNTER_FROM = 200;

function updateCounter() {
    const input = document.getElementById("chat-input");
    const counter = document.getElementById("chat-counter");
    const left = CHAT_MAX_CHARS - input.value.length;
    counter.hidden = left > CHAT_COUNTER_FROM;
    counter.textContent = t("chat.chars_left", { n: left });
}

async function sendChat(text) {
    const message = text.trim();
    if (!message || chatBusy) {
        return;
    }
    chatBusy = true;
    const input = document.getElementById("chat-input");
    const send = document.getElementById("chat-send");
    input.value = "";
    updateCounter();
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

// Escape closes the chat, but only the dialog while Remove project is open.
document.addEventListener("keydown", (event) => {
    const panel = document.getElementById("chat-panel");
    const dialog = document.getElementById("remove-project-dialog");
    if (event.key !== "Escape" || panel.classList.contains("hidden")
            || dialog.open) {
        return;
    }
    toggleChat(false);
    document.getElementById("chat-toggle").focus();
});

document.getElementById("chat-form").addEventListener("submit", (event) => {
    event.preventDefault();
    sendChat(document.getElementById("chat-input").value);
});

document.getElementById("chat-input").addEventListener("input", updateCounter);

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
            updateCounter();
            input.focus();
            return;
        }
        sendChat(text);
    });
});
