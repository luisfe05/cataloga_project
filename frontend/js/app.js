/**
 * app.js
 *
 * Switches between the three views (Catalog, Dashboard, Settings) when a
 * link in the navigation bar is clicked. Only one view is visible at a
 * time; the others get the "hidden" class.
 *
 * Also starts the app: startApp() reads the saved language first, so
 * every screen is drawn in that language from the start.
 *
 * The project dropdown in the header lives here too, because it changes
 * what every view shows.
 */

// Value of the last option in the project dropdown.
const NEW_PROJECT_OPTION = "__new__";

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
 * Fill the project dropdown and the round badge in the header.
 * Projects whose folder is missing (for example, an external drive that
 * is not connected) are marked as not available.
 */
async function loadProjectHeader() {
    let list;
    try {
        list = await getProjects();
    } catch (error) {
        return;
    }
    const select = document.getElementById("project-select");
    select.innerHTML = "";
    if (list.projects.length === 0) {
        const empty = document.createElement("option");
        empty.value = "";
        empty.textContent = t("header.no_project");
        select.appendChild(empty);
    }
    list.projects.forEach((project) => {
        const option = document.createElement("option");
        option.value = project.folder;
        option.textContent = project.available ? project.name
            : t("header.unavailable", { name: project.name });
        select.appendChild(option);
    });
    const newOption = document.createElement("option");
    newOption.value = NEW_PROJECT_OPTION;
    newOption.textContent = t("header.new_project");
    select.appendChild(newOption);
    select.value = list.active_folder;

    const active = list.projects
        .find((project) => project.folder === list.active_folder);
    // The circle shows the first letter of the project name.
    document.getElementById("project-badge").textContent = active
        ? active.name.charAt(0).toUpperCase() : "";
}

/**
 * Redraw everything after the active project changed.
 */
async function refreshAfterProjectChange() {
    await loadProjectHeader();
    await loadSettings();
    loadCatalog();
    if (!document.getElementById("view-dashboard")
            .classList.contains("hidden")) {
        loadDashboard();
    }
}

/**
 * Handle a choice in the project dropdown: switch to that project, or
 * open the New project form in Settings.
 */
async function chooseProject() {
    const select = document.getElementById("project-select");
    if (select.value === NEW_PROJECT_OPTION) {
        // Put the dropdown back on the active project until the new one
        // is created.
        await loadProjectHeader();
        showView("settings");
        startNewProject();
        return;
    }
    try {
        await setActiveProject(select.value);
    } catch (error) {
        showToolbarMessage(errorText(error), true);
    }
    await refreshAfterProjectChange();
}

document.getElementById("project-select")
    .addEventListener("change", chooseProject);

/**
 * Load the saved language, then show the account screen: create the
 * account the first time, log in after that (see auth.js).
 * GET /auth/status works without logging in. If the backend does not
 * answer, the app starts in English and the login screen says so.
 */
async function startApp() {
    let status = null;
    try {
        status = await getAuthStatus();
    } catch (error) {
        // Keep English; the login screen shows the error below.
    }
    setLanguage(status ? status.language : "en");
    fillProviders();
    if (status && !status.account_exists) {
        showSetupScreen();
        return;
    }
    showLoginScreen();
    if (!status) {
        showAuthMessage("login-message", t("catalog.backend_down"));
    }
}

/**
 * Show the app after a successful login or account setup, and draw
 * every screen with the active project's data.
 */
function enterApp() {
    document.getElementById("auth-screen").classList.add("hidden");
    document.getElementById("nav-bar").classList.remove("hidden");
    document.getElementById("app-main").classList.remove("hidden");
    showView("catalog");
    loadProjectHeader();
    loadSettings();
    loadCatalog();
}

// DOMContentLoaded fires after every script at the end of the page has
// run, so all the functions above exist by then.
document.addEventListener("DOMContentLoaded", startApp);
