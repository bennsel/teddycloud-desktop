import logging
import sys
from importlib.metadata import PackageNotFoundError, version

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow, QMessageBox, QStackedWidget, QVBoxLayout, QWidget

from .audio_player import AudioPlayerBar
from .custom_models_page import CustomModelsPage
from .encoder_page import EncoderPage
from .images import ImageCache
from .settings import APP_NAME, SETTINGS_NAME, AppSettings, SettingsDialog
from .tap_page import TapPage
from .teddycloud import TeddyCloudClient
from .tonieboxes_page import TonieboxesPage
from .tonies_page import ToniesPage

PROJECT_URL = "https://github.com/bennsel/teddycloud-desktop"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(900, 600)

        self.app_settings = AppSettings()
        self.client = TeddyCloudClient(self)
        self.client.requestFailed.connect(self.on_request_failed)
        self._apply_settings()
        self.images = ImageCache(self.client, self)

        # Zentrales Widget: Startseite bzw. Tonie-Übersicht, darunter die Wiedergabeleiste
        self.welcome_label = QLabel(
            "Willkommen!\n\nÜber „Tonies → Tonies“ werden die Tonies und über „Tonieboxen → Tonieboxen“ "
            "die Tonieboxen der TeddyCloud angezeigt.",
            self,
        )
        self.welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.player = AudioPlayerBar(self)
        self.tonies_page = ToniesPage(self.client, self.images, self.player, self.app_settings, self)
        self.tonies_page.statusMessage.connect(self.statusBar().showMessage)

        self.tonieboxes_page = TonieboxesPage(self.client, self.images, self)
        self.tonieboxes_page.statusMessage.connect(self.statusBar().showMessage)
        self.tonieboxes_page.showTonieRequested.connect(self.show_tonie)

        self.stack = QStackedWidget(self)
        self.stack.addWidget(self.welcome_label)
        self.stack.addWidget(self.tonies_page)
        self.stack.addWidget(self.tonieboxes_page)

        self.encoder_page = EncoderPage(self.client, self.images, self)
        self.encoder_page.statusMessage.connect(self.statusBar().showMessage)
        self.stack.addWidget(self.encoder_page)

        self.custom_models_page = CustomModelsPage(self.client, self.images, self)
        self.custom_models_page.statusMessage.connect(self.statusBar().showMessage)
        self.stack.addWidget(self.custom_models_page)

        self.tap_page = TapPage(self.client, self.app_settings, self)
        self.tap_page.statusMessage.connect(self.statusBar().showMessage)
        self.stack.addWidget(self.tap_page)

        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.stack, 1)
        layout.addWidget(self.player)
        self.setCentralWidget(central)

        self._create_menus()
        self.statusBar().showMessage("Bereit")

    def _create_menus(self) -> None:
        menu_bar = self.menuBar()

        # Datei
        file_menu = menu_bar.addMenu("&Datei")
        settings_action = QAction("&Einstellungen …", self)
        settings_action.setShortcut(QKeySequence("Ctrl+,"))
        # Unter macOS verschiebt Qt den Eintrag automatisch ins Programm-Menü
        settings_action.setMenuRole(QAction.MenuRole.PreferencesRole)
        settings_action.triggered.connect(self.open_settings)
        file_menu.addAction(settings_action)
        file_menu.addSeparator()
        quit_action = QAction("&Beenden", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.setMenuRole(QAction.MenuRole.QuitRole)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # Tonies
        tonies_menu = menu_bar.addMenu("&Tonies")
        tonies_action = QAction("&Tonies", self)
        tonies_action.setShortcut(QKeySequence("Ctrl+T"))
        tonies_action.triggered.connect(self.show_tonies)
        tonies_menu.addAction(tonies_action)
        encoder_action = QAction("&Audio Encoder", self)
        encoder_action.setShortcut(QKeySequence("Ctrl+E"))
        encoder_action.triggered.connect(self.show_encoder)
        tonies_menu.addAction(encoder_action)
        custom_models_action = QAction("&Custom-Modelle", self)
        custom_models_action.setShortcut(QKeySequence("Ctrl+M"))
        custom_models_action.triggered.connect(self.show_custom_models)
        tonies_menu.addAction(custom_models_action)
        tap_action = QAction("TeddyAudio &Playlists", self)
        tap_action.setShortcut(QKeySequence("Ctrl+P"))
        tap_action.triggered.connect(self.show_taps)
        tonies_menu.addAction(tap_action)

        # Tonieboxen
        tonieboxes_menu = menu_bar.addMenu("Tonie&boxen")
        tonieboxes_action = QAction("Tonie&boxen", self)
        tonieboxes_action.setShortcut(QKeySequence("Ctrl+B"))
        tonieboxes_action.triggered.connect(self.show_tonieboxes)
        tonieboxes_menu.addAction(tonieboxes_action)

        # Bearbeiten
        edit_menu = menu_bar.addMenu("&Bearbeiten")
        copy_action = QAction("&Kopieren", self)
        copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        copy_action.setToolTip("Ausgewählte (oder alle angezeigten) Tonies als Text kopieren")
        copy_action.triggered.connect(self.copy_selection)
        edit_menu.addAction(copy_action)
        select_all_action = QAction("&Alles auswählen", self)
        select_all_action.setShortcut(QKeySequence.StandardKey.SelectAll)
        select_all_action.triggered.connect(self.select_all)
        edit_menu.addAction(select_all_action)

        # Ansicht
        view_menu = menu_bar.addMenu("&Ansicht")
        refresh_action = QAction("&Aktualisieren", self)
        refresh_action.setShortcut(QKeySequence.StandardKey.Refresh)
        refresh_action.triggered.connect(self.refresh)
        view_menu.addAction(refresh_action)
        filter_action = QAction("&Filter anzeigen", self)
        filter_action.setCheckable(True)
        filter_action.setShortcut(QKeySequence("Ctrl+F"))
        filter_action.toggled.connect(self.toggle_filter)
        self.tonies_page.filter_button.toggled.connect(filter_action.setChecked)
        view_menu.addAction(filter_action)

        # Hilfe
        help_menu = menu_bar.addMenu("&Hilfe")
        about_action = QAction(f"Ü&ber {APP_NAME}", self)
        about_action.setMenuRole(QAction.MenuRole.AboutRole)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        about_qt_action = QAction("Über &Qt", self)
        about_qt_action.setMenuRole(QAction.MenuRole.AboutQtRole)
        about_qt_action.triggered.connect(QApplication.aboutQt)
        help_menu.addAction(about_qt_action)

    def _apply_settings(self) -> None:
        self.client.endpoint = self.app_settings.endpoint
        self.client.timeout_seconds = self.app_settings.timeout_seconds
        self.client.username = self.app_settings.username
        self.client.password = self.app_settings.password

    def _ensure_endpoint(self) -> bool:
        if not self.app_settings.endpoint:
            QMessageBox.information(self, "Kein Endpunkt", "Bitte zuerst den TeddyCloud-Endpunkt in den Einstellungen festlegen.")
            self.open_settings()
        return bool(self.app_settings.endpoint)

    def open_settings(self) -> None:
        if SettingsDialog(self.app_settings, self).exec():
            self._apply_settings()
            self.statusBar().showMessage(f"TeddyCloud-Endpunkt: {self.app_settings.endpoint}")
            if self.stack.currentWidget() is not self.welcome_label:
                self.stack.currentWidget().load()

    def show_tonies(self) -> None:
        if not self._ensure_endpoint():
            return
        self.stack.setCurrentWidget(self.tonies_page)
        self.tonies_page.load()

    def show_tonie(self, overlay: str, ruid: str) -> None:
        """Zuletzt gespielten Tonie einer Toniebox in der Tonie-Übersicht zeigen."""
        self.stack.setCurrentWidget(self.tonies_page)
        self.tonies_page.show_tonie(overlay, ruid)

    def show_tonieboxes(self) -> None:
        if not self._ensure_endpoint():
            return
        self.stack.setCurrentWidget(self.tonieboxes_page)
        self.tonieboxes_page.load()

    def show_encoder(self) -> None:
        if not self._ensure_endpoint():
            return
        self.stack.setCurrentWidget(self.encoder_page)
        self.encoder_page.load()

    def show_taps(self) -> None:
        if not self._ensure_endpoint():
            return
        self.stack.setCurrentWidget(self.tap_page)
        self.tap_page.load()

    def show_custom_models(self) -> None:
        if not self._ensure_endpoint():
            return
        self.stack.setCurrentWidget(self.custom_models_page)
        self.custom_models_page.load()

    def refresh(self) -> None:
        # Jede Seite hat load(); auf der Startseite stattdessen die Tonies öffnen
        if self.stack.currentWidget() is self.welcome_label:
            self.show_tonies()
        else:
            self.stack.currentWidget().load()

    def toggle_filter(self, visible: bool) -> None:
        if visible and self.stack.currentWidget() is not self.tonies_page:
            self.show_tonies()
        self.tonies_page.filter_button.setChecked(visible)

    def select_all(self) -> None:
        # In Eingabefeldern greift Strg+A weiterhin als Textauswahl, da das Feld das Kürzel zuerst erhält
        if self.stack.currentWidget() is self.tonies_page:
            self.tonies_page.select_all()

    def copy_selection(self) -> None:
        if self.stack.currentWidget() is self.tonies_page:
            QApplication.clipboard().setText(self.tonies_page.selection_as_text())

    def on_request_failed(self, message: str) -> None:
        self.statusBar().showMessage("Fehler beim Abruf der TeddyCloud")
        QMessageBox.warning(self, "TeddyCloud", message)

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            f"Über {APP_NAME}",
            f"<h3>{APP_NAME} {app_version()}</h3>"
            "<p>Plattformübergreifende PyQt6-Oberfläche zum Verwalten der Tonies und Tonieboxen einer "
            '<a href="https://github.com/toniebox-reverse-engineering/teddycloud">TeddyCloud</a>.</p>'
            f'<p><a href="{PROJECT_URL}">{PROJECT_URL}</a></p>'
            "<p>Lizenz: GNU General Public License v3.0 oder später.</p>"
            "<p>Kein offizielles Produkt der tonies GmbH. „Toniebox“ und „Tonie“ sind Marken der tonies GmbH.</p>",
        )


def app_version() -> str:
    try:
        return version("teddycloud-desktop")
    except PackageNotFoundError:
        return ""


def main() -> None:
    # Fehler und Fortschritt (z. B. beim Audio Encoder) zusätzlich auf der Konsole ausgeben
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = QApplication(sys.argv)
    app.setOrganizationName(SETTINGS_NAME)
    app.setApplicationName(SETTINGS_NAME)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
