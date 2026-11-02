/** help.js: the "?" next to a field. Hover, click or keyboard show a balloon. */

/** Turn every .help-tip placeholder into a button and its balloon. */
function buildHelpTips() {
    document.querySelectorAll(".help-tip").forEach((tip, index) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "help-button";
        button.dataset.i18nLabel = "help.open";
        button.setAttribute("aria-expanded", "false");
        const icon = document.createElement("span");
        icon.className = "icon icon-help";
        button.appendChild(icon);
        const bubble = document.createElement("span");
        bubble.className = "help-bubble";
        bubble.id = `help-bubble-${index}`;
        bubble.setAttribute("role", "tooltip");
        bubble.dataset.i18n = tip.dataset.help;
        button.setAttribute("aria-describedby", bubble.id);
        button.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopPropagation();
            setHelpOpen(tip, !tip.classList.contains("open"));
        });
        // The keyboard opens it the way the mouse does.
        button.addEventListener("focus", () => setHelpOpen(tip, true));
        button.addEventListener("blur", () => setHelpOpen(tip, false));
        tip.addEventListener("mouseleave", () => {
            tip.classList.remove("dismissed");
        });
        tip.append(button, bubble);
    });
}

function setHelpOpen(tip, open) {
    tip.classList.toggle("open", open);
    tip.classList.remove("dismissed");
    tip.querySelector(".help-button")
        .setAttribute("aria-expanded", String(open));
}

/** Close every balloon; one under the mouse stays closed until it leaves. */
function closeHelpTips() {
    document.querySelectorAll(".help-tip").forEach((tip) => {
        setHelpOpen(tip, false);
        tip.classList.add("dismissed");
    });
}

document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
        closeHelpTips();
    }
});
document.addEventListener("click", (event) => {
    if (!event.target.closest(".help-tip")) {
        closeHelpTips();
    }
});
buildHelpTips();
