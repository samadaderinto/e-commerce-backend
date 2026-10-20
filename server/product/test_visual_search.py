from __future__ import annotations

import io
from decimal import Decimal
import pytest
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework.exceptions import ValidationError

from core.models import User
from product.models import Product, Specification
from product.visual_search import VisualSearchEngine, extract_dominant_palette, analyze_image_regions
from store.models import Store


def create_test_image(format="JPEG", size=(300, 400), color=(20, 20, 20)) -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", size, color=color)
    img.save(buf, format=format)
    return buf.getvalue()


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def seller_user(db) -> User:
    return User.objects.create_user(
        email="merchant-visual@proace.local",
        password="TestPassword123!",
        first_name="Visual",
        last_name="Merchant",
    )


@pytest.fixture
def active_store(db, seller_user) -> Store:
    return Store.objects.create(
        user=seller_user,
        name="Aesthetic Studio",
        username="aesthetic-studio",
        status=Store.STATUS_ACTIVE,
        verified_at="2026-01-01T00:00:00Z",
    )


@pytest.fixture
def sample_products(db, active_store) -> list[Product]:
    p1 = Product.objects.create(
        store=active_store,
        title="Midnight Urban Bomber Jacket",
        category="outwear",
        brand="ProAce Apparel",
        price=Decimal("120.00"),
        discount=0,
        available=15,
        visibility=True,
    )
    p1.tags.add("jacket", "bomber", "black", "outerwear")
    Specification.objects.create(product=p1, color="Black", height=10, width=10, breadth=10, weight=1, serial="SPEC-V001")

    p2 = Product.objects.create(
        store=active_store,
        title="Chunky Cloud Leather Low-Top Sneakers",
        category="outwear",
        brand="Apex Footwear",
        price=Decimal("95.00"),
        discount=0,
        available=20,
        visibility=True,
    )
    p2.tags.add("sneakers", "shoes", "white", "chunky", "footwear")
    Specification.objects.create(product=p2, color="White", height=10, width=10, breadth=10, weight=1, serial="SPEC-V002")

    p3 = Product.objects.create(
        store=active_store,
        title="Solid Natural White Oak Workstation Desk",
        category="home",
        brand="Nordic Home",
        price=Decimal("380.00"),
        discount=0,
        available=5,
        visibility=True,
    )
    p3.tags.add("desk", "oak", "wood", "workspace", "furniture")
    Specification.objects.create(product=p3, color="Tan", height=10, width=10, breadth=10, weight=1, serial="SPEC-V003")

    return [p1, p2, p3]


@pytest.mark.django_db
class TestVisualSearchEngine:
    def test_image_validation_valid(self):
        raw = create_test_image(format="JPEG", size=(200, 200))
        img = VisualSearchEngine.load_and_validate_image(io.BytesIO(raw))
        assert isinstance(img, Image.Image)
        assert img.mode == "RGB"

    def test_image_validation_rejects_corrupted_data(self):
        with pytest.raises(ValidationError) as exc:
            VisualSearchEngine.load_and_validate_image(b"not-an-image-payload")
        assert "not a valid or readable image" in str(exc.value)

    def test_truncated_jpeg_with_valid_headers_is_a_validation_error(self) -> None:
        raw = create_test_image(format='JPEG', size=(300, 400))[:-50]
        with pytest.raises(ValidationError):
            VisualSearchEngine.load_and_validate_image(io.BytesIO(raw))

    def test_image_validation_rejects_oversized_file(self):
        large_bytes = b"x" * (VisualSearchEngine.MAX_FILE_SIZE_BYTES + 100)
        with pytest.raises(ValidationError) as exc:
            VisualSearchEngine.load_and_validate_image(large_bytes)
        assert "exceeds maximum allowed size" in str(exc.value)

    def test_palette_extraction(self):
        # Create image with pure blue (0, 0, 255)
        raw = create_test_image(format="PNG", size=(100, 100), color=(25, 55, 130))
        img = Image.open(io.BytesIO(raw))
        palette = extract_dominant_palette(img, num_colors=3)
        assert len(palette) >= 1
        assert "Blue" in palette[0]["name"] or "Navy" in palette[0]["name"]
        assert palette[0]["percentage"] > 80

    def test_region_analysis_uses_model_not_aspect_ratio(self, monkeypatch):
        monkeypatch.setattr("product.local_vision.recognize", lambda image: {
            "label": "Book", "category": "books", "score": 0.30, "margin": 0.08,
        })
        for size in [(300, 500), (500, 300)]:
            items = analyze_image_regions(Image.new("RGB", size, "red"))
            assert len(items) == 1
            assert items[0]["label"] == "Book"
            assert items[0]["confidence"] is None
            assert items[0]["box"] == [0, 0, 1, 1]


