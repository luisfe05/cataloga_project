# Cataloga

Cataloga is a desktop app that uses AI to classify and catalog research material. It sorts each file into a media-type folder, gives it a serial filename, writes a short summary of its content, and logs everything in a searchable worksheet.

This is a Holberton School Portfolio Project.

## Tech stack

| Layer | Technology |
|---|---|
| Desktop window | pywebview |
| Frontend | HTML, CSS, JavaScript |
| Backend | Flask (REST API on localhost) |
| Database | SQLite |
| AI providers | Gemini, Groq, Claude, xAI, OpenAI |
| API key storage | OS keyring |
| Packaging | PyInstaller |
| Tests | pytest |
| Interface languages | English (default) and Spanish (Latin America), chosen in Settings |

## How files are added

| Step | What happens |
|---|---|
| 1 | In Settings, choose a project folder. Cataloga creates a Drop Zone folder and the five media-type folders inside it. |
| 2 | Drop new files into Drop Zone. Files that were already in the project folder are never moved. |
| 3 | Every few seconds, Cataloga classifies each file in Drop Zone, moves it to its media-type folder, and adds it to the catalog. |

Projects made with an older version have an Inbox folder instead. Cataloga renames it to Drop Zone the first time it checks the project folder. If both folders exist and Inbox still has files, the Catalog screen shows a warning. Cataloga does not move those files.

## Project structure

| Folder / File | Description |
|---|---|
| main.py | Starts the Flask server and opens the desktop window |
| backend/models/ | Document class, one worksheet row |
| backend/db/ | Database schema and CatalogRepository (all database reads and writes) |
| backend/pipeline/ | ClassificationPipeline, FileOrganizer, and the AI provider clients |
| backend/config/ | AppConfig, the app settings |
| backend/routes/ | API endpoints for documents, dashboard, and settings |
| frontend/ | HTML, CSS, and JavaScript for the app screens |
| tests/ | pytest test suite |
| database/ | Local SQLite database (not tracked by git) |

## Status

MVP in development.

## Author

Luis Felipe Gonzalez Lopez, [github.com/luisfe05](https://github.com/luisfe05)
