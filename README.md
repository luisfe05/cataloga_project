# Cataloga

Cataloga is a Mac desktop app that classifies, renames, and summarizes research files, and keeps them in a searchable catalog.

This is a Holberton School Portfolio Project.

## The problem it solves

Research material piles up fast: scans, PDFs, photos, audio, and video, with names like `IMG_4521.jpg` or `scan0003.pdf`. A name like that says nothing about what is inside the file. Tools like Google Drive keep the files safe, but they do not describe them or put them in order. Finding the right document weeks later means opening files one by one.

Cataloga reads each new file, decides what kind of material it is, gives it a name that makes sense, writes a short summary, and adds it to a catalog you can search, filter, and export.

## Features

| Feature | What it does |
|---|---|
| Drop Zone | Each project has a Drop Zone folder. Every file you drop there is processed. Files already in the project folder are never moved |
| Project folders | When you create a project, you describe it in one or two sentences. The AI proposes a tree of folders (two levels) and you edit it before you create the project |
| Automatic classification | The AI reads each file and puts it in the folder of the tree that fits its content. The media type (Press, Documents, Photos, Audio, Video) stays as a column. If no folder fits, the file stays in the Drop Zone in Manual Review with a suggested folder. Projects made before this change keep their five media-type folders |
| 100-character summary | The AI writes a summary of up to 100 characters for every readable document. Files it cannot read go to Manual Review instead of being skipped |
| File naming methods | Every new file gets a readable name: date and topic, source, date and topic, number and topic, or your own template |
| Several projects | Each project has its own folder and its own catalog. Switch between them from the sidebar |
| Login | One local account protects the app. The password is saved only as a bcrypt hash |
| Chatbot | Ask Cataloga finds documents, filters the catalog, summarizes the project, and proposes new file names or a move to another folder. A file is only renamed or moved after you click Confirm |
| Open, preview, and Finder | Click a file name to open it, the eye icon (or the space bar) to preview it with Quick Look, and the folder icon to show it in Finder |
| English and Spanish | The interface is in English by default. Spanish (Latin America) can be chosen in Settings |
| Dashboard | Counts of classified documents and documents that need review, a breakdown by media type, and the latest activity |
| Editable worksheet | Edit Mode lets you fix the source, date, summary, and status. The worksheet can be downloaded as a CSV file |

## Tech stack

| Part | Technology |
|---|---|
| Desktop window | pywebview |
| Frontend | HTML, CSS, and plain JavaScript |
| Backend | Flask REST API on `127.0.0.1:5050` |
| Database | SQLite, one catalog per project |
| AI | Ollama Cloud with `gemma4:31b` by default. Gemini, Groq, Claude, xAI, and OpenAI can be chosen in Settings |
| API keys | The macOS Keychain, through keyring |
| Packaging | PyInstaller |
| Tests | pytest |

## How to run from source

Run these commands from the `cataloga` folder.

| Step | Command |
|---|---|
| 1. Create a virtual environment | `python3 -m venv venv` |
| 2. Turn it on | `source venv/bin/activate` |
| 3. Install the packages | `pip install -r requirements.txt` |
| 4. Start the app | `python main.py` |

The app opens in its own window. When it runs from source, it keeps its data (the project list and the account) in the `database/` folder.

To use Ollama Cloud, the app needs an API key. Save it once in the Keychain with the command below. It asks for the key without showing it.

```
python -m keyring set cataloga ollama
```

When running from source, the key can also come from the `OLLAMA_API_KEY` environment variable or from a line `OLLAMA_API_KEY=...` in a `.env` file. The `.env` file is ignored by git and is never included in the Mac app.

## How to build the Mac app

With the virtual environment on, run this from the `cataloga` folder:

```
./build.sh
```

| Item | Where |
|---|---|
| The app | `dist/Cataloga.app` |
| Its data (project list and account) | `~/Library/Application Support/Cataloga/` |

## How to use

| Step | What to do |
|---|---|
| 1. Create your account | The first time Cataloga opens, choose a username and a password (at least 8 characters). After that, log in |
| 2. Create a project | In Settings, type a name, pick a folder, and describe the project. Click Suggest folders, edit the tree, and click Create project. Cataloga creates a Drop Zone folder and the folders of the tree |
| 3. Drop files | Put new files in the project's Drop Zone. Every few seconds, Cataloga classifies each one, renames it, writes its summary, and moves it to its folder. Files with no folder stay in the Drop Zone: use Move, or Create folder and move, in Catalog. If the folder was the only thing missing, the file becomes Classified |
| 4. Review the Catalog | Search, filter by media type or source, and open the Manual Review tab to see the files that need a summary or a source. Turn on Edit Mode to fix a field |
| 5. Use the chat | Click the round button at the bottom right and ask, for example, "Find press clippings" or "Summarize this project". If the chat proposes a new name, nothing changes until you click Confirm |

If you forget your password, close Cataloga and delete `account.json` from the data folder (`~/Library/Application Support/Cataloga/` for the Mac app, `database/` when running from source). Then open Cataloga and create a new account. Your projects and their files are not touched.

To take a project out of the list, open Settings and click Remove project. Its folder, files, and catalog are never deleted, so you can add the same folder again later.

## File naming methods

Choose the method in Settings. Files already in the catalog keep their names.

