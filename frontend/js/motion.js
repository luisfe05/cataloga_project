/** motion.js: numbers that count up and bars that grow. Skipped with reduced motion. */

// Longest time a number takes to count up, in milliseconds.
const COUNT_UP_MS = 600;

/** Does the user ask the system for less motion? */
function prefersReducedMotion() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** Count from the value on screen, so an unchanged number does not move on refresh. */
function countUp(element, value) {
    const start = Number(element.textContent) || 0;
    // Stop a count that is still running on this element.
    cancelAnimationFrame(element.countUpFrame);
    if (start === value || prefersReducedMotion()) {
        element.textContent = value;
        return;
    }
    const startTime = performance.now();
    const step = (now) => {
        // A frame can come slightly before startTime; a negative progress would go below zero.
        const progress = Math.max(0,
            Math.min((now - startTime) / COUNT_UP_MS, 1));
        // Ease out: fast at first, slow at the end.
        const eased = 1 - Math.pow(1 - progress, 3);
        element.textContent = Math.round(start + (value - start) * eased);
        if (progress < 1) {
            element.countUpFrame = requestAnimationFrame(step);
        }
    };
    element.countUpFrame = requestAnimationFrame(step);
}

/** Move a CSS variable, so a CSS transition makes the bar grow. */
function growBar(element, name, from, to) {
    element.style.setProperty(name, from);
    // Reading the size draws the start size first; otherwise the bar jumps.
    element.getBoundingClientRect();
    element.style.setProperty(name, to);
}
