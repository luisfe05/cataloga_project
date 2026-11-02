/** plan.js: the Plan view. What the pipeline proposed, chosen and applied in batches. */

// The last answer of GET /plan, so filters work without asking again.
let planView = null;
let planTimer = null;

/** Folder path for the screen: "A / B", or the project folder. */
function planFolderLabel(place) {
    return place ? place.split("/").join(" / ") : t("plan.root");
}

/** The text of a row's action or status. */
function planLabel(prefix, value) {
    const key = `plan.${prefix}_${value}`;
    return key in LANG_EN ? t(key) : value;
}

function planMessage(text) {
    const message = document.getElementById("plan-message");
    message.textContent = text;
    message.classList.toggle("hidden", !text);
}

/** Show or hide the parts of the view that need a plan. */
function showPlanParts(visible) {
    ["plan-filters", "plan-table-wrap"].forEach((id) => {
        document.getElementById(id).classList.toggle("hidden", !visible);
    });
}

/** Read the three filters. */
function planFilters() {
    return {
        folder: document.getElementById("plan-filter-folder").value,
        action: document.getElementById("plan-filter-action").value,
        search: document.getElementById("plan-search").value.trim()
            .toLowerCase(),
    };
}

/** The rows that pass the filters: the journal rows, or the unchanged ones. */
function filteredPlanRows() {
    const filters = planFilters();
    let rows = planView.rows;
    if (filters.action === "none") {
        rows = planView.unchanged;
    } else if (filters.action === "review") {
        rows = rows.filter((row) => row.review);
    } else if (filters.action) {
        rows = rows.filter((row) => row.action === filters.action);
    }
    if (filters.folder) {
        rows = rows.filter((row) => row.new_folder === filters.folder);
    }
    if (filters.search) {
        rows = rows.filter((row) => [row.filename, row.old_name,
            row.new_name, row.old_folder, row.new_folder, row.why,
            row.summary].join(" ").toLowerCase().includes(filters.search));
    }
    return rows;
}

/** Fill the Destination filter with the folders rows go to. */
function fillPlanFolderFilter() {
    const select = document.getElementById("plan-filter-folder");
    const current = select.value;
    const folders = [...new Set(planView.rows.map((row) => row.new_folder)
        .filter(Boolean))].sort();
    select.innerHTML = "";
    const all = document.createElement("option");
    all.value = "";
    all.textContent = t("plan.filter_folder_all");
    select.appendChild(all);
    folders.forEach((folder) => {
        const option = document.createElement("option");
        option.value = folder;
        option.textContent = planFolderLabel(folder);
        select.appendChild(option);
    });
    select.value = folders.includes(current) ? current : "";
}

/** The folder dropdown of a row: every place of the tree. */
function planFolderSelect(row) {
    const select = document.createElement("select");
    select.className = "status-select";
    select.setAttribute("aria-label", t("plan.col_proposed"));
    const same = document.createElement("option");
    same.value = "";
    same.textContent = t("plan.same_folder");
    select.appendChild(same);
    planView.folders.forEach((place) => {
        const option = document.createElement("option");
        option.value = place;
        option.textContent = planFolderLabel(place);
        select.appendChild(option);
    });
    select.value = planView.folders.includes(row.new_folder)
        && row.new_folder !== row.old_folder ? row.new_folder : "";
    select.addEventListener("change", () => {
        savePlanEdit(row.id, { folder: select.value });
    });
    return select;
}

/** The name box of a row. Saved when it loses focus with a new value. */
function planNameInput(row) {
    const input = document.createElement("input");
    input.type = "text";
    input.value = row.new_name || "";
    input.setAttribute("aria-label", t("plan.col_name"));
    input.addEventListener("change", () => {
        if (input.value.trim() && input.value.trim() !== row.new_name) {
            savePlanEdit(row.id, { name: input.value.trim() });
        }
    });
    return input;
}

async function savePlanEdit(itemId, data) {
    try {
        const view = await editPlanItem(itemId, data);
        Object.assign(planView, view);
        renderPlan();
    } catch (error) {
        showToolbarMessage(errorText(error), true);
    }
}

/** Whether a row can still be chosen or edited. */
function planRowOpen(row) {
    return ["proposed", "approved", "skipped"].includes(row.status)
        && row.action !== "create_folder";
}

