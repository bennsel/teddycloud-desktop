"""Dialoge der Toniebox-Kacheln: Bearbeiten, Einstellungen und Zertifikate."""

from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .icons import icon
from .images import ImageCache
from .teddycloud import BoxModel, SettingOption, TeddyCloudClient, Toniebox, format_box_id

UNSET_MODEL = "-1"
INT32_MAX = 2**31 - 1

# Wie Settings.tsx der Weboberfläche: nur diese Einstellungen lassen sich je Toniebox überschreiben
BOX_SETTING_PREFIXES = (
    "core.certdir",
    "core.client_cert.",
    "core.flex_",
    "core.contentdir",
    "toniebox.",
    "cloud.enabled",
    "cloud.enableV1Claim",
    "cloud.enableV1CloudReset",
    "cloud.enableV1FreshnessCheck",
    "cloud.enableV1Log",
    "cloud.enableV1Time",
    "cloud.enableV1Ota",
    "cloud.enableV2Content",
    "cloud.cacheOta",
    "cloud.localOta",
    "cloud.cacheContent",
    "cloud.cacheToLibrary",
    "cloud.markCustomTagByPass",
    "cloud.prioCustomContent",
    "cloud.updateOnLowerAudioId",
    "cloud.dumpRuidAuthContentJson",
)
EDITABLE_TYPES = ("bool", "int", "uint", "string")


def is_box_setting(option: SettingOption) -> bool:
    return (
        "core.settings_level" not in option.id
        and option.type in EDITABLE_TYPES
        and any(prefix in option.id for prefix in BOX_SETTING_PREFIXES)
    )


def box_subtitle(version: str, box_id: str) -> str:
    return f"{version or 'MAC'}: {format_box_id(box_id)}"


def info_banner(text: str, parent: QWidget, warning: bool = False) -> QLabel:
    label = QLabel(text, parent)
    label.setWordWrap(True)
    color = ("#fffbe6", "#ffe58f") if warning else ("#e6f4ff", "#91caff")
    label.setStyleSheet(
        f"background: {color[0]}; border: 1px solid {color[1]}; border-radius: 6px; padding: 8px; color: #262626;"
    )
    return label


