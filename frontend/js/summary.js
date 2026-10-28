/** summary.js: summaries cut at 2 lines, with Read more when the text does not fit. */

// Ids of open summaries, so they stay open when Catalog redraws its table.
const openSummaries = new Set();

/** Show the button while open, or while closed only if the text is cut. */
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

/** Build a summary with its Read more / Show less button. */
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
    // A closed summary waits for the observer to say if the text is cut.
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

/** Stop watching summaries in an element about to be emptied. */
function forgetSummaries(container) {
    container.querySelectorAll(".summary-text").forEach((text) => {
        summaryObserver.unobserve(text);
    });
}