@pytest.mark.django_db
class TestVisualSearchApi:
    def test_truncated_jpeg_upload_returns_clean_400(self, api_client: APIClient) -> None:
        response = api_client.post('/api/v1/products/visual-search/', {
            'image': SimpleUploadedFile(
                'truncated.jpg', create_test_image(format='JPEG')[:-50],
                content_type='image/jpeg',
            ),
        }, format='multipart')
        assert response.status_code == 400
        assert 'OSError' not in str(response.data)
        assert 'truncated (' not in str(response.data)

    def test_get_presets_returns_curated_looks(self, api_client):
        res = api_client.get("/api/v1/products/visual-search/presets/")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        assert len(data) >= 3
        preset_ids = [p["id"] for p in data]
        assert "urban_streetwear" in preset_ids
        assert "minimal_workspace" in preset_ids

    def test_search_with_preset_id(self, api_client, sample_products):
        res = api_client.post(
            "/api/v1/products/visual-search/",
            {"preset_id": "urban_streetwear", "item_id": "item_jacket"},
            format="multipart",
        )
        assert res.status_code == 200
        data = res.json()
        assert "detected_items" in data
        assert "results" in data
        assert "palette" in data
        assert data["selected_item_id"] == "item_jacket"
        # The bomber jacket should be ranked at or near the top
        assert len(data["results"]) >= 1
        top_match = data["results"][0]
        assert "Bomber Jacket" in top_match["product"]["title"]
        assert top_match["similarity_score"] is None
        assert data["method"] == "preset_metadata"
        assert len(top_match["match_reasons"]) >= 1

    @pytest.mark.parametrize("score,margin", [(0.30, 0.08), (0.10, 0.08), (0.30, 0.001)])
    def test_book_never_returns_unrelated_categories(
        self, api_client, sample_products, active_store, monkeypatch, score, margin,
    ):
        book = Product.objects.create(
            store=active_store, title="Red Paper Book", category="books",
            price=Decimal("12.00"), discount=0, available=5, visibility=True,
        )
        monkeypatch.setattr("product.local_vision.recognize", lambda image: {
            "label": "Book", "category": "books", "score": score,
            "margin": margin, "embedding": [1.0] + [0.0] * 511,
        })

        def rank(embedding: list[float], candidates: list[dict]) -> list[dict]:
            assert all(row["id"] == book.pk for row in candidates)
            return [{"id": row["id"], "score": 0.31} for row in candidates]

        monkeypatch.setattr("product.local_vision.rank", rank)
        res = api_client.post("/api/v1/products/visual-search/", {
            "image": SimpleUploadedFile("book.jpg", create_test_image(), content_type="image/jpeg"),
        }, format="multipart")
        assert res.status_code == 200
        data = res.json()
        assert data["method"] == "local_clip"
        if score >= 0.20 and margin >= 0.015:
            assert data["selected_item"]["label"] == "Book"
            assert [row["product"]["id"] for row in data["results"]] == [book.pk]
            assert data["results"][0]["similarity_score"] is None
        else:
            assert data["detected_items"] == []
            assert data["results"] == []

    def test_unavailable_model_does_not_guess(self, api_client, settings):
        settings.LOCAL_VISION_URL = ""
        res = api_client.post("/api/v1/products/visual-search/", {
            "image": SimpleUploadedFile("book.jpg", create_test_image(), content_type="image/jpeg"),
        }, format="multipart")
        assert res.status_code == 503
        assert "text search" in str(res.json()).lower()

    @pytest.mark.parametrize("box", ["[0,0,0,1]", "[0,0,2,1]", "[0,0,NaN,1]", "null", "{}"])
    def test_invalid_crop_rejected(self, api_client, box):
        res = api_client.post("/api/v1/products/visual-search/", {
            "image": SimpleUploadedFile("book.jpg", create_test_image(), content_type="image/jpeg"),
            "focus_box": box,
        }, format="multipart")
        assert res.status_code == 400

    def test_candidates_exclude_nonpublic_products(self, sample_products, active_store):
        product = sample_products[0]
        assert product in VisualSearchEngine.candidates("outwear", None)
        product.is_blocked = True
        product.save(update_fields=["is_blocked"])
        assert product not in VisualSearchEngine.candidates("outwear", None)
        active_store.verified_at = None
        active_store.save(update_fields=["verified_at"])
        assert VisualSearchEngine.candidates("outwear", None) == []

    def test_search_requires_image_or_preset(self, api_client):
        res = api_client.post(
            "/api/v1/products/visual-search/",
            {"query": "just a query without image"},
            format="multipart",
        )
        assert res.status_code == 400
        data = res.json()
        assert "image" in data or "image" in str(data)
