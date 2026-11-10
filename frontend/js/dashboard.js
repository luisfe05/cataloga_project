/** dashboard.js: stat cards, the ring, Media Mix and activity from GET /dashboard/stats. */

// Order of the Media Mix segments and chips.
const MIX_ORDER = ["Documents", "Press", "Photos", "Audio", "Video"];

// One brand color per type, from darkest to lightest, so the types also
// differ by lightness and not only by hue. Each one is a token in main.css
// and keeps 3:1 against the bar's Paper rail.
const MIX_COLORS = {
    Documents: "var(--color-deep-space)",
    Press: "var(--color-nebula)",
    Photos: "var(--color-violet)",
    Audio: "var(--color-iris)",
    Video: "var(--color-lilac)",
};

// What is on screen now, so a refresh with the same numbers does not
// play the ring or the Media Mix again from zero.
let ringLeft = "100";
let drawnMix = "";

/** Say how long ago a timestamp was. One text key per case: word order changes by language. */
function timeAgo(timestamp) {
    const seconds = (Date.now() - new Date(timestamp).getTime()) / 1000;
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (minutes < 1) {
        return t("time.just_now");
    }
    if (minutes < 60) {
        return t("time.minutes", { n: minutes });
    }
    if (hours < 24) {
        return hours === 1 ? t("time.hour") : t("time.hours", { n: hours });
    }
    if (days === 1) {
        return t("time.yesterday");
    }
    return t("time.days", { n: days });
}

/** Media Mix: one bar split by type, and a chip per type that filters the Catalog. */
function renderMediaMix(breakdown) {
    const key = JSON.stringify([MIX_ORDER.map((type) => breakdown[type] || 0),
        currentLanguage]);
    if (key === drawnMix) {
        return;
    }
    drawnMix = key;
    const bar = document.getElementById("mix-bar");
    const chips = document.getElementById("mix-chips");
    bar.innerHTML = "";
    chips.innerHTML = "";
    const counts = MIX_ORDER.map((type) => breakdown[type] || 0);
    const total = counts.reduce((sum, count) => sum + count, 0);
    const described = [];

    MIX_ORDER.forEach((type, index) => {
        const count = counts[index];
        const percent = total ? Math.round((count / total) * 100) : 0;
        described.push(`${valueLabel(type)} ${percent}%`);
        if (count) {
            const segment = document.createElement("span");
            segment.className = "mix-segment";
            segment.style.flexGrow = count;
            segment.style.backgroundColor = MIX_COLORS[type];
            segment.title = `${valueLabel(type)}: ${count} (${percent}%)`;
            bar.appendChild(segment);
        }

        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "mix-chip";
        chip.dataset.type = type;
        chip.style.setProperty("--chip-color", MIX_COLORS[type]);
        const dot = document.createElement("span");
        dot.className = "mix-dot";
        dot.setAttribute("aria-hidden", "true");
        const name = document.createElement("span");
        name.textContent = valueLabel(type);
        const number = document.createElement("strong");
        number.textContent = count;
        const share = document.createElement("span");
        share.className = "mix-share";
        share.textContent = `${percent}%`;
        chip.append(dot, name, number, share);
        chip.setAttribute("aria-label", t("dash.mix_open",
            { type: valueLabel(type), n: count }));
        chip.addEventListener("click", () => {
            showView("catalog");
            applyCatalogFilters({ media_type: type });
        });
        chips.appendChild(chip);
    });
    bar.setAttribute("aria-label", described.join(", "));
    // The segments grow from the left (CSS) each time the numbers change.
    bar.classList.remove("is-growing");
    bar.getBoundingClientRect();
    bar.classList.add("is-growing");
}

