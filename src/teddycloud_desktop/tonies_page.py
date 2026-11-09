"""Kachelübersicht aller Tonies, nachgebaut nach /web/tonies der TeddyCloud-Weboberfläche."""

from collections.abc import Callable
from datetime import datetime

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import export
from .audio_player import AudioPlayerBar
from .flow_layout import FlowLayout
from .icons import icon
from .images import ImageCache
from .settings import AppSettings
from .teddycloud import NO_RUID, TeddyCloudClient, Toniebox, TonieCard, sort_cards
from .tonie_card import CARD_STYLESHEET, TonieCardWidget
from .tonie_dialogs import EditTonieDialog, TonieInfoDialog, confirm_hide
from .tonies_filter import ToniesFilter, default_language, visible_tonies

PAGE_SIZES = [24, 48, 96, 0]  # 0 = alle
DEFAULT_CONTENT_DIR_LABEL = "TeddyCloud Standard-Inhaltsverzeichnis"


class TriStateCombo(QComboBox):
    """Auswahl egal / ja / nein für ein Flag."""

    def __init__(self, yes: str, no: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.addItem("egal", None)
        self.addItem(yes, True)
        self.addItem(no, False)

    def value(self) -> bool | None:
        return self.currentData()


class ToniesPage(QWidget):
    statusMessage = pyqtSignal(str)

    def __init__(
        self,
        client: TeddyCloudClient,
        images: ImageCache,
        player: AudioPlayerBar,
        settings: AppSettings,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._client = client
        self._images = images
        self._player = player
        self._settings = settings

        self._all_cards: list[TonieCard] = []
        self._cards: list[TonieCard] = []  # sichtbare, sortierte Tonies
        self._filtered: list[TonieCard] = []
        self._widgets: dict[str, TonieCardWidget] = {}
        self._selected: set[str] = set()
        self._boxes: list[Toniebox] = []
        self._last_played: dict[str, list[str]] = {}
        self._overlay = settings.overlay
        self._default_language = ""
        self._cloud_available = True
        self._page = 0

        self.setStyleSheet(CARD_STYLESHEET)
        self._build_ui()

    # ---------- Oberfläche ----------

    def _build_ui(self) -> None:
        title = QLabel("<h2>Tonies</h2>", self)
        self.overlay_combo = QComboBox(self)
        self.overlay_combo.setMinimumWidth(220)
        self.overlay_combo.setToolTip("Inhaltsverzeichnis / Toniebox")
        self.overlay_combo.currentIndexChanged.connect(self._on_overlay_changed)
        refresh_button = QPushButton(icon("refresh"), "Aktualisieren", self)
        refresh_button.clicked.connect(self.load)
        header = QHBoxLayout()
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(QLabel("Toniebox:", self))
        header.addWidget(self.overlay_combo)
        header.addWidget(refresh_button)

        # Filter, über den Button "Filter" ein- und ausklappbar
        self.filter_button = QPushButton("Filter", self)
        self.filter_button.setCheckable(True)
        self.filter_box = QGroupBox(self)
        self.filter_box.setVisible(False)
        self.filter_button.toggled.connect(self.filter_box.setVisible)
        self.filter_content = QWidget(self.filter_box)
        self.search_edit = QLineEdit(self.filter_content)
        self.search_edit.setPlaceholderText("Serie, Episode, Modell, UID oder Quelle")
        self.series_edit = QLineEdit(self.filter_content)
        self.episode_edit = QLineEdit(self.filter_content)
        self.language_combo = QComboBox(self.filter_content)
        self.valid_combo = TriStateCombo("gültig", "ungültig", self.filter_content)
        self.exists_combo = TriStateCombo("vorhanden", "nicht vorhanden", self.filter_content)
        self.live_combo = TriStateCombo("live", "nicht live", self.filter_content)
        self.nocloud_combo = TriStateCombo("Cloud gesperrt", "Cloud erlaubt", self.filter_content)
        self.cloud_auth_combo = TriStateCombo("mit Cloud-Auth", "ohne Cloud-Auth", self.filter_content)
        self.last_played_box = QCheckBox("Nur zuletzt auf einer Toniebox gespielte", self.filter_content)
        reset_button = QPushButton("Filter zurücksetzen", self.filter_content)
        reset_button.clicked.connect(self.reset_filters)
        for edit in (self.search_edit, self.series_edit, self.episode_edit):
            edit.setClearButtonEnabled(True)
            edit.textChanged.connect(self._apply_filters)
        for combo in (
            self.language_combo,
            self.valid_combo,
            self.exists_combo,
            self.live_combo,
            self.nocloud_combo,
            self.cloud_auth_combo,
        ):
            combo.currentIndexChanged.connect(self._apply_filters)
        self.last_played_box.toggled.connect(self._apply_filters)

        grid = QGridLayout(self.filter_content)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.addWidget(QLabel("Suche:"), 0, 0)
        grid.addWidget(self.search_edit, 0, 1, 1, 3)
        grid.addWidget(QLabel("Serie:"), 1, 0)
        grid.addWidget(self.series_edit, 1, 1)
        grid.addWidget(QLabel("Episode:"), 1, 2)
        grid.addWidget(self.episode_edit, 1, 3)
        grid.addWidget(QLabel("Sprache:"), 2, 0)
        grid.addWidget(self.language_combo, 2, 1)
        grid.addWidget(QLabel("Gültig:"), 2, 2)
        grid.addWidget(self.valid_combo, 2, 3)
        grid.addWidget(QLabel("Inhalt:"), 3, 0)
        grid.addWidget(self.exists_combo, 3, 1)
        grid.addWidget(QLabel("Live:"), 3, 2)
        grid.addWidget(self.live_combo, 3, 3)
        grid.addWidget(QLabel("Cloud:"), 4, 0)
        grid.addWidget(self.nocloud_combo, 4, 1)
        grid.addWidget(QLabel("Cloud-Auth:"), 4, 2)
        grid.addWidget(self.cloud_auth_combo, 4, 3)
        grid.addWidget(self.last_played_box, 5, 0, 1, 3)
        grid.addWidget(reset_button, 5, 3)
        filter_layout = QVBoxLayout(self.filter_box)
        filter_layout.addWidget(self.filter_content)

        # Auswahlmodus und Sammelaktionen
        self.select_button = QPushButton(icon("select"), "Auswählen", self)
        self.select_button.setCheckable(True)
        self.select_button.setToolTip("Auswahlmodus aktivieren")
        self.select_button.toggled.connect(self.set_selection_mode)
        self.selected_label = QLabel(self)
        self.select_all_button = QPushButton("Alle auswählen", self)
        self.select_all_button.clicked.connect(self.select_all)
        self.unselect_button = QPushButton("Auswahl aufheben", self)
        self.unselect_button.clicked.connect(self.unselect_all)
        self.actions_button = QToolButton(self)
        self.actions_button.setText("Aktionen")
        self.actions_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.actions_button.setMenu(self._build_actions_menu())
        self._selection_widgets = (self.selected_label, self.select_all_button, self.unselect_button, self.actions_button)
        for widget in self._selection_widgets:
            widget.setVisible(False)

        # Seiten
        self.count_label = QLabel(self)
        self.page_size_combo = QComboBox(self)
        for size in PAGE_SIZES:
            self.page_size_combo.addItem(f"{size} Tonies/Seite" if size else "Zeige alle", size)
        self.page_size_combo.setCurrentIndex(1)
        self.page_size_combo.currentIndexChanged.connect(self._on_page_size_changed)
        self.prev_button = QToolButton(self)
        self.prev_button.setText("‹")
        self.prev_button.clicked.connect(lambda: self._go_to_page(self._page - 1))
        self.page_label = QLabel(self)
        self.next_button = QToolButton(self)
        self.next_button.setText("›")
        self.next_button.clicked.connect(lambda: self._go_to_page(self._page + 1))

        toolbar = QHBoxLayout()
        toolbar.addWidget(self.filter_button)
        toolbar.addWidget(self.select_button)
        for widget in self._selection_widgets:
            toolbar.addWidget(widget)
        toolbar.addStretch(1)
        toolbar.addWidget(self.count_label)
        toolbar.addWidget(self.page_size_combo)
        toolbar.addWidget(self.prev_button)
        toolbar.addWidget(self.page_label)
        toolbar.addWidget(self.next_button)

        # Kacheln
        self.cards_container = QWidget(self)
        self.flow = FlowLayout(self.cards_container)
        self.flow.setContentsMargins(4, 4, 4, 4)
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.cards_container)
        self.empty_label = QLabel(self)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setVisible(False)

        layout = QVBoxLayout(self)
        layout.addLayout(header)
        layout.addLayout(toolbar)
        layout.addWidget(self.filter_box)
        layout.addWidget(self.empty_label)
        layout.addWidget(self.scroll, 1)

    def _build_actions_menu(self) -> QMenu:
        menu = QMenu(self)

        def add(text: str, slot: Callable[[], None], icon_name: str | None = None) -> None:
            action = menu.addAction(text)
            if icon_name:
                action.setIcon(icon(icon_name))
            action.triggered.connect(slot)

        add("Cloud deaktivieren", lambda: self._bulk_set("nocloud", True), "nocloud")
        add("Cloud aktivieren", lambda: self._bulk_set("nocloud", False), "cloud")
        add("Live aktivieren", lambda: self._bulk_set("live", True), "live")
        add("Live deaktivieren", lambda: self._bulk_set("live", False))
        add("Tags ausblenden", self._bulk_hide, "hide")
        menu.addSeparator()
        add("Als CSV exportieren", lambda: self._export("csv"), "download")
        add("Als JSON exportieren", lambda: self._export("json"), "download")
        add("Exportieren – vollständige Informationen – als JSON", lambda: self._export("full_json"), "download")
        add("Als HTML exportieren", lambda: self._export("html"), "download")
        add("Als HTML mit eingebetteten Bildern exportieren", lambda: self._export("html_inline"), "download")
        return menu

    # ---------- Laden ----------

    def load(self) -> None:
        """Lädt Tonieboxen, Inhaltsverzeichnisse, Tonies und die zuletzt gespielten Tonies."""
        self.statusMessage.emit(f"Lade Tonies von {self._client.endpoint} …")
        self._images.clear()
        self._client.fetch_setting("cloud.enabled", "", lambda value: self._set_cloud_available(value == "true"), lambda _m: None)
        self._client.fetch_boxes(self._on_boxes, lambda _message: self._on_boxes([]))

    def show_tonie(self, overlay: str, ruid: str) -> None:
        """Wie der Link /tonies?tonieRUID=…&overlay=… der Weboberfläche: Box wählen und auf den Tonie filtern."""
        self._overlay = overlay
        self._settings.overlay = overlay
        self.reset_filters()
        self.search_edit.setText(ruid)
        self.filter_button.setChecked(True)
        self.load()

    def _set_cloud_available(self, available: bool) -> None:
        self._cloud_available = available
        for widget in self._widgets.values():
            widget.set_cloud_available(available)

    def _on_boxes(self, boxes: list[Toniebox]) -> None:
        self._boxes = boxes
        self._last_played = {}
        for box in boxes:
            self._fetch_last_played(box)

        # Wie in der Weboberfläche: Tonieboxen mit gleichem Inhaltsverzeichnis zusammenfassen
        targets = [("", DEFAULT_CONTENT_DIR_LABEL)] + [(box.id, box.name) for box in boxes]
        content_dirs: dict[str, str] = {}

        def collect(box_id: str, content_dir: str) -> None:
            content_dirs[box_id] = content_dir
            if len(content_dirs) == len(targets):
                self._build_overlay_combo(targets, content_dirs)

        for box_id, _name in targets:
            self._client.fetch_setting(
                "core.contentdir", box_id, lambda d, b=box_id: collect(b, d), lambda _m, b=box_id: collect(b, "")
            )

    def _build_overlay_combo(self, targets: list[tuple[str, str]], content_dirs: dict[str, str]) -> None:
        groups: dict[str, tuple[str, list[str]]] = {}  # Inhaltsverzeichnis -> (Overlay-ID, Boxnamen)
        id_to_group: dict[str, str] = {}
        default_dir = content_dirs.get("", "")
        for box_id, name in targets[1:]:
            directory = content_dirs.get(box_id, "")
            group_id, names = groups.setdefault(directory, (box_id, []))
            names.append(name)
            id_to_group[box_id] = group_id
        if default_dir not in groups:
            groups[default_dir] = ("", [DEFAULT_CONTENT_DIR_LABEL])
            id_to_group[""] = ""

        overlay = id_to_group.get(self._overlay, None)
        if overlay is None:
            overlay = next(iter(groups.values()))[0]
        self.overlay_combo.blockSignals(True)
        self.overlay_combo.clear()
        for group_id, names in groups.values():
            self.overlay_combo.addItem(", ".join(names), group_id)
        self.overlay_combo.setCurrentIndex(max(self.overlay_combo.findData(overlay), 0))
        self.overlay_combo.blockSignals(False)
        self._set_overlay(overlay)

    def _on_overlay_changed(self) -> None:
        self._set_overlay(self.overlay_combo.currentData() or "")

    def _set_overlay(self, overlay: str) -> None:
        self._overlay = overlay
        self._settings.overlay = overlay
        self._selected.clear()
        self._client.fetch_tags(overlay, self._on_tags)

    def _fetch_last_played(self, box: Toniebox) -> None:
        def on_ruid(ruid: str) -> None:
            if not ruid or ruid.lower() == NO_RUID:
                return
            self._client.fetch_setting(
                "internal.last_ruid_time",
                box.id,
                lambda t: self._add_last_played(ruid, box, t),
                lambda _m: self._add_last_played(ruid, box, ""),
            )

        self._client.fetch_setting("internal.last_ruid", box.id, on_ruid, lambda _m: None)

    def _add_last_played(self, ruid: str, box: Toniebox, timestamp: str) -> None:
        text = box.name
        if timestamp.isdigit() and int(timestamp) > 0:
            text += f" ({datetime.fromtimestamp(int(timestamp)):%d.%m.%Y %H:%M:%S})"
        self._last_played.setdefault(ruid.lower(), []).append(text)
        widget = self._widgets.get(ruid.lower())
        if widget is not None:
            widget.set_last_played(self._last_played[ruid.lower()])

    def _on_tags(self, cards: list[TonieCard]) -> None:
        self._all_cards = cards
        self._cards = sort_cards(visible_tonies(cards))
        self._default_language = default_language(self._cards)
        self._update_language_combo()
        self._page = 0
        self._apply_filters()
        self.statusMessage.emit(f"{len(self._cards)} Tonies geladen")

    def _update_language_combo(self) -> None:
        current = self.language_combo.currentData()
        languages = sorted({card.tonie_info.language for card in self._cards if card.tonie_info.language})
        self.language_combo.blockSignals(True)
        self.language_combo.clear()
        self.language_combo.addItem("alle", "")
        for language in languages:
            self.language_combo.addItem(language, language)
        self.language_combo.setCurrentIndex(max(self.language_combo.findData(current), 0))
        self.language_combo.blockSignals(False)

    # ---------- Filter und Seiten ----------

    def current_filter(self) -> ToniesFilter:
        return ToniesFilter(
            search_text=self.search_edit.text().strip(),
            series=self.series_edit.text().strip(),
            episode=self.episode_edit.text().strip(),
            language=self.language_combo.currentData() or "",
            valid=self.valid_combo.value(),
            exists=self.exists_combo.value(),
            live=self.live_combo.value(),
            nocloud=self.nocloud_combo.value(),
            has_cloud_auth=self.cloud_auth_combo.value(),
            last_played_only=self.last_played_box.isChecked(),
        )

    def reset_filters(self) -> None:
        for edit in (self.search_edit, self.series_edit, self.episode_edit):
            edit.blockSignals(True)
            edit.clear()
            edit.blockSignals(False)
        for combo in (
            self.language_combo,
            self.valid_combo,
            self.exists_combo,
            self.live_combo,
            self.nocloud_combo,
            self.cloud_auth_combo,
        ):
            combo.blockSignals(True)
            combo.setCurrentIndex(0)
            combo.blockSignals(False)
        self.last_played_box.blockSignals(True)
        self.last_played_box.setChecked(False)
        self.last_played_box.blockSignals(False)
        self._apply_filters()

    def _apply_filters(self) -> None:
        tonies_filter = self.current_filter()
        last_played = set(self._last_played)
        self._filtered = [card for card in self._cards if tonies_filter.matches(card, last_played)]
        self._page = min(self._page, max(self._page_count() - 1, 0))
        self._render_page()

    def _page_size(self) -> int:
        return self.page_size_combo.currentData() or 0

    def _page_count(self) -> int:
        size = self._page_size()
        return max((len(self._filtered) + size - 1) // size, 1) if size else 1

    def _on_page_size_changed(self) -> None:
        self._page = 0
        self._render_page()

    def _go_to_page(self, page: int) -> None:
        if 0 <= page < self._page_count():
            self._page = page
            self._render_page()
            self.scroll.verticalScrollBar().setValue(0)

    def _render_page(self) -> None:
        size = self._page_size()
        page_cards = self._filtered[self._page * size : (self._page + 1) * size] if size else self._filtered

        # Kacheln neu aufbauen; bei höchstens einer Seite bleibt das schnell
        for widget in self._widgets.values():
            self.flow.removeWidget(widget)
            widget.deleteLater()
        self._widgets = {}
        selection_mode = self.select_button.isChecked()
        for card in page_cards:
            widget = TonieCardWidget(card, self._images, self.cards_container)
            widget.set_default_language(self._default_language)
            widget.set_cloud_available(self._cloud_available)
            widget.set_last_played(self._last_played.get(card.ruid.lower(), []))
            widget.set_selection_mode(selection_mode)
            widget.set_selected(card.ruid in self._selected)
            widget.infoRequested.connect(self.show_info)
            widget.editRequested.connect(self.edit)
            widget.playRequested.connect(self.play)
            widget.downloadRequested.connect(self.download_from_cloud)
            widget.cloudToggled.connect(lambda c: self._set_flag(c, "nocloud", not c.nocloud))
            widget.liveToggled.connect(lambda c: self._set_flag(c, "live", not c.live))
            widget.selectionToggled.connect(self._on_selection_toggled)
            self.flow.addWidget(widget)
            self._widgets[card.ruid] = widget

        total = len(self._cards)
        shown = len(self._filtered)
        self.count_label.setText(f"{shown} von {total} Tonies" if shown != total else f"{total} Tonies")
        self.page_label.setText(f"Seite {self._page + 1} von {self._page_count()}")
        self.prev_button.setEnabled(self._page > 0)
        self.next_button.setEnabled(self._page < self._page_count() - 1)
        self.empty_label.setText("Keine Tonies gefunden." if self._cards else "Keine Tonies vorhanden.")
        self.empty_label.setVisible(not page_cards)
        self._update_selection_label()

    # ---------- Auswahl ----------

    def set_selection_mode(self, enabled: bool) -> None:
        if self.select_button.isChecked() != enabled:
            self.select_button.setChecked(enabled)  # löst diese Methode erneut aus
            return
        self.select_button.setText("Abbrechen" if enabled else "Auswählen")
        self.select_button.setToolTip("Auswahlmodus beenden" if enabled else "Auswahlmodus aktivieren")
        for widget in self._selection_widgets:
            widget.setVisible(enabled)
        if not enabled:
            self._selected.clear()
        for widget in self._widgets.values():
            widget.set_selection_mode(enabled)
        self._update_selection_label()

    def select_all(self) -> None:
        self.set_selection_mode(True)
        self._selected = {card.ruid for card in self._filtered}
        for ruid, widget in self._widgets.items():
            widget.set_selected(ruid in self._selected)
        self._update_selection_label()

    def unselect_all(self) -> None:
        self._selected.clear()
        for widget in self._widgets.values():
            widget.set_selected(False)
        self._update_selection_label()

    def _on_selection_toggled(self, ruid: str, selected: bool) -> None:
        if selected:
            self._selected.add(ruid)
        else:
            self._selected.discard(ruid)
        widget = self._widgets.get(ruid)
        if widget is not None:
            widget.set_selected(selected)
        self._update_selection_label()

    def _update_selection_label(self) -> None:
        self.selected_label.setText(f"{len(self._selected)} Tags/Tonies ausgewählt")
        self.actions_button.setEnabled(bool(self._selected))

    def selected_cards(self) -> list[TonieCard]:
        return [card for card in self._cards if card.ruid in self._selected]

    def selection_as_text(self) -> str:
        """Ausgewählte (oder ohne Auswahl alle gefilterten) Tonies tabulatorgetrennt."""
        cards = self.selected_cards() or self._filtered
        lines = ["Serie\tEpisode\tModell\tUID"]
        lines += [f"{c.tonie_info.series}\t{c.tonie_info.episode}\t{c.tonie_info.model}\t{c.uid}" for c in cards]
        return "\n".join(lines)

    # ---------- Aktionen pro Kachel ----------

    def _label(self, card: TonieCard) -> str:
        return f'"{card.tonie_info.title}" [{card.ruid}]' if card.tonie_info.title else f"[{card.ruid}]"

    def show_info(self, card: TonieCard) -> None:
        dialog = TonieInfoDialog(card, self._client, self._images, self._last_played.get(card.ruid.lower(), []), self)
        dialog.playRequested.connect(self.play)
        dialog.hideRequested.connect(lambda c: self._hide([c]))
        dialog.exec()

    def edit(self, card: TonieCard) -> None:
        dialog = EditTonieDialog(card, self._client, self._overlay, self)
        dialog.saved.connect(lambda c: self.refresh_card(c.ruid))
        if dialog.exec():
            self.statusMessage.emit(f"Änderungen an {self._label(card)} gespeichert")

    def play(self, card: TonieCard, start_seconds: int = 0) -> None:
        if card.valid:
            url = self._client.media_url(card.audio_url)
        elif card.source.startswith("http"):
            url = self._client.media_url(card.source)
        else:
            return
        info = card.source_info if card.shows_alternative_source and card.source_info else card.tonie_info
        self._player.play(url, info.title or card.uid, start_seconds)

    def download_from_cloud(self, card: TonieCard) -> None:
        self.statusMessage.emit(f"{self._label(card)} wird heruntergeladen …")

        def done(_data: bytes) -> None:
            self.statusMessage.emit(f"Datei von {self._label(card)} heruntergeladen")
            self.refresh_card(card.ruid)

        def failed(message: str) -> None:
            self._error(f"Fehler beim Hintergrund-Download von {self._label(card)}: {message}")

        self._client.get_bytes(self._client.url(card.download_trigger_url), done, failed, timeout=False)

    def _set_flag(self, card: TonieCard, key: str, value: bool, done: Callable[[], None] | None = None) -> None:
        messages = {
            ("nocloud", True): "Cloud-Zugriff für {} blockiert",
            ("nocloud", False): "Cloud-Zugriff für {} aktiviert",
            ("live", True): "Live-Modus für {} aktiviert",
            ("live", False): "Live-Modus für {} deaktiviert",
        }

        def success() -> None:
            self.statusMessage.emit(messages[(key, value)].format(self._label(card)))
            self.refresh_card(card.ruid)
            if done:
                done()

        def failed(message: str) -> None:
            flag = "Cloud-Zugriff (nocloud)" if key == "nocloud" else "Live-Flag"
            self._error(f"Konnte {flag} für {self._label(card)} nicht ändern: {message}")
            if done:
                done()

        self._client.set_content(card.ruid, self._overlay, key, value, success, failed)

    def refresh_card(self, ruid: str) -> None:
        self._client.fetch_tag(ruid, self._overlay, self._on_card_refreshed)

    def _on_card_refreshed(self, card: TonieCard) -> None:
        self._cards = [card if c.ruid == card.ruid else c for c in self._cards]
        self._filtered = [card if c.ruid == card.ruid else c for c in self._filtered]
        if card.hide:
            self._remove_cards({card.ruid})
            return
        widget = self._widgets.get(card.ruid)
        if widget is not None:
            widget.set_card(card)

    def _hide(self, cards: list[TonieCard]) -> None:
        def hide_next(remaining: list[TonieCard]) -> None:
            if not remaining:
                return
            card = remaining[0]

            def success() -> None:
                self.statusMessage.emit(f"Tonie {self._label(card)} ausgeblendet")
                self._remove_cards({card.ruid})
                hide_next(remaining[1:])

            def failed(message: str) -> None:
                self._error(f"Tonie {self._label(card)} konnte nicht ausgeblendet werden: {message}")
                hide_next(remaining[1:])

            self._client.set_content(card.ruid, self._overlay, "hide", True, success, failed)

        hide_next(cards)

    def _remove_cards(self, ruids: set[str]) -> None:
        self._cards = [c for c in self._cards if c.ruid not in ruids]
        self._selected -= ruids
        self._apply_filters()

    # ---------- Sammelaktionen ----------

    def _bulk_set(self, key: str, value: bool) -> None:
        cards = self.selected_cards()

        def next_card(remaining: list[TonieCard]) -> None:
            if remaining:
                self._set_flag(remaining[0], key, value, lambda: next_card(remaining[1:]))

        next_card(cards)

    def _bulk_hide(self) -> None:
        cards = self.selected_cards()
        if not cards:
            return
        if len(cards) == 1:
            confirmed = confirm_hide(self, cards[0])
        else:
            confirmed = (
                QMessageBox.question(
                    self,
                    "Tags ausblenden",
                    f"Möchtest du die {len(cards)} ausgewählten Tonies/Tags wirklich aus der Toniesübersicht "
                    "ausblenden? Um sie wieder einzublenden musst du sie auf eine deiner Tonieboxen platzieren.",
                )
                == QMessageBox.StandardButton.Yes
            )
        if confirmed:
            self._hide(cards)

    def _export(self, kind: str) -> None:
        cards = self.selected_cards()
        if not cards:
            return
        extension, file_filter = {
            "csv": ("csv", "CSV-Datei (*.csv)"),
            "json": ("json", "JSON-Datei (*.json)"),
            "full_json": ("json", "JSON-Datei (*.json)"),
            "html": ("html", "HTML-Datei (*.html)"),
            "html_inline": ("html", "HTML-Datei (*.html)"),
        }[kind]
        target, _ = QFileDialog.getSaveFileName(
            self, "Exportieren", export.export_filename(f"selected_tonies.{extension}"), file_filter
        )
        if not target:
            return

        if kind == "csv":
            content = export.to_csv(cards)
        elif kind == "json":
            content = export.to_json(cards)
        elif kind == "full_json":
            content = export.to_full_json(cards)
        else:

            def image_src(card: TonieCard) -> str:
                image = self._images.cached(card.picture) if kind == "html_inline" else None
                if image is not None:
                    return export.image_data_url(image)
                return self._client.url(card.picture).toString(QUrl.UrlFormattingOption.RemoveUserInfo)

            content = export.to_html(cards, image_src)
        try:
            with open(target, "w", encoding="utf-8") as file:
                file.write(content)
        except OSError as exc:
            self._error(f"Export fehlgeschlagen: {exc}")
            return
        self.statusMessage.emit(f"{len(cards)} Tonies exportiert nach {target}")

    def _error(self, message: str) -> None:
        self.statusMessage.emit(message)
        QMessageBox.warning(self, "Tonies", message)
