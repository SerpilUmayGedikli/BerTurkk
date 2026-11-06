"""Deterministic fake backend for tests and demos. No model, no network.

Its scores are derived from a hash of the input text. They carry no meaning
and must never be reported as model accuracy.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence

from tcmcp.backends.base import Prediction


class FakeBackend:
    """Hash-based classifier that mimics lazy loading."""

    def __init__(self, labels: Sequence[str], model_id: str = "fake") -> None:
        cleaned = tuple(labels)
        if not cleaned:
            raise ValueError("labels must not be empty")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("labels must be unique")
        if any(not label for label in cleaned):
            raise ValueError("labels must be non-empty strings")
        self._labels = cleaned
        self._model_id = model_id
        self._loaded = False
        self.load_count = 0

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def labels(self) -> tuple[str, ...]:
        return self._labels

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self._loaded = True
            self.load_count += 1

    def predict(self, text: str) -> Prediction:
        self._ensure_loaded()
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        logits = [digest[i % len(digest)] / 255.0 * 4.0 for i in range(len(self._labels))]
        peak = max(logits)
        exps = [math.exp(x - peak) for x in logits]
        total = sum(exps)
        scores = {label: e / total for label, e in zip(self._labels, exps, strict=True)}
        best = max(self._labels, key=lambda label: scores[label])
        return Prediction(label=best, scores=scores, model_id=self._model_id)
