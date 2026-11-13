# Cataloga

An AI organizer for your personal drive.

Cataloga reads every file in a folder, proposes clear names and folders that you approve, and answers questions about your files.

Landing page, with the demo video: https://luisfe05.github.io/cataloga-landing/

A Holberton School Portfolio Project. Mac only, for now.

## The problem

A portable drive fills up fast. Files land outside their folders, and most of them have names like `scan_123.pdf` or `IMG_456.jpg`, which say nothing about what is inside. Storage keeps the files safe, but it does not put them in order, so finding one file weeks later means opening them one by one.

Cataloga is for researchers, photographers, journalists, and anyone with a drive they never manage to organize.

## What it does

| Feature | What it does |
|---|---|
| Ask Cataloga | A chat that finds documents, filters the catalog, summarizes the project, and proposes to rename or move a file. It only answers about the files in the project, and nothing changes until you click Confirm |
| Reads every file | Documents, scanned PDFs, photos and their metadata, and code. Audio and video are read with Gemini. Each file gets a summary of up to 100 characters |
| Clear names and folders | Proposes a readable name and a folder for each file, based on its content and the kind of project |
| To Approve | Nothing moves until you approve it. You can edit or skip any change, and Undo puts every file back with its old name |
| Home, Preview, and Show in Finder | Browse the project like Finder, in icons or columns, preview photos, PDFs, audio, and video, and jump to any file in Finder |
| Folder Names | Suggest folders with AI, Learn from my folder to copy a tree you already organized, and change the folders whenever you want |
| Projects and accounts | Several projects and several accounts on one Mac, in English or Spanish |

The full list of features is in [docs/FEATURES.md](docs/FEATURES.md).

## How it works

| Step | What happens |
|---|---|
| 1. Create an account | Choose a username and a password. Cataloga gives you a recovery key: save it, it is the way back in if you forget your password |
| 2. Choose a folder | Click New project and pick a folder: a drive, or any folder on your Mac |
| 3. Cataloga reads each file | Every file stays where it is while Cataloga reads it and writes its card: summary, source, date, topic, and the folder it fits |
| 4. Review and approve | Open To Approve, check the proposed names and folders, approve them, and click Apply changes. Undo this batch puts them back |
| 5. Ask Cataloga | Click the round button at the bottom right and ask, for example, "Find press clippings" or "Summarize this project" |

## Tech stack

| Part | Technology | Why |
|---|---|---|
| Desktop app | pywebview, with HTML, CSS, and plain JavaScript | It uses the web engine the Mac already has, so the app stays light |
| App engine | Python and Flask | Python has libraries to read PDFs, photos, and their metadata. Flask is a local API that only runs on your computer (`127.0.0.1:5050`) |
| Database | SQLite | No server to install. Each project keeps its catalog inside its own folder, so the catalog travels with the drive |
| AI | Ollama Cloud (`gemma4:31b`) by default | Low cost. Gemini is added only for audio and video. Other providers (Gemini, Groq, Claude, xAI, and OpenAI) can be chosen in Settings |
| Security | bcrypt and the macOS Keychain (keyring) | Passwords are saved only as hashes, and API keys stay in the Keychain |
| Packaging and tests | PyInstaller and pytest | One command builds the Mac app, and the tests run without internet |

## Privacy and security

| Rule | How |
|---|---|
| Runs on your Mac | The app, the catalog, and the accounts stay on your computer. Only what is read from each file (text, pictures, or a short audio or video clip) goes to the AI provider you choose |
| Passwords | Saved only as bcrypt hashes |
| API keys | Saved in the macOS Keychain, per account, never in the database |
| Secrets | Files like `.env` or `*.pem` are never read or sent to the AI. Keys and passwords found inside other files are replaced with `[REDACTED]` before anything is sent |
| Ask Cataloga | Only answers about the files of the project |
| Your approval | Your files move only when you apply a batch in To Approve, click Confirm in the chat, or mark a folder No asking. In a project with a Drop Zone, the files you drop there are filed for you |
| Your files | Removing a project or deleting an account never deletes its folder or its files |

## Run it from source

Run these commands in Terminal.

| Step | Command |
|---|---|
| 1. Get the code | `git clone https://github.com/luisfe05/cataloga_project.git` and `cd cataloga_project` |
| 2. Create a virtual environment | `python3 -m venv venv` |
| 3. Turn it on | `source venv/bin/activate` |
| 4. Install the packages | `pip install -r requirements.txt` |
| 5. Start the app | `python main.py` |

The app opens in its own window. From source, it keeps its data (the accounts and each account's project list) in the `database/` folder.

Cataloga needs an Ollama Cloud API key. Type it in Settings, AI Provider, or save it once in the Keychain with the command below. It asks for the key without showing it, and the key moves to your account the next time you log in.

```
python -m keyring set cataloga ollama
```

To build the Mac app, run `./build.sh` with the virtual environment on. The app is saved in `dist/Cataloga.app`, and it keeps its data in `~/Library/Application Support/Cataloga/`.

## Tests

Run these in the `cataloga` folder with the virtual environment on. The AI calls are replaced with fakes, so the tests need no API key and no internet.

| Check | Command | Result |
|---|---|---|
| Tests | `python -m pytest` | 1,238 tests in 63 test files |
| Code style | `pycodestyle --exclude=venv,build,dist .` | No errors |

`pycodestyle` is not in `requirements.txt`. Install it with `pip install pycodestyle`.

## Project structure

| Folder or file | What it holds |
|---|---|
| `main.py` | Starts the Flask server, the folder watcher, and the desktop window |
| `build.sh` | Builds `Cataloga.app` with PyInstaller |
| `assets/` | The app icon |
| `backend/app.py` | Creates the Flask app and registers the routes |
| `backend/config/` | Accounts, recovery keys, API keys, and the app settings |
| `backend/db/` | The database schema and CatalogRepository, which does every database read and write |
| `backend/models/` | The Document class, one row of the catalog |
| `backend/pipeline/` | ClassificationPipeline, FileOrganizer, file naming, the plan, Ask Cataloga, and the AI provider clients |
| `backend/routes/` | The API endpoints |
| `frontend/` | The app screens: `index.html`, `css/`, `js/` (with `js/lang/` for English and Spanish), `legal/`, fonts, and icons |
| `tests/` | The pytest tests |
| `database/` | Data when running from source (not tracked by git) |

## Documentation

| Document | What it has |
|---|---|
| [docs/FEATURES.md](docs/FEATURES.md) | Every feature of the app, in detail |
| [docs/API.md](docs/API.md) | The 63 API endpoints |
| [docs/NAMING.md](docs/NAMING.md) | The file naming methods and rules |

## Author

Luis Felipe González López, Holberton School Puerto Rico.

| Link | Where |
|---|---|
| GitHub | https://github.com/luisfe05 |
| LinkedIn | https://www.linkedin.com/in/luisgonz |
| Landing page | https://luisfe05.github.io/cataloga-landing/ |

## License

MIT License. See [LICENSE](LICENSE).
