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
| Learns from your moves | Every time you move a file to another folder (Move, Create folder and move, or the chat after Confirm), Cataloga remembers it. The AI reads the latest ten moves of the project before it files a new document, so the same kind of file lands where you put it |
| Every format | Text and code of any kind are read by their bytes, not by a list of extensions, and big ones only at the start. Design files show their picture (Photoshop's flattened image, Illustrator's first page, Sketch's preview, InDesign's XMP thumbnail) or their XMP title and author. Zips are cataloged from the list of what they hold, never unpacked. An unknown format is cataloged from its name, its folder and the files next to it: no format goes to Manual Review only because the app cannot read it |
| Read the folder in place | New projects start without a Drop Zone: Cataloga reads every file where it is, subfolders included, and catalogs it without moving or renaming. The Catalog shows how far the reading is, with Pause and Resume. A file that did not change is never read twice. Hidden files, `.git`, `node_modules`, `.cataloga` and links are never read. What Cataloga would do with each file (its folder and its name) is kept for the organization plan, which comes next. Drop Zone stays as a choice for new projects, and older projects keep it |
| Scanned photos | A photo goes to the AI at 1,600 px with its four corners enlarged, so a date stamped by the camera (`11 13 '97`) or written by hand can be read. A scan lying on its side is turned before it is read; the original file is never changed. TIFF scans of any size are read: the size limit applies to what is sent, not to the file. The date of a photo comes from the stamp (Date from: Photo stamp), then from a camera's EXIF (a scanner's EXIF is the day of the scan and never counts), then from a year in the file name or its folders. Settings says whether stamps read month first or day first |
| Catalog only | A project mode for websites, code, and edits that link their files by path (InDesign, Premiere, After Effects, Final Cut). Cataloga reads, summarizes and catalogs each file where it is. Nothing is moved or renamed, there is no folder tree and no Drop Zone. Reading the whole folder in place comes with the in-place scanner |
| Event folders | A folder marked Events holds one folder per event, named Event_Year. The AI files each photo in its event, proposes a new event folder there (and only there) when the event has none, and a file in an event folder takes the event's year as its date when nothing better is known |
| Folder trees | A project's folders can go six levels deep. The AI chooses one folder path per file. A folder marked Catch-all receives what fits nowhere else, as a classified file. Folders already created are never renamed |
| Automatic classification | One AI request per file fills its whole card: media type, summary, source, date, topic, keywords, the folder of the tree that fits its content, one line on why (the Why this folder column), and how sure the AI was. The AI sees the file name, its folder, the other files next to it, the file's own metadata, and an extract of the content. A meaningful name counts as evidence; camera and scanner names are ignored; when name and content disagree, the content wins and the card says so. If no folder fits, the file stays in the Drop Zone in Manual Review with a suggested folder. Projects made before the folder trees keep their five media-type folders |
| Industry conventions | A built-in list of how each field organizes its archive (legal, construction, web and code, film and video, photo archive, documentary, library, general): typical folders, a naming pattern, and rules. The folder suggestion uses it. When a new project's folder looks like a website or a linked edit, Settings says so |
| Project sheet | A short text of what the work is (Settings > About this project). Write it, or click Write it for me: the AI reads a sample of the folder (its structure, some file names, a few extracts) and writes it. Cataloga reads the sheet before every file, so the classification understands the work |
| 100-character summary | The AI writes a summary of up to 100 characters for every readable document |
| Manual Review | Only these send a file to Manual Review: it could not be read, the AI had low confidence, no folder fits, it is a duplicate, or (later) its path is too long. A missing source or date never does; the catalog just shows the field empty |
| File naming methods | Every new file gets a readable name: date and topic, source, date and topic, number and topic, or your own template |
| Several projects | Each project has its own folder and its own catalog. Switch between them from the sidebar |
| Login | Accounts on this computer. Each account has its own project list and settings. Passwords are saved only as bcrypt hashes |
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
| AI | Ollama Cloud with `gemma4:31b` by default. Gemini, Groq, Claude, xAI, and OpenAI can be chosen in Settings. A fallback provider answers when the main one fails (Claude, when its key is saved). Only Gemini reads audio and video. An optional server URL sends every request through a Cataloga server that holds the keys |
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

