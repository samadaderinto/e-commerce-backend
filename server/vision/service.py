"""Single-request local CLIP inference. No images or embeddings are persisted."""
from __future__ import annotations

from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import BytesIO
import json
import logging
import math
import os
from typing import Any

from PIL import Image
import torch
from transformers import CLIPModel, CLIPProcessor

from visual_labels import VISUAL_SUBJECTS

logger = logging.getLogger('commerce.vision')
logging.basicConfig(level=logging.INFO)
MODEL_ID = 'openai/clip-vit-base-patch32'
REVISION = 'b527df4b30e5cc18bde1cc712833a741d2d8c362'
torch.set_num_threads(max(1, min(4, int(os.environ.get('VISION_THREADS', '2')))))
processor = CLIPProcessor.from_pretrained(MODEL_ID, revision=REVISION)
model = CLIPModel.from_pretrained(MODEL_ID, revision=REVISION, use_safetensors=True).eval()
with torch.inference_mode():
    subject_vectors = model.get_text_features(**processor(
        text=[row[2] for row in VISUAL_SUBJECTS], return_tensors='pt', padding=True, truncation=True,
    ))
    subject_vectors = subject_vectors / subject_vectors.norm(dim=-1, keepdim=True)


text_cache: OrderedDict[str, torch.Tensor] = OrderedDict()


def text_vectors(texts: list[str]) -> torch.Tensor:
    missing = list(dict.fromkeys(text for text in texts if text not in text_cache))
    for start in range(0, len(missing), 32):
        batch = missing[start:start + 32]
        inputs = processor(text=batch, return_tensors='pt', padding=True, truncation=True)
        with torch.inference_mode():
            features = model.get_text_features(**inputs)
            features = features / features.norm(dim=-1, keepdim=True)
        for text, vector in zip(batch, features, strict=True):
            text_cache[text] = vector
    vectors = torch.stack([text_cache[text] for text in texts])
    for text in texts:
        text_cache.move_to_end(text)
    while len(text_cache) > 2048:
        text_cache.popitem(last=False)
    return vectors


class Handler(BaseHTTPRequestHandler):
    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(10)

    def reply(self, status: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload, allow_nan=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        self.reply(200 if self.path == '/health' else 404, {'ready': self.path == '/health'})

    def do_POST(self) -> None:
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 5 * 1024 * 1024:
                self.reply(400, {'detail': 'Invalid request size.'})
                return
            raw = self.rfile.read(length)
            if self.path == '/analyze':
                with Image.open(BytesIO(raw)) as source:
                    if source.width * source.height > 16_000_000:
                        raise ValueError('Image too large')
                    image = source.convert('RGB')
                inputs = processor(images=image, return_tensors='pt')
                with torch.inference_mode():
                    vector = model.get_image_features(**inputs)[0]
                    vector = vector / vector.norm()
                scores = [(float(vector @ subject_vectors[index]), label, category)
                          for index, (label, category, _) in enumerate(VISUAL_SUBJECTS)]
                scores.sort(reverse=True)
                score, label, category = scores[0]
                other = next(row[0] for row in scores if row[2] != category)
                alternatives = [
                    {'label': candidate_label, 'category': candidate_category,
                     'score': candidate_score}
                    for candidate_score, candidate_label, candidate_category in scores
                    if candidate_category and candidate_score >= 0.20
                    and score - candidate_score <= 0.04
                ][:3]
                self.reply(200, {'label': label, 'category': category, 'score': score,
                                 'margin': score - other, 'embedding': vector.tolist(),
                                 'alternatives': alternatives})
            elif self.path == '/rank':
                payload = json.loads(raw)
                values = payload['embedding']
                candidates = payload['candidates']
                if (len(values) != 512 or not all(isinstance(v, (float, int)) and math.isfinite(v) for v in values)
                        or not isinstance(candidates, list) or not 1 <= len(candidates) <= 512):
                    raise ValueError('Invalid ranking request')
                vector = torch.tensor(values)
                if not 0.99 < float(vector.norm()) < 1.01:
                    raise ValueError('Invalid embedding')
                for row in candidates:
                    if not isinstance(row['text'], str) or len(row['text']) > 512:
                        raise ValueError('Invalid description')
                features = text_vectors([row['text'] for row in candidates])
                results = [{'id': int(row['id']), 'score': float(vector @ features[index])}
                           for index, row in enumerate(candidates)]
                self.reply(200, {'results': sorted(results, key=lambda row: row['score'], reverse=True)})
            else:
                self.reply(404, {'detail': 'Not found.'})
        except (ValueError, KeyError, TypeError, OSError):
            self.reply(400, {'detail': 'Unable to read image or ranking request.'})
        except Exception:
            logger.exception('Local vision inference failed')
            self.reply(503, {'detail': 'Recognition temporarily unavailable.'})


if __name__ == '__main__':
    # One inference at a time bounds CPU and model memory; API timeouts bound callers.
    HTTPServer(('0.0.0.0', 8010), Handler).serve_forever()
