"""Erzeugt die Beschreibung eines GitHub-Releases aus dem passenden Abschnitt der CHANGELOG.md.

Aufruf: python packaging/release_notes.py v1.2.3 [-o notes.md]

Bricht ab, wenn die Version des Tags nicht zu pyproject.toml passt oder der CHANGELOG-Abschnitt fehlt bzw. leer ist,
damit kein Release mit falscher Version oder ohne Beschreibung entsteht. Nur Standardbibliothek (Python >= 3.11).
"""

import argparse
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Fester Teil jeder Release-Beschreibung; die Archivnamen erzeugt packaging/build.py
DOWNLOAD_NOTES = """\
## Download

| System | File |
|--------|------|
| Windows (x64) | `teddycloud-desktop-windows-amd64.zip` |
| macOS (Apple Silicon) | `teddycloud-desktop-macos-arm64.zip` |
| Linux (x86_64) | `teddycloud-desktop-linux-x86_64.tar.gz` |

Unpack the archive and start **TeddyCloud Desktop**. No Python installation is needed.

**First start:** the builds are not signed, so the system warns once.
- **macOS:** right-click the app and choose *Open*, or run `xattr -dr com.apple.quarantine "TeddyCloud Desktop.app"`.
- **Windows:** in the SmartScreen dialog click *More info* → *Run anyway*.
- **Linux:** built on Ubuntu 22.04, needs glibc 2.35 or newer.
"""


def tag_to_version(tag: str) -> str:
    return tag.removeprefix("refs/tags/").removeprefix("v")


def project_version(pyproject: str) -> str:
    return tomllib.loads(pyproject)["project"]["version"]


def extract_section(changelog: str, version: str) -> str:
    """Text unter „## [<version>]“ bis zur nächsten Überschrift zweiter Ebene oder den Link-Definitionen am Ende."""
    lines = changelog.splitlines()
    heading = re.compile(rf"^## \[{re.escape(version)}\](\s|$)")
    start = next((i for i, line in enumerate(lines) if heading.match(line)), None)
    if start is None:
        raise ValueError(f"CHANGELOG.md hat keinen Abschnitt „## [{version}]“.")
    section: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("## ") or re.match(r"^\[[^\]]+\]:\s", line):
            break
        section.append(line)
    text = "\n".join(section).strip()
    if not text:
        raise ValueError(f"Der Abschnitt „## [{version}]“ in CHANGELOG.md ist leer.")
    return text


def build_notes(section: str) -> str:
    # Überschriften des CHANGELOG-Abschnitts („### Added“) bleiben unter „What's new“ erhalten
    return f"## What's new\n\n{section}\n\n{DOWNLOAD_NOTES}"


def release_notes(tag: str, changelog: str, pyproject: str) -> str:
    version = tag_to_version(tag)
    expected = project_version(pyproject)
    if version != expected:
        raise ValueError(f"Tag-Version {version} passt nicht zu version = {expected} in pyproject.toml.")
    return build_notes(extract_section(changelog, version))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("tag", help="Git-Tag, z. B. v1.2.3")
    parser.add_argument("-o", "--output", type=Path, help="Zieldatei (Standard: Ausgabe auf stdout)")
    args = parser.parse_args()

    try:
        notes = release_notes(
            args.tag,
            (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"),
            (ROOT / "pyproject.toml").read_text(encoding="utf-8"),
        )
    except ValueError as error:
        sys.exit(f"Fehler: {error}")

    if args.output:
        args.output.write_text(notes, encoding="utf-8")
    else:
        print(notes)


if __name__ == "__main__":
    main()
