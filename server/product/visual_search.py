from __future__ import annotations

import io
import math
import re
from typing import Any

from PIL import Image, ImageOps
from django.db.models import Q, QuerySet
from rest_framework.exceptions import ValidationError

from product.models import Product
from store.models import Store


# Reference RGB centroids for standard named color palettes
NAMED_COLORS: list[tuple[str, tuple[int, int, int]]] = [
    ("Black", (20, 20, 20)),
    ("Charcoal", (50, 50, 50)),
    ("Gray", (128, 128, 128)),
    ("Silver", (192, 192, 192)),
    ("White", (245, 245, 245)),
    ("Off-White", (238, 235, 225)),
    ("Beige", (225, 215, 195)),
    ("Tan", (210, 180, 140)),
    ("Brown", (110, 65, 35)),
    ("Navy Blue", (15, 30, 80)),
    ("Deep Blue", (25, 55, 130)),
    ("Blue", (40, 100, 210)),
    ("Sky Blue", (115, 185, 240)),
    ("Cyan", (0, 190, 210)),
    ("Teal", (20, 128, 128)),
    ("Forest Green", (25, 75, 40)),
    ("Olive", (100, 110, 40)),
    ("Green", (45, 150, 75)),
    ("Emerald Green", (20, 160, 100)),
    ("Lime", (140, 205, 50)),
    ("Yellow", (245, 215, 40)),
    ("Gold", (212, 175, 55)),
    ("Amber", (245, 165, 30)),
    ("Orange", (240, 105, 30)),
    ("Coral", (240, 100, 90)),
    ("Red", (220, 40, 45)),
    ("Crimson", (160, 25, 40)),
    ("Burgundy", (105, 20, 45)),
    ("Pink", (245, 140, 175)),
    ("Rose", (225, 80, 130)),
    ("Purple", (130, 50, 175)),
    ("Violet", (110, 40, 160)),
    ("Lavender", (185, 155, 220)),
]

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "outwear": [
        "jacket", "coat", "hoodie", "sweatshirt", "sweater", "shirt", "t-shirt", "tee",
        "top", "pants", "jeans", "trousers", "shorts", "joggers", "cargo", "shoes",
        "sneakers", "boots", "sandals", "footwear", "outfit", "apparel", "clothing",
        "streetwear", "athletic", "suit", "blazer", "dress", "skirt", "vest", "overcoat",
    ],
    "footwear": [
        "shoes", "sneakers", "boots", "sandals", "runners", "trainer", "kicks", "footwear",
        "loafers", "oxfords", "chelsea", "heels", "slides", "cleats",
    ],
    "jewelry": [
        "watch", "necklace", "bracelet", "ring", "earrings", "glasses", "sunglasses",
        "eyewear", "bag", "backpack", "crossbody", "tote", "duffle", "wallet", "belt",
        "cap", "hat", "beanie", "scarf", "gloves", "accessory", "accessories",
    ],
    "home": [
        "desk", "chair", "table", "lamp", "lighting", "sofa", "couch", "rug", "shelf",
        "cabinet", "mirror", "planter", "pot", "cushion", "pillow", "decor", "furniture",
        "clock", "vase", "mat", "workspace", "stool", "drawer",
    ],
    "computing": [
        "laptop", "computer", "keyboard", "mouse", "monitor", "display", "screen", "pc",
        "macbook", "dock", "stand", "trackpad", "peripheral", "case", "sleeve",
    ],
    "electronics": [
        "headphones", "earbuds", "speaker", "audio", "camera", "microphone", "charger",
        "cable", "gadget", "smartwatch", "wireless", "powerbank", "electronics",
    ],
    "sports": [
        "gym", "fitness", "yoga", "mat", "bottle", "dumbbell", "weights", "strap",
        "resistance", "running", "ball", "gloves", "trainer", "outdoor", "athletic",
    ],
}