function renderPlanRows() {
    const body = document.getElementById("plan-rows");
    body.innerHTML = "";
    filteredPlanRows().forEach((row) => {
        const tr = document.createElement("tr");
        tr.dataset.id = row.id || "";
        if (row.status === "failed") {
            tr.classList.add("row-failed");
        }
        const check = document.createElement("td");
        if (planRowOpen(row)) {
            const box = document.createElement("input");
            box.type = "checkbox";
            box.className = "plan-check";
            box.value = row.id;
            box.setAttribute("aria-label", row.old_name || "");
            check.appendChild(box);
        }
        tr.appendChild(check);
        const file = makeCell(row.action === "create_folder"
            ? planLabel("action", "create_folder") : row.old_name, "nowrap");
        if (row.reason) {
            const note = document.createElement("p");
            note.className = "review-note";
            note.textContent = row.reason;
            file.appendChild(note);
        }
        tr.appendChild(file);
        tr.appendChild(makeCell(row.action === "create_folder" ? ""
            : planFolderLabel(row.old_folder), "nowrap"));
        const proposed = makeCell("", "nowrap");
        if (planRowOpen(row) && planView.folders.length) {
            proposed.appendChild(planFolderSelect(row));
        } else {
            proposed.textContent = row.new_folder === row.old_folder
                && row.action !== "create_folder" ? t("plan.same_folder")
                : planFolderLabel(row.new_folder);
        }
        tr.appendChild(proposed);
        const name = makeCell("", "plan-name");
        if (planRowOpen(row)) {
            name.appendChild(planNameInput(row));
        } else {
            name.textContent = row.action === "create_folder" ? ""
                : (row.new_name === row.old_name || !row.new_name
                    ? t("plan.keep_name") : row.new_name);
        }
        tr.appendChild(name);
        tr.appendChild(makeCell(row.why || row.review_note || "",
            "plan-why"));
        tr.appendChild(makeCell(row.confidence
            ? t(`catalog.confidence_${row.confidence}`) : "", "nowrap"));
        const status = makeCell(planLabel("status", row.status),
            row.review ? "nowrap status-review" : "nowrap");
        tr.appendChild(status);
        body.appendChild(tr);
    });
    document.getElementById("plan-check-all").checked = false;
}

/** The ids of the checked rows. */
function checkedPlanIds() {
    return [...document.querySelectorAll(".plan-check:checked")]
        .map((box) => Number(box.value));
}

function renderPlanSummary() {
    const counts = planView.summary;
    document.getElementById("plan-summary").textContent =
        t("plan.summary", { files: counts.files_read, moves: counts.moves,
            renames: counts.renames, folders: counts.new_folders })
        + " " + t("plan.summary_unchanged", { n: counts.unchanged });
}

/** A batch being applied, undone or paused: progress and its buttons. */
function renderPlanProgress(batch, counts) {
    const box = document.getElementById("plan-progress");
    const resume = document.getElementById("plan-resume");
    const undo = document.getElementById("plan-undo");
    if (!batch) {
        box.classList.add("hidden");
        return;
    }
    const total = counts.approved + counts.pending + counts.applied
        + counts.failed + counts.undone;
    const vars = { done: counts.applied, total: total, failed: counts.failed,
        note: planNote(batch.note) };
    let text;
    if (batch.status === "applying") {
        text = t("plan.applying", vars);
    } else if (batch.status === "undoing") {
        text = t("plan.undoing", { done: counts.undone, total: total });
    } else if (batch.status === "paused") {
        text = t("plan.paused", vars);
    } else {
        text = t("plan.applied", vars);
    }
    document.getElementById("plan-progress-text").textContent = text;
    resume.classList.toggle("hidden", batch.status !== "paused");
    undo.classList.toggle("hidden",
        !["applied", "paused"].includes(batch.status));
    resume.dataset.batch = batch.id;
    undo.dataset.batch = batch.id;
    box.classList.remove("hidden");
}

/** The pause note in the user's language. */
function planNote(note) {
    if (!note) {
        return "";
    }
    if (note.startsWith("The project folder")) {
        return t("plan.note_disk");
    }
    if (note.startsWith("The app closed")) {
        return t("plan.note_interrupted");
    }
    return note;
}

