"""TeddyAudio Playlists verwalten, nachgebaut nach /web/tonies/tap der TeddyCloud-Weboberfläche."""

import json
from datetime import datetime

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .encoder_page import INVALID_NAME_CHARS_DISPLAY, LibraryDirectoryTree, is_valid_name
from .icons import icon
from .settings import AppSettings
from .tap import (
    MAX_TAP_FILES,
    TAP_AUDIO_EXTENSIONS,
    TAP_EXTENSION,
    TapFile,
    TeddyAudioPlaylist,
    build_taf_filepath,
    library_source,
    parse_tap,
    split_taf_filepath,
    validate_tap,
)
from .tap_convert import TapConverter, conversion_problems
from .teddycloud import LibraryEntry, TeddyCloudClient, TonieCard, sort_cards
from .tonie_dialogs import LibraryFileDialog
from .toniebox_dialogs import info_banner
from .tonies_filter import visible_tonies

PATH_ROLE = Qt.ItemDataRole.UserRole


def _join(folder: str, name: str) -> str:
    return folder.rstrip("/") + "/" + name


def _format_size(size: int) -> str:
    return f"{size / 1024:.1f} KB" if size < 1_048_576 else f"{size / 1_048_576:.1f} MB"


def _icon_button(name: str, tooltip: str, slot, parent: QWidget) -> QToolButton:
    button = QToolButton(parent)
    button.setIcon(icon(name))
    button.setToolTip(tooltip)
    button.clicked.connect(lambda _checked=False: slot())
    return button


# ---------------------------------------------------------------------------
# Hilfsdialoge
# ---------------------------------------------------------------------------


