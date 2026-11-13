# Cataloga features

Every feature of the app, in detail. The short version is in the [README](../README.md).

## Ask Cataloga

| Feature | What it does |
|---|---|
| Find and filter | Finds documents ("Find press clippings"), shows them in the chat, or filters the Catalog List for you |
| Summarize the project | Writes a short summary of the whole project from the stored summaries |
| Rename and move | Proposes a new name, or a move to another folder of the project. A file is only renamed or moved after you click Confirm. Move is not offered in Catalog only projects |
| Limits | Ask Cataloga only answers about the files in this project. Its answer is always one action from a fixed list (answer, show documents, filter the catalog, summarize the project, propose a rename, propose a move), checked by the app before it is shown |
| Guardrails | Text inside a file is treated as data, never as instructions. Paths that leave the project, like `../`, are refused |

## Reading files

| Feature | What it does |
|---|---|
| Read the folder in place | New projects start without a Drop Zone: Cataloga reads every file where it is, subfolders included, without moving or renaming it. The banner shows how far the reading is, with Pause and Resume. A file that did not change is never read twice |
| Now or Later | When you create a project, choose Now to read the folder at once, or Later to only list it and start from the banner in Home |
| Skipped files | Hidden files, `.git`, `node_modules`, `.cataloga`, and links are never read |
| Every format | Text and code of any kind are read by their bytes, not by a list of extensions, and big ones only at the start. Design files show their picture (Photoshop, Illustrator, Sketch, InDesign) or their title and author. Zips are cataloged from the list of what they hold, never unpacked. An unknown format is cataloged from its name, its folder, and the files next to it |
| Scanned PDFs | The first three pages are read as pictures |
| Scanned photos | A photo goes to the AI at 1,600 px with its four corners enlarged, so a date stamped by the camera (`11 13 '97`) or written by hand can be read. A scan lying on its side is turned before it is read; the original file is never changed. TIFF scans of any size are read |
| Photo dates | The date of a photo comes from the stamp, then from a camera's EXIF (a scanner's EXIF is the day of the scan and never counts), then from a year in the file name or its folders. Settings says whether stamps read month first or day first |
| Audio and video | With a Gemini key in Settings, the first two minutes are listened to or watched, and the summary and name come from that. Without one, from the title in their tags and their length |
| Time limits | Each file has a time limit. A file that takes too long goes to Manual Review as "Timed out while reading", and the reading goes on. Retry timed-out files reads only those files again |
| iCloud files | A file that is only in iCloud is cataloged by its name and never downloaded |
| Watches the folder | After the first reading, new and changed files are read every 10 seconds, where they are, with a proposed folder and name that wait in To Approve |

## The card of each file

| Feature | What it does |
|---|---|
| One request per file | One AI request fills the whole card: media type, summary, source, date, topic, keywords, the folder that fits its content, one line on why (Why this folder), and how sure the AI was |
| What the AI sees | The file name, its folder, the other files next to it, the file's own metadata, and an extract of the content. Camera and scanner names are ignored. When name and content disagree, the content wins |
| 100-character summary | A summary of up to 100 characters for every readable file |
| Summaries in your language | Summary, topic, keywords, and the folder reason are written in the language of the app (English or Spanish), whatever the file's language. A summary in another language is asked once more, and if it fails again it is not saved |
| Project sheet | A short text of what the work is (Settings, About This Project). Write it, or click Write it for me: the AI reads a sample of the folder and writes it. Cataloga reads it before every file |
| Industry conventions | A built-in list of how each field organizes its archive (documentary and research, legal, construction, web and code, film and video, photo archive, library, general): typical folders, a naming pattern, and rules. When a new project's folder looks like a website or a linked edit, the New project form says so |
| Learns from your moves | Every time you move a file to another folder, Cataloga remembers it. The AI reads the latest ten moves of the project before it files a new document |
| Duplicates | Every new file is hashed. A file that is already in the catalog gets no AI call and goes to Manual Review as "Duplicate of" the first one |
| Manual Review | Only these send a file to Manual Review: it could not be read, the AI had low confidence, no folder fits, it is a duplicate, it timed out, or its path would be too long. Every file there has a note that says why. A missing source or date never sends a file there |

## To Approve

