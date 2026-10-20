"""A high semantic score cannot override a contradictory catalog item type."""

from decimal import Decimal
from typing import Any

import pytest
from django.utils import timezone
from PIL import Image

from core.models import User
from product.models import Product
from product.visual_labels import VISUAL_SUBJECTS
from product.visual_retrieval import SUBJECT_TITLE_PATTERNS
from product.visual_search import VisualSearchEngine
from store.models import Store

pytestmark = pytest.mark.django_db


@pytest.fixture
def store() -> Store:
    user = User.objects.create_user(
        email="shoe-fixture@example.test", password="fixture-only"
    )
    return Store.objects.create(
        user=user, name="Subject fixture", status="active", verified_at=timezone.now()
    )


def product(
    store: Store, title: str, description: str = "", category: str = "outwear"
) -> Product:
    return Product.objects.create(
        store=store,
        title=title,
        description=description,
        category=category,
        price=Decimal("30"),
        discount=0,
        available=3,
        visibility=True,
    )


@pytest.mark.parametrize(
    "label,title,category",
    [
        ("Shoes", "Brown leather Oxford shoes", "outwear"),
        ("Shoes", "Chunky sole derby brogues", "outwear"),
        ("Jacket", "Waxed field safari parka", "outwear"),
        ("Shirt", "Organic cotton polo", "outwear"),
        ("Trousers", "Relaxed denim jeans", "outwear"),
        ("Watch", "Automatic wristwatch", "jewelry"),
        ("Table", "Oak workstation desk", "home"),
    ],
)
def test_subject_gate_accepts_product_type_synonyms(
    store: Store, label: str, title: str, category: str
) -> None:
    expected = product(store, title, category=category)
    assert list(VisualSearchEngine.candidates(category, None, subject_label=label)) == [
        expected
    ]


def test_shoe_search_rejects_coats_even_if_description_mentions_shoes(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    shoes = product(store, "Brown leather lace-up Oxford shoes")
    product(
        store,
        "Waxed field utility safari parka",
        "Looks great with leather shoes and boots.",
    )
    monkeypatch.setattr(
        "product.local_vision.recognize",
        lambda image: {
            "label": "Shoes",
            "category": "outwear",
            "score": 0.35,
            "margin": 0.08,
            "embedding": [1.0] + [0.0] * 511,
        },
    )

    def rank(
        embedding: list[float], rows: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        assert [row["id"] for row in rows] == [shoes.pk]
        return [{"id": shoes.pk, "score": 0.8}]

    monkeypatch.setattr("product.local_vision.rank", rank)
    result = VisualSearchEngine.analyze_look(Image.new("RGB", (200, 200)))
    assert result["selected_item"]["label"] == "Shoes"
    assert [row["product_id"] for row in result["results"]] == [shoes.pk]


def test_no_shoes_returns_empty_instead_of_jackets(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    product(store, "Safari parka")
    monkeypatch.setattr(
        "product.local_vision.recognize",
        lambda image: {
            "label": "Shoes",
            "category": "outwear",
            "score": 0.35,
            "margin": 0.08,
            "embedding": [1.0] + [0.0] * 511,
        },
    )
    monkeypatch.setattr("product.local_vision.rank", lambda embedding, rows: [])
    result = VisualSearchEngine.analyze_look(Image.new("RGB", (200, 200)))
    assert result["selected_item"]["label"] == "Shoes"
    assert result["results"] == []


def test_subject_gate_is_rechecked_after_model_call(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    shoes = product(store, "Leather Oxford shoes")
    monkeypatch.setattr(
        "product.local_vision.recognize",
        lambda image: {
            "label": "Shoes",
            "category": "outwear",
            "score": 0.35,
            "margin": 0.08,
            "embedding": [1.0] + [0.0] * 511,
        },
    )

    def rank(
        embedding: list[float], rows: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        Product.objects.filter(pk=shoes.pk).update(title="Safari parka")
        return [{"id": shoes.pk, "score": 0.9}]

    monkeypatch.setattr("product.local_vision.rank", rank)
    assert (
        VisualSearchEngine.analyze_look(Image.new("RGB", (200, 200)))["results"] == []
    )


def test_all_product_labels_have_a_retrieval_rule() -> None:
    assert {label for label, category, _ in VISUAL_SUBJECTS if category} == set(
        SUBJECT_TITLE_PATTERNS
    )


def test_unknown_subject_never_falls_back_to_whole_category(store: Store) -> None:
    product(store, "Safari parka")
    assert (
        VisualSearchEngine.candidates("outwear", None, subject_label="Unknown object")
        == []
    )


@pytest.mark.parametrize(
    "label,title,category",
    [
        ("Shoes", "Shoe care cleaning kit", "outwear"),
        ("Shoes", "Leather shoe storage bag", "outwear"),
        ("Dress", "Brown leather dress shoes", "outwear"),
        ("Watch", "Leather watch strap", "jewelry"),
    ],
)
def test_accessories_and_compound_names_do_not_imply_the_main_item(
    store: Store,
    label: str,
    title: str,
    category: str,
) -> None:
    product(store, title, category=category)
    assert VisualSearchEngine.candidates(category, None, subject_label=label) == []
