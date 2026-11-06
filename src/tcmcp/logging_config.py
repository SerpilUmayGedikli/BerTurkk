"""Logging setup. Logs go to stderr ONLY.

With the stdio transport, stdout carries the MCP protocol. Anything else written
there corrupts the stream, so this module never attaches a stdout handler.
"""

from __future__ import annotations

import logging
import sys

_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(level: str = "INFO") -> None:
    """Route all log records to stderr at ``level``, replacing existing root handlers."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(_FORMAT))
    root.addHandler(handler)
    root.setLevel(level)
