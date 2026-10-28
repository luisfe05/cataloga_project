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
    "catalog.no_folder": "Go to Settings to choose the AI provider.",
    "catalog.empty": "Drop files into the Drop Zone folder inside {path} "
        + "and they will appear here once they are classified.",
    "catalog.no_match": "No files match your search.",
    "catalog.progress": "Catalog progress",
    "catalog.progress_percent": "{n}% classified",
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
    "dash.empty": "No activity yet. Drop files into the Drop Zone to start.",
    "dash.load_failed": "Could not load the dashboard: {message}",
    "dash.of_total": "of {n} documents",
    "dash.no_documents": "No documents yet",
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
    "settings.ai_title": "AI Provider",
    "settings.ai_using": "Cataloga uses {provider} ({model}).",
    "settings.ai_needs_key": "{provider} needs an API key. Add it in "
        + "Advanced settings.",
    "settings.advanced": "Advanced settings",
    "settings.ai_hint": "Choose another AI provider or model. Your API "
        + "key is saved in the macOS Keychain.",
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

    // Settings: file names
    "naming.title": "File names",
    "naming.hint": "Choose how Cataloga names new files. Files already in "
        + "the catalog keep their names.",
    "naming.m1": "Date and topic",
    "naming.m1_example": "2026-07-15_oceanman-malta.pdf",
    "naming.m2": "Source, date and topic",
    "naming.m2_example": "el-nuevo-dia_2026-07-15_oceanman-malta.pdf",
    "naming.m3": "Number and topic",
    "naming.m3_example": "0001_oceanman-malta.pdf",
    "naming.custom": "Custom",
    "naming.template": "Template",
    "naming.template_help":
        "Use {date}, {source}, {topic}, {number} and {original}.",
    "naming.preview": "Preview",
    "naming.media_rule": "Photos, audio and video use the file date and a "
        + "number, for example 2026-07-15_0001.jpg.",
    "naming.duplicate_rule":
        "If a name already exists, Cataloga adds -2, -3 and so on.",
    "naming.changed_note": "Only new files will use this method.",
    "naming.err_empty": "Write a template, or choose one of the 3 methods.",
    "naming.err_no_token": "Add at least one of {date}, {source}, {topic}, "
        + "{number} or {original}.",
    "naming.err_unknown": "{token} is not a valid part. Use {date}, "
        + "{source}, {topic}, {number} or {original}.",
    "naming.err_chars":
        "File names cannot use these characters: / \\ : * ? \" < > |",

    // Account and login
    "auth.setup_title": "Create your account",
    "auth.setup_hint": "This account protects Cataloga on this computer. "
        + "It does not encrypt your files. Keep the password somewhere "
        + "safe: there is no way to recover it.",
    "auth.login_title": "Log in",
    "auth.username": "Username",
    "auth.password": "Password",
    "auth.confirm_password": "Confirm password",
    "auth.create_account": "Create account",
    "auth.log_in": "Log in",
    "auth.log_out": "Log out",
    "auth.password_mismatch": "The passwords do not match.",
    "account.title": "Account",
    "account.change_password": "Change password",
    "account.current_password": "Current password",
    "account.new_password": "New password",
    "account.password_changed": "Password changed. You are still logged in.",

    // Projects (multi-project)
    "header.new_project": "New project…",
    "header.unavailable": "{name} (not available)",
    "header.unavailable_hint": "Folder not found. Open it and remove it "
        + "in Settings.",
    "project.edit_title": "Project settings",
    "project.new_title": "New project",
    "project.folder_locked": "The project folder can't change, because the "
        + "catalog is saved inside it.",
    "project.create": "Create project",
    "project.creating":
        "Creating the project and testing the AI connection...",
    "project.created": "Project created. The AI connection works.",
    "project.opened_existing": "This folder already had a Cataloga "
        + "catalog, so it was added to your projects.",
    "project.cancel": "Cancel",
    "project.remove": "Remove project",
    "project.remove_title": "Remove \"{name}\" from Cataloga?",
    "project.remove_text": "This only takes the project out of your list. "
        + "Its folder, its files, and its catalog stay where they are. "
        + "You can add the same folder again later with New project, and "
        + "everything will be there.",
    "project.remove_confirm": "Remove",
    "project.removed": "Project removed from the list. Its folder and "
        + "files were not changed.",
    "catalog.no_project": "Create a project in Settings to start.",

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
    "error.keyring_failed": "The API key could not be saved in the macOS "
        + "Keychain. Open Keychain Access, make sure the login keychain "
        + "is unlocked, and try again.",
    "error.connection_failed": "Could not connect to the AI provider. "
        + "Check the API key and the model.",
    "error.no_project": "There is no open project. Create one in Settings.",
    "error.project_unavailable": "The project folder {path} is not "
        + "available. Connect the drive or choose another project.",
    "error.project_exists":
        "That folder is already a project. Choose it from the project list.",
    "error.unauthorized": "Log in to use Cataloga.",
    "error.wrong_login": "The username or password is wrong.",
    "error.wrong_password": "The current password is wrong.",
    "error.too_many_attempts": "Too many wrong passwords. Try again in "
        + "{seconds} seconds.",
    "error.password_too_short":
        "The password must have at least 8 characters.",
    "error.password_too_long": "The password is too long. Use 72 "
        + "characters or fewer (fewer with accents or symbols).",
    "error.account_exists": "The account already exists. Log in instead.",
    "error.no_account": "Create the account first.",
    "error.generic": "Something went wrong. Try again.",
};