class EditTonieboxDialog(QDialog):
    """Name und Farbvariante (Modell) einer Toniebox ändern."""

    saved = pyqtSignal(object)  # aktualisierte Toniebox

    def __init__(
        self,
        box: Toniebox,
        version: str,
        models: list[BoxModel],
        client: TeddyCloudClient,
        images: ImageCache,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._box = box
        self._client = client
        self._images = images
        self._models = models
        self.setWindowTitle(f'Toniebox "{box.name}" bearbeiten')
        self.setMinimumWidth(460)

        heading = QLabel(
            f"<h3>Toniebox \"{box.name}\" bearbeiten</h3><span style='color:gray'>{box_subtitle(version, box.id)}</span>", self
        )

        self.name_edit = QLineEdit(box.name, self)
        self.name_edit.textChanged.connect(self._on_changed)
        self.rollback_button = QToolButton(self)
        self.rollback_button.setIcon(icon("rollback"))
        self.rollback_button.setToolTip("Ursprünglichen Namen wiederherstellen")
        self.rollback_button.clicked.connect(lambda: self.name_edit.setText(box.name))
        name_row = QHBoxLayout()
        name_row.addWidget(self.rollback_button)
        name_row.addWidget(self.name_edit, 1)

        self.model_combo = QComboBox(self)
        self.model_combo.addItem("Modell unbekannt/nicht gesetzt", UNSET_MODEL)
        for model in models:
            self.model_combo.addItem(model.name, model.id)
        index = self.model_combo.findData(box.model)
        self.model_combo.setCurrentIndex(index if index >= 0 else 0)
        self._original_model = self.model_combo.currentData()
        self.model_combo.currentIndexChanged.connect(self._on_changed)
        self.preview = QLabel(self)
        self.preview.setFixedHeight(140)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        images.imageReady.connect(lambda path, _image: self._update_preview() if path == self._current_img_src() else None)

        self.error_label = QLabel(self)
        self.error_label.setStyleSheet("color: #d4380d")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel, self)
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setText("Speichern")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        self.buttons.accepted.connect(self._save)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(heading)
        layout.addWidget(QLabel("<b>Name</b>", self))
        layout.addLayout(name_row)
        layout.addWidget(QLabel("<b>Modell</b>", self))
        layout.addWidget(self.model_combo)
        layout.addWidget(self.preview)
        layout.addWidget(self.error_label)
        layout.addWidget(self.buttons)
        self._on_changed()

    def _current_img_src(self) -> str:
        model = next((m for m in self._models if m.id == self.model_combo.currentData()), None)
        return model.img_src if model else ""

    def _update_preview(self) -> None:
        image = self._images.get(self._current_img_src()) if self._current_img_src() else None
        if image is None:
            self.preview.clear()
            return
        self.preview.setPixmap(
            QPixmap.fromImage(image).scaled(
                200, 140, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
        )

    def _on_changed(self) -> None:
        name_changed = self.name_edit.text() != self._box.name
        model_changed = self.model_combo.currentData() != self._original_model
        self.rollback_button.setEnabled(name_changed)
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(name_changed or model_changed)
        self._update_preview()

    def _save(self) -> None:
        name = self.name_edit.text()
        model = self.model_combo.currentData()
        steps: list[tuple[str, str]] = []
        if name != self._box.name:
            steps.append(("boxName", name))
        if model != self._original_model:
            steps.append(("boxModel", model))
        self.buttons.setEnabled(False)

        def next_step(remaining: list[tuple[str, str]]) -> None:
            if not remaining:
                self._client.trigger_write_config()
                self.saved.emit(Toniebox(self._box.id, name, self._box.common_name, model))
                self.accept()
                return
            key, value = remaining[0]
            self._client.set_setting(key, value, self._box.id, lambda: next_step(remaining[1:]), failed)

        def failed(message: str) -> None:
            self.error_label.setText(f"Fehler beim Speichern der Konfiguration: {message}")
            self.error_label.setVisible(True)
            self.buttons.setEnabled(True)

        next_step(steps)


class _SettingRow:
    """Eingabefeld einer Einstellung mit der Checkbox "überschrieben" (Wert nur für diese Box)."""

    def __init__(
        self, option: SettingOption, parent: QWidget, on_change: Callable[[], None], fetch_global: Callable[["_SettingRow"], None]
    ) -> None:
        self.option = option
        self.initial_value = option.value
        self.initial_overlayed = option.overlayed
        self.value = option.value
        self.overlayed = option.overlayed
        self._on_change = on_change
        self._fetch_global = fetch_global

        self.label = QLabel(option.label, parent)
        self.label.setWordWrap(True)
        self.label.setToolTip(f"{option.description}\n\n{option.id}" if option.description else option.id)

        if option.type == "bool":
            self.editor: QWidget = QCheckBox(parent)
            self.editor.toggled.connect(self._edited)
        elif option.type in ("int", "uint"):
            self.editor = QSpinBox(parent)
            minimum = int(option.minimum) if option.minimum is not None else (0 if option.type == "uint" else -INT32_MAX)
            maximum = int(option.maximum) if option.maximum is not None else INT32_MAX
            self.editor.setRange(max(minimum, -INT32_MAX), min(maximum, INT32_MAX))
            self.editor.valueChanged.connect(self._edited)
        else:
            self.editor = QLineEdit(parent)
            self.editor.textChanged.connect(self._edited)
        self.overlay_box = QCheckBox("überschrieben", parent)
        self.overlay_box.setToolTip("Eigener Wert für diese Toniebox. Ohne Haken gilt der allgemeine TeddyCloud-Wert.")
        self.overlay_box.toggled.connect(self._overlay_toggled)
        self.show_value(option.value)
        self.overlay_box.blockSignals(True)
        self.overlay_box.setChecked(option.overlayed)
        self.overlay_box.blockSignals(False)
        self.editor.setEnabled(option.overlayed)

    def show_value(self, value: Any) -> None:
        self.editor.blockSignals(True)
        if isinstance(self.editor, QCheckBox):
            self.editor.setChecked(bool(value))
        elif isinstance(self.editor, QSpinBox):
            self.editor.setValue(int(value or 0))
        else:
            self.editor.setText("" if value is None else str(value))
        self.editor.blockSignals(False)
        self.value = self._editor_value()

    def _editor_value(self) -> Any:
        if isinstance(self.editor, QCheckBox):
            return self.editor.isChecked()
        if isinstance(self.editor, QSpinBox):
            return self.editor.value()
        return self.editor.text()

    def _edited(self, *_args) -> None:
        self.value = self._editor_value()
        self._on_change()

    def _overlay_toggled(self, checked: bool) -> None:
        self.overlayed = checked
        self.editor.setEnabled(checked)
        if not checked:
            # Wie in der Weboberfläche: den allgemeinen Wert anzeigen, der danach wieder gilt
            self._fetch_global(self)
        self._on_change()

    def parse_global(self, text: str) -> Any:
        if self.option.type == "bool":
            return text == "true"
        if self.option.type in ("int", "uint"):
            try:
                return int(text)
            except ValueError:
                return 0
        return text

    @property
    def changed(self) -> bool:
        return self.value != self.initial_value or self.overlayed != self.initial_overlayed

    def discard(self) -> None:
        self.overlay_box.blockSignals(True)
        self.overlay_box.setChecked(self.initial_overlayed)
        self.overlay_box.blockSignals(False)
        self.overlayed = self.initial_overlayed
        self.editor.setEnabled(self.overlayed)
        self.show_value(self.initial_value)

    def commit(self) -> None:
        self.initial_value = self.value
        self.initial_overlayed = self.overlayed


class TonieboxSettingsDialog(QDialog):
    """Einstellungen, die für eine einzelne Toniebox überschrieben werden können."""

    def __init__(self, box: Toniebox, client: TeddyCloudClient, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._box = box
        self._client = client
        self._rows: list[_SettingRow] = []
        self.setWindowTitle(f'Einstellungen der Toniebox "{box.name}" bearbeiten')
        self.resize(760, 680)

        layout = QVBoxLayout(self)
        layout.addWidget(
            info_banner("<b>Achtung! Settings level</b><br>Falls du Einstellungen vermisst, erhöhe das 'Settings level'.", self)
        )

        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        layout.addWidget(self.scroll, 1)

        # Settings level (gilt für die gesamte TeddyCloud)
        self.level_group = QButtonGroup(self)
        level_row = QHBoxLayout()
        level_row.addStretch(1)
        level_row.addWidget(QLabel("Settings level:", self))
        for level, text in ((1, "Basic"), (2, "Detail"), (3, "Expert")):
            button = QRadioButton(text, self)
            self.level_group.addButton(button, level)
            level_row.addWidget(button)
        level_row.addStretch(1)
        self.level_group.idClicked.connect(self._change_level)
        layout.addLayout(level_row)

        self.status_label = QLabel(self)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        buttons = QDialogButtonBox(self)
        self.discard_button = buttons.addButton("Verwerfen", QDialogButtonBox.ButtonRole.ResetRole)
        self.discard_button.clicked.connect(self._discard)
        self.save_button = buttons.addButton("Speichern", QDialogButtonBox.ButtonRole.ApplyRole)
        self.save_button.clicked.connect(self._save)
        close_button = buttons.addButton("Schließen", QDialogButtonBox.ButtonRole.RejectRole)
        close_button.clicked.connect(self.reject)
        layout.addWidget(buttons)

        self._load()

    # ---------- Laden ----------

    def _load(self) -> None:
        self._show_message("Lade Einstellungen …")
        self._client.fetch_setting("core.settings_level", "", self._on_level, lambda _m: self._on_level("1"))

    def _on_level(self, value: str) -> None:
        button = self.level_group.button(int(value) if value.isdigit() else 1)
        if button is not None:
            button.setChecked(True)
        self._client.fetch_settings_index(self._box.id, self._build_form, self._show_error)

    def _build_form(self, options: list[SettingOption]) -> None:
        container = QWidget(self.scroll)
        grid = QGridLayout(container)
        grid.setColumnStretch(1, 1)
        self._rows = []
        previous: list[str] = []
        row_index = 0
        for option in filter(is_box_setting, options):
            parts = option.id.split(".")
            # Überschriften für neue Kategorien, wie in der Weboberfläche ("Category core", ".client_cert")
            for depth, part in enumerate(parts[:-1]):
                if depth < len(previous) and previous[depth] == part:
                    continue
                text = f"<h3>Category {part}</h3>" if depth == 0 else f"<h4>{'&nbsp;' * depth * 3}.{part}</h4>"
                grid.addWidget(QLabel(text, container), row_index, 0, 1, 3)
                row_index += 1
            previous = parts
            row = _SettingRow(option, container, self._update_buttons, self._fetch_global_value)
            grid.addWidget(row.label, row_index, 0)
            grid.addWidget(row.editor, row_index, 1)
            grid.addWidget(row.overlay_box, row_index, 2)
            self._rows.append(row)
            row_index += 1
        grid.setRowStretch(row_index, 1)
        self.scroll.setWidget(container)
        self._show_message("" if self._rows else "Keine Einstellungen für dieses Settings level vorhanden.")
        self._update_buttons()

    def _fetch_global_value(self, row: _SettingRow) -> None:
        def apply(text: str) -> None:
            if not row.overlayed:
                row.show_value(row.parse_global(text))
                self._update_buttons()

        self._client.fetch_setting(row.option.id, "", apply, self._show_error)

    # ---------- Speichern ----------

    def has_unsaved_changes(self) -> bool:
        return any(row.changed for row in self._rows)

    def _update_buttons(self) -> None:
        dirty = self.has_unsaved_changes()
        self.save_button.setEnabled(dirty)
        self.discard_button.setEnabled(dirty)
        # Das Settings level lässt sich nur ohne ungespeicherte Änderungen umschalten
        for button in self.level_group.buttons():
            button.setEnabled(not dirty)

    def _discard(self) -> None:
        for row in self._rows:
            row.discard()
        self._update_buttons()

    def _save(self) -> None:
        changed = [row for row in self._rows if row.changed]
        if not changed:
            return
        self.save_button.setEnabled(False)
        errors: list[str] = []
        pending = len(changed)

        def finished(row: _SettingRow, error: str | None) -> None:
            nonlocal pending
            if error is None:
                row.commit()
            else:
                errors.append(f"{row.option.label}: {error}")
            pending -= 1
            if pending == 0:
                self._client.trigger_write_config()
                if errors:
                    self._show_error("Fehler beim Speichern:\n" + "\n".join(errors))
                else:
                    self._show_message(f"{len(changed)} Einstellung(en) gespeichert.")
                self._update_buttons()

        for row in changed:
            # Ohne "überschrieben" wird der Box-Wert entfernt, dann gilt wieder der TeddyCloud-Wert
            reset = not row.overlayed
            self._client.set_setting(
                row.option.id,
                row.value,
                self._box.id,
                lambda r=row: finished(r, None),
                lambda message, r=row: finished(r, message),
                reset=reset,
            )

    def _change_level(self, level: int) -> None:
        def done() -> None:
            self._client.trigger_write_config()
            self._client.fetch_settings_index(self._box.id, self._build_form, self._show_error)

        self._client.set_setting("core.settings_level", level, "", done, self._show_error)

    def _show_message(self, text: str) -> None:
        self.status_label.setStyleSheet("")
        self.status_label.setText(text)

    def _show_error(self, text: str) -> None:
        self.status_label.setStyleSheet("color: #d4380d")
        self.status_label.setText(text)


class _DropArea(QLabel):
    filesDropped = pyqtSignal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(120)
        self.setWordWrap(True)
        self.setText("Ziehe die Client-Zertifikate (*.der) aus deiner Box hierher\n(ca.der, client.der, private.der)")
        self.setStyleSheet("border: 2px dashed palette(mid); border-radius: 8px; padding: 12px;")

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            self.filesDropped.emit(paths)
            event.acceptProposedAction()


class CertificatesDialog(QDialog):
    """Client-Zertifikate einer Toniebox in deren Zertifikatsverzeichnis (core.certdir) hochladen."""

    def __init__(self, box: Toniebox, client: TeddyCloudClient, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._box = box
        self._client = client
        self.setWindowTitle(f'Zertifikate für Toniebox "{box.name}" hochladen')
        self.setMinimumWidth(520)

        self.path_label = QLabel("Upload Pfad (certDir): wird ermittelt …", self)
        self.path_label.setWordWrap(True)
        self.drop_area = _DropArea(self)
        self.drop_area.filesDropped.connect(self.upload)
        choose_button = QPushButton(icon("upload"), "Dateien auswählen …", self)
        choose_button.clicked.connect(self._choose_files)
        self.results = QListWidget(self)
        self.results.setMaximumHeight(130)
        self.results.setWordWrap(True)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Schließen")
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.path_label)
        layout.addWidget(self.drop_area)
        layout.addWidget(choose_button, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.results)
        layout.addWidget(buttons)

        client.fetch_settings_index(box.id, self._on_options, lambda m: self.path_label.setText(m))

    def _on_options(self, options: list[SettingOption]) -> None:
        option = next((o for o in options if o.id == "core.certdir"), None)
        if option is not None:
            self._show_path(str(option.value), option.overlayed)
            return

        # Bei niedrigem Settings level fehlt core.certdir im Index: allgemeinen und Box-Wert vergleichen
        def with_default(default_dir: str) -> None:
            self._client.fetch_setting(
                "core.certdir",
                self._box.id,
                lambda box_dir: self._show_path(box_dir, box_dir != default_dir),
                self.path_label.setText,
            )

        self._client.fetch_setting("core.certdir", "", with_default, self.path_label.setText)

    def _show_path(self, path: str, box_specific: bool) -> None:
        hint = " (Toniebox spezifisch hinterlegt)" if box_specific else " <b>(ACHTUNG: Default Pfad!)</b>"
        self.path_label.setText(f"Upload Pfad (certDir): <i>{path}</i><small>{hint}</small>")

    def _choose_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Zertifikate auswählen", "", "Zertifikate (*.der);;Alle Dateien (*)")
        if paths:
            self.upload(paths)

    def upload(self, paths: list[str]) -> None:
        pending = 0
        uploaded = 0

        def finished(name: str, error: str | None) -> None:
            nonlocal pending, uploaded
            pending -= 1
            if error is None:
                uploaded += 1
                self.results.addItem(f"✓ Zertifikat {name} erfolgreich hochgeladen.")
            else:
                self.results.addItem(f"✗ Der Upload des Zertifikats {name} ist fehlgeschlagen: {error}")
            if pending == 0 and uploaded:
                self._client.trigger_write_config()

        for path in paths:
            name = path.replace("\\", "/").rsplit("/", 1)[-1]
            if not name.lower().endswith(".der"):
                self.results.addItem(f"✗ Der Upload des Zertifikats {name} ist fehlgeschlagen: ungültiger Dateityp (nur *.der)")
                continue
            pending += 1
            try:
                self._client.upload_certificate(
                    path, self._box.id, lambda n=name: finished(n, None), lambda m, n=name: finished(n, m)
                )
            except OSError as exc:
                finished(name, str(exc))
