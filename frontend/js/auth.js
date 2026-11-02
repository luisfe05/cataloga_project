/** auth.js: accounts on this computer; the token lives only in memory. */

// Shortest password allowed, the same rule as backend/config/account.py.
const MIN_PASSWORD_LENGTH = 8;

function showAuthMessage(id, text, kind = "error") {
    const message = document.getElementById(id);
    message.textContent = text;
    message.className = "form-message " + kind;
}

function showAuthForm(formId) {
    document.getElementById("nav-bar").classList.add("hidden");
    document.getElementById("app-main").classList.add("hidden");
    // A dialog left open would stay on top of the login screen.
    const dialog = document.getElementById("remove-project-dialog");
    if (dialog.open) {
        dialog.close();
    }
    document.getElementById("auth-screen").classList.remove("hidden");
    ["register-form", "login-form"].forEach((id) => {
        document.getElementById(id).classList.toggle("hidden", id !== formId);
    });
}

/** Show the "Create an account" form. */
function showRegisterScreen() {
    showAuthForm("register-form");
    showAuthMessage("register-message", "");
    document.getElementById("register-username").focus();
}

/** Show the login form. api.js also calls this on a 401. */
function showLoginScreen() {
    setSessionToken("");
    showAuthForm("login-form");
    document.getElementById("login-password").value = "";
    document.getElementById("forgot-hint").classList.add("hidden");
    showAuthMessage("login-message", "");
    document.getElementById("login-username").focus();
}

/** Return the problem with a new password, or "". The backend checks it again. */
function newPasswordProblem(password, confirmation) {
    if (password.length < MIN_PASSWORD_LENGTH) {
        return t("error.password_too_short");
    }
    if (password !== confirmation) {
        return t("auth.password_mismatch");
    }
    return "";
}

/** Say under the field when the passwords differ. True when they match. */
function showConfirmProblem() {
    const confirmation = document.getElementById("register-confirm").value;
    const same = confirmation
        === document.getElementById("register-password").value;
    document.getElementById("register-confirm-message").textContent =
        same ? "" : t("auth.password_mismatch");
    return same;
}

/** Add the eye that shows or hides what was typed in a password field. */
function addPasswordEye(field) {
    const input = field.querySelector("input");
    const eye = document.createElement("button");
    eye.type = "button";
    eye.className = "password-eye";
    const icon = document.createElement("span");
    eye.appendChild(icon);
    const show = (visible) => {
        input.type = visible ? "text" : "password";
        icon.className = `icon ${visible ? "icon-eye-off" : "icon-eye"}`;
        eye.setAttribute("aria-label",
            t(visible ? "auth.hide_password" : "auth.show_password"));
    };
    eye.addEventListener("click", () => show(input.type === "password"));
    show(false);
    field.appendChild(eye);
}

/** Create an account, then go into the app (already logged in). */
async function submitRegister(event) {
    event.preventDefault();
    const username = document.getElementById("register-username").value.trim();
    const password = document.getElementById("register-password").value;
    const confirmation = document.getElementById("register-confirm").value;
    if (!username) {
        showAuthMessage("register-message", t("error.missing_field"));
        return;
    }
    if (!showConfirmProblem()) {
        return;
    }
    const problem = newPasswordProblem(password, confirmation);
    if (problem) {
        showAuthMessage("register-message", problem);
        return;
    }
    try {
        await registerAccount(username, password);
    } catch (error) {
        showAuthMessage("register-message", errorText(error));
        return;
    }
    // The passwords are not needed anymore.
    document.getElementById("register-password").value = "";
    document.getElementById("register-confirm").value = "";
    enterApp();
}

/** Check the username and password, then go into the app. */
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

async function submitLogout() {
    try {
        await logOut();
    } catch (error) {
        // The session is forgotten here anyway.
    }
    showLoginScreen();
}

/** Change the password from Settings > Account. The session stays open. */
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

document.getElementById("register-form")
    .addEventListener("submit", submitRegister);
document.getElementById("login-form")
    .addEventListener("submit", submitLogin);
document.querySelectorAll(".password-field").forEach(addPasswordEye);
// The message goes away as soon as the two match.
document.getElementById("register-confirm").addEventListener("input", () => {
    if (document.getElementById("register-confirm-message").textContent) {
        showConfirmProblem();
    }
});
document.getElementById("show-login-link")
    .addEventListener("click", showLoginScreen);
document.getElementById("show-register-link")
    .addEventListener("click", showRegisterScreen);
// The line stays visible until the login form is shown again.
document.getElementById("forgot-link").addEventListener("click", () => {
    document.getElementById("forgot-hint").classList.remove("hidden");
});
document.getElementById("logout-button")
    .addEventListener("click", submitLogout);
document.getElementById("password-form")
    .addEventListener("submit", submitPasswordChange);