class FolderPickerDialog(QDialog):
    """Ordner der Bibliothek wählen, mit „Neuen Ordner anlegen“."""

    def __init__(self, client: TeddyCloudClient, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._client = client
        self.setWindowTitle(title)
        self.resize(460, 420)
        self.tree = LibraryDirectoryTree(client, self)
        self.tree.reload()
        new_dir = QPushButton(icon("folder"), "Neuen Ordner anlegen", self)
        new_dir.clicked.connect(self._create_folder)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.tree, 1)
        layout.addWidget(new_dir, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(buttons)

    def selected_path(self) -> str:
        return self.tree.selected_path()

    def _create_folder(self) -> None:
        parent = self.tree.currentItem()
        if parent is None:
            return
        name, ok = QInputDialog.getText(self, "Neuen Ordner anlegen", "Gib den Ordnernamen an")
        name = name.strip()
        if not ok or not name:
            return
        if not is_valid_name(name):
            QMessageBox.warning(
                self, "Ungültiger Ordnername", f"Deine Eingabe enthält ungültige Zeichen, wie {INVALID_NAME_CHARS_DISPLAY}"
            )
            return
        self._client.create_library_directory(
            _join(parent.data(0, PATH_ROLE), name),
            lambda: self.tree.add_directory(parent, name),
            lambda message: QMessageBox.warning(self, "Verzeichniserstellung fehlgeschlagen!", message),
        )


class JsonViewerDialog(QDialog):
    def __init__(self, title: str, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(640, 520)
        view = QPlainTextEdit(text, self)
        view.setReadOnly(True)
        view.setStyleSheet("font-family: monospace;")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(view)
        layout.addWidget(buttons)


class AssignTonieDialog(QDialog):
    """Eine Bibliotheksdatei (z. B. eine TAP) einem Tonie als Quelle zuweisen, wie AssignTonieModal."""

    def __init__(self, client: TeddyCloudClient, overlay: str, source: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._client = client
        self._overlay = overlay
        self._source = source
        self._cards: list[TonieCard] = []
        self.setWindowTitle("Einem Tonie zuweisen")
        self.resize(520, 520)
        self.info = QLabel(f"Quelle: <b>{source}</b>", self)
        self.info.setWordWrap(True)
        self.search = QLineEdit(self)
        self.search.setPlaceholderText("Tonie suchen (Serie, Episode, UID) …")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._fill)
        self.list = QListWidget(self)
        self.list.currentItemChanged.connect(lambda *_: self._update_ok())
        self.list.itemDoubleClicked.connect(lambda _item: self._assign())
        self.status = QLabel("Lade Tonies …", self)
        self.status.setWordWrap(True)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Zuweisen")
        self.buttons.accepted.connect(self._assign)
        self.buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.info)
        layout.addWidget(self.search)
        layout.addWidget(self.list, 1)
        layout.addWidget(self.status)
        layout.addWidget(self.buttons)
        self._update_ok()
        client.fetch_tags(overlay, self._on_tags, self.status.setText)

    def _on_tags(self, cards: list[TonieCard]) -> None:
        self._cards = sort_cards(visible_tonies(cards))
        self.status.clear()
        self._fill()

    def _fill(self) -> None:
        needle = self.search.text().strip().lower()
        self.list.clear()
        for card in self._cards:
            text = f"{card.tonie_info.title or 'Tonie/Tag'}   ({card.uid})"
            if needle and needle not in text.lower():
                continue
            item = QListWidgetItem(icon("audio"), text)
            item.setData(PATH_ROLE, card)
            item.setToolTip(f"Aktuelle Quelle: {card.source or '–'}")
            self.list.addItem(item)
        self._update_ok()

    def _update_ok(self) -> None:
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(self.list.currentItem() is not None)

    def _assign(self) -> None:
        item = self.list.currentItem()
        if item is None:
            return
        card: TonieCard = item.data(PATH_ROLE)
        # Wie useAssignSourceToTonie: Quelle setzen, Cloud sperren, Live nur für Streams
        steps: list[tuple[str, str | bool]] = [("source", self._source)]
        if not card.nocloud:
            steps.append(("nocloud", True))
        should_be_live = self._source.startswith("http")
        if should_be_live != card.live:
            steps.append(("live", should_be_live))
        self.buttons.setEnabled(False)
        self.status.setText("Weise zu …")

        def next_step(remaining: list) -> None:
            if not remaining:
                self.assigned_to = card
                self.accept()
                return
            key, value = remaining[0]
            self._client.set_content(card.ruid, self._overlay, key, value, lambda: next_step(remaining[1:]), failed)

        def failed(message: str) -> None:
            self.buttons.setEnabled(True)
            self.status.setText(f"Zuweisen fehlgeschlagen: {message}")

        next_step(steps)


# ---------------------------------------------------------------------------
# TAP-Editor
# ---------------------------------------------------------------------------


class _TapFileRow(QWidget):
    """Eine Datei der Playlist: Nummer, Dateipfad (mit Auswahl), Beschreibung, Verschieben, Entfernen."""

    def __init__(self, editor: "TapEditorDialog", file: TapFile) -> None:
        super().__init__(editor)
        self._editor = editor
        self.number = QLabel(self)
        self.number.setMinimumWidth(28)
        self.number.setStyleSheet("font-weight: bold;")
        self.path_edit = QLineEdit(file.filepath, self)
        self.path_edit.setPlaceholderText("Dateipfad, z. B. lib://Musik/lied.mp3")
        self.path_edit.setToolTip("Legt den Pfad zur Audioquelle fest (muss mit ffmpeg kompatibel sein)")
        self.name_edit = QLineEdit(file.name, self)
        self.name_edit.setPlaceholderText("Beschreibung")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.number)
        layout.addWidget(_icon_button("clear", "Dateipfad leeren", self.path_edit.clear, self))
        layout.addWidget(self.path_edit, 3)
        layout.addWidget(_icon_button("folder", "Datei aus der Bibliothek wählen", self._browse, self))
        layout.addWidget(self.name_edit, 2)
        layout.addWidget(_icon_button("up", "Nach oben", lambda: editor.move_row(self, -1), self))
        layout.addWidget(_icon_button("down", "Nach unten", lambda: editor.move_row(self, 1), self))
        layout.addWidget(_icon_button("delete", "Datei entfernen", lambda: editor.remove_row(self), self))

    def value(self) -> TapFile:
        return TapFile(filepath=self.path_edit.text().strip(), name=self.name_edit.text().strip())

    def _browse(self) -> None:
        dialog = LibraryFileDialog(self._editor.client, self.path_edit.text(), self._editor, extensions=TAP_AUDIO_EXTENSIONS)
        dialog.setWindowTitle("Datei auswählen")
        if dialog.exec() and dialog.selected_entry is not None:
            self.path_edit.setText(dialog.selected_source)
            self.name_edit.setText(dialog.selected_entry.name)


