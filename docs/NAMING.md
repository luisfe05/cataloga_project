# File naming in Cataloga

Choose the method in Settings, File Names, per project. Files already in the catalog keep their names until you approve a new one in To Approve or confirm one in Ask Cataloga.

## Methods

| Method | Example |
|---|---|
| Date and topic | `2026-07-15_harbor-race.pdf` |
| Source, date and topic | `harbor-gazette_2026-07-15_harbor-race.pdf` |
| Number and topic | `0001_harbor-race.pdf` |
| Topic, source and date | `harbor-race_harbor-gazette_2026-07-15.pdf` (new projects start here) |
| Event and year, plus a number | `Harbor-Swim_1998_14.jpg`: the file takes the name of its event folder and the next number, counted on the disk (a folder with 13 photos gives 14). Outside an event folder, Topic, source and date names the file |
| Custom | Click the parts in order (Topic, Source, Date, Original) and pick `_` or `-` between them. The extension is added on its own |
| Keep original names | Files are classified and moved, but never renamed |

| Option | What it does |
|---|---|
| Style | `harbor-race` (lowercase) or `Harbor-Race` (Title-Case), per project |
| Accents | Always dropped from new names (`Dia`, not `Día`), so the names work on every computer |
| Dates stamped on photos | Month first (`11 13 '97`) or day first (`13 11 97`), for the dates printed by a camera |

## Rules

| Rule | What happens |
|---|---|
| Topic | The AI gives a short topic in the same request as the source and date |
| No date | The name has no date part; the catalog shows the date empty |
| No source | That part is left out |
| No topic | The original file name is used |
| Photos | Named with the project's method from what the photo shows |
| Audio and video | With a Gemini key in Settings, the first two minutes are listened to or watched and the name comes from that. Without one, from the title in their tags |
| Files with nothing to read | Their date and a number, for example `2026-07-15_0001.jpg`. If only the disk date is known, `undated_0001.jpg` |
| Name already taken | The new file gets `_2`, `_3`, and so on; the first one keeps its name |
| Versions | A version mark in the original name (`v01`, `draft-3`) stays at the end of the new name |
| Already well named | A file in its right folder whose name already follows the project's method gets no new name |
| Long paths | The topic, then the source, are shortened a word at a time so the full path stays under 240 characters. If it still cannot fit, the file stays put, in Manual Review |
| Protected names | `index.html`, `README*`, `.gitignore`, `package.json`, `favicon.ico`, `robots.txt`, `sitemap.xml`, config files, and lock files are never renamed, in any mode |
| Secrets | `.env`, `*.pem`, `*.key`, `id_rsa*`, `credentials*`, `*.p12`, `*.pfx`, `*.keychain` are never read, never sent to the AI, and never renamed. They are cataloged by name only, in Manual Review with the note "Possible secret, not read" |
| Folder names | Folders keep spaces, capitals, and accents, but never use `/ \ : * ? " < >`, the vertical bar, or Windows reserved names like `CON`. Folders already created are never renamed |
| Rename from the chat | Uses the same cleaning rules, only after you click Confirm |
