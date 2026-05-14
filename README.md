# ZunioBooks

ZunioBooks is a lightweight Windows utility for building audiobook files specifically optimized for the Zune podcast app.

The tool can:

* Merge MP3 audiobook chapters
* Convert MB4 to MP3
* Generate Zune-compatible files so your Audiobooks show up in the Podcasts app
* Re-encode audio when needed (Zune is picky about which mp3 files it will recognize). 


## Why?

Zune doesn't have a native Audiobook feature - but the Podcast app works great for Audiobooks.

ZunioBooks was built to simplify that workflow.
Get your Audiobooks from wherever you get them - often you end up with dozen or over a hundred mp3 files that are impossible to sort properly on your Zune.
Zunio Books will merge the multiple MP3 files together, tag them as a "Podcast", add the filenames and Album property (title of the book). 
All you have to do is set the Outupt folder to the local folder that your Zune monitors for podcasts and there you go - your audio books are in your list of Podcasts. 

OR - sometimes your book comes as an MB4 - ZunioBooks can convert that to a single .mp3 file and set the same properties - so your Zune software will pick it up. 
## Features

* Drag-and-drop mp3 files or open a whole folder.
* Sortable chapter/file list
* MP3 merge support
*   Merge all files into a single output
*   Merge only the files you select - you can break your book up into as many files as you want
*   OR use the magic "3 files" button that will separate your list of mp3s into 3 output files - Book01 Book02 and Book03. For a 12 hour book you end up with 3 ~4 hours mp3 files... all set to go in your Podcasts app. 
* M4B conversion
* Optional re-encoding
* Zune compatibility mode (sometimes Zune won't "see" mp3 files - this checkbox makes sure the mp3 output is visible to your zune software. 
* Simple Windows UI

## Requirements

* Windows
* FFMPEG configured in your PATH


## Running From Source

Install dependencies:

```bash
pip install -r requirements.txt
```

Run:

```bash
python app.py
```

## Building EXE

```bash
build.bat
```

## Status

This is an enthusiast hobby project and is still evolving.

Bug reports, suggestions, and pull requests are welcome.

## Contributions

Please submit pull requests rather than direct commits.

## License

MIT License
