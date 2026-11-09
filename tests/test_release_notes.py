"""Release-Beschreibung aus CHANGELOG.md (packaging/release_notes.py)."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# Nicht als „packaging“ importieren: der Name kollidiert mit dem gleichnamigen PyPI-Paket
_spec = importlib.util.spec_from_file_location("release_notes", ROOT / "packaging" / "release_notes.py")
release_notes = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(release_notes)

CHANGELOG = """\
# Changelog

## [Unreleased]

## [1.1.0] - 2026-12-01

### Fixed

- Something

## [1.0.0] - 2026-11-10

Initial release.

[Unreleased]: https://example.org/compare/v1.1.0...HEAD
[1.1.0]: https://example.org/v1.1.0
"""

PYPROJECT = '[project]\nname = "x"\nversion = "1.1.0"\n'


def test_extract_middle_section() -> None:
    assert release_notes.extract_section(CHANGELOG, "1.1.0") == "### Fixed\n\n- Something"


def test_extract_last_section_stops_at_link_definitions() -> None:
    assert release_notes.extract_section(CHANGELOG, "1.0.0") == "Initial release."


def test_version_prefix_is_not_matched() -> None:
    with pytest.raises(ValueError, match="keinen Abschnitt"):
        release_notes.extract_section(CHANGELOG, "1.1")


def test_missing_section_raises() -> None:
    with pytest.raises(ValueError, match="keinen Abschnitt"):
        release_notes.extract_section(CHANGELOG, "2.0.0")


def test_empty_section_raises() -> None:
    with pytest.raises(ValueError, match="leer"):
        release_notes.extract_section(CHANGELOG, "Unreleased")


def test_tag_prefixes_are_removed() -> None:
    assert release_notes.tag_to_version("v1.2.3") == "1.2.3"
    assert release_notes.tag_to_version("refs/tags/v1.2.3") == "1.2.3"


def test_tag_must_match_pyproject_version() -> None:
    with pytest.raises(ValueError, match="pyproject.toml"):
        release_notes.release_notes("v1.0.0", CHANGELOG, PYPROJECT)


def test_notes_contain_section_and_downloads() -> None:
    notes = release_notes.release_notes("v1.1.0", CHANGELOG, PYPROJECT)
    assert notes.startswith("## What's new\n\n### Fixed\n\n- Something")
    for archive in (
        "teddycloud-desktop-windows-amd64.zip",
        "teddycloud-desktop-macos-arm64.zip",
        "teddycloud-desktop-linux-x86_64.tar.gz",
    ):
        assert archive in notes


def test_changelog_has_section_for_current_version() -> None:
    # Fällt schon in der CI auf, wenn nach einer Versionserhöhung der CHANGELOG-Eintrag fehlt
    version = release_notes.project_version((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    release_notes.extract_section((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), version)
