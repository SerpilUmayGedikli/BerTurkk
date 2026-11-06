from __future__ import annotations

import math

import pytest

from tcmcp.backends import Backend, FakeBackend, Prediction

LABELS = ("dunya", "ekonomi", "spor")


def test_fake_backend_satisfies_protocol() -> None:
    assert isinstance(FakeBackend(LABELS), Backend)


def test_predict_returns_valid_prediction() -> None:
    pred = FakeBackend(LABELS, model_id="fake-news").predict("Galatasaray maçı kazandı.")
    assert isinstance(pred, Prediction)
    assert pred.model_id == "fake-news"
    assert set(pred.scores) == set(LABELS)
    assert math.isclose(sum(pred.scores.values()), 1.0, rel_tol=1e-9)
    assert all(0.0 <= s <= 1.0 for s in pred.scores.values())
    assert pred.label == max(pred.scores, key=lambda k: pred.scores[k])


def test_predict_is_deterministic() -> None:
    text = "Merkez Bankası faiz kararını açıkladı. İstanbul'da ışıklar."
    assert FakeBackend(LABELS).predict(text) == FakeBackend(LABELS).predict(text)


def test_lazy_loading_happens_once_on_first_predict() -> None:
    backend = FakeBackend(LABELS)
    assert not backend.is_loaded
    assert backend.load_count == 0
    backend.predict("a")
    backend.predict("b")
    assert backend.is_loaded
    assert backend.load_count == 1


@pytest.mark.parametrize("labels", [(), ("a", "a"), ("a", "")])
def test_invalid_labels_rejected(labels: tuple[str, ...]) -> None:
    with pytest.raises(ValueError):
        FakeBackend(labels)


def test_prediction_is_immutable() -> None:
    pred = FakeBackend(LABELS).predict("x")
    with pytest.raises(ValueError):
        pred.label = "other"
