"""Environment-based settings (prefix ``TCMCP_``).

Secrets are never hard-coded; anything sensitive must come from the environment.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
BackendName = Literal["fake"]


class Settings(BaseSettings):
    """Server settings read from ``TCMCP_*`` environment variables."""

    model_config = SettingsConfigDict(env_prefix="TCMCP_", extra="ignore")

    log_level: LogLevel = "INFO"
    backend: BackendName = "fake"
    max_text_chars: int = Field(default=5000, ge=1, le=100_000)


def load_settings() -> Settings:
    """Read settings from the current environment."""
    return Settings()
