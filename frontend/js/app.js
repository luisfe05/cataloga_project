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
 * The project list in the sidebar lives here too, because it changes
 * what every view shows.
 */

// data-folder of the New project button at the end of the list.
const NEW_PROJECT_OPTION = "__new__";

// Folder of the active project, so a click on it only opens Catalog.
let activeFolder = "";

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
 * Make one button of the project list.
 * @param {string} text - What the button says.
 * @param {string} folder - Project folder, or NEW_PROJECT_OPTION.
 * @param {string} title - Tooltip with the full text.
 * @returns {HTMLLIElement}
 */
function makeProjectButton(text, folder, title) {
    const item = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "project-link";
    button.dataset.folder = folder;
    button.textContent = text;
    button.title = title;
    item.appendChild(button);
    return item;
}

/**
 * Fill the project list in the sidebar and the title of Catalog.
 * Projects whose folder is missing (for example, an external drive that
 * is not connected) are dimmed and marked as not available. They can
 * still be opened, so they can be removed in Settings.
 * Called again after a language change, so the text is redrawn.
 */
async function loadProjectHeader() {
    let list;
    try {
        list = await getProjects();
    } catch (error) {
        return;
    }
    activeFolder = list.active_folder || "";
    const projectList = document.getElementById("project-list");
    projectList.innerHTML = "";
    if (list.projects.length === 0) {
        const empty = document.createElement("li");
        empty.className = "project-empty";
        empty.textContent = t("header.no_project");
        projectList.appendChild(empty);
    }
    list.projects.forEach((project) => {
        const item = project.available
            ? makeProjectButton(project.name, project.folder, project.name)
            : makeProjectButton(
                t("header.unavailable", { name: project.name }),
                project.folder,
                `${project.name}. ${t("header.unavailable_hint")}`);
        const button = item.firstChild;
        button.classList.toggle("unavailable", !project.available);
        if (project.folder === activeFolder) {
            button.classList.add("active");
            button.setAttribute("aria-current", "true");
        }
        projectList.appendChild(item);
    });
    const newText = t("header.new_project");
    const newItem = makeProjectButton(newText, NEW_PROJECT_OPTION, newText);
    newItem.firstChild.classList.add("new-project");
    projectList.appendChild(newItem);

    // The Catalog title shows the active project's name.
    const active = list.projects
        .find((project) => project.folder === activeFolder);
    const title = document.getElementById("catalog-title");
    title.textContent = active ? active.name : t("header.no_project");
    title.title = title.textContent;
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
 * Handle a click in the project list: switch to that project and open
 * Catalog, or open the New project form in Settings.
 * @param {string} folder - Project folder, or NEW_PROJECT_OPTION.
 */
async function chooseProject(folder) {
    if (folder === NEW_PROJECT_OPTION) {
        showView("settings");
        startNewProject();
        return;
    }
    // The active project is already loaded: just open Catalog.
    if (folder !== activeFolder) {
        try {
            await setActiveProject(folder);
        } catch (error) {
            showToolbarMessage(errorText(error), true);
        }
        await refreshAfterProjectChange();
    }
    showView("catalog");
}

// One listener for the whole list, because its buttons are redrawn
// every time loadProjectHeader() runs.
document.getElementById("project-list").addEventListener("click", (event) => {
    const button = event.target.closest(".project-link");
    if (button) {
        chooseProject(button.dataset.folder);
    }
});

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