PRESET_LOOKS: dict[str, dict[str, Any]] = {
    "urban_streetwear": {
        "id": "urban_streetwear",
        "title": "Urban Streetwear Outfit",
        "subtitle": "Chunky sneakers, cargo pants, bomber jacket & crossbody bag",
        "image_url": "/demo-looks/streetwear.jpg",
        "style": "Contemporary Minimal Streetwear",
        "items": [
            {
                "id": "item_jacket",
                "label": "Black Flight Bomber Jacket",
                "category": "outwear",
                "box": [0.12, 0.22, 0.52, 0.78],
                "dominant_colors": ["#141414", "#2B2B2B"],
                "keywords": ["bomber", "jacket", "flight", "outerwear", "black"],
            },
            {
                "id": "item_pants",
                "label": "Relaxed Tech Cargo Trousers",
                "category": "outwear",
                "box": [0.48, 0.28, 0.78, 0.72],
                "dominant_colors": ["#3C3F41", "#1E2022"],
                "keywords": ["cargo", "pants", "trousers", "joggers", "charcoal"],
            },
            {
                "id": "item_sneakers",
                "label": "Chunky Low-Top Sneakers",
                "category": "footwear",
                "box": [0.75, 0.20, 0.96, 0.80],
                "dominant_colors": ["#F5F5F5", "#E0E0E0", "#141414"],
                "keywords": ["sneakers", "shoes", "white", "chunky", "low-top", "footwear"],
            },
            {
                "id": "item_bag",
                "label": "Compact Canvas Crossbody Pack",
                "category": "jewelry",
                "box": [0.30, 0.15, 0.48, 0.35],
                "dominant_colors": ["#1E2022", "#4A4D50"],
                "keywords": ["bag", "crossbody", "pack", "canvas", "strap"],
            },
        ],
    },
    "minimal_workspace": {
        "id": "minimal_workspace",
        "title": "Scandinavian Minimalist Workspace",
        "subtitle": "Solid oak desk, ergonomic mesh chair & studio monitors",
        "image_url": "/demo-looks/workspace.jpg",
        "style": "Nordic Minimalist Interior",
        "items": [
            {
                "id": "item_desk",
                "label": "Solid White Oak Standing Desk",
                "category": "home",
                "box": [0.40, 0.10, 0.72, 0.90],
                "dominant_colors": ["#D2B48C", "#E1D7C3"],
                "keywords": ["desk", "oak", "wood", "table", "workspace"],
            },
            {
                "id": "item_chair",
                "label": "Ergonomic High-Back Task Chair",
                "category": "home",
                "box": [0.35, 0.45, 0.88, 0.85],
                "dominant_colors": ["#202020", "#505050"],
                "keywords": ["chair", "ergonomic", "office", "task", "mesh"],
            },
            {
                "id": "item_audio",
                "label": "Wireless Studio Monitor Headphones",
                "category": "electronics",
                "box": [0.42, 0.70, 0.60, 0.86],
                "dominant_colors": ["#141414", "#808080"],
                "keywords": ["headphones", "audio", "studio", "wireless", "monitors"],
            },
            {
                "id": "item_keyboard",
                "label": "Low-Profile Wireless Mechanical Keyboard",
                "category": "computing",
                "box": [0.55, 0.32, 0.68, 0.68],
                "dominant_colors": ["#F5F5F5", "#808080"],
                "keywords": ["keyboard", "mechanical", "wireless", "computing"],
            },
        ],
    },
    "gym_performance": {
        "id": "gym_performance",
        "title": "Athletic Training & Performance Fit",
        "subtitle": "Breathable technical tee, compression shorts & road trainers",
        "image_url": "/demo-looks/gym.jpg",
        "style": "High-Performance Activewear",
        "items": [
            {
                "id": "item_tee",
                "label": "Seamless Moisture-Wicking Tee",
                "category": "outwear",
                "box": [0.15, 0.25, 0.50, 0.75],
                "dominant_colors": ["#183050", "#286090"],
                "keywords": ["shirt", "tee", "training", "athletic", "navy", "top"],
            },
            {
                "id": "item_shorts",
                "label": "2-in-1 Lined Performance Shorts",
                "category": "outwear",
                "box": [0.46, 0.30, 0.72, 0.70],
                "dominant_colors": ["#141414", "#303030"],
                "keywords": ["shorts", "compression", "running", "athletic", "black"],
            },
            {
                "id": "item_shoes",
                "label": "Cushioned Road Running Trainers",
                "category": "footwear",
                "box": [0.72, 0.22, 0.96, 0.78],
                "dominant_colors": ["#F0F0F0", "#3080E0"],
                "keywords": ["running", "shoes", "sneakers", "trainers", "blue", "white"],
            },
            {
                "id": "item_bottle",
                "label": "Insulated Stainless Steel Water Bottle",
                "category": "sports",
                "box": [0.40, 0.76, 0.62, 0.88],
                "dominant_colors": ["#C0C0C0", "#141414"],
                "keywords": ["bottle", "water", "stainless", "insulated", "sports"],
            },
        ],
    },
    "weekend_casual": {
        "id": "weekend_casual",
        "title": "Weekend Denim & Leather Casual",
        "subtitle": "Classic denim trucker jacket, heavy cotton tee & Chelsea boots",
        "image_url": "/demo-looks/casual.jpg",
        "style": "Timeless Casual Everyday",
        "items": [
            {
                "id": "item_jacket",
                "label": "Washed Indigo Denim Trucker Jacket",
                "category": "outwear",
                "box": [0.14, 0.22, 0.54, 0.78],
                "dominant_colors": ["#204575", "#3A6090"],
                "keywords": ["denim", "jacket", "indigo", "blue", "trucker", "casual"],
            },
            {
                "id": "item_boots",
                "label": "Full-Grain Leather Chelsea Boots",
                "category": "footwear",
                "box": [0.74, 0.24, 0.96, 0.76],
                "dominant_colors": ["#5A3520", "#382012"],
                "keywords": ["boots", "chelsea", "leather", "brown", "shoes"],
            },
            {
                "id": "item_tee",
                "label": "Heavyweight Vintage White Pocket Tee",
                "category": "outwear",
                "box": [0.22, 0.35, 0.48, 0.65],
                "dominant_colors": ["#F8F7F2", "#ECE8DC"],
                "keywords": ["t-shirt", "tee", "white", "cotton", "pocket"],
            },
            {
                "id": "item_watch",
                "label": "Minimalist Field Watch with Olive Strap",
                "category": "jewelry",
                "box": [0.45, 0.16, 0.56, 0.28],
                "dominant_colors": ["#646E28", "#1E1E1E"],
                "keywords": ["watch", "field", "olive", "strap", "minimalist"],
            },
        ],
    },
}


