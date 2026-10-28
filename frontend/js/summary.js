/**
 * summary.js
 *
 * A summary shown in at most 2 lines, cut with "…" by CSS line-clamp.
 * When the text does not fit, a "Read more" button opens it in place,
 * and "Show less" closes it again. Used by Catalog and the chat cards.
 *
 * Whether the text fits is only known once it is drawn, so a
 * ResizeObserver checks it then, and again whenever its width changes
 * (a smaller window, or the chat panel opening).
 */

// Ids of the summaries the user opened. Catalog redraws its table
// every few seconds, so this keeps them open after a redraw.
const openSummaries = new Set();

/**
 * Show the button only when it is needed: always while the summary is
 * open (to close it), and while closed only if the text is cut.
 * @param {HTMLElement} text - The .summary-text element.
 */
function updateReadMore(text) {
    const button = text.nextElementSibling;
    const isOpen = text.classList.contains("open");
    // scrollHeight is the full text; clientHeight is the 2 lines shown.
    const isCut = text.scrollHeight > text.clientHeight + 1;
    button.hidden = !isOpen && !isCut;
}

// One observer for every summary on screen.
const summaryObserver = new ResizeObserver((entries) => {
    entries.forEach((entry) => updateReadMore(entry.target));
});

/**
 * Build a summary with its Read more / Show less button.
 * @param {string} summary - The summary text.
 * @param {number} id - The document id, to remember if it is open.
 * @returns {HTMLDivElement}
 */
function makeSummary(summary, id) {
    const block = document.createElement("div");
    block.className = "summary-block";

    const text = document.createElement("p");
    text.className = "summary-text";
    // Plain text: a summary from the AI is never run as HTML.
    text.textContent = summary;

    const button = document.createElement("button");
    button.type = "button";
    button.className = "read-more";
    // An open summary always needs its Show less button. A closed one
    // waits for the observer to say if the text is cut.
    button.hidden = !openSummaries.has(id);

    // Draw the open or closed state, with its button text.
    const show = (isOpen) => {
        text.classList.toggle("open", isOpen);
        button.textContent = t(isOpen ? "summary.show_less"
            : "summary.read_more");
        button.setAttribute("aria-expanded", String(isOpen));
    };
    show(openSummaries.has(id));

    button.addEventListener("click", (event) => {
        // The click must not also select the Catalog row.
        event.stopPropagation();
        const isOpen = !text.classList.contains("open");
        if (isOpen) {
            openSummaries.add(id);
        } else {
            openSummaries.delete(id);
        }
        show(isOpen);
        updateReadMore(text);
    });

    block.append(text, button);
    summaryObserver.observe(text);
    return block;
}

/**
 * Stop watching the summaries inside an element that is about to be
 * emptied, so the observer does not keep rows that are gone.
 * @param {HTMLElement} container
 */
function forgetSummaries(container) {
    container.querySelectorAll(".summary-text").forEach((text) => {
        summaryObserver.unobserve(text);
    });
}
