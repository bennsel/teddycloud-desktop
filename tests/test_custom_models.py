import pytest

from teddycloud_desktop.custom_models import (
    CustomEntry,
    CustomModelFilter,
    category_options,
    clean_entry,
    entries_differ,
    entry_from_api,
    field_errors,
    matches_tokens,
    original_pictures,
    parse_entries,
    sort_entries,
    suggested_model,
    validate_entries,
)


def test_entry_from_api_trims_and_wraps_single_values() -> None:
    entry = entry_from_api(
        {
            "model": " custom-1 ",
            "series": "Serie",
            "release": 2024,
            "audio_id": 123,
            "hash": "ABC",
            "tracks": ["a", " ", None, "b"],
        }
    )
    assert entry.model == "custom-1"
    assert entry.release == "2024"
    assert entry.audio_ids == ["123"]
    assert entry.hashes == ["ABC"]
    assert entry.tracks == ["a", "b"]
    assert entry.episodes == ""


def test_entry_from_api_tolerates_non_dict() -> None:
    assert entry_from_api(None) == CustomEntry()


def test_parse_entries_requires_list() -> None:
    assert [e.model for e in parse_entries([{"model": "a"}, {"model": "b"}])] == ["a", "b"]
    with pytest.raises(ValueError):
        parse_entries({"model": "a"})


def test_clean_entry_drops_incomplete_pairs_and_empty_tracks() -> None:
    entry = CustomEntry(
        model=" m ",
        series="s",
        language="de-de",
        audio_ids=["1", "2", " ", "4"],
        hashes=["h1", "", "h3"],
        tracks=["t1", "  ", " t2 "],
    )
    cleaned = clean_entry(entry)
    assert cleaned.model == "m"
    assert cleaned.audio_ids == ["1"]
    assert cleaned.hashes == ["h1"]
    assert cleaned.tracks == ["t1", "t2"]
    assert cleaned.language == "de-de"


def test_clean_entry_clears_invalid_language() -> None:
    assert clean_entry(CustomEntry(language="klingonisch")).language == ""


def test_to_payload_omits_empty_fields() -> None:
    entry = CustomEntry(model="m", series="", title="T", audio_ids=["1", "2"], hashes=["h1", ""])
    assert entry.to_payload() == {"model": "m", "series": "", "title": "T", "audio_id": ["1"], "hash": ["h1"]}


def test_to_payload_full() -> None:
    entry = CustomEntry(model="m", series="s", episodes="e", release="1", tracks=["a"], audio_ids=["1"], hashes=["h"])
    payload = entry.to_payload()
    assert payload == {
        "model": "m",
        "series": "s",
        "episodes": "e",
        "release": "1",
        "audio_id": ["1"],
        "hash": ["h"],
        "tracks": ["a"],
    }
    # Kopie statt derselben Liste
    payload["tracks"].append("b")
    assert entry.tracks == ["a"]


def test_copy_is_deep_for_lists() -> None:
    entry = CustomEntry(model="m", audio_ids=["1"])
    copy = entry.copy()
    copy.audio_ids.append("2")
    assert entry.audio_ids == ["1"]


def test_selection_text() -> None:
    assert CustomEntry(model="m", series="S", episodes="E").selection_text() == "[m] S - E"
    assert CustomEntry(model="m", series="S").selection_text() == "[m] S"


def test_entries_differ_ignores_hash_case_and_whitespace() -> None:
    left = CustomEntry(model="m", series="s", audio_ids=["1"], hashes=["ABC"])
    right = CustomEntry(model="m ", series="s", audio_ids=["1"], hashes=["abc"])
    assert not entries_differ(left, right)
    assert entries_differ(left, CustomEntry(model="m", series="x", audio_ids=["1"], hashes=["abc"]))
    assert entries_differ(left, CustomEntry(model="m", series="s"))


