"""Report discovery inside the allowed reports folder.

Only regular, non-hidden files with an allowed extension directly inside the folder are
listed. Symbolic links and sub-folders are ignored. Reading reports (with path-traversal
protection) is added in Aşama 3.
"""

from __future__ import annotations

from pathlib import Path

ALLOWED_SUFFIXES = frozenset({".md", ".json"})
EXCLUDED_NAMES = frozenset({"README.md"})


def list_report_names(reports_dir: Path) -> list[str]:
    """Return sorted report file names in ``reports_dir`` (empty if it does not exist)."""
    if not reports_dir.is_dir():
        return []
    names: list[str] = []
    for entry in reports_dir.iterdir():
        if entry.is_symlink() or not entry.is_file():
            continue
        if entry.name.startswith(".") or entry.name in EXCLUDED_NAMES:
            continue
        if entry.suffix.lower() not in ALLOWED_SUFFIXES:
            continue
        names.append(entry.name)
    return sorted(names)
