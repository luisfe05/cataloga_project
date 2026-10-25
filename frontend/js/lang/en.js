/**
 * lang/en.js
 *
 * English text for every label, button, and message in the app.
 * English is the default language. es.js must have the same keys.
 * Words in braces, like {n} or {path}, are filled in by t() in i18n.js.
 */

const LANG_EN = {
    // Navigation and header
    "nav.catalog": "Catalog",
    "nav.dashboard": "Dashboard",
    "nav.settings": "Settings",
    "header.project": "Project",
    "header.no_project": "No project yet",

    // Catalog
    "catalog.tab_all": "All Files",
    "catalog.tab_review": "Manual Review ({n})",
    "catalog.search": "Search",
    "catalog.filter_type_all": "Media Type: All",
    "catalog.filter_source_all": "Source: All",
    "catalog.download": "Download Worksheet",
    "catalog.edit_mode": "Edit Mode",
    "catalog.col_original": "Original Filename",
    "catalog.col_filename": "Filename",
    "catalog.col_type": "Media Type",
    "catalog.col_source": "Source",
    "catalog.col_date": "Date",
    "catalog.col_summary": "Summary",
    "catalog.col_status": "Status",
    "catalog.summary_placeholder": "Manual Summary",
    "catalog.saving": "Saving...",
    "catalog.saving_summary":
        "Saving and updating the summary with your edit...",
    "catalog.saved": "Saved.",
    "catalog.saved_summary": "Saved. The summary was updated using your edit.",
    "catalog.save_failed": "Could not save.",
    "catalog.edit_mode_on": "Edit Mode is on. Click a cell to edit it. "
        + "Automatic refresh is paused.",
    "catalog.summary_limit": "Summaries can have up to 100 characters.",
    "catalog.summary_count": "{n} / 100",
    "catalog.old_inbox_warning": "Your old Inbox folder still has files. "
        + "Move them to Drop Zone to catalog them.",
    "catalog.no_folder":
        "Go to Settings to choose the project folder and the AI provider.",
    "catalog.empty": "Drop files into the Drop Zone folder inside {path} "
        + "and they will appear here once they are classified.",
    "catalog.no_match": "No files match your search.",
    "catalog.load_failed": "Could not load the catalog: {message}",
    "catalog.backend_down": "the app's backend is not responding.",
    "catalog.export_saved": "Worksheet saved to {path}",
    "catalog.export_failed": "Could not save the worksheet.",

    // Dashboard
    "dash.classified": "Documents Classified",
    "dash.review": "Needs Manual Review",
    "dash.sources": "Sources Tracked",
    "dash.breakdown": "Media Type Breakdown",
    "dash.activity": "Recent Activity",
    "dash.action_classified": "Classified",
    "dash.action_review": "Flagged for manual review,",
    "dash.action_edited": "Edited",
    "dash.empty": "No activity yet. Drop files into the Drop Zone to start.",
    "dash.load_failed": "Could not load the dashboard: {message}",
    "time.just_now": "just now",
    "time.minutes": "{n} min ago",
    "time.hour": "1 hour ago",
    "time.hours": "{n} hours ago",
    "time.yesterday": "yesterday",
    "time.days": "{n} days ago",

    // Settings
    "settings.research_title": "Research Settings",
    "settings.research_hint": "Configure your research project and where "
        + "files are stored. Cataloga creates a Drop Zone folder inside it: "
        + "drop new files there to have them cataloged.",
    "settings.research_name": "Research Name",
    "settings.folder": "Target Data Folder",
    "settings.browse": "Browse",
    "settings.ai_title": "AI Provider Plug in",
    "settings.ai_hint": "Plug in your own AI API key.",
    "settings.ai_provider": "AI Provider",
    "settings.api_key": "API Key",
    "settings.api_key_placeholder": "Paste your API key",
    "settings.api_key_saved": "Saved. Type a new key only to replace it.",
    "settings.model": "Model",
    "settings.save": "Save",
    "settings.save_anyway": "Save anyway",
    "settings.saving": "Saving and testing the AI connection...",
    "settings.saved": "Settings saved. The AI connection works.",
    "settings.save_failed": "Could not save settings.",
    "settings.load_failed": "Could not load settings: {message}",

    // Drop Zone (not shown on screen yet)
    "dropzone.title": "Drop Zone",
    "dropzone.instruction": "Copy or drag new files into the Drop Zone "
        + "folder. Cataloga processes them and leaves your other files "
        + "where they are.",
    "dropzone.short": "New files go here",

    // Settings: language
    "lang.title": "Language",
    "lang.hint": "Changes the app's buttons, labels and messages. "
        + "File names and summaries are not translated.",
    "lang.en": "English",
    "lang.es": "Español (Latinoamérica)",

    // Labels for values stored in the database. The stored value itself
    // never changes; only what the user sees.
    "value.Press": "Press",
    "value.Documents": "Documents",
    "value.Photos": "Photos",
    "value.Audio": "Audio",
    "value.Video": "Video",
    "value.Classified": "Classified",
    "value.Manual Review": "Manual Review",
    "value.Edited": "Edited",

    // Errors, one per backend error code
    "error.not_found":
        "That file is not in the catalog anymore. Refresh the page.",
    "error.invalid_body":
        "The app sent a request it could not read. Try again.",
    "error.invalid_field": "That field cannot be edited.",
    "error.missing_field": "Fill in every required field.",
    "error.invalid_directory":
        "That folder does not exist. Choose another one.",
    "error.folder_not_empty": "This folder already has {n} items. "
        + "Cataloga will not move them: only files you drop into its "
        + "Drop Zone folder are cataloged. Click Save anyway to use this "
        + "folder.",
    "error.unsupported_provider": "That AI provider is not supported.",
    "error.unsupported_format": "Only CSV export is supported.",
    "error.connection_failed": "Could not connect to the AI provider. "
        + "Check the API key and the model.",
    "error.generic": "Something went wrong. Try again.",
};
