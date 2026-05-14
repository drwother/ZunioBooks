# MP3 Merger — User Guide and Operating Instructions

## Purpose

MP3 Merger is a simple Windows desktop app for combining multiple `.mp3` files into one or more larger `.mp3` files.

Typical use case:

- You download an audiobook as 100 separate MP3 files.
- You want to import it to a Zune or another older player as 3 larger files.
- The app lets you sort the files, manually reorder them, then merge selected files, all files, or automatically split the list into 3 output files.

---

## Key Features

- Add MP3 files from a folder.
- Drag-and-drop MP3 files into the app.
- Drag-and-drop a folder into the app to import all `.mp3` files in that folder.
- Default sort: filename ascending.
- Manual sort: drag rows inside the list.
- Optional columns:
  - Filename
  - Folder
  - Full Path
  - Size MB
  - Modified Date
- Merge selected files.
- Merge all files.
- Remove selected files.
- Clear all files.
- Easy Button:
  - Splits the current file list into 3 groups by file count.
  - Uses the current sort/manual order.
  - Creates output files using suffixes `_01`, `_02`, `_03`.
  - Any extra 1 or 2 files go into output file `_03`.
- Fast default merge using ffmpeg stream copy.
- Optional re-encode mode for problem files.
- No installer required once built; run the `.exe`.

---

## Important Requirement: ffmpeg Must Be Installed

This app assumes `ffmpeg` is already installed and available in the Windows PATH.

Before using the app, open Command Prompt and run:

```bat
ffmpeg -version
```

If you see ffmpeg version information, you are good.

If Windows says `ffmpeg is not recognized`, install ffmpeg and add it to PATH.

Recommended Windows installation method:

```bat
winget install Gyan.FFmpeg
```

Then close and reopen Command Prompt and test again:

```bat
ffmpeg -version
```

---

## How to Use the App

### 1. Open the App

Run:

```text
MP3Merger.exe
```

If running from source during development:

```bat
run_dev.bat
```

---

### 2. Add MP3 Files

Use any of these methods:

- Click **Add Folder**
- Click **Add Files**
- Drag MP3 files into the list
- Drag a folder into the list

The app imports only `.mp3` files.

Duplicate file paths are ignored.

---

### 3. Sort or Reorder Files

Default import order is:

```text
filename ascending
```

To restore filename sort:

```text
Edit > Sort by Filename Asc
```

To manually reorder:

```text
Select one or more rows and drag them to a new position.
```

The merge operation uses the exact order currently shown in the list.

---

### 4. Choose Output Folder and Filename

At the top of the app:

- Use **Browse Output Folder**
- Enter an output filename in the textbox

You can type:

```text
My Audiobook
```

The app will automatically add `.mp3`.

You can also type:

```text
My Audiobook.mp3
```

---

## Merge Options

### Merge Selected

1. Select one or more rows.
2. Click **Merge Selected**.

Output example:

```text
My Audiobook.mp3
```

---

### Merge All

1. Add files to the list.
2. Confirm the order.
3. Click **Merge All**.

Output example:

```text
My Audiobook.mp3
```

---

### Easy Button: Split into 3

1. Add all audiobook files.
2. Confirm the order.
3. Enter an output folder.
4. Enter a base filename, for example:

```text
My Audiobook
```

5. Click:

```text
Easy Button: Split into 3
```

If there are 60 files:

```text
Files 01–20 -> My Audiobook_01.mp3
Files 21–40 -> My Audiobook_02.mp3
Files 41–60 -> My Audiobook_03.mp3
```

If there are 62 files:

```text
Files 01–20 -> My Audiobook_01.mp3
Files 21–40 -> My Audiobook_02.mp3
Files 41–62 -> My Audiobook_03.mp3
```

Extra files always go into the third output file.

---

## Fast Merge vs Re-Encode

### Default: Fast Merge

By default, the app uses ffmpeg with stream copy:

```bat
-c copy
```

This is:

- very fast
- no quality loss
- ideal for most audiobook MP3 sets

### If Fast Merge Fails

Some MP3 collections have mismatched stream parameters, corrupt headers, or odd metadata.

If fast merge fails, the app shows a friendly error and recommends:

```text
Check "Re-encode instead of fast copy" and try again.
```

### Re-Encode Mode

Re-encode mode uses:

```bat
-c:a libmp3lame -q:a 2
```

This is slower, but more tolerant.

---

## Menus and Right-Click Options

Most actions are available in three places:

- Buttons at the top
- Menu bar
- Right-click menu on the file list

Available actions:

- Merge Selected
- Merge All
- Easy Button: Split into 3
- Remove Selected
- Clear All
- Sort by Filename Asc
- Choose Columns

---

## Build Instructions for Developer

### Development Requirements

Install these free tools:

1. Python 3.11 or newer  
   Download from Python.org or Microsoft Store.

2. ffmpeg  
   Must be available in PATH.

3. No paid IDE required. Recommended editor:
   - Visual Studio Code
   - Notepad++
   - or any text editor

---

### Project Files

```text
MP3Merger_Windows_Portable/
  app.py
  requirements.txt
  build.bat
  run_dev.bat
  USER_GUIDE.md
```

---

### Run from Source

Double-click:

```text
run_dev.bat
```

This will:

1. Create a local `.venv`
2. Install dependencies
3. Start the app

---

### Build the Portable EXE

Double-click:

```text
build.bat
```

This creates:

```text
dist\MP3Merger.exe
```

You can copy that `.exe` anywhere on the same computer.

The app itself does not need installation.

`ffmpeg` still must be installed in PATH on the computer running the app.

---

## Notes and Limitations

- The app only imports `.mp3` files.
- It does not scan subfolders recursively.
- It does not edit MP3 tags.
- It does not normalize volume.
- It does not split by duration.
- It does not automatically fall back to re-encode; it recommends re-encode after a fast merge failure so the user stays in control.
- For best results, ensure filenames sort naturally before merging, for example:

```text
Chapter 001.mp3
Chapter 002.mp3
Chapter 003.mp3
```

Avoid:

```text
Chapter 1.mp3
Chapter 10.mp3
Chapter 2.mp3
```

unless you manually reorder them.
