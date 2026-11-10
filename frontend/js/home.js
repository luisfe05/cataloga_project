/** home.js: the Home screen. The project's folders and files, like Finder. */

// Folders on the way down, each as answered by GET /browse.
let homeTrail = [];
let homeSelected = null;
let homeView = "icons";
// What the screen last drew, so a refresh does not redraw for nothing.
let homeDrawn = "";

const LOGOMARK_SELECTED = 6;

/** The logomark of a folder by its depth, as in the mockup. */
function folderMark(depth) {
    if (depth <= 1) {
        return 4;
    }
    return depth === 2 ? 3 : 5;
}

function homeDepth(place) {
    return place ? place.split("/").length : 0;
}

function logomarkImage(number) {
    const image = document.createElement("img");
    image.className = "home-mark";
    image.alt = "";
    image.src = `assets/logomarks/logomark-${number}.svg`;
    return image;
}

/** Sizes as Finder says them. */
function humanSize(bytes) {
    if (bytes < 1000) {
        return `${bytes} B`;
    }
    const units = ["KB", "MB", "GB", "TB"];
    let value = bytes;
    let unit = -1;
    do {
        value /= 1000;
        unit += 1;
    } while (value >= 1000 && unit < units.length - 1);
    return `${value >= 100 ? Math.round(value) : value.toFixed(1)} ${units[unit]}`;
}

/** A photo's real small picture; the gradient stays if it has none. */
function photoImage(file, className) {
    const image = document.createElement("img");
    image.className = className;
    image.alt = "";
    image.loading = "lazy";
    image.src = fileThumbUrl(file.path);
    image.addEventListener("error", () => {
        image.removeAttribute("src");
    });
    return image;
}

function fileIcon(file) {
    if (file.photo) {
        return photoImage(file, "home-thumb");
    }
    const doc = document.createElement("i");
    doc.className = "home-doc";
    doc.textContent = file.extension.slice(0, 5);
    return doc;
}

function statusBadge(file) {
    if (!file.document) {
        return null;
    }
    const review = file.document.status === "Manual Review";
    const badge = document.createElement("i");
    badge.className = `home-badge ${review ? "rev" : "ok"}`;
    if (review) {
        badge.textContent = "!";
    } else {
        // The same check icon as the rest of the app, not a text glyph.
        const check = document.createElement("span");
        check.className = "icon icon-check";
        badge.appendChild(check);
    }
    return badge;
}

/** The folder on screen. */
function homeHere() {
    return homeTrail[homeTrail.length - 1];
}

function isSelected(kind, item) {
    return Boolean(homeSelected) && homeSelected.kind === kind
        && homeSelected.item.path === item.path;
}

function selectHomeItem(kind, item) {
    homeSelected = { kind: kind, item: item };
    drawHome();
}

/** Go into a folder: double-click in icons, a click in columns. */
async function enterHomeFolder(place, keepSelected) {
    try {
        const listed = await browseFolderList(place);
        homeTrail.push(listed);
        if (!keepSelected) {
            homeSelected = null;
        }
        drawHome();
    } catch (error) {
        showToolbarMessage(errorText(error), true);
    }
}

function drawCrumbs() {
    const crumbs = document.getElementById("home-crumbs");
    crumbs.innerHTML = "";
    // At the project's root the path is only the title again, so it hides.
    crumbs.classList.toggle("hidden", homeTrail.length <= 1);
    homeTrail.forEach((level, index) => {
        if (index) {
            const arrow = document.createElement("span");
            arrow.textContent = "›";
            crumbs.appendChild(arrow);
        }
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = index === 0
            ? document.getElementById("home-title").textContent
            : level.path.split("/").pop();
        button.addEventListener("click", () => {
            homeTrail = homeTrail.slice(0, index + 1);
            homeSelected = null;
            drawHome();
        });
        crumbs.appendChild(button);
    });
}

function makeChip(text) {
    const chip = document.createElement("span");
    chip.className = "home-chip";
    // The number in bold, as in the mockup.
    const found = text.match(/^(\S+)(.*)$/);
    const number = document.createElement("b");
    number.textContent = found[1];
    chip.append(number, found[2]);
    return chip;
}

function drawChips(totals) {
    const chips = document.getElementById("home-chips");
    chips.innerHTML = "";
    if (totals.cataloged) {
        chips.append(
            makeChip(t("home.classified", { n: totals.classified })),
            makeChip(t("home.manual_review", { n: totals.review })),
            makeChip(t("home.files", { n: totals.files })));
        return;
    }
    const waiting = document.createElement("span");
    waiting.className = "home-chip";
    waiting.textContent = t("home.not_cataloged");
    chips.append(makeChip(t("home.files", { n: totals.files })),
        makeChip(t("home.folders", { n: totals.folders })), waiting);
}

