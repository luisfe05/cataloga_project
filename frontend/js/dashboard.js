/** dashboard.js: stat cards, circles, breakdown bars, and activity from GET /dashboard/stats. */

// Order of the bars, as in the wireframe.
const BREAKDOWN_ORDER = ["Documents", "Audio", "Video", "Press", "Photos"];

// Last height of each bar, so a refresh grows it from there, not from zero.
const lastBarHeights = {};

// Smallest and largest circle in the Manual Review card, in pixels.
const ORB_MIN = 24;
const ORB_MAX = 96;

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

/** Draw one bar per media type, with its count and share. The tallest is Violet. */
function renderBreakdown(breakdown) {
    const container = document.getElementById("media-breakdown");
    container.innerHTML = "";
    const counts = BREAKDOWN_ORDER.map((type) => breakdown[type] || 0);
    const total = counts.reduce((sum, count) => sum + count, 0);
    const largest = Math.max(...counts);
    // Only one bar is marked, even when two have the same count.
    const topType = largest > 0
        ? BREAKDOWN_ORDER[counts.indexOf(largest)] : null;

    BREAKDOWN_ORDER.forEach((type, index) => {
        const count = counts[index];
        const percent = total ? Math.round((count / total) * 100) : 0;
        // Bars are measured against the largest one, so it fills the track.
        const height = largest ? Math.round((count / largest) * 100) : 0;

        const item = document.createElement("div");
        item.className = type === topType
            ? "breakdown-item is-top" : "breakdown-item";

        const number = document.createElement("strong");
        number.className = "breakdown-count";
        number.textContent = count;

        const track = document.createElement("div");
        track.className = "bar-track";
        const fill = document.createElement("div");
        fill.className = "bar-fill";
        track.appendChild(fill);

        const header = document.createElement("div");
        header.className = "breakdown-header";
        const label = document.createElement("span");
        label.className = "breakdown-type";
        label.textContent = valueLabel(type);
        // The full name on hover, for a name split in a narrow card.
        label.title = label.textContent;
        const value = document.createElement("span");
        value.textContent = `${percent}%`;
        header.append(label, value);

        item.append(number, track, header);
        container.appendChild(item);

        growBar(fill, "--share", lastBarHeights[type] || "0%", `${height}%`);
        lastBarHeights[type] = `${height}%`;
    });
}

/** Size the two circles by their share, and write the total under Documents Classified. */
function renderShares(classified, review) {
    const total = classified + review;
    document.getElementById("stat-total").textContent = total
        ? t("dash.of_total", { n: total }) : t("dash.no_documents");

    // With no documents both circles keep the smallest size.
    const orbSize = (count) => {
        const share = total ? count / total : 0;
        return `${Math.round(ORB_MIN + (ORB_MAX - ORB_MIN) * share)}px`;
    };
    document.getElementById("orb-classified").style
        .setProperty("--size", orbSize(classified));
    document.getElementById("orb-review").style
        .setProperty("--size", orbSize(review));
}

/** Write the finding under the title, with a button to the Manual Review tab. */
function renderFinding(classified, review) {
    document.getElementById("dash-finding")
        .classList.toggle("hidden", classified + review === 0);
    let text = t("dash.finding_done");
    if (review === 1) {
        text = t("dash.finding_review_one");
    } else if (review > 1) {
        text = t("dash.finding_review", { n: review });
    }
    document.getElementById("dash-finding-text").textContent = text;
    document.getElementById("dash-review-button")
        .classList.toggle("hidden", review === 0);
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
    message.textContent = activity.length ? "" : t("dash.empty");
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
        renderShares(stats.documents_classified, stats.needs_manual_review);
        renderFinding(stats.documents_classified, stats.needs_manual_review);
        renderBreakdown(stats.media_type_breakdown);
        renderActivity(stats.recent_activity);
    } catch (error) {
        // Clear the previous project's numbers so they never mix with this one.
        ["stat-classified", "stat-review", "stat-sources"].forEach((id) => {
            countUp(document.getElementById(id), 0);
        });
        renderShares(0, 0);
        renderFinding(0, 0);
        document.getElementById("stat-total").textContent = "";
        document.getElementById("media-breakdown").innerHTML = "";
        document.getElementById("activity-list").innerHTML = "";
        const message = document.getElementById("dashboard-message");
        message.textContent = t("dash.load_failed",
            { message: errorText(error) });
        message.classList.remove("hidden");
    }
}

// Review in Catalog: the Manual Review tab, with the other filters cleared.
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
