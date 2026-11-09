"""Dialoge der Tonie-Kacheln: Informationen, Bearbeiten und Dateiauswahl aus der Bibliothek."""

from collections.abc import Callable

from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .icons import icon
from .images import ImageCache
from .teddycloud import LibraryEntry, TeddyCloudClient, TonieCard, TonieInfo

LIBRARY_PREFIX = "lib://"
AUDIO_EXTENSIONS = (".taf", ".tap")


def _icon_button(name: str, tooltip: str, slot: Callable[[], None], parent: QWidget) -> QToolButton:
    button = QToolButton(parent)
    button.setIcon(icon(name))
    button.setIconSize(QSize(18, 18))
    button.setToolTip(tooltip)
    button.clicked.connect(slot)
    return button


def model_display_text(info: TonieInfo) -> str:
    if not info.model:
        return ""
    if not info.series:
        return f"[{info.model}]"
    return f"[{info.model}] {info.title}"


def confirm_hide(parent: QWidget, card: TonieCard) -> bool:
    label = card.tonie_info.title + (f" ({card.tonie_info.model})" if card.tonie_info.model else "")
    answer = QMessageBox.question(
        parent,
        "Tonie/Tag ausblenden",
        f'Möchtest du den Tonie/Tag "{label.strip() or card.uid}" wirklich aus der Toniesübersicht ausblenden? '
        "Um ihn wieder einzublenden musst du den Tonie/Tag auf eine deiner Tonieboxen platzieren.",
    )
    return answer == QMessageBox.StandardButton.Yes