/** One folder or file in the icon view. */
function makeIconItem(kind, item, icon, count) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `home-item ${isSelected(kind, item) ? "sel" : ""}`;
    button.title = item.name;
    const holder = document.createElement("span");
    holder.className = "home-ic";
    holder.appendChild(icon);
    if (kind === "file") {
        const badge = statusBadge(item);
        if (badge) {
            holder.appendChild(badge);
        }
    }
    const name = document.createElement("span");
    name.className = "home-nm";
    name.textContent = item.name;
    const size = document.createElement("span");
    size.className = "home-ct";
    size.textContent = count;
    button.append(holder, name, size);
    const enter = () => (kind === "folder" ? enterHomeFolder(item.path)
        : openPreviewAt(item.path));
    button.addEventListener("click", () => selectHomeItem(kind, item));
    button.addEventListener("dblclick", enter);
    button.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            enter();
        }
    });
    return button;
}

function drawIcons(box) {
    const here = homeHere();
    const grid = document.createElement("div");
    grid.className = "home-grid";
    const depth = homeDepth(here.path) + 1;
    here.folders.forEach((folder) => {
        grid.appendChild(makeIconItem("folder", folder,
            logomarkImage(folderMark(depth)),
            t("home.files", { n: folder.files })));
    });
    here.files.forEach((file) => {
        grid.appendChild(makeIconItem("file", file, fileIcon(file),
            humanSize(file.size)));
    });
    box.appendChild(grid);
}

/** One row of a column. A selected row sits on violet: logomark-6. */
function makeColumnRow(kind, item, levelIndex, selected, depth) {
    const row = document.createElement("button");
    row.type = "button";
    row.className = `home-row ${selected ? "sel" : ""}`;
    row.title = item.name;
    if (kind === "folder") {
        row.appendChild(logomarkImage(selected ? LOGOMARK_SELECTED
            : folderMark(depth)));
    } else if (item.photo) {
        row.appendChild(photoImage(item, "home-mini"));
    } else {
        // The icon view's document, small, with its extension.
        const doc = document.createElement("i");
        doc.className = "home-minidoc";
        doc.textContent = item.extension.slice(0, 4);
        row.appendChild(doc);
    }
    const name = document.createElement("span");
    name.textContent = item.name;
    row.appendChild(name);
    if (kind === "folder") {
        const chevron = document.createElement("b");
        chevron.className = "home-chev";
        chevron.textContent = "›";
        row.appendChild(chevron);
    }
    row.addEventListener("click", async () => {
        homeTrail = homeTrail.slice(0, levelIndex + 1);
        homeSelected = { kind: kind, item: item };
        if (kind === "folder") {
            await enterHomeFolder(item.path, true);
        } else {
            drawHome();
        }
        const columns = document.querySelector(".home-cols");
        if (columns) {
            columns.scrollLeft = columns.scrollWidth;
        }
    });
    if (kind === "file") {
        row.addEventListener("dblclick", () => openPreviewAt(item.path));
    }
    return row;
}

function drawColumns(box) {
    const columns = document.createElement("div");
    columns.className = "home-cols";
    homeTrail.forEach((level, index) => {
        const column = document.createElement("div");
        column.className = "home-col";
        const next = homeTrail[index + 1];
        const depth = homeDepth(level.path) + 1;
        level.folders.forEach((folder) => {
            const open = Boolean(next) && next.path === folder.path;
            column.appendChild(makeColumnRow("folder", folder, index,
                open || isSelected("folder", folder), depth));
        });
        level.files.forEach((file) => {
            column.appendChild(makeColumnRow("file", file, index,
                isSelected("file", file), depth));
        });
        columns.appendChild(column);
    });
    box.appendChild(columns);
}

function addFact(list, label, value) {
    const term = document.createElement("dt");
    term.textContent = t(label);
    const detail = document.createElement("dd");
    if (value instanceof Node) {
        detail.appendChild(value);
    } else {
        detail.textContent = value;
    }
    list.append(term, detail);
}

function statusPill(text, kind) {
    const pill = document.createElement("span");
    pill.className = `home-status ${kind}`;
    pill.textContent = text;
    return pill;
}

/** The panel for a folder: what is inside it. */
function drawFolderInfo(info, name, path, files) {
    const big = document.createElement("div");
    big.className = "home-big";
    big.appendChild(logomarkImage(folderMark(homeDepth(path))));
    const title = document.createElement("h3");
    title.textContent = name;
    const facts = document.createElement("dl");
    facts.className = "home-kv";
    addFact(facts, "home.kind", t("home.kind_folder"));
    addFact(facts, "home.contains", t("home.files", { n: files }));
    const done = homeTrail[0].totals.cataloged > 0;
    addFact(facts, "home.status", done
        ? statusPill(t("home.cataloged"), "ok")
        : statusPill(t("home.not_cataloged"), "none"));
    const hint = document.createElement("p");
    hint.className = "home-hint";
    hint.textContent = t("home.double_click");
    info.append(big, title, facts, hint);
}

