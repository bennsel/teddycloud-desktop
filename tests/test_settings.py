"""Passwortablage von AppSettings mit einem gefälschten keyring-Modul und einer ini-Datei."""

from pathlib import Path

import pytest
from PyQt6.QtCore import QSettings

from teddycloud_desktop import settings as settings_module
from teddycloud_desktop.settings import KEYRING_ACCOUNT, PASSWORD_KEY, SETTINGS_NAME, AppSettings


class FakeKeyring:
    def __init__(self, fail: bool = False) -> None:
        self.store: dict[tuple[str, str], str] = {}
        self.fail = fail

    def _check(self) -> None:
        if self.fail:
            raise RuntimeError("kein Schlüsselbund")

    def get_password(self, service: str, account: str) -> str | None:
        self._check()
        return self.store.get((service, account))

    def set_password(self, service: str, account: str, value: str) -> None:
        self._check()
        self.store[(service, account)] = value

    def delete_password(self, service: str, account: str) -> None:
        self._check()
        del self.store[(service, account)]


@pytest.fixture
def ini_path(tmp_path: Path) -> str:
    return str(tmp_path / "settings.ini")


def _qsettings(path: str) -> QSettings:
    return QSettings(path, QSettings.Format.IniFormat)


def _install(monkeypatch: pytest.MonkeyPatch, fail: bool = False) -> FakeKeyring:
    fake = FakeKeyring(fail)
    monkeypatch.setattr(settings_module, "keyring", fake)
    return fake


def test_plain_values_and_endpoint_normalization(ini_path: str) -> None:
    app = AppSettings(_qsettings(ini_path))
    assert app.timeout_seconds == settings_module.DEFAULT_TIMEOUT_SECONDS
    app.endpoint = " teddycloud.local/ "
    app.timeout_seconds = 30
    app.username = "user"
    app.overlay = "box1"
    reloaded = AppSettings(_qsettings(ini_path))
    assert (reloaded.endpoint, reloaded.timeout_seconds, reloaded.username, reloaded.overlay) == (
        "http://teddycloud.local",
        30,
        "user",
        "box1",
    )


def test_password_goes_to_keyring(monkeypatch: pytest.MonkeyPatch, ini_path: str) -> None:
    fake = _install(monkeypatch)
    qs = _qsettings(ini_path)
    app = AppSettings(qs)
    app.password = "geheim"
    assert fake.store == {(SETTINGS_NAME, KEYRING_ACCOUNT): "geheim"}
    assert not qs.contains(PASSWORD_KEY)
    assert app.keyring_available
    assert AppSettings(_qsettings(ini_path)).password == "geheim"

    app.password = ""
    assert fake.store == {}


def test_password_falls_back_to_plaintext_without_keyring(monkeypatch: pytest.MonkeyPatch, ini_path: str) -> None:
    _install(monkeypatch, fail=True)
    qs = _qsettings(ini_path)
    app = AppSettings(qs)
    app.password = "geheim"
    assert not app.keyring_available
    assert qs.value(PASSWORD_KEY) == "geheim"

    reloaded = AppSettings(_qsettings(ini_path))
    assert reloaded.password == "geheim"
    assert not reloaded.keyring_available


def test_legacy_plaintext_password_is_migrated(monkeypatch: pytest.MonkeyPatch, ini_path: str) -> None:
    legacy = _qsettings(ini_path)
    legacy.setValue(PASSWORD_KEY, "alt")
    legacy.sync()
    fake = _install(monkeypatch)

    qs = _qsettings(ini_path)
    app = AppSettings(qs)
    assert app.password == "alt"
    assert fake.store == {(SETTINGS_NAME, KEYRING_ACCOUNT): "alt"}
    assert not qs.contains(PASSWORD_KEY)
    assert app.keyring_available


def test_plaintext_password_replaces_older_keyring_entry(monkeypatch: pytest.MonkeyPatch, ini_path: str) -> None:
    # Klartext entsteht nur, wenn der Schlüsselbund beim Speichern ausfiel, und ist daher der neuere Wert
    fake = _install(monkeypatch)
    fake.store[(SETTINGS_NAME, KEYRING_ACCOUNT)] = "alt"
    qs = _qsettings(ini_path)
    qs.setValue(PASSWORD_KEY, "neu")

    app = AppSettings(qs)
    assert app.password == "neu"
    assert fake.store == {(SETTINGS_NAME, KEYRING_ACCOUNT): "neu"}
    assert not qs.contains(PASSWORD_KEY)
