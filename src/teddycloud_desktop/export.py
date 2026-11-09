"""Export ausgewählter Tonies, gleiche Formate wie die TeddyCloud-Weboberfläche."""

import base64
import csv
import html
import io
import json
from collections.abc import Callable
from datetime import datetime

from PyQt6.QtCore import QBuffer, QIODevice
from PyQt6.QtGui import QImage

from .teddycloud import TonieCard

UNSET_TONIE = "Tonie/Tag"


def export_filename(name: str) -> str:
    """Wie in der Weboberfläche mit Zeitstempel davor, z. B. 20261002_143000_selected_tonies.csv."""
    return f"{datetime.now():%Y%m%d_%H%M%S}_{name}"


def to_csv(cards: list[TonieCard]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_ALL, lineterminator="\n")
    buffer.write("Series,Episode,Model-No\n")
    for card in cards:
        writer.writerow([card.tonie_info.series or UNSET_TONIE, card.tonie_info.episode, card.tonie_info.model])
    return buffer.getvalue()


def to_json(cards: list[TonieCard]) -> str:
    rows = [
        {"series": c.tonie_info.series or UNSET_TONIE, "episode": c.tonie_info.episode, "model": c.tonie_info.model}
        for c in cards
    ]
    return json.dumps(rows, indent=2, ensure_ascii=False)


def to_full_json(cards: list[TonieCard]) -> str:
    """Alle Felder, wie sie /api/getTagIndex liefert."""
    return json.dumps([card.raw for card in cards], indent=2, ensure_ascii=False)


def image_data_url(image: QImage) -> str:
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return "data:image/png;base64," + base64.b64encode(bytes(buffer.data())).decode()


def to_html(cards: list[TonieCard], image_src: Callable[[TonieCard], str]) -> str:
    """`image_src` liefert je Tonie die Bildquelle (absolute URL oder eingebettete data:-URL)."""
    items = "".join(
        f"""
    <li id="export-{html.escape(card.ruid)}">
      <img class="thumb" src="{html.escape(image_src(card))}" alt="{html.escape(card.tonie_info.series)}" />
      <div class="info">
        {html.escape(card.tonie_info.series or UNSET_TONIE)} - {html.escape(card.tonie_info.episode)}
        <span class="model">({html.escape(card.tonie_info.model)})</span>
      </div>
    </li>"""
        for card in cards
    )
    return f"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Tonies-Exportliste</title>
<style>
  body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 24px; }}
  h1 {{ font-size: 20px; margin: 0 0 16px; }}
  ul {{ list-style: none; padding: 0; margin: 0; }}
  li {{ display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }}
  img.thumb {{ width: 150px; height: 150px; object-fit: contain; }}
  .info {{ font-size: 14px; }}
  .model {{ color: #666; font-size: 12px; font-family: ui-monospace, monospace; margin-left: 6px; }}
  .footer {{ margin-top: 24px; color: #666; font-size: 12px; }}
</style>
</head>
<body>
  <h1>Tonies-Exportliste</h1>
  <ul>{items or "<p>Keine Einträge.</p>"}
  </ul>
  <div class="footer">Erstellt am {datetime.now():%d.%m.%Y %H:%M:%S}</div>
</body></html>
"""
