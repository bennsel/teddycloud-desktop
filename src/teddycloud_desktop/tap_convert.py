"""TeddyAudio Playlist (TAP) in der GUI in eine TAF umwandeln, statt die TeddyCloud das per FFmpeg tun zu lassen.

Ablauf: die Dateien der TAP herunterladen, lokal mit QAudioDecoder (FFmpeg in Qt) zu 48 kHz Stereo PCM
dekodieren und per /api/pcmUpload genau an den `filepath` der TAP hochladen (vorhandene TAF wird
überschrieben). Liegt dort eine gültige TAF, verwendet die TeddyCloud sie für die TAP direkt
(CT_SOURCE_TAP_CACHED) und erzeugt nichts mehr selbst. Jede Umwandlung bekommt eine neue Audio-ID, die
auch in die .tap geschrieben wird, damit Tonieboxen mit der alten Fassung im Cache neu laden.
"""

import logging
import os
import shutil
import tempfile
from dataclasses import replace
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtNetwork import QNetworkReply

from .encoder_custom import find_taf_hash
from .encoder_page import PcmDecoder, new_audio_id
from .tap import LIBRARY_PREFIX, TeddyAudioPlaylist, split_taf_filepath
from .teddycloud import LIBRARY_FILES_PATH, LibraryEntry, TeddyCloudClient

log = logging.getLogger("teddycloud_desktop")
CONTENT_PREFIX = "content://"


def source_path(filepath: str) -> str:
    """Pfad bzw. URL, unter dem eine Datei der TAP heruntergeladen werden kann; leer, wenn nicht unterstützt."""
    filepath = filepath.strip()
    if filepath.startswith(LIBRARY_PREFIX):
        return LIBRARY_FILES_PATH + "/" + filepath[len(LIBRARY_PREFIX) :].lstrip("/")
    if filepath.startswith(CONTENT_PREFIX):
        return "/content/" + filepath[len(CONTENT_PREFIX) :].lstrip("/")
    if filepath.startswith(("http://", "https://")):
        return filepath
    return ""


def conversion_problems(tap: TeddyAudioPlaylist) -> list[str]:
    problems = []
    if not tap.filepath.strip():
        problems.append("Die TAP hat keinen Dateipfad für die TAF.")
    if not tap.files:
        problems.append("Die TAP enthält keine Dateien.")
    for index, file in enumerate(tap.files, start=1):
        if not source_path(file.filepath):
            problems.append(
                f"Datei {index}: „{file.filepath}“ wird nicht unterstützt (erwartet lib://, content:// oder http(s)://)."
            )
    return problems


