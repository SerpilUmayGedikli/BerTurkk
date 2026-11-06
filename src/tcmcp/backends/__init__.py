"""Pluggable classification backends."""

from tcmcp.backends.base import Backend, Prediction
from tcmcp.backends.fake import FakeBackend

__all__ = ["Backend", "FakeBackend", "Prediction"]
