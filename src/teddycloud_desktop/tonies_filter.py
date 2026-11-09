"""Filter der Tonie-Übersicht, angelehnt an das Filterpanel der Weboberfläche."""

from collections import Counter
from dataclasses import dataclass

from .teddycloud import TonieCard


@dataclass
class ToniesFilter:
    search_text: str = ""
    series: str = ""
    episode: str = ""
    language: str = ""
    # None = egal, True = nur mit, False = nur ohne
    valid: bool | None = None
    exists: bool | None = None
    live: bool | None = None
    nocloud: bool | None = None
    has_cloud_auth: bool | None = None
    last_played_only: bool = False

    def matches(self, card: TonieCard, last_played_ruids: set[str] | frozenset[str] = frozenset()) -> bool:
        info = card.tonie_info
        if self.search_text:
            needle = self.search_text.casefold()
            haystack = (info.series, info.episode, info.model, card.uid, card.ruid, card.source)
            if not any(needle in value.casefold() for value in haystack):
                return False
        if self.series and self.series.casefold() not in info.series.casefold():
            return False
        if self.episode and self.episode.casefold() not in info.episode.casefold():
            return False
        if self.language and info.language != self.language:
            return False
        for wanted, actual in (
            (self.valid, card.valid),
            (self.exists, card.exists),
            (self.live, card.live),
            (self.nocloud, card.nocloud),
            (self.has_cloud_auth, card.has_cloud_auth),
        ):
            if wanted is not None and wanted != actual:
                return False
        if self.last_played_only and card.ruid not in last_played_ruids:
            return False
        return True


def visible_tonies(cards: list[TonieCard]) -> list[TonieCard]:
    """Wie /web/tonies: nur echte Tags (keine System-Sounds) und keine ausgeblendeten."""
    return [card for card in cards if card.type == "tag" and not card.hide]


def default_language(cards: list[TonieCard]) -> str:
    """Häufigste Sprache; nur abweichende Sprachen werden auf den Kacheln markiert."""
    counts = Counter(card.tonie_info.language for card in cards if card.tonie_info.language)
    return counts.most_common(1)[0][0] if counts else ""
