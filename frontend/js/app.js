/**
 * app.js
 *
 * Switches between the three views (Catalog, Dashboard, Settings) when a
 * link in the navigation bar is clicked. Only one view is visible at a
 * time; the others get the "hidden" class.
 *
 * Also starts the app: startApp() reads the saved language first, so
 * every screen is drawn in that language from the start.
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
    // Load fresh numbers every time the dashboard is opened.
    if (name === "dashboard") {
        loadDashboard();
    }
}

document.querySelectorAll(".nav-link").forEach((link) => {
    link.addEventListener("click", (event) => {
        // Stop the "#" link from jumping to the top of the page.
        event.preventDefault();
        showView(link.dataset.view);
    });
});

/**
 * Load the saved language, then draw the screens.
 * If the backend does not answer, the app starts in English and each
 * screen shows its own "could not load" message.
 */
async function startApp() {
    let language = "en";
    try {
        const settings = await getSettings();
        language = settings.language;
    } catch (error) {
        // Keep English; loadCatalog() below shows the error.
    }
    setLanguage(language);
    fillProviders();
    loadSettings();
    loadCatalog();
}

// DOMContentLoaded fires after every script at the end of the page has
// run, so all the functions above exist by then.
document.addEventListener("DOMContentLoaded", startApp);
