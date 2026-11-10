/** plan.js: To Approve. What the pipeline proposed, chosen and applied in batches. */

// The last answer of GET /plan, so filters work without asking again.
let planView = null;
let planTimer = null;
let planTab = "files";
// Which changes show: all, rename, move or skipped.
let planShow = "all";

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

/** Show one panel of the Plan: only that part scrolls. */
function showPlanTab(name) {
    planTab = name || planTab;
    const panels = { files: ["plan-filters", "plan-table-wrap"],
        folders: ["plan-folders"], batches: ["plan-batches"] };
    // The tab the list is on is not offered as a link.
    Object.keys(panels).forEach((tab) => {
        panels[tab].forEach((id) => {
            document.getElementById(id).classList
                .toggle("hidden", tab !== name);
        });
    });
    document.querySelectorAll("[data-plan-tab]").forEach((button) => {
        button.classList.toggle("hidden", button.dataset.planTab === name);
    });
}

/** Show or hide the parts of the view that need a plan. */
function showPlanParts(visible) {
    document.getElementById("plan-tabs").classList.toggle("hidden", !visible);
    document.getElementById("plan-actions").classList
        .toggle("hidden", !visible);
    showPlanTab(visible ? planTab : "");
}

/** The rows that change a file: renames, moves, or both. */
function changeRows() {
    return planView.rows.filter((row) => row.document_id
        && row.action !== "create_folder");
}

/** Does a row rename its file? Does it move it? */
function renamesFile(row) {
    return ["rename", "move_rename"].includes(row.action);
}

function movesFile(row) {
    return ["move", "move_rename"].includes(row.action);
}

/** The rows of the chosen view: all, renames, moves, or skipped. */
function filteredPlanRows() {
    const rows = changeRows();
    if (planShow === "rename") {
        return rows.filter(renamesFile);
    }
    if (planShow === "move") {
        return rows.filter(movesFile);
    }
    if (planShow === "skipped") {
        return rows.filter((row) => row.status === "skipped");
    }
    return rows;
}

/** "All 30", "Renames 18", "Moves 12", "Skipped 1" on the four buttons. */
function renderPlanShow() {
    const rows = changeRows();
    const counts = { all: rows.length, rename: rows.filter(renamesFile).length,
        move: rows.filter(movesFile).length,
        skipped: rows.filter((row) => row.status === "skipped").length };
    document.querySelectorAll("[data-plan-show]").forEach((button) => {
        const name = button.dataset.planShow;
        button.textContent = t(`plan.show_${name}`, { n: counts[name] });
        button.setAttribute("aria-pressed", String(name === planShow));
    });
}

/** The folder dropdown of a row: every place of the tree. */
function planFolderSelect(row) {
    const select = document.createElement("select");
    select.className = "plan-folder-select";
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
    // A long folder ends in "…"; the mouse shows it whole.
    select.title = select.value ? planFolderLabel(select.value)
        : t("plan.same_folder");
    select.addEventListener("change", () => {
        savePlanEdit(row.id, { folder: select.value });
    });
    return select;
}