function renderPlanBatches() {
    const section = document.getElementById("plan-batches");
    const list = document.getElementById("plan-batch-list");
    list.innerHTML = "";
    const batches = planView.batches || [];
    section.classList.toggle("hidden", batches.length === 0);
    batches.forEach((batch) => {
        const item = document.createElement("li");
        if (batch.origin === "watch") {
            const label = document.createElement("span");
            label.className = "batch-label";
            label.textContent = t("plan.filed_without_asking");
            item.appendChild(label);
        }
        const text = document.createElement("span");
        const counts = batch.summary;
        text.textContent = t("plan.batch_line", { id: batch.id,
            date: (batch.applied_at || batch.created).replace("T", " "),
            applied: counts.applied, failed: counts.failed,
            undone: counts.undone })
            + (batch.status === "paused"
                ? " " + t("plan.paused", { note: planNote(batch.note),
                    done: counts.applied,
                    total: counts.applied + counts.approved + counts.failed })
                : "");
        item.appendChild(text);
        if (["applied", "paused"].includes(batch.status)) {
            const undo = document.createElement("button");
            undo.type = "button";
            undo.className = "pill-button";
            undo.textContent = t("plan.undo");
            undo.addEventListener("click", () => runPlanAction("undo",
                batch.id, "plan.undo_started"));
            item.appendChild(undo);
        }
        list.appendChild(item);
    });
}

function renderPlan() {
    renderPlanSummary();
    fillPlanFolderFilter();
    renderPlanRows();
    renderPlanBatches();
    const running = (planView.batches || []).find((batch) =>
        ["applying", "undoing", "paused"].includes(batch.status));
    renderPlanProgress(running || null, running ? running.summary : null);
    if (!planView.rows.length) {
        planMessage(t("plan.empty"));
    } else {
        planMessage("");
    }
    // The table and the buttons wait while a batch runs.
    document.querySelectorAll("#plan-filters .toolbar button")
        .forEach((button) => { button.disabled = Boolean(planView.busy); });
}

async function loadPlan() {
    clearTimeout(planTimer);
    try {
        const view = await getPlan();
        if (view.message) {
            planView = null;
            showPlanParts(false);
            document.getElementById("plan-summary").textContent = "";
            document.getElementById("plan-batches").classList.add("hidden");
            document.getElementById("plan-progress").classList.add("hidden");
            planMessage(view.mode === "catalog" ? t("plan.catalog_only")
                : t("plan.no_plan"));
            return;
        }
        planView = view;
        showPlanParts(true);
        renderPlan();
        if (view.busy) {
            // A batch is running: ask again in a second.
            planTimer = setTimeout(loadPlan, 1000);
        }
    } catch (error) {
        planMessage(t("plan.load_failed"));
    }
}

async function choosePlan(data) {
    try {
        const view = await choosePlanItems(data);
        Object.assign(planView, view);
        renderPlan();
        showToolbarMessage(t("plan.approved_count",
            { n: planView.summary.approved }));
    } catch (error) {
        showToolbarMessage(errorText(error), true);
    }
}

async function runPlanAction(action, batchId, messageKey) {
    try {
        await runPlan(action, batchId);
        showToolbarMessage(t(messageKey));
        planTimer = setTimeout(loadPlan, 500);
    } catch (error) {
        showToolbarMessage(errorText(error), true);
    }
}

document.getElementById("plan-approve-all").addEventListener("click", () => {
    choosePlan({ status: "approved", all: true });
});
document.getElementById("plan-approve-selected").addEventListener("click",
    () => choosePlan({ status: "approved", ids: checkedPlanIds() }));
document.getElementById("plan-skip-selected").addEventListener("click",
    () => choosePlan({ status: "skipped", ids: checkedPlanIds() }));
document.getElementById("plan-apply").addEventListener("click", () => {
    runPlanAction("apply", null, "plan.started");
});
document.getElementById("plan-resume").addEventListener("click", (event) => {
    runPlanAction("resume", Number(event.target.dataset.batch),
        "plan.started");
});
document.getElementById("plan-undo").addEventListener("click", (event) => {
    runPlanAction("undo", Number(event.target.dataset.batch),
        "plan.undo_started");
});
document.getElementById("plan-check-all").addEventListener("change",
    (event) => {
        document.querySelectorAll(".plan-check").forEach((box) => {
            box.checked = event.target.checked;
        });
    });
["plan-filter-folder", "plan-filter-action"].forEach((id) => {
    document.getElementById(id).addEventListener("change", renderPlanRows);
});
document.getElementById("plan-search").addEventListener("input",
    renderPlanRows);