def _color_distance(c1: tuple[int, int, int], c2: tuple[int, int, int]) -> float:
    """Calculates weighted Euclidean distance between two RGB colors (favoring human perception)."""
    r1, g1, b1 = c1
    r2, g2, b2 = c2
    r_mean = (r1 + r2) / 2.0
    dr = r1 - r2
    dg = g1 - g2
    db = b1 - b2
    return math.sqrt(
        (2.0 + r_mean / 256.0) * dr * dr
        + 4.0 * dg * dg
        + (2.0 + (255.0 - r_mean) / 256.0) * db * db
    )


def rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}".upper()


def match_color_name(rgb: tuple[int, int, int]) -> str:
    """Finds the closest human-friendly color name for an RGB tuple."""
    closest_name = "Neutral"
    min_dist = float("inf")
    for name, candidate_rgb in NAMED_COLORS:
        dist = _color_distance(rgb, candidate_rgb)
        if dist < min_dist:
            min_dist = dist
            closest_name = name
    return closest_name


def extract_dominant_palette(
    image: Image.Image, num_colors: int = 5
) -> list[dict[str, Any]]:
    """Extracts dominant color palette and percentages from a PIL Image."""
    # Resize small for high-speed color quantization
    thumb = image.copy()
    thumb.thumbnail((120, 120))
    thumb = thumb.convert("RGB")

    # Quantize down to 16 colors to cluster pixels
    quantized = thumb.quantize(colors=16, method=Image.Quantize.FASTOCTREE)
    palette_raw = quantized.getpalette() or []
    counts = quantized.getcolors() or []

    if not counts:
        return [{"hex": "#808080", "name": "Gray", "percentage": 100}]

    total_pixels = sum(count for count, _ in counts)
    sorted_counts = sorted(counts, key=lambda x: x[0], reverse=True)

    extracted: list[dict[str, Any]] = []
    seen_names: set[str] = set()

    for count, idx in sorted_counts:
        r = palette_raw[idx * 3]
        g = palette_raw[idx * 3 + 1]
        b = palette_raw[idx * 3 + 2]
        color_name = match_color_name((r, g, b))
        percentage = round((count / total_pixels) * 100, 1)

        # Merge visually identical colors
        if color_name in seen_names and len(extracted) >= num_colors:
            continue

        seen_names.add(color_name)
        extracted.append(
            {
                "hex": rgb_to_hex(r, g, b),
                "name": color_name,
                "percentage": percentage,
                "rgb": [r, g, b],
            }
        )
        if len(extracted) >= num_colors:
            break

    return extracted


