/**
 * dashboard.js
 *
 * Dashboard view (Screen 3).
 * Renders the three stat cards, media type breakdown bars,
 * and recent activity list, from GET /dashboard/stats.
 */

// Order of the bars, as in the wireframe.
const BREAKDOWN_ORDER = ["Documents", "Audio", "Video", "Press", "Photos"];

// How each activity_log action reads in the Recent Activity list.
const ACTION_TEXT = {
    "Classified": "Classified",
    "Manual Review": "Flagged for manual review,",
    "Edited": "Edited",
};

/**
 * Describe how long ago a timestamp was, like "2 min ago" or
 * "yesterday".
 * @param {string} timestamp - ISO text such as 2026-10-21T16:55:00.
 * @returns {string}
 */
function timeAgo(timestamp) {
    const seconds = (Date.now() - new Date(timestamp).getTime()) / 1000;
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (minutes < 1) {
        return "just now";
    }
    if (minutes < 60) {
        return `${minutes} min ago`;
    }
    if (hours < 24) {
        return hours === 1 ? "1 hour ago" : `${hours} hours ago`;
    }
    if (days === 1) {
        return "yesterday";
    }
    return `${days} days ago`;
}

/**
 * Draw one bar per media type, with its share of all documents.
 * @param {Object} breakdown - {media_type: count}
 */
function renderBreakdown(breakdown) {
    const container = document.getElementById("media-breakdown");
    container.innerHTML = "";
    const total = BREAKDOWN_ORDER
        .reduce((sum, type) => sum + (breakdown[type] || 0), 0);

    BREAKDOWN_ORDER.forEach((type) => {
        const count = breakdown[type] || 0;
        // Avoid dividing by zero when the catalog is empty.
        const percent = total ? Math.round((count / total) * 100) : 0;

        const item = document.createElement("div");
        item.className = "breakdown-item";

        const header = document.createElement("div");
        header.className = "breakdown-header";
        const label = document.createElement("span");
        label.textContent = type;
        const value = document.createElement("strong");
        value.textContent = `${percent}%`;
        header.append(label, value);

        const track = document.createElement("div");
        track.className = "bar-track";
        const fill = document.createElement("div");
        fill.className = "bar-fill";
        // The fill's width is the percentage, so the bar shows the share.
        fill.style.width = `${percent}%`;
        track.appendChild(fill);

        item.append(header, track);
        container.appendChild(item);
    });
}

/**
 * List the latest actions, newest first.
 * @param {Array<Object>} activity - [{filename, action, timestamp}]
 */
function renderActivity(activity) {
    const list = document.getElementById("activity-list");
    list.innerHTML = "";
    activity.forEach((entry) => {
        const item = document.createElement("li");
        const name = document.createElement("span");
        name.textContent = entry.filename;
        const when = document.createElement("span");
        when.className = "activity-when";
        const action = ACTION_TEXT[entry.action] || entry.action;
        when.textContent = `${action} ${timeAgo(entry.timestamp)}`;
        item.append(name, when);
        list.appendChild(item);
    });

    const message = document.getElementById("dashboard-message");
    message.textContent = activity.length
        ? "" : "No activity yet. Drop files into the Drop Zone to start.";
    message.classList.toggle("hidden", activity.length > 0);
}

/**
 * Load the stats and draw the whole dashboard.
 */
async function loadDashboard() {
    try {
        const stats = await getDashboardStats();
        document.getElementById("stat-classified").textContent =
            stats.documents_classified;
        document.getElementById("stat-review").textContent =
            stats.needs_manual_review;
        document.getElementById("stat-sources").textContent =
            stats.sources_tracked;
        renderBreakdown(stats.media_type_breakdown);
        renderActivity(stats.recent_activity);
    } catch (error) {
        const message = document.getElementById("dashboard-message");
        message.textContent = "Could not load the dashboard: "
            + (error.message || "the app's backend is not responding.");
        message.classList.remove("hidden");
    }
}

// Keep the numbers current while the dashboard is open.
setInterval(() => {
    const view = document.getElementById("view-dashboard");
    if (!view.classList.contains("hidden")) {
        loadDashboard();
    }
}, REFRESH_SECONDS * 1000);
