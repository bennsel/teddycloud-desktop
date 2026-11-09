"""Dialoge des Custom-Modell-Editors: Bearbeiten, Bildauswahl, Vorschau (nach /web/tonies/customeditor)."""

from collections import deque
from collections.abc import Callable

from PyQt6.QtCore import QObject, QSize, QStringListModel, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon, QImage, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .custom_models import CustomEntry, clean_entry, entries_differ, field_errors, matches_tokens, original_pictures
from .icons import icon
from .images import ImageCache
from .languages import LANGUAGE_CODES
from .teddycloud import TONIES_JSON_PATH, LibraryEntry, TeddyCloudClient
from .tonie_dialogs import LibraryFileDialog

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif")
CHANGED_STYLE = "background: #fffbe6; border: 1px solid #ffe58f;"
MAX_ORIGINAL_RESULTS = 300


def custom_img_path(folder: str, name: str) -> str:
    """Webpfad eines eigenen Bildes wie toCustomImgWebPath: /custom_img/<ordner>/<datei>."""
    folder = folder.strip("/")
    return f"/custom_img/{folder}/{name}" if folder else f"/custom_img/{name}"


def _thumbnail(image: QImage) -> QIcon:
    return QIcon(
        QPixmap.fromImage(image).scaled(110, 110, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    )


def _icon_button(name: str, tooltip: str, slot: Callable[[], None], parent: QWidget) -> QToolButton:
    button = QToolButton(parent)
    button.setIcon(icon(name))
    button.setIconSize(QSize(18, 18))
    button.setToolTip(tooltip)
    button.clicked.connect(lambda _checked=False: slot())
    return button


# ---------------------------------------------------------------------------
# Audio-Index der Bibliothek
# ---------------------------------------------------------------------------


class LibraryAudioIndex(QObject):
    """Durchsucht die Bibliothek nach TAF-Dateien, um Audio-ID + Hash einem lib://-Pfad zuzuordnen.

    Wie in der Weboberfläche nur zur Anzeige; die Suche läuft einmal im Hintergrund und gedrosselt.
    """

    ready = pyqtSignal()
    MAX_PARALLEL = 4

    def __init__(self, client: TeddyCloudClient, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._client = client
        self._paths: dict[str, str] = {}
        self._queue: deque[str] = deque()
        self._running = 0
        self._started = False
        self.is_ready = False

    @staticmethod
    def _key(audio_id: str, hash_value: str) -> str:
        return f"{audio_id.strip()}::{hash_value.strip().lower()}"

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._queue.append("/")
        self._next()

    def resolve(self, audio_id: str, hash_value: str) -> str:
        return self._paths.get(self._key(audio_id, hash_value), "")

    def _next(self) -> None:
        while self._running < self.MAX_PARALLEL and self._queue:
            path = self._queue.popleft()
            self._running += 1
            self._client.fetch_library(path, lambda entries, p=path: self._listed(p, entries), lambda _m: self._done())
        if self._running == 0 and not self._queue and not self.is_ready:
            self.is_ready = True
            self.ready.emit()

    def _listed(self, path: str, entries: list[LibraryEntry]) -> None:
        for entry in entries:
            child = path.rstrip("/") + "/" + entry.name
            if entry.is_dir:
                self._queue.append(child)
            elif entry.audio_id and entry.hash:
                self._paths[self._key(entry.audio_id, entry.hash)] = "lib://" + child.lstrip("/")
        self._done()

    def _done(self) -> None:
        self._running -= 1
        self._next()


# ---------------------------------------------------------------------------
# Bildvorschau und Bildauswahl
# ---------------------------------------------------------------------------


class ImagePreviewDialog(QDialog):
    def __init__(self, path: str, images: ImageCache, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Bildvorschau")
        self._path = path
        self.label = QLabel("Wird geladen …", self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setMinimumSize(320, 320)
        path_label = QLabel(path, self)
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        path_label.setWordWrap(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.label, 1)
        layout.addWidget(path_label)
        layout.addWidget(buttons)
        images.imageReady.connect(self._on_image)
        image = images.get(path)
        if image is not None:
            self._on_image(path, image)

    def _on_image(self, path: str, image: QImage) -> None:
        if path == self._path:
            self.label.setPixmap(
                QPixmap.fromImage(image).scaled(
                    480, 480, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
            )


class ImagePickerDialog(QDialog):
    """Bild aus custom_img (mit Upload und Ordnern) oder aus den Original-Bildern von tonies.json wählen."""

    def __init__(self, client: TeddyCloudClient, images: ImageCache, initial: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._client = client
        self._images = images
        self.selected_path = ""
        self._original: list[str] | None = None
        self.setWindowTitle("Bild auswählen")
        self.resize(760, 560)

        self.tabs = QTabWidget(self)
        self.tabs.addTab(self._build_custom_tab(), "Custom")
        self.tabs.addTab(self._build_original_tab(), "Original")
        self.tabs.currentChanged.connect(self._on_tab_changed)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Übernehmen")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        self.buttons.accepted.connect(self._accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs, 1)
        layout.addWidget(self.buttons)
        images.imageReady.connect(self._on_image_ready)

        # Mit dem Ordner bzw. Reiter des bisherigen Bildes beginnen
        if initial.startswith("/custom_img/"):
            self._folder = "/" + initial[len("/custom_img/") :].rsplit("/", 1)[0] if initial.count("/") > 2 else "/"
        else:
            self._folder = "/"
            if initial:
                self.tabs.setCurrentIndex(1)
                self.original_search.setText(initial.rsplit("/", 1)[-1].rsplit(".", 1)[0])
        self._load_folder()
        self._update_ok()

    # ---------- Custom ----------

    def _build_custom_tab(self) -> QWidget:
        tab = QWidget(self)
        self.folder_label = QLabel(tab)
        up = _icon_button("up", "Übergeordneter Ordner", self._go_up, tab)
        new_dir = QPushButton(icon("folder"), "Neuer Ordner", tab)
        new_dir.clicked.connect(self._create_folder)
        upload = QPushButton(icon("upload"), "Bild hochladen …", tab)
        upload.clicked.connect(self._upload)
        top = QHBoxLayout()
        top.addWidget(up)
        top.addWidget(self.folder_label, 1)
        top.addWidget(new_dir)
        top.addWidget(upload)

        self.custom_list = QListWidget(tab)
        self.custom_list.setViewMode(QListView.ViewMode.IconMode)
        self.custom_list.setIconSize(QSize(110, 110))
        self.custom_list.setGridSize(QSize(140, 150))
        self.custom_list.setResizeMode(QListView.ResizeMode.Adjust)
        self.custom_list.setMovement(QListView.Movement.Static)
        self.custom_list.setWordWrap(True)
        self.custom_list.itemDoubleClicked.connect(self._on_custom_double_click)
        self.custom_list.currentItemChanged.connect(self._update_ok)
        self.custom_status = QLabel(tab)

        layout = QVBoxLayout(tab)
        layout.addLayout(top)
        layout.addWidget(self.custom_list, 1)
        layout.addWidget(self.custom_status)
        return tab

    def _load_folder(self) -> None:
        self.folder_label.setText(f"custom_img: {self._folder}")
        self.custom_list.clear()
        self.custom_status.setText("Wird geladen …")
        self._client.fetch_library(self._folder, self._show_folder, self.custom_status.setText, special="custom_img")

    def _show_folder(self, entries: list[LibraryEntry]) -> None:
        self.custom_list.clear()
        count = 0
        for entry in entries:
            if entry.is_dir:
                item = QListWidgetItem(icon("folder", size=64), entry.name)
                item.setData(Qt.ItemDataRole.UserRole, ("dir", entry.name))
            elif entry.name.lower().endswith(IMAGE_EXTENSIONS):
                path = custom_img_path(self._folder, entry.name)
                item = QListWidgetItem(entry.name)
                item.setData(Qt.ItemDataRole.UserRole, ("img", path))
                self._set_thumbnail(item, path)
                count += 1
            else:
                continue
            self.custom_list.addItem(item)
        self.custom_status.setText(f"{count} Bild(er)" if count else "Keine Bilder in diesem Ordner")

    def _set_thumbnail(self, item: QListWidgetItem, path: str) -> None:
        image = self._images.get(path)
        if image is not None:
            item.setIcon(_thumbnail(image))

    def _on_image_ready(self, path: str, image: QImage) -> None:
        for lst in (self.custom_list,):
            for row in range(lst.count()):
                item = lst.item(row)
                data = item.data(Qt.ItemDataRole.UserRole)
                if data and data[1] == path:
                    item.setIcon(_thumbnail(image))
        if path == self._original_preview_path:
            self.original_preview.setPixmap(
                QPixmap.fromImage(image).scaled(
                    220, 220, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
            )

    def _on_custom_double_click(self, item: QListWidgetItem) -> None:
        kind, value = item.data(Qt.ItemDataRole.UserRole)
        if kind == "dir":
            self._folder = self._folder.rstrip("/") + "/" + value
            self._load_folder()
        else:
            self._accept()

    def _go_up(self) -> None:
        if self._folder != "/":
            self._folder = self._folder.rstrip("/").rsplit("/", 1)[0] or "/"
            self._load_folder()

    def _create_folder(self) -> None:
        name, ok = QInputDialog.getText(self, "Neuen Ordner anlegen", "Gib den Ordnernamen an")
        name = name.strip()
        if not ok or not name:
            return
        path = self._folder.rstrip("/") + "/" + name
        self._client.create_library_directory(
            path,
            self._load_folder,
            lambda m: QMessageBox.warning(self, "Verzeichniserstellung fehlgeschlagen!", m),
            special="custom_img",
        )

    def _upload(self) -> None:
        patterns = " ".join(f"*{ext}" for ext in IMAGE_EXTENSIONS)
        files, _ = QFileDialog.getOpenFileNames(self, "Bilder hochladen", "", f"Bilder ({patterns})")
        pending = [f for f in files if f.lower().endswith(IMAGE_EXTENSIONS)]

        def next_file() -> None:
            if not pending:
                self._load_folder()
                return
            path = pending.pop(0)
            self.custom_status.setText(f"Lade {path.rsplit('/', 1)[-1]} hoch …")
            self._client.upload_custom_image(path, self._folder, next_file, failed)

        def failed(message: str) -> None:
            QMessageBox.warning(self, "Upload fehlgeschlagen", message)
            next_file()

        next_file()

    # ---------- Original ----------

    def _build_original_tab(self) -> QWidget:
        tab = QWidget(self)
        self.original_search = QLineEdit(tab)
        self.original_search.setPlaceholderText("Suchwörter (alle müssen in der URL vorkommen, Reihenfolge egal) …")
        self.original_search.setClearButtonEnabled(True)
        self._search_timer = QTimer(self, singleShot=True, interval=250)
        self._search_timer.timeout.connect(self._filter_original)
        self.original_search.textChanged.connect(lambda: self._search_timer.start())
        self.original_list = QListWidget(tab)
        self.original_list.currentItemChanged.connect(self._on_original_selected)
        self.original_list.currentItemChanged.connect(self._update_ok)
        self.original_list.itemDoubleClicked.connect(lambda _item: self._accept())
        self.original_preview = QLabel(tab)
        self.original_preview.setFixedSize(230, 230)
        self.original_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._original_preview_path = ""
        self.original_status = QLabel(tab)
        row = QHBoxLayout()
        row.addWidget(self.original_list, 1)
        row.addWidget(self.original_preview)
        layout = QVBoxLayout(tab)
        layout.addWidget(self.original_search)
        layout.addLayout(row, 1)
        layout.addWidget(self.original_status)
        return tab

    def _on_tab_changed(self, index: int) -> None:
        self._update_ok()
        if index == 1 and self._original is None:
            self._original = []
            self.original_status.setText("Original Bilder werden geladen …")
            self._client.fetch_json(TONIES_JSON_PATH, self._on_catalog, self.original_status.setText)

    def _on_catalog(self, catalog) -> None:
        self._original = original_pictures(catalog)
        self._filter_original()

    def _filter_original(self) -> None:
        if not self._original:
            self.original_status.setText(
                "Keine Original-Bilder gefunden" if self._original == [] and self.tabs.currentIndex() == 1 else ""
            )
            return
        query = self.original_search.text()
        matches = [url for url in self._original if matches_tokens(url, query)]
        self.original_list.clear()
        for url in matches[:MAX_ORIGINAL_RESULTS]:
            self.original_list.addItem(url)
        if not matches:
            self.original_status.setText("Keine URLs passen zur Suche")
        elif len(matches) > MAX_ORIGINAL_RESULTS:
            self.original_status.setText(
                f"{len(matches)} Treffer, die ersten {MAX_ORIGINAL_RESULTS} werden angezeigt – Suche verfeinern"
            )
        else:
            self.original_status.setText(f"{len(matches)} Treffer")

    def _on_original_selected(self, item: QListWidgetItem | None) -> None:
        self.original_preview.clear()
        self._original_preview_path = item.text() if item else ""
        if item:
            image = self._images.get(item.text())
            if image is not None:
                self._on_image_ready(item.text(), image)

    # ---------- Auswahl ----------

    def _current_selection(self) -> str:
        if self.tabs.currentIndex() == 0:
            item = self.custom_list.currentItem()
            data = item.data(Qt.ItemDataRole.UserRole) if item else None
            return data[1] if data and data[0] == "img" else ""
        item = self.original_list.currentItem()
        return item.text() if item else ""

    def _update_ok(self, *_args) -> None:
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(bool(self._current_selection()))

    def _accept(self) -> None:
        selection = self._current_selection()
        if selection:
            self.selected_path = selection
            self.accept()


# ---------------------------------------------------------------------------
# Bearbeitungsdialog
# ---------------------------------------------------------------------------


class CollapsibleSection(QWidget):
    """Aufklappbarer Abschnitt wie das Collapse-Element der Weboberfläche."""

    def __init__(self, title: str, content: QWidget, expanded: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.header = QToolButton(self)
        self.header.setText(title)
        self.header.setCheckable(True)
        self.header.setChecked(expanded)
        self.header.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.header.setStyleSheet("QToolButton { border: none; font-weight: bold; }")
        self.header.toggled.connect(self._toggle)
        self.content = content
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.addWidget(self.header)
        layout.addWidget(content)
        self._toggle(expanded)

    def _toggle(self, expanded: bool) -> None:
        self.header.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        self.content.setVisible(expanded)


class _AudioRow(QWidget):
    changed = pyqtSignal()
    removeRequested = pyqtSignal(object)

    def __init__(self, audio_id: str, hash_value: str, baseline: tuple[str, str], dialog: "CustomModelEditDialog") -> None:
        super().__init__(dialog)
        self._dialog = dialog
        self._baseline = baseline
        self._path = ""
        self.path_edit = QLineEdit(self)
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText("Custom-Audio aus der Bibliothek wählen")
        self.audio_edit = QLineEdit(audio_id, self)
        self.audio_edit.setPlaceholderText("audio_id")
        self.hash_edit = QLineEdit(hash_value, self)
        self.hash_edit.setPlaceholderText("hash")
        for edit in (self.audio_edit, self.hash_edit):
            edit.textChanged.connect(self._on_changed)
        self.undo_button = _icon_button("rollback", "Ursprüngliche Zuordnung wiederherstellen", self.undo, self)
        self.remove_button = QPushButton("−", self)
        self.remove_button.setFixedWidth(32)
        self.remove_button.setToolTip("Zuordnung entfernen")
        self.remove_button.clicked.connect(lambda: self.removeRequested.emit(self))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(_icon_button("clear", "Zuordnung leeren", self.clear, self))
        layout.addWidget(self.undo_button)
        layout.addWidget(self.path_edit, 3)
        layout.addWidget(_icon_button("folder", "Audio aus der Bibliothek auswählen", self.browse, self))
        layout.addWidget(self.audio_edit, 2)
        layout.addWidget(self.hash_edit, 3)
        layout.addWidget(self.remove_button)
        self.refresh_path()

    def values(self) -> tuple[str, str]:
        return self.audio_edit.text().strip(), self.hash_edit.text().strip()

    def _on_changed(self) -> None:
        self._path = ""
        self.refresh_path()
        self.changed.emit()

    def refresh_path(self) -> None:
        """Wie AudioLibraryPathInput: gewählter Pfad, sonst aus dem Index aufgelöst, sonst ID/Hash-Kurzform."""
        audio_id, hash_value = self.values()
        resolved = self._dialog.audio_index.resolve(audio_id, hash_value) if audio_id and hash_value else ""
        display = self._path or resolved or (f"{audio_id} / {hash_value[:8]}…" if audio_id and hash_value else "")
        self.path_edit.setText(display)
        self.path_edit.setToolTip(display)
        self.undo_button.setEnabled((audio_id, hash_value) != self._baseline)

    def clear(self) -> None:
        self.audio_edit.setText("")
        self.hash_edit.setText("")

    def undo(self) -> None:
        self.audio_edit.setText(self._baseline[0])
        self.hash_edit.setText(self._baseline[1])

    def browse(self) -> None:
        dialog = LibraryFileDialog(self._dialog.client, "", self._dialog, require_taf=True)
        dialog.setWindowTitle("Audio aus der Bibliothek auswählen")
        if dialog.exec() and dialog.selected_entry is not None:
            self.audio_edit.setText(dialog.selected_entry.audio_id)
            self.hash_edit.setText(dialog.selected_entry.hash)
            self._path = dialog.selected_source
            self.refresh_path()

    def set_changed_style(self, changed: bool) -> None:
        for edit in (self.audio_edit, self.hash_edit, self.path_edit):
            edit.setStyleSheet(CHANGED_STYLE if changed else "")


class CustomModelEditDialog(QDialog):
    """Formular für ein Custom-Modell; geänderte Felder werden wie in der Weboberfläche gelb markiert."""

    saveRequested = pyqtSignal(object, bool)  # Entwurf, still (beim Blättern)
    navigateRequested = pyqtSignal(int)  # -1 / +1

    def __init__(
        self,
        client: TeddyCloudClient,
        images: ImageCache,
        audio_index: LibraryAudioIndex,
        categories: list[str],
        parent: QWidget | None = None,
        show_audio: bool = True,
    ) -> None:
        super().__init__(parent)
        # Ohne Audio-Teil z. B. im Audio Encoder, der die Zuordnung nach dem Kodieren selbst setzt
        self._show_audio = show_audio
        self.client = client
        self.images = images
        self.audio_index = audio_index
        self._baseline: CustomEntry | None = None
        self._audio_rows: list[_AudioRow] = []
        self._track_edits: list[QLineEdit] = []
        self._image_paths: list[str] | None = None
        self.resize(820, 760)

        # Pflichtfelder
        self.model_edit = QLineEdit(self)
        self.series_edit = QLineEdit(self)
        self.episodes_edit = QLineEdit(self)
        top = QGridLayout()
        for column, (label, edit) in enumerate(
            (("Modell *", self.model_edit), ("Serie *", self.series_edit), ("Episode", self.episodes_edit))
        ):
            top.addWidget(QLabel(label, self), 0, column)
            top.addWidget(edit, 1, column)
        self.series_edit.setToolTip("Die Serie wird als Titel der Toniecard angezeigt")
        self.episodes_edit.setToolTip("Die Episode wird innerhalb der Toniecard angezeigt")

        # Medien und Bilder
        media = QWidget(self)
        self.pic_edit = QLineEdit(media)
        self.pic_edit.setPlaceholderText("Bild aus custom_img oder von Original-Tonies wählen")
        self._pic_completer_model = QStringListModel(self)
        completer = QCompleter(self._pic_completer_model, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.pic_edit.setCompleter(completer)
        self.pic_edit.installEventFilter(self)
        choose_pic = QPushButton("Bild auswählen", media)
        choose_pic.clicked.connect(self._choose_image)
        self.pic_preview = QLabel(media)
        self.pic_preview.setFixedSize(120, 120)
        self.pic_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pic_preview.setStyleSheet("border: 1px dashed palette(mid);")
        self.pic_preview.mousePressEvent = lambda _e: self._preview()  # type: ignore[method-assign]
        self.pic_preview.setCursor(Qt.CursorShape.PointingHandCursor)
        pic_row = QHBoxLayout()
        pic_row.addWidget(self.pic_edit, 1)
        pic_row.addWidget(choose_pic)
        media_layout = QHBoxLayout(media)
        media_layout.setContentsMargins(16, 0, 0, 0)
        media_inner = QVBoxLayout()
        media_inner.addWidget(QLabel("Url zum Bild", media))
        media_inner.addLayout(pic_row)
        media_inner.addStretch(1)
        media_layout.addLayout(media_inner, 1)
        media_layout.addWidget(self.pic_preview)
        images.imageReady.connect(self._on_image_ready)

        # Optionale Metadaten
        meta = QWidget(self)
        self.no_edit = QLineEdit(meta)
        self.title_edit = QLineEdit(meta)
        self.release_edit = QLineEdit(meta)
        self.release_edit.setToolTip("Nur Ziffern, z. B. ein Jahr")
        self.language_combo = QComboBox(meta)
        self.language_combo.setEditable(True)
        self.language_combo.addItems([""] + list(LANGUAGE_CODES))
        self.language_combo.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        self.language_combo.setToolTip("Format: de-de")
        self.category_combo = QComboBox(meta)
        self.category_combo.setEditable(True)
        self.category_combo.addItems([""] + categories)
        meta_form = QFormLayout(meta)
        meta_form.setContentsMargins(16, 0, 0, 0)
        meta_form.addRow("No", self.no_edit)
        meta_form.addRow("Titel", self.title_edit)
        meta_form.addRow("Release", self.release_edit)
        meta_form.addRow("Sprache", self.language_combo)
        meta_form.addRow("Kategorie", self.category_combo)

        # Audio-Zuordnung
        audio = QWidget(self)
        hint = QLabel(
            "<b>Hinweis: Audio-Zuordnung</b><br>Optional - nur für Metadaten (Titel, Tracks). Custom Tags funktionieren "
            "auch ohne Modell. Nur Custom-Audio - offizielle IDs überschreiben echte Tonies. Verknüpft keine NFC-Tags mit Audio.",
            audio,
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("background: #e6f4ff; border: 1px solid #91caff; border-radius: 6px; padding: 8px; color: #262626;")
        self.audio_layout = QVBoxLayout()
        add_audio = QPushButton("Audio ID und Hash hinzufügen", audio)
        add_audio.clicked.connect(lambda: self._add_audio_row("", "", ("", "")))
        audio_layout = QVBoxLayout(audio)
        audio_layout.setContentsMargins(16, 0, 0, 0)
        audio_layout.addWidget(hint)
        audio_layout.addLayout(self.audio_layout)
        audio_layout.addWidget(add_audio, 0, Qt.AlignmentFlag.AlignLeft)
        audio_index.ready.connect(self._refresh_audio_paths)

        # Tracks
        tracks = QWidget(self)
        self.tracks_layout = QVBoxLayout()
        add_track = QPushButton("Track hinzufügen", tracks)
        add_track.clicked.connect(lambda: self._add_track(""))
        tracks_layout = QVBoxLayout(tracks)
        tracks_layout.setContentsMargins(16, 0, 0, 0)
        tracks_layout.addLayout(self.tracks_layout)
        tracks_layout.addWidget(add_track, 0, Qt.AlignmentFlag.AlignLeft)

        sections = QWidget(self)
        sections_layout = QVBoxLayout(sections)
        sections_layout.setContentsMargins(0, 0, 0, 0)
        sections_layout.addWidget(CollapsibleSection("Medien und Bilder", media, expanded=True))
        sections_layout.addWidget(CollapsibleSection("Optionale Metadaten", meta))
        audio_section = CollapsibleSection("Audio-Zuordnung", audio)
        audio_section.setVisible(show_audio)
        sections_layout.addWidget(audio_section)
        sections_layout.addWidget(CollapsibleSection("Tracks", tracks))
        sections_layout.addStretch(1)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setWidget(sections)

        self.error_label = QLabel(self)
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #d4380d")
        self.warning_label = QLabel(self)
        self.warning_label.setWordWrap(True)
        self.warning_label.setStyleSheet("color: #ad6800")

        # Navigation und Speichern
        self.prev_button = QPushButton("‹ Zurück", self)
        self.prev_button.clicked.connect(lambda: self._navigate(-1))
        self.next_button = QPushButton("Weiter ›", self)
        self.next_button.clicked.connect(lambda: self._navigate(1))
        self.position_label = QLabel(self)
        self.save_on_navigate = QCheckBox("Beim Blättern speichern", self)
        self.cancel_button = QPushButton("Abbrechen", self)
        self.cancel_button.clicked.connect(self.reject)
        self.save_button = QPushButton("Speichern", self)
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(self._save)
        bottom = QHBoxLayout()
        bottom.addWidget(self.prev_button)
        bottom.addWidget(self.position_label)
        bottom.addWidget(self.next_button)
        bottom.addWidget(self.save_on_navigate)
        bottom.addStretch(1)
        bottom.addWidget(self.cancel_button)
        bottom.addWidget(self.save_button)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(scroll, 1)
        layout.addWidget(self.warning_label)
        layout.addWidget(self.error_label)
        layout.addLayout(bottom)

        for edit in (
            self.model_edit,
            self.series_edit,
            self.episodes_edit,
            self.pic_edit,
            self.no_edit,
            self.title_edit,
            self.release_edit,
        ):
            edit.textChanged.connect(self._update_changes)
        for combo in (self.language_combo, self.category_combo):
            combo.editTextChanged.connect(self._update_changes)
        self.pic_edit.textChanged.connect(self._update_preview)

    # ---------- Laden ----------

    def load(self, entry: CustomEntry, baseline: CustomEntry | None, title: str, position: tuple[int, int] | None) -> None:
        """Zeigt `entry` an; `baseline` ist der gespeicherte Stand (None bei neuen Modellen)."""
        self._baseline = baseline
        self.setWindowTitle(title)
        self.error_label.clear()
        self.warning_label.clear()
        self.model_edit.setText(entry.model)
        self.series_edit.setText(entry.series)
        self.episodes_edit.setText(entry.episodes)
        self.pic_edit.setText(entry.pic)
        self.no_edit.setText(entry.no)
        self.title_edit.setText(entry.title)
        self.release_edit.setText(entry.release)
        self.language_combo.setEditText(entry.language)
        self.category_combo.setEditText(entry.category)

        for row in self._audio_rows:
            row.deleteLater()
        self._audio_rows = []
        pairs = entry.audio_pairs() or [("", "")]
        base_pairs = baseline.audio_pairs() if baseline else []
        for index, (audio_id, hash_value) in enumerate(pairs):
            self._add_audio_row(audio_id, hash_value, base_pairs[index] if index < len(base_pairs) else ("", ""))

        for edit in self._track_edits:
            edit.parentWidget().deleteLater()
        self._track_edits = []
        for track in entry.tracks or [""]:
            self._add_track(track)

        navigable = position is not None
        for widget in (self.prev_button, self.next_button, self.position_label, self.save_on_navigate):
            widget.setVisible(navigable)
        if position:
            index, total = position
            self.position_label.setText(f"{index + 1} / {total}")
            self.prev_button.setEnabled(index > 0)
            self.next_button.setEnabled(index < total - 1)
        self._update_changes()
        self._update_preview()
        if self._show_audio:
            self.audio_index.start()

    def _add_audio_row(self, audio_id: str, hash_value: str, baseline: tuple[str, str]) -> None:
        row = _AudioRow(audio_id, hash_value, baseline, self)
        row.changed.connect(self._update_changes)
        row.removeRequested.connect(self._remove_audio_row)
        self._audio_rows.append(row)
        self.audio_layout.addWidget(row)
        self._update_remove_buttons()
        self._update_changes()

    def _remove_audio_row(self, row: _AudioRow) -> None:
        self._audio_rows.remove(row)
        row.deleteLater()
        self._update_remove_buttons()
        self._update_changes()

    def _update_remove_buttons(self) -> None:
        # Wie in der Weboberfläche: die letzte Zuordnung kann nur geleert, nicht entfernt werden
        for row in self._audio_rows:
            row.remove_button.setVisible(len(self._audio_rows) > 1)

    def _refresh_audio_paths(self) -> None:
        for row in self._audio_rows:
            row.refresh_path()

    def _add_track(self, text: str) -> None:
        holder = QWidget(self)
        edit = QLineEdit(text, holder)
        remove = QPushButton("−", holder)
        remove.setFixedWidth(32)
        remove.setToolTip("Track entfernen")
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(edit, 1)
        row.addWidget(remove)
        edit.textChanged.connect(self._update_changes)
        remove.clicked.connect(lambda: self._remove_track(edit))
        self._track_edits.append(edit)
        self.tracks_layout.addWidget(holder)
        self._update_changes()

    def _remove_track(self, edit: QLineEdit) -> None:
        self._track_edits.remove(edit)
        edit.parentWidget().deleteLater()
        self._update_changes()

    # ---------- Werte ----------

    def draft(self) -> CustomEntry:
        pairs = [row.values() for row in self._audio_rows]
        return CustomEntry(
            model=self.model_edit.text(),
            series=self.series_edit.text(),
            episodes=self.episodes_edit.text(),
            no=self.no_edit.text(),
            title=self.title_edit.text(),
            release=self.release_edit.text(),
            language=self.language_combo.currentText(),
            category=self.category_combo.currentText(),
            pic=self.pic_edit.text(),
            audio_ids=[a for a, _ in pairs],
            hashes=[h for _, h in pairs],
            tracks=[edit.text() for edit in self._track_edits],
        )

    def has_changes(self) -> bool:
        if self._baseline is None:
            return True
        return entries_differ(clean_entry(self.draft()), self._baseline)

    def _update_changes(self, *_args) -> None:
        """Geänderte Felder gegenüber dem gespeicherten Stand markieren."""
        if not hasattr(self, "save_button"):
            return
        base = self._baseline
        draft = clean_entry(self.draft())
        fields = {
            "model": self.model_edit,
            "series": self.series_edit,
            "episodes": self.episodes_edit,
            "pic": self.pic_edit,
            "no": self.no_edit,
            "title": self.title_edit,
            "release": self.release_edit,
        }
        for name, widget in fields.items():
            widget.setStyleSheet(CHANGED_STYLE if base and getattr(draft, name) != getattr(base, name) else "")
        for name, combo in (("language", self.language_combo), ("category", self.category_combo)):
            changed = base is not None and combo.currentText().strip() != getattr(base, name)
            combo.setStyleSheet(CHANGED_STYLE if changed else "")
        pairs_changed = base is not None and draft.normalized_pairs() != base.normalized_pairs()
        for row in self._audio_rows:
            row.set_changed_style(pairs_changed)
        tracks_changed = base is not None and draft.tracks != base.tracks
        for edit in self._track_edits:
            edit.setStyleSheet(CHANGED_STYLE if tracks_changed else "")
        self.save_button.setEnabled(self.has_changes())

    # ---------- Bild ----------

    def eventFilter(self, obj, event) -> bool:
        # Bildpfade für die Vorschläge erst beim ersten Fokus sammeln (wie runCollectImagePathsWhenNeeded)
        if obj is self.pic_edit and event.type() == event.Type.FocusIn and self._image_paths is None:
            self._image_paths = []
            self._collect_image_paths("/")
        return super().eventFilter(obj, event)

    def _collect_image_paths(self, folder: str) -> None:
        def listed(entries: list[LibraryEntry]) -> None:
            for entry in entries:
                if entry.is_dir:
                    self._collect_image_paths(folder.rstrip("/") + "/" + entry.name)
                elif entry.name.lower().endswith(IMAGE_EXTENSIONS):
                    self._image_paths.append(custom_img_path(folder, entry.name))
            self._pic_completer_model.setStringList(sorted(set(self._image_paths)))

        self.client.fetch_library(folder, listed, lambda _m: None, special="custom_img")

    def _choose_image(self) -> None:
        dialog = ImagePickerDialog(self.client, self.images, self.pic_edit.text().strip(), self)
        if dialog.exec():
            self.pic_edit.setText(dialog.selected_path)

    def _update_preview(self) -> None:
        path = self.pic_edit.text().strip() or "/img_unknown.png"
        self._preview_path = path
        self.pic_preview.clear()
        image = self.images.get(path)
        if image is not None:
            self._on_image_ready(path, image)

    def _on_image_ready(self, path: str, image: QImage) -> None:
        if path == getattr(self, "_preview_path", None):
            self.pic_preview.setPixmap(
                QPixmap.fromImage(image).scaled(
                    116, 116, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
            )

    def _preview(self) -> None:
        if self.pic_edit.text().strip():
            ImagePreviewDialog(self.pic_edit.text().strip(), self.images, self).exec()

    # ---------- Aktionen ----------

    def show_error(self, message: str) -> None:
        self.error_label.setText(message)

    def show_warning(self, message: str) -> None:
        self.warning_label.setText(message)

    def _save(self, silent: bool = False) -> None:
        errors = field_errors(self.draft())
        if errors:
            self.show_error("Bitte zuerst diese Probleme beheben:\n- " + "\n- ".join(errors))
            return
        self.error_label.clear()
        self.saveRequested.emit(self.draft(), silent)

    def _navigate(self, direction: int) -> None:
        if self.save_on_navigate.isChecked() and self.has_changes():
            # Beim Blättern still speichern; die Seite blättert nach erfolgreichem Speichern weiter
            self._pending_direction = direction
            self._save(silent=True)
            return
        self.navigateRequested.emit(direction)

    def take_pending_direction(self) -> int:
        direction = getattr(self, "_pending_direction", 0)
        self._pending_direction = 0
        return direction


def confirm_rename(parent: QWidget, from_model: str, to_model: str) -> tuple[bool, bool]:
    """Rückfrage beim Umbenennen. Liefert (bestätigt, verknüpfte Tonies umstellen)."""
    box = QMessageBox(parent)
    box.setWindowTitle("Modell umbenennen")
    box.setIcon(QMessageBox.Icon.Question)
    box.setText(f'Modell-ID wird von "{from_model}" zu "{to_model}" geändert. Verknüpfte Tonies werden automatisch aktualisiert.')
    skip = QCheckBox("Modellzuordnung von verknüpften Tonies entfernen (Audio bleibt)", box)
    box.setCheckBox(skip)
    confirm = box.addButton("Bestätigen", QMessageBox.ButtonRole.AcceptRole)
    box.addButton("Abbrechen", QMessageBox.ButtonRole.RejectRole)
    box.exec()
    return box.clickedButton() is confirm, not skip.isChecked()