The app opens in its own window. When it runs from source, it keeps its data (the accounts and each account's project list) in the `database/` folder.

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
| Its data (accounts and project lists) | `~/Library/Application Support/Cataloga/` |

## How to use

| Step | What to do |
|---|---|
| 1. Create an account | Choose a username (3 to 30 letters, digits, dots, underscores or hyphens) and a password (at least 8 characters). Each person on the computer can have their own account, with their own projects. After that, log in |
| 2. Create a project | In Settings, type a name, pick a folder, and describe the project. Click Suggest folders, edit the tree (folders inside folders, up to six levels; each folder can be marked Events, Catch-all, or No asking), and click Create project. Cataloga creates a Drop Zone folder and the folders of the tree. Number new folders gives them a 01_, 02_ prefix |
| 3. Drop files | Put new files in the project's Drop Zone. Every few seconds, Cataloga classifies each one, renames it, writes its summary, and moves it to its folder. Files with no folder stay in the Drop Zone: use Move, or Create folder and move, in Catalog. If the folder was the only thing missing, the file becomes Classified |
| 4. Review the Catalog | Search, filter by media type or source, and open the Manual Review tab to see the files that need a person. The note under the status says why. More columns shows Why this folder and Confidence. Turn on Edit Mode to fix a field |
| 5. Use the chat | Click the round button at the bottom right and ask, for example, "Find press clippings" or "Summarize this project". If the chat proposes a new name, nothing changes until you click Confirm |

Cataloga has no email, so a lost password cannot be recovered. Create a new account and add your project folders to it again: the projects and their files are not touched, because each catalog lives inside its project folder. Accounts made with an older version keep working after the update.

To take a project out of the list, open Settings and click Remove project. Its folder, files, and catalog are never deleted, so you can add the same folder again later.

## File naming methods

Choose the method in Settings. Files already in the catalog keep their names.

| Method | Example |
|---|---|
| Date and topic | `date_topic-name.pdf` |
| Source, date and topic | `source-name_date_topic-name.pdf` |
| Number and topic | `0001_topic-name.pdf` |
| Topic, source and date | `topic-name_source-name_date.pdf` (new projects start here) |
| Event and year, plus a number | `Event-Name_1998_1.jpg`: the file takes the name of its event folder and the next number, counted on the disk (a folder with 13 photos gives 14). Outside an event folder, Topic, source and date names the file |
| Custom | Click the parts in order (Topic, Source, Date, Original) and pick `_` or `-` between them. The extension is added on its own |
| Style | `topic-name` (lowercase) or `Topic-Name` (Title-Case), per project. Accents are dropped (`Dia`) unless Keep accents is on (`Día`) |
| Keep original names | Files are classified and moved, but never renamed |

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
| Protected names | `index.html`, `README*`, `.gitignore`, `package.json`, `favicon.ico`, `robots.txt`, `sitemap.xml`, config files and lock files are never renamed, in any mode |
| Secrets | `.env`, `*.pem`, `*.key`, `id_rsa*`, `credentials*`, `*.p12`, `*.pfx`, `*.keychain` are never read and never sent to the AI. They are cataloged by name only, in Manual Review with the note "Possible secret, not read" |
| Rename from the chat | Uses the same cleaning rules, only after you click Confirm |

## API endpoints

The backend runs on `http://127.0.0.1:5050`. Routes that need login ask for the session token in the header `Authorization: Bearer <token>`. Without it, the answer is `401 unauthorized`. The routes for documents, dashboard, and the AI provider work on the active project.

| Method | Path | Login | What it does |
|---|---|---|---|
| GET | `/auth/status` | No | Says whether any account exists, and the language of the last account that logged in |
| POST | `/auth/register` | No | Creates an account and logs in. A taken username gives `409 username_taken` |
| POST | `/auth/login` | No | Logs in. After 5 wrong passwords in a row for one account, that account waits 30 seconds |
| POST | `/auth/logout` | Yes | Ends the session |
| POST | `/auth/password` | Yes | Changes the password. The session stays open |
| GET | `/documents` | Yes | Lists and searches the documents, with optional filters |
| GET | `/documents/export` | Yes | Exports the worksheet as a CSV file |
| GET | `/documents/<id>` | Yes | Gets one document |
| PATCH | `/documents/<id>` | Yes | Edits the source, date, summary, media type, or status |
| POST | `/documents/<id>/rename` | Yes | Renames one file, only after the user confirms in the chat |
| POST | `/documents/<id>/move` | Yes | Moves one file to another folder of the project's tree, given as a path like `Research/Photos/Events`. With `create_folder`, every missing level is created first |
| POST | `/documents/<id>/open` | Yes | Opens the file with its default app |
| POST | `/documents/<id>/reveal` | Yes | Shows the file in Finder, selected |
| POST | `/documents/<id>/preview` | Yes | Opens a Quick Look preview of the file |
| GET | `/dashboard/stats` | Yes | Gives the numbers for the dashboard |
| GET | `/settings` | Yes | Gives the active project's settings and the language |
| PUT | `/settings` | Yes | Saves the project name, the naming template, the folder tree (new folders only; folders with documents stay), and the language |
| POST | `/settings/sheet/suggest` | Yes | Asks the AI to write the project sheet from a sample of a folder (the active project's, or `folder`). Saves nothing |
| PUT | `/settings/ai-provider` | Yes | Saves the provider, model, and API key of one role: `text` (default), `fallback`, or `media` (Gemini only) |
| DELETE | `/settings/ai-provider/<role>` | Yes | Takes the fallback or media provider away. The key stays in the Keychain |
| POST | `/settings/ai-provider/test` | Yes | Tests the connection to the AI provider, through the server URL if one is sent |
| GET | `/projects` | Yes | Lists the projects and says which one is active |
| GET | `/scan` | Yes | How far the reading of the project folder is: status, files done and total, the current file |
| POST | `/scan/start`, `/scan/pause`, `/scan/resume` | Yes | Reads the active project's folder in place, holds it, or lets it go on |
| POST | `/projects` with `catalog_only` | Yes | Creates a Catalog only project: no folders are created, names are kept, Move and Rename answer `409 catalog_only` |
| POST | `/projects` | Yes | Creates a project with its folder tree, or opens a folder that already has a catalog |
| POST | `/projects/folders/suggest` | Yes | Asks Ollama Cloud for a folder tree from the project description. With `industry`, the request lists the folders that field usually has. Saves nothing |
| POST | `/projects/folders/inspect` | Yes | Says whether a folder looks like a website or a linked project (index.html, package.json, .git, .prproj, .indd...). Saves nothing |
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
| `backend/config/` | The accounts, each account's project list, and the app settings |
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
