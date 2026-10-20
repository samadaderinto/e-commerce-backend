"""Ambiguous photos offer bounded choices instead of invented detections."""

from decimal import Decimal
from unittest.mock import Mock

import pytest
from PIL import Image
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from core.models import User
from product.models import Product
from product.visual_search import VisualSearchEngine
from store.models import Store


@pytest.fixture
def ambiguous_prediction(monkeypatch: pytest.MonkeyPatch) -> Mock:
    monkeypatch.setattr(
        "product.local_vision.recognize",
        lambda image: {
            "label": "Person",
            "category": "",
            "score": 0.255,
            "margin": 0.009,
            "embedding": [1.0] + [0.0] * 511,
            "alternatives": [
                {
                    "label": "Suit jacket / blazer",
                    "category": "outwear",
                    "score": 0.247,
                },
                {"label": "Shirt", "category": "outwear", "score": 0.245},
            ],
        },
    )
    rank = Mock(return_value=[])
    monkeypatch.setattr("product.local_vision.rank", rank)
    return rank


def test_ambiguous_person_photo_offers_choices_without_search(
    ambiguous_prediction: Mock,
) -> None:
    result = VisualSearchEngine.analyze_look(Image.new("RGB", (200, 200)))
    assert result["selection_required"] is True
    assert result["selected_item"] is None
    assert result["selected_item_id"] is None
    assert result["results"] == []
    assert result["detected_items"][0]["label"] == "Suit jacket / blazer"
    assert all(item["confidence"] is None for item in result["detected_items"])
    ambiguous_prediction.assert_not_called()


@pytest.mark.django_db
def test_selected_blazer_search_does_not_fall_back_to_unrelated_clothing(
    ambiguous_prediction: Mock,
) -> None:
    seller = User.objects.create_user(
        email="suit-fixture@example.test", password="fixture-only"
    )
    store = Store.objects.create(
        user=seller, name="Suit fixtures", status="active", verified_at=timezone.now()
    )
    blazer = Product.objects.create(
        store=store,
        title="Tailored navy blazer",
        category="outwear",
        price=Decimal("80"),
        discount=0,
        available=2,
        visibility=True,
    )
    Product.objects.create(
        store=store,
        title="Plain cotton T-shirt",
        category="outwear",
        price=Decimal("10"),
        discount=0,
        available=2,
        visibility=True,
    )
    Product.objects.create(
        store=store,
        title="Casual cotton tracksuit",
        category="outwear",
        price=Decimal("30"),
        discount=0,
        available=2,
        visibility=True,
    )
    ambiguous_prediction.side_effect = lambda embedding, rows: [
        {"id": row["id"], "score": 0.30} for row in rows
    ]
    result = VisualSearchEngine.analyze_look(
        Image.new("RGB", (200, 200)),
        selected_item_id="candidate-suit-jacket-blazer",
    )
    assert result["selection_required"] is False
    assert result["selected_item"]["label"] == "Suit jacket / blazer"
    assert [row["product_id"] for row in result["results"]] == [blazer.pk]
    assert result["message"].startswith("Searching your selected item:")


@pytest.mark.django_db
def test_selected_blazer_without_catalog_match_stays_selected(
    ambiguous_prediction: Mock,
) -> None:
    result = VisualSearchEngine.analyze_look(
        Image.new("RGB", (200, 200)),
        selected_item_id="candidate-suit-jacket-blazer",
    )
    assert result["selected_item_id"] == "candidate-suit-jacket-blazer"
    assert result["results"] == []
    assert "no relevant catalog items" in result["message"]


def test_unoffered_selection_is_rejected(ambiguous_prediction: Mock) -> None:
    with pytest.raises(ValidationError):
        VisualSearchEngine.analyze_look(
            Image.new("RGB", (200, 200)), selected_item_id="candidate-watch"
        )
    ambiguous_prediction.assert_not_called()
