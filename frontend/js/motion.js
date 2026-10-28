/**
 * motion.js
 *
 * Small animations shared by the catalog and the dashboard: numbers
 * that count up and bars that grow. When the system asks for reduced
 * motion, numbers are set right away and the CSS turns off the
 * transitions.
 */

// Longest time a number takes to count up, in milliseconds.
const COUNT_UP_MS = 600;

/**
 * Does the user ask the system for less motion?
 * @returns {boolean}
 */
function prefersReducedMotion() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/**
 * Count a number up (or down) from the value on screen to a new one.
 * The dashboard refreshes every few seconds, so starting from the value
 * on screen means an unchanged number does not move.
 * @param {HTMLElement} element
 * @param {number} value
 */
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
        // The time of a frame can be a little before startTime, so
        // keep progress between 0 and 1. A negative one would make the
        // number jump below zero.
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

/**
 * Move a CSS variable from one value to another, so a CSS transition
 * makes the bar grow.
 * @param {HTMLElement} element
 * @param {string} name - CSS variable, like "--share".
 * @param {string} from - Size to start from, like "0%".
 * @param {string} to - Final size, like "40%".
 */
function growBar(element, name, from, to) {
    element.style.setProperty(name, from);
    // Reading the size makes the browser draw the start size first;
    // without it the bar would jump straight to the final size.
    element.getBoundingClientRect();
    element.style.setProperty(name, to);
}
