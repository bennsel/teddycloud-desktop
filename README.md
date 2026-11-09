# TeddyCloud Desktop

Deutsche Version: [README.de.md](README.de.md)

[![CI](https://github.com/bennsel/teddycloud-desktop/actions/workflows/ci.yml/badge.svg)](https://github.com/bennsel/teddycloud-desktop/actions/workflows/ci.yml)
[![License: GPL v3+](https://img.shields.io/badge/license-GPL--3.0--or--later-blue.svg)](LICENSE)

A cross-platform desktop application (Windows, macOS, Linux) built with PyQt6 for managing the Tonies and Tonieboxes of a [TeddyCloud](https://github.com/toniebox-reverse-engineering/teddycloud) server. The two overviews are modelled on the `/web/tonies` and `/web/tonieboxes` pages of the TeddyCloud web UI ([teddycloud_web](https://github.com/toniebox-reverse-engineering/teddycloud_web)).

> This is an unofficial community project and is not affiliated with tonies GmbH (see [Disclaimer](#disclaimer)).

<!-- ![TeddyCloud Desktop screenshot](docs/screenshot.png) -->

The user interface is in German. Menu and button labels are quoted in German below, with an English explanation in parentheses where helpful.

## Features

**[Tonie overview](#tonie-overview-tonies--tonies)**
- Tiles with picture, series, episode and UID for every Tonie, per Toniebox content directory (boxes sharing a directory are merged)
- Filter by text, series, episode, language, valid/content/live/cloud state and "last played on a Toniebox"
- Paging (24/48/96/all), natural sort order, marker for the Tonie last played on each box
- Play the content in the built-in player, including jumping to individual tracks
- Toggle cloud access and live mode, fetch missing content from the Tonie cloud
- Info dialog with track list, download as `.ogg`, hide Tonies
- Edit dialog: assign a source from the library (`.taf`/`.tap`) or a radio stream URL, change the model via catalog search
- Selection mode with bulk actions (cloud, live, hide) and export as CSV, JSON, full JSON, HTML or HTML with embedded images
- Copy as text to the clipboard

**[Audio Encoder](#audio-encoder-tonies--audio-encoder)**
- Encode up to 99 audio files (MP3, AAC/M4A, WAV, FLAC, OGG, Opus, AIFF, WMA, AC3, DTS, TAF, MP4) into one TAF, one chapter per file
- Drag & drop, chapter order by drag & drop or natural sorting
- Choose the target folder in the library, create new folders
- Local decoding with Qt's bundled FFmpeg, no extra installation; TeddyCloud does the Opus encoding
- Optionally create a custom Tonie in one go: series, episode and cover read from the audio tags, tracks from the file names, cover uploaded automatically

**[Custom models](#custom-models-tonies--custom-modelle)**
- Create, edit, duplicate, rename and delete your own models in `tonies.custom.json`
- Filter, sort by many fields, paging, browse with optional auto-save
- Pick pictures from `custom_img` (with upload and new folders) or from the official catalog
- Map audio ID and hash directly from a `.taf` in the library
- Validation as in the web UI (duplicate IDs, duplicate audio pairs, language codes)

**[TeddyAudio Playlists](#teddyaudio-playlists-tonies--teddyaudio-playlists)**
- Browse the library for `.tap` files, create, edit, rename, move, download and delete playlists
- Editor with multi-select from the library and chapter order
- Assign a playlist to a Tonie
- **Convert to TAF in the app** instead of relying on FFmpeg on the server

**[Toniebox overview](#toniebox-overview-tonieboxen--tonieboxen)**
- Tiles with name, color variant picture, hardware version, MAC address and online state
- Last played Tonie per box, one click opens it in the Tonie overview
- Rename a box and choose its model, re-enable API access
- Upload client certificates via drag & drop
- Box-specific settings with "override" per option and settings levels Basic/Detail/Expert
- Remove a box

**General**
- Runs on Windows, macOS and Linux; prebuilt binaries, no Python needed
- Optional HTTP Basic Auth for TeddyCloud behind a reverse proxy; the password is kept in the system keyring
- Keyboard shortcuts for all pages (Ctrl+T, Ctrl+E, Ctrl+P, Ctrl+M, Ctrl+B, F5 …)

## Download

- **Prebuilt binaries** for Windows, macOS and Linux are attached to the [GitHub Releases](https://github.com/bennsel/teddycloud-desktop/releases). Download, unpack, run – no Python installation required.
- **From source** with [uv](https://docs.astral.sh/uv/), see the next section.

## Running from source

Requirements: [uv](https://docs.astral.sh/uv/) and Python ≥ 3.11 (uv installs a suitable version on demand).

```bash
git clone https://github.com/bennsel/teddycloud-desktop.git
cd teddycloud-desktop
uv sync                                # install dependencies
uv run teddycloud-desktop              # start the app
uv run python -m teddycloud_desktop    # alternative
```

Audio playback uses Qt's FFmpeg backend, which ships with the PyQt6 package. Artist, album and cover art of audio files are read with [mutagen](https://mutagen.readthedocs.io/), installed by `uv sync`.

## Menus

| Menu | Entry | Shortcut | Function |
|------|-------|----------|----------|
| Datei (File) | Einstellungen … (Settings) | Ctrl+, | Set the TeddyCloud endpoint, request timeout and Basic Auth |
| Datei | Beenden (Quit) | Ctrl+Q | Close the application |
| **Tonies** | **Tonies** | Ctrl+T | Open and load the Tonie overview (tiles) |
| **Tonies** | **Audio Encoder** | Ctrl+E | Encode audio files into a TAF file in the TeddyCloud library |
| **Tonies** | **TeddyAudio Playlists** | Ctrl+P | Create and edit playlists (`.tap`) and assign them to Tonies |
| **Tonies** | **Custom-Modelle** (custom models) | Ctrl+M | Create, edit, duplicate and delete your own Tonie models in `tonies.custom.json` |
| **Tonieboxen** | **Tonieboxen** | Ctrl+B | Open and load the Toniebox overview |
| Bearbeiten (Edit) | Kopieren (Copy) | Ctrl+C | Copy the selected Tonies (or all filtered ones if none are selected) to the clipboard as tab-separated text (series, episode, model, UID) |
| Bearbeiten | Alles auswählen (Select all) | Ctrl+A | Enter selection mode and select all filtered Tonies |
| Ansicht (View) | Aktualisieren (Refresh) | F5 | Reload the current page (Tonies, Tonieboxes, or the folder tree in the Audio Encoder) |
| Ansicht | Filter anzeigen (Show filter) | Ctrl+F | Show/hide the filter bar |
| Hilfe (Help) | Über TeddyCloud Desktop / Über Qt (About) | – | About dialogs (version, project link, license, trademark note) |

On macOS, Qt moves Settings, Quit and About into the application menu as usual on the Mac.

## Settings

- **TeddyCloud endpoint**: base URL of the TeddyCloud, e.g. `http://teddycloud.local` or `http://192.168.1.10:8080`. `http://` is added if no scheme is given; trailing `/` are removed. If TeddyCloud runs behind a reverse proxy under a sub-path, include that path.
- **Request timeout**: 1–300 seconds (default 10). Does not apply to downloads (audio download, cloud download).
- **Basic Auth user / password** (optional): for TeddyCloud behind a reverse proxy with HTTP Basic Auth. When a user is set, every request to the TeddyCloud carries an `Authorization: Basic …` header. Credentials are never sent to other hosts (e.g. external picture URLs from the Tonie catalog). For audio playback the credentials go into the stream URL (`http://user:pass@host/…`) because the media player cannot set headers. A password without a user is rejected.

**Password storage:** the Basic Auth password is stored in the operating system's keyring via [keyring](https://pypi.org/project/keyring/) (Windows Credential Manager, macOS Keychain, Secret Service such as GNOME Keyring or KWallet on Linux), service `teddycloud-desktop`, account `basic-auth`. Only if no keyring is available is it stored in plain text in the settings (see locations below); the settings dialog then shows a hint. A plain-text password from an older version is migrated into the keyring automatically.

> **Security note:** Basic Auth only Base64-encodes the credentials, which is effectively unencrypted. Use an `https://` endpoint for access over the internet.

All other settings (including the last selected Toniebox) are stored with `QSettings` (organisation and application both `teddycloud-desktop`):

| System | Location |
|--------|----------|
| Linux | `~/.config/teddycloud-desktop/teddycloud-desktop.conf` |
| Windows | Registry: `HKEY_CURRENT_USER\Software\teddycloud-desktop\teddycloud-desktop` |
| macOS | `~/Library/Preferences/com.teddycloud-desktop.teddycloud-desktop.plist` |

If no endpoint is configured yet, "Tonies → Tonies" opens the settings dialog automatically.

## Tonie overview (Tonies → Tonies)

### Header

- **Toniebox**: selects the content directory ("overlay"). As in the web UI, Tonieboxes sharing the same content directory (`core.contentdir`) are merged into one entry, e.g. "Kinderzimmer, Wohnzimmer". If no box uses the default directory, "TeddyCloud Standard-Inhaltsverzeichnis" (default content directory) is added. The choice is remembered.
- **Aktualisieren** (Refresh): reloads Tonieboxes, Tonies and the last played Tonies.

### Toolbar

- **Filter**: shows the filter bar. All filters apply immediately:
  - search (series, episode, model, UID, RUID or source), series, episode, language
  - valid, has content, live, cloud blocked, cloud auth: each "egal" (any), "ja" (yes) or "nein" (no)
  - "only Tonies last played on a Toniebox"
  - reset filters
- **Auswählen** (Select): selection mode. Each tile gets a checkbox, plus:
  - select all filtered Tonies (across pages) and clear selection
  - **Aktionen** (actions) for the selection: disable/enable cloud, enable/disable live, hide tags (with confirmation), export as CSV, JSON, full JSON (raw data from `/api/getTagIndex`), HTML, and HTML with embedded images. File names start with a timestamp as in the web UI, e.g. `20261002_143000_selected_tonies.csv`.
  - "Abbrechen" (Cancel) leaves selection mode.
- **Pages**: 24, 48 (default) or 96 Tonies per page or "Zeige alle" (show all), with ‹ and › to page.

As in the web UI only real Tonies/tags are shown: no system sounds (`type == "system"`) and no hidden ones (`hide == true`). Sorted by series, then episode, using natural sort order ("Folge 2" before "Folge 10").

### Tile

Top to bottom:

1. **Series** (or the model if the series is empty, otherwise "Tonie/Tag"). Next to it a language code (e.g. `GB`) if the language differs from the most common language of all Tonies, and the checkbox in selection mode.
2. **Tonie picture**. If different content is assigned to the figure (`sourceInfo` differs), the picture of the assigned content is overlaid in the bottom right; the tooltip names both titles.
3. **Episode** (bold)
4. **RFID tag ID** (UID, e.g. `E0:04:03:50:0D:4F:2A:1B`, selectable). Without an episode the UID takes its place.
5. **Actions** (icons):

| Icon | Action |
|------|--------|
| ⓘ Info | Info dialog (see below) |
| ✎ Pencil | Edit dialog (see below) |
| ▶ Play | Play the content in the player bar at the bottom of the window. Playable if the content is valid (`valid`) or the source is a radio stream (`http…`); otherwise greyed out. |
| ⤓ Download | Shown instead of Play when content is missing but can be fetched from the Tonie cloud (`downloadTriggerUrl`). Starts the download on the TeddyCloud and refreshes the tile. Greyed out when the cloud is disabled (`cloud.enabled`). |
| ☁ Cloud | Toggles `nocloud`. Red and struck through means cloud access is blocked. |
| ⇄ Live | Toggles `live`. Red means live mode is on. |

A blue top border marks Tonies last played on a Toniebox; the tooltip names box and time.

### Info dialog

- Title: series and episode (or the title of the assigned content), with the UID below.
- Large picture and, if applicable, a note about the assigned content.
- "Zuletzt gespielt auf" (last played on) with Toniebox and time.
- Valid, exists, source, model.
- Track list: if the track positions (`trackSeconds`) match the track list, each track can be played from its start position.
- **Download TAF als \*.ogg**: saves the audio content as an Ogg file.
- **Tonie/Tag ausblenden** (hide, with confirmation): sets `hide=true`. A hidden Tonie only reappears when it is placed on a Toniebox.

### Edit dialog

- **Quelle** (source, the assigned content): free text, e.g. `lib://Folder/File.taf` or a radio stream URL `http://…`. Buttons to clear, reset to the original value, and pick a file from the TeddyCloud library (double-click to open folders, select `.taf`/`.tap` files).
- **Modell** (model): free text with clear/reset, plus a catalog search (model number, series or episode). Clicking a result takes over the model.
- **Speichern** (Save) is only enabled when something changed. The flow matches the web UI:
  1. A changed, non-empty model is checked against the catalog; unknown models are rejected.
  2. If the source changed, `source` is set, plus `nocloud=true` (so the cloud doesn't overwrite your content) and `live` according to the source (on for `http…` streams, otherwise off).
  3. A changed model is set via `tonie_model`.
  4. The tile is reloaded.

### Web UI features not included

- **Radio stream search** (queries the external radio-browser service). Stream URLs can be entered directly as source.
- **"Set audio from model", "set model from audio", assign previous/next episode** – these would require a full scan of the library for audio IDs.
- **Custom filter expressions and saved filters**
- **Live check of the Boxine cloud connection** – the cloud download is enabled based on the `cloud.enabled` setting only.

## Audio Encoder (Tonies → Audio Encoder)

Modelled on `/web/tonies/encoder`. Several audio files are encoded into one TAF file, one chapter per file. The TAF file is stored in the TeddyCloud library and can then be selected as a Tonie's source (`lib://…`) in the edit dialog.

1. **Add files** via "Datei(en) auswählen" (choose files) or drag & drop, up to 99 files. Same formats as the web UI: `.mp3 .aac .m4a .wav .flac .ogg .opus .aiff .aif .wma .ac3 .dts .taf .mp4`.
2. **Order** (= chapter order): drag & drop, sort alphabetically, or via "…" with numeric ordering (chapter 2 before chapter 10). Remove files with "Datei entfernen"/Del or clear the list.
3. **Target folder** in the library folder tree (lazy-loaded). "Neuen Ordner anlegen" creates a subfolder.
4. **File name** without `.taf`. With a single file its name is suggested. As in the web UI, `< > : " / \ | ? *` are not allowed.
5. **Custom-Tonie anlegen** (create custom Tonie, optional): after encoding, a custom model for the new TAF file is created right away (see below).
6. **Konvertieren** (Convert): the progress bar shows decoding, then upload, then waits while TeddyCloud encodes. "Abbrechen" cancels at any time. On success the list is cleared.

### Creating a custom Tonie while encoding

- **Model** (suggested: next free ID `custom-<n>`), **series** and **episode**.
- **Series and episode from audio tags**: series comes from the artist (album artist preferred, otherwise track artist, otherwise the TAF file name); episode comes from the album. The first match in list order wins; an info line shows where values came from. Values you typed yourself are never overwritten.
- **Tracks** are taken from the file names without extension, in list order (e.g. `01 Intro.mp3` → `01 Intro`).
- **Supported tag formats** (via mutagen):

  | Format | Artist / album | Cover |
  |--------|----------------|-------|
  | MP3, AIFF | ID3 (`TPE2`/`TPE1`, `TALB`) | ID3 `APIC`, front cover preferred |
  | FLAC, OGG Vorbis, OGG Opus | Vorbis comments (`ALBUMARTIST`/`ARTIST`, `ALBUM`) | FLAC picture block or `METADATA_BLOCK_PICTURE` |
  | M4A/MP4/AAC in MP4 container | `aART`/`©ART`, `©alb` | `covr` |
  | WMA | `WM/AlbumArtist`/`Author`, `WM/AlbumTitle` | `WM/Picture` |
  | WAV | ID3 or RIFF INFO (`IART`, `IPRD`) | ID3 `APIC` |

  `.taf`, raw AAC (ADTS), AC3 and DTS carry no such tags.
- **Cover from the audio files**: the first embedded cover in list order is previewed and used automatically. After encoding it is scaled to at most 800 px, uploaded as `custom_img/<model>.jpg` (PNG if transparent) and set as the model's picture. A picture chosen manually in "Weitere Angaben" takes precedence. If the image upload fails, the Tonie is created without a picture.
- **"Weitere Angaben …"** (more details) opens the custom model edit dialog without the audio section to adjust picture, title, no, release, language, category and tracks.
- **Before encoding** the data is validated (required fields, language code, release, duplicate model ID). Nothing is encoded on errors.
- **After encoding** the app reads the target folder via `/api/fileIndexV2`, takes the server-computed hash from the TAF header (the audio ID must match the one sent with the upload), and creates the model via `/api/toniesCustomJsonUpsert`. If only the model creation fails, the TAF file is kept and the model can be added later under "Tonies → Custom-Modelle".

### How encoding works

As with "server-side encoding" in the web UI:

- Each file is decoded locally to 48 kHz stereo 16-bit PCM by `QAudioDecoder` with Qt's FFmpeg backend – no extra installation needed.
- PCM data is buffered in temporary files (about 690 MB per hour of audio, which is also uploaded) and deleted afterwards.
- Upload: `POST /api/pcmUpload?name=<name>.taf&audioId=<Unix time − 0x50000000>&path=<folder>&special=library` with one `multipart/form-data` part per file. TeddyCloud encodes the TAF with the bitrate from its `encode.bitrate` setting. Several encodes within the same second each get their own, higher audio ID.
- `.taf` input files: the 4096-byte header is skipped and only the Ogg/Opus part is decoded.
- The multipart `boundary` is sent unquoted, because TeddyCloud's HTTP server (CycloneTCP) does not strip quotes and would otherwise hang.
- If no data is transferred for 60 seconds during upload (e.g. a reverse proxy size limit such as nginx `client_max_body_size`), the upload is aborted with a message. The encoding step on the TeddyCloud has no time limit.
- Progress and errors are also logged to the console (logger `teddycloud_desktop`).

**Not included:** the web UI's "encoding in the browser" option (WebAssembly Opus encoder + `/api/tafUpload`); a comparable local encoder would need an extra native library. The `encode.use_frontend` setting is ignored.

## Custom models (Tonies → Custom-Modelle)

Modelled on `/web/tonies/customeditor`. Custom models are your own entries in `tonies.custom.json` with series, episode, picture, tracks and an optional audio mapping. Assign one to a Tonie via the "Modell" field in the Tonie edit dialog; the Tonie then shows its title and picture.

### Overview

- **Tiles** with series (or model), picture, episode and model ID; click the picture for a preview.
- **Per-tile actions**: edit, duplicate (new ID `custom-<n>`, "Kopie" appended to the title), delete (with confirmation).
- **"Neues Modell"** (new model) suggests the next free ID `custom-<n>`.
- **Filter**: search text with selectable fields (default: series and model), series, episode, language.
- **Sort** by series (then episode), model, title, episode, release, language, category or no, ascending or descending, with numeric ordering.
- **Pages** of 24, 48, 96 or 192 models or show all.

### Edit dialog

- **Required**: model, series; plus episode.
- **Pictures**: picture path with suggestions from `custom_img` and preview. "Bild auswählen" (choose picture) has two tabs: *Custom* (`custom_img` folders with thumbnails, upload, new folder) and *Original* (picture URLs from `tonies.json`, multi-word search).
- **Optional metadata**: no, title, release (digits only), language (valid code such as `de-de`, with suggestions), category (suggestions, most common first).
- **Audio mapping**: pairs of audio ID and hash. The folder button picks a `.taf` from the library and takes audio ID and hash from its header. Existing pairs are shown as `lib://…` paths if the file is in the library (the library is scanned once in the background).
- **Tracks**: list with add/remove.
- Fields changed from the saved state are highlighted in yellow; "Speichern" is only enabled when something changed.
- **Browse** the filtered list with "‹ Zurück" / "Weiter ›" (back/next); "Beim Blättern speichern" saves automatically while browsing.

### Saving

Same flow as the web UI:

1. Validate the form (required fields, numeric release, valid language code).
2. Validate the whole list: duplicate model IDs and duplicate audio ID/hash pairs are rejected; a model that also exists in the official `tonies.json` only triggers a warning.
3. If the model ID changed: confirm "Modell umbenennen" (rename model), then `toniesCustomJsonRename`; linked Tonies are updated automatically (optionally the model link can be removed instead).
4. `toniesCustomJsonUpsert` with the entry; empty fields, incomplete audio pairs and empty tracks are dropped.

TeddyCloud error messages (e.g. "Target model already exists") are shown in the dialog.

**Differences from the web UI:** with an empty `tonies.custom.json` a hint is shown instead of auto-opening "Neues Modell"; duplicate models are reported more clearly; multiple audio pairs can be added (the web UI can only remove existing ones).

## TeddyAudio Playlists (Tonies → TeddyAudio Playlists)

Modelled on `/web/tonies/tap`. A TeddyAudio Playlist (TAP) is a JSON file `<name>.tap` in the library:

```json
{
  "type": "tap",
  "audio_id": 1792625260,
  "filepath": "lib://Playlists/Party Mix.taf",
  "name": "Party Mix",
  "files": [
    {"filepath": "lib://Music/song1.mp3", "name": "Song 1"},
    {"filepath": "lib://Music/song2.flac", "name": "Song 2"}
  ]
}
```

**How a TAP is used:** assign it to a Tonie as source (`lib://….tap`). On first play TeddyCloud builds the TAF at `filepath` from the files using FFmpeg and caches it (`tonie_audio_playlist.c`). It is rebuilt when the TAF is missing or its audio ID differs from `audio_id` (so `audio_id` = 0 forces a rebuild). TeddyCloud itself marks this feature as "still in development".

### Overview

- Library folders with all `.tap` files (name, size, date). Double-click opens a folder, ‹↑› goes up, a filter field helps searching.
- **Neue TAP erstellen** (new TAP in the current folder) and **Neuen Ordner anlegen** (new folder).
- **Actions for the selected TAP** (buttons or right-click): edit, **In TAF umwandeln** (convert to TAF, see below), **Einem Tonie zuweisen** (assign to a Tonie of the selected Toniebox, with search; sets `source`, blocks the cloud via `nocloud` and turns `live` off, as in the web UI), show JSON (also on double-click), download, rename, move, delete.

### Convert to TAF (in the GUI instead of on the server)

Instead of letting TeddyCloud build the TAF with FFmpeg on first play (which often fails there), the app builds it itself:

1. Each file of the TAP is downloaded (`lib://…` via `/library/…`, `content://…` via `/content/…`, `http(s)://` directly) and decoded locally to 48 kHz stereo PCM, as in the Audio Encoder.
2. Missing target folders are created.
3. The PCM data is uploaded via `/api/pcmUpload` exactly to the TAP's playlist file path, one chapter per file. **An existing TAF is overwritten.**
4. The app checks that the new TAF with the expected audio ID is in the library.
5. The new audio ID is written back into the same `.tap`.

A valid TAF at the TAP's `filepath` makes TeddyCloud serve it directly ("TAP_CACHED"). Every conversion gets a new audio ID, so Tonieboxes that cached an old version download the new content. The Opus encoding itself is done by TeddyCloud's built-in encoder (same as the Audio Encoder), not FFmpeg on the server. A non-modal progress window shows the steps; "Abbrechen" cancels; the TAP page is disabled meanwhile; temporary files are always removed.

### Editor

- **Audio-ID**: defaults to the current Unix time, as in the web UI; 0 forces a rebuild of the TAF.
- **Dateipfad Playlist** (playlist file path, required): folder and file name of the `.taf` to create. The file name follows the TAP name until you change it.
- **TAP Name** (required): also the `.tap` file name; invalid characters are replaced by `_` as in the web UI.
- **Dateien** (files; order = chapters, max. 99): "Datei hinzufügen" opens the library with multi-select (all formats FFmpeg handles). Per row: path (clear, pick from library), description, ↑/↓, remove.
- **Speichern** uploads the JSON as `<name>.tap` via `/api/fileUpload` into the current folder.

**Differences from the web UI:** renaming a TAP removes the old `.tap` file; overwriting an existing TAP asks first; a playlist needs at least one file; order is changed with ↑/↓ instead of drag & drop.

## Toniebox overview (Tonieboxen → Tonieboxen)

Heading "Deine Tonieboxen" (your Tonieboxes) with refresh. If `core.allowNewBox` is enabled in TeddyCloud, a "Neue Tonieboxen erlaubt" (new boxes allowed) warning is shown.

### Tile

1. **Box name** (`boxName`).
2. **Color variant picture** from `tonieboxes.json` / `tonieboxes.custom.json`, including its `crop`. Without a model a placeholder suggests choosing one via ✎.
3. **Last played Tonie** in the bottom right of the picture (tooltip: title and time). Clicking it opens the Tonie overview with this box selected and filtered to that Tonie, like the link in the web UI.
4. **Hardware version** (`CC3200`, `CC3235`, `ESP32`, `TB2`, otherwise `MAC`) and the **MAC address** (`AA:BB:CC:DD:EE:FF`). If `frontend.check_cc3200_cfw` is enabled and a CC3200 box answers `/api/ajax?cmd=box-battery&sub=stats` at its IP, the MAC links to the custom firmware's web frontend.
5. **Actions:**

| Icon | Action |
|------|--------|
| Wi-Fi green / grey | Online / offline; when offline the tooltip shows "last online" (`internal.last_connection`). |
| Red lock | Shown instead of Wi-Fi when the box's API access is disabled (`toniebox.api_access=false`); click to re-enable. |
| ✎ Edit | Change name and model (color variant, with preview), saved via `boxName` / `boxModel`, then the config is written. |
| Shield (certificates) | Upload client certificates (`ca.der`, `client.der`, `private.der`) via drag & drop or file dialog into `core.certdir` (shows whether it is box-specific or the default path). Only `*.der` is accepted. |
| Gear (settings) | Box-specific settings (see below) |
| Trash (delete) | Remove the box from TeddyCloud after confirmation (`removeOverlay`) |

### Toniebox settings

The same settings as in the web UI: `core.certdir`, `core.client_cert.*`, `core.flex_*`, `core.contentdir`, `toniebox.*` and selected `cloud.*` options, grouped by category. Which options appear depends on the settings level.

- Each row has a label (tooltip: description and key), an input (switch, number or text) and **"überschrieben"** (overridden). Only when checked does the box use its own value. Unchecking shows the global TeddyCloud value again and resets the box value on save (`/api/settings/reset/…`).
- **Speichern** (Save) sends all changed values and then writes the config. **Verwerfen** (Discard) restores the loaded state.
- **Settings level** Basic / Detail / Expert applies to the whole TeddyCloud; it can only be switched without unsaved changes and reloads the list.

The Toniebox sub-pages of the web UI (box setup, flashing guides, box version detection, plugins) are guides, not part of `/web/tonieboxes`, and are not included.

## TeddyCloud API used

All requests go to the configured endpoint, with Basic Auth if configured. Wrong or missing credentials (HTTP 401) show "Host requires authentication". `overlay` is the ID of the selected Toniebox; if empty, the parameter is omitted and the default content directory applies.

| Method and path | Purpose |
|-----------------|---------|
| `GET /api/getBoxes` | Tonieboxes (`ID`, `boxName`) for the Toniebox selection |
| `GET /api/settings/get/core.contentdir?overlay=…` | Content directory per box, for grouping |
| `GET /api/settings/get/internal.last_ruid?overlay=…` and `…/internal.last_ruid_time` | Last played Tonie per box (RUID and Unix time) |
| `GET /api/settings/get/cloud.enabled` | Whether the cloud download is offered |
| `GET /api/getTagIndex?overlay=…` | All Tonies (see below) |
| `GET /api/getTagInfo?ruid=…&overlay=…` | Reload one Tonie after a change (`{"tagInfo": {…}}`) |
| `POST /content/json/set/<ruid>?overlay=…` | Change a property; `text/plain` body with exactly one value: `live=true`, `nocloud=false`, `hide=true`, `source=<urlencoded>` or `tonie_model=<urlencoded>` |
| `GET /api/toniesJsonSearch?searchModel=…&searchSeries=…&searchEpisode=…` | Catalog search in the edit dialog and model validation |
| `GET /api/fileIndexV2?path=…&special=library` | Library folder contents for the file picker |
| `GET <audioUrl>` | Playback and download, e.g. `/content/download/…?overlay=…&skip_header=true`. Seeking to a track uses HTTP Range requests, which TeddyCloud supports. |
| `GET <downloadTriggerUrl>` | Fetch content from the Tonie cloud to the TeddyCloud |
| `GET <picture>` | Tonie pictures. Relative paths (`/cache/…`, `/img_unknown.png`) go to the endpoint with Basic Auth; absolute URLs are loaded directly, with Basic Auth only for the same host and port. At most 4 downloads run in parallel; one retry on timeout. |
| `GET /api/tonieboxesJson`, `GET /api/tonieboxesCustomJson` | Toniebox color variants: `[{"id", "name", "img_src", "crop": [x, y, scale]}]` |
| `GET /api/settings/get/<key>?overlay=<box ID>` | Box status: `internal.online`, `internal.toniebox_firmware.boxIC` (1 = CC3200, 2 = CC3235, 3 = ESP32, 4 = TB2), `internal.last_connection`, `internal.last_ruid` (`ffffffffffffffff` = none), `internal.last_ruid_time`, `internal.ip`, `toniebox.api_access`; global: `core.allowNewBox`, `frontend.check_cc3200_cfw`, `core.settings_level` |
| `GET /api/settings/getIndex?overlay=<box ID>` | All box settings: `{"options": [{"ID", "label", "description", "type", "value", "overlayed", "level", "min", "max"}]}` |
| `POST /api/settings/set/<key>?overlay=<box ID>` | Set a setting; `text/plain` body with the value. Answers `OK` or `ERROR`, both with HTTP 200. Empty values are rejected. |
| `POST /api/settings/reset/<key>?overlay=<box ID>` | Remove the box value so the global value applies again |
| `GET /api/triggerWriteConfig` | Write changed settings to the config file (after every change, as in the web UI) |
| `POST /api/uploadCert?overlay=<box ID>` | Upload certificates (`multipart/form-data`, one part per file) |
| `POST /api/settings/removeOverlay?overlay=<box ID>` | Delete a Toniebox, answers `OK` |
| `GET /api/toniesCustomJson` | All custom models (contents of `tonies.custom.json`) |
| `GET /api/toniesJson` | Official catalog `tonies.json` (duplicate model warning, categories, original pictures) |
| `POST /api/toniesCustomJsonUpsert` | Create or replace a custom model (same model ID); JSON body. Answers `OK`, HTTP 400 with reason on errors. |
| `POST /api/toniesCustomJsonRename` | Body `{"fromModel", "toModel", "updateContentJson": true}` |
| `POST /api/toniesCustomJsonDelete` | Body `{"models": ["custom-1", …]}` |
| `GET /api/fileIndexV2?path=…&special=custom_img` | Custom picture folders; picture paths look like `/custom_img/<folder>/<file>` |
| `POST /api/fileUpload?path=…&special=custom_img` | Upload a picture (`multipart/form-data`, field `file`) |
| `GET /library/<path>` | Contents of a library file, e.g. a `.tap` for editing |
| `POST /api/fileUpload?path=…&special=library` | Upload a file into the library (e.g. a `.tap`; field and file name = `<name>.tap`) |
| `POST /api/fileMove?special=library` | Rename/move; body `source=<path>&target=<path>` (urlencoded), answers `OK` |
| `POST /api/fileDelete?special=library` | Delete a file; body: path, answers `OK` |
| `POST /api/dirCreate?special=library` | Create a library folder; `text/plain` body with the full path, e.g. `/Audiobooks/New`. Answers `OK` or an error message. |
| `POST /api/pcmUpload?name=…&audioId=…&path=…&special=library` | Audio Encoder: PCM (48 kHz, stereo, s16le, interleaved), one multipart part per file. TeddyCloud encodes the TAF, one chapter per part. |

`/api/getTagIndex` returns `{"tags": [{"ruid", "uid", "type", "valid", "exists", "live", "nocloud", "hasCloudAuth", "hide", "claimed", "source", "trackSeconds", "audioUrl", "downloadTriggerUrl", "tonieInfo": {"model", "series", "episode", "picture", "language", "tracks"}, "sourceInfo"}]}`. `downloadTriggerUrl` is only present when the content is missing and can be fetched from the cloud; `sourceInfo` only when the assigned content belongs to a different model than the figure.

`/api/toniesJsonSearch` cannot list all Tonies: it only searches the catalog files `tonies.json` / `tonies.custom.json`, returns an empty list without a search term and at most 18 results (see `handleApiToniesJsonSearch` in TeddyCloud's `src/handler_api.c`). The overview therefore uses `/api/getTagIndex`.

## Project structure

```
src/teddycloud_desktop/
├── main.py                  # Main window with menus; wires client, settings, pages and player
├── settings.py              # AppSettings (QSettings wrapper, keyring) and settings dialog
├── teddycloud.py            # Data model, JSON parsers and async API client (QNetworkAccessManager)
├── tonies_page.py           # Tonie overview: Toniebox selection, filter, selection mode, pages, actions
├── encoder_page.py          # Audio Encoder: file list, target folder, PCM decoding (QAudioDecoder), upload
├── encoder_custom.py        # Optional "Custom-Tonie anlegen" section of the Audio Encoder
├── audio_tags.py            # Artist, album and cover from audio files (mutagen, Qt-free)
├── custom_models_page.py    # Custom models: tiles, filter, sorting, save flow
├── custom_model_dialogs.py  # Edit dialog, picture picker, preview, library audio index
├── custom_models.py         # Custom model data logic (Qt-free)
├── tap_page.py              # TeddyAudio Playlists: list, editor, assign, folder picker
├── tap.py                   # TAP format: read, write, validate (Qt-free)
├── tap_convert.py           # Convert a TAP to TAF in the GUI (download, decode, PCM upload)
├── languages.py             # Valid language codes (generated from teddycloud_web)
├── tonieboxes_page.py       # Toniebox overview and actions (edit, certificates, settings, delete)
├── toniebox_card.py         # Toniebox tile (loads its own status)
├── toniebox_dialogs.py      # Edit, settings and certificate dialogs
├── tonies_filter.py         # Filter logic (Qt-free)
├── tonie_card.py            # Tonie tile widget
├── tonie_dialogs.py         # Info, edit and library dialogs
├── audio_player.py          # Player bar (QtMultimedia)
├── images.py                # Async image cache
├── export.py                # CSV/JSON/HTML export
├── flow_layout.py           # Wrapping layout for the tiles
└── icons.py                 # Custom SVG icons
```

## Development

```bash
uv sync                # install dependencies including dev tools
uv run pytest          # run the tests
uv run ruff check      # lint
uv run ruff format     # format
```

To release a new version:

1. Raise `version` in `pyproject.toml` and run `uv lock`.
2. Move the entries from `## [Unreleased]` in [CHANGELOG.md](CHANGELOG.md) into a new section `## [X.Y.Z] - YYYY-MM-DD` and update the links at the end.
3. Commit and push, then `git tag vX.Y.Z && git push origin vX.Y.Z`.

A GitHub Actions workflow builds the Windows, macOS and Linux binaries with PyInstaller and creates the GitHub Release. Its description is generated by `packaging/release_notes.py` from the CHANGELOG section plus download instructions; preview it with `uv run python packaging/release_notes.py vX.Y.Z`. The release fails early if the tag does not match the version in `pyproject.toml` or the CHANGELOG section is missing.

## License

TeddyCloud Desktop is licensed under the **GNU General Public License v3.0 or later** (GPL-3.0-or-later), see [LICENSE](LICENSE). The reason is PyQt6, which is licensed under the GPL v3 (or a commercial license), so an application distributed with it must use a GPL-compatible license as well. Third-party notices are in [NOTICE](NOTICE).

## Acknowledgements and origin

- The UI and API flows mirror the TeddyCloud web UI [teddycloud_web](https://github.com/toniebox-reverse-engineering/teddycloud_web) by the toniebox-reverse-engineering project. Many thanks to everyone behind [TeddyCloud](https://github.com/toniebox-reverse-engineering/teddycloud) and teddycloud_web.
- `languages.py` is generated from `languageOptions` in teddycloud_web's `LanguageFlagIcon.tsx`; `BOX_SETTING_PREFIXES` in `toniebox_dialogs.py` is copied from teddycloud_web's `Settings.tsx`.
- teddycloud_web license: as of November 2026 the repository contains **no license file** and no license field in `package.json`; GitHub shows no license. The TeddyCloud backend is licensed under GPL-2.0.

## Disclaimer

This project is not affiliated with, endorsed by, or reviewed by tonies GmbH (formerly Boxine GmbH). "Toniebox" and "Tonie" are trademarks of tonies GmbH. The names are used only to describe what the software is for.