/** The ring of Documents Classified and the line under the number. */
function renderClassified(classified, review) {
    const total = classified + review;
    document.getElementById("stat-total").textContent = total
        ? t("dash.of_total", { n: total }) : t("dash.no_documents");
    const percent = total ? Math.round((classified / total) * 100) : 0;
    document.getElementById("classified-percent").textContent = `${percent}%`;
    // pathLength is 100, so the offset is what is left to fill.
    const ring = document.querySelector("#classified-ring .ring-fill");
    growBar(ring, "--ring-left", ringLeft, String(100 - percent));
    ringLeft = String(100 - percent);
}

/** The three sources with the most documents, each a link to its documents. */
function renderTopSources(sources) {
    const list = document.getElementById("top-sources");
    list.innerHTML = "";
    sources.forEach((item) => {
        const row = document.createElement("li");
        const link = document.createElement("button");
        link.type = "button";
        link.className = "link-button source-link";
        link.textContent = item.source;
        link.setAttribute("aria-label", t("chat.show_source",
            { source: item.source }));
        link.addEventListener("click", () => {
            showView("catalog");
            applyCatalogFilters({ source: item.source, sort: "newest" });
        });
        const count = document.createElement("span");
        count.className = "source-count";
        count.textContent = item.count;
        row.append(link, count);
        list.appendChild(row);
    });
    list.closest(".top-sources").classList.toggle("hidden", !sources.length);
}

function renderActivity(activity) {
    const list = document.getElementById("activity-list");
    list.innerHTML = "";
    activity.forEach((entry) => {
        const item = document.createElement("li");
        const name = document.createElement("span");
        name.textContent = entry.filename;
        name.className = "activity-name";
        // Manual Review gets the Violet border.
        const badge = document.createElement("span");
        badge.className = entry.action === "Manual Review"
            ? "activity-badge is-review" : "activity-badge";
        badge.textContent = valueLabel(entry.action);
        const when = document.createElement("span");
        when.className = "activity-when";
        when.textContent = timeAgo(entry.timestamp);
        item.append(name, badge, when);
        list.appendChild(item);
    });

    const message = document.getElementById("dashboard-message");
    // A project read where it is has no Drop Zone: it says how to start.
    const inPlace = ["place", "catalog"].includes(projectFolderMode);
    message.textContent = activity.length ? ""
        : t(inPlace ? "catalog.empty_place" : "dash.empty");
    message.classList.toggle("hidden", activity.length > 0);
}

async function loadDashboard() {
    try {
        const stats = await getDashboardStats();
        countUp(document.getElementById("stat-classified"),
            stats.documents_classified);
        countUp(document.getElementById("stat-review"),
            stats.needs_manual_review);
        countUp(document.getElementById("stat-sources"),
            stats.sources_tracked);
        renderClassified(stats.documents_classified,
            stats.needs_manual_review);
        document.getElementById("dash-review-button").classList
            .toggle("hidden", stats.needs_manual_review === 0);
        renderTopSources(stats.top_sources || []);
        renderMediaMix(stats.media_type_breakdown);
        renderActivity(stats.recent_activity);
    } catch (error) {
        // Clear the previous project's numbers so they never mix with this one.
        ["stat-classified", "stat-review", "stat-sources"].forEach((id) => {
            countUp(document.getElementById(id), 0);
        });
        renderClassified(0, 0);
        renderTopSources([]);
        document.getElementById("stat-total").textContent = "";
        document.getElementById("mix-bar").innerHTML = "";
        document.getElementById("mix-chips").innerHTML = "";
        drawnMix = "";
        document.getElementById("activity-list").innerHTML = "";
        const message = document.getElementById("dashboard-message");
        message.textContent = t("dash.load_failed",
            { message: errorText(error) });
        message.classList.remove("hidden");
    }
}

// Go Review: the Manual Review tab, with the other filters cleared.
document.getElementById("dash-review-button").addEventListener("click", () => {
    showView("catalog");
    applyCatalogFilters({ status: "Manual Review" });
});

// Keep the numbers current while the dashboard is open.
setInterval(() => {
    const view = document.getElementById("view-dashboard");
    if (!view.classList.contains("hidden") && sessionToken) {
        loadDashboard();
    }
}, REFRESH_SECONDS * 1000);
