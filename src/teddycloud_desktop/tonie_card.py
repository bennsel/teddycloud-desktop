"""Kachel für einen einzelnen Tonie, nachgebaut nach der TonieCard der TeddyCloud-Weboberfläche."""

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QCheckBox, QFrame, QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from .icons import ACTIVE_COLOR, DISABLED_COLOR, icon
from .images import ImageCache
from .teddycloud import TonieCard

CARD_WIDTH = 210
IMAGE_SIZE = 186
UNSET_TONIE = "Tonie/Tag"


def _elided(label: QLabel, text: str, width: int) -> None:
    label.setText(label.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, width))
    label.setToolTip(text)


class TonieCardWidget(QFrame):
    infoRequested = pyqtSignal(object)
    editRequested = pyqtSignal(object)
    playRequested = pyqtSignal(object)
    downloadRequested = pyqtSignal(object)
    cloudToggled = pyqtSignal(object)
    liveToggled = pyqtSignal(object)
    selectionToggled = pyqtSignal(str, bool)

    def __init__(self, card: TonieCard, images: ImageCache, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._images = images
        self.card = card
        self._default_language = ""
        self._last_played: list[str] = []
        self._cloud_available = True

        self.setObjectName("tonieCard")
        self.setFixedWidth(CARD_WIDTH)
        self.setFrameShape(QFrame.Shape.StyledPanel)

        # Kopfzeile: Serie, Sprache, Auswahl
        self.series_label = QLabel(self)
        font = self.series_label.font()
        font.setBold(True)
        self.series_label.setFont(font)
        self.language_label = QLabel(self)
        self.language_label.setObjectName("languageBadge")
        self.select_box = QCheckBox(self)
        self.select_box.setVisible(False)
        self.select_box.toggled.connect(lambda checked: self.selectionToggled.emit(self.card.ruid, checked))
        header = QHBoxLayout()
        header.setSpacing(6)
        header.addWidget(self.series_label, 1)
        header.addWidget(self.language_label)
        header.addWidget(self.select_box)

        # Bild mit optional überlagertem Bild des zugewiesenen Inhalts
        self.image_label = QLabel(self)
        self.image_label.setFixedSize(IMAGE_SIZE, IMAGE_SIZE)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.source_image_label = QLabel(self.image_label)
        self.source_image_label.setFixedSize(IMAGE_SIZE // 2, IMAGE_SIZE // 2)
        self.source_image_label.move(IMAGE_SIZE - IMAGE_SIZE // 2 - 6, IMAGE_SIZE - IMAGE_SIZE // 2)
        self.source_image_label.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)

        # Episode und RFID-Tag-ID
        self.episode_label = QLabel(self)
        episode_font = self.episode_label.font()
        episode_font.setBold(True)
        self.episode_label.setFont(episode_font)
        self.uid_label = QLabel(self)
        self.uid_label.setObjectName("uidLabel")
        self.uid_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        # Aktionen
        self.info_button = self._tool_button("info", "Informationen anzeigen", lambda: self.infoRequested.emit(self.card))
        self.edit_button = self._tool_button("edit", "Bearbeiten", lambda: self.editRequested.emit(self.card))
        self.play_button = self._tool_button("play", "Abspielen", self._on_play_clicked)
        self.cloud_button = self._tool_button("cloud", "", lambda: self.cloudToggled.emit(self.card))
        self.live_button = self._tool_button("live", "", lambda: self.liveToggled.emit(self.card))
        actions = QHBoxLayout()
        actions.setSpacing(0)
        for button in (self.info_button, self.edit_button, self.play_button, self.cloud_button, self.live_button):
            actions.addWidget(button, 1)

        separator = QFrame(self)
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setObjectName("cardSeparator")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 4)
        layout.setSpacing(4)
        layout.addLayout(header)
        layout.addWidget(self.image_label, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.episode_label)
        layout.addWidget(self.uid_label)
        layout.addWidget(separator)
        layout.addLayout(actions)

        images.imageReady.connect(self._on_image_ready)
        self.set_card(card)

    def _tool_button(self, name: str, tooltip: str, slot) -> QToolButton:
        button = QToolButton(self)
        button.setIcon(icon(name))
        button.setIconSize(QSize(20, 20))
        button.setAutoRaise(True)
        button.setToolTip(tooltip)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(slot)
        return button

    # ---------- Darstellung ----------

    def set_card(self, card: TonieCard) -> None:
        self.card = card
        info = card.tonie_info
        _elided(self.series_label, info.series or info.model or UNSET_TONIE, CARD_WIDTH - 70)
        # Wie in der Weboberfläche: ohne Episode steht die UID an deren Stelle
        _elided(self.episode_label, info.episode or card.uid, CARD_WIDTH - 20)
        self.uid_label.setText(card.uid if info.episode else "")
        self.uid_label.setVisible(bool(info.episode))
        self._update_language()
        self._update_actions()
        self._update_images()
        self._update_last_played()

    def set_default_language(self, language: str) -> None:
        self._default_language = language
        self._update_language()

    def set_last_played(self, boxes: list[str]) -> None:
        """Namen der Tonieboxen, auf denen dieser Tonie zuletzt gespielt wurde."""
        self._last_played = boxes
        self._update_last_played()

    def set_cloud_available(self, available: bool) -> None:
        self._cloud_available = available
        self._update_actions()

    def set_selection_mode(self, enabled: bool) -> None:
        self.select_box.setVisible(enabled)
        if not enabled:
            self.set_selected(False)

    def set_selected(self, selected: bool) -> None:
        self.select_box.blockSignals(True)
        self.select_box.setChecked(selected)
        self.select_box.blockSignals(False)
        self.setProperty("selected", selected)
        self._repolish()

    def _repolish(self) -> None:
        self.style().unpolish(self)
        self.style().polish(self)

    def _update_language(self) -> None:
        language = self.card.tonie_info.language
        show = bool(language) and language.lower() != self._default_language.lower()
        self.language_label.setText(language.split("-")[-1].upper() if show else "")
        self.language_label.setToolTip(f"Sprache: {language}" if show else "")
        self.language_label.setVisible(show)

    def _update_last_played(self) -> None:
        self.setProperty("lastPlayed", bool(self._last_played))
        self.setToolTip("Zuletzt gespielt auf: " + ", ".join(self._last_played) if self._last_played else "")
        self._repolish()

    def _update_actions(self) -> None:
        card = self.card
        if card.is_playable:
            self.play_button.setIcon(icon("play"))
            self.play_button.setToolTip("Abspielen")
            self.play_button.setEnabled(True)
        elif card.download_trigger_url:
            self.play_button.setIcon(icon("download") if self._cloud_available else icon("download", DISABLED_COLOR))
            self.play_button.setToolTip(
                "Inhalt aus der Tonie-Cloud herunterladen"
                if self._cloud_available
                else "Keine Verbindung zur Tonie-Cloud (Boxine) verfügbar"
            )
            self.play_button.setEnabled(self._cloud_available)
        else:
            self.play_button.setIcon(icon("play", DISABLED_COLOR))
            self.play_button.setToolTip(
                "Es ist kein Inhalt zum Abspielen verfügbar. Entweder ist er nicht zugewiesen oder es fehlen "
                "Daten von der Tonies/Boxine-Cloud. Stelle die Figur auf die Box, um dies zu beheben."
            )
            self.play_button.setEnabled(False)

        self.cloud_button.setIcon(icon("nocloud", ACTIVE_COLOR) if card.nocloud else icon("cloud"))
        self.cloud_button.setToolTip(
            "Cloud-Zugriff gesperrt (klicken zum Aktivieren)" if card.nocloud else "Cloud-Zugriff erlaubt (klicken zum Sperren)"
        )
        self.live_button.setIcon(icon("live", ACTIVE_COLOR) if card.live else icon("live"))
        self.live_button.setToolTip(
            "Live-Modus aktiv (klicken zum Deaktivieren)" if card.live else "Live-Modus inaktiv (klicken zum Aktivieren)"
        )

    def _on_play_clicked(self) -> None:
        if self.card.is_playable:
            self.playRequested.emit(self.card)
        elif self.card.download_trigger_url:
            self.downloadRequested.emit(self.card)

    # ---------- Bilder ----------

    def _update_images(self) -> None:
        self._show_image(self.image_label, self._images.get(self.card.picture), IMAGE_SIZE)
        if self.card.shows_alternative_source and self.card.source_info and self.card.source_info.picture:
            self.source_image_label.setVisible(True)
            self.source_image_label.setToolTip(
                f'Der Toniefigur "{self.card.tonie_info.title}" ist der Inhalt "{self.card.source_info.title}" zugewiesen!'
            )
            self._show_image(self.source_image_label, self._images.get(self.card.source_info.picture), IMAGE_SIZE // 2)
        else:
            self.source_image_label.setVisible(False)

    @staticmethod
    def _show_image(label: QLabel, image: QImage | None, size: int) -> None:
        if image is None:
            label.clear()
            return
        pixmap = QPixmap.fromImage(image)
        ratio = label.devicePixelRatioF()
        pixmap = pixmap.scaled(
            int(size * ratio), int(size * ratio), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        pixmap.setDevicePixelRatio(ratio)
        label.setPixmap(pixmap)

    def _on_image_ready(self, path: str, image: QImage) -> None:
        if path == self.card.picture:
            self._show_image(self.image_label, image, IMAGE_SIZE)
        if self.card.source_info and path == self.card.source_info.picture and self.source_image_label.isVisible():
            self._show_image(self.source_image_label, image, IMAGE_SIZE // 2)


CARD_STYLESHEET = """
QFrame#tonieCard { background: palette(base); border: 1px solid palette(mid); border-radius: 8px; }
QFrame#tonieCard[selected="true"] { background: palette(alternate-base); border: 2px solid palette(highlight); }
QFrame#tonieCard[lastPlayed="true"] { border-top: 3px solid #1677ff; }
QFrame#cardSeparator { color: palette(midlight); }
QLabel#uidLabel { color: palette(placeholder-text); font-size: 11px; }
QLabel#languageBadge { border: 1px solid palette(mid); border-radius: 3px; padding: 0 3px; font-size: 10px; }
"""
