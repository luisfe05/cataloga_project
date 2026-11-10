/** motion.js: numbers that count up, bars that grow, and pausing the gradients. */

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

// The gradients that move all the time (main.css, home.css).
const DRIFT_ANIMATIONS = ["backdrop-drift", "sidebar-drift", "gradient-drift"];

/** Stop every moving gradient while the window is hidden or not in front. */
function setMotionPaused(paused) {
    document.documentElement.classList.toggle("motion-paused", paused);
    // WebKit did not always start them again from the class alone.
    document.getAnimations().forEach((animation) => {
        if (DRIFT_ANIMATIONS.includes(animation.animationName)) {
            if (paused) {
                animation.pause();
            } else {
                animation.play();
            }
        }
    });
}

// Views with many glass cards: the page and sidebar backgrounds stay still,
// because every card is blurred again on each frame they move.
const STILL_BACKGROUND_VIEWS = ["settings", "dashboard"];

/** Keep the two big backgrounds still in some views; showView() calls this. */
function setStillBackground(view) {
    const body = document.body;
    const still = STILL_BACKGROUND_VIEWS.includes(view);
    if (still === body.classList.contains("view-static-bg")) {
        return;
    }
    if (still) {
        // Each layer glides back to its start from where it is now: no jump.
        body.style.setProperty("--backdrop-from",
            getComputedStyle(body, "::before").transform);
        const sidebar = document.querySelector(".sidebar");
        body.style.setProperty("--sidebar-from",
            getComputedStyle(sidebar, "::before").transform);
    }
    body.classList.toggle("view-static-bg", still);
}

document.addEventListener("visibilitychange", () => {
    setMotionPaused(document.hidden);
});
// pywebview's window sends blur and focus like a browser tab.
window.addEventListener("blur", () => setMotionPaused(true));
window.addEventListener("focus", () => setMotionPaused(false));
