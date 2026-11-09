"""Datenlogik des Custom-Modell-Editors (tonies.custom.json), nach customModelEditorUtils.ts der Weboberfläche.

Bewusst ohne Qt, damit Normalisierung, Prüfung, Filter und Sortierung leicht testbar sind.
"""

import re
from collections import Counter
from dataclasses import dataclass, field, replace
from typing import Any

from .languages import to_language_code
from .teddycloud import natural_key

# Spalten, nach denen gefiltert und sortiert werden kann (Schlüssel -> Beschriftung)
FIELDS = {
    "series": "Serie",
    "model": "Modell",
    "title": "Titel",
    "episodes": "Episode",
    "release": "Release",
    "language": "Sprache",
    "category": "Kategorie",
    "no": "No",
}
DEFAULT_FILTER_FIELDS = ("series", "model")
TEXT_FIELDS = ("no", "model", "title", "series", "episodes", "release", "language", "category", "pic")


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [text for text in (_text(item) for item in value) if text]
    text = _text(value)
    return [text] if text else []


@dataclass
class CustomEntry:
    model: str = ""
    series: str = ""
    episodes: str = ""
    no: str = ""
    title: str = ""
    release: str = ""
    language: str = ""
    category: str = ""
    pic: str = ""
    audio_ids: list[str] = field(default_factory=list)
    hashes: list[str] = field(default_factory=list)
    tracks: list[str] = field(default_factory=list)

    @property
    def model_key(self) -> str:
        return model_key(self.model)

    def copy(self) -> "CustomEntry":
        return replace(self, audio_ids=list(self.audio_ids), hashes=list(self.hashes), tracks=list(self.tracks))

    def audio_pairs(self) -> list[tuple[str, str]]:
        return [(audio_id, self.hashes[i] if i < len(self.hashes) else "") for i, audio_id in enumerate(self.audio_ids)]

    def normalized_pairs(self) -> list[str]:
        """Vergleichsform der Audio-Zuordnung wie normalizeAudioPairs (Hash ohne Groß/Klein)."""
        return [f"{a}::{h.lower()}" for a, h in self.audio_pairs() if a or h]

    def selection_text(self) -> str:
        return f"[{self.model}] {self.series}{f' - {self.episodes}' if self.episodes else ''}".strip()

    def to_payload(self) -> dict[str, Any]:
        """JSON für /api/toniesCustomJsonUpsert; leere Felder werden wie in der Weboberfläche weggelassen."""
        payload: dict[str, Any] = {"model": self.model, "series": self.series}
        for name in ("no", "title", "episodes", "release", "language", "category", "pic"):
            if getattr(self, name):
                payload[name] = getattr(self, name)
        pairs = [(a, h) for a, h in self.audio_pairs() if a and h]
        if pairs:
            payload["audio_id"] = [a for a, _ in pairs]
            payload["hash"] = [h for _, h in pairs]
        if self.tracks:
            payload["tracks"] = list(self.tracks)
        return payload


def model_key(model: str) -> str:
    return _text(model).lower()


def entry_from_api(data: Any) -> CustomEntry:
    """Wie normalizeEntryFromApi: Texte trimmen, Einzelwerte zu Listen."""
    source = data if isinstance(data, dict) else {}
    return CustomEntry(
        model=_text(source.get("model")),
        series=_text(source.get("series")),
        episodes=_text(source.get("episodes")),
        no=_text(source.get("no")),
        title=_text(source.get("title")),
        release=_text(source.get("release")),
        language=_text(source.get("language")),
        category=_text(source.get("category")),
        pic=_text(source.get("pic")),
        audio_ids=_string_list(source.get("audio_id")),
        hashes=_string_list(source.get("hash")),
        tracks=_string_list(source.get("tracks")),
    )


def parse_entries(data: Any) -> list[CustomEntry]:
    if not isinstance(data, list):
        raise ValueError("Antwort ist keine Liste")
    return [entry_from_api(item) for item in data]


def clean_entry(entry: CustomEntry) -> CustomEntry:
    """Formularwerte bereinigen wie toEntry: unvollständige Audio-Paare und leere Tracks entfernen."""
    pairs = [(_text(a), _text(h)) for a, h in entry.audio_pairs()]
    pairs = [(a, h) for a, h in pairs if a and h]
    language = _text(entry.language)
    return CustomEntry(
        model=_text(entry.model),
        series=_text(entry.series),
        episodes=_text(entry.episodes),
        no=_text(entry.no),
        title=_text(entry.title),
        release=_text(entry.release),
        language=to_language_code(language) if language else "",
        category=_text(entry.category),
        pic=_text(entry.pic),
        audio_ids=[a for a, _ in pairs],
        hashes=[h for _, h in pairs],
        tracks=[t for t in (_text(track) for track in entry.tracks) if t],
    )


