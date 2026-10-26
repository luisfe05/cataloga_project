/**
 * i18n.js
 *
 * Picks the text for the current language. Load it after lang/en.js and
 * lang/es.js, and before the other scripts.
 *
 * Fixed text in index.html is marked with data-i18n="key" (the element's
 * text) or data-i18n-placeholder="key" (an input's placeholder), and
 * applyTranslations() fills them in.
 */

// Every language the app offers, by the code saved in app_config.
const LANGUAGES = { en: LANG_EN, es: LANG_ES };

// The language in use. English until the saved choice is loaded.
let currentLanguage = "en";

/**
 * Return the text for a key in the current language.
 * If the key is missing in that language, the English text is used, and
 * if it is missing there too, the key itself is shown so it is easy to
 * spot.
 * @param {string} key - For example "catalog.tab_review".
 * @param {Object} [vars] - Values for the words in braces, e.g. {n: 3}.
 * @returns {string}
 */
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

/**
 * Return the on-screen label of a value stored in the database, like
 * "Press" or "Manual Review". The stored value never changes.
 * @param {string} stored
 * @returns {string}
 */
function valueLabel(stored) {
    const key = `value.${stored}`;
    return key in LANG_EN ? t(key) : stored;
}

/**
 * Return the message for an error from api.js, in the current language.
 * The backend's own message stays in English and is not shown.
 * @param {Object} error - {code, message, ...}. A network failure has no
 *     code.
 * @returns {string}
 */
function errorText(error) {
    if (!error || !error.code) {
        return t("catalog.backend_down");
    }
    const key = `error.${error.code}`;
    if (!(key in LANG_EN)) {
        return t("error.generic");
    }
    // count and path are sent by the backend for some errors, like
    // folder_not_empty and project_unavailable.
    return t(key, { n: error.count, path: error.path });
}

/**
 * Fill every element marked with data-i18n or data-i18n-placeholder.
 */
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

/**
 * Switch the language and translate the fixed text on the page.
 * Unknown codes fall back to English.
 * @param {string} language - "en" or "es".
 */
function setLanguage(language) {
    currentLanguage = language in LANGUAGES ? language : "en";
    applyTranslations();
}
