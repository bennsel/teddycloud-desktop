# TeddyCloud Desktop

English version: [README.md](README.md)

Plattformübergreifende Desktop-Anwendung (Windows, macOS, Linux) auf Basis von PyQt6 zum Verwalten der Tonies und Tonieboxen einer [TeddyCloud](https://github.com/toniebox-reverse-engineering/teddycloud)-Instanz. Die beiden Übersichten sind den Seiten `/web/tonies` und `/web/tonieboxes` der TeddyCloud-Weboberfläche ([teddycloud_web](https://github.com/toniebox-reverse-engineering/teddycloud_web)) nachgebaut.

> Dies ist ein inoffizielles Community-Projekt, nicht verbunden mit der tonies GmbH (siehe [Haftungsausschluss](#haftungsausschluss)).

## Funktionen

**[Tonie-Übersicht](#tonie-übersicht-tonies--tonies)**
- Kacheln mit Bild, Serie, Episode und UID für jeden Tonie, je Inhaltsverzeichnis einer Toniebox (Boxen mit gleichem Verzeichnis werden zusammengefasst)
- Filter nach Text, Serie, Episode, Sprache, Gültig/Inhalt/Live/Cloud-Status und „zuletzt auf einer Toniebox gespielt“
- Seitenweise Anzeige (24/48/96/alle), natürliche Sortierung, Markierung des zuletzt gespielten Tonies je Box
- Inhalte im eingebauten Player abspielen, auch direkt ab einzelnen Titeln
- Cloud-Zugriff und Live-Modus umschalten, fehlende Inhalte aus der Tonie-Cloud laden
- Infodialog mit Titelliste, Download als `.ogg`, Tonies ausblenden
- Bearbeitungsdialog: Quelle aus der Bibliothek (`.taf`/`.tap`) oder Radiostream-URL zuweisen, Modell per Katalogsuche ändern
- Auswahlmodus mit Sammelaktionen (Cloud, Live, Ausblenden) und Export als CSV, JSON, vollständiges JSON, HTML oder HTML mit eingebetteten Bildern
- Als Text in die Zwischenablage kopieren

**[Audio Encoder](#audio-encoder-tonies--audio-encoder)**
- Bis zu 99 Audiodateien (MP3, AAC/M4A, WAV, FLAC, OGG, Opus, AIFF, WMA, AC3, DTS, TAF, MP4) zu einer TAF kodieren, ein Kapitel pro Datei
- Drag & Drop, Kapitelreihenfolge per Drag & Drop oder natürlicher Sortierung
- Zielordner in der Bibliothek wählen, neue Ordner anlegen
- Lokales Dekodieren mit dem mitgelieferten FFmpeg von Qt, keine Zusatzinstallation; die Opus-Kodierung übernimmt die TeddyCloud
- Optional in einem Schritt einen Custom-Tonie anlegen: Serie, Episode und Cover aus den Audio-Tags, Titel aus den Dateinamen, Cover wird automatisch hochgeladen

**[Custom-Modelle](#custom-modelle-tonies--custom-modelle)**
- Eigene Modelle in `tonies.custom.json` anlegen, bearbeiten, duplizieren, umbenennen und löschen
- Filtern, nach vielen Feldern sortieren, seitenweise Anzeige, Blättern mit optionalem automatischem Speichern
- Bilder aus `custom_img` (mit Upload und neuen Ordnern) oder aus dem offiziellen Katalog wählen
- Audio-ID und Hash direkt aus einer `.taf` der Bibliothek übernehmen
- Prüfungen wie in der Weboberfläche (doppelte IDs, doppelte Audio-Paare, Sprachcodes)

**[TeddyAudio Playlists](#teddyaudio-playlists-tonies--teddyaudio-playlists)**
- `.tap`-Dateien in der Bibliothek durchsuchen, Playlists anlegen, bearbeiten, umbenennen, verschieben, herunterladen und löschen
- Editor mit Mehrfachauswahl aus der Bibliothek und Kapitelreihenfolge
- Playlist einem Tonie zuweisen
- **In der App in eine TAF umwandeln**, statt auf FFmpeg auf dem Server angewiesen zu sein

**[Tonieboxen-Übersicht](#tonieboxen-übersicht-tonieboxen--tonieboxen)**
- Kacheln mit Name, Bild der Farbvariante, Hardware-Version, MAC-Adresse und Online-Status
- Zuletzt gespielter Tonie je Box, ein Klick öffnet ihn in der Tonie-Übersicht
- Box umbenennen und Modell wählen, API-Zugriff wieder freigeben
- Client-Zertifikate per Drag & Drop hochladen
- Box-spezifische Einstellungen mit „überschrieben“ je Option und den Einstellungsstufen Basic/Detail/Expert
- Box entfernen

**Allgemein**
- Läuft unter Windows, macOS und Linux; fertige Programme ohne Python-Installation
- Optional HTTP Basic Auth für eine TeddyCloud hinter einem Reverse-Proxy; das Passwort liegt im Schlüsselbund des Systems
- Tastenkürzel für alle Seiten (Strg+T, Strg+E, Strg+P, Strg+M, Strg+B, F5 …)

## Download

- **Fertige Programme** für Windows, macOS und Linux liegen bei den [GitHub Releases](https://github.com/bennsel/teddycloud-desktop/releases). Herunterladen, entpacken, starten – eine Python-Installation ist nicht nötig.
- **Aus dem Quellcode** mit [uv](https://docs.astral.sh/uv/) starten, siehe nächster Abschnitt.

## Installation und Start aus dem Quellcode

Voraussetzung: [uv](https://docs.astral.sh/uv/) und Python ≥ 3.11 (uv installiert die passende Version bei Bedarf selbst).

```bash
git clone https://github.com/bennsel/teddycloud-desktop.git
cd teddycloud-desktop
uv sync                                # Abhängigkeiten installieren
uv run teddycloud-desktop              # Anwendung starten
uv run python -m teddycloud_desktop    # alternativ
```

Für die Audio-Wiedergabe nutzt Qt das FFmpeg-Backend, das im PyQt6-Paket enthalten ist. Künstler, Album und Cover der Audiodateien liest die Python-Bibliothek [mutagen](https://mutagen.readthedocs.io/), die `uv sync` mitinstalliert.

## Menüs

| Menü | Eintrag | Tastenkürzel | Funktion |
|------|---------|--------------|----------|
| Datei | Einstellungen … | Strg+, | TeddyCloud-Endpunkt, Zeitlimit und Basic Auth festlegen |
| Datei | Beenden | Strg+Q | Anwendung schließen |
| **Tonies** | **Tonies** | Strg+T | Tonie-Übersicht mit Kacheln öffnen und laden |
| **Tonies** | **Audio Encoder** | Strg+E | Audiodateien zu einer TAF-Datei in der TeddyCloud-Bibliothek kodieren |
| **Tonies** | **TeddyAudio Playlists** | Strg+P | Playlists (`.tap`) anlegen, bearbeiten und Tonies zuweisen |
| **Tonies** | **Custom-Modelle** | Strg+M | Eigene Tonie-Modelle in `tonies.custom.json` anlegen, bearbeiten, duplizieren und löschen |
| **Tonieboxen** | **Tonieboxen** | Strg+B | Übersicht der Tonieboxen öffnen und laden |
| Bearbeiten | Kopieren | Strg+C | Ausgewählte Tonies (ohne Auswahl: alle gefilterten) als Text in die Zwischenablage kopieren (Serie, Episode, Modell, UID, tabulatorgetrennt) |
| Bearbeiten | Alles auswählen | Strg+A | Auswahlmodus aktivieren und alle gefilterten Tonies auswählen |
| Ansicht | Aktualisieren | F5 | Aktuelle Seite neu laden (Tonies, Tonieboxen oder den Ordnerbaum im Audio Encoder) |
| Ansicht | Filter anzeigen | Strg+F | Filterleiste ein-/ausblenden |
| Hilfe | Über TeddyCloud Desktop / Über Qt | – | Infodialoge (Version, Projekt-Link, Lizenz, Markenhinweis) |

Unter macOS verschiebt Qt „Einstellungen“, „Beenden“ und „Über …“ automatisch ins Programm-Menü, so wie es auf dem Mac üblich ist.

## Einstellungen

- **TeddyCloud-Endpunkt**: Basis-URL der TeddyCloud, z. B. `http://teddycloud.local` oder `http://192.168.1.10:8080`. Wird kein Schema angegeben, wird `http://` ergänzt; abschließende `/` werden entfernt. Läuft die TeddyCloud hinter einem Reverse-Proxy unter einem Unterpfad, gehört dieser Pfad mit in den Endpunkt.
- **Zeitlimit für Anfragen**: 1–300 Sekunden (Standard: 10). Gilt nicht für Downloads (Audio-Download, Cloud-Download).
- **Basic-Auth-Benutzer / -Passwort** (optional): für TeddyCloud-Instanzen hinter einem Reverse-Proxy mit HTTP Basic Auth. Ist ein Benutzer gesetzt, wird bei jeder Anfrage an die TeddyCloud der Header `Authorization: Basic …` mitgeschickt. An fremde Server (z. B. externe Bild-URLs aus dem Tonie-Katalog) werden die Zugangsdaten nicht gesendet. Für die Audio-Wiedergabe stehen die Zugangsdaten in der Stream-URL (`http://user:pass@host/…`), weil der Mediaplayer keine eigenen Header setzen kann. Ein Passwort ohne Benutzer wird abgelehnt.

**Speicherung des Passworts:** Das Basic-Auth-Passwort liegt im Schlüsselbund des Betriebssystems (über die Bibliothek [keyring](https://pypi.org/project/keyring/): Windows-Anmeldeinformationsverwaltung, macOS-Schlüsselbund, unter Linux Secret Service wie GNOME Keyring oder KWallet), Dienst `teddycloud-desktop`, Konto `basic-auth`. Nur wenn kein Schlüsselbund verfügbar ist, wird es im Klartext in den Einstellungen gespeichert (siehe Speicherorte unten); der Einstellungsdialog weist dann darauf hin. Ein noch im Klartext gespeichertes Passwort aus einer älteren Version wird automatisch in den Schlüsselbund übernommen.

> **Hinweis zur Sicherheit:** Basic Auth überträgt die Zugangsdaten nur Base64-kodiert, also praktisch unverschlüsselt. Für Zugriffe über das Internet sollte deshalb ein `https://`-Endpunkt verwendet werden.

Die übrigen Einstellungen (inklusive der zuletzt gewählten Toniebox) werden über `QSettings` (Organisation und Anwendung jeweils `teddycloud-desktop`) gespeichert:

| System | Speicherort |
|--------|-------------|
| Linux | `~/.config/teddycloud-desktop/teddycloud-desktop.conf` |
| Windows | Registry: `HKEY_CURRENT_USER\Software\teddycloud-desktop\teddycloud-desktop` |
| macOS | `~/Library/Preferences/com.teddycloud-desktop.teddycloud-desktop.plist` |

Ist noch kein Endpunkt hinterlegt, öffnet „Tonies → Tonies“ automatisch den Einstellungsdialog.

## Tonie-Übersicht (Tonies → Tonies)

### Kopfzeile

- **Toniebox**: Auswahl des Inhaltsverzeichnisses („Overlay“). Wie in der Weboberfläche werden Tonieboxen mit demselben Inhaltsverzeichnis (`core.contentdir`) zu einem Eintrag zusammengefasst, z. B. „Kinderzimmer, Wohnzimmer“. Hat keine Box das Standardverzeichnis, erscheint zusätzlich „TeddyCloud Standard-Inhaltsverzeichnis“. Die Auswahl wird gespeichert.
- **Aktualisieren**: lädt Tonieboxen, Tonies und die zuletzt gespielten Tonies neu.

### Werkzeugleiste

- **Filter**: blendet die Filterleiste ein. Alle Filter wirken sofort:
  - Suche (Serie, Episode, Modell, UID, RUID oder Quelle), Serie, Episode, Sprache
  - Gültig, Inhalt vorhanden, Live, Cloud gesperrt, Cloud-Auth: jeweils „egal“, „ja“ oder „nein“
  - „Nur zuletzt auf einer Toniebox gespielte“
  - „Filter zurücksetzen“
- **Auswählen**: schaltet den Auswahlmodus ein. Jede Kachel bekommt eine Checkbox, und es erscheinen:
  - „Alle auswählen“ (alle gefilterten Tonies, auch auf anderen Seiten) und „Auswahl aufheben“
  - **Aktionen** für die Auswahl: Cloud deaktivieren/aktivieren, Live aktivieren/deaktivieren, Tags ausblenden (mit Rückfrage), Export als CSV, als JSON, als JSON mit vollständigen Informationen (Rohdaten von `/api/getTagIndex`), als HTML und als HTML mit eingebetteten Bildern. Die Dateinamen beginnen wie in der Weboberfläche mit einem Zeitstempel, z. B. `20261002_143000_selected_tonies.csv`.
  - „Abbrechen“ beendet den Auswahlmodus.
- **Seiten**: 24, 48 (Standard) oder 96 Tonies pro Seite oder „Zeige alle“, dazu Blättern mit ‹ und ›.

Angezeigt werden wie in der Weboberfläche nur echte Tonies/Tags: keine System-Sounds (`type == "system"`) und keine ausgeblendeten (`hide == true`). Sortiert wird nach Serie und dann Episode, mit natürlicher Sortierung („Folge 2“ vor „Folge 10“).

### Kachel

Von oben nach unten:

1. **Serie**, bei leerer Serie das Modell, ohne beides „Tonie/Tag“. Rechts daneben ein Sprachkürzel (z. B. `GB`), falls die Sprache von der häufigsten Sprache aller Tonies abweicht, und im Auswahlmodus die Checkbox.
2. **Tonie-Bild**. Ist der Figur ein anderer Inhalt zugewiesen (`sourceInfo` weicht ab), wird unten rechts zusätzlich das Bild des zugewiesenen Inhalts eingeblendet. Der Tooltip nennt beide Titel.
3. **Episode** (fett)
4. **RFID-Tag-ID** (UID, z. B. `E0:04:03:50:0D:4F:2A:1B`, markierbar). Ohne Episode steht die UID an deren Stelle.
5. **Aktionen** (Icons):

| Icon | Aktion |
|------|--------|
| ⓘ Info | Informationsdialog (siehe unten) |
| ✎ Stift | Bearbeitungsdialog (siehe unten) |
| ▶ Play | Inhalt in der Wiedergabeleiste am unteren Fensterrand abspielen. Abspielbar ist ein Tonie, wenn sein Inhalt gültig ist (`valid`) oder die Quelle ein Radiostream (`http…`) ist. Sonst ist das Icon ausgegraut. |
| ⤓ Download | Erscheint statt Play, wenn der Inhalt noch fehlt, aber aus der Tonie-Cloud geladen werden kann (`downloadTriggerUrl`). Startet den Download auf der TeddyCloud und aktualisiert danach die Kachel. Ausgegraut, wenn die Cloud deaktiviert ist (`cloud.enabled`). |
| ☁ Cloud | Schaltet `nocloud` um. Rot durchgestrichen bedeutet: Cloud-Zugriff gesperrt. |
| ⇄ Live | Schaltet `live` um. Rot bedeutet: Live-Modus aktiv. |

Ein blauer oberer Rand markiert Tonies, die zuletzt auf einer Toniebox gespielt wurden. Der Tooltip der Kachel nennt Box und Zeitpunkt.

### Informationsdialog

- Titel: Serie und Episode, bei zugewiesenem anderen Inhalt dessen Titel. Darunter die UID.
- Großes Bild und gegebenenfalls ein Hinweis auf den zugewiesenen Inhalt.
- „Zuletzt gespielt auf“ mit Toniebox und Zeitpunkt.
- Gültig, Existiert, Quelle, Modell.
- Trackliste: Stimmen die Track-Positionen (`trackSeconds`) mit der Trackliste überein, lässt sich jeder Track einzeln ab seiner Startposition abspielen.
- **Download TAF als \*.ogg**: speichert den Audioinhalt als Ogg-Datei.
- **Tonie/Tag ausblenden** (mit Rückfrage): setzt `hide=true`. Wieder einblenden lässt sich ein Tonie nur, indem man ihn auf eine Toniebox stellt.

### Bearbeitungsdialog

- **Quelle** (zugewiesener Inhalt): Freitext, z. B. `lib://Ordner/Datei.taf` oder eine Radiostream-URL `http://…`. Dazu gibt es Schaltflächen zum Leeren, zum Zurücksetzen auf den ursprünglichen Wert und zur Dateiauswahl aus der TeddyCloud-Bibliothek (Ordner per Doppelklick öffnen, `.taf`/`.tap`-Dateien auswählen).
- **Modell**: Freitext mit Leeren/Zurücksetzen. Darunter eine Suche im Tonie-Katalog (Modellnummer, Serie oder Episode). Ein Klick auf einen Treffer übernimmt das Modell.
- **Speichern** ist nur aktiv, wenn sich etwas geändert hat. Der Ablauf entspricht der Weboberfläche:
  1. Ein geändertes, nicht leeres Modell wird gegen den Katalog geprüft. Unbekannte Modelle werden abgelehnt.
  2. Bei geänderter Quelle wird `source` gesetzt. Außerdem wird `nocloud=true` gesetzt (damit die Cloud den eigenen Inhalt nicht überschreibt) und `live` passend zur Quelle: an für `http…`-Streams, sonst aus.
  3. Ein geändertes Modell wird über `tonie_model` gesetzt.
  4. Die Kachel wird neu geladen.

### Nicht übernommene Funktionen der Weboberfläche

Diese Teile von `/web/tonies` sind bewusst nicht enthalten:

- **Radiostream-Suche**: Sie fragt einen externen Dienst (radio-browser) ab. Stream-URLs lassen sich direkt als Quelle eintragen.
- **„Audio aus Modell setzen“, „Modell aus Audio setzen“, vorherige/nächste Episode zuweisen**: Dafür müsste die Bibliothek vollständig nach Audio-IDs durchsucht werden.
- **Eigene Filterausdrücke und gespeicherte Filter**
- **Live-Prüfung der Boxine-Cloud-Verbindung**: Der Cloud-Download wird nur anhand der Einstellung `cloud.enabled` freigegeben.

## Audio Encoder (Tonies → Audio Encoder)

Nachgebaut nach `/web/tonies/encoder`. Mehrere Audiodateien werden zu einer TAF-Datei kodiert, jede Datei wird ein Kapitel. Die TAF-Datei landet in der Bibliothek der TeddyCloud und kann danach im Bearbeitungsdialog eines Tonies als Quelle (`lib://…`) gewählt werden.

1. **Dateien hinzufügen**: per „Datei(en) auswählen“ oder per Drag & Drop in die Liste, höchstens 99 Dateien. Unterstützt werden dieselben Formate wie in der Weboberfläche: `.mp3 .aac .m4a .wav .flac .ogg .opus .aiff .aif .wma .ac3 .dts .taf .mp4`. Andere Dateien werden mit „Nicht unterstützter Dateityp!“ abgelehnt.
2. **Reihenfolge** (= Kapitelreihenfolge): Einträge per Drag & Drop verschieben, „Alphabetisch sortieren (lexikografisch)“, über „…“ auch „mit Zahlenreihenfolge“ (Kapitel 2 vor Kapitel 10). Mit „Datei entfernen“ bzw. Entf und „Liste leeren“ lässt sich die Liste aufräumen.
3. **Zielordner** im Ordnerbaum der Bibliothek wählen. Unterordner werden beim Aufklappen geladen. „Neuen Ordner anlegen“ legt einen Unterordner im gewählten Ordner an und wählt ihn aus.
4. **Dateiname** ohne `.taf`. Bei genau einer Datei wird deren Name vorgeschlagen. Wie in der Weboberfläche sind die Zeichen `< > : " / \ | ? *` nicht erlaubt.
5. **Custom-Tonie anlegen (optional)**: Mit dem Haken wird nach dem Kodieren direkt ein Custom-Modell für die neue TAF-Datei angelegt (siehe unten). Ohne Haken wird wie bisher nur kodiert.
6. **Konvertieren**: Der Fortschrittsbalken zeigt erst das Dekodieren, dann den Upload, danach wartet er, während die TeddyCloud kodiert. „Abbrechen“ stoppt jederzeit. Nach Erfolg wird die Liste geleert.

### Custom-Tonie direkt beim Kodieren anlegen

- **Modell** (vorgeschlagen: nächste freie ID `custom-<n>`), **Serie** und **Episode**.
- **Serie und Episode aus den Audio-Tags:**
  - Die **Serie** kommt aus dem Künstler. Der Album-Interpret (`album_artist`) wird bevorzugt, weil er über alle Dateien gleich ist; sonst gilt der Track-Künstler. Ohne Künstler folgt die Serie wie bisher dem TAF-Dateinamen.
  - Die **Episode** kommt aus dem Album.
  - Je Feld zählt der erste Treffer in Listenreihenfolge. Eine Infozeile zeigt, woher die Werte stammen.
  - Selbst eingetragene Werte werden nie überschrieben; die Infozeile meldet dann „eigene Eingabe bleibt“.
- **Tracks** werden aus den Dateinamen ohne Endung übernommen, in der Reihenfolge der Liste, die auch die Kapitelreihenfolge ist. Aus `01 Intro.mp3` wird z. B. der Track `01 Intro`.
- **Gelesene Formate** (über mutagen):

  | Format | Künstler / Album | Cover |
  |--------|------------------|-------|
  | MP3, AIFF | ID3 (`TPE2`/`TPE1`, `TALB`) | ID3 `APIC`, Frontcover bevorzugt |
  | FLAC, OGG Vorbis, OGG Opus | Vorbis-Kommentare (`ALBUMARTIST`/`ARTIST`, `ALBUM`) | FLAC-Bildblock bzw. `METADATA_BLOCK_PICTURE` |
  | M4A/MP4/AAC im MP4-Container | `aART`/`©ART`, `©alb` | `covr` |
  | WMA | `WM/AlbumArtist`/`Author`, `WM/AlbumTitle` | `WM/Picture` |
  | WAV | ID3 oder RIFF-INFO (`IART`, `IPRD`) | ID3 `APIC` |

  `.taf`, rohes AAC (ADTS), AC3 und DTS enthalten keine solchen Tags.
- **Bild aus den Audiodateien:** Die App nimmt in Listenreihenfolge das erste eingebettete Cover.
  - Der Bereich zeigt eine Vorschau mit der Quelldatei.
  - „Bild aus den Audiodateien übernehmen“ ist automatisch angehakt, sobald ein Cover gefunden wurde.
  - Nach dem Kodieren wird das Cover auf höchstens 800 px verkleinert, als `custom_img/<modell>.jpg` hochgeladen (PNG bei Transparenz) und als Bild des Modells eingetragen.
  - Ein in „Weitere Angaben“ von Hand gewähltes Bild hat Vorrang und nimmt den Haken weg. Setzt man ihn wieder, gilt das Cover.
  - Scheitert der Bild-Upload, wird der Tonie ohne Bild angelegt, und die Meldung sagt das.
- **„Weitere Angaben …“** öffnet den Bearbeitungsdialog der Custom-Modelle, ohne Audio-Teil. Dort lassen sich Bild, Titel, No, Release, Sprache, Kategorie und die Tracks von Hand anpassen. Angepasste Tracks werden statt der Dateinamen verwendet.
- **Vor dem Kodieren** werden die Angaben geprüft: Pflichtfelder, Sprachcode, Release und doppelte Modell-ID. Bei Fehlern wird nicht kodiert.
- **Nach dem Kodieren**:
  - Die App liest den Ordner der neuen Datei über `/api/fileIndexV2`. Aus dem TAF-Header kommt der vom Server berechnete Hash; die Audio-ID muss dabei mit der beim Upload übergebenen übereinstimmen.
  - Dann legt sie das Modell mit dieser Audio-Zuordnung über `/api/toniesCustomJsonUpsert` an.
  - Danach sind die Felder für den nächsten Tonie zurückgesetzt.
- **Fehlerfall**: Scheitert nur das Anlegen des Modells, bleibt die TAF-Datei erhalten. Die Meldung erklärt, dass das Modell unter „Tonies → Custom-Modelle“ nachgeholt werden kann.

### Wie kodiert wird

Wie bei „Encoding auf dem Server“ in der Weboberfläche:

- Jede Datei wird lokal in 48 kHz Stereo 16 Bit PCM umgewandelt. Statt der Web Audio API übernimmt das `QAudioDecoder` mit dem FFmpeg-Backend von Qt, also ohne zusätzliche Installation.
- Die PCM-Daten werden als temporäre Dateien zwischengespeichert, damit lange Hörspiele nicht im Arbeitsspeicher liegen, und nach dem Upload gelöscht. Pro Stunde Audio fallen dabei rund 690 MB an, die auch übertragen werden.
- Upload: `POST /api/pcmUpload?name=<Name>.taf&audioId=<Unix-Zeit − 0x50000000>&path=<Ordner>&special=library` mit einem `multipart/form-data`-Teil je Datei. Die TeddyCloud erzeugt daraus die TAF-Datei mit der Bitrate aus ihrer Einstellung `encode.bitrate`. Wie in der Weboberfläche ist die Audio-ID die Unix-Zeit minus 0x50000000. Zusätzlich bekommt bei mehreren Kodierungen in derselben Sekunde jede eine eigene, höhere ID.
- `.taf`-Dateien als Eingabe: Der 4096-Byte-Header wird übersprungen und nur der Ogg/Opus-Teil dekodiert.
- Der `boundary` im `Content-Type`-Header wird ohne Anführungszeichen gesendet. Der HTTP-Server der TeddyCloud (CycloneTCP) entfernt keine Anführungszeichen und bliebe sonst beim Einlesen hängen. Das gilt auch für den Zertifikat-Upload.
- Kommen während des Uploads 60 Sekunden lang keine Daten mehr an, wird abgebrochen und eine Meldung angezeigt, z. B. bei einem Reverse-Proxy mit Größenlimit wie nginx `client_max_body_size`. Das anschließende Kodieren auf der TeddyCloud hat kein Zeitlimit.
- Fortschritt und Fehler werden zusätzlich auf der Konsole protokolliert (Logger `teddycloud_desktop`).

**Nicht übernommen:** die Option „Encoding im Browser“. Die Weboberfläche nutzt dafür einen WebAssembly-Opus-Encoder und lädt die fertige TAF-Datei über `/api/tafUpload` hoch. Ein vergleichbarer lokaler Opus/TAF-Encoder würde eine zusätzliche native Bibliothek erfordern. Die Einstellung `encode.use_frontend` wird deshalb ignoriert.

## Custom-Modelle (Tonies → Custom-Modelle)

Nachgebaut nach `/web/tonies/customeditor`. Custom-Modelle sind eigene Einträge in `tonies.custom.json` mit Serie, Episode, Bild, Tracks und optionaler Audio-Zuordnung. Ein Tonie bekommt sie im Bearbeitungsdialog der Tonie-Übersicht über das Feld „Modell“ zugewiesen und zeigt dann deren Titel und Bild.

### Übersicht

- **Kacheln** mit Serie (bzw. Modell), Bild, Episode und Modell-ID. Ein Klick aufs Bild öffnet eine Vorschau.
- **Aktionen je Kachel**:
  - Bearbeiten
  - Duplizieren: neue ID `custom-<n>`, an den Titel wird „Kopie“ angehängt
  - Löschen, mit Rückfrage
- **„Neues Modell“** schlägt automatisch die nächste freie ID `custom-<n>` vor.
- **Filter**:
  - Suchtext mit Auswahl der durchsuchten Felder („In Feldern suchen“, Standard: Serie und Modell)
  - Serie, Episode, Sprache
- **Sortierung** nach Serie (dann Episode), Modell, Titel, Episode, Release, Sprache, Kategorie oder No, auf- oder absteigend, mit Zahlenreihenfolge.
- **Seiten** mit 24, 48, 96 oder 192 Modellen oder „Zeige alle“.

### Bearbeitungsdialog

- **Pflichtfelder:** Modell, Serie. Dazu Episode.
- **Medien und Bilder:**
  - Bildpfad mit Vorschlägen aus `custom_img` und Vorschau; ein Klick auf die Vorschau vergrößert.
  - „Bild auswählen“ bietet zwei Reiter:
    - *Custom:* Ordner von `custom_img` mit Vorschaubildern, „Bild hochladen …“ und „Neuer Ordner“
    - *Original:* Bild-URLs aus `tonies.json`, Suche mit mehreren Wörtern in beliebiger Reihenfolge
- **Optionale Metadaten:**
  - No, Titel
  - Release (nur Ziffern)
  - Sprache: muss ein gültiger Code wie `de-de` sein, mit Vorschlägen
  - Kategorie: Vorschläge aus vorhandenen Kategorien, häufigste zuerst
- **Audio-Zuordnung:** Paare aus Audio-ID und Hash.
  - Die Ordnerschaltfläche wählt eine `.taf`-Datei aus der Bibliothek und übernimmt Audio-ID und Hash aus deren TAF-Header.
  - Bereits zugeordnete Paare werden als `lib://…`-Pfad angezeigt, sofern die Datei in der Bibliothek liegt. Dafür wird die Bibliothek einmal im Hintergrund durchsucht.
  - Dazu Leeren, Zurücksetzen und weitere Paare hinzufügen.
- **Tracks:** Liste mit Hinzufügen und Entfernen.
- **Hervorhebung:** Gegenüber dem gespeicherten Stand geänderte Felder sind gelb hinterlegt. „Speichern“ ist nur bei Änderungen aktiv.
- **Blättern:** Mit „‹ Zurück“ / „Weiter ›“ durch die gefilterte Liste. Mit „Beim Blättern speichern“ werden Änderungen dabei automatisch gesichert.

### Speichern

Der Ablauf entspricht der Weboberfläche:

1. Formular prüfen: Pflichtfelder, Release numerisch, gültiger Sprachcode.
2. Gesamte Liste prüfen: Doppelte Modell-IDs und doppelte Audio-ID/Hash-Paare werden abgelehnt. Ein Modell, das es auch im offiziellen `tonies.json` gibt, erzeugt nur eine Warnung.
3. Bei geänderter Modell-ID: Rückfrage „Modell umbenennen“, dann `toniesCustomJsonRename`. Verknüpfte Tonies werden automatisch umgestellt. Optional lässt sich die Modellzuordnung stattdessen entfernen; das Audio bleibt.
4. `toniesCustomJsonUpsert` mit dem Eintrag. Leere Felder werden weggelassen, unvollständige Audio-Paare und leere Tracks entfernt.

Fehlermeldungen der TeddyCloud (z. B. „Target model already exists“) erscheinen im Dialog.

**Abweichungen von der Weboberfläche:**
- Bei leerer `tonies.custom.json` öffnet sich nicht automatisch der Dialog „Neues Modell“, sondern es erscheint ein Hinweis.
- Ein doppeltes Modell wird verständlicher als „Doppeltes Modell: …“ gemeldet.
- Es lassen sich mehrere Audio-Paare anlegen; die Weboberfläche kann nur vorhandene entfernen.

## TeddyAudio Playlists (Tonies → TeddyAudio Playlists)

Nachgebaut nach `/web/tonies/tap`. Eine TeddyAudio Playlist (TAP) ist eine JSON-Datei `<Name>.tap` in der Bibliothek:

```json
{
  "type": "tap",
  "audio_id": 1792625260,
  "filepath": "lib://Playlists/Party Mix.taf",
  "name": "Party Mix",
  "files": [
    {"filepath": "lib://Musik/lied1.mp3", "name": "Lied 1"},
    {"filepath": "lib://Musik/lied2.flac", "name": "Lied 2"}
  ]
}
```

**So wird eine TAP verwendet:** Man weist sie einem Tonie als Quelle zu (`lib://….tap`). Beim ersten Abspielen erzeugt die TeddyCloud mit FFmpeg aus den Dateien die TAF-Datei unter `filepath` und speichert sie für später (`tonie_audio_playlist.c`). Neu erzeugt wird sie, wenn die TAF fehlt oder ihre Audio-ID nicht zu `audio_id` passt. Wer `audio_id` auf 0 setzt, erzwingt also einen Neuaufbau. Die TeddyCloud kennzeichnet die Funktion selbst als „noch in Entwicklung“.

### Übersicht

- Ordner der Bibliothek mit allen `.tap`-Dateien, mit Name, Größe und Datum. Ein Doppelklick auf einen Ordner öffnet ihn, ‹↑› führt eine Ebene höher, ein Filterfeld hilft beim Suchen.
- **Neue TAP erstellen** (im aktuellen Ordner) und **Neuen Ordner anlegen**.
- **Aktionen für die gewählte TAP** (Buttons oder Rechtsklick):
  - Bearbeiten
  - **In TAF umwandeln** (siehe unten)
  - **Einem Tonie zuweisen**: Tonie aus der Liste der gewählten Toniebox wählen (mit Suche). Wie in der Weboberfläche wird `source` gesetzt, die Cloud gesperrt (`nocloud`) und `live` ausgeschaltet.
  - JSON anzeigen (auch per Doppelklick)
  - Herunterladen
  - Umbenennen
  - Verschieben (Ordnerauswahl)
  - Löschen

### In TAF umwandeln (in der GUI statt auf dem Server)

Statt die TeddyCloud die TAF beim ersten Abspielen per FFmpeg erzeugen zu lassen, was dort oft scheitert, erstellt die App die TAF selbst. Auslöser ist „In TAF umwandeln“ als Button oder im Kontextmenü der markierten Zeile.

1. Jede Datei der TAP wird heruntergeladen (`lib://…` über `/library/…`, `content://…` über `/content/…`, `http(s)://` direkt) und lokal mit FFmpeg (in Qt enthalten) zu 48 kHz Stereo PCM dekodiert, wie im Audio Encoder.
2. Fehlende Ordner des Ziels werden angelegt.
3. Die PCM-Daten werden per `/api/pcmUpload` genau an den **Dateipfad Playlist** der TAP hochgeladen; jede Datei wird ein Kapitel. **Eine vorhandene TAF wird dabei überschrieben.**
4. Die App prüft, ob die neue TAF mit der erwarteten Audio-ID in der Bibliothek liegt.
5. Die neue Audio-ID wird in die `.tap` geschrieben; dieselbe Datei wird überschrieben.

**Warum die Toniebox die Datei erkennt:** Liegt am `filepath` einer TAP eine gültige TAF, verwendet die TeddyCloud sie direkt („TAP_CACHED“) und erzeugt nichts mehr selbst. Jede Umwandlung bekommt eine neue Audio-ID. So lädt auch eine Toniebox, die die alte Fassung schon gespeichert hat, den neuen Inhalt.

**Einschränkung:** Herunterladen und Dekodieren der Quelldateien passieren in der GUI. Die eigentliche Opus-Kodierung zur TAF macht der eingebaute Encoder der TeddyCloud, derselbe wie beim Audio Encoder und in der Weboberfläche, nicht FFmpeg auf dem Server.

**Während der Umwandlung:**
- Ein Fortschrittsfenster zeigt Laden, Dekodieren, Hochladen und das Schreiben der TAF auf dem Server.
- „Abbrechen“ stoppt die Umwandlung jederzeit.
- Die TAP-Seite ist so lange gesperrt.
- Temporäre Dateien werden in jedem Fall gelöscht.

### Editor

- **Audio-ID**: Standard ist die aktuelle Unix-Zeit, wie in der Weboberfläche. 0 erzwingt den Neuaufbau der TAF.
- **Dateipfad Playlist** (Pflicht): Ordner („Ordner …“, mit „Neuen Ordner anlegen“) und Dateiname der zu erzeugenden `.taf`. Der Dateiname folgt dem TAP-Namen, bis man ihn selbst ändert.
- **TAP Name** (Pflicht): zugleich der Dateiname der `.tap`. Ungültige Zeichen werden wie im Web durch `_` ersetzt.
- **Dateien** (Reihenfolge = Kapitel, höchstens 99):
  - „Datei hinzufügen“ öffnet die Bibliothek mit Mehrfachauswahl; erlaubt sind alle Formate, die FFmpeg verarbeitet.
  - Je Zeile: Dateipfad (Leeren, Auswahl aus der Bibliothek), Beschreibung, ↑/↓ und Entfernen.
- **Speichern** lädt die JSON als `<Name>.tap` per `/api/fileUpload` in den aktuellen Ordner hoch.

**Abweichungen von der Weboberfläche:**
- Wird beim Bearbeiten der Name geändert, entfernt die App die alte `.tap`-Datei; im Web bleibt sie liegen.
- Gibt es eine gleichnamige TAP schon, fragt die App vor dem Überschreiben.
- Eine Playlist braucht mindestens eine Datei, weil die TeddyCloud sonst keine TAF erzeugen kann.
- Die Reihenfolge wird mit ↑/↓ statt per Drag & Drop geändert.

## Tonieboxen-Übersicht (Tonieboxen → Tonieboxen)

Überschrift „Deine Tonieboxen“ mit „Aktualisieren“. Ist in der TeddyCloud `core.allowNewBox` aktiv, erscheint der Warnhinweis „Neue Tonieboxen erlaubt“. Ohne registrierte Box steht „Keine Tonieboxen gefunden.“ da.

### Kachel

1. **Name** der Box (`boxName`).
2. **Bild der Farbvariante** aus `tonieboxes.json` bzw. `tonieboxes.custom.json`, inklusive des dort hinterlegten Ausschnitts (`crop`). Ist kein Modell gesetzt, erscheint ein Platzhalter mit dem Hinweis, das Modell über ✎ zu wählen.
3. **Zuletzt gespielter Tonie** unten rechts im Bild, mit Tooltip (Titel und Zeitpunkt). Ein Klick öffnet die Tonie-Übersicht mit dieser Box als Toniebox-Auswahl und filtert auf den Tonie, wie der Link in der Weboberfläche.
4. **Hardware-Version** (`CC3200`, `CC3235`, `ESP32`, `TB2`, sonst `MAC`) und die **MAC-Adresse** im Format `AA:BB:CC:DD:EE:FF`. Ist `frontend.check_cc3200_cfw` aktiv und antwortet eine CC3200-Box unter ihrer IP auf `/api/ajax?cmd=box-battery&sub=stats`, wird die MAC zum Link auf das Web-Frontend der Custom-Firmware.
5. **Aktionen:**

| Icon | Aktion |
|------|--------|
| WLAN grün / grau | Online bzw. offline. Der Tooltip nennt bei offline „zuletzt online“ (`internal.last_connection`). |
| Schloss rot | Statt des WLAN-Symbols, wenn der API-Zugriff der Box deaktiviert ist (`toniebox.api_access=false`). Ein Klick aktiviert ihn wieder. |
| ✎ Bearbeiten | Name und Modell (Farbvariante, mit Vorschau) ändern. Gespeichert wird über `boxName` bzw. `boxModel`, danach wird die Konfiguration geschrieben. |
| Schild Zertifikate | Client-Zertifikate (`ca.der`, `client.der`, `private.der`) per Drag & Drop oder Dateiauswahl hochladen. Angezeigt wird das Zielverzeichnis `core.certdir` mit dem Hinweis, ob es boxspezifisch ist oder der Default-Pfad. Nur `*.der` wird angenommen. |
| Zahnrad Einstellungen | Boxspezifische Einstellungen (siehe unten) |
| Papierkorb Löschen | Box nach Rückfrage aus der TeddyCloud entfernen (`removeOverlay`) |

### Einstellungen einer Toniebox

Es werden dieselben Einstellungen angezeigt wie in der Weboberfläche: `core.certdir`, `core.client_cert.*`, `core.flex_*`, `core.contentdir`, `toniebox.*` und ausgewählte `cloud.*`-Optionen. Gruppiert wird nach Kategorie („Category core“, „.client_cert“ …). Welche Optionen erscheinen, hängt vom Settings level ab.

- Jede Zeile hat Beschriftung (Tooltip: Beschreibung und Schlüssel), Eingabefeld (Schalter, Zahl oder Text) und **„überschrieben“**. Nur mit Haken gilt ein eigener Wert für diese Box. Wird der Haken entfernt, zeigt das Feld wieder den allgemeinen TeddyCloud-Wert, und beim Speichern wird der Box-Wert zurückgesetzt (`/api/settings/reset/…`).
- **Speichern** sendet alle geänderten Werte und schreibt danach die Konfiguration. **Verwerfen** stellt den geladenen Stand wieder her.
- **Settings level** Basic / Detail / Expert gilt für die gesamte TeddyCloud. Es lässt sich nur ohne ungespeicherte Änderungen umschalten und lädt die Liste neu.

### Nicht übernommen

Die Unterseiten der Tonieboxen-Navigation (Box-Setup, Flash-Anleitungen für CC3200/CC3235/ESP32/TB2, Box-Version bestimmen, Plugins) sind Anleitungen und nicht Teil von `/web/tonieboxes`. Sie fehlen deshalb hier.

## Verwendete TeddyCloud-API

Alle Anfragen gehen an den eingestellten Endpunkt, mit Basic Auth, falls konfiguriert. Bei falschen oder fehlenden Zugangsdaten (HTTP 401) erscheint die Meldung „Host requires authentication“. `overlay` ist die ID der gewählten Toniebox. Bei leerem Wert wird der Parameter weggelassen, dann gilt das Standard-Inhaltsverzeichnis.

| Methode und Pfad | Zweck |
|------------------|-------|
| `GET /api/getBoxes` | Tonieboxen (`ID`, `boxName`) für die Toniebox-Auswahl |
| `GET /api/settings/get/core.contentdir?overlay=…` | Inhaltsverzeichnis je Box zum Gruppieren |
| `GET /api/settings/get/internal.last_ruid?overlay=…` und `…/internal.last_ruid_time` | Zuletzt gespielter Tonie je Box (RUID und Unix-Zeit) |
| `GET /api/settings/get/cloud.enabled` | Ob der Cloud-Download angeboten wird |
| `GET /api/getTagIndex?overlay=…` | Alle Tonies (siehe unten) |
| `GET /api/getTagInfo?ruid=…&overlay=…` | Einen Tonie nach einer Änderung neu laden (Antwort: `{"tagInfo": {…}}`) |
| `POST /content/json/set/<ruid>?overlay=…` | Eigenschaft ändern, Body `text/plain` mit genau einem Wert: `live=true`, `nocloud=false`, `hide=true`, `source=<URL-kodiert>` oder `tonie_model=<URL-kodiert>` |
| `GET /api/toniesJsonSearch?searchModel=…&searchSeries=…&searchEpisode=…` | Katalogsuche im Bearbeitungsdialog und Prüfung des Modells |
| `GET /api/fileIndexV2?path=…&special=library` | Ordnerinhalt der Bibliothek für die Dateiauswahl |
| `GET <audioUrl>` | Wiedergabe und Download, z. B. `/content/download/…?overlay=…&skip_header=true`. Der Sprung zu einem Track nutzt HTTP-Range-Anfragen, die TeddyCloud unterstützt. |
| `GET <downloadTriggerUrl>` | Inhalt aus der Tonie-Cloud auf die TeddyCloud laden |
| `GET <picture>` | Tonie-Bilder: Relative Pfade wie `/cache/…` oder `/img_unknown.png` gehen an den Endpunkt, mit Basic Auth. Absolute URLs werden direkt geladen, mit Basic Auth nur bei gleichem Host und Port. Es laufen höchstens 4 Downloads gleichzeitig, der Rest wartet. Bei Zeitüberschreitung gibt es einen zweiten Versuch. |
| `GET /api/tonieboxesJson`, `GET /api/tonieboxesCustomJson` | Farbvarianten der Tonieboxen: `[{"id", "name", "img_src", "crop": [x, y, scale]}]` |
| `GET /api/settings/get/<key>?overlay=<Box-ID>` | Box-Status: `internal.online`, `internal.toniebox_firmware.boxIC` (1 = CC3200, 2 = CC3235, 3 = ESP32, 4 = TB2), `internal.last_connection`, `internal.last_ruid` (`ffffffffffffffff` = keiner), `internal.last_ruid_time`, `internal.ip`, `toniebox.api_access`; global: `core.allowNewBox`, `frontend.check_cc3200_cfw`, `core.settings_level` |
| `GET /api/settings/getIndex?overlay=<Box-ID>` | Alle Einstellungen der Box: `{"options": [{"ID", "label", "description", "type", "value", "overlayed", "level", "min", "max"}]}` |
| `POST /api/settings/set/<key>?overlay=<Box-ID>` | Einstellung setzen, Body `text/plain` mit dem Wert (`true`/`false`, Zahl oder Text). Antwort `OK` oder `ERROR`, beides mit HTTP 200. Leere Werte lehnt die TeddyCloud ab. |
| `POST /api/settings/reset/<key>?overlay=<Box-ID>` | Box-Wert entfernen, danach gilt wieder der allgemeine Wert |
| `GET /api/triggerWriteConfig` | Geänderte Einstellungen in die Konfigurationsdatei schreiben (nach jeder Änderung, wie in der Weboberfläche) |
| `POST /api/uploadCert?overlay=<Box-ID>` | Zertifikat hochladen (`multipart/form-data`, ein Teil je Datei) |
| `POST /api/settings/removeOverlay?overlay=<Box-ID>` | Toniebox löschen, Antwort `OK` |
| `GET /api/toniesCustomJson` | Alle Custom-Modelle (Inhalt von `tonies.custom.json`): `[{"model", "series", "episodes", "title", "no", "release", "language", "category", "pic", "audio_id": [...], "hash": [...], "tracks": [...]}]` |
| `GET /api/toniesJson` | Offizieller Katalog `tonies.json` (Warnung bei gleichen Modell-IDs, Kategorien, Original-Bilder) |
| `POST /api/toniesCustomJsonUpsert` | Custom-Modell anlegen oder ersetzen (gleiche Modell-ID), Body: JSON-Objekt. Antwort `OK`, bei Fehlern HTTP 400 mit Begründung. |
| `POST /api/toniesCustomJsonRename` | Body `{"fromModel", "toModel", "updateContentJson": true}` |
| `POST /api/toniesCustomJsonDelete` | Body `{"models": ["custom-1", …]}` |
| `GET /api/fileIndexV2?path=…&special=custom_img` | Ordner der eigenen Bilder. Bildpfade haben die Form `/custom_img/<ordner>/<datei>`. |
| `POST /api/fileUpload?path=…&special=custom_img` | Bild hochladen (`multipart/form-data`, Feld `file`) |
| `GET /library/<pfad>` | Inhalt einer Bibliotheksdatei, z. B. einer `.tap` zum Bearbeiten |
| `POST /api/fileUpload?path=…&special=library` | Datei in die Bibliothek hochladen (z. B. eine `.tap`; Feldname und Dateiname = `<Name>.tap`) |
| `POST /api/fileMove?special=library` | Umbenennen/Verschieben, Body `source=<pfad>&target=<pfad>` (URL-kodiert), Antwort `OK` |
| `POST /api/fileDelete?special=library` | Datei löschen, Body: Pfad, Antwort `OK` |
| `POST /api/dirCreate?special=library` | Ordner in der Bibliothek anlegen. Body `text/plain` mit dem vollständigen Pfad, z. B. `/Hörspiele/Neu`. Antwort `OK` oder eine Fehlermeldung. |
| `POST /api/pcmUpload?name=…&audioId=…&path=…&special=library` | Audio Encoder: PCM (48 kHz, Stereo, s16le, interleaved) je Datei als eigener Multipart-Teil. Die TeddyCloud kodiert daraus die TAF-Datei, jeder Teil wird ein Kapitel. |

### Antwort von `/api/getTagIndex`

```json
{
  "tags": [
    {
      "ruid": "a1b2c3d4e5f60708",
      "uid": "E0:04:03:50:0D:4F:2A:1B",
      "type": "tag",
      "valid": true,
      "exists": true,
      "live": false,
      "nocloud": false,
      "hasCloudAuth": true,
      "hide": false,
      "claimed": true,
      "source": "lib://…",
      "trackSeconds": [0, 312, 640],
      "audioUrl": "/content/download/…?overlay=…&skip_header=true",
      "downloadTriggerUrl": "/content/download/…",
      "tonieInfo": {
        "model": "10000123",
        "series": "…",
        "episode": "…",
        "picture": "https://…",
        "language": "de-de",
        "tracks": ["…"]
      },
      "sourceInfo": { "…": "nur wenn der Inhalt zu einem anderen Tonie gehört" }
    }
  ]
}
```

`downloadTriggerUrl` gibt es nur, wenn der Inhalt fehlt und aus der Cloud geladen werden kann. `sourceInfo` gibt es nur, wenn der zugewiesene Inhalt zu einem anderen Modell gehört als die Figur.

### Hinweis zu `/api/toniesJsonSearch`

Dieser Endpunkt eignet sich nicht zum Auflisten aller Tonies. Er durchsucht nur die Katalogdateien `tonies.json` / `tonies.custom.json` (alle veröffentlichten Tonies, nicht die eigenen), liefert ohne Suchbegriff eine leere Liste und höchstens 18 Treffer (siehe `handleApiToniesJsonSearch` in `src/handler_api.c` der TeddyCloud). Die Übersicht nutzt deshalb `/api/getTagIndex`.

## Projektstruktur

```
src/teddycloud_desktop/
├── main.py          # Hauptfenster mit Menüs; verbindet Client, Einstellungen, Tonie-Seite und Player
├── settings.py      # AppSettings (QSettings-Wrapper) und Einstellungsdialog
├── teddycloud.py    # Datenmodell, JSON-Parser und asynchroner API-Client (QNetworkAccessManager)
├── tonies_page.py   # Tonie-Übersicht: Toniebox-Auswahl, Filter, Auswahlmodus, Seiten, Aktionen
├── encoder_page.py  # Audio Encoder: Dateiliste, Zielordner, PCM-Dekodierung (QAudioDecoder) und Upload
├── encoder_custom.py        # Optionaler Bereich „Custom-Tonie anlegen“ im Audio Encoder
├── audio_tags.py            # Künstler, Album und Cover aus Audiodateien (mutagen, ohne Qt)
├── custom_models_page.py    # Custom-Modelle: Kacheln, Filter, Sortierung, Speicherablauf
├── custom_model_dialogs.py  # Bearbeitungsdialog, Bildauswahl, Vorschau, Audio-Index der Bibliothek
├── custom_models.py         # Datenlogik der Custom-Modelle (ohne Qt)
├── tap_page.py              # TeddyAudio Playlists: Liste, Editor, Zuweisen, Ordnerauswahl
├── tap.py                   # TAP-Format: lesen, schreiben, prüfen (ohne Qt)
├── tap_convert.py           # TAP in der GUI zur TAF umwandeln (Download, Dekodieren, PCM-Upload)
├── languages.py             # Gültige Sprachcodes (aus teddycloud_web generiert)
├── tonieboxes_page.py   # Tonieboxen-Übersicht und Aktionen (Bearbeiten, Zertifikate, Einstellungen, Löschen)
├── toniebox_card.py     # Toniebox-Kachel (lädt ihren Status selbst)
├── toniebox_dialogs.py  # Bearbeiten-, Einstellungs- und Zertifikats-Dialog
├── tonies_filter.py # Filterlogik (ohne Qt)
├── tonie_card.py    # Kachel-Widget
├── tonie_dialogs.py # Informations-, Bearbeitungs- und Bibliotheks-Dialog
├── audio_player.py  # Wiedergabeleiste (QtMultimedia)
├── images.py        # Asynchroner Bild-Cache
├── export.py        # CSV-/JSON-/HTML-Export
├── flow_layout.py   # Umbrechendes Layout für die Kacheln
└── icons.py         # Eigene SVG-Icons
```

## Entwicklung

```bash
uv sync                # Abhängigkeiten inkl. Entwicklungswerkzeuge installieren
uv run pytest          # Tests ausführen
uv run ruff check      # Linter
uv run ruff format     # Code formatieren
```

Ein neues Release:

1. `version` in `pyproject.toml` erhöhen und `uv lock` ausführen.
2. Die Einträge unter `## [Unreleased]` in [CHANGELOG.md](CHANGELOG.md) in einen neuen Abschnitt `## [X.Y.Z] - JJJJ-MM-TT` verschieben und die Links am Ende ergänzen. Das CHANGELOG ist englisch, weil es die Release-Beschreibung auf GitHub liefert.
3. Committen und pushen, dann `git tag vX.Y.Z && git push origin vX.Y.Z`.

Ein GitHub-Actions-Workflow baut daraus mit PyInstaller die Programme für Windows, macOS und Linux und legt das GitHub Release an. Die Beschreibung erzeugt `packaging/release_notes.py` aus dem CHANGELOG-Abschnitt plus Download-Hinweisen; Vorschau mit `uv run python packaging/release_notes.py vX.Y.Z`. Passt der Tag nicht zur Version in `pyproject.toml` oder fehlt der CHANGELOG-Abschnitt, bricht das Release früh ab.

## Lizenz

TeddyCloud Desktop steht unter der **GNU General Public License v3.0 oder später** (GPL-3.0-or-later), siehe [LICENSE](LICENSE). Grund dafür ist PyQt6: Es ist unter der GPL v3 lizenziert (alternativ kommerziell), deshalb muss eine damit verteilte Anwendung ebenfalls unter einer GPL-kompatiblen Lizenz stehen. Hinweise zu Bibliotheken und Code Dritter stehen in [NOTICE](NOTICE).

## Danksagung und Herkunft

- Oberfläche und API-Abläufe sind der TeddyCloud-Weboberfläche [teddycloud_web](https://github.com/toniebox-reverse-engineering/teddycloud_web) des Projekts toniebox-reverse-engineering nachgebaut. Vielen Dank an alle Beteiligten von [TeddyCloud](https://github.com/toniebox-reverse-engineering/teddycloud) und teddycloud_web.
- `languages.py` ist aus `languageOptions` in `LanguageFlagIcon.tsx` von teddycloud_web generiert, `BOX_SETTING_PREFIXES` in `toniebox_dialogs.py` ist aus `Settings.tsx` von teddycloud_web übernommen.
- Lizenz von teddycloud_web: Das Repository enthält (Stand November 2026) **keine Lizenzdatei** und keine Lizenzangabe in `package.json`; GitHub zeigt keine Lizenz an. Das Backend TeddyCloud steht unter der GPL-2.0.

## Haftungsausschluss

Dieses Projekt ist nicht mit der tonies GmbH (ehemals Boxine GmbH) verbunden und wird von ihr weder unterstützt noch geprüft. „Toniebox“ und „Tonie“ sind Marken der tonies GmbH. Die Namen werden nur verwendet, um zu beschreiben, wofür die Software gedacht ist.
