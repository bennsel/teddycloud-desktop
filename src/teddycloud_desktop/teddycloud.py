"""Zugriff auf die REST-API einer TeddyCloud-Instanz.

Die Endpunkte und Abläufe entsprechen denen der TeddyCloud-Weboberfläche (/web/tonies).
"""

import base64
import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote, urlencode

from PyQt6.QtCore import QByteArray, QFile, QIODevice, QObject, QUrl, pyqtSignal
from PyQt6.QtNetwork import QHttpMultiPart, QHttpPart, QNetworkAccessManager, QNetworkReply, QNetworkRequest

# Alle Tonies (Tags), die der TeddyCloud bekannt sind
TAG_INDEX_PATH = "/api/getTagIndex"
# Ein einzelner Tonie, z. B. nach einer Änderung
TAG_INFO_PATH = "/api/getTagInfo"
# Durchsucht den Tonie-Katalog (tonies.json), maximal 18 Treffer
SEARCH_PATH = "/api/toniesJsonSearch"
# Registrierte Tonieboxen, deren ID als "overlay" verwendet wird
BOXES_PATH = "/api/getBoxes"
# Verzeichnisinhalt, z. B. der Bibliothek (special=library)
FILE_INDEX_PATH = "/api/fileIndexV2"
# Ändert Eigenschaften (source, tonie_model, live, nocloud, hide) eines Tonies
CONTENT_JSON_SET_PATH = "/content/json/set/"
SETTING_GET_PATH = "/api/settings/get/"
SETTING_SET_PATH = "/api/settings/set/"
SETTING_RESET_PATH = "/api/settings/reset/"
SETTINGS_INDEX_PATH = "/api/settings/getIndex"
# Schreibt geänderte Einstellungen in die Konfigurationsdatei der TeddyCloud
TRIGGER_WRITE_CONFIG_PATH = "/api/triggerWriteConfig"
# Entfernt die Toniebox (deren Overlay) aus der TeddyCloud
REMOVE_OVERLAY_PATH = "/api/settings/removeOverlay"
UPLOAD_CERT_PATH = "/api/uploadCert"
# Ordner in der Bibliothek anlegen (Body: Pfad)
DIR_CREATE_PATH = "/api/dirCreate"
# Custom-Modelle in tonies.custom.json (Body jeweils JSON, Antwort "OK" bzw. Fehlertext mit HTTP 4xx)
CUSTOM_MODELS_PATH = "/api/toniesCustomJson"
CUSTOM_UPSERT_PATH = "/api/toniesCustomJsonUpsert"
CUSTOM_DELETE_PATH = "/api/toniesCustomJsonDelete"
CUSTOM_RENAME_PATH = "/api/toniesCustomJsonRename"
TONIES_JSON_PATH = "/api/toniesJson"
FILE_UPLOAD_PATH = "/api/fileUpload"
# Body: Pfad der Datei; Antwort "OK"
FILE_DELETE_PATH = "/api/fileDelete"
# Body: source=…&target=… (URL-kodiert); Antwort "OK"
FILE_MOVE_PATH = "/api/fileMove"
# Dateien der Bibliothek direkt lesen (wie /library/<pfad> in der Weboberfläche)
LIBRARY_FILES_PATH = "/library"
# Nimmt 48 kHz Stereo 16 Bit PCM (je Datei ein Teil = ein Kapitel) entgegen und kodiert daraus eine TAF-Datei
PCM_UPLOAD_PATH = "/api/pcmUpload"
# Farbvarianten der Tonieboxen mit Bild
BOX_MODELS_PATHS = ("/api/tonieboxesJson", "/api/tonieboxesCustomJson")

# Werte von internal.toniebox_firmware.boxIC
BOX_VERSIONS = {"1": "CC3200", "2": "CC3235", "3": "ESP32", "4": "TB2"}
# internal.last_ruid, wenn noch kein Tonie gespielt wurde
NO_RUID = "ffffffffffffffff"

UNKNOWN_PICTURE = "/img_unknown.png"

log = logging.getLogger("teddycloud_desktop")

OnError = Callable[[str], None] | None


@dataclass(frozen=True)
class TonieInfo:
    model: str = ""
    series: str = ""
    episode: str = ""
    language: str = ""
    picture: str = ""
    tracks: tuple[str, ...] = ()

    @property
    def title(self) -> str:
        return self.series + (f" - {self.episode}" if self.episode else "")