/** The panel for a file: everything the catalog knows about it. */
function drawFileInfo(info, file) {
    const big = document.createElement("div");
    big.className = "home-big";
    big.appendChild(fileIcon(file));
    const title = document.createElement("h3");
    title.textContent = file.name;
    const facts = document.createElement("dl");
    facts.className = "home-kv";
    const kind = file.photo ? t("home.kind_photo")
        : file.extension.toUpperCase();
    addFact(facts, "home.kind", `${kind} · ${humanSize(file.size)}`);
    const doc = file.document;
    if (!doc) {
        addFact(facts, "home.status",
            statusPill(t("home.not_cataloged"), "none"));
    } else {
        addFact(facts, "home.status", doc.status === "Manual Review"
            ? statusPill(valueLabel("Manual Review"), "rev")
            : statusPill(valueLabel("Classified"), "ok"));
        addFact(facts, "home.date", doc.date || t("home.no_date"));
        addFact(facts, "home.date_from", doc.date_source
            ? t(`catalog.date_from_${doc.date_source.replace(" ", "_")}`)
            : "-");
        addFact(facts, "home.source", doc.source || "-");
        addFact(facts, "home.summary", doc.summary || "-");
    }
    info.append(big, title, facts);
    if (doc && doc.why) {
        const why = document.createElement("div");
        why.className = "home-why";
        const label = document.createElement("b");
        label.textContent = t("home.why");
        why.append(label, doc.why);
        info.appendChild(why);
    }
    const actions = document.createElement("div");
    actions.className = "home-actions";
    const open = document.createElement("button");
    open.type = "button";
    open.textContent = t("home.open");
    open.addEventListener("click", () => openPreviewAt(file.path));
    const show = document.createElement("button");
    show.type = "button";
    show.textContent = t("home.show");
    show.addEventListener("click", () => {
        revealFile(file.path).catch((error) => {
            showToolbarMessage(errorText(error), true);
        });
    });
    actions.append(open, show);
    info.appendChild(actions);
}

function drawInfo() {
    const info = document.getElementById("home-info");
    info.innerHTML = "";
    if (homeSelected && homeSelected.kind === "file") {
        drawFileInfo(info, homeSelected.item);
    } else if (homeSelected) {
        drawFolderInfo(info, homeSelected.item.name, homeSelected.item.path,
            homeSelected.item.files);
    } else {
        const here = homeHere();
        drawFolderInfo(info, here.path ? here.path.split("/").pop()
            : document.getElementById("home-title").textContent, here.path,
            here.contains);
    }
}

function drawHome() {
    const here = homeHere();
    if (!here) {
        return;
    }
    drawCrumbs();
    drawChips(homeTrail[0].totals);
    const box = document.getElementById("home-browser");
    box.innerHTML = "";
    if (!here.folders.length && !here.files.length && homeView === "icons") {
        const empty = document.createElement("p");
        empty.className = "home-hint";
        empty.style.padding = "16px";
        empty.textContent = t("home.empty");
        box.appendChild(empty);
    } else if (homeView === "icons") {
        drawIcons(box);
    } else {
        drawColumns(box);
    }
    drawInfo();
}

/** Read every level of the trail again; draw only if something changed. */
async function loadHome() {
    const message = document.getElementById("home-message");
    const work = document.getElementById("home-work");
    const places = homeTrail.length ? homeTrail.map((level) => level.path)
        : [""];
    try {
        const levels = [];
        for (const place of places) {
            try {
                levels.push(await browseFolderList(place));
            } catch (error) {
                // A folder that is gone: stay at the last one that exists.
                if (!levels.length) {
                    throw error;
                }
                break;
            }
        }
        message.classList.add("hidden");
        work.classList.remove("hidden");
        const answer = JSON.stringify(levels);
        if (answer === homeDrawn) {
            return;
        }
        homeDrawn = answer;
        homeTrail = levels;
        refreshHomeSelection();
        drawHome();
    } catch (error) {
        homeTrail = [];
        homeDrawn = "";
        work.classList.add("hidden");
        message.classList.remove("hidden");
        message.textContent = error && error.code === "no_project"
            ? t("home.no_project") : t("home.load_failed");
        document.getElementById("home-chips").innerHTML = "";
        document.getElementById("home-crumbs").innerHTML = "";
    }
}

/** The selected item may have new data after a refresh. */
function refreshHomeSelection() {
    if (!homeSelected) {
        return;
    }
    const list = homeSelected.kind === "folder" ? "folders" : "files";
    const fresh = homeTrail.flatMap((level) => level[list])
        .find((item) => item.path === homeSelected.item.path);
    homeSelected = fresh ? { kind: homeSelected.kind, item: fresh } : null;
}

/** Another project: back to its top folder. */
function resetHome() {
    homeTrail = [];
    homeSelected = null;
    homeDrawn = "";
    loadHome();
}

document.querySelectorAll("[data-home-view]").forEach((button) => {
    button.addEventListener("click", () => {
        homeView = button.dataset.homeView;
        document.querySelectorAll("[data-home-view]").forEach((other) => {
            other.classList.toggle("on", other === button);
        });
        drawHome();
    });
});

// New files and new catalog data appear on their own while Home is open.
setInterval(() => {
    if (sessionToken && !document.getElementById("view-home")
        .classList.contains("hidden")) {
        loadHome();
    }
}, 5000);