class TapConverter(QObject):
    """Wandelt eine TAP Schritt für Schritt um; meldet Fortschritt (0…1000, -1 = unbestimmt)."""

    progress = pyqtSignal(str, int)
    finished = pyqtSignal(object, str)  # aktualisierte TAP, Erfolgsmeldung
    failed = pyqtSignal(str)

    def __init__(
        self,
        client: TeddyCloudClient,
        tap: TeddyAudioPlaylist,
        tap_folder: str,
        tap_file_name: str,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._client = client
        # Neue Audio-ID für die neue TAF; wird nach dem Erfolg auch in die .tap geschrieben
        self._tap = replace(tap, audio_id=new_audio_id())
        self._tap_folder = tap_folder
        self._tap_file_name = tap_file_name
        self._taf_folder, base = split_taf_filepath(tap.filepath)
        self._taf_name = base + ".taf"
        self._temp_dir = ""
        self._pcm_files: list[str] = []
        self._reply: QNetworkReply | None = None
        self._decoder: PcmDecoder | None = None
        self._cancelled = False

    @property
    def target(self) -> str:
        return self._tap.filepath

    def start(self) -> None:
        problems = conversion_problems(self._tap)
        if problems:
            self.failed.emit("\n".join(problems))
            return
        self._temp_dir = tempfile.mkdtemp(prefix="teddycloud_desktop_tap_")
        log.info("Wandle TAP %s in %s um (Audio-ID %s)", self._tap_file_name, self._tap.filepath, self._tap.audio_id)
        self._next_file()

    def cancel(self) -> None:
        self._cancelled = True
        if self._decoder is not None:
            self._decoder.stop()
        if self._reply is not None:
            self._reply.abort()
        self._cleanup()

    # ---------- 1. Herunterladen und dekodieren ----------

    def _share(self, index: int, part: float) -> int:
        """Fortschritt: Herunterladen/Dekodieren belegt 0…700, der Upload 700…1000."""
        return int((index + part) / len(self._tap.files) * 700)

    def _next_file(self) -> None:
        if self._cancelled:
            return
        index = len(self._pcm_files)
        if index == len(self._tap.files):
            self._ensure_folder()
            return
        file = self._tap.files[index]
        label = file.name or Path(file.filepath).name
        suffix = Path(file.filepath).suffix or ".audio"
        source = os.path.join(self._temp_dir, f"quelle_{index}{suffix}")
        pcm = os.path.join(self._temp_dir, f"pcm_{index}.pcm")

        def downloaded() -> None:
            self._reply = None
            if self._cancelled:
                return
            self.progress.emit(f"Datei {index + 1}/{len(self._tap.files)} dekodieren: {label}", self._share(index, 0.5))
            decoder = PcmDecoder(source, pcm, self)
            decoder.progress.connect(
                lambda share: self.progress.emit(
                    f"Datei {index + 1}/{len(self._tap.files)} dekodieren: {label}", self._share(index, 0.5 + share / 2)
                )
            )
            decoder.finished.connect(lambda _p: decoded())
            decoder.failed.connect(
                lambda message: self._fail(f"Datei {index + 1} ({label}) konnte nicht dekodiert werden: {message}")
            )
            self._decoder = decoder
            decoder.start()

        def decoded() -> None:
            self._decoder = None
            try:
                os.remove(source)  # Quelle wird nicht mehr gebraucht
            except OSError:
                pass
            self._pcm_files.append(pcm)
            self._next_file()

        def progress(received: int, total: int) -> None:
            part = received / total / 2 if total > 0 else 0
            self.progress.emit(f"Datei {index + 1}/{len(self._tap.files)} laden: {label}", self._share(index, part))

        self.progress.emit(f"Datei {index + 1}/{len(self._tap.files)} laden: {label}", self._share(index, 0))
        self._reply = self._client.download_to_file(
            self._client.url(source_path(file.filepath)),
            source,
            progress,
            downloaded,
            lambda message: self._fail(f"Datei {index + 1} ({file.filepath}) konnte nicht geladen werden: {message}"),
        )

    # ---------- 2. Zielordner sicherstellen ----------

    def _ensure_folder(self) -> None:
        """/api/pcmUpload legt keine Ordner an; fehlende Ordner des TAF-Pfads der Reihe nach anlegen."""
        parts = [p for p in self._taf_folder.strip("/").split("/") if p]
        paths = ["/" + "/".join(parts[: i + 1]) for i in range(len(parts))]

        def check(index: int) -> None:
            if index == len(paths):
                self._upload()
                return
            path = paths[index]
            parent = paths[index - 1] if index else "/"
            name = parts[index]

            def listed(entries: list[LibraryEntry]) -> None:
                if any(e.is_dir and e.name == name for e in entries):
                    check(index + 1)
                else:
                    self.progress.emit(f"Lege Ordner {path} an …", 700)
                    self._client.create_library_directory(path, lambda: check(index + 1), self._fail)

            self._client.fetch_library(parent, listed, self._fail)

        check(0)

    # ---------- 3. Hochladen und prüfen ----------

    def _upload(self) -> None:
        if self._cancelled:
            return
        parts = [(f.name or Path(f.filepath).name, pcm) for f, pcm in zip(self._tap.files, self._pcm_files, strict=True)]

        def progress(sent: int, total: int) -> None:
            if total > 0:
                if sent < total:
                    self.progress.emit(f"Lade {len(parts)} Kapitel hoch …", 700 + int(sent / total * 300))
                else:
                    self.progress.emit(f"TeddyCloud schreibt {self._taf_name} …", -1)

        self.progress.emit(f"Lade {len(parts)} Kapitel hoch …", 700)
        self._reply = self._client.upload_pcm(
            parts,
            self._taf_name,
            self._taf_folder,
            self._tap.audio_id,
            progress,
            self._verify,
            lambda message: self._fail(f"Hochladen fehlgeschlagen: {message}"),
        )

    def _verify(self) -> None:
        self._reply = None
        self.progress.emit("Prüfe die neue TAF-Datei …", -1)

        def listed(entries: list[LibraryEntry]) -> None:
            if not find_taf_hash(entries, self._taf_name, self._tap.audio_id):
                self._fail(f"Die TAF-Datei {self._tap.filepath} mit Audio-ID {self._tap.audio_id} wurde nicht gefunden.")
                return
            self._save_tap()

        self._client.fetch_library(self._taf_folder, listed, self._fail)

    def _save_tap(self) -> None:
        """Neue Audio-ID in die .tap übernehmen (dieselbe Datei wird überschrieben)."""
        self.progress.emit(f"Aktualisiere {self._tap_file_name} …", -1)
        done = f"TAF erstellt: {self._tap.filepath} ({len(self._tap.files)} Kapitel, Audio-ID {self._tap.audio_id})."

        def saved() -> None:
            self._cleanup()
            log.info(done)
            self.finished.emit(self._tap, done)

        def failed(message: str) -> None:
            # Die TAF liegt trotzdem am richtigen Ort und wird von der TeddyCloud verwendet
            self._cleanup()
            self.finished.emit(
                self._tap, f"{done}\nDie Audio-ID konnte nicht in {self._tap_file_name} gespeichert werden: {message}"
            )

        self._client.upload_library_file(self._tap.to_bytes(), self._tap_file_name, self._tap_folder, saved, failed)

    # ---------- Abschluss ----------

    def _fail(self, message: str) -> None:
        if self._cancelled:
            return
        log.error(message)
        self._cancelled = True
        self._cleanup()
        self.failed.emit(message)

    def _cleanup(self) -> None:
        if self._temp_dir:
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            self._temp_dir = ""