def test_suggested_model() -> None:
    entries = [
        CustomEntry(model="custom-3"),
        CustomEntry(model="CUSTOM-10"),
        CustomEntry(model="custom-x"),
        CustomEntry(model="12"),
    ]
    assert suggested_model(entries) == "custom-11"
    assert suggested_model([]) == "custom-1"


def test_field_errors() -> None:
    assert field_errors(CustomEntry(model="m", series="s", release="2024", language="de-de")) == []
    errors = field_errors(CustomEntry(model=" ", series="", release="20a4", language="xx"))
    assert len(errors) == 4
    assert "Release muss numerisch sein" in errors


def test_validate_entries_duplicate_model_case_insensitive() -> None:
    error, warning = validate_entries([CustomEntry(model="Custom-1"), CustomEntry(model="custom-1")], [])
    assert error == "Doppeltes Modell: custom-1"
    assert warning == ""


def test_validate_entries_duplicate_audio_pair() -> None:
    entries = [
        CustomEntry(model="a", audio_ids=["1"], hashes=["ABC"]),
        CustomEntry(model="b", audio_ids=["1 "], hashes=["abc"]),
    ]
    error, _ = validate_entries(entries, [])
    assert error.startswith("Doppelte audio_id+hash-Kombination")


def test_validate_entries_warns_about_base_models() -> None:
    entries = [CustomEntry(model="10000001"), CustomEntry(model="custom-1"), CustomEntry(model="10000000")]
    assert validate_entries(entries, [CustomEntry(model="10000000"), CustomEntry(model="10000001")]) == (
        "",
        "Modell existiert in base tonies.json: 10000000, 10000001",
    )
    assert validate_entries(entries, []) == ("", "")


def test_category_options_most_common_first() -> None:
    first = [CustomEntry(category="Hörspiel"), CustomEntry(category="Musik"), CustomEntry(category="")]
    second = [CustomEntry(category="Musik"), CustomEntry(category="Audiobook")]
    assert category_options(first, second) == ["Musik", "Audiobook", "Hörspiel"]


def test_original_pictures() -> None:
    catalog = [{"pic": " https://a "}, {"tonieInfo": {"picture": "https://b"}}, {"pic": "https://a"}, "kaputt", {"pic": 5}]
    assert original_pictures(catalog) == ["https://a", "https://b"]
    assert original_pictures({"pic": "x"}) == []


def test_matches_tokens_any_order() -> None:
    assert matches_tokens("Benjamin Blümchen als Koch", "koch benjamin")
    assert not matches_tokens("Benjamin Blümchen", "benjamin bibi")
    assert matches_tokens("egal", "")


def test_filter_text_only_searches_selected_fields() -> None:
    entry = CustomEntry(model="custom-1", series="Serie", title="Geheimtitel", language="de-de", episodes="Folge 2")
    assert CustomModelFilter(text="CUSTOM").matches(entry)
    assert not CustomModelFilter(text="geheim").matches(entry)
    assert CustomModelFilter(text="geheim", fields=("title",)).matches(entry)
    assert CustomModelFilter(series="seri", episode="folge", language="DE-DE").matches(entry)
    assert not CustomModelFilter(language="en-us").matches(entry)


def test_sort_by_series_then_episode_naturally_then_model() -> None:
    entries = [
        CustomEntry(model="c", series="B", episodes="Folge 10"),
        CustomEntry(model="b", series="B", episodes="Folge 2"),
        CustomEntry(model="a", series="a", episodes=""),
        CustomEntry(model="d2", series="B", episodes="Folge 2"),
    ]
    assert [e.model for e in sort_entries(entries, "series")] == ["a", "b", "d2", "c"]
    assert [e.model for e in sort_entries(entries, "series", descending=True)] == ["c", "d2", "b", "a"]


def test_sort_by_other_column() -> None:
    entries = [CustomEntry(model="x", release="2020"), CustomEntry(model="y", release=""), CustomEntry(model="z", release="999")]
    assert [e.model for e in sort_entries(entries, "release")] == ["y", "z", "x"]
