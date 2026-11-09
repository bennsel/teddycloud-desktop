"""Kachel für eine Toniebox, nachgebaut nach der TonieboxCard der TeddyCloud-Weboberfläche."""

from datetime import datetime

from PyQt6.QtCore import QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QImage, QMouseEvent, QPainter, QPaintEvent, QPixmap
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from .icons import ACTIVE_COLOR, DEFAULT_COLOR, SUCCESS_COLOR, icon
from .images import ImageCache
from .teddycloud import BOX_VERSIONS, NO_RUID, BoxModel, TeddyCloudClient, Toniebox, TonieCard, format_box_id

CARD_WIDTH = 300
IMAGE_WIDTH = CARD_WIDTH - 22
IMAGE_HEIGHT = 230


def format_timestamp(value: str) -> str:
    """Unix-Zeit der TeddyCloud lesbar machen; 0 oder leer bedeutet unbekannt."""
    if not value.strip().isdigit() or int(value) == 0:
        return ""
    return f"{datetime.fromtimestamp(int(value)):%d.%m.%Y %H:%M:%S}"


class BoxImage(QWidget):
    """Bild der Farbvariante mit Ausschnitt (crop) und dem zuletzt gespielten Tonie unten rechts."""

    tonieClicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(IMAGE_WIDTH, IMAGE_HEIGHT)
        self._image: QImage | None = None
        self._crop: tuple[float, float, float] | None = None
        self._placeholder = False
        self.tonie_label = QLabel(self)
        self.tonie_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tonie_label.setVisible(False)
        self.tonie_label.mousePressEvent = self._on_tonie_pressed  # type: ignore[method-assign]

    def set_box_image(self, image: QImage | None, crop: tuple[float, float, float] | None, placeholder: bool) -> None:
        self._image = image
        self._crop = crop
        self._placeholder = placeholder
        self.update()

    def set_tonie_image(self, image: QImage | None, tooltip: str) -> None:
        if image is None:
            self.tonie_label.setVisible(False)
            return
        size = int(IMAGE_HEIGHT * 0.6)
        pixmap = QPixmap.fromImage(image).scaled(
            size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        self.tonie_label.setPixmap(pixmap)
        self.tonie_label.resize(pixmap.size())
        self.tonie_label.move(IMAGE_WIDTH - pixmap.width() - 8, IMAGE_HEIGHT - pixmap.height() - 8)
        self.tonie_label.setToolTip(tooltip)
        self.tonie_label.setVisible(True)
        self.tonie_label.raise_()

    def _on_tonie_pressed(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.tonieClicked.emit()

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setClipRect(self.rect())
        if self._image is not None and not self._image.isNull():
            width = float(IMAGE_WIDTH)
            height = width * self._image.height() / max(self._image.width(), 1)
            if self._crop:
                # Entspricht CSS "transform: scale(s) translateX(x) translateY(y)" um die Bildmitte
                x, y, scale = self._crop
                painter.translate(width / 2, height / 2)
                painter.scale(scale, scale)
                painter.translate(x, y)
                painter.translate(-width / 2, -height / 2)
            painter.drawImage(QRectF(0, 0, width, height), self._image)
        elif self._placeholder:
            size = int(IMAGE_HEIGHT * 0.7)
            pixmap = icon("box", DEFAULT_COLOR, size).pixmap(QSize(size, size))
            painter.drawPixmap((IMAGE_WIDTH - size) // 2, (IMAGE_HEIGHT - size) // 2, pixmap)
        painter.end()


class TonieboxCardWidget(QFrame):
    editRequested = pyqtSignal(object)
    certificatesRequested = pyqtSignal(object)
    settingsRequested = pyqtSignal(object)
    deleteRequested = pyqtSignal(object)
    tonieClicked = pyqtSignal(str, str)  # Box-ID, RUID
    statusMessage = pyqtSignal(str)

    def __init__(
        self,
        box: Toniebox,
        models: list[BoxModel],
        client: TeddyCloudClient,
        images: ImageCache,
        check_cfw: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.box = box
        self._models = models
        self._client = client
        self._images = images
        self._check_cfw = check_cfw

        self.online = False
        self.version = ""
        self.last_online = ""
        self.last_ip = ""
        self.cfw_installed = False
        self.api_access = True
        self.last_tonie: TonieCard | None = None
        self._last_tonie_time = ""

        self.setObjectName("tonieboxCard")
        self.setFixedWidth(CARD_WIDTH)
        self.setFrameShape(QFrame.Shape.StyledPanel)

        self.name_label = QLabel(self)
        font = self.name_label.font()
        font.setBold(True)
        font.setPointSizeF(font.pointSizeF() * 1.15)
        self.name_label.setFont(font)

        self.image = BoxImage(self)
        self.image.tonieClicked.connect(self._on_tonie_clicked)

        self.description_label = QLabel(self)
        self.description_label.setObjectName("boxDescription")
        self.description_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.description_label.setOpenExternalLinks(True)

        self.status_button = self._tool_button("wifi", "", self._on_status_clicked)
        self.edit_button = self._tool_button("edit", "Name und Modell bearbeiten", lambda: self.editRequested.emit(self))
        self.cert_button = self._tool_button(
            "certificate", "Zertifikate hochladen", lambda: self.certificatesRequested.emit(self)
        )
        self.settings_button = self._tool_button(
            "settings", "Einstellungen bearbeiten", lambda: self.settingsRequested.emit(self)
        )
        self.delete_button = self._tool_button("delete", "Toniebox löschen", lambda: self.deleteRequested.emit(self))
        actions = QHBoxLayout()
        actions.setSpacing(0)
        for button in (self.status_button, self.edit_button, self.cert_button, self.settings_button, self.delete_button):
            actions.addWidget(button, 1)

        separator = QFrame(self)
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setObjectName("cardSeparator")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 4)
        layout.setSpacing(6)
        layout.addWidget(self.name_label)
        layout.addWidget(self.image, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.description_label)
        layout.addWidget(separator)
        layout.addLayout(actions)

        images.imageReady.connect(self._on_image_ready)
        self._update_name()
        self._update_box_image()
        self._update_description()
        self._update_status()
        self.reload()

    def _tool_button(self, name: str, tooltip: str, slot) -> QToolButton:
        button = QToolButton(self)
        button.setIcon(icon(name))
        button.setIconSize(QSize(20, 20))
        button.setAutoRaise(True)
        button.setToolTip(tooltip)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(slot)
        return button

    # ---------- Daten laden ----------

    def reload(self) -> None:
        """Lädt Status, Version, letzten Tonie und API-Zugriff der Box (wie die Weboberfläche je Karte)."""
        box_id = self.box.id
        ignore = lambda _message: None  # noqa: E731 - fehlende Werte zeigen einfach nichts an
        self._client.fetch_setting("internal.online", box_id, self._on_online, ignore)
        self._client.fetch_setting("internal.toniebox_firmware.boxIC", box_id, self._on_version, ignore)
        self._client.fetch_setting("toniebox.api_access", box_id, self._on_api_access, ignore)
        self._client.fetch_setting("internal.last_connection", box_id, self._on_last_connection, ignore)
        self._client.fetch_setting("internal.last_ruid", box_id, self._on_last_ruid, ignore)
        if self._check_cfw:
            self._client.fetch_setting("internal.ip", box_id, self._on_ip, ignore)

    def _on_online(self, value: str) -> None:
        self.online = value == "true"
        self._update_status()

    def _on_version(self, value: str) -> None:
        self.version = BOX_VERSIONS.get(value, "")
        self._update_description()
        self._check_custom_firmware()

    def _on_api_access(self, value: str) -> None:
        self.api_access = value == "true"
        self._update_status()

    def _on_last_connection(self, value: str) -> None:
        self.last_online = format_timestamp(value)
        self._update_status()

    def _on_ip(self, value: str) -> None:
        self.last_ip = value
        self._check_custom_firmware()

    def _check_custom_firmware(self) -> None:
        """Bei CC3200-Boxen mit Custom-Firmware (CFW) antwortet die Box selbst auf eine Batterie-Abfrage."""
        if not (self._check_cfw and self.last_ip and self.version == "CC3200"):
            return

        def found(_data: bytes) -> None:
            self.cfw_installed = True
            self._update_description()

        self._client.get_bytes(
            self._client.url(f"http://{self.last_ip}/api/ajax?cmd=box-battery&sub=stats"), found, lambda _m: None
        )

    def _on_last_ruid(self, ruid: str) -> None:
        if not ruid or ruid == NO_RUID:
            return

        def with_time(time_value: str) -> None:
            self._last_tonie_time = format_timestamp(time_value)
            self._client.fetch_tags(self.box.id, lambda cards: self._set_last_tonie(cards, ruid), lambda _m: None)

        self._client.fetch_setting("internal.last_ruid_time", self.box.id, with_time, lambda _m: with_time(""))

    def _set_last_tonie(self, cards: list[TonieCard], ruid: str) -> None:
        self.last_tonie = next((card for card in cards if card.ruid == ruid.lower()), None)
        self._update_tonie_image()

    # ---------- Darstellung ----------

    def set_box(self, box: Toniebox) -> None:
        self.box = box
        self._update_name()
        self._update_box_image()

    def model(self) -> BoxModel | None:
        return next((model for model in self._models if model.id == self.box.model), None)

    def _update_name(self) -> None:
        self.name_label.setText(self.box.name or format_box_id(self.box.id))
        self.name_label.setToolTip(self.box.name)

    def _update_box_image(self) -> None:
        model = self.model()
        if model is None or not model.img_src:
            self.image.set_box_image(None, None, placeholder=True)
            self.image.setToolTip("Klicke auf ✎ (Bearbeiten), um das richtige Modell deiner Toniebox auszuwählen!")
            return
        self.image.setToolTip(model.name)
        self.image.set_box_image(self._images.get(model.img_src), model.crop, placeholder=False)

    def _update_tonie_image(self) -> None:
        tonie = self.last_tonie
        if tonie is None:
            self.image.set_tonie_image(None, "")
            return
        tooltip = "Zuletzt gespielter Tonie: " + tonie.tonie_info.title
        if self._last_tonie_time:
            tooltip += f" ({self._last_tonie_time})"
        self.image.set_tonie_image(self._images.get(tonie.picture), tooltip + "\nKlicken, um den Tonie anzuzeigen")

    def _update_description(self) -> None:
        prefix = self.version or "MAC"
        mac = format_box_id(self.box.id)
        if self.cfw_installed and self.last_ip:
            self.description_label.setText(f'{prefix} <a href="http://{self.last_ip}">{mac} 🔗</a>')
            self.description_label.setToolTip("Öffne Web Frontend deiner Toniebox")
        else:
            self.description_label.setText(f"{prefix} {mac}")
            self.description_label.setToolTip("")

    def _update_status(self) -> None:
        if not self.api_access:
            self.status_button.setIcon(icon("lock", ACTIVE_COLOR))
            self.status_button.setToolTip("Zugriff auf TeddyCloud APIs deaktiviert. Klicken zum Aktivieren.")
        elif self.online:
            self.status_button.setIcon(icon("wifi", SUCCESS_COLOR))
            self.status_button.setToolTip("online")
        else:
            self.status_button.setIcon(icon("wifi", "#a6a6a6"))
            self.status_button.setToolTip("offline" + (f" - zuletzt online: {self.last_online}" if self.last_online else ""))
        self.status_button.setCursor(Qt.CursorShape.PointingHandCursor if not self.api_access else Qt.CursorShape.ArrowCursor)

    def _on_image_ready(self, path: str, image: QImage) -> None:
        model = self.model()
        if model is not None and path == model.img_src:
            self.image.set_box_image(image, model.crop, placeholder=False)
        if self.last_tonie is not None and path == self.last_tonie.picture:
            self._update_tonie_image()

    # ---------- Aktionen ----------

    def _on_tonie_clicked(self) -> None:
        if self.last_tonie is not None:
            self.tonieClicked.emit(self.box.id, self.last_tonie.ruid)

    def _on_status_clicked(self) -> None:
        # Wie in der Weboberfläche lässt sich der API-Zugriff hier nur wieder einschalten (Schloss-Symbol)
        if not self.api_access:
            self.set_api_access(True)

    def set_api_access(self, enabled: bool) -> None:
        mac = self.box.id

        def done() -> None:
            self._client.trigger_write_config()
            self.api_access = enabled
            self._update_status()
            state = "aktiviert" if enabled else "deaktiviert"
            self.statusMessage.emit(f"Zugriff auf TeddyCloud-APIs für Toniebox {mac} {state}")

        def failed(message: str) -> None:
            self.statusMessage.emit(f"Änderung des Zugriffs auf TeddyCloud-API für Toniebox {mac} fehlgeschlagen: {message}")

        self._client.set_setting("toniebox.api_access", enabled, mac, done, failed)


TONIEBOX_CARD_STYLESHEET = """
QFrame#tonieboxCard { background: palette(base); border: 1px solid palette(mid); border-radius: 8px; }
QFrame#cardSeparator { color: palette(midlight); }
QLabel#boxDescription { color: palette(placeholder-text); }
"""
