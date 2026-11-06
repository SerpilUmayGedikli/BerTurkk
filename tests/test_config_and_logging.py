from __future__ import annotations

import logging

import pytest
from pydantic import ValidationError

from tcmcp.config import Settings, load_settings
from tcmcp.logging_config import configure_logging


def test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("TCMCP_LOG_LEVEL", "TCMCP_BACKEND", "TCMCP_MAX_TEXT_CHARS"):
        monkeypatch.delenv(var, raising=False)
    s = load_settings()
    assert s.log_level == "INFO"
    assert s.backend == "fake"
    assert s.max_text_chars == 5000


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TCMCP_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("TCMCP_MAX_TEXT_CHARS", "1234")
    s = load_settings()
    assert s.log_level == "DEBUG"
    assert s.max_text_chars == 1234


@pytest.mark.parametrize(
    ("var", "value"),
    [("TCMCP_LOG_LEVEL", "LOUD"), ("TCMCP_BACKEND", "gpt"), ("TCMCP_MAX_TEXT_CHARS", "0")],
)
def test_invalid_env_rejected(monkeypatch: pytest.MonkeyPatch, var: str, value: str) -> None:
    monkeypatch.setenv(var, value)
    with pytest.raises(ValidationError):
        Settings()


def test_logs_go_to_stderr_not_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    logging.getLogger("tcmcp.test").info("hello-stderr")
    captured = capsys.readouterr()
    assert "hello-stderr" in captured.err
    assert captured.out == ""
