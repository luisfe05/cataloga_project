/** app.js: view switching, the sidebar project list, and app start. */

// data-folder of the New project button at the end of the list.
const NEW_PROJECT_OPTION = "__new__";

// Folder of the active project, so a click on it only opens Catalog.
let activeFolder = "";

function showView(name) {
    document.querySelectorAll(".view").forEach((view) => {
        view.classList.toggle("hidden", view.id !== `view-${name}`);
    });
    // In these two the header stays put and only the list scrolls.
    document.getElementById("app-main").classList
        .toggle("fixed-view", ["home", "catalog", "plan"].includes(name));
    document.getElementById("home-top").classList
        .toggle("hidden", !["home", "catalog"].includes(name));
    document.querySelectorAll("[data-home-tab]").forEach((tab) => {
        tab.classList.toggle("on", tab.dataset.homeTab === name);
    });
    document.getElementById("home-views").style.visibility =
        name === "home" ? "visible" : "hidden";
    if (name === "home") {
        loadHome();
    }
    document.querySelectorAll(".nav-link").forEach((link) => {
        link.classList.toggle("active", link.dataset.view === name);
    });
    // Load fresh numbers every time the dashboard is opened.
    if (name === "dashboard") {
        loadDashboard();
    }
    if (name === "plan") {
        loadPlan();
    }
    // The cards of the open tab drop into place. Settings never shows a
    // half-made new project: it reloads the saved one, or General alone.
    if (name === "settings") {
        if (projectMode === "new") {
            if (hasProjects) {
                loadSettings();
            } else {
                showSettingsTab("general", false);
            }
        } else {
            // Files read since Settings loaded must count in Folder Names.
            refreshFolderCounts();
        }
        dropSettingsCards();
    }
    if (name === "new") {
        dropSettingsCards();
    }
}

document.querySelectorAll("[data-home-tab]").forEach((tab) => {
    tab.addEventListener("click", () => showView(tab.dataset.homeTab));
});

document.querySelectorAll(".nav-link").forEach((link) => {
    link.addEventListener("click", (event) => {
        event.preventDefault();
        showView(link.dataset.view);
    });
});

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

/** Fill the sidebar project list and the Catalog title. Missing folders stay clickable. */
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

    const active = list.projects
        .find((project) => project.folder === activeFolder);
    const title = document.getElementById("catalog-title");
    title.textContent = active ? active.name : t("header.no_project");
    title.title = title.textContent;
    document.getElementById("home-title").textContent = title.textContent;
}

async function refreshAfterProjectChange() {
    // Answers about the old project must not mix with the new one.
    clearChat();
    await loadProjectHeader();
    await loadSettings();
    loadCatalog();
    resetHome();
    if (!document.getElementById("view-dashboard")
            .classList.contains("hidden")) {
        loadDashboard();
    }
}

/** Switch to a project and open Home, or open the New project form. */
async function chooseProject(folder) {
    if (folder === NEW_PROJECT_OPTION) {
        // Reset first, so the cards drop already empty.
        openNewProject();
        return;
    }
    // The active project is already loaded: just open Home.
    if (folder !== activeFolder) {
        try {
            await setActiveProject(folder);
        } catch (error) {
            showToolbarMessage(errorText(error), true);
        }
        await refreshAfterProjectChange();
    }
    showView("home");
}

// One listener for the list, because loadProjectHeader() redraws its buttons.
document.getElementById("project-list").addEventListener("click", (event) => {
    const button = event.target.closest(".project-link");
    if (button) {
        chooseProject(button.dataset.folder);
    }
});

/** Load the saved language, then show the login or the register screen. */
async function startApp() {
    let status = null;
    try {
        status = await getAuthStatus();
    } catch (error) {
        // Keep English; the login screen shows the error below.
    }
    setLanguage(status ? status.language : "en");
    termsVersion = status ? status.terms_version : "";
    fillProviders();
    showLoginScreen();
    // The first person on this computer has no account: the terms first.
    if (status && !status.account_exists) {
        openTermsDialog("new");
        return;
    }
    if (!status) {
        showAuthMessage("login-message", t("catalog.backend_down"));
    }
}

/** Show the app after login and draw every screen. */
function enterApp() {
    document.getElementById("auth-screen").classList.add("hidden");
    document.getElementById("nav-bar").classList.remove("hidden");
    document.getElementById("app-main").classList.remove("hidden");
    // A new session starts with a closed, empty chat (chat.js).
    clearChat();
    toggleChat(false);
    showView("home");
    loadProjectHeader();
    loadSettings();
    loadCatalog();
}

// DOMContentLoaded fires after every script has run, so all functions exist.
document.addEventListener("DOMContentLoaded", startApp);
