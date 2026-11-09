# Changelog

All notable changes to this project are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

The release workflow takes the section of the tagged version as the description of the GitHub release, so every version needs a section here before it is tagged.

## [Unreleased]

## [0.1.0] - 2026-11-10

Initial release.

### Added

- **Tonie overview**: tiles for all Tonies per Toniebox content directory, filters (text, series, episode, language, state, last played), paging, built-in player with track jumps, cloud and live toggles, cloud download, info and edit dialogs (source from the library or a radio stream, model via catalog search), selection mode with bulk actions and export as CSV, JSON, HTML or HTML with embedded images.
- **Audio Encoder**: encode up to 99 audio files into one TAF (one chapter per file) in the TeddyCloud library, with local decoding through Qt's bundled FFmpeg. Optionally creates a custom Tonie in the same step, with series, episode and cover taken from the audio tags.
- **Custom models**: create, edit, duplicate, rename and delete entries in `tonies.custom.json`, with picture picker, audio ID/hash mapping from library files and the same validation as the web UI.
- **TeddyAudio Playlists**: browse, create, edit, rename, move, download and delete `.tap` playlists, assign them to a Tonie, and convert them to a TAF in the app instead of on the server.
- **Toniebox overview**: name, color variant, hardware version, MAC address, online state and last played Tonie per box; edit name and model, upload certificates, box-specific settings with overrides, remove a box.
- Optional HTTP Basic Auth for TeddyCloud behind a reverse proxy; the password is stored in the system keyring.
- Prebuilt binaries for Windows, macOS (Apple Silicon) and Linux.

[Unreleased]: https://github.com/bennsel/teddycloud-desktop/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/bennsel/teddycloud-desktop/releases/tag/v0.1.0
