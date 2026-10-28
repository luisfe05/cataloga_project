/** i18n.js: texts by language. Load after lang/*.js and before the other scripts. */

// Every language the app offers, by the code saved in app_config.
const LANGUAGES = { en: LANG_EN, es: LANG_ES };

// The language in use. English until the saved choice is loaded.
let currentLanguage = "en";

/** Text for a key in the current language; falls back to English, then to the key. */
function t(key, vars = {}) {
    let text = LANGUAGES[currentLanguage][key];
    if (text === undefined) {
        text = LANG_EN[key];
    }
    if (text === undefined) {
        return key;
    }
    // Replace each {name} with its value, e.g. {n} with 3.
    Object.keys(vars).forEach((name) => {
        text = text.split(`{${name}}`).join(String(vars[name]));
    });
    return text;
}

/** On-screen label of a stored value, like "Press". The stored value never changes. */
function valueLabel(stored) {
    const key = `value.${stored}`;
    return key in LANG_EN ? t(key) : stored;
}

/** Error message in the current language. The backend's English message is not shown. */
function errorText(error) {
    if (!error || !error.code) {
        return t("catalog.backend_down");
    }
    const key = `error.${error.code}`;
    if (!(key in LANG_EN)) {
        return t("error.generic");
    }
    // Some errors send count, path, or retry_after.
    return t(key, {
        n: error.count, path: error.path, seconds: error.retry_after,
    });
}

/** Fill every element marked with data-i18n or data-i18n-placeholder. */
function applyTranslations() {
    document.documentElement.lang = currentLanguage;
    document.querySelectorAll("[data-i18n]").forEach((element) => {
        element.textContent = t(element.dataset.i18n);
    });
    document.querySelectorAll("[data-i18n-placeholder]")
        .forEach((element) => {
            element.placeholder = t(element.dataset.i18nPlaceholder);
        });
}

/** Switch the language and translate the page. Unknown codes fall back to English. */
function setLanguage(language) {
    currentLanguage = language in LANGUAGES ? language : "en";
    applyTranslations();
}
