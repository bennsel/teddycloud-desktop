"""Optional beim Kodieren direkt ein Custom-Modell (tonies.custom.json) für die neue TAF-Datei anlegen."""

import re
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QCheckBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from .audio_tags import read_audio_tags
from .custom_model_dialogs import CustomModelEditDialog, LibraryAudioIndex
from .custom_models import (
    CustomEntry,
    category_options,
    clean_entry,
    field_errors,
    parse_entries,
    suggested_model,
    validate_entries,
)
from .images import ImageCache
from .teddycloud import CUSTOM_MODELS_PATH, LibraryEntry, TeddyCloudClient


def tracks_from_files(file_names: list[str]) -> list[str]:
    """Tracknamen aus den Dateinamen (ohne Endung), in der Reihenfolge der Liste = Kapitelreihenfolge."""
    return [Path(name).stem.strip() for name in file_names if Path(name).stem.strip()]


# Coverbilder landen in der Wurzel von custom_img (existiert immer; /api/fileUpload legt keine Ordner an)
COVER_FOLDER = "/"
COVER_MAX_SIZE = 800
COVER_PREVIEW_SIZE = 72


def cover_file_name(model: str, image: QImage) -> str:
    """Dateiname des hochgeladenen Covers, z. B. custom-11.jpg (PNG nur bei Transparenz)."""
    base = re.sub(r'[<>:"/\\|?*\s]+', "_", model.strip()).strip("_") or "cover"
    return f"{base}.{'png' if image.hasAlphaChannel() else 'jpg'}"


