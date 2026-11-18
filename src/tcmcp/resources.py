"""Safe, read-only access to reports inside the allowed reports folder.

A report name is a plain file name directly inside the folder. Rejected:
path separators, ``..``, absolute or drive paths, null bytes, hidden files,
symbolic links, sub-folders, extensions outside the allow-list, ``README.md``
and files larger than ``MAX_REPORT_BYTES``. The final path is also confirmed
to resolve inside the folder (``safe_join``), so a symlinked parent cannot escape.
"""

from __future__ import annotations

import re
from pathlib import Path

from mcp.shared.path_security import PathEscapeError, safe_join

ALLOWED_SUFFIXES: dict[str, str] = {".md": "text/markdown", ".json": "application/json"}
EXCLUDED_NAMES = frozenset({"README.md"})
MAX_REPORT_BYTES = 1_000_000

# First char alphanumeric (no hidden files), then letters, digits, "_", "-", ".".
_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.\-]{0,127}")


class ReportAccessError(Exception):
    """A report could not be served. The message is safe to show to clients."""


def mime_type_for(name: str) -> str:
    """MIME type for an allowed report name."""
    return ALLOWED_SUFFIXES[Path(name).suffix.lower()]


def is_valid_report_name(name: str) -> bool:
    """True if ``name`` is a plain, allowed report file name (no path components)."""
    if not _NAME_RE.fullmatch(name):
        return False
    if ".." in name or name in EXCLUDED_NAMES:
        return False
    return Path(name).suffix.lower() in ALLOWED_SUFFIXES


def _resolve(reports_dir: Path, name: str) -> Path:
    if not is_valid_report_name(name):
        raise ReportAccessError("invalid report name.")
    candidate = reports_dir / name
    if candidate.is_symlink():
        raise ReportAccessError("report not found.")
    try:
        path = safe_join(reports_dir, name)
    except PathEscapeError:
        raise ReportAccessError("report not found.") from None
    if not path.is_file():
        raise ReportAccessError("report not found.")
    return path


def list_report_names(reports_dir: Path) -> list[str]:
    """Return sorted names of servable reports (empty if the folder does not exist)."""
    if not reports_dir.is_dir():
        return []
    names: list[str] = []
    for entry in reports_dir.iterdir():
        if not is_valid_report_name(entry.name):
            continue
        try:
            _resolve(reports_dir, entry.name)
        except ReportAccessError:
            continue
        names.append(entry.name)
    return sorted(names)


def read_report(reports_dir: Path, name: str) -> str:
    """Read one report as UTF-8 text after all checks."""
    path = _resolve(reports_dir, name)
    if path.stat().st_size > MAX_REPORT_BYTES:
        raise ReportAccessError("report is too large to serve.")
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        raise ReportAccessError("report could not be read.") from None
