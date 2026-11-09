"""Einfache Wiedergabeleiste für Tonie-Inhalte (QtMultimedia mit FFmpeg-Backend)."""

from PyQt6.QtCore import QSize, Qt, QUrl
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSlider, QToolButton, QWidget

from .icons import icon


def _format_time(ms: int) -> str:
    seconds = max(ms, 0) // 1000
    hours, rest = divmod(seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"


class AudioPlayerBar(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pending_start_ms = 0

        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.player.positionChanged.connect(self._on_position)
        self.player.durationChanged.connect(self._on_duration)
        self.player.playbackStateChanged.connect(self._on_state)
        self.player.mediaStatusChanged.connect(self._on_media_status)
        self.player.errorOccurred.connect(self._on_error)

        self.play_button = QToolButton(self)
        self.play_button.setIconSize(QSize(22, 22))
        self.play_button.setIcon(icon("play"))
        self.play_button.clicked.connect(self.toggle)
        self.stop_button = QToolButton(self)
        self.stop_button.setIconSize(QSize(22, 22))
        self.stop_button.setIcon(icon("stop"))
        self.stop_button.setToolTip("Stopp")
        self.stop_button.clicked.connect(self.stop)
        self.title_label = QLabel(self)
        self.title_label.setMinimumWidth(200)
        self.slider = QSlider(Qt.Orientation.Horizontal, self)
        self.slider.sliderMoved.connect(self.player.setPosition)
        self.time_label = QLabel("0:00 / 0:00", self)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.addWidget(self.play_button)
        layout.addWidget(self.stop_button)
        layout.addWidget(self.title_label)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.time_label)
        self.setVisible(False)

    def play(self, url: QUrl, title: str, start_seconds: int = 0) -> None:
        self.setVisible(True)
        self.title_label.setText(title)
        self.title_label.setToolTip(title)
        self._pending_start_ms = start_seconds * 1000
        if self.player.source() == url and self._pending_start_ms:
            self.player.setPosition(self._pending_start_ms)
            self._pending_start_ms = 0
        else:
            self.player.setSource(url)
        self.player.play()

    def toggle(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def stop(self) -> None:
        self.player.stop()
        self.setVisible(False)

    def _on_media_status(self, status: QMediaPlayer.MediaStatus) -> None:
        # Sprung zu einem Track erst, wenn das Medium geladen ist
        if self._pending_start_ms and status in (
            QMediaPlayer.MediaStatus.LoadedMedia,
            QMediaPlayer.MediaStatus.BufferedMedia,
        ):
            self.player.setPosition(self._pending_start_ms)
            self._pending_start_ms = 0

    def _on_position(self, position: int) -> None:
        if not self.slider.isSliderDown():
            self.slider.setValue(position)
        self.time_label.setText(f"{_format_time(position)} / {_format_time(self.player.duration())}")

    def _on_duration(self, duration: int) -> None:
        self.slider.setRange(0, duration)

    def _on_state(self, state: QMediaPlayer.PlaybackState) -> None:
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.play_button.setIcon(icon("pause" if playing else "play"))
        self.play_button.setToolTip("Pause" if playing else "Abspielen")

    def _on_error(self, _error: QMediaPlayer.Error, message: str) -> None:
        self.title_label.setText(f"Fehler bei der Wiedergabe: {message}")