class TapEditorDialog(QDialog):
    """Anlegen bzw. Bearbeiten einer TAP; Felder wie TeddyAudioPlaylistEditorModal."""

    def __init__(
        self, client: TeddyCloudClient, folder: str, tap: TeddyAudioPlaylist | None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.client = client
        self.edit_mode = tap is not None
        tap = tap or TeddyAudioPlaylist()
        self._rows: list[_TapFileRow] = []
        self.setWindowTitle(f"TAP {tap.name}.tap bearbeiten" if self.edit_mode else f"Neue TAP in {folder or '/'} erstellen")
        self.resize(900, 640)

        self.audio_id_edit = QLineEdit(str(tap.audio_id), self)
        self.audio_id_edit.setToolTip(
            "Legt die Audio-ID fest, wenn die Datei zwischengespeichert ist. Setze sie auf 0, um die "
            "zwischengespeicherte Datei neu zu erstellen"
        )
        self.audio_id_edit.setMaximumWidth(160)

        taf_folder, taf_base = split_taf_filepath(tap.filepath) if tap.filepath else (folder or "/", "")
        self._taf_folder = taf_folder
        self.taf_folder_label = QLabel(self)
        change_folder = QPushButton(icon("folder"), "Ordner …", self)
        change_folder.clicked.connect(self._choose_taf_folder)
        self.taf_name_edit = QLineEdit(taf_base, self)
        self.taf_name_edit.setPlaceholderText("filename")
        self.taf_name_edit.setToolTip("Legt einen Pfad für die TAF-Datei fest, die von ffmpeg erstellt wird")
        taf_row = QHBoxLayout()
        taf_row.addWidget(self.taf_folder_label)
        taf_row.addWidget(change_folder)
        taf_row.addWidget(self.taf_name_edit, 1)
        taf_row.addWidget(QLabel(".taf", self))

        self.name_edit = QLineEdit(tap.name, self)
        self.name_edit.setToolTip("Legt den Namen der Wiedergabeliste fest (zugleich der Dateiname der .tap)")
        # Ohne eigenen Namen folgt der TAF-Dateiname dem TAP-Namen
        self.name_edit.textChanged.connect(self._sync_taf_name)
        self._auto_taf_name: str | None = taf_base if (not self.edit_mode or taf_base == tap.name) else None

        form = QFormLayout()
        form.addRow("Audio-ID", self.audio_id_edit)
        form.addRow("Dateipfad Playlist *", taf_row)
        form.addRow("TAP Name *", self.name_edit)

        self.rows_layout = QVBoxLayout()
        self.rows_layout.setSpacing(4)
        rows_container = QWidget(self)
        rows_outer = QVBoxLayout(rows_container)
        rows_outer.setContentsMargins(0, 0, 0, 0)
        rows_outer.addLayout(self.rows_layout)
        rows_outer.addStretch(1)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setWidget(rows_container)
        self.add_button = QPushButton(icon("upload"), "Datei hinzufügen", self)
        self.add_button.clicked.connect(self._add_files)
        self.count_label = QLabel(self)

        self.error_label = QLabel(self)
        self.error_label.setStyleSheet("color: #d4380d")
        self.error_label.setWordWrap(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Speichern" if self.edit_mode else "Anlegen")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        header = QHBoxLayout()
        header.addWidget(QLabel("<b>Dateien</b> (Reihenfolge = Kapitel)", self))
        header.addStretch(1)
        header.addWidget(self.count_label)
        header.addWidget(self.add_button)
        layout.addLayout(header)
        layout.addWidget(scroll, 1)
        layout.addWidget(self.error_label)
        layout.addWidget(buttons)

        for file in tap.files:
            self._add_row(file)
        self._update_rows()
        self._update_taf_folder()

    # ---------- Dateien ----------

    def _add_row(self, file: TapFile) -> None:
        row = _TapFileRow(self, file)
        self._rows.append(row)
        self.rows_layout.addWidget(row)

    def remove_row(self, row: _TapFileRow) -> None:
        self._rows.remove(row)
        row.deleteLater()
        self._update_rows()

    def move_row(self, row: _TapFileRow, direction: int) -> None:
        index = self._rows.index(row)
        target = index + direction
        if 0 <= target < len(self._rows):
            self._rows[index], self._rows[target] = self._rows[target], self._rows[index]
            self.rows_layout.removeWidget(row)
            self.rows_layout.insertWidget(target, row)
            self._update_rows()

    def _update_rows(self) -> None:
        for index, row in enumerate(self._rows, start=1):
            row.number.setText(f"{index}.")
        self.count_label.setText(f"{len(self._rows)} / {MAX_TAP_FILES}")
        self.add_button.setEnabled(len(self._rows) < MAX_TAP_FILES)

    def _add_files(self) -> None:
        free = MAX_TAP_FILES - len(self._rows)
        dialog = LibraryFileDialog(self.client, "", self, extensions=TAP_AUDIO_EXTENSIONS, max_files=free)
        dialog.setWindowTitle(f"Dateien auswählen (höchstens {free})")
        if dialog.exec():
            for source, entry in zip(dialog.selected_sources, dialog.selected_entries, strict=True):
                self._add_row(TapFile(filepath=source, name=entry.name))
            self._update_rows()

    # ---------- Ziel-TAF ----------

    def _update_taf_folder(self) -> None:
        self.taf_folder_label.setText(f"Bibliothek: {self._taf_folder.rstrip('/') or ''}/")

    def _choose_taf_folder(self) -> None:
        dialog = FolderPickerDialog(self.client, "Ordner für die TAF-Datei wählen", self)
        if dialog.exec():
            self._taf_folder = dialog.selected_path()
            self._update_taf_folder()

    def _sync_taf_name(self, name: str) -> None:
        """Der TAF-Dateiname folgt dem TAP-Namen, bis er von Hand geändert wird."""
        current = self.taf_name_edit.text()
        if current == "" or current == self._auto_taf_name:
            self._auto_taf_name = name.strip()
            self.taf_name_edit.setText(self._auto_taf_name)

    # ---------- Ergebnis ----------

    def playlist(self) -> TeddyAudioPlaylist:
        try:
            audio_id = int(self.audio_id_edit.text().strip() or 0)
        except ValueError:
            audio_id = -1
        return TeddyAudioPlaylist(
            name=self.name_edit.text().strip(),
            audio_id=audio_id,
            filepath=build_taf_filepath(self._taf_folder, self.taf_name_edit.text()) if self.taf_name_edit.text().strip() else "",
            files=[row.value() for row in self._rows],
        )

    def _accept(self) -> None:
        tap = self.playlist()
        errors = validate_tap(tap, self.taf_name_edit.text())
        if tap.audio_id < 0:
            errors.insert(0, "Die Audio-ID muss eine Zahl ≥ 0 sein")
        if not is_valid_name(self.taf_name_edit.text()):
            errors.insert(0, f"Der TAF-Dateiname enthält ungültige Zeichen, wie {INVALID_NAME_CHARS_DISPLAY}")
        if errors:
            self.error_label.setText("\n".join(errors))
            return
        self.result_playlist = tap
        self.accept()


# ---------------------------------------------------------------------------
# Seite
# ---------------------------------------------------------------------------


class TapPage(QWidget):
    statusMessage = pyqtSignal(str)

    def __init__(self, client: TeddyCloudClient, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._client = client
        self._settings = settings
        self._folder = "/"
        self._converter = None  # laufende TAP-Umwandlung

        new_button = QPushButton(icon("edit"), "Neue TAP erstellen", self)
        new_button.clicked.connect(self.create_tap)
        new_dir_button = QPushButton(icon("folder"), "Neuen Ordner anlegen", self)
        new_dir_button.clicked.connect(self._create_folder)
        refresh_button = QPushButton(icon("refresh"), "Aktualisieren", self)
        refresh_button.clicked.connect(self.load)
        header = QHBoxLayout()
        header.addWidget(QLabel("<h2>TeddyAudio Playlists</h2>", self))
        header.addStretch(1)
        header.addWidget(new_button)
        header.addWidget(new_dir_button)
        header.addWidget(refresh_button)

        banner = info_banner(
            "<b>Information</b><br>Die TeddyAudio Playlists sind in der TeddyCloud noch in Entwicklung und können "
            "instabil sein. Eine TAP wird einem Tonie als Quelle zugewiesen; beim ersten Abspielen erzeugt die "
            "TeddyCloud daraus die TAF-Datei unter „Dateipfad Playlist“.",
            self,
        )

        up = _icon_button("up", "Übergeordneter Ordner", self._go_up, self)
        self.path_label = QLabel(self)
        self.filter_edit = QLineEdit(self)
        self.filter_edit.setPlaceholderText("Filter …")
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.setMaximumWidth(260)
        self.filter_edit.textChanged.connect(self._apply_filter)
        nav = QHBoxLayout()
        nav.addWidget(up)
        nav.addWidget(self.path_label, 1)
        nav.addWidget(self.filter_edit)

        self.table = QTreeWidget(self)
        self.table.setHeaderLabels(["Name", "Größe", "Datum"])
        self.table.setRootIsDecorated(False)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.itemDoubleClicked.connect(self._on_double_click)
        self.table.currentItemChanged.connect(lambda *_: self._update_actions())
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context_menu)

        # Aktionen für die gewählte TAP (wie die Aktions-Spalte der Weboberfläche)
        self._actions = []
        actions = QHBoxLayout()
        for icon_name, text, slot in (
            ("edit", "Bearbeiten", self.edit_selected),
            ("refresh", "In TAF umwandeln", self.convert_selected),
            ("audio", "Einem Tonie zuweisen", self.assign_selected),
            ("file", "JSON anzeigen", self.show_json_selected),
            ("download", "Herunterladen", self.download_selected),
            ("edit", "Umbenennen", self.rename_selected),
            ("folder", "Verschieben", self.move_selected),
            ("delete", "Löschen", self.delete_selected),
        ):
            button = QPushButton(icon(icon_name), text, self)
            button.clicked.connect(slot)
            actions.addWidget(button)
            self._actions.append((text, slot, button))
        actions.addStretch(1)

        self.empty_label = QLabel(self)
        self.empty_label.setStyleSheet("color: gray")

        layout = QVBoxLayout(self)
        layout.addLayout(header)
        layout.addWidget(banner)
        layout.addLayout(nav)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.empty_label)
        layout.addLayout(actions)
        self._update_actions()

    # ---------- Laden und Navigation ----------

    def load(self) -> None:
        self.path_label.setText(f"Bibliothek: {self._folder}")
        self.table.clear()
        self.empty_label.setText("Wird geladen …")
        self._client.fetch_library(self._folder, self._show_entries, self._show_error)

    def _show_entries(self, entries: list[LibraryEntry]) -> None:
        self.table.clear()
        taps = 0
        for entry in entries:
            # Wie FileBrowser mit filetypeFilter=[".tap"]: Ordner und TAP-Dateien
            if not entry.is_dir and not entry.name.lower().endswith(TAP_EXTENSION):
                continue
            item = QTreeWidgetItem(
                [
                    entry.name,
                    "" if entry.is_dir else _format_size(entry.size),
                    f"{datetime.fromtimestamp(entry.date):%d.%m.%Y %H:%M}" if entry.date else "",
                ]
            )
            item.setIcon(0, icon("folder" if entry.is_dir else "audio"))
            item.setData(0, PATH_ROLE, entry)
            self.table.addTopLevelItem(item)
            taps += 0 if entry.is_dir else 1
        self.empty_label.setText("" if taps else "Keine TAP-Dateien in diesem Ordner.")
        self._apply_filter()
        self._update_actions()

    def _show_error(self, message: str) -> None:
        self.empty_label.setText(message)

    def _apply_filter(self) -> None:
        needle = self.filter_edit.text().strip().lower()
        for i in range(self.table.topLevelItemCount()):
            item = self.table.topLevelItem(i)
            item.setHidden(bool(needle) and needle not in item.text(0).lower())

    def _on_double_click(self, item: QTreeWidgetItem) -> None:
        entry: LibraryEntry = item.data(0, PATH_ROLE)
        if entry.is_dir:
            self._folder = _join(self._folder, entry.name)
            self.load()
        else:
            self.show_json_selected()

    def _go_up(self) -> None:
        if self._folder != "/":
            self._folder = self._folder.rstrip("/").rsplit("/", 1)[0] or "/"
            self.load()

    def _create_folder(self) -> None:
        name, ok = QInputDialog.getText(
            self, "Neuen Ordner anlegen", f"Gib den Ordnernamen an\n(übergeordnete(r) Ordner: {self._folder})"
        )
        name = name.strip()
        if not ok or not name:
            return
        if not is_valid_name(name):
            self._warn("Ungültiger Ordnername", f"Deine Eingabe enthält ungültige Zeichen, wie {INVALID_NAME_CHARS_DISPLAY}")
            return
        self._client.create_library_directory(
            _join(self._folder, name), self.load, lambda m: self._warn("Verzeichniserstellung fehlgeschlagen!", m)
        )

    # ---------- Auswahl ----------

    def _selected(self) -> LibraryEntry | None:
        item = self.table.currentItem()
        entry = item.data(0, PATH_ROLE) if item is not None else None
        return entry if entry is not None and not entry.is_dir else None

    def _selected_path(self) -> str:
        entry = self._selected()
        return _join(self._folder, entry.name) if entry else ""

    def _update_actions(self) -> None:
        has_tap = self._selected() is not None
        for _text, _slot, button in self._actions:
            button.setEnabled(has_tap)

    def _context_menu(self, position) -> None:
        if self._selected() is None:
            return
        menu = QMenu(self)
        for text, slot, _button in self._actions:
            menu.addAction(text, slot)
        menu.exec(self.table.viewport().mapToGlobal(position))

    # ---------- Anlegen und Bearbeiten ----------

    def create_tap(self) -> None:
        dialog = TapEditorDialog(self._client, self._folder, None, self)
        if dialog.exec():
            self._save(dialog.result_playlist, self._folder, None)

    def edit_selected(self) -> None:
        entry, path = self._selected(), self._selected_path()
        if entry is None:
            return

        def loaded(data: bytes) -> None:
            try:
                tap = parse_tap(data)
            except ValueError as exc:
                self._warn("TAP kann nicht geöffnet werden", f"{entry.name}: {exc}")
                return
            dialog = TapEditorDialog(self._client, self._folder, tap, self)
            if dialog.exec():
                self._save(dialog.result_playlist, self._folder, entry.name)

        self._client.fetch_library_file(path, loaded, lambda m: self._warn("TAP kann nicht geladen werden", m))

    def _save(self, tap: TeddyAudioPlaylist, folder: str, old_file_name: str | None) -> None:
        """Wie useTAPEditor: die JSON als <Name>.tap in den aktuellen Ordner hochladen."""
        file_name = tap.file_name

        def saved() -> None:
            self.statusMessage.emit(f'TAP "{file_name}" wurde erfolgreich in "{folder}" gespeichert!')
            # Abweichend von der Weboberfläche: bei geändertem Namen die alte Datei entfernen statt sie liegen zu lassen
            if old_file_name and old_file_name != file_name:
                self._client.delete_library_file(
                    _join(folder, old_file_name),
                    self.load,
                    lambda m: (self._warn("Alte TAP-Datei nicht gelöscht", m), self.load()),
                )
            else:
                self.load()

        def failed(message: str) -> None:
            self._warn(
                "TAP-Speichern fehlgeschlagen!",
                f'Speichern der TAP-Datei "{file_name}" in "{folder}" ist fehlgeschlagen: {message}',
            )

        if old_file_name != file_name and any(
            self.table.topLevelItem(i).text(0) == file_name for i in range(self.table.topLevelItemCount())
        ):
            answer = QMessageBox.question(
                self, "TAP überschreiben?", f'Es gibt bereits "{file_name}" in diesem Ordner. Überschreiben?'
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._client.upload_library_file(tap.to_bytes(), file_name, folder, saved, failed)

    # ---------- weitere Aktionen ----------

    def assign_selected(self) -> None:
        entry = self._selected()
        if entry is None:
            return
        source = library_source(self._folder, entry.name)
        dialog = AssignTonieDialog(self._client, self._settings.overlay, source, self)
        if dialog.exec():
            card = dialog.assigned_to
            self.statusMessage.emit(f'"{entry.name}" wurde dem Tonie "{card.tonie_info.title or card.uid}" zugewiesen.')

    def convert_selected(self) -> None:
        """TAP in der GUI in eine TAF umwandeln (statt per FFmpeg auf der TeddyCloud)."""
        entry, path, folder = self._selected(), self._selected_path(), self._folder
        if entry is None:
            return
        if getattr(self, "_converter", None) is not None:
            self._warn("Umwandlung läuft", "Es läuft bereits eine Umwandlung. Bitte warte, bis sie fertig ist.")
            return
        self._converter = True  # Platzhalter, bis die TAP geladen ist

        def loaded(data: bytes) -> None:
            self._converter = None
            try:
                tap = parse_tap(data)
            except ValueError as exc:
                self._warn("TAP kann nicht geöffnet werden", f"{entry.name}: {exc}")
                return
            problems = conversion_problems(tap)
            if problems:
                self._warn("Umwandeln nicht möglich", "\n".join(problems))
                return
            self._run_conversion(tap, folder, entry.name)

        def load_failed(message: str) -> None:
            self._converter = None
            self._warn("TAP kann nicht geladen werden", message)

        self._client.fetch_library_file(path, loaded, load_failed)

    def _run_conversion(self, tap: TeddyAudioPlaylist, folder: str, file_name: str) -> None:
        converter = TapConverter(self._client, tap, folder, file_name, self)
        # Nicht modal: ein modaler QProgressDialog ruft in setValue() processEvents() auf. Aus den
        # Fortschritts-Signalen einer laufenden Netzwerkanfrage heraus bringt das den gestreamten
        # Upload aus dem Tritt (er bricht ab und hängt). Stattdessen wird die Seite gesperrt.
        dialog = QProgressDialog(f"Wandle {file_name} um …", "Abbrechen", 0, 1000, self.window())
        dialog.setWindowTitle(f"{file_name} in TAF umwandeln")
        dialog.setWindowModality(Qt.WindowModality.NonModal)
        dialog.setMinimumDuration(0)
        dialog.setMinimumWidth(480)
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        self._converter = converter  # Referenz halten, solange die Umwandlung läuft
        state = {"done": False}  # close() des Fortschrittsdialogs löst auch "canceled" aus
        self.setEnabled(False)

        def end() -> None:
            state["done"] = True
            dialog.close()
            dialog.deleteLater()
            self._converter = None
            self.setEnabled(True)

        def progress(text: str, value: int) -> None:
            dialog.setLabelText(f"{text}\nZiel: {tap.filepath}")
            if value < 0:
                dialog.setRange(0, 0)
            else:
                dialog.setRange(0, 1000)
                dialog.setValue(value)

        def finished(_tap: TeddyAudioPlaylist, message: str) -> None:
            end()
            self.statusMessage.emit(message.replace("\n", " "))
            QMessageBox.information(self, "Umwandlung abgeschlossen", message)
            self.load()

        def failed(message: str) -> None:
            end()
            self._warn("Umwandlung fehlgeschlagen", message)

        def cancelled() -> None:
            if state["done"]:
                return
            converter.cancel()
            end()
            self.statusMessage.emit(f"Umwandlung von {file_name} abgebrochen.")

        converter.progress.connect(progress)
        converter.finished.connect(finished)
        converter.failed.connect(failed)
        dialog.canceled.connect(cancelled)
        dialog.show()
        converter.start()

    def show_json_selected(self) -> None:
        entry, path = self._selected(), self._selected_path()
        if entry is None:
            return

        def loaded(data: bytes) -> None:
            text = data.decode("utf-8", errors="replace")
            try:
                text = json.dumps(json.loads(text), indent=2, ensure_ascii=False)
            except json.JSONDecodeError:
                pass
            JsonViewerDialog(entry.name, text, self).exec()

        self._client.fetch_library_file(path, loaded, lambda m: self._warn("Datei kann nicht geladen werden", m))

    def download_selected(self) -> None:
        entry, path = self._selected(), self._selected_path()
        if entry is None:
            return
        target, _ = QFileDialog.getSaveFileName(self, "TAP speichern", entry.name, "TeddyAudio Playlist (*.tap)")
        if not target:
            return

        def loaded(data: bytes) -> None:
            with open(target, "wb") as file:
                file.write(data)
            self.statusMessage.emit(f"{entry.name} gespeichert unter {target}")

        self._client.fetch_library_file(path, loaded, lambda m: self._warn("Download fehlgeschlagen", m))

    def rename_selected(self) -> None:
        entry, path = self._selected(), self._selected_path()
        if entry is None:
            return
        name, ok = QInputDialog.getText(self, "Umbenennen", "Neuer Dateiname", text=entry.name)
        name = name.strip()
        if not ok or not name or name == entry.name:
            return
        if not is_valid_name(name):
            self._warn("Ungültiger Dateiname", f"Deine Eingabe enthält ungültige Zeichen, wie {INVALID_NAME_CHARS_DISPLAY}")
            return
        if not name.lower().endswith(TAP_EXTENSION):
            name += TAP_EXTENSION
        self._client.move_library_file(
            path, _join(self._folder, name), self.load, lambda m: self._warn("Umbenennen fehlgeschlagen", m)
        )

    def move_selected(self) -> None:
        entry, path = self._selected(), self._selected_path()
        if entry is None:
            return
        dialog = FolderPickerDialog(self._client, f'"{entry.name}" verschieben nach …', self)
        if not dialog.exec():
            return
        target_folder = dialog.selected_path()
        if target_folder.rstrip("/") == self._folder.rstrip("/"):
            return
        self._client.move_library_file(
            path, _join(target_folder, entry.name), self.load, lambda m: self._warn("Verschieben fehlgeschlagen", m)
        )

    def delete_selected(self) -> None:
        entry, path = self._selected(), self._selected_path()
        if entry is None:
            return
        answer = QMessageBox.question(self, "Löschen", f'Möchtest du "{entry.name}" wirklich löschen?')
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._client.delete_library_file(path, self.load, lambda m: self._warn("Löschen fehlgeschlagen", m))

    def _warn(self, title: str, message: str) -> None:
        self.statusMessage.emit(message)
        QMessageBox.warning(self, title, message)
