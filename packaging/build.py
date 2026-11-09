"""Baut mit PyInstaller eine eigenständige Anwendung in dist/ und packt sie als Archiv.

Aufruf: uv run --with pyinstaller python packaging/build.py
"""

import platform
import shutil
import subprocess
import sys
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parent.parent
APP_NAME = "TeddyCloud Desktop"


def main() -> None:
    PyInstaller.__main__.run(
        [
            str(ROOT / "packaging" / "launcher.py"),
            "--name",
            APP_NAME,
            "--windowed",
            "--noconfirm",
            "--clean",
            "--distpath",
            str(ROOT / "dist"),
            "--workpath",
            str(ROOT / "build"),
            "--specpath",
            str(ROOT / "build"),
            # Für die Versionsanzeige im Über-Dialog und die Schlüsselbund-Backends (Entry Points)
            "--copy-metadata",
            "teddycloud-desktop",
            "--copy-metadata",
            "keyring",
            "--add-data",
            f"{ROOT / 'LICENSE'}{':' if sys.platform != 'win32' else ';'}.",
        ]
    )

    system = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")
    archive = ROOT / "dist" / f"teddycloud-desktop-{system}-{platform.machine().lower()}"
    if sys.platform == "darwin":
        # ditto erhält die Symlinks in den Qt-Frameworks des .app-Bundles, shutil.make_archive nicht
        bundle = ROOT / "dist" / f"{APP_NAME}.app"
        path = f"{archive}.zip"
        subprocess.run(["ditto", "-c", "-k", "--keepParent", str(bundle), path], check=True)
    else:
        fmt = "gztar" if system == "linux" else "zip"
        path = shutil.make_archive(str(archive), fmt, root_dir=ROOT / "dist", base_dir=APP_NAME)
    print(f"Archiv: {path}")


if __name__ == "__main__":
    main()
