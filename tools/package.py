"""Construit l'archive ZIP installable du plugin dans dist/.

Usage : python tools/package.py
"""
from __future__ import annotations

import configparser
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_DIR = ROOT / "geoplateforme_usage_stats"
DIST = ROOT / "dist"

EXCLUDE_DIR_NAMES = {"__pycache__", ".pytest_cache"}
EXCLUDE_SUFFIXES = {".pyc"}


def plugin_version() -> str:
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(PLUGIN_DIR / "metadata.txt", encoding="utf-8")
    return parser["general"]["version"]


def build() -> Path:
    DIST.mkdir(exist_ok=True)
    out_path = DIST / f"geoplateforme_usage_stats_plugin_{plugin_version()}.zip"
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(PLUGIN_DIR.rglob("*")):
            if path.is_dir() or path.suffix in EXCLUDE_SUFFIXES:
                continue
            if any(part in EXCLUDE_DIR_NAMES for part in path.parts):
                continue
            archive.write(path, path.relative_to(ROOT).as_posix())
    return out_path


if __name__ == "__main__":
    target = build()
    print(f"{target} ({target.stat().st_size / 1024:.1f} Kio)")
