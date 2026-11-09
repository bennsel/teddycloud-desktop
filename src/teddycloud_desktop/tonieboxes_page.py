"""Übersicht der Tonieboxen, nachgebaut nach /web/tonieboxes der TeddyCloud-Weboberfläche."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget

from .flow_layout import FlowLayout
from .icons import icon
from .images import ImageCache
from .teddycloud import BoxModel, TeddyCloudClient, Toniebox
from .toniebox_card import TONIEBOX_CARD_STYLESHEET, TonieboxCardWidget
from .toniebox_dialogs import CertificatesDialog, EditTonieboxDialog, TonieboxSettingsDialog, info_banner


class TonieboxesPage(QWidget):
    statusMessage = pyqtSignal(str)
    showTonieRequested = pyqtSignal(str, str)  # Box-ID (Overlay), RUID
    boxesChanged = pyqtSignal()

    def __init__(self, client: TeddyCloudClient, images: ImageCache, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._client = client
        self._images = images
        self._models: list[BoxModel] = []
        self._cards: list[TonieboxCardWidget] = []
        self._check_cfw = False

        self.setStyleSheet(TONIEBOX_CARD_STYLESHEET)

        refresh_button = QPushButton(icon("refresh"), "Aktualisieren", self)
        refresh_button.clicked.connect(self.load)
        header = QHBoxLayout()
        header.addWidget(QLabel("<h2>Deine Tonieboxen</h2>", self))
        header.addStretch(1)
        header.addWidget(refresh_button)

        self.new_boxes_banner = info_banner(
            "<b>Neue Tonieboxen erlaubt</b><br>Du kannst neue Tonieboxen mit TeddyCloud verbinden. Wenn du alle "
            'deine Boxen verbunden hast, deaktiviere aus Sicherheitsgründen bitte die Einstellung "Allow new boxes".',
            self,
            warning=True,
        )
        self.new_boxes_banner.setVisible(False)

        self.empty_label = QLabel(
            "<p>Keine Tonieboxen gefunden.</p><p>Tonieboxen erscheinen erst nach erfolgreicher Verbindung. "
            "Stelle sicher, dass deine Toniebox richtig verbunden ist.</p>",
            self,
        )
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setVisible(False)

        self.cards_container = QWidget(self)
        self.flow = FlowLayout(self.cards_container, spacing=16)
        self.flow.setContentsMargins(4, 4, 4, 4)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.cards_container)

        layout = QVBoxLayout(self)
        layout.addLayout(header)
        layout.addWidget(self.new_boxes_banner)
        layout.addWidget(self.empty_label)
        layout.addWidget(scroll, 1)

    # ---------- Laden ----------

    def load(self) -> None:
        self.statusMessage.emit(f"Lade Tonieboxen von {self._client.endpoint} …")
        self._client.fetch_setting(
            "core.allowNewBox", "", lambda v: self.new_boxes_banner.setVisible(v == "true"), lambda _m: None
        )

        def with_cfw_flag(value: str) -> None:
            self._check_cfw = value == "true"
            self._client.fetch_box_models(self._on_models)

        self._client.fetch_setting("frontend.check_cc3200_cfw", "", with_cfw_flag, lambda _m: with_cfw_flag("false"))

    def _on_models(self, models: list[BoxModel]) -> None:
        self._models = models
        if not models:
            self.statusMessage.emit("Fehler beim Abrufen der Toniebox-Modelle")
        self._client.fetch_boxes(self._on_boxes)

    def _on_boxes(self, boxes: list[Toniebox]) -> None:
        for card in self._cards:
            self.flow.removeWidget(card)
            card.deleteLater()
        self._cards = []
        for box in boxes:
            card = TonieboxCardWidget(box, self._models, self._client, self._images, self._check_cfw, self.cards_container)
            card.editRequested.connect(self.edit)
            card.certificatesRequested.connect(self.certificates)
            card.settingsRequested.connect(self.settings)
            card.deleteRequested.connect(self.delete)
            card.tonieClicked.connect(self.showTonieRequested)
            card.statusMessage.connect(self.statusMessage)
            self.flow.addWidget(card)
            self._cards.append(card)
        self.empty_label.setVisible(not boxes)
        self.statusMessage.emit(f"{len(boxes)} Tonieboxen geladen")

    # ---------- Aktionen ----------

    def edit(self, card: TonieboxCardWidget) -> None:
        dialog = EditTonieboxDialog(card.box, card.version, self._models, self._client, self._images, self)

        def saved(box: Toniebox) -> None:
            old = card.box
            card.set_box(box)
            if box.name != old.name:
                self.statusMessage.emit(f'Neuer Name "{box.name}" der Toniebox {box.id} wurde erfolgreich gespeichert.')
            if box.model != old.model:
                self.statusMessage.emit(f'Neues Modell "{box.model}" der Toniebox {box.id} wurde erfolgreich gespeichert.')
            self.boxesChanged.emit()

        dialog.saved.connect(saved)
        dialog.exec()

    def certificates(self, card: TonieboxCardWidget) -> None:
        CertificatesDialog(card.box, self._client, self).exec()

    def settings(self, card: TonieboxCardWidget) -> None:
        TonieboxSettingsDialog(card.box, self._client, self).exec()
        # z. B. den API-Zugriff (toniebox.api_access) neu anzeigen
        card.reload()

    def delete(self, card: TonieboxCardWidget) -> None:
        box = card.box
        answer = QMessageBox.question(self, "Bestätige Löschvorgang", f"Möchtest du die Toniebox {box.name} wirklich löschen?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.statusMessage.emit(f"Toniebox {box.id} wird aus TeddyCloud gelöscht …")

        def done() -> None:
            self.statusMessage.emit(f"Toniebox {box.id} erfolgreich aus TeddyCloud gelöscht!")
            self.boxesChanged.emit()
            self.load()

        def failed(message: str) -> None:
            self.statusMessage.emit(message)
            QMessageBox.warning(self, "Löschen fehlgeschlagen", f"Löschen der Toniebox {box.id} fehlgeschlagen: {message}")

        self._client.remove_toniebox(box.id, done, failed)
