"""Named CSV exports (section 7). One clearly-named file per analysis
angle instead of one catch-all export, each keeping business names and
UUIDs side by side.
"""
from __future__ import annotations

import csv

from ..core.export_context import ExportContext

DELIMITER = ";"

EXPORTS = (
    ("synthese", "summary_rows"),
    ("series_api", "series_api_rows"),
    ("series_analytiques", "series_analytiques_rows"),
    ("series_groupes", "series_groupes_rows"),
    ("controle_couverture", "coverage_rows"),
    ("composition_groupes", "composition_rows"),
)


def _ordered_fieldnames(rows: list[dict]) -> list[str]:
    seen: dict[str, None] = {}
    for row in rows:
        for key in row:
            seen.setdefault(key, None)
    return list(seen)


def write_csv(path: str, rows: list[dict]) -> None:
    fieldnames = _ordered_fieldnames(rows)
    with open(path, "w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, delimiter=DELIMITER, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def export_named_csv(name: str, path: str, context: ExportContext) -> None:
    attribute = dict(EXPORTS).get(name)
    if attribute is None:
        raise ValueError(f"Export CSV inconnu : {name}")
    write_csv(path, getattr(context, attribute))


def export_all_csv(directory: str, base_name: str, context: ExportContext) -> list[str]:
    """Write every named export into ``directory``, returns the file paths."""
    from pathlib import Path

    written = []
    for name, attribute in EXPORTS:
        rows = getattr(context, attribute)
        if not rows:
            continue
        target = Path(directory) / f"{base_name}_{name}.csv"
        write_csv(str(target), rows)
        written.append(str(target))
    return written
