"""Custom-Modelle (tonies.custom.json) verwalten, nachgebaut nach /web/tonies/customeditor."""

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QImage, QMouseEvent, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .custom_model_dialogs import CustomModelEditDialog, ImagePreviewDialog, LibraryAudioIndex, confirm_rename
from .custom_models import (
    DEFAULT_FILTER_FIELDS,
    FIELDS,
    CustomEntry,
    CustomModelFilter,
    category_options,
    clean_entry,
    model_key,
    parse_entries,
    sort_entries,
    suggested_model,
    validate_entries,
)
from .flow_layout import FlowLayout
from .icons import ACTIVE_COLOR, icon
from .images import ImageCache
from .teddycloud import CUSTOM_MODELS_PATH, TONIES_JSON_PATH, UNKNOWN_PICTURE, TeddyCloudClient
from .tonie_card import CARD_STYLESHEET, CARD_WIDTH, IMAGE_SIZE

PAGE_SIZES = [24, 48, 96, 192, 0]  # 0 = alle


class CustomModelCard(QFrame):
    editRequested = pyqtSignal(object)
    duplicateRequested = pyqtSignal(object)
    deleteRequested = pyqtSignal(object)
    previewRequested = pyqtSignal(str)

    def __init__(self, entry: CustomEntry, images: ImageCache, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.entry = entry
        self._picture = entry.pic or UNKNOWN_PICTURE
        self.setObjectName("tonieCard")
        self.setFixedWidth(CARD_WIDTH)
        self.setFrameShape(QFrame.Shape.StyledPanel)

        title = QLabel(self)
        font = title.font()
        font.setBold(True)
        title.setFont(font)
        name = entry.series or entry.model or "-"
        title.setText(title.fontMetrics().elidedText(name, Qt.TextElideMode.ElideRight, CARD_WIDTH - 24))
        title.setToolTip(name)

        self.image = QLabel(self)
        self.image.setFixedSize(IMAGE_SIZE, IMAGE_SIZE)
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if entry.pic:
            self.image.setCursor(Qt.CursorShape.PointingHandCursor)
            self.image.setToolTip("Bildvorschau")
            self.image.mousePressEvent = self._on_image_clicked  # type: ignore[method-assign]

        # Wie die Weboberfläche: Episode als Titel, Modell als Beschreibung (wenn es nicht schon oben steht)
        episode = QLabel(entry.episodes, self)
        episode_font = episode.font()
        episode_font.setBold(True)
        episode.setFont(episode_font)
        episode.setVisible(bool(entry.episodes))
        model = QLabel(entry.model, self)
        model.setObjectName("uidLabel")
        model.setVisible(bool(entry.model) and entry.model != name)

        actions = QHBoxLayout()
        actions.setSpacing(0)
        for icon_name, tooltip, signal, color in (
            ("edit", "Bearbeiten", self.editRequested, None),
            ("copy", "Duplizieren", self.duplicateRequested, None),
            ("delete", "Löschen", self.deleteRequested, ACTIVE_COLOR),
        ):
            button = QToolButton(self)
            button.setIcon(icon(icon_name, color) if color else icon(icon_name))
            button.setIconSize(QSize(20, 20))
            button.setAutoRaise(True)
            button.setToolTip(tooltip)
            button.clicked.connect(lambda _checked=False, s=signal: s.emit(self.entry))
            actions.addWidget(button, 1)

        separator = QFrame(self)
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setObjectName("cardSeparator")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 4)
        layout.setSpacing(4)
        layout.addWidget(title)
        layout.addWidget(self.image, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(episode)
        layout.addWidget(model)
        layout.addWidget(separator)
        layout.addLayout(actions)

        images.imageReady.connect(self._on_image_ready)
        image = images.get(self._picture)
        if image is not None:
            self._on_image_ready(self._picture, image)

    def _on_image_ready(self, path: str, image: QImage) -> None:
        if path == self._picture:
            self.image.setPixmap(
                QPixmap.fromImage(image).scaled(
                    IMAGE_SIZE, IMAGE_SIZE, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
            )

    def _on_image_clicked(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.previewRequested.emit(self.entry.pic)


class CustomModelsPage(QWidget):
    statusMessage = pyqtSignal(str)
    modelsChanged = pyqtSignal()

    def __init__(self, client: TeddyCloudClient, images: ImageCache, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._client = client
        self._images = images
        self._entries: list[CustomEntry] = []  # gespeicherter Stand von tonies.custom.json
        self._base: list[CustomEntry] = []  # tonies.json (Warnung bei gleichen Modellen, Kategorien)
        self._visible: list[CustomEntry] = []  # gefiltert und sortiert
        self._cards: list[CustomModelCard] = []
        self._page = 0
        self._dialog: CustomModelEditDialog | None = None
        self._editing: CustomEntry | None = None  # gespeicherter Stand des bearbeiteten Modells, None = neu
        self._audio_index: LibraryAudioIndex | None = None

        self.setStyleSheet(CARD_STYLESHEET)
        self._build_ui()

    # ---------- Oberfläche ----------

    def _build_ui(self) -> None:
        new_button = QPushButton(icon("edit"), "Neues Modell", self)
        new_button.clicked.connect(self.create_model)
        refresh_button = QPushButton(icon("refresh"), "Aktualisieren", self)
        refresh_button.clicked.connect(self.load)
        header = QHBoxLayout()
        header.addWidget(QLabel("<h2>Custom-Modelle</h2>", self))
        header.addStretch(1)
        header.addWidget(new_button)
        header.addWidget(refresh_button)

        # Filter
        self.filter_button = QPushButton("Filter", self)
        self.filter_button.setCheckable(True)
        self.filter_box = QGroupBox(self)
        self.filter_box.setVisible(False)
        self.filter_button.toggled.connect(self.filter_box.setVisible)
        self.search_edit = QLineEdit(self.filter_box)
        self.search_edit.setPlaceholderText("Modelle filtern...")
        self.fields_button = QToolButton(self.filter_box)
        self.fields_button.setText("In Feldern suchen")
        self.fields_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        fields_menu = QMenu(self.fields_button)
        self._field_actions = {}
        for key, label in FIELDS.items():
            action = fields_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(key in DEFAULT_FILTER_FIELDS)
            action.toggled.connect(self._apply_filters)
            self._field_actions[key] = action
        self.fields_button.setMenu(fields_menu)
        self.series_edit = QLineEdit(self.filter_box)
        self.episode_edit = QLineEdit(self.filter_box)
        self.language_combo = QComboBox(self.filter_box)
        reset_button = QPushButton("Filter zurücksetzen", self.filter_box)
        reset_button.clicked.connect(self.reset_filters)
        for edit in (self.search_edit, self.series_edit, self.episode_edit):
            edit.setClearButtonEnabled(True)
            edit.textChanged.connect(self._apply_filters)
        self.language_combo.currentIndexChanged.connect(self._apply_filters)
        grid = QGridLayout(self.filter_box)
        grid.addWidget(QLabel("Suche:"), 0, 0)
        grid.addWidget(self.search_edit, 0, 1, 1, 2)
        grid.addWidget(self.fields_button, 0, 3)
        grid.addWidget(QLabel("Serie:"), 1, 0)
        grid.addWidget(self.series_edit, 1, 1)
        grid.addWidget(QLabel("Episode:"), 1, 2)
        grid.addWidget(self.episode_edit, 1, 3)
        grid.addWidget(QLabel("Sprache:"), 2, 0)
        grid.addWidget(self.language_combo, 2, 1)
        grid.addWidget(reset_button, 2, 3)

        # Sortierung und Seiten
        self.sort_combo = QComboBox(self)
        for key, label in FIELDS.items():
            self.sort_combo.addItem(f"Sortieren: {label}", key)
        self.sort_combo.currentIndexChanged.connect(self._apply_filters)
        self.order_button = QToolButton(self)
        self.order_button.setCheckable(True)
        self.order_button.setText("↑")
        self.order_button.setToolTip("Aufsteigend / absteigend")
        self.order_button.toggled.connect(lambda down: (self.order_button.setText("↓" if down else "↑"), self._apply_filters()))
        self.count_label = QLabel(self)
        self.page_size_combo = QComboBox(self)
        for size in PAGE_SIZES:
            self.page_size_combo.addItem(f"{size} Modelle/Seite" if size else "Zeige alle", size)
        self.page_size_combo.currentIndexChanged.connect(self._on_page_size_changed)
        self.prev_button = QToolButton(self)
        self.prev_button.setText("‹")
        self.prev_button.clicked.connect(lambda: self._go_to_page(self._page - 1))
        self.page_label = QLabel(self)
        self.next_button = QToolButton(self)
        self.next_button.setText("›")
        self.next_button.clicked.connect(lambda: self._go_to_page(self._page + 1))
        toolbar = QHBoxLayout()
        toolbar.addWidget(self.filter_button)
        toolbar.addWidget(self.sort_combo)
        toolbar.addWidget(self.order_button)
        toolbar.addStretch(1)
        toolbar.addWidget(self.count_label)
        toolbar.addWidget(self.page_size_combo)
        toolbar.addWidget(self.prev_button)
        toolbar.addWidget(self.page_label)
        toolbar.addWidget(self.next_button)

        self.cards_container = QWidget(self)
        self.flow = FlowLayout(self.cards_container)
        self.flow.setContentsMargins(4, 4, 4, 4)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.cards_container)
        self.scroll = scroll
        self.empty_label = QLabel(self)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setVisible(False)

        layout = QVBoxLayout(self)
        layout.addLayout(header)
        layout.addLayout(toolbar)
        layout.addWidget(self.filter_box)
        layout.addWidget(self.empty_label)
        layout.addWidget(scroll, 1)

    # ---------- Laden ----------

    def load(self) -> None:
        self.statusMessage.emit("Lade Custom-Modelle …")
        self._audio_index = LibraryAudioIndex(self._client, self)  # Bibliothek kann sich geändert haben
        self._dialog = None
        self._client.fetch_json(TONIES_JSON_PATH, self._on_base, lambda _m: self._on_base([]))
        self._client.fetch_json(CUSTOM_MODELS_PATH, self._on_custom)

    def _on_base(self, data) -> None:
        try:
            self._base = parse_entries(data)
        except ValueError:
            self._base = []

    def _on_custom(self, data) -> None:
        try:
            self._entries = parse_entries(data)
        except ValueError as exc:
            self.statusMessage.emit(f"Unerwartete Antwort von {CUSTOM_MODELS_PATH}: {exc}")
            return
        self._update_language_combo()
        self._apply_filters()
        self.statusMessage.emit(f"{len(self._entries)} Custom-Modelle geladen")

    def _update_language_combo(self) -> None:
        current = self.language_combo.currentData()
        self.language_combo.blockSignals(True)
        self.language_combo.clear()
        self.language_combo.addItem("alle", "")
        for language in sorted({e.language for e in self._entries if e.language}):
            self.language_combo.addItem(language, language)
        self.language_combo.setCurrentIndex(max(self.language_combo.findData(current), 0))
        self.language_combo.blockSignals(False)

    # ---------- Filter, Sortierung, Seiten ----------

    def current_filter(self) -> CustomModelFilter:
        fields = tuple(key for key, action in self._field_actions.items() if action.isChecked()) or DEFAULT_FILTER_FIELDS
        return CustomModelFilter(
            text=self.search_edit.text(),
            fields=fields,
            series=self.series_edit.text(),
            episode=self.episode_edit.text(),
            language=self.language_combo.currentData() or "",
        )

    def reset_filters(self) -> None:
        for edit in (self.search_edit, self.series_edit, self.episode_edit):
            edit.blockSignals(True)
            edit.clear()
            edit.blockSignals(False)
        for key, action in self._field_actions.items():
            action.blockSignals(True)
            action.setChecked(key in DEFAULT_FILTER_FIELDS)
            action.blockSignals(False)
        self.language_combo.setCurrentIndex(0)
        self._apply_filters()

    def _apply_filters(self, *_args) -> None:
        model_filter = self.current_filter()
        filtered = [entry for entry in self._entries if model_filter.matches(entry)]
        self._visible = sort_entries(filtered, self.sort_combo.currentData() or "series", self.order_button.isChecked())
        self._page = min(self._page, self._page_count() - 1)
        self._render()

    def _page_size(self) -> int:
        return self.page_size_combo.currentData() or 0

    def _page_count(self) -> int:
        size = self._page_size()
        return max((len(self._visible) + size - 1) // size, 1) if size else 1

    def _on_page_size_changed(self) -> None:
        self._page = 0
        self._render()

    def _go_to_page(self, page: int) -> None:
        if 0 <= page < self._page_count():
            self._page = page
            self._render()
            self.scroll.verticalScrollBar().setValue(0)

    def _render(self) -> None:
        size = self._page_size()
        page_entries = self._visible[self._page * size : (self._page + 1) * size] if size else self._visible
        for card in self._cards:
            self.flow.removeWidget(card)
            card.deleteLater()
        self._cards = []
        for entry in page_entries:
            card = CustomModelCard(entry, self._images, self.cards_container)
            card.editRequested.connect(self.edit_model)
            card.duplicateRequested.connect(self.duplicate_model)
            card.deleteRequested.connect(self.delete_model)
            card.previewRequested.connect(lambda path: ImagePreviewDialog(path, self._images, self).exec())
            self.flow.addWidget(card)
            self._cards.append(card)
        total, shown = len(self._entries), len(self._visible)
        self.count_label.setText(f"{shown} von {total} Modellen" if shown != total else f"{total} Modelle")
        self.page_label.setText(f"Seite {self._page + 1} von {self._page_count()}")
        self.prev_button.setEnabled(self._page > 0)
        self.next_button.setEnabled(self._page < self._page_count() - 1)
        if not self._entries:
            self.empty_label.setText(
                "<h3>Keine Custom-Modelle</h3>tonies.custom.json ist leer. Füge dein erstes Modell über „Neues Modell“ hinzu."
            )
        else:
            self.empty_label.setText("Keine Modelle passen zum Filter.")
        self.empty_label.setVisible(not page_entries)

    # ---------- Bearbeiten ----------

    def _editor(self) -> CustomModelEditDialog:
        if self._dialog is None:
            if self._audio_index is None:
                self._audio_index = LibraryAudioIndex(self._client, self)
            self._dialog = CustomModelEditDialog(
                self._client, self._images, self._audio_index, category_options(self._entries, self._base), self
            )
            self._dialog.saveRequested.connect(self._save)
            self._dialog.navigateRequested.connect(self._navigate)
        return self._dialog

    def create_model(self, template: CustomEntry | None = None) -> None:
        entry = template or CustomEntry(model=suggested_model(self._entries))
        self._editing = None
        dialog = self._editor()
        dialog.load(entry, None, "Neues Modell", None)
        dialog.exec()

    def duplicate_model(self, entry: CustomEntry) -> None:
        copy = entry.copy()
        copy.model = suggested_model(self._entries)
        if copy.title:
            copy.title = f"{copy.title} Kopie"
        self.create_model(copy)

    def edit_model(self, entry: CustomEntry) -> None:
        self._open_existing(entry)
        self._editor().exec()

    def _open_existing(self, entry: CustomEntry) -> None:
        self._editing = entry
        index = next((i for i, e in enumerate(self._visible) if e is entry), -1)
        position = (index, len(self._visible)) if index >= 0 else None
        title = f"Modell {index + 1} von {len(self._visible)} bearbeiten" if index >= 0 else "Modell bearbeiten"
        self._editor().load(entry.copy(), entry, title, position)

    def _navigate(self, direction: int) -> None:
        if self._editing is None:
            return
        index = next((i for i, e in enumerate(self._visible) if e is self._editing), -1)
        target = index + direction
        if 0 <= target < len(self._visible):
            self._open_existing(self._visible[target])

    def _save(self, draft: CustomEntry, silent: bool) -> None:
        dialog = self._editor()
        entry = clean_entry(draft)
        original = self._editing
        others = [e for e in self._entries if e is not original]
        error, warning = validate_entries(others + [entry], self._base)
        if error:
            dialog.show_error(f"Bitte zuerst diese Probleme beheben:\n- {error}")
            return
        dialog.show_warning(warning)

        def upsert() -> None:
            self._client.upsert_custom_model(entry.to_payload(), lambda: self._saved(entry, original, silent), failed)

        def failed(message: str) -> None:
            dialog.show_error(f"Modellerstellung fehlgeschlagen! {message}")
            dialog.take_pending_direction()

        if original is not None and original.model.strip() != entry.model:
            confirmed, update_tonies = confirm_rename(dialog, original.model, entry.model)
            if not confirmed:
                dialog.take_pending_direction()
                return
            self._client.rename_custom_model(
                original.model,
                entry.model,
                update_tonies,
                upsert,
                lambda message: failed(f"Umbenennung fehlgeschlagen: {message}"),
            )
        else:
            upsert()

    def _saved(self, entry: CustomEntry, original: CustomEntry | None, silent: bool) -> None:
        if original is not None and original in self._entries:
            self._entries[self._entries.index(original)] = entry
        else:
            # Upsert ersetzt ein vorhandenes Modell gleichen Namens
            self._entries = [e for e in self._entries if model_key(e.model) != entry.model_key] + [entry]
        self._editing = entry
        self._update_language_combo()
        self._apply_filters()
        self.modelsChanged.emit()
        self.statusMessage.emit(f"Modell {entry.series or entry.model} wurde erfolgreich gespeichert")
        dialog = self._editor()
        direction = dialog.take_pending_direction()
        if silent and direction:
            self._navigate(direction)
        else:
            dialog.accept()

    def delete_model(self, entry: CustomEntry) -> None:
        answer = QMessageBox.question(
            self, "Modell löschen", f'"{entry.model}" wirklich löschen? Dies kann nicht rückgängig gemacht werden.'
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        def deleted() -> None:
            self._entries = [e for e in self._entries if e is not entry]
            self._apply_filters()
            self.modelsChanged.emit()
            self.statusMessage.emit(f'Modell "{entry.model}" wurde gelöscht.')

        def failed(message: str) -> None:
            self.statusMessage.emit(message)
            QMessageBox.warning(self, "Löschen fehlgeschlagen", message)

        self._client.delete_custom_models([entry.model], deleted, failed)