def subject_for(result: dict[str, Any], box: list[float]) -> dict[str, Any] | None:
    """A whole-image/crop classification, never a fabricated object bounding box."""
    if not result['category'] or float(result['score']) < 0.20 or float(result['margin']) < 0.015:
        return None
    return {
        'id': 'subject', 'label': result['label'], 'category': result['category'],
        'confidence': None, 'box': box, 'dominant_colors': [],
        'keywords': [result['label'].lower()],
    }


def analyze_image_regions(image: Image.Image) -> list[dict[str, Any]]:
    """Recognize one subject; this is not multi-object detection."""
    from product.local_vision import recognize

    item = subject_for(recognize(image), [0.0, 0.0, 1.0, 1.0])
    return [item] if item else []


class VisualSearchEngine:
    """
    Local subject recognition and bounded image-to-description catalog ranking.
    Preset examples use explicit metadata, never fabricated recognition scores.
    """

    MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MiB
    ALLOWED_IMAGE_FORMATS = {"JPEG", "JPG", "PNG", "WEBP"}

    @classmethod
    def load_and_validate_image(cls, file_obj: Any) -> Image.Image:
        """Validates uploaded image size, format, orientation, and decodes into a clean RGB PIL Image."""
        if hasattr(file_obj, "size") and file_obj.size > cls.MAX_FILE_SIZE_BYTES:
            raise ValidationError("Image file exceeds maximum allowed size of 5MB.")

        raw_bytes = file_obj.read(cls.MAX_FILE_SIZE_BYTES + 1) if hasattr(file_obj, "read") else bytes(file_obj)
        if len(raw_bytes) > cls.MAX_FILE_SIZE_BYTES:
            raise ValidationError("Image file exceeds maximum allowed size of 5MB.")

        try:
            image = Image.open(io.BytesIO(raw_bytes))
            if image.width * image.height > 16_000_000:
                raise ValidationError('Image dimensions are too large. Use an image under 16 megapixels.')
            image.verify()
        except ValidationError:
            raise
        except Exception as err:
            raise ValidationError("Uploaded file is not a valid or readable image.") from err

        # Header verification is not a full pixel decode (notably for JPEG).
        try:
            with Image.open(io.BytesIO(raw_bytes)) as source:
                if (source.format or "").upper() not in cls.ALLOWED_IMAGE_FORMATS:
                    raise ValidationError('Supported image formats are JPEG, PNG, and WebP.')
                image = ImageOps.exif_transpose(source).convert('RGB')
                image.load()
                image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
        except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as error:
            raise ValidationError('Uploaded file is not a valid or readable image.') from error

        return image

    @classmethod
    def analyze_look(
        cls, image: Image.Image, focus_box: list[float] | None = None,
        selected_item_id: str | None = None, user_query: str = "",
        category_filter: str = "", store_id: int | None = None,
    ) -> dict[str, Any]:
        from product.local_vision import recognize, rank

        box = focus_box or [0.0, 0.0, 1.0, 1.0]
        if (len(box) != 4 or not all(math.isfinite(v) and 0 <= v <= 1 for v in box)
                or box[0] >= box[2] or box[1] >= box[3]):
            raise ValidationError({'focus_box': 'Choose a valid image crop.'})
        if focus_box:
            width, height = image.size
            bounds = (int(box[1] * width), int(box[0] * height),
                      int(box[3] * width), int(box[2] * height))
            if bounds[0] >= bounds[2] or bounds[1] >= bounds[3]:
                raise ValidationError({'focus_box': 'Choose a larger image crop.'})
            image = image.crop(bounds)
        prediction = recognize(image)
        item = subject_for(prediction, box)
        choices: list[dict[str, Any]] = []
        if item:
            choices = [item]
        else:
            from django.utils.text import slugify

            choices = [
                {
                    'id': f"candidate-{slugify(candidate['label'])}",
                    'label': candidate['label'], 'category': candidate['category'],
                    'confidence': None, 'box': box, 'dominant_colors': [],
                    'keywords': [candidate['label'].lower()],
                }
                for candidate in prediction.get('alternatives', [])
            ]
        if selected_item_id:
            item = next((choice for choice in choices if choice['id'] == selected_item_id), None)
            if item is None:
                raise ValidationError({'item_id': 'Choose one of the suggested items for this photo.'})
        results: list[dict[str, Any]] = []
        message = 'No reliable product subject was recognized. Try a clearer, closer photo or text search.'
        if choices and item is None:
            message = 'Possible items found. Choose what you want to search for; these suggestions are not confirmed detections.'
        if item:
            candidates = cls.candidates(item['category'], store_id, user_query, item['label'])
            if category_filter and category_filter != item['category']:
                candidates = []
            descriptors = [
                {'id': product.pk, 'text': f"A photo of {product.title}, {product.brand}, {product.get_category_display()}"[:512]}
                for product in candidates
            ]
            ranked = rank(prediction['embedding'], descriptors)
            # Hydrate authoritative product data again after potentially slow inference.
            current_products = cls.public_products().filter(category=item['category'])
            if store_id:
                current_products = current_products.filter(store_id=store_id)
            if user_query:
                current_products = current_products.filter(
                    Q(title__icontains=user_query) | Q(tags__name__icontains=user_query)
                ).distinct()
            current_products = cls.filter_subject(current_products, item['label'])
            current = current_products.in_bulk([row['id'] for row in ranked])
            for row in ranked:
                product = current.get(row['id'])
                if float(row['score']) < 0.18 or product is None:
                    continue
                results.append({
                    'product': product, 'product_id': product.pk, 'similarity_score': None,
                    'match_reasons': ['Local image-to-description semantic ranking'],
                })
                if len(results) == 24:
                    break
            origin = 'Searching your selected item' if selected_item_id and item['id'].startswith('candidate-') else 'Recognized subject'
            message = (
                f"{origin}: {item['label']}. Related catalog items are ranked against their descriptions, not verified identical photos."
                if results else f"{origin}: {item['label']}, but no relevant catalog items were found."
            )
        return {
            'palette': extract_dominant_palette(image, num_colors=6),
            'detected_items': choices,
            'selected_item_id': item['id'] if item else None, 'selected_item': item,
            'results': results, 'query_applied': user_query or (item['label'] if item else ''),
            'method': 'local_clip', 'message': message,
            'selection_required': bool(choices and item is None),
        }

    @classmethod
    def public_products(cls) -> QuerySet[Product]:
        return Product.objects.filter(
            visibility=True, is_blocked=False, store__status=Store.STATUS_ACTIVE,
            store__verified_at__isnull=False,
        ).select_related('store', 'specification').prefetch_related('images', 'tags')

    @classmethod
    def filter_subject(cls, products: QuerySet[Product], label: str) -> QuerySet[Product]:
        if not label:
            return products
        from product.visual_retrieval import subject_title_filter

        return products.filter(subject_title_filter(label))

    @classmethod
    def candidates(cls, category: str, store_id: int | None, query: str = '', subject_label: str = '') -> list[Product]:
        products = cls.public_products().filter(category=category)
        if store_id:
            products = products.filter(store_id=store_id)
        if query:
            products = products.filter(Q(title__icontains=query) | Q(tags__name__icontains=query)).distinct()
        return list(cls.filter_subject(products, subject_label).order_by('-created', '-pk')[:256])

    @classmethod
    def match_products(
        cls, target_category: str, target_colors: list[str],
        target_keywords: list[str], user_query: str = "",
        store_id: int | None = None, limit: int = 24,
    ) -> list[dict[str, Any]]:
        """Curated preset browsing only; no recognition/confidence claims."""
        # Footwear is represented by outwear in the authoritative catalog.
        category = 'outwear' if target_category == 'footwear' else target_category
        products = cls.public_products().filter(category=category)
        if store_id:
            products = products.filter(store_id=store_id)
        tokens = [token for token in target_keywords if len(token) >= 3]
        if user_query:
            tokens.extend(re.findall(r'\b[a-zA-Z]+\b', user_query))
        if tokens:
            conditions = Q()
            for token in tokens:
                conditions |= Q(title__icontains=token) | Q(tags__name__icontains=token)
            products = products.filter(conditions).distinct()
        return [
            {'product': product, 'product_id': product.pk, 'similarity_score': None,
             'match_reasons': ['Curated example: category and catalog text, not image recognition']}
            for product in products.order_by('-average_rating', '-created', '-pk')[:limit]
        ]

    @classmethod
    def get_preset_look(cls, preset_id: str) -> dict[str, Any] | None:
        """Returns metadata and pre-configured detected hotspots for sample showcase looks."""
        return PRESET_LOOKS.get(preset_id)
