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
    "catalog.search": "Search the catalog",
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
    "summary.read_more": "Read more",
    "summary.show_less": "Show less",
    "catalog.summary_placeholder": "Manual Summary",
    "catalog.saving": "Saving...",
    "catalog.saving_summary":
        "Saving and updating the summary with your edit...",
    "catalog.saved": "Saved.",
    "catalog.saved_summary": "Saved. The summary was updated using your edit.",
    "catalog.save_failed": "Could not save.",
    "catalog.edit_banner": "Editing. Click a cell to change it. It saves "
        + "when you leave the cell or press Enter. Automatic refresh is "
        + "paused.",
    "catalog.summary_limit": "Summaries can have up to 100 characters.",
    "catalog.summary_count": "{n} / 100",
    "catalog.old_inbox_warning": "Your old Inbox folder still has files. "
        + "Move them to Drop Zone to catalog them.",
    "catalog.no_folder": "Go to Settings to choose the AI provider.",
    "catalog.empty": "Drop files into the Drop Zone folder inside {path} "
        + "and they will appear here once they are classified.",
    "catalog.no_match": "No files match your search.",
    "catalog.progress": "Catalog progress",
    "scan.running": "Reading {done} of {total} files: {file}",
    "scan.paused": "Paused at {done} of {total} files.",
    "scan.done": "All {total} files were read. Nothing was moved or renamed.",
    "scan.idle": "",
    "scan.stopped": "Reading stopped at {done} of {total} files.",
    "scan.pause": "Pause",
    "scan.resume": "Resume",
    "catalog.progress_percent": "{n}% classified",
    "catalog.load_failed": "Could not load the catalog: {message}",
    "catalog.backend_down": "the app's backend is not responding.",
    "catalog.export_saved": "Worksheet saved to {path}",
    "catalog.export_failed": "Could not save the worksheet.",
    "catalog.filter_category_all": "Category: All",
    "catalog.filter_subcategory_all": "Subcategory: All",
    "catalog.more_columns": "More columns",
    "catalog.col_category": "Category",
    "catalog.col_subcategory": "Subcategory",
    "catalog.col_keywords": "Keywords",
    "catalog.col_counterparty": "Counterparty",
    "catalog.col_confidentiality": "Confidentiality",
    "catalog.col_owner": "Owner",
    "catalog.col_effective_start": "Effective start",
    "catalog.col_effective_end": "Effective end",
    "catalog.col_date_from": "Date from",
    "catalog.date_from_photo": "Photo (taken)",
    "catalog.date_from_content": "Content",
    "catalog.date_from_metadata": "File metadata",
    "catalog.date_from_file": "File date",
    "catalog.date_from_photo_stamp": "Photo stamp",
    "catalog.date_from_name": "File name or folder",
    "catalog.col_folder_reason": "Why this folder",
    "catalog.col_confidence": "Confidence",
    "catalog.confidence_high": "High",
    "catalog.confidence_medium": "Medium",
    "catalog.confidence_low": "Low",
    "catalog.note_low_confidence": "Low confidence",
    "catalog.not_in_list": "{value} (not in list)",
    "catalog.note_duplicate": "Duplicate of {name}",
    "catalog.note_no_category": "Category not in the project list",
    "catalog.note_no_folder": "No folder fits this file",
    "catalog.col_folder": "Folder",
    "catalog.filter_folder_all": "Folder: All",
    "catalog.filter_subfolder_all": "Subfolder: All",
    "catalog.in_drop_zone": "Drop Zone",
    "catalog.suggested_folder": "Suggested: {folder}",
    "catalog.proposed": "Proposed: {folder} / {name}",
    "catalog.same_folder": "same folder",
    "catalog.create_and_move": "Create folder and move",
    "catalog.move_to": "Move to…",
    "catalog.moving": "Moving...",
    "catalog.moved": "Moved to {folder}",
    "catalog.note_media": "Audio and video reading is coming soon",
    "catalog.note_media_length":
        "Audio and video reading is coming soon. Length {length}",
    "catalog.note_image": "Could not read the image",
    "catalog.note_scan": "Could not read the scanned pages",
    "catalog.note_too_big": "File is larger than 50 MB, so it was not read",
    "catalog.note_topic": "No topic could be found in the photo",
    "catalog.note_missing": "Missing: {fields}",
    "catalog.keywords_limit": "Use up to 5 keywords, separated by commas, "
        + "with up to 40 characters each.",
    "catalog.counterparty_limit": "Counterparty can have up to 100 characters.",
    "catalog.date_format": "Write the date as YYYY-MM-DD, like 2026-07-15.",

    // Dashboard
    "dash.classified": "Documents Classified",
    "dash.review": "Needs Manual Review",
    "dash.sources": "Sources Tracked",
    "dash.breakdown": "Media Type Breakdown",
    "dash.activity": "Recent Activity",
    "dash.empty": "No activity yet. Drop files into the Drop Zone to start.",
    "dash.finding_review_one": "1 document needs manual review.",
    "dash.finding_review": "{n} documents need manual review.",
    "dash.finding_done": "Every document is classified.",
    "dash.review_button": "Review in Catalog",
    "dash.load_failed": "Could not load the dashboard: {message}",
    "dash.of_total": "of {n} documents",
    "dash.no_documents": "No documents yet",

    // Chat
    "chat.open_label": "Open Cataloga assistant",
    "chat.title": "Cataloga assistant",
    "chat.close": "Close",
    "chat.empty_title": "How can I help with this project?",
    "chat.empty_hint": "I can find files, filter the catalog, summarize the "
        + "project, and propose new names. I never rename a file without your "
        + "OK.",
    "chat.example_summary": "Summarize this project",
    "chat.example_press": "Find press clippings",
    "chat.example_review": "Show items in Manual Review",
    "chat.example_rename": "Rename a file",
    "chat.example_rename_prompt": "Rename the file ",
    "chat.placeholder": "Ask about your files…",
    "chat.send": "Send",
    "chat.thinking": "Thinking…",
    "chat.sources": "Sources",
    "chat.filters_applied": "Catalog filters applied",
    "chat.open_catalog": "Open Catalog",
    "chat.rename_title": "Proposed new name",
    "chat.confirm": "Confirm",
    "chat.cancel": "Cancel",
    "chat.renamed": "Renamed to {name}",
    "chat.rename_cancelled": "Cancelled. Nothing changed.",
    "chat.move_title": "Move {name} to another folder",
    "chat.summary_total": "Documents",
    "chat.summary_dates": "Dates",
    "chat.summary_sources": "Top sources",
    "chat.notice_invalid_reply": "Sorry, I could not understand that. Try "
        + "asking in a different way.",
    "chat.notice_ai_unavailable": "The AI provider did not answer. Check "
        + "Settings > AI Provider and try again.",
    "chat.notice_no_documents": "I could not find documents that match. Try "
        + "other words.",
    "chat.notice_no_filters": "I could not turn that into catalog filters. "
        + "Try a type, a source, or a status.",
    "chat.notice_rename_not_found": "I could not find that file in this "
        + "project. Try its name or its date.",
    "chat.notice_rename_invalid": "That name has no valid characters. Use "
        + "letters and numbers.",
    "chat.notice_rename_same": "The file already has that name.",
    "chat.notice_move_unavailable": "This project sorts files by type, so "
        + "files are not moved between folders.",
    "chat.notice_rename_unavailable": "This file keeps its name: the project catalogs in place, or other programs look for it by name.",
    "chat.notice_move_invalid": "That folder is not in this project. "
        + "Use one of the project's folders.",
    "chat.notice_move_same": "The file is already in that folder.",

    // File links: open, preview, show in Finder
    "files.open": "Open file",
    "files.preview": "Preview",
    "files.reveal": "Show in Finder",
    "files.show_in_catalog": "Show in Catalog",
    "files.not_found": "File not found. It may have been moved or "
        + "deleted.",
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
        + "keys are saved in the macOS Keychain.",
    "settings.ai_text_title": "Text and images",
    "settings.ai_fallback_title": "Fallback (optional)",
    "settings.ai_fallback_hint": "Answers when the main provider fails or "
        + "cannot read a file. With a Claude key saved, Claude is the "
        + "fallback unless you choose another.",
    "settings.ai_media_title": "Audio and video",
    "settings.ai_media_hint": "Only Google Gemini reads audio and video. "
        + "Paid Gemini keys are not used to train models. Free keys are.",
    "settings.ai_none": "None",
    "settings.ai_using_fallback": "Fallback: {provider} ({model}).",
    "settings.server_title": "Server (optional)",
    "settings.server_hint": "A Cataloga server that holds the API keys. "
        + "Leave it empty to call the providers from this computer.",
    "settings.server_url": "Server URL",
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
    "naming.m1_example": "date_topic-name.pdf",
    "naming.m2": "Source, date and topic",
    "naming.m2_example": "source-name_date_topic-name.pdf",
    "naming.m3": "Number and topic",
    "naming.m3_example": "0001_topic-name.pdf",
    "naming.m4": "Topic, source and date",
    "naming.m4_example": "topic-name_source-name_date.pdf",
    "naming.m5": "Event and year, plus a number",
    "naming.m5_example": "Event-Name_1998_1.jpg (the file takes the name of its "
        + "event folder)",
    "naming.custom": "Custom",
    "naming.keep": "Keep original names",
    "naming.keep_example": "the-name-you-gave-it.pdf",
    "naming.preview": "Preview",
    "naming.stamp_order": "Dates stamped on photos",
    "naming.stamp_month": "Month first (11 13 '97)",
    "naming.stamp_day": "Day first (13 11 97)",
    "naming.photo_date_rule": "A photo's date comes from the date printed or "
        + "written on it, then from a camera's EXIF (a scanner's EXIF is "
        + "the day of the scan), then from a year in its name or folder.",
    "naming.media_rule": "Photos are named with this method from what they "
        + "show, and audio and video from the title in their tags. Files "
        + "with nothing to read use their date and a number, for example "
        + "2026-07-15_0001.jpg, or only the number when no date is known.",
    "naming.duplicate_rule": "Without a reliable date the name has no date "
        + "part. If a name already exists, the new file gets _2, _3 and so "
        + "on; the first one keeps its name.",
    "naming.version_rule": "A version mark in the original name (v01, v02) "
        + "stays at the end of the new name.",
    "naming.path_rule": "Names are shortened so the full path stays under "
        + "240 characters, the Windows limit.",
    "naming.style": "Style",
    "naming.keep_accents": "Keep accents (Día, not Dia)",
    "naming.changed_note": "Only new files will use this method.",
    "naming.blocks_add": "Click the parts in order",
    "naming.chosen": "Your file name",
    "naming.chosen_empty": "No parts yet. Click Topic, Source, Date or "
        + "Original above.",
    "naming.block_topic": "Topic",
    "naming.block_source": "Source",
    "naming.block_date": "Date",
    "naming.block_number": "Number",
    "naming.block_original": "Original",
    "naming.separator": "Separator",
    "naming.move_left": "Move left",
    "naming.move_right": "Move right",
    "naming.remove_block": "Remove part",
    "naming.extension_note": "The extension (.pdf, .jpg) is added on its own. "
        + "A number is added only when the name already exists.",
    "naming.legacy": "Saved custom name: {template}. Click parts to replace it.",
    "naming.err_no_blocks": "Click at least one part for the file name.",
    "naming.err_empty": "Write a template, or choose one of the 4 methods.",
    "naming.err_no_token": "Add at least one of {date}, {source}, {topic}, "
        + "{number}, {topic_number} or {original}.",
    "naming.err_unknown": "{token} is not a valid part. Use {date}, "
        + "{source}, {topic}, {number}, {topic_number} or {original}.",
    "naming.err_chars":
        "File names cannot use these characters: / \\ : * ? \" < > |",

    // Settings: categories (Digital Archiving Guideline)
    "categories.title": "Categories",
    "categories.hint": "Cataloga sorts each new document into one of these "
        + "categories. Write your industry and click Suggest categories, "
        + "then edit the list.",
    "categories.industry": "Industry",
    "categories.industry_placeholder": "For example: sports documentary",
    "categories.suggest": "Suggest categories",
    "categories.suggesting": "Asking the AI provider for categories...",
    "categories.suggested": "The list was replaced. Click Save to keep it.",
    "categories.need_industry": "Write the industry first.",
    "categories.add": "Add category",
    "categories.remove": "Remove category",
    "categories.name_placeholder": "Category",
    "categories.subs_placeholder": "Subcategories, separated by commas",
    "categories.rules": "Up to 10 categories. A document that fits none goes "
        + "to Manual Review. Documents keep their category if you change "
        + "the list.",

    // Folder tree of a project
    "sheet.title": "About this project",
    "sheet.hint": "A short sheet of what this work is. Cataloga reads it "
        + "before every file, so the classification understands the work. "
        + "Write it, or let the AI write it from a sample of the folder, "
        + "then edit it.",
    "sheet.label": "Project sheet",
    "sheet.placeholder": "Work: ...\nIndustry: ...\nParts: ...\nFile "
        + "types: ...\nNaming style: ...",
    "sheet.suggest": "Write it for me",
    "sheet.need_folder": "Choose the project folder first.",
    "sheet.suggesting": "Reading a sample of the folder...",
    "sheet.suggested": "Edit the sheet if you like, then click Save.",
    "folders.title": "Folders",
    "folders.hint": "Cataloga files each new document in the folder that "
        + "fits its content. Describe the project and click Suggest folders, "
        + "then edit the tree before you create the project.",
    "folders.description": "What is this project about?",
    "folders.description_placeholder": "For example: documentary about a "
        + "Puerto Rican swimmer who competes in Malta",
    "folders.suggest": "Suggest folders",
    "folders.file_types": "Start from file types",
    "folders.learn": "Learn from my folder",
    "folders.need_folder": "Choose the project folder first.",
    "folders.learning": "Reading the folder as it is...",
    "folders.learned": "{folders} folders and {files} files read. "
        + "{description} For example: {examples}. Edit anything, then "
        + "create the project: nothing on the disk changes.",
    "folders.suggesting": "Asking Ollama Cloud for folders...",
    "folders.suggested": "Edit the folders, then create the project.",
    "folders.need_description": "Describe the project first.",
    "folders.add": "Add folder",
    "folders.remove": "Remove folder",
    "folders.remove_with_subs": "Remove \"{name}\" and its subfolders?",
    "folders.has_documents": "{n} documents are in this folder, so it stays.",
    "folders.name_placeholder": "Folder name",
    "folders.inside": "Inside",
    "folders.top_level": "Top level",
    "folders.unnamed": "(no name)",
    "folders.rules": "Up to six levels deep, 20 top folders and 10 "
        + "subfolders in each. Folders already created can't be renamed; "
        + "you can add folders and remove empty ones. Removed folders stay "
        + "on the disk. A folder with subfolders only holds files in them.",
    "folders.flag_events": "Events",
    "folders.flag_events_hint": "Holds one folder per event, named "
        + "Event_Year. Cataloga proposes new event folders here, and only "
        + "here, and files in them take the event's name plus a number.",
    "folders.flag_fallback": "Catch-all",
    "folders.flag_fallback_hint": "Files that fit nowhere else go here "
        + "instead of Manual Review.",
    "folders.flag_auto": "No asking",
    "folders.flag_auto_hint": "New files that belong here are filed "
        + "without asking (projects without a Drop Zone).",
    "folders.numbered": "Number new folders (01_, 02_)",
    "folders.err_depth": "Folders can go six levels deep at most.",
    "folders.err_none": "Add at least one folder.",
    "folders.err_empty": "Every folder needs a name.",
    "folders.err_long": "\"{name}\" is too long. Use 60 characters or fewer.",
    "folders.err_chars": "\"{name}\" has a character folders can't use: "
        + "/ \\ : * ? \" < > |",
    "folders.err_reserved": "\"{name}\" can't be a folder name on Mac or "
        + "Windows.",
    "folders.err_twin": "Two folders are named \"{name}\" in the same place.",
    "folders.err_subs": "A folder can have 10 subfolders at most.",

    // Account and login
    "auth.register_title": "Create an account",
    "auth.register_hint": "Each account on this computer has its own "
        + "project list and settings. Catalogs stay inside each project "
        + "folder. There is no way to recover a lost password.",
    "auth.login_title": "Log in",
    "auth.username": "Username",
    "auth.password": "Password",
    "auth.confirm_password": "Confirm password",
    "auth.create_account": "Create account",
    "auth.log_in": "Log in",
    "auth.log_out": "Log out",
    "auth.password_mismatch": "The passwords do not match.",
    "auth.need_account": "Create an account",
    "auth.have_account": "I already have an account",
    "auth.forgot": "Forgot your password?",
    "auth.forgot_hint": "Passwords cannot be recovered: Cataloga has no "
        + "email. Your projects and files stay intact in their folders. "
        + "Create a new account to keep working.",
    "account.title": "Account",
    "account.hint": "Each account on this computer has its own projects "
        + "and settings.",
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
    "project.mode_place": "Read the folder in place",
    "project.mode_place_hint": "Every file is read where it is, subfolders "
        + "included. Nothing moves or renames until you approve a plan",
    "project.mode_tree": "Drop Zone",
    "project.mode_tree_hint": "Cataloga creates the folders now and files "
        + "what you drop into Drop Zone",
    "project.catalog_only": "Catalog only: read and catalog the files where "
        + "they are. Never move or rename them",
    "project.catalog_only_hint": "For websites, code, and edits that link "
        + "their files by path (InDesign, Premiere, After Effects, Final "
        + "Cut). Cataloga reads, summarizes and catalogs each file in "
        + "place. There is no folder tree and no Drop Zone.",
    "project.linked_advice": "This folder looks like a website or a linked "
        + "project ({markers}). Moving or renaming its files would break "
        + "it. Catalog only is ticked for you: it keeps every link working.",
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
    "value.Renamed": "Renamed",
    "value.Public": "Public",
    "value.Internal": "Internal",
    "value.Confidential": "Confidential",
    "value.Restricted": "Restricted",

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
    "error.invalid_role": "That provider role does not exist.",
    "error.invalid_server_url": "The server URL must start with http:// "
        + "or https://.",
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
    "error.username_taken": "That username is taken.",
    "error.invalid_username": "Use 3 to 30 letters, digits, dots, "
        + "underscores or hyphens.",
    "error.generic": "Something went wrong. Try again.",
    "error.invalid_name": "The new name has no valid characters.",
    "error.file_missing": "The file is missing or outside the project folder.",
    "error.invalid_categories": "The category list is not valid. Check the "
        + "names and keep 10 categories or fewer.",
    "error.suggest_failed":
        "The AI provider did not suggest categories. Try again.",
    "error.no_provider": "Choose an AI provider in Settings first.",
    "error.nothing_to_learn": "This folder has no subfolders to learn from.",
    "error.invalid_folders": "The folder tree is not valid. Check the names.",
    "error.invalid_sheet": "The project sheet is too long. Use 1,500 "
        + "characters or fewer.",
    "error.invalid_description":
        "The description must be 300 characters or fewer.",
    "error.folder_not_empty": "A folder with documents can't be removed.",
    "error.unknown_folder": "That folder is not in this project.",
    "error.not_tree_project":
        "This project sorts files by type, so files are not moved.",
    "error.use_move": "Use Move to change a document's folder.",
    "error.catalog_only": "This project catalogs files in place: nothing is "
        + "moved or renamed.",
    "error.protected_name": "Other programs look for this file by name, so "
        + "it keeps it.",
    "error.no_api_key": "Ollama Cloud has no API key yet. Add it in Advanced "
        + "settings, or build the folders by hand.",
    "error.suggest_folders_failed":
        "The AI provider did not suggest folders. Try again.",
};
