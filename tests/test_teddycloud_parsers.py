import base64

import pytest

from teddycloud_desktop.encoder_custom import find_taf_hash
from teddycloud_desktop.teddycloud import (
    UNKNOWN_PICTURE,
    LibraryEntry,
    TonieInfo,
    basic_auth_header,
    format_box_id,
    natural_key,
    normalize_endpoint,
    parse_box_models,
    parse_boxes,
    parse_file_index,
    parse_search,
    parse_settings_index,
    parse_tag,
    parse_tag_index,
    parse_tag_info,
    setting_to_text,
    sort_cards,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  teddycloud.local/  ", "http://teddycloud.local"),
        ("https://tc:8443//", "https://tc:8443"),
        ("192.168.1.10:8080", "http://192.168.1.10:8080"),
        ("", ""),
        ("   ", ""),
    ],
)
def test_normalize_endpoint(raw: str, expected: str) -> None:
    assert normalize_endpoint(raw) == expected


def test_basic_auth_header() -> None:
    header = basic_auth_header("user", "pä:ss")
    assert header.startswith(b"Basic ")
    assert base64.b64decode(header[6:]).decode() == "user:pä:ss"


def test_format_box_id_and_setting_to_text() -> None:
    assert format_box_id("aabbccddeeff") == "AA:BB:CC:DD:EE:FF"
    assert setting_to_text(True) == "true"
    assert setting_to_text(False) == "false"
    assert setting_to_text(5) == "5"


def test_natural_key_and_sort_cards(make_card) -> None:
    assert sorted(["Folge 10", "folge 2", "Folge 1"], key=natural_key) == ["Folge 1", "folge 2", "Folge 10"]
    cards = [
        make_card(ruid="1", series="B", episode="10"),
        make_card(ruid="2", series="b", episode="9"),
        make_card(ruid="3", series="A"),
    ]
    assert [c.ruid for c in sort_cards(cards)] == ["3", "2", "1"]


TAG = {
    "ruid": "0123456789abcdef",
    "uid": "E0:04:03:50:1E:A8:6B:2C",
    "type": "tag",
    "valid": True,
    "exists": True,
    "live": False,
    "nocloud": True,
    "hasCloudAuth": True,
    "source": "lib://by/audioID/1.taf",
    "audioUrl": "/content/download/abc",
    "tonieInfo": {
        "model": "10000001",
        "series": "Serie",
        "episode": "Folge",
        "picture": "https://cdn/p.png",
        "tracks": ["a", "b"],
    },
    "sourceInfo": {"series": "Andere", "tracks": ["x"]},
    "trackSeconds": [0, "65"],
}


def test_parse_tag_full() -> None:
    card = parse_tag(TAG)
    assert card.ruid == "0123456789abcdef"
    assert card.valid and card.exists and card.nocloud and card.has_cloud_auth
    assert not card.live and not card.hide and not card.claimed
    assert card.audio_url == "/content/download/abc"
    assert card.tonie_info == TonieInfo(
        model="10000001", series="Serie", episode="Folge", picture="https://cdn/p.png", tracks=("a", "b")
    )
    assert card.track_seconds == (0, 65)
    assert card.raw is TAG
    assert card.picture == "https://cdn/p.png"
    assert card.shows_alternative_source
    assert card.display_tracks == ("x",)
    assert card.is_playable


def test_parse_tag_minimal_defaults() -> None:
    card = parse_tag({"ruid": "r", "tonieInfo": None, "source": None})
    assert card.type == "tag"
    assert card.source == ""
    assert card.source_info is None
    assert card.tonie_info == TonieInfo()
    assert card.picture == UNKNOWN_PICTURE
    assert not card.shows_alternative_source
    assert not card.is_playable
    assert parse_tag({"ruid": "r", "source": "https://stream"}).is_playable


def test_same_source_info_is_not_alternative() -> None:
    info = {"series": "S", "episode": "E", "tracks": ["t"]}
    card = parse_tag({"ruid": "r", "tonieInfo": info, "sourceInfo": dict(info, model="other")})
    assert not card.shows_alternative_source
    assert card.display_tracks == ("t",)


