/** auth.js: accounts on this computer; the token lives only in memory. */

// Shortest password allowed, the same rule as backend/config/account.py.
const MIN_PASSWORD_LENGTH = 8;

// The terms version the server asks for (GET /auth/status).
let termsVersion = "";
// The terms dialog says yes before a new account, or after a login.
let termsMode = "new";
// The key on screen: who it is for, and the one-time ticket to save it.
let recoveryShown = { username: "", ticket: "" };
// What happens after the recovery key dialog closes.
let afterRecovery = null;

function showAuthMessage(id, text, kind = "error") {
    const message = document.getElementById(id);
    message.textContent = text;
    message.className = "form-message " + kind;
}

function showAuthForm(formId) {
    showLoginLanguage();
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

/** Show the "Create an account" form, after the terms were accepted. */
function showRegisterScreen() {
    showAuthForm("register-form");
    showAuthMessage("register-message", "");
    document.getElementById("register-username").focus();
}

/** Open the Terms and Privacy dialog: "new" before an account, "update" after a login. */
function openTermsDialog(mode) {
    termsMode = mode;
    const check = document.getElementById("terms-agree");
    check.checked = false;
    const accept = document.getElementById("terms-accept");
    accept.disabled = true;
    accept.textContent = t(mode === "new" ? "terms.accept_new"
        : "terms.accept_update");
    document.getElementById("terms-title").textContent =
        t(mode === "new" ? "terms.title" : "terms.title_update");
    document.getElementById("terms-dialog").showModal();
}

/** Open a legal page in the dialog, inside the app and without internet. */
function openLegalPage(href) {
    const dialog = document.getElementById("legal-dialog");
    const frame = document.getElementById("legal-frame");
    const title = t(href.includes("privacy") ? "legal.privacy"
        : "legal.terms");
    document.getElementById("legal-dialog-title").textContent = title;
    frame.title = title;
    frame.src = href;
    dialog.showModal();
}

/** Every "legal/..." link, on the login, the overlay and Settings. */
document.addEventListener("click", (event) => {
    const link = event.target.closest("a.legal-link");
    if (!link) {
        return;
    }
    event.preventDefault();
    openLegalPage(link.getAttribute("href"));
});

document.getElementById("legal-close").addEventListener("click", () => {
    document.getElementById("legal-dialog").close();
});

/** The box is checked: create the account form, or accept and go in. */
async function acceptTermsDialog() {
    const dialog = document.getElementById("terms-dialog");
    if (termsMode === "new") {
        dialog.close();
        showRegisterScreen();
        return;
    }
    try {
        await acceptTerms(termsVersion);
    } catch (error) {
        return;
    }
    dialog.close();
    enterApp();
}

/** Show a recovery key with Save now and Later; then() runs when it closes. */
function showRecoveryKey(username, key, ticket, then) {
    recoveryShown = { username: username, ticket: ticket };
    afterRecovery = then;
    document.getElementById("recovery-key").textContent = key;
    document.getElementById("recovery-ways").innerHTML = "";
    ["recovery.way_save", "recovery.way_later"].forEach((textKey) => {
        const line = document.createElement("span");
        line.textContent = t(textKey, { file: recoveryFileName(username) });
        document.getElementById("recovery-ways").appendChild(line);
    });
    showAuthMessage("recovery-message", "");
    document.getElementById("recovery-dialog").showModal();
}

/** The file name the Save window starts with. */
function recoveryFileName(username) {
    return `Cataloga Recovery Key - ${username}.txt`;
}

/** Close the key dialog and go on (into the app, or back to Settings). */
function closeRecoveryKey() {
    document.getElementById("recovery-dialog").close();
    const then = afterRecovery;
    afterRecovery = null;
    if (then) {
        then();
    }
}

/** Save now: the Mac's Save window, then the server writes the file. */
async function saveRecoveryNow() {
    const api = window.pywebview && window.pywebview.api;
    if (!api || !api.choose_recovery_file) {
        showAuthMessage("recovery-message", t("recovery.no_window"));
        return;
    }
    const path = await api.choose_recovery_file(recoveryShown.username);
    if (!path) {
        // The Save window was closed: the key is still on screen.
        return;
    }
    try {
        await saveRecoveryFile(path, recoveryShown.ticket);
    } catch (error) {
        // Inside a project: the dialog stays open to choose another place.
        showAuthMessage("recovery-message", errorText(error));
        return;
    }
    closeRecoveryKey();
}

/** Copy the key on screen. */
async function copyRecoveryKey() {
    const key = document.getElementById("recovery-key").textContent;
    try {
        await navigator.clipboard.writeText(key);
        showAuthMessage("recovery-message", t("recovery.copied"), "success");
    } catch (error) {
        showAuthMessage("recovery-message", t("recovery.copy_failed"));
    }
}

/** Forgot your password: the username and the recovery key. */
function openForgotDialog() {
    const form = document.getElementById("forgot-form");
    form.reset();
    document.getElementById("forgot-username").value =
        document.getElementById("login-username").value.trim();
    showAuthMessage("forgot-message", "");
    document.getElementById("forgot-dialog").showModal();
    document.getElementById(document.getElementById("forgot-username").value
        ? "forgot-key" : "forgot-username").focus();
}

/** Reset the password, then show the new key; the old one stops working. */
async function submitForgot(event) {
    event.preventDefault();
    const username = document.getElementById("forgot-username").value.trim();
    const key = document.getElementById("forgot-key").value.trim();
    const password = document.getElementById("forgot-password").value;
    const confirmation = document.getElementById("forgot-confirm").value;
    if (!username || !key) {
        showAuthMessage("forgot-message", t("error.missing_field"));
        return;
    }
    const problem = newPasswordProblem(password, confirmation);
    if (problem) {
        showAuthMessage("forgot-message", problem);
        return;
    }
    let answer;
    try {
        answer = await resetPassword(username, key, password);
    } catch (error) {
        showAuthMessage("forgot-message", errorText(error));
        return;
    }
    document.getElementById("forgot-form").reset();
    document.getElementById("forgot-dialog").close();
    showRecoveryKey(answer.username, answer.recovery_key, answer.save_ticket,
        () => goInAfterLogin(answer.terms_ok));
}

/** After a login or a reset: the terms first if they changed, then the app. */
function goInAfterLogin(termsOk) {
    if (termsOk === false) {
        openTermsDialog("update");
        return;
    }
    enterApp();
}

/** The EN / ES switch on the login screen. */
function showLoginLanguage() {
    document.querySelectorAll("[data-login-lang]").forEach((button) => {
        button.setAttribute("aria-pressed",
            String(button.dataset.loginLang === currentLanguage));
    });
}

/** Show the login form. api.js also calls this on a 401. */
function showLoginScreen() {
    setSessionToken("");
    showAuthForm("login-form");
    document.getElementById("login-password").value = "";
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
    let answer;
    try {
        answer = await registerAccount(username, password, termsVersion);
    } catch (error) {
        showAuthMessage("register-message", errorText(error));
        return;
    }
    // The passwords are not needed anymore.
    document.getElementById("register-password").value = "";
    document.getElementById("register-confirm").value = "";
    // The key is shown once now; later it needs the password.
    showRecoveryKey(answer.username, answer.recovery_key, answer.save_ticket,
        enterApp);
}

/** Check the username and password, then go into the app. */
async function submitLogin(event) {
    event.preventDefault();
    const username = document.getElementById("login-username").value.trim();
    const passwordField = document.getElementById("login-password");
    let answer;
    try {
        answer = await logIn(username, passwordField.value);
    } catch (error) {
        passwordField.value = "";
        showAuthMessage("login-message", errorText(error));
        return;
    }
    passwordField.value = "";
    goInAfterLogin(answer.terms_ok);
}

/** Leave the app: a reload empties the memory of every view and the chat. */
function leaveApp() {
    // The token is only in memory, so the reload also forgets it.
    setSessionToken("");
    window.location.reload();
}

async function submitLogout() {
    try {
        await logOut();
    } catch (error) {
        // The session is forgotten here anyway.
    }
    leaveApp();
}

// Settings > Account: which button asked for the password ("current" or "new").
let recoveryWanted = "current";

/** "Not saved yet" or "Saved on <date>", under Recovery key. */
async function loadRecoveryStatus() {
    const line = document.getElementById("recovery-status");
    try {
        const status = await getRecoveryStatus();
        line.textContent = status.saved
            ? t("recovery.saved_on", { date: status.saved })
            : t("recovery.not_saved");
    } catch (error) {
        line.textContent = "";
    }
}

/** Save current key or Get a new key: first the password. */
function askRecoveryPassword(wanted) {
    recoveryWanted = wanted;
    document.getElementById("recovery-confirm").classList.remove("hidden");
    showAuthMessage("recovery-confirm-message", "");
    const field = document.getElementById("recovery-password");
    field.value = "";
    field.focus();
}

/** Check the password, then show the key with Save now and Later. */
async function continueRecovery() {
    const field = document.getElementById("recovery-password");
    if (!field.value) {
        showAuthMessage("recovery-confirm-message", t("error.missing_field"));
        return;
    }
    let answer;
    try {
        answer = await getRecoveryKey(field.value, recoveryWanted === "new");
    } catch (error) {
        showAuthMessage("recovery-confirm-message", errorText(error));
        return;
    }
    field.value = "";
    document.getElementById("recovery-confirm").classList.add("hidden");
    const username = document.getElementById("account-username").value;
    showRecoveryKey(username, answer.recovery_key, answer.save_ticket,
        loadRecoveryStatus);
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
// A new account starts with the Terms and Privacy.
document.getElementById("show-register-link")
    .addEventListener("click", () => openTermsDialog("new"));
document.getElementById("terms-agree").addEventListener("change", (event) => {
    document.getElementById("terms-accept").disabled = !event.target.checked;
});
document.getElementById("terms-accept")
    .addEventListener("click", acceptTermsDialog);
document.getElementById("terms-cancel").addEventListener("click", () => {
    document.getElementById("terms-dialog").close();
    // Saying no after a login leaves the app.
    if (termsMode === "update") {
        submitLogout();
    }
});
document.getElementById("forgot-link")
    .addEventListener("click", openForgotDialog);
document.getElementById("forgot-form")
    .addEventListener("submit", submitForgot);
document.getElementById("forgot-back").addEventListener("click", () => {
    document.getElementById("forgot-dialog").close();
});
document.getElementById("recovery-save")
    .addEventListener("click", saveRecoveryNow);
document.getElementById("recovery-later")
    .addEventListener("click", closeRecoveryKey);
document.getElementById("recovery-copy")
    .addEventListener("click", copyRecoveryKey);
// Esc closes the key dialog the same way as Later.
document.getElementById("recovery-dialog").addEventListener("cancel",
    (event) => {
        event.preventDefault();
        closeRecoveryKey();
    });
document.querySelectorAll("[data-login-lang]").forEach((button) => {
    button.addEventListener("click", () => {
        setLanguage(button.dataset.loginLang);
        showLoginLanguage();
    });
});
document.getElementById("logout-button")
    .addEventListener("click", submitLogout);
document.getElementById("password-form")
    .addEventListener("submit", submitPasswordChange);
document.getElementById("recovery-current")
    .addEventListener("click", () => askRecoveryPassword("current"));
document.getElementById("recovery-new")
    .addEventListener("click", () => askRecoveryPassword("new"));
document.getElementById("recovery-continue")
    .addEventListener("click", continueRecovery);
// Enter in this field must not send the Change password form.
document.getElementById("recovery-password").addEventListener("keydown",
    (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            continueRecovery();
        }
    });
