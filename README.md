# Cataloga

Cataloga is a desktop app that uses AI to classify and catalog research material. It sorts each file into a media-type folder, gives it a readable filename, writes a short summary of its content, and logs everything in a searchable worksheet.

This is a Holberton School Portfolio Project.

## Tech stack

| Layer | Technology |
|---|---|
| Desktop window | pywebview |
| Frontend | HTML, CSS, JavaScript |
| Backend | Flask (REST API on localhost) |
| Database | SQLite |
| AI providers | Ollama Cloud (default), Gemini, Groq, Claude, xAI, OpenAI |
| API key storage | OS keyring |
| Packaging | PyInstaller |
| Tests | pytest |
| Interface languages | English (default) and Spanish (Latin America), chosen in Settings |

## Projects

Cataloga can hold several research projects. Each one has its own folder and its own catalog, saved inside that folder in `.cataloga/catalog.db`. Choose the project from the dropdown at the top of the Catalog screen, or pick "New project" there.

| Item | Where it is saved |
|---|---|
| A project's catalog, name, file names method, and AI provider | `<project folder>/.cataloga/catalog.db` |
| The list of projects, the active project, and the language | `projects.json` in the app's data folder |
| API keys | OS keyring, shared by every project |

To take a project out of the list, open Settings and click Remove project. This only changes the list. The project folder, its files, and its `.cataloga` catalog are never deleted. To add the project back, choose New project and pick the same folder: Cataloga opens its catalog with all its data.

The first time this version opens, the catalog of an older version becomes the first project. Nothing is lost, and the old database file is left as a backup.

## AI providers and API keys

Every new project starts with Ollama Cloud and the `gemma4:31b` model. To use another provider or model, open Settings and then Advanced settings.

| Item | How it works |
|---|---|
| Where keys are saved | The OS keyring (the macOS Keychain), under the service name `cataloga`, one key per provider |
| Adding a key | Type it in Advanced settings and click Save. Cataloga tests the connection first and only saves a key that works |
| Keys on screen | Never shown. Settings only says which providers have a key |
| No key yet | Settings opens Advanced settings and asks for one |

### Ollama key for development

When running from the code (not the packaged app), Cataloga looks for the Ollama Cloud key in this order:

| Order | Where |
|---|---|
| 1 | The OS keyring, like every other provider |
| 2 | The `OLLAMA_API_KEY` environment variable |
| 3 | A line `OLLAMA_API_KEY=...` in a `.env` file in the `cataloga` folder |

The `.env` file is ignored by git and is not included in the packaged app. The packaged app only reads the keyring.

To save a key in the keyring once, run this from the `cataloga` folder with the virtual environment active. It asks for the key without showing it or saving it in the Terminal history:

```
python -m keyring set cataloga ollama
```

## How files are added

| Step | What happens |
|---|---|
| 1 | Create a project with a name and a folder. Cataloga creates a Drop Zone folder and the five media-type folders inside it. |
| 2 | Drop new files into Drop Zone. Files that were already in the project folder are never moved. |
| 3 | Every few seconds, Cataloga classifies each file in the active project's Drop Zone, moves it to its media-type folder, and adds it to that project's catalog. |

Projects made with an older version have an Inbox folder instead. Cataloga renames it to Drop Zone the first time it checks the project folder. If both folders exist and Inbox still has files, the Catalog screen shows a warning. Cataloga does not move those files.

## File names

In Settings, choose how Cataloga names new files. Files already in the catalog keep their names.

| Method | Example |
|---|---|
| Date and topic (default) | `2026-07-15_oceanman-malta.pdf` |
| Source, date and topic | `el-nuevo-dia_2026-07-15_oceanman-malta.pdf` |
| Number and topic | `0001_oceanman-malta.pdf` |
| Custom | A template with `{date}`, `{source}`, `{topic}`, `{number}` and `{original}` |

| Rule | What happens |
|---|---|
| Topic | The AI gives a short topic in the same request as the source and date |
| No date | `undated` is used |
| No source | That part is left out |
| No topic | The original file name is used |
| Photos, audio, video, and files without text | File date and number, for example `2026-07-15_0001.jpg` |
| Name already taken | `-2`, `-3` and so on are added |

## Project structure

| Folder / File | Description |
|---|---|
| main.py | Starts the Flask server and opens the desktop window |
| backend/models/ | Document class, one worksheet row |
| backend/db/ | Database schema and CatalogRepository (all database reads and writes) |
| backend/pipeline/ | ClassificationPipeline, FileOrganizer, and the AI provider clients |
| backend/config/ | AppConfig (a project's settings) and the project list |
| backend/routes/ | API endpoints for documents, dashboard, settings, and projects |
| frontend/ | HTML, CSS, and JavaScript for the app screens |
| tests/ | pytest test suite |
| database/ | When running from the code: projects.json and the old single database (not tracked by git) |

## Status

MVP in development.

## Author

Luis Felipe Gonzalez Lopez, [github.com/luisfe05](https://github.com/luisfe05)
