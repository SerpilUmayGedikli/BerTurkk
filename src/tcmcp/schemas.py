"""Pydantic output models and label sets for the MCP tools."""

from __future__ import annotations

from pydantic import BaseModel, Field

# Label sets of the BERTurk project (reports/baseline_*.json in that repository).
NEWS_LABELS: tuple[str, ...] = (
    "dunya",
    "ekonomi",
    "kultur",
    "saglik",
    "siyaset",
    "spor",
    "teknoloji",
)
SENTIMENT_LABELS: tuple[str, ...] = ("Negative", "Notr", "Positive")

NOTR_SHORTCUT_NOTE = (
    "Notr is unreliable: almost all Notr training examples come from Wikipedia, so the "
    "model may detect encyclopedic style rather than neutral opinion. Detection of truly "
    "neutral opinions was not measured."
)


class ClassificationResult(BaseModel):
    """Result of one classification call."""

    label: str = Field(description="Predicted label.")
    confidence: float = Field(ge=0.0, le=1.0, description="Score of the predicted label.")
    scores: dict[str, float] = Field(description="Score per label.")
    model_id: str = Field(description="Identifier of the backend model.")
    latency_ms: float = Field(ge=0.0, description="Server-side prediction time in ms.")


class SentimentResult(ClassificationResult):
    """Sentiment result with caveats about the model."""

    notes: list[str] = Field(description="Known limitations of this model.")


class ReportList(BaseModel):
    """Names of the available reports."""

    reports: list[str] = Field(description="Report file names, sorted.")
