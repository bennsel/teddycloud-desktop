from teddycloud_desktop.tonies_filter import ToniesFilter, default_language, visible_tonies


def test_empty_filter_matches_everything(make_card) -> None:
    assert ToniesFilter().matches(make_card())


def test_search_text_is_case_insensitive_over_several_fields(make_card) -> None:
    card = make_card(series="Benjamin Blümchen", episode="Folge 1", model="10000123", uid="E0:04:03:50", source="lib://x.taf")
    assert ToniesFilter(search_text="BLÜMCHEN").matches(card)
    assert ToniesFilter(search_text="10000123").matches(card)
    assert ToniesFilter(search_text="e0:04").matches(card)
    assert ToniesFilter(search_text="lib://").matches(card)
    assert ToniesFilter(search_text="cdef").matches(card)  # Teil der RUID
    assert not ToniesFilter(search_text="Bibi").matches(card)


def test_series_and_episode_are_substring_filters(make_card) -> None:
    card = make_card(series="Die drei ???", episode="Der Super-Papagei")
    assert ToniesFilter(series="drei").matches(card)
    assert ToniesFilter(episode="papagei").matches(card)
    assert not ToniesFilter(series="fünf").matches(card)
    assert not ToniesFilter(episode="Phantomsee").matches(card)


def test_language_must_match_exactly(make_card) -> None:
    card = make_card(language="de-de")
    assert ToniesFilter(language="de-de").matches(card)
    assert not ToniesFilter(language="de").matches(card)


def test_tristate_flags(make_card) -> None:
    card = make_card(valid=True, live=False)
    assert ToniesFilter(valid=True).matches(card)
    assert not ToniesFilter(valid=False).matches(card)
    assert ToniesFilter(live=False).matches(card)
    assert not ToniesFilter(live=True).matches(card)
    assert ToniesFilter(nocloud=None, exists=None).matches(card)


def test_last_played_only(make_card) -> None:
    card = make_card(ruid="aaaa")
    flt = ToniesFilter(last_played_only=True)
    assert not flt.matches(card)
    assert flt.matches(card, {"aaaa"})


def test_visible_tonies_drops_system_sounds_and_hidden(make_card) -> None:
    tag = make_card(ruid="1")
    hidden = make_card(ruid="2", hide=True)
    system = make_card(ruid="3", type="system")
    assert visible_tonies([tag, hidden, system]) == [tag]


def test_default_language_is_most_common(make_card) -> None:
    cards = [make_card(language="de-de"), make_card(language="en-us"), make_card(language="de-de"), make_card(language="")]
    assert default_language(cards) == "de-de"
    assert default_language([make_card()]) == ""
    assert default_language([]) == ""