@pytest.mark.parametrize("tag", [{}, {"ruid": ""}, None, "abc"])
def test_parse_tag_requires_ruid(tag) -> None:
    with pytest.raises(ValueError):
        parse_tag(tag)


def test_parse_tag_index_deduplicates_ruids() -> None:
    cards = parse_tag_index({"tags": [{"ruid": "a", "uid": "1"}, {"ruid": "b"}, {"ruid": "a", "uid": "2"}]})
    assert [(c.ruid, c.uid) for c in cards] == [("a", "1"), ("b", "")]
    with pytest.raises(ValueError):
        parse_tag_index({"tags": None})


def test_parse_tag_info() -> None:
    assert parse_tag_info({"tagInfo": {"ruid": "x"}}).ruid == "x"
    with pytest.raises(ValueError):
        parse_tag_info([])
    with pytest.raises(ValueError):
        parse_tag_info({})


def test_parse_search() -> None:
    assert parse_search([{"model": "1", "series": "S"}, None]) == [TonieInfo(model="1", series="S"), TonieInfo()]
    with pytest.raises(ValueError):
        parse_search({})


def test_parse_boxes() -> None:
    boxes = parse_boxes(
        {
            "boxes": [
                {"ID": "aabb", "boxName": "Kinderzimmer", "commonName": "cn1", "boxModel": "m"},
                {"ID": "ccdd", "commonName": "cn2"},
            ]
        }
    )
    assert [(b.id, b.name, b.common_name, b.model) for b in boxes] == [
        ("aabb", "Kinderzimmer", "cn1", "m"),
        ("ccdd", "cn2", "cn2", ""),
    ]
    with pytest.raises(ValueError):
        parse_boxes({})


def test_parse_box_models_crop() -> None:
    models = parse_box_models([{"id": 3, "name": "Rot", "crop": [1, 2, 0.5, 9]}, {"id": "4", "crop": [1, 2]}])
    assert models[0].id == "3"
    assert models[0].crop == (1.0, 2.0, 0.5)
    assert models[1].crop is None


def test_parse_settings_index() -> None:
    options = parse_settings_index(
        {
            "options": [
                {"ID": "core.x", "type": "int", "value": 3, "overlayed": 1, "level": 2, "min": 0, "max": 10},
                {"ID": "core.y"},
            ]
        }
    )
    assert options[0].label == "core.x"
    assert options[0].overlayed is True
    assert (options[0].level, options[0].minimum, options[0].maximum) == (2, 0, 10)
    assert options[1].type == "string"
    assert options[1].level == 1


def test_parse_file_index_sorts_dirs_first_and_reads_taf_header() -> None:
    entries = parse_file_index(
        {
            "files": [
                {"name": "."},
                {"name": ".."},
                {"name": "b10.taf", "size": "12", "tafHeader": {"audioId": 1234, "sha1Hash": "ABC"}, "date": 99},
                {"name": "b2.mp3"},
                {"name": "Ordner", "isDir": True},
                {"name": "x.taf", "tonieInfo": {"series": "S"}},
            ]
        }
    )
    assert [e.name for e in entries] == ["Ordner", "b2.mp3", "b10.taf", "x.taf"]
    taf = entries[2]
    assert (taf.is_taf, taf.audio_id, taf.hash, taf.size, taf.date) == (True, "1234", "ABC", 12, 99)
    assert entries[1].is_taf is False
    assert entries[3].tonie_info == TonieInfo(series="S")
    with pytest.raises(ValueError):
        parse_file_index({"files": "x"})


def test_find_taf_hash() -> None:
    entries = [
        LibraryEntry(name="neu.taf", is_dir=False, audio_id="1", hash="alt"),
        LibraryEntry(name="neu.taf", is_dir=False, audio_id="2", hash=""),
        LibraryEntry(name="neu.taf", is_dir=False, audio_id="2", hash="h2"),
    ]
    assert find_taf_hash(entries, "neu.taf", 2) == "h2"
    assert find_taf_hash(entries, "neu.taf", 3) == ""
    assert find_taf_hash(entries, "andere.taf", 1) == ""