/** The name box of a row. Saved when it loses focus with a new value. */
function planNameInput(row) {
    const input = document.createElement("input");
    input.type = "text";
    // Looks like text; a click edits it.
    input.className = "plan-new-name";
    input.value = row.new_name || row.old_name || "";
    input.title = input.value;
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

/** Where a row's file ends up: its new folder, or the one it is in. */
function planDestination(row) {
    return movesFile(row) ? row.new_folder : row.old_folder;
}

/** One group header: the destination folder, its file count, new or not. */
function planGroupHeader(folder, count) {
    const header = document.createElement("div");
    header.className = "plan-group";
    const name = document.createElement("span");
    name.className = "plan-group-name";
    name.textContent = planFolderLabel(folder);
    const facts = document.createElement("span");
    facts.className = "plan-group-facts";
    const made = planView.rows.some((row) => row.action === "create_folder"
        && row.new_folder === folder);
    facts.textContent = (count === 1 ? t("plan.files_one")
        : t("plan.files_many", { n: count }))
        + (made ? ` · ${t("plan.new_folder")}` : "");
    header.append(name, facts);
    return header;
}

/** One row: the box, the file as it is (struck through), →, as it will be, Skip or Undo. */
function planRow(row) {
    const line = document.createElement("div");
    line.className = "plan-row";
    line.dataset.id = row.id;
    const skipped = row.status === "skipped";
    const open = planRowOpen(row);
    line.classList.toggle("is-skipped", skipped);
    line.classList.toggle("row-failed", row.status === "failed");

    // The box approves the change; unticked, the change is skipped.
    const check = document.createElement("label");
    check.className = "check-hit";
    const box = document.createElement("input");
    box.type = "checkbox";
    box.checked = row.status === "approved" || !open
        && ["applied", "pending"].includes(row.status);
    box.disabled = !open || Boolean(planView.busy);
    box.setAttribute("aria-label", t("plan.approve_row",
        { name: row.old_name || "" }));
    box.addEventListener("change", () => choosePlan({
        status: box.checked ? "approved" : "skipped", ids: [row.id] }));
    check.appendChild(box);

    const before = document.createElement("div");
    before.className = "plan-before";
    const oldName = document.createElement("span");
    oldName.className = "plan-old-name";
    oldName.textContent = row.old_name;
    oldName.title = row.old_name;
    const oldLine = document.createElement("span");
    oldLine.className = "plan-old-line";
    oldLine.append(oldName, makeFileActions(row.document_id));
    const where = document.createElement("span");
    where.className = "plan-where";
    where.textContent = t("plan.in_folder",
        { folder: planFolderLabel(row.old_folder) });
    before.append(oldLine, where);

    const arrow = document.createElement("span");
    arrow.className = "plan-arrow";
    arrow.setAttribute("aria-hidden", "true");
    arrow.textContent = "→";

    const after = document.createElement("div");
    after.className = "plan-after";
    if (open && !skipped) {
        after.appendChild(planNameInput(row));
    } else {
        const newName = document.createElement("span");
        newName.className = "plan-new-name";
        newName.textContent = row.new_name || row.old_name;
        after.appendChild(newName);
    }
    const why = document.createElement("span");
    why.className = "plan-why";
    if (skipped) {
        why.textContent = t("plan.skipped_note");
    } else {
        // The folder can still change here; the reason says why this one.
        if (open && planView.folders.length) {
            why.appendChild(planFolderSelect(row));
        }
        const reason = document.createElement("span");
        reason.textContent = row.reason || row.why || row.review_note || "";
        why.appendChild(reason);
    }
    after.appendChild(why);

    // Skip a change, or Undo the skip: the row's own choice.
    const action = document.createElement("button");
    action.type = "button";
    action.className = "link-button plan-row-action";
    action.textContent = t(skipped ? "plan.undo_skip" : "plan.skip");
    action.disabled = !open || Boolean(planView.busy);
    action.addEventListener("click", () => choosePlan({
        status: skipped ? "approved" : "skipped", ids: [row.id] }));
    line.append(check, before, arrow, after, action);
    return line;
}

function renderPlanRows() {
    const list = document.getElementById("plan-rows");
    list.innerHTML = "";
    renderPlanShow();
    // Grouped by where the files end up, in the order of the tree.
    const groups = new Map();
    filteredPlanRows().forEach((row) => {
        const folder = planDestination(row) || "";
        if (!groups.has(folder)) {
            groups.set(folder, []);
        }
        groups.get(folder).push(row);
    });
    [...groups.keys()].sort().forEach((folder) => {
        const rows = groups.get(folder);
        list.appendChild(planGroupHeader(folder, rows.length));
        rows.forEach((row) => list.appendChild(planRow(row)));
    });
    list.classList.toggle("hidden", groups.size === 0);
}

/** Folders taken out of the tree, to remove at Apply if they are empty. */
function removalRows() {
    return planView.rows.filter((row) => row.action === "remove_folder"
        && row.status === "approved");
}

/** "30 changes · 18 renames · 12 moves. Nothing changes until you apply." */
function renderPlanSummary() {
    const rows = changeRows();
    // Only the parts that are not 0.
    const parts = [["plan.summary_changes", rows.length],
        ["plan.summary_renames", rows.filter(renamesFile).length],
        ["plan.summary_moves", rows.filter(movesFile).length]]
        .filter(([, n]) => n > 0).map(([key, n]) => t(key, { n: n }));
    // Folders taken out of the tree: removed only if they end up empty.
    const removals = removalRows().length;
    if (removals) {
        parts.push(t(removals === 1 ? "plan.summary_removal_one"
            : "plan.summary_removals", { n: removals }));
    }
    document.getElementById("plan-summary").textContent = parts.length
        ? `${parts.join(" · ")}. ${t("plan.summary_note")}` : "";
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
    const list = document.getElementById("plan-batch-list");
    list.innerHTML = "";
    const batches = planView.batches || [];
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

/** Every folder of the tree with its Leave as is switch. */
function renderPlanFolders() {
    const list = document.getElementById("plan-folder-list");
    list.innerHTML = "";
    const folders = planView.tree_folders || [];
    folders.forEach((folder) => {
        const item = document.createElement("li");
        const name = document.createElement("span");
        name.textContent = planFolderLabel(folder.path);
        const label = document.createElement("label");
        label.className = "switch-label plan-leave";
        const input = document.createElement("input");
        input.type = "checkbox";
        input.checked = folder.leave;
        input.dataset.folder = folder.path;
        input.setAttribute("aria-label", t("plan.leave") + ": "
            + planFolderLabel(folder.path));
        input.addEventListener("change", async () => {
            try {
                const view = await setLeaveAlone(folder.path, input.checked);
                Object.assign(planView, view);
                renderPlan();
            } catch (error) {
                input.checked = !input.checked;
                showToolbarMessage(errorText(error), true);
            }
        });
        const text = document.createElement("span");
        text.textContent = t("plan.leave");
        const knob = document.createElement("span");
        knob.className = "switch";
        label.append(text, input, knob);
        item.append(name, label);
        list.appendChild(item);
    });
}

/** Why a plan has no rows. */
function emptyPlanText() {
    if (planView.unread) {
        return t("plan.unread", { n: planView.unread });
    }
    return planView.mode === "tree" ? t("plan.drop_zone") : t("plan.empty");
}

/** The main button says how many changes it applies. */
function updateApplyButton() {
    const count = planView.rows.filter((row) => row.document_id
        && row.status === "approved").length + removalRows().length;
    const button = document.getElementById("plan-apply");
    button.textContent = count === 1 ? t("plan.apply_one")
        : count ? t("plan.apply_many", { n: count }) : t("plan.apply");
    document.getElementById("plan-approve-all").disabled =
        Boolean(planView.busy);
    button.disabled = count === 0 || Boolean(planView.busy);
    // An off button says why: nothing approved yet.
    document.getElementById("plan-apply-hint").textContent =
        count === 0 && !planView.busy ? t("plan.need_approval") : "";
}

function renderPlan() {
    renderPlanSummary();
    renderPlanRows();
    renderPlanFolders();
    renderPlanBatches();
    // The batch in progress, or the newest one applied, with its Undo.
    const running = (planView.batches || []).find((batch) =>
        ["applying", "undoing", "paused", "applied"].includes(batch.status));
    renderPlanProgress(running || null, running ? running.summary : null);
    planMessage(changeRows().length || removalRows().length
        ? "" : emptyPlanText());
    updateApplyButton();
    refreshPlanBadge();
}

/** The number next to Plan in the sidebar. */
async function refreshPlanBadge() {
    let count = 0;
    try {
        count = (await getPlanCount()).waiting;
    } catch (error) {
        // No project yet, or logged out: no number.
    }
    const badge = document.getElementById("plan-badge");
    badge.textContent = count;
    badge.classList.toggle("hidden", !count);
}

/** Nothing to show: an empty list and its line (and Choose folder with no project). */
function clearPlan(text, noProject) {
    planView = null;
    showPlanParts(false);
    document.getElementById("plan-summary").textContent = "";
    document.getElementById("plan-progress").classList.add("hidden");
    document.getElementById("plan-rows").innerHTML = "";
    document.getElementById("plan-apply-hint").textContent = "";
    document.getElementById("plan-start").classList
        .toggle("hidden", !noProject);
    planMessage(text);
}

async function loadPlan() {
    clearTimeout(planTimer);
    document.getElementById("plan-start").classList.add("hidden");
    try {
        const view = await getPlan();
        if (view.message) {
            clearPlan(view.mode === "catalog" ? t("plan.catalog_only")
                : t("plan.no_plan"), false);
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
        // No project is a start, not a failure. Nothing of before stays.
        const noProject = Boolean(error && error.code === "no_project");
        clearPlan(noProject ? t("plan.no_project") : t("plan.load_failed"),
            noProject);
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
document.querySelectorAll("[data-plan-tab]").forEach((button) => {
    button.addEventListener("click", () => {
        showPlanTab(button.dataset.planTab);
    });
});
document.querySelectorAll("[data-plan-show]").forEach((button) => {
    button.addEventListener("click", () => {
        planShow = button.dataset.planShow;
        renderPlanRows();
    });
});