| Method | Example |
|---|---|
| Date and topic | `date_topic-name.pdf` |
| Source, date and topic | `source-name_date_topic-name.pdf` |
| Number and topic | `0001_topic-name.pdf` |
| Topic, source and date | `topic-name_source-name_date.pdf` (new projects start here) |
| Custom | Click the parts in order (Topic, Source, Date, Original) and pick `_` or `-` between them. The extension is added on its own |
| Style | `topic-name` (lowercase) or `Topic-Name` (Title-Case), per project. Accents are dropped (`Dia`) unless Keep accents is on (`Día`) |

| Rule | What happens |
|---|---|
| Topic | The AI gives a short topic in the same request as the source and date |
| No date | The name has no date part; the catalog shows the date empty |
| No source | That part is left out |
| No topic | The original file name is used |
| Photos | Named with the project's method from what the photo shows |
| Audio and video | Named with the project's method from the title in their tags |
| Files with nothing to read | Their date and a number, for example `2026-07-15_0001.jpg`. If only the disk date is known, `undated_0001.jpg` |
| Name already taken | The new file gets `_2`, `_3`, and so on; the first one keeps its name |
| Versions | A version mark in the original name (`v01`, `draft-3`) stays at the end of the new name |
| Long paths | The topic, then the source, are shortened a word at a time so the full path stays under 240 characters (the Windows limit). If it still cannot fit, the file stays put, in Manual Review |
| Rename from the chat | Uses the same cleaning rules, only after you click Confirm |

## API endpoints

The backend runs on `http://127.0.0.1:5050`. Routes that need login ask for the session token in the header `Authorization: Bearer <token>`. Without it, the answer is `401 unauthorized`. The routes for documents, dashboard, and the AI provider work on the active project.

| Method | Path | Login | What it does |
|---|---|---|---|
| GET | `/auth/status` | No | Says whether the account exists, and the app language |
| POST | `/auth/setup` | No | Creates the account (only once) and logs in |
| POST | `/auth/login` | No | Logs in. After 5 wrong passwords in a row, waits 30 seconds |
| POST | `/auth/logout` | Yes | Ends the session |
| POST | `/auth/password` | Yes | Changes the password. The session stays open |
| GET | `/documents` | Yes | Lists and searches the documents, with optional filters |
| GET | `/documents/export` | Yes | Exports the worksheet as a CSV file |
| GET | `/documents/<id>` | Yes | Gets one document |
| PATCH | `/documents/<id>` | Yes | Edits the source, date, summary, media type, or status |
| POST | `/documents/<id>/rename` | Yes | Renames one file, only after the user confirms in the chat |
| POST | `/documents/<id>/move` | Yes | Moves one file to another folder of the project's tree. Creates the folder only when asked |
| POST | `/documents/<id>/open` | Yes | Opens the file with its default app |
| POST | `/documents/<id>/reveal` | Yes | Shows the file in Finder, selected |
| POST | `/documents/<id>/preview` | Yes | Opens a Quick Look preview of the file |
| GET | `/dashboard/stats` | Yes | Gives the numbers for the dashboard |
| GET | `/settings` | Yes | Gives the active project's settings and the language |
| PUT | `/settings` | Yes | Saves the project name, the naming template, the folder tree (new folders only; folders with documents stay), and the language |
| PUT | `/settings/ai-provider` | Yes | Saves the AI provider, model, and API key |
| POST | `/settings/ai-provider/test` | Yes | Tests the connection to the AI provider |
| GET | `/projects` | Yes | Lists the projects and says which one is active |
| POST | `/projects` | Yes | Creates a project with its folder tree, or opens a folder that already has a catalog |
| POST | `/projects/folders/suggest` | Yes | Asks Ollama Cloud for a folder tree from the project description. Saves nothing |
| PUT | `/projects/active` | Yes | Switches the active project |
| DELETE | `/projects` | Yes | Takes a project out of the list. Never deletes its folder or files |
| POST | `/chat` | Yes | Answers a chat message with one action from a fixed list. Never changes anything |

## Project structure

| Folder or file | What it holds |
|---|---|
| `main.py` | Starts the Flask server, the folder watcher, and the desktop window |
| `build.sh` | Builds `Cataloga.app` with PyInstaller |
| `assets/` | The app icon |
| `backend/app.py` | Creates the Flask app and registers the routes |
| `backend/folder_watcher.py` | Checks the active project's Drop Zone every few seconds |
| `backend/config/` | The project list, the account, and the app settings |
| `backend/db/` | The database schema and CatalogRepository, which does every database read and write |
| `backend/models/` | The Document class, one row of the worksheet |
| `backend/pipeline/` | ClassificationPipeline, FileOrganizer, file naming, the chat assistant, and the AI provider clients |
| `backend/routes/` | The API endpoints |
| `frontend/` | The app screens: `index.html`, `css/`, `js/` (with `js/lang/` for English and Spanish), fonts, and icons |
| `tests/` | The pytest tests |
| `qa/` | The answer key for the 100-file test batch |
| `database/` | Data when running from source (not tracked by git) |

## Tests

Run these from the `cataloga` folder with the virtual environment on. The AI calls are replaced with fakes, so the tests do not need an API key or internet.

| Check | Command | Result |
|---|---|---|
| Tests | `python -m pytest` | 333 tests in 13 test files |
| Code style | `pycodestyle --exclude=venv,build,dist .` | No errors |

`pycodestyle` is not in `requirements.txt`. Install it with `pip install pycodestyle`.

## Author

Luis Felipe González López, GitHub [luisfe05](https://github.com/luisfe05), Holberton School Puerto Rico.
