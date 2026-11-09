"""Audio Encoder: Audiodateien zu einer TAF-Datei in der Bibliothek kodieren (nach /web/tonies/encoder).

Wie bei der Einstellung "Encoding auf dem Server" der Weboberfläche werden die Dateien lokal zu
48 kHz Stereo 16 Bit PCM dekodiert (hier mit QAudioDecoder/FFmpeg statt der Web Audio API) und an
/api/pcmUpload geschickt. Die TeddyCloud kodiert daraus die TAF-Datei, jede Datei wird ein Kapitel.
"""

import logging
import os
import re
import shutil
import tempfile
import time
from pathlib import Path

from PyQt6.QtCore import QObject, QSize, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QImage, QKeySequence, QPainter, QPaintEvent, QShortcut
from PyQt6.QtMultimedia import QAudioDecoder, QAudioFormat
from PyQt6.QtNetwork import QNetworkReply
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .custom_model_dialogs import custom_img_path
from .custom_models import CustomEntry
from .encoder_custom import COVER_FOLDER, CustomTonieOptions, cover_file_name, find_taf_hash
from .icons import icon
from .images import ImageCache
from .teddycloud import LibraryEntry, TeddyCloudClient, natural_key

log = logging.getLogger("teddycloud_desktop")

MAX_FILES = 99
SUPPORTED_EXTENSIONS = (
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
# Wie fieldInputValidator.ts der Weboberfläche (Windows-Regeln für Datei- und Ordnernamen)
INVALID_NAME_CHARS = re.compile(r'[<>:"/\\|?*]')
INVALID_NAME_CHARS_DISPLAY = '< > : " / \\ | ? *'
TAF_HEADER_SIZE = 4096
PCM_SAMPLE_RATE = 48000
# Upload abbrechen, wenn so lange keine Daten mehr abfließen (das Kodieren danach hat kein Zeitlimit)
UPLOAD_STALL_TIMEOUT_MS = 60_000
# Name eines neu angelegten Ordners, der nach dem Nachladen ausgewählt werden soll
PENDING_SELECTION_ROLE = Qt.ItemDataRole.UserRole + 2


def is_valid_name(name: str) -> bool:
    return not INVALID_NAME_CHARS.search(name)


def is_supported(path: str) -> bool:
    return path.lower().endswith(SUPPORTED_EXTENSIONS)


_last_audio_id = 0


def new_audio_id() -> int:
    """Wie die Weboberfläche: aktuelle Unix-Zeit minus 0x50000000.

    Anders als dort nie zweimal dieselbe ID: Bei zwei Kodierungen in derselben Sekunde bekommt die
    zweite die nächsthöhere Zahl (die Zeitbasis holt das nach wenigen Sekunden wieder ein).
    """
    global _last_audio_id
    _last_audio_id = max(int(time.time()) - 0x50000000, _last_audio_id + 1)
    return _last_audio_id


class PcmDecoder(QObject):
    """Dekodiert eine Audiodatei in eine Datei mit 48 kHz Stereo 16 Bit PCM (interleaved, little endian)."""

    progress = pyqtSignal(float)  # 0.0 … 1.0
    finished = pyqtSignal(str)  # Pfad der PCM-Datei
    failed = pyqtSignal(str)

    def __init__(self, source: str, target: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._source = source
        self._target = open(target, "wb")
        self._target_path = target
        self._done = False

        audio_format = QAudioFormat()
        audio_format.setSampleRate(PCM_SAMPLE_RATE)
        audio_format.setChannelCount(2)
        audio_format.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        self._decoder = QAudioDecoder(self)
        self._decoder.setAudioFormat(audio_format)
        self._decoder.bufferReady.connect(self._on_buffer)
        self._decoder.finished.connect(self._on_finished)
        self._decoder.error.connect(self._on_error)

        self._ogg_copy = ""
        if source.lower().endswith(".taf"):
            # TAF = 4096 Byte Protobuf-Header + Ogg/Opus; FFmpeg bekommt nur den Ogg-Teil als eigene Datei
            handle, self._ogg_copy = tempfile.mkstemp(prefix="teddycloud_desktop_", suffix=".ogg")
            with open(source, "rb") as taf, os.fdopen(handle, "wb") as ogg:
                taf.seek(TAF_HEADER_SIZE)
                shutil.copyfileobj(taf, ogg)
            self._decoder.setSource(QUrl.fromLocalFile(self._ogg_copy))
        else:
            self._decoder.setSource(QUrl.fromLocalFile(source))

    def start(self) -> None:
        self._decoder.start()

    def stop(self) -> None:
        self._done = True
        self._decoder.stop()
        self._close()

    def _close(self) -> None:
        self._target.close()
        if self._ogg_copy:
            try:
                os.remove(self._ogg_copy)
            except OSError:
                pass
            self._ogg_copy = ""

    def _on_buffer(self) -> None:
        buffer = self._decoder.read()
        if buffer.isValid() and not self._done:
            self._target.write(buffer.data().asstring(buffer.byteCount()))
            duration = self._decoder.duration()
            if duration > 0:
                self.progress.emit(min(self._decoder.position() / duration, 1.0))

    def _on_finished(self) -> None:
        if self._done:
            return
        self._done = True
        self._close()
        if os.path.getsize(self._target_path) == 0:
            self.failed.emit(f"{Path(self._source).name}: keine Audiodaten gefunden")
        else:
            self.finished.emit(self._target_path)

    def _on_error(self, _error: QAudioDecoder.Error) -> None:
        if self._done:
            return
        self._done = True
        self._close()
        self.failed.emit(f"{Path(self._source).name}: {self._decoder.errorString()}")


class AudioFileList(QListWidget):
    """Liste der zu kodierenden Dateien: Reihenfolge per Drag & Drop, Dateien von außen hineinziehen."""

    filesDropped = pyqtSignal(list)

    PLACEHOLDER = (
        f"Klicke auf „Datei(en) auswählen“ oder ziehe bis zu {MAX_FILES} Audiodateien, die du in eine "
        "TAF-Datei konvertieren möchtest, in diesen Bereich.\n\nZiehe die Audiodateien hier her!"
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setAcceptDrops(True)
        self.setIconSize(QSize(20, 20))
        self.setMinimumHeight(180)

    def paths(self) -> list[str]:
        return [self.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.count())]

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        if event.mimeData().hasUrls():
            paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
            self.filesDropped.emit(paths)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        if self.count() == 0:
            painter = QPainter(self.viewport())
            painter.setPen(self.palette().placeholderText().color())
            painter.drawText(
                self.viewport().rect().adjusted(24, 24, -24, -24),
                Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                self.PLACEHOLDER,
            )
            painter.end()


class LibraryDirectoryTree(QTreeWidget):
    """Ordnerbaum der TeddyCloud-Bibliothek; Unterordner werden beim Aufklappen geladen."""

    def __init__(self, client: TeddyCloudClient, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._client = client
        self.setHeaderHidden(True)
        self.setMinimumHeight(150)
        self.itemExpanded.connect(self._load_children)

    def reload(self) -> None:
        self.clear()
        root = self._add_item(None, "Bibliothek", "/")
        self.setCurrentItem(root)
        root.setExpanded(True)

    def selected_path(self) -> str:
        item = self.currentItem()
        return item.data(0, Qt.ItemDataRole.UserRole) if item is not None else "/"

    def _add_item(self, parent: QTreeWidgetItem | None, name: str, path: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem([name])
        item.setIcon(0, icon("folder"))
        item.setData(0, Qt.ItemDataRole.UserRole, path)
        item.setData(0, Qt.ItemDataRole.UserRole + 1, False)  # Kinder schon geladen?
        # Platzhalter, damit der Pfeil zum Aufklappen erscheint
        item.addChild(QTreeWidgetItem(["…"]))
        if parent is None:
            self.addTopLevelItem(item)
        else:
            parent.addChild(item)
        return item

    def _load_children(self, item: QTreeWidgetItem) -> None:
        if item.data(0, Qt.ItemDataRole.UserRole + 1):
            return
        item.setData(0, Qt.ItemDataRole.UserRole + 1, True)
        path = item.data(0, Qt.ItemDataRole.UserRole)

        def show(entries: list[LibraryEntry]) -> None:
            item.takeChildren()
            select = item.data(0, PENDING_SELECTION_ROLE)
            item.setData(0, PENDING_SELECTION_ROLE, None)
            for entry in entries:
                if entry.is_dir:
                    child = self._add_item(item, entry.name, path.rstrip("/") + "/" + entry.name)
                    if entry.name == select:
                        self.setCurrentItem(child)

        def failed(message: str) -> None:
            item.takeChildren()
            item.setData(0, Qt.ItemDataRole.UserRole + 1, False)
            item.setToolTip(0, message)

        self._client.fetch_library(path, show, failed)

    def add_directory(self, parent: QTreeWidgetItem, name: str) -> None:
        """Neu angelegten Ordner anzeigen und auswählen."""
        if not parent.data(0, Qt.ItemDataRole.UserRole + 1):
            # Inhalt noch nicht geladen: beim Laden (durch das Aufklappen) wird der Ordner ausgewählt
            parent.setData(0, PENDING_SELECTION_ROLE, name)
            parent.setExpanded(True)
            return
        path = parent.data(0, Qt.ItemDataRole.UserRole).rstrip("/") + "/" + name
        child = self._add_item(parent, name, path)
        child.takeChildren()
        child.setData(0, Qt.ItemDataRole.UserRole + 1, True)
        parent.setExpanded(True)
        self.setCurrentItem(child)


class EncoderPage(QWidget):
    statusMessage = pyqtSignal(str)

    def __init__(self, client: TeddyCloudClient, images: ImageCache, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._client = client
        self._busy = False
        self._audio_id = 0
        self._custom_draft: CustomEntry | None = None
        self._custom_cover: QImage | None = None
        self._decoder: PcmDecoder | None = None
        self._reply: QNetworkReply | None = None
        self._pcm_files: list[str] = []
        self._last_sent = 0
        self._stall_message = ""
        self._stall_timer = QTimer(self, singleShot=True, interval=UPLOAD_STALL_TIMEOUT_MS)
        self._stall_timer.timeout.connect(self._on_upload_stalled)

        # Dateiliste
        self.file_list = AudioFileList(self)
        self.file_list.filesDropped.connect(self.add_files)
        self.file_list.model().rowsInserted.connect(self._update_state)
        self.file_list.model().rowsRemoved.connect(self._update_state)
        delete_shortcut = QShortcut(QKeySequence.StandardKey.Delete, self.file_list, self.remove_selected)
        delete_shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)

        self.add_button = QPushButton(icon("upload"), "Datei(en) auswählen", self)
        self.add_button.clicked.connect(self._choose_files)
        self.sort_button = QPushButton("Alphabetisch sortieren (lexikografisch)", self)
        self.sort_button.clicked.connect(self.sort_literal)
        self.sort_menu_button = QToolButton(self)
        self.sort_menu_button.setText("…")
        self.sort_menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        sort_menu = QMenu(self.sort_menu_button)
        sort_menu.addAction("Alphabetisch sortieren (lexikografisch)", self.sort_literal)
        sort_menu.addAction("Alphabetisch sortieren (mit Zahlenreihenfolge)", self.sort_natural)
        self.sort_menu_button.setMenu(sort_menu)
        self.remove_button = QPushButton(icon("delete"), "Datei entfernen", self)
        self.remove_button.clicked.connect(self.remove_selected)
        self.clear_button = QPushButton("Liste leeren", self)
        self.clear_button.clicked.connect(self.file_list.clear)
        list_buttons = QHBoxLayout()
        list_buttons.addWidget(self.add_button)
        list_buttons.addWidget(self.sort_button)
        list_buttons.addWidget(self.sort_menu_button)
        list_buttons.addWidget(self.remove_button)
        list_buttons.addWidget(self.clear_button)
        list_buttons.addStretch(1)

        # Ziel
        self.directory_tree = LibraryDirectoryTree(client, self)
        self.directory_tree.currentItemChanged.connect(self._update_state)
        self.new_dir_button = QPushButton(icon("folder"), "Neuen Ordner anlegen", self)
        self.new_dir_button.clicked.connect(self.create_directory)
        self.target_label = QLabel(self)
        self.name_edit = QLineEdit(self)
        self.name_edit.setPlaceholderText("Dateiname")
        self.name_edit.textChanged.connect(self._update_state)
        self.name_error = QLabel(f"Deine Eingabe enthält ungültige Zeichen, wie {INVALID_NAME_CHARS_DISPLAY}", self)
        self.name_error.setStyleSheet("color: #d4380d")
        self.name_error.setVisible(False)
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("<b>Datei speichern unter</b>", self))
        name_row.addWidget(self.target_label, 1)
        name_row.addWidget(self.name_edit, 1)
        name_row.addWidget(QLabel(".taf", self))
        dir_header = QHBoxLayout()
        dir_header.addWidget(QLabel("Zielordner auswählen:", self))
        dir_header.addStretch(1)
        dir_header.addWidget(self.new_dir_button)

        # Optional: Custom-Tonie für die neue TAF-Datei anlegen
        self.custom_options = CustomTonieOptions(client, images, self)
        self.custom_options.changed.connect(self._update_state)
        self.name_edit.textChanged.connect(self.custom_options.set_taf_name)
        for signal in (self.file_list.model().rowsInserted, self.file_list.model().rowsRemoved, self.file_list.model().rowsMoved):
            signal.connect(lambda *_args: self.custom_options.set_files(self.file_list.paths()))

        # Ausführen
        self.progress = QProgressBar(self)
        self.progress.setVisible(False)
        self.status_label = QLabel(self)
        self.status_label.setWordWrap(True)
        self.cancel_button = QPushButton("Abbrechen", self)
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self.cancel)
        self.encode_button = QPushButton("Konvertieren", self)
        self.encode_button.setDefault(True)
        self.encode_button.clicked.connect(self.encode)
        run_row = QHBoxLayout()
        run_row.addWidget(QLabel("<span style='color:gray'>Encoding auf dem Server</span>", self))
        run_row.addStretch(1)
        run_row.addWidget(self.progress, 3)
        run_row.addWidget(self.cancel_button)
        run_row.addWidget(self.encode_button)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Audio Encoder</h2>", self))
        layout.addWidget(self.file_list, 2)
        layout.addLayout(list_buttons)
        layout.addSpacing(8)
        layout.addLayout(dir_header)
        layout.addWidget(self.directory_tree, 1)
        layout.addLayout(name_row)
        layout.addWidget(self.name_error, 0, Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.custom_options)
        layout.addLayout(run_row)
        layout.addWidget(self.status_label)
        self._update_state()

    def load(self) -> None:
        """Ordnerbaum der Bibliothek (neu) laden."""
        if not self._busy:
            self.directory_tree.reload()
            self.custom_options.load()

    # ---------- Dateiliste ----------

    def _choose_files(self) -> None:
        patterns = " ".join(f"*{ext}" for ext in SUPPORTED_EXTENSIONS)
        paths, _ = QFileDialog.getOpenFileNames(self, "Audiodateien auswählen", "", f"Audiodateien ({patterns})")
        if paths:
            self.add_files(paths)

    def add_files(self, paths: list[str]) -> None:
        if self._busy:
            return
        for path in paths:
            if os.path.isdir(path):
                continue
            if not is_supported(path):
                self._warn(
                    "Nicht unterstützter Dateityp!", f'Die Datei "{Path(path).name}" hat einen nicht unterstützten Dateityp!'
                )
                continue
            if self.file_list.count() >= MAX_FILES:
                self._warn("Zu viele Dateien!", f"Du kannst nur maximal {MAX_FILES} Dateien hinzufügen.")
                break
            item = QListWidgetItem(icon("audio"), Path(path).name)
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(f"{path}\n{os.path.getsize(path) / 1_048_576:.1f} MB")
            self.file_list.addItem(item)
        # Wie in der Weboberfläche: bei genau einer Datei deren Namen vorschlagen
        if self.file_list.count() == 1 and not self.name_edit.text():
            self.name_edit.setText(Path(self.file_list.paths()[0]).stem)

    def remove_selected(self) -> None:
        if self._busy:
            return
        for item in self.file_list.selectedItems():
            self.file_list.takeItem(self.file_list.row(item))

    def _sort(self, key) -> None:
        paths = sorted(self.file_list.paths(), key=lambda p: key(Path(p).name))
        self.file_list.clear()
        self.add_files(paths)

    def sort_literal(self) -> None:
        self._sort(lambda name: name)

    def sort_natural(self) -> None:
        self._sort(natural_key)

    # ---------- Ziel ----------

    def create_directory(self) -> None:
        parent = self.directory_tree.currentItem()
        if parent is None:
            return
        parent_path = parent.data(0, Qt.ItemDataRole.UserRole)
        name, ok = QInputDialog.getText(
            self, "Neuen Ordner anlegen", f"Gib den Ordnernamen an\n(übergeordnete(r) Ordner: {parent_path})"
        )
        name = name.strip()
        if not ok or not name:
            return
        if not is_valid_name(name):
            self._warn("Ungültiger Ordnername", f"Deine Eingabe enthält ungültige Zeichen, wie {INVALID_NAME_CHARS_DISPLAY}")
            return
        full_path = parent_path.rstrip("/") + "/" + name

        def created() -> None:
            self.directory_tree.add_directory(parent, name)
            self.statusMessage.emit(f'Neues Verzeichnis "{full_path}" wurde erstellt!')

        self._client.create_library_directory(
            full_path, created, lambda message: self._warn("Verzeichniserstellung fehlgeschlagen!", message)
        )

    # ---------- Zustand ----------

    def _update_state(self, *_args) -> None:
        name = self.name_edit.text()
        invalid = not is_valid_name(name)
        self.name_error.setVisible(invalid)
        self.name_edit.setStyleSheet("border: 1px solid #d4380d;" if invalid or (self.file_list.count() and not name) else "")
        self.target_label.setText(self.directory_tree.selected_path().rstrip("/") + "/")
        has_files = self.file_list.count() > 0
        for widget in (self.sort_button, self.sort_menu_button, self.remove_button, self.clear_button):
            widget.setEnabled(has_files and not self._busy)
        for widget in (
            self.add_button,
            self.file_list,
            self.directory_tree,
            self.new_dir_button,
            self.name_edit,
            self.custom_options,
        ):
            widget.setEnabled(not self._busy)
        self.encode_button.setEnabled(has_files and bool(name) and not invalid and not self._busy)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.progress.setVisible(busy)
        self.cancel_button.setVisible(busy)
        self._update_state()

    def _status(self, text: str) -> None:
        self.status_label.setStyleSheet("")
        self.status_label.setText(text)
        self.statusMessage.emit(text)

    def _warn(self, title: str, text: str) -> None:
        self.statusMessage.emit(text)
        QMessageBox.warning(self, title, text)

    # ---------- Kodieren ----------

    def encode(self) -> None:
        if not self.encode_button.isEnabled():
            return
        # Den optionalen Custom-Tonie vorher prüfen, damit nach dem Kodieren nichts mehr scheitert
        self._custom_draft = None
        if self.custom_options.isChecked():
            if self.custom_options.validate():
                self._show_error("Bitte zuerst die Angaben zum Custom-Tonie korrigieren.")
                return
            self._custom_draft = self.custom_options.entry()
            self._custom_cover = self.custom_options.cover_image()
        self._sources = self.file_list.paths()
        self._taf_name = self.name_edit.text() + ".taf"
        self._audio_id = new_audio_id()
        self._target_path = self.directory_tree.selected_path()
        self._pcm_files = []
        self._set_busy(True)
        self.progress.setRange(0, 1000)
        self._decode_next()

    def _decode_next(self) -> None:
        index = len(self._pcm_files)
        if index == len(self._sources):
            self._upload()
            return
        source = self._sources[index]
        handle, target = tempfile.mkstemp(prefix="teddycloud_desktop_", suffix=".pcm")
        os.close(handle)
        self._pcm_files.append(target)
        self._status(f"Kodierung {index + 1}/{len(self._sources)}: {Path(source).name}")
        decoder = PcmDecoder(source, target, self)
        decoder.progress.connect(lambda share: self.progress.setValue(int((index + share) / len(self._sources) * 500)))
        decoder.finished.connect(lambda _path: self._decode_next())
        decoder.failed.connect(lambda message: self._fail("Fehler bei der Verarbeitung der Audiodatei: " + message))
        self._decoder = decoder
        decoder.start()

    def _upload(self) -> None:
        self._decoder = None
        self._status(f'Datei "{self._taf_name}" wird hochgeladen …')
        parts = [(Path(source).name, pcm) for source, pcm in zip(self._sources, self._pcm_files, strict=True)]

        total_size = sum(os.path.getsize(pcm) for pcm in self._pcm_files)
        log.info(
            "Lade %d Datei(en) (%.1f MB PCM) als %s nach %s hoch",
            len(parts),
            total_size / 1_048_576,
            self._taf_name,
            self._target_path,
        )
        self._stall_message = ""

        def progress(sent: int, total: int) -> None:
            if total > 0 and sent > self._last_sent:
                self._last_sent = sent
                self._stall_timer.start()  # es fließen noch Daten
                self.progress.setValue(500 + int(sent / total * 500))
                if sent == total:
                    # Hochgeladen; jetzt kodiert die TeddyCloud, das dauert je nach Länge
                    self._stall_timer.stop()
                    self.progress.setRange(0, 0)
                    log.info("Upload abgeschlossen, TeddyCloud kodiert %s", self._taf_name)
                    self._status(f'Verarbeitung läuft … Dateien werden in "{self._taf_name}" kodiert …')

        def failed(message: str) -> None:
            self._fail("Beim Hochladen ist ein Fehler aufgetreten: " + (self._stall_message or message))

        self._last_sent = 0
        self._stall_timer.start()
        self._reply = self._client.upload_pcm(
            parts, self._taf_name, self._target_path, self._audio_id, progress, self._succeeded, failed
        )

    def _on_upload_stalled(self) -> None:
        """Während des Uploads kommen keine Daten mehr an: nicht endlos warten, sondern abbrechen."""
        if self._reply is None:
            return
        seconds = self._stall_timer.interval() // 1000
        self._stall_message = (
            f"Die TeddyCloud nimmt seit {seconds} Sekunden keine Daten mehr an "
            f"({self._last_sent / 1_048_576:.1f} MB übertragen). Ist ein Reverse-Proxy mit Größenlimit "
            "(z. B. nginx client_max_body_size) dazwischen?"
        )
        log.warning(self._stall_message)
        self._reply.abort()

    def _succeeded(self) -> None:
        self._reply = None
        self._cleanup()
        target = self._target_path.rstrip("/") + "/" + self._taf_name
        log.info("TAF-Datei %s erstellt", target)
        done = f'Dateikodierung erfolgreich! Dateien wurden als "{target}" kodiert und zur Library hinzugefügt.'
        if self._custom_draft is None:
            self._finish_success(done)
        else:
            self._create_custom_tonie(done)

    def _finish_success(self, message: str, error: str = "") -> None:
        self._set_busy(False)
        if error:
            self._show_error(f"{message}\n{error}")
            self.statusMessage.emit(error)
        else:
            self._status(message)
        self.file_list.clear()
        self.name_edit.clear()

    def _create_custom_tonie(self, done: str) -> None:
        """Hash der neuen TAF-Datei ermitteln und das Custom-Modell mit Audio-Zuordnung und Tracks anlegen."""
        self.progress.setRange(0, 0)
        self._status(f"{done}\nLege Custom-Tonie an …")
        draft = self._custom_draft
        cover = self._custom_cover
        notes: list[str] = []

        def listed(entries: list[LibraryEntry]) -> None:
            hash_value = find_taf_hash(entries, self._taf_name, self._audio_id)
            if not hash_value:
                failed("Der Hash der neuen TAF-Datei wurde in der Bibliothek nicht gefunden.")
                return
            entry = CustomEntry(**{**draft.__dict__, "audio_ids": [str(self._audio_id)], "hashes": [hash_value]})
            if cover is None:
                upsert(entry)
            else:
                upload_cover(entry)

        def upload_cover(entry: CustomEntry) -> None:
            """Cover nach custom_img hochladen und als Bild eintragen; ohne Erfolg geht es ohne Bild weiter."""
            self._status(f"{done}\nLade Bild aus den Audiodateien hoch …")
            folder = tempfile.mkdtemp(prefix="teddycloud_desktop_cover_")
            path = os.path.join(folder, cover_file_name(entry.model, cover))

            def cleanup() -> None:
                shutil.rmtree(folder, ignore_errors=True)

            def uploaded() -> None:
                cleanup()
                entry.pic = custom_img_path(COVER_FOLDER, os.path.basename(path))
                log.info("Cover für %s hochgeladen: %s", entry.model, entry.pic)
                upsert(entry)

            def upload_failed(message: str) -> None:
                cleanup()
                notes.append(f"Das Bild konnte nicht hochgeladen werden ({message}); der Tonie wurde ohne Bild angelegt.")
                upsert(entry)

            if not cover.save(path, quality=90):
                upload_failed("Bild konnte nicht gespeichert werden")
                return
            self._client.upload_custom_image(path, COVER_FOLDER, uploaded, upload_failed)

        def upsert(entry: CustomEntry) -> None:
            self._client.upsert_custom_model(entry.to_payload(), lambda: created(entry), failed)

        def created(entry: CustomEntry) -> None:
            log.info("Custom-Modell %s für %s angelegt", entry.model, self._taf_name)
            self.custom_options.created(entry)
            picture = (
                " und Bild aus den Audiodateien"
                if cover is not None and entry.pic.startswith("/custom_img/") and not notes
                else ""
            )
            message = f'{done}\nCustom-Tonie "{entry.series}" [{entry.model}] mit {len(entry.tracks)} Track(s){picture} angelegt.'
            self._finish_success(message, "\n".join(notes))

        def failed(message: str) -> None:
            self._finish_success(
                done,
                f"Der Custom-Tonie konnte nicht angelegt werden: {message}\n"
                "Du kannst ihn unter „Tonies → Custom-Modelle“ anlegen und dort die TAF-Datei aus der Bibliothek zuordnen.",
            )

        self._client.fetch_library(self._target_path, listed, failed)

    def _show_error(self, message: str) -> None:
        self.status_label.setStyleSheet("color: #d4380d")
        self.status_label.setText(message)

    def _fail(self, message: str) -> None:
        if not self._busy:
            return  # z. B. nach Abbrechen
        log.error(message)
        self._reply = None
        self._cleanup()
        self._set_busy(False)
        self.status_label.setStyleSheet("color: #d4380d")
        self.status_label.setText(message)
        self.statusMessage.emit(message)

    def cancel(self) -> None:
        if self._decoder is not None:
            self._decoder.stop()
        if self._reply is not None:
            reply, self._reply = self._reply, None
            self._busy = False
            reply.abort()
        self._cleanup()
        self._set_busy(False)
        self._status("Abgebrochen.")

    def _cleanup(self) -> None:
        self._stall_timer.stop()
        self._decoder = None
        self.progress.setRange(0, 1000)
        for path in self._pcm_files:
            try:
                os.remove(path)
            except OSError:
                pass
        self._pcm_files = []
