"""Bounded internal model requests; failures never become invented predictions."""
from __future__ import annotations

from io import BytesIO
import logging
import math
from typing import Any

from django.conf import settings
from PIL import Image
import requests
from rest_framework.exceptions import APIException

from .visual_labels import VISUAL_SUBJECTS

logger = logging.getLogger(__name__)


class VisionUnavailable(APIException):
    status_code = 503
    default_detail = 'Picture recognition is temporarily unavailable. Please use text search.'
    default_code = 'vision_unavailable'


def model_request(path: str, **kwargs: Any) -> dict[str, Any]:
    url = str(getattr(settings, 'LOCAL_VISION_URL', '')).rstrip('/')
    if not url:
        raise VisionUnavailable()
    try:
        response = requests.post(f'{url}/{path}', timeout=(2, 15), **kwargs)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError('Invalid model response')
        return payload
    except (requests.RequestException, ValueError):
        logger.warning('Local picture recognition unavailable', exc_info=True)
        raise VisionUnavailable() from None


def recognize(image: Image.Image) -> dict[str, Any]:
    buffer = BytesIO()
    image.save(buffer, format='JPEG', quality=90)
    result = model_request('analyze', data=buffer.getvalue(), headers={'Content-Type': 'image/jpeg'})
    try:
        embedding = result['embedding']
        if (len(embedding) != 512 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in embedding)
                or (result['label'], result['category']) not in {(label, category) for label, category, _ in VISUAL_SUBJECTS}
                or not math.isfinite(float(result['score'])) or not math.isfinite(float(result['margin']))):
            raise ValueError('Invalid recognition response')
        alternatives = result.get('alternatives', [])
        allowed = {(label, category) for label, category, _ in VISUAL_SUBJECTS if category}
        seen: set[str] = set()
        if not isinstance(alternatives, list) or len(alternatives) > 3:
            raise ValueError('Invalid alternatives')
        for candidate in alternatives:
            if (
                (candidate['label'], candidate['category']) not in allowed
                or candidate['label'] in seen
                or not math.isfinite(float(candidate['score']))
                or not 0.20 <= float(candidate['score']) <= 1
                or float(candidate['score']) > float(result['score']) + 0.000001
                or float(result['score']) - float(candidate['score']) > 0.04
            ):
                raise ValueError('Invalid alternatives')
            seen.add(candidate['label'])
    except (KeyError, ValueError, TypeError):
        logger.warning('Local vision returned invalid recognition data')
        raise VisionUnavailable() from None
    return result


def rank(embedding: list[float], candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not candidates:
        return []
    payload = model_request('rank', json={'embedding': embedding, 'candidates': candidates})
    try:
        rows = payload['results']
        allowed = {row['id'] for row in candidates}
        seen: set[int] = set()
        if not isinstance(rows, list) or len(rows) > len(allowed):
            raise ValueError('Invalid ranking')
        for row in rows:
            if row['id'] not in allowed or row['id'] in seen or not math.isfinite(float(row['score'])):
                raise ValueError('Invalid ranking')
            seen.add(row['id'])
        return sorted(rows, key=lambda row: float(row['score']), reverse=True)
    except (KeyError, TypeError, ValueError):
        logger.warning('Local vision returned invalid ranking data')
        raise VisionUnavailable() from None
