"""Lädt Tonie-Bilder asynchron und hält sie im Speicher vor."""

from collections import deque

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QImage

from .teddycloud import TeddyCloudClient

# Qt öffnet höchstens 6 Verbindungen je Server und lässt weitere Anfragen warten; das Zeitlimit einer
# Anfrage läuft dabei aber schon. Deshalb stellt der Cache Bilder selbst in eine Warteschlange und
# startet nur wenige gleichzeitig, damit das Zeitlimit nur für laufende Downloads gilt.
MAX_PARALLEL_DOWNLOADS = 4
MAX_ATTEMPTS = 2


class ImageCache(QObject):
    """Jedes Bild wird nur einmal geladen; wartende Kacheln erhalten es über `imageReady`."""

    imageReady = pyqtSignal(str, QImage)

    def __init__(self, client: TeddyCloudClient, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._client = client
        self._images: dict[str, QImage] = {}
        self._pending: set[str] = set()  # wartend oder gerade geladen
        self._queue: deque[str] = deque()
        self._attempts: dict[str, int] = {}
        self._running = 0

    def clear(self) -> None:
        """Geladene Bilder verwerfen und noch nicht gestartete Downloads streichen."""
        self._images.clear()
        for path in self._queue:
            self._pending.discard(path)
        self._queue.clear()

    def get(self, path: str) -> QImage | None:
        """Liefert das Bild sofort, falls bekannt; sonst wird es geladen und später gemeldet."""
        if not path:
            return None
        if path in self._images:
            return self._images[path]
        if path not in self._pending:
            self._pending.add(path)
            self._attempts[path] = 0
            self._queue.append(path)
            self._start_next()
        return None

    def cached(self, path: str) -> QImage | None:
        return self._images.get(path)

    def _start_next(self) -> None:
        while self._running < MAX_PARALLEL_DOWNLOADS and self._queue:
            path = self._queue.popleft()
            self._running += 1
            self._attempts[path] += 1
            self._client.get_bytes(
                self._client.url(path),
                lambda data, p=path: self._loaded(p, data),
                lambda message, p=path: self._failed(p, message),
            )

    def _loaded(self, path: str, data: bytes) -> None:
        self._running -= 1
        self._pending.discard(path)
        self._attempts.pop(path, None)
        image = QImage.fromData(data)
        if not image.isNull():
            self._images[path] = image
            self.imageReady.emit(path, image)
        self._start_next()

    def _failed(self, path: str, _message: str) -> None:
        self._running -= 1
        if self._attempts.get(path, MAX_ATTEMPTS) < MAX_ATTEMPTS:
            # z. B. Zeitüberschreitung, weil die TeddyCloud das Bild erst in ihren Cache lädt: hinten anstellen
            self._queue.append(path)
        else:
            self._pending.discard(path)
            self._attempts.pop(path, None)
        self._start_next()
