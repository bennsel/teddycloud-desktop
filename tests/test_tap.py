import json

import pytest

from teddycloud_desktop.encoder_page import new_audio_id
from teddycloud_desktop.tap import (
    MAX_TAP_FILES,
    TapFile,
    TeddyAudioPlaylist,
    build_taf_filepath,
    library_source,
    parse_tap,
    safe_tap_name,
    split_taf_filepath,
    validate_tap,
)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Party", "Party"),
        ("  a/b:c*d?  ", "a_b_c_d_"),
        ('x<>"|\\y', "x_____y"),
        ("Ende. . ", "Ende"),
        ("tab\there", "tab_here"),
        ("...", "untitled"),
        ("", "untitled"),
    ],
)
def test_safe_tap_name(name: str, expected: str) -> None:
    assert safe_tap_name(name) == expected


def test_to_json_and_file_name() -> None:
    tap = TeddyAudioPlaylist(
        name="Party: Mix", audio_id=42, filepath="lib://P/Party.taf", files=[TapFile("lib://a.mp3", "Lied Ä")]
    )
    assert tap.to_json() == {
        "type": "tap",
        "audio_id": 42,
        "filepath": "lib://P/Party.taf",
        "name": "Party: Mix",
        "files": [{"filepath": "lib://a.mp3", "name": "Lied Ä"}],
    }
    assert tap.file_name == "Party_ Mix.tap"
    assert "Lied Ä" in tap.to_bytes().decode("utf-8")


def test_roundtrip() -> None:
    tap = TeddyAudioPlaylist(
        name="N", audio_id=7, filepath="lib://x.taf", files=[TapFile("lib://1.mp3", "1"), TapFile("lib://2.ogg")]
    )
    assert parse_tap(tap.to_bytes()) == tap


def test_parse_tap_tolerates_bad_fields() -> None:
    data = json.dumps({"type": "tap", "audio_id": "kaputt", "files": [{"filepath": "lib://a.mp3"}, "x", {"name": None}]})
    tap = parse_tap(data.encode())
    assert tap.audio_id == 0
    assert tap.name == ""
    assert tap.filepath == ""
    assert tap.files == [TapFile("lib://a.mp3", ""), TapFile("", "")]


def test_parse_tap_accepts_numeric_string_audio_id() -> None:
    assert parse_tap(b'{"type": "tap", "audio_id": "123"}').audio_id == 123


@pytest.mark.parametrize("data", [b"kein json", b"\xff\xfe", b"[]", b'{"type": "taf"}'])
def test_parse_tap_rejects_invalid(data: bytes) -> None:
    with pytest.raises(ValueError):
        parse_tap(data)


@pytest.mark.parametrize(
    ("filepath", "expected"),
    [
        ("lib://Ordner/Datei.taf", ("/Ordner", "Datei")),
        ("lib://A/B/Datei.TAF", ("/A/B", "Datei")),
        ("lib://Datei.taf", ("/", "Datei")),
        ("/Ordner/Datei", ("/Ordner", "Datei")),
    ],
)
def test_split_taf_filepath(filepath: str, expected: tuple[str, str]) -> None:
    assert split_taf_filepath(filepath) == expected


def test_build_taf_filepath_and_library_source() -> None:
    assert build_taf_filepath("/Ordner/", " Datei.taf ") == "lib://Ordner/Datei.taf"
    assert build_taf_filepath("/", "Datei") == "lib://Datei.taf"
    assert build_taf_filepath(*split_taf_filepath("lib://A/B/x.taf")) == "lib://A/B/x.taf"
    assert library_source("/Ordner/", "x.tap") == "lib://Ordner/x.tap"
    assert library_source("", "x.tap") == "lib://x.tap"


def test_validate_tap() -> None:
    ok = TeddyAudioPlaylist(name="N", files=[TapFile("lib://a.mp3")])
    assert validate_tap(ok, "base") == []
    assert len(validate_tap(TeddyAudioPlaylist(name=" "), " ")) == 3
    errors = validate_tap(TeddyAudioPlaylist(name="N", files=[TapFile("lib://a.mp3"), TapFile(" ")]), "b")
    assert errors == ["Datei 2: Der Dateipfad muss ausgefüllt werden"]
    too_many = TeddyAudioPlaylist(name="N", files=[TapFile("lib://a.mp3")] * (MAX_TAP_FILES + 1))
    assert validate_tap(too_many, "b") == [f"Eine Playlist kann höchstens {MAX_TAP_FILES} Dateien enthalten"]


def test_new_audio_id_strictly_increasing() -> None:
    ids = [new_audio_id() for _ in range(50)]
    assert all(b > a for a, b in zip(ids, ids[1:], strict=False))
    assert ids[0] > 0
