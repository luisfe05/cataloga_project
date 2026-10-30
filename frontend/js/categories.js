/** categories.js: Industry and the project's category list in Settings. Saved with Save. */

// Same as MAX_CATEGORIES in archive_rules.py.
const MAX_CATEGORIES = 10;

/** One editable row: category name, its subcategories separated by commas, and Remove. */
function makeCategoryRow(category) {
    const row = document.createElement("div");
    row.className = "category-row";

    const name = document.createElement("input");
    name.type = "text";
    name.className = "category-name";
    name.value = category.name;
    name.placeholder = t("categories.name_placeholder");
    name.setAttribute("aria-label", t("categories.name_placeholder"));

    const subcategories = document.createElement("input");
    subcategories.type = "text";
    subcategories.className = "category-subs";
    subcategories.value = category.subcategories.join(", ");
    subcategories.placeholder = t("categories.subs_placeholder");
    subcategories.setAttribute("aria-label", t("categories.subs_placeholder"));

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "category-remove";
    remove.textContent = "×";
    remove.setAttribute("aria-label", t("categories.remove"));
    remove.addEventListener("click", () => {
        row.remove();
        updateAddCategoryButton();
    });

    row.append(name, subcategories, remove);
    return row;
}

/** Only 10 categories, so Add is off at the limit. */
function updateAddCategoryButton() {
    const count = document.querySelectorAll("#category-list .category-row")
        .length;
    document.getElementById("add-category").disabled =
        count >= MAX_CATEGORIES;
}

/** Fill the section with the saved industry and categories. */
function showCategories(industry, categories) {
    document.getElementById("industry").value = industry || "";
    const list = document.getElementById("category-list");
    list.innerHTML = "";
    categories.forEach((category) => {
        list.appendChild(makeCategoryRow(category));
    });
    document.getElementById("categories-message").textContent = "";
    updateAddCategoryButton();
}

/** Read the rows as [{ name, subcategories }]. Rows without a name are skipped. */
function readCategories() {
    const categories = [];
    document.querySelectorAll("#category-list .category-row")
        .forEach((row) => {
            const name = row.querySelector(".category-name").value.trim();
            if (!name) {
                return;
            }
            const subcategories = row.querySelector(".category-subs").value
                .split(",").map((sub) => sub.trim()).filter(Boolean);
            categories.push({ name: name, subcategories: subcategories });
        });
    return categories;
}

/** Ask the AI for categories. They replace the list, but nothing is saved until Save. */
async function suggestProjectCategories() {
    const industry = document.getElementById("industry").value.trim();
    const message = document.getElementById("categories-message");
    const button = document.getElementById("suggest-categories");
    if (!industry) {
        message.textContent = t("categories.need_industry");
        message.className = "form-message error";
        return;
    }
    button.disabled = true;
    message.textContent = t("categories.suggesting");
    message.className = "form-message";
    try {
        const result = await suggestCategories(industry);
        showCategories(industry, result.categories);
        message.textContent = t("categories.suggested");
        message.className = "form-message success";
    } catch (error) {
        message.textContent = errorText(error);
        message.className = "form-message error";
    } finally {
        button.disabled = false;
    }
}

document.getElementById("suggest-categories")
    .addEventListener("click", suggestProjectCategories);

document.getElementById("add-category").addEventListener("click", () => {
    const row = makeCategoryRow({ name: "", subcategories: [] });
    document.getElementById("category-list").appendChild(row);
    row.querySelector(".category-name").focus();
    updateAddCategoryButton();
});
