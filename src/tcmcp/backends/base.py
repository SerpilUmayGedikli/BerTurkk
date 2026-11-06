"""Backend interface shared by all classifiers."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class Prediction(BaseModel):
    """A single classification result."""

    model_config = ConfigDict(frozen=True)

    label: str = Field(min_length=1)
    scores: dict[str, float]
    model_id: str = Field(min_length=1)


@runtime_checkable
class Backend(Protocol):
    """A text classifier. Implementations load their model lazily on first use."""

    @property
    def model_id(self) -> str: ...

    @property
    def labels(self) -> tuple[str, ...]: ...

    def predict(self, text: str) -> Prediction: ...
