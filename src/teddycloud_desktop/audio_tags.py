"""Künstler, Album und Cover aus Audiodateien lesen (mit mutagen, ohne Qt).

Unterstützt ID3 (MP3, WAV, AIFF), Vorbis-Kommentare (FLAC, OGG Vorbis/Opus/FLAC), MP4/M4A und ASF (WMA),
dazu RIFF-INFO in WAV-Dateien (IART/IPRD), das mutagen selbst nicht liest.
"""

import base64
import struct
from dataclasses import dataclass, field

import mutagen
from mutagen.asf import ASFTags
from mutagen.flac import Picture
from mutagen.id3 import ID3
from mutagen.mp4 import MP4Tags

# Bildtyp "Front Cover" laut ID3/FLAC; wird bevorzugt, wenn eine Datei mehrere Bilder enthält
FRONT_COVER = 3


@dataclass
class AudioTags:
    album_artist: str = ""
    artists: list[str] = field(default_factory=list)
    album: str = ""
    # (Bildtyp, Bilddaten)
    pictures: list[tuple[int, bytes]] = field(default_factory=list)

    @property
    def artist(self) -> str:
        """Album-Interpret bevorzugen (über alle Dateien einheitlich), sonst die Track-Künstler."""
        return self.album_artist or ", ".join(dict.fromkeys(self.artists))  # doppelte Einträge (z. B. WMA) entfernen

    @property
    def cover(self) -> bytes:
        """Das Frontcover, sonst das erste Bild; leer, wenn keins eingebettet ist."""
        for picture_type, data in self.pictures:
            if picture_type == FRONT_COVER and data:
                return data
        return next((data for _type, data in self.pictures if data), b"")


def _texts(value) -> list[str]:
    """Textwerte aus den verschiedenen Tag-Typen (ID3-Frame, Liste, ASF-Attribut) als Liste."""
    if value is None:
        return []
    if hasattr(value, "text"):  # ID3-Frame
        value = value.text
    if not isinstance(value, list):
        value = [value]
    result = []
    for item in value:
        item = getattr(item, "value", item)  # ASF-Attribut
        text = str(item).strip()
        if text:
            result.append(text)
    return result


def _first(value) -> str:
    texts = _texts(value)
    return texts[0] if texts else ""


def _asf_picture(data: bytes) -> tuple[int, bytes] | None:
    """WM/Picture: Typ (1 Byte), Länge (4 Byte LE), MIME und Beschreibung (UTF-16, nullterminiert), Bilddaten."""
    try:
        picture_type, length = struct.unpack_from("<bI", data)
        position = 5
        for _ in range(2):  # MIME-Typ und Beschreibung überspringen
            while data[position : position + 2] != b"\x00\x00":
                position += 2
            position += 2
        return picture_type, data[position : position + length]
    except (struct.error, IndexError):
        return None


def _riff_info(path: str) -> dict[bytes, str]:
    """INFO-Liste einer WAV-Datei (z. B. IART = Künstler, IPRD = Album)."""
    result: dict[bytes, str] = {}
    try:
        with open(path, "rb") as file:
            if file.read(4) != b"RIFF":
                return result
            file.seek(12)
            while True:
                header = file.read(8)
                if len(header) < 8:
                    break
                chunk_id, size = header[:4], struct.unpack("<I", header[4:])[0]
                if chunk_id == b"LIST" and size >= 4 and file.read(4) == b"INFO":
                    info = file.read(size - 4)
                    position = 0
                    while position + 8 <= len(info):
                        key, length = info[position : position + 4], struct.unpack("<I", info[position + 4 : position + 8])[0]
                        raw = info[position + 8 : position + 8 + length].rstrip(b"\x00")
                        try:
                            result[key] = raw.decode("utf-8").strip()
                        except UnicodeDecodeError:
                            result[key] = raw.decode("latin-1").strip()
                        position += 8 + length + (length & 1)
                    break
                file.seek(size + (size & 1) - (4 if chunk_id == b"LIST" and size >= 4 else 0), 1)
    except OSError:
        pass
    return result


def read_audio_tags(path: str) -> AudioTags:
    """Liest die Tags einer Datei; unbekannte oder beschädigte Dateien ergeben leere Angaben."""
    try:
        audio = mutagen.File(path)
    except (mutagen.MutagenError, OSError, ValueError):
        return AudioTags()
    if audio is None:
        return AudioTags()
    result = AudioTags()
    tags = audio.tags

    if isinstance(tags, ID3):
        result.album_artist = _first(tags.get("TPE2"))
        result.artists = [t for frame in tags.getall("TPE1") for t in _texts(frame)]
        result.album = _first(tags.get("TALB"))
        result.pictures = [(frame.type, frame.data) for frame in tags.getall("APIC")]
    elif isinstance(tags, MP4Tags):
        result.album_artist = _first(tags.get("aART"))
        result.artists = _texts(tags.get("\xa9ART"))
        result.album = _first(tags.get("\xa9alb"))
        result.pictures = [(FRONT_COVER, bytes(cover)) for cover in tags.get("covr", [])]
    elif isinstance(tags, ASFTags):
        result.album_artist = _first(tags.get("WM/AlbumArtist"))
        result.artists = _texts(tags.get("Author"))
        result.album = _first(tags.get("WM/AlbumTitle"))
        for attribute in tags.get("WM/Picture", []):
            picture = _asf_picture(bytes(attribute.value))
            if picture:
                result.pictures.append(picture)
    elif tags is not None and hasattr(tags, "get"):
        # Vorbis-Kommentare (FLAC, OGG); Schlüssel sind ohne Groß/Klein
        result.album_artist = _first(tags.get("albumartist")) or _first(tags.get("album artist"))
        result.artists = _texts(tags.get("artist"))
        result.album = _first(tags.get("album"))
        for encoded in _texts(tags.get("metadata_block_picture")):
            try:
                picture = Picture(base64.b64decode(encoded))
            except (ValueError, mutagen.MutagenError):
                continue
            result.pictures.append((picture.type, picture.data))

    # FLAC führt Bilder zusätzlich als eigene Blöcke
    for picture in getattr(audio, "pictures", []) or []:
        result.pictures.append((picture.type, picture.data))

    # WAV ohne ID3: Künstler und Album aus der RIFF-INFO-Liste
    if path.lower().endswith(".wav") and not (result.artist or result.album):
        info = _riff_info(path)
        result.artists = [info[b"IART"]] if info.get(b"IART") else []
        result.album = info.get(b"IPRD", "")
    return result