@dataclass(frozen=True)
class TonieCard:
    ruid: str
    uid: str = ""
    type: str = "tag"
    valid: bool = False
    exists: bool = False
    claimed: bool = False
    hide: bool = False
    live: bool = False
    nocloud: bool = False
    has_cloud_auth: bool = False
    source: str = ""
    audio_url: str = ""
    download_trigger_url: str = ""
    tonie_info: TonieInfo = TonieInfo()
    # Nur gesetzt, wenn der Inhalt zu einem anderen Tonie gehört als die Figur
    source_info: TonieInfo | None = None
    track_seconds: tuple[int, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    @property
    def picture(self) -> str:
        return self.tonie_info.picture.strip() or UNKNOWN_PICTURE

    @property
    def shows_alternative_source(self) -> bool:
        """Entspricht der Logik der Weboberfläche: zugewiesener Inhalt weicht vom Modell ab."""
        return self.source_info is not None and self.source_info.title != self.tonie_info.title

    @property
    def is_playable(self) -> bool:
        return self.valid or self.source.startswith("http")

    @property
    def display_tracks(self) -> tuple[str, ...]:
        info = self.source_info if self.shows_alternative_source else self.tonie_info
        return info.tracks


@dataclass(frozen=True)
class Toniebox:
    id: str
    name: str
    common_name: str = ""
    model: str = ""


@dataclass(frozen=True)
class BoxModel:
    """Farbvariante einer Toniebox aus tonieboxes.json."""

    id: str
    name: str
    img_src: str = ""
    # [x, y, scale] wie in der Weboberfläche: CSS scale(scale) translateX(x px) translateY(y px)
    crop: tuple[float, float, float] | None = None


@dataclass
class SettingOption:
    """Eine Einstellung aus /api/settings/getIndex."""

    id: str
    label: str
    description: str
    type: str  # bool, int, uint, hex, string, float
    value: Any
    overlayed: bool = False
    level: int = 1
    minimum: float | None = None
    maximum: float | None = None


def format_box_id(box_id: str) -> str:
    """MAC-Adresse lesbar machen: aabbccddeeff -> AA:BB:CC:DD:EE:FF (wie in der Weboberfläche)."""
    return re.sub(r"(.{2})(?=.)", r"\1:", box_id).upper()


def setting_to_text(value: Any) -> str:
    """Wert so senden, wie ihn die TeddyCloud erwartet (bool als true/false)."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


@dataclass(frozen=True)
class LibraryEntry:
    name: str
    is_dir: bool
    size: int = 0
    tonie_info: TonieInfo | None = None
    is_taf: bool = False
    # Aus dem TAF-Header; nötig für die Audio-Zuordnung von Custom-Modellen
    audio_id: str = ""
    hash: str = ""
    date: int = 0  # Änderungszeit (Unix-Zeit)


def normalize_endpoint(endpoint: str) -> str:
    """Entfernt Leerzeichen und abschließende Schrägstriche und ergänzt bei Bedarf http://."""
    endpoint = endpoint.strip().rstrip("/")
    if endpoint and "://" not in endpoint:
        endpoint = f"http://{endpoint}"
    return endpoint


def basic_auth_header(username: str, password: str) -> bytes:
    credentials = base64.b64encode(f"{username}:{password}".encode())
    return b"Basic " + credentials


def natural_key(text: str) -> list[Any]:
    """Sortierschlüssel, bei dem "Folge 2" vor "Folge 10" kommt."""
    return [int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", text or "")]


def sort_cards(cards: list[TonieCard]) -> list[TonieCard]:
    return sorted(cards, key=lambda c: (natural_key(c.tonie_info.series), natural_key(c.tonie_info.episode)))


def parse_tonie_info(info: Any) -> TonieInfo:
    if not isinstance(info, dict):
        return TonieInfo()
    return TonieInfo(
        model=info.get("model") or "",
        series=info.get("series") or "",
        episode=info.get("episode") or "",
        language=info.get("language") or "",
        picture=info.get("picture") or "",
        tracks=tuple(info.get("tracks") or ()),
    )


def parse_tag(tag: dict[str, Any]) -> TonieCard:
    if not isinstance(tag, dict) or not tag.get("ruid"):
        raise ValueError("Tag ohne 'ruid'")
    return TonieCard(
        ruid=tag["ruid"],
        uid=tag.get("uid") or "",
        type=tag.get("type") or "tag",
        valid=bool(tag.get("valid")),
        exists=bool(tag.get("exists")),
        claimed=bool(tag.get("claimed")),
        hide=bool(tag.get("hide")),
        live=bool(tag.get("live")),
        nocloud=bool(tag.get("nocloud")),
        has_cloud_auth=bool(tag.get("hasCloudAuth")),
        source=tag.get("source") or "",
        audio_url=tag.get("audioUrl") or "",
        download_trigger_url=tag.get("downloadTriggerUrl") or "",
        tonie_info=parse_tonie_info(tag.get("tonieInfo")),
        source_info=parse_tonie_info(tag["sourceInfo"]) if "sourceInfo" in tag else None,
        track_seconds=tuple(int(s) for s in tag.get("trackSeconds") or ()),
        raw=tag,
    )


def parse_tag_index(data: Any) -> list[TonieCard]:
    """Wandelt die Antwort von /api/getTagIndex um (alle Typen, doppelte RUIDs entfernt)."""
    if not isinstance(data, dict) or not isinstance(data.get("tags"), list):
        raise ValueError("Antwort enthält keine Liste 'tags'")
    cards: dict[str, TonieCard] = {}
    for tag in data["tags"]:
        card = parse_tag(tag)
        cards.setdefault(card.ruid, card)
    return list(cards.values())


def parse_tag_info(data: Any) -> TonieCard:
    if not isinstance(data, dict):
        raise ValueError("Antwort enthält kein 'tagInfo'")
    return parse_tag(data.get("tagInfo"))


def parse_search(data: Any) -> list[TonieInfo]:
    """Wandelt die Antwort von /api/toniesJsonSearch um."""
    if not isinstance(data, list):
        raise ValueError("Antwort ist keine Liste")
    return [parse_tonie_info(info) for info in data]


def parse_boxes(data: Any) -> list[Toniebox]:
    if not isinstance(data, dict) or not isinstance(data.get("boxes"), list):
        raise ValueError("Antwort enthält keine Liste 'boxes'")
    return [
        Toniebox(
            id=box.get("ID") or "",
            name=box.get("boxName") or box.get("commonName") or "",
            common_name=box.get("commonName") or "",
            model=box.get("boxModel") or "",
        )
        for box in data["boxes"]
    ]


def parse_box_models(data: Any) -> list[BoxModel]:
    if not isinstance(data, list):
        raise ValueError("Antwort ist keine Liste")
    models = []
    for item in data:
        crop = item.get("crop")
        models.append(
            BoxModel(
                id=str(item.get("id") or ""),
                name=item.get("name") or "",
                img_src=item.get("img_src") or "",
                crop=tuple(float(v) for v in crop[:3]) if isinstance(crop, list) and len(crop) >= 3 else None,
            )
        )
    return models


def parse_settings_index(data: Any) -> list[SettingOption]:
    if not isinstance(data, dict) or not isinstance(data.get("options"), list):
        raise ValueError("Antwort enthält keine Liste 'options'")
    return [
        SettingOption(
            id=option.get("ID") or "",
            label=option.get("label") or option.get("ID") or "",
            description=option.get("description") or "",
            type=option.get("type") or "string",
            value=option.get("value"),
            overlayed=bool(option.get("overlayed")),
            level=int(option.get("level") or 1),
            minimum=option.get("min"),
            maximum=option.get("max"),
        )
        for option in data["options"]
    ]


def parse_file_index(data: Any) -> list[LibraryEntry]:
    if not isinstance(data, dict) or not isinstance(data.get("files"), list):
        raise ValueError("Antwort enthält keine Liste 'files'")
    entries = [
        LibraryEntry(
            name=entry.get("name") or "",
            is_dir=bool(entry.get("isDir")),
            size=int(entry.get("size") or 0),
            tonie_info=parse_tonie_info(entry["tonieInfo"]) if "tonieInfo" in entry else None,
            is_taf="tafHeader" in entry,
            audio_id=str((entry.get("tafHeader") or {}).get("audioId") or ""),
            hash=str((entry.get("tafHeader") or {}).get("sha1Hash") or ""),
            date=int(entry.get("date") or 0),
        )
        for entry in data["files"]
        if entry.get("name") not in (".", "..")
    ]
    return sorted(entries, key=lambda e: (not e.is_dir, natural_key(e.name)))


def _parse_json_bytes(data: bytes) -> Any:
    return json.loads(data.decode("utf-8"))


class TeddyCloudClient(QObject):
    """Asynchroner HTTP-Client, damit die Oberfläche während der Anfragen bedienbar bleibt.

    Alle Methoden rufen nach Abschluss `on_success` bzw. `on_error` auf. Ohne `on_error`
    wird stattdessen das Signal `requestFailed` ausgelöst.
    """

    requestFailed = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._manager = QNetworkAccessManager(self)
        self.endpoint = ""
        self.timeout_seconds = 10
        # Basic Auth wird nur verwendet, wenn ein Benutzer gesetzt ist
        self.username = ""
        self.password = ""

    # ---------- URLs ----------

    def url(self, path: str, query: dict[str, str] | None = None) -> QUrl:
        """Absolute URL zu einem Pfad der TeddyCloud; absolute URLs bleiben unverändert."""
        if re.match(r"^[a-z][a-z0-9+.-]*://", path, re.IGNORECASE):
            url = QUrl(path)
        else:
            url = QUrl(self.endpoint + (path if path.startswith("/") else f"/{path}"))
        if query:
            existing = url.query()
            encoded = urlencode(query, quote_via=quote)
            url.setQuery(f"{existing}&{encoded}" if existing else encoded)
        return url

    def media_url(self, path: str) -> QUrl:
        """URL für den Mediaplayer, der keine eigenen Header setzen kann: Zugangsdaten in der URL."""
        url = self.url(path)
        if self.username and self._is_own_host(url):
            url.setUserName(self.username)
            url.setPassword(self.password)
        return url

    def _is_own_host(self, url: QUrl) -> bool:
        """Gehört die URL zur eigenen TeddyCloud? Nur dann werden Zugangsdaten mitgeschickt."""
        own = QUrl(self.endpoint)

        def port(u: QUrl) -> int:
            # https://host und https://host:443 sind derselbe Server
            return u.port(443 if u.scheme().lower() == "https" else 80)

        return url.host().lower() == own.host().lower() and port(url) == port(own)

    @staticmethod
    def _overlay_query(overlay: str) -> dict[str, str]:
        return {"overlay": overlay} if overlay else {}

    # ---------- Basisanfragen ----------

    def _request(self, url: QUrl) -> QNetworkRequest:
        request = QNetworkRequest(url)
        request.setTransferTimeout(self.timeout_seconds * 1000)
        # Zugangsdaten nur an die eigene TeddyCloud senden, nicht an externe Bildserver
        if self.username and self._is_own_host(url):
            request.setRawHeader(b"Authorization", basic_auth_header(self.username, self.password))
        return request

    def get_bytes(
        self, url: QUrl, on_success: Callable[[bytes], None], on_error: OnError = None, timeout: bool = True
    ) -> QNetworkReply | None:
        if not self.endpoint:
            self._fail("Es ist kein TeddyCloud-Endpunkt konfiguriert.", on_error)
            return None
        request = self._request(url)
        if not timeout:
            request.setTransferTimeout(0)
        reply = self._manager.get(request)
        reply.finished.connect(lambda: self._finish(reply, on_success, on_error))
        return reply

    def get_json(
        self,
        path: str,
        query: dict[str, str] | None,
        parser: Callable[[Any], Any],
        on_success: Callable[[Any], None],
        on_error: OnError = None,
    ) -> None:
        def handle(data: bytes) -> None:
            try:
                result = parser(_parse_json_bytes(data))
            except (ValueError, TypeError, AttributeError, KeyError) as exc:
                self._fail(f"Unerwartete Antwort von {path}: {exc}", on_error)
                return
            on_success(result)

        self.get_bytes(self.url(path, query), handle, on_error)

    def post_text(
        self,
        path: str,
        body: str,
        query: dict[str, str] | None,
        on_success: Callable[[bytes], None],
        on_error: OnError = None,
    ) -> None:
        if not self.endpoint:
            self._fail("Es ist kein TeddyCloud-Endpunkt konfiguriert.", on_error)
            return
        request = self._request(self.url(path, query))
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "text/plain")
        reply = self._manager.post(request, QByteArray(body.encode("utf-8")))
        reply.finished.connect(lambda: self._finish(reply, on_success, on_error))

    def _post_multipart(self, request: QNetworkRequest, multipart: QHttpMultiPart) -> QNetworkReply:
        """Sendet multipart/form-data so, dass der HTTP-Server der TeddyCloud (CycloneTCP) es versteht.

        Qt schreibt den Boundary in Anführungszeichen (boundary="…"). CycloneTCP übernimmt die
        Anführungszeichen mit, findet die Trennzeilen im Body nie und bleibt beim Einlesen hängen.
        Deshalb wird der Header hier ohne Anführungszeichen gesetzt.
        """
        boundary = bytes(multipart.boundary()).decode("ascii")
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, f"multipart/form-data; boundary={boundary}")
        reply = self._manager.post(request, multipart)
        multipart.setParent(reply)
        return reply

    def _finish(self, reply: QNetworkReply, on_success: Callable[[bytes], None], on_error: OnError) -> None:
        reply.deleteLater()
        if reply.error() != QNetworkReply.NetworkError.NoError:
            # Zugangsdaten nicht in Fehlermeldungen anzeigen
            url = reply.url().toString(QUrl.UrlFormattingOption.RemoveUserInfo)
            self._fail(f"Anfrage an {url} fehlgeschlagen: {reply.errorString()}", on_error)
            return
        on_success(bytes(reply.readAll()))

    def _fail(self, message: str, on_error: OnError) -> None:
        log.warning(message)
        if on_error is not None:
            on_error(message)
        else:
            self.requestFailed.emit(message)

    # ---------- TeddyCloud-Funktionen ----------

    def fetch_tags(self, overlay: str, on_success: Callable[[list[TonieCard]], None], on_error: OnError = None) -> None:
        self.get_json(TAG_INDEX_PATH, self._overlay_query(overlay), parse_tag_index, on_success, on_error)

    def fetch_tag(self, ruid: str, overlay: str, on_success: Callable[[TonieCard], None], on_error: OnError = None) -> None:
        query = {"ruid": ruid, **self._overlay_query(overlay)}
        self.get_json(TAG_INFO_PATH, query, parse_tag_info, on_success, on_error)

    def set_content(
        self, ruid: str, overlay: str, key: str, value: str | bool, on_success: Callable[[], None], on_error: OnError = None
    ) -> None:
        """Setzt eine Eigenschaft (source, tonie_model, live, nocloud, hide) eines Tonies."""
        text = str(value).lower() if isinstance(value, bool) else quote(value, safe="")
        self.post_text(
            CONTENT_JSON_SET_PATH + ruid, f"{key}={text}", self._overlay_query(overlay), lambda _: on_success(), on_error
        )

    def search_models(
        self, term: str, on_success: Callable[[list[TonieInfo]], None], on_error: OnError = None, model_only: bool = False
    ) -> None:
        # Der Begriff wird in Modellnummer, Serie und Episode gesucht
        query = {
            "searchModel": term,
            "searchSeries": "" if model_only else term,
            "searchEpisode": "" if model_only else term,
        }
        self.get_json(SEARCH_PATH, query, parse_search, on_success, on_error)

    def fetch_boxes(self, on_success: Callable[[list[Toniebox]], None], on_error: OnError = None) -> None:
        self.get_json(BOXES_PATH, None, parse_boxes, on_success, on_error)

    def fetch_setting(self, key: str, overlay: str, on_success: Callable[[str], None], on_error: OnError = None) -> None:
        self.get_bytes(
            self.url(SETTING_GET_PATH + key, self._overlay_query(overlay)),
            lambda data: on_success(data.decode("utf-8", errors="replace").strip()),
            on_error,
        )

    def fetch_library(
        self, path: str, on_success: Callable[[list[LibraryEntry]], None], on_error: OnError = None, special: str = "library"
    ) -> None:
        """Ordnerinhalt der Bibliothek (special="library") bzw. der eigenen Bilder (special="custom_img")."""
        self.get_json(FILE_INDEX_PATH, {"path": path, "special": special}, parse_file_index, on_success, on_error)

    def create_library_directory(
        self, path: str, on_success: Callable[[], None], on_error: OnError = None, special: str = "library"
    ) -> None:
        """Legt den Ordner `path` (relativ zur Bibliothek, z. B. "/Hörspiele/Neu") an."""

        def check(data: bytes) -> None:
            text = data.decode("utf-8", errors="replace").strip()
            if text == "OK":
                on_success()
            else:
                self._fail(f'Erstellen des Verzeichnisses "{path}" fehlgeschlagen: {text}', on_error)

        self.post_text(DIR_CREATE_PATH, path, {"special": special}, check, on_error)

    # ---------- Custom-Modelle (tonies.custom.json) ----------

    def fetch_json(self, path: str, on_success: Callable[[Any], None], on_error: OnError = None) -> None:
        """Beliebiges JSON laden, z. B. /api/toniesCustomJson oder /api/toniesJson."""
        self.get_json(path, None, lambda data: data, on_success, on_error)

    def post_json(self, path: str, payload: Any, on_success: Callable[[], None], on_error: OnError = None) -> None:
        if not self.endpoint:
            self._fail("Es ist kein TeddyCloud-Endpunkt konfiguriert.", on_error)
            return
        request = self._request(self.url(path))
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
        body = QByteArray(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        reply = self._manager.post(request, body)

        def finished() -> None:
            # Bei HTTP 4xx steht die genaue Begründung der TeddyCloud im Body (z. B. "Target model already exists")
            if reply.error() != QNetworkReply.NetworkError.NoError:
                detail = bytes(reply.readAll()).decode("utf-8", errors="replace").strip()
                reply.deleteLater()
                self._fail(detail or reply.errorString(), on_error)
                return
            reply.deleteLater()
            on_success()

        reply.finished.connect(finished)

    def upsert_custom_model(self, payload: dict[str, Any], on_success: Callable[[], None], on_error: OnError = None) -> None:
        self.post_json(CUSTOM_UPSERT_PATH, payload, on_success, on_error)

    def delete_custom_models(self, models: list[str], on_success: Callable[[], None], on_error: OnError = None) -> None:
        self.post_json(CUSTOM_DELETE_PATH, {"models": models}, on_success, on_error)

    def rename_custom_model(
        self, from_model: str, to_model: str, update_content_json: bool, on_success: Callable[[], None], on_error: OnError = None
    ) -> None:
        """Benennt ein Modell um; mit `update_content_json` werden verknüpfte Tonies automatisch umgestellt."""
        payload = {"fromModel": from_model, "toModel": to_model, "updateContentJson": update_content_json}
        self.post_json(CUSTOM_RENAME_PATH, payload, on_success, on_error)

    def upload_custom_image(self, file_path: str, folder: str, on_success: Callable[[], None], on_error: OnError = None) -> None:
        """Lädt ein Bild in den Ordner `folder` von custom_img hoch."""
        if not self.endpoint:
            self._fail("Es ist kein TeddyCloud-Endpunkt konfiguriert.", on_error)
            return
        with open(file_path, "rb") as file:
            content = file.read()
        name = file_path.replace("\\", "/").rsplit("/", 1)[-1].replace('"', "'")
        multipart = QHttpMultiPart(QHttpMultiPart.ContentType.FormDataType)
        part = QHttpPart()
        part.setHeader(QNetworkRequest.KnownHeaders.ContentDispositionHeader, f'form-data; name="file"; filename="{name}"')
        part.setBody(QByteArray(content))
        multipart.append(part)
        request = self._request(self.url(FILE_UPLOAD_PATH, {"path": folder or "/", "special": "custom_img"}))
        reply = self._post_multipart(request, multipart)
        reply.finished.connect(lambda: self._finish(reply, lambda _d: on_success(), on_error))

    # ---------- Dateien der Bibliothek (z. B. TeddyAudio Playlists) ----------

    def upload_library_file(
        self,
        data: bytes,
        file_name: str,
        folder: str,
        on_success: Callable[[], None],
        on_error: OnError = None,
        special: str = "library",
    ) -> None:
        """Legt eine Datei mit dem Inhalt `data` im Ordner `folder` an (vorhandene wird überschrieben)."""
        if not self.endpoint:
            self._fail("Es ist kein TeddyCloud-Endpunkt konfiguriert.", on_error)
            return
        safe_name = file_name.replace('"', "'")
        multipart = QHttpMultiPart(QHttpMultiPart.ContentType.FormDataType)
        part = QHttpPart()
        part.setHeader(
            QNetworkRequest.KnownHeaders.ContentDispositionHeader, f'form-data; name="{safe_name}"; filename="{safe_name}"'
        )
        part.setBody(QByteArray(data))
        multipart.append(part)
        request = self._request(self.url(FILE_UPLOAD_PATH, {"path": folder or "/", "special": special}))
        reply = self._post_multipart(request, multipart)
        reply.finished.connect(lambda: self._finish(reply, lambda _d: on_success(), on_error))

    def download_to_file(
        self,
        url: QUrl,
        target: str,
        on_progress: Callable[[int, int], None],
        on_success: Callable[[], None],
        on_error: OnError = None,
    ) -> QNetworkReply | None:
        """Lädt `url` direkt in die Datei `target` (ohne Zeitlimit, ohne alles im Speicher zu halten)."""
        if not self.endpoint:
            self._fail("Es ist kein TeddyCloud-Endpunkt konfiguriert.", on_error)
            return None
        request = self._request(url)
        request.setTransferTimeout(0)
        file = open(target, "wb")
        reply = self._manager.get(request)
        reply.readyRead.connect(lambda: file.write(bytes(reply.readAll())))
        reply.downloadProgress.connect(on_progress)

        def finished() -> None:
            file.write(bytes(reply.readAll()))
            file.close()
            reply.deleteLater()
            if reply.error() != QNetworkReply.NetworkError.NoError:
                shown = reply.url().toString(QUrl.UrlFormattingOption.RemoveUserInfo)
                self._fail(f"Anfrage an {shown} fehlgeschlagen: {reply.errorString()}", on_error)
            else:
                on_success()

        reply.finished.connect(finished)
        return reply

    def fetch_library_file(self, path: str, on_success: Callable[[bytes], None], on_error: OnError = None) -> None:
        """Inhalt einer Bibliotheksdatei, wie die Weboberfläche über /library/<pfad>."""
        self.get_bytes(self.url(LIBRARY_FILES_PATH + "/" + path.lstrip("/")), on_success, on_error)

    def _post_expect_ok(self, path: str, body: str, query: dict[str, str], what: str, on_success, on_error) -> None:
        def check(data: bytes) -> None:
            text = data.decode("utf-8", errors="replace").strip()
            if text == "OK":
                on_success()
            else:
                self._fail(f"{what} fehlgeschlagen: {text}", on_error)

        self.post_text(path, body, query, check, on_error)

    def delete_library_file(
        self, path: str, on_success: Callable[[], None], on_error: OnError = None, special: str = "library"
    ) -> None:
        self._post_expect_ok(FILE_DELETE_PATH, path, {"special": special}, f'Löschen von "{path}"', on_success, on_error)

    def move_library_file(
        self, source: str, target: str, on_success: Callable[[], None], on_error: OnError = None, special: str = "library"
    ) -> None:
        """Verschiebt bzw. benennt eine Datei um (Pfade relativ zur Bibliothek)."""
        body = urlencode({"source": source, "target": target}, quote_via=quote)
        self._post_expect_ok(FILE_MOVE_PATH, body, {"special": special}, f'Verschieben von "{source}"', on_success, on_error)

    def upload_pcm(
        self,
        parts: list[tuple[str, str]],
        taf_name: str,
        path: str,
        audio_id: int,
        on_progress: Callable[[int, int], None],
        on_success: Callable[[], None],
        on_error: OnError = None,
    ) -> QNetworkReply | None:
        """Lädt PCM-Dateien (Anzeigename, lokaler Pfad) hoch; die TeddyCloud kodiert sie zu `taf_name`.

        Die Daten werden direkt aus den Dateien gestreamt, damit lange Hörspiele nicht im Speicher liegen.
        """
        if not self.endpoint:
            self._fail("Es ist kein TeddyCloud-Endpunkt konfiguriert.", on_error)
            return None
        multipart = QHttpMultiPart(QHttpMultiPart.ContentType.FormDataType)
        for index, (name, pcm_path) in enumerate(parts):
            device = QFile(pcm_path, multipart)
            if not device.open(QIODevice.OpenModeFlag.ReadOnly):
                self._fail(f"Datei {pcm_path} konnte nicht gelesen werden.", on_error)
                return None
            part = QHttpPart()
            part.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "audio/pcm")
            safe_name = name.replace('"', "'")
            part.setHeader(
                QNetworkRequest.KnownHeaders.ContentDispositionHeader,
                f'form-data; name="{safe_name}"; filename="pcmData.{index}.pcm"',
            )
            part.setBodyDevice(device)
            multipart.append(part)

        query = {"name": taf_name, "audioId": str(audio_id), "path": path, "special": "library"}
        request = self._request(self.url(PCM_UPLOAD_PATH, query))
        # Das Kodieren auf dem Server kann dauern, daher kein Zeitlimit
        request.setTransferTimeout(0)
        reply = self._post_multipart(request, multipart)
        reply.uploadProgress.connect(on_progress)
        reply.finished.connect(lambda: self._finish(reply, lambda _d: on_success(), on_error))
        return reply

    # ---------- Tonieboxen und Einstellungen ----------

    def fetch_box_models(self, on_success: Callable[[list[BoxModel]], None]) -> None:
        """Lädt tonieboxes.json und tonieboxes.custom.json; fehlt eine Datei, bleibt sie leer."""
        results: dict[str, list[BoxModel]] = {}

        def collect(path: str, models: list[BoxModel]) -> None:
            results[path] = models
            if len(results) == len(BOX_MODELS_PATHS):
                on_success([model for p in BOX_MODELS_PATHS for model in results[p]])

        for path in BOX_MODELS_PATHS:
            self.get_json(path, None, parse_box_models, lambda m, p=path: collect(p, m), lambda _e, p=path: collect(p, []))

    def fetch_settings_index(
        self, overlay: str, on_success: Callable[[list[SettingOption]], None], on_error: OnError = None
    ) -> None:
        self.get_json(SETTINGS_INDEX_PATH, self._overlay_query(overlay), parse_settings_index, on_success, on_error)

    def set_setting(
        self,
        key: str,
        value: Any,
        overlay: str,
        on_success: Callable[[], None],
        on_error: OnError = None,
        reset: bool = False,
    ) -> None:
        """Setzt eine Einstellung; mit `reset` wird der Overlay-Wert entfernt (zurück zum TeddyCloud-Wert)."""

        def check(data: bytes) -> None:
            # Die TeddyCloud antwortet auch bei Fehlern mit HTTP 200, aber mit "ERROR" im Text
            if data.strip() == b"ERROR":
                self._fail(f"Die TeddyCloud hat den Wert für {key} abgelehnt.", on_error)
            else:
                on_success()

        path = (SETTING_RESET_PATH if reset else SETTING_SET_PATH) + key
        self.post_text(path, "" if reset else setting_to_text(value), self._overlay_query(overlay), check, on_error)

    def trigger_write_config(self, on_success: Callable[[], None] | None = None, on_error: OnError = None) -> None:
        self.get_bytes(self.url(TRIGGER_WRITE_CONFIG_PATH), lambda _d: on_success() if on_success else None, on_error)

    def remove_toniebox(self, box_id: str, on_success: Callable[[], None], on_error: OnError = None) -> None:
        def check(data: bytes) -> None:
            if data.strip() == b"OK":
                on_success()
            else:
                self._fail(f"Löschen der Toniebox {box_id} fehlgeschlagen", on_error)

        self.post_text(REMOVE_OVERLAY_PATH, "", {"overlay": box_id}, check, on_error)

    def upload_certificate(self, file_path: str, overlay: str, on_success: Callable[[], None], on_error: OnError = None) -> None:
        """Lädt eine Zertifikatsdatei (ca.der, client.der, private.der) als multipart/form-data hoch."""
        if not self.endpoint:
            self._fail("Es ist kein TeddyCloud-Endpunkt konfiguriert.", on_error)
            return
        with open(file_path, "rb") as file:
            content = file.read()
        multipart = QHttpMultiPart(QHttpMultiPart.ContentType.FormDataType)
        part = QHttpPart()
        name = file_path.replace("\\", "/").rsplit("/", 1)[-1]
        part.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/x-x509-ca-cert")
        part.setHeader(QNetworkRequest.KnownHeaders.ContentDispositionHeader, f'form-data; name="filename"; filename="{name}"')
        part.setBody(QByteArray(content))
        multipart.append(part)
        reply = self._post_multipart(self._request(self.url(UPLOAD_CERT_PATH, self._overlay_query(overlay))), multipart)
        reply.finished.connect(lambda: self._finish(reply, lambda _d: on_success(), on_error))