class TonieInfoDialog(QDialog):
    """Entspricht dem Informations-Dialog der Weboberfläche."""

    playRequested = pyqtSignal(object, int)  # Tonie, Startposition in Sekunden
    hideRequested = pyqtSignal(object)

    def __init__(
        self,
        card: TonieCard,
        client: TeddyCloudClient,
        images: ImageCache,
        last_played: list[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._card = card
        self._client = client
        info = card.tonie_info
        from_source = card.shows_alternative_source and card.source_info is not None

        title = (card.source_info.title if from_source else info.title).strip()
        if not title:
            title = f"Tonie/Tag {info.model}" if info.model else "Unbekanntes Modell"
        self.setWindowTitle(title)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        heading = QLabel(f"<h3>{title}</h3>" + (f"<span style='color:gray'>{card.uid}</span>" if card.uid else ""), self)
        heading.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(heading)

        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumHeight(300)
        layout.addWidget(self.image_label)
        if from_source:
            layout.addWidget(QLabel(f'Der Toniefigur "{info.title}" ist der Inhalt "{card.source_info.title}" zugewiesen!', self))
        self._image_path = card.picture
        image = images.get(self._image_path)
        if image is not None:
            self._set_image(image)
        images.imageReady.connect(self._on_image_ready)

        if last_played:
            layout.addWidget(QLabel("<b>Zuletzt gespielt auf:</b><br>" + "<br>".join(last_played), self))

        form = QFormLayout()
        form.addRow("<b>Gültig:</b>", QLabel("Ja" if card.valid else "Nein", self))
        form.addRow("<b>Existiert:</b>", QLabel("Ja" if card.exists else "Nein", self))
        if card.source:
            source = QLabel(card.source, self)
            source.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            form.addRow("<b>Quelle:</b>", source)
        if info.model:
            form.addRow("<b>Modell:</b>", QLabel(info.model, self))
        layout.addLayout(form)

        tracks = card.display_tracks
        if tracks:
            layout.addWidget(QLabel("<b>Trackliste:</b>", self))
            # Einzelne Tracks sind nur abspielbar, wenn die Track-Positionen zur Trackliste passen
            playable = bool(card.audio_url) and len(card.track_seconds) == len(tracks)
            for index, track in enumerate(tracks):
                row = QHBoxLayout()
                if playable:
                    start = card.track_seconds[index]
                    row.addWidget(
                        _icon_button(
                            "play", "Ab hier abspielen", lambda _checked=False, s=start: self.playRequested.emit(card, s), self
                        )
                    )
                row.addWidget(QLabel(f"{index + 1}. {track}", self), 1)
                layout.addLayout(row)

        if card.exists and card.audio_url:
            self.download_button = QPushButton(icon("download"), "Download TAF als *.ogg", self)
            self.download_button.clicked.connect(self._download)
            layout.addWidget(self.download_button, 0, Qt.AlignmentFlag.AlignLeft)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, self)
        buttons.accepted.connect(self.accept)
        hide_button = buttons.addButton("Tonie/Tag ausblenden", QDialogButtonBox.ButtonRole.ResetRole)
        hide_button.setIcon(icon("hide"))
        hide_button.clicked.connect(self._hide)
        layout.addWidget(buttons)

    def _set_image(self, image: QImage) -> None:
        pixmap = QPixmap.fromImage(image).scaled(
            300, 300, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        self.image_label.setPixmap(pixmap)

    def _on_image_ready(self, path: str, image: QImage) -> None:
        if path == self._image_path:
            self._set_image(image)

    def _hide(self) -> None:
        if confirm_hide(self, self._card):
            self.hideRequested.emit(self._card)
            self.accept()

    def _download(self) -> None:
        card = self._card
        name = card.source_info.title if card.shows_alternative_source and card.source_info else card.tonie_info.title
        default_name = (name.strip() or card.ruid).replace("/", "_") + ".ogg"
        target, _ = QFileDialog.getSaveFileName(self, "Audio speichern", default_name, "Ogg-Audio (*.ogg)")
        if not target:
            return
        self.download_button.setEnabled(False)
        self.download_button.setText("Wird heruntergeladen …")

        def done(data: bytes) -> None:
            with open(target, "wb") as file:
                file.write(data)
            self.download_button.setText(f"Gespeichert: {target}")

        def failed(message: str) -> None:
            self.download_button.setEnabled(True)
            self.download_button.setText("Download TAF als *.ogg")
            QMessageBox.warning(self, "Download fehlgeschlagen", message)

        self._client.get_bytes(self._client.url(card.audio_url), done, failed, timeout=False)


class LibraryFileDialog(QDialog):
    """Auswahl einer Audiodatei (.taf/.tap) aus der TeddyCloud-Bibliothek."""

    def __init__(
        self,
        client: TeddyCloudClient,
        initial_source: str = "",
        parent: QWidget | None = None,
        require_taf: bool = False,
        extensions: tuple[str, ...] = AUDIO_EXTENSIONS,
        max_files: int = 1,
    ) -> None:
        super().__init__(parent)
        self._client = client
        # Nur .taf mit TAF-Header (Audio-ID und Hash), z. B. für die Audio-Zuordnung von Custom-Modellen
        self._require_taf = require_taf
        self._extensions = extensions
        # Mehr als 1: Mehrfachauswahl (z. B. Dateien einer TeddyAudio Playlist)
        self._max_files = max_files
        self.selected_source = ""
        self.selected_entry: LibraryEntry | None = None
        self.selected_sources: list[str] = []
        self.selected_entries: list[LibraryEntry] = []
        self.setWindowTitle("Audiodatei aus der Bibliothek wählen")
        self.resize(560, 460)

        self.path_label = QLabel(self)
        up_button = _icon_button("up", "Übergeordneter Ordner", self._go_up, self)
        top = QHBoxLayout()
        top.addWidget(up_button)
        top.addWidget(self.path_label, 1)

        self.list = QListWidget(self)
        self.list.itemDoubleClicked.connect(self._on_double_click)
        self.list.currentItemChanged.connect(self._update_ok)
        if max_files > 1:
            self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
            self.list.itemSelectionChanged.connect(self._update_ok)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        self.buttons.accepted.connect(self._accept_selection)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.list)
        layout.addWidget(self.buttons)

        # Mit dem Ordner der bisherigen Quelle beginnen
        path = initial_source[len(LIBRARY_PREFIX) :] if initial_source.startswith(LIBRARY_PREFIX) else ""
        self._path = "/" + path.rsplit("/", 1)[0].strip("/") if "/" in path else "/"
        self._load()

    def _load(self) -> None:
        self.path_label.setText(f"Bibliothek: {self._path}")
        self.list.clear()
        self.list.addItem("Wird geladen …")
        self._update_ok()
        self._client.fetch_library(self._path, self._show_entries, self._show_error)

    def _show_entries(self, entries: list[LibraryEntry]) -> None:
        self.list.clear()
        for entry in entries:
            if not entry.is_dir and not entry.name.lower().endswith(self._extensions):
                continue
            if self._require_taf and not entry.is_dir and not (entry.is_taf and entry.audio_id and entry.hash):
                continue
            text = entry.name
            if entry.tonie_info and entry.tonie_info.series:
                text += f"   —   {entry.tonie_info.title}"
            item = QListWidgetItem(icon("folder" if entry.is_dir else "audio"), text)
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self.list.addItem(item)
        self._update_ok()

    def _show_error(self, message: str) -> None:
        self.list.clear()
        self.list.addItem(message)

    def _entry(self, item: QListWidgetItem | None) -> LibraryEntry | None:
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def _on_double_click(self, item: QListWidgetItem) -> None:
        entry = self._entry(item)
        if entry is None:
            return
        if entry.is_dir:
            self._path = self._path.rstrip("/") + "/" + entry.name
            self._load()
        else:
            self._accept_selection()

    def _go_up(self) -> None:
        if self._path != "/":
            self._path = self._path.rstrip("/").rsplit("/", 1)[0] or "/"
            self._load()

    def _selected_files(self) -> list[LibraryEntry]:
        if self._max_files > 1:
            entries = [self._entry(item) for item in self.list.selectedItems()]
        else:
            entries = [self._entry(self.list.currentItem())]
        return [e for e in entries if e is not None and not e.is_dir]

    def _update_ok(self, *_args) -> None:
        count = len(self._selected_files())
        ok = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok.setEnabled(0 < count <= self._max_files)
        if self._max_files > 1:
            ok.setText(f"Übernehmen ({count})" if count else "Übernehmen")
            ok.setToolTip(f"Höchstens {self._max_files} Dateien" if count > self._max_files else "")

    def _accept_selection(self) -> None:
        entries = self._selected_files()
        if not entries or len(entries) > self._max_files:
            return
        folder = self._path.strip("/")
        # Reihenfolge wie in der Liste
        order = {id(self._entry(self.list.item(i))): i for i in range(self.list.count())}
        entries.sort(key=lambda e: order.get(id(e), 0))
        self.selected_entries = entries
        self.selected_sources = [LIBRARY_PREFIX + (f"{folder}/" if folder else "") + e.name for e in entries]
        self.selected_entry, self.selected_source = entries[0], self.selected_sources[0]
        self.accept()


class EditTonieDialog(QDialog):
    """Bearbeiten von Quelle (zugewiesener Inhalt) und Modell eines Tonies wie in der Weboberfläche."""

    saved = pyqtSignal(object)  # Tonie, der neu geladen werden soll

    def __init__(self, card: TonieCard, client: TeddyCloudClient, overlay: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._card = card
        self._client = client
        self._overlay = overlay
        self.setWindowTitle("Tonie/Tag bearbeiten" + (f" ({card.tonie_info.model})" if card.tonie_info.model else ""))
        self.setMinimumWidth(620)

        layout = QVBoxLayout(self)
        if card.tonie_info.series:
            layout.addWidget(QLabel(f"<span style='color:gray'>{card.tonie_info.title}</span>", self))

        # Quelle
        source_box = QGroupBox("Quelle", self)
        self.source_edit = QLineEdit(card.source, source_box)
        self.source_edit.setPlaceholderText("lib://Ordner/Datei.taf oder http://… für einen Radiostream")
        self.source_edit.textChanged.connect(self._on_changed)
        self.source_rollback = _icon_button(
            "rollback", "Ursprünglichen Wert wiederherstellen", lambda: self.source_edit.setText(card.source), source_box
        )
        source_row = QHBoxLayout()
        source_row.addWidget(_icon_button("clear", "Quelle leeren", self.source_edit.clear, source_box))
        source_row.addWidget(self.source_rollback)
        source_row.addWidget(self.source_edit, 1)
        source_row.addWidget(_icon_button("folder", "Datei aus der Bibliothek wählen", self._select_file, source_box))
        self.source_error = QLabel(source_box)
        self.source_error.setStyleSheet("color: #d4380d")
        self.source_error.setVisible(False)
        source_layout = QVBoxLayout(source_box)
        source_layout.addLayout(source_row)
        source_layout.addWidget(self.source_error)
        layout.addWidget(source_box)

        # Modell
        model_box = QGroupBox("Modell", self)
        self.model_edit = QLineEdit(card.tonie_info.model, model_box)
        self.model_edit.textChanged.connect(self._on_model_text_changed)
        self.model_rollback = _icon_button(
            "rollback", "Ursprünglichen Wert wiederherstellen", lambda: self.model_edit.setText(card.tonie_info.model), model_box
        )
        model_row = QHBoxLayout()
        model_row.addWidget(_icon_button("clear", "Modell leeren", self.model_edit.clear, model_box))
        model_row.addWidget(self.model_rollback)
        model_row.addWidget(self.model_edit, 1)
        self.model_display = QLabel(model_display_text(card.tonie_info), model_box)
        self.model_display.setStyleSheet("color: gray")
        self.model_error = QLabel(model_box)
        self.model_error.setStyleSheet("color: #d4380d")
        self.model_error.setVisible(False)
        self.search_edit = QLineEdit(model_box)
        self.search_edit.setPlaceholderText("Nach einem Modell suchen (Modellnummer, Serie oder Episode)")
        self.search_edit.setClearButtonEnabled(True)
        self.search_results = QListWidget(model_box)
        self.search_results.setMaximumHeight(160)
        self.search_results.setVisible(False)
        self.search_results.itemClicked.connect(self._on_search_result)
        # Erst suchen, wenn der Benutzer kurz nicht tippt
        self._search_timer = QTimer(self, singleShot=True, interval=300)
        self._search_timer.timeout.connect(self._search)
        self.search_edit.textChanged.connect(lambda: self._search_timer.start())
        model_layout = QVBoxLayout(model_box)
        model_layout.addLayout(model_row)
        model_layout.addWidget(self.model_display)
        model_layout.addWidget(self.model_error)
        model_layout.addWidget(self.search_edit)
        model_layout.addWidget(self.search_results)
        layout.addWidget(model_box)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel, self)
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setText("Speichern")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        self.buttons.accepted.connect(self._save)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self._on_changed()

    # ---------- Eingaben ----------

    @property
    def source(self) -> str:
        return self.source_edit.text()

    @property
    def model(self) -> str:
        return self.model_edit.text()

    def _on_changed(self) -> None:
        source_changed = self.source != self._card.source
        model_changed = self.model != self._card.tonie_info.model
        self.source_rollback.setEnabled(source_changed)
        self.model_rollback.setEnabled(model_changed)
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(source_changed or model_changed)

    def _on_model_text_changed(self) -> None:
        self.model_error.setVisible(False)
        if self.model == self._card.tonie_info.model:
            self.model_display.setText(model_display_text(self._card.tonie_info))
        elif not self.model:
            self.model_display.setText("")
        self._on_changed()

    def _select_file(self) -> None:
        dialog = LibraryFileDialog(self._client, self.source, self)
        if dialog.exec():
            self.source_edit.setText(dialog.selected_source)

    def _search(self) -> None:
        term = self.search_edit.text().strip()
        if not term:
            self.search_results.setVisible(False)
            return
        self._client.search_models(term, lambda results: self._show_results(term, results), self._show_search_error)

    def _show_results(self, term: str, results: list[TonieInfo]) -> None:
        if term != self.search_edit.text().strip():
            return  # veraltete Antwort
        self.search_results.clear()
        for info in results:
            item = QListWidgetItem(model_display_text(info) or info.model)
            item.setData(Qt.ItemDataRole.UserRole, info)
            self.search_results.addItem(item)
        if not results:
            self.search_results.addItem("Keine Treffer")
        self.search_results.setVisible(True)

    def _show_search_error(self, message: str) -> None:
        self.search_results.clear()
        self.search_results.addItem(message)
        self.search_results.setVisible(True)

    def _on_search_result(self, item: QListWidgetItem) -> None:
        info = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(info, TonieInfo):
            return
        self.model_edit.setText(info.model)
        self.model_display.setText(model_display_text(info))
        self.search_edit.clear()
        self.search_results.setVisible(False)

    # ---------- Speichern ----------

    def _save(self) -> None:
        self.buttons.setEnabled(False)
        model = self.model.strip()
        if self.model != self._card.tonie_info.model and model:
            # Nur Modelle aus dem Katalog sind gültig
            self._client.search_models(model, self._validated_model, self._save_failed, model_only=True)
        else:
            self._run_save_steps()

    def _validated_model(self, results: list[TonieInfo]) -> None:
        model_key = self.model.strip().lower()
        if not any(info.model.strip().lower() == model_key for info in results):
            self.model_error.setText(
                f'Das Modell "{self.model.strip()}" ist ungültig. Bitte ein vorhandenes Modell aus der Suche auswählen.'
            )
            self.model_error.setVisible(True)
            self.buttons.setEnabled(True)
            return
        self._run_save_steps()

    def _run_save_steps(self) -> None:
        card, source, model = self._card, self.source, self.model
        steps: list[tuple[str, str | bool]] = []
        if source != card.source:
            steps.append(("source", source))
            # Wie in der Weboberfläche: eigener Inhalt soll nicht von der Cloud überschrieben werden
            if not card.nocloud:
                steps.append(("nocloud", True))
            should_be_live = source.startswith("http")
            if should_be_live != card.live:
                steps.append(("live", should_be_live))
        if model != card.tonie_info.model:
            steps.append(("tonie_model", model))
        self._next_step(steps)

    def _next_step(self, steps: list[tuple[str, str | bool]]) -> None:
        if not steps:
            self.saved.emit(self._card)
            self.accept()
            return
        key, value = steps[0]
        self._client.set_content(
            self._card.ruid,
            self._overlay,
            key,
            value,
            lambda: self._next_step(steps[1:]),
            lambda msg: self._save_failed(msg, key),
        )

    def _save_failed(self, message: str, key: str = "") -> None:
        self.buttons.setEnabled(True)
        label = self.source_error if key == "source" else self.model_error
        label.setText(f"Speichern fehlgeschlagen: {message}")
        label.setVisible(True)
        # Teilweise gespeicherte Änderungen trotzdem in der Kachel anzeigen
        self.saved.emit(self._card)
