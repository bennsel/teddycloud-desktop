"""Gemeinsame Fixtures; Qt läuft ohne Bildschirm."""

import os
from collections.abc import Callable
from typing import Any

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from teddycloud_desktop.teddycloud import TonieCard, TonieInfo  # noqa: E402


@pytest.fixture
def make_card() -> Callable[..., TonieCard]:
    """Baut eine TonieCard; Serie/Episode/Modell/Sprache landen in tonie_info."""

    def factory(
        ruid: str = "0123456789abcdef",
        series: str = "",
        episode: str = "",
        model: str = "",
        language: str = "",
        **kwargs: Any,
    ) -> TonieCard:
        info = TonieInfo(model=model, series=series, episode=episode, language=language)
        return TonieCard(ruid=ruid, tonie_info=info, **kwargs)

    return factory
