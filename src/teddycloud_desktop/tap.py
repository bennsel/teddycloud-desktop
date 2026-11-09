"""TeddyAudio Playlists (.tap), nach useTAPEditor.ts / TeddyAudioPlaylistEditorModal.tsx der Weboberfläche.

Eine TAP ist eine JSON-Datei in der Bibliothek. Wird sie einem Tonie als Quelle zugewiesen, erzeugt die
TeddyCloud beim ersten Abspielen mit FFmpeg aus `files` die TAF-Datei unter `filepath`
(tonie_audio_playlist.c, tap_generate_taf). Sie wird neu erzeugt, wenn die Audio-ID der TAF nicht zu
`audio_id` passt, z. B. nach dem Setzen auf 0.
"""

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any

LIBRARY_PREFIX = "lib://"
TAP_EXTENSION = ".tap"
MAX_TAP_FILES = 99
# Wie ffmpegSupportedExtensions der Weboberfläche: das kann die TeddyCloud in eine TAF umwandeln
TAP_AUDIO_EXTENSIONS = (
    ".mp3",
    ".aac",
    ".m4a",
    ".wav",
    ".flac",
    ".ogg",
    ".opus",
    ".aiff",
    ".aif",
    ".wma",
    ".ac3",
    ".dts",
    ".taf",
    ".mp4",
)


@dataclass
class TapFile:
    filepath: str = ""
    name: str = ""


@dataclass
class TeddyAudioPlaylist:
    name: str = ""
    audio_id: int = field(default_factory=lambda: int(time.time()))  # wie Date.now()/1000 in der Weboberfläche
    filepath: str = ""  # Ziel-TAF, z. B. lib://Playlists/Party.taf
    files: list[TapFile] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "type": "tap",
            "audio_id": self.audio_id,
            "filepath": self.filepath,
            "name": self.name,
            "files": [{"filepath": f.filepath, "name": f.name} for f in self.files],
        }

    def to_bytes(self) -> bytes:
        return json.dumps(self.to_json(), indent=2, ensure_ascii=False).encode("utf-8")

    @property
    def file_name(self) -> str:
        """Name der .tap-Datei; sie heißt wie die Playlist."""
        return safe_tap_name(self.name) + TAP_EXTENSION


def parse_tap(data: bytes) -> TeddyAudioPlaylist:
    try:
        raw = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"keine gültige TAP-Datei ({exc})") from exc
    if not isinstance(raw, dict) or raw.get("type") != "tap":
        raise ValueError('keine gültige TAP-Datei (type ist nicht "tap")')
    try:
        audio_id = int(raw.get("audio_id") or 0)
    except (TypeError, ValueError):
        audio_id = 0
    files = [
        TapFile(filepath=str(f.get("filepath") or ""), name=str(f.get("name") or ""))
        for f in raw.get("files") or []
        if isinstance(f, dict)
    ]
    return TeddyAudioPlaylist(
        name=str(raw.get("name") or ""), audio_id=audio_id, filepath=str(raw.get("filepath") or ""), files=files
    )


def safe_tap_name(name: str) -> str:
    """Wie die Weboberfläche: ungültige Zeichen durch _ ersetzen, Punkte/Leerzeichen am Ende entfernen."""
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name.strip())
    safe = re.sub(r"[. ]+$", "", safe)
    return safe or "untitled"


def split_taf_filepath(filepath: str) -> tuple[str, str]:
    """lib://Ordner/Datei.taf -> ("/Ordner", "Datei")."""
    path = filepath.strip()
    if path.startswith(LIBRARY_PREFIX):
        path = path[len(LIBRARY_PREFIX) :]
    path = "/" + path.lstrip("/")
    folder, _, base = path.rpartition("/")
    if base.lower().endswith(".taf"):
        base = base[:-4]
    return folder or "/", base


def build_taf_filepath(folder: str, base: str) -> str:
    """("/Ordner", "Datei") -> lib://Ordner/Datei.taf"""
    folder = folder.strip("/")
    base = base.strip()
    if base.lower().endswith(".taf"):
        base = base[:-4]
    return f"{LIBRARY_PREFIX}{folder + '/' if folder else ''}{base}.taf"


def library_source(folder: str, name: str) -> str:
    """Pfad einer Bibliotheksdatei als Quelle, z. B. für einen Tonie: lib://Ordner/datei.tap"""
    folder = folder.strip("/")
    return f"{LIBRARY_PREFIX}{folder + '/' if folder else ''}{name}"


def validate_tap(tap: TeddyAudioPlaylist, taf_base: str) -> list[str]:
    errors = []
    if not taf_base.strip():
        errors.append("Der Dateipfad Playlist muss ausgefüllt werden")
    if not tap.name.strip():
        errors.append("Der TAP Name muss ausgefüllt werden")
    if not tap.files:
        # Ohne Dateien kann die TeddyCloud keine TAF erzeugen (tap_generate_taf bricht ab)
        errors.append("Die Playlist braucht mindestens eine Datei")
    if len(tap.files) > MAX_TAP_FILES:
        errors.append(f"Eine Playlist kann höchstens {MAX_TAP_FILES} Dateien enthalten")
    for index, file in enumerate(tap.files, start=1):
        if not file.filepath.strip():
            errors.append(f"Datei {index}: Der Dateipfad muss ausgefüllt werden")
    return errors