def prepare_cover(image: QImage) -> QImage:
    """Große Cover (oft 3000 px) auf eine für Tonie-Bilder übliche Größe verkleinern."""
    if max(image.width(), image.height()) > COVER_MAX_SIZE:
        return image.scaled(
            COVER_MAX_SIZE, COVER_MAX_SIZE, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
    return image


@dataclass
class AudioMetadata:
    """Aus den Audiodateien gelesene Angaben; je Feld der erste Treffer in Listenreihenfolge."""

    cover: QImage | None = None
    cover_source: str = ""
    artist: str = ""
    artist_source: str = ""
    album: str = ""
    album_source: str = ""

    def complete(self) -> bool:
        return self.cover is not None and bool(self.artist) and bool(self.album)


class MetadataFinder(QObject):
    """Liest Cover, Künstler und Album aus den Audiodateien (in Listenreihenfolge, je Feld der erste Treffer).

    Die Tags liest mutagen (audio_tags.py). Je Durchlauf der Ereignisschleife wird nur eine Datei
    gelesen, damit die Oberfläche auch bei vielen Dateien bedienbar bleibt.
    """

    finished = pyqtSignal(object)  # AudioMetadata

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._paths: list[str] = []
        self._result = AudioMetadata()
        self._generation = 0

    def search(self, paths: list[str]) -> None:
        self._generation += 1  # laufende ältere Suche verwerfen
        self._paths = list(paths)
        self._result = AudioMetadata()
        QTimer.singleShot(0, lambda g=self._generation: self._next(g))

    def _next(self, generation: int) -> None:
        if generation != self._generation:
            return
        if not self._paths or self._result.complete():
            self.finished.emit(self._result)
            return
        path = self._paths.pop(0)
        tags, result, name = read_audio_tags(path), self._result, Path(path).name
        if result.cover is None and tags.cover:
            image = QImage.fromData(tags.cover)
            if not image.isNull():
                result.cover, result.cover_source = image, name
        if not result.artist and tags.artist:
            result.artist, result.artist_source = tags.artist, name
        if not result.album and tags.album:
            result.album, result.album_source = tags.album, name
        QTimer.singleShot(0, lambda: self._next(generation))


def find_taf_hash(entries: list[LibraryEntry], taf_name: str, audio_id: int) -> str:
    """Hash der gerade erzeugten TAF-Datei aus dem Ordnerinhalt; die Audio-ID muss zur hochgeladenen passen."""
    for entry in entries:
        if entry.name == taf_name and entry.hash and entry.audio_id == str(audio_id):
            return entry.hash
    return ""


class CustomTonieOptions(QGroupBox):
    """Ankreuzbarer Bereich im Audio Encoder. Ohne Haken wird nur kodiert."""

    changed = pyqtSignal()

    def __init__(self, client: TeddyCloudClient, images: ImageCache, parent: QWidget | None = None) -> None:
        super().__init__("Custom-Tonie anlegen (optional)", parent)
        self._client = client
        self._images = images
        self._existing: list[CustomEntry] = []
        self._file_names: list[str] = []
        # Aus den Audiodateien: Cover, Künstler (→ Serie) und Album (→ Episode)
        self._cover: QImage | None = None
        self._cover_source = ""
        self._artist = ""
        self._taf_name = ""
        self._meta_finder = MetadataFinder(self)
        self._meta_finder.finished.connect(self._on_metadata)
        self._meta_timer = QTimer(self, singleShot=True, interval=300)
        self._meta_timer.timeout.connect(self._search_metadata)
        # Zuletzt automatisch eingetragene Werte; solange das Feld noch so lautet, darf es ersetzt werden
        self._auto_series = ""
        self._auto_episode = ""
        self._auto_model = ""
        # Angaben aus "Weitere Angaben …" (Bild, Sprache, Kategorie, …) und ggf. von Hand geänderte Tracks
        self._extra = CustomEntry()
        self._tracks_override: list[str] | None = None
        self._dialog: CustomModelEditDialog | None = None

        self.setCheckable(True)
        self.setChecked(False)
        self.setToolTip(
            "Legt nach dem Kodieren ein Custom-Modell an: Audio-ID und Hash der neuen TAF-Datei werden "
            "zugeordnet, die Tracks kommen aus den Dateinamen. Serie, Episode und Bild werden aus Künstler, "
            "Album und Cover der Audiodateien vorgeschlagen."
        )
        self.model_edit = QLineEdit(self)
        self.series_edit = QLineEdit(self)
        self.episodes_edit = QLineEdit(self)
        self.tracks_label = QLabel(self)
        self.tracks_label.setWordWrap(True)
        self.details_button = QPushButton("Weitere Angaben …", self)
        self.details_button.setToolTip("Bild, Titel, Sprache, Kategorie, Release und Tracks bearbeiten")
        self.details_button.clicked.connect(self.edit_details)
        self.extra_label = QLabel(self)
        self.extra_label.setStyleSheet("color: gray")
        self.error_label = QLabel(self)
        self.error_label.setStyleSheet("color: #d4380d")
        self.error_label.setWordWrap(True)
        self.cover_preview = QLabel(self)
        self.cover_preview.setFixedSize(COVER_PREVIEW_SIZE, COVER_PREVIEW_SIZE)
        self.cover_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_preview.setStyleSheet("border: 1px dashed palette(mid);")
        self.use_cover_box = QCheckBox("Bild aus den Audiodateien übernehmen", self)
        self.use_cover_box.setToolTip(
            "Das erste eingebettete Cover (in Listenreihenfolge) wird nach dem Kodieren nach custom_img "
            "hochgeladen und als Bild des Custom-Tonies eingetragen."
        )
        self.use_cover_box.toggled.connect(self._on_use_cover_toggled)
        self.cover_info = QLabel(self)
        self.cover_info.setStyleSheet("color: gray")
        self.meta_info = QLabel(self)
        self.meta_info.setStyleSheet("color: gray")
        self.meta_info.setWordWrap(True)
        cover_text = QWidget(self)
        cover_line = QHBoxLayout()
        cover_line.addWidget(self.use_cover_box)
        cover_line.addWidget(self.cover_info, 1)
        cover_text_layout = QVBoxLayout(cover_text)
        cover_text_layout.setContentsMargins(0, 0, 0, 0)
        cover_text_layout.addLayout(cover_line)
        cover_text_layout.addWidget(self.meta_info)

        grid = QGridLayout(self)
        for column, (label, edit) in enumerate(
            (("Modell *", self.model_edit), ("Serie *", self.series_edit), ("Episode", self.episodes_edit))
        ):
            grid.addWidget(QLabel(label, self), 0, column)
            grid.addWidget(edit, 1, column)
            edit.textChanged.connect(self._on_edited)
        grid.addWidget(self.details_button, 1, 3)
        grid.addWidget(self.tracks_label, 2, 0, 1, 3)
        grid.addWidget(self.extra_label, 2, 3)
        cover_row = QHBoxLayout()
        cover_row.addWidget(self.cover_preview)
        cover_row.addWidget(cover_text, 1)
        grid.addLayout(cover_row, 3, 0, 1, 4)
        grid.addWidget(self.error_label, 4, 0, 1, 4)
        self.toggled.connect(self._on_toggled)
        self._on_toggled(False)
        self._update_labels()

    # ---------- Daten ----------

    def load(self) -> None:
        """Vorhandene Custom-Modelle laden (für den Vorschlag custom-<n> und die Prüfung auf Duplikate)."""
        self._client.fetch_json(CUSTOM_MODELS_PATH, self._on_models, lambda _m: None)

    def _on_models(self, data) -> None:
        try:
            self._existing = parse_entries(data)
        except ValueError:
            self._existing = []
        self._suggest_model()

    def _suggest_model(self) -> None:
        # Nur überschreiben, solange der Benutzer die vorgeschlagene ID nicht geändert hat
        if self.model_edit.text() in ("", self._auto_model):
            self._auto_model = suggested_model(self._existing)
            self.model_edit.setText(self._auto_model)

    def set_files(self, paths: list[str]) -> None:
        """Pfade der Audiodateien in Listenreihenfolge (Tracks und Cover-Suche)."""
        self._file_names = paths
        self._update_labels()
        if self.isChecked():
            self._meta_timer.start()  # kurz warten, falls gerade mehrere Dateien hinzukommen

    def set_taf_name(self, name: str) -> None:
        """Ohne Künstler aus den Audiodateien folgt die Serie dem TAF-Namen, bis der Benutzer sie selbst ändert."""
        self._taf_name = name.strip()
        if not self._artist:
            self._set_auto_series(self._taf_name)

    def _set_auto_series(self, value: str) -> None:
        if self.series_edit.text() in ("", self._auto_series):
            self._auto_series = value
            self.series_edit.setText(value)

    def _set_auto_episode(self, value: str) -> None:
        if self.episodes_edit.text() in ("", self._auto_episode):
            self._auto_episode = value
            self.episodes_edit.setText(value)

    def tracks(self) -> list[str]:
        return self._tracks_override if self._tracks_override is not None else tracks_from_files(self._file_names)

    def entry(self, audio_id: str = "", hash_value: str = "") -> CustomEntry:
        extra = self._extra
        return clean_entry(
            CustomEntry(
                model=self.model_edit.text(),
                series=self.series_edit.text(),
                episodes=self.episodes_edit.text(),
                no=extra.no,
                title=extra.title,
                release=extra.release,
                language=extra.language,
                category=extra.category,
                pic=extra.pic,
                audio_ids=[audio_id] if audio_id else [],
                hashes=[hash_value] if hash_value else [],
                tracks=self.tracks(),
            )
        )

    def cover_image(self) -> QImage | None:
        """Das zu verwendende Cover (schon verkleinert) oder None."""
        if self.use_cover_box.isChecked() and self._cover is not None:
            return prepare_cover(self._cover)
        return None

    def validate(self) -> list[str]:
        draft = self.entry()
        errors = field_errors(draft)
        error, _warning = validate_entries(self._existing + [draft], [])
        if error:
            errors.append(error)
        self.error_label.setText("\n".join(errors))
        return errors

    def created(self, entry: CustomEntry) -> None:
        """Nach erfolgreichem Anlegen: Felder für den nächsten Tonie zurücksetzen."""
        self._existing.append(entry)
        self._extra = CustomEntry()
        self._tracks_override = None
        self._set_cover(None, "")
        self._artist = ""
        self.meta_info.clear()
        self._auto_series = ""
        self._auto_episode = ""
        self.series_edit.clear()
        self.episodes_edit.clear()
        self.model_edit.clear()
        self._suggest_model()
        self._update_labels()

    # ---------- Oberfläche ----------

    def _on_toggled(self, checked: bool) -> None:
        # Ohne Haken nur die Überschrift zeigen, damit der Encoder übersichtlich bleibt
        for child in self.findChildren(QWidget):
            child.setVisible(checked)
        if checked and not self.model_edit.text():
            self._suggest_model()
        if checked:
            self._search_metadata()
        self.error_label.clear()
        self.changed.emit()

    def _on_edited(self) -> None:
        self.error_label.clear()
        self.changed.emit()

    def _update_labels(self) -> None:
        tracks = self.tracks()
        source = "von Hand angepasst" if self._tracks_override is not None else "aus den Dateinamen"
        if tracks:
            preview = ", ".join(tracks[:4]) + (" …" if len(tracks) > 4 else "")
            self.tracks_label.setText(f"<b>Tracks</b> ({len(tracks)}, {source}): {preview}")
        else:
            self.tracks_label.setText("<b>Tracks:</b> werden aus den Dateinamen übernommen")
        extra = [
            name
            for name, value in (
                ("Bild", self._extra.pic),
                ("Titel", self._extra.title),
                ("Sprache", self._extra.language),
                ("Kategorie", self._extra.category),
                ("Release", self._extra.release),
                ("No", self._extra.no),
            )
            if value
        ]
        self.extra_label.setText(("Weitere Angaben: " + ", ".join(extra)) if extra else "")

    # ---------- Metadaten der Audiodateien ----------

    def _search_metadata(self) -> None:
        if not self._file_names:
            self._on_metadata(AudioMetadata())
            return
        self.cover_info.setText("Lese Metadaten der Audiodateien …")
        self._meta_finder.search(self._file_names)

    def _on_metadata(self, meta: AudioMetadata) -> None:
        self._set_cover(meta.cover, meta.cover_source)
        # Künstler -> Serie (sonst TAF-Name), Album -> Episode; von Hand eingetragene Werte bleiben
        self._artist = meta.artist
        self._set_auto_series(meta.artist or self._taf_name)
        self._set_auto_episode(meta.album)
        found = []
        for field, edit, value, source, label in (
            ("Serie", self.series_edit, meta.artist, meta.artist_source, "Künstler"),
            ("Episode", self.episodes_edit, meta.album, meta.album_source, "Album"),
        ):
            if value:
                kept = "" if edit.text() == value else " – eigene Eingabe bleibt"
                found.append(f"{field} aus {label} „{value}“ ({source}){kept}")
        if found:
            self.meta_info.setText("; ".join(found))
        else:
            self.meta_info.setText("Kein Künstler/Album in den Audiodateien gefunden" if self._file_names else "")

    def _set_cover(self, image: QImage | None, source: str) -> None:
        had_cover = self._cover is not None
        self._cover, self._cover_source = image, source
        self.use_cover_box.setEnabled(image is not None)
        if image is None:
            self.cover_preview.clear()
            self.cover_preview.setText("–")
            self.use_cover_box.setChecked(False)
            self.cover_info.setText("Kein eingebettetes Bild in den Audiodateien gefunden" if self._file_names else "")
            return
        self.cover_preview.setPixmap(
            QPixmap.fromImage(image).scaled(
                COVER_PREVIEW_SIZE - 4,
                COVER_PREVIEW_SIZE - 4,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        self.cover_info.setText(f"aus {source} ({image.width()}×{image.height()})")
        # Neu gefundenes Cover vorschlagen, außer der Benutzer hat schon selbst ein Bild gewählt
        if not had_cover and not self._extra.pic:
            self.use_cover_box.setChecked(True)
        self._update_labels()

    def _on_use_cover_toggled(self, checked: bool) -> None:
        if checked and self._extra.pic:
            # Das Cover ersetzt ein in "Weitere Angaben" gewähltes Bild
            self._extra.pic = ""
        self._update_labels()
        self.changed.emit()

    def edit_details(self) -> None:
        """Den Bearbeitungsdialog der Custom-Modelle ohne Audio-Teil öffnen; gespeichert wird erst nach dem Kodieren."""
        if self._dialog is None:
            self._dialog = CustomModelEditDialog(
                self._client,
                self._images,
                LibraryAudioIndex(self._client, self),
                category_options(self._existing),
                self,
                show_audio=False,
            )
            self._dialog.saveRequested.connect(self._details_saved)
            self._dialog.save_button.setText("Übernehmen")
        self._dialog.load(self.entry(), None, "Weitere Angaben zum Custom-Tonie", None)
        self._dialog.exec()

    def _details_saved(self, draft: CustomEntry, _silent: bool) -> None:
        draft = clean_entry(draft)
        self.model_edit.setText(draft.model)
        self.series_edit.setText(draft.series)
        self.episodes_edit.setText(draft.episodes)
        if draft.pic:
            # Von Hand gewähltes Bild hat Vorrang vor dem Cover aus den Audiodateien
            self.use_cover_box.setChecked(False)
        self._extra = draft
        self._tracks_override = draft.tracks if draft.tracks != tracks_from_files(self._file_names) else None
        self._update_labels()
        self._dialog.accept()
        self.changed.emit()
