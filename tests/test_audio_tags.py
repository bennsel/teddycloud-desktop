"""Winzige Testdateien werden mit struct bzw. mutagen erzeugt; echte Audiodaten sind nicht nötig."""

import struct
from pathlib import Path

from mutagen.flac import FLAC, Picture
from mutagen.id3 import APIC, TALB, TPE1, TPE2
from mutagen.wave import WAVE

from teddycloud_desktop.audio_tags import FRONT_COVER, AudioTags, read_audio_tags


def _chunk(chunk_id: bytes, data: bytes) -> bytes:
    return chunk_id + struct.pack("<I", len(data)) + data + (b"\x00" if len(data) & 1 else b"")


def _write_wav(path: Path, extra_chunks: bytes = b"") -> None:
    fmt = _chunk(b"fmt ", struct.pack("<HHIIHH", 1, 1, 8000, 16000, 2, 16))
    body = b"WAVE" + fmt + extra_chunks + _chunk(b"data", b"\x00" * 4)
    path.write_bytes(b"RIFF" + struct.pack("<I", len(body)) + body)


def _info_list(**fields: bytes) -> bytes:
    return _chunk(b"LIST", b"INFO" + b"".join(_chunk(key.encode(), value) for key, value in fields.items()))


def _write_flac(path: Path) -> None:
    """Nur fLaC-Kennung und STREAMINFO (44,1 kHz, Stereo, 16 Bit)."""
    info = bytearray(34)
    struct.pack_into(">HH", info, 0, 4096, 4096)
    info[10:18] = ((44100 << 44) | (1 << 41) | (15 << 36)).to_bytes(8, "big")
    path.write_bytes(b"fLaC" + bytes([0x80, 0, 0, 34]) + bytes(info))


def test_artist_prefers_album_artist_and_removes_duplicates() -> None:
    assert AudioTags(album_artist="AA", artists=["X"]).artist == "AA"
    assert AudioTags(artists=["X", "Y", "X"]).artist == "X, Y"


def test_cover_prefers_front_cover() -> None:
    assert AudioTags(pictures=[(0, b""), (4, b"back"), (FRONT_COVER, b"front")]).cover == b"front"
    assert AudioTags(pictures=[(0, b""), (4, b"back")]).cover == b"back"
    assert AudioTags().cover == b""


def test_missing_or_unknown_file_gives_empty_tags(tmp_path: Path) -> None:
    assert read_audio_tags(str(tmp_path / "fehlt.mp3")) == AudioTags()
    junk = tmp_path / "junk.bin"
    junk.write_bytes(b"\x00\x01\x02 kein audio")
    assert read_audio_tags(str(junk)) == AudioTags()


def test_wav_riff_info_fallback(tmp_path: Path) -> None:
    path = tmp_path / "info.wav"
    _write_wav(path, _info_list(IART=b"Interpret\x00", IPRD="Album ä".encode() + b"\x00"))
    tags = read_audio_tags(str(path))
    assert tags.artists == ["Interpret"]
    assert tags.album == "Album ä"


def test_wav_riff_info_latin1_and_skips_other_chunks(tmp_path: Path) -> None:
    path = tmp_path / "latin1.WAV"
    other_list = _chunk(b"LIST", b"adtl" + _chunk(b"labl", b"xyz"))
    _write_wav(path, _chunk(b"junk", b"abc") + other_list + _info_list(IART=b"M\xfcller"))
    tags = read_audio_tags(str(path))
    assert tags.artist == "Müller"
    assert tags.album == ""


def test_wav_with_id3_chunk(tmp_path: Path) -> None:
    path = tmp_path / "id3.wav"
    # RIFF-INFO wird ignoriert, sobald ID3 etwas liefert
    _write_wav(path, _info_list(IART=b"Falsch"))
    wave = WAVE(str(path))
    wave.add_tags()
    wave.tags.add(TPE1(encoding=3, text=["Track 1", "Track 2"]))
    wave.tags.add(TPE2(encoding=3, text=["Album-Interpret"]))
    wave.tags.add(TALB(encoding=3, text=["Das Album"]))
    wave.tags.add(APIC(encoding=3, mime="image/png", type=0, desc="other", data=b"other"))
    wave.tags.add(APIC(encoding=3, mime="image/png", type=3, desc="front", data=b"front"))
    wave.save()

    tags = read_audio_tags(str(path))
    assert tags.artists == ["Track 1", "Track 2"]
    assert tags.artist == "Album-Interpret"
    assert tags.album == "Das Album"
    assert tags.cover == b"front"


def test_flac_vorbis_comments_and_picture_block(tmp_path: Path) -> None:
    path = tmp_path / "a.flac"
    _write_flac(path)
    flac = FLAC(str(path))
    flac["artist"] = ["Künstler"]
    flac["albumartist"] = ["Album-Künstler"]
    flac["album"] = ["Album"]
    picture = Picture()
    picture.type = FRONT_COVER
    picture.mime = "image/jpeg"
    picture.data = b"cover"
    flac.add_picture(picture)
    flac.save()

    tags = read_audio_tags(str(path))
    assert tags.artists == ["Künstler"]
    assert tags.artist == "Album-Künstler"
    assert tags.album == "Album"
    assert tags.cover == b"cover"