| Feature | What it does |
|---|---|
| The plan | Cataloga proposes a folder and a name for each file, with the reason. Each row can be edited, approved, or skipped. Approve all leaves out Manual Review and low-confidence rows |
| Apply | Apply changes moves and renames the approved files as one batch. Nothing moves before that |
| Undo | Undo this batch puts every file back where it was, with its old name, and removes only the empty folders the batch made |
| Batches | Every batch is listed: the plan, files filed without asking, moves made by hand, and changes confirmed in Ask Cataloga. Each one can be undone |
| Safe moves | A file is never replaced (a repeated name gets `_2`, `_3`), it must be where and as it was before it moves, and a batch that stops halfway (a drive that leaves, the app that closes) is settled at the next start |
| Leave as is | Files in a folder marked Leave as is are cataloged, but never get a new folder or name |
| No asking | New files in a folder marked No asking are filed on their own, as their own batch, which can be undone |

## Home and Catalog List

| Feature | What it does |
|---|---|
| Home | Browse the project like Finder, in Icons or Columns, with thumbnails and a panel with each file's date, source, summary, and why it belongs in its folder |
| Preview | Double-click a file in Home, or press the space bar in the Catalog List, to see it in an overlay: photos, PDFs, text, audio, and video |
| Open and Show in Finder | Open a file with its default app, or show it in Finder, selected |
| Catalog List | Search and filter every file, with the Manual Review tab |
| Edit Mode | Fix the source, date, summary, keywords, and status, and the extra fields under More columns. A new summary is written when you change the source or the date |
| Download the worksheet | The catalog downloads as a CSV file |
| Dashboard | Counts of classified files and files that need review, a breakdown by media type, and the latest activity |

## Folder Names

| Feature | What it does |
|---|---|
| Suggest folders | The AI proposes a tree of folders (two levels) from About This Project, with the usual folders of the project's field. You edit it before anything is made |
| Start from file types | Starts the tree from five folders: Press, Documents, Photos, Audio, and Video |
| Learn from my folder | For a folder you already organized: reads its tree as it is (up to six levels), finds the folders that hold events and the catch-all folder, and how the files are named. Nothing on the disk changes |
| Change the folders | Add, rename, or remove folders whenever you want. When files are already read, the new moves wait in To Approve |
| Folder trees | Folders can go six levels deep. A folder marked Catch-all receives what fits nowhere else |
| Event folders | A folder marked Events holds one folder per event, named Event_Year. The AI files each photo in its event, and proposes a new event folder there (and only there) |

## Project modes

| Mode | What it does |
|---|---|
| Read in place | The default. Cataloga reads every file where it is, and every move or rename waits in To Approve |
| Use a Drop Zone | Cataloga creates the folders now, and files what you drop into the Drop Zone folder. Older projects keep this mode |
| Catalog only | For websites, code, and edits that link their files by path (InDesign, Premiere, After Effects, Final Cut). Cataloga reads and catalogs each file where it is. Nothing is moved or renamed. It can be turned off in Folder Names |

## Accounts and settings

| Feature | What it does |
|---|---|
| Accounts | Several accounts on one Mac. Each account has its own projects, settings, AI provider, and API keys. Passwords are saved only as bcrypt hashes. After 5 wrong passwords in a row, that username waits 30 seconds |
| Recovery key | Shown when you create the account. With it you can set a new password if you forget yours. Settings, Account shows it again (with the password) or makes a new one |
| Terms and Privacy | Accepted when you create the account, and again when they change |
| Delete account | Settings, Account. Deletes the account, its recovery key, and its API keys. Project folders and their catalogs stay |
| Several projects | Each project has its own folder and its own catalog. Switch between them in Projects. Remove project takes it out of the list and never deletes its folder or files |
| AI Provider | Ollama Cloud (`gemma4:31b`) by default. Gemini, Groq, Claude, xAI, and OpenAI in Advanced settings. A fallback provider answers when the main one fails or cannot read pictures. Gemini reads audio and video. An optional server URL sends every request through a server that keeps the keys |
| Secrets | Files like `.env`, `*.pem`, `*.key`, `id_rsa*`, and `credentials*` are cataloged by name only, never read or sent to the AI. Keys and passwords inside other files are replaced with `[REDACTED]` before anything is sent, and the Catalog says how many were hidden. A password written in free text with no label is not recognized |
| English and Spanish | The app is in English by default. Spanish (Latin America) can be chosen in Settings, General |
| File Names | Seven ways to name files, set per project. See [NAMING.md](NAMING.md) |
