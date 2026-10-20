from __future__ import annotations

from typing import Any

from PIL import Image
import pytest
import requests

from product import local_vision


def test_missing_model_configuration_is_unavailable(settings: Any) -> None:
    settings.LOCAL_VISION_URL = ''
    with pytest.raises(local_vision.VisionUnavailable):
        local_vision.recognize(Image.new('RGB', (10, 10)))


def test_network_failure_is_safe(settings: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    settings.LOCAL_VISION_URL = 'http://internal-model'

    def fail(*args: Any, **kwargs: Any) -> None:
        raise requests.Timeout('internal diagnostic')

    monkeypatch.setattr(local_vision.requests, 'post', fail)
    with pytest.raises(local_vision.VisionUnavailable) as error:
        local_vision.model_request('analyze')
    assert 'internal diagnostic' not in str(error.value)


@pytest.mark.parametrize('payload', [
    {}, {'label': 'Book', 'category': 'books', 'embedding': [0.0]},
    {'label': 'Invented object', 'category': 'books', 'embedding': [0.0] * 512, 'score': 0.3, 'margin': 0.1},
    {'label': 'Book', 'category': 'books', 'embedding': [0.0] * 512, 'score': float('nan'), 'margin': 0.1},
])
def test_invalid_predictions_never_become_matches(payload: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(local_vision, 'model_request', lambda *args, **kwargs: payload)
    with pytest.raises(local_vision.VisionUnavailable):
        local_vision.recognize(Image.new('RGB', (10, 10)))


@pytest.mark.parametrize('rows', [
    [{'id': 999, 'score': 0.8}],
    [{'id': 1, 'score': float('nan')}],
    [{'id': 1, 'score': 0.8}, {'id': 1, 'score': 0.8}],
])
def test_rank_rejects_foreign_duplicate_or_invalid_results(rows: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(local_vision, 'model_request', lambda *args, **kwargs: {'results': rows})
    with pytest.raises(local_vision.VisionUnavailable):
        local_vision.rank([1.0] + [0.0] * 511, [{'id': 1, 'text': 'A book'}])


@pytest.mark.parametrize('candidate', [
    {'label': 'Invented object', 'category': 'outwear', 'score': 0.25},
    {'label': 'Shirt', 'category': 'outwear', 'score': float('nan')},
    {'label': 'Shirt', 'category': 'outwear', 'score': 0.15},
    {'label': 'Shirt', 'category': 'outwear', 'score': 0.9},
])
def test_invalid_suggestions_are_rejected(candidate: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(local_vision, 'model_request', lambda *args, **kwargs: {
        'label': 'Person', 'category': '', 'score': 0.26, 'margin': 0.01,
        'embedding': [1.0] + [0.0] * 511, 'alternatives': [candidate],
    })
    with pytest.raises(local_vision.VisionUnavailable):
        local_vision.recognize(Image.new('RGB', (10, 10)))
