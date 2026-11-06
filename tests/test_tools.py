from __future__ import annotations

import math
import os
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from mcp import Client
from mcp.types import CallToolResult, TextContent

from tcmcp.backends import FakeBackend, Prediction
from tcmcp.config import Settings
from tcmcp.schemas import NEWS_LABELS, NOTR_SHORTCUT_NOTE, SENTIMENT_LABELS
from tcmcp.server import build_server

SAMPLE = "Merkez Bankası faiz kararını açıkladı; borsa günü yükselişle kapattı."


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _settings(tmp_path: Path, **overrides: Any) -> Settings:
    return Settings(reports_dir=tmp_path, log_level="WARNING", **overrides)


def _text(result: CallToolResult) -> str:
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


async def _call(client: Client, tool: str, args: dict[str, Any]) -> CallToolResult:
    return await client.call_tool(tool, args)


@pytest.fixture
async def client(tmp_path: Path) -> AsyncIterator[Client]:
    async with Client(build_server(_settings(tmp_path)), raise_exceptions=True) as c:
        yield c


# ---------------------------------------------------------------- happy paths


@pytest.mark.anyio
async def test_classify_news_structured_output(client: Client) -> None:
    result = await _call(client, "classify_news", {"text": SAMPLE})
    assert not result.is_error
    data = result.structured_content
    assert isinstance(data, dict)
    assert set(data) == {"label", "confidence", "scores", "model_id", "latency_ms"}
    assert data["label"] in NEWS_LABELS
    assert set(data["scores"]) == set(NEWS_LABELS)
    assert math.isclose(sum(data["scores"].values()), 1.0, rel_tol=1e-9)
    assert data["confidence"] == data["scores"][data["label"]]
    assert data["model_id"] == "fake-news"
    assert data["latency_ms"] >= 0.0


@pytest.mark.anyio
async def test_classify_sentiment_includes_notr_note(client: Client) -> None:
    result = await _call(client, "classify_sentiment", {"text": "Bu ürün harika, çok memnunum!"})
    assert not result.is_error
    data = result.structured_content
    assert isinstance(data, dict)
    assert data["label"] in SENTIMENT_LABELS
    assert set(data["scores"]) == set(SENTIMENT_LABELS)
    assert data["notes"] == [NOTR_SHORTCUT_NOTE]


@pytest.mark.anyio
async def test_output_does_not_echo_input_text(client: Client) -> None:
    marker = "ZXQ-unique-marker-ZXQ"
    result = await _call(client, "classify_news", {"text": f"{marker} haber metni"})
    assert marker not in _text(result)
    assert marker not in str(result.structured_content)


# ------------------------------------------------------------ invalid input


@pytest.mark.anyio
@pytest.mark.parametrize("tool", ["classify_news", "classify_sentiment"])
@pytest.mark.parametrize("text", ["", "   ", "\n\t "])
async def test_empty_or_whitespace_rejected(client: Client, tool: str, text: str) -> None:
    result = await _call(client, tool, {"text": text})
    assert result.is_error
    assert "must not be empty" in _text(result)


@pytest.mark.anyio
async def test_too_long_text_rejected_without_echo(tmp_path: Path) -> None:
    srv = build_server(_settings(tmp_path, max_text_chars=50))
    async with Client(srv, raise_exceptions=True) as c:
        long_text = "SECRETMARKER " * 10
        result = await _call(c, "classify_news", {"text": long_text})
    assert result.is_error
    msg = _text(result)
    assert "too long" in msg
    assert "50" in msg
    assert "SECRETMARKER" not in msg


@pytest.mark.anyio
async def test_text_at_exact_limit_accepted(tmp_path: Path) -> None:
    srv = build_server(_settings(tmp_path, max_text_chars=10))
    async with Client(srv, raise_exceptions=True) as c:
        result = await _call(c, "classify_news", {"text": "ç" * 10})
    assert not result.is_error


@pytest.mark.anyio
async def test_missing_argument_rejected(client: Client) -> None:
    result = await _call(client, "classify_news", {})
    assert result.is_error


@pytest.mark.anyio
async def test_non_string_argument_rejected(client: Client) -> None:
    result = await _call(client, "classify_news", {"text": 123})
    assert result.is_error


# --------------------------------------------------------- backend problems


class _UnknownLabelBackend(FakeBackend):
    def predict(self, text: str) -> Prediction:
        return Prediction(label="hava_durumu", scores=dict.fromkeys(self.labels, 0.1), model_id="x")


class _WrongScoresBackend(FakeBackend):
    def predict(self, text: str) -> Prediction:
        return Prediction(label=self.labels[0], scores={self.labels[0]: 1.5}, model_id="x")


class _CrashingBackend(FakeBackend):
    def predict(self, text: str) -> Prediction:
        raise RuntimeError(r"secret path C:\models\private token=abc123")


class _SlowBackend(FakeBackend):
    def predict(self, text: str) -> Prediction:
        time.sleep(1.0)
        return super().predict(text)


