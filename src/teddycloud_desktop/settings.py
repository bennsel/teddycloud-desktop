"""Persistente Einstellungen und der Einstellungsdialog."""

import logging

import keyring
from PyQt6.QtCore import QSettings, QUrl
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QMessageBox, QSpinBox, QWidget

from .teddycloud import normalize_endpoint

APP_NAME = "TeddyCloud Desktop"
# Organisation und Anwendung für QSettings, außerdem Dienstname im Schlüsselbund
SETTINGS_NAME = "teddycloud-desktop"
KEYRING_ACCOUNT = "basic-auth"

ENDPOINT_KEY = "teddycloud/endpoint"
TIMEOUT_KEY = "teddycloud/timeout_seconds"
USERNAME_KEY = "teddycloud/username"
PASSWORD_KEY = "teddycloud/password"
OVERLAY_KEY = "tonies/overlay"
DEFAULT_TIMEOUT_SECONDS = 10

log = logging.getLogger("teddycloud_desktop")


class AppSettings:
    """Speichert die Einstellungen plattformabhängig über QSettings (Registry, plist bzw. ini-Datei).

    Das Passwort liegt im Schlüsselbund des Systems (Windows-Anmeldeinformationsverwaltung, macOS-Schlüsselbund,
    Secret Service unter Linux). Nur wenn keiner verfügbar ist, landet es unverschlüsselt in QSettings.
    """

    def __init__(self, settings: QSettings | None = None) -> None:
        self._settings = settings or QSettings(SETTINGS_NAME, SETTINGS_NAME)
        self._password: str | None = None
        self.keyring_available = True

    @property
    def endpoint(self) -> str:
        return self._settings.value(ENDPOINT_KEY, "", type=str)

    @endpoint.setter
    def endpoint(self, value: str) -> None:
        self._settings.setValue(ENDPOINT_KEY, normalize_endpoint(value))

    @property
    def timeout_seconds(self) -> int:
        return self._settings.value(TIMEOUT_KEY, DEFAULT_TIMEOUT_SECONDS, type=int)

    @timeout_seconds.setter
    def timeout_seconds(self, value: int) -> None:
        self._settings.setValue(TIMEOUT_KEY, value)

    @property
    def username(self) -> str:
        return self._settings.value(USERNAME_KEY, "", type=str)

    @username.setter
    def username(self, value: str) -> None:
        self._settings.setValue(USERNAME_KEY, value)

    @property
    def password(self) -> str:
        if self._password is None:
            self._password = self._load_password()
        return self._password

    @password.setter
    def password(self, value: str) -> None:
        self._password = value
        if self._store_in_keyring(value):
            self._settings.remove(PASSWORD_KEY)
        else:
            # Achtung: QSettings speichert das Passwort unverschlüsselt
            self._settings.setValue(PASSWORD_KEY, value)

    def _load_password(self) -> str:
        fallback = self._settings.value(PASSWORD_KEY, "", type=str)
        try:
            stored = keyring.get_password(SETTINGS_NAME, KEYRING_ACCOUNT)
        except Exception as error:  # je nach Backend z. B. NoKeyringError oder D-Bus-Fehler
            log.warning("Schlüsselbund nicht verfügbar: %s", error)
            self.keyring_available = False
            return fallback
        # Ein unverschlüsselt gespeichertes Passwort in den Schlüsselbund übernehmen. Es ist immer das neuere,
        # denn es wird nur geschrieben, wenn der Schlüsselbund beim Speichern nicht verfügbar war.
        if fallback and self._store_in_keyring(fallback):
            self._settings.remove(PASSWORD_KEY)
            return fallback
        return stored or fallback

    def _store_in_keyring(self, value: str) -> bool:
        try:
            if value:
                keyring.set_password(SETTINGS_NAME, KEYRING_ACCOUNT, value)
            elif keyring.get_password(SETTINGS_NAME, KEYRING_ACCOUNT) is not None:
                keyring.delete_password(SETTINGS_NAME, KEYRING_ACCOUNT)
        except Exception as error:
            log.warning("Passwort konnte nicht im Schlüsselbund gespeichert werden: %s", error)
            self.keyring_available = False
            return False
        self.keyring_available = True
        return True

    # Zuletzt gewählte Toniebox (deren ID) in der Tonie-Übersicht
    @property
    def overlay(self) -> str:
        return self._settings.value(OVERLAY_KEY, "", type=str)

    @overlay.setter
    def overlay(self, value: str) -> None:
        self._settings.setValue(OVERLAY_KEY, value)


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings

        self.setWindowTitle("Einstellungen")
        self.setMinimumWidth(450)

        self.endpoint_edit = QLineEdit(settings.endpoint, self)
        self.endpoint_edit.setPlaceholderText("http://teddycloud.local")

        self.timeout_spin = QSpinBox(self)
        self.timeout_spin.setRange(1, 300)
        self.timeout_spin.setSuffix(" s")
        self.timeout_spin.setValue(settings.timeout_seconds)

        self.username_edit = QLineEdit(settings.username, self)
        self.username_edit.setPlaceholderText("optional")

        self.password_edit = QLineEdit(settings.password, self)
        self.password_edit.setPlaceholderText("optional")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QFormLayout(self)
        layout.addRow("TeddyCloud-Endpunkt:", self.endpoint_edit)
        layout.addRow("Zeitlimit für Anfragen:", self.timeout_spin)
        layout.addRow("Basic-Auth-Benutzer:", self.username_edit)
        layout.addRow("Basic-Auth-Passwort:", self.password_edit)
        if not settings.keyring_available:
            hint = QLabel(
                "Kein Schlüsselbund verfügbar: Das Passwort wird unverschlüsselt in den Einstellungen gespeichert.", self
            )
            hint.setWordWrap(True)
            layout.addRow(hint)
        layout.addRow(buttons)

    def accept(self) -> None:
        endpoint = normalize_endpoint(self.endpoint_edit.text())
        url = QUrl(endpoint)
        if not url.isValid() or url.scheme() not in ("http", "https") or not url.host():
            QMessageBox.warning(
                self,
                "Ungültiger Endpunkt",
                "Bitte eine gültige Adresse angeben, z. B. http://teddycloud.local oder http://192.168.1.10:8080",
            )
            return

        username = self.username_edit.text().strip()
        password = self.password_edit.text()
        if password and not username:
            QMessageBox.warning(self, "Benutzer fehlt", "Für Basic Auth muss zum Passwort auch ein Benutzer angegeben werden.")
            return

        self._settings.endpoint = endpoint
        self._settings.timeout_seconds = self.timeout_spin.value()
        self._settings.username = username
        self._settings.password = password
        super().accept()
