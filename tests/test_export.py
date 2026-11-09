import base64
import json
import re

from PyQt6.QtGui import QColor, QImage

from teddycloud_desktop.export import UNSET_TONIE, export_filename, image_data_url, to_csv, to_full_json, to_html, to_json
from teddycloud_desktop.teddycloud import parse_tag


def test_export_filename_has_timestamp_prefix() -> None:
    assert re.fullmatch(r"\d{8}_\d{6}_selected_tonies\.csv", export_filename("selected_tonies.csv"))


def test_csv_quotes_values_and_uses_placeholder_for_unset(make_card) -> None:
    cards = [make_card(series='Die "drei" ???', episode="Folge 1, Teil 2", model="10000001"), make_card()]
    assert to_csv(cards) == (f'Series,Episode,Model-No\n"Die ""drei"" ???","Folge 1, Teil 2","10000001"\n"{UNSET_TONIE}","",""\n')


def test_json_rows_keep_umlauts(make_card) -> None:
    data = to_json([make_card(series="Bibi Blocksberg", episode="Hexen Ärger", model="1")])
    assert "Ärger" in data
    assert json.loads(data) == [{"series": "Bibi Blocksberg", "episode": "Hexen Ärger", "model": "1"}]
    assert json.loads(to_json([make_card()]))[0]["series"] == UNSET_TONIE


def test_full_json_uses_raw_tag_data() -> None:
    raw = {"ruid": "abc", "uid": "E0", "tonieInfo": {"series": "S"}, "extra": 42}
    assert json.loads(to_full_json([parse_tag(raw)])) == [raw]


def test_html_escapes_content_and_uses_image_source(make_card) -> None:
    card = make_card(ruid="r1", series="<b>Serie</b>", episode="A & B", model="m1")
    page = to_html([card], lambda c: f"https://img/{c.ruid}.png?a=1&b=2")
    assert 'id="export-r1"' in page
    assert "&lt;b&gt;Serie&lt;/b&gt; - A &amp; B" in page
    assert 'src="https://img/r1.png?a=1&amp;b=2"' in page
    assert "<b>Serie</b>" not in page


def test_html_without_cards_shows_placeholder() -> None:
    assert "Keine Einträge." in to_html([], lambda _card: "")


def test_image_data_url_is_png() -> None:
    image = QImage(2, 2, QImage.Format.Format_RGB32)
    image.fill(QColor("red"))
    url = image_data_url(image)
    assert url.startswith("data:image/png;base64,")
    assert base64.b64decode(url.split(",", 1)[1]).startswith(b"\x89PNG")
