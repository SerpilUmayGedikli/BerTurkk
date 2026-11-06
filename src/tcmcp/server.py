"""MCP server entry point (stdio by default).

Tools: ``classify_news``, ``classify_sentiment``, ``list_reports``.
Resources and prompts are added in Aşama 3.

No ``from __future__ import annotations`` here: tool signatures use a per-server
``Field`` (max length from settings) that the SDK must evaluate eagerly.
"""

import logging
import math
import time
from typing import Annotated, Any

import anyio
import anyio.to_thread
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from tcmcp import __version__
from tcmcp.backends import Backend, FakeBackend, Prediction
from tcmcp.config import Settings, load_settings
from tcmcp.logging_config import configure_logging
from tcmcp.resources import list_report_names
from tcmcp.schemas import (
    NEWS_LABELS,
    NOTR_SHORTCUT_NOTE,
    SENTIMENT_LABELS,
    ClassificationResult,
    ReportList,
    SentimentResult,
)

SERVER_NAME = "turkish-nlp-tools"
INSTRUCTIONS = "Turkish text classification tools. Read-only."

READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)

logger = logging.getLogger(__name__)


def default_backends(settings: Settings) -> tuple[Backend, Backend]:
    """Create (news, sentiment) backends. Construction is cheap; models load lazily."""
    if settings.backend == "fake":
        return (
            FakeBackend(NEWS_LABELS, model_id="fake-news"),
            FakeBackend(SENTIMENT_LABELS, model_id="fake-sentiment"),
        )
    raise ValueError(f"unknown backend: {settings.backend}")  # pragma: no cover


def _check_text(text: str, max_chars: int) -> None:
    if not text.strip():
        raise ToolError("text must not be empty or whitespace only.")
    if len(text) > max_chars:
        raise ToolError(f"text is too long: limit is {max_chars} characters.")


def _validate(pred: Prediction, labels: tuple[str, ...]) -> None:
    """Reject a malformed backend prediction instead of passing it to the client."""
    if pred.label not in labels:
        raise ValueError("label not in label set")
    if set(pred.scores) != set(labels):
        raise ValueError("score keys do not match label set")
    if any(not math.isfinite(s) or s < 0.0 or s > 1.0 for s in pred.scores.values()):
        raise ValueError("score outside [0, 1]")


async def classify(backend: Backend, text: str, settings: Settings) -> ClassificationResult:
    """Validate input, run the backend in a worker thread with a timeout, validate output.

    Error messages never contain the input text, paths or exception details; those go to
    the stderr log only (without the text).
    """
    _check_text(text, settings.max_text_chars)
    start = time.perf_counter()
    try:
        with anyio.fail_after(settings.call_timeout_s):
            pred = await anyio.to_thread.run_sync(backend.predict, text, abandon_on_cancel=True)
    except TimeoutError:
        logger.warning("backend %s timed out", backend.model_id)
        raise ToolError("classification timed out; try a shorter text or retry later.") from None
    except Exception:
        logger.exception("backend %s failed", backend.model_id)
        raise ToolError("classification backend failed.") from None
    latency_ms = (time.perf_counter() - start) * 1000.0
    try:
        _validate(pred, backend.labels)
    except ValueError as exc:
        logger.error("backend %s returned an invalid prediction: %s", backend.model_id, exc)
        raise ToolError("classification backend returned an invalid result.") from None
    return ClassificationResult(
        label=pred.label,
        confidence=pred.scores[pred.label],
        scores=dict(pred.scores),
        model_id=pred.model_id,
        latency_ms=round(latency_ms, 3),
    )


def build_server(
    settings: Settings | None = None,
    *,
    news_backend: Backend | None = None,
    sentiment_backend: Backend | None = None,
) -> MCPServer[Any]:
    """Create the MCP server. Does not load any model (models load lazily)."""
    cfg = settings if settings is not None else load_settings()
    configure_logging(cfg.log_level)
    default_news, default_sentiment = default_backends(cfg)
    news = news_backend if news_backend is not None else default_news
    sentiment = sentiment_backend if sentiment_backend is not None else default_sentiment

    server: MCPServer[Any] = MCPServer(
        name=SERVER_NAME,
        version=__version__,
        instructions=INSTRUCTIONS,
        log_level=cfg.log_level,
    )

    # Length limits are advertised in the JSON schema but enforced in ``_check_text``:
    # pydantic's own constraint errors would echo part of the input back to the model.
    text_param = Field(
        description=f"Turkish text, 1 to {cfg.max_text_chars} characters.",
        json_schema_extra={"minLength": 1, "maxLength": cfg.max_text_chars},
    )

    @server.tool(title="Classify Turkish news category", annotations=READ_ONLY)
    async def classify_news(text: Annotated[str, text_param]) -> ClassificationResult:
        """Classify a Turkish news text into one of 7 categories."""
        return await classify(news, text, cfg)

    @server.tool(title="Classify Turkish sentiment", annotations=READ_ONLY)
    async def classify_sentiment(text: Annotated[str, text_param]) -> SentimentResult:
        """Classify Turkish text sentiment as Negative, Notr or Positive."""
        base = await classify(sentiment, text, cfg)
        return SentimentResult(**base.model_dump(), notes=[NOTR_SHORTCUT_NOTE])

    @server.tool(title="List experiment reports", annotations=READ_ONLY)
    def list_reports() -> ReportList:
        """List the names of the available experiment reports."""
        return ReportList(reports=list_report_names(cfg.reports_dir))

    logger.debug("server built (backend=%s)", cfg.backend)
    return server


def main() -> None:
    """Run the server over stdio. stdout is reserved for the protocol."""
    server = build_server()
    logger.info("starting %s %s over stdio", SERVER_NAME, __version__)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