def entries_differ(left: CustomEntry, right: CustomEntry) -> bool:
    return (
        any(_text(getattr(left, name)) != _text(getattr(right, name)) for name in TEXT_FIELDS)
        or left.normalized_pairs() != right.normalized_pairs()
        or left.tracks != right.tracks
    )


def suggested_model(entries: list[CustomEntry]) -> str:
    """Nächste freie ID der Form custom-<n>."""
    highest = 0
    for entry in entries:
        match = re.fullmatch(r"custom-(\d+)", entry.model.strip(), re.IGNORECASE)
        if match:
            highest = max(highest, int(match.group(1)))
    return f"custom-{highest + 1}"


def field_errors(entry: CustomEntry) -> list[str]:
    """Pflichtfelder und Formate wie die Formularregeln der Weboberfläche."""
    errors = []
    if not entry.model.strip():
        errors.append("Das Modell muss ausgefüllt werden.")
    if not entry.series.strip():
        errors.append("Die Serie muss ausgefüllt werden.")
    if entry.release.strip() and not entry.release.strip().isdigit():
        errors.append("Release muss numerisch sein")
    if entry.language.strip() and not to_language_code(entry.language):
        errors.append("Ungültiger Sprachcode. Bitte verwende einen Code wie de-de, en-us.")
    return errors


def validate_entries(entries: list[CustomEntry], base_entries: list[CustomEntry]) -> tuple[str, str]:
    """Liefert (Fehler, Warnung): doppelte Modelle/Audio-Paare sind Fehler, Modelle aus tonies.json eine Warnung."""
    models: set[str] = set()
    pairs: set[str] = set()
    for entry in entries:
        if entry.model_key in models:
            return f"Doppeltes Modell: {entry.model}", ""
        models.add(entry.model_key)
        for audio_id, hash_value in entry.audio_pairs():
            pair = f"{audio_id.strip()}::{hash_value.strip().lower()}"
            if pair in pairs:
                return f"Doppelte audio_id+hash-Kombination: {audio_id}", ""
            pairs.add(pair)
    base_models = {entry.model_key for entry in base_entries}
    in_base = sorted({entry.model for entry in entries if entry.model_key in base_models})
    if in_base:
        return "", "Modell existiert in base tonies.json: " + ", ".join(in_base)
    return "", ""


def category_options(*entry_lists: list[CustomEntry]) -> list[str]:
    """Vorhandene Kategorien, häufigste zuerst."""
    counts = Counter(entry.category for entries in entry_lists for entry in entries if entry.category)
    return [name for name, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]


def original_pictures(catalog: Any) -> list[str]:
    """Bild-URLs aus tonies.json für die Bildauswahl ("Original")."""
    pictures: set[str] = set()
    for item in catalog if isinstance(catalog, list) else []:
        if not isinstance(item, dict):
            continue
        for value in (item.get("pic"), (item.get("tonieInfo") or {}).get("picture")):
            if isinstance(value, str) and value.strip():
                pictures.add(value.strip())
    return sorted(pictures)


def matches_tokens(text: str, query: str) -> bool:
    """Alle Suchwörter müssen (in beliebiger Reihenfolge) vorkommen."""
    lower = text.lower()
    return all(token.lower() in lower for token in query.split())


@dataclass
class CustomModelFilter:
    text: str = ""
    fields: tuple[str, ...] = DEFAULT_FILTER_FIELDS
    series: str = ""
    episode: str = ""
    language: str = ""

    def matches(self, entry: CustomEntry) -> bool:
        needle = self.text.strip().lower()
        if needle and not any(needle in _text(getattr(entry, name)).lower() for name in self.fields):
            return False
        if self.series.strip() and self.series.strip().lower() not in entry.series.lower():
            return False
        if self.episode.strip() and self.episode.strip().lower() not in entry.episodes.lower():
            return False
        if self.language and entry.language.lower() != self.language.lower():
            return False
        return True


def sort_entries(entries: list[CustomEntry], column: str, descending: bool = False) -> list[CustomEntry]:
    """Wie useCustomModelEditorTable: Serie sortiert zusätzlich nach Episode, danach immer nach Modell."""

    def key(entry: CustomEntry) -> tuple:
        if column == "series":
            primary = (natural_key(entry.series.lower()), natural_key(entry.episodes.lower()))
        else:
            primary = (natural_key(_text(getattr(entry, column)).lower()),)
        return (*primary, natural_key(entry.model))

    return sorted(entries, key=key, reverse=descending)
