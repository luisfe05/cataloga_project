/**
 * auth.js
 *
 * The app's local account: one username and password for the whole
 * app (not per project).
 * - The first time, the account screen shows "Create your account".
 * - After that, it shows "Log in".
 * - Log out (in the nav bar) ends the session and shows "Log in" again.
 * - Settings has an Account section to change the password. The
 *   session stays open after the change.
 *
 * After 5 wrong passwords in a row, the backend refuses new tries for a
 * short time and says how many seconds are left.
 *
 * The session token is kept in api.js (sessionToken), only in memory.
 */

// Shortest password allowed, the same rule as backend/config/account.py.
const MIN_PASSWORD_LENGTH = 8;

/**
 * Show a message under one of the account forms.
 * @param {string} id - The message element's id.
 * @param {string} text - The message, or "" to clear it.
 * @param {string} [kind] - "error" (default) or "success".
 */
function showAuthMessage(id, text, kind = "error") {
    const message = document.getElementById(id);
    message.textContent = text;
    message.className = "form-message " + kind;
}

/**
 * Hide the app and show one of the two account forms.
 * @param {string} formId - "setup-form" or "login-form".
 */
function showAuthForm(formId) {
    document.getElementById("nav-bar").classList.add("hidden");
    document.getElementById("app-main").classList.add("hidden");
    // A dialog left open would stay on top of the login screen.
    const dialog = document.getElementById("remove-project-dialog");
    if (dialog.open) {
        dialog.close();
    }
    document.getElementById("auth-screen").classList.remove("hidden");
    ["setup-form", "login-form"].forEach((id) => {
        document.getElementById(id).classList.toggle("hidden", id !== formId);
    });
}

/**
 * Show the "Create your account" form (first time only).
 */
function showSetupScreen() {
    showAuthForm("setup-form");
    showAuthMessage("setup-message", "");
    document.getElementById("setup-username").focus();
}

/**
 * Show the "Log in" form. The password field is always emptied.
 * api.js also calls this when the backend answers 401 (no session).
 */
function showLoginScreen() {
    setSessionToken("");
    showAuthForm("login-form");
    document.getElementById("login-password").value = "";
    showAuthMessage("login-message", "");
    document.getElementById("login-username").focus();
}

/**
 * Return the message for a new password that breaks a rule, or "".
 * The backend checks the same rules again.
 * @param {string} password
 * @param {string} confirmation - The "Confirm password" field.
 * @returns {string}
 */
function newPasswordProblem(password, confirmation) {
    if (password.length < MIN_PASSWORD_LENGTH) {
        return t("error.password_too_short");
    }
    if (password !== confirmation) {
        return t("auth.password_mismatch");
    }
    return "";
}

/**
 * Create the account, then go into the app (already logged in).
 * @param {Event} event
 */
async function submitSetup(event) {
    // Stop the form from reloading the page.
    event.preventDefault();
    const username = document.getElementById("setup-username").value.trim();
    const password = document.getElementById("setup-password").value;
    const confirmation = document.getElementById("setup-confirm").value;
    if (!username) {
        showAuthMessage("setup-message", t("error.missing_field"));
        return;
    }
    const problem = newPasswordProblem(password, confirmation);
    if (problem) {
        showAuthMessage("setup-message", problem);
        return;
    }
    try {
        await setupAccount(username, password);
    } catch (error) {
        showAuthMessage("setup-message", errorText(error));
        return;
    }
    // The passwords are not needed anymore.
    document.getElementById("setup-password").value = "";
    document.getElementById("setup-confirm").value = "";
    enterApp();
}

/**
 * Check the username and password, then go into the app.
 * @param {Event} event
 */
async function submitLogin(event) {
    event.preventDefault();
    const username = document.getElementById("login-username").value.trim();
    const passwordField = document.getElementById("login-password");
    try {
        await logIn(username, passwordField.value);
    } catch (error) {
        passwordField.value = "";
        showAuthMessage("login-message", errorText(error));
        return;
    }
    passwordField.value = "";
    enterApp();
}

/**
 * End the session and go back to the login screen.
 */
async function submitLogout() {
    try {
        await logOut();
    } catch (error) {
        // The session is forgotten here anyway.
    }
    showLoginScreen();
}

/**
 * Change the password from Settings > Account. The session stays open.
 * @param {Event} event
 */
async function submitPasswordChange(event) {
    event.preventDefault();
    const fields = ["current-password", "new-password",
        "confirm-new-password"].map((id) => document.getElementById(id));
    const [current, newPassword, confirmation] =
        fields.map((field) => field.value);
    if (!current) {
        showAuthMessage("password-message", t("error.missing_field"));
        return;
    }
    const problem = newPasswordProblem(newPassword, confirmation);
    if (problem) {
        showAuthMessage("password-message", problem);
        return;
    }
    const button = document.getElementById("change-password-button");
    button.disabled = true;
    try {
        await changePassword(current, newPassword);
        fields.forEach((field) => {
            field.value = "";
        });
        showAuthMessage("password-message", t("account.password_changed"),
            "success");
    } catch (error) {
        showAuthMessage("password-message", errorText(error));
    } finally {
        button.disabled = false;
    }
}

document.getElementById("setup-form")
    .addEventListener("submit", submitSetup);
document.getElementById("login-form")
    .addEventListener("submit", submitLogin);
document.getElementById("logout-button")
    .addEventListener("click", submitLogout);
document.getElementById("password-form")
    .addEventListener("submit", submitPasswordChange);
