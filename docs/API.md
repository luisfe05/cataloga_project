# Cataloga API

The backend is a Flask REST API that only runs on your computer, at `http://127.0.0.1:5050`. The app's screens are its only client. There are 63 endpoints, in `backend/routes/`.

| Rule | What it means |
|---|---|
| Login | Every route needs the session token in the header `Authorization: Bearer <token>`, except the four marked Public. Without it, the answer is `401 unauthorized` |
| Token in the URL | `/documents/<id>/media`, `/browse/media`, and `/browse/thumb` also take the token as `?token=`, because an audio player or an image cannot send headers |
| Active project | The routes for documents, browse, scan, plan, dashboard, and the project's settings work on the active project |
| Errors | An error answers `{"error": {"code": "...", "message": "..."}}` with its HTTP status |

## Accounts (`auth.py`)

| Method | Path | What it does |
|---|---|---|
| GET | `/auth/status` | Public. Says whether any account exists, and the language of the last account that logged in |
| POST | `/auth/register` | Public. Creates an account and logs in. Needs `accepted_terms`. Answers the new recovery key once. A taken username gives `409 username_taken` |
| POST | `/auth/login` | Public. Logs in. After 5 wrong passwords in a row, that username waits 30 seconds |
| POST | `/auth/logout` | Ends the session. The old token stops working |
| POST | `/auth/password` | Changes the password. The session stays open |
| POST | `/auth/terms` | Accepts a new version of the Terms and Privacy, after a login that asked for it |
| POST | `/auth/delete-account` | Needs the password. Deletes the account, its Keychain entries, and its data. Project folders are never touched |
| GET | `/auth/recovery` | Says whether the recovery key was saved to a file, and when |
| POST | `/auth/recovery/key` | Needs the password. Shows the same recovery key again, or makes a new one |
| POST | `/auth/recovery/save` | Writes the key to the file chosen in the Save window. Refused inside a project folder |
| POST | `/auth/recovery/reset` | Public. Sets a new password with the username and the recovery key. 5 wrong tries wait 5 minutes |

## Projects (`projects.py`)

| Method | Path | What it does |
|---|---|---|
| GET | `/projects` | Lists the projects and says which one is active |
| POST | `/projects` | Creates a project in a folder and makes it active, or opens a folder that already has a catalog. With `catalog_only`, nothing is moved or renamed |
| PUT | `/projects/active` | Switches the active project |
| DELETE | `/projects` | Takes a project out of the list. Never deletes its folder, files, or catalog |
| POST | `/projects/folders/suggest` | Asks the AI for a folder tree from the project description. With `industry`, it adds the folders that field usually has. Saves nothing |
| POST | `/projects/folders/learn` | Reads a folder the user organized and answers its tree, marks, and naming style. Saves nothing |
| POST | `/projects/folders/list` | Counts what a folder holds. No AI, and nothing is written |
| POST | `/projects/active/learn` | Uses the tree and the names of the active project's own folder |
| POST | `/projects/folders/inspect` | Says whether a folder looks like a website or a linked project (`index.html`, `package.json`, `.git`, `.prproj`, `.indd`...). Saves nothing |

## Reading the folder (`scan.py`)

| Method | Path | What it does |
|---|---|---|
| GET | `/scan` | How far the reading is: status, files done and total, the current file, and how many files Retry would read |
| POST | `/scan/start` | Reads the active project's folder in place, with its subfolders |
| POST | `/scan/retry` | Reads again only the files that timed out or could not be read |
| POST | `/scan/pause` | Holds the reading before its next file |
| POST | `/scan/resume` | Lets a paused reading go on |

## Documents (`documents.py`)

| Method | Path | What it does |
|---|---|---|
| GET | `/documents` | Lists and searches the documents, with optional filters |
| GET | `/documents/export` | Downloads the worksheet as a CSV file |
| GET | `/documents/<id>` | Gets one document |
| PATCH | `/documents/<id>` | Edits the editable fields. Never the file name or, in a tree project, the folder |
| POST | `/documents/<id>/rename` | Renames one file, only after the user clicks Confirm in the chat |
| POST | `/documents/<id>/move` | Moves one file to another folder of the tree, given as a path like `Research/Photos/Events`. With `create_folder`, every missing level is created first |
| POST | `/documents/<id>/open` | Opens the file with its default app |
| POST | `/documents/<id>/reveal` | Shows the file in Finder, selected |
| GET | `/documents/<id>/preview` | What the preview overlay shows: a picture or text |
| GET | `/documents/<id>/media` | Streams audio or video, so the player can seek |

## Home (`browse.py`)

| Method | Path | What it does |
|---|---|---|
| GET | `/browse` | Lists one folder of the active project, with its folders, files, and catalog data |
| GET | `/browse/thumb` | A photo's small picture, made once and kept in `.cataloga` |
| GET | `/browse/preview` | What the preview overlay shows, for a file cataloged or not |
| GET | `/browse/media` | Streams a recording, so the player can seek |
| POST | `/browse/reveal` | Shows a file or a folder in Finder |
| POST | `/browse/open` | Opens a file with its default app. A path outside the project gives `400 outside_project` |

## To Approve (`plan.py`)

| Method | Path | What it does |
|---|---|---|
| GET | `/plan` | The draft plan, the batches, and whether one is being applied |
| GET | `/plan/count` | How many proposals nobody has approved or skipped: the number in the sidebar |
| PUT | `/plan/leave` | Marks a folder Leave as is, or unmarks it |
| PUT | `/plan/items` | Approves or skips rows, by `ids` or `all` |
| PATCH | `/plan/items/<id>` | Changes a row's folder or name before applying |
| POST | `/plan/apply` | Applies the approved rows as a batch, or resumes a paused one |
| POST | `/plan/resume` | Goes on with a batch that paused (the drive is back) |
| POST | `/plan/undo` | Undoes a batch, the newest one when none is named |
| GET | `/plan/progress` | How far a batch is while it is applied or undone |
| GET | `/batches` | Every batch applied so far, with its counts |

## Settings (`settings.py`)

| Method | Path | What it does |
|---|---|---|
| GET | `/settings` | The active project's settings, its folder tree with counts, and the app language |
| PUT | `/settings` | Saves the project name, the naming method, the folder tree, and the language. Folder changes in a project already read wait in To Approve |
| PATCH | `/settings` | Saves one General field, `{key, value}`: `language` or `server_url` |
| POST | `/settings/categories/suggest` | Asks the AI for categories for an industry. Saves nothing |
| POST | `/settings/sheet/suggest` | Asks the AI to write the project sheet from a sample of the folder. Saves nothing |
| GET | `/settings/ai-status` | Which provider reads the files and whether it connects. Never the key |
| PUT | `/settings/ai-provider` | Saves the provider, model, and API key of one role: `text` (default), `fallback`, or `media` (Gemini only) |
| DELETE | `/settings/ai-provider/<role>` | Takes the fallback or media provider away. The key stays in the Keychain |
| POST | `/settings/ai-provider/test` | Tests the connection to the AI provider, through the server URL if one is sent |
| POST | `/settings/ai-provider/legacy-key` | Answers "Is it yours?" about an old shared key: `claim` or `decline` |

## Ask Cataloga and Dashboard

| Method | Path | What it does |
|---|---|---|
| POST | `/chat` | Answers one chat message with one action from a fixed list. Never changes anything by itself |
| GET | `/dashboard/stats` | The numbers for the Dashboard |
