"""
Build script — Orion ERP Desktop
Lance depuis ce dossier : python build_exe.py
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT     = Path(__file__).resolve().parent
MAIN     = ROOT / "main.py"
ICON     = ROOT / "assets" / "icon.ico"
DIST_DIR = ROOT / "dist"
BUILD_DIR= ROOT / "build"
APP_NAME = "OrionERP-Desktop"


def clean():
    for d in (DIST_DIR, BUILD_DIR):
        if d.exists():
            try:
                shutil.rmtree(d, ignore_errors=True)
                print(f"Supprime : {d}")
            except Exception as e:
                print(f"Avertissement suppression {d}: {e}")


def build():
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name",          APP_NAME,
        "--windowed",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--add-data",      f"{ROOT / 'assets'}{os.pathsep}assets",
        "--hidden-import", "keyring.backends.Windows",
        "--collect-all",   "PySide6",
        str(MAIN),
    ]
    if ICON.exists():
        cmd += ["--icon", str(ICON)]

    print("Compilation PyInstaller…")
    print(" ".join(cmd))
    subprocess.check_call(cmd, cwd=str(ROOT))

    exe = DIST_DIR / APP_NAME / f"{APP_NAME}.exe"
    if not exe.exists():
        raise FileNotFoundError(f"EXE introuvable : {exe}")
    print(f"\nEXE généré :\n  {exe}")
    return exe


if __name__ == "__main__":
    clean()
    build()