@pytest.mark.anyio
@pytest.mark.parametrize("backend_cls", [_UnknownLabelBackend, _WrongScoresBackend])
async def test_invalid_backend_prediction_rejected(
    tmp_path: Path, backend_cls: type[FakeBackend]
) -> None:
    srv = build_server(_settings(tmp_path), news_backend=backend_cls(NEWS_LABELS))
    async with Client(srv, raise_exceptions=True) as c:
        result = await _call(c, "classify_news", {"text": SAMPLE})
    assert result.is_error
    msg = _text(result)
    assert "invalid result" in msg
    assert "hava_durumu" not in msg


@pytest.mark.anyio
async def test_backend_exception_is_sanitised(tmp_path: Path) -> None:
    srv = build_server(_settings(tmp_path), sentiment_backend=_CrashingBackend(SENTIMENT_LABELS))
    async with Client(srv, raise_exceptions=True) as c:
        result = await _call(c, "classify_sentiment", {"text": SAMPLE})
    assert result.is_error
    msg = _text(result)
    assert "backend failed" in msg
    for leak in ("secret", "models", "token", "abc123", "Traceback", "RuntimeError"):
        assert leak not in msg


@pytest.mark.anyio
async def test_backend_timeout(tmp_path: Path) -> None:
    srv = build_server(
        _settings(tmp_path, call_timeout_s=0.1), news_backend=_SlowBackend(NEWS_LABELS)
    )
    async with Client(srv, raise_exceptions=True) as c:
        started = time.perf_counter()
        result = await _call(c, "classify_news", {"text": SAMPLE})
        elapsed = time.perf_counter() - started
    assert result.is_error
    assert "timed out" in _text(result)
    assert elapsed < 0.9


# ------------------------------------------------------------- lazy loading


@pytest.mark.anyio
async def test_backends_load_lazily_on_first_call(tmp_path: Path) -> None:
    news = FakeBackend(NEWS_LABELS, model_id="fake-news")
    sentiment = FakeBackend(SENTIMENT_LABELS, model_id="fake-sentiment")
    srv = build_server(_settings(tmp_path), news_backend=news, sentiment_backend=sentiment)
    async with Client(srv, raise_exceptions=True) as c:
        await c.list_tools()
        assert not news.is_loaded
        assert not sentiment.is_loaded
        await _call(c, "classify_news", {"text": SAMPLE})
        await _call(c, "classify_news", {"text": "ikinci haber"})
    assert news.load_count == 1
    assert not sentiment.is_loaded


# ------------------------------------------------------------ list_reports


@pytest.mark.anyio
async def test_list_reports_filters_and_sorts(tmp_path: Path) -> None:
    (tmp_path / "b_report.md").write_text("# b", encoding="utf-8")
    (tmp_path / "a_metrics.json").write_text("{}", encoding="utf-8")
    (tmp_path / "README.md").write_text("readme", encoding="utf-8")
    (tmp_path / ".hidden.md").write_text("x", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("x", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "inner.md").write_text("x", encoding="utf-8")
    async with Client(build_server(_settings(tmp_path)), raise_exceptions=True) as c:
        result = await _call(c, "list_reports", {})
    assert not result.is_error
    assert result.structured_content == {"reports": ["a_metrics.json", "b_report.md"]}


@pytest.mark.anyio
async def test_list_reports_missing_dir_is_empty(tmp_path: Path) -> None:
    srv = build_server(Settings(reports_dir=tmp_path / "nope", log_level="WARNING"))
    async with Client(srv, raise_exceptions=True) as c:
        result = await _call(c, "list_reports", {})
    assert result.structured_content == {"reports": []}


@pytest.mark.anyio
async def test_list_reports_skips_symlinks(tmp_path: Path) -> None:
    target = tmp_path / "real.md"
    target.write_text("# real", encoding="utf-8")
    try:
        os.symlink(target, tmp_path / "link.md")
    except OSError:
        pytest.skip("symlinks not permitted on this system")
    async with Client(build_server(_settings(tmp_path)), raise_exceptions=True) as c:
        result = await _call(c, "list_reports", {})
    assert result.structured_content == {"reports": ["real.md"]}


# ---------------------------------------------------------------- schemas


@pytest.mark.anyio
async def test_tool_schemas(tmp_path: Path) -> None:
    srv = build_server(_settings(tmp_path, max_text_chars=1234))
    async with Client(srv, raise_exceptions=True) as c:
        tools = {t.name: t for t in (await c.list_tools()).tools}
    for name in ("classify_news", "classify_sentiment"):
        text_schema = tools[name].input_schema["properties"]["text"]
        assert text_schema["type"] == "string"
        assert text_schema["minLength"] == 1
        assert text_schema["maxLength"] == 1234
        assert tools[name].input_schema["required"] == ["text"]
    news_out = tools["classify_news"].output_schema
    sent_out = tools["classify_sentiment"].output_schema
    assert news_out is not None
    assert sent_out is not None
    assert set(news_out["properties"]) == {
        "label",
        "confidence",
        "scores",
        "model_id",
        "latency_ms",
    }
    assert set(sent_out["properties"]) == set(news_out["properties"]) | {"notes"}
    assert tools["list_reports"].input_schema.get("properties", {}) == {}
    for tool in tools.values():
        assert tool.annotations is not None
        assert tool.annotations.read_only_hint is True
        assert tool.annotations.open_world_hint is False
