/**
 * app.js
 *
 * Switches between the three views (Catalog, Dashboard, Settings) when a
 * link in the navigation bar is clicked. Only one view is visible at a
 * time; the others get the "hidden" class.
 */

/**
 * Show one view and hide the others.
 * @param {string} name - "catalog", "dashboard", or "settings".
 */
function showView(name) {
    document.querySelectorAll(".view").forEach((view) => {
        view.classList.toggle("hidden", view.id !== `view-${name}`);
    });
    document.querySelectorAll(".nav-link").forEach((link) => {
        link.classList.toggle("active", link.dataset.view === name);
    });
}

document.querySelectorAll(".nav-link").forEach((link) => {
    link.addEventListener("click", (event) => {
        // Stop the "#" link from jumping to the top of the page.
        event.preventDefault();
        showView(link.dataset.view);
    });
});
